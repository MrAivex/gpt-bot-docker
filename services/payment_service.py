# services/payment_service.py
from config.logger import logger
from db.repositories import UserRepository
from config.subscriptions import AVAILABLE_SUBSCRIPTIONS

class PaymentService:
    def __init__(self, user_repo: UserRepository, yookassa_client, subscription_service):
        self.user_repo = user_repo
        self.yookassa = yookassa_client
        self.subscription_service = subscription_service   # добавили

    async def create_payment(self, sub_id: str, user_id: int, chat_id: int, email: str):
        """Генерирует ссылку на оплату и возвращает её."""
        sub_info = AVAILABLE_SUBSCRIPTIONS.get(sub_id)
        if not sub_info:
            return "❌ Неверный тариф."

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
        metadata = payment_data.get('metadata', {})
        user_id = metadata.get('user_id')
        sub_id = metadata.get('sub_id')
        chat_id = metadata.get('chat_id')

        if not user_id or not sub_id:
            logger.error(f"Нет user_id или sub_id в метаданных: {metadata}")
            return None, None, None

        user_id = int(user_id)

        if not chat_id:
            user = await self.user_repo.get_user(user_id)
            chat_id = user.chat_id if user else None

        success, message = await self.subscription_service.activate_or_extend(user_id, sub_id)
        if success:
            logger.info(f"Платёж обработан: {message}")
            return user_id, chat_id, message
        else:
            logger.error(f"Ошибка активации: {message}")
            return None, None, None