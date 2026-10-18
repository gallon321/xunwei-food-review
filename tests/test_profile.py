import re
import unittest
import test_dish_reviews
from xunwei.db import get_db, init_db


class ProfileTest(unittest.TestCase):
    setUp = test_dish_reviews.DishReviewsTest.setUp
    tearDown = test_dish_reviews.DishReviewsTest.tearDown
    login = test_dish_reviews.DishReviewsTest.login

    def ids(self, tab='history', page=1):
        html = self.client.get('/profile', query_string=dict(tab=tab, page=page)).get_data(as_text=True)
        return [int(value) for value in re.findall(r'data-card-id="(\d+)"', html)]

    def test_login_empty_states_and_navigation(self):
        self.assertIn('/login', self.client.get('/profile').location)
        self.client.get('/restaurant/1')
        self.login()
        html = self.client.get('/profile').get_data(as_text=True)
        for text in ('我的收藏', '浏览记录', '历史点评', '的美食空间', '还没有收藏的店铺'):
            self.assertIn(text, html)
        self.assertIn('还没有浏览记录', self.client.get('/profile?tab=history').get_data(as_text=True))
        self.assertIn('用点评记住每一种味道', self.client.get('/profile?tab=reviews').get_data(as_text=True))
        self.assertEqual(self.ids('unknown'), [])
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT COUNT(*) FROM browsing_history').fetchone()[0], 0)

    def test_recent_order_dedup_dish_visits_and_account_isolation(self):
        self.login()
        self.client.get('/restaurant/1')
        self.client.get('/restaurant/2')
        self.assertEqual(self.ids(), [2, 1])
        self.client.get('/restaurant/1/dish/1')
        self.assertEqual(self.ids(), [1, 2])
        self.client.get('/restaurant/999')
        self.client.get('/restaurant/2/dish/1')
        self.assertEqual(self.ids(), [1, 2])
        self.login('bobby')
        self.assertEqual(self.ids(), [])
        self.client.get('/restaurant/2')
        self.assertEqual(self.ids(), [2])
        self.client.post('/profile/history/1/remove')
        self.login()
        self.assertEqual(self.ids(), [1, 2])

    def test_history_remove_clear_csrf_and_no_favorite_loss(self):
        self.login()
        self.client.get('/restaurant/1')
        self.client.get('/restaurant/2')
        self.client.post('/favorite/1')
        self.app.config['CSRF_ENABLED'] = True
        self.assertEqual(self.client.post('/profile/history/clear').status_code, 400)
        self.assertEqual(self.client.post('/profile/history/1/remove').status_code, 400)
        self.assertEqual(self.ids(), [2, 1])
        self.app.config['CSRF_ENABLED'] = False
        self.client.post('/profile/history/1/remove', data=dict(user_id=3))
        self.assertEqual(self.ids(), [2])
        self.client.post('/profile/history/clear')
        self.assertEqual(self.ids(), [])
        self.assertEqual(self.ids('favorites'), [1])
        self.login('bobby')
        self.assertEqual(self.ids('favorites'), [])

    def test_history_limit_and_pagination(self):
        with self.app.app_context():
            db = get_db()
            for rid in range(3, 103):
                db.execute('INSERT INTO restaurants(id,name,category,address) VALUES (?,?,?,?)', (rid, f'餐厅{rid}', '川菜', '北京'))
            db.commit()
        self.login()
        for rid in range(1, 103):
            self.assertEqual(self.client.get(f'/restaurant/{rid}').status_code, 200)
        self.assertEqual(self.ids(), [102, 101, 100, 99, 98, 97])
        self.assertEqual(self.ids(page=999), [6, 5, 4, 3])
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT COUNT(*) FROM browsing_history').fetchone()[0], 100)
        self.client.get('/restaurant/1')
        self.assertEqual(self.ids()[0], 1)
        with self.app.app_context():
            self.assertIsNone(get_db().execute('SELECT 1 FROM browsing_history WHERE restaurant_id=3').fetchone())

    def test_combined_review_history_and_private_hidden_status(self):
        self.login()
        self.client.post('/restaurant/1/review', data=dict(rating=4, content='店铺的真实历史点评'))
        self.client.post('/restaurant/1/dish/1/review', data=dict(rating=5, content='菜品的真实历史评价'))
        self.login('admin')
        self.client.post('/admin/dish-review/1/toggle')
        self.login()
        html = self.client.get('/profile?tab=reviews').get_data(as_text=True)
        for text in ('店铺的真实历史点评', '菜品的真实历史评价', '店铺点评', '菜品评价', '已隐藏', '编辑'):
            self.assertIn(text, html)
        self.assertIn('4 星', html)
        self.assertIn('5 星', html)
        self.login('bobby')
        html = self.client.get('/profile?tab=reviews').get_data(as_text=True)
        self.assertNotIn('真实历史', html)
        self.login()
        response = self.client.post('/dish-review/1/delete', data=dict(next='/profile?tab=reviews'))
        self.assertTrue(response.location.endswith('/profile?tab=reviews'))
        html = self.client.get(response.location).get_data(as_text=True)
        self.assertNotIn('菜品的真实历史评价', html)
        self.assertIn('店铺的真实历史点评', html)

    def test_upgrade_and_cascade_preserve_existing_data(self):
        self.login()
        self.client.post('/favorite/1')
        with self.app.app_context():
            db = get_db()
            db.execute('DROP TABLE browsing_history')
            db.execute('PRAGMA user_version=4')
            db.commit()
            init_db()
            init_db()
            self.assertEqual(db.execute('SELECT COUNT(*) FROM favorites').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM browsing_history').fetchone()[0], 0)
        self.client.get('/restaurant/1')
        with self.app.app_context():
            db = get_db()
            db.execute('DELETE FROM restaurants WHERE id=1')
            db.commit()
            self.assertEqual(db.execute('SELECT COUNT(*) FROM browsing_history').fetchone()[0], 0)
            self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
