import os
from contextlib import redirect_stdout, redirect_stderr
from config import TELEGRAM_TOKEN
from moviepy import VideoFileClip
from utils.validate_url import validate_url
from utils.logger import logger, request_context
from utils.downloader_youtube import (
    download_youtube_video,
    download_youtube_audio,
    DownloadError
)
from utils.constants import (
    HELP_MESSAGE,
    UNKNOWN_COMMAND_MESSAGE,
    MISSING_URL_MESSAGE,
    PROCESSING_START_MESSAGE,
    NOT_IMPLEMENTED_MESSAGE,
    DOWNLOAD_ERROR_MESSAGE,
    TECHNICAL_ERROR_MESSAGE,
    FILE_TOO_LARGE_MESSAGE
)
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

async def process_media_command(update: Update, context: ContextTypes.DEFAULT_TYPE, command_type: str):
    with request_context() as request_id:
        user_id = update.effective_user.id
        username = update.effective_user.username or "No username"

        logger.info(f"Received {command_type} command from user {username} (ID: {user_id})")

        if not context.args or len(context.args) != 1:
            logger.warning(f"Missing URL in {command_type} command from user {user_id}")
            await update.message.reply_text(MISSING_URL_MESSAGE.format(f"/{command_type}"))
            return

        url = context.args[0]
        logger.info(f"Processing URL: {url}")

        # Validate URL and get platform
        is_valid, error_message, platform = validate_url(url)
        if not is_valid:
            logger.warning(f"Invalid URL provided by user {user_id}: {url}")
            await update.message.reply_text(error_message)
            return

        # Сообщение пользователю о начале обработки
        logger.info(f"URL validation passed. Platform: {platform}")
        await update.message.reply_text(PROCESSING_START_MESSAGE)

        try:
            if platform == 'YouTube':
                try:
                    if command_type == "video":
                        filepath = await download_youtube_video(url, request_id=request_id)

                        # Проверяем, что файл существует
                        if not os.path.exists(filepath):
                            await update.message.reply_text(TECHNICAL_ERROR_MESSAGE)
                            return

                        # Проверяем, что файл имеет правильный размер
                        file_size = os.path.getsize(filepath)
                        if file_size > 45_000_000:  # 45MB
                            await update.message.reply_text(FILE_TOO_LARGE_MESSAGE)
                            return

                        # Отправляем видео
                        with redirect_stdout(None), redirect_stderr(None):  # Скрываем вывод ffmpeg
                            with VideoFileClip(filepath) as clip:
                                width = clip.w
                                height = clip.h
                                await update.message.reply_video(
                                    video=open(filepath, 'rb'),
                                    width=width,
                                    height=height,
                                    supports_streaming=True,
                                    filename=os.path.basename(filepath)
                                )
                                logger.info(f"Video {url} sent successfully to {username} (ID: {user_id})")

                    elif command_type == "audio":
                        filepath, title = await download_youtube_audio(url, request_id=request_id)

                        # Проверяем, что файл существует
                        if not os.path.exists(filepath):
                            await update.message.reply_text(TECHNICAL_ERROR_MESSAGE)
                            return

                        # Проверяем, что файл имеет правильный размер
                        file_size = os.path.getsize(filepath)
                        if file_size > 45_000_000:  # 45MB
                            await update.message.reply_text(FILE_TOO_LARGE_MESSAGE)
                            return

                        # Отправляем аудио файл
                        await update.message.reply_audio(
                            audio=open(filepath, 'rb'),
                            title=title,
                            filename=os.path.basename(filepath),
                            performer="from YouTube via Saver"
                        )
                        logger.info(f"Audio {url} sent successfully to {username} (ID: {user_id})")

                except DownloadError as e:
                    logger.error(f"Download error for {url}: {str(e)}")
                    error_message = str(e)

                    if "too large" in error_message.lower():
                        await update.message.reply_text(FILE_TOO_LARGE_MESSAGE)
                    else:
                        await update.message.reply_text(DOWNLOAD_ERROR_MESSAGE)
                    logger.error(f"Download error: {e}")

                except Exception as e:
                    logger.error(f"Error processing video: {e}")
                    await update.message.reply_text(TECHNICAL_ERROR_MESSAGE)

                finally:
                    if 'filepath' in locals() and os.path.exists(filepath):
                        try:
                            os.remove(filepath)
                            logger.debug(f"Temporary file removed: {filepath}")
                        except Exception as e:
                            logger.error(f"Error removing temporary file {filepath}: {e}")
            else:
                logger.info(f"Platform {platform} not implemented yet")
                await update.message.reply_text(NOT_IMPLEMENTED_MESSAGE.format(platform))

        except Exception as e:
            logger.error(f"Unexpected error processing {command_type} command: {str(e)}", exc_info=True)
            await update.message.reply_text(TECHNICAL_ERROR_MESSAGE)

        logger.info(f"Request completed for user {user_id}")


async def video_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await process_media_command(update, context, "video")

async def audio_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await process_media_command(update, context, "audio")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_MESSAGE)

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_MESSAGE)

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(UNKNOWN_COMMAND_MESSAGE)

def main():
    with request_context('MAIN'):
        # Создание приложения
        logger.info('Starting bot')
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

        # Обработчики команд
        app.add_handler(CommandHandler('start', start))
        app.add_handler(CommandHandler('help', help))
        app.add_handler(CommandHandler('video', video_command))
        app.add_handler(CommandHandler('audio', audio_command))

        # Обработчик сообщений для неизвестных команд
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, unknown_command))

        # Запуск бота
        logger.info('Bot initialized, starting polling')
        app.run_polling()

if __name__ == '__main__':
    main()
