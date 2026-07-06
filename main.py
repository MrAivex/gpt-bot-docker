# main.py
from aiohttp import web
from core.container import AppContainer
from config.logger import logger
from config.main import TOKEN, WEBHOOK_URL, WEBHOOK_PATH
import os

async def on_startup(app):
    # 1. Инициализация контейнера
    container = AppContainer()
    await container.initialize()
    app['container'] = container

    # 2. Регистрация вебхука MAX
    import aiohttp
    api_url = "https://platform-api.max.ru/subscriptions"
    headers = {"Authorization": TOKEN, "Content-Type": "application/json"}
    try:
        async with aiohttp.ClientSession() as session:
            payload = {"url": WEBHOOK_URL, "event_types": ["message_created"]}
            async with session.post(api_url, json=payload, headers=headers) as resp:
                if resp.status in [200, 201]:
                    logger.info(f"Вебхук зарегистрирован: {WEBHOOK_URL}")
                else:
                    logger.warning(f"Ошибка регистрации вебхука: {resp.status}")
    except Exception as e:
        logger.error(f"Не удалось зарегистрировать вебхук: {e}")

    # 3. Подключаем маршруты к уже готовому контейнеру
    from handlers.webhook import WebhookHandler
    handler = WebhookHandler(container)
    app.router.add_post(WEBHOOK_PATH, handler.handle_max_webhook)
    app.router.add_post('/yookassa-webhook', handler.handle_yookassa_webhook)

    # 4. Запуск планировщика фоновых задач
    from core.scheduler import SchedulerService
    scheduler = SchedulerService(container)
    scheduler.start()
    app['scheduler'] = scheduler

async def on_cleanup(app):
    container = app.get('container')
    if container:
        await container.shutdown()
    scheduler = app.get('scheduler')
    if scheduler:
        scheduler.shutdown()

def main():
    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    os.makedirs('temp_images', exist_ok=True)
    app.router.add_static('/temp_images/', path='temp_images', name='temp_images')
    web.run_app(app, host='0.0.0.0', port=8080)

if __name__ == "__main__":
    main()