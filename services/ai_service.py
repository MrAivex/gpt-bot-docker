from db.repositories import MessageRepository
from db.models import User
from ai.providers import AIProvider, MODELS, DEFAULT_MODEL, create_provider
from config.main import OPENAI_API_KEY
from config.logger import logger


class AIService:
    def __init__(self, message_repo: MessageRepository):
        self.message_repo = message_repo
        # Кеш провайдеров? Пока создаём на лету, чтобы не хранить состояние.
        # Можно позже оптимизировать.

    def get_provider_for_user(self, user: User) -> AIProvider:
        model_id = user.selected_model or DEFAULT_MODEL
        return create_provider(model_id, OPENAI_API_KEY)

    def get_cost_for_user(self, user: User, image_url: str = None) -> int:
        provider = self.get_provider_for_user(user)
        return provider.get_cost()

    async def generate_response(self, user: User, user_text: str, image_url: str = None):
        provider = self.get_provider_for_user(user)
        history = await self.message_repo.get_recent_history(user.user_id)
        messages = [{"role": "system", "content": "Ты умный ИИ ассистент"}] + history + [{"role": "user", "content": user_text}]

        if provider.supports_image_generation:
            if image_url:
                response = await provider.edit_image(image_url, user_text)
            else:
                response = await provider.generate_image_from_text(user_text)
        else:
            response = await provider.get_answer(messages, image_url)

        await self.message_repo.save_message(user.user_id, 'user', user_text)
        if isinstance(response, str) and (response.startswith("data:image/") or response.startswith("BASE64:")):
            await self.message_repo.save_message(user.user_id, 'assistant', "[image]")
        else:
            await self.message_repo.save_message(user.user_id, 'assistant', response)
        return response
        
    @staticmethod
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