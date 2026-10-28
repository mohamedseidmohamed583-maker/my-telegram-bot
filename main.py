import os
import re
import html
import json
import asyncio
import subprocess
import requests
import shutil
import tempfile
import glob
import static_ffmpeg
# FFmpeg setup
try:
    static_ffmpeg.add_paths()
except Exception as e:
    print("Static FFmpeg setup warning:", e)
FFMPEG_PATH = shutil.which("ffmpeg")
from datetime import datetime, timedelta
from threading import Thread
from urllib.parse import quote, urlparse
from flask import Flask
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    BotCommand
)
from telegram.constants import ChatAction
from telegram.error import RetryAfter
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    TypeHandler,
    filters
)
import yt_dlp
from admin_panel import setup_admin
from ads import setup_ads
from growth import setup_growth, bump_stat, platform_of
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
admin_map_col = mongo_client["mamebot"]["admin_map"]
_lang_cache = {}
GROWTH = None

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

# ---- daily limit: downloads + video->audio conversions per user ----
DAILY_LIMIT = int(os.environ.get("DAILY_LIMIT", "10"))
def _today():
    # the day changes at midnight Ethiopia time (UTC+3)
    return (datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%d")
def take_quota_sync(user_id):
    """Atomically uses one of today's downloads. True = allowed."""
    if user_id == ADMIN_ID:
        return True
    today = _today()
    try:
        users_col.update_one({"_id": user_id}, {"$setOnInsert": {"msg_count": 0}}, upsert=True)
        users_col.update_one(
            {"_id": user_id, "dl_date": {"$ne": today}},
            {"$set": {"dl_date": today, "dl_count": 0}},
        )
        r = users_col.update_one(
            {"_id": user_id, "dl_date": today, "dl_count": {"$lt": DAILY_LIMIT}},
            {"$inc": {"dl_count": 1}},
        )
        return r.modified_count == 1
    except Exception as e:
        print("DB quota error:", e)
        return True          # if the database hiccups, do not block users
def refund_quota_sync(user_id):
    if user_id == ADMIN_ID:
        return
    try:
        users_col.update_one(
            {"_id": user_id, "dl_date": _today(), "dl_count": {"$gt": 0}},
            {"$inc": {"dl_count": -1}},
        )
    except Exception as e:
        print("DB quota refund error:", e)
def get_quota_used(user_id):
    try:
        doc = users_col.find_one({"_id": user_id}, {"dl_date": 1, "dl_count": 1})
        if doc and doc.get("dl_date") == _today():
            return doc.get("dl_count", 0)
    except Exception as e:
        print("DB quota read error:", e)
    return 0
def get_all_user_ids():
    try:
        return [d["_id"] for d in users_col.find({}, {"_id": 1})]
    except Exception as e:
        print("DB list error:", e)
        return []
def save_admin_map(message_ids, user_id):
    """Remember which user a forwarded message belongs to (survives restarts)."""
    try:
        admin_map_col.insert_many(
            [{"_id": mid, "user_id": user_id} for mid in message_ids], ordered=False
        )
    except Exception as e:
        print("DB admin_map save error:", e)

def load_admin_map(message_id):
    try:
        d = admin_map_col.find_one({"_id": message_id})
        return d["user_id"] if d else None
    except Exception as e:
        print("DB admin_map load error:", e)
        return None
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
        "done_msg": "✅ <b>ተጠናቋል! ቋንቋዎ ተስተካክሏል።</b>",
        "loading": '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> <b>Loading|ይጠብቁ...</b>',
        "video_converted": '<tg-emoji emoji-id="5305534793935527938">🎵</tg-emoji> <b>ከቪዲዮ የተቀየረው (Extracted Audio)</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Converted with</b> @{bot_username} & @mame_posts',
        "video_downloaded": '🚀 <b>Downloaded with</b> @{bot_username} & @mame_posts\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Enjoy!</b>',
        "size_limit": "⚠️ <b>ቪዲዮው ከ 50MB በላይ ስለሆነ በቴሌግራም መላክ አይቻልም!</b>",
        "fail_download": "💔 <b> የፈለጉትን File ማግኘት አልቻልኩም!</b>\n\nእባክዎ የላኩት ሊንክ private አለመሆኑን አረጋግጠው እንደገና ይሞክሩ።",
        "photo_download": '📸 <b>Downloaded Photo</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Downloaded with</b> @{bot_username}',
        "welcome": (
            'Hello <tg-emoji emoji-id="5305577086478489521">🚨</tg-emoji>\n\n'
            '<tg-emoji emoji-id="5305739801314501775">✅</tg-emoji> <b>My options (ከሁሉም Social Media ላይ video, photo እና audio ማውረድና መቀየር ይችላሉ!) :</b>\n\n'
            '<tg-emoji emoji-id="5305290882742788410">🎵</tg-emoji> | <b>Tiktok & Likee: videos & photos</b>\n'
            '<tg-emoji emoji-id="5305551797711053969">📸</tg-emoji> | <b>Pinterest & Instagram: reels, photos & stories</b>\n'
            '<tg-emoji emoji-id="5305777524012262308">▶️</tg-emoji> | <b>YouTube: videos & music (Full & Shorts)</b>\n'
            '<tg-emoji emoji-id="5305474827602140530">✖️</tg-emoji> | <b>Twitter (X): videos & voice</b>\n'
            '<tg-emoji emoji-id="5305311717629142471">📘</tg-emoji> | <b>Facebook, Reddit, Twitch, Vimeo & Others</b>\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>Video to Audio Converter: ቪዲዮ ወደ ኦዲዮ መቀየር ይችላሉ! </b>\n\n'
            '<b>And others Social Media | ሌሎችንም ሶሻል ሚድያ ማውረድ ይችላሉ!:</b> <tg-emoji emoji-id="5305466057278923962">📥</tg-emoji>'
        ),
        "price": (
            '<tg-emoji emoji-id="5447458260200214425">💰</tg-emoji> <b>የማስታወቂያ ዋጋዎች</b>\n\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 12 Hours — <b>በስምምነት ETB</b>\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 24 Hours — <b>500 ETB</b>\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 48 Hours — <b>700 ETB</b>\n\n'
            'የፈለጉትን ምርጫ አሳውቀው የክፍያ አማራጮችን (payment method) ይጎብኙ <tg-emoji emoji-id="5463249828450424568">🤝</tg-emoji>'
        ),
        "order": (
            '<tg-emoji emoji-id="5197304993920616826">📢</tg-emoji> <b> @mame_posts ቻናል ላይ ማስታወቂያ ለማሰራት</b>\n\n'
            '<tg-emoji emoji-id="5305634553140912174">👇</tg-emoji> እባክዎ ማስታወቂያ ማሰራት የሚፈልጉትን Post ከስር ልከው የማስታወቂያ ዋጋዎችን ይመልከቱ <tg-emoji emoji-id="5305739801314501775">ℹ️</tg-emoji>'
        ),
        "payment": (
            '<tg-emoji emoji-id="5186349709169525403">💳</tg-emoji> <b>Payment Method</b>\n\n'
            '<tg-emoji emoji-id="5961054379350955385">🏦</tg-emoji> <b>ንግድ ባንክ (CBE)</b>\n<code>1000528274394</code>\n\nMohammed Seid\n\n'
            '<tg-emoji emoji-id="5960632377339285724">📱</tg-emoji> <b>ቴሌ ብር (TELE BIRR)</b>\n<code>+251963266849</code>\n\n'
            '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>ክፍያውን ሲፈጽሙ ስክሪን ሹቱን ከስር ይላኩ!</b>'
        ),
        "support": (
            '<tg-emoji emoji-id="5305545479814161889">💬</tg-emoji> <b>Support & Downloader Help</b>\n\n'
            '<tg-emoji emoji-id="5305655375142364109">📺</tg-emoji> <b>ቪዲዮ/ፎቶ ለማውረድ:</b> የ Tiktok, Instagram, Facebook, Reddit, Twitch, Vimeo, SoundCloud, Threads እና ሌሎች ሊንክ ቀጥታ ለቦቱ ይላኩ።\n\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>Video to Audio:</b> ማናቸውንም ቪዲዮ ከስልክዎ ይላኩ፣ ወደ MP3 Audio ቀይሮ ይልክልዎታል።\n\n'
            '<tg-emoji emoji-id="5949327894567195412">👩‍💻</tg-emoji> ለአድሚን መልዕክት ለመላክም እዚሁ መጻፍ ይችላሉ።'
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
        "done_msg": "✅ <b>Done! Your language has been set.</b>",
        "loading": '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> <b>Loading|Please wait...</b>',
        "video_converted": '<tg-emoji emoji-id="5305534793935527938">🎵</tg-emoji> <b>Extracted Audio</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Converted with</b> @{bot_username} & @mame_posts',
        "video_downloaded": '🚀 <b>Downloaded with</b> @{bot_username} & @mame_posts\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Enjoy!</b>',
        "size_limit": "⚠️ <b>File is larger than 50MB! Telegram limit exceeded.</b>",
        "fail_download": "💔 <b>Could not download the file! Please check if link is public.</b>",
        "photo_download": '📸 <b>Downloaded Photo</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Downloaded with</b> @{bot_username}',
        "welcome": (
            'Hello <tg-emoji emoji-id="5305577086478489521">🚨</tg-emoji>\n\n'
            '<tg-emoji emoji-id="5305739801314501775">✅</tg-emoji> <b>My options (You can download video, photo, and audio from all Social Media):</b>\n\n'
            '<tg-emoji emoji-id="5305290882742788410">🎵</tg-emoji> | <b>Tiktok & Likee: videos & photos</b>\n'
            '<tg-emoji emoji-id="5305551797711053969">📸</tg-emoji> | <b>Pinterest & Instagram: reels, photos & stories</b>\n'
            '<tg-emoji emoji-id="5305777524012262308">▶️</tg-emoji> | <b>YouTube: videos & music (Full & Shorts)</b>\n'
            '<tg-emoji emoji-id="5305474827602140530">✖️</tg-emoji> | <b>Twitter (X): videos & voice</b>\n'
            '<tg-emoji emoji-id="5305311717629142471">📘</tg-emoji> | <b>Facebook, Reddit, Twitch, Vimeo & Others</b>\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>Video to Audio Converter: Convert video to audio!</b>\n\n'
            '<b>And other Social Media:</b> <tg-emoji emoji-id="5305466057278923962">📥</tg-emoji>'
        ),
        "price": (
            '<tg-emoji emoji-id="5447458260200214425">💰</tg-emoji> <b>Advertising Rates</b>\n\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 12 Hours — <b>Negotiable ETB</b>\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 24 Hours — <b>500 ETB</b>\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 48 Hours — <b>700 ETB</b>\n\n'
            'Choose your plan and proceed to Payment Method <tg-emoji emoji-id="5463249828450424568">🤝</tg-emoji>'
        ),
        "order": (
            '<tg-emoji emoji-id="5197304993920616826">📢</tg-emoji> <b>To Advertise on @mame_posts Channel</b>\n\n'
            '<tg-emoji emoji-id="5305634553140912174">👇</tg-emoji> Please send your promo post below and view our rates <tg-emoji emoji-id="5305739801314501775">ℹ️</tg-emoji>'
        ),
        "payment": (
            '<tg-emoji emoji-id="5186349709169525403">💳</tg-emoji> <b>Payment Method</b>\n\n'
            '<tg-emoji emoji-id="5961054379350955385">🏦</tg-emoji> <b>Commercial Bank of Ethiopia (CBE)</b>\n<code>1000528274394</code>\n\nMohammed Seid\n\n'
            '<tg-emoji emoji-id="5960632377339285724">📱</tg-emoji> <b>TELEBIRR</b>\n<code>+251963266849</code>\n\n'
            '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Please send receipt screenshot after payment!</b>'
        ),
        "support": (
            '<tg-emoji emoji-id="5305545479814161889">💬</tg-emoji> <b>Support & Downloader Help</b>\n\n'
            '<tg-emoji emoji-id="5305655375142364109">📺</tg-emoji> <b>To Download Video/Photo:</b> Send links from Tiktok, Instagram, Facebook, Reddit, Twitch, Vimeo, SoundCloud, Threads, etc.\n\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>Video to Audio:</b> Send any video to convert it to MP3 audio.\n\n'
            '<tg-emoji emoji-id="5949327894567195412">👩‍💻</tg-emoji> You can write messages here to reach out to the Admin.'
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
        "done_msg": "✅ <b>تم! تم تعيين لغتك.</b>",
        "loading": '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> <b>جاري التحميل...</b>',
        "video_converted": '<tg-emoji emoji-id="5305534793935527938">🎵</tg-emoji> <b>الصوت المستخرج</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>تم التحويل بواسطة</b> @{bot_username} & @mame_posts',
        "video_downloaded": '🚀 <b>تم التحميل بواسطة</b> @{bot_username} & @mame_posts\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>استمتع!</b>',
        "size_limit": "⚠️ <b>حجم الملف أكبر من 50 ميغابايت!</b>",
        "fail_download": "💔 <b>تعذر تحميل الملف! يرجى التأكد من أن الرابط عام.</b>",
        "photo_download": '📸 <b>الصورة المحملة</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>تم التحميل بواسطة</b> @{bot_username}',
        "welcome": (
            'مرحباً بك <tg-emoji emoji-id="5305577086478489521">🚨</tg-emoji>\n\n'
            '<tg-emoji emoji-id="5305739801314501775">✅</tg-emoji> <b>خياراتي (يمكنك تحميل وتعديل الفيديوهات والصور والصوتيات من جميع منصات التواصل الاجتماعي):</b>\n\n'
            '<tg-emoji emoji-id="5305290882742788410">🎵</tg-emoji> | <b>Tiktok & Likee: مقاطع وصور</b>\n'
            '<tg-emoji emoji-id="5305551797711053969">📸</tg-emoji> | <b>Pinterest & Instagram: ريلز، صور وستوري</b>\n'
            '<tg-emoji emoji-id="5305777524012262308">▶️</tg-emoji> | <b>YouTube: فيديوهات وموسيقى (كامل وShorts)</b>\n'
            '<tg-emoji emoji-id="5305474827602140530">✖️</tg-emoji> | <b>Twitter (X): فيديوهات وتغريدات صوتية</b>\n'
            '<tg-emoji emoji-id="5305311717629142471">📘</tg-emoji> | <b>Facebook, Reddit, Twitch, Vimeo وغيرها</b>\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>تحويل الفيديو إلى صوت: يمكنك تحويل أي فيديو إلى ملف صوتي MP3!</b>\n\n'
            '<b>والمزيد من منصات التواصل الاجتماعي:</b> <tg-emoji emoji-id="5305466057278923962">📥</tg-emoji>'
        ),
        "price": (
            '<tg-emoji emoji-id="5447458260200214425">💰</tg-emoji> <b>أسعار الإعلانات</b>\n\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 12 ساعة — <b>حسب الاتفاق ETB</b>\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 24 ساعة — <b>500 ETB</b>\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 48 ساعة — <b>700 ETB</b>\n\n'
            'اختر خطتك ثم انتقل إلى طرق الدفع <tg-emoji emoji-id="5463249828450424568">🤝</tg-emoji>'
        ),
        "order": (
            '<tg-emoji emoji-id="5197304993920616826">📢</tg-emoji> <b>للإعلان على قناة @mame_posts</b>\n\n'
            '<tg-emoji emoji-id="5305634553140912174">👇</tg-emoji> يرجى إرسال المنشور الذي تريد الإعلان عنه أدناه لعرض الأسعار <tg-emoji emoji-id="5305739801314501775">ℹ️</tg-emoji>'
        ),
        "payment": (
            '<tg-emoji emoji-id="5186349709169525403">💳</tg-emoji> <b>طرق الدفع</b>\n\n'
            '<tg-emoji emoji-id="5961054379350955385">🏦</tg-emoji> <b>البنك التجاري الإثيوبي (CBE)</b>\n<code>1000528274394</code>\n\nMohammed Seid\n\n'
            '<tg-emoji emoji-id="5960632377339285724">📱</tg-emoji> <b>تلي بر (TELE BIRR)</b>\n<code>+251963266849</code>\n\n'
            '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>يرجى إرسال صورة إيصال الدفع بعد التحويل!</b>'
        ),
        "support": (
            '<tg-emoji emoji-id="5305545479814161889">💬</tg-emoji> <b>الدعم والمساعدة في التحميل</b>\n\n'
            '<tg-emoji emoji-id="5305655375142364109">📺</tg-emoji> <b>لتحميل الفيديوهات/الصور:</b> أرسل روابط تيك توك، إنستغرام، فيسبوك، ريديت، تويتش وغيرها مباشرة.\n\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>تحويل الفيديو إلى صوت:</b> أرسل أي فيديو لتحويله إلى ملف صوتي MP3.\n\n'
            '<tg-emoji emoji-id="5949327894567195412">👩‍💻</tg-emoji> يمكنك كتابة رسائلك هنا للتواصل مع المسؤول مباشرة.'
        )
    }
}
EXTRA_TEXT = {
    "am": {
        "msg_received": "✅ መልዕክትዎ ተቀብለናል። Admin ያነበበውን መልስ ይልክልዎታል።",
        "joined_ok": '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>አሁን ቻናሉን ተቀላቅለዋል።</b>\n\nእባክዎ የላኩትን ሊንክ ደግመው ይላኩ።',
        "tg_limit": "⚠️ <b>ቴሌግራም ቦቶች ከ 20MB በላይ የሆነ ቪዲዮ ማውረድ አይችሉም።</b>",
        "limit_reached": "⛔ <b>ዛሬ የሚፈቀደውን {limit} ማውረድ/መቀየር ጨርሰዋል።</b>\n\nነገ እንደገና ይሞክሩ (ቆጠራው በኢትዮጵያ ሰዓት እኩለ ሌሊት ይታደሳል)።",
    },
    "en": {
        "msg_received": "✅ Message received. The admin will reply if needed.",
        "joined_ok": '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>You have joined the channel.</b>\n\nPlease send your link again.',
        "tg_limit": "⚠️ <b>Telegram bots cannot download videos larger than 20MB.</b>",
        "limit_reached": "⛔ <b>You have used today's limit of {limit} downloads/conversions.</b>\n\nTry again tomorrow (it resets at midnight Ethiopia time).",
    },
    "ar": {
        "msg_received": "✅ تم استلام رسالتك. سيرد المسؤول إذا لزم الأمر.",
        "joined_ok": '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>تم الانضمام إلى القناة.</b>\n\nيرجى إعادة إرسال الرابط.',
        "tg_limit": "⚠️ <b>لا تستطيع بوتات تيليجرام تحميل فيديو أكبر من 20 ميغابايت.</b>",
        "limit_reached": "⛔ <b>لقد استنفدت الحد اليومي: {limit} تحميلات/تحويلات.</b>\n\nحاول مرة أخرى غداً (يتجدد عند منتصف الليل بتوقيت إثيوبيا).",
    },
}
for _lang, _d in EXTRA_TEXT.items():
    TRANSLATIONS[_lang].update(_d)
EXTRA_TEXT2 = {
    "am": {"btn_invite": "🎁 ጓደኛ ጋብዝ", "btn_myads": "📋 የእኔ ማስታወቂያዎች",
           "price_users": "👥 <b>አሁን {n}+ ተጠቃሚዎች</b> ቦቱን ይጠቀማሉ"},
    "en": {"btn_invite": "🎁 Invite Friends", "btn_myads": "📋 My Ads",
           "price_users": "👥 <b>{n}+ users</b> already use this bot"},
    "ar": {"btn_invite": "🎁 ادعُ أصدقاءك", "btn_myads": "📋 إعلاناتي",
           "price_users": "👥 <b>أكثر من {n} مستخدم</b> يستخدمون هذا البوت"},
}
for _lang, _d in EXTRA_TEXT2.items():
    TRANSLATIONS[_lang].update(_d)
_dl_sem = None
def get_sem():
    """Max 3 downloads at the same time (protects RAM / disk on small hosts)."""
    global _dl_sem
    if _dl_sem is None:
        _dl_sem = asyncio.Semaphore(3)
    return _dl_sem
async def take_quota(user_id):
    return await asyncio.to_thread(take_quota_sync, user_id)
async def refund_quota(user_id):
    await asyncio.to_thread(refund_quota_sync, user_id)
async def quota_line(user_id):
    if user_id == ADMIN_ID:
        return "📥 <b>Today:</b> ∞"
    used = await asyncio.to_thread(get_quota_used, user_id)
    return f"📥 <b>Today:</b> {used}/{DAILY_LIMIT}"
async def price_users_line(user_id):
    try:
        n = await asyncio.to_thread(users_col.estimated_document_count)
    except Exception:
        return ""
    n = (n // 10) * 10
    if n < 10:
        return ""
    return "\n\n" + get_trans(user_id, "price_users").format(n=n)
async def count_stat(user_id, kind, url=None):
    if user_id == ADMIN_ID:
        return
    await asyncio.to_thread(bump_stat, users_col, platform_of(url) if url else None, kind)
async def _send_with_retry(make):
    try:
        return await make()
    except RetryAfter as e:
        ra = e.retry_after
        ra = ra.total_seconds() if hasattr(ra, "total_seconds") else ra
        await asyncio.sleep(ra + 1)
        return await make()
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
        [
            btn(get_trans(user_id, "btn_invite"), callback_data="cmd_invite", style="success"),
            btn(get_trans(user_id, "btn_myads"), callback_data="cmd_myads", style="primary")
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
        BotCommand("invite", "Invite friends & win"),
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
            '<tg-emoji emoji-id="6034962180875490251">🔒</tg-emoji> '
            '<b>You must join the channel below to use the bot!</b>\n\n'
            '1️⃣ <tg-emoji emoji-id="5267442591548320083">📢</tg-emoji> <b>Click Join Channel:</b>\n'
            '2️⃣ <tg-emoji emoji-id="5305749202997911340">✅</tg-emoji> <b>Click I\'ve Joined and resend your link!</b>'
        )
        btn_join_text = "Join Channel"
        btn_joined_text = "I've Joined"
    elif lang == "ar":
        text = (
            '<tg-emoji emoji-id="6034962180875490251">🔒</tg-emoji> '
            '<b>يجب عليك الاشتراك في القناة أدناه لاستخدام البوت!</b>\n\n'
            '1️⃣ <tg-emoji emoji-id="5267442591548320083">📢</tg-emoji> <b>اضغط على انضمام للقناة:</b>\n'
            '2️⃣ <tg-emoji emoji-id="5305749202997911340">✅</tg-emoji> <b>اضغط على تم الانضمام وأعد إرسال الرابط!</b>'
        )
        btn_join_text = "انضمام للقناة"
        btn_joined_text = "تم الانضمام"
    else:
        text = (
            '<tg-emoji emoji-id="6034962180875490251">🔒</tg-emoji> '
            '<b>ቦቱን ለመጠቀም ከታች ያለውን ቻናል መቀላቀል አለብዎት!</b>\n\n'
            '1️⃣ <tg-emoji emoji-id="5267442591548320083">📢</tg-emoji> <b>Join Channel የሚለውን ይጫኑ:</b>\n'
            '2️⃣ <tg-emoji emoji-id="5305749202997911340">✅</tg-emoji> <b>I\'ve Joined የሚለውን ተጭነው የላኩትን ደግመው ይላኩ!</b>'
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
    if GROWTH:
        await GROWTH.on_start(update, context)      # must run BEFORE the user is marked as started
    await asyncio.to_thread(record_user_activity, user_id)
    setup_keyboard = ReplyKeyboardMarkup([["🏠 Menu"]], resize_keyboard=True, input_field_placeholder="Send link 🔗")
    user_lang = get_user_language(user_id)
    if not user_lang:
        await update.message.reply_text(
            "<b>Please select your language / እባክዎ ቋንቋ ይምረጡ / اختر لغتك፦</b>",
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
    await asyncio.to_thread(record_user_activity, user.id)
    total_users, user_msg_count = await asyncio.to_thread(get_user_stats, user.id)
    username_text = f"@{user.username}" if user.username else "የለውም"
    msg = (
        '<tg-emoji emoji-id="5431577498364158238">📊</tg-emoji> <b>My Status & Stats</b>\n\n'
        f'👤 <b>Username:</b> {username_text}\n'
        f'🆔 <b>ID:</b> <code>{user.id}</code>\n\n'
        f'💬 <b>Your Messages:</b> {user_msg_count}\n'
        f'👥 <b>Bot Users:</b> {total_users}\n\n'
        '🔥 <b>Engagement: Active</b>\n' + await quota_line(user.id)
    )
    await update.message.reply_text(msg, parse_mode="HTML")
async def rates_command(update, context):
    if not update.message:
        return
    user_id = update.effective_user.id
    await asyncio.to_thread(record_user_activity, user_id)
    await update.message.reply_text(get_trans(user_id, "price") + await price_users_line(user_id), parse_mode="HTML")
async def payment_command(update, context):
    if not update.message:
        return
    user_id = update.effective_user.id
    await asyncio.to_thread(record_user_activity, user_id)
    await update.message.reply_text(get_trans(user_id, "payment"), parse_mode="HTML")
async def help_command(update, context):
    if not update.message:
        return
    user_id = update.effective_user.id
    await asyncio.to_thread(record_user_activity, user_id)
    await update.message.reply_text(get_trans(user_id, "support"), parse_mode="HTML")
async def broadcast_command(update, context):
    if not update.message or update.effective_user.id != ADMIN_ID:
        return
    reply_msg = update.message.reply_to_message
    has_args = bool(context.args)
    if not reply_msg and not has_args:
        await update.message.reply_text("❌ Reply to a message or use:\n/broadcast your message")
        return
    ids = await asyncio.to_thread(get_all_user_ids)
    text_to_send = " ".join(context.args) if has_args else None
    success_count = 0
    fail_count = 0
    status_msg = await update.message.reply_text("📢 Broadcasting...")
    for chat_id in ids:
        async def _send():
            if reply_msg:
                return await reply_msg.copy(chat_id=chat_id)
            return await context.bot.send_message(chat_id=chat_id, text=text_to_send, parse_mode="HTML")
        try:
            await _send_with_retry(_send)
            success_count += 1
        except Exception:
            fail_count += 1
        await asyncio.sleep(0.05)
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
    size = getattr(video, "file_size", None)
    if size and size > 20 * 1024 * 1024:
        await update.message.reply_text(get_trans(user_id, "tg_limit"), parse_mode="HTML")
        return
    if not await take_quota(user_id):
        await update.message.reply_text(
            get_trans(user_id, "limit_reached").format(limit=DAILY_LIMIT), parse_mode="HTML")
        return
    refund_needed = True
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
        refund_needed = False
        await count_stat(user_id, "converts")
        if status_msg:
            try:
                await status_msg.delete()
            except Exception:
                pass
    except Exception as e:
        print("Video to Audio Error:", e)
        if refund_needed:
            await refund_quota(user_id)
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
SHORT_HOSTS = {"pin.it", "vm.tiktok.com", "vt.tiktok.com", "fb.watch", "t.co", "bit.ly", "tinyurl.com", "lnkd.in"}
def _needs_unshorten(url: str) -> bool:
    p = urlparse(url if "://" in url else "https://" + url)
    host = (p.hostname or "").lower()
    if host in SHORT_HOSTS:
        return True
    if host.endswith("facebook.com") and "/share/" in p.path:
        return True
    if host.endswith("reddit.com") and "/s/" in p.path:
        return True
    return False
def unshorten_url(url: str) -> str:
    try:
        resp = requests.get(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'},
            allow_redirects=True, timeout=10, stream=True,
        )
        final = resp.url
        resp.close()
        if "login" in urlparse(final).path.lower():
            return url
        return final
    except Exception:
        return url
def clean_url(raw_url: str) -> str:
    # Only resolve real short links. Resolving normal links can send
    # Instagram/Facebook to a login page and break the download.
    return unshorten_url(raw_url) if _needs_unshorten(raw_url) else raw_url
def get_video_options(url: str, output_template: str, fallback: bool = False):
    is_youtube = any(domain in url.lower() for domain in ["youtube.com", "youtu.be"])
    opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'playlist_items': '1',
        'socket_timeout': 30,
        'retries': 3,
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
    
AUDIO_EXTS = ('.mp3', '.m4a', '.aac', '.opus', '.ogg', '.wav', '.flac')
IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.webp')
MAX_UPLOAD = 50 * 1024 * 1024
def find_downloaded_file(folder: str):
    try:
        files = [f for f in os.listdir(folder) if not f.endswith(('.part', '.ytdl', '.temp'))]
    except FileNotFoundError:
        return None
    if not files:
        return None
    paths = [os.path.join(folder, f) for f in files]
    return max(paths, key=os.path.getsize)
def fetch_pinterest_image(url: str):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    res = requests.get(url, headers=headers, timeout=10)
    found = re.findall(r'https://i\.pinimg\.com/(?:originals|736x)/[^\s"\'\>]+\.(?:jpg|png|jpeg|webp)', res.text)
    return found[0] if found else None
async def handle_url_download(update: Update, context: ContextTypes.DEFAULT_TYPE, raw_url: str):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if not await take_quota(user_id):
        await update.message.reply_text(
            get_trans(user_id, "limit_reached").format(limit=DAILY_LIMIT), parse_mode="HTML")
        return
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_DOCUMENT)
    status_msg = await update.message.reply_text(
        get_trans(user_id, "loading"),
        parse_mode="HTML"
    )
    bot_username = get_bot_username(context)
    share_link = quote(f"https://t.me/{bot_username}?start=share", safe="")
    share_text = quote("Try this awesome Downloader Bot!🔥", safe="")
    share_url = f"https://t.me/share/url?url={share_link}&text={share_text}"
    reply_markup_share = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Share Bot 🚀", url=share_url)]])
    url = await asyncio.to_thread(clean_url, raw_url)
    # Direct Pinterest Image extraction
    if "pinterest.com" in url or "pin.it" in url:
        try:
            real_img_url = await asyncio.to_thread(fetch_pinterest_image, url)
            if real_img_url:
                await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_DOCUMENT)
                await update.message.reply_photo(
                    photo=real_img_url,
                    caption=get_trans(user_id, "photo_download").format(bot_username=bot_username),
                    reply_markup=reply_markup_share,
                    parse_mode="HTML"
                )
                await count_stat(user_id, "downloads", url)
                await status_msg.delete()
                return
        except Exception as pe:
            print("Pinterest Fetch Error:", pe)
    workdir = tempfile.mkdtemp(prefix=f"dl_{user_id}_")
    media_template = os.path.join(workdir, "media.%(ext)s")
    sent_any = False
    video_title = None
    ffmpeg_bin = FFMPEG_PATH if FFMPEG_PATH else "ffmpeg"
    try:
        async with get_sem():
            try:
                info = await asyncio.to_thread(download_media_func, url, media_template, False)
            except Exception as err1:
                print("Download primary failed, trying client fallback:", err1)
                info = await asyncio.to_thread(download_media_func, url, media_template, True)
        if info:
            video_title = info.get("title")
        actual_file = find_downloaded_file(workdir)
        if actual_file and os.path.exists(actual_file):
            ext = os.path.splitext(actual_file)[1].lower()
            size = os.path.getsize(actual_file)
            safe_name = re.sub(r'[\\/:*?"<>|\r\n]+', ' ', video_title or "audio").strip()[:60] or "audio"
            audio_caption = (
                '<tg-emoji emoji-id="5307705891313721642">🎧</tg-emoji> <b>Extracted Audio (MP3)</b>\n\n'
                f'<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Downloaded with</b> @{bot_username}'
            )
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_DOCUMENT)
            if ext in IMAGE_EXTS:
                photo_caption = get_trans(user_id, "photo_download").format(bot_username=bot_username)
                try:
                    with open(actual_file, 'rb') as pf:
                        await update.message.reply_photo(
                            photo=pf, caption=photo_caption,
                            reply_markup=reply_markup_share, parse_mode="HTML"
                        )
                except Exception as photo_err:
                    print("reply_photo failed, document fallback:", photo_err)
                    with open(actual_file, 'rb') as pf:
                        await update.message.reply_document(
                            document=pf, caption=photo_caption,
                            reply_markup=reply_markup_share, parse_mode="HTML"
                        )
                sent_any = True
            elif size > MAX_UPLOAD:
                await status_msg.edit_text(get_trans(user_id, "size_limit"), parse_mode="HTML")
                await refund_quota(user_id)
                return
            elif ext in AUDIO_EXTS:
                with open(actual_file, 'rb') as af:
                    await update.message.reply_audio(
                        audio=af,
                        title=(video_title or "Audio")[:64],
                        performer="🎧 Mame Posts Bot",
                        filename=f"{safe_name}{ext}",
                        caption=audio_caption,
                        reply_markup=reply_markup_share,
                        parse_mode="HTML"
                    )
                sent_any = True
            else:
                video_caption = get_trans(user_id, "video_downloaded").format(bot_username=bot_username)
                try:
                    with open(actual_file, 'rb') as vf:
                        await update.message.reply_video(
                            video=vf,
                            caption=video_caption,
                            reply_markup=reply_markup_share,
                            parse_mode="HTML",
                            supports_streaming=True
                        )
                except Exception as vid_err:
                    print("reply_video failed, document fallback:", vid_err)
                    with open(actual_file, 'rb') as doc_file:
                        await update.message.reply_document(
                            document=doc_file,
                            caption=video_caption,
                            reply_markup=reply_markup_share,
                            parse_mode="HTML"
                        )
                sent_any = True
                # Extract Audio (a failure here must not hide the video that was already sent)
                audio_output = os.path.join(workdir, "audio_extract.mp3")
                try:
                    cmd = [ffmpeg_bin, "-y", "-i", actual_file, "-vn", "-acodec", "libmp3lame", "-q:a", "2", audio_output]
                    await asyncio.to_thread(
                        subprocess.run, cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300
                    )
                    if os.path.exists(audio_output) and 0 < os.path.getsize(audio_output) <= MAX_UPLOAD:
                        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_DOCUMENT)
                        with open(audio_output, 'rb') as af:
                            await update.message.reply_audio(
                                audio=af,
                                title=(video_title or "Audio")[:64],
                                performer="🎧 Mame Posts Bot",
                                filename=f"{safe_name}.mp3",
                                caption=audio_caption,
                                reply_markup=reply_markup_share,
                                parse_mode="HTML"
                            )
                except Exception as audio_err:
                    print("Audio extraction error:", audio_err)
    except Exception as e:
        print("Media Download Execution Error:", e)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    if sent_any:
        await count_stat(user_id, "downloads", url)
        try:
            await status_msg.delete()
        except Exception:
            pass
    else:
        await refund_quota(user_id)      # nothing was delivered, give the download back
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
        await asyncio.to_thread(set_user_language, user_id, lang_code)
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
            "<b>Please select your language / እባክዎ ቋንቋ ይምረጡ / اختر لغتك፦</b>",
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
            if key_cmd == "price":
                text += await price_users_line(user_id)
            try:
                await query.edit_message_text(text=text, reply_markup=get_back_keyboard(user_id, True), parse_mode="HTML")
            except Exception:
                await query.edit_message_text(text=text, reply_markup=get_back_keyboard(user_id, False), parse_mode="HTML")
            return
    if data == "cmd_status":
        await query.answer()
        total_users, user_msg_count = await asyncio.to_thread(get_user_stats, user_id)
        username_text = f"@{user.username}" if user.username else "የለውም"
        msg = (
            '<tg-emoji emoji-id="5431577498364158238">📊</tg-emoji> <b>My Status & Stats</b>\n\n'
            f'👤 <b>Username:</b> {username_text}\n'
            f'🆔 <b>ID:</b> <code>{user_id}</code>\n\n'
            f'💬 <b>Your Messages:</b> {user_msg_count}\n'
            f'👥 <b>Bot Users:</b> {total_users}\n\n'
            '🔥 <b>Engagement: Active</b>\n' + await quota_line(user.id)
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
                    get_trans(user_id, "joined_ok"),
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
def extract_supported_url(text: str):
    cands = re.findall(r"https?://[^\s]+", text)
    if not cands:
        cands = ["https://" + c for c in re.findall(r"\b(?:[\w-]+\.)+[a-z]{2,}/[^\s]*", text, re.I)]
    for cand in cands:
        cand = cand.rstrip(".,!?)]}")
        host = (urlparse(cand).hostname or "").lower()
        for d in SUPPORTED_DOMAINS:
            if host == d or host.endswith("." + d):
                return cand
    return None
async def handle_user_messages(update, context):
    if not update.message:
        return
    user_id = update.effective_user.id
    await asyncio.to_thread(record_user_activity, user_id)
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
    target_url = extract_supported_url(text)
    if target_url:
        if not await is_joined(update, context):
            await show_force_join(update, context)
            return
        await handle_url_download(update, context, target_url)
        return
    # Forward other messages to Admin (private chats only, never the admin's own messages)
    if update.effective_chat.type != "private" or user_id == ADMIN_ID:
        return
    username = f"@{update.effective_user.username}" if update.effective_user.username else "No username"
    header_text = (
        "📩 <b>New User Message</b>\n\n"
        f"👤 <b>Name:</b> {html.escape(update.effective_user.full_name)}\n"
        f"🔗 <b>Username:</b> {html.escape(username)}\n"
        f"🆔 <b>ID:</b> <code>{user_id}</code>"
    )
    try:
        header_msg = await context.bot.send_message(chat_id=ADMIN_ID, text=header_text, parse_mode="HTML")
        forwarded_msg = await update.message.forward(chat_id=ADMIN_ID)
        await asyncio.to_thread(save_admin_map, [header_msg.message_id, forwarded_msg.message_id], user_id)
        await update.message.reply_text(get_trans(user_id, "msg_received"))
    except Exception as e:
        print("Admin forwarding error:", e)
async def admin_reply(update, context):
    if not update.message or update.effective_user.id != ADMIN_ID:
        return
    replied_msg = update.message.reply_to_message
    if not replied_msg:
        return
    target_user_id = await asyncio.to_thread(load_admin_map, replied_msg.message_id)
    if not target_user_id:
        origin = getattr(replied_msg, "forward_origin", None)
        fwd_user = getattr(origin, "sender_user", None) if origin else None
        if not fwd_user:
            fwd_user = getattr(replied_msg, "forward_from", None)
        if fwd_user:
            target_user_id = fwd_user.id
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
async def prime_user(update, context):
    """Load the user's language into the cache before other handlers run."""
    user = update.effective_user
    if user and user.id not in _lang_cache:
        await asyncio.to_thread(get_user_language, user.id)
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print("❌ ERROR:", context.error)
# ============================================================
# MAIN
# ============================================================
def main():
    global GROWTH
    if not TOKEN:
        raise RuntimeError("❌ BOT_TOKEN environment variable is missing!")
    # remove temp files left behind by a crash / restart
    for pattern in (os.path.join(tempfile.gettempdir(), "dl_*"), "input_vid_*", "output_aud_*"):
        for leftover in glob.glob(pattern):
            try:
                shutil.rmtree(leftover) if os.path.isdir(leftover) else os.remove(leftover)
            except Exception:
                pass
    keep_alive()
    application = (
        ApplicationBuilder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )
    application.add_handler(TypeHandler(Update, prime_user), group=-6)
    setup_admin(application, users_col, ADMIN_ID)
    setup_ads(application, users_col, ADMIN_ID, TRANSLATIONS, FORCE_CHANNEL)
    GROWTH = setup_growth(application, users_col, ADMIN_ID, TRANSLATIONS, FORCE_CHANNEL)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", start))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("rates", rates_command))
    application.add_handler(CommandHandler("rate", rates_command))
    application.add_handler(CommandHandler("payment", payment_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command, block=False))
    application.add_handler(CallbackQueryHandler(check_join, pattern=r"^check_join$"))
    application.add_handler(CallbackQueryHandler(button_callback, pattern=r"^(cmd_|lang_)"))
    admin_filter = filters.User(user_id=ADMIN_ID) & filters.REPLY & ~filters.COMMAND
    application.add_handler(MessageHandler(admin_filter, admin_reply))
    type_filter = (
        filters.TEXT
        | filters.VIDEO
        | filters.VIDEO_NOTE
        | filters.PHOTO
        | filters.Document.ALL
        | filters.VOICE
        | filters.AUDIO
        | filters.Sticker.ALL
    ) & ~filters.COMMAND
    # block=False: a long download no longer freezes the bot for every other user
    application.add_handler(MessageHandler(type_filter, handle_user_messages, block=False))
    application.add_error_handler(error_handler)
    print("🤖 Mame Posts Bot is running...")
    application.run_polling(drop_pending_updates=True)
if __name__ == "__main__":
    main()
