import os
import re
import json
import asyncio
import subprocess
import requests
import shutil
import static_ffmpeg
# FFmpeg setup
try:
    static_ffmpeg.add_paths()
except Exception as e:
    print("Static FFmpeg setup warning:", e)
FFMPEG_PATH = shutil.which("ffmpeg")
from threading import Thread
from urllib.parse import quote
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
# ============================================================
# CREATE COOKIES FILE FROM RENDER ENVIRONMENT VARIABLE
# ============================================================
COOKIES_ENV = os.environ.get("YOUTUBE_COOKIES")
if COOKIES_ENV:
    formatted_cookies = COOKIES_ENV.replace("\\n", "\n")
    with open("cookies.txt", "w", encoding="utf-8") as f:
        f.write(formatted_cookies)
    print("✅ cookies.txt file created successfully from Environment Variable!")
# ============================================================
# FLASK WEB SERVER (KEEP ALIVE)
# ============================================================
app_web = Flask(__name__)
@app_web.route("/")
def home():
    return "Bot is Alive!"
def run_web():
    port = int(os.environ.get("PORT", 10000))
    app_web.run(host="0.0.0.0", port=port)
def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()
# ============================================================
# CONFIGURATION
# ============================================================
TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 6753546651))
FORCE_CHANNEL = "@mame_posts"
FORCE_CHANNEL_LINK = "https://t.me/mame_posts"
# ============================================================
# DATABASE MANAGEMENT
# ============================================================
from pymongo import MongoClient

