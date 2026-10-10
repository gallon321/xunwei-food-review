from datetime import date, timedelta
import unittest
import test_project
from xunwei.db import get_db, init_db
from xunwei.discovery import ranked_restaurants, recommend_restaurants, today


class DiscoveryTest(unittest.TestCase):
    setUp = test_project.ProjectTest.setUp
    tearDown = test_project.ProjectTest.tearDown
    post = test_project.ProjectTest.post
    login = test_project.ProjectTest.login
    def sale(self, rid, when, quantity, source='manual'):
        get_db().execute('INSERT INTO daily_sales VALUES (?,?,?,?,?)',
                         (rid, when.isoformat(), quantity, source, '2026-10-10T12:00:00'))

    def test_calendar_boundaries_sources_and_ties(self):
        current = date(2026, 10, 10)
        with self.app.app_context():
            self.sale(1, current, 10)
            self.sale(2, current, 10)
            self.sale(1, date(2026, 10, 5), 20)
            self.sale(2, date(2026, 10, 4), 50)
            self.sale(1, date(2026, 9, 30), 999)
            self.sale(2, date(2026, 10, 11), 999)
            self.sale(3, current, 999, 'demo')
            self.assertEqual([r['rank'] for r in ranked_restaurants('day', current=current)], [1, 1])
            self.assertEqual([(r['id'], r['sales']) for r in ranked_restaurants('week', current=current)], [(1, 30), (2, 10)])
            self.assertEqual([(r['id'], r['sales']) for r in ranked_restaurants('month', current=current)], [(2, 60), (1, 30)])
            self.assertEqual(ranked_restaurants('day', source='demo', current=current)[0]['id'], 3)
            self.assertEqual(len(ranked_restaurants('day', category='川菜', current=current)), 1)

    def test_sales_authorization_validation_and_upsert(self):
        self.assertEqual(self.client.get('/admin/sales').status_code, 403)
        self.login(username='foodie', password='foodie123')
        self.assertEqual(self.post('/admin/sales', dict(restaurant_id=1, sale_date=str(today()), quantity=10)).status_code, 403)
        self.post('/logout')
        self.login()
        for amount in ('-1', 'abc', '1000001'):
            self.assertEqual(self.post('/admin/sales', dict(restaurant_id=1, sale_date=str(today()), quantity=amount)).status_code, 400)
        self.assertEqual(self.post('/admin/sales', dict(restaurant_id=1, sale_date=str(today()+timedelta(days=1)), quantity=1)).status_code, 400)
        self.assertEqual(self.post('/admin/sales', dict(restaurant_id=99999, sale_date=str(today()), quantity=1)).status_code, 404)
        for amount in (12, 18):
            self.assertEqual(self.post('/admin/sales', dict(restaurant_id=1, sale_date=str(today()), quantity=amount)).status_code, 302)
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT COUNT(*),SUM(quantity) FROM daily_sales').fetchone()[:], (1, 18))
        self.assertEqual(self.client.get('/admin/sales').status_code, 200)

    def test_demo_idempotence_and_manual_preservation(self):
        self.login()
        self.post('/admin/sales', dict(restaurant_id=1, sale_date=str(today()), quantity=321))
        self.assertEqual(self.post('/admin/sales/demo').status_code, 302)
        with self.app.app_context():
            count = get_db().execute('SELECT COUNT(*) FROM daily_sales').fetchone()[0]
            self.assertEqual(ranked_restaurants('day')[0]['sales'], 321)
        self.post('/admin/sales/demo')
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT COUNT(*) FROM daily_sales').fetchone()[0], count)
            init_db()
            self.assertEqual(get_db().execute('SELECT COUNT(*) FROM daily_sales').fetchone()[0], count)
        self.app.config['PRODUCTION'] = True
        self.assertEqual(self.post('/admin/sales/demo').status_code, 403)

    def test_personalized_reasons_filters_and_negative_feedback(self):
        with self.app.app_context():
            db = get_db()
            user_id = db.execute("SELECT id FROM users WHERE username='foodie'").fetchone()[0]
            initial, personalized = recommend_restaurants(user_id)
            self.assertFalse(personalized)
            self.assertTrue(initial)
            db.execute("INSERT INTO favorites VALUES (?,?,?)", (user_id, 1, '2026-10-10'))
            db.execute("INSERT INTO restaurants(name,category,address,avg_price) VALUES ('川菜新店','川菜','测试地址',65)")
            new_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
            rows, personalized = recommend_restaurants(user_id)
            self.assertTrue(personalized)
            self.assertEqual(rows[0]['id'], new_id)
            self.assertIn('符合你偏好的川菜', rows[0]['reasons'])
            rows, _ = recommend_restaurants(user_id, category='川菜', budget=66)
            self.assertEqual([r['id'] for r in rows], [new_id])
            db.execute('''INSERT INTO reviews(restaurant_id,author,rating,content,created_at,user_id)
                          VALUES (?, 'foodie',1,'不喜欢这家餐厅','2026-10-10',?)''', (new_id,user_id))
            rows, _ = recommend_restaurants(user_id)
            self.assertNotIn(new_id, [r['id'] for r in rows])
            db.execute("UPDATE reviews SET status='hidden' WHERE restaurant_id=?", (new_id,))
            rows, _ = recommend_restaurants(user_id)
            self.assertIn(new_id, [r['id'] for r in rows])

    def test_public_pages_and_invalid_parameters(self):
        for path in ('/rankings', '/rankings?period=week', '/rankings?period=month&source=demo', '/recommendations', '/recommendations?budget=60&category=川菜'):
            self.assertEqual(self.client.get(path).status_code, 200, path)
        for path in ('/rankings?period=bad', '/rankings?source=bad', '/recommendations?budget=abc', '/recommendations?budget=-1'):
            self.assertEqual(self.client.get(path).status_code, 400)
        self.assertIn('销量排行榜', self.client.get('/').get_data(as_text=True))
        self.assertIn('登录', self.client.get('/recommendations').get_data(as_text=True))
