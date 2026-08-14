import os
import sqlite3
import telebot
from telebot import types

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 1040416634

bot = telebot.TeleBot(TOKEN)

# =========================
# DATABASE
# =========================

db = sqlite3.connect("shop.db", check_same_thread=False)
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT,
    name TEXT,
    description TEXT,
    price TEXT,
    photo_id TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
)
""")

cursor.execute("""
INSERT OR IGNORE INTO settings (key, value)
VALUES ('support', '☎️ اطلاعات پشتیبانی هنوز تنظیم نشده است.')
""")

db.commit()

user_states = {}

# =========================
# CATEGORIES
# =========================

CATEGORIES = {
    "mobile": "📱 موبایل",
    "gadget": "🎮 گجت",
    "massager": "💆 ماساژور",
    "cable": "🔌 کابل",
    "headphone": "🎧 هدفون",
    "charger": "⚡ شارژر",
    "handsfree": "🎙 هندزفری",
    "airpod": "🎧 AirPods",
    "holder": "🚗 هلدر",
    "converter": "🔄 تبدیل",
    "flash": "💾 فلش و رم",
    "speaker": "🔊 اسپیکر",
    "keyboard": "🖱 موس و کیبورد",
    "modem": "📡 مودم اینترنت",
    "simcard": "📲 سیمکارت"
}

CATEGORY_BY_NAME = {v: k for k, v in CATEGORIES.items()}

# =========================
# MAIN MENU
# =========================

def main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

    buttons = [types.KeyboardButton(x) for x in CATEGORIES.values()]

    for i in range(0, len(buttons), 2):
        markup.row(*buttons[i:i+2])

    markup.row(types.KeyboardButton("☎️ پشتیبانی و ارتباط با ما"))

    if user_id == ADMIN_ID:
        markup.row(types.KeyboardButton("🔐 پنل مدیریت"))

    return markup


# =========================
# ADMIN MENU
# =========================

def admin_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

    markup.row(
        types.KeyboardButton("➕ افزودن محصول"),
        types.KeyboardButton("🗑 حذف محصول")
    )

    markup.row(
        types.KeyboardButton("✏️ ویرایش محصول"),
        types.KeyboardButton("☎️ ویرایش پشتیبانی")
    )

    markup.row(types.KeyboardButton("🏠 منوی اصلی"))

    return markup


def category_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

    buttons = [types.KeyboardButton(x) for x in CATEGORIES.values()]

    for i in range(0, len(buttons), 2):
        markup.row(*buttons[i:i+2])

    markup.row(types.KeyboardButton("❌ لغو"))

    return markup


# =========================
# START
# =========================

@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(
        message.chat.id,
        "🟡 به فروشگاه موبایل پاسارگاد خوش آمدید\n\n"
        "👇 دسته‌بندی مورد نظر خود را انتخاب کنید:",
        reply_markup=main_menu(message.from_user.id)
    )


# =========================
# SHOW PRODUCTS
# =========================

def show_product(chat_id, category, index=0):

    cursor.execute(
        "SELECT id, name, description, price, photo_id FROM products WHERE category=? ORDER BY id DESC",
        (category,)
    )

    products = cursor.fetchall()

    if not products:
        bot.send_message(
            chat_id,
            "❌ در این دسته هنوز محصولی ثبت نشده است."
        )
        return

    index %= len(products)

    product = products[index]

    product_id = product[0]
    name = product[1]
    description = product[2]
    price = product[3]
    photo_id = product[4]

    caption = (
        f"🛍 {name}\n\n"
        f"📝 {description}\n\n"
        f"💰 قیمت: {price}\n\n"
        f"📦 محصول {index + 1} از {len(products)}"
    )

    markup = types.InlineKeyboardMarkup()

    markup.row(
        types.InlineKeyboardButton(
            "⬅️ قبلی",
            callback_data=f"p|{category}|{index-1}"
        ),
        types.InlineKeyboardButton(
            "بعدی ➡️",
            callback_data=f"p|{category}|{index+1}"
        )
    )

    bot.send_photo(
        chat_id,
        photo_id,
        caption=caption,
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("p|"))
def product_navigation(call):

    parts = call.data.split("|")

    category = parts[1]
    index = int(parts[2])

    try:
        bot.delete_message(
            call.message.chat.id,
            call.message.message_id
        )
    except:
        pass

    show_product(
        call.message.chat.id,
        category,
        index
    )

    bot.answer_callback_query(call.id)


# =========================
# TEXT MESSAGES
# =========================

@bot.message_handler(content_types=["text"])
def messages(message):

    text = message.text
    user_id = message.from_user.id
    chat_id = message.chat.id

    # CANCEL
    if text == "❌ لغو":

        user_states.pop(user_id, None)

        bot.send_message(
            chat_id,
            "✅ عملیات لغو شد.",
            reply_markup=main_menu(user_id)
        )

        return

    # MAIN MENU
    if text == "🏠 منوی اصلی":

        user_states.pop(user_id, None)

        bot.send_message(
            chat_id,
            "🏠 منوی اصلی",
            reply_markup=main_menu(user_id)
        )

        return

    # CATEGORIES
    if text in CATEGORY_BY_NAME:

        category = CATEGORY_BY_NAME[text]

        show_product(chat_id, category)

        return

    # SUPPORT
    if text == "☎️ پشتیبانی و ارتباط با ما":

        cursor.execute(
            "SELECT value FROM settings WHERE key='support'"
        )

        result = cursor.fetchone()

        support_text = result[0] if result else "اطلاعات پشتیبانی ثبت نشده."

        bot.send_message(
            chat_id,
            support_text
        )

        return

    # ADMIN PANEL
    if text == "🔐 پنل مدیریت":

        if user_id != ADMIN_ID:
            return

        bot.send_message(
            chat_id,
            "🔐 پنل مدیریت موبایل پاسارگاد",
            reply_markup=admin_menu()
        )

        return

    # =========================
    # ADD PRODUCT
    # =========================

    if text == "➕ افزودن محصول" and user_id == ADMIN_ID:

        user_states[user_id] = {
            "action": "add",
            "step": "category"
        }

        bot.send_message(
            chat_id,
            "📂 دسته‌بندی محصول را انتخاب کن:",
            reply_markup=category_menu()
        )

        return

    if user_id in user_states:

        state = user_states[user_id]

        if state["action"] == "add":

            if state["step"] == "category":

                if text not in CATEGORY_BY_NAME:
                    bot.send_message(chat_id, "یکی از دسته‌ها را انتخاب کن.")
                    return

                state["category"] = CATEGORY_BY_NAME[text]
                state["step"] = "name"

                bot.send_message(
                    chat_id,
                    "✏️ اسم محصول را بفرست:"
                )

                return

            if state["step"] == "name":

                state["name"] = text
                state["step"] = "description"

                bot.send_message(
                    chat_id,
                    "📝 مشخصات و توضیحات محصول را بفرست:"
                )

                return

            if state["step"] == "description":

                state["description"] = text
                state["step"] = "price"

                bot.send_message(
                    chat_id,
                    "💰 قیمت محصول را بفرست:"
                )

                return

            if state["step"] == "price":

                state["price"] = text
                state["step"] = "photo"

                bot.send_message(
                    chat_id,
                    "🖼 حالا عکس محصول را بفرست:"
                )

                return

    # =========================
    # DELETE PRODUCT
    # =========================

    if text == "🗑 حذف محصول" and user_id == ADMIN_ID:

        user_states[user_id] = {
            "action": "delete"
        }

        cursor.execute(
            "SELECT id, name FROM products ORDER BY id DESC"
        )

        products = cursor.fetchall()

        if not products:
            bot.send_message(chat_id, "محصولی برای حذف وجود ندارد.")
            return

        markup = types.InlineKeyboardMarkup()

        for product in products:

            markup.row(
                types.InlineKeyboardButton(
                    f"🗑 {product[1]}",
                    callback_data=f"d|{product[0]}"
                )
            )

        bot.send_message(
            chat_id,
            "محصولی که می‌خواهی حذف کنی انتخاب کن:",
            reply_markup=markup
        )

        return

    # =========================
    # EDIT PRODUCT
    # =========================

    if text == "✏️ ویرایش محصول" and user_id == ADMIN_ID:

        cursor.execute(
            "SELECT id, name FROM products ORDER BY id DESC"
        )

        products = cursor.fetchall()

        if not products:
            bot.send_message(chat_id, "محصولی برای ویرایش وجود ندارد.")
            return

        markup = types.InlineKeyboardMarkup()

        for product in products:

            markup.row(
                types.InlineKeyboardButton(
                    f"✏️ {product[1]}",
                    callback_data=f"e|{product[0]}"
                )
            )

        bot.send_message(
            chat_id,
            "محصول مورد نظر را انتخاب کن:",
            reply_markup=markup
        )

        return

    # =========================
    # EDIT SUPPORT
    # =========================

    if text == "☎️ ویرایش پشتیبانی" and user_id == ADMIN_ID:

        user_states[user_id] = {
            "action": "support"
        }

        bot.send_message(
            chat_id,
            "☎️ متن جدید پشتیبانی را کامل بفرست.\n\n"
            "مثلاً:\n"
            "☎️ تماس: 0912...\n"
            "💬 واتساپ: 0912...\n"
            "📷 اینستاگرام: @...\n"
            "📍 آدرس: ..."
        )

        return

    if user_id in user_states:

        state = user_states[user_id]

        if state["action"] == "support":

            cursor.execute(
                "UPDATE settings SET value=? WHERE key='support'",
                (text,)
            )

            db.commit()

            user_states.pop(user_id, None)

            bot.send_message(
                chat_id,
                "✅ اطلاعات پشتیبانی با موفقیت ذخیره شد.",
                reply_markup=admin_menu()
            )

            return


# =========================
# PHOTO FOR NEW PRODUCT
# =========================

@bot.message_handler(content_types=["photo"])
def photo_handler(message):

    user_id = message.from_user.id
    chat_id = message.chat.id

    if user_id not in user_states:
        return

    state = user_states[user_id]

    if state.get("action") == "add" and state.get("step") == "photo":

        photo_id = message.photo[-1].file_id

        cursor.execute(
            """
            INSERT INTO products
            (category, name, description, price, photo_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                state["category"],
                state["name"],
                state["description"],
                state["price"],
                photo_id
            )
        )

        db.commit()

        user_states.pop(user_id, None)

        bot.send_message(
            chat_id,
            "✅ محصول با موفقیت اضافه شد.",
            reply_markup=admin_menu()
        )


