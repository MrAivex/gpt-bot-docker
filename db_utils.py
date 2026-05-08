from logger_config import logger


async def fetch_active_chats(pool): # Собираем chat_id у тех, у кого они есть
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch('SELECT chat_id FROM users WHERE chat_id IS NOT NULL')
            chat_ids = list(set([row['chat_id'] for row in rows]))
            logger.info(f"Собрано {len(chat_ids)} активных chat_id для рассылки.")
            return chat_ids
        
    except Exception as e:
        logger.error(f"Ошибка при сборе chat_id в db_utils: {e}")
        return None
    
async def fetch_referral_users_count(pool):
    try:
        async with pool.acquire() as conn:
            count = await conn.fetchval('SELECT COUNT(*) FROM users WHERE referrer_id IS NOT NULL')
            return count if count else 0
        
    except Exception as e:
        logger.error(f"Ошибка при подсчете реферальных пользователей: {e}")
        return 0
    
async def fetch_chat_ids_count(pool):
    try:
        async with pool.acquire() as conn:
            count = await conn.fetchval('SELECT COUNT(*) FROM users WHERE chat_id IS NOT NULL')
            return count if count else 0
        
    except Exception as e:
        logger.error(f"Ошибка при подсчете chat_id: {e}")
        return 0
    
async def fetch_users_for_renewal(pool):
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT 
                    user_id, 
                    chat_id, 
                    subscription_status, 
                    payment_token, 
                    user_email,  -- Добавили поле email
                    subscription_end
                FROM users 
                WHERE subscription_end::date = (CURRENT_TIMESTAMP + INTERVAL '1 day')::date
                  AND payment_token IS NOT NULL
                  AND subscription_status != 'inactive'
                  AND user_email IS NOT NULL -- Продление без почты невозможно (чек)
            ''')
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Ошибка при поиске пользователей для продления: {e}")
        return []