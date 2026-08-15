# Mobile Pasargad Telegram Bot - Complete Version
# بدون قیمت | کاتالوگ | پنل مدیریت | پشتیبانی | افزودن با عکس و AI

import os
import json
import sqlite3
import base64
import threading
import requests
import telebot
from telebot import types

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
AI_KEY = os.getenv("OPENAI_API_KEY", "").strip()

AI_URL = "https://1xai.ir/v1/chat/completions"
AI_MODEL = "gpt-4o"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing in Railway Variables.")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

DB_FILE = "mobile_pasargad.db"
db_lock = threading.Lock()

CATEGORIES = [
    ("📱 موبایل", "mobile"),
    ("🎮 گجت", "gadget"),
    ("💆 ماساژور", "massager"),
    ("🔌 کابل و شارژر", "cable_charger"),
    ("🎧 هدفون", "headphone"),
    ("🎶 هندزفری", "handsfree"),
    ("🎧 ایرپاد", "airpods"),
    ("💾 رم و فلش", "memory"),
    ("📱 هولدر", "holder"),
    ("📶 سیمکارت", "simcard"),
    ("📦 متفرقه", "other"),
]

BRANDS = [
    "Apple",
    "Samsung",
    "Xiaomi",
    "Vocal",
    "Realme",
    "Nokia"
]

user_state = {}
user_product_page = {}
user_category = {}


