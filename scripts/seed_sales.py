"""Append random demo sales, preserving existing records: python scripts/seed_sales.py."""
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from xunwei import create_app
from xunwei.db import get_db
from xunwei.discovery import ranked_restaurants, today
from xunwei.migrations import backup_database


def main():
    app = create_app()
    if app.config['PRODUCTION']:
        raise RuntimeError('Demo sales are disabled in production.')
    with app.app_context():
        db = get_db()
        restaurants = db.execute('SELECT id FROM restaurants ORDER BY id').fetchall()
        if not restaurants:
            print('No restaurants found; no records added.')
            return
        backup = backup_database(db, 'before-demo-sales')
        rng = random.SystemRandom()
        current = today()
        timestamp = datetime.now().isoformat(timespec='seconds')
        count = 0
        with db:
            for restaurant in restaurants:
                daily_baseline = rng.randint(35, 160)
                for offset in range(35):
                    sale_date = current - timedelta(days=offset)
                    weekend_boost = 1.25 if sale_date.weekday() >= 5 else 1
                    quantity = max(1, round(daily_baseline * weekend_boost * rng.uniform(.6, 1.5)))
                    cursor = db.execute('''INSERT OR IGNORE INTO daily_sales
                        (restaurant_id,sale_date,quantity,source,updated_at) VALUES (?,?,?,'demo',?)''',
                        (restaurant['id'], sale_date.isoformat(), quantity, timestamp))
                    count += cursor.rowcount
            db.execute('INSERT INTO audit_logs(actor_id,action,target,created_at) VALUES (NULL,?,?,?)',
                       ('生成随机演示销量', str(count), timestamp))
        print(f'Added {count} demo records for {len(restaurants)} restaurants over 35 days.')
        print(f'Date range: {current-timedelta(days=34)} through {current}.')
        print(f'Backup: {backup}')
        for period in ('day', 'week', 'month'):
            rows = ranked_restaurants(period, source='demo')
            assert rows and all(rows[i]['sales'] >= rows[i+1]['sales'] for i in range(len(rows)-1))
            print(f'{period}: {len(rows)} restaurants; total {sum(row["sales"] for row in rows)} orders.')


if __name__ == '__main__':
    main()
