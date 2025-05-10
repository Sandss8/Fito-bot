import logging
from telegram.ext import ApplicationBuilder
from config import Config
from handlers.start import StartHandler
from handlers.registration import RegistrationHandler
from handlers.food_tracking import FoodTrackingHandler
from handlers.error import ErrorHandler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def setup_handlers(app):
    """Регистрация всех обработчиков"""
    handlers = [
        StartHandler(),
        RegistrationHandler(),
        FoodTrackingHandler()
    ]

    for handler in handlers:
        for h in handler.get_handlers():
            app.add_handler(h)


def main():
    app = ApplicationBuilder().token(Config.TOKEN).build()

    # Настройка обработчиков
    setup_handlers(app)

    # Обработчик ошибок
    app.add_error_handler(ErrorHandler().handle)

    logger.info("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()
