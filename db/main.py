from db.utils import DBUtils
import asyncpg
from config.logger import logger
from config.main import DB_DSN
from config.subscriptions import DEFAULT_SUBSCRIPTION, AVAILABLE_SUBSCRIPTIONS
from db.init import INIT_QUERIES
from datetime import datetime


class DBMain(DBUtils):
    def __init__(self):
        super().__init__(pool=None)

    async def connect(self):
        try:
            self.pool = await asyncpg.create_pool(DB_DSN)
            DBUtils.__init__(self, self.pool)

            async with self.pool.acquire() as conn:
                await conn.execute(INIT_QUERIES)

            logger.info("Пул PostgreSQL и таблицы инициализированы с полем подписки.")
            
        except Exception as e:
            logger.error(f"Ошибка подключения к БД: {e}")
            raise

    async def disconnect(self):
        if self.pool:
            await self.pool.close()
            logger.info("Соединение с PostgreSQL закрыто.")

#---------------МЕТОДЫ ИЗ DB_UTILS.PY--------------------------------------------
    async def get_all_active_chat_ids(self): # Получает список chat_id где они есть
        chat_ids = await self._fetch(
            table="users",
            columns=["chat_id"],
            filters={"chat_id": "IS NOT NULL"}
        )
        
        unique_chats = list(set(chat_ids))
        return unique_chats
    
    async def get_referral_users_count(self): # Получаем количество приглашенных пользователей
        return await self._count(
            table="users",
            filters={"referrer_id": "IS NOT NULL"}
        )
    
    async def get_active_chats_count(self): # Получаем количество пользователей у которых есть chat_id
        return await self._count(
            table="users",
            filters={"chat_id": "IS NOT NULL"}
        )
    
    async def get_users_for_renewal(self): # Список пользователей для автопродления подписки
        return self._fetch(
            table="users",
            columns=["subscription_status", "user_id", "chat_id", "user_email", "payment_token", "subscription_end"],
            filters={
                "subscription_status": {"op": "!=", "val": "inactive"},
                "chat_id": "IS NOT NULL",
                "user_email": "IS NOT NULL",
                "payment_token": "IS NOT NULL"
            }
        )
    
    async def update_user_activity(self, user_id: int, chat_id: int):
        query = '''
            INSERT INTO users (user_id, chat_id, last_active, bonus_queries, subscription_status, sub_queries)
            VALUES ($1, $2, CURRENT_TIMESTAMP, 10, 'inactive', 0)
            ON CONFLICT (user_id) DO UPDATE 
            SET chat_id = EXCLUDED.chat_id, 
                last_active = CURRENT_TIMESTAMP
        '''
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(query, user_id, chat_id)
        except Exception as e:
            logger.error(f"Ошибка в update_user_activity: {e}")

    async def decrement_queries(self, user_id: int) -> bool:
        user = await self.get_user(user_id)
        if not user:
            return False

        sub_q = user.sub_queries
        bonus_q = user.bonus_queries

        if sub_q > 0:
            await self._update(table="users", record_id=user_id, id_col="user_id", sub_queries=sub_q - 1)
            return True
        elif bonus_q > 0:
            await self._update(table="users", record_id=user_id, id_col="user_id", bonus_queries=bonus_q - 1)
            return True

        return False

    async def get_top_users_by_queries(self, limit: int = 10):
        return await self._fetch(
            table="users",
            columns=["user_id", "total_queries", "subscription_status"],
            order_by="total_queries DESC",
            limit=limit
        )
    
    async def count_active_subscriptions(self):
        return await self._count(
            table="users",
            filters={
                "subscription_status": {"op": "!=", "val": "inactive"}
            }
        )
    
    async def update_user_email(self, user_id: int, email: str):
        await self._update(table="users", record_id=user_id, id_col="user_id", user_email=email)
        logger.info(f"Email для пользователя {user_id} обновлен на {email}")

    async def get_user(self, user_id: int):
        return await self._get(table="users", record_id=user_id, id_col="user_id")

    async def reset_subscription_limits(self, subscriptions_config: dict):
        await self._bulk_update_limits(
            table="users",
            status_col="subscription_status",
            limit_col="sub_queries",
            config=subscriptions_config
        )

    async def save_message(self, user_id: int, role: str, content: str):
        await self._insert(table="chat_history", user_id=user_id, role=role, content=content)

    async def register_user_with_referrer(self, user_id: int, chat_id: int, referrer_id: int):
        user = await self._get(table="users", record_id=user_id, id_col="user_id")
        
        if not user:
            final_referrer = referrer_id if referrer_id != user_id else None
            
            await self._insert("users", 
                user_id=user_id, 
                chat_id=chat_id, 
                referrer_id=final_referrer,
                bonus_queries=10,
                last_active=datetime.now()
            )
            return True # Сигнал для начисления бонуса
        
        await self.register_user(user_id, chat_id)
        return False

    async def add_referral_bonus(self, referrer_id: int, bonus_queries: int = 3):
        await self._update(
            table="users",
            record_id=referrer_id,
            id_col="user_id",
            bonus_queries=f"bonus_queries + {bonus_queries}"
        )

    async def delete_user(self, user_id: int):
        return await self._delete_many(table="users", filters={"user_id": user_id})
    
    async def update_user_subscription(self, user_id, sub_id):
        sub_info = AVAILABLE_SUBSCRIPTIONS[sub_id] or DEFAULT_SUBSCRIPTION
        new_sub_limit = sub_info.requests
        duration_days = sub_info.duration_days

        await self._update(
            table="users",
            record_id=int(user_id),
            id_col="user_id",
            subscription_status=sub_id,
            sub_queries=new_sub_limit, 
            used_queries=0,
            last_active="CURRENT_TIMESTAMP",
            subscription_start="CURRENT_TIMESTAMP",
            subscription_end=(
                f"GREATEST(CURRENT_TIMESTAMP, COALESCE(subscription_end, CURRENT_TIMESTAMP)) "
                f"+ ('{duration_days} days')::interval"
            )
        )
        logger.info(f"Подписка {sub_id} (лимит: {new_sub_limit}) обновлена для {user_id}")

    async def deactivate_expired_subscriptions(self, sub_id: str):
        available_requests = DEFAULT_SUBSCRIPTION.requests
        return await self._update_many(
            table="users",
            filters={
                "subscription_end": {"op": "<", "val": "CURRENT_TIMESTAMP"},
                "subscription_status": {"op": "!=", "val": "inactive"}
            },
            subscription_status=sub_id,
            sub_queries=available_requests,
            subscription_start="CURRENT_TIMESTAMP",
            subscription_end="NULL",
            last_active="CURRENT_TIMESTAMP",
            used_queries=0
        )
    
    async def get_recent_history(self, user_id: int, limit: int = 10):
        history = await self._fetch(
            table="chat_history",
            columns=["role", "content", "created_at"],
            filters={"user_id": user_id},
            order_by="created_at DESC",
            limit=limit
        )
        
        return [
            {"role": msg['role'], "content": msg['content']} 
            for msg in reversed(history)
        ]
    
    async def clear_old_history(self):
        return await self._delete_many(
            table="chat_history",
            filters={
                "created_at": {"op": "<", "val": "NOW() - INTERVAL '3 days'"}
            }
        )
    
    async def delete_user_history(self, user_id: int):
        return await self._delete_many(table="chat_history", filters={"user_id": user_id})
    
    async def get_total_users_count(self):
        return await self._count(table="users")
#--------------------------------------------------------------------------------

db = DBMain()