MONGO_URI = os.environ.get("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("❌ MONGO_URI environment variable is missing!")

mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
users_col = mongo_client["mamebot"]["users"]
_lang_cache = {}

def record_user_activity(user_id):
    try:
        users_col.update_one(
            {"_id": user_id},
            {"$inc": {"msg_count": 1}, "$set": {"started": True}},
            upsert=True
        )
    except Exception as e:
        print("DB record error:", e)

def set_user_language(user_id, lang_code):
    _lang_cache[user_id] = lang_code
    try:
        users_col.update_one(
            {"_id": user_id},
            {"$set": {"lang": lang_code},
             "$setOnInsert": {"msg_count": 1, "started": True}},
            upsert=True
        )
    except Exception as e:
        print("DB lang set error:", e)

def get_user_language(user_id):
    if user_id in _lang_cache:
        return _lang_cache[user_id]
    try:
        doc = users_col.find_one({"_id": user_id}, {"lang": 1})
        lang = doc.get("lang") if doc else None
    except Exception as e:
        print("DB lang get error:", e)
        return None
    if lang:
        _lang_cache[user_id] = lang
    return lang

def get_user_stats(user_id):
    try:
        total_users = users_col.count_documents({})
        doc = users_col.find_one({"_id": user_id}, {"msg_count": 1})
        return total_users, (doc.get("msg_count", 0) if doc else 0)
    except Exception as e:
        print("DB stats error:", e)
        return 0, 0

def get_all_user_ids():
    try:
        return [d["_id"] for d in users_col.find({}, {"_id": 1})]
    except Exception as e:
        print("DB list error:", e)
        return []
# ============================================================
# TRANSLATIONS
# ============================================================
TRANSLATIONS = {
    "am": {
        "btn_add": "ቦቱን ወደ ቻትዎ ለመጨመር",
        "btn_order": "ማስታወቂያ ለማሰራት",
        "btn_price": "Price | ዋጋ",
        "btn_payment": "Payment Method",
        "btn_status": "My Status & Stats",
        "btn_lang": "Language | ቋንቋ",
        "btn_support": "Support | ድጋፍ",
        "btn_back": "Back to Menu",
        "done_msg": "✅ ተጠናቋል! ቋንቋዎ ተስተካክሏል።",
        "loading": '⏳ Loading|ይጠብቁ...',
        "video_converted": '🎵 ከቪዲዮ የተቀየረው (Extracted Audio)\n\n✅ Converted with @{bot_username} & @mame_posts',
        "video_downloaded": '🚀 Downloaded with @{bot_username} & @mame_posts\n\n✅ Enjoy!',
        "size_limit": "⚠️ ቪዲዮው ከ 50MB በላይ ስለሆነ በቴሌግራም መላክ አይቻልም!",
        "fail_download": "💔  የፈለጉትን File ማግኘት አልቻልኩም!\n\nእባክዎ የላኩት ሊንክ private አለመሆኑን አረጋግጠው እንደገና ይሞክሩ።",
        "photo_download": '📸 Downloaded Photo\n\n✅ Downloaded with @{bot_username}',
        "welcome": (
            'Hello 🚨\n\n'
            '✅ My options (ከሁሉም Social Media ላይ video, photo እና audio ማውረድና መቀየር ይችላሉ!) :\n\n'
            '🎵 | Tiktok & Likee: videos & photos\n'
            '📸 | Pinterest & Instagram: reels, photos & stories\n'
            '▶️ | YouTube: videos & music (Full & Shorts)\n'
            '✖️ | Twitter (X): videos & voice\n'
            '📘 | Facebook, Reddit, Twitch, Vimeo & Others\n'
            '📹 Video to Audio Converter: ቪዲዮ ወደ ኦዲዮ መቀየር ይችላሉ! \n\n'
            'And others Social Media | ሌሎችንም ሶሻል ሚድያ ማውረድ ይችላሉ!: 📥'
        ),
        "price": (
            '💰 የማስታወቂያ ዋጋዎች\n\n'
            '📌 12 Hours — በስምምነት ETB\n'
            '📌 24 Hours — 500 ETB\n'
            '📌 48 Hours — 700 ETB\n\n'
            'የፈለጉትን ምርጫ አሳውቀው የክፍያ አማራጮችን (payment method) ይጎብኙ 🤝'
        ),
        "order": (
            '📢  @mame_posts ቻናል ላይ ማስታወቂያ ለማሰራት\n\n'
            '👇 እባክዎ ማስታወቂያ ማሰራት የሚፈልጉትን Post ከስር ልከው የማስታወቂያ ዋጋዎችን ይመልከቱ ℹ️'
        ),
        "payment": (
            '💳 Payment Method\n\n'
            '🏦 ንግድ ባንክ (CBE)\n1000528274394\n\nMohammed Seid\n\n'
            '📱 ቴሌ ብር (TELE BIRR)\n+251963266849\n\n'
            '✅ ክፍያውን ሲፈጽሙ ስክሪን ሹቱን ከስር ይላኩ!'
        ),
        "support": (
            '💬 Support & Downloader Help\n\n'
            '📺 ቪዲዮ/ፎቶ ለማውረድ: የ Tiktok, Instagram, Facebook, Reddit, Twitch, Vimeo, SoundCloud, Threads እና ሌሎች ሊንክ ቀጥታ ለቦቱ ይላኩ።\n\n'
            '📹 Video to Audio: ማናቸውንም ቪዲዮ ከስልክዎ ይላኩ፣ ወደ MP3 Audio ቀይሮ ይልክልዎታል።\n\n'
            '👩‍💻 ለአድሚን መልዕክት ለመላክም እዚሁ መጻፍ ይችላሉ።'
        )
    },
    "en": {
        "btn_add": "Add a bot to the chat",
        "btn_order": "Promote / Advertise",
        "btn_price": "Price & Rates",
        "btn_payment": "Payment Method",
        "btn_status": "My Status & Stats",
        "btn_lang": "Language | ቋንቋ",
        "btn_support": "Support & Help",
        "btn_back": "Back to Menu",
        "done_msg": "✅ Done! Your language has been set.",
        "loading": '⏳ Loading|Please wait...',
        "video_converted": '🎵 Extracted Audio\n\n✅ Converted with @{bot_username} & @mame_posts',
        "video_downloaded": '🚀 Downloaded with @{bot_username} & @mame_posts\n\n✅ Enjoy!',
        "size_limit": "⚠️ File is larger than 50MB! Telegram limit exceeded.",
        "fail_download": "💔 Could not download the file! Please check if link is public.",
        "photo_download": '📸 Downloaded Photo\n\n✅ Downloaded with @{bot_username}',
        "welcome": (
            'Hello 🚨\n\n'
            '✅ My options (You can download video, photo, and audio from all Social Media):\n\n'
            '🎵 | Tiktok & Likee: videos & photos\n'
            '📸 | Pinterest & Instagram: reels, photos & stories\n'
            '▶️ | YouTube: videos & music (Full & Shorts)\n'
            '✖️ | Twitter (X): videos & voice\n'
            '📘 | Facebook, Reddit, Twitch, Vimeo & Others\n'
            '📹 Video to Audio Converter: Convert video to audio!\n\n'
            'And other Social Media: 📥'
        ),
        "price": (
            '💰 Advertising Rates\n\n'
            '📌 12 Hours — Negotiable ETB\n'
            '📌 24 Hours — 500 ETB\n'
            '📌 48 Hours — 700 ETB\n\n'
            'Choose your plan and proceed to Payment Method 🤝'
        ),
        "order": (
            '📢 To Advertise on @mame_posts Channel\n\n'
            '👇 Please send your promo post below and view our rates ℹ️'
        ),
        "payment": (
            '💳 Payment Method\n\n'
            '🏦 Commercial Bank of Ethiopia (CBE)\n1000528274394\n\nMohammed Seid\n\n'
            '📱 TELEBIRR\n+251963266849\n\n'
            '✅ Please send receipt screenshot after payment!'
        ),
        "support": (
            '💬 Support & Downloader Help\n\n'
            '📺 To Download Video/Photo: Send links from Tiktok, Instagram, Facebook, Reddit, Twitch, Vimeo, SoundCloud, Threads, etc.\n\n'
            '📹 Video to Audio: Send any video to convert it to MP3 audio.\n\n'
            '👩‍💻 You can write messages here to reach out to the Admin.'
        )
    },
    "ar": {
        "btn_add": "إضافة البوت إلى المجموعة",
        "btn_order": "طلب إعلان",
        "btn_price": "أسعار الإعلانات",
        "btn_payment": "طرق الدفع",
        "btn_status": "حسابي وإحصائياتي",
        "btn_lang": "Language | ቋንቋ",
        "btn_support": "الدعم والتعليمات",
        "btn_back": "العودة للقائمة",
        "done_msg": "✅ تم! تم تعيين لغتك.",
        "loading": '⏳ جاري التحميل...',
        "video_converted": '🎵 الصوت المستخرج\n\n✅ تم التحويل بواسطة @{bot_username} & @mame_posts',
        "video_downloaded": '🚀 تم التحميل بواسطة @{bot_username} & @mame_posts\n\n✅ استمتع!',
        "size_limit": "⚠️ حجم الملف أكبر من 50 ميغابايت!",
        "fail_download": "💔 تعذر تحميل الملف! يرجى التأكد من أن الرابط عام.",
        "photo_download": '📸 الصورة المحملة\n\n✅ تم التحميل بواسطة @{bot_username}',
        "welcome": (
            'مرحباً بك 🚨\n\n'
            '✅ خياراتي (يمكنك تحميل وتعديل الفيديوهات والصور والصوتيات من جميع منصات التواصل الاجتماعي):\n\n'
            '🎵 | Tiktok & Likee: مقاطع وصور\n'
            '📸 | Pinterest & Instagram: ريلز، صور وستوري\n'
            '▶️ | YouTube: فيديوهات وموسيقى (كامل وShorts)\n'
            '✖️ | Twitter (X): فيديوهات وتغريدات صوتية\n'
            '📘 | Facebook, Reddit, Twitch, Vimeo وغيرها\n'
            '📹 تحويل الفيديو إلى صوت: يمكنك تحويل أي فيديو إلى ملف صوتي MP3!\n\n'
            'والمزيد من منصات التواصل الاجتماعي: 📥'
        ),
        "price": (
            '💰 أسعار الإعلانات\n\n'
            '📌 12 ساعة — حسب الاتفاق ETB\n'
            '📌 24 ساعة — 500 ETB\n'
            '📌 48 ساعة — 700 ETB\n\n'
            'اختر خطتك ثم انتقل إلى طرق الدفع 🤝'
        ),
        "order": (
            '📢 للإعلان على قناة @mame_posts\n\n'
            '👇 يرجى إرسال المنشور الذي تريد الإعلان عنه أدناه لعرض الأسعار ℹ️'
        ),
        "payment": (
            '💳 طرق الدفع\n\n'
            '🏦 البنك التجاري الإثيوبي (CBE)\n1000528274394\n\nMohammed Seid\n\n'
            '📱 تلي بر (TELE BIRR)\n+251963266849\n\n'
            '✅ يرجى إرسال صورة إيصال الدفع بعد التحويل!'
        ),
        "support": (
            '💬 الدعم والمساعدة في التحميل\n\n'
            '📺 لتحميل الفيديوهات/الصور: أرسل روابط تيك توك، إنستغرام، فيسبوك، ريديت، تويتش وغيرها مباشرة.\n\n'
            '📹 تحويل الفيديو إلى صوت: أرسل أي فيديو لتحويله إلى ملف صوتي MP3.\n\n'
            '👩‍💻 يمكنك كتابة رسائلك هنا للتواصل مع المسؤول مباشرة.'
        )
    }
}
def get_trans(user_id, key):
    lang = get_user_language(user_id)
    if not lang or lang not in TRANSLATIONS:
        lang = "am"
    lang_dict = TRANSLATIONS.get(lang, TRANSLATIONS["am"])
    return lang_dict.get(key, TRANSLATIONS["am"].get(key, ""))
def get_bot_username(context):
    username = context.bot.username
    return username if username else "mame_posts_bot"
def get_main_menu_keyboard(bot_username, user_id, use_custom_emoji=True):
    def btn(text, callback_data=None, url=None, emoji_id=None, style=None):
        kwargs = {"text": text}
        if callback_data:
            kwargs["callback_data"] = callback_data
        if url:
            kwargs["url"] = url
        if use_custom_emoji and emoji_id:
            kwargs["icon_custom_emoji_id"] = emoji_id
        if style:
            kwargs["api_kwargs"] = {"style": style}
        return InlineKeyboardButton(**kwargs)
    keyboard = [
        [btn(get_trans(user_id, "btn_add"), url=f"https://t.me/{bot_username}?startgroup=true", emoji_id="5305545479814161889", style="success")],
        [btn(get_trans(user_id, "btn_order"), callback_data="cmd_order", emoji_id="5267442591548320083", style="primary")],
        [
            btn(get_trans(user_id, "btn_price"), callback_data="cmd_price", emoji_id="5447458260200214425", style="primary"),
            btn(get_trans(user_id, "btn_payment"), callback_data="cmd_payment", emoji_id="5186349709169525403", style="success")
        ],
        [
            btn(get_trans(user_id, "btn_status"), callback_data="cmd_status", emoji_id="5431577498364158238", style="primary"),
            btn(get_trans(user_id, "btn_lang"), callback_data="cmd_change_lang", emoji_id="5431577498364158238", style="primary")
        ],
        [btn(get_trans(user_id, "btn_support"), callback_data="cmd_support", emoji_id="5949327894567195412", style="danger")]
    ]
    return InlineKeyboardMarkup(keyboard)
def get_language_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("🇪🇹 አማርኛ", callback_data="lang_am"),
            InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
        ],
        [InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar")]
    ]
    kwargs["api_kwargs"] = {"style": "danger"}
    return InlineKeyboardMarkup(keyboard)
