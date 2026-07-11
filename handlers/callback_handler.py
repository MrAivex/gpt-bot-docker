# handlers/callback_handler.py
from services.subscription_service import SubscriptionService
from services.payment_service import PaymentService
from db.repositories import UserRepository, MessageRepository
from templates.messages import Messages
from templates.keyboards import Keyboards
from handlers.models import Update
from bot_client import MaxBot
from config.subscriptions import AVAILABLE_SUBSCRIPTIONS
from ai.providers import MODELS, DEFAULT_MODEL
from config.logger import logger

class CallbackHandler:
    def __init__(self, bot: MaxBot, user_repo: UserRepository, message_repo: MessageRepository, 
                 subscription_service: SubscriptionService, payment_service: PaymentService, 
                 messages: Messages, keyboards: Keyboards):
        self.bot = bot
        self.user_repo = user_repo
        self.message_repo = message_repo
        self.subscription_service = subscription_service
        self.payment = payment_service
        self.msg = messages
        self.kb = keyboards

    async def handle(self, update: Update):
        """Обрабатывает callback_query из inline-кнопок."""
        payload = update.callback_payload
        if not payload:
            return False

        chat_id = update.chat_id
        user_id = update.user_id

        if payload == "show_main_menu_edit":
            await self.bot.edit_message(chat_id, update.message_id, self.msg.HELP_TEXT, reply_markup=self.kb.main_menu())
            return True
        
        if payload == "show_main_menu_new":
            await self.bot.send_message(chat_id, self.msg.HELP_TEXT, reply_markup=self.kb.main_menu())
            return True
        
        if payload == "settings":
            await self.bot.edit_message(chat_id, update.message_id, self.msg.SETTINGS, self.kb.settings())
            return True

        if payload == "clear_ai_history":
            await self.message_repo.delete_user_history(user_id)
            await self.bot.send_message(chat_id, self.msg.HISTORY_CLEARED, reply_markup=self.kb.menu_button_new_msg())
            return True
        
        if payload == "show_referal_link":
            await self.bot.edit_message(chat_id, update.message_id, self.msg.referal_text(user_id), 
                                        reply_markup=self.kb.menu_button_edit_msg())
            return True
        
        if payload == "about_bot":
            await self.bot.edit_message(chat_id, update.message_id, self.msg.ABOUT_BOT, 
                                        reply_markup=self.kb.menu_button_edit_msg())
            return True
        
        if payload == "see_subscriptions":
            await self.bot.edit_message(chat_id, update.message_id, self.msg.SEE_SUBSCRIPTIONS, 
                                        reply_markup=self.kb.subscription_list())
            return True

        if payload.startswith("buy_"):
            sub_id = payload.replace("buy_", "")
            user_obj = await self.user_repo.get_user(user_id)
            if not user_obj or not user_obj.user_email:
                await self.bot.edit_message(chat_id, update.message_id, self.msg.NEED_EMAIL, 
                                            reply_markup=self.kb.back_to_sub_list())
                return True

            pay_url = await self.payment.create_payment(sub_id, user_id, chat_id, user_obj.user_email)
            if pay_url.startswith("❌"):
                await self.bot.edit_message(chat_id, update.message_id, pay_url, 
                                            reply_markup=self.kb.back_to_sub_list())
                return True
            
            sub_name = AVAILABLE_SUBSCRIPTIONS[sub_id].name
            await self.bot.edit_message(chat_id, update.message_id, self.msg.payment_sub_info(sub_name), 
                                        reply_markup=self.kb.payment_keyboard(pay_url))
            return True
        
        if payload == "subscription_status":
            user_data = await self.user_repo.get_user(user_id)
            if not user_data or user_data.subscription_status == 'inactive':
                await self.bot.edit_message(chat_id, update.message_id, self.msg.NO_SUBSCRIPTION, 
                                            reply_markup=self.kb.menu_and_sub_list_edit())
            else:
                sub_id = user_data.subscription_status
                sub_info = AVAILABLE_SUBSCRIPTIONS[sub_id]
                sub_name_user = sub_info.name if sub_info else sub_id
                end_date = user_data.subscription_end
                await self.bot.edit_message(chat_id, update.message_id, self.msg.sub_status(sub_name_user, end_date),
                                            reply_markup=self.kb.menu_button_edit_msg())
            return True
        
        if payload == "support":
            await self.bot.edit_message(chat_id, update.message_id, self.msg.SUPPORT, self.kb.menu_button_edit_msg())
            return True
        
        if payload == "my_queries":
            user_data = await self.user_repo.get_user(user_id)
            await self.bot.edit_message(chat_id, update.message_id, 
                                        self.msg.available_queries(user_data.sub_queries, user_data.bonus_queries),
                                        reply_markup=self.kb.menu_button_edit_msg())
            return True
        
        if payload == "delete_pay_token":
            await self.user_repo.remove_payment_token(user_id)
            await self.bot.send_message(chat_id, "✅ Способ оплаты успешно удалён.", 
                                        reply_markup=self.kb.menu_button_new_msg())
            return True
        
        if payload == "select_model":
            current = await self.user_repo.get_selected_model(user_id)
            await self.bot.edit_message(chat_id, update.message_id, self.msg.MODELS_HEADER, 
                                        reply_markup=self.kb.models_menu(current))
            return True
        
        if payload.startswith("select_model_"):
            model_id = payload.replace("select_model_", "")
            if model_id in MODELS or model_id == DEFAULT_MODEL:
                await self.user_repo.set_selected_model(user_id, model_id)
                current = await self.user_repo.get_selected_model(user_id)
                await self.bot.edit_message(chat_id, update.message_id, self.msg.MODELS_HEADER, 
                                        reply_markup=self.kb.models_menu(current))
            else:
                await self.bot.send_message(chat_id, "❌ Неизвестная модель.", 
                                            reply_markup=self.kb.menu_button_new_msg())
            return True
        
        if payload == "subscribe_channel":
            status = await self.user_repo.get_subscribe_on_channel(user_id)
            if status == 'subscribed':
                await self.bot.send_message(chat_id, self.msg.BONUS_ALREADY_CLAIMED)
                return True

            from config.main import CHANNEL_ID
            is_subscribed = await self.bot.check_channel_subscription(user_id, CHANNEL_ID)
            if is_subscribed:
                await self.user_repo.set_subscription_bonus(user_id)
                await self.bot.send_message(chat_id, self.msg.BONUS_GRANTED)
            else:
                await self.bot.send_message(chat_id, self.msg.SUBSCRIBE_TO_GET_BONUS)
            return True
        

        return False