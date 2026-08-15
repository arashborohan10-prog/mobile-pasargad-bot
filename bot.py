import os
import json
import base64
import sqlite3
import urllib.request
import urllib.error

import telebot
from telebot import types

BOT_TOKEN = os.getenv("BOT_TOKEN")
AI_API_KEY = os.getenv("ONE_XAI_API_KEY") or os.getenv("OPENAI_API_KEY")

AI_BASE_URL = "https://1xai.ir/v1/chat/completions"
AI_MODEL = "gpt-4o-mini"

ADMIN_ID = 1040416634

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

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
    cursor.execute(
        "ALTER TABLE products ADD COLUMN subcategory TEXT"
    )

cursor.execute("""
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
)
""")

cursor.execute(
    "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
    (
        "support",
        "☎️ اطلاعات پشتیبانی هنوز تنظیم نشده است."
    )
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

CATEGORY_BY_NAME = {
    name: key
    for key, name in CATEGORIES.items()
}

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
        "aux_35": "جک 3.5mm (AUX)",
    },

    "airpod": {
        "apple": "Apple",
        "samsung": "Samsung",
        "xiaomi": "Xiaomi",
        "qcy": "QCY",
        "ldnio": "LDNIO",
        "power_max": "Power Max",
        "anker": "Anker",
        "haylou": "Haylou",
        "other": "متفرقه",
    },

    "memory": {
        "memory_card": "💳 کارت حافظه (Memory Card)",
        "usb_flash": "💾 فلش مموری (USB Flash)",
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
    category: {
        name: key
        for key, name in values.items()
    }
    for category, values in SUBCATEGORIES.items()
}


def main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(
        resize_keyboard=True
    )

    buttons = [
        types.KeyboardButton(name)
        for name in CATEGORIES.values()
    ]

    for i in range(0, len(buttons), 2):
        markup.row(*buttons[i:i + 2])

    markup.row(
        types.KeyboardButton("🛟 پشتیبانی")
    )

    if user_id == ADMIN_ID:
        markup.row(
            types.KeyboardButton("🔐 پنل مدیریت")
        )

    return markup


def admin_menu():
    markup = types.ReplyKeyboardMarkup(
        resize_keyboard=True
    )

    markup.row(
        types.KeyboardButton("🤖 افزودن هوشمند"),
        types.KeyboardButton("➕ افزودن دستی"),
    )

    markup.row(
        types.KeyboardButton("✏️ ویرایش محصول"),
        types.KeyboardButton("🗑 حذف محصول"),
    )

    markup.row(
        types.KeyboardButton("☎️ ویرایش پشتیبانی")
    )

    markup.row(
        types.KeyboardButton("🏠 منوی اصلی")
    )

    return markup


def category_menu():
    markup = types.ReplyKeyboardMarkup(
        resize_keyboard=True
    )

    buttons = [
        types.KeyboardButton(name)
        for name in CATEGORIES.values()
    ]

    for i in range(0, len(buttons), 2):
        markup.row(*buttons[i:i + 2])

    markup.row(
        types.KeyboardButton("❌ لغو")
    )

    return markup


def admin_subcategory_menu(category):
    markup = types.ReplyKeyboardMarkup(
        resize_keyboard=True
    )

    buttons = [
        types.KeyboardButton(name)
        for name in SUBCATEGORIES.get(
            category,
            {}
        ).values()
    ]

    for i in range(0, len(buttons), 2):
        markup.row(*buttons[i:i + 2])

    markup.row(
        types.KeyboardButton("❌ لغو")
    )

    return markup


def customer_subcategory_menu(category):
    markup = types.InlineKeyboardMarkup()

    row = []

    for key, name in SUBCATEGORIES.get(
        category,
        {}
    ).items():

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


