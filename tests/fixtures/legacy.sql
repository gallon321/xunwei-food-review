CREATE TABLE IF NOT EXISTS restaurants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            address TEXT NOT NULL,
            phone TEXT,
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
INSERT INTO restaurants (id,name,category,address) VALUES (99,'迁移保留餐厅','川菜','原有地址');
INSERT INTO reviews (restaurant_id,author,rating,content,created_at) VALUES (99,'旧用户',5,'迁移保留的历史点评','2025-01-01');
