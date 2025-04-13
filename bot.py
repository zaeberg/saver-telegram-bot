import asyncio
import os
from config import TELEGRAM_TOKEN
from utils.get_video_info import get_video_info
from utils.validate_url import validate_url
from utils.logger import logger, request_context
from utils.constants import (
    HELP_MESSAGE,
    UNAVAILABLE_REELS,
    UNKNOWN_COMMAND_MESSAGE,
    MISSING_URL_MESSAGE,
    QUEUE_MESSAGE,
    NOT_IMPLEMENTED_MESSAGE,
    DOWNLOAD_ERROR_MESSAGE,
    TECHNICAL_ERROR_MESSAGE,
    FILE_TOO_LARGE_MESSAGE,
    START_AGAIN,
    ACTION_CANCEL,
    ACTION_EMPTY,
    WAIT_FOR_LINK
)
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from utils.downloader_base import DownloadError
from utils.downloader_youtube import YouTubeDownloader
from utils.downloader_twitter import TwitterDownloader
from utils.downloader_instagram import InstagramDownloader

# Константы для кнопок
VIDEO_BUTTON_TEXT = "Видео 🎬"
AUDIO_BUTTON_TEXT = "Аудио 🎵"
CANCEL_BUTTON_TEXT = "Отмена 🚫"

# Инициализация
youtube_downloader = YouTubeDownloader()
twitter_downloader = TwitterDownloader()
instagram_downloader = InstagramDownloader()

