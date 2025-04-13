HELP_MESSAGE = """
Привет! Я могу помочь тебе скачать видео или аудио из YouTube, Twitter и Instagram.

Просто нажми на нужную кнопку и следом отправь мне ссылку.
Например: https://www.youtube.com/watch?v=dQw4w9WgXcQ

Пожалуйста, учти ограничения Telegram на размер файла (~49MB). Я постараюсь выбрать наилучшее качество в рамках этого лимита.
"""

FILE_TOO_LARGE_MESSAGE = "Ошибка: Файл слишком большой ({}) для отправки через Telegram (лимит ~49MB)."
DOWNLOAD_ERROR_MESSAGE = "Ошибка: Не удалось скачать файл. Попробуйте другую ссылку или повторите позже."
TECHNICAL_ERROR_MESSAGE = "Ошибка: Произошла техническая ошибка. Пожалуйста, попробуйте позже."
INVALID_URL_MESSAGE = "Ошибка: Пожалуйста, предоставьте корректную ссылку."
UNSUPPORTED_DOMAIN_MESSAGE = "Ошибка: Бот поддерживает только ссылки на видео из Twitter, YouTube Shorts и Instagram Reels."
START_AGAIN="Ошибка: Попробуйте снова /start"

QUEUE_MESSAGE = "Работаю"
ACTION_CANCEL="Действие отменено"
ACTION_EMPTY="Сейчас нет активного действия для отмены"
WAIT_FOR_LINK="Жду ссылку"

NOT_IMPLEMENTED_MESSAGE = "Скачивание с платформы {} пока не поддерживается."
MISSING_URL_MESSAGE = "Пожалуйста, укажите ссылку после команды. Например: {} <ссылка>"

UNAVAILABLE_REELS = "Не могу скачать это видео из Instagram. Возможно, оно приватное или требует входа в аккаунт."
UNKNOWN_COMMAND_MESSAGE = "Неизвестная команда или неверный формат. Используйте /help чтобы увидеть список команд."

SUPPORTED_DOMAINS = {
    'youtube.com': 'YouTube',
    'youtu.be': 'YouTube',
    'twitter.com': 'Twitter',
    'x.com': 'Twitter',
    'instagram.com': 'Instagram'
}
