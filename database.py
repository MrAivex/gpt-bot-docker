import asyncpg
from logger_config import logger
from config import DB_DSN, ADMIN_ID
from subscriptions_config import DEFAULT_SUBSCRIPTION

class DatabaseManager:
    def __init__(self):
        self.pool = None

    async def connect(self):
        """Создаем пул соединений и инициализируем таблицы"""
        try:
            self.pool = await asyncpg.create_pool(DB_DSN)
            async with self.pool.acquire() as conn:
                await conn.execute('''
                    -- Таблица пользователей и лимитов
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        used_queries INTEGER DEFAULT 0,
                        available_queries INTEGER DEFAULT 10,
                        total_queries INTEGER DEFAULT 0,
                        subscription_type TEXT DEFAULT 'inactive',
                        subscription_start TIMESTAMP,
                        subscription_end TIMESTAMP,
                        last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                                   
                    -- Миграция: добавляем колонки дат, если их нет
                    ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_start TIMESTAMP;
                    ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_end TIMESTAMP;
                    
                    -- Добавляем колонку "Подписка", если она отсутствует (для существующих БД)
                    ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_status TEXT DEFAULT 'inactive';
                    
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
                ''')
            logger.info("Пул PostgreSQL и таблицы инициализированы с полем подписки.")
        except Exception as e:
            logger.error(f"Ошибка подключения к БД: {e}")
            raise

    async def disconnect(self):
        """Закрываем пул при выключении бота"""
        if self.pool:
            await self.pool.close()
            logger.info("Соединение с PostgreSQL закрыто.")

    async def register_user(self, user_id: int):
        """Регистрирует пользователя, если его еще нет в базе"""
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO users (user_id, last_active)
                VALUES ($1, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id) DO UPDATE 
                SET last_active = CURRENT_TIMESTAMP
            ''', user_id)
            logger.info(f"Пользователь {user_id} проверен/зарегистрирован в БД")

    async def get_user(self, user_id: int):
        """Получает данные пользователя из базы"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow('SELECT * FROM users WHERE user_id = $1', user_id)
            if row:
                return dict(row) # Превращаем запись в обычный словарь
            return None

    async def check_and_update_user(self, user_id: int):
        """Проверяет лимиты и обновляет счетчик запросов"""
        # Твой админский фильтр теперь внутри метода
        if user_id == ADMIN_ID:
            return 999

        async with self.pool.acquire() as conn:
            user = await conn.fetchrow('''
                INSERT INTO users (user_id) 
                VALUES ($1) 
                ON CONFLICT (user_id) DO UPDATE 
                SET used_queries = users.used_queries + 1, 
                    total_queries = users.total_queries + 1,
                    available_queries = users.available_queries - 1,
                    last_active = CURRENT_TIMESTAMP
                RETURNING available_queries
            ''', user_id)
            return user['available_queries']

    async def save_message(self, user_id: int, role: str, content: str):
        """Сохраняет сообщение в историю (для памяти)"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO chat_history (user_id, role, content) VALUES ($1, $2, $3)",
                user_id, role, content
            )

    async def update_user_subscription(self, user_id, sub_id, duration_days):
        """Активирует подписку пользователю"""
        async with self.pool.acquire() as conn:
            # Например, устанавливаем статус и сбрасываем счетчик использованных запросов
            await conn.execute('''
                UPDATE users 
                SET subscription_status = $1, 
                    used_queries = 0,
                    last_active = CURRENT_TIMESTAMP 
                               
                    subscription_start = CURRENT_TIMESTAMP,
                    -- Прибавляем дни к текущему времени прямо в SQL
                    subscription_end = CURRENT_TIMESTAMP + ($3 || ' days')::interval
                
                WHERE user_id = $2
            ''', sub_id,  int(user_id), str(duration_days))
            logger.info(f"Подписка {sub_id} прописана в БД для {user_id}")
    
    async def deactivate_expired_subscriptions(self, sub_id):
        """Сбрасывает просроченные подписки в 'inactive'"""
        async with self.pool.acquire() as conn:
            logger.info("okak")
            available_requests = DEFAULT_SUBSCRIPTION[sub_id]['requests']
            # Находим всех, у кого дата окончания меньше текущей и статус не 'inactive'
            result = await conn.execute('''
                UPDATE users 
                SET subscription_status = $1,
                    available_queries = $2,
                    subscription_start = CURRENT_TIMESTAMP,
                    subscription_end = CURRENT_TIMESTAMP,
                    last_active = CURRENT_TIMESTAMP,
                    used_queries = 0
                                        
                WHERE subscription_end < CURRENT_TIMESTAMP 
                  AND subscription_status != 'inactive'
            ''', str(sub_id), int(available_requests))
            return result

    # В database.py
    async def get_recent_history(self, user_id: int, limit: int = 10):
        """Получает историю в правильном порядке: от старых к новым"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT role, content FROM (
                    SELECT role, content, created_at 
                    FROM chat_history 
                    WHERE user_id = $1 
                    ORDER BY created_at DESC 
                    LIMIT $2
                ) AS subquery
                ORDER BY created_at ASC
            ''', user_id, limit)
            return [{"role": r['role'], "content": r['content']} for r in rows]
        
    async def clear_old_history(self):
        """Удаляет старую историю переписки"""
        async with self.pool.acquire() as conn:
        # Удаляем записи старше 3 дней
            await conn.execute("DELETE FROM chat_history WHERE created_at < NOW() - INTERVAL '3 days'")

    async def delete_user_history(self, user_id: int):
        """Полное удаление истории сообщений конкретного пользователя"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM chat_history WHERE user_id = $1", 
                user_id
            )
            logger.info(f"История пользователя {user_id} полностью очищена.")

# Создаем экземпляр для экспорта
db = DatabaseManager()