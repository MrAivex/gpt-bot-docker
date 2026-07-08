# handlers/message_handler.py
import asyncio
from config.logger import logger
from services.cooldown_service import CooldownService
from services.limit_service import LimitService
from services.ai_service import AIService
from db.repositories import UserRepository
from templates.messages import Messages
from templates.keyboards import Keyboards
from handlers.models import Update
from bot_client import MaxBot
from config.main import ADMIN_ID

class MessageHandler:
    def __init__(self, bot: MaxBot, user_repo: UserRepository, cooldown: CooldownService,
                 limit: LimitService, ai_service: AIService, messages: Messages, keyboards: Keyboards):
        self.bot = bot
        self.user_repo = user_repo
        self.cooldown = cooldown
        self.limit = limit
        self.ai = ai_service
        self.msg = messages
        self.kb = keyboards

    async def process(self, update: Update):
        chat_id = update.chat_id
        user_id = update.user_id
        text = update.text
        attachments = update.attachments

        # 1. Cooldown
        if not self.cooldown.is_allowed(user_id):
            await self.bot.send_message(chat_id, self.msg.COOLDOWN_WARNING)
            return
        
        user = await self.user_repo.get_user(user_id)
        if not user:
            await self.user_repo.register_user(user_id, chat_id)
            user = await self.user_repo.get_user(user_id)

        image_url = None
        if attachments:
            for att in attachments:
                att_type = str(att.get('type', '')).lower()
                payload = att.get('payload', {})
                url = payload.get('url') or att.get('url')
                if att_type in ['image', 'photo', 'file'] and url:
                    image_url = url
                    break

        # 2. Проверка и списание лимита
        cost = self.ai.get_cost_for_user(user, image_url=image_url)
        if user_id not in ADMIN_ID:
            allowed, _ = await self.limit.check_and_deduct(user_id, cost)
            if not allowed:
                msg = self.msg.LIMIT_EXCEEDED_WITH_COST.format(cost=cost)
                await self.bot.send_message(chat_id, msg, reply_markup=self.kb.limit_exceeded())
                return

        user_text = text
        if not user_text and image_url:
            user_text = "Что на этом изображении?"
        if not user_text:
            return

        # 4. Отправляем заглушку
        stub_msg_id = await self.bot.send_message(chat_id, self.msg.STUB_TEXT)

        # 5. Вызов AI
        ai_response = await self.ai.generate_response(user, user_text, image_url)

        # 🔁 Возврат пазлов при ошибке генерации
        if isinstance(ai_response, str) and ai_response.startswith("🤖 Не удалось"):
            if user_id not in ADMIN_ID:
                await self.limit.refund(user_id, cost)
            if stub_msg_id:
                await self.bot.edit_message(chat_id, stub_msg_id, ai_response)
            else:
                await self.bot.send_message(chat_id, ai_response)
            return

        # 6. Обработка ответа
        if isinstance(ai_response, str) and ai_response.startswith("data:image/"):
            b64_content = ai_response.split(",", 1)[1]
            import base64, os, uuid, asyncio
            filename = f"{uuid.uuid4()}.png"
            filepath = os.path.join('temp_images', filename)
            os.makedirs('temp_images', exist_ok=True)
            with open(filepath, 'wb') as f:
                f.write(base64.b64decode(b64_content))
            await asyncio.sleep(0.5)  # даём файловой системе сохранить
            file_url = f"https://empty-snail-52.loca.lt/temp_images/{filename}"
            if stub_msg_id:
                await self.bot.edit_message(chat_id, stub_msg_id, "✅ Изображение готово:")
            await self.bot.send_photo(chat_id, file_url, caption=user_text)

        elif isinstance(ai_response, str) and ai_response.startswith("http"):
            # Прямая ссылка (на случай других моделей)
            if stub_msg_id:
                await self.bot.edit_message(chat_id, stub_msg_id, "✅ Изображение готово:")
            await self.bot.send_photo(chat_id, ai_response, caption=user_text)

        else:
            # Текстовый ответ
            parts = self.ai.split_message(ai_response, limit=3900)
            if stub_msg_id:
                try:
                    await self.bot.edit_message(chat_id, stub_msg_id, parts[0],
                                                reply_markup=self.kb.menu_button_new_msg())
                except Exception as e:
                    logger.error(f"Ошибка edit: {e}")
                    await self.bot.send_message(chat_id, parts[0])
                for part in parts[1:]:
                    await asyncio.sleep(0.2)
                    await self.bot.send_message(chat_id, part)
            else:
                for part in parts:
                    await self.bot.send_message(chat_id, part)