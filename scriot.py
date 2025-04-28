import telebot
import asyncio
from telebot import types
bot = telebot.TeleBot("7777717880:AAHFu4PF8t-sfOJ9gpof5JA1K0RIcB3nR18")

@bot.message_handler(commands=["start"])
def main(message):
    bot.send_message(message.chat.id,f"Привет ,{message.from_user.first_name}!")


@bot.message_handler(commands=["stats"])
def start_stats(message):
    bot.send_message(message.chat.id, "Введите ваш вес (в кг):")
    bot.register_next_step_handler(message, process_weight)


def process_weight(message):
    try:
        weight = float(message.text)
        bot.send_message(message.chat.id, "Введите ваш рост (в см):")
        bot.register_next_step_handler(message, process_height, weight)
    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, введите корректный вес.")
        bot.register_next_step_handler(message, process_weight)


def process_height(message, weight):
    try:
        height = float(message.text)
        bot.send_message(message.chat.id, "Введите ваш возраст (в годах):")
        bot.register_next_step_handler(message, process_age, weight, height)
    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, введите корректный рост.")
        bot.register_next_step_handler(message, process_height, weight)


def process_age(message, weight, height):
    try:
        age = int(message.text)
        bot.send_message(message.chat.id, "Введите ваш пол (male/female):")
        bot.register_next_step_handler(message, process_gender, weight, height, age)

    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, введите корректный возраст.")
        bot.register_next_step_handler(message, process_age, weight, height)


def process_gender(message, weight, height, age):
    gender = message.text.lower()
    if gender not in ['male', 'female']:
        bot.send_message(message.chat.id, "Пожалуйста, введите корректный пол (male/female).")
        bot.register_next_step_handler(message, process_gender, weight, height, age)
        return

    bot.send_message(message.chat.id, "Введите уровень активности (sedentary/light/moderate/active/very active):")
    bot.register_next_step_handler(message, process_activity_level, weight, height, age, gender)


def process_activity_level(message, weight, height, age, gender):
    activity_level = message.text.lower()
    activity_multiplier = {
        'sedentary': 1.2,
        'light': 1.375,
        'moderate': 1.55,
        'active': 1.725,
        'very active': 1.9
    }

    if activity_level not in activity_multiplier:
        bot.send_message(message.chat.id, "Пожалуйста, введите корректный уровень активности.")
        bot.register_next_step_handler(message, process_activity_level, weight, height, age, gender)
        return

    bot.send_message(message.chat.id, "Введите вашу цель (lose/gain/maintain):")
    bot.register_next_step_handler(message, process_goal, weight, height, age, gender, activity_level)


def process_goal(message, weight, height, age, gender, activity_level):
    goal = message.text.lower()

    # Расчет BMR
    if gender == 'male':
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161

    # Расчет TDEE
    activity_multiplier = {
        'sedentary': 1.2,
        'light': 1.375,
        'moderate': 1.55,
        'active': 1.725,
        'very active': 1.9
    }

    tdee = bmr * activity_multiplier[activity_level]

    # Целевое калорийное потребление
    if goal == 'lose':
        caloric_intake = tdee - 500
    elif goal == 'gain':
        caloric_intake = tdee + 500
    else:
        caloric_intake = tdee

    # Расчет макронутриентов
    protein = caloric_intake * 0.3 / 4
    fats = caloric_intake * 0.25 / 9
    carbs = caloric_intake * 0.45 / 4

    # Отправка результатов
    bot.send_message(message.chat.id, f"Ваши калории: {caloric_intake:.2f} ккал")
    bot.send_message(message.chat.id, f"Ваши белки: {protein:.2f} г")
    bot.send_message(message.chat.id, f"Ваши жиры: {fats:.2f} г")
    bot.send_message(message.chat.id, f"Ваши углеводы: {carbs:.2f} г")


bot.polling(non_stop=True)