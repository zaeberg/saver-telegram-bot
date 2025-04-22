# Используем официальный базовый образ Python 3.10/3.11 slim
FROM python:3.11-slim-bookworm as base

# Устанавливаем рабочую директорию в контейнере
WORKDIR /app

# Устанавливаем переменные окружения
ENV PYTHONDONTWRITEBYTECODE 1 # Предотвращает создание .pyc файлов
ENV PYTHONUNBUFFERED 1       # Вывод Python напрямую в терминал (полезно для логов Docker)

# Системные зависимости: ffmpeg нужен для yt-dlp (слияние форматов) и moviepy
# Устанавливаем зависимости одной командой для уменьшения слоев
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Копируем файл с зависимостями
COPY requirements.txt .

# Устанавливаем Python-зависимости
# --no-cache-dir чтобы не хранить кеш pip и уменьшить размер образа
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код вашего бота в рабочую директорию /app
# Теперь код будет лежать в /app/saver-telegram-bot/
COPY saver-telegram-bot/ ./saver-telegram-bot/

# Создаем директорию temp, если ее нет (хотя BaseDownloader ее создает)
# и даем права, если будем использовать не-root пользователя (хорошая практика)
# RUN mkdir -p /app/saver-telegram-bot/temp

# --- Опционально: Запуск от не-root пользователя ---
# Создаем пользователя приложения
# RUN useradd --system --create-home appuser
# RUN chown -R appuser:appuser /app
# Переключаемся на пользователя
# USER appuser
# Если вы используете USER appuser, убедитесь, что у него есть права на запись в /app/saver-telegram-bot/temp
# -------------------------------------------------

# Команда для запуска бота при старте контейнера
CMD ["python", "saver-telegram-bot/bot.py"]
