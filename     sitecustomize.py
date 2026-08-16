# ==========================================
# Mobile Pasargad - User Analytics Add-on
# ==========================================

import os
import sqlite3
import threading
from datetime import datetime, timedelta

import telebot
from telebot import types

try:
    from telebot.handler_backends import ContinueHandling
except Exception:
    ContinueHandling = None


DB_FILE = (
    os.getenv("DB_FILE", "mobile_pasargad.db").strip()
    or "mobile_pasargad.db"
)

ADMIN_ID = os.getenv("ADMIN_ID", "1040416634").strip()

_db_lock = threading.RLock()


def _connect():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_analytics_db():
    with _db_lock:
        conn = _connect()

        conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_users (
                user_id INTEGER PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                username TEXT,
                first_seen TEXT,
                last_seen TEXT,
                activity_count INTEGER DEFAULT 0,
                session_count INTEGER DEFAULT 0,
                last_action TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                event_type TEXT,
                event_text TEXT,
                created_at TEXT
            )
        """)

        conn.commit()
        conn.close()


def _record_user(user, event_type, event_text=""):
    if not user:
        return

    now = datetime.now()
    now_text = now.strftime("%Y-%m-%d %H:%M:%S")
    user_id = int(user.id)

    first_name = getattr(user, "first_name", "") or ""
    last_name = getattr(user, "last_name", "") or ""
    username = getattr(user, "username", "") or ""

    with _db_lock:
        conn = _connect()

        old = conn.execute(
            "SELECT last_seen FROM bot_users WHERE user_id=?",
            (user_id,)
        ).fetchone()

        new_session = 1

        if old and old["last_seen"]:
            try:
                last_seen = datetime.strptime(
                    old["last_seen"],
                    "%Y-%m-%d %H:%M:%S"
                )

                if now - last_seen < timedelta(minutes=30):
                    new_session = 0
            except Exception:
                new_session = 0

        conn.execute("""
            INSERT INTO bot_users (
                user_id,
                first_name,
                last_name,
                username,
                first_seen,
                last_seen,
                activity_count,
                session_count,
                last_action
            )
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)

            ON CONFLICT(user_id) DO UPDATE SET
                first_name=excluded.first_name,
                last_name=excluded.last_name,
                username=excluded.username,
                last_seen=excluded.last_seen,
                activity_count=bot_users.activity_count + 1,
                session_count=bot_users.session_count + excluded.session_count,
                last_action=excluded.last_action
        """, (
            user_id,
            first_name,
            last_name,
            username,
            now_text,
            now_text,
            new_session,
            f"{event_type}: {event_text}"[:500]
        ))

        conn.execute("""
            INSERT INTO bot_activity (
                user_id,
                event_type,
                event_text,
                created_at
            )
            VALUES (?, ?, ?, ?)
        """, (
            user_id,
            event_type,
            str(event_text)[:500],
            now_text
        ))

        conn.commit()
        conn.close()


def _is_admin(user_id):
    return str(user_id) == ADMIN_ID


def _analytics_menu(bot, chat_id):
    with _db_lock:
        conn = _connect()

        total = conn.execute(
            "SELECT COUNT(*) AS n FROM bot_users"
        ).fetchone()["n"]

        today = datetime.now().strftime("%Y-%m-%d")

        active_today = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM bot_users
            WHERE substr(last_seen,1,10)=?
            """,
            (today,)
        ).fetchone()["n"]

        activities = conn.execute(
            "SELECT COUNT(*) AS n FROM bot_activity"
        ).fetchone()["n"]

        conn.close()

    keyboard = types.InlineKeyboardMarkup()

    keyboard.row(
        types.InlineKeyboardButton(
            "👥 همه کاربران",
            callback_data="ana:users:0"
        )
    )

    keyboard.row(
        types.InlineKeyboardButton(
            "🕘 آخرین فعالیت‌ها",
            callback_data="ana:events:0"
        )
    )

    text = (
        "👥 <b>کاربران ربات</b>\n\n"
        f"👤 کل کاربران: <b>{total}</b>\n"
        f"🟢 فعال امروز: <b>{active_today}</b>\n"
        f"🧾 کل فعالیت‌ها: <b>{activities}</b>"
    )

    bot.send_message(
        chat_id,
        text,
        parse_mode="HTML",
        reply_markup=keyboard
    )


