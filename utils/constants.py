# Константы для кнопок
VIDEO_BUTTON_TEXT = "Видео 🎬"
AUDIO_BUTTON_TEXT = "Аудио 🎵"
CANCEL_BUTTON_TEXT = "Отмена 🚫"


HELP_MESSAGE = """
Привет! Я могу помочь тебе скачать видео или аудио из YouTube, Twitter и Instagram.

Просто нажми на нужную кнопку и следом отправь мне ссылку.
Например: https://www.youtube.com/watch?v=dQw4w9WgXcQ

Пожалуйста, учти ограничения Telegram на размер файла (~49MB). Я постараюсь выбрать наилучшее качество в рамках этого лимита.
"""

FILE_TOO_LARGE_MESSAGE = "☹️ Ошибка: Файл слишком большой ({}) для отправки через Telegram (лимит ~49MB)."
DOWNLOAD_ERROR_MESSAGE = "☹️ Ошибка: Не удалось скачать файл. Попробуй другую ссылку или повтори попытку позже."
TECHNICAL_ERROR_MESSAGE = "☹️ Ошибка: Произошла техническая ошибка. Пожалуйста, попробуй позже."
INVALID_URL_MESSAGE = f"☹️ Ошибка: Пожалуйста, предоставь корректную ссылку или нажми '{CANCEL_BUTTON_TEXT}'."
UNSUPPORTED_DOMAIN_MESSAGE = "☹️ Ошибка: Бот поддерживает только ссылки на видео из Twitter, YouTube Shorts и Instagram Reels."

QUEUE_MESSAGE = "⏳ Загружаю, пожалуйста подожди"
ACTION_CANCEL="☝️Действие отменено"
ACTION_EMPTY="👇 Нечего отменять"
WAIT_FOR_LINK="🔗 Отправь ссылку в чат"

USE_BUTTONS_WARN = "⚠️ Пожалуйста, используй кнопки."
NOT_IMPLEMENTED_MESSAGE = "☹️ Скачивание с платформы {} пока не поддерживается."

UNAVAILABLE_REELS = "☹️ Не могу скачать это видео из Instagram. Возможно, оно приватное или требует входа в аккаунт."

UNKNOWN_COMMAND_MESSAGE = "🤡 Неизвестная команда или неверный формат. Попробуй /help чтобы увидеть список команд."

SUPPORTED_DOMAINS = {
    'youtube.com': 'YouTube',
    'youtu.be': 'YouTube',
    'twitter.com': 'Twitter',
    'x.com': 'Twitter',
    'instagram.com': 'Instagram'
}
