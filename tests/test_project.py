import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path
from xunwei import create_app
from xunwei.db import get_db, init_db
from xunwei.migrations import backup_database, SCHEMA_VERSION


class ProjectTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app(dict(TESTING=True, DATABASE=str(Path(self.temp.name) / 'test.db'),
                                   SECRET_KEY='test-secret', SEED_DEMO=True))
        with self.app.app_context():
            init_db()
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def post(self, path, data=None, client=None):
        client = client or self.client
        client.get('/login')
        with client.session_transaction() as saved:
            token = saved['csrf_token']
        return client.post(path, data=dict(data or {}, csrf_token=token))

    def login(self, client=None, username='admin', password='admin123'):
        return self.post('/login', dict(username=username, password=password), client)

    def test_password_revokes_other_sessions(self):
        other = self.app.test_client()
        self.login()
        self.login(other)
        response = self.post('/settings', dict(current_password='admin123', password='New-password-123', confirm_password='New-password-123'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(other.get('/profile').status_code, 302)
        self.assertEqual(self.login(password='New-password-123').status_code, 302)
        self.assertEqual(self.client.get('/profile').status_code, 200)

    def test_rate_limit(self):
        for _ in range(10):
            self.login(password='wrong-password')
        self.assertEqual(self.login(password='wrong-password').status_code, 429)

    def test_dishes_and_audit(self):
        self.login()
        self.assertEqual(self.post('/admin/restaurant/1/dishes', dict(name='项目测试菜', price='32')).status_code, 302)
        with self.app.app_context():
            dish_id = get_db().execute("SELECT id FROM dishes WHERE name='项目测试菜'").fetchone()[0]
        self.assertIn('项目测试菜', self.client.get('/restaurant/1').get_data(as_text=True))
        self.assertEqual(self.post('/admin/restaurant/2/dishes', dict(dish_id=dish_id, name='越权目标', price=8)).status_code, 404)
        self.assertEqual(self.post('/admin/restaurant/1/dishes', dict(dish_id=dish_id, name='更新菜品', price=40)).status_code, 302)
        self.assertEqual(self.post(f'/admin/restaurant/1/dish/{dish_id}/delete').status_code, 302)
        self.assertIn('删除菜品', self.client.get('/admin/audit').get_data(as_text=True))
        self.post('/logout')
        self.login(username='foodie', password='foodie123')
        self.assertEqual(self.client.get('/admin/restaurant/1/dishes').status_code, 403)
        self.assertEqual(self.client.get('/admin/audit').status_code, 403)

    def test_factory_isolation_and_no_implicit_demo(self):
        other_app = create_app(dict(TESTING=True, DATABASE=str(Path(self.temp.name) / 'empty.db'), SECRET_KEY='another'))
        with other_app.app_context():
            init_db()
            self.assertEqual(get_db().execute('SELECT COUNT(*) FROM users').fetchone()[0], 0)
            self.assertEqual(get_db().execute('SELECT COUNT(*) FROM restaurants').fetchone()[0], 0)
        self.assertEqual(self.client.get('/health').json['status'], 'ok')
        self.assertIn('蜀香居', self.client.get('/restaurant/1').get_data(as_text=True))

    def test_empty_install_can_enable_demo_later(self):
        new_path = Path(self.temp.name) / 'fresh.db'
        fresh = create_app(dict(TESTING=True, DATABASE=str(new_path), SECRET_KEY='fresh-key'))
        runner = fresh.test_cli_runner()
        self.assertEqual(runner.invoke(args=['init-db']).exit_code, 0)
        with fresh.app_context():
            self.assertEqual(get_db().execute('SELECT COUNT(*) FROM restaurants').fetchone()[0], 0)
        self.assertEqual(runner.invoke(args=['init-db', '--demo']).exit_code, 0)
        with fresh.app_context():
            self.assertEqual(get_db().execute('SELECT COUNT(*) FROM restaurants').fetchone()[0], 8)
            self.assertEqual(get_db().execute('SELECT COUNT(*) FROM users').fetchone()[0], 2)

    def test_backup_and_version(self):
        with self.app.app_context():
            target = backup_database(get_db())
            init_db()
            self.assertEqual(get_db().execute('PRAGMA user_version').fetchone()[0], SCHEMA_VERSION)
        with closing(sqlite3.connect(target)) as backup:
            self.assertEqual(backup.execute('SELECT COUNT(*) FROM restaurants').fetchone()[0], 8)

    def test_cli_admin_and_production_config(self):
        runner = self.app.test_cli_runner()
        result = runner.invoke(args=['create-admin', '--username', 'manager', '--password', 'Another-password'])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self.login(username='manager', password='Another-password').status_code, 302)
        self.assertEqual(self.client.get('/admin').status_code, 200)
        with self.assertRaises(RuntimeError):
            create_app(dict(TESTING=True, PRODUCTION=True, SECRET_KEY=None))

    def test_csrf_stays_enabled_in_testing(self):
        self.assertEqual(self.client.post('/login', data={'username': 'admin', 'password': 'admin123'}).status_code, 400)
        self.assertEqual(self.login().status_code, 302)

    def test_legacy_migration_preserves_data_and_creates_backup(self):
        path = Path(self.temp.name) / 'legacy.db'
        with closing(sqlite3.connect(path)) as db:
            db.executescript((Path(__file__).parent / 'fixtures' / 'legacy.sql').read_text(encoding='utf-8'))
            db.commit()
        legacy = create_app(dict(DATABASE=str(path), SECRET_KEY='migration-test', SEED_DEMO=False))
        with legacy.app_context():
            init_db()
            init_db()
            self.assertEqual(get_db().execute('SELECT name FROM restaurants WHERE id=99').fetchone()[0], '迁移保留餐厅')
            self.assertEqual(get_db().execute('SELECT COUNT(*) FROM reviews').fetchone()[0], 1)
            self.assertIn('session_version', {r[1] for r in get_db().execute('PRAGMA table_info(users)')})
        self.assertEqual(len(list((path.parent / 'backups').glob('legacy-before-upgrade-*.db'))), 1)


if __name__ == '__main__':
    unittest.main()