def _show_users(bot, chat_id, page=0):
    offset = page * 10

    with _db_lock:
        conn = _connect()

        rows = conn.execute("""
            SELECT *
            FROM bot_users
            ORDER BY last_seen DESC
            LIMIT 10 OFFSET ?
        """, (offset,)).fetchall()

        conn.close()

    keyboard = types.InlineKeyboardMarkup()

    for row in rows:
        name = (
            f"{row['first_name'] or ''} "
            f"{row['last_name'] or ''}"
        ).strip()

        if not name:
            name = "بدون نام"

        keyboard.add(
            types.InlineKeyboardButton(
                f"👤 {name}"[:60],
                callback_data=f"ana:user:{row['user_id']}"
            )
        )

    navigation = []

    if page > 0:
        navigation.append(
            types.InlineKeyboardButton(
                "⬅️ قبلی",
                callback_data=f"ana:users:{page - 1}"
            )
        )

    if len(rows) == 10:
        navigation.append(
            types.InlineKeyboardButton(
                "بعدی ➡️",
                callback_data=f"ana:users:{page + 1}"
            )
        )

    if navigation:
        keyboard.row(*navigation)

    bot.send_message(
        chat_id,
        "👥 <b>لیست کاربران ربات</b>",
        parse_mode="HTML",
        reply_markup=keyboard
    )


def _show_user(bot, chat_id, user_id):
    with _db_lock:
        conn = _connect()

        row = conn.execute(
            "SELECT * FROM bot_users WHERE user_id=?",
            (user_id,)
        ).fetchone()

        conn.close()

    if not row:
        bot.send_message(chat_id, "کاربر پیدا نشد.")
        return

    name = (
        f"{row['first_name'] or ''} "
        f"{row['last_name'] or ''}"
    ).strip()

    username = (
        f"@{row['username']}"
        if row["username"]
        else "ندارد"
    )

    text = (
        "👤 <b>اطلاعات کاربر</b>\n\n"
        f"نام: {name or 'ندارد'}\n"
        f"یوزرنیم: {username}\n"
        f"🆔 ID: <code>{user_id}</code>\n\n"
        f"📅 اولین ورود: {row['first_seen']}\n"
        f"🕘 آخرین فعالیت: {row['last_seen']}\n"
        f"🔁 تعداد ورود/نشست: {row['session_count']}\n"
        f"📊 تعداد فعالیت: {row['activity_count']}\n\n"
        f"🔎 آخرین کار:\n{row['last_action'] or 'ندارد'}"
    )

    keyboard = types.InlineKeyboardMarkup()

    keyboard.add(
        types.InlineKeyboardButton(
            "📜 تاریخچه فعالیت",
            callback_data=f"ana:history:{user_id}:0"
        )
    )

    # Telegram only exposes profile photos the user has made
    # available to the bot/API.
    try:
        photos = bot.get_user_profile_photos(
            user_id,
            limit=1
        )

        if photos.total_count > 0:
            bot.send_photo(
                chat_id,
                photos.photos[0][-1].file_id,
                caption=text,
                parse_mode="HTML",
                reply_markup=keyboard
            )
            return
    except Exception:
        pass

    bot.send_message(
        chat_id,
        text,
        parse_mode="HTML",
        reply_markup=keyboard
    )


def _show_history(bot, chat_id, user_id, page=0):
    offset = page * 15

    with _db_lock:
        conn = _connect()

        rows = conn.execute("""
            SELECT *
            FROM bot_activity
            WHERE user_id=?
            ORDER BY id DESC
            LIMIT 15 OFFSET ?
        """, (user_id, offset)).fetchall()

        conn.close()

    lines = ["📜 <b>تاریخچه فعالیت کاربر</b>\n"]

    if not rows:
        lines.append("فعالیتی ثبت نشده.")

    for row in rows:
        lines.append(
            f"• {row['created_at']}\n"
            f"  {row['event_type']} → "
            f"{row['event_text'] or '-'}"
        )

    keyboard = types.InlineKeyboardMarkup()
    nav = []

    if page > 0:
        nav.append(
            types.InlineKeyboardButton(
                "⬅️ قبلی",
                callback_data=f"ana:history:{user_id}:{page - 1}"
            )
        )

    if len(rows) == 15:
        nav.append(
            types.InlineKeyboardButton(
                "بعدی ➡️",
                callback_data=f"ana:history:{user_id}:{page + 1}"
            )
        )

    if nav:
        keyboard.row(*nav)

    bot.send_message(
        chat_id,
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=keyboard
    )


