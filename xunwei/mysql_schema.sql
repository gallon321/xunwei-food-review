
        CREATE TABLE IF NOT EXISTS restaurants (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(255) NOT NULL,
            category VARCHAR(255) NOT NULL,
            address VARCHAR(255) NOT NULL,
            phone VARCHAR(255),
            opening_time VARCHAR(5),
            closing_time VARCHAR(5),
            description TEXT,
            avg_price INTEGER DEFAULT 0,
            rating REAL DEFAULT 0,
            taste_score REAL DEFAULT 0,
            environment_score REAL DEFAULT 0,
            service_score REAL DEFAULT 0,
            emoji VARCHAR(255),
            gradient VARCHAR(255)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
        CREATE TABLE IF NOT EXISTS dishes (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            restaurant_id INTEGER NOT NULL,
            name VARCHAR(255) NOT NULL,
            price INTEGER DEFAULT 0,
            recommend_count INTEGER DEFAULT 0,
            FOREIGN KEY (restaurant_id) REFERENCES restaurants(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            restaurant_id INTEGER NOT NULL,
            author VARCHAR(255) NOT NULL,
            rating INTEGER NOT NULL,
            taste_score INTEGER DEFAULT 0,
            environment_score INTEGER DEFAULT 0,
            service_score INTEGER DEFAULT 0,
            content TEXT NOT NULL,
            created_at VARCHAR(255) NOT NULL,
            user_id INTEGER,
            status VARCHAR(16) NOT NULL DEFAULT 'visible',
            INDEX idx_reviews_restaurant(restaurant_id,status,created_at),
            INDEX idx_reviews_user(user_id,created_at),
            FOREIGN KEY (restaurant_id) REFERENCES restaurants(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            username VARCHAR(20) COLLATE utf8mb4_bin NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role VARCHAR(255) NOT NULL DEFAULT 'user',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at VARCHAR(255) NOT NULL,
            session_version INTEGER NOT NULL DEFAULT 0
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
        CREATE TABLE IF NOT EXISTS favorites (
            user_id INTEGER NOT NULL,
            restaurant_id INTEGER NOT NULL,
            created_at VARCHAR(255) NOT NULL,
            PRIMARY KEY (user_id, restaurant_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (restaurant_id) REFERENCES restaurants(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
        
CREATE TABLE IF NOT EXISTS app_meta (`key` VARCHAR(64) PRIMARY KEY, value TEXT NOT NULL) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS audit_logs (id INTEGER PRIMARY KEY AUTO_INCREMENT, actor_id INTEGER,
 action TEXT NOT NULL, target TEXT NOT NULL, created_at VARCHAR(32) NOT NULL) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS login_attempts (identity VARCHAR(255) PRIMARY KEY, failures INTEGER NOT NULL,
 started_at DOUBLE NOT NULL) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
CREATE TABLE IF NOT EXISTS daily_sales (restaurant_id INTEGER NOT NULL, sale_date VARCHAR(10) NOT NULL,
 quantity INTEGER NOT NULL CHECK(quantity BETWEEN 0 AND 1000000),
 source VARCHAR(10) NOT NULL DEFAULT 'manual' CHECK(source IN ('manual','demo')),
 updated_at VARCHAR(32) NOT NULL, PRIMARY KEY(restaurant_id,sale_date),
 FOREIGN KEY(restaurant_id) REFERENCES restaurants(id) ON DELETE CASCADE,
 INDEX idx_daily_sales_date(sale_date,restaurant_id)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS dish_reviews (
 id INTEGER PRIMARY KEY AUTO_INCREMENT,
 dish_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
 rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5), content TEXT NOT NULL,
 created_at VARCHAR(255) NOT NULL, status VARCHAR(16) NOT NULL DEFAULT 'visible',
 INDEX idx_dish_reviews(dish_id,status,created_at,id),
 FOREIGN KEY(dish_id) REFERENCES dishes(id) ON DELETE CASCADE,
 FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
CREATE TABLE IF NOT EXISTS browsing_history (
 user_id INTEGER NOT NULL, restaurant_id INTEGER NOT NULL, viewed_at VARCHAR(32) NOT NULL,
 PRIMARY KEY(user_id,restaurant_id), INDEX idx_browsing_user(user_id,viewed_at,restaurant_id),
 FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
 FOREIGN KEY(restaurant_id) REFERENCES restaurants(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;


        CREATE TABLE IF NOT EXISTS phone_accounts (
            phone VARCHAR(11) PRIMARY KEY,
            user_id INTEGER NOT NULL UNIQUE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS sms_codes (
            phone VARCHAR(11) NOT NULL,
            purpose VARCHAR(10) NOT NULL,
            code_hash VARCHAR(64) NOT NULL,
            expires_at DOUBLE NOT NULL,
            attempts INTEGER NOT NULL,
            sent_at DOUBLE NOT NULL,
            PRIMARY KEY(phone,purpose)
        );
        CREATE TABLE IF NOT EXISTS sms_limits (
            identity VARCHAR(64) PRIMARY KEY,
            hits INTEGER NOT NULL,
            expires_at DOUBLE NOT NULL
        );
