import os
import re
import json
import asyncio
import subprocess
import requests
import static_ffmpeg
static_ffmpeg.add_paths()
from threading import Thread
from flask import Flask
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    BotCommand
)
from telegram.constants import ChatAction
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
# CREATE COOKIES FILE FROM RENDER ENVIRONMENT VARIABLE
# ==================================================
COOKIES_ENV = os.environ.get("YOUTUBE_COOKIES")

if COOKIES_ENV:
    with open("cookies.txt", "w") as f:
        f.write(COOKIES_ENV)

    print("✅ cookies.txt file created successfully from Environment Variable!")


# ==================================================
# FLASK WEB SERVER (Render Port Binding)
# ==================================================
app_web = Flask(__name__)


@app_web.route('/')
def home():
    return "Bot is Alive!"


def run_web():
    port = int(os.environ.get("PORT", 10000))
    app_web.run(host='0.0.0.0', port=port)


def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()


# ==================================================
# CONFIGURATION
# ==================================================

# IMPORTANT:
# Put your bot token in Render Environment Variable:
# BOT_TOKEN = your_new_bot_token

TOKEN = os.environ.get("BOT_TOKEN")

if not TOKEN:
    raise ValueError(
        "❌ BOT_TOKEN environment variable is missing!"
    )

ADMIN_ID = int(os.environ.get("ADMIN_ID", 6753546651))

# Force Join Channel
FORCE_CHANNEL = "@mame_posts"
FORCE_CHANNEL_LINK = "https://t.me/mame_posts"


# ==================================================
# DATABASE MANAGEMENT
# ==================================================

DATA_FILE = "user_data.json"


def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    return {}


def save_data(data):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f)

    except Exception as e:
        print("Save Error:", e)


def record_user_activity(user_id):
    data = load_data()
    uid_str = str(user_id)

    if uid_str not in data:
        data[uid_str] = {
            "msg_count": 0,
            "started": True
        }

    data[uid_str]["msg_count"] = data[uid_str].get("msg_count", 0) + 1
    data[uid_str]["started"] = True

    save_data(data)


def get_user_stats(user_id):
    data = load_data()
    uid_str = str(user_id)

    total_users = len(data)
    user_msg_count = data.get(uid_str, {}).get("msg_count", 0)

    return total_users, user_msg_count


# ==================================================
# MAIN MENU KEYBOARD
# ==================================================

