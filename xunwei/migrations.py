"""Additive schema upgrades and SQLite-consistent pre-upgrade backup."""
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from flask import current_app

SCHEMA_VERSION = 4


def backup_before_upgrade(db):
    version = db.execute('PRAGMA user_version').fetchone()[0]
    if version > SCHEMA_VERSION:
        raise RuntimeError('Database schema is newer than this application.')
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE name='restaurants'").fetchone()
    if exists and version < SCHEMA_VERSION and not current_app.testing:
        backup_database(db, 'before-upgrade')


def backup_database(db, label='backup'):
    if current_app.config['DATABASE_BACKEND'] == 'mysql':
        from .mysql import backup_database as mysql_backup
        return mysql_backup(label)
    source = Path(current_app.config['DATABASE']).resolve()
    folder = source.parent / 'backups'
    folder.mkdir(exist_ok=True)
    target = folder / f'{source.stem}-{label}-{datetime.now():%Y%m%d-%H%M%S-%f}.db'
    with closing(sqlite3.connect(target)) as destination:
        db.backup(destination)
    return target


def migrate(db):
    if db.execute('PRAGMA user_version').fetchone()[0] >= SCHEMA_VERSION:
        return
    columns = {r[1] for r in db.execute('PRAGMA table_info(users)')}
    if 'session_version' not in columns:
        db.execute('ALTER TABLE users ADD COLUMN session_version INTEGER NOT NULL DEFAULT 0')
    columns = {r[1] for r in db.execute('PRAGMA table_info(restaurants)')}
    for name in ('opening_time', 'closing_time'):
        if name not in columns:
            db.execute(f'ALTER TABLE restaurants ADD COLUMN {name} TEXT')
    db.executescript('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_id INTEGER, action TEXT NOT NULL, target TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS login_attempts (
            identity TEXT PRIMARY KEY, failures INTEGER NOT NULL, started_at REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_reviews_restaurant ON reviews(restaurant_id, status, created_at);
        CREATE INDEX IF NOT EXISTS idx_reviews_user ON reviews(user_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_dishes_restaurant ON dishes(restaurant_id);
        CREATE INDEX IF NOT EXISTS idx_restaurants_category ON restaurants(category);
        CREATE TABLE IF NOT EXISTS daily_sales (
            restaurant_id INTEGER NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
            sale_date TEXT NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity >= 0 AND quantity <= 1000000),
            source TEXT NOT NULL DEFAULT 'manual' CHECK(source IN ('manual','demo')),
            updated_at TEXT NOT NULL,
            PRIMARY KEY (restaurant_id, sale_date)
        );
        CREATE INDEX IF NOT EXISTS idx_daily_sales_date ON daily_sales(sale_date, restaurant_id);
        CREATE TABLE IF NOT EXISTS dish_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dish_id INTEGER NOT NULL REFERENCES dishes(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'visible' CHECK(status IN ('visible','hidden'))
        );
        CREATE INDEX IF NOT EXISTS idx_dish_reviews ON dish_reviews(dish_id,status,created_at,id);
        PRAGMA user_version = 4;
    ''')
    db.commit()
