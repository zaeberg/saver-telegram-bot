HELP_MESSAGE = """
Привет! Я бот для скачивания медиа.

Отправь мне ссылку из Twitter, YouTube Shorts или Instagram Reels, и я скачаю видео или аудио.

Доступные команды:
/video <ссылка> - скачать видео
/audio <ссылка> - скачать аудио
/help - эта справка
"""

UNKNOWN_COMMAND_MESSAGE = "Неизвестная команда или неверный формат. Используйте /help для справки."
MISSING_URL_MESSAGE = "Пожалуйста, укажите ссылку после команды. Пример: {} <ссылка>"
INVALID_URL_MESSAGE = "Ошибка: Пожалуйста, предоставьте корректную ссылку."
UNSUPPORTED_DOMAIN_MESSAGE = "Ошибка: Бот поддерживает только ссылки на видео из Twitter, YouTube Shorts и Instagram Reels."
PROCESSING_MESSAGE = "Получена команда {} для URL: {}. Обработка еще не реализована."
PROCESSING_START_MESSAGE = "Запрос принят, начинаю обработку..."
DOWNLOAD_ERROR_MESSAGE = "Ошибка: Не удалось скачать видео. Возможно, оно недоступно или приватное."
TECHNICAL_ERROR_MESSAGE = "Произошла техническая ошибка. Пожалуйста, попробуйте позже."
NOT_IMPLEMENTED_MESSAGE = "Загрузка с {} пока не реализована."
FILE_TOO_LARGE_MESSAGE = "Извините, видео слишком большое для отправки в Telegram (максимум 50MB). Попробуйте другое видео."
UNAVAILABLE_REELS = "Извините, этот Reel недоступен (приватный контент)"

SUPPORTED_DOMAINS = {
    'youtube.com': 'YouTube',
    'youtu.be': 'YouTube',
    'twitter.com': 'Twitter',
    'x.com': 'Twitter',
    'instagram.com': 'Instagram'
}
