from datetime import datetime
import hashlib
from .db import IntegrityErrors
import time
from flask import (Blueprint, current_app as app, abort, flash, g, jsonify,
                   redirect, render_template, request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash
from .db import get_db
from .security import login_required, admin_required, safe_next
from .services import recalculate_restaurant

bp = Blueprint("accounts", __name__)

# ---------------------------------------------------------------- 用户与收藏
@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        errors = []
        if not 3 <= len(username) <= 20:
            errors.append("用户名需为 3~20 个字符")
        if not 8 <= len(password) <= 72:
            errors.append("密码需为 8~72 个字符")
        if get_db().execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
            errors.append("用户名已存在")
        if not errors:
            try:
                cur = get_db().execute("INSERT INTO users (username,password_hash,created_at) VALUES (?,?,?)",
                                       (username, generate_password_hash(password), datetime.now().strftime("%Y-%m-%d %H:%M")))
            except IntegrityErrors:
                get_db().rollback()
                flash('用户名已存在', 'error')
                return render_template('auth.html', mode='register'), 400
            get_db().commit()
            session.clear()
            session["user_id"] = cur.lastrowid
            session['version'] = 0
            flash("注册成功，欢迎加入寻味！", "success")
            return redirect(url_for("catalog.index"))
        for error in errors:
            flash(error, "error")
    return render_template("auth.html", mode="register")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        now = time.time()
        username = (request.form.get('username') or '').strip()
        # Hash identifiers so the rate-limit table does not store raw IP addresses.
        identities = [hashlib.sha256(v.encode()).hexdigest() for v in
                      ('user:' + username, 'ip:' + (request.remote_addr or 'unknown'))]
        db = get_db()
        db.execute('DELETE FROM login_attempts WHERE started_at < ?', (now - 900,))
        db.commit()
        for identity, limit in zip(identities, (10, 50)):
            attempt = db.execute('SELECT failures FROM login_attempts WHERE identity=?', (identity,)).fetchone()
            if attempt and attempt['failures'] >= limit:
                abort(429)
        user = get_db().execute("SELECT * FROM users WHERE username=?", ((request.form.get("username") or "").strip(),)).fetchone()
        if user and user["is_active"] and check_password_hash(user["password_hash"], request.form.get("password") or ""):
            db.execute('DELETE FROM login_attempts WHERE identity=?', (identities[0],))
            db.commit()
            session.clear()
            session["user_id"] = user["id"]
            session['version'] = user['session_version']
            flash("登录成功", "success")
            return redirect(safe_next())
        for identity in identities:
            db.execute('''INSERT INTO login_attempts VALUES (?,1,?)
                          ON CONFLICT(identity) DO UPDATE SET failures=failures+1''', (identity, now))
        db.commit()
        flash("用户名、密码错误或账号已停用", "error")
    return render_template("auth.html", mode="login")


@bp.post("/logout")
def logout():
    session.clear()
    flash("已退出登录", "success")
    return redirect(url_for("catalog.index"))

@bp.route("/profile")
@login_required
def profile():
    db = get_db()
    uid = g.user['id']
    tab = request.args.get('tab', 'favorites')
    if tab not in ('favorites', 'history', 'reviews'):
        tab = 'favorites'
    counts = {key: db.execute(f'SELECT COUNT(*) FROM {table} WHERE user_id=?', (uid,)).fetchone()[0]
              for key, table in (('favorites', 'favorites'), ('history', 'browsing_history'), ('reviews', 'reviews'))}
    counts['reviews'] += db.execute('SELECT COUNT(*) FROM dish_reviews WHERE user_id=?', (uid,)).fetchone()[0]
    per_page = 6
    pages = max(1, (counts[tab] + per_page - 1) // per_page)
    page = min(max(request.args.get('page', 1, type=int), 1), pages)
    offset = (page - 1) * per_page
    if tab == 'reviews':
        items = db.execute('''SELECT * FROM (
            SELECT rv.id,rv.restaurant_id,rv.rating,rv.content,rv.created_at,rv.status,
                r.name AS restaurant_name,'restaurant' AS kind,NULL AS dish_id,'' AS dish_name
            FROM reviews rv JOIN restaurants r ON r.id=rv.restaurant_id WHERE rv.user_id=?
            UNION ALL
            SELECT dr.id,d.restaurant_id,dr.rating,dr.content,dr.created_at,dr.status,
                r.name AS restaurant_name,'dish' AS kind,d.id AS dish_id,d.name AS dish_name
            FROM dish_reviews dr JOIN dishes d ON d.id=dr.dish_id
            JOIN restaurants r ON r.id=d.restaurant_id WHERE dr.user_id=?
            ) own_reviews ORDER BY created_at DESC,id DESC,kind LIMIT ? OFFSET ?''',
            (uid, uid, per_page, offset)).fetchall()
    else:
        table, date_field = ('favorites', 'created_at') if tab == 'favorites' else ('browsing_history', 'viewed_at')
        items = db.execute(f'''SELECT r.*,f.{date_field} AS activity_at,
            (SELECT COUNT(*) FROM reviews rv WHERE rv.restaurant_id=r.id AND rv.status='visible') AS review_count
            FROM {table} f JOIN restaurants r ON r.id=f.restaurant_id
            WHERE f.user_id=? ORDER BY f.{date_field} DESC,r.id DESC LIMIT ? OFFSET ?''',
            (uid, per_page, offset)).fetchall()
    favorite_ids = [row[0] for row in db.execute('SELECT restaurant_id FROM favorites WHERE user_id=?', (uid,))]
    return render_template('profile.html', tab=tab, counts=counts, items=items,
                           favorite_ids=favorite_ids, page=page, pages=pages)


@bp.post('/profile/history/clear')
@login_required
def clear_history():
    get_db().execute('DELETE FROM browsing_history WHERE user_id=?', (g.user['id'],))
    get_db().commit()
    flash('浏览记录已清空。', 'success')
    return redirect(url_for('accounts.profile', tab='history'))


@bp.post('/profile/history/<int:rid>/remove')
@login_required
def remove_history(rid):
    get_db().execute('DELETE FROM browsing_history WHERE user_id=? AND restaurant_id=?', (g.user['id'], rid))
    get_db().commit()
    flash('已移除这条浏览记录。', 'success')
    return redirect(url_for('accounts.profile', tab='history'))


@bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        current = request.form.get('current_password', '')
        password = request.form.get('password', '')
        if not check_password_hash(g.user['password_hash'], current):
            flash('当前密码不正确', 'error')
        elif not 8 <= len(password) <= 72:
            flash('新密码需为 8~72 个字符', 'error')
        elif password != request.form.get('confirm_password'):
            flash('两次新密码不一致', 'error')
        else:
            get_db().execute('UPDATE users SET password_hash=?, session_version=session_version+1 WHERE id=?',
                             (generate_password_hash(password), g.user['id']))
            get_db().commit()
            session.clear()
            flash('密码已修改，请重新登录；其他设备的登录也已失效。', 'success')
            return redirect(url_for('accounts.login'))
        return render_template('settings.html'), 400
    return render_template('settings.html')
