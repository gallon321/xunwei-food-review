import os
import re
import tempfile
import unittest
from unittest.mock import patch

from werkzeug.security import generate_password_hash
from xunwei import create_app
from xunwei.db import get_db, init_db
from xunwei.hours import business_hours, valid_hours


class BusinessHoursTest(unittest.TestCase):
    def test_boundaries_and_overnight(self):
        for start, end, now, opened in [
            ('09:00', '18:00', '08:59', False),
            ('09:00', '18:00', '09:00', True),
            ('09:00', '18:00', '18:00', False),
            ('20:00', '02:00', '23:59', True),
            ('20:00', '02:00', '00:00', True),
            ('20:00', '02:00', '02:00', False),
            ('20:00', '02:00', '19:59', False),
            ('00:00', '00:00', '12:00', True),
            (None, None, '12:00', False),
        ]:
            with self.subTest(start=start, end=end, now=now):
                self.assertEqual(business_hours(dict(opening_time=start, closing_time=end), now)['is_open'], opened)

    def test_validation(self):
        self.assertTrue(valid_hours('', ''))
        self.assertTrue(valid_hours('20:00', '02:00'))
        for start, end in [('9:00', '18:00'), ('24:00', '18:00'), ('12:60', '18:00'),
                           ('09:00', ''), ('', '18:00'), ('09:00:00', '18:00')]:
            self.assertFalse(valid_hours(start, end))


class BusinessHoursIntegrationTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        self.app = create_app(dict(TESTING=True, DATABASE=self.path, SECRET_KEY='test', CSRF_ENABLED=False))
        self.client = self.app.test_client()
        with self.app.app_context():
            init_db()
            db = get_db()
            db.execute("INSERT INTO users(username,password_hash,role,created_at) VALUES (?,?,?,?)",
                       ('admin', generate_password_hash('password'), 'admin', '2026-10-16'))
            # Open shops must move across the page boundary, including a low-rated shop.
            for i in range(1, 10):
                db.execute('''INSERT INTO restaurants(id,name,category,address,avg_price,rating,
                    opening_time,closing_time) VALUES (?,?,?,?,?,?,?,?)''',
                    (i, f'测试店{i}', '川菜', '北京', i * 10, 5 - i / 10,
                     '09:00' if i > 6 else '20:00', '18:00' if i > 6 else '02:00'))
            db.commit()

    def tearDown(self):
        os.unlink(self.path)

    def ids(self, url):
        return [int(v) for v in re.findall(r'data-card-id="(\d+)"', self.client.get(url).get_data(as_text=True))]

    @patch('xunwei.catalog.current_time', return_value='12:00')
    def test_priority_before_pagination_and_secondary_sort(self, clock):
        self.assertEqual(self.ids('/?q=测试'), [7, 8, 9, 1, 2, 3])
        self.assertEqual(self.ids('/?q=测试&page=2'), [4, 5, 6])
        self.assertEqual(self.ids('/?q=测试&sort=price_desc'), [9, 8, 7, 6, 5, 4])
        self.assertEqual(self.ids('/?q=测试&category=中餐&location=北京&favorites=1&ids=1,8'), [8, 1])
        html = self.client.get('/?q=测试').get_data(as_text=True)
        self.assertIn('营业中', html)
        self.assertIn('休息中', html)
        self.assertIn('每日 20:00–次日 02:00', html)

    @patch('xunwei.catalog.current_time', return_value='00:30')
    def test_sql_overnight_and_unknown(self, clock):
        with self.app.app_context():
            db = get_db()
            db.execute("UPDATE restaurants SET opening_time=NULL,closing_time=NULL WHERE id=1")
            db.execute("UPDATE restaurants SET opening_time='00:00',closing_time='00:00' WHERE id=9")
            db.commit()
        self.assertEqual(self.ids('/?sort=price_asc'), [2, 3, 4, 5, 6, 9])
        self.assertIn('营业时间未设置', self.client.get('/restaurant/1').get_data(as_text=True))
        self.assertIn('全天营业', self.client.get('/restaurant/9').get_data(as_text=True))

    def test_admin_create_edit_and_validation(self):
        self.client.post('/login', data=dict(username='admin', password='password'))
        data = dict(name='新店', category='川菜', address='北京', avg_price='30', opening_time='20:00', closing_time='02:00')
        self.assertEqual(self.client.post('/admin/restaurant/new', data=data).status_code, 302)
        with self.app.app_context():
            row = get_db().execute("SELECT * FROM restaurants WHERE name='新店'").fetchone()
            rid = row['id']
            self.assertEqual((row['opening_time'], row['closing_time']), ('20:00', '02:00'))
        url = f'/admin/restaurant/{rid}/edit'
        self.assertIn('value="20:00"', self.client.get(url).get_data(as_text=True))
        for bad in ['24:00', '9:00', '09:60', '']:
            self.assertEqual(self.client.post(url, data={**data, 'opening_time': bad}).status_code, 400)
        self.assertEqual(self.client.post(url, data={**data, 'opening_time': '', 'closing_time': ''}).status_code, 302)
        self.assertIn('营业时间未设置', self.client.get(f'/restaurant/{rid}').get_data(as_text=True))

    def test_upgrade_from_v2_preserves_data_and_is_repeatable(self):
        with self.app.app_context():
            db = get_db()
            db.execute('ALTER TABLE restaurants DROP COLUMN opening_time')
            db.execute('ALTER TABLE restaurants DROP COLUMN closing_time')
            db.execute('PRAGMA user_version=2')
            db.commit()
            init_db()
            init_db()
            row = db.execute('SELECT * FROM restaurants WHERE id=1').fetchone()
            self.assertEqual(row['name'], '测试店1')
            self.assertIsNone(row['opening_time'])
            self.assertIsNone(row['closing_time'])
            from xunwei.migrations import SCHEMA_VERSION
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], SCHEMA_VERSION)
