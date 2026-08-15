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


# =========================
# تنظیمات اصلی
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

ADMIN_ID = os.getenv(
    "ADMIN_ID",
    "1040416634"
).strip()

AI_KEY = os.getenv(
    "OPENAI_API_KEY",
    ""
).strip()

AI_MODEL = os.getenv(
    "AI_MODEL",
    "gpt-4o-mini"
).strip() or "gpt-4o-mini"

AI_URL = (
    "https://1xai.ir/v1/"
    "chat/completions"
)

DB_FILE = os.getenv(
    "DB_FILE",
    "mobile_pasargad.db"
).strip() or "mobile_pasargad.db"


if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN is missing "
        "in Railway Variables"
    )


bot = telebot.TeleBot(
    BOT_TOKEN,
    parse_mode="HTML"
)

db_lock = threading.RLock()

user_state = {}


# =========================
# دسته‌ها
# =========================

CATEGORIES = [

    (
        "📱 موبایل",
        "mobile"
    ),

    (
        "🎮 گجت",
        "gadget"
    ),

    (
        "💆 ماساژور",
        "massager"
    ),

    (
        "🔌 کابل و شارژر",
        "cable_charger"
    ),

    (
        "🎧 هدفون",
        "headphone"
    ),

    (
        "🎶 هندزفری",
        "handsfree"
    ),

    (
        "🎧 ایرپاد",
        "airpods"
    ),

    (
        "💾 رم و فلش",
        "memory"
    ),

    (
        "📱 هولدر",
        "holder"
    ),

    (
        "📶 سیمکارت",
        "simcard"
    ),

    (
        "📦 متفرقه",
        "other"
    ),
]


# =========================
# برندهای موبایل
# فقط همین ۶ برند
# =========================

BRANDS = [

    (
        "🍎 Apple",
        "apple"
    ),

    (
        "📱 Samsung",
        "samsung"
    ),

    (
        "🟠 Xiaomi",
        "xiaomi"
    ),

    (
        "📱 Vocal",
        "vocal"
    ),

    (
        "🔷 Nokia",
        "nokia"
    ),

    (
        "🟢 Realme",
        "realme"
    ),
]


CAT_BY_TEXT = dict(
    CATEGORIES
)

CAT_LABEL = {
    key: label
    for label, key
    in CATEGORIES
}

BRAND_LABEL = {
    key: label
    for label, key
    in BRANDS
}

VALID_CATEGORIES = set(
    CAT_LABEL
)

VALID_BRANDS = set(
    BRAND_LABEL
)


# =========================
# دیتابیس
# =========================

def db():

    conn = sqlite3.connect(
        DB_FILE,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    return conn


def infer_brand(name):

    n = (
        name or ""
    ).lower()

    # Apple

    if any(
        x in n
        for x in [
            "iphone",
            "آیفون",
            "apple",
            "اپل"
        ]
    ):
        return "apple"

    # Samsung

    if any(
        x in n
        for x in [
            "samsung",
            "سامسونگ",
            "galaxy",
            "گلکسی"
        ]
    ):
        return "samsung"

    # Xiaomi
    # Redmi و POCO هم زیر Xiaomi

    if any(
        x in n
        for x in [
            "xiaomi",
            "شیائومی",
            "شیامی",
            "redmi",
            "ردمی",
            "poco",
            "پوکو"
        ]
    ):
        return "xiaomi"

    # Vocal

    if any(
        x in n
        for x in [
            "vocal",
            "وکال"
        ]
    ):
        return "vocal"

    # Nokia

    if any(
        x in n
        for x in [
            "nokia",
            "نوکیا"
        ]
    ):
        return "nokia"

    # Realme

    if any(
        x in n
        for x in [
            "realme",
            "ریلمی"
        ]
    ):
        return "realme"

    return ""


def init_db():

    with db_lock:

        conn = db()

        conn.execute(
            """
            CREATE TABLE
            IF NOT EXISTS products (

                id INTEGER
                PRIMARY KEY AUTOINCREMENT,

                category TEXT
                NOT NULL,

                name TEXT
                NOT NULL,

                specs TEXT
                DEFAULT '',

                photo_id TEXT
                DEFAULT '',

                brand TEXT
                DEFAULT '',

                created_at DATETIME
                DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE
            IF NOT EXISTS settings (

                key TEXT
                PRIMARY KEY,

                value TEXT
                DEFAULT ''
            )
            """
        )

        columns = {

            row["name"]

            for row in conn.execute(
                "PRAGMA table_info(products)"
            ).fetchall()
        }

        # اگر دیتابیس قبلی
        # ستون brand نداشت
        # خودش اضافه می‌شود

        if "brand" not in columns:

            conn.execute(
                """
                ALTER TABLE products
                ADD COLUMN brand TEXT
                DEFAULT ''
                """
            )

        # محصولات قدیمی موبایل
        # بدون حذف دیتابیس
        # برندبندی می‌شوند

        rows = conn.execute(
            """
            SELECT
                id,
                name,
                brand

            FROM products

            WHERE category='mobile'
            """
        ).fetchall()

        for row in rows:

            current_brand = (
                row["brand"]
                or ""
            ).strip().lower()

            # POCO و Redmi
            # همیشه Xiaomi

            if current_brand in (
                "poco",
                "redmi"
            ):

                current_brand = (
                    "xiaomi"
                )

            if (
                current_brand
                not in VALID_BRANDS
            ):

                current_brand = (
                    infer_brand(
                        row["name"]
                    )
                )

            if current_brand:

                conn.execute(
                    """
                    UPDATE products

                    SET brand=?

                    WHERE id=?
                    """,

                    (
                        current_brand,
                        row["id"]
                    )
                )

        conn.commit()

        conn.close()


def is_admin(user_id):

    return (
        str(user_id)
        ==
        ADMIN_ID
    )


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

            (key,)
        ).fetchone()

        conn.close()

    if row:

        return row["value"]

    return default


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

            SET value=
                excluded.value
            """,

            (
                key,
                value
            )
        )

        conn.commit()

        conn.close()


# =========================
# محصولات
# =========================

def add_product(
    category,
    name,
    specs,
    photo_id="",
    brand=""
):

    if (
        category
        not in VALID_CATEGORIES
    ):

        category = "other"

    if category == "mobile":

        if brand in (
            "poco",
            "redmi"
        ):

            brand = "xiaomi"

        if brand not in VALID_BRANDS:

            brand = infer_brand(
                name
            )

    else:

        brand = ""

    with db_lock:

        conn = db()

        cur = conn.execute(
            """
            INSERT INTO products(
                category,
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
                ?
            )
            """,

            (
                category,

                (
                    name
                    or ""
                ).strip(),

                (
                    specs
                    or ""
                ).strip(),

                photo_id
                or "",

                brand
                or ""
            )
        )

        conn.commit()

        product_id = (
            cur.lastrowid
        )

        conn.close()

    return product_id


def get_product(
    product_id
):

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
                brand,
                id
            """
        ).fetchall()

        conn.close()

    return rows


