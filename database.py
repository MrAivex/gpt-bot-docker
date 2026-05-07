import asyncpg
from logger_config import logger
from config import DB_DSN, ADMIN_ID
from subscriptions_config import DEFAULT_SUBSCRIPTION
import db_utils

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
                        last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        user_email TEXT,
                        referrer_id BIGINT,
                        chat_id BIGINT
                    );
                                   
                    -- Миграция: добавляем колонки дат, если их нет
                    ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_start TIMESTAMP;
                    ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_end TIMESTAMP;
                    ALTER TABLE users ADD COLUMN IF NOT EXISTS user_email TEXT;
                    ALTER TABLE users ADD COLUMN IF NOT EXISTS referrer_id BIGINT;
                    ALTER TABLE users ADD COLUMN IF NOT EXISTS chat_id BIGINT;
                    
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

#---------------МЕТОДЫ ИЗ DB_UTILS.PY--------------------------------------------
    async def get_all_active_chat_ids(self): # получаем список chat_id для рассылки
            return await db_utils.fetch_active_chats(self.pool)
    
    async def get_referral_users_count(self): # Получаем количество приглашенных пользователей
        return await db_utils.fetch_referral_users_count(self.pool)
    
    async def get_active_chats_count(self): # Получаем количество пользователей у которых есть chat_id
        return await db_utils.fetch_chat_ids_count(self.pool) 
