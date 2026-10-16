"""Run existing business tests on an explicitly designated disposable MySQL schema.
Usage: set MYSQL_TEST_DATABASE to a dedicated schema ending in _test, grant the
configured application account access to it, then python scripts/test_mysql.py.
All tables in that schema are dropped between tests. Never use a business schema.
"""
import os
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))
from xunwei import create_app
from xunwei.mysql import connect, TABLES
import test_app, test_project, test_discovery

name = os.environ.get('MYSQL_TEST_DATABASE', '')
if not name.endswith('_test') or name == create_app({'TESTING': True}).config['MYSQL_DATABASE']:
    raise SystemExit('MYSQL_TEST_DATABASE must designate a separate disposable schema ending in _test.')


def mysql_app(config=None):
    config = dict(config or {})
    config.update(DATABASE_BACKEND='mysql', MYSQL_DATABASE=name)
    app = create_app(config)
    with app.app_context():
        db = connect(app.config)
        try:
            for table in reversed(TABLES):
                db.execute(f'DROP TABLE IF EXISTS `{table}`')
            db.commit()
        finally:
            db.close()
    return app


for module in (test_app, test_project, test_discovery):
    module.create_app = mysql_app
suite = unittest.TestSuite()
for case in (test_app.XunweiTestCase, test_discovery.DiscoveryTest, test_project.ProjectTest):
    for method in case.__dict__:
        if not method.startswith('test_'):
            continue
        if method in ('test_seed_shops_preserves_records_and_is_repeatable', 'test_factory_isolation_and_no_implicit_demo',
                      'test_empty_install_can_enable_demo_later', 'test_backup_and_version',
                      'test_legacy_migration_preserves_data_and_creates_backup'):
            continue
        suite.addTest(case(method))
result = unittest.TextTestRunner(verbosity=1).run(suite)
raise SystemExit(not result.wasSuccessful())
