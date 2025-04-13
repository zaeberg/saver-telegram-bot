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
    FILE_TOO_LARGE_MESSAGE
)
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from utils.downloader_base import DownloadError
from utils.downloader_youtube import YouTubeDownloader
from utils.downloader_twitter import TwitterDownloader
from utils.downloader_instagram import InstagramDownloader

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
        try:
            job = await queue.get()

            chat_id = job['chat_id']
            url = job['url']
            command_type = job['type']
            platform = job['platform']
            request_id = job['request_id']

            with request_context(request_id):
                logger.info(f"Processing job: [{command_type}] for {url} from chat {chat_id}")

                filepath = None

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
                            if exists:
                                await loop.run_in_executor(None, os.remove, filepath)
                        except Exception as e:
                            logger.error(f"Error removing temporary file {filepath}: {e}")

                    # Сигнал воркееру что задача обработана
                    queue.task_done()

        except asyncio.CancelledError:
            logger.info("Download worker task cancelled.")
            break

        except Exception as e:
            logger.critical(f"Critical error IN download worker MAIN loop: {e}", exc_info=True)
            await asyncio.sleep(5)

# Принимает запрос, валидирует URL и ставит задачу в очередь
async def process_media_command(update: Update, context: ContextTypes.DEFAULT_TYPE, command_type: str):
    request_id = context.request_id
    user_id = update.effective_user.id
    username = update.effective_user.username or f"ID:{user_id}"
    chat_id = update.message.chat_id

    # Проверка на наличие аргументов, нужен 1 урл
    if not context.args or len(context.args) != 1:
        logger.warning(f"Missing URL in {command_type} command from user {username}")
        await update.message.reply_text(MISSING_URL_MESSAGE.format(f"/{command_type}"))
        return

    url = context.args[0]
    logger.info(f"Received {command_type} request for {url} from user {username}")

    # Валидация URL и платформы
    is_valid, error_message, platform = validate_url(url)
    if not is_valid:
        logger.warning(f"Invalid URL: {url} from user {username}. Reason: {error_message}")
        await update.message.reply_text(error_message)
        return

    if platform not in ['YouTube', 'Twitter', 'Instagram']:
        logger.warning(f"Unsupported platform: {platform} from URL: {url}")
        await update.message.reply_text(NOT_IMPLEMENTED_MESSAGE.format(platform))
        return

    # Получаем очередь из bot_data
    try:
        download_queue = context.bot_data['download_queue']
    except KeyError:
        logger.critical(f"[{request_id}] Download queue not found in bot_data")
        await update.message.reply_text(TECHNICAL_ERROR_MESSAGE)
        return

    # Сообщение пользователю о добавлении в очередь
    await update.message.reply_text(QUEUE_MESSAGE)

    # Создаем задачу для воркера
    job = {
        'chat_id': chat_id,
        'url': url,
        'type': command_type,
        'platform': platform,
        'request_id': request_id
    }

    # Помещаем задачу в очередь
    await download_queue.put(job)

async def video_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with request_context() as request_id:
        context.request_id = request_id
        await process_media_command(update, context, "video")

async def audio_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
   with request_context() as request_id:
       context.request_id = request_id
       await process_media_command(update, context, "audio")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_MESSAGE)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_MESSAGE)

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received unknown command: {update.message.text} from user {update.effective_user.username or update.effective_user.id}")
    await update.message.reply_text(UNKNOWN_COMMAND_MESSAGE)

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

        # Обработчики команд
        app.add_handler(CommandHandler('start', start))
        app.add_handler(CommandHandler('help', help_command))
        app.add_handler(CommandHandler('video', video_command))
        app.add_handler(CommandHandler('audio', audio_command))

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
