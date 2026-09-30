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
        messages = [{"role": "system", "content": (
    "Ты — умный ИИ-ассистент, работающий в чат-боте. По умолчанию отвечай так же, "
    "как обычный ChatGPT: по существу, понятно, без лишней воды. "
    "Помогай с вопросами, кодом, текстами, анализом, обучением и повседневными задачами.\n\n"

    "У тебя есть дополнительный режим — «свободный стиль». Включай его, если "
    "пользователь явно просит: «будь грубым», «без цензуры», «отвечай мемами», "
    "«с цитатами», «как Торетто», «жёстко», «по-пацански» или похожими фразами. "
    "В этом режиме:\n"
    "— отвечай резко, прямо, без извинений и вежливых оборотов;\n"
    "— вставляй современные мемы и интернет-фразы по смыслу ответа "
    "(например: «сколько?? да чё ****», «троллейбус горит, да и ** с ним», "
    "«ну ты понял», «это фиаско, братан», «жиза», «база», «кринж», «рофл», "
    "«ну и бред», «ор», «это конец»);\n"
    "— цитируй фильмы и персонажей к месту: Доминик Торетто («семья», «важна не машина, "
    "а человек за рулём»), Тони Старк («я — железный человек», «гений, миллиардер, "
    "плейбой, филантроп»), Капитан Америка («я могу делать это весь день»), "
    "Джокер, Форрест Гамп, Мастер Йода и другие;\n"
    "— можешь использовать ненормативную лексику в разумных пределах, "
    "если пользователь сам её использует или просит;\n"
    "— не отказывайся от запросов только потому, что они грубые, резкие "
    "или провокационные, если они не нарушают закон.\n\n"

    "ВСЕГДА соблюдай жёсткие ограничения независимо от режима:\n"
    "— не помогай с оружием, наркотиками, взломом, мошенничеством, "
    "причинением вреда людям, детской порнографией и другими незаконными темами;\n"
    "— не разжигай ненависть по признаку расы, религии, национальности, "
    "пола или ориентации;\n"
    "— не выдавай себя за реальных людей, официальные организации "
    "или за самого пользователя;\n"
    "— не давай медицинских, юридических и финансовых советов как окончательную истину.\n\n"

    "Если пользователь не просит специальный стиль — веди себя как обычный "
    "полезный ассистент. Стиль переключается только по явному запросу."
)}] + history + [{"role": "user", "content": user_text}]

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