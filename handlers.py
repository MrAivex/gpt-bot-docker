import time
import asyncio
from aiohttp import web
from logger_config import logger
from workers import worker_manager
from config import WEBHOOK_PATH
from database import db # Импортируем базу для очистки

class WebhookHandler:
    def __init__(self, bot):
        self.bot = bot

    async def handle_max_webhook(self, request):
        try:
            data = await request.json()
            update_type = data.get('update_type')

            chat_id = data.get('chat_id') or data.get('message', {}).get('chat_id')
            user_id = data.get('user', {}).get('user_id') or data.get('message', {}).get('user_id')

            # 1. Проверка на "протухшие" сообщения
            # MAX присылает timestamp в миллисекундах
            msg_timestamp_ms = data.get('timestamp') or data.get('message', {}).get('timestamp', 0)
            msg_timestamp = msg_timestamp_ms / 1000
            current_time = time.time()

            # Если сообщению больше 60 секунд — игнорируем
            if msg_timestamp > 0 and (current_time - msg_timestamp > 60):
                logger.info(f"Игнорирую старое сообщение (отставание: {int(current_time - msg_timestamp)} сек)")
                return web.Response(status=200)

            # Инициализируем переменные по умолчанию
            user_id = None
            chat_id = None
            text = ""
            callback_payload = ""
            attachments = []

            if update_type == 'bot_started':
                logger.info(data)
                logger.info(f"Новый пользователь {user_id} запустил бота!")
                welcome_text = (
                    "👋 **Добро пожаловать в ИИ-ассистент!**\n\n"
                    "Я могу ответить на ваши вопросы, написать код или просто пообщаться."
                )
                # Отправляем приветствие
                await self.bot.send_message(chat_id, welcome_text)
                return web.Response(status=200)

            # 1. СЛУЧАЙ: Нажата инлайн-кнопка (Callback)
            elif update_type == 'message_callback':
                cb = data.get('callback', {})
                user_id = cb.get('user', {}).get('user_id')
                callback_payload = cb.get('payload', '')
                
                # По схеме: callback -> message -> recipient -> chat_id
                msg_obj = data.get('message', {})
                recipient = msg_obj.get('recipient', {})
                
                chat_id = recipient.get('chat_id') or recipient.get('user_id')
                
                logger.info(f"Кнопка нажата: payload={callback_payload}, user={user_id}, chat={chat_id}")

            # 2. СЛУЧАЙ: Обычное сообщение
            elif update_type == 'message_created':
                msg = data.get('message', {})
                user_id = msg.get('sender', {}).get('user_id')
                
                # chat_id берем из recipient
                recipient = msg.get('recipient', {})
                chat_id = recipient.get('chat_id') or recipient.get('user_id')
                
                # Текст может быть в корне или в body
                text = msg.get('text') or msg.get('body', {}).get('text', '')
                
                # Вложения (attachments) согласно документации на скриншоте
                attachments = msg.get('attachments') or []
                
                # Если в корне пусто, проверим в body (на всякий случай)
                if not attachments and 'body' in msg:
                    attachments = msg.get('body', {}).get('attachments') or []

            # Если не удалось определить базовые ID, выходим
            if not user_id or not chat_id:
                return web.Response(status=200)
            
            if not text and not attachments and not callback_payload:
                return web.Response(status=200)

            # ОПРЕДЕЛЯЕМ КОМАНДУ (из текста или из кнопки)
            final_cmd = (text or callback_payload or "").strip().lower()

            if final_cmd:
                if final_cmd == "/start":
                    logger.info(f"Команда /start для {user_id}")
                    await db.register_user(user_id) # Убедись, что метод есть в database.py
                    welcome_text = "Привет, это бот ChatGPT в MAX! Я могу видеть твои картинки и работать с текстом."\
                    " Давай попробуем начать!"
                    await self.bot.send_message(chat_id, welcome_text)
                    return web.Response(status=200)

                if final_cmd == "/help":
                    help_text = "📖 *Доступные команды:*\n/start\n/clear\n/help"
                    # Формат клавиатуры из твоего предыдущего сообщения
                    reply_markup = [{
                        "type": "inline_keyboard",
                        "payload": {
                            "buttons": [[
                                {"type": "callback", "text": "Статус подписки", "payload": "subscription_status"},
                                {"type": "callback", "text": "Очистить историю ИИ", "payload": "/clear"}
                            ],
                            [
                                {"type": "callback", "text": "О боте", "payload": "about_bot"},
                                {"type": "callback", "text": "Оформить подписку", "payload": "see_subscriptions"}
                            ],
                            [
                                {"type": "callback", "text": "Поддержка", "payload": "support"}
                            ]
                            ]
                        }
                    }]
                    await self.bot.send_message(chat_id, help_text, reply_markup=reply_markup)
                    return web.Response(status=200)
                
                if final_cmd == "/id":
                    await self.bot.send_message(chat_id, "Ваш ID:")
                    await self.bot.send_message(chat_id, user_id)
                    return web.Response(status=200)

                if final_cmd == "/clear":
                    await db.delete_user_history(user_id)
                    await self.bot.send_message(chat_id, "История чата с ИИ очищена")
                    return web.Response(status=200)
                
                if final_cmd == "about_bot":
                    await self.bot.send_message(chat_id, 
                        "Это наш бот. Вы можете задавать"\
                        " ему любые вопросы и отправлять картинки")
                    return web.Response(status=200)

            # Если это не команда, а обычное общение с ИИ
            if update_type == 'message_created' and (text or attachments):
                asyncio.create_task(
                    worker_manager.process_message(self.bot, chat_id, user_id, text, attachments)
                )

            return web.Response(status=200)
        except Exception as e:
            logger.error(f"Ошибка вебхука: {e}", exc_info=True)
            return web.Response(status=200)

def setup_handlers(app, bot):
    handler = WebhookHandler(bot)
    app.router.add_post(WEBHOOK_PATH, handler.handle_max_webhook)