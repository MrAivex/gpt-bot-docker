# core/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config.logger import logger

class SchedulerService:
    def __init__(self, container):
        self.container = container
        self.scheduler = AsyncIOScheduler()

    def start(self):
        # Проверка истекших подписок раз в день в 00:30
        self.scheduler.add_job(
            self.container.subscription_service.deactivate_expired,
            'cron', hour=0, minute=30
        )
        # Сброс лимитов активных подписок раз в день в 01:00
        self.scheduler.add_job(
            self.container.subscription_service.reset_limits_for_active,
            'cron', hour=1, minute=0
        )
        # Очистка старых сообщений раз в день в 01:30
        self.scheduler.add_job(
            self.container.message_repo.clear_old_history,
            'cron', hour=1, minute=30
        )
        self.scheduler.start()
        logger.info("Планировщик фоновых задач запущен.")

    def shutdown(self):
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Планировщик остановлен.")