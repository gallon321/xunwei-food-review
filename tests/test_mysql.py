import unittest
from decimal import Decimal
from unittest.mock import Mock, patch
import pymysql
from xunwei.mysql import Result, Row, translate, initialize
from xunwei import create_app


class MySQLAdapterTest(unittest.TestCase):
    def test_hours_upgrade_only_adds_missing_columns_and_backs_up_first(self):
        db = Mock()
        def execute(sql, params=()):
            result = Mock()
            result.fetchone.return_value = Row(value='2')
            result.__iter__ = Mock(return_value=iter([{'Field': 'id'}, {'Field': 'opening_time'}]))
            return result
        db.execute.side_effect = execute
        app = create_app({'TESTING': False, 'SEED_DEMO': False, 'SECRET_KEY': 'mysql-migration-test'})
        with app.app_context(), patch('xunwei.mysql.backup_database') as backup:
            def check_backup(label):
                self.assertEqual(label, 'before-upgrade')
                self.assertFalse(any('ALTER TABLE' in call.args[0] for call in db.execute.call_args_list))
            backup.side_effect = check_backup
            initialize(db)
            backup.assert_called_once()
        alters = [call.args[0] for call in db.execute.call_args_list if 'ALTER TABLE' in call.args[0]]
        self.assertEqual(alters, ['ALTER TABLE restaurants ADD COLUMN closing_time VARCHAR(5) NULL'])
        db.commit.assert_called_once()

    def test_placeholder_literals_and_upserts(self):
        self.assertEqual(translate("SELECT '?' AS label WHERE name LIKE ?"), "SELECT '?' AS label WHERE name LIKE %s")
        sql = translate("INSERT INTO daily_sales VALUES (?,?,?,'manual',?) ON CONFLICT(restaurant_id,sale_date) DO UPDATE SET quantity=excluded.quantity")
        self.assertIn('ON DUPLICATE KEY UPDATE quantity=VALUES(quantity)', sql)
        self.assertEqual(translate('INSERT OR IGNORE INTO favorites VALUES (?,?,?)'),
                         'INSERT IGNORE INTO favorites VALUES (%s,%s,%s)')

    def test_parameter_values_are_escaped_by_driver(self):
        raw = pymysql.connect(defer_connect=True)
        raw.server_status = 0
        sql = raw.cursor().mogrify(translate("SELECT '100%' WHERE name=?"), ("a' OR 1=1 --",))
        self.assertIn("SELECT '100%'", sql)
        self.assertIn("a\\' OR 1=1 --", sql)

    def test_buffered_rows_support_names_positions_and_mapping(self):
        cursor = Mock(lastrowid=7, rowcount=2, description=[('rating',), ('name',), ('sales',)])
        cursor.fetchall.return_value = [(Decimal('4.5'), '川菜', Decimal('18')), (None, '日料', Decimal('0'))]
        result = Result(cursor)
        row = result.fetchone()
        self.assertEqual(row[0], 4.5)
        self.assertEqual(row[:], (4.5, '川菜', 18))
        self.assertIsInstance(row['sales'], int)
        self.assertEqual(dict(row), dict(rating=4.5, name='川菜', sales=18))
        self.assertEqual(result.fetchall()[0]['name'], '日料')
        self.assertIsNone(result.fetchone())

    def test_mysql_is_default_and_sqlite_is_explicit(self):
        self.assertEqual(create_app({'TESTING': True}) .config['DATABASE_BACKEND'], 'mysql')
        self.assertEqual(create_app({'TESTING': True, 'DATABASE': ':memory:'}).config['DATABASE_BACKEND'], 'sqlite')
