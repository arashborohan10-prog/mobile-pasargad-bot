import os
import telebot
from telebot import types

TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=["start"])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

    mobile = types.KeyboardButton("📱 موبایل")
    gadget = types.KeyboardButton("🎧 گجت")
    massager = types.KeyboardButton("💆 ماساژور")
    accessories = types.KeyboardButton("🔌 لوازم جانبی")

    markup.add(mobile, gadget, massager, accessories)

    bot.send_message(
        message.chat.id,
        "🟡 به فروشگاه موبایل پاسارگاد خوش آمدید\n\n"
        "دسته‌بندی مورد نظر خود را انتخاب کنید 👇",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: True)
def menu(message):
    if message.text == "📱 موبایل":
        bot.send_message(message.chat.id, "📱 بخش موبایل\nمحصولات این بخش به‌زودی اضافه می‌شوند.")

    elif message.text == "🎧 گجت":
        bot.send_message(message.chat.id, "🎧 بخش گجت\nمحصولات این بخش به‌زودی اضافه می‌شوند.")

    elif message.text == "💆 ماساژور":
        bot.send_message(message.chat.id, "💆 بخش ماساژور\nمحصولات این بخش به‌زودی اضافه می‌شوند.")

    elif message.text == "🔌 لوازم جانبی":
        bot.send_message(message.chat.id, "🔌 بخش لوازم جانبی\nمحصولات این بخش به‌زودی اضافه می‌شوند.")

print("Mobile Pasargad Bot is running...")
bot.infinity_polling()