def get_back_keyboard(user_id, use_custom_emoji=True):
    kwargs = {"text": get_trans(user_id, "btn_back"), "callback_data": "cmd_back"}
    if use_custom_emoji:
        kwargs["icon_custom_emoji_id"] = "5248948801674159296"
    return InlineKeyboardMarkup([[InlineKeyboardButton(**kwargs)]])
async def post_init(application):
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("menu", "Main menu"),
        BotCommand("status", "Check status"),
        BotCommand("rate", "Advertising rates"),
        BotCommand("payment", "Payment methods"),
        BotCommand("help", "Help and support")
    ]
    await application.bot.set_my_commands(commands)
async def is_joined(update, context):
    user_id = update.effective_user.id
    try:
        member = await context.bot.get_chat_member(chat_id=FORCE_CHANNEL, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        print("Force Join Error:", e)
        return True
async def show_force_join(update, context):
    user_id = update.effective_user.id
    lang = get_user_language(user_id)
    if lang == "en":
        text = (
            '🔒 '
            'You must join the channel below to use the bot!\n\n'
            '1️⃣ 📢 Click Join Channel:\n'
            '2️⃣ ✅ Click I\'ve Joined and resend your link!'
        )
        btn_join_text = "Join Channel"
        btn_joined_text = "I've Joined"
    elif lang == "ar":
        text = (
            '🔒 '
            'يجب عليك الاشتراك في القناة أدناه لاستخدام البوت!\n\n'
            '1️⃣ 📢 اضغط على انضمام للقناة:\n'
            '2️⃣ ✅ اضغط على تم الانضمام وأعد إرسال الرابط!'
        )
        btn_join_text = "انضمام للقناة"
        btn_joined_text = "تم الانضمام"
    else:
        text = (
            '🔒 '
            'ቦቱን ለመጠቀም ከታች ያለውን ቻናል መቀላቀል አለብዎት!\n\n'
            '1️⃣ 📢 Join Channel የሚለውን ይጫኑ:\n'
            '2️⃣ ✅ I\'ve Joined የሚለውን ተጭነው የላኩትን ደግመው ይላኩ!'
        )
        btn_join_text = "Join Channel"
        btn_joined_text = "I've Joined"
    keyboard_custom = [
        [InlineKeyboardButton(text=btn_join_text, icon_custom_emoji_id="5767358836134382747", url=FORCE_CHANNEL_LINK)],
        [InlineKeyboardButton(text=btn_joined_text, icon_custom_emoji_id="5895288332581082241", callback_data="check_join")]
    ]
    keyboard_normal = [
        [InlineKeyboardButton(text=f"📢 {btn_join_text}", url=FORCE_CHANNEL_LINK)],
        [InlineKeyboardButton(text=f"✅ {btn_joined_text}", callback_data="check_join")]
    ]
    try:
        await update.message.reply_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard_custom), parse_mode="HTML")
    except Exception:
        await update.message.reply_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard_normal), parse_mode="HTML")
