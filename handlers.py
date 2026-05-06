import time
import re
import asyncio
from aiohttp import web
from logger_config import logger
from workers import worker_manager
from config import WEBHOOK_PATH, ADMIN_ID, ADMIN_COMMANDS, REF_URL, ADMIN_CHAT_ID
from database import db
from payments import create_payment_link 
from subscriptions_config import AVAILABLE_SUBSCRIPTIONS
from datetime import datetime, timedelta
from handlers_utils import HandlersUtils as h_utils

EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

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
                subscription_end = metadata.get('subscription_end')
                
                if user_id and sub_id:
                    # 1. Получаем данные о подписке из конфига
                    from subscriptions_config import AVAILABLE_SUBSCRIPTIONS
                    sub_info = AVAILABLE_SUBSCRIPTIONS.get(sub_id, {})
                    duration = sub_info.get('duration_days', 31) # 30 дней по умолчанию
                    
                    # 2. Обновляем статус пользователя в БД
                    # Предположим, у вас есть метод update_subscription в database.py
                    await db.update_user_subscription(user_id, sub_id, duration) 
                    

                    # expiry_date = (datetime.now() + timedelta(days=duration)).strftime("%d.%m.%Y")
                    expiry_date = (datetime.fromisoformat(subscription_end) + timedelta(days=duration)).strftime("%d.%m.%Y")
                    # 3. Отправляем уведомление пользователю
                    success_text = (
                        f"✅ **Оплата прошла успешно!**\n\n"
                        f"Подписка: '{sub_info.get('name')}' активирована.\n"
                        f"Действует до: {expiry_date}"
                    )
                    await self.bot.send_message(chat_id, success_text)
                    
                    logger.info(f"Подписка {sub_id} активирована для пользователя {user_id}")
            
            return web.Response(status=200) # ЮKassa должна получить 200 OK
        except Exception as e:
            logger.error(f"Ошибка в вебхуке ЮKassa: {e}")

            error_msg = f"❗ **Критическая ошибка у юзера {user_id}:**\n`{str(e)[:1000]}`"
            await self.bot.send_message(273542052, error_msg)

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
                return web.Response(status=200)

            # Инициализируем переменные по умолчанию
            user_id = None
            chat_id = None
            text = ""
            callback_payload = ""
            attachments = []

            if update_type == 'bot_started':
                user_info = data.get('user', {})
                us_start_id = user_info.get('user_id')
                us_chat_id = data.get('chat_id')
                logger.info(f"Новый пользователь {us_start_id} запустил бота!")
                welcome_text = (
                    "👋 **Добро пожаловать в ИИ-ассистент!**\n\n"
                    "Я могу ответить на ваши вопросы, написать код или просто пообщаться."
                )
                referrer_id_str = data.get('payload') # Извлекаем данные из диплинка
    
                if referrer_id_str and referrer_id_str.isdigit():
                    referrer_id = int(referrer_id_str)
                    ref_obj = await db.get_user(referrer_id)
                    ref_chat_id = ref_obj.get('chat_id')
                    if referrer_id != us_start_id and ref_chat_id:
                        # Логика регистрации через рефералку
                        is_new = await db.register_user_with_referrer(us_start_id, us_chat_id, referrer_id)
                        if is_new:
                            await db.add_referral_bonus(referrer_id, 3)
                            await self.bot.send_message(ref_chat_id, "🎁 Вам начислено 3 запроса за приглашение друга!")
                        await self.bot.send_message(us_chat_id, f"👋 {welcome_text}")
                        return web.Response(status=200)
                await db.register_user_with_referrer(us_start_id, us_chat_id)
                await self.bot.send_message(us_chat_id, welcome_text)
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
                if text.startswith("/start"):
                    parts = text.split(" ")
                    referrer_id = None
                    
                    # Если в ссылке есть ID (например, /start 5333223)
                    if len(parts) > 1 and parts[1].isdigit():
                        referrer_id = int(parts[1])

                    # Пытаемся зарегистрировать новичка
                    is_new = await db.register_user_with_referrer(user_id, chat_id, referrer_id)
                    
                    if is_new and referrer_id:
                        # Начисляем бонус пригласившему
                        await db.add_referral_bonus(referrer_id, 3)
                        # Уведомляем пригласившего (опционально)
                        try:
                            await self.bot.send_message(referrer_id, "🎁 Вам начислено 3 запроса за приглашение друга!")
                        except:
                            pass

                    await self.bot.send_message(chat_id, "Привет! Я твой ИИ ассистент, можешь задать мне любой вопрос!"\
                                                        "\n\nМеню доступно по команде /help")
                    return web.Response(status=200)

                # if final_cmd == "/start":
                #     await db.register_user(user_id)
                #     welcome_text = "Привет, это бот ChatGPT в MAX! Я могу видеть твои картинки и работать с текстом."\
                #     " Давай попробуем начать!"
                #     await self.bot.send_message(chat_id, welcome_text)
                #     return web.Response(status=200)

                if final_cmd == "/ref":
                    link = f"{REF_URL}?start={user_id}"
                    await self.bot.send_message(chat_id, "❗❗Прежде чем отправить другу ссылку, обязательно "\
                                    "выполни команду /start , иначе не узнаешь, когда придет вознаграждение!!"
                                    "🔗 Твоя ссылка для приглашений:"\
                                    f"\n`{link}`\n\nЗа каждого друга даем 3 бесплатных запроса!")
                    return web.Response(status=200)

                if final_cmd == "/help":
                    help_text = "📖 *Доступные команды:*\n/start\n/help\n"\
                    "/ref - пригласить друга"
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
                                {"type": "callback", "text": "Поддержка", "payload": "support"},
                                {"type": "callback", "text": "Мои запросы", "payload": "my_queries"}
                            ],
                            [
                                {"type": "callback", "text": "Пригласить друга", "payload": "/ref"}
                            ]
                            ]
                        }
                    }]
                    await self.bot.send_message(chat_id, help_text, reply_markup=reply_markup)
                    return web.Response(status=200)
                
                if final_cmd == "/id":
                    await self.bot.send_message(chat_id, f"Ваш user_id: {user_id}\n"\
                                                         f"Ваш chat_id: {chat_id}")
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
                        text += f"{info['name']} за {info['price']} руб.\n\n"
                        
                        # Создаем кнопку для каждой подписки. 
                        # При нажатии бот получит payload вида 'buy_sub_month'
                        buttons_rows.append([
                            {
                                "type": "callback", 
                                "text": f"{info['requests']} запросов/день, {info['price']} руб.", 
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
                    user_abj = await db.get_user(user_id)

                    if not user_abj.get('user_email'):
                        await self.bot.send_message(
                            chat_id, 
                            "Необходимо указать электронную почту для получения чека, "\
                            "для этого пришлите её в чат с ботом отдельным сообщением без."\
                            " Сообщение должно содержать только почту без каких-либо других символов"
                        )
                        return web.Response(status=200)

                    subscription_end = user_abj.get("subscription_end", datetime.now())
                    
                    # Здесь мы наконец вызываем функцию из payments.py
                    us_email = user_abj.get('user_email')
                    pay_url = await create_payment_link(sub_id, user_id, chat_id, subscription_end, us_email)

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
                        await db.register_user_with_referrer(user_id, chat_id)
                        # 2. Используем chat_id вместо user_id для отправки
                        await self.bot.send_message(chat_id, "Вам доступен пробный период\n\n"
                            "Приобрести подписку можно по команде /help")
                    else:
                        # Достаем статус из словаря (get_user возвращает запись из БД)
                        sub_id = user_data.get('subscription_status', 'inactive')
                        if sub_id == 'inactive':
                            await self.bot.send_message(chat_id, "У вас нет активной подписки.\n\n"
                                                                "Вы можете выбрать тариф в меню /help")
                        else:
                            # Если подписка есть, пытаемся достать её название
                            sub_info = AVAILABLE_SUBSCRIPTIONS.get(sub_id)
                            if sub_info:
                                sub_name = sub_info['name']
                                # Если добавили дату окончания, выводим и её
                                end_date = user_data.get('subscription_end')
                                date_str = f"\nДействует до: {end_date.strftime('%d.%m.%Y')}" if end_date else ""
                                
                                await self.bot.send_message(chat_id, f"🌟 Активная подписка: {sub_name}{date_str}")
                            else:
                                # На случай, если в БД какой-то странный ID
                                await self.bot.send_message(chat_id, "Статус подписки: неактивна.")
                    
                    return web.Response(status=200)
                        
                if final_cmd == "support":
                    support_url = "https://max.ru/u/f9LHodD0cOJXVUzeev1dZIA1PzKBWw0LlmNLaBSmG-2TUd6cMHvZLgojjsU"
                    await self.bot.send_message(chat_id, f"Чат техподдержки:\n\n{support_url}")
                    return web.Response(status=200)

                
                if final_cmd == "my_queries":
                    query_data = await db.get_user(user_id)
                    my_queries = query_data.get('available_queries')
                    await self.bot.send_message(chat_id, f"Доступные запросы: {my_queries}")
                    return web.Response(status=200)
                
                if re.match(EMAIL_REGEX, text):
                    await db.update_user_email(user_id, text)
                    await self.bot.send_message(chat_id, f"✅ Email `{text}` сохранен. Теперь вы можете перейти к оплате.")
                    return web.Response(status=200)

#-------АДМИНСКИЕ КОМАНДЫ---------------------------------------------------------------

                if text.lower() == "/admin" and user_id in ADMIN_ID:
                    admin_commands_list = "Список команд админа:\n"
                    for command_name in ADMIN_COMMANDS:
                        admin_commands_list += f"{command_name}\n"
                    await self.bot.send_message(chat_id, admin_commands_list)
                    return web.Response(status=200)

                if text.lower() == "/count" and user_id in ADMIN_ID:
                    try:
                        total_users = await db.get_total_users_count()
                        await self.bot.send_message(
                            chat_id, 
                            f"📊 **Статистика бота**\n\n"
                            f"Всего пользователей в БД: `{total_users}`"
                        )
                        return web.Response(status=200)
                    except Exception as e:
                        logger.error(f"Ошибка при получении статистики: {e}")
                        await self.bot.send_message(chat_id, "Ошибка при обращении к базе данных.")
                        return web.Response(status=200)
                    
                if text.lower().startswith("/user") and user_id in ADMIN_ID: # Информация о пользователе
                    try:
                        # Извлекаем ID из сообщения "/user 111111"
                        parts = text.split()
                        if len(parts) < 2:
                            await self.bot.send_message(chat_id, "⚠️ Формат: `/user id_пользователя`")
                            return web.Response(status=200)

                        target_id = int(parts[1])
                        user_info = await db.get_user(target_id)

                        if not user_info:
                            await self.bot.send_message(chat_id, f"❌ Пользователь с ID `{target_id}` не найден.")
                        else:
                            status = user_info.get('subscription_status', 'inactive')
                            queries_left = user_info.get('available_queries', 0)
                            total = user_info.get('total_queries', 0)
                            sub_end = user_info.get('subscription_end')
                            sub_end_str = sub_end.strftime('%d.%m.%Y %H:%M') if sub_end else "Нет"
                            email = user_info.get('user_email') or "Не указан"
                            user_chat_id = user_info.get('chat_id') or "Не указан"
                            us_referer_id = user_info.get('referrer_id') or "Не указан"

                            report = (
                                f"👤 **Данные пользователя {target_id}:**\n\n"
                                f"🔹 Статус: `{status}`\n"
                                f"📧 Email: `{email}`\n"
                                f"🔹 Осталось лимитов: `{queries_left}`\n"
                                f"🔹 Всего запросов: `{total}`\n"
                                f"🔹 Подписка до: `{sub_end_str}`\n"
                                f"🔹 Последняя активность: `{user_info.get('last_active').strftime('%d.%m.%Y %H:%M')}`\n"
                                f"🔹 chat_id: `{user_chat_id}`\n"
                                f"🔹 referrer_id: `{us_referer_id}`"
                            )
                            await self.bot.send_message(chat_id, report)

                        return web.Response(status=200)
                    except ValueError:
                        await self.bot.send_message(chat_id, "⚠️ ID должен быть числом.")
                        return web.Response(status=200)
                    except Exception as e:
                        logger.error(f"Ошибка при поиске пользователя {target_id}: {e}")
                        await self.bot.send_message(chat_id, "Ошибка при обращении к БД.")
                        return web.Response(status=200)

                if text.lower().startswith("/update") and user_id in ADMIN_ID:
                    try:
                        parts = text.split(maxsplit=3) # /update id поле значение
                        if len(parts) < 4:
                            await self.bot.send_message(chat_id, "⚠️ Формат: `/update {id} {поле} {значение}`")
                            return web.Response(status=200)

                        target_id = int(parts[1])
                        field = parts[2].lower()
                        raw_value = parts[3]
                        final_value = raw_value

                        int_fields = ['used_queries', 'available_queries', 'total_queries']
                        date_fields = ['subscription_end', 'subscription_start']

                        if field in int_fields:
                            final_value = int(raw_value)
                        elif field in date_fields:
                            # Ожидаем формат ДД.ММ.ГГГГ или ГГГГ-ММ-ДД
                            try:
                                final_value = datetime.strptime(raw_value, "%d.%m.%Y")
                            except ValueError:
                                final_value = datetime.fromisoformat(raw_value)
                        elif raw_value.lower() == "null":
                            final_value = None

                        # Вызов метода БД
                        await db.update_user_field(target_id, field, final_value)
                        
                        await self.bot.send_message(chat_id, f"✅ Поле `{field}` для пользователя `{target_id}` успешно обновлено!")

                    except ValueError as e:
                        await self.bot.send_message(chat_id, f"❌ Ошибка данных: Проверьте формат числа или даты. ({e})")
                    except Exception as e:
                        logger.error(f"Ошибка при обновлении пользователя: {e}")
                        await self.bot.send_message(chat_id, f"❌ Произошла ошибка: {str(e)}")
                    
                    return web.Response(status=200)
                        
                if text.lower() == "/max_queries" and user_id in ADMIN_ID: # МАКСИМАЛЬНОЕ КОЛИЧЕСТВО ЗАПРОСОВ
                    top_users = await db.get_top_users_by_queries(limit=10)
                    
                    if top_users:
                        response_text = "🏆 **ТОП-5 пользователей бота:**\n\n"
                        
                        # Перебираем пользователей и формируем список
                        for index, user in enumerate(top_users, start=1):
                            # Значки для первых трех мест
                            medal = "🥇" if index == 1 else "🥈" if index == 2 else "🥉" if index == 3 else "🔸"
                            
                            response_text += (
                                f"{medal} **Место {index}**\n"
                                f"👤 ID: `{user['user_id']}`\n"
                                f"📊 Запросов: `{user['total_queries']}`\n"
                                f"💎 Статус: `{user['subscription_status']}`\n\n"
                            )
                    else:
                        response_text = "📭 В базе данных пока нет пользователей."
                        
                    await self.bot.send_message(chat_id, response_text)
                    return web.Response(status=200)
                
                if text.lower() == "/active_users" and user_id in ADMIN_ID: # КОЛ-ВО ЛЮДЕЙ С ПОДПИСКОЙ
                    # Получаем число активных подписчиков
                    count = await db.count_active_subscribers()
                    
                    response_text = (
                        "📊 **Статистика подписок**\n\n"
                        f"✅ Количество активных платных пользователей: `{count}`"
                    )
                    
                    await self.bot.send_message(chat_id, response_text)
                    return web.Response(status=200)
                
                if text.startswith("/delete ") and user_id in ADMIN_ID: # УДАЛИТЬ ПОЛЬЗОВАТЕЛЯ
                    # Извлекаем ID из команды "/delete 12345"
                    parts = text.split(" ")
                    if len(parts) < 2 or not parts[1].isdigit():
                        await self.bot.send_message(chat_id, "⚠️ Формат команды: `/delete {user_id}`")
                        return web.Response(status=200)

                    target_id = int(parts[1])
                    
                    # Пытаемся удалить
                    success = await db.delete_user(target_id)
                    
                    if success:
                        response_text = f"✅ Пользователь `{target_id}` успешно удален из базы данных."
                    else:
                        response_text = f"❌ Пользователь `{target_id}` не найден в базе."
                        
                    await self.bot.send_message(chat_id, response_text)
                    return web.Response(status=200)
#---------------------АДМИНСКИЕ КОМАНДЫ ИЗ handlers_utils.py--------------------------------------------
                if text.lower().startswith("/send") and user_id in ADMIN_ID: # Рассылка по команде /send
                    asyncio.create_task(h_utils.process_broadcast(self.bot, chat_id, text))
                    return web.Response(status=200)
                
                if text.lower() == "/refered_users" and user_id in ADMIN_ID:
                    await h_utils.get_referral_stats(self.bot, chat_id)
                    return web.Response(status=200)
                
                if text.lower() == "/chat_ids" and user_id in ADMIN_ID:
                    await h_utils.get_chats_stats(self.bot, chat_id)
                    return web.Response(status=200)
#--------------------------------------------------------------------------------------
                 
            # Если это не команда, а обычное общение с ИИ
            if update_type == 'message_created' and (text or attachments):
                request 
                asyncio.create_task(
                    worker_manager.process_message(self.bot, chat_id, user_id, text, attachments)
                )

            return web.Response(status=200)
        except Exception as e:
            logger.error(f"Ошибка вебхука: {e}", exc_info=True)

            error_msg = f"❗ **Критическая ошибка у юзера {user_id}:**\n`{str(e)[:1000]}`"
            await self.bot.send_message(273542052, error_msg)

            return web.Response(status=200)

# handlers.py

def setup_handlers(app, bot):
    handler = WebhookHandler(bot)
    # Основной вебхук MAX
    app.router.add_post(WEBHOOK_PATH, handler.handle_max_webhook)
    
    # КРИТИЧНО: Добавь этот маршрут для ЮKassa
    app.router.add_post('/yookassa-webhook', handler.handle_yookassa_webhook)