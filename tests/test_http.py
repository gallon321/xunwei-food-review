"""Real HTTP smoke tests with cookies and CSRF, against a temporary database."""
import http.cookiejar
import json
import re
import tempfile
import threading
import unittest
from datetime import date
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPCookieProcessor, HTTPRedirectHandler

from waitress import create_server
from xunwei import create_app
from xunwei.db import init_db, get_db


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class RealHTTPTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app(dict(TESTING=True, DATABASE=str(Path(self.temp.name) / 'http.db'),
                                   SECRET_KEY='isolated-http-test-key', SEED_DEMO=True))
        with self.app.app_context():
            init_db()
        self.server = create_server(self.app, host='127.0.0.1', port=0, threads=2)
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.server.effective_port}'
        self.client = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()), NoRedirect())

    def tearDown(self):
        self.server.close()
        self.server.task_dispatcher.shutdown()
        self.thread.join(timeout=3)
        self.temp.cleanup()

    def request(self, path, data=None, headers=None):
        request = Request(self.base + path, data=data, headers=headers or {})
        try:
            response = self.client.open(request, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            return response.code, response.read().decode('utf-8'), response.headers

    def post(self, path, data=None, json_data=None):
        _, page, _ = self.request('/login')
        token = re.search(r'csrf: "([a-f0-9]+)"', page).group(1)
        if json_data is not None:
            return self.request(path, json.dumps(json_data).encode(),
                                {'Content-Type': 'application/json', 'X-CSRF-Token': token})
        return self.request(path, urlencode(dict(data or {}, csrf_token=token)).encode(),
                            {'Content-Type': 'application/x-www-form-urlencoded'})

    def login(self, username='foodie', password='foodie123'):
        self.assertEqual(self.post('/login', dict(username=username, password=password))[0], 302)

    def test_public_http_responses(self):
        for path in ('/', '/?q=蜀香居', '/restaurant/1', '/rankings?period=day',
                     '/rankings?period=week', '/rankings?period=month&source=demo',
                     '/recommendations', '/login', '/register'):
            with self.subTest(path=path):
                # URL must be ASCII on the actual HTTP transport.
                if path == '/?q=蜀香居':
                    path = '/?' + urlencode({'q': '蜀香居'})
                status, body, headers = self.request(path)
                self.assertEqual(status, 200)
                self.assertIn('text/html', headers['Content-Type'])
                self.assertIn('寻味', body)
                self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
        status, body, headers = self.request('/health')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {'status': 'ok', 'version': '1.0.0'})
        self.assertEqual(self.request('/favicon.ico')[0], 204)
        for path, expected in (('/missing', 404), ('/restaurant/999999', 404),
                               ('/rankings?period=invalid', 400),
                               ('/rankings?period=&source=', 400),
                               ('/recommendations?budget=-1', 400), ('/admin', 403), ('/profile', 302)):
            self.assertEqual(self.request(path)[0], expected, path)

    def test_session_csrf_and_review_lifecycle(self):
        self.assertEqual(self.request('/login', b'username=foodie&password=foodie123',
                                     {'Content-Type': 'application/x-www-form-urlencoded'})[0], 400)
        self.login()
        self.assertEqual(self.request('/profile')[0], 200)
        self.assertEqual(self.request('/admin')[0], 403)
        for _ in range(2):
            status, body, _ = self.post('/favorites/migrate', json_data={'ids': [1, 1, 999999]})
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)['count'], 1)
        self.assertEqual(self.post('/favorites/migrate', json_data={'ids': 5})[0], 400)
        review = dict(rating=5, taste_score=5, environment_score=4, service_score=5,
                      content='真实 HTTP 测试点评，不会写入用户数据库')
        self.assertEqual(self.post('/restaurant/1/review', review)[0], 302)
        with self.app.app_context():
            rid = get_db().execute('SELECT MAX(id) FROM reviews').fetchone()[0]
        self.assertEqual(self.request(f'/review/{rid}/edit')[0], 200)
        review['content'] = '真实 HTTP 更新测试点评'
        self.assertEqual(self.post(f'/review/{rid}/edit', review)[0], 302)
        self.assertEqual(self.post(f'/review/{rid}/delete')[0], 302)
        self.assertEqual(self.post('/logout')[0], 302)
        self.assertEqual(self.request('/profile')[0], 302)

    def test_admin_http_sales_and_restaurant_lifecycle(self):
        self.login('admin', 'admin123')
        for path in ('/admin', '/admin/audit', '/admin/sales', '/admin/restaurant/new'):
            self.assertEqual(self.request(path)[0], 200, path)
        sale = dict(restaurant_id=1, sale_date=date.today().isoformat(), quantity=18)
        self.assertEqual(self.post('/admin/sales', sale)[0], 302)
        sale['quantity'] = -1
        self.assertEqual(self.post('/admin/sales', sale)[0], 400)
        self.assertEqual(self.post('/admin/sales/demo')[0], 302)
        restaurant = dict(name='HTTP测试餐厅', category='川菜', address='隔离测试路', avg_price=50)
        self.assertEqual(self.post('/admin/restaurant/new', restaurant)[0], 302)
        with self.app.app_context():
            rid = get_db().execute('SELECT MAX(id) FROM restaurants').fetchone()[0]
        self.assertEqual(self.request(f'/restaurant/{rid}')[0], 200)
        restaurant['name'] = 'HTTP更新餐厅'
        self.assertEqual(self.post(f'/admin/restaurant/{rid}/edit', restaurant)[0], 302)
        self.assertEqual(self.post(f'/admin/restaurant/{rid}/delete')[0], 302)
        self.assertEqual(self.request(f'/restaurant/{rid}')[0], 404)
