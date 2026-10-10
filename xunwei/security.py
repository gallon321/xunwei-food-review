import secrets
from functools import wraps
from urllib.parse import urlsplit
from flask import current_app as app, abort, flash, g, redirect, request, session, url_for
from .db import get_db

def load_user_and_csrf():
    g.user = None
    if session.get("user_id"):
        g.user = get_db().execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
        if g.user is None or not g.user["is_active"] or session.get('version', -1) != g.user['session_version']:
            session.clear()
            g.user = None
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)
    if request.method in ('POST', 'PUT', 'PATCH', 'DELETE') and app.config.get("CSRF_ENABLED", True):
        token = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
        if not token or not secrets.compare_digest(token.encode('utf-8'), session["csrf_token"].encode('utf-8')):
            abort(400, "CSRF token invalid")


def inject_globals():
    fav_count = 0
    if g.get("user"):
        fav_count = get_db().execute("SELECT COUNT(*) FROM favorites WHERE user_id=?", (g.user["id"],)).fetchone()[0]
    return {"csrf_token": session.get("csrf_token", ""), "favorite_count": fav_count}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("请先登录", "error")
            return redirect(url_for("accounts.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None or g.user["role"] != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def safe_next(default="catalog.index"):
    target = request.args.get("next") or request.form.get("next")
    return target if target and target.startswith("/") and not urlsplit(target).netloc and not target.startswith("//") and "\\" not in target and not any(ord(c) < 32 for c in target) else url_for(default)