def get_main_menu_keyboard(bot_username):
    keyboard = [
        [
            InlineKeyboardButton(
                "🤖 Add a bot to the chat ➕",
                url=f"https://t.me/{bot_username}?startgroup=true"
            )
        ],
        [
            InlineKeyboardButton(
                "📢 ማስታወቂያ ለማሰራት 🪪",
                callback_data="cmd_order"
            )
        ],
        [
            InlineKeyboardButton(
                "💵 Price | ዋጋ",
                callback_data="cmd_price"
            ),
            InlineKeyboardButton(
                "💳 Payment Method",
                callback_data="cmd_payment"
            )
        ],
        [
            InlineKeyboardButton(
                "👤 My Status & Stats 📊",
                callback_data="cmd_status"
            )
        ],
        [
            InlineKeyboardButton(
                "💬 Support | ድጋፍ",
                callback_data="cmd_support"
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


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
# AUTO SET BOT COMMANDS
# ==================================================

async def post_init(application):
    commands = [
        BotCommand("start", "ቦቱን ለመጀመር"),
        BotCommand("menu", "ዋና ማውጫ"),
        BotCommand("status", "የእርስዎን እና የቦቱን Status ለማየት"),
        BotCommand("rate", "የማስታወቂያ ዋጋዎች"),
        BotCommand("payment", "የከፈያ መንገድ"),
        BotCommand("help", "እርዳታና ድጋፍ"),
    ]

    await application.bot.set_my_commands(commands)


# ==================================================
# CHECK IF USER JOINED CHANNEL
# ==================================================

async def is_joined(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        print("Force Join Error:", e)
        return True


# ==================================================
# FORCE JOIN MESSAGE
# ==================================================

async def show_force_join(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    text = (
        '<tg-emoji emoji-id="6034962180875490251">🔒</tg-emoji> '
        '<b>ቦቱን ለመጠቀም ከታች ያለውን ቻናል መቀላቀል አለብዎት!</b>\n\n'
        '1️⃣ '
        '<tg-emoji emoji-id="5267442591548320083">📢</tg-emoji> '
        '<b>Join Channel የሚለውን ይጫኑ::</b>\n'
        '2️⃣ ከዚያ '
        '<tg-emoji emoji-id="5305749202997911340">✅</tg-emoji> '
        '<b>I\'ve Joined የሚለውን ተጭነው የላኩትን ደግመው ይላኩ '
        '<tg-emoji emoji-id="5217449524410199951">🙂</tg-emoji>::</b>'
    )

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
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )


# ==================================================
# START & MENU COMMAND
# ==================================================

def get_welcome_text():
    return (
        f'Hello <tg-emoji emoji-id="5305577086478489521">🚨</tg-emoji>\n\n'
        f'<tg-emoji emoji-id="5305739801314501775">✅</tg-emoji> '
        f'<b>My options (ከሁሉም Social Media ላይ video, photo እና audio ማውረድና መቀየር ይችላሉ!) :</b>\n\n'
        f'<tg-emoji emoji-id="5305290882742788410">🎵</tg-emoji> | '
        f'<b>Tiktok & Likee: videos & photos</b>\n'
        f'<tg-emoji emoji-id="5305551797711053969">📸</tg-emoji> | '
        f'<b>Pinterest & Instagram: reels, photos & stories</b>\n'
        f'<tg-emoji emoji-id="5305777524012262308">▶️</tg-emoji> | '
        f'<b>YouTube: videos & music (Full & Shorts)</b>\n'
        f'<tg-emoji emoji-id="5305474827602140530">✖️</tg-emoji> | '
        f'<b>Twitter (X): videos & voice</b>\n'
        f'<tg-emoji emoji-id="5305311717629142471">📘</tg-emoji> | '
        f'<b>Facebook, Reddit, Twitch, Vimeo & Others</b>\n'
        f'<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> '
        f'<b>Video to Audio Converter: ቪዲዮ ወደ ኦዲዮ መቀየር ይችላሉ! </b>\n\n'
        f'<b>And others Social Media | ሌሎችንም ሶሻል ሚድያ ማውረድ ይችላሉ!:</b> '
        f'<tg-emoji emoji-id="5305466057278923962">📥</tg-emoji>'
    )


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user_id = update.effective_user.id
    record_user_activity(user_id)

    bot_username = context.bot.username or "mame_posts_bot"

    setup_keyboard = ReplyKeyboardMarkup(
        [["🏠 Menu"]],
        resize_keyboard=True,
        input_field_placeholder="Send link 🔗"
    )

    await update.message.reply_text(
        " <b> @ads_poster1bot !</b>",
        reply_markup=setup_keyboard,
        parse_mode="HTML"
    )

    await update.message.reply_text(
        get_welcome_text(),
        reply_markup=get_main_menu_keyboard(bot_username),
        parse_mode="HTML"
    )


# ==================================================
# STATUS COMMAND (/status)
# ==================================================

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    record_user_activity(user.id)

    total_users, user_msg_count = get_user_stats(user.id)
    username_text = f"@{user.username}" if user.username else "የለውም"

    msg = (
        f'<tg-emoji emoji-id="5431577498364158238">📊</tg-emoji> '
        f'<b>የእርስዎ እና የቦቱ Status</b>\n\n'
        f'<tg-emoji emoji-id="5875078913725571378">👤</tg-emoji> '
        f'<b>የግል መረጃዎት፦</b>\n'
        f'<tg-emoji emoji-id="5465638272648617243">✈️</tg-emoji> '
        f'<b>ስም:</b> {user.full_name}\n'
        f'<tg-emoji emoji-id="5465638272648617243">✈️</tg-emoji> '
        f'<b>Username:</b> {username_text}\n'
        f'<tg-emoji emoji-id="5465638272648617243">✈️</tg-emoji> '
        f'<b>Telegram ID:</b> <code>{user.id}</code>\n'
        f'<tg-emoji emoji-id="5465638272648617243">✈️</tg-emoji> '
        f'<b>የላኳቸው አጠቃላይ መልዕክቶች:</b> <code>{user_msg_count}</code>\n\n'

        f'<tg-emoji emoji-id="5307979128543158051">🤖</tg-emoji> '
        f'<b>የቦቱ አጠቃላይ መረጃ፦</b>\n'
        f'<tg-emoji emoji-id="5465638272648617243">✈️</tg-emoji> '
        f'<b>ሁኔታ:</b> Active '
        f'<tg-emoji emoji-id="5307976826440687996">🔥</tg-emoji>\n'
        f'<tg-emoji emoji-id="5465638272648617243">✈️</tg-emoji> '
        f'<b>ጠቅላላ Users:</b> <code>{total_users}</code> '
        f'<tg-emoji emoji-id="5305466057278923962">👥</tg-emoji>'
    )

    await update.message.reply_text(
        msg,
        parse_mode="HTML"
    )


# ==================================================
# BROADCAST COMMAND
# ==================================================

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    reply_msg = update.message.reply_to_message
    has_args = bool(context.args)

    if not reply_msg and not has_args:
        await update.message.reply_text(
            "⚠️ እባክዎ የሚተላለፈውን መልዕክት ሬፕላይ ያድርጉ ወይም ከኮማንድ ጋር ጽሁፍ ይጻፉ።"
        )
        return

    data = load_data()
    success_count = 0
    fail_count = 0

    status_msg = await update.message.reply_text(
        '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> '
        '<b>መልዕክቱን ለተጠቃሚዎች በመላክ ላይ ይገኛል...</b>',
        parse_mode="HTML"
    )

    for uid_str in data.keys():
        try:
            chat_id = int(uid_str)

            if reply_msg:
                await reply_msg.copy(chat_id=chat_id)
            else:
                text_to_send = " ".join(context.args)

                await context.bot.send_message(
                    chat_id=chat_id,
                    text=text_to_send,
                    parse_mode="HTML"
                )

            success_count += 1
            await asyncio.sleep(0.05)

        except Exception:
            fail_count += 1

    await status_msg.edit_text(
        f"✔️ <b>ብሮድካስት ተጠናቋል!</b>\n\n"
        f"• የተሳካ: <code>{success_count}</code>\n"
        f"• ያልተሳካ (ቦቱን የዘጉ): <code>{fail_count}</code>",
        parse_mode="HTML"
    )


# ==================================================
# EXTRA COMMAND HANDLERS
# ==================================================

async def rates_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    record_user_activity(update.effective_user.id)

    await update.message.reply_text(
        f'<tg-emoji emoji-id="5447458260200214425">💰</tg-emoji> '
        f'<b>የማስታወቂያ ዋጋዎች</b>\n\n'
        f'<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> '
        f'12 Hours — <b>በስምምነት ETB</b>\n'
        f'<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> '
        f'24 Hours — <b>500 ETB</b>\n'
        f'<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> '
        f'48 Hours — <b>700 ETB</b>\n\n'
        f'የፈለጉትን ምርጫ አሳውቀው የክፍያ አማራጮችን (payment method) ይጎብኙ! '
        f'<tg-emoji emoji-id="5463249828450424568">🤝</tg-emoji>',
        parse_mode="HTML"
    )


async def payment_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    record_user_activity(update.effective_user.id)

    await update.message.reply_text(
        f'<tg-emoji emoji-id="5186349709169525403">💳</tg-emoji> '
        f'<b>Payment Method</b>\n\n'
        f'<tg-emoji emoji-id="5961054379350955385">🏦</tg-emoji> '
        f'<b>ንግድ ባንክ (CBE)</b>\n'
        f'<code>1000528274394</code>\n\n'
        f'Mohammed Seid\n\n'
        f'<tg-emoji emoji-id="5960632377339285724">📱</tg-emoji> '
        f'<b>ቴሌ ብር (TELE BIRR)</b>\n'
        f'<code>+251963266849</code>\n\n'
        f'<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> '
        f'<b>ክፍያውን ሲፈጽሙ ስክሪን ሹቱን ከስር ይላኩ!</b>',
        parse_mode="HTML"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    record_user_activity(update.effective_user.id)

    await update.message.reply_text(
        f'<tg-emoji emoji-id="5305545479814161889">💬</tg-emoji> '
        f'<b>Support & Downloader Help</b>\n\n'
        f'<tg-emoji emoji-id="5305655375142364109">📺</tg-emoji> '
        f'<b>ቪዲዮ/ፎቶ ለማውረድ:</b> የ Tiktok, Instagram, Facebook, Reddit, Twitch, Vimeo, SoundCloud, Threads እና ሌሎችን ሊንክ ቀጥታ ለቦቱ ይላኩ።\n\n'
        f'<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> '
        f'<b>Video to Audio:</b> ማናቸውንም ቪዲዮ ከስልክዎ ይላኩ፣ ወደ MP3 Audio ቀይሮ ይልክልዎታል።\n\n'
        f'<tg-emoji emoji-id="5949327894567195412">👩‍💻</tg-emoji> '
        f'ለአድሚን መልዕክት ለመላክም እዚሁ መጻፍ ይችላሉ።',
        parse_mode="HTML"
    )


# ==================================================
# VIDEO TO AUDIO CONVERTER HANDLER
# ==================================================

async def convert_video_to_audio(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user_id = update.effective_user.id
    record_user_activity(user_id)

    if not await is_joined(update, context):
        await show_force_join(update, context)
        return

    video = (
        update.message.video
        or update.message.video_note
        or (
            update.message.document
            if update.message.document
            and update.message.document.mime_type
            and update.message.document.mime_type.startswith('video/')
            else None
        )
    )

    if not video:
        return

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.RECORD_VOICE
    )

    status_msg = await update.message.reply_text(
        '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> '
        '<b>Loading | ይጠብቁ...🔎</b>',
        parse_mode="HTML"
    )

    file_id = update.message.message_id

    input_path = f"input_vid_{user_id}_{file_id}.mp4"
    output_path = f"output_aud_{user_id}_{file_id}.mp3"

    try:
        tg_file = await video.get_file()
        await tg_file.download_to_drive(input_path)

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            input_path,
            "-vn",
            "-acodec",
            "libmp3lame",
            "-q:a",
            "2",
            output_path
        ]

        await asyncio.to_thread(
            subprocess.run,
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        if os.path.exists(output_path):
            bot_username = context.bot.username or "mame_posts_bot"

            share_url = (
                f"https://t.me/share/url?"
                f"url=https://t.me/{bot_username}?start=share"
                f"&text=Try%20this%20awesome%20Video%20to%20Audio%20Converter%20Bot!🔥"
            )

            keyboard_share = [
                [
                    InlineKeyboardButton(
                        "🔗 Share Bot 🚀",
                        url=share_url
                    )
                ]
            ]

            reply_markup_share = InlineKeyboardMarkup(
                keyboard_share
            )

            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id,
                action=ChatAction.UPLOAD_DOCUMENT
            )

            with open(output_path, 'rb') as audio_file:
                await update.message.reply_audio(
                    audio=audio_file,
                    caption=(
                        f'<tg-emoji emoji-id="5305534793935527938">🎵</tg-emoji> '
                        f'<b>ከቪዲዮ የተቀየረው (Extracted Audio)</b>\n\n'
                        f'<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> '
                        f'<b>Converted with</b> @{bot_username} & @mame_posts'
                    ),
                    reply_markup=reply_markup_share,
                    parse_mode="HTML"
                )

            await status_msg.delete()

        else:
            await status_msg.edit_text(
                "😥 <b>ቪዲዮውን ወደ ኦዲዮ መቀየር አልተቻለም!</b>",
                parse_mode="HTML"
            )

    except Exception as e:
        print("Video to Audio Error:", e)

        await status_msg.edit_text(
            "😥 <b>ቪዲዮውን ማውረድ አልተቻለም!</b>",
            parse_mode="HTML"
        )

    finally:
        for path in [
            input_path,
            output_path
        ]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass


# ==================================================
# DOWNLOAD ENGINE
# VIDEOS + PHOTOS + AUDIO
# ==================================================

def unshorten_url(url: str) -> str:
    """
    Expand short URLs such as pin.it.
    YouTube URLs are NOT expanded here because yt-dlp
    can handle Shorts and youtu.be directly.
    """

    lower_url = url.lower()

    if (
        "youtube.com/" in lower_url
        or "youtu.be/" in lower_url
    ):
        return url

    try:
        session = requests.Session()

        session.headers.update({
            'User-Agent':
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 '
                '(KHTML, like Gecko) '
                'Chrome/128.0.0.0 Safari/537.36'
        })

        resp = session.head(
            url,
            allow_redirects=True,
            timeout=10
        )

        if resp.url:
            return resp.url

    except Exception:
        pass

    return url


def clean_url(raw_url: str) -> str:
    url = raw_url.strip().strip("<>")

    # Remove common punctuation accidentally copied with URL
    url = url.rstrip(".,!?;:)]}\"'")

    lower_url = url.lower()

    # IMPORTANT:
    # Do NOT convert YouTube Shorts into watch URLs.
    # yt-dlp handles Shorts directly.
    if (
        "youtube.com/shorts/" in lower_url
        or "youtube.com/watch" in lower_url
        or "youtu.be/" in lower_url
    ):
        return url

    return unshorten_url(url)


def get_video_options(
    url: str,
    output_template: str,
    fallback: bool = False
):
    """
    More current/general yt-dlp configuration.

    The old forced YouTube player clients were removed because
    forcing old clients can cause YouTube extraction failures.
    """

    opts = {
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'geo_bypass': True,

        # Don't stop after one media item.
        'noplaylist': False,

        # Download fragments concurrently.
        'concurrent_fragment_downloads': 5,

        'outtmpl': output_template,

        # Video first, but keep a fallback for sites that expose
        # only a single combined format.
        'format':
            'bv*[ext=mp4]+ba[ext=m4a]/'
            'bv*+ba/'
            'b[ext=mp4]/'
            'b',

        'merge_output_format': 'mp4',

        'http_headers': {
            'User-Agent':
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 '
                '(KHTML, like Gecko) '
                'Chrome/128.0.0.0 Safari/537.36',

            'Accept':
                'text/html,application/xhtml+xml,'
                'application/xml;q=0.9,image/webp,*/*;q=0.8',

            'Accept-Language':
                'en-US,en;q=0.9',
        },

        # Continue when a playlist/carousel has an item
        # that cannot be downloaded.
        'ignoreerrors': True,

        # Do not download thumbnails as separate media.
        'writethumbnail': False,

        # Don't download subtitles.
        'writesubtitles': False,
        'writeautomaticsub': False,
    }

    # --------------------------------------------------
    # YOUTUBE
    # --------------------------------------------------
    #
    # IMPORTANT:
    # No forced player_client list here.
    # yt-dlp is allowed to select the currently supported
    # extraction method.
    #
    if (
        "youtube.com" in url.lower()
        or "youtu.be" in url.lower()
    ):
        opts['format'] = (
            'bv*[ext=mp4]+ba[ext=m4a]/'
            'bv*+ba/'
            'b[ext=mp4]/'
            'b'
        )

    # --------------------------------------------------
    # TIKTOK
    # --------------------------------------------------
    elif "tiktok.com" in url.lower():
        opts['format'] = (
            'bv*+ba/'
            'b'
        )

    # --------------------------------------------------
    # INSTAGRAM
    # --------------------------------------------------
    elif "instagram.com" in url.lower():
        opts['format'] = (
            'bv*+ba/'
            'b'
        )

    # --------------------------------------------------
    # TWITTER / X
    # --------------------------------------------------
    elif (
        "twitter.com" in url.lower()
        or "x.com" in url.lower()
    ):
        opts['format'] = (
            'bv*[ext=mp4]+ba[ext=m4a]/'
            'bv*+ba/'
            'b[ext=mp4]/'
            'b'
        )

    # --------------------------------------------------
    # LIKEE
    # --------------------------------------------------
    elif (
        "likee" in url.lower()
        or "likee.video" in url.lower()
    ):
        opts['http_headers']['Referer'] = "https://likee.video/"
        opts['format'] = 'b/bv*'

    # --------------------------------------------------
    # VIMEO
    # --------------------------------------------------
    elif "vimeo.com" in url.lower():
        opts['http_headers']['Referer'] = "https://vimeo.com/"
        opts['format'] = (
            'bv*[ext=mp4]+ba[ext=m4a]/'
            'bv*+ba/'
            'b[ext=mp4]/'
            'b'
        )

    # --------------------------------------------------
    # FACEBOOK
    # --------------------------------------------------
    elif (
        "facebook.com" in url.lower()
        or "fb.watch" in url.lower()
    ):
        opts['format'] = (
            'bv*+ba/'
            'b[ext=mp4]/'
            'b'
        )

    # --------------------------------------------------
    # REDDIT
    # --------------------------------------------------
    elif (
        "reddit.com" in url.lower()
        or "redd.it" in url.lower()
    ):
        opts['format'] = (
            'bv*+ba/'
            'b[ext=mp4]/'
            'b'
        )

    # --------------------------------------------------
    # PINTEREST
    # --------------------------------------------------
    elif (
        "pinterest.com" in url.lower()
        or "pin.it" in url.lower()
    ):
        opts['format'] = (
            'bv*+ba/'
            'b'
        )

    # --------------------------------------------------
    # THREADS
    # --------------------------------------------------
    elif "threads.net" in url.lower():
        opts['format'] = (
            'bv*+ba/'
            'b'
        )

    # --------------------------------------------------
    # TUMBLR
    # --------------------------------------------------
    elif "tumblr.com" in url.lower():
        opts['format'] = (
            'bv*+ba/'
            'b'
        )

    # --------------------------------------------------
    # TWITCH
    # --------------------------------------------------
    elif "twitch.tv" in url.lower():
        opts['format'] = (
            'bv*+ba/'
            'b'
        )

    # --------------------------------------------------
    # SOUNDCLOUD
    # --------------------------------------------------
    elif "soundcloud.com" in url.lower():
        opts['format'] = 'b'

    # --------------------------------------------------
    # COOKIES
    # --------------------------------------------------
    if os.path.exists("cookies.txt"):
        opts['cookiefile'] = "cookies.txt"

    return opts


def download_media_func(
    url: str,
    output_template: str,
    fallback: bool = False
):
    opts = get_video_options(
        url,
        output_template,
        fallback
    )

    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])


def find_downloaded_files(prefix: str):
    """
    Find ALL downloaded media files belonging to this request.
    This fixes photo/carousel downloads where more than one
    file can be returned.
    """

    files = []

    ignored_extensions = {
        '.part',
        '.ytdl',
        '.json',
        '.description',
        '.info.json'
    }

    for filename in os.listdir("."):
        if not filename.startswith(prefix):
            continue

        lower_name = filename.lower()

        if any(
            lower_name.endswith(ext)
            for ext in ignored_extensions
        ):
            continue

        if os.path.isfile(filename):
            files.append(filename)

    # Keep a stable order.
    files.sort()

    return files


def is_photo_file(filename: str):
    ext = os.path.splitext(filename)[1].lower()

    return ext in [
        '.jpg',
        '.jpeg',
        '.png',
        '.webp',
        '.gif',
        '.bmp'
    ]


def is_video_file(filename: str):
    ext = os.path.splitext(filename)[1].lower()

    return ext in [
        '.mp4',
        '.mkv',
        '.webm',
        '.mov',
        '.avi',
        '.flv',
        '.m4v'
    ]


async def send_downloaded_photo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    filename: str,
    bot_username: str,
    reply_markup_share
):
    try:
        with open(filename, "rb") as photo_file:
            await update.message.reply_photo(
                photo=photo_file,
                caption=(
                    f'📸 <b>Downloaded Photo</b>\n\n'
                    f'<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> '
                    f'<b>Downloaded with</b> @{bot_username}'
                ),
                reply_markup=reply_markup_share,
                parse_mode="HTML"
            )

        return True

    except Exception as e:
        print("Photo Send Error:", e)

        # Some image files can be too large for send_photo.
        # Send them as a document instead of losing the download.
        try:
            with open(filename, "rb") as photo_file:
                await update.message.reply_document(
                    document=photo_file,
                    caption=(
                        f'📸 <b>Downloaded Photo</b>\n\n'
                        f'<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> '
                        f'<b>Downloaded with</b> @{bot_username}'
                    ),
                    reply_markup=reply_markup_share,
                    parse_mode="HTML"
                )

            return True

        except Exception as document_error:
            print(
                "Photo Document Send Error:",
                document_error
            )

    return False


async def send_downloaded_video(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    filename: str,
    bot_username: str,
    reply_markup_share
):
    try:
        file_size = os.path.getsize(filename)

        # Keep the original 50 MB behavior.
        if file_size <= 50 * 1024 * 1024:
            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id,
                action=ChatAction.UPLOAD_VIDEO
            )

            with open(filename, "rb") as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption=(
                        f'<tg-emoji emoji-id="5305762354187772738">🚀</tg-emoji> '
                        f'<b>Downloaded with</b> @{bot_username} & @mame_posts\n\n'
                        f'<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> '
                        f'<b>Enjoy!</b>'
                    ),
                    reply_markup=reply_markup_share,
                    parse_mode="HTML"
                )

            return True

        # For files over 50 MB, send as document.
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.UPLOAD_DOCUMENT
        )

        with open(filename, "rb") as video_file:
            await update.message.reply_document(
                document=video_file,
                caption=(
                    f'<tg-emoji emoji-id="5305762354187772738">🚀</tg-emoji> '
                    f'<b>Downloaded with</b> @{bot_username} & @mame_posts\n\n'
                    f'<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> '
                    f'<b>Enjoy!</b>'
                ),
                reply_markup=reply_markup_share,
                parse_mode="HTML"
            )

        return True

    except Exception as e:
        print("Video Send Error:", e)

    return False


