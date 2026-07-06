# services/subscription_service.py
from db.repositories import UserRepository
from config.subscriptions import AVAILABLE_SUBSCRIPTIONS, DEFAULT_SUBSCRIPTION
from config.logger import logger

class SubscriptionService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def activate_or_extend(self, user_id: int, sub_id: str):
        """Активирует новую подписку или продлевает текущую."""
        sub_info = AVAILABLE_SUBSCRIPTIONS.get(sub_id) or DEFAULT_SUBSCRIPTION.get(sub_id)
        if not sub_info:
            logger.error(f"Неизвестный sub_id: {sub_id}")
            return False
        await self.user_repo.activate_subscription(user_id, sub_id, sub_info)
        logger.info(f"Подписка {sub_id} активирована для user {user_id}")
        return True

    async def deactivate_expired(self):
        """Деактивирует все подписки с истекшим сроком."""
        await self.user_repo.deactivate_expired_subscriptions('inactive')
        logger.info("Деактивация истекших подписок выполнена.")

    async def reset_limits_for_active(self):
        """Сбрасывает использованные запросы и обновляет лимиты согласно тарифам."""
        await self.user_repo.reset_subscription_limits(AVAILABLE_SUBSCRIPTIONS)
        logger.info("Сброс лимитов активных подписок выполнен.")

    async def get_sub_info(self, user_id):
        sub_id = await self.user_repo.get_user(user_id)
        return sub_id