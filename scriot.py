import telebot

bot = telebot.TeleBot("7777717880:AAHFu4PF8t-sfOJ9gpof5JA1K0RIcB3nR18")

@bot.message_handler(commands=["start"])
def main(message):
    bot.send_message(message.chat.id,f"Привет ,{message.from_user.first_name}!")


@bot.message_handler(commands=["stats"])
def calculate_kbju(message):
    data = message.text.split()[1:]
    if len(data) != 6:
        bot.send_message(message.chat.id,
                         "Пожалуйста, введите все данные: вес, рост, возраст, пол, уровень активности и цель.")
        return

    try:
        weight = float(data[0])
        height = float(data[1])
        age = int(data[2])
        gender = data[3].lower()
        activity_level = data[4].lower()
        goal = data[5].lower()
    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, убедитесь, что вес, рост и возраст являются числами.")
        return

    if gender == 'male':
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161

    activity_multiplier = {
        'sedentary': 1.2,
        'light': 1.375,
        'moderate': 1.55,
        'active': 1.725,
        'very active': 1.9
    }

    tdee = bmr * activity_multiplier.get(activity_level, 1.2)

    if goal == 'lose':
        caloric_intake = tdee - 500
    elif goal == 'gain':
        caloric_intake = tdee + 500
    else:
        caloric_intake = tdee

    protein = caloric_intake * 0.3 / 4
    fats = caloric_intake * 0.25 / 9
    carbs = caloric_intake * 0.45 / 4

    bot.send_message(message.chat.id, f"Ваши калории: {caloric_intake:.2f} ккал")
    bot.send_message(message.chat.id, f"Ваши белки: {protein:.2f} г")
    bot.send_message(message.chat.id, f"Ваши жиры: {fats:.2f} г")
    bot.send_message(message.chat.id, f"Ваши углеводы: {carbs:.2f} г")


bot.polling(non_stop=True)