async def extract_and_send_audio(
    update: Update,
    video_file: str,
    user_id: int,
    message_id: int,
    bot_username: str,
    reply_markup_share
):
    audio_output = (
        f"audio_{user_id}_{message_id}.mp3"
    )

    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            video_file,
            "-vn",
            "-acodec",
            "libmp3lame",
            "-q:a",
            "2",
            audio_output
        ]

        result = await asyncio.to_thread(
            subprocess.run,
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        if (
            result.returncode == 0
            and os.path.exists(audio_output)
            and os.path.getsize(audio_output) > 0
        ):
            await context_bot_send_audio(
                update,
                audio_output,
                bot_username,
                reply_markup_share
            )

            return True

    except Exception as e:
        print("Audio Extraction Error:", e)

    finally:
        if os.path.exists(audio_output):
            try:
                os.remove(audio_output)
            except Exception:
                pass

    return False


async def context_bot_send_audio(
    update: Update,
    audio_output: str,
    bot_username: str,
    reply_markup_share
):
    await update.message.reply_audio(
        audio=open(audio_output, "rb"),
        caption=(
            f'<tg-emoji emoji-id="5307705891313721642">🎧</tg-emoji> '
            f'<b>Extracted Audio (MP3)</b>\n\n'
            f'<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> '
            f'<b>Downloaded with</b> @{bot_username}'
        ),
        reply_markup=reply_markup_share,
        parse_mode="HTML"
    )


async def handle_url_download(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    raw_url: str
):
    chat_id = update.effective_chat.id

    await context.bot.send_chat_action(
        chat_id=chat_id,
        action=ChatAction.UPLOAD_DOCUMENT
    )

    status_msg = await update.message.reply_text(
        '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> '
        '<b>Loading | ይጠብቁ...🔎</b>',
        parse_mode="HTML"
    )

    bot_username = context.bot.username or "mame_posts_bot"

    share_url = (
        f"https://t.me/share/url?"
        f"url=https://t.me/{bot_username}?start=share"
        f"&text=Try%20this%20awesome%20Downloader%20Bot!🔥"
    )

    reply_markup_share = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔗 Share Bot 🚀",
                url=share_url
            )
        ]
    ])

    url = clean_url(raw_url)

    # ==================================================
    # PINTEREST REAL PHOTO EXTRACTION
    # ==================================================
    if (
        "pinterest.com" in url.lower()
        or "pin.it" in url.lower()
    ):
        try:
            headers = {
                'User-Agent':
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 '
                    '(KHTML, like Gecko) '
                    'Chrome/128.0.0.0 Safari/537.36'
            }

            res = requests.get(
                url,
                headers=headers,
                timeout=15
            )

            img_matches = re.findall(
                r'https://i\.pinimg\.com/'
                r'(?:originals|736x)/'
                r'[^\s"\'\>]+\.'
                r'(?:jpg|png|jpeg|webp)',
                res.text
            )

            # Remove duplicates while preserving order.
            img_matches = list(dict.fromkeys(img_matches))

            if img_matches:
                sent_photo = False

                for image_url in img_matches[:10]:
                    try:
                        await update.message.reply_photo(
                            photo=image_url,
                            caption=(
                                f'📸 <b>Pinterest Photo</b>\n\n'
                                f'<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> '
                                f'<b>Downloaded with</b> @{bot_username}'
                            ),
                            reply_markup=reply_markup_share,
                            parse_mode="HTML"
                        )

                        sent_photo = True

                    except Exception as image_error:
                        print(
                            "Pinterest Image Send Error:",
                            image_error
                        )

                if sent_photo:
                    await status_msg.delete()
                    return

        except Exception as pe:
            print("Pinterest Fetch Error:", pe)

    # ==================================================
    # NORMAL DOWNLOAD
    # ==================================================

    media_prefix = (
        f"media_"
        f"{update.effective_user.id}_"
        f"{update.message.message_id}"
    )

    # autonumber prevents carousel/photo posts from overwriting
    # each other.
    media_template = (
        f"{media_prefix}_%(autonumber)03d.%(ext)s"
    )

    sent_any = False

    downloaded_files = []

    try:
        # --------------------------------------------------
        # FIRST ATTEMPT
        # --------------------------------------------------
        try:
            await asyncio.to_thread(
                download_media_func,
                url,
                media_template,
                False
            )

        except Exception as first_error:
            print(
                "Primary Download Error:",
                first_error
            )

            # --------------------------------------------------
            # FALLBACK
            # --------------------------------------------------
            try:
                await asyncio.to_thread(
                    download_media_func,
                    url,
                    media_template,
                    True
                )

            except Exception as fallback_error:
                print(
                    "Fallback Download Error:",
                    fallback_error
                )

        # --------------------------------------------------
        # FIND ALL DOWNLOADED FILES
        # --------------------------------------------------
        downloaded_files = find_downloaded_files(
            media_prefix
        )

        # --------------------------------------------------
        # SEND EVERY FILE
        # --------------------------------------------------
        for actual_file in downloaded_files:

            if not os.path.exists(actual_file):
                continue

            # ----------------------------------------------
            # PHOTO
            # ----------------------------------------------
            if is_photo_file(actual_file):
                photo_sent = await send_downloaded_photo(
                    update,
                    context,
                    actual_file,
                    bot_username,
                    reply_markup_share
                )

                if photo_sent:
                    sent_any = True

                continue

            # ----------------------------------------------
            # VIDEO
            # ----------------------------------------------
            if is_video_file(actual_file):
                video_sent = await send_downloaded_video(
                    update,
                    context,
                    actual_file,
                    bot_username,
                    reply_markup_share
                )

                if video_sent:
                    sent_any = True

                    # Extract MP3 only from videos.
                    audio_sent = await extract_and_send_audio(
                        update,
                        actual_file,
                        update.effective_user.id,
                        update.message.message_id,
                        bot_username,
                        reply_markup_share
                    )

                    if audio_sent:
                        sent_any = True

                continue

            # ----------------------------------------------
            # AUDIO / OTHER MEDIA
            # ----------------------------------------------
            ext = os.path.splitext(actual_file)[1].lower()

            if ext in [
                '.mp3',
                '.m4a',
                '.aac',
                '.ogg',
                '.opus',
                '.wav',
                '.flac'
            ]:
                try:
                    await update.message.reply_audio(
                        audio=open(actual_file, "rb"),
                        caption=(
                            f'🎵 <b>Downloaded Audio</b>\n\n'
                            f'<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> '
                            f'<b>Downloaded with</b> @{bot_username}'
                        ),
                        reply_markup=reply_markup_share,
                        parse_mode="HTML"
                    )

                    sent_any = True

                except Exception as audio_error:
                    print(
                        "Audio Send Error:",
                        audio_error
                    )

    except Exception as e:
        print("Media Download Error:", e)

    # ==================================================
    # CLEAN TEMPORARY FILES
    # ==================================================

    for f in os.listdir('.'):
        if f.startswith(media_prefix):
            try:
                os.remove(f)
            except Exception:
                pass

    # ==================================================
    # RESULT
    # ==================================================

    if sent_any:
        try:
            await status_msg.delete()
        except Exception:
            pass

    else:
        try:
            await status_msg.edit_text(
                "💔 <b> የፈለጉትን File ማግኘት አልቻልኩም!</b>\n\n"
                "እባክዎ የላኩት ሊንክ private አለመሆኑን "
                "አረጋግጠው እንደገና ይሞክሩ።",
                parse_mode="HTML"
            )

        except Exception:
            pass


