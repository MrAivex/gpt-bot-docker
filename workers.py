import asyncio
from collections import OrderedDict
from datetime import datetime, timedelta
from database import db
from ai_providers import get_ai_brain
from logger_config import logger
from config import ADMIN_ID
from config import ADMIN_ID, OPENAI_API_KEY # Импортируем ключ

# Реализация ограниченного словаря
class LimitedDict(OrderedDict):
    def __init__(self, limit=10000):
        self.limit = limit
        super().__init__()

    def __setitem__(self, key, value):
        # Если ключ уже есть, удаляем его, чтобы при вставке он стал "самым свежим"
        if key in self:
            del self[key]
        # Если лимит превышен, удаляем самый старый элемент (первый в очереди)
        if len(self) >= self.limit:
            self.popitem(last=False)
        super().__setitem__(key, value)

# Ограничиваем память 10 000 активных пользователей. 
# Этого за глаза хватит для VPS с небольшим объемом RAM.
user_cooldowns = LimitedDict(limit=10000)

brain = get_ai_brain("openai", api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = {
    "role": "system", 
    "content": "Ты — полезный ИИ-ассистент в мессенджере MAX. Отвечай дружелюбно. Ты помнишь контекст предыдущих сообщений."
}

class ProcessManager:
    @staticmethod
    async def process_message(bot, chat_id, user_id, user_text, attachments=None):
        """
        Обновленный метод: принимает список вложений (attachments)
        """
        try:
            logger.info(f"--- ЗАПУСК ЛОГИКИ ДЛЯ {user_id} ---")

            # --- ВОТ СЮДА ВСТАВЛЯЕМ ПРОВЕРКУ ---
            user_data = await db.get_user(user_id)
            if not user_data:
                # Если юзера нет в базе, создаем его (автоматически через твой метод)
                user_data = await db.get_or_create_user(user_id)

            # Проверяем лимиты
            if user_data['subscription_status'] == 'inactive' and user_data['used_queries'] >= user_data['available_queries']:
                await bot.send_message(chat_id, "🚀 **Лимит бесплатных запросов исчерпан!**\n\nОформите подписку в меню, чтобы продолжить общение без ограничений.")
                return 
            # -----------------------------------

            # 1. Защита от спама (Cooldown)
            now = datetime.now()
            last_msg_time = user_cooldowns.get(user_id)

            if last_msg_time and (now - last_msg_time) < timedelta(seconds=3):
                logger.warning(f"Флуд от {user_id}. Запрос проигнорирован.")
                await bot.send_message(chat_id=chat_id, text="⚠️ Пожалуйста, подождите 3 секунды перед следующим сообщением.")
                return

            user_cooldowns[user_id] = now

            # 2. Лимиты из БД
            remaining_queries = await db.check_and_update_user(user_id)
            if remaining_queries <= 0 and user_id != ADMIN_ID:
                reply_markup = [{
                        "type": "inline_keyboard",
                        "payload": {
                            "buttons": [[
                                {"type": "callback", "text": "Подписки", "payload": "see_subscriptions"},
                                {"type": "callback", "text": "Настройки", "payload": "settings"}
                            ]]
                        }
                    }]
                await bot.send_message(
                    chat_id=chat_id,
                    text="❌ Лимит запросов исчерпан. \n"\
                        "Для продолжения общения оформите подписку",
                    reply_markup=reply_markup
                    )
                return

            # 3. Извлекаем фото (если есть)
            image_url = None
            if attachments:
                logger.info(f"Получено вложений: {len(attachments)}")
                for att in attachments:
                    att_type = str(att.get('type', '')).lower()
                    payload = att.get('payload', {})
                    
                    # Пробуем достать URL из payload или из корня аттача
                    url = payload.get('url') or att.get('url')
                    
                    # Согласно скриншоту, тип может быть 'image'
                    if att_type in ['image', 'photo', 'file'] and url:
                        image_url = url
                        logger.info(f"URL картинки найден: {image_url}")
                        break

            # 4. Контекст памяти
            history = await db.get_recent_history(user_id, limit=5)
            
            # Важно: если текста нет (пользователь скинул только фото), 
            # добавляем дефолтный вопрос, чтобы модель понимала, что делать.
            if not user_text and image_url:
                user_text = "Что на этом изображении?"
            
            if not user_text:
                return

            full_messages = [SYSTEM_PROMPT] + history + [{"role": "user", "content": user_text}]

            # 5. Отправляем заглушку
            stub_text = "🤖 Думаю..."
            if image_url:
                stub_text = "🖼 Анализирую изображение..."
            
            # Нам нужно, чтобы send_message возвращал ID созданного сообщения
            # Для этого немного поправим bot_client ниже, а пока представим, что он возвращает ID
            stub_msg_id = await bot.send_message(chat_id=chat_id, text=stub_text)

            # 5. Запрос к ИИ (передаем URL картинки, если он есть)
            logger.info(f"Запрос к ИИ для чата {chat_id}. Контекст: {len(full_messages)} сообщ.")
            ai_response = await brain.get_answer(full_messages, image_url=image_url)

           # 7. Заменяем заглушку на реальный ответ
            if stub_msg_id:
                logger.info(f"Пытаюсь отредактировать сообщение {stub_msg_id}")
                success = await bot.edit_message(chat_id, stub_msg_id, ai_response)
                if not success:
                    await bot.send_message(chat_id=chat_id, text=ai_response)
            else:
                # Если мы здесь, значит stub_msg_id был None изначально
                logger.warning("Заглушка не была создана или ID не получен, шлю новым сообщением")
                await bot.send_message(chat_id=chat_id, text=ai_response)
            
            # Сохраняем в историю текст пользователя (или пометку о фото)
            log_text = user_text if user_text else "[Изображение]"
            await db.save_message(user_id, 'user', log_text)
            await db.save_message(user_id, 'assistant', ai_response)
            
            logger.info(f"Воркер успешно завершил работу для {user_id}")

        except Exception as e:
            logger.error(f"Ошибка воркера {user_id}: {e}")
            await bot.send_message(chat_id=chat_id, text="🤖 Произошла ошибка при обработке сообщения.")

worker_manager = ProcessManager()