#--------------------------------------------------------------------------------

    async def disconnect(self):
        """Закрываем пул при выключении бота"""
        if self.pool:
            await self.pool.close()
            logger.info("Соединение с PostgreSQL закрыто.")

    async def register_user(self, user_id: int, chat_id: int):
        """Регистрирует пользователя, если его еще нет в базе"""
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO users (user_id, last_active, chat_id)
                VALUES ($1, CURRENT_TIMESTAMP, $2)
                ON CONFLICT (user_id) DO UPDATE 
                SET last_active = CURRENT_TIMESTAMP,
                    chat_id = $2
            ''', user_id, chat_id)
            logger.info(f"Пользователь {user_id} проверен/зарегистрирован в БД")

    async def get_top_users_by_queries(self, limit: int = 10):
        """Возвращает список пользователей с наибольшим количеством запросов"""
        async with self.pool.acquire() as conn:
            # Получаем заданное количество строк, отсортированных по убыванию
            rows = await conn.fetch('''
                SELECT user_id, total_queries, subscription_status 
                FROM users 
                ORDER BY total_queries DESC 
                LIMIT $1
            ''', limit)
            
            # Преобразуем записи БД в список словарей
            return [dict(row) for row in rows]
        
    async def count_active_subscribers(self):
        """Возвращает количество пользователей, у которых подписка не 'inactive'"""
        async with self.pool.acquire() as conn:
            # Используем COUNT для быстрого подсчета без загрузки самих данных
            count = await conn.fetchval('''
                SELECT COUNT(*) 
                FROM users 
                WHERE subscription_status != 'inactive'
            ''')
            return count if count else 0

    async def update_user_email(self, user_id: int, email: str):
        """Сохраняет или обновляет email пользователя"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                'UPDATE users SET user_email = $2 WHERE user_id = $1',
                user_id, email
            )
            logger.info(f"Email для пользователя {user_id} обновлен на {email}")

    async def get_user(self, user_id: int):
        """Получает данные пользователя из базы"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow('SELECT * FROM users WHERE user_id = $1', user_id)
            if row:
                return dict(row) # Превращаем запись в обычный словарь
            return None

    async def check_and_update_user(self, user_id: int, chat_id: int):
        """Проверяет лимиты и обновляет счетчик запросов"""
        # Твой админский фильтр теперь внутри метода
        if user_id in ADMIN_ID:
            return # Админу ничего не списываем

        async with self.pool.acquire() as conn:
            await conn.execute('''
            UPDATE users 
            SET used_queries = used_queries + 1, 
                total_queries = total_queries + 1,
                available_queries = GREATEST(0, available_queries - 1)
                last_active = CURRENT_TIMESTAMP,
                chat_id = $2
            WHERE user_id = $1
        ''', user_id, chat_id)
            
    # database.py

    async def update_user_field(self, user_id: int, field: str, value):
        """Универсальный метод обновления поля пользователя"""
        # Белый список полей для безопасности
        allowed_fields = {
            'used_queries', 'available_queries', 'total_queries', 
            'subscription_status', 'subscription_end', 'subscription_start'
        }
        
        if field not in allowed_fields:
            raise ValueError(f"Поле {field} недоступно для редактирования")

        async with self.pool.acquire() as conn:
            # Используем f-строку ТОЛЬКО для имени поля (которое проверено), 
            # а само значение передаем через параметр $2 для безопасности.
            query = f"UPDATE users SET {field} = $2 WHERE user_id = $1"
            await conn.execute(query, user_id, value)
            
    async def reset_subscription_limits(self, query):
        async with self.pool.acquire() as conn:
            await conn.execute(query)

            logger.info("Лимиты подписчиков динамически обновлены на основе конфига.")

    async def save_message(self, user_id: int, role: str, content: str):
        """Сохраняет сообщение в историю (для памяти)"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO chat_history (user_id, role, content) VALUES ($1, $2, $3)",
                user_id, role, content
            )

#-----------------РЕФЕРАЛКА--------------------------------------------------------
    async def register_user_with_referrer(self, user_id: int, chat_id: int, referrer_id: int = None):
        """Регистрирует пользователя и связывает его с реферером"""
        async with self.pool.acquire() as conn:
            # Проверяем, существует ли уже пользователь
            user = await conn.fetchrow('SELECT * FROM users WHERE user_id = $1', user_id)
            await conn.execute('''
                UPDATE users 
                SET chat_id = $1 
                WHERE user_id = $2 
                               ''', chat_id, user_id)
            if not user:
                # Если реферер указан, проверяем, что это не сам пользователь
                if referrer_id == user_id:
                    referrer_id = None
                    
                await conn.execute('''
                    INSERT INTO users (user_id, referrer_id, available_queries, subscription_status, chat_id)
                        VALUES ($1, $2, 10, 'inactive', $3)
                        ON CONFLICT (user_id) 
                        DO UPDATE SET chat_id = EXCLUDED.chat_id;
                ''', user_id, referrer_id, chat_id)
                return True
            return False
        
    async def add_referral_bonus(self, referrer_id: int, bonus_queries: int = 3):
        """Начисляет бонусные запросы пригласившему"""
        async with self.pool.acquire() as conn:
            await conn.execute('''
                UPDATE users 
                SET available_queries = available_queries + $1 
                WHERE user_id = $2
            ''', bonus_queries, referrer_id)
#-------------------------------------------------------------------------------------

    async def delete_user(self, user_id: int):
        """Полностью удаляет пользователя и все связанные с ним данные из БД"""
        async with self.pool.acquire() as conn:
            # Удаляем пользователя. Если есть внешние ключи с ON DELETE CASCADE, 
            # история сообщений удалится автоматически.
            result = await conn.execute('DELETE FROM users WHERE user_id = $1', user_id)
            
            # Возвращаем True, если строка была удалена, и False, если юзер не найден
            return result == 'DELETE 1'

    async def update_user_subscription(self, user_id, sub_id, duration_days):
        """Активирует подписку пользователю"""
        async with self.pool.acquire() as conn:
            # Например, устанавливаем статус и сбрасываем счетчик использованных запросов
            await conn.execute('''
                UPDATE users 
                SET subscription_status = $1, 
                    used_queries = 0,
                    last_active = CURRENT_TIMESTAMP, 
                    subscription_start = CURRENT_TIMESTAMP,
                    -- Прибавляем дни к текущему времени прямо в SQL
                    subscription_end = GREATEST(CURRENT_TIMESTAMP, COALESCE(subscription_end, CURRENT_TIMESTAMP)) + ($3 || ' days')::interval
                
                WHERE user_id = $2
            ''', sub_id,  int(user_id), str(duration_days))
            logger.info(f"Подписка {sub_id} прописана в БД для {user_id}")
    
    async def deactivate_expired_subscriptions(self, sub_id):
        """Сбрасывает просроченные подписки в 'inactive'"""
        async with self.pool.acquire() as conn:
            available_requests = DEFAULT_SUBSCRIPTION[sub_id]['requests']
            # Находим всех, у кого дата окончания меньше текущей и статус не 'inactive'
            result = await conn.execute('''
                UPDATE users 
                SET subscription_status = $1,
                    available_queries = $2,
                    subscription_start = CURRENT_TIMESTAMP,
                    subscription_end = NULL,
                    last_active = CURRENT_TIMESTAMP,
                    used_queries = 0
                                        
                WHERE subscription_end < CURRENT_TIMESTAMP 
                  AND subscription_status != 'inactive'
            ''', str(sub_id), int(available_requests))
            return result

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

    #-------АДМИНСКИЕ ЗАПРОСЫ---------------------------------------------------------------

    async def get_total_users_count(self):
        """Возвращает общее количество зарегистрированных пользователей"""
        async with self.pool.acquire() as conn:
            count = await conn.fetchval('SELECT COUNT(*) FROM users')
            return count
        
    #---------------------------------------------------------------------------------------

# Создаем экземпляр для экспорта
db = DatabaseManager()