# ==================================================
# BUTTON CLICK HANDLER
# ==================================================

async def button_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    data = query.data
    user = query.from_user

    if data == "cmd_back":
        bot_username = context.bot.username or "mame_posts_bot"

        await query.edit_message_text(
            get_welcome_text(),
            reply_markup=get_main_menu_keyboard(bot_username),
            parse_mode="HTML"
        )

    elif data == "cmd_price":
        await query.edit_message_text(
            f'<tg-emoji emoji-id="5447458260200214425">💰</tg-emoji> '
            f'<b>የማስታወቂያ ዋጋዎች</b>\n\n'
            f'<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> '
            f'12 Hours — <b>በስምምነት ETB</b>\n'
            f'<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> '
            f'24 Hours — <b>500 ETB</b>\n'
            f'<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> '
            f'48 Hours — <b>700 ETB</b>\n\n'
            f'የፈለጉትን ምርጫ አሳውቀው '
            f'የክፍያ አማራጮችን (payment method) ይጎብኙ '
            f'<tg-emoji emoji-id="5463249828450424568">🤝</tg-emoji>',
            reply_markup=get_back_keyboard(),
            parse_mode="HTML"
        )

    elif data == "cmd_order":
        await query.edit_message_text(
            f'<tg-emoji emoji-id="5197304993920616826">📢</tg-emoji> '
            f'<b> @mame_posts ቻናል ላይ ማስታወቂያ ለማሰራት</b>\n\n'
            f'<tg-emoji emoji-id="5305634553140912174">👇</tg-emoji> '
            f'እባክዎ ማስታወቂያ ማሰራት የሚፈልጉትን Post '
            f'ከስር ልከው የማስታወቂያ ዋጋዎችን ይመልከቱ '
            f'<tg-emoji emoji-id="5305739801314501775">ℹ️</tg-emoji>',
            reply_markup=get_back_keyboard(),
            parse_mode="HTML"
        )

    elif data == "cmd_status":
        total_users, user_msg_count = get_user_stats(user.id)
        username_text = (
            f"@{user.username}"
            if user.username
            else "የለውም"
        )

        msg = (
            f'<tg-emoji emoji-id="5431577498364158238">📊</tg-emoji> '
            f'<b>የእርስዎ እና የቦቱ Status</b>\n\n'
            f'<tg-emoji emoji-id="5875078913725571378">👤</tg-emoji> '
            f'<b>የግል መረጃዎት፦</b>\n'
            f'<tg-emoji emoji-id="5465638272648617243">✈️</tg-emoji> '
            f'<b>ስም:</b> {user.full_name}\n'
            f'<tg-emoji emoji-id="5465638272648617243">✈️</tg-emoji> '
            f'<b>Username:</b> {username_text}\n'
            f'<tg-emoji emoji-id="5465638272648617243">✈️</tg-emoji> '
            f'<b>Telegram ID:</b> <code>{user.id}</code>\n'
            f'<tg-emoji emoji-id="5465638272648617243">✈️</tg-emoji> '
            f'<b>የላኳቸው አጠቃላይ መልዕክቶች:</b> '
            f'<code>{user_msg_count}</code>\n\n'

            f'<tg-emoji emoji-id="5307979128543158051">🤖</tg-emoji> '
            f'<b>የቦቱ አጠቃላይ መረጃ፦</b>\n'
            f'<tg-emoji emoji-id="5465638272648617243">✈️</tg-emoji> '
            f'<b>ሁኔታ:</b> Active '
            f'<tg-emoji emoji-id="5307976826440687996">🔥</tg-emoji>\n'
            f'<tg-emoji emoji-id="5465638272648617243">✈️</tg-emoji> '
            f'<b>ጠቅላላ Users:</b> <code>{total_users}</code> '
            f'<tg-emoji emoji-id="5305466057278923962">👥</tg-emoji>'
        )

        await query.edit_message_text(
            msg,
            reply_markup=get_back_keyboard(),
            parse_mode="HTML"
        )

    elif data == "cmd_payment":
        await query.edit_message_text(
            f'<tg-emoji emoji-id="5186349709169525403">💳</tg-emoji> '
            f'<b>Payment Method</b>\n\n'
            f'<tg-emoji emoji-id="5961054379350955385">🏦</tg-emoji> '
            f'<b>ንግድ ባንክ (CBE)</b>\n'
            f'<code>1000528274394</code>\n\n'
            f'Mohammed Seid\n\n'
            f'<tg-emoji emoji-id="5960632377339285724">📱</tg-emoji> '
            f'<b>ቴሌ ብር (TELE BIRR)</b>\n'
            f'<code>+251963266849</code>\n\n'
            f'<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> '
            f'<b>ክፍያውን ሲፈጽሙ ስክሪን ሹቱን ከስር ይላኩ!</b>',
            reply_markup=get_back_keyboard(),
            parse_mode="HTML"
        )

    elif data == "cmd_support":
        await query.edit_message_text(
            f'<tg-emoji emoji-id="5305545479814161889">💬</tg-emoji> '
            f'<b>Support & Downloader Help</b>\n\n'
            f'<tg-emoji emoji-id="5305655375142364109">📺</tg-emoji> '
            f'<b>ቪዲዮ/ፎቶ ለማውረድ:</b> የ Tiktok, Instagram, Facebook, Reddit, '
            f'Twitch, Vimeo, SoundCloud, Threads እና ሌሎች ሊንክ '
            f'ቀጥታ ለቦቱ ይላኩ።\n\n'
            f'<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> '
            f'<b>Video to Audio:</b> ማናቸውንም ቪዲዮ ከስልክዎ ይላኩ፣ '
            f'ወደ MP3 Audio ቀይሮ ይልክልዎታል።\n\n'
            f'<tg-emoji emoji-id="5949327894567195412">👩‍💻</tg-emoji> '
            f'ለአድሚን መልዕክት ለመላክም እዚሁ መጻፍ ይችላሉ።',
            reply_markup=get_back_keyboard(),
            parse_mode="HTML"
        )


