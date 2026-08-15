import os
import json
import base64
import html
import sqlite3
import threading
import urllib.request
import urllib.error

import telebot
from telebot import types

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = os.getenv("ADMIN_ID", "1040416634").strip()
AI_KEY = os.getenv("OPENAI_API_KEY", "").strip()
AI_MODEL = os.getenv("AI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
AI_URL = "https://1xai.ir/v1/chat/completions"
DB_FILE = os.getenv("DB_FILE", "mobile_pasargad.db").strip() or "mobile_pasargad.db"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing in Railway Variables")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
db_lock = threading.RLock()
user_state = {}

CATEGORIES = [
    ("📱 موبایل", "mobile"),
    ("🎮 گجت", "gadget"),
    ("💆 ماساژور", "massager"),
    ("🔌 کابل و شارژر", "cable_charger"),
    ("🎧 هدفون", "headphone"),
    ("🎶 هندزفری", "handsfree"),
    ("🎧 ایرپاد", "airpods"),
    ("💾 رم و فلش", "ram_flash"),
    ("📱 هولدر", "holder"),
    ("📶 سیمکارت", "simcard"),
    ("🔋 پاوربانک", "powerbank"),
    ("📦 متفرقه", "other"),
]

SUBMENUS = {
    "mobile": [
        ("🍎 Apple", "apple"),
        ("📱 Samsung", "samsung"),
        ("🟠 Xiaomi", "xiaomi"),
        ("📱 Vocal", "vocal"),
        ("🔷 Nokia", "nokia"),
        ("🟢 Realme", "realme"),
    ],

    "cable_charger": [
        ("🍎 Lightning", "lightning"),
        ("🔌 Type-C", "type_c"),
        ("🔌 Micro USB", "micro_usb"),
    ],

    "airpods": [
        ("🎧 Power Max", "power_max"),
        ("📱 Samsung", "samsung"),
        ("🍎 Apple", "apple"),
        ("🟠 Xiaomi", "xiaomi"),
        ("🎧 Haylou", "haylou"),
        ("🎧 Anker", "anker"),
        ("🔌 LDNIO", "ldnio"),
        ("📦 متفرقه", "other"),
    ],

    "handsfree": [
        ("🎧 سرسوزنی 3.5mm", "jack_35"),
        ("🔌 Type-C", "type_c"),
    ],

    "ram_flash": [
        ("💾 رم", "ram"),
        ("🔌 فلش", "flash"),
    ],

    "simcard": [
        ("📶 همراه اول", "mci"),
        ("📶 ایرانسل", "irancell"),
        ("📶 رایتل", "rightel"),
        ("📶 سامانتل", "samantel"),
        ("📶 شاتل", "shatel"),
        ("📶 آپتل", "aptel"),
    ],
}

CAT_BY_TEXT = dict(CATEGORIES)
CAT_LABEL = {key: label for label, key in CATEGORIES}
VALID_CATEGORIES = set(CAT_LABEL)

SUB_LABEL = {
    category: {key: label for label, key in items}
    for category, items in SUBMENUS.items()
}

VALID_SUBS = {
    category: set(mapping)
    for category, mapping in SUB_LABEL.items()
}


def db():
    conn = sqlite3.connect(
        DB_FILE,
        check_same_thread=False
    )
    conn.row_factory = sqlite3.Row
    return conn


def infer_mobile_brand(name):
    n = (name or "").lower()

    if any(x in n for x in [
        "iphone",
        "آیفون",
        "apple",
        "اپل"
    ]):
        return "apple"

    if any(x in n for x in [
        "samsung",
        "سامسونگ",
        "galaxy",
        "گلکسی"
    ]):
        return "samsung"

    if any(x in n for x in [
        "xiaomi",
        "شیائومی",
        "شیامی",
        "redmi",
        "ردمی",
        "poco",
        "پوکو"
    ]):
        return "xiaomi"

    if any(x in n for x in [
        "vocal",
        "وکال"
    ]):
        return "vocal"

    if any(x in n for x in [
        "nokia",
        "نوکیا"
    ]):
        return "nokia"

    if any(x in n for x in [
        "realme",
        "ریلمی"
    ]):
        return "realme"

    return ""


def init_db():

    with db_lock:

        conn = db()

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                subcategory TEXT DEFAULT '',
                name TEXT NOT NULL,
                specs TEXT DEFAULT '',
                photo_id TEXT DEFAULT '',
                brand TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT DEFAULT ''
            )
            """
        )

        columns = {
            r["name"]
            for r in conn.execute(
                "PRAGMA table_info(products)"
            ).fetchall()
        }

        if "subcategory" not in columns:
            conn.execute(
                """
                ALTER TABLE products
                ADD COLUMN subcategory TEXT DEFAULT ''
                """
            )

        if "brand" not in columns:
            conn.execute(
                """
                ALTER TABLE products
                ADD COLUMN brand TEXT DEFAULT ''
                """
            )

        rows = conn.execute(
            """
            SELECT
                id,
                category,
                name,
                subcategory,
                brand
            FROM products
            """
        ).fetchall()

        for row in rows:

            category = (
                row["category"] or ""
            ).strip()

            sub = (
                row["subcategory"] or ""
            ).strip().lower()

            brand = (
                row["brand"] or ""
            ).strip().lower()

            if category == "mobile" and not sub:

                if brand in (
                    "poco",
                    "redmi"
                ):
                    brand = "xiaomi"

                if brand not in VALID_SUBS.get(
                    "mobile",
                    set()
                ):
                    brand = infer_mobile_brand(
                        row["name"]
                    )

                if brand:
                    conn.execute(
                        """
                        UPDATE products
                        SET
                            subcategory=?,
                            brand=?
                        WHERE id=?
                        """,
                        (
                            brand,
                            brand,
                            row["id"]
                        )
                    )

            elif (
                category == "mobile"
                and
                sub in (
                    "poco",
                    "redmi"
                )
            ):

                conn.execute(
                    """
                    UPDATE products
                    SET
                        subcategory='xiaomi',
                        brand='xiaomi'
                    WHERE id=?
                    """,
                    (
                        row["id"],
                    )
                )

        conn.commit()
        conn.close()


def is_admin(user_id):
    return str(user_id) == ADMIN_ID


def get_setting(
    key,
    default=""
):

    with db_lock:

        conn = db()

        row = conn.execute(
            """
            SELECT value
            FROM settings
            WHERE key=?
            """,
            (
                key,
            )
        ).fetchone()

        conn.close()

    return (
        row["value"]
        if row
        else default
    )


def set_setting(
    key,
    value
):

    with db_lock:

        conn = db()

        conn.execute(
            """
            INSERT INTO settings(
                key,
                value
            )
            VALUES(
                ?,
                ?
            )
            ON CONFLICT(key)
            DO UPDATE
            SET value=excluded.value
            """,
            (
                key,
                value
            )
        )

        conn.commit()
        conn.close()


def add_product(
    category,
    subcategory,
    name,
    specs,
    photo_id=""
):

    if category not in VALID_CATEGORIES:
        category = "other"

    if category in SUBMENUS:

        if subcategory not in VALID_SUBS[category]:

            if category == "mobile":
                subcategory = infer_mobile_brand(
                    name
                )

            else:
                subcategory = ""

    else:
        subcategory = ""

    brand = (
        subcategory
        if category == "mobile"
        else ""
    )

    with db_lock:

        conn = db()

        conn.execute(
            """
            INSERT INTO products(
                category,
                subcategory,
                name,
                specs,
                photo_id,
                brand
            )
            VALUES(
                ?,
                ?,
                ?,
                ?,
                ?,
                ?
            )
            """,
            (
                category,
                subcategory or "",
                (name or "").strip(),
                (specs or "").strip(),
                photo_id or "",
                brand
            )
        )

        conn.commit()
        conn.close()


def get_product(product_id):

    with db_lock:

        conn = db()

        row = conn.execute(
            """
            SELECT *
            FROM products
            WHERE id=?
            """,
            (
                product_id,
            )
        ).fetchone()

        conn.close()

    return row


def all_products():

    with db_lock:

        conn = db()

        rows = conn.execute(
            """
            SELECT *
            FROM products
            ORDER BY
                category,
                subcategory,
                id DESC
            """
        ).fetchall()

        conn.close()

    return rows


def products_for(
    category,
    subcategory=""
):

    with db_lock:

        conn = db()

        if category in SUBMENUS:

            rows = conn.execute(
                """
                SELECT *
                FROM products
                WHERE
                    category=?
                    AND
                    subcategory=?
                ORDER BY id ASC
                """,
                (
                    category,
                    subcategory
                )
            ).fetchall()

        else:

            rows = conn.execute(
                """
                SELECT *
                FROM products
                WHERE category=?
                ORDER BY id ASC
                """,
                (
                    category,
                )
            ).fetchall()

        conn.close()

    return rows


def update_product(
    product_id,
    field,
    value
):

    if field not in {
        "name",
        "specs",
        "photo_id"
    }:
        return False

    with db_lock:

        conn = db()

        conn.execute(
            f"""
            UPDATE products
            SET {field}=?
            WHERE id=?
            """,
            (
                value,
                product_id
            )
        )

        if field == "name":

            row = conn.execute(
                """
                SELECT category
                FROM products
                WHERE id=?
                """,
                (
                    product_id,
                )
            ).fetchone()

            if (
                row
                and
                row["category"] == "mobile"
            ):

                inferred = infer_mobile_brand(
                    value
                )

                if inferred:

                    conn.execute(
                        """
                        UPDATE products
                        SET
                            subcategory=?,
                            brand=?
                        WHERE id=?
                        """,
                        (
                            inferred,
                            inferred,
                            product_id
                        )
                    )

        conn.commit()
        conn.close()

    return True


def delete_product(product_id):

    with db_lock:

        conn = db()

        conn.execute(
            """
            DELETE FROM products
            WHERE id=?
            """,
            (
                product_id,
            )
        )

        conn.commit()
        conn.close()


def main_keyboard(user_id):

    kb = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        row_width=2
    )

    for i in range(
        0,
        len(CATEGORIES),
        2
    ):

        row = [
            types.KeyboardButton(
                CATEGORIES[i][0]
            )
        ]

        if i + 1 < len(CATEGORIES):

            row.append(
                types.KeyboardButton(
                    CATEGORIES[
                        i + 1
                    ][0]
                )
            )

        kb.row(*row)

    kb.row(
        types.KeyboardButton(
            "📞 پشتیبانی"
        )
    )

    if is_admin(user_id):

        kb.row(
            types.KeyboardButton(
                "⚙️ پنل مدیریت"
            )
        )

    return kb


def admin_keyboard():

    kb = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        row_width=2
    )

    kb.row(
        "➕ افزودن محصول",
        "🤖 افزودن با هوش مصنوعی"
    )

    kb.row(
        "✏️ ویرایش محصول",
        "🗑 حذف محصول"
    )

    kb.row(
        "📋 لیست محصولات",
        "📞 ویرایش پشتیبانی"
    )

    kb.row(
        "⬅️ بازگشت به منو"
    )

    return kb


def category_keyboard(prefix):

    kb = types.InlineKeyboardMarkup(
        row_width=2
    )

    buttons = [
        types.InlineKeyboardButton(
            label,
            callback_data=f"{prefix}:{key}"
        )
        for label, key
        in CATEGORIES
    ]

    for i in range(
        0,
        len(buttons),
        2
    ):

        kb.row(
            *buttons[
                i:i + 2
            ]
        )

    kb.row(
        types.InlineKeyboardButton(
            "❌ لغو",
            callback_data="cancel"
        )
    )

    return kb


def submenu_keyboard(
    category,
    prefix
):

    kb = types.InlineKeyboardMarkup(
        row_width=2
    )

    items = SUBMENUS.get(
        category,
        []
    )

    buttons = [
        types.InlineKeyboardButton(
            label,
            callback_data=(
                f"{prefix}:"
                f"{category}:"
                f"{key}"
            )
        )
        for label, key
        in items
    ]

    for i in range(
        0,
        len(buttons),
        2
    ):

        kb.row(
            *buttons[
                i:i + 2
            ]
        )

    if prefix == "shopsub":

        kb.row(
            types.InlineKeyboardButton(
                "⬅️ منوی اصلی",
                callback_data="shop:home"
            )
        )

    else:

        kb.row(
            types.InlineKeyboardButton(
                "❌ لغو",
                callback_data="cancel"
            )
        )

    return kb


def product_nav_keyboard(
    category,
    subcategory,
    index,
    total
):

    kb = types.InlineKeyboardMarkup(
        row_width=3
    )

    row = []

    if index > 0:

        row.append(
            types.InlineKeyboardButton(
                "⬅️ قبلی",
                callback_data=(
                    f"nav:"
                    f"{category}:"
                    f"{subcategory or '-'}:"
                    f"{index - 1}"
                )
            )
        )

    row.append(
        types.InlineKeyboardButton(
            f"{index + 1}/{total}",
            callback_data="noop"
        )
    )

    if index < total - 1:

        row.append(
            types.InlineKeyboardButton(
                "بعدی ➡️",
                callback_data=(
                    f"nav:"
                    f"{category}:"
                    f"{subcategory or '-'}:"
                    f"{index + 1}"
                )
            )
        )

    kb.row(*row)

    if category in SUBMENUS:

        kb.row(
            types.InlineKeyboardButton(
                "🔙 برگشت به زیرمنو",
                callback_data=(
                    f"shopmenu:"
                    f"{category}"
                )
            )
        )

    return kb


def show_submenu(
    chat_id,
    category
):

    bot.send_message(
        chat_id,
        (
            f"<b>"
            f"{html.escape(CAT_LABEL.get(category, category))}"
            f"</b>\n"
            "گزینه موردنظر را انتخاب کنید:"
        ),
        reply_markup=submenu_keyboard(
            category,
            "shopsub"
        )
    )


def send_product(
    chat_id,
    category,
    subcategory="",
    index=0
):

    rows = products_for(
        category,
        subcategory
    )

    if not rows:

        label = CAT_LABEL.get(
            category,
            category
        )

        if category in SUBMENUS:

            sublabel = SUB_LABEL.get(
                category,
                {}
            ).get(
                subcategory,
                subcategory
            )

            bot.send_message(
                chat_id,
                (
                    "فعلاً محصولی در "
                    f"<b>{html.escape(sublabel)}</b> "
                    "ثبت نشده است."
                )
            )

        else:

            bot.send_message(
                chat_id,
                (
                    "فعلاً محصولی در "
                    f"<b>{html.escape(label)}</b> "
                    "ثبت نشده است."
                )
            )

        return

    index = max(
        0,
        min(
            int(index),
            len(rows) - 1
        )
    )

    p = rows[index]

    text = (
        f"<b>📦 "
        f"{html.escape(p['name'] or 'محصول')}"
        f"</b>\n\n"
        f"{html.escape(p['specs'] or 'مشخصات ثبت نشده است.')}"
    )

    markup = product_nav_keyboard(
        category,
        subcategory,
        index,
        len(rows)
    )

    if p["photo_id"]:

        bot.send_photo(
            chat_id,
            p["photo_id"],
            caption=text,
            reply_markup=markup
        )

    else:

        bot.send_message(
            chat_id,
            text,
            reply_markup=markup
        )


def support_text():

    return get_setting(
        "support_text",
        (
            "<b>📞 پشتیبانی موبایل پاسارگاد</b>"
            "\n\n"
            "اطلاعات پشتیبانی هنوز ثبت نشده است."
        )
    )


def send_product_selector(
    chat_id,
    mode
):

    rows = all_products()

    if not rows:

        bot.send_message(
            chat_id,
            "هنوز محصولی ثبت نشده است."
        )

        return

    kb = types.InlineKeyboardMarkup(
        row_width=1
    )

    for p in rows[:100]:

        cat = CAT_LABEL.get(
            p["category"],
            p["category"]
        )

        sub = ""

        if (
            p["category"] in SUBMENUS
            and
            p["subcategory"]
        ):

            sublabel = SUB_LABEL.get(
                p["category"],
                {}
            ).get(
                p["subcategory"],
                p["subcategory"]
            )

            sub = f" | {sublabel}"

        title = (
            f"{cat}"
            f"{sub}"
            " | "
            f"{p['name']}"
        )

        kb.add(
            types.InlineKeyboardButton(
                title[:60],
                callback_data=(
                    f"{mode}:"
                    f"{p['id']}"
                )
            )
        )

    bot.send_message(
        chat_id,
        "محصول را انتخاب کن:",
        reply_markup=kb
    )


def clean_ai_json(text):

    content = (
        text or ""
    ).strip()

    if content.startswith("```"):

        content = (
            content
            .replace(
                "```json",
                ""
            )
            .replace(
                "```",
                ""
            )
            .strip()
        )

    start = content.find("{")
    end = content.rfind("}")

    if (
        start != -1
        and
        end != -1
        and
        end > start
    ):

        content = content[
            start:end + 1
        ]

    return json.loads(
        content
    )


def normalize_ai_result(result):

    category = str(
        result.get(
            "category",
            "other"
        )
    ).strip().lower()

    if category not in VALID_CATEGORIES:
        category = "other"

    subcategory = str(
        result.get(
            "subcategory",
            ""
        )
    ).strip().lower()

    name = str(
        result.get(
            "name",
            ""
        )
    ).strip() or "محصول جدید"

    specs = str(
        result.get(
            "specs",
            ""
        )
    ).strip()

    if category == "mobile":

        if subcategory in (
            "poco",
            "redmi"
        ):
            subcategory = "xiaomi"

        if (
            subcategory
            not in VALID_SUBS["mobile"]
        ):
            subcategory = infer_mobile_brand(
                name
            )

    elif category in SUBMENUS:

        if (
            subcategory
            not in VALID_SUBS[category]
        ):
            subcategory = ""

    else:
        subcategory = ""

    return {
        "category": category,
        "subcategory": subcategory,
        "name": name,
        "specs": specs
    }


def ai_from_photo(image_bytes):

    if not AI_KEY:

        raise RuntimeError(
            "OPENAI_API_KEY در Railway Variables تنظیم نشده است."
        )

    encoded = base64.b64encode(
        image_bytes
    ).decode(
        "utf-8"
    )

    data_url = (
        "data:image/jpeg;base64,"
        +
        encoded
    )

    prompt = """