async def send_main_menu(chat_id, context, user_id):
    bot_username = get_bot_username(context)
    text = get_trans(user_id, "welcome")
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=get_main_menu_keyboard(bot_username, user_id, use_custom_emoji=True),
            parse_mode="HTML"
        )
    except Exception:
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=get_main_menu_keyboard(bot_username, user_id, use_custom_emoji=False),
            parse_mode="HTML"
        )
# ============================================================
# COMMAND HANDLERS
# ============================================================
async def start(update, context):
    if not update.message:
        return
    user_id = update.effective_user.id
    record_user_activity(user_id)
    setup_keyboard = ReplyKeyboardMarkup([["🏠 Menu"]], resize_keyboard=True, input_field_placeholder="Send link 🔗")
    user_lang = get_user_language(user_id)
    if not user_lang:
        await update.message.reply_text(
            "Please select your language / እባክዎ ቋንቋ ይምረጡ / اختر لغتك፦",
            reply_markup=get_language_keyboard(),
            parse_mode="HTML"
        )
        return
    await update.message.reply_text("🏠", reply_markup=setup_keyboard)
    await send_main_menu(update.effective_chat.id, context, user_id)
async def status_command(update, context):
    if not update.message:
        return
    user = update.effective_user
    record_user_activity(user.id)
    total_users, user_msg_count = get_user_stats(user.id)
    username_text = f"@{user.username}" if user.username else "የለውም"
    msg = (
        '📊 My Status & Stats\n\n'
        f'👤 Username: {username_text}\n'
        f'🆔 ID: {user.id}\n\n'
        f'💬 Your Messages: {user_msg_count}\n'
        f'👥 Bot Users: {total_users}\n\n'
        '🔥 Engagement: Active'
    )
    await update.message.reply_text(msg, parse_mode="HTML")
