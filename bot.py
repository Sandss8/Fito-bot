# bot.py

import os
import logging
from datetime import datetime
import urllib.parse
import requests
from dotenv import load_dotenv
from telegram import (
    Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, ConversationHandler
)

from database import Database

# ============ Настройка логирования ============
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============ Загрузка переменных окружения ============
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
FATSECRET_CLIENT_ID = os.getenv("FATSECRET_CLIENT_ID")
FATSECRET_CLIENT_SECRET = os.getenv("FATSECRET_CLIENT_SECRET")

# ============ Константы для состояний ============
(START, GENDER, AGE, HEIGHT, WEIGHT, ACTIVITY_LEVEL,
 CHOOSE_ACTION, ENTER_DISH_NAME, ENTER_WEIGHT,
 ADD_DISH, DISH_SOURCE,
 CUSTOM_NAME, CUSTOM_VOLUME_CHECK, CUSTOM_INGREDIENTS_WEIGHT, CUSTOM_INGREDIENTS_LIST, CUSTOM_RECIPE,
 STORE_NAME, STORE_CALORIES
 ) = range(18)

ACTIVITY_LEVELS = [
    "1. Малоподвижный образ жизни",
    "2. Лёгкие физические нагрузки, прогулки",
    "3. Тренировки 4-5 раз в неделю",
    "4. Физическая активность 5-6 раз в неделю",
    "5. Высокая активность 6-7 раз в неделю",
    "6. Профессиональный спорт (2+ тренировки в день)"
]
ACTIVITY_FACTORS = {level: factor for level, factor in zip(ACTIVITY_LEVELS, [1.2, 1.375, 1.55, 1.725, 1.9, 2.1])}


