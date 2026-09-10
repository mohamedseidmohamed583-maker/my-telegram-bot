import os
import json
import asyncio

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand
)

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters
)

import yt_dlp


# ==================================================
# CONFIGURATION
# ==================================================

# ⚠️ አዲሱን BotFather TOKEN እዚህ አስገባ
TOKEN = "8795814797:AAFVzEEUF9vBh0kfwrD_r4CPRVRtklmGtCo"

ADMIN_ID = 6753546651


# ==================================================
# FORCE JOIN CHANNEL
# ==================================================

FORCE_CHANNEL = "@mame_posts"
FORCE_CHANNEL_LINK = "https://t.me/mame_posts"


# ==================================================
# CUSTOM EMOJI IDs
# ==================================================

# ---------- WELCOME / PLATFORM EMOJIS ----------

EMOJI_WELCOME = "53055770864784895215305739801314501775"

EMOJI_OPTIONS = "5305290882742788410"

EMOJI_TIKTOK = "5305551797711053969"

EMOJI_INSTAGRAM = "5305777524012262308"

EMOJI_YOUTUBE = "5305474827602140530"

EMOJI_TWITTER = "5305311717629142471"

EMOJI_FACEBOOK = "5305749202997911340"


# ---------- MAIN MENU BUTTON EMOJIS ----------

EMOJI_ORDER = "5197304993920616826"

EMOJI_PRICE = "5447458260200214425"

EMOJI_PAYMENT_BANK = "5961054379350955385"

EMOJI_PAYMENT_TELEBIRR = "5960632377339285724"

EMOJI_STATUS = "5431577498364158238"

EMOJI_SUPPORT = "5305545479814161889"


# ==================================================
# DATABASE MANAGEMENT
# ==================================================

DATA_FILE = "user_data.json"


def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    return {}


def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        print("Save Error:", e)


def record_user_activity(user_id):
    data = load_data()

    uid_str = str(user_id)

    if uid_str not in data:
        data[uid_str] = {
            "msg_count": 0
        }

    data[uid_str]["msg_count"] = (
        data[uid_str].get("msg_count", 0) + 1
    )

    save_data(data)


def get_user_stats(user_id):
    data = load_data()

    uid_str = str(user_id)

    total_users = len(data)

    user_msg_count = data.get(
        uid_str,
        {}
    ).get(
        "msg_count",
        0
    )

    return total_users, user_msg_count


# ==================================================
# MAIN MENU
# ==================================================

