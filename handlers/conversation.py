from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters,
)
from utils.constants import (
    ACTION_EMPTY, USE_BUTTONS_WARN, VIDEO_BUTTON_TEXT, AUDIO_BUTTON_TEXT, CANCEL_BUTTON_TEXT,
    WAIT_FOR_LINK, ACTION_CANCEL, QUEUE_MESSAGE, HELP_MESSAGE,
    TECHNICAL_ERROR_MESSAGE, NOT_IMPLEMENTED_MESSAGE,
    SUPPORTED_DOMAINS
)
from utils.validate_url import validate_url
from utils.logger import logger, request_context
from ui.keyboards import get_main_keyboard_markup, get_cancel_keyboard_markup

# Возможные состояния
CHOOSING_ACTION, AWAITING_LINK = range(2)

# Функции-обработчики для состояний
async def ask_for_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало диалога или возврат к выбору действия."""
    with request_context():
        logger.info(f"User {update.effective_user.id} entering action selection.")
        await update.message.reply_text(HELP_MESSAGE, reply_markup=get_main_keyboard_markup())
        return CHOOSING_ACTION

async def ask_for_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Пользователь выбрал действие (Видео/Аудио), просим ссылку."""
    with request_context():
        action = update.message.text
        user_id = update.effective_user.id

        if action == VIDEO_BUTTON_TEXT:
            context.user_data['action_type'] = 'video'
            logger.info(f"User {user_id} selected action: video")
        elif action == AUDIO_BUTTON_TEXT:
            context.user_data['action_type'] = 'audio'
            logger.info(f"User {user_id} selected action: audio")
        else:
            logger.warning(f"User {user_id} sent unexpected text in CHOOSING_ACTION: {action}")
            await update.message.reply_text(USE_BUTTONS_WARN, reply_markup=get_main_keyboard_markup())
            return CHOOSING_ACTION

        await update.message.reply_text(WAIT_FOR_LINK, reply_markup=get_cancel_keyboard_markup())
        return AWAITING_LINK

async def handle_link_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Пользователь отправил текст, когда бот ожидал ссылку."""
    with request_context() as request_id:
        url = update.message.text
        chat_id = update.message.chat_id
        user_id = update.effective_user.id
        action_type = context.user_data.get('action_type')

        # Проверка на наличие action_type на всякий случай
        if not action_type:
            logger.error(f"User {user_id} in AWAITING_LINK state without action_type.")
            await update.message.reply_text(TECHNICAL_ERROR_MESSAGE, reply_markup=get_main_keyboard_markup())
            context.user_data.clear()
            return ConversationHandler.END

        # Обработка кнопки "Отмена" внутри состояния ожидания ссылки
        if url == CANCEL_BUTTON_TEXT:
            logger.info(f"User {user_id} cancelled action '{action_type}'")
            await update.message.reply_text(ACTION_CANCEL, reply_markup=get_main_keyboard_markup())
            context.user_data.clear()
            return ConversationHandler.END

        logger.info(f"[{request_id}] Received potential link '{url}' from user {user_id} for action '{action_type}'")

        # Валидация ссылки
        is_valid, error_message, platform = validate_url(url)
        if not is_valid:
            logger.warning(f"Invalid URL from {user_id}: {url}. Reason: {error_message}")
            await update.message.reply_text(error_message, reply_markup=get_cancel_keyboard_markup())
            return AWAITING_LINK # Ждем ссылку

        # Валидация платформы
        supported_platforms = list(SUPPORTED_DOMAINS.values())
        if platform not in supported_platforms:
            logger.warning(f"Unsupported platform from {user_id}: {platform} ({url})")
            await update.message.reply_text(NOT_IMPLEMENTED_MESSAGE.format(platform or 'Unknown'), reply_markup=get_cancel_keyboard_markup())
            return AWAITING_LINK # Ждём ссылку

        # Ставим задачу в очередь воркера
        try:
            download_queue = context.bot_data['download_queue']
            job = {
                'chat_id': chat_id,
                'url': url,
                'type': action_type,
                'platform': platform,
                'request_id': request_id
            }
            await download_queue.put(job)
            logger.info(f"Job for {url} added to queue.")
            await update.message.reply_text(QUEUE_MESSAGE, reply_markup=get_main_keyboard_markup()) # Возвращаем основную клавиатуру

        except KeyError:
            logger.critical("Download queue not found!")
            await update.message.reply_text(TECHNICAL_ERROR_MESSAGE, reply_markup=get_main_keyboard_markup())
        except Exception as e:
            logger.error(f"[{request_id}] Error adding job to queue: {e}", exc_info=True)
            await update.message.reply_text(TECHNICAL_ERROR_MESSAGE, reply_markup=get_main_keyboard_markup())

        # Очищаем состояние пользователя
        context.user_data.clear()
        # Завершаем диалог
        return ConversationHandler.END

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка команды /cancel во время диалога."""
    with request_context():
        user_id = update.effective_user.id
        action = context.user_data.get('action_type')
        log_msg = f"User {user_id} used /cancel"
        reply_text = ACTION_CANCEL

        if action:
            log_msg += f" during action '{action}'"
        else:
            log_msg += " without an active action selection."
            reply_text = ACTION_EMPTY

        logger.info(log_msg)
        context.user_data.clear()
        await update.message.reply_text(reply_text, reply_markup=get_main_keyboard_markup())
        return ConversationHandler.END

async def unexpected_input_in_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка неожиданного ввода внутри диалога."""
    with request_context():
        # Получаем текущее состояние
        current_state = context.user_data.get(ConversationHandler.STATE)
        logger.warning(f"User {update.effective_user.id} sent unexpected input '{update.message.text}' in state {current_state}")
        await update.message.reply_text(
            USE_BUTTONS_WARN,
            reply_markup=get_cancel_keyboard_markup() if current_state == AWAITING_LINK else get_main_keyboard_markup()
        )

# Создание ConversationHandler
# По сути конечный автомат где каждому состоянию соответствует функция обработчик
# А внутри происходит переключение состояний и обработка ввода пользователя
def get_conversation_handler() -> ConversationHandler:
    conv_handler = ConversationHandler(
        entry_points=[
            # Команды /start или /help могут начать диалог выбора действия
            CommandHandler('start', ask_for_action),
            CommandHandler('help', ask_for_action),
            # Нажатие кнопок Видео/Аудио начинает диалог, если он не активен
            MessageHandler(filters.Regex(f'^({VIDEO_BUTTON_TEXT}|{AUDIO_BUTTON_TEXT})$'), ask_for_link)
        ],
        states={
            CHOOSING_ACTION: [
                MessageHandler(filters.Regex(f'^({VIDEO_BUTTON_TEXT}|{AUDIO_BUTTON_TEXT})$'), ask_for_link),
                # Можно добавить обработку других кнопок/текста на этом этапе, если нужно
            ],
            AWAITING_LINK: [
                # Обрабатываем кнопку Отмена или любую текстовую ссылку
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link_input),
            ],
        },
        fallbacks=[
            # Обработчик отмены состояния
            CommandHandler('cancel', cancel_conversation),
            # Обработчик для неожиданных команд/сообщений внутри диалога
            MessageHandler(filters.COMMAND, unexpected_input_in_conversation),
            # Ловит вообще все остальное
            MessageHandler(filters.ALL, unexpected_input_in_conversation),
        ],
        # Может понадобиться для отладки
        # persistent=True, name="download_conversation"
    )
    return conv_handler
