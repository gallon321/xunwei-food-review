from datetime import datetime
import hashlib
import sqlite3
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
            except sqlite3.IntegrityError:
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
    reviews = db.execute("""SELECT rv.*,r.name AS restaurant_name FROM reviews rv
                            JOIN restaurants r ON r.id=rv.restaurant_id
                            WHERE rv.user_id=? ORDER BY rv.created_at DESC""", (g.user["id"],)).fetchall()
    favorites = db.execute("""SELECT r.* FROM favorites f JOIN restaurants r ON r.id=f.restaurant_id
                              WHERE f.user_id=? ORDER BY f.created_at DESC""", (g.user["id"],)).fetchall()
    return render_template("profile.html", reviews=reviews, favorites=favorites)


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