async def rates_command(update, context):
    if not update.message:
        return
    user_id = update.effective_user.id
    record_user_activity(user_id)
    await update.message.reply_text(get_trans(user_id, "price"), parse_mode="HTML")
async def payment_command(update, context):
    if not update.message:
        return
    user_id = update.effective_user.id
    record_user_activity(user_id)
    await update.message.reply_text(get_trans(user_id, "payment"), parse_mode="HTML")
async def help_command(update, context):
    if not update.message:
        return
    user_id = update.effective_user.id
    record_user_activity(user_id)
    await update.message.reply_text(get_trans(user_id, "support"), parse_mode="HTML")
async def broadcast_command(update, context):
    if not update.message or update.effective_user.id != ADMIN_ID:
        return
    reply_msg = update.message.reply_to_message
    has_args = bool(context.args)
    if not reply_msg and not has_args:
        await update.message.reply_text("❌ Reply to a message or use:\n/broadcast your message")
        return
    data = {str(uid): {} for uid in get_all_user_ids()}
    success_count = 0
    fail_count = 0
    status_msg = await update.message.reply_text("📢 Broadcasting...")
    for uid_str in data.keys():
        try:
            chat_id = int(uid_str)
            if reply_msg:
                await reply_msg.copy(chat_id=chat_id)
            else:
                text_to_send = " ".join(context.args)
                await context.bot.send_message(chat_id=chat_id, text=text_to_send, parse_mode="HTML")
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail_count += 1
    await status_msg.edit_text(
        f"✅ Broadcast completed.\n\nSuccessful: {success_count}\nFailed: {fail_count}"
    )