# ==================================================
# USER MESSAGES HANDLER
# ==================================================

async def handle_user_messages(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not update.message:
        return

    user_id = update.effective_user.id
    record_user_activity(user_id)

    text = (
        update.message.text
        or update.message.caption
        or ""
    )

    if text == "🏠 Menu":
        await start(update, context)
        return

    valid_domains = [
        "instagram.com",
        "tiktok.com",
        "youtube.com",
        "youtu.be",
        "facebook.com",
        "fb.watch",
        "twitter.com",
        "x.com",
        "pinterest.com",
        "pin.it",
        "reddit.com",
        "redd.it",
        "twitch.tv",
        "tumblr.com",
        "vimeo.com",
        "threads.net",
        "soundcloud.com",
        "likee.video",
        "likee.com",
        "l.likee.video",
        "lk.video"
    ]

    is_supported_link = any(
        domain in text.lower()
        for domain in valid_domains
    )

    if is_supported_link:
        if not await is_joined(update, context):
            await show_force_join(update, context)
            return

        url_match = re.search(
            r'https?://[^\s]+',
            text
        )

        target_url = (
            url_match.group(0)
            if url_match
            else text
        )

        await handle_url_download(
            update,
            context,
            target_url
        )

        return

    username = update.effective_user.username

    username_text = (
        f"@{username}"
        if username
        else "No Username"
    )

    header_msg = await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"📩<b>አዲስ መልዕክት!</b>\n\n"
            f"👤 User: {update.effective_user.full_name}\n"
            f"🌐 Username: {username_text}\n"
            f"🆔 ID: <code>{user_id}</code>"
        ),
        parse_mode="HTML"
    )

    forwarded_msg = await update.message.forward(
        chat_id=ADMIN_ID
    )

    if "user_mapping" not in context.bot_data:
        context.bot_data["user_mapping"] = {}

    context.bot_data["user_mapping"][
        str(header_msg.message_id)
    ] = user_id

    context.bot_data["user_mapping"][
        str(forwarded_msg.message_id)
    ] = user_id

    await update.message.reply_text(
        "✅ መልዕክትዎን ተቀብለናል።\n\n"
        "📩 በቅርቡ እንመልስልዎታለን። ❤️"
    )