def get_products(category, subcategory=None):

    if subcategory is None:

        cursor.execute(
            """
            SELECT
                id,
                name,
                description,
                photo_id
            FROM products
            WHERE category=?
            ORDER BY id DESC
            """,
            (category,)
        )

    else:

        cursor.execute(
            """
            SELECT
                id,
                name,
                description,
                photo_id
            FROM products
            WHERE category=?
            AND subcategory=?
            ORDER BY id DESC
            """,
            (
                category,
                subcategory
            )
        )

    return cursor.fetchall()


def save_product(
    category,
    subcategory,
    name,
    description,
    photo_id
):

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
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            category,
            subcategory,
            name,
            description,
            photo_id
        )
    )

    db.commit()


def show_product(
    chat_id,
    category,
    subcategory=None,
    index=0
):

    products = get_products(
        category,
        subcategory
    )

    if not products:

        bot.send_message(
            chat_id,
            "❌ در این بخش هنوز محصولی ثبت نشده است."
        )

        return

    index %= len(products)

    product = products[index]

    name = product[1]
    description = product[2]
    photo_id = product[3]

    caption = (
        f"🛍 {name}\n\n"
        f"📝 {description}\n\n"
        f"📦 محصول {index + 1} از {len(products)}"
    )

    sub_value = (
        subcategory
        if subcategory is not None
        else "-"
    )

    markup = types.InlineKeyboardMarkup()

    markup.row(

        types.InlineKeyboardButton(
            "⬅️ قبلی",
            callback_data=(
                f"p|{category}|"
                f"{sub_value}|"
                f"{index - 1}"
            )
        ),

        types.InlineKeyboardButton(
            "بعدی ➡️",
            callback_data=(
                f"p|{category}|"
                f"{sub_value}|"
                f"{index + 1}"
            )
        )

    )

    bot.send_photo(
        chat_id,
        photo_id,
        caption=caption,
        reply_markup=markup
    )


def download_photo_base64(photo_id):

    file_info = bot.get_file(photo_id)

    photo_bytes = bot.download_file(
        file_info.file_path
    )

    encoded = base64.b64encode(
        photo_bytes
    ).decode("utf-8")

    return encoded


def clean_json_text(text):

    text = (text or "").strip()

    if text.startswith("```"):

        text = text.replace(
            "```json",
            "",
            1
        )

        text = text.replace(
            "```",
            ""
        ).strip()

    first = text.find("{")
    last = text.rfind("}")

    if (
        first != -1
        and last != -1
        and last > first
    ):

        text = text[first:last + 1]

    return text


def normalize_ai_result(data):

    category = str(
        data.get(
            "category",
            "other"
        )
    ).strip().lower()

    if category not in CATEGORIES:
        category = "other"

    subcategory = data.get(
        "subcategory"
    )

    if subcategory is not None:

        subcategory = str(
            subcategory
        ).strip().lower()

    allowed_subs = SUBCATEGORIES.get(
        category
    )

    if allowed_subs:

        if subcategory not in allowed_subs:
            subcategory = None

    else:

        subcategory = None

    name = str(
        data.get(
            "name",
            ""
        )
    ).strip()

    description = str(
        data.get(
            "description",
            ""
        )
    ).strip()

    confidence = str(
        data.get(
            "confidence",
            "نامشخص"
        )
    ).strip()

    if not name:
        name = "مدل نامشخص"

    if not description:
        description = (
            "مشخصات نیاز به بررسی دارد."
        )

    return {
        "category": category,
        "subcategory": subcategory,
        "name": name,
        "description": description,
        "confidence": confidence
    }