# =========================
# DELETE CALLBACK
# =========================

@bot.callback_query_handler(func=lambda call: call.data.startswith("d|"))
def delete_product(call):

    if call.from_user.id != ADMIN_ID:
        return

    product_id = int(call.data.split("|")[1])

    cursor.execute(
        "DELETE FROM products WHERE id=?",
        (product_id,)
    )

    db.commit()

    bot.answer_callback_query(
        call.id,
        "✅ محصول حذف شد."
    )

    bot.edit_message_text(
        "✅ محصول با موفقیت حذف شد.",
        call.message.chat.id,
        call.message.message_id
    )


# =========================
# EDIT CALLBACK
# =========================

@bot.callback_query_handler(func=lambda call: call.data.startswith("e|"))
def edit_product(call):

    if call.from_user.id != ADMIN_ID:
        return

    product_id = int(call.data.split("|")[1])

    user_states[call.from_user.id] = {
        "action": "edit",
        "product_id": product_id,
        "step": "name"
    }

    bot.send_message(
        call.message.chat.id,
        "✏️ اسم جدید محصول را بفرست:"
    )

    bot.answer_callback_query(call.id)


@bot.message_handler(func=lambda message:
                     message.from_user.id in user_states and
                     user_states[message.from_user.id].get("action") == "edit")
def edit_steps(message):

    user_id = message.from_user.id
    chat_id = message.chat.id
    state = user_states[user_id]

    if state["step"] == "name":

        state["name"] = message.text
        state["step"] = "description"

        bot.send_message(
            chat_id,
            "📝 مشخصات جدید محصول را بفرست:"
        )

        return

    if state["step"] == "description":

        state["description"] = message.text
        state["step"] = "price"

        bot.send_message(
            chat_id,
            "💰 قیمت جدید محصول را بفرست:"
        )

        return

    if state["step"] == "price":

        cursor.execute(
            """
            UPDATE products
            SET name=?, description=?, price=?
            WHERE id=?
            """,
            (
                state["name"],
                state["description"],
                message.text,
                state["product_id"]
            )
        )

        db.commit()

        user_states.pop(user_id, None)

        bot.send_message(
            chat_id,
            "✅ محصول با موفقیت ویرایش شد.",
            reply_markup=admin_menu()
        )


# =========================
# RUN BOT
# =========================

print("Mobile Pasargad Bot is running...")

bot.infinity_polling(
    timeout=60,
    long_polling_timeout=60
)
