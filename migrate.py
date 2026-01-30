"""
Скрипт миграции базы данных VPN-бота на версию 3.0
Добавляет поддержку Outline API
"""
import sqlite3
import os

DB_PATH = "vpn_bot.db"


def migrate():
    """Миграция базы данных"""
    if not os.path.exists(DB_PATH):
        print("База данных не найдена, создастся автоматически при запуске бота")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("🔄 Миграция на VPN Bot 3.0...")

    # ==================== СЕРВЕРЫ ====================
    
    try:
        cursor.execute("ALTER TABLE servers ADD COLUMN location TEXT DEFAULT 'Unknown'")
        print("✅ servers.location")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE servers ADD COLUMN country_code TEXT DEFAULT 'XX'")
        print("✅ servers.country_code")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE servers ADD COLUMN flag_emoji TEXT DEFAULT '🌍'")
        print("✅ servers.flag_emoji")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE servers ADD COLUMN outline_api_url TEXT")
        print("✅ servers.outline_api_url")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE servers ADD COLUMN outline_cert TEXT")
        print("✅ servers.outline_cert")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE servers ADD COLUMN is_active INTEGER DEFAULT 1")
        print("✅ servers.is_active")
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute("ALTER TABLE servers ADD COLUMN max_users INTEGER DEFAULT 25")
        print("✅ servers.max_users")
    except sqlite3.OperationalError:
        pass

    # ==================== ПОДПИСКИ ====================
    
    try:
        cursor.execute("ALTER TABLE subscriptions ADD COLUMN outline_key_id TEXT")
        print("✅ subscriptions.outline_key_id")
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute("ALTER TABLE subscriptions ADD COLUMN access_url TEXT")
        print("✅ subscriptions.access_url")
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute("ALTER TABLE subscriptions ADD COLUMN reminder_sent INTEGER DEFAULT 0")
        print("✅ subscriptions.reminder_sent")
    except sqlite3.OperationalError:
        pass

    # ==================== ТАБЛИЦЫ ====================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            referrer_id INTEGER,
            referral_code TEXT UNIQUE,
            trial_used INTEGER DEFAULT 0,
            bonus_days INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("✅ users")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS promo_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            discount_percent INTEGER DEFAULT 0,
            bonus_days INTEGER DEFAULT 0,
            max_uses INTEGER DEFAULT 0,
            current_uses INTEGER DEFAULT 0,
            valid_until TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("✅ promo_codes")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            server_id INTEGER,
            period TEXT NOT NULL,
            os TEXT NOT NULL,
            price INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            is_trial INTEGER DEFAULT 0,
            vpn_key TEXT,
            outline_key_id TEXT,
            access_url TEXT,
            promo_code_id INTEGER,
            starts_at TIMESTAMP,
            expires_at TIMESTAMP,
            reminder_sent INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("✅ subscriptions")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subscription_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            payment_method TEXT NOT NULL,
            payment_id TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            confirmed_at TIMESTAMP
        )
    """)
    print("✅ payments")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS referral_rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER NOT NULL,
            referred_id INTEGER NOT NULL,
            bonus_days INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("✅ referral_rewards")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subscription_id INTEGER,
            user_id INTEGER NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("✅ reviews")

    # Обновляем max_users для существующих серверов
    cursor.execute("UPDATE servers SET max_users = 25 WHERE max_users = 50 OR max_users IS NULL")
    cursor.execute("UPDATE servers SET location = name WHERE location = 'Unknown' OR location IS NULL")

    conn.commit()
    conn.close()

    print("\n🎉 Миграция на VPN Bot 3.0 завершена!")
    print("Запустите бота: python bot.py")


if __name__ == "__main__":
    migrate()
