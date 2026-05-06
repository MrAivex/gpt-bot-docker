import asyncio
from logger_config import logger
from database import db

class HandlersUtils:
    @staticmethod
    async def process_broadcast(bot, admin_chat_id, text):  # Рассылка сообщений по пользователям
        broadcast_text = text.replace("/send ", "", 1).strip()
        
        if not broadcast_text:
            await bot.send_message(admin_chat_id, "⚠️ Ошибка: пустой текст. Используйте: `/send текст`.")
            return

        chat_ids = await db.get_all_active_chat_ids()
        await bot.send_message(admin_chat_id, f"🚀 Начинаю рассылку на {len(chat_ids)} пользователей...")
        success_count = 0
        error_count = 0

        if chat_ids:
            for cid in chat_ids:
                try:
                    await bot.send_message(cid, broadcast_text)
                    success_count += 1
                    await asyncio.sleep(0.05)

                except Exception as e:
                    logger.error(f"Не удалось отправить сообщение {cid}: {e}")
                    error_count += 1
                    await asyncio.sleep(0.1)

        report = (
            f"📊 **Отчет о рассылке:**\n"
            f"✅ Успешно: `{success_count}`\n"
            f"❌ Ошибок: `{error_count}`"
        )
        await bot.send_message(admin_chat_id, report)

    @staticmethod
    async def get_referral_stats(bot, admin_chat_id):
        try:
            count = await db.get_referral_users_count()
            message = (
                "📈 **Статистика по рефералам**\n\n"
                f"Всего пользователей, пришедших по ссылкам: `{count}`"
            )
            await bot.send_message(admin_chat_id, message)

        except Exception as e:
            logger.error(f"Ошибка команды /refered_users: {e}")
            await bot.send_message(admin_chat_id, "❌ Не удалось получить статистику.")

    @staticmethod
    async def get_chats_stats(bot, admin_chat_id):
        """
        Получает статистику доступных для рассылки чатов.
        """
        try:
            count = await db.get_active_chats_count()
            
            message = (
                "📱 **Статистика по охвату**\n\n"
                f"Пользователей с активным `chat_id`: `{count}`\n"
                f"_(Этим людям можно отправить рассылку)_"
            )
            await bot.send_message(admin_chat_id, message)
        except Exception as e:
            logger.error(f"Ошибка команды /chat_ids: {e}")
            await bot.send_message(admin_chat_id, "❌ Ошибка при получении данных о чатах.")