from datetime import date, datetime, timedelta
from flask import (Blueprint, current_app as app, abort, flash, g, jsonify,
                   redirect, render_template, request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash
from .db import get_db
from .security import login_required, admin_required, safe_next
from .services import recalculate_restaurant
from .services import audit

bp = Blueprint("admin", __name__)
THEMES = {
    'warm': ('暖橙', 'linear-gradient(135deg,#ff9a5a,#e6533f)'),
    'green': ('青绿', 'linear-gradient(135deg,#43c6ac,#2a7faa)'),
    'purple': ('紫藤', 'linear-gradient(135deg,#c471ed,#6a4fb5)'),
    'pink': ('樱粉', 'linear-gradient(135deg,#fbc2eb,#f78fb3)'),
}


@bp.route('/admin/sales', methods=['GET', 'POST'])
@admin_required
def sales():
    from .discovery import today
    db = get_db()
    current = today()
    if request.method == 'POST':
        rid = request.form.get('restaurant_id', type=int)
        quantity = request.form.get('quantity', type=int)
        try:
            sale_date = date.fromisoformat(request.form.get('sale_date', ''))
        except ValueError:
            abort(400)
        if quantity is None or not 0 <= quantity <= 1000000 or sale_date > current:
            abort(400)
        if not db.execute('SELECT 1 FROM restaurants WHERE id=?', (rid,)).fetchone():
            abort(404)
        db.execute('''INSERT INTO daily_sales(restaurant_id,sale_date,quantity,source,updated_at)
            VALUES (?,?,?,'manual',?) ON CONFLICT(restaurant_id,sale_date) DO UPDATE
            SET quantity=excluded.quantity,source='manual',updated_at=excluded.updated_at''',
            (rid, sale_date.isoformat(), quantity, datetime.now().isoformat(timespec='seconds')))
        audit('保存日销量', f'{rid}/{sale_date}/{quantity}')
        db.commit()
        flash('日销量已保存，同一天重复录入会更新总量，不会叠加。', 'success')
        return redirect(url_for('admin.sales'))
    total = db.execute('SELECT COUNT(*) FROM daily_sales').fetchone()[0]
    pages = max(1, (total + 29) // 30)
    page = min(max(request.args.get('page', 1, type=int), 1), pages)
    records = db.execute('''SELECT s.*,r.name FROM daily_sales s JOIN restaurants r ON r.id=s.restaurant_id
        ORDER BY s.sale_date DESC,r.id ASC LIMIT 30 OFFSET ?''', ((page - 1) * 30,)).fetchall()
    return render_template('sales.html', restaurants=db.execute('SELECT id,name FROM restaurants ORDER BY id').fetchall(),
                           records=records, today=current, page=page, pages=pages,
                           demo_allowed=not app.config['PRODUCTION'])


@bp.post('/admin/sales/demo')
@admin_required
def sales_demo():
    from .discovery import today
    if app.config['PRODUCTION']:
        abort(403)
    db = get_db()
    current = today()
    count = 0
    for r in db.execute('SELECT id FROM restaurants').fetchall():
        for offset in range(35):
            sale_date = current - timedelta(days=offset)
            # Reproducible sample trends; do not replace manually entered records.
            quantity = 15 + (r['id'] * 37 + offset * (r['id'] * 3 + 11)) % 160
            cursor = db.execute('''INSERT OR IGNORE INTO daily_sales
                (restaurant_id,sale_date,quantity,source,updated_at) VALUES (?,?,?,'demo',?)''',
                (r['id'], sale_date.isoformat(), quantity, datetime.now().isoformat(timespec='seconds')))
            count += cursor.rowcount
    audit('生成演示销量', count)
    db.commit()
    flash(f'新增 {count} 条演示销量；演示数据与录入销量分开统计。', 'success')
    return redirect(url_for('discovery.rankings', source='demo'))


@bp.context_processor
def theme_options():
    return dict(themes=THEMES)

# ---------------------------------------------------------------- 管理后台
@bp.route("/admin")
@admin_required
def admin_dashboard():
    db = get_db()
    stats = {name: db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
             for name in ("users", "restaurants", "reviews")}
    restaurants = db.execute("SELECT * FROM restaurants ORDER BY id DESC").fetchall()
    review_pages = max(1, (stats["reviews"] + 19) // 20)
    review_page = min(max(request.args.get("review_page", 1, type=int), 1), review_pages)
    reviews = db.execute("""SELECT rv.*,r.name restaurant_name FROM reviews rv
                            JOIN restaurants r ON r.id=rv.restaurant_id ORDER BY rv.id DESC LIMIT 20 OFFSET ?""", ((review_page - 1) * 20,)).fetchall()
    users = db.execute("SELECT * FROM users ORDER BY id").fetchall()
    return render_template("admin.html", stats=stats, restaurants=restaurants, reviews=reviews, users=users,
                           review_page=review_page, review_pages=review_pages)


def restaurant_form_data():
    data = {key: (request.form.get(key) or "").strip() for key in
            ("name", "category", "address", "phone", "description", "avg_price", "emoji", "gradient")}
    data['gradient'] = THEMES.get(request.form.get('theme'), THEMES['warm'])[1]
    return data


def valid_restaurant(data):
    try:
        price = int(data["avg_price"] or 0)
    except ValueError:
        price = -1
    limits = {"name": 80, "category": 30, "address": 200, "phone": 40, "description": 2000, "emoji": 12, "gradient": 150}
    valid = all(data[k] for k in ("name", "category", "address")) and 0 <= price <= 100000
    valid = valid and all(len(data[k]) <= limit for k, limit in limits.items())
    if not valid:
        flash("请填写名称、分类和地址；人均价格须为 0~100000 的整数，文字不得超长。", "error")
    return valid


@bp.route("/admin/restaurant/new", methods=["GET", "POST"])
@admin_required
def admin_restaurant_new():
    if request.method == "POST":
        data = restaurant_form_data()
        if valid_restaurant(data):
            cur = get_db().execute("""INSERT INTO restaurants
                (name,category,address,phone,description,avg_price,rating,taste_score,environment_score,service_score,emoji,gradient)
                VALUES (?,?,?,?,?,?,0,0,0,0,?,?)""", (data["name"], data["category"], data["address"], data["phone"],
                data["description"], int(data["avg_price"] or 0), data["emoji"] or "🍽️",
                data["gradient"] or "linear-gradient(135deg,#ff9a5a,#e6533f)"))
            audit('创建餐厅', cur.lastrowid)
            get_db().commit()
            flash("餐厅已创建", "success")
            return redirect(url_for("admin.admin_dashboard"))
        return render_template("restaurant_form.html", restaurant=data), 400
    return render_template("restaurant_form.html", restaurant=None)


@bp.route("/admin/restaurant/<int:rid>/edit", methods=["GET", "POST"])
@admin_required
def admin_restaurant_edit(rid):
    restaurant = get_db().execute("SELECT * FROM restaurants WHERE id=?", (rid,)).fetchone()
    if restaurant is None:
        abort(404)
    if request.method == "POST":
        data = restaurant_form_data()
        if valid_restaurant(data):
            get_db().execute("""UPDATE restaurants SET name=?,category=?,address=?,phone=?,description=?,avg_price=?,emoji=?,gradient=? WHERE id=?""",
                (data["name"], data["category"], data["address"], data["phone"], data["description"],
                 int(data["avg_price"] or 0), data["emoji"] or "🍽️", data["gradient"], rid))
            audit('编辑餐厅', rid)
            get_db().commit()
            flash("餐厅已更新", "success")
            return redirect(url_for("admin.admin_dashboard"))
        return render_template("restaurant_form.html", restaurant=data), 400
    return render_template("restaurant_form.html", restaurant=restaurant)


@bp.post("/admin/restaurant/<int:rid>/delete")
@admin_required
def admin_restaurant_delete(rid):
    if not get_db().execute('SELECT 1 FROM restaurants WHERE id=?', (rid,)).fetchone():
        abort(404)
    get_db().execute("DELETE FROM restaurants WHERE id=?", (rid,))
    audit('删除餐厅', rid)
    get_db().commit()
    flash("餐厅已删除", "success")
    return redirect(url_for("admin.admin_dashboard"))


@bp.post("/admin/review/<int:review_id>/toggle")
@admin_required
def admin_review_toggle(review_id):
    review = get_db().execute("SELECT * FROM reviews WHERE id=?", (review_id,)).fetchone()
    if review is None:
        abort(404)
    status = "hidden" if review["status"] == "visible" else "visible"
    get_db().execute("UPDATE reviews SET status=? WHERE id=?", (status, review_id))
    audit('隐藏点评' if status == 'hidden' else '恢复点评', review_id)
    recalculate_restaurant(review["restaurant_id"])
    get_db().commit()
    flash("点评状态已更新", "success")
    return redirect(url_for("admin.admin_dashboard"))


@bp.post("/admin/user/<int:user_id>/toggle")
@admin_required
def admin_user_toggle(user_id):
    if not get_db().execute('SELECT 1 FROM users WHERE id=?', (user_id,)).fetchone():
        abort(404)
    if user_id == g.user["id"]:
        flash("不能停用当前管理员账号", "error")
    else:
        get_db().execute("UPDATE users SET is_active=1-is_active,session_version=session_version+1 WHERE id=?", (user_id,))
        audit('切换用户状态', user_id)
        get_db().commit()
        flash("用户状态已更新", "success")
    return redirect(url_for("admin.admin_dashboard"))


@bp.route('/admin/restaurant/<int:rid>/dishes', methods=['GET', 'POST'])
@admin_required
def dishes(rid):
    db = get_db()
    restaurant = db.execute('SELECT * FROM restaurants WHERE id=?', (rid,)).fetchone()
    if restaurant is None:
        abort(404)
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        price = request.form.get('price', type=int)
        dish_id = request.form.get('dish_id', type=int)
        if not 1 <= len(name) <= 80 or price is None or not 0 <= price <= 100000:
            flash('菜名需为 1~80 字，价格需为 0~100000 的整数', 'error')
        else:
            if dish_id:
                if not db.execute('SELECT 1 FROM dishes WHERE id=? AND restaurant_id=?', (dish_id, rid)).fetchone():
                    abort(404)
                db.execute('UPDATE dishes SET name=?,price=? WHERE id=? AND restaurant_id=?', (name, price, dish_id, rid))
            else:
                dish_id = db.execute('INSERT INTO dishes(restaurant_id,name,price) VALUES (?,?,?)', (rid, name, price)).lastrowid
            audit('保存菜品', dish_id)
            db.commit()
            flash('菜品已保存', 'success')
            return redirect(url_for('admin.dishes', rid=rid))
    rows = db.execute('SELECT * FROM dishes WHERE restaurant_id=? ORDER BY id', (rid,)).fetchall()
    return render_template('dishes.html', restaurant=restaurant, dishes=rows)


@bp.post('/admin/restaurant/<int:rid>/dish/<int:dish_id>/delete')
@admin_required
def delete_dish(rid, dish_id):
    cursor = get_db().execute('DELETE FROM dishes WHERE restaurant_id=? AND id=?', (rid, dish_id))
    if not cursor.rowcount:
        abort(404)
    audit('删除菜品', dish_id)
    get_db().commit()
    flash('菜品已删除', 'success')
    return redirect(url_for('admin.dishes', rid=rid))


@bp.get('/admin/audit')
@admin_required
def audit_log():
    db = get_db()
    count = db.execute('SELECT COUNT(*) FROM audit_logs').fetchone()[0]
    pages = max(1, (count + 19) // 20)
    page = min(max(1, request.args.get('page', 1, type=int)), pages)
    logs = db.execute('''SELECT a.*,u.username FROM audit_logs a LEFT JOIN users u ON u.id=a.actor_id
                         ORDER BY a.id DESC LIMIT 20 OFFSET ?''', ((page - 1) * 20,)).fetchall()
    return render_template('audit.html', logs=logs, page=page, pages=pages)
