import uuid
from yookassa import Configuration, Payment
from config import SHOP_ID, PAYMENT_TOKEN
from subscriptions_config import AVAILABLE_SUBSCRIPTIONS

# Настройка ЮKassa
Configuration.configure(SHOP_ID, PAYMENT_TOKEN)

async def create_payment_link(sub_id, user_id, chat_id):
    sub_info = AVAILABLE_SUBSCRIPTIONS.get(sub_id)
    if not sub_info:
        return "Ошибка: тариф не найден."

    amount = sub_info['price']
    description = sub_info['name']
    idempotency_key = str(uuid.uuid4())

    try:
        # ВАЖНО: вызываем Payment.create, а не create_payment_link!
        payment = Payment.create({
            "amount": {"value": f"{amount}.00", "currency": "RUB"},
            "confirmation": {
                "type": "redirect",
                "return_url": "https://max.ru/id973302994385_1_bot" # Ссылка на вашего бота
            },
            "capture": True,
            "description": description,
            "metadata": {
                "user_id": str(user_id),
                "chat_id": str(chat_id), # Добавьте передачу chat_id
                "sub_id": sub_id
            }
        }, idempotency_key)

        return payment.confirmation.confirmation_url
    except Exception as e:
        return f"Ошибка платежной системы: {e}"