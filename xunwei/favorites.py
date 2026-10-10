from datetime import datetime
from flask import (Blueprint, current_app as app, abort, flash, g, jsonify,
                   redirect, render_template, request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash
from .db import get_db
from .security import login_required, admin_required, safe_next
from .services import recalculate_restaurant

bp = Blueprint("favorites", __name__)

@bp.post("/favorite/<int:rid>")
@login_required
def toggle_favorite(rid):
    db = get_db()
    if not db.execute("SELECT 1 FROM restaurants WHERE id=?", (rid,)).fetchone():
        abort(404)
    exists = db.execute("SELECT 1 FROM favorites WHERE user_id=? AND restaurant_id=?", (g.user["id"], rid)).fetchone()
    if exists:
        db.execute("DELETE FROM favorites WHERE user_id=? AND restaurant_id=?", (g.user["id"], rid))
        active = False
    else:
        db.execute("INSERT INTO favorites VALUES (?,?,?)", (g.user["id"], rid, datetime.now().strftime("%Y-%m-%d %H:%M")))
        active = True
    db.commit()
    count = db.execute("SELECT COUNT(*) FROM favorites WHERE user_id=?", (g.user["id"],)).fetchone()[0]
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify(active=active, count=count)
    return redirect(url_for("accounts.profile"))


@bp.post("/favorites/migrate")
@login_required
def migrate_favorites():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict) or not isinstance(payload.get("ids", []), list):
        abort(400)
    ids = payload.get("ids", [])
    valid_ids = []
    for value in ids[:100]:
        try:
            rid = int(value)
            if 0 < rid < 2147483648:
                valid_ids.append(rid)
        except (TypeError, ValueError, OverflowError):
            continue
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    for rid in valid_ids:
        if get_db().execute("SELECT 1 FROM restaurants WHERE id=?", (rid,)).fetchone():
            get_db().execute("INSERT OR IGNORE INTO favorites VALUES (?,?,?)", (g.user["id"], rid, now))
    get_db().commit()
    return jsonify(count=get_db().execute("SELECT COUNT(*) FROM favorites WHERE user_id=?", (g.user["id"],)).fetchone()[0])
