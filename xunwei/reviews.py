from datetime import datetime
from flask import (Blueprint, current_app as app, abort, flash, g, jsonify,
                   redirect, render_template, request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash
from .db import get_db
from .security import login_required, admin_required, safe_next
from .services import recalculate_restaurant
from .services import audit

bp = Blueprint("reviews", __name__)


@bp.post('/restaurant/<int:rid>/dish/<int:did>/review')
@login_required
def add_dish_review(rid, did):
    db = get_db()
    if not db.execute('SELECT 1 FROM dishes WHERE id=? AND restaurant_id=?', (did, rid)).fetchone():
        abort(404)
    rating = request.form.get('rating', type=int)
    content = (request.form.get('content') or '').strip()
    if rating not in range(1, 6) or not 5 <= len(content) <= 500:
        flash('请选择 1~5 星，并填写 5~500 字菜品评价。', 'error')
        return redirect(url_for('catalog.dish_detail', rid=rid, did=did, _anchor='write-dish-review'))
    db.execute('''INSERT INTO dish_reviews(dish_id,user_id,rating,content,created_at)
        VALUES (?,?,?,?,?)''', (did, g.user['id'], rating, content, datetime.now().strftime('%Y-%m-%d %H:%M')))
    db.commit()
    flash('菜品评价已发布。', 'success')
    return redirect(url_for('catalog.dish_detail', rid=rid, did=did))


@bp.post('/dish-review/<int:review_id>/delete')
@login_required
def delete_dish_review(review_id):
    db = get_db()
    review = db.execute('''SELECT dr.*,d.restaurant_id FROM dish_reviews dr
        JOIN dishes d ON d.id=dr.dish_id WHERE dr.id=?''', (review_id,)).fetchone()
    if review is None:
        abort(404)
    if g.user['role'] != 'admin' and review['user_id'] != g.user['id']:
        abort(403)
    db.execute('DELETE FROM dish_reviews WHERE id=?', (review_id,))
    if g.user['role'] == 'admin':
        audit('删除菜品评价', review_id)
    db.commit()
    flash('菜品评价已删除，评分已更新。', 'success')
    return redirect(url_for('catalog.dish_detail', rid=review['restaurant_id'], did=review['dish_id']))

# ---------------------------------------------------------------- 发布点评
@bp.route("/restaurant/<int:rid>/review", methods=["POST"])
def add_review(rid):
    if g.user is None:
        flash("登录后才能发布点评", "error")
        return redirect(url_for("accounts.login", next=url_for("catalog.detail", rid=rid)))
    db = get_db()
    r = db.execute("SELECT id FROM restaurants WHERE id = ?", (rid,)).fetchone()
    if r is None:
        flash("未找到该餐厅", "error")
        return redirect(url_for("catalog.index"))

    author = g.user["username"]
    content = (request.form.get("content") or "").strip()

    def _score(field):
        try:
            return int(request.form.get(field))
        except (TypeError, ValueError):
            return None

    rating = _score("rating")
    taste = _score("taste_score") if "taste_score" in request.form else rating
    env = _score("environment_score") if "environment_score" in request.form else rating
    service = _score("service_score") if "service_score" in request.form else rating

    errors = []
    if rating not in (1, 2, 3, 4, 5):
        errors.append("请选择 1~5 星的综合评分")
    if not 5 <= len(content) <= 500:
        errors.append("点评内容需为 5~500 个字符")
    for v in (taste, env, service):
        if v not in (1, 2, 3, 4, 5):
            errors.append("分项评分需为 1~5 星")

    if errors:
        for e in errors:
            flash(e, "error")
        return redirect(url_for("catalog.detail", rid=rid))

    db.execute(
        """INSERT INTO reviews
           (restaurant_id, author, rating, taste_score, environment_score,
            service_score, content, created_at, user_id, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'visible')""",
        (rid, author, rating, taste, env, service, content,
         datetime.now().strftime("%Y-%m-%d %H:%M"), g.user["id"]),
    )
    recalculate_restaurant(rid)
    db.commit()
    flash("点评发布成功，感谢分享！", "success")
    return redirect(url_for("catalog.detail", rid=rid))

def owned_review(review_id):
    review = get_db().execute("SELECT * FROM reviews WHERE id=?", (review_id,)).fetchone()
    if review is None:
        abort(404)
    if g.user["role"] != "admin" and review["user_id"] != g.user["id"]:
        abort(403)
    return review


@bp.route("/review/<int:review_id>/edit", methods=["GET", "POST"])
@login_required
def edit_review(review_id):
    review = owned_review(review_id)
    if request.method == "POST":
        try:
            values = tuple(int(request.form.get(k, 0)) for k in ("rating", "taste_score", "environment_score", "service_score"))
        except ValueError:
            values = ()
        content = (request.form.get("content") or "").strip()
        if len(values) != 4 or any(v not in range(1, 6) for v in values) or not 5 <= len(content) <= 500:
            flash("请填写有效评分和 5~500 字点评", "error")
        else:
            get_db().execute("""UPDATE reviews SET rating=?,taste_score=?,environment_score=?,service_score=?,content=?
                                WHERE id=?""", values + (content, review_id))
            if g.user['role'] == 'admin':
                audit('编辑点评', review_id)
            recalculate_restaurant(review["restaurant_id"])
            get_db().commit()
            flash("点评已更新", "success")
            return redirect(url_for("accounts.profile"))
    return render_template("review_edit.html", review=review)


@bp.post("/review/<int:review_id>/delete")
@login_required
def delete_review(review_id):
    review = owned_review(review_id)
    get_db().execute("DELETE FROM reviews WHERE id=?", (review_id,))
    if g.user['role'] == 'admin':
        audit('删除点评', review_id)
    recalculate_restaurant(review["restaurant_id"])
    get_db().commit()
    flash("点评已删除", "success")
    return redirect(url_for("admin.admin_dashboard" if g.user["role"] == "admin" else "accounts.profile"))
