import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from database import db
from logger_config import logger
from config import TOKEN, WEBHOOK_URL

# Инициализируем планировщик
scheduler = AsyncIOScheduler()

async def scheduled_cleanup():
    """Фоновая задача для очистки базы данных"""
    try:
        logger.info("Запуск плановой очистки истории сообщений...")
        # Удаляем сообщения старше 3 дней
        await db.clear_old_history() 
        logger.info("Плановая очистка завершена успешно.")
    except Exception as e:
        logger.error(f"Ошибка при выполнении плановой очистки: {e}")

async def check_subscriptions_task():
    """Фоновая задача для проверки просрочки"""
    try:
        logger.info("Проверка истекших подписок...")
        await db.deactivate_expired_subscriptions("inactive")
    except Exception as e:
        logger.error(f"Ошибка в задаче проверки подписок: {e}")

async def on_startup(app):
    """Логика при запуске сервера"""
    # 1. Подключаемся к БД
    await db.connect()
    
    # 2. Регистрация вебхука в MAX
    # webhook_url = f"https://my-super-gpt-bot.loca.lt{WEBHOOK_PATH}"
    api_url = "https://platform-api.max.ru/subscriptions"
    headers = {"Authorization": TOKEN, "Content-Type": "application/json"}
    
    try:
        async with aiohttp.ClientSession() as session:
            payload = {"url": WEBHOOK_URL, "event_types": ["message_created"]}
            async with session.post(api_url, json=payload, headers=headers) as resp:
                if resp.status in [200, 201]:
                    logger.info(f"Вебхук успешно зарегистрирован: {WEBHOOK_URL}")
                else:
                    logger.warning(f"MAX API вернул статус {resp.status} при регистрации вебхука")
    except Exception as e:
        logger.error(f"Не удалось зарегистрировать вебхук: {e}")

    # 3. Настройка планировщика

    # Запускаем проверку итсекших подписок каждый час
    scheduler.add_job(check_subscriptions_task, 'cron', hour=4, minute=0)

    # Запускаем очистку каждый день в 3:00 ночи
    scheduler.add_job(scheduled_cleanup, 'cron', hour=3, minute=0)
    
    # Также можно добавить один запуск сразу при старте для теста (опционально)
    # scheduler.add_job(scheduled_cleanup) 
    
    scheduler.start()
    logger.info("Бот готов к работе!")

async def on_cleanup(app):
    """Логика при остановке сервера"""
    # Останавливаем планировщик
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Планировщик задач остановлен.")
        
    # Отключаемся от БД
    await db.disconnect()
    logger.info("Бот успешно остановлен.")