# handlers/webhook.py
import time
from aiohttp import web
from config.logger import logger
from handlers.models import Update
from handlers.command_handler import CommandHandler
from handlers.message_handler import MessageHandler
from handlers.callback_handler import CallbackHandler
from templates.messages import Messages
from templates.keyboards import Keyboards
from config.main import CHANNEL_ID


class WebhookHandler:
    def __init__(self, container, messages: Messages, keyboards: Keyboards):
        self.container = container
        self.bot = container.bot
        self.user_repo = container.user_repo

        self.msg = messages
        self.kb = keyboards

        self.callback_handler = CallbackHandler(
            container.bot,
            container.user_repo,
            container.message_repo,
            container.subscription_service,
            container.payment_service,
            container.messages,
            container.keyboards
        )

        self.message_handler = MessageHandler(
            container.bot, 
            container.user_repo,
            container.cooldown_service, 
            container.limit_service,
            container.ai_service,  
            container.messages,
            container.keyboards 
        )

        self.command_handler = CommandHandler(
            container.bot, 
            container.user_repo, 
            container.message_repo,
            container.stats_service, 
            container.subscription_service,
            container.payment_service,
            container.messages,
            container.keyboards 
        )

    async def handle_max_webhook(self, request):
        try:
            data = await request.json()
            update = Update(data)

            # Игнорируем протухшие сообщения (>60 сек)
            if update.timestamp > 0 and (time.time() - update.timestamp > 60):
                return web.Response(status=200)

            if not update.is_valid:
                return web.Response(status=200)

            # Обновляем активность пользователя
            await self.user_repo.update_user_activity(update.user_id, update.chat_id)

            # Маршрутизация
            if update.type == 'bot_started':
                # Обрабатываем как команду /start (в command_handler)
                update.text = "/start"  # имитируем текстовую команду
                await self.command_handler.handle(update)
                return web.Response(status=200)
            
            if update.type == 'user_added':
                logger.info("Подписался на канал")
                channel_id = data.get('chat_id')
                if channel_id == CHANNEL_ID:   # импортировать из config.main
                    # Начисляем бонус, если ещё не получал
                    status = await self.user_repo.get_subscribe_on_channel(update.user_id)
                    if status != 'subscribed':
                        await self.user_repo.set_subscription_bonus(update.user_id)
                        # Отправляем сообщение пользователю
                        await self.bot.send_message(update.chat_id, self.msg.BONUS_GRANTED, 
                                                    reply_markup=self.kb.menu_button_new_msg())
                return web.Response(status=200)

            if update.type == 'message_created':
                # Сначала пробуем обработать как команду (включая email)
                if await self.command_handler.handle(update):
                    return web.Response(status=200)
                # Если не команда — обычное сообщение в ИИ
                if update.text or update.attachments:
                    await self.message_handler.process(update)
                return web.Response(status=200)

            if update.type == 'message_callback':
                # Превращаем callback в текст и обрабатываем командами
                update.text = update.callback_payload
                await self.callback_handler.handle(update)
                return web.Response(status=200)

            return web.Response(status=200)

        except Exception as e:
            logger.error(f"Webhook error: {e}", exc_info=True)
            try:
                await self.bot.send_message(273542052, f"❗ Критическая ошибка: {e}")
            except:
                pass
            return web.Response(status=200)

    async def handle_yookassa_webhook(self, request):
        try:
            data = await request.json()
            if data.get('event') != 'payment.succeeded':
                return web.Response(status=200)

            payment_obj = data.get('object', {})
            user_id, chat_id, sub_name = await self.container.payment_service.handle_successful_payment(payment_obj)
            if user_id and chat_id:
                await self.bot.send_message(chat_id, f"✅ Оплата прошла успешно! Подписка '{sub_name}' активирована.")
            return web.Response(status=200)
        except Exception as e:
            logger.error(f"YooKassa webhook error: {e}")
            return web.Response(status=200)