def analyze_product_with_ai(
    photo_id,
    corrected_model=None
):

    if not AI_API_KEY:

        raise RuntimeError(
            "کلید هوش مصنوعی تنظیم نشده است."
        )

    image_base64 = download_photo_base64(
        photo_id
    )

    categories_json = json.dumps(
        {
            key: {
                "title": CATEGORIES[key],
                "subcategories": (
                    SUBCATEGORIES.get(
                        key,
                        {}
                    )
                )
            }
            for key in CATEGORIES
        },
        ensure_ascii=False
    )

    correction_text = ""

    if corrected_model:

        correction_text = (
            "\nادمین مدل درست را مشخص کرده است: "
            f"{corrected_model}\n"
            "همین مدل را مبنا قرار بده "
            "و نام مدل را تغییر نده."
        )

    prompt = f"""
تو دستیار ثبت محصول فروشگاه موبایل پاسارگاد هستی.

یک عکس محصول برایت ارسال شده است.
محصول را تا حد ممکن دقیق تشخیص بده.
{correction_text}

قوانین:

1- قیمت ننویس.

2- درباره حافظه، رم، رنگ، گارانتی
یا مشخصاتی که مطمئن نیستی حدس نزن.

3- توضیحات فارسی، کوتاه،
مرتب و مناسب مشتری باشد.

4- فقط مشخصات مطمئن همان مدل
را بنویس.

5- category و subcategory فقط
از کلیدهای مجاز پایین باشند.

6- اگر مدل دقیق معلوم نیست،
confidence را «نیاز به تأیید» بگذار.

7- اگر دسته زیر‌دسته ندارد،
subcategory را null بگذار.

8- فقط JSON خام بده.

دسته‌ها:

{categories_json}

فرمت خروجی:

{{
"name":"نام دقیق محصول",
"description":"مشخصات کوتاه فارسی",
"category":"کلید دسته",
"subcategory":"کلید زیر دسته یا null",
"confidence":"بالا یا متوسط یا نیاز به تأیید"
}}
""".strip()

    payload = {
        "model": AI_MODEL,
        "temperature": 0.1,
        "max_tokens": 700,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": (
                                "data:image/jpeg;base64,"
                                + image_base64
                            ),
                            "detail": "low"
                        }
                    }
                ]
            }
        ]
    }

    body = json.dumps(
        payload
    ).encode("utf-8")

    request = urllib.request.Request(
        AI_BASE_URL,
        data=body,
        headers={
            "Authorization": (
                f"Bearer {AI_API_KEY}"
            ),
            "Content-Type": (
                "application/json"
            )
        },
        method="POST"
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=90
        ) as response:

            result = json.loads(
                response.read().decode(
                    "utf-8"
                )
            )

    except urllib.error.HTTPError as error:

        error_text = error.read().decode(
            "utf-8",
            errors="replace"
        )

        raise RuntimeError(
            "خطای سرویس هوش مصنوعی "
            f"({error.code}): "
            f"{error_text[:500]}"
        )

    except urllib.error.URLError as error:

        raise RuntimeError(
            "اتصال به هوش مصنوعی برقرار نشد: "
            f"{error}"
        )

    try:

        answer = (
            result["choices"][0]
            ["message"]["content"]
        )

    except Exception:

        raise RuntimeError(
            "پاسخ هوش مصنوعی قابل خواندن نبود."
        )

    parsed = json.loads(
        clean_json_text(answer)
    )

    return normalize_ai_result(
        parsed
    )


def ai_preview_text(result):

    category_title = CATEGORIES.get(
        result["category"],
        result["category"]
    )

    subcategory_title = "ندارد"

    if result.get("subcategory"):

        subcategory_title = (
            SUBCATEGORIES
            .get(
                result["category"],
                {}
            )
            .get(
                result["subcategory"],
                result["subcategory"]
            )
        )

    return (
        "🤖 پیش‌نمایش هوشمند محصول\n\n"

        f"📌 نام: "
        f"{result['name']}\n\n"

        f"📝 مشخصات:\n"
        f"{result['description']}\n\n"

        f"📂 دسته: "
        f"{category_title}\n"

        f"📁 زیر‌دسته: "
        f"{subcategory_title}\n"

        f"🎯 اطمینان تشخیص: "
        f"{result['confidence']}\n\n"

        "اگر همه‌چیز درست است تأیید کن.\n"
        "اگر مدل اشتباه است اصلاح مدل را بزن."
    )


