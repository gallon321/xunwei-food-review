import sqlite3
from pymysql import IntegrityError as MySQLIntegrityError

IntegrityErrors = (sqlite3.IntegrityError, MySQLIntegrityError)
from datetime import datetime
from flask import current_app as app, g
from .seed import seed_data

def get_db():
    if "db" not in g:
        if app.config['DATABASE_BACKEND'] == 'mysql':
            from .mysql import connect
            g.db = connect(app.config)
            return g.db
        if app.config['DATABASE_BACKEND'] != 'sqlite':
            raise RuntimeError('Unsupported DATABASE_BACKEND')
        g.db = sqlite3.connect(app.config["DATABASE"], timeout=15)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    if app.config['DATABASE_BACKEND'] == 'mysql':
        from .mysql import initialize
        initialize(db)
        return
    from .migrations import backup_before_upgrade
    backup_before_upgrade(db)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS restaurants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            address TEXT NOT NULL,
            phone TEXT,
            opening_time TEXT,
            closing_time TEXT,
            description TEXT,
            avg_price INTEGER DEFAULT 0,
            rating REAL DEFAULT 0,
            taste_score REAL DEFAULT 0,
            environment_score REAL DEFAULT 0,
            service_score REAL DEFAULT 0,
            emoji TEXT,
            gradient TEXT
        );
        CREATE TABLE IF NOT EXISTS dishes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            restaurant_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            price INTEGER DEFAULT 0,
            recommend_count INTEGER DEFAULT 0,
            FOREIGN KEY (restaurant_id) REFERENCES restaurants(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            restaurant_id INTEGER NOT NULL,
            author TEXT NOT NULL,
            rating INTEGER NOT NULL,
            taste_score INTEGER DEFAULT 0,
            environment_score INTEGER DEFAULT 0,
            service_score INTEGER DEFAULT 0,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            user_id INTEGER,
            status TEXT NOT NULL DEFAULT 'visible',
            FOREIGN KEY (restaurant_id) REFERENCES restaurants(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS favorites (
            user_id INTEGER NOT NULL,
            restaurant_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (user_id, restaurant_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (restaurant_id) REFERENCES restaurants(id) ON DELETE CASCADE
        );
        """
    )
    columns = {row[1] for row in db.execute("PRAGMA table_info(reviews)")}
    if "user_id" not in columns:
        db.execute("ALTER TABLE reviews ADD COLUMN user_id INTEGER")
    if "status" not in columns:
        db.execute("ALTER TABLE reviews ADD COLUMN status TEXT NOT NULL DEFAULT 'visible'")
    db.commit()
    if app.config.get("SEED_DEMO"):
        from werkzeug.security import generate_password_hash
        for username, password, role in (("admin", "admin123", "admin"), ("foodie", "foodie123", "user")):
            if not db.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
                db.execute("INSERT INTO users (username,password_hash,role,created_at) VALUES (?,?,?,?)",
                           (username, generate_password_hash(password), role, datetime.now().isoformat(timespec="seconds")))
        db.commit()
    db.execute("CREATE TABLE IF NOT EXISTS app_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    if not db.execute("SELECT 1 FROM app_meta WHERE key='seeded'").fetchone():
        if app.config.get("SEED_DEMO") and db.execute("SELECT COUNT(*) FROM restaurants").fetchone()[0] == 0:
            seed_data(db)
        if app.config.get('SEED_DEMO') or db.execute('SELECT COUNT(*) FROM restaurants').fetchone()[0]:
            db.execute("INSERT INTO app_meta VALUES ('seeded','1')")
    from .migrations import migrate
    migrate(db)
    from .services import recalculate_restaurant
    for restaurant in db.execute("SELECT id FROM restaurants").fetchall():
        recalculate_restaurant(restaurant["id"])
    db.commit()
