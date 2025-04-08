import os
from dotenv import load_dotenv

# Загрузка переменных окружения из файла .env
load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
