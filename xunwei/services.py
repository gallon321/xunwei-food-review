from .db import get_db
from flask import g
from datetime import datetime


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
