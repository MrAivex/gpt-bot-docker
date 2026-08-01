# subscriptions_config.py
from dataclasses import dataclass

@dataclass
class SubscriptionPlan:
    id: str
    name: str
    price: int
    sub_queries: int = 0
    bonus_queries: int = 0
    duration_days: int = 0   # 0 = разовый пакет, >0 = подписка


_ALL_PLANS = [
    SubscriptionPlan("inactive", "Нет подписки", 0, 10, 0, 0),
    SubscriptionPlan("sub_50_31", "50 🧩/день на месяц", 199, 50, 0, 31),
    SubscriptionPlan("sub_100_31", "100 🧩/день на месяц", 399, 100, 0, 31),
    SubscriptionPlan("sub_200_31", "200 🧩/день на месяц", 699, 200, 0, 31),
    SubscriptionPlan("sub_100_0", "Пакет 100 🧩", 19, 0, 100, 0),
    SubscriptionPlan("sub_300_0", "Пакет 300 🧩", 49, 0, 300, 0),
    SubscriptionPlan("sub_500_0", "Пакет 500 🧩", 79, 0, 500, 0),
    SubscriptionPlan("sub_1000_0", "Пакет 1000 🧩", 149, 0, 1000, 0),
    SubscriptionPlan("sub_3000_0", "Пакет 3000 🧩", 439, 0, 3000, 0),
    SubscriptionPlan("sub_10000_0", "Пакет 10000 🧩", 1399, 0, 10000, 0),
    
]

# Словарь доступных для покупки (без inactive)
AVAILABLE_SUBSCRIPTIONS = {p.id: p for p in _ALL_PLANS if p.id != "inactive"}

# Объект неактивной подписки
DEFAULT_SUBSCRIPTION = next(p for p in _ALL_PLANS if p.id == "inactive")


# DEFAULT_SUBSCRIPTION = {
#     "inactive": {
#         "name": "Нет подписки",
#         "price": 0,
#         "requests": 0,
#         "duration_days": 0
#     }
# }

# AVAILABLE_SUBSCRIPTIONS = {
#     "sub_unlim_1d": {
#         "name": "Безлимит на день",
#         "price": 39,
#         "requests": 10000,
#         "duration_days": 1
#     },
#     "sub_unlim_3d": {
#         "name": "Безлимит на 3 дня",
#         "price": 99,
#         "requests": 30000,
#         "duration_days": 3
#     },
#     "sub_unlim_7d": {
#         "name": "Безлимит на неделю",
#         "price": 189,
#         "requests": 70000,
#         "duration_days": 7
#     },
#     "sub_10": {
#         "name": "10 запросов/день на месяц",
#         "price": 79,
#         "requests": 10,
#         "duration_days": 31
#     },
#     "sub_20": {
#         "name": "20 запросов/день на месяц",
#         "price": 159,
#         "requests": 20,
#         "duration_days": 31
#     },
#     "sub_40": {
#         "name": "40 запросов/день на месяц",
#         "price": 309,
#         "requests": 40,
#         "duration_days": 31
#     },
#     "sub_100": {
#         "name": "100 запросов/день на месяц",
#         "price": 779,
#         "requests": 100,
#         "duration_days": 31
#     }
# }

def create_reset_limits_text(sub_list):
    """Динамически сбрасывает счетчики на основе конфига подписок"""
    
    # 1. Формируем части CASE для SQL
    # Мы перебираем все подписки из словаря AVAILABLE_SUBSCRIPTIONS
    case_parts = []
    for sub_id, info in sub_list.items():
        # Добавляем строку вида: WHEN subscription_status = 'sub_5' THEN 5
        case_parts.append(f"WHEN subscription_status = '{sub_id}' THEN {info['requests']}")
    
    # Соединяем все части в одну строку
    case_statement = "\n                ".join(case_parts)

    # 2. Собираем итоговый SQL запрос
    query = f'''
        UPDATE users 
        SET available_queries = CASE 
                {case_statement}
                ELSE available_queries
            END,
            used_queries = 0
        WHERE subscription_end > CURRENT_TIMESTAMP 
          AND subscription_status != 'inactive'
    '''
    return query