# ============ Класс для работы с OpenFoodFacts API ============
class OpenFoodFactsAPI:
    SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl"

    def search_food(self, query: str) -> dict:
        params = {"search_terms": query, "search_simple": 1,
                  "action": "process", "json": 1, "page_size": 5}
        resp = requests.get(self.SEARCH_URL, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json().get("products", [])
        if not data:
            raise ValueError("Не найдено продуктов")
        return data[0]  # берём первый продукт


# ============ Калькулятор BMR и калорий ============
class CalorieCalculator:
    @staticmethod
    def bmr(g, w, h, a):
        return 10 * w + 6.25 * h - 5 * a + (5 if g == "М" else -161)

    @staticmethod
    def daily_calories(bmr, alvl):
        return bmr * ACTIVITY_FACTORS[f'{alvl}']


# ============ Сессия пользователя ============
class UserSession:
    def __init__(self):
        self.data: dict = {}

    def clear(self):
        self.data.clear()


# ============ Основной контроллер бота ============
class BotController:
    def __init__(self):
        self.reply_keyboard = None
        self.db = Database()
        self.api = OpenFoodFactsAPI()
        self.calc = CalorieCalculator()
        self.sessions: dict[int, UserSession] = {}

    def _get_session(self, user_id: int) -> UserSession:
        if user_id not in self.sessions:
            self.sessions[user_id] = UserSession()
        return self.sessions[user_id]

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_name = update.effective_user.first_name
        reg_done = context.user_data.get('registration_complete', False)

        if reg_done:
            keyboard = [["Профиль", "Добавить блюдо"],
                        ["Подсчёт ккал блюда"]]
            hello_text = ''
        else:
            keyboard = [["Регистрация", "Подсчёт ккал блюда"]]
            hello_text = f'Привет, {user_name}! '
        await update.message.reply_text(
            f"{hello_text}Что ты хочешь сделать?",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        )
        return CHOOSE_ACTION

    async def choose_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        sess = self._get_session(update.effective_user.id)
        reg_done = context.user_data.get('registration_complete', False)
        if str(text) == "Регистрация" and not reg_done:
            sess.clear()
            await update.message.reply_text(
                f"Чтобы помочь тебе, мне надо задать пару вопросов.\n"
                f"Пример ответа будет отображаться вот так: |Пример|"
            )
            reply_keyboard_gen = [["М", "Ж"]]
            await update.message.reply_text("Укажите ваш биологический пол:",
                                            reply_markup=ReplyKeyboardMarkup(reply_keyboard_gen,
                                                                             one_time_keyboard=True))
            return GENDER
        elif str(text) == "Подсчёт ккал блюда":
            await update.message.reply_text("Какое блюдо вы ели или готовите? Опишите кратко.")
            return ENTER_DISH_NAME
        elif str(text) == "Профиль":
            if not reg_done:
                await update.message.reply_text(
                    "Вы ещё не зарегистрированы. Пожалуйста, зарегистрируйтесь.",
                    reply_markup=ReplyKeyboardMarkup([["Регистрация"]], one_time_keyboard=True)
                )
                return CHOOSE_ACTION

            # вывод данных профиля
            data = self.db.get_user_data(update.effective_user.id)
            text = (
                f"👤 Ваш профиль:\n"
                f"• Пол: {data['gender']}\n"
                f"• Возраст: {data['age']}\n"
                f"• Рост: {data['height']} см\n"
                f"• Вес: {data['weight']} кг\n"
                f"• Активность: {data['activity_level'][2:]}\n"
                f"• BMR: {data['bmr']:.0f} ккал\n"
                f"• Норма: {data['daily_calories']:.0f} ккал\n"
                f"• Зарегистрирован: {data['registration_date']}"
            )
            await update.message.reply_text(text)
            return CHOOSE_ACTION
        else:
            await update.message.reply_text("Пожалуйста, используйте кнопки ниже:")
            return START

    # --- Регистрационные хендлеры ---
    async def gender(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        gender = update.message.text.upper()
        if str(gender) not in ['М', 'Ж']:
            await update.message.reply_text(
                "Пожалуйста, выберите пол, используя кнопки ниже:",
                reply_markup=ReplyKeyboardMarkup([["М", "Ж"]], one_time_keyboard=True)
            )
            return GENDER
        self._get_session(update.effective_user.id).data["gender"] = gender
        await update.message.reply_text("Введите ваш возраст (полных лет):\n| 25 |")
        return AGE  # Переводим бота в состояние ожидания возраста

    async def age(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            age = int(update.message.text)
            if not 10 <= age <= 120:
                raise ValueError
            self._get_session(update.effective_user.id).data["age"] = age

            await update.message.reply_text('Введите ваш рост в см \n| 175 |')
            return HEIGHT  # Переводим бота в состояние ожидания роста
        except ValueError:
            await update.message.reply_text("Пожалуйста, введите корректное, целое число \n| 20 | (10-120)")
            return AGE  # Остаемся в состоянии возраста

    async def height(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            height = int(update.message.text)
            if not 100 <= height <= 250:
                raise ValueError
            self._get_session(update.effective_user.id).data["height"] = height  # Сохраняем рост

            await update.message.reply_text("Введите ваш вес в кг \n| 50 | 50,5 | 50.55 |")
            return WEIGHT  # Переводим бота в состояние ожидания веса

        except ValueError:
            await update.message.reply_text("Пожалуйста, введите корректное, целое число  \n| 150 | (100-250)")
            return HEIGHT  # Остаемся в состоянии роста

    async def weight(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            weight = float(update.message.text.replace(",", "."))
            if not 30 <= weight <= 300:
                raise ValueError
            self._get_session(update.effective_user.id).data["weight"] = weight  # Сохраняем вес

            # Создаем клавиатуру с уровнями активности
            reply_keyboard = [
                [ACTIVITY_LEVELS[0]],  # Первый уровень - отдельная строка
                [ACTIVITY_LEVELS[1], ACTIVITY_LEVELS[2]],  # Вторая строка - 2 кнопки
                [ACTIVITY_LEVELS[3], ACTIVITY_LEVELS[4]],  # Третья строка - 2 кнопки
                [ACTIVITY_LEVELS[5]]  # Последний уровень - отдельная строка
            ]

            await update.message.reply_text(
                "Выберите уровень физической активности:",
                reply_markup=ReplyKeyboardMarkup(
                    reply_keyboard,
                    one_time_keyboard=True,  # Клавиатура скроется после выбора
                    resize_keyboard=True  # Кнопки подстроятся под размер
                )
            )
            return ACTIVITY_LEVEL

        except ValueError:
            await update.message.reply_text("Пожалуйста, введите корректный вес \n| 70 | 70,5 | 70.55 | (30-300)")
            return WEIGHT  # Остаемся в состоянии веса

    async def activity_level(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        sess = self._get_session(user_id)

        activity = update.message.text
        if activity not in ACTIVITY_LEVELS and int(activity[0]) not in range(1, 7):
            reply_keyboard = [
                [ACTIVITY_LEVELS[0]],
                [ACTIVITY_LEVELS[1], ACTIVITY_LEVELS[2]],
                [ACTIVITY_LEVELS[3], ACTIVITY_LEVELS[4]],
                [ACTIVITY_LEVELS[5]]
            ]
            await update.message.reply_text(
                "Пожалуйста, выберите уровень активности из предложенных:",
                reply_markup=ReplyKeyboardMarkup(
                    reply_keyboard,
                    one_time_keyboard=True,
                    resize_keyboard=True
                )
            )
            return ACTIVITY_LEVEL

        if activity.isdigit():
            activity = ACTIVITY_LEVELS[int(activity) - 1]
        self._get_session(update.effective_user.id).data["activity_level"] = activity  # Сохраняем активность

        # меню после регистрации
        await update.message.reply_text(
            "✅ Регистрация завершена!",
            reply_markup=ReplyKeyboardRemove()
        )
        context.user_data['registration_complete'] = True

        # считаем
        bmr_val = self.calc.bmr(
            sess.data["gender"], sess.data["weight"], sess.data["height"], sess.data["age"]
        )
        dc = self.calc.daily_calories(bmr_val, activity)
        await update.message.reply_text(
            "📊 Результаты расчета:\n\n"
            f"🔹 Основной обмен: {bmr_val:.0f} ккал/день\n"
            f"🔹 С учетом активности: {dc:.0f} ккал/день\n\n"
            "Это примерная норма для поддержания текущего веса."
        )

        # сохраняем в бд
        user_data = {
            "user_id": user_id,
            "username": update.effective_user.username,
            "first_name": update.effective_user.first_name,
            "last_name": update.effective_user.last_name,
            **sess.data,
            "bmr": bmr_val,
            "daily_calories": dc,
            "registration_date": datetime.now().isoformat(sep=" ", timespec="seconds")
        }
        self.db.save_user_data(user_data)
        return await self.start(update, context)

    # --- Подсчёт калорий в блюде ---
    async def enter_dish_name(self, upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
        query = upd.message.text
        sess = self._get_session(upd.effective_user.id)

        try:
            product = self.api.search_food(query)
        except Exception as e:
            logger.error("OFF API error: %s", e)
            await upd.message.reply_text("Сервис OpenFoodFacts временно недоступен или ничего не найдено.")
            return CHOOSE_ACTION

        sess.data["food_name"] = product.get("product_name", "—")
        nutr = product.get("nutriments", {})

        # нутриенты на 100 г
        sess.data["kcal_100g"] = nutr.get("energy-kcal_100g", 0)
        sess.data["prot_100g"] = nutr.get("proteins_100g", 0)
        sess.data["fat_100g"] = nutr.get("fat_100g", 0)
        sess.data["carb_100g"] = nutr.get("carbohydrates_100g", 0)

        await upd.message.reply_text(
            f"🔍 Нашёл: {sess.data['food_name']}\n"
            f"Калорийность: {sess.data['kcal_100g']:.0f} ккал/100 г\n"
            f"Белки: {sess.data['prot_100g']:.1f} г, "
            f"Жиры: {sess.data['fat_100g']:.1f} г, "
            f"Угл.: {sess.data['carb_100g']:.1f} г\n\n"
            "Введите вес в граммах для расчёта:"
        )
        return ENTER_WEIGHT

    async def enter_weight(self, upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
        text = upd.message.text.replace(",", ".")
        sess = self._get_session(upd.effective_user.id)

        try:
            grams = float(text)
        except ValueError:
            await upd.message.reply_text("Пожалуйста, введите число в граммах.")
            return ENTER_WEIGHT

        # считаем пропорцию
        kcal = sess.data["kcal_100g"] * grams / 100
        prot = sess.data["prot_100g"] * grams / 100
        fat = sess.data["fat_100g"] * grams / 100
        carb = sess.data["carb_100g"] * grams / 100

        await upd.message.reply_text(
            f"{grams:.0f} г ≈ {kcal:.0f} ккал\n"
            f"Белки: {prot:.1f} г, Жиры: {fat:.1f} г, Угл.: {carb:.1f} г"
        )

        # сохраняем приём пищи
        meal = {
            "food_name": sess.data["food_name"],
            "calories": kcal,
            "protein": prot,
            "fat": fat,
            "carbs": carb,
            "weight": grams
        }
        self.db.save_meal(upd.effective_user.id, meal)

        kb = [[KeyboardButton("Подсчёт ккал блюда")]]
        await upd.message.reply_text("Готово!", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
        return CHOOSE_ACTION

    async def error(self, update: Update | None, context: ContextTypes.DEFAULT_TYPE):
        # Логируем полную трассировку
        logger.error("Uncaught exception", exc_info=context.error)

        # Если update есть и у него есть message — отвечаем пользователю
        if update is not None and getattr(update, "message", None):
            try:
                await update.message.reply_text(
                    "❌ Произошла непредвиденная ошибка. Пожалуйста, попробуйте позже."
                )
            except Exception as send_exc:
                # Даже если не удалось отправить текст — просто логируем
                logger.error("Failed to send error message to user: %s", send_exc)

    def run(self):
        app = ApplicationBuilder().token(TOKEN).build()

        conv = ConversationHandler(
            entry_points=[CommandHandler("start", self.start)],
            states={
                START: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.start)],
                CHOOSE_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.choose_action)],
                GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.gender)],
                AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.age)],
                HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.height)],
                WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.weight)],
                ACTIVITY_LEVEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.activity_level)],
                ENTER_DISH_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.enter_dish_name)],
                ENTER_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.enter_weight)],
            },
            fallbacks=[]
        )

        async def reset(_):
            await app.bot.delete_webhook(drop_pending_updates=True)

        app.post_init = reset

        app.add_handler(conv)
        app.add_error_handler(self.error)
        print("Бот запущен")
        app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    BotController().run()
