from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, filters
from config import Config
from base import BaseHandler
from services.fatsecret import FatSecretAPI
import logging

logger = logging.getLogger(__name__)


class FoodTrackingHandler(BaseHandler):
    def __init__(self):
        super().__init__()
        self.fatsecret = FatSecretAPI()
        self.message_handlers = [
            (filters.Text(["Подсчёт ккал блюда"]) & ~filters.COMMAND, self.start_tracking),
            (filters.TEXT & ~filters.COMMAND, self.handle_food_input)
        ]

    async def start_tracking(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало процесса подсчета калорий"""
        await update.message.reply_text(
            "Какое блюдо вы ели или готовите? Опишите кратко:\n"
            "Пример: |Куриная грудка с рисом|"
        )
        context.user_data['food_tracking_stage'] = 'dish_name'
        return Config.ENTER_DISH_NAME

    async def handle_food_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Роутинг ввода пользователя"""
        current_stage = context.user_data.get('food_tracking_stage')

        if current_stage == 'dish_name':
            return await self.handle_dish_name(update, context)
        elif current_stage == 'weight':
            return await self.handle_weight(update, context)

        return Config.CHOOSE_ACTION

    async def handle_dish_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка названия блюда"""
        dish_name = update.message.text
        context.user_data['dish_name'] = dish_name

        try:
            # Поиск блюда в FatSecret API
            search_result = self.fatsecret.search_food(dish_name)

            if not search_result.get('foods', {}).get('food'):
                await update.message.reply_text(
                    "❌ Не удалось найти информацию по этому блюду.\n"
                    "Попробуйте уточнить название или ввести другой продукт."
                )
                return Config.CHOOSE_ACTION

            # Берем первый результат из поиска
            food_item = search_result['foods']['food'][0]
            context.user_data['current_food'] = food_item

            # Формируем информационное сообщение
            message = (
                f"🔍 Найдено: {food_item['food_name']}\n"
                f"Описание: {food_item.get('food_description', 'нет данных')}\n\n"
                "Введите вес продукта в граммах для расчета калорийности:\n"
                "Пример: |150|"
            )

            await update.message.reply_text(message)
            context.user_data['food_tracking_stage'] = 'weight'
            return Config.ENTER_WEIGHT

        except Exception as e:
            logger.error(f"Ошибка поиска блюда: {e}")
            await update.message.reply_text(
                "⚠️ Произошла ошибка при поиске блюда. Попробуйте позже."
            )
            return Config.CHOOSE_ACTION

    async def handle_weight(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка веса продукта и расчет калорий"""
        try:
            weight = float(update.message.text.replace(',', '.'))
            if not 0 < weight < 5000:  # Реалистичные ограничения веса
                raise ValueError

            food_item = context.user_data.get('current_food')
            if not food_item:
                await update.message.reply_text(
                    "❌ Информация о блюде утеряна. Начните заново."
                )
                return Config.CHOOSE_ACTION

            # Парсим калорийность из описания
            desc = food_item.get('food_description', '')
            if 'Calories:' not in desc:
                await update.message.reply_text(
                    "❌ Не удалось определить калорийность продукта.\n"
                    "Попробуйте выбрать другое блюдо."
                )
                return Config.CHOOSE_ACTION

            # Извлекаем калории на 100г
            calories_part = desc.split('Calories:')[-1].split('kcal')[0].strip()
            calories_per_100g = float(calories_part)

            # Расчет общей калорийности
            total_calories = (calories_per_100g * weight) / 100

            # Формируем результат
            nutrition_info = self._parse_nutrition_info(desc)
            result_message = (
                f"🍽 {food_item['food_name']} - {weight:.0f}г\n"
                f"🔹 Калории: {total_calories:.0f} ккал\n"
            )

            if nutrition_info:
                result_message += "\n".join(
                    f"🔹 {k}: {v * weight / 100:.1f}{unit}"
                    for k, (v, unit) in nutrition_info.items()
                )

            await update.message.reply_text(result_message)

            # Предложение продолжить
            reply_keyboard = [[KeyboardButton("Подсчёт ккал блюда")]]
            await update.message.reply_text(
                "Хотите подсчитать другое блюдо?",
                reply_markup=ReplyKeyboardMarkup(
                    reply_keyboard,
                    resize_keyboard=True,
                    one_time_keyboard=True
                )
            )

            return Config.CHOOSE_ACTION

        except ValueError:
            await update.message.reply_text(
                "⚠️ Пожалуйста, введите корректный вес в граммах (число от 1 до 5000).\n"
                "Пример: |200| или |150.5|"
            )
            return Config.ENTER_WEIGHT

        except Exception as e:
            logger.error(f"Ошибка расчета калорий: {e}")
            await update.message.reply_text(
                "⚠️ Произошла ошибка при расчете. Попробуйте снова."
            )
            return Config.CHOOSE_ACTION

    def _parse_nutrition_info(self, description: str) -> dict:
        """Парсинг информации о БЖУ из описания продукта"""
        nutrition = {}
        parts = description.split('|')

        for part in parts:
            part = part.strip()
            if ':' in part:
                name, value = part.split(':', 1)
                name = name.strip()
                value = value.strip()

                if 'g' in value:
                    num = value.replace('g', '').strip()
                    nutrition[name] = (float(num), 'g')
                elif 'mg' in value:
                    num = value.replace('mg', '').strip()
                    nutrition[name] = (float(num), 'mg')

        return nutrition
