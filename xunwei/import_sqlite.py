"""Copy a consistent SQLite snapshot into an empty MySQL application schema."""
import sqlite3
from collections import Counter
from pathlib import Path
import click
from flask import current_app
from .db import get_db
from .mysql import TABLES, initialize


def migrate_sqlite(source):
    if current_app.config['DATABASE_BACKEND'] != 'mysql':
        raise click.ClickException('Migration target must use the mysql backend.')
    source = Path(source).resolve(strict=True)
    snapshot = sqlite3.connect(':memory:')
    original = sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)
    try:
        original.backup(snapshot)
    finally:
        original.close()
    snapshot.row_factory = sqlite3.Row
    db = get_db()
    counts = {}
    try:
        if snapshot.execute('PRAGMA foreign_key_check').fetchone():
            raise click.ClickException('Source has broken foreign keys; migration cancelled.')
        if snapshot.execute('PRAGMA user_version').fetchone()[0] not in (2, 3, 4, 5, 6):
            raise click.ClickException('Source must be upgraded to schema version 2, 3, 4, 5 or 6 first.')
        initialize(db)
        # Prevent simultaneous invocations of this import command.
        if db.execute("SELECT GET_LOCK('xunwei_sqlite_import',10)").fetchone()[0] != 1:
            raise click.ClickException('Another import is running.')
        try:
            for table in TABLES:
                condition = " WHERE `key` <> 'schema_version'" if table == 'app_meta' else ''
                if db.execute(f'SELECT COUNT(*) FROM `{table}`{condition}').fetchone()[0]:
                    raise click.ClickException('Target must be empty. Existing data was not overwritten.')
            for table in TABLES:
                # Older supported SQLite versions have no dish review table yet.
                exists = snapshot.execute('SELECT 1 FROM sqlite_master WHERE type=? AND name=?', ('table', table)).fetchone()
                rows = [] if table in ('dish_reviews', 'browsing_history', 'phone_accounts', 'sms_codes', 'sms_limits') and not exists else snapshot.execute(f'SELECT * FROM "{table}"').fetchall()
                for row in rows:
                    if table == 'app_meta' and row['key'] == 'schema_version':
                        continue
                    names = ','.join(f'`{name}`' for name in row.keys())
                    marks = ','.join('?' for _ in row)
                    db.execute(f'INSERT INTO `{table}` ({names}) VALUES ({marks})', tuple(row))
                counts[table] = len(rows)
                condition = " WHERE `key` <> 'schema_version'" if table == 'app_meta' else ''
                expected = len([r for r in rows if table != 'app_meta' or r['key'] != 'schema_version'])
                if db.execute(f'SELECT COUNT(*) FROM `{table}`{condition}').fetchone()[0] != expected:
                    raise click.ClickException(f'Row count mismatch: {table}')
                if rows:
                    names = ','.join(f'`{name}`' for name in rows[0].keys())
                    actual = db.execute(f'SELECT {names} FROM `{table}`{condition}').fetchall()
                    expected_rows = [tuple(r) for r in rows if table != 'app_meta' or r['key'] != 'schema_version']
                    if Counter(expected_rows) != Counter(tuple(r.values()) for r in actual):
                        raise click.ClickException(f'Data verification failed: {table}')
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.execute("SELECT RELEASE_LOCK('xunwei_sqlite_import')")
    finally:
        snapshot.close()
    return counts
