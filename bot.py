import os
import logging
from database import Database
from datetime import datetime
import requests
from dotenv import load_dotenv
from telegram import (
    Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, ConversationHandler
)

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
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")  # Ключ для Yandex Cloud API
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")  # ID каталога в Yandex Cloud

# ============ Константы для состояний ============
GENDER, AGE, HEIGHT, WEIGHT, ACTIVITY_LEVEL = range(5)
START, CHOOSE_ACTION, ENTER_DISH_NAME, ENTER_WEIGHT, CHAT_WITH_AI = range(5, 10)

ACTIVITY_LEVELS = [
    "1. Малоподвижный образ жизни",
    "2. Лёгкие физические нагрузки, прогулки",
    "3. Тренировки 4-5 раз в неделю",
    "4. Физическая активность 5-6 раз в неделю",
    "5. Высокая активность 6-7 раз в неделю",
    "6. Профессиональный спорт (2+ тренировки в день)"
]
ACTIVITY_FACTORS = {
    ACTIVITY_LEVELS[0]: 1.2,
    ACTIVITY_LEVELS[1]: 1.375,
    ACTIVITY_LEVELS[2]: 1.55,
    ACTIVITY_LEVELS[3]: 1.725,
    ACTIVITY_LEVELS[4]: 1.9,
    ACTIVITY_LEVELS[5]: 2.1
}


# ============ Класс для работы с DeepSeek API ============
class YandexGPTAPI:
    API_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

    def __init__(self, api_key: str, folder_id: str):
        self.api_key = api_key
        self.folder_id = folder_id

    async def get_response(self, message: str) -> str:
        """Получение ответа от YandexGPT API"""
        try:
            headers = {
                "Authorization": f"Api-Key {self.api_key}",
                "Content-Type": "application/json",
            }

            data = {
                "modelUri": f"gpt://{self.folder_id}/yandexgpt-lite",
                "completionOptions": {
                    "stream": False,
                    "temperature": 0.7,
                    "maxTokens": 2000
                },
                "messages": [
                    {
                        "role": "system",
                        "text": "Ты - полезный ассистент в телеграм-боте."
                    },
                    {
                        "role": "user",
                        "text": message
                    }
                ]
            }

            response = requests.post(self.API_URL, headers=headers, json=data, timeout=30)
            response.raise_for_status()

            result = response.json()
            return result['result']['alternatives'][0]['message']['text']

        except Exception as e:
            logger.error(f"YandexGPT API error: {e}")
            return "Извините, произошла ошибка при обработке вашего запроса."


# ============ Класс для работы с FatSecret API ============
class FatSecretAPI:
    TOKEN_URL = "https://oauth.fatsecret.com/connect/token"
    BASE_URL = "https://platform.fatsecret.com/rest/server.api"

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: str = ""

    def _refresh_token(self):
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "client_credentials",
            "scope": "basic",
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        resp = requests.post(self.TOKEN_URL, headers=headers, data=data)
        resp.raise_for_status()
        payload = resp.json()
        if "access_token" not in payload:
            logger.error("FatSecret: no access_token in response %s", payload)
            raise RuntimeError("FatSecret token error")
        self._token = payload["access_token"]

    def search_food(self, query: str) -> dict:
        if not self._token:
            self._refresh_token()
        params = {
            "method": "foods.search",
            "search_expression": query,
            "format": "json"
        }
        headers = {"Authorization": f"Bearer {self._token}"}
        resp = requests.get(self.BASE_URL, params=params, headers=headers)
        resp.raise_for_status()
        return resp.json()