def send_ai_preview(
    chat_id,
    user_id
):

    state = user_states.get(
        user_id
    )

    if (
        not state
        or "ai_result" not in state
    ):

        bot.send_message(
            chat_id,
            "❌ پیش‌نمایش پیدا نشد."
        )

        return

    result = state["ai_result"]

    markup = types.InlineKeyboardMarkup()

    markup.row(
        types.InlineKeyboardButton(
            "✅ تأیید و ذخیره",
            callback_data="ai|save"
        )
    )

    markup.row(

        types.InlineKeyboardButton(
            "✏️ اصلاح مدل",
            callback_data="ai|correct"
        ),

        types.InlineKeyboardButton(
            "❌ لغو",
            callback_data="ai|cancel"
        )

    )

    bot.send_photo(
        chat_id,
        state["photo_id"],
        caption=ai_preview_text(
            result
        ),
        reply_markup=markup
    )


@bot.message_handler(
    commands=["start"]
)
def start(message):

    user_states.pop(
        message.from_user.id,
        None
    )

    bot.send_message(
        message.chat.id,
        "🟡 به فروشگاه موبایل پاسارگاد خوش آمدید\n\n"
        "👇 دسته‌بندی مورد نظر خود را انتخاب کنید:",
        reply_markup=main_menu(
            message.from_user.id
        )
    )


@bot.callback_query_handler(
    func=lambda call:
    call.data.startswith("s|")
)
def subcategory_callback(call):

    parts = call.data.split(
        "|",
        2
    )

    if len(parts) != 3:

        bot.answer_callback_query(
            call.id,
            "❌ خطا"
        )

        return

    category = parts[1]
    subcategory = parts[2]

    if (
        category not in SUBCATEGORIES
        or subcategory
        not in SUBCATEGORIES[category]
    ):

        bot.answer_callback_query(
            call.id,
            "❌ دسته‌بندی نامعتبر است."
        )

        return

    bot.answer_callback_query(
        call.id
    )

    show_product(
        call.message.chat.id,
        category,
        subcategory,
        0
    )


@bot.callback_query_handler(
    func=lambda call:
    call.data.startswith("p|")
)
def product_navigation(call):

    parts = call.data.split(
        "|",
        3
    )

    if len(parts) != 4:

        bot.answer_callback_query(
            call.id,
            "❌ خطا"
        )

        return

    category = parts[1]

    subcategory = (
        None
        if parts[2] == "-"
        else parts[2]
    )

    try:

        index = int(
            parts[3]
        )

    except ValueError:

        bot.answer_callback_query(
            call.id,
            "❌ خطا"
        )

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

    bot.answer_callback_query(
        call.id
    )


