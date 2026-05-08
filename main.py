from aiohttp import web # lt --port 8080 --subdomain empty-snail-52
from config.config_main import TOKEN # function qw { .\venv\Scripts\activate; python main.py }
from handlers.handlers_main import setup_handlers
from bot_client import MaxBot
from lifecycle.lifecycle_main import on_startup, on_cleanup

# Инициализируем бота из нового файла
bot = MaxBot(TOKEN)

def main():
    app = web.Application()
    
    # Настраиваем роуты (вебхуки)
    setup_handlers(app, bot)
    
    # Подключаем логику запуска и остановки
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    
    # Запуск
    web.run_app(app, host='0.0.0.0', port=8080)

if __name__ == "__main__":
    main()