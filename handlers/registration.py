from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, filters
from config import Config
from handlers.base import BaseHandler
from datetime import datetime
from database import Database


class RegistrationHandler(BaseHandler):
    def __init__(self):
        super().__init__()
        self.db = Database()
        self.message_handlers = [
            (filters.Text(["Регистрация"]) & ~filters.COMMAND, self.start_registration),
            (filters.Text(["М", "Ж"]) & ~filters.COMMAND, self.handle_gender),
            (filters.Regex(r'^\d+$') & ~filters.COMMAND, self.handle_numeric_input),
            (filters.Regex(r'^\d+[,.]?\d*$') & ~filters.COMMAND, self.handle_weight_input),
            (filters.Text(Config.ACTIVITY_LEVELS) & ~filters.COMMAND, self.handle_activity)
        ]

    async def start_registration(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало процесса регистрации"""
        if context.user_data.get('registration_complete', False):
            await update.message.reply_text("Вы уже зарегистрированы!")
            return Config.CHOOSE_ACTION

        await update.message.reply_text(
            "Для регистрации ответьте на несколько вопросов.\n"
            "Пример ответа: |Пример|"
        )
        reply_keyboard = [["М", "Ж"]]
        await update.message.reply_text(
            "Укажите ваш биологический пол:",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
        )
        return Config.GENDER

    async def handle_gender(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора пола"""
        gender = update.message.text.upper()
        context.user_data['gender'] = gender

        gender_text = "Мужской" if gender == "М" else "Женский"
        await update.message.reply_text(
            f"✅ Ваш пол: {gender_text}",
            reply_markup=ReplyKeyboardRemove()
        )
        await update.message.reply_text("Введите ваш возраст (полных лет):\n|25|")
        return Config.AGE

    async def handle_numeric_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка числовых вводов (возраст, рост)"""
        current_state = context.user_data.get('registration_stage', 'age')

        if current_state == 'age':
            return await self.handle_age(update, context)
        elif current_state == 'height':
            return await self.handle_height(update, context)

    async def handle_age(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка возраста"""
        try:
            age = int(update.message.text)
            if not 10 <= age <= 120:
                raise ValueError

            context.user_data['age'] = age
            context.user_data['registration_stage'] = 'height'

            await update.message.reply_text(f"✅ Вам {age} лет")
            await update.message.reply_text("Введите ваш рост в см:\n|175|")
            return Config.HEIGHT

        except ValueError:
            await update.message.reply_text("Пожалуйста, введите корректный возраст (10-120 лет)")
            return Config.AGE

    async def handle_height(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка роста"""
        try:
            height = int(update.message.text)
            if not 100 <= height <= 250:
                raise ValueError

            context.user_data['height'] = height
            context.user_data['registration_stage'] = 'weight'

            await update.message.reply_text(f"✅ Ваш рост: {height} см")
            await update.message.reply_text("Введите ваш вес в кг:\n|70.5|")
            return Config.WEIGHT

        except ValueError:
            await update.message.reply_text("Пожалуйста, введите корректный рост (100-250 см)")
            return Config.HEIGHT

    async def handle_weight_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка веса"""
        try:
            weight = float(update.message.text.replace(',', '.'))
            if not 30 <= weight <= 300:
                raise ValueError

            context.user_data['weight'] = weight
            context.user_data['registration_stage'] = 'activity'

            await update.message.reply_text(f"✅ Ваш вес: {weight} кг")

            # Создаем клавиатуру с уровнями активности
            reply_keyboard = [
                [Config.ACTIVITY_LEVELS[0]],
                [Config.ACTIVITY_LEVELS[1], Config.ACTIVITY_LEVELS[2]],
                [Config.ACTIVITY_LEVELS[3], Config.ACTIVITY_LEVELS[4]],
                [Config.ACTIVITY_LEVELS[5]]
            ]

            await update.message.reply_text(
                "Выберите уровень физической активности:",
                reply_markup=ReplyKeyboardMarkup(
                    reply_keyboard,
                    one_time_keyboard=True,
                    resize_keyboard=True
                )
            )
            return Config.ACTIVITY_LEVEL

        except ValueError:
            await update.message.reply_text("Пожалуйста, введите корректный вес (30-300 кг)")
            return Config.WEIGHT

    async def handle_activity(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка уровня активности"""
        activity = update.message.text
        context.user_data['activity_level'] = activity
        context.user_data['registration_complete'] = True

        await update.message.reply_text(
            f"✅ Ваш уровень активности: {activity[2:]}",
            reply_markup=ReplyKeyboardRemove()
        )

        # Расчет дневной нормы калорий
        weight = context.user_data['weight']
        height = context.user_data['height']
        age = context.user_data['age']
        gender = context.user_data['gender']
        activity_factor = Config.ACTIVITY_FACTORS[activity]

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

        # Сохранение данных пользователя
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

        self.db.save_user_data(user_data)

        # Возврат в главное меню
        reply_keyboard = [["Подсчёт ккал блюда"]]
        await update.message.reply_text(
            "Регистрация завершена! Что дальше?",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
        )
        return Config.CHOOSE_ACTION