# ============================================================
# VIDEO TO AUDIO CONVERTER
# ============================================================
async def convert_video_to_audio(update, context):
    if not update.message:
        return
    user_id = update.effective_user.id
    record_user_activity(user_id)
    if not await is_joined(update, context):
        await show_force_join(update, context)
        return
    video = update.message.video or update.message.video_note
    if not video:
        document = update.message.document
        if document and document.mime_type and document.mime_type.startswith("video/"):
            video = document
    if not video:
        return
    file_id = update.message.message_id
    input_path = f"input_vid_{user_id}_{file_id}.mp4"
    output_path = f"output_aud_{user_id}_{file_id}.mp3"
    status_msg = None
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.RECORD_VOICE)
        status_msg = await update.message.reply_text(get_trans(user_id, "loading"), parse_mode="HTML")
        tg_file = await video.get_file()
        await tg_file.download_to_drive(input_path)
        if not os.path.exists(input_path) or os.path.getsize(input_path) == 0:
            raise RuntimeError("Downloaded video is empty")
        ffmpeg_bin = FFMPEG_PATH if FFMPEG_PATH else "ffmpeg"
        cmd = [ffmpeg_bin, "-y", "-i", input_path, "-vn", "-acodec", "libmp3lame", "-q:a", "2", output_path]
        result = await asyncio.to_thread(subprocess.run, cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=300)
        if result.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            raise RuntimeError("FFmpeg error")
        bot_username = get_bot_username(context)
        share_url = f"https://t.me/share/url?url={quote(f'https://t.me/{bot_username}?start=share')}&text={quote('Try this awesome Bot!🔥')}"
        keyboard_share = [[InlineKeyboardButton("🔗 Share Bot 🚀", url=share_url)]]
        caption_text = get_trans(user_id, "video_converted").format(bot_username=bot_username)
        raw_name = getattr(video, "file_name", None)
        base_title = os.path.splitext(raw_name)[0] if raw_name else (update.message.caption or "")
        base_title = base_title.strip() or "Audio"
        safe_name = re.sub(r'[\\/:*?"<>|\r\n]+', ' ', base_title).strip()[:60] or "audio"
        with open(output_path, "rb") as audio_file:
            await update.message.reply_audio(
                audio=audio_file,
                title=base_title[:64],
                performer="🎧 Mame Posts Bot",
                filename=f"{safe_name}.mp3",
                caption=caption_text,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(keyboard_share)
            )
        if status_msg:
            await status_msg.delete()
    except Exception as e:
        print("Video to Audio Error:", e)
        if status_msg:
            await status_msg.edit_text(get_trans(user_id, "fail_download"), parse_mode="HTML")
    finally:
        for path in [input_path, output_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
# ============================================================
# MODERN URL DOWNLOAD ENGINE (WITH YOUTUBE FIX)
# ============================================================
def unshorten_url(url: str) -> str:
    try:
        session = requests.Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        resp = session.head(url, allow_redirects=True, timeout=10)
        return resp.url
    except Exception:
        return url
def clean_url(raw_url: str) -> str:
    return unshorten_url(raw_url)
def get_video_options(url: str, output_template: str, fallback: bool = False):
    is_youtube = any(domain in url.lower() for domain in ["youtube.com", "youtu.be"])
    opts = {
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'geo_bypass': True,
        'concurrent_fragment_downloads': 5,
        'outtmpl': output_template,
        'merge_output_format': 'mp4',
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    }
    if is_youtube:
        if fallback:
            # Fallback 1: Combined 720p/360p pre-merged progressive stream
            opts['format'] = 'best[ext=mp4][filesize<50M]/best[filesize<50M]/best'
            opts['extractor_args'] = {
                'youtube': {
                    'player_client': ['ios', 'android']
                }
            }
        else:
            # Primary: Best video + best audio merged, cap at 45MB to respect Telegram limits
            opts['format'] = 'bestvideo[ext=mp4][filesize<45M]+bestaudio[ext=m4a]/best[ext=mp4][filesize<50M]/best[filesize<50M]/best'
            opts['extractor_args'] = {
                'youtube': {
                    'player_client': ['android', 'ios', 'web_creator']
                }
            }
    else:
        opts['format'] = 'best[filesize<50M]/bestvideo+bestaudio/best'
    if "likee" in url or "likee.video" in url:
        opts['http_headers']['Referer'] = 'https://likee.video/'
    elif "vimeo.com" in url:
        opts['http_headers']['Referer'] = 'https://vimeo.com/'
    if os.path.exists('cookies.txt'):
        opts['cookiefile'] = 'cookies.txt'
    return opts
def download_media_func(url: str, output_template: str, fallback: bool = False):
    with yt_dlp.YoutubeDL(get_video_options(url, output_template, fallback)) as ydl:
        info = ydl.extract_info(url, download=True)
    return info
    
def find_downloaded_file(prefix: str):
    for f in os.listdir('.'):
        if f.startswith(prefix) and not f.endswith(('.part', '.ytdl', '.temp')):
            return f
    return None
async def handle_url_download(update: Update, context: ContextTypes.DEFAULT_TYPE, raw_url: str):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_DOCUMENT)
    status_msg = await update.message.reply_text(
        get_trans(user_id, "loading"),
        parse_mode="HTML"
    )
    bot_username = get_bot_username(context)
    share_url = f"https://t.me/share/url?url=https://t.me/{bot_username}?start=share&text=Try%20this%20awesome%20Downloader%20Bot!🔥"
    reply_markup_share = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Share Bot 🚀", url=share_url)]])
    url = clean_url(raw_url)
    # Direct Pinterest Image extraction
    if "pinterest.com" in url or "pin.it" in url:
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            res = requests.get(url, headers=headers, timeout=10)
            img_matches = re.findall(r'https://i\.pinimg\.com/(?:originals|736x)/[^\s"\'\>]+\.(?:jpg|png|jpeg|webp)', res.text)
            if img_matches:
                real_img_url = img_matches[0]
                await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_DOCUMENT)
                await update.message.reply_photo(
                    photo=real_img_url,
                    caption=get_trans(user_id, "photo_download").format(bot_username=bot_username),
                    reply_markup=reply_markup_share,
                    parse_mode="HTML"
                )
                await status_msg.delete()
                return
        except Exception as pe:
            print("Pinterest Fetch Error:", pe)
    media_prefix = f"media_{user_id}_{update.message.message_id}"
    media_template = f"{media_prefix}.%(ext)s"
    sent_any = False
    video_title = None
    try:
        try:
            info = await asyncio.to_thread(download_media_func, url, media_template, False)
        except Exception as err1:
            print("Download primary failed, trying client fallback:", err1)
            info = await asyncio.to_thread(download_media_func, url, media_template, True)
        if info:
            video_title = info.get("title")
        actual_file = find_downloaded_file(media_prefix)
        if actual_file and os.path.exists(actual_file):
            ext = os.path.splitext(actual_file)[1].lower()
            if ext in ['.jpg', '.jpeg', '.png', '.webp']:
                await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_DOCUMENT)
                with open(actual_file, 'rb') as pf:
                    await update.message.reply_photo(
                        photo=pf,
                        caption=get_trans(user_id, "photo_download").format(bot_username=bot_username),
                        reply_markup=reply_markup_share,
                        parse_mode="HTML"
                    )
                sent_any = True
            else:
                if os.path.getsize(actual_file) <= 50 * 1024 * 1024:
                    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_DOCUMENT)
                    try:
                        with open(actual_file, 'rb') as vf:
                            await update.message.reply_video(
                                video=vf,
                                caption=f'🚀 Downloaded with @{bot_username} & @mame_posts\n\n✅ Enjoy!',
                                reply_markup=reply_markup_share,
                                parse_mode="HTML",
                                supports_streaming=True
                            )
                        sent_any = True
                    except Exception as vid_err:
                        print("reply_video failed, document fallback:", vid_err)
                        with open(actual_file, 'rb') as doc_file:
                            await update.message.reply_document(
                                document=doc_file,
                                caption=f'🚀 Downloaded with @{bot_username} & @mame_posts',
                                reply_markup=reply_markup_share,
                                parse_mode="HTML"
                            )
                        sent_any = True
                    # Extract Audio
                    audio_output = f"audio_{user_id}_{update.message.message_id}.mp3"
                    ffmpeg_bin = FFMPEG_PATH if FFMPEG_PATH else "ffmpeg"
                    cmd = [ffmpeg_bin, "-y", "-i", actual_file, "-vn", "-acodec", "libmp3lame", "-q:a", "2", audio_output]
                    await asyncio.to_thread(subprocess.run, cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    if os.path.exists(audio_output) and os.path.getsize(audio_output) > 0:
                        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_DOCUMENT)
                        safe_name = re.sub(r'[\\/:*?"<>|\r\n]+', ' ', video_title or "audio").strip()[:60] or "audio"
                        with open(audio_output, 'rb') as af:
                            await update.message.reply_audio(
                                audio=af,
                                title=(video_title or "Audio")[:64],
                                performer="🎧 Mame Posts Bot",
                                filename=f"{safe_name}.mp3",
                                caption=f'🎧 Extracted Audio (MP3)\n\n✅ Downloaded with @{bot_username}',
                                reply_markup=reply_markup_share,
                                parse_mode="HTML"
                            )
                        os.remove(audio_output)
                        sent_any = True
                else:
                    await status_msg.edit_text(get_trans(user_id, "size_limit"), parse_mode="HTML")
                    return
    except Exception as e:
        print("Media Download Execution Error:", e)
    finally:
        for f in os.listdir('.'):
            if f.startswith(media_prefix):
                try:
                    os.remove(f)
                except Exception:
                    pass
    if sent_any:
        try:
            await status_msg.delete()
        except Exception:
            pass
    else:
        try:
            await status_msg.edit_text(get_trans(user_id, "fail_download"), parse_mode="HTML")
        except Exception:
            pass
