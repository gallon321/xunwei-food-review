import os
import tempfile
import unittest

from xunwei import create_app
from xunwei.db import get_db, init_db


class XunweiTestCase(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.app = create_app(dict(TESTING=True, DATABASE=self.db_path, SECRET_KEY="test-key", SEED_DEMO=True, CSRF_ENABLED=False))
        self.client = self.app.test_client()
        with self.app.app_context():
            init_db()

    def tearDown(self):
        os.unlink(self.db_path)

    def login(self, username="foodie", password="foodie123"):
        return self.client.post("/login", data={"username": username, "password": password}, follow_redirects=True)

    def test_home_and_detail(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertIn("蜀香居".encode(), self.client.get("/restaurant/1").data)

    def test_location_search_and_photo_cards(self):
        with self.app.app_context():
            get_db().execute("UPDATE restaurants SET address='搜索测试路88号' WHERE id=1")
            get_db().commit()
        html = self.client.get('/?location=搜索测试路&q=蜀香居').get_data(as_text=True)
        self.assertIn('蜀香居', html)
        self.assertIn('restaurant-photo', html)
        self.assertIn('location=', html)
        html = self.client.get('/?location=不存在的街道').get_data(as_text=True)
        self.assertNotIn('class="restaurant-photo"', html)

    def test_register_login_logout(self):
        response = self.client.post("/register", data={"username": "newuser", "password": "secret12"}, follow_redirects=True)
        self.assertIn("注册成功".encode(), response.data)
        self.assertEqual(self.client.post("/logout").status_code, 302)
        self.assertIn("登录成功".encode(), self.login("newuser", "secret12").data)

    def test_login_required_and_favorite(self):
        self.assertEqual(self.client.post("/favorite/1").status_code, 302)
        self.login()
        response = self.client.post("/favorite/1", headers={"X-Requested-With": "XMLHttpRequest"})
        self.assertTrue(response.get_json()["active"])
        self.assertEqual(response.get_json()["count"], 1)

    def test_review_create_edit_delete_and_ownership(self):
        self.login()
        response = self.client.post("/restaurant/1/review", data={
            "rating": "5", "taste_score": "5", "environment_score": "4",
            "service_score": "5", "content": "测试点评内容很不错"
        })
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            review_id = get_db().execute("SELECT id FROM reviews WHERE user_id IS NOT NULL ORDER BY id DESC").fetchone()[0]
        self.assertEqual(self.client.post(f"/review/{review_id}/edit", data={
            "rating": "4", "taste_score": "4", "environment_score": "4",
            "service_score": "4", "content": "修改后的点评内容"
        }).status_code, 302)
        self.client.post("/logout")
        self.client.post("/register", data={"username": "someone", "password": "secret12"})
        self.assertEqual(self.client.get(f"/review/{review_id}/edit").status_code, 403)
        self.client.post("/logout")
        self.login()
        self.assertEqual(self.client.post(f"/review/{review_id}/delete").status_code, 302)

    def test_admin_permissions_and_actions(self):
        self.login()
        self.assertEqual(self.client.get("/admin").status_code, 403)
        self.client.post("/logout")
        self.login("admin", "admin123")
        self.assertEqual(self.client.get("/admin").status_code, 200)
        response = self.client.post("/admin/restaurant/new", data={
            "name": "测试餐厅", "category": "测试菜", "address": "测试路1号", "avg_price": "50"
        }, follow_redirects=True)
        self.assertIn("餐厅已创建".encode(), response.data)

    def test_missing_pages(self):
        self.assertEqual(self.client.get("/missing").status_code, 404)
        self.assertEqual(self.client.get("/restaurant/9999").status_code, 404)
        self.assertEqual(self.client.get("/favicon.ico").status_code, 204)

    def test_favorites_across_pages_and_idempotent_migration(self):
        self.login()
        for _ in range(2):
            response = self.client.post('/favorites/migrate', json={'ids': [7, 7, 999999]})
            self.assertEqual(response.json['count'], 1)
        html = self.client.get('/?favorites=1').get_data(as_text=True)
        self.assertIn('巷子口烤肉', html)
        self.assertNotIn('甜心烘焙', html)
        self.assertEqual(self.client.post('/favorites/migrate', json={'ids': 5}).status_code, 400)
        self.client.post('/logout')
        self.assertIn('巷子口烤肉', self.client.get('/?favorites=1&ids=7').get_data(as_text=True))

    def test_invalid_price_and_score_do_not_write(self):
        self.login('admin', 'admin123')
        with self.app.app_context():
            count = get_db().execute('SELECT COUNT(*) FROM restaurants').fetchone()[0]
        for price in ('abc', '-5', '100001'):
            response = self.client.post('/admin/restaurant/new', data={
                'name': '测试', 'category': '测试', 'address': '测试', 'avg_price': price})
            self.assertEqual(response.status_code, 400)
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT COUNT(*) FROM restaurants').fetchone()[0], count)
            review_count = get_db().execute('SELECT COUNT(*) FROM reviews').fetchone()[0]
        self.client.post('/restaurant/1/review', data={'rating': '5', 'taste_score': '0', 'content': '无效口味评分测试'})
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT COUNT(*) FROM reviews').fetchone()[0], review_count)

    def test_moderation_updates_counts_and_ratings(self):
        self.login('admin', 'admin123')
        with self.app.app_context():
            ids = [r[0] for r in get_db().execute('SELECT id FROM reviews WHERE restaurant_id=1')]
        for rid in ids:
            self.client.post(f'/admin/review/{rid}/toggle')
        self.assertIn('0 条点评', self.client.get('/?q=蜀香居').get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT rating FROM restaurants WHERE id=1').fetchone()[0], 0)
        self.assertEqual(self.client.get('/admin?review_page=3').status_code, 200)
        self.assertIn('蜀香居', self.client.get('/admin?review_page=3').get_data(as_text=True))

    def test_disabled_user_loses_active_session(self):
        self.login()
        with self.app.app_context():
            get_db().execute("UPDATE users SET is_active=0 WHERE username='foodie'")
            get_db().commit()
        self.assertEqual(self.client.get('/profile').status_code, 302)
        self.assertNotIn('登录成功', self.login().get_data(as_text=True))

    def test_initialization_preserves_deleted_catalog(self):
        with self.app.app_context():
            init_db()
            self.assertEqual(get_db().execute('SELECT COUNT(*) FROM users').fetchone()[0], 2)
            get_db().execute('DELETE FROM restaurants')
            get_db().commit()
            init_db()
            self.assertEqual(get_db().execute('SELECT COUNT(*) FROM restaurants').fetchone()[0], 0)

    def test_csrf_valid_token_and_no_open_redirect(self):
        self.app.config['CSRF_ENABLED'] = True
        try:
            self.client.get('/login')
            with self.client.session_transaction() as saved:
                token = saved['csrf_token']
            response = self.client.post('/login', data={
                'username': 'foodie', 'password': 'foodie123',
                'csrf_token': token, 'next': '/\\evil.example'})
            self.assertEqual(response.location, '/')
        finally:
            self.app.config['CSRF_ENABLED'] = False

    def test_csrf_rejects_missing_token(self):
        self.app.config["CSRF_ENABLED"] = True
        try:
            self.assertEqual(self.client.post("/login", data={"username": "foodie", "password": "foodie123"}).status_code, 400)
        finally:
            self.app.config["CSRF_ENABLED"] = False


if __name__ == "__main__":
    unittest.main()
