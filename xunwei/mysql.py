"""MySQL 8 backend; application queries retain bound positional parameters."""
import re
from decimal import Decimal
from pathlib import Path
from datetime import datetime
import pymysql
from flask import current_app

TABLES = ('restaurants', 'users', 'dishes', 'reviews', 'favorites', 'app_meta',
          'audit_logs', 'login_attempts', 'daily_sales', 'dish_reviews', 'browsing_history', 'phone_accounts', 'sms_codes', 'sms_limits')


class Row(dict):
    def __getitem__(self, key):
        return tuple(self.values())[key] if isinstance(key, (int, slice)) else super().__getitem__(key)


class Result:
    def __init__(self, cursor):
        self.lastrowid, self.rowcount = cursor.lastrowid, cursor.rowcount
        names = [c[0] for c in cursor.description] if cursor.description else []
        self.rows = [Row(zip(names, ((int(v) if v == v.to_integral_value() else float(v)) if isinstance(v, Decimal) else v for v in r)))
                     for r in cursor.fetchall()] if names else []
        self.position = 0

    def fetchone(self):
        if self.position >= len(self.rows):
            return None
        row = self.rows[self.position]
        self.position += 1
        return row

    def fetchall(self):
        rows = self.rows[self.position:]
        self.position = len(self.rows)
        return rows

    def __iter__(self):
        return iter(self.fetchall())


def translate(sql):
    sql = sql.replace('INSERT OR IGNORE', 'INSERT IGNORE')
    sql = re.sub(r'ON CONFLICT\([^)]+\) DO UPDATE\s+SET', 'ON DUPLICATE KEY UPDATE', sql)
    sql = re.sub(r'excluded\.(\w+)', r'VALUES(\1)', sql)
    # Replace placeholders only outside quoted literals and identifiers.
    parts = re.split(r"('(?:''|\\.|[^'\\])*'|\"(?:\"\"|\\.|[^\"\\])*\"|`[^`]*`)", sql)
    return ''.join(p.replace('%', '%%').replace('?', '%s') if i % 2 == 0
                   else p.replace('%', '%%') for i, p in enumerate(parts))


class Connection:
    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql, params=()):
        with self.raw.cursor() as cursor:
            cursor.execute(translate(sql), tuple(params))
            return Result(cursor)

    def commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()

    def close(self):
        self.raw.close()


def connect(config):
    return Connection(pymysql.connect(
        host=config['MYSQL_HOST'], port=config['MYSQL_PORT'], user=config['MYSQL_USER'],
        password=config['MYSQL_PASSWORD'], database=config['MYSQL_DATABASE'],
        charset='utf8mb4', autocommit=False, connect_timeout=10,
    ))


def initialize(db):
    schema = Path(__file__).with_name('mysql_schema.sql').read_text(encoding='utf-8')
    for statement in schema.split(';'):
        if statement.strip():
            db.execute(statement)
    version = db.execute("SELECT value FROM app_meta WHERE `key`='schema_version'").fetchone()
    if version and int(version[0]) > 6:
        raise RuntimeError('Database schema is newer than this application.')
    columns = {row['Field'] for row in db.execute('SHOW COLUMNS FROM restaurants')}
    missing = [name for name in ('opening_time', 'closing_time') if name not in columns]
    if missing and not current_app.testing:
        backup_database('before-upgrade')
    for name in missing:
        db.execute(f'ALTER TABLE restaurants ADD COLUMN {name} VARCHAR(5) NULL')
    db.execute("INSERT INTO app_meta (`key`,value) VALUES ('schema_version','6') ON DUPLICATE KEY UPDATE value='6'")
    if current_app.config.get('SEED_DEMO'):
        from werkzeug.security import generate_password_hash
        for username, password, role in (('admin', 'admin123', 'admin'), ('foodie', 'foodie123', 'user')):
            if not db.execute('SELECT 1 FROM users WHERE username=?', (username,)).fetchone():
                db.execute('INSERT INTO users(username,password_hash,role,created_at) VALUES (?,?,?,?)',
                           (username, generate_password_hash(password), role, datetime.now().isoformat(timespec='seconds')))
        if not db.execute("SELECT 1 FROM app_meta WHERE `key`='seeded'").fetchone():
            if db.execute('SELECT COUNT(*) FROM restaurants').fetchone()[0] == 0:
                from .seed import seed_data
                seed_data(db)
            db.execute("INSERT INTO app_meta (`key`,value) VALUES ('seeded','1')")
    db.commit()


def backup_database(label='backup'):
    folder = Path(current_app.root_path).parent / 'backups'
    folder.mkdir(exist_ok=True)
    target = folder / f'mysql-{label}-{datetime.now():%Y%m%d-%H%M%S-%f}.sql'
    db = connect(current_app.config)
    try:
        db.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
        db.execute('START TRANSACTION WITH CONSISTENT SNAPSHOT')
        with target.open('x', encoding='utf-8') as output:
            output.write('SET NAMES utf8mb4;\nSET FOREIGN_KEY_CHECKS=0;\n')
            for table in TABLES:
                ddl = db.execute(f'SHOW CREATE TABLE `{table}`').fetchone()[1]
                output.write(ddl.replace('CREATE TABLE ', 'CREATE TABLE IF NOT EXISTS ', 1) + ';\n')
                for row in db.execute(f'SELECT * FROM `{table}`'):
                    columns = ','.join(f'`{k}`' for k in row)
                    values = ','.join(db.raw.escape(v) for v in row.values())
                    output.write(f'INSERT INTO `{table}` ({columns}) VALUES ({values});\n')
            output.write('SET FOREIGN_KEY_CHECKS=1;\n')
        return target
    finally:
        db.close()