def get_main_menu_keyboard():

    keyboard = [

        # ORDER
        [
            InlineKeyboardButton(
                "ማስታወቂያ ለማሰራት",
                callback_data="cmd_order",
                icon_custom_emoji_id=EMOJI_ORDER
            )
        ],

        # PRICE + PAYMENT
        [
            InlineKeyboardButton(
                "Price | ዋጋ",
                callback_data="cmd_price",
                icon_custom_emoji_id=EMOJI_PRICE
            ),

            InlineKeyboardButton(
                "Payment Method",
                callback_data="cmd_payment",
                icon_custom_emoji_id=EMOJI_PAYMENT_BANK
            )
        ],

        # STATUS
        [
            InlineKeyboardButton(
                "My Status & Stats",
                callback_data="cmd_status",
                icon_custom_emoji_id=EMOJI_STATUS
            )
        ],

        # SUPPORT
        [
            InlineKeyboardButton(
                "Support & Platforms",
                callback_data="cmd_support",
                icon_custom_emoji_id=EMOJI_SUPPORT
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


# ==================================================
# BACK BUTTON
# ==================================================

def get_back_keyboard():

    keyboard = [
        [
            InlineKeyboardButton(
                "🔙 Back to Menu",
                callback_data="cmd_back"
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


# ==================================================
# PREMIUM WELCOME MESSAGE
# ==================================================

def get_welcome_message():

    return (
        f'<tg-emoji emoji-id="{EMOJI_WELCOME}">👋</tg-emoji> '
        '<b>እንኳን ደህና መጡ!</b> 🙂\n\n'

        f'<tg-emoji emoji-id="{EMOJI_OPTIONS}">🛠️</tg-emoji> '
        '<b>My options:</b>\n\n'

        f'<tg-emoji emoji-id="{EMOJI_TIKTOK}">🎵</tg-emoji> '
        '<b>TikTok:</b> videos & photos\n'

        f'<tg-emoji emoji-id="{EMOJI_INSTAGRAM}">📸</tg-emoji> '
        '<b>Instagram:</b> reels, posts & stories\n'

        f'<tg-emoji emoji-id="{EMOJI_YOUTUBE}">▶️</tg-emoji> '
        '<b>YouTube:</b> videos & music\n'

        f'<tg-emoji emoji-id="{EMOJI_TWITTER}">❌</tg-emoji> '
        '<b>Twitter (X):</b> videos & voice\n'

        f'<tg-emoji emoji-id="{EMOJI_FACEBOOK}">📘</tg-emoji> '
        '<b>Facebook:</b> video\n\n'

        'And others: 📥'
    )


# ==================================================
# AUTO SET BOT COMMANDS
# ==================================================

async def post_init(application):

    commands = [

        BotCommand(
            "start",
            "ቦቱን ለመጀመር"
        ),

        BotCommand(
            "menu",
            "ዋና ማውጫ"
        ),

        BotCommand(
            "status",
            "የእርስዎን እና የቦቱን Status ለማየት"
        ),

        BotCommand(
            "rates",
            "የማስታወቂያ ዋጋዎች"
        ),

        BotCommand(
            "payment",
            "የክፍያ መንገድ"
        ),

        BotCommand(
            "help",
            "እርዳታና ድጋፍ"
        )
    ]

    await application.bot.set_my_commands(commands)


# ==================================================
# CHECK CHANNEL JOIN
# ==================================================

async def is_joined(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    try:

        member = await context.bot.get_chat_member(
            chat_id=FORCE_CHANNEL,
            user_id=user_id
        )

        return member.status in [
            "member",
            "administrator",
            "creator"
        ]

    except Exception as e:

        print(
            "Force Join Error:",
            e
        )

        return True


# ==================================================
# FORCE JOIN MESSAGE
# ==================================================

async def show_force_join(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    keyboard = [

        [
            InlineKeyboardButton(
                "📢 Join Channel",
                url=FORCE_CHANNEL_LINK
            )
        ],

        [
            InlineKeyboardButton(
                "✅ I've Joined",
                callback_data="check_join"
            )
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:

        await update.message.reply_text(

            "🔒 <b>ቦቱን ለመጠቀም ከታች ያለውን "
            "ቻናል መቀላቀል አለብዎት!</b>\n\n"

            "1️⃣ 📢 Join Channel የሚለውን ይጫኑ።\n"

            "2️⃣ ከዚያ ✅ I've Joined ይጫኑ።",

            reply_markup=reply_markup,

            parse_mode="HTML"
        )


# ==================================================
# START
# ==================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    record_user_activity(user_id)

    if not await is_joined(
        update,
        context
    ):

        await show_force_join(
            update,
            context
        )

        return

    await update.message.reply_text(

        get_welcome_message(),

        reply_markup=get_main_menu_keyboard(),

        parse_mode="HTML"
    )


# ==================================================
# STATUS COMMAND
# ==================================================

async def status_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    record_user_activity(
        user.id
    )

    if not await is_joined(
        update,
        context
    ):

        await show_force_join(
            update,
            context
        )

        return

    total_users, user_msg_count = (
        get_user_stats(user.id)
    )

    username_text = (
        f"@{user.username}"
        if user.username
        else "የለውም"
    )

    msg = (

        "📊 <b>የእርስዎ እና የቦቱ Status</b>\n\n"

        "👤 <b>የግል መረጃዎት፦</b>\n"

        f"• <b>ስም:</b> {user.full_name}\n"

        f"• <b>Username:</b> {username_text}\n"

        f"• <b>Telegram ID:</b> "
        f"<code>{user.id}</code>\n"

        f"• <b>የላኳቸው አጠቃላይ መልዕክቶች:</b> "
        f"<code>{user_msg_count}</code>\n\n"

        "🤖 <b>የቦቱ አጠቃላይ መረጃ፦</b>\n"

        f"• <b>አጠቃላይ የቦቱ ተጠቃሚዎች:</b> "
        f"<code>{total_users} Users</code>\n"

        "• <b>ሁኔታ:</b> Active ✅"
    )

    await update.message.reply_text(
        msg,
        parse_mode="HTML"
    )


# ==================================================
# RATES COMMAND
# ==================================================

async def rates_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    record_user_activity(
        update.effective_user.id
    )

    if not await is_joined(
        update,
        context
    ):

        await show_force_join(
            update,
            context
        )

        return

    await update.message.reply_text(

        "💰 <b>የማስታወቂያ ዋጋዎች</b>\n\n"

        "📌 12 Hours — "
        "<b>በስምምነት ETB</b>\n"

        "📌 24 Hours — "
        "<b>500 ETB</b>\n"

        "📌 48 Hours — "
        "<b>700 ETB</b>\n\n"

        "የማስታወቂያውን አይነት አይተን "
        "አስተያየት እናደርጋለን! 🤝",

        parse_mode="HTML"
    )


# ==================================================
# PAYMENT COMMAND
# ==================================================

async def payment_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    record_user_activity(
        update.effective_user.id
    )

    if not await is_joined(
        update,
        context
    ):

        await show_force_join(
            update,
            context
        )

        return

    await update.message.reply_text(

        "💳 <b>Payment Method</b>\n\n"

        f'<tg-emoji emoji-id="{EMOJI_PAYMENT_BANK}">🏦</tg-emoji> '
        "<b>CBE / ንግድ ባንክ</b>\n"

        "1000528274394\n\n"

        "Mohammed Seid\n\n"

        f'<tg-emoji emoji-id="{EMOJI_PAYMENT_TELEBIRR}">📱</tg-emoji> '
        "<b>TELE BIRR</b>\n"

        "+251963266849\n",

        parse_mode="HTML"
    )


# ==================================================
# HELP COMMAND
# ==================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    record_user_activity(
        update.effective_user.id
    )

    if not await is_joined(
        update,
        context
    ):

        await show_force_join(
            update,
            context
        )

        return

    await update.message.reply_text(

        "💬 <b>Support & Downloader Help</b>\n\n"

        "📥 <b>ቪዲዮ ለማውረድ:</b>\n"

        "የ Instagram, TikTok, YouTube, "
        "Facebook, Pinterest ወይም Twitter "
        "ሊንክ ቀጥታ ለቦቱ ይላኩ።\n\n"

        "👨‍💻 ለአድሚን መልዕክት ለመላክም "
        "እዚሁ መጻፍ ይችላሉ።",

        parse_mode="HTML"
    )


# ==================================================
# DOWNLOAD ENGINE
# ==================================================

def download_video(
    url: str,
    output_template: str
):

    ydl_opts = {

        "format":
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]"
            "/best[ext=mp4]/best",

        "outtmpl":
            output_template,

        "quiet": True,

        "no_warnings": True,

        "nocheckcertificate": True,

        "ignoreerrors": False,

        "geo_bypass": True,

        "extractor_args": {

            "youtube": {
                "player_client": [
                    "android",
                    "web"
                ]
            },

            "facebook": {
                "fetch_shares": [False]
            }
        },

        "http_headers": {

            "User-Agent":
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/125.0.0.0 "
                "Safari/537.36"
        }
    }

    with yt_dlp.YoutubeDL(
        ydl_opts
    ) as ydl:

        ydl.download([url])


# ==================================================
# HANDLE URL DOWNLOAD
# ==================================================

async def handle_url_download(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    url: str
):

    status_msg = await update.message.reply_text(

        "🚀 <b>ቪዲዮውን በማውረድ ላይ ይገኛል፣ "
        "እባክዎ ይጠብቁ...</b> 📥",

        parse_mode="HTML"
    )

    bot_username = (
        context.bot.username
        or "mame_posts_bot"
    )

    share_url = (
        "https://t.me/share/url?"
        "url=https://t.me/"
        f"{bot_username}"
        "?start=share"
        "&text=Try%20this%20awesome%20Video%20Downloader%20Bot!🔥"
    )

    keyboard = [

        [
            InlineKeyboardButton(
                "🔗 Share Bot 🚀",
                url=share_url
            )
        ]
    ]

    reply_markup = InlineKeyboardMarkup(
        keyboard
    )

    file_base = (
        f"video_"
        f"{update.effective_user.id}_"
        f"{update.message.message_id}"
    )

    output_template = (
        f"{file_base}.%(ext)s"
    )

    expected_file = (
        f"{file_base}.mp4"
    )

    try:

        await asyncio.to_thread(
            download_video,
            url,
            output_template
        )

        actual_file = expected_file

        if not os.path.exists(
            actual_file
        ):

            for f in os.listdir("."):

                if f.startswith(
                    file_base
                ):

                    actual_file = f
                    break

        if os.path.exists(
            actual_file
        ):

            await status_msg.edit_text(

                "📤 <b>ቪዲዮውን በመላክ ላይ "
                "ይገኛል...</b>",

                parse_mode="HTML"
            )

            with open(
                actual_file,
                "rb"
            ) as video_file:

                await update.message.reply_video(

                    video=video_file,

                    caption=(
                        f"🚀 <b>Downloaded with</b> "
                        f"@{bot_username}\n\n"

                        "🥰 <b>Enjoy! Don't forget "
                        "to share it with your friends.</b>"
                    ),

                    reply_markup=reply_markup,

                    parse_mode="HTML"
                )

            await status_msg.delete()

            os.remove(
                actual_file
            )

        else:

            await status_msg.edit_text(

                "💔 <b>ቪዲዮውን ማግኘት "
                "አልተቻለም።</b>",

                parse_mode="HTML"
            )

    except Exception as e:

        print(
            "Download Error:",
            e
        )

        for f in os.listdir("."):

            if f.startswith(
                file_base
            ):

                try:
                    os.remove(f)
                except:
                    pass

        await status_msg.edit_text(

            "😭 <b>ቪዲዮውን ማውረድ "
            "አልተቻለም!</b>\n\n"

            "እባክዎ የላኩት ሊንክ "
            "ትክክለኛ መሆኑን አረጋግጠው "
            "እንደገና ይሞክሩ። "
            "በጣም ይቅርታ 👐",

            parse_mode="HTML"
        )


# ==================================================
# BUTTON CALLBACK
# ==================================================

async def button_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    data = query.data

    user = query.from_user


    # ------------------------------------------------
    # BACK
    # ------------------------------------------------

    if data == "cmd_back":

        await query.edit_message_text(

            get_welcome_message(),

            reply_markup=get_main_menu_keyboard(),

            parse_mode="HTML"
        )


    # ------------------------------------------------
    # PRICE
    # ------------------------------------------------

    elif data == "cmd_price":

        await query.edit_message_text(

            "💰 <b>የማስታወቂያ ዋጋዎች</b>\n\n"

            "📌 12 Hours — "
            "<b>በስምምነት ETB</b>\n"

            "📌 24 Hours — "
            "<b>500 ETB</b>\n"

            "📌 48 Hours — "
            "<b>700 ETB</b>\n\n"

            "የማስታወቂያውን አይነት "
            "አይተን አስተያየት "
            "እናደርጋለን! 🤝",

            reply_markup=get_back_keyboard(),

            parse_mode="HTML"
        )


    # ------------------------------------------------
    # ORDER
    # ------------------------------------------------

    elif data == "cmd_order":

        await query.edit_message_text(

            "📢 <b>ማስታወቂያ ለማሰራት</b>\n\n"

            "👇 እባክዎ ማስታወቂያ "
            "ማሰራት የሚፈልጉትን "
            "Post እዚህ ይላኩ 👐",

            reply_markup=get_back_keyboard(),

            parse_mode="HTML"
        )


    # ------------------------------------------------
    # STATUS
    # ------------------------------------------------

    elif data == "cmd_status":

        total_users, user_msg_count = (
            get_user_stats(user.id)
        )

        username_text = (
            f"@{user.username}"
            if user.username
            else "የለውም"
        )

        msg = (

            "📊 <b>የእርስዎ እና የቦቱ Status</b>\n\n"

            "👤 <b>የግል መረጃዎት፦</b>\n"

            f"• <b>ስም:</b> {user.full_name}\n"

            f"• <b>Username:</b> {username_text}\n"

            f"• <b>Telegram ID:</b> "
            f"<code>{user.id}</code>\n"

            f"• <b>የላኳቸው አጠቃላይ "
            f"መልዕክቶች:</b> "
            f"<code>{user_msg_count}</code>\n\n"

            "🤖 <b>የቦቱ አጠቃላይ መረጃ፦</b>\n"

            f"• <b>አጠቃላይ የቦቱ "
            f"ተጠቃሚዎች:</b> "
            f"<code>{total_users} Users</code>\n"

            "• <b>ሁኔታ:</b> Active ✅"
        )

        await query.edit_message_text(

            msg,

            reply_markup=get_back_keyboard(),

            parse_mode="HTML"
        )


    # ------------------------------------------------
    # PAYMENT
    # ------------------------------------------------

    elif data == "cmd_payment":

        await query.edit_message_text(

            "💳 <b>Payment Method</b>\n\n"

            f'<tg-emoji emoji-id="{EMOJI_PAYMENT_BANK}">'
            '🏦</tg-emoji> '
            "<b>ንግድ ባንክ / CBE</b>\n"

            "1000528274394\n\n"

            "Mohammed Seid\n\n"

            f'<tg-emoji emoji-id="{EMOJI_PAYMENT_TELEBIRR}">'
            '📱</tg-emoji> '
            "<b>TELE BIRR</b>\n"

            "+251963266849",

            reply_markup=get_back_keyboard(),

            parse_mode="HTML"
        )


    # ------------------------------------------------
    # SUPPORT
    # ------------------------------------------------

    elif data == "cmd_support":

        await query.edit_message_text(

            f'<tg-emoji emoji-id="{EMOJI_OPTIONS}">'
            '🛠️</tg-emoji> '
            '<b>My options:</b>\n\n'

            f'<tg-emoji emoji-id="{EMOJI_TIKTOK}">'
            '🎵</tg-emoji> '
            '<b>TikTok:</b> videos & photos\n'

            f'<tg-emoji emoji-id="{EMOJI_INSTAGRAM}">'
            '📸</tg-emoji> '
            '<b>Instagram:</b> reels, posts & stories\n'

            f'<tg-emoji emoji-id="{EMOJI_YOUTUBE}">'
            '▶️</tg-emoji> '
            '<b>YouTube:</b> videos & music\n'

            f'<tg-emoji emoji-id="{EMOJI_TWITTER}">'
            '❌</tg-emoji> '
            '<b>Twitter (X):</b> videos & voice\n'

            f'<tg-emoji emoji-id="{EMOJI_FACEBOOK}">'
            '📘</tg-emoji> '
            '<b>Facebook:</b> video\n\n'

            "And others: 📥",

            reply_markup=get_back_keyboard(),

            parse_mode="HTML"
        )


# ==================================================
# USER MESSAGE HANDLER
# ==================================================

async def handle_user_messages(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    user_id = update.effective_user.id

    record_user_activity(
        user_id
    )

    if not await is_joined(
        update,
        context
    ):

        await show_force_join(
            update,
            context
        )

        return

    text = update.message.text or ""


    # ------------------------------------------------
    # SUPPORTED DOMAINS
    # ------------------------------------------------

    valid_domains = [

        "instagram.com",
        "tiktok.com",
        "youtube.com",
        "youtu.be",

        "pinterest.com",
        "pin.it",

        "twitter.com",
        "x.com",

        "facebook.com",
        "fb.watch",

        "reddit.com",
        "soundcloud.com",
        "spotify.com",
        "vimeo.com",
        "twitch.tv",
        "tumblr.com",
        "vk.com"
    ]


    is_supported_link = any(

        domain in text.lower()

        for domain in valid_domains
    )


    # ------------------------------------------------
    # DOWNLOAD
    # ------------------------------------------------

    if is_supported_link:

        urls = [

            word

            for word in text.split()

            if word.startswith(
                "http://"
            )
            or word.startswith(
                "https://"
            )
        ]

        target_url = (
            urls[0]
            if urls
            else text
        )

        await handle_url_download(
            update,
            context,
            target_url
        )

        return


    # ------------------------------------------------
    # SEND MESSAGE TO ADMIN
    # ------------------------------------------------

    username = update.effective_user.username

    username_text = (
        f"@{username}"
        if username
        else "No Username"
    )


    header_msg = await context.bot.send_message(

        chat_id=ADMIN_ID,

        text=(

            "📩 <b>አዲስ መልዕክት!</b>\n\n"

            f"👤 User: "
            f"{update.effective_user.full_name}\n"

            f"🔗 Username: "
            f"{username_text}\n"

            f"🆔 ID: "
            f"<code>{user_id}</code>"
        ),

        parse_mode="HTML"
    )


    forwarded_msg = await update.message.forward(
        chat_id=ADMIN_ID
    )


    # ------------------------------------------------
    # SAVE USER MAPPING
    # ------------------------------------------------

    if "user_mapping" not in context.bot_data:

        context.bot_data[
            "user_mapping"
        ] = {}


    context.bot_data[
        "user_mapping"
    ][
        str(header_msg.message_id)
    ] = user_id


    context.bot_data[
        "user_mapping"
    ][
        str(forwarded_msg.message_id)
    ] = user_id


    # ------------------------------------------------
    # CONFIRM TO USER
    # ------------------------------------------------

    await update.message.reply_text(

        "✅ መልዕክትዎን ተቀብለናል።\n\n"

        "📩 በቅርቡ እንመልስልዎታለን። ❤️"
    )


# ==================================================
# ADMIN REPLY
# ==================================================

async def admin_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id != ADMIN_ID:
        return


    if (
        update.message
        and update.message.reply_to_message
    ):

        replied_msg = (
            update.message.reply_to_message
        )

        target_user_id = None

        user_mapping = (
            context.bot_data.get(
                "user_mapping",
                {}
            )
        )


        replied_id_str = str(
            replied_msg.message_id
        )


        if replied_id_str in user_mapping:

            target_user_id = (
                user_mapping[
                    replied_id_str
                ]
            )


        # ------------------------------------------------
        # FORWARDED MESSAGE USER
        # ------------------------------------------------

        if (
            not target_user_id
            and replied_msg.forward_from
        ):

            target_user_id = (
                replied_msg.forward_from.id
            )


        # ------------------------------------------------
        # FIND ID FROM TEXT
        # ------------------------------------------------

        if (
            not target_user_id
            and replied_msg.text
            and "🆔 ID:" in replied_msg.text
        ):

            try:

                user_id_str = (
                    replied_msg.text
                    .split("🆔 ID:")[1]
                    .split()[0]
                )

                target_user_id = int(
                    user_id_str
                    .replace(
                        "<code>",
                        ""
                    )
                    .replace(
                        "</code>",
                        ""
                    )
                )

            except Exception:
                pass


        # ------------------------------------------------
        # FIND ID FROM CAPTION
        # ------------------------------------------------

        if (
            not target_user_id
            and replied_msg.caption
            and "🆔 ID:" in replied_msg.caption
        ):

            try:

                user_id_str = (
                    replied_msg.caption
                    .split("🆔 ID:")[1]
                    .split()[0]
                )

                target_user_id = int(
                    user_id_str
                    .replace(
                        "<code>",
                        ""
                    )
                    .replace(
                        "</code>",
                        ""
                    )
                )

            except Exception:
                pass


        # ------------------------------------------------
        # SEND REPLY TO USER
        # ------------------------------------------------

        if target_user_id:

            try:

                await update.message.copy(
                    chat_id=target_user_id
                )

                await update.message.reply_text(

                    "✅ መልሱ ለተጠቃሚው ተልኳል!"
                )

            except Exception as e:

                print(
                    "Reply Error:",
                    e
                )

                await update.message.reply_text(

                    "😭 መልሱን መላክ አልተቻለም።\n\n"
                    "ተጠቃሚው ቦቱን ዘግቶት "
                    "ሊሆን ይችላል።"
                )

        else:

            await update.message.reply_text(

                "⚠️ እባክዎ ከተጠቃሚው "
                "የመጣውን መልዕክት "
                "Reply ያድርጉ።"
            )


# ==================================================
# CHECK JOIN BUTTON
# ==================================================

async def check_join(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    try:

        member = await context.bot.get_chat_member(

            chat_id=FORCE_CHANNEL,

            user_id=user_id
        )


        if member.status in [

            "member",
            "administrator",
            "creator"

        ]:

            await query.edit_message_text(

                "✅ <b>ቻናሉን ተቀላቅለዋል!</b>\n\n"

                "🤖 አሁን /start የሚለውን "
                "ተጭነው ቦቱን ይጠቀሙ።",

                parse_mode="HTML"
            )

        else:

            await query.answer(

                "እባክዎ መጀመሪያ Channel "
                "ይቀላቀሉ! 🙂",

                show_alert=True
            )

    except Exception as e:

        print(
            "Check Join Error:",
            e
        )

        await query.answer(

            "⚠️ አባልነትዎን "
            "ማረጋገጥ አልተቻለም።",

            show_alert=True
        )


# ==================================================
# ERROR HANDLER
# ==================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    print(
        "❌ ERROR:",
        context.error
    )


# ==================================================
# MAIN
# ==================================================

def main():

    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )


    # ------------------------------------------------
    # COMMANDS
    # ------------------------------------------------

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CommandHandler(
            "menu",
            start
        )
    )

    app.add_handler(
        CommandHandler(
            "status",
            status_command
        )
    )

    app.add_handler(
        CommandHandler(
            "rates",
            rates_command
        )
    )

    app.add_handler(
        CommandHandler(
            "payment",
            payment_command
        )
    )

    app.add_handler(
        CommandHandler(
            "help",
            help_command
        )
    )


    # ------------------------------------------------
    # CALLBACK BUTTONS
    # ------------------------------------------------

    app.add_handler(

        CallbackQueryHandler(
            check_join,
            pattern="^check_join$"
        )
    )

    app.add_handler(

        CallbackQueryHandler(
            button_callback,
            pattern="^cmd_"
        )
    )


    # ------------------------------------------------
    # ADMIN REPLY FILTER
    # ------------------------------------------------

    admin_filter = (

        filters.User(
            user_id=ADMIN_ID
        )

        & filters.REPLY

        & ~filters.COMMAND
    )


    app.add_handler(
