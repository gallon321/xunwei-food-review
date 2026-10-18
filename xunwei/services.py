from .db import get_db
from flask import g
from datetime import datetime, timedelta, timezone


def record_visit(rid):
    """Keep the latest visit to at most 100 restaurants for the signed-in user."""
    if not g.get('user'):
        return
    db = get_db()
    uid = g.user['id']
    now = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='microseconds')
    db.execute('''INSERT INTO browsing_history(user_id,restaurant_id,viewed_at) VALUES (?,?,?)
        ON CONFLICT(user_id,restaurant_id) DO UPDATE SET viewed_at=excluded.viewed_at''', (uid, rid, now))
    stale = db.execute('''SELECT restaurant_id FROM browsing_history WHERE user_id=?
        ORDER BY viewed_at DESC,restaurant_id DESC LIMIT 100 OFFSET 100''', (uid,)).fetchall()
    for row in stale:
        db.execute('DELETE FROM browsing_history WHERE user_id=? AND restaurant_id=?', (uid, row['restaurant_id']))
    db.commit()


def audit(action, target):
    """Log the action in the same transaction as the write being audited."""
    get_db().execute('INSERT INTO audit_logs(actor_id,action,target,created_at) VALUES (?,?,?,?)',
                     (g.user['id'], action, str(target), datetime.now().isoformat(timespec='seconds')))

def recalculate_restaurant(rid):
    db = get_db()
    scores = db.execute("""SELECT AVG(rating),AVG(taste_score),AVG(environment_score),AVG(service_score)
                           FROM reviews WHERE restaurant_id=? AND status='visible'""", (rid,)).fetchone()
    if scores[0] is not None:
        db.execute("UPDATE restaurants SET rating=?,taste_score=?,environment_score=?,service_score=? WHERE id=?",
                   tuple(round(scores[i], 1) for i in range(4)) + (rid,))
    else:
        db.execute("UPDATE restaurants SET rating=0,taste_score=0,environment_score=0,service_score=0 WHERE id=?", (rid,))
