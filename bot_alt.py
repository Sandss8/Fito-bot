from datetime import datetime
from database import Database
import os
import requests
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes,
    filters, ConversationHandler
)
import logging

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# Загружаем токены из .env файла окружения
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
FATSECRET_CLIENT_ID = os.getenv("FATSECRET_CLIENT_ID")
FATSECRET_CLIENT_SECRET = os.getenv("FATSECRET_CLIENT_SECRET")

# Инициализация базы данных
db = Database()

# Константы для состояний пользователя
GENDER, AGE, HEIGHT, WEIGHT, ACTIVITY_LEVEL = range(5)
CHOOSE_ACTION, ENTER_DISH_NAME, ENTER_WEIGHT, ENTER_INGREDIENTS = range(5, 9)

# Возможные уровни активности пользователя
ACTIVITY_LEVELS = [
    "1. Малоподвижный образ жизни",
    "2. Лёгкие физические нагрузки, прогулки",
    "3. Тренировки 4-5 раз в неделю",
    "4. Физическая активность 5-6 раз в неделю",
    "5. Высокая активность 6-7 раз в неделю",
    "6. Профессиональный спорт (2+ тренировки в день)"
]

# Факторы активности для расчета суточной нормы калорий
ACTIVITY_FACTORS = {
    ACTIVITY_LEVELS[0]: 1.2,
    ACTIVITY_LEVELS[1]: 1.375,
    ACTIVITY_LEVELS[2]: 1.55,
    ACTIVITY_LEVELS[3]: 1.725,
    ACTIVITY_LEVELS[4]: 1.9,
    ACTIVITY_LEVELS[5]: 2.1
}


# --- Работа с FatSecret API ---
def get_access_token():
    """
    Получение access_token с использованием Client Credentials Flow OAuth2.
    Добавлена обработка ошибок.
    """
    url = "https://oauth.fatsecret.com/connect/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "scope": "basic",
        "client_id": FATSECRET_CLIENT_ID,
        "client_secret": FATSECRET_CLIENT_SECRET
    }
    try:
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()
        token_data = response.json()
        if 'access_token' not in token_data:
            logger.error(f"FatSecret API error: {token_data}")
            raise ValueError("No access_token in response")
        return token_data["access_token"]
    except Exception as e:
        logger.error(f"Error getting access token: {e}")
        raise


def search_food(query, token):
    """
    Выполняет поиск продуктов по текстовому запросу через FatSecret API.
    Возвращает JSON с найденными продуктами.
    """
    url = "https://platform.fatsecret.com/rest/server.api"
    params = {
        "method": "foods.search",
        "search_expression": query,
        "format": "json"
    }
    headers = {
        "Authorization": f"Bearer {token}"
    }
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error searching food: {e}")
        raise


# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.message.chat.first_name
    reply_keyboard = [["Регистрация", "Подсчёт ккал блюда"]]
    await update.message.reply_text(
        f"Привет, {user_name}! Выбери, что ты хочешь сделать?\n\n"
        "Рекомендую для начала зарегистрироваться, чтобы подсчитать дневную норму ккал!",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return CHOOSE_ACTION


async def choose_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_data = context.user_data

    # Проверяем, завершена ли регистрация
    registration_complete = user_data.get('registration_complete', False)

    if str(text) == "Регистрация" and not registration_complete:
        await update.message.reply_text(
            f"Чтобы помочь тебе, мне надо задать пару вопросов.\n"
            f"Пример ответа будет отображаться вот так: |Пример|"
        )
        reply_keyboard = [["М", "Ж"]]
        await update.message.reply_text("Укажите ваш биологический пол:",
                                        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))

        return GENDER
    elif str(text) == "Подсчёт ккал блюда":
        await update.message.reply_text("Какое блюдо вы ели или готовите? Опишите кратко.")
        return ENTER_DISH_NAME
    else:
        if registration_complete:
            reply_keyboard = [["Подсчёт ккал блюда"]]
        else:
            reply_keyboard = [["Регистрация", "Подсчёт ккал блюда"]]
        await update.message.reply_text("Пожалуйста, используйте кнопки ниже:",
                                        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
        return CHOOSE_ACTION


# Обработчик сообщения с гендером
async def gender_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gender = update.message.text.upper()
    if str(gender) not in ['М', 'Ж']:
        await update.message.reply_text(
            "Пожалуйста, выберите пол, используя кнопки ниже:",
            reply_markup=ReplyKeyboardMarkup([["М", "Ж"]], one_time_keyboard=True)
        )
        return GENDER

    context.user_data['gender'] = gender
    gender_text = "Мужской" if gender == "М" else "Женский"
    await update.message.reply_text(f"✅ Ваш пол: {gender_text}", reply_markup=ReplyKeyboardRemove())

    await update.message.reply_text("Введите ваш возраст (полных лет):\n| 25 |")
    return AGE  # Переводим бота в состояние ожидания возраста


# Обработчик сообщения с возрастом
async def age_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        age = int(update.message.text)
        if not 10 <= age <= 120:
            raise ValueError
        context.user_data['age'] = age
        await update.message.reply_text(f"✅ Вам {age} лет)")

        await update.message.reply_text('Введите ваш рост в см \n| 175 |')
        return HEIGHT  # Переводим бота в состояние ожидания роста
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите корректное, целое число \n| 20 | (10-120)")
        return AGE  # Остаемся в состоянии возраста


# Обработчик сообщения с ростом
async def height_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        height = int(update.message.text)
        if not 100 <= height <= 250:
            raise ValueError
        context.user_data['height'] = height  # Сохраняем рост
        await update.message.reply_text(f"✅ Ваш рост: {height} см")

        await update.message.reply_text("Введите ваш вес в кг \n| 50 | 50,5 | 50.55 |")
        return WEIGHT  # Переводим бота в состояние ожидания веса

    except ValueError:
        await update.message.reply_text("Пожалуйста, введите корректное, целое число  \n| 150 | (100-250)")
        return HEIGHT  # Остаемся в состоянии роста


# Обработчик сообщения с весом
async def weight_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    weight = update.message.text
    try:
        weight = float(str(weight).replace(',', '.'))
        if not 30 <= weight <= 300:
            raise ValueError
        context.user_data['weight'] = weight  # Сохраняем вес
        await update.message.reply_text(f"✅ Ваш вес: {weight} кг")

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


async def activity_level_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    activity = update.message.text
    if activity not in ACTIVITY_LEVELS:
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

    context.user_data['activity_level'] = activity
    context.user_data['registration_complete'] = True
    await update.message.reply_text(f"✅ Ваш уровень активности: {activity[2:]}", reply_markup=ReplyKeyboardRemove())

    # Расчет и вывод результатов
    weight = context.user_data['weight']
    height = context.user_data['height']
    age = context.user_data['age']
    gender = context.user_data['gender']
    activity_factor = ACTIVITY_FACTORS[activity]

    # Формула Миффлина-Сан Жеора
    if gender == "М":
        bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
    else:
        bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161

    daily_calories = bmr * activity_factor

    await update.message.reply_text(
        "📊 Результаты расчета:\n\n"
        f"🔹 Основной обмен: {bmr:.0f} ккал/день\n"
        f"🔹 С учетом активности: {daily_calories:.0f} ккал/день\n\n"
        "Это примерная норма для поддержания текущего веса."
    )

    # Подготавливаем данные для сохранения
    user_data = {
        'user_id': update.message.chat.id,
        'username': update.message.chat.username,
        'first_name': update.message.chat.first_name,
        'last_name': update.message.chat.last_name,
        'gender': gender,
        'age': age,
        'height': height,
        'weight': weight,
        'activity_level': activity,
        'bmr': bmr,
        'daily_calories': daily_calories,
        'registration_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    # Сохраняем данные через наш класс Database
    db.save_user_data(user_data)

    # Показать меню после расчета
    reply_keyboard = [["Подсчёт ккал блюда"]]
    await update.message.reply_text(
        "Что дальше хочешь сделать?",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    )

    return CHOOSE_ACTION


# Получение названия блюда
async def enter_dish_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Принимает от пользователя название продукта или блюда,
    ищет его в FatSecret и предлагает ввести массу (в граммах).
    """
    query = update.message.text
    context.user_data['dish_query'] = query

    try:
        token = get_access_token()
        result = search_food(query, token)

        if "foods" not in result or "food" not in result["foods"] or not result["foods"]["food"]:
            await update.message.reply_text("❌ Не удалось найти информацию по блюду. Попробуйте другое название.")
            return CHOOSE_ACTION

        # Используем первый результат из поиска
        food = result["foods"]["food"][0]
        context.user_data['food'] = food

        name = food["food_name"]
        desc = food.get("food_description", "Нет описания")

        await update.message.reply_text(
            f"🔍 Найдено: {name}\nОписание: {desc}\n\n"
            f"Введите вес продукта в граммах для расчета калорийности."
        )
        return ENTER_WEIGHT

    except Exception as e:
        logger.error(f"FatSecret API error: {str(e)}")
        await update.message.reply_text(
            "Сервис питания временно недоступен. Пожалуйста, попробуйте позже."
        )
        return CHOOSE_ACTION


async def enter_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Принимает вес продукта от пользователя, извлекает калории из описания
    и рассчитывает общую калорийность.
    """
    try:
        grams = float(update.message.text.replace(',', '.'))  # Обрабатываем ввод с запятой
        food = context.user_data.get('food')
        if not food:
            await update.message.reply_text("❌ Информация о блюде утеряна. Начните поиск заново.")
            return CHOOSE_ACTION

        desc = food.get("food_description", "")
        if "Calories:" not in desc:
            await update.message.reply_text("❌ Не удалось получить информацию о калорийности. Попробуйте другое блюдо.")
            return CHOOSE_ACTION

        # Пытаемся вычленить число калорий из текстового описания
        calories_part = desc.split('Calories:')[-1].split('kcal')[0].strip()
        cal_per_100g = float(calories_part)

        total_calories = (cal_per_100g * grams) / 100

        await update.message.reply_text(
            f"🍽️ Калорийность {grams:.0f} г продукта: {total_calories:.0f} ккал."
        )

        # Показываем кнопку возврата к подсчету следующего блюда
        keyboard = [[KeyboardButton("Подсчёт ккал блюда")]]
        await update.message.reply_text("Что дальше?", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return CHOOSE_ACTION

    except ValueError:
        await update.message.reply_text("Пожалуйста, введите число — массу продукта в граммах.")
        return ENTER_WEIGHT
    except Exception as e:
        logger.error(f"Error in enter_weight: {e}")
        await update.message.reply_text("❌ Произошла ошибка при расчете калорий. Пожалуйста, попробуйте снова.")
        return CHOOSE_ACTION


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Логируем ошибки и уведомляем пользователя."""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

    if update and update.message:
        await update.message.reply_text("❌ Произошла непредвиденная ошибка. Пожалуйста, попробуйте позже.")


# Основная программа
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Добавляем обработчик ошибок
    app.add_error_handler(error_handler)

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start), CommandHandler('profile', start)],
        states={
            CHOOSE_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_action)],
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, gender_handler)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, age_handler)],
            HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, height_handler)],
            WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, weight_handler)],
            ACTIVITY_LEVEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, activity_level_handler)],
            ENTER_DISH_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_dish_name)],
            ENTER_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_weight)],
        },
        fallbacks=[]
    )

    app.add_handler(conv_handler)

    print("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()

    # return ConversationHandler.END  # Завершаем диалог
