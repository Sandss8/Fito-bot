from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler


class BaseHandler:
    def __init__(self):
        self.command_handlers = []
        self.message_handlers = []

    def get_handlers(self):
        """Возвращает список обработчиков"""
        handlers = []
        for command, callback in self.command_handlers:
            handlers.append(CommandHandler(command, callback))
        for filter_, callback in self.message_handlers:
            handlers.append(MessageHandler(filter_, callback))
        return handlers

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Основной метод обработки"""
        raise NotImplementedError
