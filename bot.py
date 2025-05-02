import os
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, ConversationHandler

# Загружаем токен из .env
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Константы для состояний
GENDER, AGE, HEIGHT, WEIGHT, ACTIVITY_LEVEL = range(5)

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


# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.message.chat.first_name
    await update.message.reply_text(
        f"Привет, {user_name}!\n"
        f"Чтобы помочь тебе, мне надо задать пару вопросов.\n"
        f"Пример ответа будет отображаться вот так: |Пример|"
    )

    reply_keyboard = [["М", "Ж"]]
    await update.message.reply_text("Укажите ваш биологический пол:",
                                    reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
    return GENDER  # Переводим бота в состояние ожидания веса


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
    return ConversationHandler.END  # Завершаем диалог


# Основная программа
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Настройка ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, gender_handler)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, age_handler)],
            HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, height_handler)],
            WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, weight_handler)],
            ACTIVITY_LEVEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, activity_level_handler)]
        },
        fallbacks=[]
    )

    app.add_handler(conv_handler)

    print("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()
