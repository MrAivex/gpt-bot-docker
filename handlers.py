import time
import asyncio
from aiohttp import web
from logger_config import logger
from workers import worker_manager
from config import WEBHOOK_PATH
from database import db # Импортируем базу для очистки
from payments import create_payment_link # <-- Вот этот импорт спасет мир!
from subscriptions_config import AVAILABLE_SUBSCRIPTIONS, DEFAULT_SUBSCRIPTION
from datetime import datetime, timedelta

class WebhookHandler:
    def __init__(self, bot):
        self.bot = bot

    # handlers.py

    async def handle_yookassa_webhook(self, request):
        try:
            data = await request.json()
            # Проверяем, что это уведомление об успешном платеже
            if data.get('event') == 'payment.succeeded':
                payment_obj = data.get('object', {})
                metadata = payment_obj.get('metadata', {})
                
                user_id = metadata.get('user_id')
                chat_id = metadata.get('chat_id')
                sub_id = metadata.get('sub_id')
                
                if user_id and sub_id:
                    # 1. Получаем данные о подписке из конфига
                    from subscriptions_config import AVAILABLE_SUBSCRIPTIONS
                    sub_info = AVAILABLE_SUBSCRIPTIONS.get(sub_id, {})
                    duration = sub_info.get('duration_days', 30) # 30 дней по умолчанию
                    
                    # 2. Обновляем статус пользователя в БД
                    # Предположим, у вас есть метод update_subscription в database.py
                    await db.update_user_subscription(user_id, sub_id, duration) 
                    

                    expiry_date = (datetime.now() + timedelta(days=duration)).strftime("%d.%m.%Y")
                    # 3. Отправляем уведомление пользователю
                    success_text = (
                        f'✅ **Оплата прошла успешно!**\n\n'
                        f'Подписка: "{sub_info.get('name')}" активирована.\n'
                        f'Действует до: {expiry_date}'
                    )
                    await self.bot.send_message(chat_id, success_text)
                    
                    logger.info(f"Подписка {sub_id} активирована для пользователя {user_id}")
            
            return web.Response(status=200) # ЮKassa должна получить 200 OK
        except Exception as e:
            logger.error(f"Ошибка в вебхуке ЮKassa: {e}")
            return web.Response(status=200)

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
                    await db.deactivate_expired_subscriptions("inactive")
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
                
                if final_cmd == "see_subscriptions":
                    # Формируем текст со списком всех тарифов
                    text = "🌟 **Доступные тарифные планы:**\n\n"
                    buttons_rows = []

                    for sub_id, info in AVAILABLE_SUBSCRIPTIONS.items():
                        text += f'{info['name']} за {info['price']} руб.\n\n'
                        
                        # Создаем кнопку для каждой подписки. 
                        # При нажатии бот получит payload вида 'buy_sub_month'
                        buttons_rows.append([
                            {
                                "type": "callback", 
                                "text": f"{info['requests']} запросов/день, {info['price']}₽", 
                                "payload": f"buy_{sub_id}"
                            }
                        ])

                    reply_markup = [{
                        "type": "inline_keyboard",
                        "payload": {
                            "buttons": buttons_rows
                        }
                    }]
                    
                    await self.bot.send_message(chat_id, text, reply_markup=reply_markup)
                    return web.Response(status=200)
                
                # --- ОБРАБОТКА НАЖАТОЙ КНОПКИ ОПЛАТЫ ПОДПИСКИ ---
                if final_cmd.startswith("buy_"):
                    sub_id = final_cmd.replace("buy_", "")
                    
                    # Здесь мы наконец вызываем функцию из payments.py
                    pay_url = await create_payment_link(sub_id, user_id, chat_id)

                    if "Ошибка" in pay_url:
                        await self.bot.send_message(chat_id, pay_url)
                        return web.Response(status=200)

                    reply_markup = [{
                        "type": "inline_keyboard",
                        "payload": {
                            "buttons": [[
                                {"type": "link", "text": "💳 Оплатить", "url": pay_url}
                            ]]
                        }
                    }]
                    
                    sub_name = AVAILABLE_SUBSCRIPTIONS[sub_id]['name']
                    await self.bot.send_message(chat_id, f"Вы выбрали: {sub_name}\nДля оплаты нажмите на кнопку:", reply_markup=reply_markup)
                    return web.Response(status=200)
                # --------------------------

                if final_cmd == "subscription_status":
                    # 1. Добавляем await перед вызовом функции
                    user_data = await db.get_user(user_id)
                    
                    if user_data is None:
                        await db.register_user(user_id)
                        # 2. Используем chat_id вместо user_id для отправки
                        await self.bot.send_message(chat_id, "Вам доступен пробный период\n\n"
                            "Приобрести подписку можно по команде /help")
                    else:
                        # Достаем статус из словаря (get_user возвращает запись из БД)
                        sub_id = user_data.get('subscription_status', 'inactive')
                        sub_name = AVAILABLE_SUBSCRIPTIONS[sub_id]['name']
                        await self.bot.send_message(chat_id, f'Активная подписка: {sub_name}')
                    
                    return web.Response(status=200)
                        
                if final_cmd == "support":
                    support_url = "https://max.ru/u/f9LHodD0cOJXVUzeev1dZIA1PzKBWw0LlmNLaBSmG-2TUd6cMHvZLgojjsU"
                    await self.bot.send_message(chat_id, f'Чат техподдержки:\n\n{support_url}')
                 
            # Если это не команда, а обычное общение с ИИ
            if update_type == 'message_created' and (text or attachments):
                asyncio.create_task(
                    worker_manager.process_message(self.bot, chat_id, user_id, text, attachments)
                )

            return web.Response(status=200)
        except Exception as e:
            logger.error(f"Ошибка вебхука: {e}", exc_info=True)
            return web.Response(status=200)

# handlers.py

def setup_handlers(app, bot):
    handler = WebhookHandler(bot)
    # Основной вебхук MAX
    app.router.add_post(WEBHOOK_PATH, handler.handle_max_webhook)
    
    # КРИТИЧНО: Добавь этот маршрут для ЮKassa
    app.router.add_post('/yookassa-webhook', handler.handle_yookassa_webhook)