def db():
    conn = sqlite3.connect(
        DB_FILE,
        check_same_thread=False
    )
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db_lock:
        conn = db()

        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                name TEXT NOT NULL,
                specs TEXT DEFAULT '',
                photo_id TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT DEFAULT ''
            )
        """)

        conn.commit()
        conn.close()


def get_setting(key, default=""):
    with db_lock:
        conn = db()

        row = conn.execute(
            "SELECT value FROM settings WHERE key=?",
            (key,)
        ).fetchone()

        conn.close()

    if row:
        return row["value"]

    return default


def set_setting(key, value):
    with db_lock:
        conn = db()

        conn.execute(
            """
            INSERT INTO settings(key,value)
            VALUES(?,?)
            ON CONFLICT(key)
            DO UPDATE SET value=excluded.value
            """,
            (key, value)
        )

        conn.commit()
        conn.close()


def is_admin(user_id):
    saved = get_setting("admin_id")

    if not saved:
        return False

    return str(user_id) == saved


def claim_admin(user_id):
    saved = get_setting("admin_id")

    if not saved:
        set_setting("admin_id", str(user_id))
        return True

    return str(user_id) == saved


def main_keyboard(user_id):
    kb = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        row_width=2
    )

    for i in range(0, len(CATEGORIES), 2):

        row = [
            types.KeyboardButton(
                CATEGORIES[i][0]
            )
        ]

        if i + 1 < len(CATEGORIES):

            row.append(
                types.KeyboardButton(
                    CATEGORIES[i + 1][0]
                )
            )

        kb.row(*row)

    kb.row(
        types.KeyboardButton("📞 پشتیبانی")
    )

    if is_admin(user_id):

        kb.row(
            types.KeyboardButton("⚙️ پنل مدیریت")
        )

    return kb


def admin_keyboard():

    kb = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        row_width=2
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
        "📞 ویرایش پشتیبانی",
        "📋 لیست محصولات"
    )

    kb.row(
        "⬅️ بازگشت به منو"
    )

    return kb


def category_keyboard():

    kb = types.InlineKeyboardMarkup(
        row_width=2
    )

    for label, key in CATEGORIES:

        kb.add(
            types.InlineKeyboardButton(
                label,
                callback_data=f"cat:{key}"
            )
        )

    return kb


def products_for_category(category):

    with db_lock:

        conn = db()

        rows = conn.execute(
            """
            SELECT *
            FROM products
            WHERE category=?
            ORDER BY id ASC
            """,
            (category,)
        ).fetchall()

        conn.close()

    return rows


def product_keyboard(category, index, total):

    kb = types.InlineKeyboardMarkup(
        row_width=3
    )

    buttons = []

    if index > 0:

        buttons.append(
            types.InlineKeyboardButton(
                "⬅️ قبلی",
                callback_data=f"nav:{category}:{index-1}"
            )
        )

    buttons.append(
        types.InlineKeyboardButton(
            f"{index + 1}/{total}",
            callback_data="noop"
        )
    )

    if index < total - 1:

        buttons.append(
            types.InlineKeyboardButton(
                "بعدی ➡️",
                callback_data=f"nav:{category}:{index+1}"
            )
        )

    kb.row(*buttons)

    return kb


def category_label(key):

    for label, category in CATEGORIES:

        if category == key:
            return label

    return key


def send_product(
    chat_id,
    category,
    index,
    edit_message_id=None
):

    rows = products_for_category(category)

    if not rows:

        bot.send_message(
            chat_id,
            "فعلاً محصولی در این دسته ثبت نشده است."
        )

        return

    index = max(
        0,
        min(index, len(rows) - 1)
    )

    product = rows[index]

    text = (
        f"<b>📱 {product['name']}</b>\n\n"
        f"{product['specs'] or 'مشخصات ثبت نشده است.'}"
    )

    markup = product_keyboard(
        category,
        index,
        len(rows)
    )

    if edit_message_id:

        try:

            if product["photo_id"]:

                bot.edit_message_media(
                    types.InputMediaPhoto(
                        product["photo_id"],
                        caption=text,
                        parse_mode="HTML"
                    ),
                    chat_id,
                    edit_message_id,
                    reply_markup=markup
                )

            else:

                bot.edit_message_text(
                    text,
                    chat_id,
                    edit_message_id,
                    reply_markup=markup,
                    parse_mode="HTML"
                )

            return

        except Exception:
            pass

    if product["photo_id"]:

        bot.send_photo(
            chat_id,
            product["photo_id"],
            caption=text,
            reply_markup=markup
        )

    else:

        bot.send_message(
            chat_id,
            text,
            reply_markup=markup
        )


def add_product(
    category,
    name,
    specs,
    photo_id=""
):

    with db_lock:

        conn = db()

        cur = conn.execute(
            """
            INSERT INTO products
            (category,name,specs,photo_id)
            VALUES(?,?,?,?)
            """,
            (
                category,
                name.strip(),
                specs.strip(),
                photo_id or ""
            )
        )

        conn.commit()

        product_id = cur.lastrowid

        conn.close()

    return product_id


def update_product(
    product_id,
    field,
    value
):

    allowed = [
        "name",
        "specs",
        "photo_id",
        "category"
    ]

    if field not in allowed:
        return

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

        conn.commit()
        conn.close()


def delete_product(product_id):

    with db_lock:

        conn = db()

        conn.execute(
            "DELETE FROM products WHERE id=?",
            (product_id,)
        )

        conn.commit()
        conn.close()


def all_products():

    with db_lock:

        conn = db()

        rows = conn.execute(
            """
            SELECT *
            FROM products
            ORDER BY category,id
            """
        ).fetchall()

        conn.close()

    return rows


def support_text():

    text = get_setting(
        "support_text"
    )

    if text:
        return text

    return (
        "<b>📞 پشتیبانی موبایل پاسارگاد</b>\n\n"
        "برای خرید و دریافت اطلاعات محصولات "
        "با ما در ارتباط باشید.\n\n"
        "📱 اطلاعات پشتیبانی هنوز ثبت نشده است."
    )


def ai_from_photo(image_bytes):

    if not AI_KEY:

        raise RuntimeError(
            "OPENAI_API_KEY در Railway تنظیم نشده است."
        )

    encoded = base64.b64encode(
        image_bytes
    ).decode("utf-8")

    data_url = (
        "data:image/jpeg;base64,"
        + encoded
    )

    prompt = """
این عکس مربوط به محصول فروشگاه موبایل
و لوازم جانبی است.

مدل و نام محصول را از روی بسته‌بندی
و خود محصول تا حد ممکن دقیق تشخیص بده.

