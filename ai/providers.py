from openai import AsyncOpenAI
from abc import ABC, abstractmethod
from config.logger import logger
import base64, aiohttp, tempfile, os

class AIProvider(ABC):
    cost_per_request: int = 1
    supports_image_generation: bool = False

    @abstractmethod
    async def get_answer(self, messages: list, image_url: str = None) -> str:
        pass

    async def generate_image_from_text(self, image_url: str, prompt: str) -> str:
        raise NotImplementedError

    def get_cost(self) -> int:
        return self.cost_per_request


class OpenAIProvider(AIProvider):
    def __init__(self, api_key, model, cost_per_request=1, supports_image=False):
        super().__init__()
        self.client = AsyncOpenAI(api_key=api_key.strip(), base_url="https://neuroapi.host/v1")
        self.model = model
        self.cost_per_request = cost_per_request
        self.supports_image_generation = supports_image

    async def get_answer(self, messages: list, image_url: str = None) -> str:
        try:
            if image_url and messages:
                for i in range(len(messages)-1, -1, -1):
                    if messages[i]['role'] == 'user':
                        current = messages[i]['content']
                        if isinstance(current, str):
                            messages[i]['content'] = [
                                {"type": "text", "text": current or "Что на этом изображении?"},
                                {"type": "image_url", "image_url": {"url": image_url}}
                            ]
                        break

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Ошибка OpenAI ({self.model}): {e}")
            return ("🤖 Не удалось получить ответ."
                    "Потраченные 🧩 пазлы возвращены на баланс в раздел 'Бонусные'")

    async def generate_image_from_text(self, prompt: str) -> str:
        """Text‑to‑image через images.generate"""
        try:
            response = await self.client.images.generate(
                model=self.model,
                prompt=prompt,
                size="1024x1024",
                # quality="low"  # опционально
            )
            return self._handle_image_response(response)
        except Exception as e:
            logger.error(f"Ошибка генерации ({self.model}): {e}")
            return ("🤖 Не удалось создать изображение."
                    "Потраченные 🧩 пазлы возвращены на баланс в раздел 'Бонусные'")

    async def edit_image(self, image_url: str, prompt: str) -> str:
        """img‑2‑img через images.edit"""
        try:
            response = await self.client.images.edit(
                model=self.model,
                image=image_url,
                prompt=prompt,
                size="1024x1024",
            )
            return self._handle_image_response(response)
        except Exception as e:
            logger.error(f"Ошибка редактирования ({self.model}): {e}")
            return ("🤖 Не удалось отредактировать изображение."
                    "Потраченные 🧩 пазлы возвращены на баланс в раздел 'Бонусные'")

    def _handle_image_response(self, response) -> str:
        if response.data and len(response.data) > 0:
            if response.data[0].url:
                return response.data[0].url
            elif response.data[0].b64_json:
                b64 = response.data[0].b64_json
                if isinstance(b64, bytes):
                    b64 = b64.decode('utf-8')
                logger.info(f"Изображение получено, размер base64: {len(b64)} символов")
                return f"BASE64:{b64}"
        logger.warning(f"Не удалось извлечь изображение из ответа: {response}")
        return "🤖 Не удалось получить изображение."

# Реестр моделей: {id: {class, kwargs, type}}
MODELS = {
    "gpt-4o": {
        "provider_class": OpenAIProvider,
        "kwargs": {"model": "gpt-4o", "cost_per_request": 1, "supports_image": False},
        "type": "text"
    },
    "gpt-image-1": {
        "provider_class": OpenAIProvider,
        "kwargs": {"model": "gpt-image-1", "cost_per_request": 20, "supports_image": True},
        "type": "image"
    },
    "gemini-3-pro-image-preview": {
        "provider_class": OpenAIProvider,
        "kwargs": {"model": "gemini-3-pro-image-preview", "cost_per_request": 20, "supports_image": True},
        "type": "image"
    },
    # будущие модели:
    # "gpt-4o-mini": {
    #     "provider_class": OpenAIProvider,
    #     "kwargs": {"model": "gpt-4o-mini", "cost_per_request": 1, "supports_image": False},
    #     "type": "text"
    # },
    # "dall-e-3": {
    #     "provider_class": OpenAIProvider,
    #     "kwargs": {"model": "dall-e-3", "cost_per_request": 25, "supports_image": True},
    #     "type": "image"
    # },
}

DEFAULT_MODEL = "gpt-4o-mini"

def create_provider(model_id, api_key):
    # Если явно запрошена DEFAULT_MODEL или модели нет в реестре – создаём с базовыми настройками
    if model_id == DEFAULT_MODEL or model_id not in MODELS:
        return OpenAIProvider(api_key, model=DEFAULT_MODEL, cost_per_request=1, supports_image=False)
    cfg = MODELS[model_id]
    cls = cfg["provider_class"]
    kwargs = cfg["kwargs"].copy()
    kwargs["api_key"] = api_key
    return cls(**kwargs)