# ============================================================
# CALLBACK QUERY & USER HANDLERS
# ============================================================
async def button_callback(update, context):
    query = update.callback_query
    data = query.data
    user = query.from_user
    user_id = user.id
    bot_username = get_bot_username(context)
    if data.startswith("lang_"):
        lang_code = data.split("_", 1)[1]
        if lang_code not in TRANSLATIONS:
            await query.answer("Language unavailable.", show_alert=True)
            return
        set_user_language(user_id, lang_code)
        await query.answer()
        try:
            await query.message.delete()
        except Exception:
            pass
        setup_keyboard = ReplyKeyboardMarkup([["🏠 Menu"]], resize_keyboard=True, input_field_placeholder="Send link 🔗")
        await context.bot.send_message(
            chat_id=user_id,
            text=get_trans(user_id, "done_msg"),
            reply_markup=setup_keyboard,
            parse_mode="HTML"
        )
        await send_main_menu(user_id, context, user_id)
        return
    if data == "cmd_change_lang":
        await query.answer()
        await query.edit_message_text(
            "Please select your language / እባክዎ ቋንቋ ይምረጡ / اختر لغتك፦",
            reply_markup=get_language_keyboard(),
            parse_mode="HTML"
        )
        return
    if data == "cmd_back":
        await query.answer()
        text = get_trans(user_id, "welcome")
        try:
            await query.edit_message_text(text=text, reply_markup=get_main_menu_keyboard(bot_username, user_id, True), parse_mode="HTML")
        except Exception:
            await query.edit_message_text(text=text, reply_markup=get_main_menu_keyboard(bot_username, user_id, False), parse_mode="HTML")
        return
    for key_cmd in ["price", "order", "payment", "support"]:
        if data == f"cmd_{key_cmd}":
            await query.answer()
            text = get_trans(user_id, key_cmd)
            try:
                await query.edit_message_text(text=text, reply_markup=get_back_keyboard(user_id, True), parse_mode="HTML")
            except Exception:
                await query.edit_message_text(text=text, reply_markup=get_back_keyboard(user_id, False), parse_mode="HTML")
            return
    if data == "cmd_status":
        await query.answer()
        total_users, user_msg_count = get_user_stats(user_id)
        username_text = f"@{user.username}" if user.username else "የለውም"
        msg = (
            '📊 My Status & Stats\n\n'
            f'👤 Username: {username_text}\n'
            f'🆔 ID: {user_id}\n\n'
            f'💬 Your Messages: {user_msg_count}\n'
            f'👥 Bot Users: {total_users}\n\n'
            '🔥 Engagement: Active'
        )
        try:
            await query.edit_message_text(text=msg, reply_markup=get_back_keyboard(user_id, True), parse_mode="HTML")
        except Exception:
            await query.edit_message_text(text=msg, reply_markup=get_back_keyboard(user_id, False), parse_mode="HTML")
        return