@bot.callback_query_handler(
    func=lambda call:
    call.data.startswith("ai|")
)
def ai_callback(call):

    if call.from_user.id != ADMIN_ID:

        bot.answer_callback_query(
            call.id,
            "⛔ دسترسی ندارید."
        )

        return

    action = call.data.split(
        "|",
        1
    )[1]

    user_id = call.from_user.id
    chat_id = call.message.chat.id

    state = user_states.get(
        user_id
    )

    if action == "cancel":

        user_states.pop(
            user_id,
            None
        )

        bot.answer_callback_query(
            call.id,
            "لغو شد"
        )

        bot.send_message(
            chat_id,
            "✅ عملیات لغو شد.",
            reply_markup=admin_menu()
        )

        return

    if (
        not state
        or state.get("action")
        != "ai_add"
    ):

        bot.answer_callback_query(
            call.id,
            "❌ اطلاعات عملیات پیدا نشد."
        )

        return

    if action == "correct":

        state["step"] = (
            "correct_model"
        )

        bot.answer_callback_query(
            call.id
        )

        bot.send_message(
            chat_id,
            "✏️ اسم دقیق مدل را بنویس.\n\n"
            "مثلاً:\n"
            "Samsung Galaxy A56 5G"
        )

        return

    if action == "save":

        result = state.get(
            "ai_result"
        )

        if not result:

            bot.answer_callback_query(
                call.id,
                "❌ اطلاعات محصول پیدا نشد."
            )

            return

        if (
            result["category"]
            in SUBCATEGORIES
            and not result.get(
                "subcategory"
            )
        ):

            state["step"] = (
                "choose_ai_subcategory"
            )

            bot.answer_callback_query(
                call.id,
                "زیر‌دسته را انتخاب کن"
            )

            bot.send_message(
                chat_id,
                "📁 زیر‌دسته محصول مشخص نیست.\n"
                "لطفاً انتخاب کن:",
                reply_markup=(
                    admin_subcategory_menu(
                        result["category"]
                    )
                )
            )

            return

        save_product(
            result["category"],
            result.get(
                "subcategory"
            ),
            result["name"],
            result["description"],
            state["photo_id"]
        )

        user_states.pop(
            user_id,
            None
        )

        bot.answer_callback_query(
            call.id,
            "✅ ذخیره شد"
        )

        bot.send_message(
            chat_id,
            "✅ محصول هوشمند با موفقیت ذخیره شد.",
            reply_markup=admin_menu()
        )

        return


@bot.callback_query_handler(
    func=lambda call:
    call.data.startswith("d|")
)
def delete_callback(call):

    if call.from_user.id != ADMIN_ID:

        bot.answer_callback_query(
            call.id,
            "⛔ دسترسی ندارید."
        )

        return

    try:

        product_id = int(
            call.data.split(
                "|",
                1
            )[1]
        )

    except ValueError:

        bot.answer_callback_query(
            call.id,
            "❌ خطا"
        )

        return

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
    func=lambda call:
    call.data.startswith("e|")
)
def edit_callback(call):

    if call.from_user.id != ADMIN_ID:

        bot.answer_callback_query(
            call.id,
            "⛔ دسترسی ندارید."
        )

        return

    try:

        product_id = int(
            call.data.split(
                "|",
                1
            )[1]
        )

    except ValueError:

        bot.answer_callback_query(
            call.id,
            "❌ خطا"
        )

        return

    cursor.execute(
        "SELECT id FROM products WHERE id=?",
        (product_id,)
    )

    if not cursor.fetchone():

        bot.answer_callback_query(
            call.id,
            "❌ محصول پیدا نشد."
        )

        return

    user_states[
        call.from_user.id
    ] = {
        "action": "edit",
        "step": "name",
        "product_id": product_id
    }

    bot.answer_callback_query(
        call.id
    )

    bot.send_message(
        call.message.chat.id,
        "✏️ اسم جدید محصول را بفرست:"
    )