def products_for(
    category,
    brand=None
):

    with db_lock:

        conn = db()

        if (
            category == "mobile"
            and
            brand
        ):

            rows = conn.execute(
                """
                SELECT *

                FROM products

                WHERE
                    category='mobile'
                    AND
                    brand=?

                ORDER BY id ASC
                """,

                (
                    brand,
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

        # اگر اسم موبایل تغییر کرد
        # برند دوباره تشخیص داده شود

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
                row["category"]
                ==
                "mobile"
            ):

                brand = infer_brand(
                    value
                )

                if brand:

                    conn.execute(
                        """
                        UPDATE products

                        SET brand=?

                        WHERE id=?
                        """,

                        (
                            brand,
                            product_id
                        )
                    )

        conn.commit()

        conn.close()

    return True


def delete_product(
    product_id
):

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


# =========================
# منوی اصلی
# =========================

def main_keyboard(
    user_id
):

    kb = (
        types.ReplyKeyboardMarkup(
            resize_keyboard=True,
            row_width=2
        )
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

        if (
            i + 1
            <
            len(CATEGORIES)
        ):

            row.append(

                types.KeyboardButton(
                    CATEGORIES[
                        i + 1
                    ][0]
                )
            )

        kb.row(
            *row
        )

    kb.row(

        types.KeyboardButton(
            "📞 پشتیبانی"
        )
    )

    # فقط برای ادمین

    if is_admin(
        user_id
    ):

        kb.row(

            types.KeyboardButton(
                "⚙️ پنل مدیریت"
            )
        )

    return kb


# =========================
# پنل مدیریت
# =========================

def admin_keyboard():

    kb = (
        types.ReplyKeyboardMarkup(
            resize_keyboard=True,
            row_width=2
        )
    )

    kb.row(

        "➕ افزودن محصول",

        "🤖 افزودن با عکس"
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


# =========================
# انتخاب دسته
# =========================

def category_keyboard(
    prefix
):

    kb = (
        types.InlineKeyboardMarkup(
            row_width=2
        )
    )

    buttons = [

        types.InlineKeyboardButton(

            label,

            callback_data=
                f"{prefix}:{key}"
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

            callback_data=
                "cancel"
        )
    )

    return kb


# =========================
# انتخاب برند
# =========================

def brand_keyboard(
    prefix
):

    kb = (
        types.InlineKeyboardMarkup(
            row_width=2
        )
    )

    buttons = [

        types.InlineKeyboardButton(

            label,

            callback_data=
                f"{prefix}:{key}"
        )

        for label, key
        in BRANDS
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

    if prefix == "shopbrand":

        kb.row(

            types.InlineKeyboardButton(

                "⬅️ منوی اصلی",

                callback_data=
                    "shop:home"
            )
        )

    else:

        kb.row(

            types.InlineKeyboardButton(

                "❌ لغو",

                callback_data=
                    "cancel"
            )
        )

    return kb


# =========================
# دکمه قبلی / بعدی
# =========================

def product_keyboard(
    category,
    brand,
    index,
    total
):

    kb = (
        types.InlineKeyboardMarkup(
            row_width=3
        )
    )

    row = []

    if index > 0:

        row.append(

            types.InlineKeyboardButton(

                "⬅️ قبلی",

                callback_data=(
                    f"nav:"
                    f"{category}:"
                    f"{brand or '-'}:"
                    f"{index - 1}"
                )
            )
        )

    row.append(

        types.InlineKeyboardButton(

            f"{index + 1}/{total}",

            callback_data=
                "noop"
        )
    )

    if (
        index
        <
        total - 1
    ):

        row.append(

            types.InlineKeyboardButton(

                "بعدی ➡️",

                callback_data=(
                    f"nav:"
                    f"{category}:"
                    f"{brand or '-'}:"
                    f"{index + 1}"
                )
            )
        )

    kb.row(
        *row
    )

    if category == "mobile":

        kb.row(

            types.InlineKeyboardButton(

                "🔙 برندهای موبایل",

                callback_data=
                    "shop:brands"
            )
        )

    return kb


# =========================
# نمایش برندها
# =========================

def show_brands(
    chat_id
):

    bot.send_message(

        chat_id,

        (
            "📱 <b>"
            "برند موبایل را "
            "انتخاب کنید:"
            "</b>"
        ),

        reply_markup=
            brand_keyboard(
                "shopbrand"
            )
    )


# =========================
# نمایش محصول
# =========================

def send_product(
    chat_id,
    category,
    brand=None,
    index=0
):

    rows = products_for(
        category,
        brand
    )

    if not rows:

        if (
            category == "mobile"
            and
            brand
        ):

            label = (
                BRAND_LABEL.get(
                    brand,
                    brand
                )
            )

            bot.send_message(
                chat_id,
                (
                    "فعلاً محصولی برای "
                    f"{html.escape(label)} "
                    "ثبت نشده است."
                )
            )

        else:

            bot.send_message(
                chat_id,
                (
                    "فعلاً محصولی "
                    "در این دسته "
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

    product = (
        rows[index]
    )

    title = html.escape(
        product["name"]
        or
        "محصول"
    )

    specs = html.escape(
        product["specs"]
        or
        "مشخصات ثبت نشده است."
    )

    text = (
        f"<b>📦 {title}</b>"
        "\n\n"
        f"{specs}"
    )

    markup = product_keyboard(

        category,

        brand,

        index,

        len(rows)
    )

    if product["photo_id"]:

        bot.send_photo(

            chat_id,

            product[
                "photo_id"
            ],

            caption=text,

            reply_markup=
                markup
        )

    else:

        bot.send_message(

            chat_id,

            text,

            reply_markup=
                markup
        )


# =========================
# پشتیبانی
# =========================

def support_text():

    return get_setting(

        "support_text",

        (
            "<b>📞 پشتیبانی "
            "موبایل پاسارگاد</b>"
            "\n\n"
            "اطلاعات پشتیبانی "
            "هنوز از پنل مدیریت "
            "ثبت نشده است."
        )
    )


# =========================
# لیست برای ویرایش / حذف
# =========================

def send_product_selector(
    chat_id,
    mode
):

    rows = all_products()

    if not rows:

        bot.send_message(
            chat_id,
            (
                "هنوز محصولی "
                "ثبت نشده است."
            )
        )

        return

    kb = (
        types.InlineKeyboardMarkup(
            row_width=1
        )
    )

    for product in rows[:100]:

        cat = (
            CAT_LABEL.get(
                product["category"],
                product["category"]
            )
        )

        brand = ""

        if (
            product["category"]
            ==
            "mobile"
            and
            product["brand"]
        ):

            brand = (
                BRAND_LABEL.get(
                    product["brand"],
                    product["brand"]
                )
            )

            brand = (
                f" | {brand}"
            )

        title = (
            f"{cat}"
            f"{brand}"
            " | "
            f"{product['name']}"
        )

        kb.add(

            types.InlineKeyboardButton(

                title[:60],

                callback_data=(
                    f"{mode}:"
                    f"{product['id']}"
                )
            )
        )

    bot.send_message(

        chat_id,

        "محصول را انتخاب کن:",

        reply_markup=
            kb
    )


# =========================
# هوش مصنوعی 1xAi
# =========================

def clean_ai_json(
    text
):

    content = (
        text or ""
    ).strip()

    if content.startswith(
        "```"
    ):

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

    start = (
        content.find(
            "{"
        )
    )

    end = (
        content.rfind(
            "}"
        )
    )

    if (
        start != -1
        and
        end != -1
        and
        end > start
    ):

        content = (
            content[
                start:end + 1
            ]
        )

    return json.loads(
        content
    )


def normalize_ai_result(
    result
):

    category = str(
        result.get(
            "category",
            "other"
        )
    ).strip().lower()

    if (
        category
        not in VALID_CATEGORIES
    ):

        category = "other"

    name = str(
        result.get(
            "name",
            ""
        )
    ).strip()

    if not name:

        name = (
            "محصول جدید"
        )

    specs = str(
        result.get(
            "specs",
            ""
        )
    ).strip()

    brand = str(
        result.get(
            "brand",
            ""
        )
    ).strip().lower()

    # POCO و Redmi
    # زیر Xiaomi

    if brand in (
        "redmi",
        "poco"
    ):

        brand = "xiaomi"

    if category == "mobile":

        if (
            brand
            not in VALID_BRANDS
        ):

            brand = infer_brand(
                name
            )

        if (
            brand
            not in VALID_BRANDS
        ):

            brand = ""

    else:

        brand = ""

    return {

        "category":
            category,

        "brand":
            brand,

        "name":
            name,

        "specs":
            specs
    }


def ai_from_photo(
    image_bytes
):

    if not AI_KEY:

        raise RuntimeError(
            (
                "OPENAI_API_KEY "
                "در Railway Variables "
                "تنظیم نشده است."
            )
        )

    encoded = (
        base64.b64encode(
            image_bytes
        ).decode(
            "utf-8"
        )
    )

    data_url = (
        "data:image/jpeg;base64,"
        +
        encoded
    )

    prompt = """
این تصویر مربوط به یک محصول فروشگاه موبایل و لوازم جانبی است.

نام و مدل محصول را تا حد ممکن دقیق از روی خود محصول و بسته‌بندی تشخیص بده.

اگر محصول موبایل است، brand فقط یکی از این شش مقدار باشد:

apple
samsung
xiaomi
vocal
nokia
realme

Redmi و POCO را زیر xiaomi قرار بده و هرگز آن‌ها را برند جدا حساب نکن.

category فقط یکی از این مقادیر باشد:

mobile
gadget
massager
cable_charger
headphone
handsfree
airpods
memory
holder
simcard
other

specs را به فارسی، کوتاه، کاربردی و در 3 تا 6 مورد بنویس.

قیمت ننویس.
گارانتی ننویس.
رنگ ننویس.
موجودی را حدس نزن.

اطلاعاتی را که از تصویر مطمئن نیستی نساز.

اگر چیزی را مطمئن نیستی حدس نزن.

فقط JSON معتبر و بدون هیچ متن اضافه برگردان:

{
  "category": "mobile",
  "brand": "samsung",
  "name": "نام دقیق محصول",
  "specs": "مشخصات کوتاه فارسی"
}
""".strip()

    payload = {

        "model":
            AI_MODEL,

        "messages": [

            {

                "role":
                    "user",

                "content": [

                    {

                        "type":
                            "text",

                        "text":
                            prompt
                    },

                    {

                        "type":
                            "image_url",

                        "image_url": {

                            "url":
                                data_url
                        }
                    }
                ]
            }
        ],

        "temperature":
            0.1,

        "max_tokens":
            700
    }

    body = (
        json.dumps(
            payload
        ).encode(
            "utf-8"
        )
    )

    req = (
        urllib.request.Request(

            AI_URL,

            data=
                body,

            headers={

                "Authorization":
                    f"Bearer {AI_KEY}",

                "Content-Type":
                    "application/json"
            },

            method=
                "POST"
        )
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
            (
                f"AI error "
                f"{error.code}: "
                f"{details[:300]}"
            )
        )

    except urllib.error.URLError as error:

        raise RuntimeError(
            (
                "AI connection error: "
                f"{error.reason}"
            )
        )

    data = json.loads(
        raw
    )

    content = (
        data[
            "choices"
        ][0][
            "message"
        ][
            "content"
        ]
    )

    result = (
        clean_ai_json(
            content
        )
    )

    return (
        normalize_ai_result(
            result
        )
    )


# =========================
# شروع افزودن دستی
# =========================

def begin_manual_add(
    message
):

    user_state[
        message.from_user.id
    ] = {

        "action":
            "add",

        "step":
            "category"
    }

    bot.send_message(

        message.chat.id,

        "دسته محصول را انتخاب کن:",

        reply_markup=
            category_keyboard(
                "addcat"
            )
    )


# =========================
# شروع افزودن با AI
# =========================

def begin_ai_add(
    message
):

    if not AI_KEY:

        bot.send_message(

            message.chat.id,

            (
                "❌ کلید 1xAi "
                "پیدا نشد.\n\n"
                "متغیر "
                "<code>OPENAI_API_KEY</code> "
                "باید در Railway "
                "تنظیم باشد."
            )
        )

        return

    user_state[
        message.from_user.id
    ] = {

        "action":
            "ai_add",

        "step":
            "photo"
    }

    bot.send_message(

        message.chat.id,

        (
            "🤖 <b>"
            "افزودن هوشمند با عکس"
            "</b>\n\n"

            "یک عکس واضح از محصول "
            "یا جعبه‌اش بفرست.\n\n"

            "هوش مصنوعی نام، دسته، "
            "برند و مشخصات را "
            "استخراج می‌کند و "
            "قبل از ذخیره به تو "
            "نشان می‌دهد."
        )
    )


# =========================
# START
# =========================

@bot.message_handler(
    commands=[
        "start"
    ]
)
def start(
    message
):

    user_state.pop(
        message.from_user.id,
        None
    )

    bot.send_message(

        message.chat.id,

        (
            "سلام 👋\n\n"

            "<b>"
            "به ربات موبایل پاسارگاد "
            "خوش آمدید."
            "</b>\n"

            "دسته موردنظر را "
            "انتخاب کنید:"
        ),

        reply_markup=
            main_keyboard(
                message.from_user.id
            )
    )


# =========================
# ID
# =========================

@bot.message_handler(
    commands=[
        "id"
    ]
)
def show_id(
    message
):

    bot.send_message(

        message.chat.id,

        (
            "شناسه عددی شما:\n"
            f"<code>"
            f"{message.from_user.id}"
            f"</code>"
        )
    )


# =========================
# ADMIN
# =========================

@bot.message_handler(
    commands=[
        "admin"
    ]
)
def admin_command(
    message
):

    if is_admin(
        message.from_user.id
    ):

        user_state.pop(
            message.from_user.id,
            None
        )

        bot.send_message(

            message.chat.id,

            (
                "⚙️ <b>"
                "پنل مدیریت"
                "</b>"
            ),

            reply_markup=
                admin_keyboard()
        )

    else:

        bot.send_message(
            message.chat.id,
            "⛔ دسترسی ندارید."
        )


# =========================
# NOOP
# =========================

@bot.callback_query_handler(
    func=lambda call:
        call.data
        ==
        "noop"
)
def noop(
    call
):

    bot.answer_callback_query(
        call.id
    )


# =========================
# منوی اصلی
# =========================

@bot.callback_query_handler(
    func=lambda call:
        call.data
        ==
        "shop:home"
)
def shop_home(
    call
):

    bot.answer_callback_query(
        call.id
    )

    bot.send_message(

        call.message.chat.id,

        "منوی اصلی:",

        reply_markup=
            main_keyboard(
                call.from_user.id
            )
    )


# =========================
# برگشت به برندها
# =========================

@bot.callback_query_handler(
    func=lambda call:
        call.data
        ==
        "shop:brands"
)
def shop_brands(
    call
):

    bot.answer_callback_query(
        call.id
    )

    show_brands(
        call.message.chat.id
    )


# =========================
# انتخاب برند مشتری
# =========================

@bot.callback_query_handler(
    func=lambda call:
        call.data.startswith(
            "shopbrand:"
        )
)
def shop_brand_selected(
    call
):

    brand = (
        call.data.split(
            ":",
            1
        )[1]
    )

    bot.answer_callback_query(
        call.id
    )

    if brand not in VALID_BRANDS:

        bot.send_message(
            call.message.chat.id,
            "برند نامعتبر است."
        )

        return

    send_product(

        call.message.chat.id,

        "mobile",

        brand,

        0
    )


# =========================
# قبلی / بعدی
# =========================

@bot.callback_query_handler(
    func=lambda call:
        call.data.startswith(
            "nav:"
        )
)
def navigation(
    call
):

    try:

        (
            _,
            category,
            brand,
            index
        ) = (
            call.data.split(
                ":",
                3
            )
        )

        if brand == "-":

            brand = None

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

            brand,

            index
        )

    except Exception:

        bot.answer_callback_query(
            call.id,
            "خطا"
        )


# =========================
# لغو
# =========================

@bot.callback_query_handler(
    func=lambda call:
        call.data
        ==
        "cancel"
)
def cancel_callback(
    call
):

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

            reply_markup=
                admin_keyboard()
        )


# =========================
# انتخاب دسته افزودن
# =========================

@bot.callback_query_handler(
    func=lambda call:
        call.data.startswith(
            "addcat:"
        )
)
def add_category_selected(
    call
):

    if not is_admin(
        call.from_user.id
    ):

        bot.answer_callback_query(

            call.id,

            "دسترسی ندارید.",

            show_alert=True
        )

        return

    state = user_state.get(
        call.from_user.id
    )

    if (
        not state
        or
        state.get(
            "action"
        )
        !=
        "add"
    ):

        bot.answer_callback_query(

            call.id,

            "عملیات منقضی شده.",

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

        bot.answer_callback_query(

            call.id,

            "دسته نامعتبر است.",

            show_alert=True
        )

        return

    state[
        "category"
    ] = category

    bot.answer_callback_query(
        call.id
    )

    if category == "mobile":

        state[
            "step"
        ] = "brand"

        bot.send_message(

            call.message.chat.id,

            "برند موبایل را انتخاب کن:",

            reply_markup=
                brand_keyboard(
                    "addbrand"
                )
        )

    else:

        state[
            "brand"
        ] = ""

        state[
            "step"
        ] = "name"

        bot.send_message(
            call.message.chat.id,
            "نام محصول را بفرست."
        )


# =========================
# انتخاب برند هنگام افزودن
# =========================

@bot.callback_query_handler(
    func=lambda call:
        call.data.startswith(
            "addbrand:"
        )
)
def add_brand_selected(
    call
):

    if not is_admin(
        call.from_user.id
    ):

        bot.answer_callback_query(

            call.id,

            "دسترسی ندارید.",

            show_alert=True
        )

        return

    state = user_state.get(
        call.from_user.id
    )

    brand = (
        call.data.split(
            ":",
            1
        )[1]
    )

    if (
        not state
        or
        state.get(
            "action"
        )
        !=
        "add"
        or
        state.get(
            "step"
        )
        !=
        "brand"
        or
        brand
        not in VALID_BRANDS
    ):

        bot.answer_callback_query(

            call.id,

            "عملیات منقضی شده.",

            show_alert=True
        )

        return

    state[
        "brand"
    ] = brand

    state[
        "step"
    ] = "name"

    bot.answer_callback_query(
        call.id
    )

    bot.send_message(
        call.message.chat.id,
        "نام محصول را بفرست."
    )


# =========================
# انتخاب محصول برای ویرایش
# =========================

@bot.callback_query_handler(
    func=lambda call:
        call.data.startswith(
            "edit:"
        )
)
def edit_select(
    call
):

    if not is_admin(
        call.from_user.id
    ):

        bot.answer_callback_query(

            call.id,

            "دسترسی ندارید.",

            show_alert=True
        )

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

    product = get_product(
        product_id
    )

    if not product:

        bot.answer_callback_query(

            call.id,

            "محصول پیدا نشد.",

            show_alert=True
        )

        return

    user_state[
        call.from_user.id
    ] = {

        "action":
            "edit",

        "step":
            "field",

        "product_id":
            product_id
    }

    kb = (
        types.InlineKeyboardMarkup(
            row_width=2
        )
    )

    kb.row(

        types.InlineKeyboardButton(

            "✏️ نام",

            callback_data=
                "editfield:name"
        ),

        types.InlineKeyboardButton(

            "📝 مشخصات",

            callback_data=
                "editfield:specs"
        )
    )

    kb.row(

        types.InlineKeyboardButton(

            "🖼 عکس",

            callback_data=
                "editfield:photo_id"
        )
    )

    kb.row(

        types.InlineKeyboardButton(

            "❌ لغو",

            callback_data=
                "cancel"
        )
    )

    bot.answer_callback_query(
        call.id
    )

    bot.send_message(

        call.message.chat.id,

        (
            "ویرایش "
            f"<b>"
            f"{html.escape(product['name'])}"
            f"</b>\n"
            "چه چیزی تغییر کند؟"
        ),

        reply_markup=
            kb
    )


# =========================
# انتخاب بخش ویرایش
# =========================

@bot.callback_query_handler(
    func=lambda call:
        call.data.startswith(
            "editfield:"
        )
)
def edit_field_selected(
    call
):

    if not is_admin(
        call.from_user.id
    ):

        bot.answer_callback_query(

            call.id,

            "دسترسی ندارید.",

            show_alert=True
        )

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
        state.get(
            "action"
        )
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

            "عملیات منقضی شده.",

            show_alert=True
        )

        return

    state[
        "field"
    ] = field

    state[
        "step"
    ] = "value"

    bot.answer_callback_query(
        call.id
    )

    if field == "photo_id":

        bot.send_message(
            call.message.chat.id,
            "عکس جدید محصول را بفرست."
        )

    elif field == "name":

        bot.send_message(
            call.message.chat.id,
            "نام جدید محصول را بفرست."
        )

    else:

        bot.send_message(
            call.message.chat.id,
            "مشخصات جدید محصول را بفرست."
        )


# =========================
# انتخاب حذف
# =========================

@bot.callback_query_handler(
    func=lambda call:
        call.data.startswith(
            "delete:"
        )
)
def delete_select(
    call
):

    if not is_admin(
        call.from_user.id
    ):

        bot.answer_callback_query(

            call.id,

            "دسترسی ندارید.",

            show_alert=True
        )

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

    product = get_product(
        product_id
    )

    if not product:

        bot.answer_callback_query(

            call.id,

            "محصول پیدا نشد.",

            show_alert=True
        )

        return

    kb = (
        types.InlineKeyboardMarkup(
            row_width=2
        )
    )

    kb.row(

        types.InlineKeyboardButton(

            "✅ بله، حذف شود",

            callback_data=
                f"delok:{product_id}"
        ),

        types.InlineKeyboardButton(

            "❌ لغو",

            callback_data=
                "cancel"
        )
    )

    bot.answer_callback_query(
        call.id
    )

    bot.send_message(

        call.message.chat.id,

        (
            "مطمئنی "
            f"<b>"
            f"{html.escape(product['name'])}"
            f"</b> "
            "حذف شود؟"
        ),

        reply_markup=
            kb
    )


# =========================
# تایید حذف
# =========================

@bot.callback_query_handler(
    func=lambda call:
        call.data.startswith(
            "delok:"
        )
)
def delete_confirm(
    call
):

    if not is_admin(
        call.from_user.id
    ):

        bot.answer_callback_query(

            call.id,

            "دسترسی ندارید.",

            show_alert=True
        )

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
        "حذف شد."
    )

    bot.send_message(

        call.message.chat.id,

        "✅ محصول حذف شد.",

        reply_markup=
            admin_keyboard()
    )


# =========================
# تایید AI
# =========================

@bot.callback_query_handler(
    func=lambda call:
        call.data
        in (
            "ai:save",
            "ai:cancel"
        )
)
def ai_confirm(
    call
):

    if not is_admin(
        call.from_user.id
    ):

        bot.answer_callback_query(

            call.id,

            "دسترسی ندارید.",

            show_alert=True
        )

        return

    state = user_state.get(
        call.from_user.id
    )

    if (
        call.data
        ==
        "ai:cancel"
    ):

        user_state.pop(
            call.from_user.id,
            None
        )

        bot.answer_callback_query(
            call.id,
            "لغو شد."
        )

        bot.send_message(

            call.message.chat.id,

            (
                "افزودن هوشمند "
                "لغو شد."
            ),

            reply_markup=
                admin_keyboard()
        )

        return

    if (
        not state
        or
        state.get(
            "action"
        )
        !=
        "ai_add"
        or
        not state.get(
            "ai_result"
        )
    ):

        bot.answer_callback_query(

            call.id,

            "اطلاعات پیدا نشد.",

            show_alert=True
        )

        return

    result = (
        state[
            "ai_result"
        ]
    )

    # اگر موبایل بود
    # برند باید مشخص باشد

    if (
        result[
            "category"
        ]
        ==
        "mobile"
        and
        result[
            "brand"
        ]
        not in VALID_BRANDS
    ):

        bot.answer_callback_query(

            call.id,

            (
                "برند موبایل مشخص نشد؛ "
                "لطفاً دستی اضافه کن."
            ),

            show_alert=True
        )

        return

    add_product(

        result[
            "category"
        ],

        result[
            "name"
        ],

        result[
            "specs"
        ],

        state.get(
            "photo_id",
            ""
        ),

        result.get(
            "brand",
            ""
        )
    )

    user_state.pop(
        call.from_user.id,
        None
    )

    bot.answer_callback_query(
        call.id,
        "ذخیره شد."
    )

    bot.send_message(

        call.message.chat.id,

        (
            "✅ محصول با موفقیت "
            "ذخیره شد."
        ),

        reply_markup=
            admin_keyboard()
    )


# =========================
# دریافت عکس
# =========================

@bot.message_handler(
    content_types=[
        "photo"
    ]
)
def photo_handler(
    message
):

    user_id = (
        message.from_user.id
    )

    state = user_state.get(
        user_id
    )

    if not is_admin(
        user_id
    ):

        return

    if not state:

        bot.send_message(

            message.chat.id,

            (
                "ابتدا از پنل مدیریت "
                "«افزودن محصول» یا "
                "«افزودن با عکس» "
                "را انتخاب کن."
            )
        )

        return

    # =====================
    # AI PHOTO
    # =====================

    if (
        state.get(
            "action"
        )
        ==
        "ai_add"
        and
        state.get(
            "step"
        )
        ==
        "photo"
    ):

        try:

            bot.send_message(

                message.chat.id,

                (
                    "🤖 عکس دریافت شد؛ "
                    "در حال بررسی نام، "
                    "برند و مشخصات..."
                )
            )

            file_info = bot.get_file(

                message.photo[
                    -1
                ].file_id
            )

            image_bytes = (
                bot.download_file(
                    file_info.file_path
                )
            )

            result = ai_from_photo(
                image_bytes
            )

            state[
                "ai_result"
            ] = result

            state[
                "photo_id"
            ] = (
                message.photo[
                    -1
                ].file_id
            )

            state[
                "step"
            ] = "confirm"

            category_label = (
                CAT_LABEL.get(
                    result[
                        "category"
                    ],
                    result[
                        "category"
                    ]
                )
            )

            brand_label = ""

            if (
                result[
                    "category"
                ]
                ==
                "mobile"
            ):

                brand_label = (
                    BRAND_LABEL.get(
                        result[
                            "brand"
                        ],
                        "نامشخص"
                    )
                )

                brand_label = (
                    "\n🏷 برند: "
                    f"{html.escape(brand_label)}"
                )

            result_text = (

                "<b>"
                "🤖 نتیجه بررسی "
                "هوش مصنوعی:"
                "</b>\n\n"

                "📂 دسته: "
                f"{html.escape(category_label)}"

                f"{brand_label}\n"

                "📦 نام: "
                f"{html.escape(result['name'])}"

                "\n\n"

                "📝 مشخصات:\n"
                f"{html.escape(result['specs'] or 'ثبت نشده')}"

                "\n\n"

                "اگر درست است "
                "«ذخیره» را بزن."
            )

            kb = (
                types.InlineKeyboardMarkup(
                    row_width=2
                )
            )

            kb.row(

                types.InlineKeyboardButton(

                    "✅ ذخیره",

                    callback_data=
                        "ai:save"
                ),

                types.InlineKeyboardButton(

                    "❌ لغو",

                    callback_data=
                        "ai:cancel"
                )
            )

            bot.send_message(

                message.chat.id,

                result_text,

                reply_markup=
                    kb
            )

        except Exception as error:

            bot.send_message(

                message.chat.id,

                (
                    "❌ هوش مصنوعی "
                    "نتوانست عکس را "
                    "بررسی کند.\n\n"

                    "<code>"
                    f"{html.escape(str(error)[:350])}"
                    "</code>\n\n"

                    "می‌توانی دوباره "
                    "عکس بفرستی یا از "
                    "افزودن دستی استفاده کنی."
                )
            )

        return

    # =====================
    # ویرایش عکس
    # =====================

    if (

        state.get(
            "action"
        )
        ==
        "edit"

        and

        state.get(
            "step"
        )
        ==
        "value"

        and

        state.get(
            "field"
        )
        ==
        "photo_id"
    ):

        update_product(

            state[
                "product_id"
            ],

            "photo_id",

            message.photo[
                -1
            ].file_id
        )

        user_state.pop(
            user_id,
            None
        )

        bot.send_message(

            message.chat.id,

            (
                "✅ عکس محصول "
                "ویرایش شد."
            ),

            reply_markup=
                admin_keyboard()
        )

        return

    # =====================
    # افزودن دستی با عکس
    # =====================

    if (

        state.get(
            "action"
        )
        ==
        "add"

        and

        state.get(
            "step"
        )
        ==
        "photo"
    ):

        add_product(

            state[
                "category"
            ],

            state[
                "name"
            ],

            state[
                "specs"
            ],

            message.photo[
                -1
            ].file_id,

            state.get(
                "brand",
                ""
            )
        )

        user_state.pop(
            user_id,
            None
        )

        bot.send_message(

            message.chat.id,

            (
                "✅ محصول با موفقیت "
                "ذخیره شد."
            ),

            reply_markup=
                admin_keyboard()
        )

        return

    bot.send_message(

        message.chat.id,

        (
            "در این مرحله "
            "منتظر عکس نیستم."
        )
    )


# =========================
# پیام‌های متنی
# =========================

@bot.message_handler(
    content_types=[
        "text"
    ],
    func=lambda message:
        True
)
def text_handler(
    message
):

    user_id = (
        message.from_user.id
    )

    text = (
        message.text
        or
        ""
    ).strip()

    # =====================
    # موبایل
    # =====================

    if text == "📱 موبایل":

        user_state.pop(
            user_id,
            None
        )

        show_brands(
            message.chat.id
        )

        return

    # =====================
    # دسته‌های اصلی
    # =====================

    if text in CAT_BY_TEXT:

        user_state.pop(
            user_id,
            None
        )

        category = (
            CAT_BY_TEXT[
                text
            ]
        )

        if category == "mobile":

            show_brands(
                message.chat.id
            )

        else:

            send_product(

                message.chat.id,

                category,

                None,

                0
            )

        return

    # =====================
    # پشتیبانی
    # =====================

    if (
        text
        ==
        "📞 پشتیبانی"
    ):

        user_state.pop(
            user_id,
            None
        )

        bot.send_message(

            message.chat.id,

            support_text(),

            reply_markup=
                main_keyboard(
                    user_id
                )
        )

        return

    # =====================
    # برگشت
    # =====================

    if (
        text
        ==
        "⬅️ بازگشت به منو"
    ):

        user_state.pop(
            user_id,
            None
        )

        bot.send_message(

            message.chat.id,

            "منوی اصلی:",

            reply_markup=
                main_keyboard(
                    user_id
                )
        )

        return

    # =====================
    # پنل مدیریت
    # =====================

    if (
        text
        ==
        "⚙️ پنل مدیریت"
    ):

        user_state.pop(
            user_id,
            None
        )

        if is_admin(
            user_id
        ):

            bot.send_message(

                message.chat.id,

                (
                    "⚙️ <b>"
                    "پنل مدیریت"
                    "</b>"
                ),

                reply_markup=
                    admin_keyboard()
            )

        else:

            bot.send_message(
                message.chat.id,
                "⛔ دسترسی ندارید."
            )

        return

    # =====================
    # از اینجا فقط ادمین
    # =====================

    if not is_admin(
        user_id
    ):

        bot.send_message(

            message.chat.id,

            (
                "لطفاً از دکمه‌های "
                "منو استفاده کنید."
            ),

            reply_markup=
                main_keyboard(
                    user_id
                )
        )

        return

    # =====================
    # افزودن محصول
    # =====================

    if (
        text
        ==
        "➕ افزودن محصول"
    ):

        begin_manual_add(
            message
        )

        return

    # =====================
    # افزودن با AI
    # =====================

    if (
        text
        ==
        "🤖 افزودن با عکس"
    ):

        begin_ai_add(
            message
        )

        return

    # =====================
    # ویرایش
    # =====================

    if (
        text
        ==
        "✏️ ویرایش محصول"
    ):

        user_state.pop(
            user_id,
            None
        )

        send_product_selector(

            message.chat.id,

            "edit"
        )

        return

    # =====================
    # حذف
    # =====================

    if (
        text
        ==
        "🗑 حذف محصول"
    ):

        user_state.pop(
            user_id,
            None
        )

        send_product_selector(

            message.chat.id,

            "delete"
        )

        return

    # =====================
    # لیست محصولات
    # =====================

    if (
        text
        ==
        "📋 لیست محصولات"
    ):

        rows = all_products()

        if not rows:

            bot.send_message(

                message.chat.id,

                (
                    "لیست محصولات "
                    "خالی است."
                )
            )

            return

        lines = [

            "<b>"
            "📋 محصولات ثبت‌شده:"
            "</b>"
        ]

        for product in rows[:100]:

            cat = (
                CAT_LABEL.get(
                    product[
                        "category"
                    ],
                    product[
                        "category"
                    ]
                )
            )

            brand = ""

            if (

                product[
                    "category"
                ]
                ==
                "mobile"

                and

                product[
                    "brand"
                ]
            ):

                brand = (
                    BRAND_LABEL.get(
                        product[
                            "brand"
                        ],
                        product[
                            "brand"
                        ]
                    )
                )

                brand = (
                    f" | {brand}"
                )

            lines.append(

                (
                    "• "
                    f"{html.escape(cat)}"
                    f"{html.escape(brand)}"
                    " — "
                    f"{html.escape(product['name'])}"
                    " "
                    f"(ID: {product['id']})"
                )
            )

        bot.send_message(

            message.chat.id,

            "\n".join(
                lines
            )
        )

        return

    # =====================
    # ویرایش پشتیبانی
    # =====================

    if (
        text
        ==
        "📞 ویرایش پشتیبانی"
    ):

        user_state[
            user_id
        ] = {

            "action":
                "support",

            "step":
                "value"
        }

        bot.send_message(

            message.chat.id,

            (
                "متن کامل پشتیبانی "
                "را بفرست.\n\n"

                "همین متن بعداً "
                "به مشتری نمایش "
                "داده می‌شود."
            )
        )

        return

    state = user_state.get(
        user_id
    )

    # =====================
    # افزودن دستی
    # =====================

    if (
        state
        and
        state.get(
            "action"
        )
        ==
        "add"
    ):

        step = state.get(
            "step"
        )

        # دسته / برند

        if step in (
            "category",
            "brand"
        ):

            bot.send_message(

                message.chat.id,

                (
                    "لطفاً از دکمه‌های "
                    "انتخابی بالا "
                    "استفاده کن."
                )
            )

            return

        # نام

        if step == "name":

            state[
                "name"
            ] = text

            state[
                "step"
            ] = "specs"

            bot.send_message(

                message.chat.id,

                (
                    "مشخصات محصول "
                    "را بفرست."
                )
            )

            return

        # مشخصات

        if step == "specs":

            state[
                "specs"
            ] = text

            state[
                "step"
            ] = "photo"

            bot.send_message(

                message.chat.id,

                (
                    "حالا عکس محصول "
                    "را بفرست.\n\n"

                    "اگر عکس نداری "
                    "بنویس:\n"

                    "<b>بدون عکس</b>"
                )
            )

            return

        # بدون عکس

        if (
            step
            ==
            "photo"

            and

            text
            ==
            "بدون عکس"
        ):

            add_product(

                state[
                    "category"
                ],

                state[
                    "name"
                ],

                state[
                    "specs"
                ],

                "",

                state.get(
                    "brand",
                    ""
                )
            )

            user_state.pop(
                user_id,
                None
            )

            bot.send_message(

                message.chat.id,

                "✅ محصول ذخیره شد.",

                reply_markup=
                    admin_keyboard()
            )

            return

        if step == "photo":

            bot.send_message(

                message.chat.id,

                (
                    "عکس محصول را "
                    "بفرست یا دقیقاً "
                    "بنویس:\n"
                    "<b>بدون عکس</b>"
                )
            )

            return

    # =====================
    # ویرایش متن
    # =====================

    if (

        state

        and

        state.get(
            "action"
        )
        ==
        "edit"

        and

        state.get(
            "step"
        )
        ==
        "value"

        and

        state.get(
            "field"
        )
        in {
            "name",
            "specs"
        }
    ):

        update_product(

            state[
                "product_id"
            ],

            state[
                "field"
            ],

            text
        )

        user_state.pop(
            user_id,
            None
        )

        bot.send_message(

            message.chat.id,

            (
                "✅ محصول "
                "ویرایش شد."
            ),

            reply_markup=
                admin_keyboard()
        )

        return

    # =====================
    # ذخیره پشتیبانی
    # =====================

    if (
        state
        and
        state.get(
            "action"
        )
        ==
        "support"
    ):

        set_setting(

            "support_text",

            text
        )

        user_state.pop(
            user_id,
            None
        )

        bot.send_message(

            message.chat.id,

            (
                "✅ متن پشتیبانی "
                "ذخیره شد."
            ),

            reply_markup=
                admin_keyboard()
        )

        return

    bot.send_message(

        message.chat.id,

        (
            "از دکمه‌های پنل "
            "مدیریت استفاده کن."
        ),

        reply_markup=
            admin_keyboard()
    )


# =========================
# اجرای ربات
# =========================

init_db()

print(
    "Mobile Pasargad bot is running..."
)

bot.infinity_polling(

    timeout=30,

    long_polling_timeout=30,

    skip_pending=True
)