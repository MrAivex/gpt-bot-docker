

INIT_QUERIES = '''
-- Таблица пользователей и лимитов
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    used_queries INTEGER DEFAULT 0,
    sub_queries BIGINT DEFAULT 0,
    total_queries INTEGER DEFAULT 0,
    subscription_status TEXT DEFAULT 'inactive',
    subscription_start TIMESTAMP,
    subscription_end TIMESTAMP,
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_email TEXT,
    payment_token TEXT,
    referrer_id BIGINT,
    chat_id BIGINT,
    subscribe_on_channel TEXT DEFAULT 'not_subscribe',
    bonus_queries BIGINT DEFAULT 10,
    selected_model TEXT DEFAULT 'gpt-4o-mini'
);

-- Миграции (добавление колонок, если их нет)
ALTER TABLE users ADD COLUMN IF NOT EXISTS sub_queries BIGINT DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS bonus_queries BIGINT DEFAULT 10;
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_start TIMESTAMP;
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_end TIMESTAMP;
ALTER TABLE users ADD COLUMN IF NOT EXISTS user_email TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS referrer_id BIGINT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS chat_id BIGINT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS payment_token TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscribe_on_channel TEXT DEFAULT 'not_subscribe';
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_status TEXT DEFAULT 'inactive';
ALTER TABLE users ADD COLUMN IF NOT EXISTS selected_model TEXT DEFAULT 'gpt-4o-mini';

CREATE INDEX IF NOT EXISTS idx_user_id ON users(user_id);

-- Таблица истории сообщений (память)
CREATE TABLE IF NOT EXISTS chat_history (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_history_user ON chat_history(user_id);
'''