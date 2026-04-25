import g4f
import httpx
from openai import AsyncOpenAI
from abc import ABC, abstractmethod
from logger_config import logger

class AIProvider(ABC):
    @abstractmethod
    async def get_answer(self, messages: list) -> str:
        pass

# --- НОВЫЙ КЛАСС ДЛЯ OPENAI ---
class OpenAIProvider(AIProvider):
    def __init__(self, api_key):
        # Создаем кастомный клиент, который игнорирует системные прокси
        # и не виснет на рукопожатии SSL
        self.client = AsyncOpenAI(
            api_key=api_key.strip(),
            base_url="https://neuroapi.host/v1" # Убрали 'api.' из начала
        )

    async def get_answer(self, messages: list, image_url: str = None) -> str:
        try:
            logger.info(f"AI Provider получил: image_url={image_url}")
            
            # --- ШАГ 3: Подготовка контента для Vision ---
            if image_url and messages:
                # Ищем последнее сообщение пользователя, чтобы прикрепить к нему фото
                for i in range(len(messages) - 1, -1, -1):
                    if messages[i]['role'] == 'user':
                        current_content = messages[i]['content']
                        
                        # Если content уже строка, превращаем его в список для Vision API
                        if isinstance(current_content, str):
                            messages[i]['content'] = [
                                {
                                    "type": "text", 
                                    "text": current_content if current_content else "Что на этом изображении?"
                                },
                                {
                                    "type": "image_url", 
                                    "image_url": {"url": image_url}
                                }
                            ]
                        break 
            # --- Конец правки ---

            response = await self.client.chat.completions.create(
                model="gpt-4o",  # gpt-4o лучше всего работает с картинками
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Ошибка NeuroAPI: {e}")
            return "🤖 Не удалось получить ответ от нейросети."

class G4FProvider(AIProvider):
    def __init__(self):
        provider_names = [
            "Blackbox",      # Сейчас один из самых стабильных
            "ChatGptEs",     # Хорошая альтернатива
            "DarkAI",        # Часто работает, когда другие лежат
            "PollinationsAI" 
        ]
        
        self.providers = []
        for name in provider_names:
            p = getattr(g4f.Provider, name, None)
            if p:
                self.providers.append(p)

    async def get_answer(self, messages: list) -> str:
        if not self.providers:
            return "🤖 Ошибка конфигурации ИИ."

        # Список моделей для пробы (от мощных к стандартным)
        models = ["gpt-4o", "gpt-4", ""] 

        for provider in self.providers:
            for model in models:
                try:
                    logger.info(f"Пробую {provider.__name__} с моделью '{model}'")
                    response = await g4f.ChatCompletion.create_async(
                        model=model,
                        provider=provider,
                        messages=messages,
                        ignore_working=True,
                        timeout=15 
                    )
                    
                    if response and len(str(response)) > 2:
                        return str(response)
                        
                except Exception as e:
                    # Если модель не подошла, просто пробуем следующую или следующего провайдера
                    continue
        
        return "🤖 Все нейросети сейчас заняты. Попробуйте через минуту!"

def get_ai_brain(provider_type="openai", api_key=None):
    if provider_type == "openai" and api_key:
        return OpenAIProvider(api_key)
    return G4FProvider()