@bot.message_handler(
    content_types=["text"]
)
def text_handler(message):

    text = message.text.strip()

    user_id = message.from_user.id
    chat_id = message.chat.id

    if text == "❌ لغو":

        user_states.pop(
            user_id,
            None
        )

        bot.send_message(
            chat_id,
            "✅ عملیات لغو شد.",
            reply_markup=main_menu(
                user_id
            )
        )

        return

    if text == "🏠 منوی اصلی":

        user_states.pop(
            user_id,
            None
        )

        bot.send_message(
            chat_id,
            "🏠 منوی اصلی",
            reply_markup=main_menu(
                user_id
            )
        )

        return

    if user_id in user_states:

        state = user_states[
            user_id
        ]

        if (
            state.get("action")
            == "ai_add"
        ):

            if (
                state.get("step")
                == "correct_model"
            ):

                corrected_model = text

                bot.send_message(
                    chat_id,
                    "🤖 مدل اصلاح شد.\n"
                    "دارم مشخصات را دوباره آماده می‌کنم..."
                )

                try:

                    result = (
                        analyze_product_with_ai(
                            state["photo_id"],
                            corrected_model
                        )
                    )

                    result["name"] = (
                        corrected_model
                    )

                    state["ai_result"] = (
                        result
                    )

                    state["step"] = (
                        "preview"
                    )

                    send_ai_preview(
                        chat_id,
                        user_id
                    )

                except Exception as error:

                    state["step"] = (
                        "correct_model"
                    )

                    bot.send_message(
                        chat_id,
                        "❌ هوش مصنوعی خطا داد.\n\n"
                        f"{str(error)[:700]}\n\n"
                        "اسم مدل را دوباره بفرست "
                        "یا «❌ لغو» را بزن."
                    )

                return

            if (
                state.get("step")
                == "choose_ai_subcategory"
            ):

                category = (
                    state["ai_result"]
                    ["category"]
                )

                lookup = (
                    SUBCATEGORY_BY_NAME
                    .get(
                        category,
                        {}
                    )
                )

                if text not in lookup:

                    bot.send_message(
                        chat_id,
                        "❌ زیر‌دسته را از دکمه‌ها انتخاب کن."
                    )

                    return

                state["ai_result"][
                    "subcategory"
                ] = lookup[text]

                result = (
                    state["ai_result"]
                )

                save_product(
                    result["category"],
                    result["subcategory"],
                    result["name"],
                    result["description"],
                    state["photo_id"]
                )

                user_states.pop(
                    user_id,
                    None
                )

                bot.send_message(
                    chat_id,
                    "✅ محصول هوشمند با موفقیت ذخیره شد.",
                    reply_markup=admin_menu()
                )

                return

        if (
            state.get("action")
            == "manual_add"
        ):

            if (
                state.get("step")
                == "category"
            ):

                if text not in CATEGORY_BY_NAME:

                    bot.send_message(
                        chat_id,
                        "❌ دسته را از دکمه‌ها انتخاب کن."
                    )

                    return

                category = (
                    CATEGORY_BY_NAME[
                        text
                    ]
                )

                state["category"] = (
                    category
                )

                if category in SUBCATEGORIES:

                    state["step"] = (
                        "subcategory"
                    )

                    bot.send_message(
                        chat_id,
                        "📂 زیر‌دسته محصول را انتخاب کن:",
                        reply_markup=(
                            admin_subcategory_menu(
                                category
                            )
                        )
                    )

                else:

                    state["subcategory"] = (
                        None
                    )

                    state["step"] = (
                        "name"
                    )

                    bot.send_message(
                        chat_id,
                        "✏️ اسم محصول را بفرست:",
                        reply_markup=(
                            types.ReplyKeyboardRemove()
                        )
                    )

                return

            if (
                state.get("step")
                == "subcategory"
            ):

                category = (
                    state["category"]
                )

                lookup = (
                    SUBCATEGORY_BY_NAME
                    .get(
                        category,
                        {}
                    )
                )

                if text not in lookup:

                    bot.send_message(
                        chat_id,
                        "❌ زیر‌دسته را از دکمه‌ها انتخاب کن."
                    )

                    return

                state["subcategory"] = (
                    lookup[text]
                )

                state["step"] = (
                    "name"
                )

                bot.send_message(
                    chat_id,
                    "✏️ اسم محصول را بفرست:",
                    reply_markup=(
                        types.ReplyKeyboardRemove()
                    )
                )

                return

            if (
                state.get("step")
                == "name"
            ):

                state["name"] = text

                state["step"] = (
                    "description"
                )

                bot.send_message(
                    chat_id,
                    "📝 مشخصات محصول را بفرست:"
                )

                return

            if (
                state.get("step")
                == "description"
            ):

                state["description"] = (
                    text
                )

                state["step"] = (
                    "photo"
                )

                bot.send_message(
                    chat_id,
                    "🖼 حالا عکس محصول را بفرست:"
                )

                return

        if (
            state.get("action")
            == "edit"
        ):

            if (
                state.get("step")
                == "name"
            ):

                state["name"] = text

                state["step"] = (
                    "description"
                )

                bot.send_message(
                    chat_id,
                    "📝 مشخصات جدید محصول را بفرست:"
                )

                return

            if (
                state.get("step")
                == "description"
            ):

                cursor.execute(
                    """
                    UPDATE products
                    SET
                        name=?,
                        description=?
                    WHERE id=?
                    """,
                    (
                        state["name"],
                        text,
                        state["product_id"]
                    )
                )

                db.commit()

                user_states.pop(
                    user_id,
                    None
                )

                bot.send_message(
                    chat_id,
                    "✅ محصول با موفقیت ویرایش شد.",
                    reply_markup=admin_menu()
                )

                return

        if (
            state.get("action")
            == "support"
        ):

            cursor.execute(
                """
                INSERT INTO settings
                (key, value)
                VALUES ('support', ?)
                ON CONFLICT(key)
                DO UPDATE SET
                value=excluded.value
                """,
                (text,)
            )

            db.commit()

            user_states.pop(
                user_id,
                None
            )

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
                "⛔ دسترسی به پنل مدیریت ندارید."
            )

            return

        bot.send_message(
            chat_id,
            "🔐 پنل مدیریت موبایل پاسارگاد",
            reply_markup=admin_menu()
        )

        return

    if (
        text == "🤖 افزودن هوشمند"
        and user_id == ADMIN_ID
    ):

        if not AI_API_KEY:

            bot.send_message(
                chat_id,
                "❌ کلید API هوش مصنوعی تنظیم نشده است."
            )

            return

        user_states[user_id] = {
            "action": "ai_add",
            "step": "photo"
        }

        cancel_markup = (
            types.ReplyKeyboardMarkup(
                resize_keyboard=True
            )
        )

        cancel_markup.row(
            types.KeyboardButton(
                "❌ لغو"
            )
        )

        bot.send_message(
            chat_id,
            "🤖 عکس واضح محصول را بفرست.\n\n"
            "بهتر است اسم مدل روی جعبه یا محصول "
            "در عکس مشخص باشد.\n\n"
            "قبل از ذخیره حتماً پیش‌نمایش می‌بینی.",
            reply_markup=cancel_markup
        )

        return

    if (
        text in (
            "➕ افزودن دستی",
            "➕ افزودن محصول"
        )
        and user_id == ADMIN_ID
    ):

        user_states[user_id] = {
            "action": "manual_add",
            "step": "category"
        }

        bot.send_message(
            chat_id,
            "📂 دسته محصول را انتخاب کن:",
            reply_markup=category_menu()
        )

        return

    if (
        text == "🗑 حذف محصول"
        and user_id == ADMIN_ID
    ):

        cursor.execute(
            """
            SELECT
                id,
                name
            FROM products
            ORDER BY id DESC
            """
        )

        products = cursor.fetchall()

        if not products:

            bot.send_message(
                chat_id,
                "❌ محصولی برای حذف وجود ندارد."
            )

            return

        markup = (
            types.InlineKeyboardMarkup()
        )

        for product_id, name in products:

            markup.row(
                types.InlineKeyboardButton(
                    f"🗑 {name}",
                    callback_data=(
                        f"d|{product_id}"
                    )
                )
            )

        bot.send_message(
            chat_id,
            "محصول مورد نظر برای حذف را انتخاب کن:",
            reply_markup=markup
        )

        return

    if (
        text == "✏️ ویرایش محصول"
        and user_id == ADMIN_ID
    ):

        cursor.execute(
            """
            SELECT
                id,
                name
            FROM products
            ORDER BY id DESC
            """
        )

        products = cursor.fetchall()

        if not products:

            bot.send_message(
                chat_id,
                "❌ محصولی برای ویرایش وجود ندارد."
            )

            return

        markup = (
            types.InlineKeyboardMarkup()
        )

        for product_id, name in products:

            markup.row(
                types.InlineKeyboardButton(
                    f"✏️ {name}",
                    callback_data=(
                        f"e|{product_id}"
                    )
                )
            )

        bot.send_message(
            chat_id,
            "محصول مورد نظر برای ویرایش را انتخاب کن:",
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

        cancel_markup = (
            types.ReplyKeyboardMarkup(
                resize_keyboard=True
            )
        )

        cancel_markup.row(
            types.KeyboardButton(
                "❌ لغو"
            )
        )

        bot.send_message(
            chat_id,
            "☎️ اطلاعات جدید پشتیبانی را بفرست.\n\n"
            "مثلاً:\n"
            "☎️ تماس: 09...\n"
            "💬 واتساپ: 09...\n"
            "📷 اینستاگرام: @...\n"
            "📍 آدرس: ...",
            reply_markup=cancel_markup
        )

        return

    if text == "🛟 پشتیبانی":

        cursor.execute(
            """
            SELECT value
            FROM settings
            WHERE key='support'
            """
        )

        result = cursor.fetchone()

        support_text = (
            result[0]
            if result
            else (
                "☎️ اطلاعات پشتیبانی "
                "هنوز تنظیم نشده است."
            )
        )

        bot.send_message(
            chat_id,
            support_text
        )

        return

    if text in CATEGORY_BY_NAME:

        category = (
            CATEGORY_BY_NAME[text]
        )

        if category in SUBCATEGORIES:

            bot.send_message(
                chat_id,
                "👇 بخش مورد نظر را انتخاب کنید:",
                reply_markup=(
                    customer_subcategory_menu(
                        category
                    )
                )
            )

        else:

            show_product(
                chat_id,
                category
            )

        return


@bot.message_handler(
    content_types=["photo"]
)
def photo_handler(message):

    user_id = message.from_user.id
    chat_id = message.chat.id

    state = user_states.get(
        user_id
    )

    if not state:
        return

    if (
        state.get("action")
        == "ai_add"
        and state.get("step")
        == "photo"
    ):

        photo_id = (
            message.photo[-1].file_id
        )

        state["photo_id"] = (
            photo_id
        )

        state["step"] = (
            "analyzing"
        )

        bot.send_message(
            chat_id,
            "🤖 عکس دریافت شد.\n"
            "دارم مدل و مشخصات محصول را بررسی می‌کنم..."
        )

        try:

            result = (
                analyze_product_with_ai(
                    photo_id
                )
            )

            state["ai_result"] = (
                result
            )

            state["step"] = (
                "preview"
            )

            send_ai_preview(
                chat_id,
                user_id
            )

        except Exception as error:

            state["step"] = (
                "photo"
            )

            bot.send_message(
                chat_id,
                "❌ هوش مصنوعی نتوانست عکس را بررسی کند.\n\n"
                f"{str(error)[:700]}\n\n"
                "یک عکس واضح‌تر بفرست "
                "یا «❌ لغو» را بزن."
            )

        return

    if (
        state.get("action")
        == "manual_add"
        and state.get("step")
        == "photo"
    ):

        photo_id = (
            message.photo[-1].file_id
        )

        save_product(
            state["category"],
            state.get(
                "subcategory"
            ),
            state["name"],
            state["description"],
            photo_id
        )

        user_states.pop(
            user_id,
            None
        )

        bot.send_message(
            chat_id,
            "✅ محصول با موفقیت اضافه شد.",
            reply_markup=admin_menu()
        )

        return


print(
    "Mobile Pasargad Bot is running..."
)

bot.infinity_polling(
    timeout=60,
    long_polling_timeout=60,
    skip_pending=True
)