# ==================================================
# ADMIN REPLY HANDLER
# ==================================================

async def admin_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if update.effective_user.id != ADMIN_ID:
        return

    if update.message and update.message.reply_to_message:
        replied_msg = update.message.reply_to_message

        target_user_id = None

        user_mapping = context.bot_data.get(
            "user_mapping",
            {}
        )

        replied_id_str = str(
            replied_msg.message_id
        )

        if replied_id_str in user_mapping:
            target_user_id = user_mapping[
                replied_id_str
            ]

        if (
            not target_user_id
            and replied_msg.forward_from
        ):
            target_user_id = replied_msg.forward_from.id

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
                    .replace("<code>", "")
                    .replace("</code>", "")
                )

            except Exception:
                pass

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
                    .replace("<code>", "")
                    .replace("</code>", "")
                )

            except Exception:
                pass

        if target_user_id:
            try:
                await update.message.copy(
                    chat_id=target_user_id
                )

                await update.message.reply_text(
                    "✅ መልሱ ለተጠቃሚው ተልኳል!"
                )

            except Exception as e:
                print("Reply Error:", e)

                await update.message.reply_text(
                    "😭 መልሱን መላክ አልተቻለም። "
                    "ተጠቃሚው ቦቱን ዘግቶት ሊሆን ይችላል።"
                )

        else:
            await update.message.reply_text(
                "⚠️ እባክዎ ከቀረቡት መልእክቶች Reply ያድርጉ።"
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
                "🤖 አሁን /start የሚለውን ተጭነው "
                "ቦቱን ይጠቀሙ።",
                parse_mode="HTML"
            )

        else:
            await query.answer(
                "እባክዎ መጀመሪያ Channel ይቀላቀሉ! 🙂",
                show_alert=True
            )

    except Exception as e:
        print("Check Join Error:", e)

        await query.answer(
            "⚠️ አባልነትዎን ማረጋገጥ አልተቻለም። 🙂",
            show_alert=True
        )


