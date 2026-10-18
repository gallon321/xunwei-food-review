import os
import tempfile
import unittest
from werkzeug.security import generate_password_hash
from xunwei import create_app
from xunwei.db import get_db, init_db


class DishReviewsTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        self.app = create_app(dict(TESTING=True, DATABASE=self.path, SECRET_KEY='test', CSRF_ENABLED=False, REVIEWS_PER_PAGE=2))
        self.client = self.app.test_client()
        with self.app.app_context():
            init_db()
            db = get_db()
            for name, role in [('admin', 'admin'), ('alice', 'user'), ('bobby', 'user')]:
                db.execute('INSERT INTO users(username,password_hash,role,created_at) VALUES (?,?,?,?)',
                           (name, generate_password_hash('password'), role, '2026-10-16'))
            for rid in (1, 2):
                db.execute('INSERT INTO restaurants(id,name,category,address) VALUES (?,?,?,?)', (rid, f'店铺{rid}', '川菜', '北京'))
            db.execute("INSERT INTO dishes(id,restaurant_id,name,price) VALUES (1,1,'回锅肉',38)")
            db.execute("INSERT INTO dishes(id,restaurant_id,name,price) VALUES (2,2,'水煮鱼',68)")
            db.commit()

    def tearDown(self):
        os.unlink(self.path)

    def login(self, name='alice'):
        self.client.post('/login', data=dict(username=name, password='password'))

    def add(self, rating=5, content='肉质鲜嫩分量很足'):
        return self.client.post('/restaurant/1/dish/1/review', data=dict(rating=rating, content=content))

    def test_menu_and_empty_states(self):
        html = self.client.get('/restaurant/1').get_data(as_text=True)
        self.assertIn('店铺菜品', html)
        self.assertIn('¥38', html)
        self.assertIn('暂无评分', html)
        self.assertNotIn('水煮鱼', html)
        self.assertLess(html.index('id="shop-menu"'), html.index('综合评分'))
        html = self.client.get('/restaurant/1/dish/1').get_data(as_text=True)
        self.assertIn('登录评价', html)
        self.assertEqual(self.client.get('/restaurant/1/dish/2').status_code, 404)
        self.assertEqual(self.client.get('/restaurant/999/dish/1').status_code, 404)

    def test_publish_average_previews_and_pagination(self):
        self.login()
        for score, content in [(5, '第一份菜品评价'), (3, '第二份菜品评价'), (4, '第三份菜品评价')]:
            self.assertEqual(self.add(score, content).status_code, 302)
        html = self.client.get('/restaurant/1').get_data(as_text=True)
        self.assertIn('4.0 分', html)
        self.assertIn('3 条评价', html)
        self.assertIn('第三份菜品评价', html)
        self.assertNotIn('第一份菜品评价', html)
        html = self.client.get('/restaurant/1/dish/1').get_data(as_text=True)
        self.assertIn('第三份菜品评价', html)
        self.assertNotIn('第一份菜品评价', html)
        self.assertIn('第一份菜品评价', self.client.get('/restaurant/1/dish/1?page=2').get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT rating FROM restaurants WHERE id=1').fetchone()[0], 0)

    def test_auth_validation_and_cross_shop(self):
        self.assertIn('/login', self.add().location)
        self.login()
        for score, content in [(0, '有效的评价文字'), (6, '有效的评价文字'), ('abc', '有效的评价文字'), (5, '太短'), (5, '字' * 501)]:
            self.add(score, content)
        self.assertEqual(self.client.post('/restaurant/2/dish/1/review', data=dict(rating=5, content='越权跨店评价测试')).status_code, 404)
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT COUNT(*) FROM dish_reviews').fetchone()[0], 0)

    def test_owner_delete_admin_moderation_and_cascade(self):
        self.login()
        self.add()
        self.login('bobby')
        self.assertEqual(self.client.post('/dish-review/1/delete').status_code, 403)
        self.assertEqual(self.client.post('/admin/dish-review/1/toggle').status_code, 403)
        self.login('admin')
        self.assertIn('回锅肉', self.client.get('/admin/restaurant/1/dish-reviews').get_data(as_text=True))
        self.client.post('/admin/dish-review/1/toggle')
        html = self.client.get('/restaurant/1/dish/1').get_data(as_text=True)
        self.assertIn('暂无评分', html)
        self.assertNotIn('肉质鲜嫩分量很足', html)
        self.client.post('/admin/dish-review/1/toggle')
        self.assertIn('5.0 分', self.client.get('/restaurant/1').get_data(as_text=True))
        self.login()
        self.assertEqual(self.client.post('/dish-review/1/delete').status_code, 302)
        self.add()
        with self.app.app_context():
            db = get_db()
            db.execute('DELETE FROM dishes WHERE id=1')
            db.commit()
            self.assertEqual(db.execute('SELECT COUNT(*) FROM dish_reviews').fetchone()[0], 0)

    def test_csrf_and_html_escaping(self):
        self.login()
        self.app.config['CSRF_ENABLED'] = True
        self.assertEqual(self.add().status_code, 400)
        self.app.config['CSRF_ENABLED'] = False
        self.add(content='<script>alert(1)</script>')
        for url in ['/restaurant/1', '/restaurant/1/dish/1']:
            html = self.client.get(url).get_data(as_text=True)
            self.assertIn('&lt;script&gt;', html)
            self.assertNotIn('<script>alert(1)</script>', html)

    def test_upgrade_v3_retains_data(self):
        with self.app.app_context():
            db = get_db()
            db.execute('DROP TABLE dish_reviews')
            db.execute('PRAGMA user_version=3')
            db.commit()
            init_db()
            init_db()
            self.assertEqual(db.execute('SELECT name FROM dishes WHERE id=1').fetchone()[0], '回锅肉')
            self.assertEqual(db.execute('SELECT COUNT(*) FROM dish_reviews').fetchone()[0], 0)
            from xunwei.migrations import SCHEMA_VERSION
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], SCHEMA_VERSION)