# Воркер для обработки очереди
# Обрабатывает задачи из очереди download_queue.
async def download_worker(application: Application, queue: asyncio.Queue):
    loop = asyncio.get_running_loop()
    logger.info("Download worker started")

    while True:
        job = None
        send_final_keyboard = False # Флаг, нужно ли отправлять основную клавиатуру
        chat_id_for_final_keyboard = None

        try:
            job = await queue.get()
            send_final_keyboard = True
            chat_id_for_final_keyboard = job['chat_id']

            chat_id = job['chat_id']
            url = job['url']
            command_type = job['type']
            platform = job['platform']
            request_id = job['request_id']

            with request_context(request_id):
                logger.info(f"Processing job: [{command_type}] for {url} from chat {chat_id}")

                filepath = None
                title = "Untitled"
                success = False # Флаг успеха операции для сообщения

                try:
                    # Подставляем правильный downloader
                    if platform == 'YouTube':
                        downloader = youtube_downloader
                    elif platform == 'Twitter':
                        downloader = twitter_downloader
                    elif platform == 'Instagram':
                        downloader = instagram_downloader
                    else:
                        logger.warning(f"Unsupported platform: {platform}")
                        await application.bot.send_message(chat_id=chat_id, text=NOT_IMPLEMENTED_MESSAGE.format(platform))
                        queue.task_done()
                        continue

                    # Скачивание
                    if command_type == "video":
                        filepath, title = await downloader.download_video(url, request_id=request_id)
                    elif command_type == "audio":
                        filepath, title = await downloader.download_audio(url, request_id=request_id)
                    else:
                        logger.warning(f"Unsupported command: {command_type}")
                        await application.bot.send_message(chat_id=chat_id, text=TECHNICAL_ERROR_MESSAGE)
                        queue.task_done()
                        continue

                    # Проверка на существование файла
                    exists = await loop.run_in_executor(None, os.path.exists, filepath)
                    if not exists:
                        raise DownloadError("Downloaded file not found")

                    # Отправляем файл
                    logger.info(f"Sending {command_type} from {platform} to chat {chat_id}")
                    if command_type == "video":
                        # Получаем размеры видео запуская процесс в executor
                        width, height = await loop.run_in_executor(None, get_video_info, filepath)

                        try:
                            # Открываем файл и отправляем его пользователю
                            with open(filepath, 'rb') as video_file_to_send:
                                await application.bot.send_video(
                                    chat_id=chat_id,
                                    video=video_file_to_send,
                                    width=width,
                                    height=height,
                                    supports_streaming=True
                                )
                                logger.info(f"Successfully sent video to chat {chat_id} ({filepath})")
                                success = True
                        except FileNotFoundError:
                            logger.error(f"File {filepath} not found before sending")
                            await application.bot.send_message(chat_id=chat_id, text=TECHNICAL_ERROR_MESSAGE)
                        except Exception as send_err:
                            logger.error(f"Error sending video file from path {filepath} to chat {chat_id}: {send_err}", exc_info=True)
                            await application.bot.send_message(chat_id=chat_id, text=TECHNICAL_ERROR_MESSAGE)

                    else: # audio
                        try:
                            # Открываем файл и отправляем его пользователю
                            with open(filepath, 'rb') as audio_file_to_send:
                                await application.bot.send_audio(
                                    chat_id=chat_id,
                                    audio=audio_file_to_send,
                                    title=title,
                                    performer=f"from {platform}"
                                )
                                logger.info(f"Successfully sent audio to chat {chat_id} ({filepath})")
                                success = True
                        except FileNotFoundError:
                            logger.error(f"File {filepath} not found before sending")
                            await application.bot.send_message(chat_id=chat_id, text=TECHNICAL_ERROR_MESSAGE)
                        except Exception as send_err:
                            logger.error(f"Error sending audio file from path {filepath} to chat {chat_id}: {send_err}", exc_info=True)
                            await application.bot.send_message(chat_id=chat_id, text=TECHNICAL_ERROR_MESSAGE)

                except DownloadError as e:
                    error_message_text = str(e)
                    reply_text = DOWNLOAD_ERROR_MESSAGE

                    if "requires Instagram login" in error_message_text:
                        reply_text = UNAVAILABLE_REELS
                    elif "too large" in error_message_text.lower():
                        try:
                            # Извлекаем размер, если он есть в сообщении
                            size_part = error_message_text.split(":")[-1].strip()
                            reply_text = FILE_TOO_LARGE_MESSAGE.format(size_part)
                        except:
                            # Если не удалось извлечь размер
                            reply_text = FILE_TOO_LARGE_MESSAGE.format("?")
                    elif "file not found" in error_message_text.lower():
                        logger.error(f"Downloaded file missing error for {url}")
                    else:
                        pass

                    logger.error(f"Download/Processing error for {url} in chat {chat_id}: {e}")

                    try:
                        await application.bot.send_message(chat_id=chat_id, text=reply_text)
                    except Exception as send_err:
                        logger.error(f"Failed to send error message to chat {chat_id}: {send_err}")

                except Exception as e:
                    logger.error(f"Unexpected error processing job for {url} in chat {chat_id}: {e}", exc_info=True)
                    try:
                        await application.bot.send_message(chat_id=chat_id, text=TECHNICAL_ERROR_MESSAGE)
                    except Exception as send_err:
                        logger.error(f"Failed to send error message to chat {chat_id}: {send_err}")

                finally:
                    # Очистка директории temp от файла
                    if filepath:
                        try:
                            exists = await loop.run_in_executor(None, os.path.exists, filepath)
                            if exists: await loop.run_in_executor(None, os.remove, filepath)
                        except Exception as e:
                            logger.error(f"Error removing temporary file {filepath}: {e}")

                    # Говорим воркееру что задача обработана
                    if job:
                        queue.task_done()
                        logger.info(f"[{request_id}] Job task done.")
                    else:
                        logger.warning("Job was None in finally block, task_done() not called.")

        except asyncio.CancelledError:
            logger.info("Download worker task cancelled.")
            send_final_keyboard = False
            break

        except Exception as e:
            logger.critical(f"Critical error IN download worker MAIN loop: {e}", exc_info=True)
            send_final_keyboard = False
            # ВАЖНО: Попытаться разблокировать очередь, если ошибка произошла ПОСЛЕ get(), но ДО task_done()
            # Проверяем, что job есть и очередь не пуста
            if job and not queue.empty():
                 try:
                     logger.warning("Attempting task_done() after critical worker loop error to prevent queue lock.")
                     queue.task_done()
                 except ValueError:
                     pass
                 except Exception as td_err:
                     logger.error(f"Failed to call task_done() after critical error: {td_err}")
            await asyncio.sleep(5) # Пауза перед следующей итерацией
        finally:
            # Показываем клавиатуру
            if send_final_keyboard and chat_id_for_final_keyboard:
                try:
                    await send_main_keyboard(application, chat_id_for_final_keyboard, "Готово")
                except Exception as final_kb_err:
                    logger.error(f"Failed to send final main keyboard to {chat_id_for_final_keyboard}: {final_kb_err}")

            # Сбрасываем флаги для следующей итерации
            send_final_keyboard = False
            chat_id_for_final_keyboard = None


