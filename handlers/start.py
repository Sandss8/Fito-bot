from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from config import Config
from handlers.base import BaseHandler


class StartHandler(BaseHandler):
    def __init__(self):
        super().__init__()
        self.command_handlers = [("start", self.start), ("profile", self.start)]

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_name = update.message.chat.first_name
        reply_keyboard = [["Регистрация", "Подсчёт ккал блюда"]]

        await update.message.reply_text(
            f"Привет, {user_name}! Выбери действие:",
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard,
                one_time_keyboard=True,
                resize_keyboard=True
            )
        )
        return Config.CHOOSE_ACTION
