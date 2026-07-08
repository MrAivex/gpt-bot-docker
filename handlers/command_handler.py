# handlers/command_handler.py
import asyncio
import re
from config.logger import logger
from config.main import ADMIN_ID, ADMIN_COMMANDS, EMAIL_REGEX
from db.repositories import UserRepository, MessageRepository
from services.stats_service import StatsService
from services.subscription_service import SubscriptionService
from services.payment_service import PaymentService
from templates.messages import Messages
from templates.keyboards import Keyboards
from handlers.models import Update
from bot_client import MaxBot



class CommandHandler:
    def __init__(self, bot: MaxBot, user_repo: UserRepository, message_repo: MessageRepository,
                 stats_service: StatsService, subscription_service: SubscriptionService,
                 payment_service: PaymentService, messages: Messages, keyboards: Keyboards):
        self.bot = bot
        self.user_repo = user_repo
        self.message_repo = message_repo
        self.stats = stats_service
        self.subscription_service = subscription_service
        self.payment = payment_service
        self.msg = messages
        self.kb = keyboards

    async def handle(self, update: Update):
        """Возвращает True, если команда обработана, иначе False."""
        text = update.intent
        if not text:
            return False

        chat_id = update.chat_id
        user_id = update.user_id

        # Обработка /start
        if text.startswith("/start"):
            parts = text.split(" ")
            referrer_id = None
            if len(parts) > 1 and parts[1].isdigit():
                referrer_id = int(parts[1])

            is_new = await self.user_repo.register_user_with_referrer(user_id, chat_id, referrer_id)
            if is_new and referrer_id:
                await self.user_repo.add_referral_bonus(referrer_id, 3)
                try:
                    await self.bot.send_message(referrer_id, "🎁 Вам начислено 3 запроса за приглашение друга!")
                except Exception:
                    pass
            await self.bot.send_message(chat_id,
                "Привет! Я твой ИИ ассистент, можешь задать мне любой вопрос!\n\nМеню доступно по команде /help")
            return True

        # Остальные команды
        # if text == "/ref":
        #     link = f"{REF_URL}?start={user_id}"
        #     await self.bot.send_message(chat_id,
        #         "❗❗Прежде чем отправить другу ссылку, обязательно выполни команду /start\n"
        #         "🔗 Твоя ссылка для приглашений:\n`" + link + "`\n\nЗа каждого друга даем 3 бесплатных запроса!")
        #     return True

        if text == "/help":
            await self.bot.send_message(chat_id, self.msg.HELP_TEXT, reply_markup=self.kb.main_menu())
            return True

        if text == "/id":
            await self.bot.send_message(chat_id, f"Ваш user_id: {user_id}\nВаш chat_id: {chat_id}")
            return True

        # if text == "/clear":
        #     await self.message_repo.delete_user_history(user_id)
        #     await self.bot.send_message(chat_id, "История чата с ИИ очищена")
        #     return True

        # if text == "about_bot":
        #     await self.bot.send_message(chat_id, "Это наш бот. Вы можете задавать ему любые вопросы и отправлять картинки")
        #     return True

        # if text == "see_subscriptions":
        #     text_out = "🌟 **Доступные тарифные планы:**"
        #     buttons_rows = []
        #     for sub_id, info in AVAILABLE_SUBSCRIPTIONS.items():
        #         buttons_rows.append([
        #             {"type": "callback", "text": f"{info.name}, {info.price} руб", "payload": f"buy_{sub_id}"}
        #         ])
        #     reply_markup = [{"type": "inline_keyboard", "payload": {"buttons": buttons_rows}}]
        #     await self.bot.send_message(chat_id, text_out, reply_markup=reply_markup)
        #     return True

        # if text.startswith("buy_"):
        #     sub_id = text.replace("buy_", "")
        #     user_obj = await self.user_repo.get_user(user_id)
        #     if not user_obj or not user_obj.user_email:
        #         await self.bot.send_message(chat_id,
        #             "Необходимо указать электронную почту для получения чека. "
        #             "Пришлите её отдельным сообщением (только email).")
        #         return True

        #     pay_url = await self.payment.create_payment(sub_id, user_id, chat_id, user_obj.user_email)
        #     if pay_url.startswith("❌"):
        #         await self.bot.send_message(chat_id, pay_url)
        #         return True

        #     reply_markup = [{
        #         "type": "inline_keyboard",
        #         "payload": {
        #             "buttons": [[{"type": "link", "text": "💳 Оплатить", "url": pay_url}]]
        #         }
        #     }]
        #     sub_name = AVAILABLE_SUBSCRIPTIONS[sub_id].name
        #     await self.bot.send_message(chat_id, f"Вы выбрали: {sub_name}\nДля оплаты нажмите на кнопку:",
        #                                 reply_markup=reply_markup)
        #     return True

        # if text == "subscription_status":
        #     user_data = await self.user_repo.get_user(user_id)
        #     if not user_data or user_data.subscription_status == 'inactive':
        #         await self.bot.send_message(chat_id, "У вас нет активной подписки.\n\nВы можете выбрать тариф в меню /help")
        #     else:
        #         sub_id = user_data.subscription_status
        #         sub_info = AVAILABLE_SUBSCRIPTIONS[sub_id]
        #         sub_name = sub_info.name if sub_info else sub_id
        #         end_date = user_data.subscription_end
        #         date_str = f"\nДействует до: {end_date.strftime('%d.%m.%Y')}" if end_date else ""
        #         await self.bot.send_message(chat_id, f"🌟 Активная подписка: {sub_name}{date_str}")
        #     return True

        # if text == "support":
        #     support_url = "https://max.ru/u/f9LHodD0cOJXVUzeev1dZIA1PzKBWw0LlmNLaBSmG-2TUd6cMHvZLgojjsU"
        #     await self.bot.send_message(chat_id, f"Чат техподдержки:\n\n{support_url}")
        #     return True

        # if text == "my_queries":
        #     user_data = await self.user_repo.get_user(user_id)
        #     queries = user_data.sub_queries + user_data.bonus_queries if user_data else 0
        #     await self.bot.send_message(chat_id, f"Доступные запросы: {queries}")
        #     return True

        if re.match(EMAIL_REGEX, text): # v
            await self.user_repo.update_user_email(user_id, text)
            await self.bot.send_message(chat_id, self.msg.save_email(text), 
                                        self.kb.menu_button_new_msg())
            return True

        # Админские команды
        if user_id in ADMIN_ID:
            return await self._handle_admin_command(text, chat_id, user_id, update)
        
        # if text == "delete_pay_token":
        #     await self.user_repo.remove_payment_token(user_id)
        #     await self.bot.send_message(chat_id, "✅ Способ оплаты успешно удалён.")
        #     return True

        return False  # не команда

    async def _handle_admin_command(self, text, chat_id, user_id, update):
        if text == "/admin":
            await self.bot.send_message(chat_id, "Список команд админа:\n" + "\n".join(ADMIN_COMMANDS))
            return True
        if text == "/count":
            total = await self.stats.get_total_users()
            await self.bot.send_message(chat_id, f"📊 Всего пользователей: `{total}`")
            return True
        if text.startswith("/user"):
            parts = text.split()
            if len(parts) < 2:
                await self.bot.send_message(chat_id, "⚠️ Формат: `/user id_пользователя`")
                return True
            try:
                target_id = int(parts[1])
                user_info = await self.user_repo.get_user(target_id)
                if not user_info:
                    await self.bot.send_message(chat_id, f"❌ Пользователь с ID `{target_id}` не найден.")
                    return True
                status = user_info.subscription_status
                queries = user_info.sub_queries + user_info.bonus_queries
                total = user_info.total_queries
                sub_end = user_info.subscription_end
                sub_end_str = sub_end.strftime('%d.%m.%Y %H:%M') if sub_end else "Нет"
                email = user_info.user_email or "Не указан"
                user_chat_id = user_info.chat_id or "Не указан"
                referrer = user_info.referrer_id or "Не указан"
                last_active = user_info.last_active
                last_active_str = last_active.strftime('%d.%m.%Y %H:%M') if last_active else "Нет"
                report = (
                    f"👤 **Данные пользователя {target_id}:**\n\n"
                    f"🔹 Статус: `{status}`\n"
                    f"📧 Email: `{email}`\n"
                    f"🔹 Осталось лимитов: `{queries}`\n"
                    f"🔹 Всего запросов: `{total}`\n"
                    f"🔹 Подписка до: `{sub_end_str}`\n"
                    f"🔹 Последняя активность: `{last_active_str}`\n"
                    f"🔹 chat_id: `{user_chat_id}`\n"
                    f"🔹 referrer_id: `{referrer}`\n"
                    f"🔹 selected_model: `{user_info.selected_model or "не выбрана"}`"
                )
                await self.bot.send_message(chat_id, report)
            except ValueError:
                await self.bot.send_message(chat_id, "⚠️ ID должен быть числом.")
            except Exception as e:
                logger.error(f"Ошибка /user: {e}")
                await self.bot.send_message(chat_id, "Ошибка при обращении к БД.")
            return True
        
        if text == "/foto":
            await self.bot.send_photo(chat_id, "https://avatars.mds.yandex.net/get-autoru-vos/2073783/ee41fc6ae5ca37f46a25c8deed71c173/1200x900", "Вот фото")
            return True

        if text.startswith("/update"):
            parts = text.split(maxsplit=3)
            if len(parts) < 4:
                await self.bot.send_message(chat_id, "⚠️ Формат: `/update id поле значение`")
                return True
            try:
                target_id = int(parts[1])
                field = parts[2].lower()
                raw_value = parts[3]
                # Простая конвертация
                if field in ['used_queries', 'available_queries', 'total_queries']:
                    value = int(raw_value)
                elif field in ['subscription_end', 'subscription_start']:
                    from datetime import datetime
                    try:
                        value = datetime.strptime(raw_value, "%d.%m.%Y")
                    except ValueError:
                        value = datetime.fromisoformat(raw_value)
                elif raw_value.lower() == "null":
                    value = None
                else:
                    value = raw_value
                await self.user_repo.update_user_field(target_id, field, value)
                await self.bot.send_message(chat_id, f"✅ Поле `{field}` для `{target_id}` обновлено.")
            except Exception as e:
                logger.error(f"Ошибка /update: {e}")
                await self.bot.send_message(chat_id, f"❌ Ошибка: {e}")
            return True

        if text == "/max_queries":
            top = await self.stats.get_top_users(10)
            if top:
                resp = "🏆 **ТОП-5 пользователей бота:**\n\n"
                medals = ["🥇", "🥈", "🥉"] + ["🔸"]*7
                for i, u in enumerate(top):
                    resp += f"{medals[i]} **Место {i+1}**\n👤 ID: `{u['user_id']}`\n📊 Запросов: `{u['total_queries']}`\n💎 Статус: `{u['subscription_status']}`\n\n"
                await self.bot.send_message(chat_id, resp)
            else:
                await self.bot.send_message(chat_id, "Пока нет данных.")
            return True

        if text == "/active_users":
            count = await self.stats.get_active_subscriptions_count()
            await self.bot.send_message(chat_id, f"✅ Активных платных пользователей: `{count}`")
            return True

        if text.startswith("/delete "):
            parts = text.split()
            if len(parts) < 2 or not parts[1].isdigit():
                await self.bot.send_message(chat_id, "⚠️ Формат: `/delete user_id`")
                return True
            target = int(parts[1])
            success = await self.user_repo.delete_user(target)
            await self.bot.send_message(chat_id, f"{'✅' if success else '❌'} Пользователь `{target}` {'' if success else 'не '}удалён.")
            return True

        if text.startswith("/send") and user_id in ADMIN_ID:
            asyncio.create_task(self._process_broadcast(chat_id, text))
            return True

        if text == "/refered_users" and user_id in ADMIN_ID:
            await self._referral_stats(chat_id)
            return True

        if text == "/chat_ids" and user_id in ADMIN_ID:
            await self._chats_stats(chat_id)
            return True

        return False
    
    async def _process_broadcast(self, admin_chat_id, text):
        broadcast_text = text.replace("/send ", "", 1).strip()
        if not broadcast_text:
            await self.bot.send_message(admin_chat_id, "⚠️ Ошибка: пустой текст.")
            return
        chat_ids = await self.user_repo.get_all_active_chat_ids()
        await self.bot.send_message(admin_chat_id, f"🚀 Рассылка на {len(chat_ids)} пользователей...")
        success, error = 0, 0
        for cid in chat_ids:
            try:
                await self.bot.send_message(cid, broadcast_text)
                success += 1
                await asyncio.sleep(0.05)
            except Exception as e:
                logger.error(f"Ошибка отправки {cid}: {e}")
                error += 1
                await asyncio.sleep(0.1)
        await self.bot.send_message(admin_chat_id,
            f"📊 Отчёт:\n✅ Успешно: `{success}`\n❌ Ошибок: `{error}`")

    async def _referral_stats(self, chat_id):
        count = await self.user_repo.get_referral_users_count()
        await self.bot.send_message(chat_id, f"📈 Приглашённых пользователей: `{count}`")

    async def _chats_stats(self, chat_id):
        count = await self.user_repo.get_active_chats_count()
        await self.bot.send_message(chat_id, f"📱 Пользователей с chat_id: `{count}`")