import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Токены
    TOKEN = os.getenv("BOT_TOKEN")
    FATSECRET_CLIENT_ID = os.getenv("FATSECRET_CLIENT_ID")
    FATSECRET_CLIENT_SECRET = os.getenv("FATSECRET_CLIENT_SECRET")

    # Состояния бота
    (GENDER, AGE, HEIGHT, WEIGHT, ACTIVITY_LEVEL,CHOOSE_ACTION, ENTER_DISH_NAME, ENTER_WEIGHT) = range(8)

    # Уровни активности
    ACTIVITY_LEVELS = [
        "1. Малоподвижный образ жизни",
        "2. Лёгкие физические нагрузки, прогулки",
        "3. Тренировки 4-5 раз в неделю",
        "4. Физическая активность 5-6 раз в неделю",
        "5. Высокая активность 6-7 раз в неделю",
        "6. Профессиональный спорт (2+ тренировки в день)"
    ]

    # Коэффициенты активности
    ACTIVITY_FACTORS = {
        ACTIVITY_LEVELS[0]: 1.2,
        ACTIVITY_LEVELS[1]: 1.375,
        ACTIVITY_LEVELS[2]: 1.55,
        ACTIVITY_LEVELS[3]: 1.725,
        ACTIVITY_LEVELS[4]: 1.9,
        ACTIVITY_LEVELS[5]: 2.1
    }