# ============ Калькулятор BMR и калорий ============
class CalorieCalculator:
    @staticmethod
    def bmr(gender: str, weight: float, height: float, age: int) -> float:
        return 10 * weight + 6.25 * height - 5 * age + (5 if gender == "М" else -161)

    @staticmethod
    def daily_calories(bmr_value: float, activity_level):
        factor = ACTIVITY_FACTORS[f'{activity_level}']
        return bmr_value * factor


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
        self.fatsecret_api = FatSecretAPI(FATSECRET_CLIENT_ID, FATSECRET_CLIENT_SECRET)
        self.yandex_gpt = YandexGPTAPI(YANDEX_API_KEY, YANDEX_FOLDER_ID)
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
            keyboard = [["Профиль", "Подсчёт ккал блюда"],
                        ["AI подсчёт ккал"]]
            hello_text = ''
        else:
            keyboard = [["Регистрация", "Подсчёт ккал блюда"],
                        ["AI подсчёт ккал"]]
            hello_text = f'Привет, {user_name}! '
        await update.message.reply_text(
            f"{hello_text}Что ты хочешь сделать?",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return CHOOSE_ACTION

    async def choose_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        sess = self._get_session(update.effective_user.id)
        reg_done = context.user_data.get('registration_complete', False)

        if text == "Регистрация" and not reg_done:
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

        elif text == "Подсчёт ккал блюда":
            # await update.message.reply_text("Какое блюдо вы ели или готовите? Опишите кратко.")
            # return ENTER_DISH_NAME
            await update.message.reply_text("Сервис в разработке...")
            return CHOOSE_ACTION

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

        elif text == "AI подсчёт ккал":
            await update.message.reply_text("Вы перешли в режим чата с AI. Задайте ваш вопрос:\n\n",
                                            reply_markup=ReplyKeyboardRemove())
            await update.message.reply_text("Чтобы выйти из этого режима, отправьте /cancel или нажмите на кнопку",
                                            reply_markup=ReplyKeyboardMarkup([["/cancel"]], one_time_keyboard=True,
                                                                             resize_keyboard=True))
            return CHAT_WITH_AI

        else:
            await update.message.reply_text("Пожалуйста, используйте кнопки ниже:")
            return START

    async def gender(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        gender = update.message.text.upper()
        if gender not in ['М', 'Ж']:
            await update.message.reply_text(
                "Пожалуйста, выберите пол, используя кнопки ниже:",
                reply_markup=ReplyKeyboardMarkup([["М", "Ж"]], one_time_keyboard=True)
            )
            return GENDER
        self._get_session(update.effective_user.id).data["gender"] = gender
        await update.message.reply_text("Введите ваш возраст (полных лет):\n| 25 |")
        return AGE

    async def age(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            age = int(update.message.text)
            if not 10 <= age <= 120:
                raise ValueError
            self._get_session(update.effective_user.id).data["age"] = age
            await update.message.reply_text('Введите ваш рост в см \n| 175 |')
            return HEIGHT
        except ValueError:
            await update.message.reply_text("Пожалуйста, введите корректное, целое число \n| 20 | (10-120)")
            return AGE

    async def height(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            height = int(update.message.text)
            if not 100 <= height <= 250:
                raise ValueError
            self._get_session(update.effective_user.id).data["height"] = height
            await update.message.reply_text("Введите ваш вес в кг \n| 50 | 50,5 | 50.55 |")
            return WEIGHT
        except ValueError:
            await update.message.reply_text("Пожалуйста, введите корректное, целое число  \n| 150 | (100-250)")
            return HEIGHT

    async def weight(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            weight = float(update.message.text.replace(",", "."))
            if not 30 <= weight <= 300:
                raise ValueError
            self._get_session(update.effective_user.id).data["weight"] = weight

            reply_keyboard = [
                [ACTIVITY_LEVELS[0]],
                [ACTIVITY_LEVELS[1], ACTIVITY_LEVELS[2]],
                [ACTIVITY_LEVELS[3], ACTIVITY_LEVELS[4]],
                [ACTIVITY_LEVELS[5]]
            ]

            await update.message.reply_text(
                "Выберите уровень физической активности:",
                reply_markup=ReplyKeyboardMarkup(
                    reply_keyboard,
                    one_time_keyboard=True,
                    resize_keyboard=True
                )
            )
            return ACTIVITY_LEVEL
        except ValueError:
            await update.message.reply_text("Пожалуйста, введите корректный вес \n| 70 | 70,5 | 70.55 | (30-300)")
            return WEIGHT

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

        await update.message.reply_text(
            "✅ Регистрация завершена!",
            reply_markup=ReplyKeyboardRemove()
        )
        context.user_data['registration_complete'] = True

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

    async def enter_dish_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.message.text
        sess = self._get_session(update.effective_user.id)
        sess.data["dish_query"] = query

        try:
            result = self.fatsecret_api.search_food(query)
            foods = result.get("foods", {}).get("food", [])
            if not foods:
                raise ValueError("не найдено")
            food = foods[0]
            sess.data["food"] = food
            await update.message.reply_text(
                f"Нашёл: {food['food_name']}\nОписание: {food.get('food_description', '-')}\nВведите граммы:"
            )
            return ENTER_WEIGHT
        except Exception:
            await update.message.reply_text("Ошибка поиска, попробуйте позже")
            return START

    async def enter_weight(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        grams = float(update.message.text.replace(",", "."))
        sess = self._get_session(update.effective_user.id)
        food = sess.data.get("food", {})
        desc = food.get("food_description", "")
        if "Calories:" not in desc:
            return await update.message.reply_text("Нет данных о калориях")
        per100 = float(desc.split("Calories:")[-1].split("kcal")[0].strip())
        total = per100 * grams / 100
        await update.message.reply_text(f"{grams:.0f} г ≈ {total:.0f} ккал")

        meal = {
            "food_name": food["food_name"],
            "calories": total,
            "protein": None, "fat": None, "carbs": None,
            "weight": grams
        }
        self.db.save_meal(update.effective_user.id, meal)  # Раскомментируйте, если реализуете базу данных

        kb = [[KeyboardButton("Подсчёт ккал блюда")]]
        return await update.message.reply_text("Готово!", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

    async def chat_with_ai(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_message = update.message.text

        if user_message.lower() in ["/cancel", "Выйти из AI"]:
            await update.message.reply_text(
                "Вы вышли из режима чата с AI.")
            return START

        ai_response = await self.yandex_gpt.get_response(user_message)
        await update.message.reply_text(ai_response, parse_mode="Markdown")
        return CHAT_WITH_AI

    async def error(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.exception("Handler error")
        if update.message:
            await update.message.reply_text("❌ Ошибка, попробуйте позже")

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
                CHAT_WITH_AI: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.chat_with_ai)],
            },
            fallbacks=[CommandHandler("cancel", self.start)]
        )

        app.add_handler(conv)
        logger.info("Бот запущен")
        app.run_polling()


if __name__ == "__main__":
    BotController().run()
