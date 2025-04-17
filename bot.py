import asyncio
from telegram.ext import Application, ApplicationBuilder, CommandHandler, MessageHandler, filters
from config import TELEGRAM_TOKEN
from utils.logger import logger, request_context
from core.worker import download_worker
from handlers.common import start_command, help_command, unknown_command
from handlers.conversation import get_conversation_handler, cancel_conversation

async def post_init(application: Application):
    """Выполняется после инициализации приложения, до старта поллинга."""
    # Можно выполнить какие-то проверки или настройки здесь
    logger.info("Bot application initialized.")

async def main():
    with request_context('MAIN'):
        logger.info('Starting bot')

        # Создание очереди
        download_queue = asyncio.Queue()

        # Собираем приложение
        app_builder = ApplicationBuilder().token(TELEGRAM_TOKEN)
        app_builder.post_init(post_init)
        app = app_builder.build()

        # Сохраняем очередь в bot_data для доступа из обработчиков
        app.bot_data['download_queue'] = download_queue

        # Запуск воркера
        worker_task = asyncio.create_task(download_worker(app, download_queue)) # Передаем app

        # Регистрация обработчиков (порядок важен)
        # 1. ConversationHandler для основного диалога
        conv_handler = get_conversation_handler()
        app.add_handler(conv_handler)

        # 2. Отдельная команда /cancel
        app.add_handler(CommandHandler('cancel', cancel_conversation))

        # 3. Простые команды ConversationHandler перехватит диалог
        app.add_handler(CommandHandler('start', start_command))
        app.add_handler(CommandHandler('help', help_command))

        # 4. Обработчик неизвестных команд (должен идти после всех простых CommandHandlers)
        app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

        # Запуск бота
        try:
            await app.initialize()
            await app.start()
            logger.info("Bot polling started")
            await app.updater.start_polling()

            # Ожидание завершения (например, по Ctrl+C)
            await asyncio.Event().wait()

        except (KeyboardInterrupt, SystemExit):
                logger.info("Shutdown requested by signal.")
        except Exception as e:
                logger.critical(f"Critical error during bot execution: {e}", exc_info=True)
        finally:
            # Остановка
            logger.info("Shutdown sequence initiated...")
            if app.updater and app.updater.running:
                await app.updater.stop()
                logger.info("Updater stopped.")
            if app.running:
                await app.stop()
                logger.info("Application shut down.")

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
    except Exception as e:
        # Логгер может быть еще не инициализирован, используем print
        print(f"FATAL: Application failed to run: {e}")
        import traceback
        traceback.print_exc()