اگر محصول موبایل است، برند را فقط
از بین این‌ها انتخاب کن:

Apple
Samsung
Xiaomi
Vocal
Realme
Nokia

برای سایر محصولات، نام دقیق محصول
را بنویس.

فقط JSON معتبر برگردان و هیچ متن دیگری ننویس:

{
  "category": "mobile",
  "name": "نام محصول",
  "specs": "۳ تا ۶ مشخصه کوتاه و مفید به فارسی"
}

category باید فقط یکی از این موارد باشد:

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

اگر چیزی را مطمئن نیستی،
حدس خطرناک نزن و آن بخش را خالی بگذار.
"""

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

        "max_tokens": 500
    }

    response = requests.post(

        AI_URL,

        headers={

            "Authorization":
                f"Bearer {AI_KEY}",

            "Content-Type":
                "application/json"
        },

        json=payload,

        timeout=60
    )

    if response.status_code != 200:

        raise RuntimeError(
            f"AI error {response.status_code}: "
            f"{response.text[:300]}"
        )

    result = response.json()

    content = (
        result["choices"][0]
        ["message"]["content"]
        .strip()
    )

    if content.startswith("```"):

        content = (
            content
            .replace("```json", "")
            .replace("```", "")
            .strip()
        )

    return json.loads(content)


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

        "سلام 👋\n\n"
        "<b>به ربات موبایل پاسارگاد خوش آمدید.</b>\n"
        "دسته محصول موردنظر را انتخاب کنید:",

        reply_markup=main_keyboard(
            message.from_user.id
        )
    )


@bot.message_handler(
    commands=["admin"]
)
def admin_command(message):

    user_id = message.from_user.id

    if claim_admin(user_id):

        bot.send_message(

            message.chat.id,

            "✅ پنل مدیریت برای شما فعال شد.",

            reply_markup=admin_keyboard()
        )

    else:

        bot.send_message(
            message.chat.id,
            "⛔ دسترسی ندارید."
        )


@bot.message_handler(
    commands=["id"]
)
def show_id(message):

    bot.send_message(

        message.chat.id,

        "شناسه عددی شما:\n"
        f"<code>{message.from_user.id}</code>"
    )


@bot.callback_query_handler(
    func=lambda call:
        call.data == "noop"
)
def noop(call):

    bot.answer_callback_query(
        call.id
    )


@bot.callback_query_handler(
    func=lambda call:
        call.data.startswith("cat:")
)
def category_callback(call):

    category = call.data.split(
        ":",
        1
    )[1]

    user_category[
        call.from_user.id
    ] = category

    bot.answer_callback_query(
        call.id
    )

    send_product(
        call.message.chat.id,
        category,
        0
    )


@bot.callback_query_handler(
    func=lambda call:
        call.data.startswith("nav:")
)
def navigation_callback(call):

    _, category, index = (
        call.data.split(":")
    )

    bot.answer_callback_query(
        call.id
    )

    send_product(

        call.message.chat.id,

        category,

        int(index),

        edit_message_id=
            call.message.message_id
    )


def begin_manual_add(message):

    user_state[
        message.from_user.id
    ] = {

        "action": "add",

        "step": "category"
    }

    bot.send_message(

        message.chat.id,

        "دسته محصول را انتخاب کن:",

        reply_markup=
            category_keyboard()
    )


def begin_ai_add(message):

    user_state[
        message.from_user.id
    ] = {

        "action": "ai_add",

        "step": "photo"
    }

    bot.send_message(

        message.chat.id,

        "📸 عکس واضح محصول را بفرست.\n\n"
        "من مدل، نام و مشخصات را بررسی می‌کنم "
        "و قبل از ذخیره نتیجه را به تو نشان می‌دهم."
    )


def send_product_list_for_edit(
    message,
    mode
):

    rows = all_products()

    if not rows:

        bot.send_message(
            message.chat.id,
            "هنوز محصولی ثبت نشده است."
        )

        return

    kb = types.InlineKeyboardMarkup(
        row_width=1
    )

    for product in rows:

        title = (
            f"{category_label(product['category'])}"
            f" | {product['name']}"
        )

        kb.add(

            types.InlineKeyboardButton(

                title[:60],

                callback_data=
                    f"{mode}:{product['id']}"
            )
        )

    bot.send_message(

        message.chat.id,

        "محصول را انتخاب کن:",

        reply_markup=kb
    )


@bot.callback_query_handler(
    func=lambda call:
        call.data.startswith("edit:")
)
def edit_select(call):

    if not is_admin(
        call.from_user.id
    ):

        bot.answer_callback_query(
            call.id,
            "دسترسی ندارید.",
            show_alert=True
        )

        return

    product_id = int(
        call.data.split(":")[1]
    )

    user_state[
        call.from_user.id
    ] = {

        "action": "edit",

        "product_id": product_id,

        "step": "field"
    }

    kb = types.InlineKeyboardMarkup(
        row_width=2
    )

    kb.add(

        types.InlineKeyboardButton(
            "✏️ نام",
            callback_data="field:name"
        ),

        types.InlineKeyboardButton(
            "📝 مشخصات",
            callback_data="field:specs"
        )
    )

    kb.add(

        types.InlineKeyboardButton(
            "🖼 عکس",
            callback_data="field:photo"
        )
    )

    bot.answer_callback_query(
        call.id
    )

    bot.send_message(

        call.message.chat.id,

        "چه چیزی را ویرایش کنم؟",

        reply_markup=kb
    )


@bot.callback_query_handler(
    func=lambda call:
        call.data.startswith("delete:")
)
def delete_select(call):

    if not is_admin(
        call.from_user.id
    ):

        bot.answer_callback_query(
            call.id,
            "دسترسی ندارید.",
            show_alert=True
        )

        return

    product_id = int(
        call.data.split(":")[1]
    )

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


@bot.callback_query_handler(
    func=lambda call:
        call.data.startswith("field:")
)
def field_select(call):

    if not is_admin(
        call.from_user.id
    ):

        bot.answer_callback_query(
            call.id,
            "دسترسی ندارید.",
            show_alert=True
        )

        return

    field = call.data.split(
        ":"
    )[1]

    state = user_state.get(
        call.from_user.id
    )

    if not state:

        bot.answer_callback_query(
            call.id
        )

        return

    state["field"] = field

    state["step"] = "value"

    bot.answer_callback_query(
        call.id
    )

    if field == "photo":

        bot.send_message(
            call.message.chat.id,
            "🖼 عکس جدید محصول را بفرست."
        )

    else:

        bot.send_message(
            call.message.chat.id,
            "مقدار جدید را بفرست."
        )


@bot.callback_query_handler(
    func=lambda call:
        call.data in (
            "ai:save",
            "ai:cancel"
        )
)
def ai_confirm(call):

    if not is_admin(
        call.from_user.id
    ):

        bot.answer_callback_query(
            call.id,
            "دسترسی ندارید.",
            show_alert=True
        )

        return

    user_id = call.from_user.id

    state = user_state.get(
        user_id
    )

    if call.data == "ai:cancel":

        user_state.pop(
            user_id,
            None
        )

        bot.answer_callback_query(
            call.id
        )

        bot.send_message(

            call.message.chat.id,

            "لغو شد.",

            reply_markup=
                admin_keyboard()
        )

        return

    if not state:

        bot.answer_callback_query(
            call.id,
            "اطلاعات پیدا نشد.",
            show_alert=True
        )

        return

    result = state.get(
        "ai_result"
    )

    if not result:

        bot.answer_callback_query(
            call.id,
            "اطلاعات پیدا نشد.",
            show_alert=True
        )

        return

    category = result.get(
        "category",
        "other"
    )

    valid_categories = [
        item[1]
        for item in CATEGORIES
    ]

    if category not in valid_categories:
        category = "other"

    add_product(

        category,

        result.get(
            "name",
            "محصول جدید"
        ),

        result.get(
            "specs",
            ""
        ),

        state.get(
            "photo_id",
            ""
        )
    )

    user_state.pop(
        user_id,
        None
    )

    bot.answer_callback_query(
        call.id,
        "ذخیره شد."
    )

    bot.send_message(

        call.message.chat.id,

        "✅ محصول با موفقیت ذخیره شد.",

        reply_markup=
            admin_keyboard()
    )


@bot.message_handler(
    content_types=["photo"]
)
def photo_handler(message):

    user_id = message.from_user.id

    state = user_state.get(
        user_id
    )

    if not state or not is_admin(
        user_id
    ):

        bot.send_message(

            message.chat.id,

            "برای افزودن محصول با عکس، "
            "ابتدا وارد پنل مدیریت شوید."
        )

        return

    # AI PHOTO ADD
    if state.get(
        "action"
    ) == "ai_add":

        try:

            file_info = bot.get_file(
                message.photo[-1].file_id
            )

            image_bytes = bot.download_file(
                file_info.file_path
            )

            bot.send_message(

                message.chat.id,

                "🤖 عکس دریافت شد؛ "
                "در حال بررسی مدل و مشخصات..."
            )

            result = ai_from_photo(
                image_bytes
            )

            state["ai_result"] = result

            state["photo_id"] = (
                message.photo[-1].file_id
            )

            state["step"] = "confirm"

            text = (

                "<b>نتیجه بررسی:</b>\n\n"

                f"📂 دسته: "
                f"{category_label(result.get('category','other'))}\n\n"

                f"📱 نام: "
                f"{result.get('name','')}\n\n"

                f"📝 مشخصات:\n"
                f"{result.get('specs','')}\n\n"

                "اگر درست است «ذخیره» را بزن؛ "
                "اگر نه «لغو» را بزن."
            )

            kb = types.InlineKeyboardMarkup()

            kb.add(

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

                "❌ هوش مصنوعی نتوانست عکس را بررسی کند.\n\n"
                f"خطا:\n<code>{str(error)[:300]}</code>\n\n"
                "می‌توانی از «افزودن محصول» "
                "به‌صورت دستی استفاده کنی."
            )

        return

    # EDIT PHOTO
    if (
        state.get("action") == "edit"
        and
        state.get("field") == "photo"
    ):

        update_product(

            state["product_id"],

            "photo_id",

            message.photo[-1].file_id
        )

        user_state.pop(
            user_id,
            None
        )

        bot.send_message(

            message.chat.id,

            "✅ عکس محصول ویرایش شد.",

            reply_markup=
                admin_keyboard()
        )

        return

    # MANUAL ADD PHOTO
    if (
        state.get("action") == "add"
        and
        state.get("step") == "photo"
    ):

        state["photo_id"] = (
            message.photo[-1].file_id
        )

        add_product(

            state["category"],

            state["name"],

            state["specs"],

            state["photo_id"]
        )

        user_state.pop(
            user_id,
            None
        )

        bot.send_message(

            message.chat.id,

            "✅ محصول با موفقیت ذخیره شد.",

            reply_markup=
                admin_keyboard()
        )

        return


@bot.message_handler(
    func=lambda message: True
)
def text_handler(message):

    user_id = message.from_user.id

    text = (
        message.text or ""
    ).strip()

    state = user_state.get(
        user_id
    )

    # MAIN CATEGORIES
    for label, category in CATEGORIES:

        if text == label:

            user_category[
                user_id
            ] = category

            send_product(

                message.chat.id,

                category,

                0
            )

            return

    # SUPPORT
    if text == "📞 پشتیبانی":

        bot.send_message(

            message.chat.id,

            support_text()
        )

        return

    # ADMIN PANEL
    if text == "⚙️ پنل مدیریت":

        if is_admin(user_id):

            bot.send_message(

                message.chat.id,

                "⚙️ پنل مدیریت",

                reply_markup=
                    admin_keyboard()
            )

        else:

            bot.send_message(

                message.chat.id,

                "⛔ دسترسی ندارید."
            )

        return

    # BACK
    if text == "⬅️ بازگشت به منو":

        user_state.pop(
            user_id,
            None
        )

        bot.send_message(

            message.chat.id,

            "منوی اصلی:",

            reply_markup=
                main_keyboard(user_id)
        )

        return

    # ONLY ADMIN FROM HERE
    if not is_admin(user_id):
        return

    # ADD PRODUCT
    if text == "➕ افزودن محصول":

        begin_manual_add(
            message
        )

        return

    # AI ADD
    if text == "🤖 افزودن با عکس":

        begin_ai_add(
            message
        )

        return

    # EDIT
    if text == "✏️ ویرایش محصول":

        send_product_list_for_edit(

            message,

            "edit"
        )

        return

    # DELETE
    if text == "🗑 حذف محصول":

        send_product_list_for_edit(

            message,

            "delete"
        )

        return

    # PRODUCT LIST
    if text == "📋 لیست محصولات":

        rows = all_products()

        if not rows:

            bot.send_message(

                message.chat.id,

                "لیست محصولات خالی است."
            )

            return

        lines = [
            "<b>📋 محصولات ثبت‌شده:</b>\n"
        ]

        for product in rows:

            lines.append(

                f"• "
                f"{category_label(product['category'])}"
                f" — "
                f"{product['name']}"
                f"  "
                f"(ID: {product['id']})"
            )

        bot.send_message(

            message.chat.id,

            "\n".join(lines)
        )

        return

    # EDIT SUPPORT
    if text == "📞 ویرایش پشتیبانی":

        user_state[
            user_id
        ] = {

            "action": "support",

            "step": "value"
        }

        bot.send_message(

            message.chat.id,

            "متن کامل پشتیبانی را بفرست.\n\n"
            "همین متن بعداً با زدن "
            "«پشتیبانی» به مشتری نمایش داده می‌شود."
        )

        return

    # MANUAL ADD FLOW
    if (
        state
        and
        state.get("action") == "add"
    ):

        step = state.get(
            "step"
        )

        # CATEGORY
        if step == "category":

            for label, category in CATEGORIES:

                if text == label:

                    state["category"] = category

                    state["step"] = "name"

                    bot.send_message(

                        message.chat.id,

                        "📱 نام محصول را بفرست."
                    )

                    return

            bot.send_message(

                message.chat.id,

                "لطفاً یکی از دسته‌ها را انتخاب کن.",

                reply_markup=
                    category_keyboard()
            )

            return

        # NAME
        if step == "name":

            state["name"] = text

            state["step"] = "specs"

            bot.send_message(

                message.chat.id,

                "📝 مشخصات محصول را بفرست."
            )

            return

        # SPECS
        if step == "specs":

            state["specs"] = text

            state["step"] = "photo"

            bot.send_message(

                message.chat.id,

                "🖼 حالا عکس محصول را بفرست.\n\n"
                "اگر عکس نداری، بنویس:\n"
                "بدون عکس"
            )

            return

        # NO PHOTO
        if (
            step == "photo"
            and
            text == "بدون عکس"
        ):

            add_product(

                state["category"],

                state["name"],

                state["specs"],

                ""
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

    # EDIT TEXT
    if (
        state
        and
        state.get("action") == "edit"
        and
        state.get("step") == "value"
    ):

        update_product(

            state["product_id"],

            state["field"],

            text
        )

        user_state.pop(
            user_id,
            None
        )

        bot.send_message(

            message.chat.id,

            "✅ محصول ویرایش شد.",

            reply_markup=
                admin_keyboard()
        )

        return

    # SUPPORT TEXT
    if (
        state
        and
        state.get("action") == "support"
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

            "✅ متن پشتیبانی ذخیره شد.",

            reply_markup=
                admin_keyboard()
        )

        return


init_db()

print(
    "Mobile Pasargad bot is running..."
)

bot.infinity_polling(

    timeout=30,

    long_polling_timeout=30,

    skip_pending=True
)