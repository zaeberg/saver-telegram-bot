import asyncio
import os
from typing import Tuple, Optional, Union
from telegram.ext import Application
from utils.logger import logger, request_context
from utils.get_video_info import get_video_info
from utils.downloader_base import DownloadError
from utils.downloader_youtube import YouTubeDownloader
from utils.downloader_twitter import TwitterDownloader
from utils.downloader_instagram import InstagramDownloader
from utils.constants import (
    UNAVAILABLE_REELS,
    NOT_IMPLEMENTED_MESSAGE,
    DOWNLOAD_ERROR_MESSAGE,
    TECHNICAL_ERROR_MESSAGE,
    FILE_TOO_LARGE_MESSAGE
)

# Инициализация downloader'ов
youtube_downloader = YouTubeDownloader()
twitter_downloader = TwitterDownloader()
instagram_downloader = InstagramDownloader()

# Воркер для обработки очереди
# Обрабатывает задачи из очереди бота
async def download_worker(application: Application, queue: asyncio.Queue):
    loop = asyncio.get_running_loop()
    logger.info("Download worker started")

    while True:
        job = None
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
                title = "Untitled"

                try:
                    # Получаем правильный downloader для платформы
                    downloader = _select_downloader(platform)
                    if not downloader:
                        logger.warning(f"Unsupported platform: {platform}")
                        await application.bot.send_message(chat_id=chat_id, text=NOT_IMPLEMENTED_MESSAGE.format(platform))
                        queue.task_done()
                        continue

                    # Скачивание
                    filepath, title = await _download_media(downloader, url, command_type, request_id)
                    if not filepath or not title:
                        logger.warning(f"Unsupported command: {command_type}")
                        await application.bot.send_message(chat_id=chat_id, text=TECHNICAL_ERROR_MESSAGE)
                        queue.task_done()
                        continue

                    # Проверка на существование файла
                    exists = await loop.run_in_executor(None, os.path.exists, filepath)
                    if not exists:
                        raise DownloadError("Downloaded file not found")

                    # Отправляет файл клиенту
                    await _send_media(
                        application,
                        loop,
                        chat_id,
                        command_type,
                        platform,
                        filepath,
                        title,
                        request_id
                    )

                except DownloadError as e:
                    await _handle_download_error(e, application, url, chat_id)

                except Exception as e:
                    logger.error(f"Unexpected error processing job for {url} in chat {chat_id}: {e}", exc_info=True)
                    try:
                        await application.bot.send_message(chat_id=chat_id, text=TECHNICAL_ERROR_MESSAGE)
                    except Exception as send_err:
                        logger.error(f"Failed to send error message to chat {chat_id}: {send_err}")

                finally:
                    # Очистка директории temp от файла
                    await _cleanup(filepath, loop)
                    # Сообщаем воркееру что задача обработана
                    worker_job_done(job, request_id, queue)

        except asyncio.CancelledError:
            logger.info("Download worker task cancelled.")
            break

        except Exception as e:
            logger.critical(f"Critical error IN download worker MAIN loop: {e}", exc_info=True)
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

# Выбирает подходящий downloader для заданной платформы
def _select_downloader(
    platform: str
) -> Union[YouTubeDownloader, TwitterDownloader, InstagramDownloader, None]:
    if platform == 'YouTube':
        return youtube_downloader
    elif platform == 'Twitter':
        return twitter_downloader
    elif platform == 'Instagram':
        return instagram_downloader
    else:
        return None

# Загружает медиафайл видео или аудио с помощью downloader'a
async def _download_media(
    downloader: Union[YouTubeDownloader, TwitterDownloader, InstagramDownloader],
    url: str,
    command_type: str,
    request_id: str
) -> Tuple[Optional[str], Optional[str]]:
    if command_type == "video":
        filepath, title = await downloader.download_video(url, request_id=request_id)
        return filepath, title
    elif command_type == "audio":
        filepath, title = await downloader.download_audio(url, request_id=request_id)
        return filepath, title
    else:
       return None, None

# Четние и отправка медиа в чат с клиентом
async def _send_media(
    application: Application,
    loop: asyncio.AbstractEventLoop,
    chat_id: int,
    command_type: str,
    platform: str,
    filepath: str,
    title: str,
    request_id: str
):
    logger.info(f"Sending {command_type} from {platform} to chat {chat_id}")
    if command_type == "video":
        # Получаем размеры видео
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

# Обработка ошибок возникших при загрузке
async def _handle_download_error(
    e: DownloadError,
    application: Application,
    url: str,
    chat_id: int
):
    error_message_text = str(e)
    reply_text = DOWNLOAD_ERROR_MESSAGE

    # Проверяем специфичную ошибку инсты
    if "requires Instagram login" in error_message_text:
        reply_text = UNAVAILABLE_REELS
    # Проверяем ошибку размера
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

# Очистка временных файлов
async def _cleanup(filepath: Optional[str], loop: asyncio.AbstractEventLoop):
    if filepath:
        try:
            exists = await loop.run_in_executor(None, os.path.exists, filepath)
            if exists: await loop.run_in_executor(None, os.remove, filepath)
        except Exception as e:
            logger.error(f"Error removing temporary file {filepath}: {e}")

# Говорим воркеру что задача завершена
def worker_job_done(job: Optional[asyncio.Task], request_id: str, queue: asyncio.Queue):
    if job:
        queue.task_done()
        logger.info(f"[{request_id}] Job task done.")
    else:
        logger.warning("Job was None in finally block, task_done() not called.")
