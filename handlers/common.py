from telegram import Update
from telegram.ext import ContextTypes
from utils.logger import logger
from ui.keyboards import send_main_keyboard
from utils.constants import (
    HELP_MESSAGE,
    UNKNOWN_COMMAND_MESSAGE
)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop('next_action', None) # Сбрасываем состояние
    await send_main_keyboard(update, update.message.chat_id, HELP_MESSAGE)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop('next_action', None)
    await send_main_keyboard(update, update.message.chat_id, HELP_MESSAGE)

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Не проверяем state, так как handle_link должен был обработать ссылку
    logger.info(f"Unknown command: {update.message.text} from {update.effective_user.id}")
    await send_main_keyboard(update, update.message.chat_id, UNKNOWN_COMMAND_MESSAGE)
