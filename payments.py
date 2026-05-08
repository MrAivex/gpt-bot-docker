import uuid
from yookassa import Configuration, Payment
from config import SHOP_ID, PAYMENT_TOKEN, RETURN_URL
from subscriptions_config import AVAILABLE_SUBSCRIPTIONS
from logger_config import logger

# Настройка ЮKassa
Configuration.configure(SHOP_ID, PAYMENT_TOKEN)

async def create_payment_link(sub_id, user_id, chat_id, subscription_end, email):
    sub_info = AVAILABLE_SUBSCRIPTIONS.get(sub_id)
    if not sub_info:
        return None

    amount = sub_info['price']
    description = sub_info['name']
    idempotency_key = str(uuid.uuid4())

    try:
        # ВАЖНО: вызываем Payment.create, а не create_payment_link!
        payment = Payment.create({
            "amount": {"value": f"{amount}.00", "currency": "RUB"},
            "confirmation": {
                "type": "redirect",
                "return_url": f"{RETURN_URL}" # Ссылка на вашего бота
            },
            "capture": True,
            "save_payment_method": True,
            "description": description,
            "metadata": {
                "subscription_end": str(subscription_end),
                "user_id": str(user_id),
                "chat_id": str(chat_id), # Добавьте передачу chat_id
                "sub_id": sub_id,
                "auto_renewal": "true" # Пометка для нас
            },
            "receipt": {
                "customer": {
                    "email": email
                },
                "items": [
                    {
                        "description": f"Доступ к сервису (подписка {sub_id})",
                        "quantity": "1.00",
                        "amount": {
                            "value": f"{amount}.00",
                            "currency": "RUB"
                        },
                        "vat_code": "1",  # 1 — Без НДС (обязательно для ИП на НПД / самозанятых)
                        "payment_mode": "full_prepayment",
                        "payment_subject": "service"
                    }
                ]
            }
        }, idempotency_key)

        return payment.confirmation.confirmation_url
    except Exception as e:
        return f"Ошибка платежной системы: {e}"
    
async def create_recurring_payment(sub_id, user_id, chat_id, subscription_end, email, payment_token):
    sub_info = AVAILABLE_SUBSCRIPTIONS.get(sub_id)
    if not sub_info:
        return "Ошибка: тариф не найден."

    amount = sub_info['price']
    description = sub_info['name']

    idempotency_key = str(uuid.uuid4())
    
    try:
        payment = Payment.create({
            "amount": {
                "value": f"{amount}.00",
                "currency": "RUB"
            },
            "capture": True,
            "payment_method_id": payment_token, # Используем сохраненный токен
            "description": f"{description}",
            "metadata": {
                "subscription_end": str(subscription_end),
                "user_id": str(user_id),
                "chat_id": str(chat_id),
                "sub_id": sub_id,
                "auto_renewal": "true"
            },
            "receipt": {
                "customer": {
                    "email": email # Email обязателен для чека по 54-ФЗ
                },
                "items": [
                    {
                        "description": f"Автопродление подписки {sub_id}",
                        "quantity": "1.00",
                        "amount": {
                            "value": f"{amount}.00",
                            "currency": "RUB"
                        },
                        "vat_code": "1", # Без НДС
                        "payment_mode": "full_prepayment",
                        "payment_subject": "service"
                    }
                ]
            }
        }, idempotency_key)

        return payment
    except Exception as e:
        logger.error(f"Ошибка при создании рекуррентного платежа для {user_id}: {e}")
        return None