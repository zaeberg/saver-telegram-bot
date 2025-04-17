from typing import Union
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application
from utils.constants import (
    VIDEO_BUTTON_TEXT,
    AUDIO_BUTTON_TEXT,
    CANCEL_BUTTON_TEXT
)

# Создает разметку основной клавиатуры.
def get_main_keyboard_markup() -> ReplyKeyboardMarkup:
    keyboard = [[KeyboardButton(VIDEO_BUTTON_TEXT), KeyboardButton(AUDIO_BUTTON_TEXT)]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

# Создает разметку клавиатуры отмены
def get_cancel_keyboard_markup() -> ReplyKeyboardMarkup:
    keyboard = [[KeyboardButton(CANCEL_BUTTON_TEXT)]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

# Отправляет сообщение с основной клавиатурой
async def send_main_keyboard(app_or_update: Union[Application, Update], chat_id: int, text: str):
    markup = get_main_keyboard_markup()
    if isinstance(app_or_update, Application):
        await app_or_update.bot.send_message(chat_id, text, reply_markup=markup)
    else: # Update
        await app_or_update.message.reply_text(text, reply_markup=markup)

# Отправляет сообщение с клавиатурой отмены
async def send_cancel_keyboard(update: Update, text: str):
    markup = get_cancel_keyboard_markup()
    await update.message.reply_text(text, reply_markup=markup)
