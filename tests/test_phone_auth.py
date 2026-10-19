import tempfile
import unittest
import time
from pathlib import Path
from unittest.mock import Mock, patch
from xunwei import create_app
from xunwei.db import init_db, get_db


class PhoneAuthTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app(dict(TESTING=True, DATABASE=str(Path(self.temp.name) / 'test.db'),
                                   SECRET_KEY='phone-test', SMS_DEMO=True))
        with self.app.app_context():
            init_db()
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def post(self, path, **data):
        self.client.get('/phone/login')
        with self.client.session_transaction() as saved:
            token = saved['csrf_token']
        return self.client.post(path, data=dict(data, csrf_token=token))

    def send(self, purpose='register', phone='13800138000'):
        return self.post('/auth/sms/send', phone=phone, purpose=purpose)

    def verify(self, code, purpose='register', **extra):
        return self.post('/phone/' + purpose, phone='13800138000', code=code, **extra)

    def test_register_login_and_replay(self):
        response = self.send()
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        code = response.json['demo_code']
        with self.app.app_context():
            row = get_db().execute('SELECT * FROM sms_codes').fetchone()
            self.assertNotIn(code, row['code_hash'])
        self.assertEqual(self.verify(code).status_code, 302)
        with self.client.session_transaction() as saved:
            uid = saved['user_id']
        self.assertEqual(self.verify(code).status_code, 400)
        self.post('/logout')
        with patch('xunwei.phone_auth.time.time', return_value=time.time() + 61):
            code = self.send('login').json['demo_code']
        self.assertEqual(self.verify(code, 'login', next='https://evil.example').location, '/')
        with self.client.session_transaction() as saved:
            self.assertEqual(saved['user_id'], uid)
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT COUNT(*) FROM users').fetchone()[0], 1)

    def test_expiry_wrong_attempts_and_purpose(self):
        code = self.send().json['demo_code']
        self.assertEqual(self.verify(code, 'login').status_code, 400)
        wrong = '000000' if code != '000000' else '111111'
        for _ in range(5):
            self.assertEqual(self.verify(wrong).status_code, 400)
        self.assertEqual(self.verify(code).status_code, 400)
        with self.app.app_context():
            db = get_db()
            db.execute('UPDATE sms_codes SET attempts=0, expires_at=0')
            db.commit()
        self.assertEqual(self.verify(code).status_code, 400)

    def test_sending_validation_cooldown_and_ip_limit(self):
        self.assertEqual(self.send(phone='123').status_code, 400)
        self.assertEqual(self.send(purpose='reset').status_code, 400)
        self.assertEqual(self.send().status_code, 200)
        self.assertEqual(self.send().status_code, 429)
        for i in range(29):
            self.assertEqual(self.send(phone=f'139{i:08d}').status_code, 200)
        self.assertEqual(self.send(phone='13700137000').status_code, 429)

    def test_unknown_disabled_and_existing_accounts(self):
        code = self.send('login').json['demo_code']
        self.assertEqual(self.verify(code, 'login').status_code, 400)
        with self.app.app_context():
            get_db().execute('DELETE FROM sms_limits')
            get_db().commit()
        code = self.send().json['demo_code']
        self.assertEqual(self.verify(code).status_code, 302)
        with self.app.app_context():
            db = get_db()
            db.execute('DELETE FROM sms_limits')
            db.execute('UPDATE users SET is_active=0')
            db.commit()
        code = self.send('login').json['demo_code']
        self.assertEqual(self.verify(code, 'login').status_code, 400)

    def test_csrf_and_production_never_disclose_codes(self):
        self.assertEqual(self.client.post('/auth/sms/send', data={'phone': '13800138000', 'purpose': 'login'}).status_code, 400)
        self.app.config['PRODUCTION'] = True
        self.assertEqual(self.send().status_code, 503)
        sender = Mock()
        self.app.config['SMS_SENDER'] = sender
        result = self.send()
        self.assertEqual(result.status_code, 200)
        self.assertNotIn('demo_code', result.json)
        sender.assert_called_once()

    def test_delivery_failure_invalidates_code(self):
        self.app.config.update(SMS_DEMO=False, SMS_SENDER=Mock(side_effect=RuntimeError('secret')))
        result = self.send()
        self.assertEqual(result.status_code, 503)
        self.assertNotIn('secret', result.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT COUNT(*) FROM sms_codes').fetchone()[0], 0)

    def test_upgrade_is_repeatable(self):
        with self.app.app_context():
            init_db()
            init_db()
            self.assertEqual(get_db().execute('PRAGMA user_version').fetchone()[0], 6)


if __name__ == '__main__':
    unittest.main()
