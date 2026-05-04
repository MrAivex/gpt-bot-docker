# subscriptions_config.py

DEFAULT_SUBSCRIPTION = {
    "inactive": {
        "name": "Нет подписки",
        "requests": 0

    }
}

AVAILABLE_SUBSCRIPTIONS = {
    "sub_10": {
        "name": "10 запросов в день на месяц",
        "price": 79,
        "requests": 10,
        "duration_days": 31
    },
    "sub_20": {
        "name": "20 запросов в день на месяц",
        "price": 159,
        "requests": 20,
        "duration_days": 31
    },
    "sub_40": {
        "name": "40 запросов в день на месяц",
        "price": 309,
        "requests": 40,
        "duration_days": 31
    },
    "sub_100": {
        "name": "100 запросов в день на месяц",
        "price": 779,
        "requests": 100,
        "duration_days": 31
    }
}

def create_reset_limits_text(sub_list):
    """Динамически сбрасывает счетчики на основе конфига подписок"""
    
    # 1. Формируем части CASE для SQL
    # Мы перебираем все подписки из словаря AVAILABLE_SUBSCRIPTIONS
    case_parts = []
    for sub_id, info in sub_list.items():
        # Добавляем строку вида: WHEN subscription_type = 'sub_5' THEN 5
        case_parts.append(f"WHEN subscription_type = '{sub_id}' THEN {info['requests']}")
    
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
          AND subscription_type != 'inactive'
    '''
    return query

RESET_LIMITS_TEXT = create_reset_limits_text(AVAILABLE_SUBSCRIPTIONS)