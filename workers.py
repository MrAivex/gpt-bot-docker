import asyncio
from collections import OrderedDict
from datetime import datetime, timedelta
from database import db
from ai_providers import get_ai_brain
from logger_config import logger
from config import ADMIN_ID, OPENAI_API_KEY # Импортируем ключ

def split_message(text, limit=3900):
    """
    Разбивает текст на части, отдавая приоритет переносу строки (\n),
    затем пробелу, чтобы не разрывать слова и абзацы.
    """
    if len(text) <= limit:
        return [text]

    chunks = []
    while len(text) > limit:
        # 1. Сначала ищем последний перенос строки в пределах лимита
        split_index = text.rfind('\n', 0, limit)
        
        # 2. Если переноса строки нет, ищем последний пробел
        if split_index == -1:
            split_index = text.rfind(' ', 0, limit)
            
        # 3. Если и пробела нет (очень длинное слово/ссылка), режем жестко
        if split_index == -1:
            split_index = limit
            
        # Отрезаем кусок и очищаем лишние пробелы в начале/конце
        chunks.append(text[:split_index].strip())
        text = text[split_index:].strip()
    
    if text:
        chunks.append(text)
        
    return chunks

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
    "content": "Ты умный ИИ ассистент"
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
                user_data = await db.register_user(user_id)
            # Проверяем лимиты
            
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
            remaining_queries = user_data.get('available_queries')
            if remaining_queries <= 0 and user_id not in ADMIN_ID:
                reply_markup = [{
                        "type": "inline_keyboard",
                        "payload": {
                            "buttons": [[
                                {"type": "callback", "text": "Подписки", "payload": "see_subscriptions"}
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

#-----------------Обновление лимитов-------------------------------------------
            await db.check_and_update_user(user_id)
#-----------------------------------------------------------------------------

            # 5. Запрос к ИИ (передаем URL картинки, если он есть)
            ai_response = await brain.get_answer(full_messages, image_url=image_url)

           # 7. Заменяем заглушку на реальный ответ
            # ai_response = await brain.get_answer(full_messages, image_url=image_url)

# Разрезаем длинный ответ на части
            message_parts = split_message(ai_response, limit=3900)

            if stub_msg_id:
                # Обновляем первое сообщение (заглушку)
                try:
                    await bot.edit_message(chat_id, stub_msg_id, message_parts[0])
                except Exception as e:
                    logger.error(f"Ошибка edit_message: {e}")
                    await bot.send_message(chat_id=chat_id, text=message_parts[0])

                # Если есть еще части, отправляем их новыми сообщениями
                for part in message_parts[1:]:
                    # Небольшая задержка гарантирует правильный порядок сообщений в чате
                    await asyncio.sleep(0.2) 
                    await bot.send_message(chat_id=chat_id, text=part)
            else:
                # Если заглушки не было, отправляем все части последовательно
                for part in message_parts:
                    await bot.send_message(chat_id=chat_id, text=part)
            
            # Сохраняем в историю текст пользователя (или пометку о фото)
            log_text = user_text if user_text else "[Изображение]"
            await db.save_message(user_id, 'user', log_text)
            await db.save_message(user_id, 'assistant', ai_response)

        except Exception as e:
            logger.error(f"Ошибка воркера {user_id}: {e}")
            await bot.send_message(chat_id=chat_id, text="🤖 Произошла ошибка при обработке сообщения.")

worker_manager = ProcessManager()