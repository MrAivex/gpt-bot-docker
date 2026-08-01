# services/subscription_service.py
from db.repositories import UserRepository
from config.subscriptions import AVAILABLE_SUBSCRIPTIONS, DEFAULT_SUBSCRIPTION
from config.logger import logger

class SubscriptionService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def activate_or_extend(self, user_id: int, sub_id: str) -> tuple[bool, str]:
        plan = AVAILABLE_SUBSCRIPTIONS.get(sub_id)
        if not plan:
            logger.error(f"Неизвестный план: {sub_id}")
            return False, "Неизвестный план"

        if plan.duration_days > 0:
            # Это подписка – обновляем sub_queries и срок
            await self.user_repo.activate_subscription(user_id, sub_id, plan)
            return True, f"Подписка '{plan.name}' активирована"
        else:
            # Разовый пакет – добавляем bonus_queries
            await self.user_repo.add_bonus_queries(user_id, plan.bonus_queries)
            return True, f"Пакет '{plan.name}' приобретён, +{plan.bonus_queries} пазлов"

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