# Создает разметку основной клавиатуры.
def get_main_keyboard_markup() -> ReplyKeyboardMarkup:
    keyboard = [[KeyboardButton(VIDEO_BUTTON_TEXT), KeyboardButton(AUDIO_BUTTON_TEXT)]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

# Создает разметку клавиатуры отмены
def get_cancel_keyboard_markup() -> ReplyKeyboardMarkup:
    keyboard = [[KeyboardButton(CANCEL_BUTTON_TEXT)]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

# Отправляет сообщение с основной клавиатурой
async def send_main_keyboard(app_or_update, chat_id: int, text: str):
    markup = get_main_keyboard_markup()
    if isinstance(app_or_update, Application):
        await app_or_update.bot.send_message(chat_id, text, reply_markup=markup)
    else: # Это Update
        await app_or_update.message.reply_text(text, reply_markup=markup)

# Отправляет сообщение с клавиатурой отмены
async def send_cancel_keyboard(update: Update, text: str):
    markup = get_cancel_keyboard_markup()
    await update.message.reply_text(text, reply_markup=markup)

# Обработчики
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop('next_action', None) # Сбрасываем состояние
    await send_main_keyboard(update, update.message.chat_id, HELP_MESSAGE)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop('next_action', None)
    await send_main_keyboard(update, update.message.chat_id, HELP_MESSAGE)

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Не проверяем state, так как handle_link должен был обработать ссылку
    logger.info(f"Unknown command: {update.message.text} from {update.effective_user.id}")
    await send_main_keyboard(update, update.message.chat_id, UNKNOWN_COMMAND_MESSAGE)

# Обрабатывает команду /cancel и показывает основную клавиатуру.
async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = context.user_data.pop('next_action', None)
    log_msg = f"User {update.effective_user.id} used /cancel"
    reply_text = "Выберите действие:"
    if action:
        log_msg += f" to cancel action '{action}'"
        reply_text = f"Действие '{action}' отменено."
    logger.info(log_msg)
    await send_main_keyboard(update, update.message.chat_id, reply_text)

# Обработчики текста кнопок
async def handle_button_press(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pressed_button_text = update.message.text
    user_id = update.effective_user.id
    chat_id = update.message.chat_id

    if pressed_button_text == VIDEO_BUTTON_TEXT:
        context.user_data['next_action'] = 'video'
        await send_cancel_keyboard(update, WAIT_FOR_LINK)

    elif pressed_button_text == AUDIO_BUTTON_TEXT:
        context.user_data['next_action'] = 'audio'
        await send_cancel_keyboard(update, WAIT_FOR_LINK)

    elif pressed_button_text == CANCEL_BUTTON_TEXT:
        action = context.user_data.pop('next_action', None)
        reply_text = "Действие отменено." if action else "Нет активного действия для отмены."
        await send_main_keyboard(update, chat_id, reply_text)

    else:
        # Если это не текст кнопки, передаем управление дальше
        # Важно: Этот обработчик должен стоять ПЕРЕД handle_link
        logger.debug(f"Text '{pressed_button_text}' is not a button press.")
        await handle_link(update, context) # Передаем управление обработчику ссылок

# Обработчик для ссылок после нажатия кнопки
# Обрабатывает текстовое сообщение, если ожидается ссылка.
async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    expected_action = context.user_data.get('next_action')

    # Если не ждем ссылку и это не команда - можно считать неизвестным текстом
    # Иначе это может быть неизвестная команда, ее обработает unknown_command
    if not expected_action:
        if not update.message.text.startswith('/'):
            await send_main_keyboard(update, update.message.chat_id, UNKNOWN_COMMAND_MESSAGE)
            return

    url = update.message.text
    chat_id = update.message.chat_id
    username = update.effective_user.username or f"ID:{update.effective_user.id}"

    with request_context() as request_id:
        logger.info(f"[{request_id}] Received potential link '{url}' from user {username} expecting action '{expected_action}'")

        # Валидация урла и платформы
        is_valid, error_message, platform = validate_url(url)
        if not is_valid:
            logger.warning(f"[{request_id}] Invalid URL received via state: {url}. Reason: {error_message}")
            # Просим ссылку или отмену
            await update.message.reply_text(f"{error_message}\n\nПожалуйста, отправь корректную ссылку или нажмите '{CANCEL_BUTTON_TEXT}'.")
            return

        supported_platforms = ['YouTube', 'Twitter', 'Instagram']
        if platform not in supported_platforms:
            logger.warning(f"[{request_id}] Unsupported platform received via state: {platform} from URL: {url}")
            # Не сбрасываем состояние, просим ссылку еще раз
            await update.message.reply_text(NOT_IMPLEMENTED_MESSAGE.format(platform or 'Unknown') + f"\n\nПожалуйста, отправь ссылку с поддерживаемой платформы для скачивания {expected_action}.")
            return

        # Получаем очередь
        try:
            download_queue = context.bot_data['download_queue']
        except KeyError:
            logger.critical(f"[{request_id}] Download queue not found in bot_data!")
            await update.message.reply_text(TECHNICAL_ERROR_MESSAGE)
            # Сбрасываем состояние при критической ошибке
            context.user_data.pop('next_action', None)
            await send_main_keyboard(update, chat_id, "Произошла ошибка.")
            return

        # Ставим задачу в очередь
        await send_main_keyboard(update, update.message.chat_id, QUEUE_MESSAGE)
        job = {
            'chat_id': chat_id,
            'url': url,
            'type': expected_action,
            'platform': platform,
            'request_id': request_id
        }
        await download_queue.put(job)

# Запускает бота и воркер.
async def main():
    with request_context('MAIN'):
        # Создание приложения
        logger.info('Starting bot')

        # Создание очереди
        download_queue = asyncio.Queue()

        # Собираем приложение и СОХРАНЯЕМ очередь в bot_data
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        app.bot_data['download_queue'] = download_queue

        # Запуск воркера
        # Передаем app в воркер, чтобы он мог использовать app.bot
        worker_task = asyncio.create_task(download_worker(app, download_queue))

        # Обработчики команд (порядок важен)
        app.add_handler(CommandHandler('start', start))
        app.add_handler(CommandHandler('help', help_command))
        app.add_handler(CommandHandler('cancel', cancel_command))

        # обработчик кнопок
        # Он должен идти ПЕРЕД обработчиком ссылок/любого текста
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex(
                f'^({VIDEO_BUTTON_TEXT}|{AUDIO_BUTTON_TEXT}|{CANCEL_BUTTON_TEXT})$'
            ),
            handle_button_press
        ))

        # Обработчик ссылок (и любого другого текста, не являющегося кнопкой или командой)
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))

        # Обработчик для неизвестных команд
        app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

        # Запуск бота
        try:
            await app.initialize()
            await app.start()
            await app.updater.start_polling()
            logger.info("Bot ready for work")

            # Ожидание завершения (например, по Ctrl+C)
            stop_event = asyncio.Event()
            await stop_event.wait()

        finally:
            # Остановка
            logger.info("Shutdown sequence initiated...")

            if app.updater and app.updater.running:
                 await app.updater.stop()
                 logger.info("Updater stopped.")

            if app.running:
                 await app.bot.shutdown()
                 logger.info("Application stopped.")

            # Отмена воркера
            if worker_task and not worker_task.done():
                logger.info("Cancelling worker task...")
                worker_task.cancel()
                try:
                    await asyncio.wait_for(worker_task, timeout=5.0)
                    logger.info("Worker task successfully cancelled.")
                except asyncio.CancelledError:
                    logger.info("Worker task already cancelled.")
                except asyncio.TimeoutError:
                    logger.warning("Worker task did not finish within timeout during cancellation.")
                except Exception as e:
                    logger.error(f"Error during worker task cancellation: {e}", exc_info=True)

            logger.info("Shutdown complete.")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user (KeyboardInterrupt).")
    except Exception as e:
        logger.critical(f"Application failed to run: {e}", exc_info=True)
