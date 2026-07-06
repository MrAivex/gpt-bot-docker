# db/repositories.py
import asyncpg
from typing import Optional
from db.models import User
from config.logger import logger
from ai.providers import DEFAULT_MODEL


class UserRepository:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def get_user(self, user_id: int) -> Optional[User]:
        query = """
            SELECT user_id, used_queries, sub_queries, total_queries, 
                subscription_status, subscription_start, subscription_end, 
                last_active, user_email, payment_token, referrer_id, chat_id, 
                subscribe_on_channel, bonus_queries, selected_model
            FROM users WHERE user_id = $1
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, user_id)
            return User(**dict(row)) if row else None

    async def update_user_activity(self, user_id: int, chat_id: int):
        query = '''
            INSERT INTO users (user_id, chat_id, last_active, bonus_queries, subscription_status, sub_queries)
            VALUES ($1, $2, CURRENT_TIMESTAMP, 10, 'inactive', 0)
            ON CONFLICT (user_id) DO UPDATE 
            SET chat_id = EXCLUDED.chat_id, 
                last_active = CURRENT_TIMESTAMP
        '''
        async with self.pool.acquire() as conn:
            await conn.execute(query, user_id, chat_id)

    async def decrement_queries(self, user_id: int, amount: int = 1) -> bool:
        if amount <= 0:
            return True

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT sub_queries, bonus_queries FROM users WHERE user_id = $1",
                user_id
            )
            if not row:
                return False

            sub = row['sub_queries'] or 0
            bonus = row['bonus_queries'] or 0

            if sub + bonus < amount:
                return False

            if sub >= amount:
                new_sub = sub - amount
                new_bonus = bonus
            else:
                new_sub = 0
                new_bonus = bonus - (amount - sub)

            await conn.execute(
                "UPDATE users SET sub_queries = $1, bonus_queries = $2 WHERE user_id = $3",
                new_sub, new_bonus, user_id
            )
            return True

    async def _update_field(self, user_id: int, field: str, value):
        query = f"UPDATE users SET {field} = $1 WHERE user_id = $2"
        async with self.pool.acquire() as conn:
            await conn.execute(query, value, user_id)

    async def register_user(self, user_id: int, chat_id: int = None):
        """Простая регистрация без реферала"""
        await self.update_user_activity(user_id, chat_id)

    async def register_user_with_referrer(self, user_id: int, chat_id: int, referrer_id: int = None):
        user = await self.get_user(user_id)
        if user is not None:
            # Уже существует – просто обновляем активность
            await self.update_user_activity(user_id, chat_id)
            return False  # не новый

        final_referrer = referrer_id if referrer_id and referrer_id != user_id else None
        query = '''
            INSERT INTO users (user_id, chat_id, referrer_id, bonus_queries, last_active, subscription_status, sub_queries)
            VALUES ($1, $2, $3, 10, CURRENT_TIMESTAMP, 'inactive', 0)
        '''
        async with self.pool.acquire() as conn:
            await conn.execute(query, user_id, chat_id, final_referrer)
        return True  # новый пользователь

    async def add_referral_bonus(self, referrer_id: int, bonus_queries: int = 3):
        query = "UPDATE users SET bonus_queries = bonus_queries + $1 WHERE user_id = $2"
        async with self.pool.acquire() as conn:
            await conn.execute(query, bonus_queries, referrer_id)

    async def update_user_email(self, user_id: int, email: str):
        await self._update_field(user_id, 'user_email', email)

    async def update_user_field(self, user_id: int, field: str, value):
        await self._update_field(user_id, field, value)

    async def activate_subscription(self, user_id: int, sub_id: str, sub_info: dict):
        """Активирует/продлевает подписку на основе переданного словаря sub_info"""
        new_limit = sub_info.requests
        duration_days = sub_info.duration_days
        query = '''
            UPDATE users 
            SET subscription_status = $1,
                sub_queries = $2,
                used_queries = 0,
                subscription_start = CURRENT_TIMESTAMP,
                subscription_end = GREATEST(CURRENT_TIMESTAMP, COALESCE(subscription_end, CURRENT_TIMESTAMP)) + ($3 || ' days')::interval,
                last_active = CURRENT_TIMESTAMP
            WHERE user_id = $4
        '''
        async with self.pool.acquire() as conn:
            await conn.execute(query, sub_id, new_limit, str(duration_days), user_id)

    async def deactivate_expired_subscriptions(self, inactive_status='inactive'):
        default_requests = 0  # DEFAULT_SUBSCRIPTION.requests
        query = '''
            UPDATE users 
            SET subscription_status = $1,
                sub_queries = $2,
                used_queries = 0,
                subscription_start = CURRENT_TIMESTAMP,
                subscription_end = NULL,
                last_active = CURRENT_TIMESTAMP
            WHERE subscription_end < CURRENT_TIMESTAMP 
              AND subscription_status != 'inactive'
        '''
        async with self.pool.acquire() as conn:
            await conn.execute(query, inactive_status, default_requests)

    async def reset_subscription_limits(self, subscriptions_config: dict):
        """Массовый сброс лимитов согласно конфигу подписок"""
        case_parts = []
        for sub_id, info in subscriptions_config.items():
            case_parts.append(f"WHEN subscription_status = '{sub_id}' THEN {info.requests}")
        case_sql = " ".join(case_parts)
        query = f"""
            UPDATE users 
            SET used_queries = 0,
                sub_queries = CASE {case_sql} ELSE sub_queries END,
                last_active = CURRENT_TIMESTAMP
            WHERE subscription_status != 'inactive'
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query)

    async def get_all_active_chat_ids(self):
        query = "SELECT DISTINCT chat_id FROM users WHERE chat_id IS NOT NULL"
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query)
            return [row['chat_id'] for row in rows]

    async def get_referral_users_count(self):
        query = "SELECT COUNT(*) FROM users WHERE referrer_id IS NOT NULL"
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query) or 0

    async def get_active_chats_count(self):
        query = "SELECT COUNT(*) FROM users WHERE chat_id IS NOT NULL"
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query) or 0

    async def get_top_users_by_queries(self, limit=10):
        query = "SELECT user_id, total_queries, subscription_status FROM users ORDER BY total_queries DESC LIMIT $1"
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, limit)
            return [dict(row) for row in rows]

    async def count_active_subscriptions(self):
        query = "SELECT COUNT(*) FROM users WHERE subscription_status != 'inactive'"
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query) or 0

    async def get_total_users_count(self):
        query = "SELECT COUNT(*) FROM users"
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query) or 0

    async def delete_user(self, user_id: int):
        query = "DELETE FROM users WHERE user_id = $1"
        async with self.pool.acquire() as conn:
            result = await conn.execute(query, user_id)
            return result == "DELETE 1"

    async def get_users_for_renewal(self):
        """Для будущего автопродления: активные подписки с payment_token и email"""
        query = """
            SELECT subscription_status, user_id, chat_id, user_email, payment_token, subscription_end
            FROM users
            WHERE subscription_status != 'inactive'
              AND chat_id IS NOT NULL
              AND user_email IS NOT NULL
              AND payment_token IS NOT NULL
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query)
            return [dict(row) for row in rows]
    
    async def remove_payment_token(self, user_id: int):
        await self._update_field(user_id, 'payment_token', None)

    async def set_selected_model(self, user_id: int, model_id: str):
        await self._update_field(user_id, 'selected_model', model_id)

    async def get_selected_model(self, user_id: int) -> str:
        user = await self.get_user(user_id)
        return user.selected_model if user and user.selected_model else DEFAULT_MODEL


class MessageRepository:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def save_message(self, user_id: int, role: str, content: str):
        query = "INSERT INTO chat_history (user_id, role, content) VALUES ($1, $2, $3)"
        async with self.pool.acquire() as conn:
            await conn.execute(query, user_id, role, content)

    async def get_recent_history(self, user_id: int, limit: int = 10) -> list[dict]:
        query = """
            SELECT role, content FROM chat_history 
            WHERE user_id = $1 
            ORDER BY created_at DESC 
            LIMIT $2
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, user_id, limit)
        return [{"role": row['role'], "content": row['content']} for row in reversed(rows)]

    async def clear_old_history(self):
        query = "DELETE FROM chat_history WHERE created_at < NOW() - INTERVAL '3 days'"
        async with self.pool.acquire() as conn:
            await conn.execute(query)

    async def delete_user_history(self, user_id: int):
        query = "DELETE FROM chat_history WHERE user_id = $1"
        async with self.pool.acquire() as conn:
            await conn.execute(query, user_id)