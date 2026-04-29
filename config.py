import os

TOKEN = "f9LHodD0cOKpRm54dQO2ji8dNZcUtkJSpeFRWkP98hwIPZO3R9PtiSg759pxVK7jWQNNCePOp5eldQ8_MpDN"

# локальный запуск
DB_DSN = "postgresql://postgres:NoForgot_938@localhost:5432/gpt_bot_db"

# запуск на серваке
# DB_DSN = "postgresql://postgres:NoForgot_938@db:5432/gpt_bot_db"

WEBHOOK_PATH = "/max-webhook"
ADMIN_ID = 5787551
OPENAI_API_KEY = "sk-jEDV6RE5q33qb53PDf58LVt4LjA2MS8ei9rPdg1pLw2GgCyN"
PAYMENT_TOKEN="test_xNodPvs81RMcfJm0G46N2Siu9-EJOnMJWyNtQxA4n_I"
SHOP_ID="1342218"
SUPPORT_LINK="https://max.ru/u/f9LHodD0cOIdennqYfdEQFtEvXCDlTkAAm3lFWmfN4GgG94KMLS2FqXsgr8"

# локальный запуск
WEBHOOK_URL=f"https://my-super-gpt-bot.loca.lt{WEBHOOK_PATH}"

# запуск на серваке
# WEBHOOK_URL=f"https://max-gpt-ai-helper-bot.ru{WEBHOOK_PATH}"