def _show_recent_events(bot, chat_id):
    with _db_lock:
        conn = _connect()

        rows = conn.execute("""
            SELECT
                a.*,
                u.first_name,
                u.last_name
            FROM bot_activity a
            LEFT JOIN bot_users u
                ON u.user_id=a.user_id
            ORDER BY a.id DESC
            LIMIT 30
        """).fetchall()

        conn.close()

    lines = ["🕘 <b>آخرین فعالیت‌های ربات</b>\n"]

    for row in rows:
        name = (
            f"{row['first_name'] or ''} "
            f"{row['last_name'] or ''}"
        ).strip()

        if not name:
            name = str(row["user_id"])

        lines.append(
            f"• {row['created_at']}\n"
            f"👤 {name}\n"
            f"🔎 {row['event_type']} → "
            f"{row['event_text'] or '-'}\n"
        )

    text = "\n".join(lines)

    # Avoid Telegram message length limit.
    if len(text) > 3900:
        text = text[:3900] + "\n..."

    bot.send_message(
        chat_id,
        text,
        parse_mode="HTML"
    )


# --------------------------------------------------
# Install analytics without editing bot.py
# --------------------------------------------------

_original_init = telebot.TeleBot.__init__


def _patched_init(self, *args, **kwargs):
    _original_init(self, *args, **kwargs)

    @self.message_handler(
        content_types=[
            "text",
            "photo",
            "document",
            "video",
            "voice",
            "audio",
            "contact",
            "location",
            "sticker"
        ],
        func=lambda message: True
    )
    def _analytics_message(message):
        try:
            content_type = getattr(
                message,
                "content_type",
                "unknown"
            )

            event_text = ""

            if content_type == "text":
                event_text = message.text or ""

                if event_text.startswith("/start"):
                    event_type = "START"
                else:
                    event_type = "TEXT"

            else:
                event_type = content_type.upper()
                event_text = content_type

            _record_user(
                message.from_user,
                event_type,
                event_text
            )

            # Admin analytics command/button
            if (
                content_type == "text"
                and event_text.strip() == "👥 کاربران ربات"
                and _is_admin(message.from_user.id)
            ):
                _analytics_menu(
                    self,
                    message.chat.id
                )
                return

        except Exception as exc:
            print("Analytics message error:", exc)

        if ContinueHandling:
            return ContinueHandling()


    @self.callback_query_handler(
        func=lambda call: True
    )
    def _analytics_callback(call):
        try:
            _record_user(
                call.from_user,
                "BUTTON",
                call.data or ""
            )

            data = call.data or ""

            if not data.startswith("ana:"):
                if ContinueHandling:
                    return ContinueHandling()
                return

            if not _is_admin(call.from_user.id):
                try:
                    self.answer_callback_query(
                        call.id,
                        "دسترسی ندارید."
                    )
                except Exception:
                    pass
                return

            try:
                self.answer_callback_query(call.id)
            except Exception:
                pass

            parts = data.split(":")
            chat_id = call.message.chat.id

            if parts[1] == "users":
                _show_users(
                    self,
                    chat_id,
                    int(parts[2])
                )

            elif parts[1] == "user":
                _show_user(
                    self,
                    chat_id,
                    int(parts[2])
                )

            elif parts[1] == "history":
                _show_history(
                    self,
                    chat_id,
                    int(parts[2]),
                    int(parts[3])
                )

            elif parts[1] == "events":
                _show_recent_events(
                    self,
                    chat_id
                )

        except Exception as exc:
            print("Analytics callback error:", exc)

        if ContinueHandling:
            return ContinueHandling()


telebot.TeleBot.__init__ = _patched_init

_init_analytics_db()