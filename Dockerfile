# Используем стабильный python-slim для уменьшения размера образа
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости для работы с Postgres (если нужно будет компилировать бинарники)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Копируем зависимости и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все файлы бота в контейнер
COPY . .

# Открываем порт, на котором работает aiohttp (согласно вашему main.py)
EXPOSE 8080

# Команда для запуска
CMD ["python", "main.py"]