async def check_join(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    try:
        member = await context.bot.get_chat_member(chat_id=FORCE_CHANNEL, user_id=user_id)
        if member.status in ["member", "administrator", "creator"]:
            await query.answer()
            try:
                await query.edit_message_text(
                    '✅ አሁን ቻናሉን ተቀላቅለዋል።\n\nእባክዎ የላኩትን ሊንክ ደግመው ይላኩ።',
                    parse_mode="HTML"
                )
            except Exception:
                pass
        else:
            await query.answer("❌ እባክዎ መጀመሪያ Channel ይቀላቀሉ!", show_alert=True)
    except Exception:
        await query.answer("⚠️ Channel membership could not be verified.", show_alert=True)
SUPPORTED_DOMAINS = [
    "youtube.com", "youtu.be", "tiktok.com", "likee.video", "likee.com",
    "pinterest.com", "pin.it", "instagram.com", "twitter.com", "x.com",
    "facebook.com", "fb.watch", "reddit.com", "redd.it", "twitch.tv",
    "vimeo.com", "vk.com", "ok.ru", "tumblr.com", "soundcloud.com", "threads.net"
]
async def handle_user_messages(update, context):
    if not update.message:
        return
    user_id = update.effective_user.id
    record_user_activity(user_id)
    if update.message.video or update.message.video_note:
        await convert_video_to_audio(update, context)
        return
    document = update.message.document
    if document and document.mime_type and document.mime_type.startswith("video/"):
        await convert_video_to_audio(update, context)
        return
    text = update.message.text or update.message.caption or ""
    if text.strip() == "🏠 Menu":
        await send_main_menu(update.effective_chat.id, context, user_id)
        return
    text_lower = text.lower()
    is_supported_link = any(domain in text_lower for domain in SUPPORTED_DOMAINS)
    if is_supported_link:
        if not await is_joined(update, context):
            await show_force_join(update, context)
            return
        url_match = re.search(r"https?://[^\s]+", text)
        target_url = url_match.group(0).rstrip(".,!?)]}") if url_match else text.strip()
        await handle_url_download(update, context, target_url)
        return
    # Forward other messages to Admin
    username = f"@{update.effective_user.username}" if update.effective_user.username else "No username"
    header_text = (
        "📩 New User Message\n\n"
        f"👤 Name: {update.effective_user.full_name}\n"
        f"🔗 Username: {username}\n"
        f"🆔 ID: {user_id}"
    )
    try:
        header_msg = await context.bot.send_message(chat_id=ADMIN_ID, text=header_text, parse_mode="HTML")
        forwarded_msg = await update.message.forward(chat_id=ADMIN_ID)
        if "user_mapping" not in context.bot_data:
            context.bot_data["user_mapping"] = {}
        user_mapping = context.bot_data["user_mapping"]
        user_mapping[str(header_msg.message_id)] = user_id
        user_mapping[str(forwarded_msg.message_id)] = user_id
        await update.message.reply_text("✅ መልዕክትዎ ተቀብለናል። Admin ያነበበውን መልስ ይልክልዎታል።")
    except Exception as e:
        print("Admin forwarding error:", e)
async def admin_reply(update, context):
    if not update.message or update.effective_user.id != ADMIN_ID:
        return
    replied_msg = update.message.reply_to_message
    if not replied_msg:
        return
    user_mapping = context.bot_data.get("user_mapping", {})
    target_user_id = None
    replied_id_str = str(replied_msg.message_id)
    if replied_id_str in user_mapping:
        target_user_id = user_mapping[replied_id_str]
    if not target_user_id and replied_msg.forward_from:
        target_user_id = replied_msg.forward_from.id
    if not target_user_id and replied_msg.text and "🆔 ID:" in replied_msg.text:
        match = re.search(r"🆔 ID:\s*(\d+)", replied_msg.text)
        if match:
            target_user_id = int(match.group(1))
    if not target_user_id and replied_msg.caption and "🆔 ID:" in replied_msg.caption:
        match = re.search(r"🆔 ID:\s*(\d+)", replied_msg.caption)
        if match:
            target_user_id = int(match.group(1))
    if target_user_id:
        try:
            await update.message.copy(chat_id=target_user_id)
            await update.message.reply_text("✅ Reply sent to the user.")
        except Exception as e:
            await update.message.reply_text(f"❌ Could not send reply.\n{e}")
    else:
        await update.message.reply_text("❌ User ID could not be found.")
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print("❌ ERROR:", context.error)
# ============================================================
# MAIN
# ============================================================
def main():
    if not TOKEN:
        raise RuntimeError("❌ BOT_TOKEN environment variable is missing!")
    keep_alive()
    application = (
        ApplicationBuilder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", start))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("rates", rates_command))
    application.add_handler(CommandHandler("rate", rates_command))
    application.add_handler(CommandHandler("payment", payment_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CallbackQueryHandler(check_join, pattern=r"^check_join$"))
    application.add_handler(CallbackQueryHandler(button_callback, pattern=r"^(cmd_|lang_)"))
    admin_filter = filters.User(user_id=ADMIN_ID) & filters.REPLY & ~filters.COMMAND
    application.add_handler(MessageHandler(admin_filter, admin_reply))
    application.add_handler(MessageHandler(filters.VIDEO | filters.VIDEO_NOTE, convert_video_to_audio))
    type_filter = (
        filters.TEXT
        | filters.PHOTO
        | filters.Document.ALL
        | filters.VOICE
        | filters.AUDIO
        | filters.Sticker.ALL
    ) & ~filters.COMMAND
    application.add_handler(MessageHandler(type_filter, handle_user_messages))
    application.add_error_handler(error_handler)
    print("🤖 Mame Posts Bot is running...")
    application.run_polling(drop_pending_updates=True)
if __name__ == "__main__":
    main()