این عکس مربوط به یکی از محصولات فروشگاه موبایل و لوازم جانبی است.

از روی عکس و جعبه محصول، نام و مدل را تا حد ممکن دقیق تشخیص بده.

فقط JSON معتبر برگردان و هیچ متن دیگری ننویس.

category فقط یکی از این‌ها باشد:
mobile
gadget
massager
cable_charger
headphone
handsfree
airpods
ram_flash
holder
simcard
powerbank
other

subcategory فقط بر اساس category از لیست زیر باشد:

mobile:
apple
samsung
xiaomi
vocal
nokia
realme

cable_charger:
lightning
type_c
micro_usb

airpods:
power_max
samsung
apple
xiaomi
haylou
anker
ldnio
other

handsfree:
jack_35
type_c

ram_flash:
ram
flash

simcard:
mci
irancell
rightel
samantel
shatel
aptel

برای categoryهای دیگر subcategory خالی باشد.

Redmi و POCO را زیر xiaomi قرار بده.

specs را فارسی، کوتاه و کاربردی در 3 تا 6 خط بنویس.

قیمت ننویس.
گارانتی ننویس.
رنگ ننویس.
موجودی را حدس نزن.

چیزی که از تصویر مطمئن نیستی نساز.

فرمت دقیق:

{
  "category": "mobile",
  "subcategory": "samsung",
  "name": "نام دقیق محصول",
  "specs": "مشخصات کوتاه فارسی"
}
""".strip()

    payload = {

        "model": AI_MODEL,

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
                            "url": data_url
                        }
                    }
                ]
            }
        ],

        "temperature": 0.1,

        "max_tokens": 800
    }

    req = urllib.request.Request(

        AI_URL,

        data=json.dumps(
            payload
        ).encode(
            "utf-8"
        ),

        headers={
            "Authorization":
                f"Bearer {AI_KEY}",

            "Content-Type":
                "application/json"
        },

        method="POST"
    )

    try:

        with urllib.request.urlopen(
            req,
            timeout=75
        ) as response:

            raw = (
                response
                .read()
                .decode(
                    "utf-8",
                    errors="replace"
                )
            )

    except urllib.error.HTTPError as error:

        details = (
            error
            .read()
            .decode(
                "utf-8",
                errors="replace"
            )
        )

        raise RuntimeError(
            f"1xAi HTTP {error.code}: "
            f"{details[:250]}"
        )

    except urllib.error.URLError as error:

        raise RuntimeError(
            "خطای اتصال به 1xAi: "
            f"{error.reason}"
        )

    data = json.loads(raw)

    content = (
        data[
            "choices"
        ][0][
            "message"
        ][
            "content"
        ]
    )

    return normalize_ai_result(
        clean_ai_json(
            content
        )
    )


@bot.message_handler(
    commands=["start"]
)
def start(message):

    user_state.pop(
        message.from_user.id,
        None
    )

    bot.send_message(
        message.chat.id,
        (
            "سلام 👋\n\n"
            "<b>به ربات موبایل پاسارگاد خوش آمدید.</b>\n"
            "دسته موردنظر را انتخاب کنید:"
        ),
        reply_markup=main_keyboard(
            message.from_user.id
        )
    )


@bot.message_handler(
    commands=["id"]
)
def show_id(message):

    bot.send_message(
        message.chat.id,
        (
            "ID شما: "
            f"<code>{message.from_user.id}</code>"
        )
    )


@bot.message_handler(
    commands=["admin"]
)
def admin_cmd(message):

    if is_admin(
        message.from_user.id
    ):

        user_state.pop(
            message.from_user.id,
            None
        )

        bot.send_message(
            message.chat.id,
            "⚙️ <b>پنل مدیریت</b>",
            reply_markup=admin_keyboard()
        )

    else:

        bot.send_message(
            message.chat.id,
            "⛔ دسترسی ندارید."
        )


@bot.callback_query_handler(
    func=lambda c:
        c.data == "noop"
)
def cb_noop(call):
    bot.answer_callback_query(
        call.id
    )


@bot.callback_query_handler(
    func=lambda c:
        c.data == "shop:home"
)
def cb_home(call):

    bot.answer_callback_query(
        call.id
    )

    bot.send_message(
        call.message.chat.id,
        "منوی اصلی:",
        reply_markup=main_keyboard(
            call.from_user.id
        )
    )


@bot.callback_query_handler(
    func=lambda c:
        c.data.startswith(
            "shopmenu:"
        )
)
def cb_shopmenu(call):

    category = (
        call.data.split(
            ":",
            1
        )[1]
    )

    bot.answer_callback_query(
        call.id
    )

    if category in SUBMENUS:

        show_submenu(
            call.message.chat.id,
            category
        )


@bot.callback_query_handler(
    func=lambda c:
        c.data.startswith(
            "shopsub:"
        )
)
def cb_shopsub(call):

    try:

        (
            _,
            category,
            subcategory
        ) = call.data.split(
            ":",
            2
        )

    except ValueError:
        return

    bot.answer_callback_query(
        call.id
    )

    if (
        category in SUBMENUS
        and
        subcategory in VALID_SUBS[
            category
        ]
    ):

        send_product(
            call.message.chat.id,
            category,
            subcategory,
            0
        )


@bot.callback_query_handler(
    func=lambda c:
        c.data.startswith(
            "nav:"
        )
)
def cb_nav(call):

    try:

        (
            _,
            category,
            subcategory,
            index
        ) = call.data.split(
            ":",
            3
        )

        if subcategory == "-":
            subcategory = ""

        index = int(
            index
        )

        bot.answer_callback_query(
            call.id
        )

        try:

            bot.delete_message(
                call.message.chat.id,
                call.message.message_id
            )

        except Exception:
            pass

        send_product(
            call.message.chat.id,
            category,
            subcategory,
            index
        )

    except Exception:

        bot.answer_callback_query(
            call.id,
            "خطا"
        )


@bot.callback_query_handler(
    func=lambda c:
        c.data == "cancel"
)
def cb_cancel(call):

    user_state.pop(
        call.from_user.id,
        None
    )

    bot.answer_callback_query(
        call.id,
        "لغو شد"
    )

    if is_admin(
        call.from_user.id
    ):

        bot.send_message(
            call.message.chat.id,
            "عملیات لغو شد.",
            reply_markup=admin_keyboard()
        )


@bot.callback_query_handler(
    func=lambda c:
        c.data.startswith(
            "addcat:"
        )
)
def cb_addcat(call):

    if not is_admin(
        call.from_user.id
    ):

        bot.answer_callback_query(
            call.id,
            "دسترسی ندارید",
            show_alert=True
        )

        return

    state = user_state.get(
        call.from_user.id
    )

    if (
        not state
        or
        state.get("action")
        !=
        "add"
    ):

        bot.answer_callback_query(
            call.id,
            "عملیات منقضی شده",
            show_alert=True
        )

        return

    category = (
        call.data.split(
            ":",
            1
        )[1]
    )

    if (
        category
        not in VALID_CATEGORIES
    ):
        return

    state["category"] = category

    bot.answer_callback_query(
        call.id
    )

    if category in SUBMENUS:

        state["step"] = "subcategory"

        bot.send_message(
            call.message.chat.id,
            "زیرگروه را انتخاب کن:",
            reply_markup=submenu_keyboard(
                category,
                "addsub"
            )
        )

    else:

        state["subcategory"] = ""
        state["step"] = "name"

        bot.send_message(
            call.message.chat.id,
            "نام محصول را بفرست."
        )


@bot.callback_query_handler(
    func=lambda c:
        c.data.startswith(
            "addsub:"
        )
)
def cb_addsub(call):

    if not is_admin(
        call.from_user.id
    ):
        return

    state = user_state.get(
        call.from_user.id
    )

    try:

        (
            _,
            category,
            subcategory
        ) = call.data.split(
            ":",
            2
        )

    except ValueError:
        return

    if (
        not state
        or
        state.get("action")
        !=
        "add"
        or
        state.get("step")
        !=
        "subcategory"
        or
        state.get("category")
        !=
        category
        or
        category
        not in SUBMENUS
        or
        subcategory
        not in VALID_SUBS[
            category
        ]
    ):

        bot.answer_callback_query(
            call.id,
            "عملیات منقضی شده",
            show_alert=True
        )

        return

    state["subcategory"] = subcategory
    state["step"] = "name"

    bot.answer_callback_query(
        call.id
    )

    bot.send_message(
        call.message.chat.id,
        "نام محصول را بفرست."
    )


@bot.callback_query_handler(
    func=lambda c:
        c.data.startswith(
            "edit:"
        )
)
def cb_edit(call):

    if not is_admin(
        call.from_user.id
    ):
        return

    try:

        product_id = int(
            call.data.split(
                ":",
                1
            )[1]
        )

    except ValueError:
        return

    p = get_product(
        product_id
    )

    if not p:

        bot.answer_callback_query(
            call.id,
            "محصول پیدا نشد"
        )

        return

    user_state[
        call.from_user.id
    ] = {
        "action": "edit",
        "step": "field",
        "product_id": product_id
    }

    kb = types.InlineKeyboardMarkup(
        row_width=2
    )

    kb.row(
        types.InlineKeyboardButton(
            "✏️ نام",
            callback_data="editfield:name"
        ),

        types.InlineKeyboardButton(
            "📝 مشخصات",
            callback_data="editfield:specs"
        )
    )

    kb.row(
        types.InlineKeyboardButton(
            "🖼 عکس",
            callback_data="editfield:photo_id"
        )
    )

    kb.row(
        types.InlineKeyboardButton(
            "❌ لغو",
            callback_data="cancel"
        )
    )

    bot.answer_callback_query(
        call.id
    )

    bot.send_message(
        call.message.chat.id,
        (
            "ویرایش "
            f"<b>{html.escape(p['name'])}</b>"
            "\nچه چیزی تغییر کند؟"
        ),
        reply_markup=kb
    )


@bot.callback_query_handler(
    func=lambda c:
        c.data.startswith(
            "editfield:"
        )
)
def cb_editfield(call):

    if not is_admin(
        call.from_user.id
    ):
        return

    state = user_state.get(
        call.from_user.id
    )

    field = (
        call.data.split(
            ":",
            1
        )[1]
    )

    if (
        not state
        or
        state.get("action")
        !=
        "edit"
        or
        field
        not in {
            "name",
            "specs",
            "photo_id"
        }
    ):

        bot.answer_callback_query(
            call.id,
            "عملیات منقضی شده",
            show_alert=True
        )

        return

    state["field"] = field
    state["step"] = "value"

    bot.answer_callback_query(
        call.id
    )

    if field == "photo_id":

        bot.send_message(
            call.message.chat.id,
            "عکس جدید را بفرست."
        )

    elif field == "name":

        bot.send_message(
            call.message.chat.id,
            "نام جدید را بفرست."
        )

    else:

        bot.send_message(
            call.message.chat.id,
            "مشخصات جدید را بفرست."
        )


@bot.callback_query_handler(
    func=lambda c:
        c.data.startswith(
            "delete:"
        )
)
def cb_delete(call):

    if not is_admin(
        call.from_user.id
    ):
        return

    try:

        product_id = int(
            call.data.split(
                ":",
                1
            )[1]
        )

    except ValueError:
        return

    p = get_product(
        product_id
    )

    if not p:

        bot.answer_callback_query(
            call.id,
            "محصول پیدا نشد"
        )

        return

    kb = types.InlineKeyboardMarkup(
        row_width=2
    )

    kb.row(
        types.InlineKeyboardButton(
            "✅ حذف شود",
            callback_data=(
                f"delok:"
                f"{product_id}"
            )
        ),

        types.InlineKeyboardButton(
            "❌ لغو",
            callback_data="cancel"
        )
    )

    bot.answer_callback_query(
        call.id
    )

    bot.send_message(
        call.message.chat.id,
        (
            "مطمئنی "
            f"<b>{html.escape(p['name'])}</b> "
            "حذف شود؟"
        ),
        reply_markup=kb
    )


@bot.callback_query_handler(
    func=lambda c:
        c.data.startswith(
            "delok:"
        )
)
def cb_delok(call):

    if not is_admin(
        call.from_user.id
    ):
        return

    try:

        product_id = int(
            call.data.split(
                ":",
                1
            )[1]
        )

    except ValueError:
        return

    delete_product(
        product_id
    )

    bot.answer_callback_query(
        call.id,
        "حذف شد"
    )

    bot.send_message(
        call.message.chat.id,
        "✅ محصول حذف شد.",
        reply_markup=admin_keyboard()
    )


@bot.callback_query_handler(
    func=lambda c:
        c.data in (
            "ai:save",
            "ai:cancel"
        )
)
def cb_ai_confirm(call):

    if not is_admin(
        call.from_user.id
    ):
        return

    state = user_state.get(
        call.from_user.id
    )

    if call.data == "ai:cancel":

        user_state.pop(
            call.from_user.id,
            None
        )

        bot.answer_callback_query(
            call.id,
            "لغو شد"
        )

        bot.send_message(
            call.message.chat.id,
            "لغو شد.",
            reply_markup=admin_keyboard()
        )

        return

    if (
        not state
        or
        state.get("action")
        !=
        "ai_add"
        or
        not state.get(
            "ai_result"
        )
    ):

        bot.answer_callback_query(
            call.id,
            "اطلاعات پیدا نشد",
            show_alert=True
        )

        return

    result = state[
        "ai_result"
    ]

    if (
        result["category"]
        in SUBMENUS
        and
        result["subcategory"]
        not in VALID_SUBS[
            result["category"]
        ]
    ):

        bot.answer_callback_query(
            call.id,
            (
                "زیرگروه دقیق تشخیص داده نشد؛ "
                "دستی اضافه کن."
            ),
            show_alert=True
        )

        return

    add_product(
        result["category"],
        result["subcategory"],
        result["name"],
        result["specs"],
        state.get(
            "photo_id",
            ""
        )
    )

    user_state.pop(
        call.from_user.id,
        None
    )

    bot.answer_callback_query(
        call.id,
        "ذخیره شد"
    )

    bot.send_message(
        call.message.chat.id,
        "✅ محصول ذخیره شد.",
        reply_markup=admin_keyboard()
    )


@bot.message_handler(
    content_types=["photo"]
)
def photo_handler(message):

    uid = message.from_user.id

    if not is_admin(uid):
        return

    state = user_state.get(
        uid
    )

    if not state:

        bot.send_message(
            message.chat.id,
            (
                "اول از پنل مدیریت "
                "یک عملیات را انتخاب کن."
            )
        )

        return

    if (
        state.get("action")
        ==
        "ai_add"
        and
        state.get("step")
        ==
        "photo"
    ):

        try:

            bot.send_message(
                message.chat.id,
                (
                    "🤖 عکس دریافت شد؛ "
                    "در حال بررسی..."
                )
            )

            file_info = bot.get_file(
                message.photo[-1].file_id
            )

            image_bytes = bot.download_file(
                file_info.file_path
            )

            result = ai_from_photo(
                image_bytes
            )

            state["ai_result"] = result
            state["photo_id"] = (
                message.photo[-1].file_id
            )
            state["step"] = "confirm"

            cat_label = CAT_LABEL.get(
                result["category"],
                result["category"]
            )

            sub_label = ""

            if (
                result["category"]
                in SUBMENUS
            ):

                sub_label = (
                    SUB_LABEL.get(
                        result["category"],
                        {}
                    ).get(
                        result["subcategory"],
                        "نامشخص"
                    )
                )

                sub_label = (
                    "\n🏷 زیرگروه: "
                    f"{html.escape(sub_label)}"
                )

            text = (
                "<b>🤖 نتیجه هوش مصنوعی</b>"
                "\n\n"
                "📂 دسته: "
                f"{html.escape(cat_label)}"
                f"{sub_label}"
                "\n"
                "📦 نام: "
                f"{html.escape(result['name'])}"
                "\n\n"
                "📝 مشخصات:\n"
                f"{html.escape(result['specs'] or 'ثبت نشده')}"
                "\n\n"
                "اگر درست است ذخیره را بزن."
            )

            kb = types.InlineKeyboardMarkup(
                row_width=2
            )

            kb.row(
                types.InlineKeyboardButton(
                    "✅ ذخیره",
                    callback_data="ai:save"
                ),

                types.InlineKeyboardButton(
                    "❌ لغو",
                    callback_data="ai:cancel"
                )
            )

            bot.send_message(
                message.chat.id,
                text,
                reply_markup=kb
            )

        except Exception as error:

            bot.send_message(
                message.chat.id,
                (
                    "❌ خطای هوش مصنوعی:\n"
                    "<code>"
                    f"{html.escape(str(error)[:350])}"
                    "</code>\n\n"
                    "دوباره عکس بفرست یا دستی اضافه کن."
                )
            )

        return

    if (
        state.get("action")
        ==
        "edit"
        and
        state.get("step")
        ==
        "value"
        and
        state.get("field")
        ==
        "photo_id"
    ):

        update_product(
            state["product_id"],
            "photo_id",
            message.photo[-1].file_id
        )

        user_state.pop(
            uid,
            None
        )

        bot.send_message(
            message.chat.id,
            "✅ عکس ویرایش شد.",
            reply_markup=admin_keyboard()
        )

        return

    if (
        state.get("action")
        ==
        "add"
        and
        state.get("step")
        ==
        "photo"
    ):

        add_product(
            state["category"],
            state.get(
                "subcategory",
                ""
            ),
            state["name"],
            state["specs"],
            message.photo[-1].file_id
        )

        user_state.pop(
            uid,
            None
        )

        bot.send_message(
            message.chat.id,
            "✅ محصول ذخیره شد.",
            reply_markup=admin_keyboard()
        )

        return

    bot.send_message(
        message.chat.id,
        "در این مرحله منتظر عکس نیستم."
    )


@bot.message_handler(
    content_types=["text"],
    func=lambda m: True
)
def text_handler(message):

    uid = message.from_user.id
    text = (
        message.text or ""
    ).strip()

    if text in CAT_BY_TEXT:

        user_state.pop(
            uid,
            None
        )

        category = CAT_BY_TEXT[
            text
        ]

        if category in SUBMENUS:

            show_submenu(
                message.chat.id,
                category
            )

        else:

            send_product(
                message.chat.id,
                category,
                "",
                0
            )

        return

    if text == "📞 پشتیبانی":

        user_state.pop(
            uid,
            None
        )

        bot.send_message(
            message.chat.id,
            support_text(),
            reply_markup=main_keyboard(
                uid
            )
        )

        return

    if text == "⬅️ بازگشت به منو":

        user_state.pop(
            uid,
            None
        )

        bot.send_message(
            message.chat.id,
            "منوی اصلی:",
            reply_markup=main_keyboard(
                uid
            )
        )

        return

    if text == "⚙️ پنل مدیریت":

        user_state.pop(
            uid,
            None
        )

        if is_admin(uid):

            bot.send_message(
                message.chat.id,
                "⚙️ <b>پنل مدیریت</b>",
                reply_markup=admin_keyboard()
            )

        else:

            bot.send_message(
                message.chat.id,
                "⛔ دسترسی ندارید."
            )

        return

    if not is_admin(uid):

        bot.send_message(
            message.chat.id,
            (
                "از دکمه‌های منو "
                "استفاده کنید."
            ),
            reply_markup=main_keyboard(
                uid
            )
        )

        return

    if text == "➕ افزودن محصول":

        user_state[
            uid
        ] = {
            "action": "add",
            "step": "category"
        }

        bot.send_message(
            message.chat.id,
            "دسته محصول را انتخاب کن:",
            reply_markup=category_keyboard(
                "addcat"
            )
        )

        return

    if text == "🤖 افزودن با هوش مصنوعی":

        if not AI_KEY:

            bot.send_message(
                message.chat.id,
                (
                    "❌ کلید 1xAi پیدا نشد. "
                    "متغیر "
                    "<code>OPENAI_API_KEY</code> "
                    "باید در Railway تنظیم باشد."
                )
            )

            return

        user_state[
            uid
        ] = {
            "action": "ai_add",
            "step": "photo"
        }

        bot.send_message(
            message.chat.id,
            (
                "🤖 یک عکس واضح از محصول یا جعبه بفرست.\n"
                "نام، دسته، زیرگروه و مشخصات را تشخیص می‌دهم "
                "و قبل از ذخیره به تو نشان می‌دهم."
            )
        )

        return

    if text == "✏️ ویرایش محصول":

        user_state.pop(
            uid,
            None
        )

        send_product_selector(
            message.chat.id,
            "edit"
        )

        return

    if text == "🗑 حذف محصول":

        user_state.pop(
            uid,
            None
        )

        send_product_selector(
            message.chat.id,
            "delete"
        )

        return

    if text == "📋 لیست محصولات":

        rows = all_products()

        if not rows:

            bot.send_message(
                message.chat.id,
                "لیست محصولات خالی است."
            )

            return

        lines = [
            "<b>📋 محصولات ثبت‌شده:</b>"
        ]

        for p in rows[:100]:

            cat = CAT_LABEL.get(
                p["category"],
                p["category"]
            )

            sub = ""

            if (
                p["category"]
                in SUBMENUS
                and
                p["subcategory"]
            ):

                sublabel = SUB_LABEL.get(
                    p["category"],
                    {}
                ).get(
                    p["subcategory"],
                    p["subcategory"]
                )

                sub = (
                    f" | "
                    f"{sublabel}"
                )

            lines.append(
                (
                    "• "
                    f"{html.escape(cat)}"
                    f"{html.escape(sub)}"
                    " — "
                    f"{html.escape(p['name'])}"
                    f" (ID: {p['id']})"
                )
            )

        bot.send_message(
            message.chat.id,
            "\n".join(lines)
        )

        return

    if text == "📞 ویرایش پشتیبانی":

        user_state[
            uid
        ] = {
            "action": "support",
            "step": "value"
        }

        bot.send_message(
            message.chat.id,
            "متن کامل پشتیبانی را بفرست."
        )

        return

    state = user_state.get(
        uid
    )

    if (
        state
        and
        state.get("action")
        ==
        "add"
    ):

        step = state.get(
            "step"
        )

        if step in (
            "category",
            "subcategory"
        ):

            bot.send_message(
                message.chat.id,
                (
                    "از دکمه‌های انتخابی "
                    "بالا استفاده کن."
                )
            )

            return

        if step == "name":

            state["name"] = text
            state["step"] = "specs"

            bot.send_message(
                message.chat.id,
                "مشخصات محصول را بفرست."
            )

            return

        if step == "specs":

            state["specs"] = text
            state["step"] = "photo"

            bot.send_message(
                message.chat.id,
                (
                    "حالا عکس محصول را بفرست. "
                    "اگر عکس نداری بنویس: "
                    "<b>بدون عکس</b>"
                )
            )

            return

        if (
            step == "photo"
            and
            text == "بدون عکس"
        ):

            add_product(
                state["category"],
                state.get(
                    "subcategory",
                    ""
                ),
                state["name"],
                state["specs"],
                ""
            )

            user_state.pop(
                uid,
                None
            )

            bot.send_message(
                message.chat.id,
                "✅ محصول ذخیره شد.",
                reply_markup=admin_keyboard()
            )

            return

        if step == "photo":

            bot.send_message(
                message.chat.id,
                (
                    "عکس را بفرست یا "
                    "دقیقاً بنویس: "
                    "<b>بدون عکس</b>"
                )
            )

            return

    if (
        state
        and
        state.get("action")
        ==
        "edit"
        and
        state.get("step")
        ==
        "value"
        and
        state.get("field")
        in {
            "name",
            "specs"
        }
    ):

        update_product(
            state["product_id"],
            state["field"],
            text
        )

        user_state.pop(
            uid,
            None
        )

        bot.send_message(
            message.chat.id,
            "✅ محصول ویرایش شد.",
            reply_markup=admin_keyboard()
        )

        return

    if (
        state
        and
        state.get("action")
        ==
        "support"
    ):

        set_setting(
            "support_text",
            text
        )

        user_state.pop(
            uid,
            None
        )

        bot.send_message(
            message.chat.id,
            "✅ متن پشتیبانی ذخیره شد.",
            reply_markup=admin_keyboard()
        )

        return

    bot.send_message(
        message.chat.id,
        (
            "از دکمه‌های پنل مدیریت "
            "استفاده کن."
        ),
        reply_markup=admin_keyboard()
    )


init_db()

print(
    "Mobile Pasargad bot is running..."
)

bot.infinity_polling(
    timeout=30,
    long_polling_timeout=30,
    skip_pending=True
)