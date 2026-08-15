import os
import sqlite3
import telebot
from telebot import types

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 1040416634

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

bot = telebot.TeleBot(TOKEN, threaded=False)

db = sqlite3.connect("shop.db", check_same_thread=False)
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    photo_id TEXT NOT NULL
)
""")

cursor.execute("PRAGMA table_info(products)")
columns = {row[1] for row in cursor.fetchall()}
if "subcategory" not in columns:
    cursor.execute("ALTER TABLE products ADD COLUMN subcategory TEXT")

cursor.execute("""
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
)
""")

cursor.execute(
    "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
    ("support", "☎️ اطلاعات پشتیبانی هنوز تنظیم نشده است.")
)
db.commit()

user_states = {}

CATEGORIES = {
    "mobile": "📱 موبایل",
    "gadget": "🎮 گجت",
    "massager": "💆 ماساژور",
    "cable_charger": "🔌 کابل و شارژر",
    "headphone": "🎵 هدفون",
    "handsfree": "🎧 هندزفری",
    "airpod": "🎶 ایرپاد",
    "memory": "💾 رم و فلش",
    "holder": "🧲 هولدر",
    "simcard": "💳 سیمکارت",
    "other": "📦 متفرقه",
}

CATEGORY_BY_NAME = {v: k for k, v in CATEGORIES.items()}

SUBCATEGORIES = {
    "mobile": {
        "apple": "Apple",
        "samsung": "Samsung",
        "xiaomi": "Xiaomi",
        "vokal": "Vokal",
        "realme": "Realme",
        "nokia": "Nokia",
    },

    "cable_charger": {
        "apple_lightning": "Apple (Lightning)",
        "samsung": "Samsung",
        "usb_c": "USB-C (Type-C)",
        "micro_usb": "Micro-USB",
    },

    "handsfree": {
        "usb_c": "USB-C (Type-C)",
        "aux": "جک 3.5mm (AUX)",
    },

    "airpod": {
        "apple": "Apple",
        "samsung": "Samsung",
        "xiaomi": "Xiaomi",
        "qcy": "QCY",
        "ldnio": "LDNIO",
        "powermax": "Power Max",
        "anker": "Anker",
        "haylou": "Haylou",
        "other": "متفرقه",
    },

    "memory": {
        "memory_card": "💳 کارت حافظه (Memory Card)",
        "flash": "💾 فلش مموری (USB Flash)",
    },

    "simcard": {
        "mci": "همراه اول",
        "irancell": "ایرانسل",
        "rightel": "رایتل",
        "shatel": "شاتل موبایل",
        "samantel": "سامانتل",
        "aptel": "آپتل",
    },
}

SUBCATEGORY_BY_NAME = {
    category: {name: key for key, name in values.items()}
    for category, values in SUBCATEGORIES.items()
}


def main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

    buttons = [
        types.KeyboardButton(name)
        for name in CATEGORIES.values()
    ]

    for i in range(0, len(buttons), 2):
        markup.row(*buttons[i:i + 2])

    markup.row(types.KeyboardButton("🛟 پشتیبانی"))

    if user_id == ADMIN_ID:
        markup.row(types.KeyboardButton("🔐 پنل مدیریت"))

    return markup


def admin_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

    markup.row(
        types.KeyboardButton("➕ افزودن محصول"),
        types.KeyboardButton("🗑 حذف محصول"),
    )

    markup.row(
        types.KeyboardButton("✏️ ویرایش محصول"),
        types.KeyboardButton("☎️ ویرایش پشتیبانی"),
    )

    markup.row(types.KeyboardButton("🏠 منوی اصلی"))

    return markup


def category_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

    buttons = [
        types.KeyboardButton(name)
        for name in CATEGORIES.values()
    ]

    for i in range(0, len(buttons), 2):
        markup.row(*buttons[i:i + 2])

    markup.row(types.KeyboardButton("❌ لغو"))

    return markup


def admin_subcategory_menu(category):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

    buttons = [
        types.KeyboardButton(name)
        for name in SUBCATEGORIES[category].values()
    ]

    for i in range(0, len(buttons), 2):
        markup.row(*buttons[i:i + 2])

    markup.row(types.KeyboardButton("❌ لغو"))

    return markup


def customer_subcategory_menu(category):
    markup = types.InlineKeyboardMarkup()

    row = []

    for key, name in SUBCATEGORIES[category].items():

        row.append(
            types.InlineKeyboardButton(
                name,
                callback_data=f"s|{category}|{key}"
            )
        )

        if len(row) == 2:
            markup.row(*row)
            row = []

    if row:
        markup.row(*row)

    return markup


@bot.message_handler(commands=["start"])
def start(message):

    user_states.pop(message.from_user.id, None)

    bot.send_message(
        message.chat.id,
        "🟡 به فروشگاه موبایل پاسارگاد خوش آمدید\n\n"
        "👇 دسته‌بندی مورد نظر خود را انتخاب کنید:",
        reply_markup=main_menu(message.from_user.id),
    )


def get_products(category, subcategory=None):

    if subcategory is None:

        cursor.execute(
            """
            SELECT id,name,description,photo_id
            FROM products
            WHERE category=?
            ORDER BY id DESC
            """,
            (category,),
        )

    else:

        cursor.execute(
            """
            SELECT id,name,description,photo_id
            FROM products
            WHERE category=? AND subcategory=?
            ORDER BY id DESC
            """,
            (category, subcategory),
        )

    return cursor.fetchall()


def show_product(chat_id, category, subcategory=None, index=0):

    products = get_products(category, subcategory)

    if not products:

        bot.send_message(
            chat_id,
            "❌ در این بخش هنوز محصولی ثبت نشده است."
        )

        return

    index %= len(products)

    product = products[index]

    caption = (
        f"🛍 {product[1]}\n\n"
        f"📝 {product[2]}\n\n"
        f"📦 محصول {index + 1} از {len(products)}"
    )

    sub = subcategory if subcategory else "-"

    markup = types.InlineKeyboardMarkup()

    markup.row(

        types.InlineKeyboardButton(
            "⬅️ قبلی",
            callback_data=f"p|{category}|{sub}|{index - 1}"
        ),

        types.InlineKeyboardButton(
            "بعدی ➡️",
            callback_data=f"p|{category}|{sub}|{index + 1}"
        )
    )

    bot.send_photo(
        chat_id,
        product[3],
        caption=caption,
        reply_markup=markup
    )


@bot.callback_query_handler(
    func=lambda call: call.data.startswith("s|")
)
def select_subcategory(call):

    _, category, subcategory = call.data.split("|", 2)

    bot.answer_callback_query(call.id)

    show_product(
        call.message.chat.id,
        category,
        subcategory,
        0
    )


@bot.callback_query_handler(
    func=lambda call: call.data.startswith("p|")
)
def navigate_products(call):

    _, category, subcategory, index = call.data.split("|", 3)

    if subcategory == "-":
        subcategory = None

    try:
        index = int(index)
    except ValueError:
        return

    try:
        bot.delete_message(
            call.message.chat.id,
            call.message.message_id
        )
    except Exception:
        pass

    show_product(
        call.message.chat.id,
        category,
        subcategory,
        index
    )

    bot.answer_callback_query(call.id)


@bot.callback_query_handler(
    func=lambda call: call.data.startswith("d|")
)
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
        "✅ محصول حذف شد"
    )

    try:

        bot.edit_message_text(
            "✅ محصول با موفقیت حذف شد.",
            call.message.chat.id,
            call.message.message_id
        )

    except Exception:
        pass


@bot.callback_query_handler(
    func=lambda call: call.data.startswith("e|")
)
def edit_product(call):

    if call.from_user.id != ADMIN_ID:
        return

    product_id = int(call.data.split("|")[1])

    user_states[call.from_user.id] = {
        "action": "edit",
        "step": "name",
        "product_id": product_id
    }

    bot.answer_callback_query(call.id)

    bot.send_message(
        call.message.chat.id,
        "✏️ اسم جدید محصول را بفرست:"
    )


@bot.message_handler(content_types=["text"])
def text_handler(message):

    text = message.text.strip()

    user_id = message.from_user.id
    chat_id = message.chat.id

    if text == "❌ لغو":

        user_states.pop(user_id, None)

        bot.send_message(
            chat_id,
            "✅ عملیات لغو شد.",
            reply_markup=main_menu(user_id)
        )

        return

    if text == "🏠 منوی اصلی":

        user_states.pop(user_id, None)

        bot.send_message(
            chat_id,
            "🏠 منوی اصلی",
            reply_markup=main_menu(user_id)
        )

        return

    if user_id in user_states:

        state = user_states[user_id]

        if state["action"] == "add":

            if state["step"] == "category":

                if text not in CATEGORY_BY_NAME:

                    bot.send_message(
                        chat_id,
                        "❌ دسته را از دکمه‌ها انتخاب کن."
                    )

                    return

                category = CATEGORY_BY_NAME[text]

                state["category"] = category

                if category in SUBCATEGORIES:

                    state["step"] = "subcategory"

                    bot.send_message(
                        chat_id,
                        "📂 زیر‌دسته را انتخاب کن:",
                        reply_markup=admin_subcategory_menu(
                            category
                        )
                    )

                else:

                    state["subcategory"] = None
                    state["step"] = "name"

                    bot.send_message(
                        chat_id,
                        "✏️ اسم محصول را بفرست:"
                    )

                return

            if state["step"] == "subcategory":

                category = state["category"]

                lookup = SUBCATEGORY_BY_NAME[category]

                if text not in lookup:

                    bot.send_message(
                        chat_id,
                        "❌ زیر‌دسته را از دکمه‌ها انتخاب کن."
                    )

                    return

                state["subcategory"] = lookup[text]

                state["step"] = "name"

                bot.send_message(
                    chat_id,
                    "✏️ اسم محصول را بفرست:",
                    reply_markup=types.ReplyKeyboardRemove()
                )

                return

            if state["step"] == "name":

                state["name"] = text

                state["step"] = "description"

                bot.send_message(
                    chat_id,
                    "📝 مشخصات محصول را بفرست:"
                )

                return

            if state["step"] == "description":

                state["description"] = text

                state["step"] = "photo"

                bot.send_message(
                    chat_id,
                    "🖼 حالا عکس محصول را بفرست:"
                )

                return

        if state["action"] == "edit":

            if state["step"] == "name":

                state["name"] = text

                state["step"] = "description"

                bot.send_message(
                    chat_id,
                    "📝 مشخصات جدید محصول را بفرست:"
                )

                return

            if state["step"] == "description":

                cursor.execute(
                    """
                    UPDATE products
                    SET name=?,description=?
                    WHERE id=?
                    """,
                    (
                        state["name"],
                        text,
                        state["product_id"]
                    )
                )

                db.commit()

                user_states.pop(user_id, None)

                bot.send_message(
                    chat_id,
                    "✅ محصول ویرایش شد.",
                    reply_markup=admin_menu()
                )

                return

        if state["action"] == "support":

            cursor.execute(
                """
                INSERT INTO settings(key,value)
                VALUES('support',?)
                ON CONFLICT(key)
                DO UPDATE SET value=excluded.value
                """,
                (text,)
            )

            db.commit()

            user_states.pop(user_id, None)

            bot.send_message(
                chat_id,
                "✅ اطلاعات پشتیبانی ذخیره شد.",
                reply_markup=admin_menu()
            )

            return

    if text == "🔐 پنل مدیریت":

        if user_id != ADMIN_ID:

            bot.send_message(
                chat_id,
                "⛔ دسترسی ندارید."
            )

            return

        bot.send_message(
            chat_id,
            "🔐 پنل مدیریت موبایل پاسارگاد",
            reply_markup=admin_menu()
        )

        return

    if text == "➕ افزودن محصول" and user_id == ADMIN_ID:

        user_states[user_id] = {
            "action": "add",
            "step": "category"
        }

        bot.send_message(
            chat_id,
            "📂 دسته محصول را انتخاب کن:",
            reply_markup=category_menu()
        )

        return

    if text == "🗑 حذف محصول" and user_id == ADMIN_ID:

        cursor.execute(
            "SELECT id,name FROM products ORDER BY id DESC"
        )

        products = cursor.fetchall()

        if not products:

            bot.send_message(
                chat_id,
                "❌ محصولی وجود ندارد."
            )

            return

        markup = types.InlineKeyboardMarkup()

        for product_id, name in products:

            markup.row(
                types.InlineKeyboardButton(
                    f"🗑 {name}",
                    callback_data=f"d|{product_id}"
                )
            )

        bot.send_message(
            chat_id,
            "محصول مورد نظر را انتخاب کن:",
            reply_markup=markup
        )

        return

    if text == "✏️ ویرایش محصول" and user_id == ADMIN_ID:

        cursor.execute(
            "SELECT id,name FROM products ORDER BY id DESC"
        )

        products = cursor.fetchall()

        if not products:

            bot.send_message(
                chat_id,
                "❌ محصولی وجود ندارد."
            )

            return

        markup = types.InlineKeyboardMarkup()

        for product_id, name in products:

            markup.row(
                types.InlineKeyboardButton(
                    f"✏️ {name}",
                    callback_data=f"e|{product_id}"
                )
            )

        bot.send_message(
            chat_id,
            "محصول مورد نظر را انتخاب کن:",
            reply_markup=markup
        )

        return

    if (
        text == "☎️ ویرایش پشتیبانی"
        and user_id == ADMIN_ID
    ):

        user_states[user_id] = {
            "action": "support"
        }

        bot.send_message(
            chat_id,
            "☎️ اطلاعات جدید پشتیبانی را بفرست:"
        )

        return

    if text == "🛟 پشتیبانی":

        cursor.execute(
            "SELECT value FROM settings WHERE key='support'"
        )

        result = cursor.fetchone()

        support = (
            result[0]
            if result
            else "☎️ اطلاعات پشتیبانی ثبت نشده است."
        )

        bot.send_message(
            chat_id,
            support
        )

        return

    if text in CATEGORY_BY_NAME:

        category = CATEGORY_BY_NAME[text]

        if category in SUBCATEGORIES:

            bot.send_message(
                chat_id,
                "👇 بخش مورد نظر را انتخاب کنید:",
                reply_markup=customer_subcategory_menu(
                    category
                )
            )

        else:

            show_product(
                chat_id,
                category
            )

        return


@bot.message_handler(content_types=["photo"])
def photo_handler(message):

    user_id = message.from_user.id

    state = user_states.get(user_id)

    if not state:
        return

    if (
        state.get("action") == "add"
        and state.get("step") == "photo"
    ):

        photo_id = message.photo[-1].file_id

        cursor.execute(
            """
            INSERT INTO products
            (
                category,
                subcategory,
                name,
                description,
                photo_id
            )
            VALUES(?,?,?,?,?)
            """,
            (
                state["category"],
                state.get("subcategory"),
                state["name"],
                state["description"],
                photo_id
            )
        )

        db.commit()

        user_states.pop(user_id, None)

        bot.send_message(
            message.chat.id,
            "✅ محصول با موفقیت اضافه شد.",
            reply_markup=admin_menu()
        )


print("Mobile Pasargad Bot is running...")

bot.infinity_polling(
    timeout=60,
    long_polling_timeout=60,
    skip_pending=True
)