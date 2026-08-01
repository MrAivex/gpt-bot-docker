# services/payment_service.py
from config.logger import logger
from db.repositories import UserRepository
from config.subscriptions import AVAILABLE_SUBSCRIPTIONS

class PaymentService:
    def __init__(self, user_repo: UserRepository, yookassa_client):
        self.user_repo = user_repo
        self.yookassa = yookassa_client

    async def create_payment(self, sub_id: str, user_id: int, chat_id: int, email: str):
        """Генерирует ссылку на оплату и возвращает её."""
        sub_info = AVAILABLE_SUBSCRIPTIONS[sub_id]
        if not sub_info:
            return "❌ Неверный тариф."

        # Вызываем API ЮKassa через клиент
        payment_url, error = await self.yookassa.create_payment(
            amount=sub_info.price,
            description=sub_info.name,
            user_id=user_id,
            chat_id=chat_id,
            sub_id=sub_id,
            email=email
        )
        if error:
            logger.error(f"Ошибка создания платежа: {error}")
            return f"❌ Ошибка при создании платежа: {error}"

        return payment_url

    async def handle_successful_payment(self, payment_data: dict):
        """Обрабатывает уведомление об успешном платеже."""
        metadata = payment_data.get('metadata', {})
        user_id = metadata.get('user_id')
        sub_id = metadata.get('sub_id')
        chat_id = metadata.get('chat_id')

        if not user_id or not sub_id:
            logger.error(f"Нет user_id или sub_id в метаданных: {metadata}")
            return None, None, None

        user_id = int(user_id)
        # Сохраняем payment_token для автопродления
        # payment_method = payment_data.get('payment_method', {})
        # if payment_method.get('saved'):
        #     token = payment_method.get('id')
        #     await self.user_repo.update_user_field(user_id, 'payment_token', token)

        # Активируем подписку через SubscriptionService
        # (можно инжектировать SubscriptionService или вызывать его метод напрямую)
        # Здесь для простоты вызовем репозиторий напрямую (потом заменим на вызов subscription_service)
        sub_info = AVAILABLE_SUBSCRIPTIONS[sub_id]
        if sub_info:
            await self.user_repo.activate_subscription(user_id, sub_id, sub_info)
            logger.info(f"Подписка {sub_id} активирована после оплаты для {user_id}")
            return user_id, chat_id, sub_info.name
        else:
            logger.error(f"Неизвестный sub_id {sub_id}")
            return None, None, None