# ==================================================
# ERROR HANDLER
# ==================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):
    print("❌ ERROR:", context.error)


# ==================================================
# MAIN EXECUTION
# ==================================================

def main():
    keep_alive()

    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    # Commands Handlers
    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("menu", start)
    )

    app.add_handler(
        CommandHandler("status", status_command)
    )

    app.add_handler(
        CommandHandler("rates", rates_command)
    )

    app.add_handler(
        CommandHandler("rate", rates_command)
    )

    app.add_handler(
        CommandHandler("payment", payment_command)
    )

    app.add_handler(
        CommandHandler("help", help_command)
    )

    app.add_handler(
        CommandHandler("broadcast", broadcast_command)
    )

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

    admin_filter = (
        filters.User(user_id=ADMIN_ID)
        & filters.REPLY
        & ~filters.COMMAND
    )

    app.add_handler(
        MessageHandler(
            admin_filter,
            admin_reply
        )
    )

    app.add_handler(
        MessageHandler(
            filters.VIDEO | filters.VIDEO_NOTE,
            convert_video_to_audio
        )
    )

    type_filter = (
        filters.TEXT
        | filters.PHOTO
        | filters.Document.ALL
        | filters.VOICE
        | filters.AUDIO
        | filters.Sticker.ALL
    ) & ~filters.COMMAND

    app.add_handler(
        MessageHandler(
            type_filter,
            handle_user_messages
        )
    )

    app.add_error_handler(error_handler)

    print("🤖 Mame Posts Bot is running...")

    app.run_polling()


if __name__ == '__main__':
    main()
