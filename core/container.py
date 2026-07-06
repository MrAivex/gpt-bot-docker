# core/container.py
import asyncpg
from config.logger import logger
from config.main import DB_DSN, TOKEN, OPENAI_API_KEY
from db.repositories import UserRepository, MessageRepository
from bot_client import MaxBot
from db.init import INIT_QUERIES
from ai.providers import MODELS, DEFAULT_MODEL, create_provider, OpenAIProvider
from services.cooldown_service import CooldownService
from services.limit_service import LimitService
from services.ai_service import AIService
from services.subscription_service import SubscriptionService
from services.payment_service import PaymentService
from services.stats_service import StatsService
from templates.messages import Messages
from templates.keyboards import Keyboards

class AppContainer:
    def __init__(self):
        self.pool = None
        self.bot = None
        self.user_repo = None
        self.message_repo = None
        self.cooldown_service = None
        self.limit_service = None
        self.ai_service = None
        self.subscription_service = None
        self.payment_service = None
        self.stats_service = None
        self.messages = None
        self.keyboards = None

    async def initialize(self):
        # Пул и таблицы
        self.pool = await asyncpg.create_pool(DB_DSN)
        async with self.pool.acquire() as conn:
            await conn.execute(INIT_QUERIES)
        logger.info("БД инициализирована.")

        # Репозитории
        self.user_repo = UserRepository(self.pool)
        self.message_repo = MessageRepository(self.pool)

        # Бот
        self.bot = MaxBot(TOKEN)

        # Сервисы
        self.cooldown_service = CooldownService(3)
        self.limit_service = LimitService(self.user_repo)
        self.subscription_service = SubscriptionService(self.user_repo)
        self.stats_service = StatsService(self.user_repo)

        # AI-сервис (новая архитектура без отдельных текстового и графического провайдеров)
        self.ai_service = AIService(self.message_repo)

        # Платёжный сервис (адаптер)
        from payments import create_payment_link
        class LegacyYooKassaAdapter:
            async def create_payment(self, amount, description, user_id, chat_id, sub_id, email):
                result = await create_payment_link(sub_id, user_id, chat_id, email)
                if "Ошибка" in result:
                    return None, result
                return result, None
        self.payment_service = PaymentService(self.user_repo, LegacyYooKassaAdapter())

        # Шаблоны
        self.messages = Messages()
        self.keyboards = Keyboards()

    async def shutdown(self):
        if self.pool:
            await self.pool.close()
            logger.info("Пул БД закрыт.")