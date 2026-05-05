import os

#------------ЗАПУСК В VS CODE-------------------------------------------------------------------------------
# function qw { .\venv\Scripts\activate; python main.py }
# lt --port 8080 --subdomain empty-snail-52

#------------УНИВЕРСАЛЬНЫЕ ПЕРЕМЕННЫЕ-------------------------------------------------------------------------------
WEBHOOK_PATH = "/max-webhook"
ADMIN_ID = [5787551, 38065306]
OPENAI_API_KEY = "sk-jEDV6RE5q33qb53PDf58LVt4LjA2MS8ei9rPdg1pLw2GgCyN"
SUPPORT_LINK="https://max.ru/u/f9LHodD0cOIdennqYfdEQFtEvXCDlTkAAm3lFWmfN4GgG94KMLS2FqXsgr8"
ADMIN_COMMANDS=["/admin", "/count", "/user", "/update", "/max_queries", "/active_users"]

#------------ЛОКАЛЬНЫЙ ЗАПУСК-------------------------------------------------------------------------------
# TOKEN = "f9LHodD0cOKpRm54dQO2ji8dNZcUtkJSpeFRWkP98hwIPZO3R9PtiSg759pxVK7jWQNNCePOp5eldQ8_MpDN"
# DB_DSN = "postgresql://postgres:NoForgot_938@localhost:5432/gpt_bot_db"
# WEBHOOK_URL=f"https://empty-snail-52.loca.lt{WEBHOOK_PATH}"
# RETURN_URL="https://max.ru/id973302994385_1_bot"

# Ссылка для уведомлений Юкассы: https://empty-snail-52.loca.lt/yookassa-webhook

#------------ЗАПУСК НА СЕРВАКЕ------------------------------------------------------------------------------
TOKEN = "f9LHodD0cOJJRiHaYG-mG1_HdoxpzU-e4nyNFAv7RiLsJ6BGBunLQsdCEMlY5wco6ZBJwg4KIcOtSf_DBp8q"
DB_DSN = "postgresql://postgres:NoForgot_938@db:5432/gpt_bot_db"
WEBHOOK_URL=f"https://max-gpt-ai-helper-bot.ru{WEBHOOK_PATH}"
RETURN_URL="https://max.ru/id973302994385_bot"

# Ссылка для уведомлений Юкассы: https://max-gpt-ai-helper-bot.ru/yookassa-webhook

#------------ТЕСТОВЫЙ МАГАЗИН--------------------------------------------------------------------------------
# PAYMENT_TOKEN="test_xNodPvs81RMcfJm0G46N2Siu9-EJOnMJWyNtQxA4n_I"
# SHOP_ID="1342218"

#------------РЕАЛЬНЫЙ МАГАЗИН--------------------------------------------------------------------------------
PAYMENT_TOKEN="live_UBT3bTpvjjaxLSXxm4PD7GtFSjhIUOAGQNbjd2yFYks"
SHOP_ID="1336875"