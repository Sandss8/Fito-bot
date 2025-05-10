import logging
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


class ErrorHandler:
    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Логирует ошибку и уведомляет пользователя"""
        error = context.error

        # Логируем полную трассировку ошибки
        logger.error(
            "Exception while handling an update:",
            exc_info=error
        )

        # Формируем понятное сообщение для пользователя
        user_message = (
            "⚠️ Произошла непредвиденная ошибка. "
            "Попробуйте повторить действие позже.\n"
            "Администратор уже уведомлен о проблеме."
        )

        # Отправляем сообщение, если возможно
        if update and update.message:
            try:
                await update.message.reply_text(user_message)
            except Exception as e:
                logger.error(f"Failed to send error message: {e}")
