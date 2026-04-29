# subscriptions_config.py

DEFAULT_SUBSCRIPTION = {
    "inactive": {
        "name": "Нет подписки",
        "requests": 0

    }
}

AVAILABLE_SUBSCRIPTIONS = {
    "sub_5": {
        "name": "5 запросов в день на месяц",
        "price": 79,
        "requests": 5,
        "duration_days": 31
    },
    "sub_10": {
        "name": "10 запросов в день на месяц",
        "price": 159,
        "requests": 10,
        "duration_days": 31
    },
    "sub_20": {
        "name": "20 запросов в день на месяц",
        "price": 309,
        "requests": 20,
        "duration_days": 31
    },
    "sub_50": {
        "name": "50 запросов в день на месяц",
        "price": 779,
        "requests": 50,
        "duration_days": 31
    }
}