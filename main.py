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
    formatted_cookies = COOKIES_ENV.replace("\\n", "\n")
    with open("cookies.txt", "w", encoding="utf-8") as f:
        f.write(formatted_cookies)
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

TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 6753546651))

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
            "started": True,
            "lang": None
        }    

    data[uid_str]["msg_count"] = data[uid_str].get("msg_count", 0) + 1    
    data[uid_str]["started"] = True    

    save_data(data)

def set_user_language(user_id, lang_code):
    data = load_data()
    uid_str = str(user_id)
    if uid_str not in data:
        data[uid_str] = {"msg_count": 1, "started": True, "lang": lang_code}
    else:
        data[uid_str]["lang"] = lang_code
    save_data(data)

def get_user_language(user_id):
    data = load_data()
    return data.get(str(user_id), {}).get("lang", None)

def get_user_stats(user_id):
    data = load_data()
    uid_str = str(user_id)

    total_users = len(data)    
    user_msg_count = data.get(uid_str, {}).get("msg_count", 0)    

    return total_users, user_msg_count

# ==================================================
# COMPLETE MULTI-LANGUAGE TRANSLATIONS WITH FULL EMOJIS
# ==================================================

TRANSLATIONS = {
    "am": {
        "btn_add": "Add a bot to the chat",
        "btn_order": "ማስታወቂያ ለማሰራት",
        "btn_price": "Price | ዋጋ",
        "btn_payment": "Payment Method",
        "btn_status": "My Status & Stats",
        "btn_lang": "Language | ቋንቋ",
        "btn_support": "Support | ድጋፍ",
        "btn_back": "Back to Menu",
        "loading": '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> <b>Loading|ይጠብቁ...</b>',
        "download_success": '<tg-emoji emoji-id="5305762354187772738">🚀</tg-emoji> <b>Downloaded with</b> @{bot_username} & @mame_posts\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Enjoy!</b>',
        "audio_extracted": '<tg-emoji emoji-id="5307705891313721642">🎧</tg-emoji> <b>Extracted Audio (MP3)</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Downloaded with</b> @{bot_username}',
        "video_converted": '<tg-emoji emoji-id="5305534793935527938">🎵</tg-emoji> <b>ከቪዲዮ የተቀየረው (Extracted Audio)</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Converted with</b> @{bot_username} & @mame_posts',
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
            '<tg-emoji emoji-id="5961054379350955385">🏦</tg-emoji> <b>ንግድ ባንክ (CBE)</b>\n'
            '<code>1000528274394</code>\n\n'
            'Mohammed Seid\n\n'
            '<tg-emoji emoji-id="5960632377339285724">📱</tg-emoji> <b>ቴሌ ብር (TELE BIRR)</b>\n'
            '<code>+251963266849</code>\n\n'
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
        "loading": '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> <b>Loading|Please wait...</b>',
        "download_success": '<tg-emoji emoji-id="5305762354187772738">🚀</tg-emoji> <b>Downloaded with</b> @{bot_username}\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Enjoy!</b>',
        "audio_extracted": '<tg-emoji emoji-id="5307705891313721642">🎧</tg-emoji> <b>Extracted Audio (MP3)</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Downloaded with</b> @{bot_username}',
        "video_converted": '<tg-emoji emoji-id="5305534793935527938">🎵</tg-emoji> <b>Extracted Audio</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Converted with</b> @{bot_username}',
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
            '<tg-emoji emoji-id="5961054379350955385">🏦</tg-emoji> <b>Commercial Bank of Ethiopia (CBE)</b>\n'
            '<code>1000528274394</code>\n\n'
            'Mohammed Seid\n\n'
            '<tg-emoji emoji-id="5960632377339285724">📱</tg-emoji> <b>TELEBIRR</b>\n'
            '<code>+251963266849</code>\n\n'
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
        "btn_back": "العودة للالقائمة",
        "loading": '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> <b>جاري التحميل...</b>',
        "download_success": '<tg-emoji emoji-id="5305762354187772738">🚀</tg-emoji> <b>تم التحميل بواسطة</b> @{bot_username}\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>استمتع!</b>',
        "audio_extracted": '<tg-emoji emoji-id="5307705891313721642">🎧</tg-emoji> <b>الصوت المستخرج (MP3)</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>تم بواسطة</b> @{bot_username}',
        "video_converted": '<tg-emoji emoji-id="5305534793935527938">🎵</tg-emoji> <b>الصوت المستخرج</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>تم التحويل بواسطة</b> @{bot_username}',
        "size_limit": "⚠️ <b>حجم الملف أكبر من 50 ميغابايت! تجاوز حد التليجرام.</b>",
        "fail_download": "💔 <b>تعذر تحميل الملف! يرجى التأكد من أن الرابط عام.</b>",
        "photo_download": '📸 <b>الصورة المحملة</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>تم التحميل بواسطة</b> @{bot_username}',
        "welcome": (
            'مرحباً <tg-emoji emoji-id="5305577086478489521">🚨</tg-emoji>\n\n'
            '<tg-emoji emoji-id="5305739801314501775">✅</tg-emoji> <b>خياراتي (يمكنك تحميل الفيديوهات والصور والصوتيات من جميع وسائل التواصل الاجتماعي):</b>\n\n'
            '<tg-emoji emoji-id="5305290882742788410">🎵</tg-emoji> | <b>تيك توك ولايكي: فيديوهات وصور</b>\n'
            '<tg-emoji emoji-id="5305551797711053969">📸</tg-emoji> | <b>بينتريست وإنستغرام: ريلز وصور والستوري</b>\n'
            '<tg-emoji emoji-id="5305777524012262308">▶️</tg-emoji> | <b>يوتيوب: فيديوهات وموسيقى</b>\n'
            '<tg-emoji emoji-id="5305474827602140530">✖️</tg-emoji> | <b>تويتر (X): فيديوهات وصوت</b>\n'
            '<tg-emoji emoji-id="5305311717629142471">📘</tg-emoji> | <b>فيسبوك وريديت وغيرها</b>\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>محول الفيديو إلى صوت</b>\n\n'
            '<b>وغيرها من وسائل التواصل الاجتماعي:</b> <tg-emoji emoji-id="5305466057278923962">📥</tg-emoji>'
        ),
        "price": (
            '<tg-emoji emoji-id="5447458260200214425">💰</tg-emoji> <b>أسعار الإعلانات</b>\n\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 12 ساعة — <b>حسب الاتفاق</b>\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 24 ساعة — <b>500 ETB</b>\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 48 ساعة — <b>700 ETB</b>\n\n'
            'اختر الخطة وراجع طرق الدفع <tg-emoji emoji-id="5463249828450424568">🤝</tg-emoji>'
        ),
        "order": (
            '<tg-emoji emoji-id="5197304993920616826">📢</tg-emoji> <b>للإعلان على قناة @mame_posts</b>\n\n'
            '<tg-emoji emoji-id="5305634553140912174">👇</tg-emoji> يرجى إرسال الإعلان المطلوب وتحقق من الأسعار <tg-emoji emoji-id="5305739801314501775">ℹ️</tg-emoji>'
        ),
        "payment": (
            '<tg-emoji emoji-id="5186349709169525403">💳</tg-emoji> <b>طرق الدفع</b>\n\n'
            '<tg-emoji emoji-id="5961054379350955385">🏦</tg-emoji> <b>البنك التجاري الإثيوبي (CBE)</b>\n'
            '<code>1000528274394</code>\n\n'
            'Mohammed Seid\n\n'
            '<tg-emoji emoji-id="5960632377339285724">📱</tg-emoji> <b>تليبر (TELEBIRR)</b>\n'
            '<code>+251963266849</code>\n\n'
            '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>يرجى إرسال لقطة الشاشة بعد الإتمام!</b>'
        ),
        "support": (
            '<tg-emoji emoji-id="5305545479814161889">💬</tg-emoji> <b>الدعم والتعليمات</b>\n\n'
            '<tg-emoji emoji-id="5305655375142364109">📺</tg-emoji> <b>للتحميل:</b> أرسل الروابط من تيك توك، إنستغرام، يوتيوب، فيسبوك وغيرها.\n\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>تحويل الفيديو إلى صوت:</b> أرسل أي فيديو لتحويله إلى MP3.\n\n'
            '<tg-emoji emoji-id="5949327894567195412">👩‍💻</tg-emoji> يمكنك كتابة رسالتك هنا للتواصل مع الأدمن.'
        )
    },
    "ru": {
        "btn_add": "Добавить бота в чат",
        "btn_order": "Заказать рекламу",
        "btn_price": "Цены и тарифы",
        "btn_payment": "Способ оплаты",
        "btn_status": "Мой статус",
        "btn_lang": "Language | Язык",
        "btn_support": "Помощь",
        "btn_back": "Назад в меню",
        "loading": '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> <b>Загрузка... Пожалуйста, подождите</b>',
        "download_success": '<tg-emoji emoji-id="5305762354187772738">🚀</tg-emoji> <b>Скачано с помощью</b> @{bot_username}\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Приятного просмотра!</b>',
        "audio_extracted": '<tg-emoji emoji-id="5307705891313721642">🎧</tg-emoji> <b>Извлеченный звук (MP3)</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Загружено через</b> @{bot_username}',
        "video_converted": '<tg-emoji emoji-id="5305534793935527938">🎵</tg-emoji> <b>Конвертированный звук</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Сконвертировано через</b> @{bot_username}',
        "size_limit": "⚠️ <b>Файл превышает 50 МБ! Превышен лимит Telegram.</b>",
        "fail_download": "💔 <b>Не удалось скачать файл! Проверьте приватность ссылки.</b>",
        "photo_download": '📸 <b>Загруженное фото</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Скачано с помощью</b> @{bot_username}',
        "welcome": (
            'Привет <tg-emoji emoji-id="5305577086478489521">🚨</tg-emoji>\n\n'
            '<tg-emoji emoji-id="5305739801314501775">✅</tg-emoji> <b>Возможности (Вы можете скачивать видео, фото и аудио из всех социальных сетей):</b>\n\n'
            '<tg-emoji emoji-id="5305290882742788410">🎵</tg-emoji> | <b>Tiktok & Likee</b>\n'
            '<tg-emoji emoji-id="5305551797711053969">📸</tg-emoji> | <b>Pinterest & Instagram</b>\n'
            '<tg-emoji emoji-id="5305777524012262308">▶️</tg-emoji> | <b>YouTube</b>\n'
            '<tg-emoji emoji-id="5305474827602140530">✖️</tg-emoji> | <b>Twitter (X)</b>\n'
            '<tg-emoji emoji-id="5305311717629142471">📘</tg-emoji> | <b>Facebook, Reddit, Twitch</b>\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>Конвертер видео в аудио</b>\n\n'
            '<b>Другие соцсети:</b> <tg-emoji emoji-id="5305466057278923962">📥</tg-emoji>'
        ),
        "price": (
            '<tg-emoji emoji-id="5447458260200214425">💰</tg-emoji> <b>Цены на рекламу</b>\n\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 12 часов — По договоренности\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 24 часа — <b>500 ETB</b>\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 48 часов — <b>700 ETB</b>\n\n'
            'Выберите план и перейдите к способу оплаты <tg-emoji emoji-id="5463249828450424568">🤝</tg-emoji>'
        ),
        "order": (
            '<tg-emoji emoji-id="5197304993920616826">📢</tg-emoji> <b>Реклама на канале @mame_posts</b>\n\n'
            '<tg-emoji emoji-id="5305634553140912174">👇</tg-emoji> Отправьте рекламный пост ниже <tg-emoji emoji-id="5305739801314501775">ℹ️</tg-emoji>'
        ),
        "payment": (
            '<tg-emoji emoji-id="5186349709169525403">💳</tg-emoji> <b>Способ оплаты</b>\n\n'
            '<tg-emoji emoji-id="5961054379350955385">🏦</tg-emoji> <b>Коммерческий банк Эфиопии (CBE)</b>\n'
            '<code>1000528274394</code>\n\n'
            'Mohammed Seid\n\n'
            '<tg-emoji emoji-id="5960632377339285724">📱</tg-emoji> <b>TELEBIRR</b>\n'
            '<code>+251963266849</code>\n\n'
            '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Отправьте скриншот чека после оплаты!</b>'
        ),
        "support": (
            '<tg-emoji emoji-id="5305545479814161889">💬</tg-emoji> <b>Поддержка</b>\n\n'
            '<tg-emoji emoji-id="5305655375142364109">📺</tg-emoji> <b>Скачивание:</b> Отправляйте ссылки на TikTok, Instagram, YouTube, Facebook и др.\n\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>Видео в аудио:</b> Отправьте любое видео для конвертации в MP3.\n\n'
            '<tg-emoji emoji-id="5949327894567195412">👩‍💻</tg-emoji> Вы можете написать сюда для связи с админом.'
        )
    },
    "fr": {
        "btn_add": "Ajouter le bot au groupe",
        "btn_order": "Publicité",
        "btn_price": "Tarifs",
        "btn_payment": "Mode de paiement",
        "btn_status": "Mon statut",
        "btn_lang": "Language | Langue",
        "btn_support": "Aide",
        "btn_back": "Retour au menu",
        "loading": '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> <b>Chargement... Patientez</b>',
        "download_success": '<tg-emoji emoji-id="5305762354187772738">🚀</tg-emoji> <b>Téléchargé avec</b> @{bot_username}\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Profitez-en!</b>',
        "audio_extracted": '<tg-emoji emoji-id="5307705891313721642">🎧</tg-emoji> <b>Audio extrait (MP3)</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Téléchargé avec</b> @{bot_username}',
        "video_converted": '<tg-emoji emoji-id="5305534793935527938">🎵</tg-emoji> <b>Audio converti</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Converti avec</b> @{bot_username}',
        "size_limit": "⚠️ <b>Le fichier dépasse 50 Mo! Limite Telegram.</b>",
        "fail_download": "💔 <b>Échec du téléchargement! Vérifiez le lien.</b>",
        "photo_download": '📸 <b>Photo téléchargée</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Téléchargée avec</b> @{bot_username}',
        "welcome": (
            'Bonjour <tg-emoji emoji-id="5305577086478489521">🚨</tg-emoji>\n\n'
            '<tg-emoji emoji-id="5305739801314501775">✅</tg-emoji> <b>Options (Téléchargez vidéos, photos et audios):</b>\n\n'
            '<tg-emoji emoji-id="5305290882742788410">🎵</tg-emoji> | <b>Tiktok & Likee</b>\n'
            '<tg-emoji emoji-id="5305551797711053969">📸</tg-emoji> | <b>Pinterest & Instagram</b>\n'
            '<tg-emoji emoji-id="5305777524012262308">▶️</tg-emoji> | <b>YouTube</b>\n'
            '<tg-emoji emoji-id="5305474827602140530">✖️</tg-emoji> | <b>Twitter (X)</b>\n'
            '<tg-emoji emoji-id="5305311717629142471">📘</tg-emoji> | <b>Facebook, Reddit, Twitch</b>\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>Convertisseur Vidéo en Audio</b>\n\n'
            '<b>Autres:</b> <tg-emoji emoji-id="5305466057278923962">📥</tg-emoji>'
        ),
        "price": (
            '<tg-emoji emoji-id="5447458260200214425">💰</tg-emoji> <b>Tarifs publicitaires</b>\n\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 12h — Négociable\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 24h — <b>500 ETB</b>\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 48h — <b>700 ETB</b>\n\n'
            'Choisissez votre plan <tg-emoji emoji-id="5463249828450424568">🤝</tg-emoji>'
        ),
        "order": (
            '<tg-emoji emoji-id="5197304993920616826">📢</tg-emoji> <b>Publicité sur @mame_posts</b>\n\n'
            '<tg-emoji emoji-id="5305634553140912174">👇</tg-emoji> Envoyez votre publication <tg-emoji emoji-id="5305739801314501775">ℹ️</tg-emoji>'
        ),
        "payment": (
            '<tg-emoji emoji-id="5186349709169525403">💳</tg-emoji> <b>Mode de paiement</b>\n\n'
            '<tg-emoji emoji-id="5961054379350955385">🏦</tg-emoji> <b>CBE</b>\n'
            '<code>1000528274394</code>\n\n'
            'Mohammed Seid\n\n'
            '<tg-emoji emoji-id="5960632377339285724">📱</tg-emoji> <b>TELEBIRR</b>\n'
            '<code>+251963266849</code>\n\n'
            '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Envoyez la capture d\'écran!</b>'
        ),
        "support": (
            '<tg-emoji emoji-id="5305545479814161889">💬</tg-emoji> <b>Support</b>\n\n'
            '<tg-emoji emoji-id="5305655375142364109">📺</tg-emoji> <b>Téléchargement:</b> Envoyez des liens.\n\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>Vidéo en audio:</b> Envoyez une vidéo.\n\n'
            '<tg-emoji emoji-id="5949327894567195412">👩‍💻</tg-emoji> Écrivez à l\'admin.'
        )
    },
    "es": {
        "btn_add": "Añadir bot al chat",
        "btn_order": "Publicidad",
        "btn_price": "Precios",
        "btn_payment": "Método de pago",
        "btn_status": "Mi estado",
        "btn_lang": "Language | Idioma",
        "btn_support": "Soporte",
        "btn_back": "Volver al menú",
        "loading": '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> <b>Cargando... Espere</b>',
        "download_success": '<tg-emoji emoji-id="5305762354187772738">🚀</tg-emoji> <b>Descargado con</b> @{bot_username}\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>¡Disfrútalo!</b>',
        "audio_extracted": '<tg-emoji emoji-id="5307705891313721642">🎧</tg-emoji> <b>Audio extraído (MP3)</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Descargado con</b> @{bot_username}',
        "video_converted": '<tg-emoji emoji-id="5305534793935527938">🎵</tg-emoji> <b>Audio convertido</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Convertido con</b> @{bot_username}',
        "size_limit": "⚠️ <b>¡El archivo supera los 50MB!</b>",
        "fail_download": "💔 <b>¡Error al descargar! Verifique el enlace.</b>",
        "photo_download": '📸 <b>Foto descargada</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Descargada con</b> @{bot_username}',
        "welcome": (
            'Hola <tg-emoji emoji-id="5305577086478489521">🚨</tg-emoji>\n\n'
            '<tg-emoji emoji-id="5305739801314501775">✅</tg-emoji> <b>Opciones (Descarga videos, fotos y audios):</b>\n\n'
            '<tg-emoji emoji-id="5305290882742788410">🎵</tg-emoji> | <b>Tiktok & Likee</b>\n'
            '<tg-emoji emoji-id="5305551797711053969">📸</tg-emoji> | <b>Pinterest & Instagram</b>\n'
            '<tg-emoji emoji-id="5305777524012262308">▶️</tg-emoji> | <b>YouTube</b>\n'
            '<tg-emoji emoji-id="5305474827602140530">✖️</tg-emoji> | <b>Twitter (X)</b>\n'
            '<tg-emoji emoji-id="5305311717629142471">📘</tg-emoji> | <b>Facebook, Reddit, Twitch</b>\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>Convertidor de Video a Audio</b>\n\n'
            '<b>Otros:</b> <tg-emoji emoji-id="5305466057278923962">📥</tg-emoji>'
        ),
        "price": (
            '<tg-emoji emoji-id="5447458260200214425">💰</tg-emoji> <b>Tarifas de publicidad</b>\n\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 12 Horas — Negociable\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 24 Horas — <b>500 ETB</b>\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 48 Horas — <b>700 ETB</b>\n\n'
            'Elija su plan <tg-emoji emoji-id="5463249828450424568">🤝</tg-emoji>'
        ),
        "order": (
            '<tg-emoji emoji-id="5197304993920616826">📢</tg-emoji> <b>Publicidad en @mame_posts</b>\n\n'
            '<tg-emoji emoji-id="5305634553140912174">👇</tg-emoji> Envíe su publicación <tg-emoji emoji-id="5305739801314501775">ℹ️</tg-emoji>'
        ),
        "payment": (
            '<tg-emoji emoji-id="5186349709169525403">💳</tg-emoji> <b>Método de pago</b>\n\n'
            '<tg-emoji emoji-id="5961054379350955385">🏦</tg-emoji> <b>CBE</b>\n'
            '<code>1000528274394</code>\n\n'
            'Mohammed Seid\n\n'
            '<tg-emoji emoji-id="5960632377339285724">📱</tg-emoji> <b>TELEBIRR</b>\n'
            '<code>+251963266849</code>\n\n'
            '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>¡Envíe la captura!</b>'
        ),
        "support": (
            '<tg-emoji emoji-id="5305545479814161889">💬</tg-emoji> <b>Soporte</b>\n\n'
            '<tg-emoji emoji-id="5305655375142364109">📺</tg-emoji> <b>Descarga:</b> Envíe enlaces.\n\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>Video a audio:</b> Envíe un video.\n\n'
            '<tg-emoji emoji-id="5949327894567195412">👩‍💻</tg-emoji> Escriba al admin.'
        )
    },
    "fa": {
        "btn_add": "افزودن ربات به گروه",
        "btn_order": "سفارش تبلیغات",
        "btn_price": "قیمت‌ها",
        "btn_payment": "روش پرداخت",
        "btn_status": "وضعیت من",
        "btn_lang": "Language | زبان",
        "btn_support": "پشتیبانی",
        "btn_back": "بازگشت به منو",
        "loading": '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> <b>در حال بارگذاری...</b>',
        "download_success": '<tg-emoji emoji-id="5305762354187772738">🚀</tg-emoji> <b>دانلود شده توسط</b> @{bot_username}\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>لذت ببرید!</b>',
        "audio_extracted": '<tg-emoji emoji-id="5307705891313721642">🎧</tg-emoji> <b>صوت استخراج شده (MP3)</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>دانلود شده توسط</b> @{bot_username}',
        "video_converted": '<tg-emoji emoji-id="5305534793935527938">🎵</tg-emoji> <b>صوت تبدیل شده</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>تبدیل شده توسط</b> @{bot_username}',
        "size_limit": "⚠️ <b>حجم فایل بیش از ۵۰ مگابایت است!</b>",
        "fail_download": "💔 <b>دانلود ناموفق!</b>",
        "photo_download": '📸 <b>تصویر دانلود شده</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>دانلود شده توسط</b> @{bot_username}',
        "welcome": (
            'سلام <tg-emoji emoji-id="5305577086478489521">🚨</tg-emoji>\n\n'
            '<tg-emoji emoji-id="5305739801314501775">✅</tg-emoji> <b>گزینه‌ها (دانلود ویدیو، عکس و صوت):</b>\n\n'
            '<tg-emoji emoji-id="5305290882742788410">🎵</tg-emoji> | <b>تیک تاک و لایکی</b>\n'
            '<tg-emoji emoji-id="5305551797711053969">📸</tg-emoji> | <b>پینترست و اینستاگرام</b>\n'
            '<tg-emoji emoji-id="5305777524012262308">▶️</tg-emoji> | <b>یوتیوب</b>\n'
            '<tg-emoji emoji-id="5305474827602140530">✖️</tg-emoji> | <b>توییتر (X)</b>\n'
            '<tg-emoji emoji-id="5305311717629142471">📘</tg-emoji> | <b>فیسبوک، ردیت، توییچ</b>\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>مبدل ویدیو به صوت</b>\n\n'
            '<b>سایر:</b> <tg-emoji emoji-id="5305466057278923962">📥</tg-emoji>'
        ),
        "price": (
            '<tg-emoji emoji-id="5447458260200214425">💰</tg-emoji> <b>تعرفه‌های تبلیغات</b>\n\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> ۱۱۲ ساعت — توافقی\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> ۲۴ ساعت — <b>500 ETB</b>\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> ۴۸ ساعت — <b>700 ETB</b>\n\n'
            'طرح خود را انتخاب کنید <tg-emoji emoji-id="5463249828450424568">🤝</tg-emoji>'
        ),
        "order": (
            '<tg-emoji emoji-id="5197304993920616826">📢</tg-emoji> <b>تبلیغات در کانال @mame_posts</b>\n\n'
            '<tg-emoji emoji-id="5305634553140912174">👇</tg-emoji> پست خود را ارسال کنید <tg-emoji emoji-id="5305739801314501775">ℹ️</tg-emoji>'
        ),
        "payment": (
            '<tg-emoji emoji-id="5186349709169525403">💳</tg-emoji> <b>روش پرداخت</b>\n\n'
            '<tg-emoji emoji-id="5961054379350955385">🏦</tg-emoji> <b>CBE</b>\n'
            '<code>1000528274394</code>\n\n'
            'Mohammed Seid\n\n'
            '<tg-emoji emoji-id="5960632377339285724">📱</tg-emoji> <b>TELEBIRR</b>\n'
            '<code>+251963266849</code>\n\n'
            '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>رسید را ارسال کنید!</b>'
        ),
        "support": (
            '<tg-emoji emoji-id="5305545479814161889">💬</tg-emoji> <b>پشتیبانی</b>\n\n'
            '<tg-emoji emoji-id="5305655375142364109">📺</tg-emoji> <b>دانلود:</b> ارسال لینک.\n\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>ویدیو به صوت:</b> ارسال ویدیو.\n\n'
            '<tg-emoji emoji-id="5949327894567195412">👩‍💻</tg-emoji> به ادمین پیام دهید.'
        )
    },
    "hi": {
        "btn_add": "चैट में बोट जोड़ें",
        "btn_order": "विज्ञापन दें",
        "btn_price": "कीमत और दरें",
        "btn_payment": "भुगतान का तरीका",
        "btn_status": "मेरा स्टेटस",
        "btn_lang": "Language | भाषा",
        "btn_support": "सहायता",
        "btn_back": "मेनू पर वापस",
        "loading": '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> <b>लोड हो रहा है... प्रतीक्षा करें</b>',
        "download_success": '<tg-emoji emoji-id="5305762354187772738">🚀</tg-emoji> <b>डाउनलोड किया गया:</b> @{bot_username}\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>आनंद लें!</b>',
        "audio_extracted": '<tg-emoji emoji-id="5307705891313721642">🎧</tg-emoji> <b>ऑडियो निकाला गया (MP3)</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>डाउनलोड किया गया:</b> @{bot_username}',
        "video_converted": '<tg-emoji emoji-id="5305534793935527938">🎵</tg-emoji> <b>कन्वर्ट किया गया ऑडियो</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>कन्वर्ट किया गया:</b> @{bot_username}',
        "size_limit": "⚠️ <b>फ़ाइल 50MB से बड़ी है!</b>",
        "fail_download": "💔 <b>डाउनलोड करने में विफल!</b>",
        "photo_download": '📸 <b>डाउनलोड फोटो</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>डाउनलोड किया गया:</b> @{bot_username}',
        "welcome": (
            'नमस्ते <tg-emoji emoji-id="5305577086478489521">🚨</tg-emoji>\n\n'
            '<tg-emoji emoji-id="5305739801314501775">✅</tg-emoji> <b>विकल्प (वीडियो, फोटो और ऑडियो डाउनलोड करें):</b>\n\n'
            '<tg-emoji emoji-id="5305290882742788410">🎵</tg-emoji> | <b>Tiktok & Likee</b>\n'
            '<tg-emoji emoji-id="5305551797711053969">📸</tg-emoji> | <b>Pinterest & Instagram</b>\n'
            '<tg-emoji emoji-id="5305777524012262308">▶️</tg-emoji> | <b>YouTube</b>\n'
            '<tg-emoji emoji-id="5305474827602140530">✖️</tg-emoji> | <b>Twitter (X)</b>\n'
            '<tg-emoji emoji-id="5305311717629142471">📘</tg-emoji> | <b>Facebook, Reddit, Twitch</b>\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>वीडियो से ऑडियो कनवर्टर</b>\n\n'
            '<b>अन्य:</b> <tg-emoji emoji-id="5305466057278923962">📥</tg-emoji>'
        ),
        "price": (
            '<tg-emoji emoji-id="5447458260200214425">💰</tg-emoji> <b>विज्ञापन दरें</b>\n\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 12 घंटे — बातचीत योग्य\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 24 घंटे — <b>500 ETB</b>\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 48 घंटे — <b>700 ETB</b>\n\n'
            'अपनी योजना चुनें <tg-emoji emoji-id="5463249828450424568">🤝</tg-emoji>'
        ),
        "order": (
            '<tg-emoji emoji-id="5197304993920616826">📢</tg-emoji> <b>@mame_posts पर विज्ञापन दें</b>\n\n'
            '<tg-emoji emoji-id="5305634553140912174">👇</tg-emoji> अपनी पोस्ट भेजें <tg-emoji emoji-id="5305739801314501775">ℹ️</tg-emoji>'
        ),
        "payment": (
            '<tg-emoji emoji-id="5186349709169525403">💳</tg-emoji> <b>भुगतान का तरीका</b>\n\n'
            '<tg-emoji emoji-id="5961054379350955385">🏦</tg-emoji> <b>CBE</b>\n'
            '<code>1000528274394</code>\n\n'
            'Mohammed Seid\n\n'
            '<tg-emoji emoji-id="5960632377339285724">📱</tg-emoji> <b>TELEBIRR</b>\n'
            '<code>+251963266849</code>\n\n'
            '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>रसीद भेजें!</b>'
        ),
        "support": (
            '<tg-emoji emoji-id="5305545479814161889">💬</tg-emoji> <b>सहायता</b>\n\n'
            '<tg-emoji emoji-id="5305655375142364109">📺</tg-emoji> <b>डाउनलोड:</b> लिंक भेजें።\n\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>वीडियो से ऑडियो:</b> वीडियो भेजें።\n\n'
            '<tg-emoji emoji-id="5949327894567195412">👩‍💻</tg-emoji> एडमिन को लिखें।'
        )
    },
    "uz": {
        "btn_add": "Botni guruhga qo'shish",
        "btn_order": "Reklama berish",
        "btn_price": "Narxlar",
        "btn_payment": "To'lov usuli",
        "btn_status": "Mening statusim",
        "btn_lang": "Language | Til",
        "btn_support": "Yordam",
        "btn_back": "Menyuga qaytish",
        "loading": '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> <b>Yuklanmoqda... Kuting</b>',
        "download_success": '<tg-emoji emoji-id="5305762354187772738">🚀</tg-emoji> <b>Yuklab olindi:</b> @{bot_username}\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Yoqimli tomosha!</b>',
        "audio_extracted": '<tg-emoji emoji-id="5307705891313721642">🎧</tg-emoji> <b>Olingan audio (MP3)</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Yuklab olindi:</b> @{bot_username}',
        "video_converted": '<tg-emoji emoji-id="5305534793935527938">🎵</tg-emoji> <b>Konvert qilingan audio</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Konvert qilindi:</b> @{bot_username}',
        "size_limit": "⚠️ <b>Fayl hajmi 50MB dan katta!</b>",
        "fail_download": "💔 <b>Yuklab bo'lmadi!</b>",
        "photo_download": '📸 <b>Yuklab olingan rasm</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Yuklab olindi:</b> @{bot_username}',
        "welcome": (
            'Salom <tg-emoji emoji-id="5305577086478489521">🚨</tg-emoji>\n\n'
            '<tg-emoji emoji-id="5305739801314501775">✅</tg-emoji> <b>Imkoniyatlar (Video, rasm va audiolar):</b>\n\n'
            '<tg-emoji emoji-id="5305290882742788410">🎵</tg-emoji> | <b>Tiktok & Likee</b>\n'
            '<tg-emoji emoji-id="5305551797711053969">📸</tg-emoji> | <b>Pinterest & Instagram</b>\n'
            '<tg-emoji emoji-id="5305777524012262308">▶️</tg-emoji> | <b>YouTube</b>\n'
            '<tg-emoji emoji-id="5305474827602140530">✖️</tg-emoji> | <b>Twitter (X)</b>\n'
            '<tg-emoji emoji-id="5305311717629142471">📘</tg-emoji> | <b>Facebook, Reddit, Twitch</b>\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>Video dan Audio konvertori</b>\n\n'
            '<b>Boshqalar:</b> <tg-emoji emoji-id="5305466057278923962">📥</tg-emoji>'
        ),
        "price": (
            '<tg-emoji emoji-id="5447458260200214425">💰</tg-emoji> <b>Reklama narxlari</b>\n\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 12 soat — Kelishuv bo\'yicha\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 24 soat — <b>500 ETB</b>\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 48 soat — <b>700 ETB</b>\n\n'
            'Rejani tanlang <tg-emoji emoji-id="5463249828450424568">🤝</tg-emoji>'
        ),
        "order": (
            '<tg-emoji emoji-id="5197304993920616826">📢</tg-emoji> <b>@mame_posts kanalida reklama</b>\n\n'
            '<tg-emoji emoji-id="5305634553140912174">👇</tg-emoji> Postingizni yuboring <tg-emoji emoji-id="5305739801314501775">ℹ️</tg-emoji>'
        ),
        "payment": (
            '<tg-emoji emoji-id="5186349709169525403">💳</tg-emoji> <b>To\'lov usuli</b>\n\n'
            '<tg-emoji emoji-id="5961054379350955385">🏦</tg-emoji> <b>CBE</b>\n'
            '<code>1000528274394</code>\n\n'
            'Mohammed Seid\n\n'
            '<tg-emoji emoji-id="5960632377339285724">📱</tg-emoji> <b>TELEBIRR</b>\n'
            '<code>+251963266849</code>\n\n'
            '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Chekni yuboring!</b>'
        ),
        "support": (
            '<tg-emoji emoji-id="5305545479814161889">💬</tg-emoji> <b>Yordam</b>\n\n'
            '<tg-emoji emoji-id="5305655375142364109">📺</tg-emoji> <b>Yuklab olish:</b> Havola yuboring.\n\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>Video dan audio:</b> Video yuboring.\n\n'
            '<tg-emoji emoji-id="5949327894567195412">👩‍💻</tg-emoji> Adminga yozing.'
        )
    },
    "pt": {
        "btn_add": "Adicionar bot ao grupo",
        "btn_order": "Anunciar",
        "btn_price": "Preços",
        "btn_payment": "Método de pagamento",
        "btn_status": "Meu status",
        "btn_lang": "Language | Idioma",
        "btn_support": "Suporte",
        "btn_back": "Voltar ao menu",
        "loading": '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> <b>Carregando... Aguarde</b>',
        "download_success": '<tg-emoji emoji-id="5305762354187772738">🚀</tg-emoji> <b>Baixado com</b> @{bot_username}\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Aproveite!</b>',
        "audio_extracted": '<tg-emoji emoji-id="5307705891313721642">🎧</tg-emoji> <b>Áudio extraído (MP3)</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Baixado com</b> @{bot_username}',
        "video_converted": '<tg-emoji emoji-id="5305534793935527938">🎵</tg-emoji> <b>Áudio convertido</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Convertido com</b> @{bot_username}',
        "size_limit": "⚠️ <b>O arquivo excede 50MB!</b>",
        "fail_download": "💔 <b>Falha ao baixar!</b>",
        "photo_download": '📸 <b>Foto Baixada</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Baixada com</b> @{bot_username}',
        "welcome": (
            'Olá <tg-emoji emoji-id="5305577086478489521">🚨</tg-emoji>\n\n'
            '<tg-emoji emoji-id="5305739801314501775">✅</tg-emoji> <b>Opções (Baixe vídeos, fotos e áudios):</b>\n\n'
            '<tg-emoji emoji-id="5305290882742788410">🎵</tg-emoji> | <b>Tiktok & Likee</b>\n'
            '<tg-emoji emoji-id="5305551797711053969">📸</tg-emoji> | <b>Pinterest & Instagram</b>\n'
            '<tg-emoji emoji-id="5305777524012262308">▶️</tg-emoji> | <b>YouTube</b>\n'
            '<tg-emoji emoji-id="5305474827602140530">✖️</tg-emoji> | <b>Twitter (X)</b>\n'
            '<tg-emoji emoji-id="5305311717629142471">📘</tg-emoji> | <b>Facebook, Reddit, Twitch</b>\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>Conversor de Vídeo para Áudio</b>\n\n'
            '<b>Outros:</b> <tg-emoji emoji-id="5305466057278923962">📥</tg-emoji>'
        ),
        "price": (
            '<tg-emoji emoji-id="5447458260200214425">💰</tg-emoji> <b>Preços de publicidade</b>\n\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 12 Horas — Negociável\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 24 Horas — <b>500 ETB</b>\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 48 Horas — <b>700 ETB</b>\n\n'
            'Escolha seu plano <tg-emoji emoji-id="5463249828450424568">🤝</tg-emoji>'
        ),
        "order": (
            '<tg-emoji emoji-id="5197304993920616826">📢</tg-emoji> <b>Anunciar no @mame_posts</b>\n\n'
            '<tg-emoji emoji-id="5305634553140912174">👇</tg-emoji> Envie sua publicação <tg-emoji emoji-id="5305739801314501775">ℹ️</tg-emoji>'
        ),
        "payment": (
            '<tg-emoji emoji-id="5186349709169525403">💳</tg-emoji> <b>Método de pagamento</b>\n\n'
            '<tg-emoji emoji-id="5961054379350955385">🏦</tg-emoji> <b>CBE</b>\n'
            '<code>1000528274394</code>\n\n'
            'Mohammed Seid\n\n'
            '<tg-emoji emoji-id="5960632377339285724">📱</tg-emoji> <b>TELEBIRR</b>\n'
            '<code>+251963266849</code>\n\n'
            '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Envie o comprovante!</b>'
        ),
        "support": (
            '<tg-emoji emoji-id="5305545479814161889">💬</tg-emoji> <b>Suporte</b>\n\n'
            '<tg-emoji emoji-id="5305655375142364109">📺</tg-emoji> <b>Download:</b> Envie links.\n\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>Vídeo para áudio:</b> Envie um vídeo.\n\n'
            '<tg-emoji emoji-id="5949327894567195412">👩‍💻</tg-emoji> Escreva para o admin.'
        )
    },
    "zh": {
        "btn_add": "添加机器人到群组",
        "btn_order": "刊登广告",
        "btn_price": "价格与费率",
        "btn_payment": "付款方式",
        "btn_status": "我的状态",
        "btn_lang": "Language | 语言",
        "btn_support": "帮助与支持",
        "btn_back": "返回菜单",
        "loading": '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> <b>加载中... 请稍候</b>',
        "download_success": '<tg-emoji emoji-id="5305762354187772738">🚀</tg-emoji> <b>已通过</b> @{bot_username} <b>下载</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>请享用！</b>',
        "audio_extracted": '<tg-emoji emoji-id="5307705891313721642">🎧</tg-emoji> <b>提取的音频 (MP3)</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>下载自</b> @{bot_username}',
        "video_converted": '<tg-emoji emoji-id="5305534793935527938">🎵</tg-emoji> <b>转换后的音频</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>转换自</b> @{bot_username}',
        "size_limit": "⚠️ <b>文件大于 50MB！</b>",
        "fail_download": "💔 <b>无法下载文件！</b>",
        "photo_download": '📸 <b>已下载照片</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>下载自</b> @{bot_username}',
        "welcome": (
            '你好 <tg-emoji emoji-id="5305577086478489521">🚨</tg-emoji>\n\n'
            '<tg-emoji emoji-id="5305739801314501775">✅</tg-emoji> <b>选项（下载视频、照片和音频）：</b>\n\n'
            '<tg-emoji emoji-id="5305290882742788410">🎵</tg-emoji> | <b>Tiktok & Likee</b>\n'
            '<tg-emoji emoji-id="5305551797711053969">📸</tg-emoji> | <b>Pinterest & Instagram</b>\n'
            '<tg-emoji emoji-id="5305777524012262308">▶️</tg-emoji> | <b>YouTube</b>\n'
            '<tg-emoji emoji-id="5305474827602140530">✖️</tg-emoji> | <b>Twitter (X)</b>\n'
            '<tg-emoji emoji-id="5305311717629142471">📘</tg-emoji> | <b>Facebook, Reddit, Twitch</b>\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>视频转音频转换器</b>\n\n'
            '<b>其他：</b> <tg-emoji emoji-id="5305466057278923962">📥</tg-emoji>'
        ),
        "price": (
            '<tg-emoji emoji-id="5447458260200214425">💰</tg-emoji> <b>广告价格</b>\n\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 12小时 — 可议价\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 24小时 — <b>500 ETB</b>\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 48小时 — <b>700 ETB</b>\n\n'
            '选择您的方案 <tg-emoji emoji-id="5463249828450424568">🤝</tg-emoji>'
        ),
        "order": (
            '<tg-emoji emoji-id="5197304993920616826">📢</tg-emoji> <b>在 @mame_posts 投放广告</b>\n\n'
            '<tg-emoji emoji-id="5305634553140912174">👇</tg-emoji> 请在下方发送您的文案 <tg-emoji emoji-id="5305739801314501775">ℹ️</tg-emoji>'
        ),
        "payment": (
            '<tg-emoji emoji-id="5186349709169525403">💳</tg-emoji> <b>付款方式</b>\n\n'
            '<tg-emoji emoji-id="5961054379350955385">🏦</tg-emoji> <b>CBE</b>\n'
            '<code>1000528274394</code>\n\n'
            'Mohammed Seid\n\n'
            '<tg-emoji emoji-id="5960632377339285724">📱</tg-emoji> <b>TELEBIRR</b>\n'
            '<code>+251963266849</code>\n\n'
            '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>请发送截图！</b>'
        ),
        "support": (
            '<tg-emoji emoji-id="5305545479814161889">💬</tg-emoji> <b>支持</b>\n\n'
            '<tg-emoji emoji-id="5305655375142364109">📺</tg-emoji> <b>下载：</b> 发送链接。\n\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>视频转音频：</b> 发送视频。\n\n'
            '<tg-emoji emoji-id="5949327894567195412">👩‍💻</tg-emoji> 给管理员发消息。'
        )
    },
    "bn": {
        "btn_add": "বোট চ্যাটে যুক্ত করুন",
        "btn_order": "বিজ্ঞাপন দিন",
        "btn_price": "মূল্য এবং হার",
        "btn_payment": "পেমেন্ট মাধ্যম",
        "btn_status": "আমার স্ট্যাটাস",
        "btn_lang": "Language | ভাষা",
        "btn_support": "সহায়তা",
        "btn_back": "মেনুতে ফিরে যান",
        "loading": '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> <b>লোড হচ্ছে... অপেক্ষা করুন</b>',
        "download_success": '<tg-emoji emoji-id="5305762354187772738">🚀</tg-emoji> <b>ডাউনলোড করেছেন:</b> @{bot_username}\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>উপভোগ করুন!</b>',
        "audio_extracted": '<tg-emoji emoji-id="5307705891313721642">🎧</tg-emoji> <b>অডিও নিষ্কাশিত (MP3)</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>ডাউনলোড করেছেন:</b> @{bot_username}',
        "video_converted": '<tg-emoji emoji-id="5305534793935527938">🎵</tg-emoji> <b>রূপান্তরিত অডিও</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>রূপান্তর করেছেন:</b> @{bot_username}',
        "size_limit": "⚠️ <b>ফাইলটি ৫০ এমবির চেয়ে বড়!</b>",
        "fail_download": "💔 <b>ডাউনলোড ব্যর্থ হয়েছে!</b>",
        "photo_download": '📸 <b>ডাউনলোড ছবি</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>ডাউনলোড করেছেন:</b> @{bot_username}',
        "welcome": (
            'হ্যালো <tg-emoji emoji-id="5305577086478489521">🚨</tg-emoji>\n\n'
            '<tg-emoji emoji-id="5305739801314501775">✅</tg-emoji> <b>বিকল্প (ভিডিও, ছবি এবং অডিও ডাউনলোড):</b>\n\n'
            '<tg-emoji emoji-id="5305290882742788410">🎵</tg-emoji> | <b>Tiktok & Likee</b>\n'
            '<tg-emoji emoji-id="5305551797711053969">📸</tg-emoji> | <b>Pinterest & Instagram</b>\n'
            '<tg-emoji emoji-id="5305777524012262308">▶️</tg-emoji> | <b>YouTube</b>\n'
            '<tg-emoji emoji-id="5305474827602140530">✖️</tg-emoji> | <b>Twitter (X)</b>\n'
            '<tg-emoji emoji-id="5305311717629142471">📘</tg-emoji> | <b>Facebook, Reddit, Twitch</b>\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>ভিডিও থেকে অডিও কনভার্টার</b>\n\n'
            '<b>অন্যান্য:</b> <tg-emoji emoji-id="5305466057278923962">📥</tg-emoji>'
        ),
        "price": (
            '<tg-emoji emoji-id="5447458260200214425">💰</tg-emoji> <b>বিজ্ঞাপনের মূল্য</b>\n\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> ১২ ঘণ্টা — আলোচনা সাপেক্ষে\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> ২৪ ঘণ্টা — <b>500 ETB</b>\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> ৪৮ ঘণ্টা — <b>700 ETB</b>\n\n'
            'আপনার পরিকল্পনা চয়ন করুন <tg-emoji emoji-id="5463249828450424568">🤝</tg-emoji>'
        ),
        "order": (
            '<tg-emoji emoji-id="5197304993920616826">📢</tg-emoji> <b>@mame_posts এ বিজ্ঞাপন দিন</b>\n\n'
            '<tg-emoji emoji-id="5305634553140912174">👇</tg-emoji> আপনার পোস্ট পাঠান <tg-emoji emoji-id="5305739801314501775">ℹ️</tg-emoji>'
        ),
        "payment": (
            '<tg-emoji emoji-id="5186349709169525403">💳</tg-emoji> <b>পেমেন্ট মাধ্যম</b>\n\n'
            '<tg-emoji emoji-id="5961054379350955385">🏦</tg-emoji> <b>CBE</b>\n'
            '<code>1000528274394</code>\n\n'
            'Mohammed Seid\n\n'
            '<tg-emoji emoji-id="5960632377339285724">📱</tg-emoji> <b>TELEBIRR</b>\n'
            '<code>+251963266849</code>\n\n'
            '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>স্ক্রিনশট পাঠান!</b>'
        ),
        "support": (
            '<tg-emoji emoji-id="5305545479814161889">💬</tg-emoji> <b>সহায়তা</b>\n\n'
            '<tg-emoji emoji-id="5305655375142364109">📺</tg-emoji> <b>ডাউনলোড:</b> লিংক পাঠান।\n\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>ভিডিও থেকে অডিও:</b> ভিডিও পাঠান।\n\n'
            '<tg-emoji emoji-id="5949327894567195412">👩‍💻</tg-emoji> এডমিনকে বার্তা পাঠান।'
        )
    },
    "id": {
        "btn_add": "Tambahkan bot ke grup",
        "btn_order": "Iklan",
        "btn_price": "Harga & Tarif",
        "btn_payment": "Metode Pembayaran",
        "btn_status": "Status Saya",
        "btn_lang": "Language | Bahasa",
        "btn_support": "Bantuan",
        "btn_back": "Kembali",
        "loading": '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> <b>Memuat... Tunggu sebentar</b>',
        "download_success": '<tg-emoji emoji-id="5305762354187772738">🚀</tg-emoji> <b>Diunduh dengan</b> @{bot_username}\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Selamat menikmati!</b>',
        "audio_extracted": '<tg-emoji emoji-id="5307705891313721642">🎧</tg-emoji> <b>Audio diekstrak (MP3)</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Diunduh dengan</b> @{bot_username}',
        "video_converted": '<tg-emoji emoji-id="5305534793935527938">🎵</tg-emoji> <b>Audio dikonversi</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Dikonversi dengan</b> @{bot_username}',
        "size_limit": "⚠️ <b>File melebihi 50MB!</b>",
        "fail_download": "💔 <b>Gagal mengunduh!</b>",
        "photo_download": '📸 <b>Foto Diunduh</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Diunduh dengan</b> @{bot_username}',
        "welcome": (
            'Halo <tg-emoji emoji-id="5305577086478489521">🚨</tg-emoji>\n\n'
            '<tg-emoji emoji-id="5305739801314501775">✅</tg-emoji> <b>Opsi (Unduh video, foto dan audio):</b>\n\n'
            '<tg-emoji emoji-id="5305290882742788410">🎵</tg-emoji> | <b>Tiktok & Likee</b>\n'
            '<tg-emoji emoji-id="5305551797711053969">📸</tg-emoji> | <b>Pinterest & Instagram</b>\n'
            '<tg-emoji emoji-id="5305777524012262308">▶️</tg-emoji> | <b>YouTube</b>\n'
            '<tg-emoji emoji-id="5305474827602140530">✖️</tg-emoji> | <b>Twitter (X)</b>\n'
            '<tg-emoji emoji-id="5305311717629142471">📘</tg-emoji> | <b>Facebook, Reddit, Twitch</b>\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>Konverter Video ke Audio</b>\n\n'
            '<b>Lainnya:</b> <tg-emoji emoji-id="5305466057278923962">📥</tg-emoji>'
        ),
        "price": (
            '<tg-emoji emoji-id="5447458260200214425">💰</tg-emoji> <b>Tarif Iklan</b>\n\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 12 Jam — Negosiasi\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 24 Jam — <b>500 ETB</b>\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 48 Jam — <b>700 ETB</b>\n\n'
            'Pilih paket Anda <tg-emoji emoji-id="5463249828450424568">🤝</tg-emoji>'
        ),
        "order": (
            '<tg-emoji emoji-id="5197304993920616826">📢</tg-emoji> <b>Iklan di Channel @mame_posts</b>\n\n'
            '<tg-emoji emoji-id="5305634553140912174">👇</tg-emoji> Kirim postingan Anda <tg-emoji emoji-id="5305739801314501775">ℹ️</tg-emoji>'
        ),
        "payment": (
            '<tg-emoji emoji-id="5186349709169525403">💳</tg-emoji> <b>Metode Pembayaran</b>\n\n'
            '<tg-emoji emoji-id="5961054379350955385">🏦</tg-emoji> <b>CBE</b>\n'
            '<code>1000528274394</code>\n\n'
            'Mohammed Seid\n\n'
            '<tg-emoji emoji-id="5960632377339285724">📱</tg-emoji> <b>TELEBIRR</b>\n'
            '<code>+251963266849</code>\n\n'
            '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Kirim tangkapan layar!</b>'
        ),
        "support": (
            '<tg-emoji emoji-id="5305545479814161889">💬</tg-emoji> <b>Bantuan</b>\n\n'
            '<tg-emoji emoji-id="5305655375142364109">📺</tg-emoji> <b>Unduh:</b> Kirim tautan.\n\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>Video ke audio:</b> Kirim video.\n\n'
            '<tg-emoji emoji-id="5949327894567195412">👩‍💻</tg-emoji> Kirim pesan ke admin.'
        )
    },
    "de": {
        "btn_add": "Bot zur Gruppe hinzufügen",
        "btn_order": "Werbung buchen",
        "btn_price": "Preise",
        "btn_payment": "Zahlungsmethode",
        "btn_status": "Mein Status",
        "btn_lang": "Language | Sprache",
        "btn_support": "Hilfe",
        "btn_back": "Zurück",
        "loading": '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> <b>Laden... Bitte warten</b>',
        "download_success": '<tg-emoji emoji-id="5305762354187772738">🚀</tg-emoji> <b>Heruntergeladen mit</b> @{bot_username}\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Viel Spaß!</b>',
        "audio_extracted": '<tg-emoji emoji-id="5307705891313721642">🎧</tg-emoji> <b>Extrahiertes Audio (MP3)</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Heruntergeladen mit</b> @{bot_username}',
        "video_converted": '<tg-emoji emoji-id="5305534793935527938">🎵</tg-emoji> <b>Konvertiertes Audio</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Konvertiert mit</b> @{bot_username}',
        "size_limit": "⚠️ <b>Datei ist größer als 50MB!</b>",
        "fail_download": "💔 <b>Download fehlgeschlagen!</b>",
        "photo_download": '📸 <b>Heruntergeladenes Foto</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Heruntergeladen mit</b> @{bot_username}',
        "welcome": (
            'Hallo <tg-emoji emoji-id="5305577086478489521">🚨</tg-emoji>\n\n'
            '<tg-emoji emoji-id="5305739801314501775">✅</tg-emoji> <b>Optionen (Videos, Fotos & Audio herunterladen):</b>\n\n'
            '<tg-emoji emoji-id="5305290882742788410">🎵</tg-emoji> | <b>Tiktok & Likee</b>\n'
            '<tg-emoji emoji-id="5305551797711053969">📸</tg-emoji> | <b>Pinterest & Instagram</b>\n'
            '<tg-emoji emoji-id="5305777524012262308">▶️</tg-emoji> | <b>YouTube</b>\n'
            '<tg-emoji emoji-id="5305474827602140530">✖️</tg-emoji> | <b>Twitter (X)</b>\n'
            '<tg-emoji emoji-id="5305311717629142471">📘</tg-emoji> | <b>Facebook, Reddit, Twitch</b>\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>Video zu Audio Konverter</b>\n\n'
            '<b>Sonstige:</b> <tg-emoji emoji-id="5305466057278923962">📥</tg-emoji>'
        ),
        "price": (
            '<tg-emoji emoji-id="5447458260200214425">💰</tg-emoji> <b>Werbepreise</b>\n\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 12 Stunden — Verhandelbar\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 24 Stunden — <b>500 ETB</b>\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 48 Stunden — <b>700 ETB</b>\n\n'
            'Wählen Sie Ihren Plan <tg-emoji emoji-id="5463249828450424568">🤝</tg-emoji>'
        ),
        "order": (
            '<tg-emoji emoji-id="5197304993920616826">📢</tg-emoji> <b>Werbung auf @mame_posts</b>\n\n'
            '<tg-emoji emoji-id="5305634553140912174">👇</tg-emoji> Senden Sie Ihren Beitrag <tg-emoji emoji-id="5305739801314501775">ℹ️</tg-emoji>'
        ),
        "payment": (
            '<tg-emoji emoji-id="5186349709169525403">💳</tg-emoji> <b>Zahlungsmethode</b>\n\n'
            '<tg-emoji emoji-id="5961054379350955385">🏦</tg-emoji> <b>CBE</b>\n'
            '<code>1000528274394</code>\n\n'
            'Mohammed Seid\n\n'
            '<tg-emoji emoji-id="5960632377339285724">📱</tg-emoji> <b>TELEBIRR</b>\n'
            '<code>+251963266849</code>\n\n'
            '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Senden Sie den Screenshot!</b>'
        ),
        "support": (
            '<tg-emoji emoji-id="5305545479814161889">💬</tg-emoji> <b>Support</b>\n\n'
            '<tg-emoji emoji-id="5305655375142364109">📺</tg-emoji> <b>Download:</b> Links senden.\n\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>Video zu Audio:</b> Video senden.\n\n'
            '<tg-emoji emoji-id="5949327894567195412">👩‍💻</tg-emoji> Schreiben Sie dem Admin.'
        )
    },
    "uk": {
        "btn_add": "Додати бота в чат",
        "btn_order": "Замовити рекламу",
        "btn_price": "Ціни та тарифи",
        "btn_payment": "Спосіб оплаты",
        "btn_status": "Мій статус",
        "btn_lang": "Language | Мова",
        "btn_support": "Допомога",
        "btn_back": "Назад",
        "loading": '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> <b>Завантаження... Зачекайте</b>',
        "download_success": '<tg-emoji emoji-id="5305762354187772738">🚀</tg-emoji> <b>Завантажено за допомогою</b> @{bot_username}\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Приємного перегляду!</b>',
        "audio_extracted": '<tg-emoji emoji-id="5307705891313721642">🎧</tg-emoji> <b>Витягнуте аудіо (MP3)</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Завантажено через</b> @{bot_username}',
        "video_converted": '<tg-emoji emoji-id="5305534793935527938">🎵</tg-emoji> <b>Сконвертоване аудіо</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Сконвертовано через</b> @{bot_username}',
        "size_limit": "⚠️ <b>Файл перевищує 50 МБ!</b>",
        "fail_download": "💔 <b>Помилка завантаження!</b>",
        "photo_download": '📸 <b>Завантажене фото</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Завантажено за допомогою</b> @{bot_username}',
        "welcome": (
            'Привіт <tg-emoji emoji-id="5305577086478489521">🚨</tg-emoji>\n\n'
            '<tg-emoji emoji-id="5305739801314501775">✅</tg-emoji> <b>Можливості (Завантажуйте відео, фото та аудіо):</b>\n\n'
            '<tg-emoji emoji-id="5305290882742788410">🎵</tg-emoji> | <b>Tiktok & Likee</b>\n'
            '<tg-emoji emoji-id="5305551797711053969">📸</tg-emoji> | <b>Pinterest & Instagram</b>\n'
            '<tg-emoji emoji-id="5305777524012262308">▶️</tg-emoji> | <b>YouTube</b>\n'
            '<tg-emoji emoji-id="5305474827602140530">✖️</tg-emoji> | <b>Twitter (X)</b>\n'
            '<tg-emoji emoji-id="5305311717629142471">📘</tg-emoji> | <b>Facebook, Reddit, Twitch</b>\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>Конвертер відео в аудіо</b>\n\n'
            '<b>Інші:</b> <tg-emoji emoji-id="5305466057278923962">📥</tg-emoji>'
        ),
        "price": (
            '<tg-emoji emoji-id="5447458260200214425">💰</tg-emoji> <b>Ціни на рекламу</b>\n\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 12 годин — За домовленістю\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 24 години — <b>500 ETB</b>\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 48 годин — <b>700 ETB</b>\n\n'
            'Оберіть план <tg-emoji emoji-id="5463249828450424568">🤝</tg-emoji>'
        ),
        "order": (
            '<tg-emoji emoji-id="5197304993920616826">📢</tg-emoji> <b>Реклама на каналі @mame_posts</b>\n\n'
            '<tg-emoji emoji-id="5305634553140912174">👇</tg-emoji> Надішліть ваш пост <tg-emoji emoji-id="5305739801314501775">ℹ️</tg-emoji>'
        ),
        "payment": (
            '<tg-emoji emoji-id="5186349709169525403">💳</tg-emoji> <b>Способи оплати</b>\n\n'
            '<tg-emoji emoji-id="5961054379350955385">🏦</tg-emoji> <b>CBE</b>\n'
            '<code>1000528274394</code>\n\n'
            'Mohammed Seid\n\n'
            '<tg-emoji emoji-id="5960632377339285724">📱</tg-emoji> <b>TELEBIRR</b>\n'
            '<code>+251963266849</code>\n\n'
            '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Надішліть скріншот!</b>'
        ),
        "support": (
            '<tg-emoji emoji-id="5305545479814161889">💬</tg-emoji> <b>Підтримка</b>\n\n'
            '<tg-emoji emoji-id="5305655375142364109">📺</tg-emoji> <b>Завантаження:</b> Надсилайте посилання.\n\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>Відео в аудіо:</b> Надішліть відео.\n\n'
            '<tg-emoji emoji-id="5949327894567195412">👩‍💻</tg-emoji> Напишіть адміну.'
        )
    },
    "tr": {
        "btn_add": "Botu gruba ekle",
        "btn_order": "Reklam ver",
        "btn_price": "Fiyatlar",
        "btn_payment": "Ödeme Yöntemi",
        "btn_status": "Durumum",
        "btn_lang": "Language | Dil",
        "btn_support": "Destek",
        "btn_back": "Geri",
        "loading": '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> <b>Yükleniyor... Lütfen bekleyin</b>',
        "download_success": '<tg-emoji emoji-id="5305762354187772738">🚀</tg-emoji> <b>İndirildi:</b> @{bot_username}\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Keyfini çıkarın!</b>',
        "audio_extracted": '<tg-emoji emoji-id="5307705891313721642">🎧</tg-emoji> <b>Ses ayıklandı (MP3)</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>İndirildi:</b> @{bot_username}',
        "video_converted": '<tg-emoji emoji-id="5305534793935527938">🎵</tg-emoji> <b>Dönüştürülen ses</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Dönüştürüldü:</b> @{bot_username}',
        "size_limit": "⚠️ <b>Dosya 50MB'tan büyük!</b>",
        "fail_download": "💔 <b>İndirme başarısız!</b>",
        "photo_download": '📸 <b>İndirilen Fotoğraf</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>İndirildi:</b> @{bot_username}',
        "welcome": (
            'Merhaba <tg-emoji emoji-id="5305577086478489521">🚨</tg-emoji>\n\n'
            '<tg-emoji emoji-id="5305739801314501775">✅</tg-emoji> <b>Seçenekler (Video, fotoğraf ve ses indirin):</b>\n\n'
            '<tg-emoji emoji-id="5305290882742788410">🎵</tg-emoji> | <b>Tiktok & Likee</b>\n'
            '<tg-emoji emoji-id="5305551797711053969">📸</tg-emoji> | <b>Pinterest & Instagram</b>\n'
            '<tg-emoji emoji-id="5305777524012262308">▶️</tg-emoji> | <b>YouTube</b>\n'
            '<tg-emoji emoji-id="5305474827602140530">✖️</tg-emoji> | <b>Twitter (X)</b>\n'
            '<tg-emoji emoji-id="5305311717629142471">📘</tg-emoji> | <b>Facebook, Reddit, Twitch</b>\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>Video - Ses Dönüştürücü</b>\n\n'
            '<b>Diğer:</b> <tg-emoji emoji-id="5305466057278923962">📥</tg-emoji>'
        ),
        "price": (
            '<tg-emoji emoji-id="5447458260200214425">💰</tg-emoji> <b>Reklam Fiyatları</b>\n\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 12 Saat — Pazarlığa açık\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 24 Saat — <b>500 ETB</b>\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 48 Saat — <b>700 ETB</b>\n\n'
            'Planınızı seçin <tg-emoji emoji-id="5463249828450424568">🤝</tg-emoji>'
        ),
        "order": (
            '<tg-emoji emoji-id="5197304993920616826">📢</tg-emoji> <b>@mame_posts Kanalına Reklam Verin</b>\n\n'
            '<tg-emoji emoji-id="5305634553140912174">👇</tg-emoji> Gönderinizi aşağıya gönderin <tg-emoji emoji-id="5305739801314501775">ℹ️</tg-emoji>'
        ),
        "payment": (
            '<tg-emoji emoji-id="5186349709169525403">💳</tg-emoji> <b>Ödeme Yöntemi</b>\n\n'
            '<tg-emoji emoji-id="5961054379350955385">🏦</tg-emoji> <b>CBE</b>\n'
            '<code>1000528274394</code>\n\n'
            'Mohammed Seid\n\n'
            '<tg-emoji emoji-id="5960632377339285724">📱</tg-emoji> <b>TELEBIRR</b>\n'
            '<code>+251963266849</code>\n\n'
            '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Ekran görüntüsünü gönderin!</b>'
        ),
        "support": (
            '<tg-emoji emoji-id="5305545479814161889">💬</tg-emoji> <b>Destek</b>\n\n'
            '<tg-emoji emoji-id="5305655375142364109">📺</tg-emoji> <b>İndirme:</b> Bağlantı gönderin.\n\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>Video - Ses:</b> Video gönderin.\n\n'
            '<tg-emoji emoji-id="5949327894567195412">👩‍💻</tg-emoji> Yöneticiye yazın.'
        )
    },
    "ko": {
        "btn_add": "그룹에 봇 추가",
        "btn_order": "광고 문의",
        "btn_price": "가격 및 요금",
        "btn_payment": "결제 방법",
        "btn_status": "내 상태",
        "btn_lang": "Language | 언어",
        "btn_support": "지원",
        "btn_back": "돌아가기",
        "loading": '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> <b>로딩 중... 잠시만요</b>',
        "download_success": '<tg-emoji emoji-id="5305762354187772738">🚀</tg-emoji> <b>다운로드 완료:</b> @{bot_username}\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>즐기세요!</b>',
        "audio_extracted": '<tg-emoji emoji-id="5307705891313721642">🎧</tg-emoji> <b>추출된 오디오 (MP3)</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>다운로드 완료:</b> @{bot_username}',
        "video_converted": '<tg-emoji emoji-id="5305534793935527938">🎵</tg-emoji> <b>변환된 오디오</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>변환 완료:</b> @{bot_username}',
        "size_limit": "⚠️ <b>파일이 50MB보다 큽니다!</b>",
        "fail_download": "💔 <b>다운로드 실패!</b>",
        "photo_download": '📸 <b>다운로드된 사진</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>다운로드 완료:</b> @{bot_username}',
        "welcome": (
            '안녕하세요 <tg-emoji emoji-id="5305577086478489521">🚨</tg-emoji>\n\n'
            '<tg-emoji emoji-id="5305739801314501775">✅</tg-emoji> <b>옵션 (동영상, 사진, 오디오 다운로드):</b>\n\n'
            '<tg-emoji emoji-id="5305290882742788410">🎵</tg-emoji> | <b>Tiktok & Likee</b>\n'
            '<tg-emoji emoji-id="5305551797711053969">📸</tg-emoji> | <b>Pinterest & Instagram</b>\n'
            '<tg-emoji emoji-id="5305777524012262308">▶️</tg-emoji> | <b>YouTube</b>\n'
            '<tg-emoji emoji-id="5305474827602140530">✖️</tg-emoji> | <b>Twitter (X)</b>\n'
            '<tg-emoji emoji-id="5305311717629142471">📘</tg-emoji> | <b>Facebook, Reddit, Twitch</b>\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>비디오-오디오 변환기</b>\n\n'
            '<b>기타:</b> <tg-emoji emoji-id="5305466057278923962">📥</tg-emoji>'
        ),
        "price": (
            '<tg-emoji emoji-id="5447458260200214425">💰</tg-emoji> <b>광고 요금</b>\n\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 12시간 — 협의 가능\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 24시간 — <b>500 ETB</b>\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 48시간 — <b>700 ETB</b>\n\n'
            '플랜을 선택하세요 <tg-emoji emoji-id="5463249828450424568">🤝</tg-emoji>'
        ),
        "order": (
            '<tg-emoji emoji-id="5197304993920616826">📢</tg-emoji> <b>@mame_posts 채널 광고</b>\n\n'
            '<tg-emoji emoji-id="5305634553140912174">👇</tg-emoji> 게시물을 보내주세요 <tg-emoji emoji-id="5305739801314501775">ℹ️</tg-emoji>'
        ),
        "payment": (
            '<tg-emoji emoji-id="5186349709169525403">💳</tg-emoji> <b>결제 방법</b>\n\n'
            '<tg-emoji emoji-id="5961054379350955385">🏦</tg-emoji> <b>CBE</b>\n'
            '<code>1000528274394</code>\n\n'
            'Mohammed Seid\n\n'
            '<tg-emoji emoji-id="5960632377339285724">📱</tg-emoji> <b>TELEBIRR</b>\n'
            '<code>+251963266849</code>\n\n'
            '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>영수증을 보내주세요!</b>'
        ),
        "support": (
            '<tg-emoji emoji-id="5305545479814161889">💬</tg-emoji> <b>지원</b>\n\n'
            '<tg-emoji emoji-id="5305655375142364109">📺</tg-emoji> <b>다운로드:</b> 링크를 보내세요.\n\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>비디오-오디오:</b> 영상을 보내세요.\n\n'
            '<tg-emoji emoji-id="5949327894567195412">👩‍💻</tg-emoji> 관리자에게 문의하세요.'
        )
    },
    "it": {
        "btn_add": "Aggiungi bot al gruppo",
        "btn_order": "Pubblicità",
        "btn_price": "Prezzi",
        "btn_payment": "Metodo di pagamento",
        "btn_status": "Mio Stato",
        "btn_lang": "Language | Lingua",
        "btn_support": "Supporto",
        "btn_back": "Indietro",
        "loading": '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> <b>Caricamento... Attendere</b>',
        "download_success": '<tg-emoji emoji-id="5305762354187772738">🚀</tg-emoji> <b>Scaricato con</b> @{bot_username}\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Buona visione!</b>',
        "audio_extracted": '<tg-emoji emoji-id="5307705891313721642">🎧</tg-emoji> <b>Audio estratto (MP3)</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Scaricato con</b> @{bot_username}',
        "video_converted": '<tg-emoji emoji-id="5305534793935527938">🎵</tg-emoji> <b>Audio convertito</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Convertito con</b> @{bot_username}',
        "size_limit": "⚠️ <b>Il file supera i 50 MB!</b>",
        "fail_download": "💔 <b>Download fallito!</b>",
        "photo_download": '📸 <b>Foto scaricata</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Scaricata con</b> @{bot_username}',
        "welcome": (
            'Ciao <tg-emoji emoji-id="5305577086478489521">🚨</tg-emoji>\n\n'
            '<tg-emoji emoji-id="5305739801314501775">✅</tg-emoji> <b>Opzioni (Scarica video, foto e audio):</b>\n\n'
            '<tg-emoji emoji-id="5305290882742788410">🎵</tg-emoji> | <b>Tiktok & Likee</b>\n'
            '<tg-emoji emoji-id="5305551797711053969">📸</tg-emoji> | <b>Pinterest & Instagram</b>\n'
            '<tg-emoji emoji-id="5305777524012262308">▶️</tg-emoji> | <b>YouTube</b>\n'
            '<tg-emoji emoji-id="5305474827602140530">✖️</tg-emoji> | <b>Twitter (X)</b>\n'
            '<tg-emoji emoji-id="5305311717629142471">📘</tg-emoji> | <b>Facebook, Reddit, Twitch</b>\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>Convertitore Video in Audio</b>\n\n'
            '<b>Altro:</b> <tg-emoji emoji-id="5305466057278923962">📥</tg-emoji>'
        ),
        "price": (
            '<tg-emoji emoji-id="5447458260200214425">💰</tg-emoji> <b>Prezzi pubblicità</b>\n\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 12 Ore — Trattabile\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 24 Ore — <b>500 ETB</b>\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 48 Ore — <b>700 ETB</b>\n\n'
            'Scegli il tuo piano <tg-emoji emoji-id="5463249828450424568">🤝</tg-emoji>'
        ),
        "order": (
            '<tg-emoji emoji-id="5197304993920616826">📢</tg-emoji> <b>Pubblicità su @mame_posts</b>\n\n'
            '<tg-emoji emoji-id="5305634553140912174">👇</tg-emoji> Invia il tuo post <tg-emoji emoji-id="5305739801314501775">ℹ️</tg-emoji>'
        ),
        "payment": (
            '<tg-emoji emoji-id="5186349709169525403">💳</tg-emoji> <b>Metodo di pagamento</b>\n\n'
            '<tg-emoji emoji-id="5961054379350955385">🏦</tg-emoji> <b>CBE</b>\n'
            '<code>1000528274394</code>\n\n'
            'Mohammed Seid\n\n'
            '<tg-emoji emoji-id="5960632377339285724">📱</tg-emoji> <b>TELEBIRR</b>\n'
            '<code>+251963266849</code>\n\n'
            '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Invia la ricevuta!</b>'
        ),
        "support": (
            '<tg-emoji emoji-id="5305545479814161889">💬</tg-emoji> <b>Supporto</b>\n\n'
            '<tg-emoji emoji-id="5305655375142364109">📺</tg-emoji> <b>Download:</b> Invia link.\n\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>Video in audio:</b> Invia un video.\n\n'
            '<tg-emoji emoji-id="5949327894567195412">👩‍💻</tg-emoji> Scrivi all\'admin.'
        )
    },
    "pl": {
        "btn_add": "Dodaj bota do grupy",
        "btn_order": "Reklama",
        "btn_price": "Cennik",
        "btn_payment": "Metoda płatności",
        "btn_status": "Mój status",
        "btn_lang": "Language | Język",
        "btn_support": "Pomoc",
        "btn_back": "Wróć",
        "loading": '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> <b>Ładowanie... Proszę czekać</b>',
        "download_success": '<tg-emoji emoji-id="5305762354187772738">🚀</tg-emoji> <b>Pobrano przez</b> @{bot_username}\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Miłego oglądania!</b>',
        "audio_extracted": '<tg-emoji emoji-id="5307705891313721642">🎧</tg-emoji> <b>Pobrany dźwięk (MP3)</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Pobrano przez</b> @{bot_username}',
        "video_converted": '<tg-emoji emoji-id="5305534793935527938">🎵</tg-emoji> <b>Skonwertowany dźwięk</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Skonwertowano przez</b> @{bot_username}',
        "size_limit": "⚠️ <b>Plik jest większy niż 50MB!</b>",
        "fail_download": "💔 <b>Nie udało się pobrać!</b>",
        "photo_download": '📸 <b>Pobrane zdjęcie</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Pobrano przez</b> @{bot_username}',
        "welcome": (
            'Cześć <tg-emoji emoji-id="5305577086478489521">🚨</tg-emoji>\n\n'
            '<tg-emoji emoji-id="5305739801314501775">✅</tg-emoji> <b>Opcje (Pobieraj wideo, zdjęcia i dźwięk):</b>\n\n'
            '<tg-emoji emoji-id="5305290882742788410">🎵</tg-emoji> | <b>Tiktok & Likee</b>\n'
            '<tg-emoji emoji-id="5305551797711053969">📸</tg-emoji> | <b>Pinterest & Instagram</b>\n'
            '<tg-emoji emoji-id="5305777524012262308">▶️</tg-emoji> | <b>YouTube</b>\n'
            '<tg-emoji emoji-id="5305474827602140530">✖️</tg-emoji> | <b>Twitter (X)</b>\n'
            '<tg-emoji emoji-id="5305311717629142471">📘</tg-emoji> | <b>Facebook, Reddit, Twitch</b>\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>Konwerter Wideo na Audio</b>\n\n'
            '<b>Inne:</b> <tg-emoji emoji-id="5305466057278923962">📥</tg-emoji>'
        ),
        "price": (
            '<tg-emoji emoji-id="5447458260200214425">💰</tg-emoji> <b>Ceny reklam</b>\n\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 12 Godzin — Do negocjacji\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 24 Godziny — <b>500 ETB</b>\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 48 Godzin — <b>700 ETB</b>\n\n'
            'Wybierz plan <tg-emoji emoji-id="5463249828450424568">🤝</tg-emoji>'
        ),
        "order": (
            '<tg-emoji emoji-id="5197304993920616826">📢</tg-emoji> <b>Reklama na @mame_posts</b>\n\n'
            '<tg-emoji emoji-id="5305634553140912174">👇</tg-emoji> Wyślij swój post <tg-emoji emoji-id="5305739801314501775">ℹ️</tg-emoji>'
        ),
        "payment": (
            '<tg-emoji emoji-id="5186349709169525403">💳</tg-emoji> <b>Metoda płatności</b>\n\n'
            '<tg-emoji emoji-id="5961054379350955385">🏦</tg-emoji> <b>CBE</b>\n'
            '<code>1000528274394</code>\n\n'
            'Mohammed Seid\n\n'
            '<tg-emoji emoji-id="5960632377339285724">📱</tg-emoji> <b>TELEBIRR</b>\n'
            '<code>+251963266849</code>\n\n'
            '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Wyślij potwierdzenie!</b>'
        ),
        "support": (
            '<tg-emoji emoji-id="5305545479814161889">💬</tg-emoji> <b>Pomoc</b>\n\n'
            '<tg-emoji emoji-id="5305655375142364109">📺</tg-emoji> <b>Pobieranie:</b> Wyślij linki.\n\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>Wideo na audio:</b> Wyślij wideo.\n\n'
            '<tg-emoji emoji-id="5949327894567195412">👩‍💻</tg-emoji> Napisz do admina.'
        )
    },
    "vi": {
        "btn_add": "Thêm bot vào nhóm",
        "btn_order": "Đặt quảng cáo",
        "btn_price": "Bảng giá",
        "btn_payment": "Phương thức thanh toán",
        "btn_status": "Trạng thái",
        "btn_lang": "Language | Ngôn ngữ",
        "btn_support": "Hỗ trợ",
        "btn_back": "Quay lại",
        "loading": '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> <b>Đang tải... Vui lòng chờ</b>',
        "download_success": '<tg-emoji emoji-id="5305762354187772738">🚀</tg-emoji> <b>Đã tải xuống bởi</b> @{bot_username}\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Tận hưởng nhé!</b>',
        "audio_extracted": '<tg-emoji emoji-id="5307705891313721642">🎧</tg-emoji> <b>Âm thanh đã trích xuất (MP3)</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Đã tải xuống bởi</b> @{bot_username}',
        "video_converted": '<tg-emoji emoji-id="5305534793935527938">🎵</tg-emoji> <b>Âm thanh đã chuyển đổi</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Đã chuyển đổi bởi</b> @{bot_username}',
        "size_limit": "⚠️ <b>Tệp lớn hơn 50MB!</b>",
        "fail_download": "💔 <b>Tải xuống thất bại!</b>",
        "photo_download": '📸 <b>Ảnh đã tải xuống</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Đã tải xuống bởi</b> @{bot_username}',
        "welcome": (
            'Xin chào <tg-emoji emoji-id="5305577086478489521">🚨</tg-emoji>\n\n'
            '<tg-emoji emoji-id="5305739801314501775">✅</tg-emoji> <b>Tùy chọn (Tải xuống video, ảnh và âm thanh):</b>\n\n'
            '<tg-emoji emoji-id="5305290882742788410">🎵</tg-emoji> | <b>Tiktok & Likee</b>\n'
            '<tg-emoji emoji-id="5305551797711053969">📸</tg-emoji> | <b>Pinterest & Instagram</b>\n'
            '<tg-emoji emoji-id="5305777524012262308">▶️</tg-emoji> | <b>YouTube</b>\n'
            '<tg-emoji emoji-id="5305474827602140530">✖️</tg-emoji> | <b>Twitter (X)</b>\n'
            '<tg-emoji emoji-id="5305311717629142471">📘</tg-emoji> | <b>Facebook, Reddit, Twitch</b>\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>Chuyển đổi Video sang Audio</b>\n\n'
            '<b>Khác:</b> <tg-emoji emoji-id="5305466057278923962">📥</tg-emoji>'
        ),
        "price": (
            '<tg-emoji emoji-id="5447458260200214425">💰</tg-emoji> <b>Giá quảng cáo</b>\n\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 12 Giờ — Thương lượng\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 24 Giờ — <b>500 ETB</b>\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 48 Giờ — <b>700 ETB</b>\n\n'
            'Chọn gói của bạn <tg-emoji emoji-id="5463249828450424568">🤝</tg-emoji>'
        ),
        "order": (
            '<tg-emoji emoji-id="5197304993920616826">📢</tg-emoji> <b>Quảng cáo trên kênh @mame_posts</b>\n\n'
            '<tg-emoji emoji-id="5305634553140912174">👇</tg-emoji> Gửi bài viết của bạn <tg-emoji emoji-id="5305739801314501775">ℹ️</tg-emoji>'
        ),
        "payment": (
            '<tg-emoji emoji-id="5186349709169525403">💳</tg-emoji> <b>Phương thức thanh toán</b>\n\n'
            '<tg-emoji emoji-id="5961054379350955385">🏦</tg-emoji> <b>CBE</b>\n'
            '<code>1000528274394</code>\n\n'
            'Mohammed Seid\n\n'
            '<tg-emoji emoji-id="5960632377339285724">📱</tg-emoji> <b>TELEBIRR</b>\n'
            '<code>+251963266849</code>\n\n'
            '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Gửi ảnh chụp màn hình!</b>'
        ),
        "support": (
            '<tg-emoji emoji-id="5305545479814161889">💬</tg-emoji> <b>Hỗ trợ</b>\n\n'
            '<tg-emoji emoji-id="5305655375142364109">📺</tg-emoji> <b>Tải xuống:</b> Gửi liên kết.\n\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>Video sang audio:</b> Gửi video.\n\n'
            '<tg-emoji emoji-id="5949327894567195412">👩‍💻</tg-emoji> Nhắn tin cho admin.'
        )
    },
    "kk": {
        "btn_add": "Ботты топқа қосу",
        "btn_order": "Жарнама беру",
        "btn_price": "Бағалар",
        "btn_payment": "Төлем әдісі",
        "btn_status": "Мәртебем",
        "btn_lang": "Language | Тіл",
        "btn_support": "Көмек",
        "btn_back": "Қайту",
        "loading": '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> <b>Жүктелуде... Күте тұрыңыз</b>',
        "download_success": '<tg-emoji emoji-id="5305762354187772738">🚀</tg-emoji> <b>Жүктеп алынды:</b> @{bot_username}\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Тамашалаңыз!</b>',
        "audio_extracted": '<tg-emoji emoji-id="5307705891313721642">🎧</tg-emoji> <b>Аудио (MP3)</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Жүктеп алынды:</b> @{bot_username}',
        "video_converted": '<tg-emoji emoji-id="5305534793935527938">🎵</tg-emoji> <b>Айырбасталған аудио</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Айырбасталды:</b> @{bot_username}',
        "size_limit": "⚠️ <b>Файл 50MB-тан үлкен!</b>",
        "fail_download": "💔 <b>Жүктеу сәтсіз аяқталды!</b>",
        "photo_download": '📸 <b>Сурет</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Жүктеп алынды:</b> @{bot_username}',
        "welcome": (
            'Сәлем <tg-emoji emoji-id="5305577086478489521">🚨</tg-emoji>\n\n'
            '<tg-emoji emoji-id="5305739801314501775">✅</tg-emoji> <b>Мүмкіндіктер (Видео, фото және аудио):</b>\n\n'
            '<tg-emoji emoji-id="5305290882742788410">🎵</tg-emoji> | <b>Tiktok & Likee</b>\n'
            '<tg-emoji emoji-id="5305551797711053969">📸</tg-emoji> | <b>Pinterest & Instagram</b>\n'
            '<tg-emoji emoji-id="5305777524012262308">▶️</tg-emoji> | <b>YouTube</b>\n'
            '<tg-emoji emoji-id="5305474827602140530">✖️</tg-emoji> | <b>Twitter (X)</b>\n'
            '<tg-emoji emoji-id="5305311717629142471">📘</tg-emoji> | <b>Facebook, Reddit, Twitch</b>\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>Видеодан аудиоға түрлендіргіш</b>\n\n'
            '<b>Басқалар:</b> <tg-emoji emoji-id="5305466057278923962">📥</tg-emoji>'
        ),
        "price": (
            '<tg-emoji emoji-id="5447458260200214425">💰</tg-emoji> <b>Жарнама бағалары</b>\n\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 12 Сағат — Келісімді\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 24 Сағат — <b>500 ETB</b>\n'
            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 48 Сағат — <b>700 ETB</b>\n\n'
            'Жоспарды таңдаңыз <tg-emoji emoji-id="5463249828450424568">🤝</tg-emoji>'
        ),
        "order": (
            '<tg-emoji emoji-id="5197304993920616826">📢</tg-emoji> <b>@mame_posts арнасында жарнама</b>\n\n'
            '<tg-emoji emoji-id="5305634553140912174">👇</tg-emoji> Постыңызды жіберіңіз <tg-emoji emoji-id="5305739801314501775">ℹ️</tg-emoji>'
        ),
        "payment": (
            '<tg-emoji emoji-id="5186349709169525403">💳</tg-emoji> <b>Төлем әдісі</b>\n\n'
            '<tg-emoji emoji-id="5961054379350955385">🏦</tg-emoji> <b>CBE</b>\n'
            '<code>1000528274394</code>\n\n'
            'Mohammed Seid\n\n'
            '<tg-emoji emoji-id="5960632377339285724">📱</tg-emoji> <b>TELEBIRR</b>\n'
            '<code>+251963266849</code>\n\n'
            '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Чек скриншотын жіберіңіз!</b>'
        ),
        "support": (
            '<tg-emoji emoji-id="5305545479814161889">💬</tg-emoji> <b>Көмек</b>\n\n'
            '<tg-emoji emoji-id="5305655375142364109">📺</tg-emoji> <b>Жүктеу:</b> Сілтеме жіберіңіз.\n\n'
            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> <b>Видеодан аудио:</b> Видео жіберіңіз.\n\n'
            '<tg-emoji emoji-id="5949327894567195412">👩‍💻</tg-emoji> Админге жазыңыз.'
        )
    }
}

def get_trans(user_id, key):
    lang = get_user_language(user_id)
    if not lang or lang not in TRANSLATIONS:
        lang = "en"
    lang_dict = TRANSLATIONS.get(lang, TRANSLATIONS.get("en", TRANSLATIONS["am"]))
    return lang_dict.get(key, TRANSLATIONS["en"].get(key, TRANSLATIONS["am"].get(key, "")))

# ==================================================
# MAIN MENU KEYBOARD (WITH CUSTOM EMOJIS)
# ==================================================

def get_main_menu_keyboard(bot_username, user_id):
    keyboard = [
        [
            InlineKeyboardButton(
                text=get_trans(user_id, "btn_add"),
                icon_custom_emoji_id="5305545479814161889",
                url=f"https://t.me/{bot_username}?startgroup=true"
            )
        ],
        [
            InlineKeyboardButton(
                text=get_trans(user_id, "btn_order"),
                icon_custom_emoji_id="5267442591548320083",
                callback_data="cmd_order"
            )
        ],
        [
            InlineKeyboardButton(
                text=get_trans(user_id, "btn_price"),
                icon_custom_emoji_id="5447458260200214425",
                callback_data="cmd_price"
            ),
            InlineKeyboardButton(
                text=get_trans(user_id, "btn_payment"),
                icon_custom_emoji_id="5186349709169525403",
                callback_data="cmd_payment"
            )
        ],
        [
            InlineKeyboardButton(
                text=get_trans(user_id, "btn_status"),
                icon_custom_emoji_id="5431577498364158238",
                callback_data="cmd_status"
            ),
            InlineKeyboardButton(
                text=get_trans(user_id, "btn_lang"),
                icon_custom_emoji_id="5431577498364158238",
                callback_data="cmd_change_lang"
            )
        ],
        [
            InlineKeyboardButton(
                text=get_trans(user_id, "btn_support"),
                icon_custom_emoji_id="5949327894567195412",
                callback_data="cmd_support"
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)

def get_language_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
            InlineKeyboardButton("🇪🇹 አማርኛ", callback_data="lang_am")
        ],
        [
            InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar")
        ],
        [
            InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
            InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr")
        ],
        [
            InlineKeyboardButton("🇪🇸 Español", callback_data="lang_es"),
            InlineKeyboardButton("🇮🇷 ایران", callback_data="lang_fa")
        ],
        [
            InlineKeyboardButton("🇮🇳 भारत", callback_data="lang_hi"),
            InlineKeyboardButton("🇺🇿 O'zbek", callback_data="lang_uz")
        ],
        [
            InlineKeyboardButton("🇵🇹 Português", callback_data="lang_pt"),
            InlineKeyboardButton("🇨🇳 中文", callback_data="lang_zh")
        ],
        [
            InlineKeyboardButton("🇧🇩 বাংলা", callback_data="lang_bn"),
            InlineKeyboardButton("🇮🇩 Indonesia", callback_data="lang_id")
        ],
        [
            InlineKeyboardButton("🇩🇪 Deutsch", callback_data="lang_de"),
            InlineKeyboardButton("🇺🇦 Українська", callback_data="lang_uk")
        ],
        [
            InlineKeyboardButton("🇹🇷 Türkçe", callback_data="lang_tr"),
            InlineKeyboardButton("🇰🇷 한국어", callback_data="lang_ko")
        ],
        [
            InlineKeyboardButton("🇮🇹 Italiano", callback_data="lang_it"),
            InlineKeyboardButton("🇵🇱 Polski", callback_data="lang_pl")
        ],
        [
            InlineKeyboardButton("🇻🇳 Tiếng Việt", callback_data="lang_vi"),
            InlineKeyboardButton("🇰🇿 Қазақша", callback_data="lang_kk")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_keyboard(user_id):
    keyboard = [
        [
            InlineKeyboardButton(
                text=get_trans(user_id, "btn_back"),
                icon_custom_emoji_id="5248948801674159296",
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

async def show_force_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        '<tg-emoji emoji-id="6034962180875490251">🔒</tg-emoji> '
        '<b>ቦቱን ለመጠቀም ከታች ያለውን ቻናል መቀላቀል አለብዎት!</b>\n\n'
        '1️⃣ <tg-emoji emoji-id="5267442591548320083">📢</tg-emoji> '
        '<b>Join Channel የሚለውን ይጫኑ::</b>\n'
        '2️⃣ ከዚያ <tg-emoji emoji-id="5305749202997911340">✅</tg-emoji> '
        '<b>I\'ve Joined የሚለውን ተጭነው የላኩትን ደግመው ይላኩ '
        '<tg-emoji emoji-id="5217449524410199951">🙂</tg-emoji>::</b>'
    )

    keyboard = [
        [
            InlineKeyboardButton("📢 Join Channel", url=FORCE_CHANNEL_LINK)
        ],
        [
            InlineKeyboardButton("✅ I've Joined", callback_data="check_join")
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
# START & MENU COMMAND (FIRST CHOICE: LANGUAGE)
# ==================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    record_user_activity(user_id)

    bot_username = context.bot.username or "ads_poster1bot"
    user_lang = get_user_language(user_id)

    if not user_lang:
        await update.message.reply_text(
            "<b>Please select your language / እባክዎ ቋንቋ ይምረጡ፦</b>",
            reply_markup=get_language_keyboard(),
            parse_mode="HTML"
        )
    else:
        setup_keyboard = ReplyKeyboardMarkup(    
            [["🏠 Menu"]],    
            resize_keyboard=True,    
            input_field_placeholder="Send link 🔗"    
        )
        await update.message.reply_text(    
            get_trans(user_id, "welcome"),    
            reply_markup=get_main_menu_keyboard(bot_username, user_id),    
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
        f'<tg-emoji emoji-id="5431577498364158238">📊</tg-emoji> <b>የእርስዎ እና የቦቱ Status</b>\n\n'    
        f'<tg-emoji emoji-id="5875078913725571378">👤</tg-emoji> <b>የግል መረጃዎት፦</b>\n'    
        f'<tg-emoji emoji-id="5465638272648617243">✈️</tg-emoji> <b>ስም:</b> {user.full_name}\n'    
        f'<tg-emoji emoji-id="5465638272648617243">✈️</tg-emoji> <b>Username:</b> {username_text}\n'    
        f'<tg-emoji emoji-id="5465638272648617243">✈️</tg-emoji> <b>Telegram ID:</b> <code>{user.id}</code>\n'    
        f'<tg-emoji emoji-id="5465638272648617243">✈️</tg-emoji> <b>የላኳቸው አጠቃላይ መልዕክቶች:</b> <code>{user_msg_count}</code>\n\n'    
            
        f'<tg-emoji emoji-id="5307979128543158051">🤖</tg-emoji> <b>የቦቱ አጠቃላይ መረጃ፦</b>\n'    
        f'<tg-emoji emoji-id="5465638272648617243">✈️</tg-emoji> <b>ሁኔታ:</b> Active <tg-emoji emoji-id="5307976826440687996">🔥</tg-emoji>\n'    
        f'<tg-emoji emoji-id="5465638272648617243">✈️</tg-emoji> <b>ጠቅላላ Users:</b> <code>{total_users}</code> <tg-emoji emoji-id="5305466057278923962">👥</tg-emoji>'    
    )    
    await update.message.reply_text(msg, parse_mode="HTML")

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
        '<tg-emoji emoji-id="5956569406996747523">⏳</tg-emoji> <b>መልዕክቱን ለተጠቃሚዎች በመላክ ላይ ይገኛል...</b>',    
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
    user_id = update.effective_user.id
    record_user_activity(user_id)
    await update.message.reply_text(
        get_trans(user_id, "price"),
        parse_mode="HTML"
    )

async def payment_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    record_user_activity(user_id)
    await update.message.reply_text(
        get_trans(user_id, "payment"),
        parse_mode="HTML"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    record_user_activity(user_id)
    await update.message.reply_text(
        get_trans(user_id, "support"),
        parse_mode="HTML"
    )

# ==================================================
# VIDEO TO AUDIO CONVERTER HANDLER
# ==================================================

async def convert_video_to_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    record_user_activity(user_id)

    if not await is_joined(update, context):    
        await show_force_join(update, context)    
        return    

    video = update.message.video or update.message.video_note or (    
        update.message.document if update.message.document and update.message.document.mime_type and update.message.document.mime_type.startswith('video/') else None    
    )    

    if not video:    
        return    

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.RECORD_VOICE)    
        
    status_msg = await update.message.reply_text(    
        get_trans(user_id, "loading"),    
        parse_mode="HTML"    
    )    

    file_id = update.message.message_id    
    input_path = f"input_vid_{user_id}_{file_id}.mp4"    
    output_path = f"output_aud_{user_id}_{file_id}.mp3"    

    try:    
        tg_file = await video.get_file()    
        await tg_file.download_to_drive(input_path)    

        cmd = [    
            "ffmpeg", "-y",    
            "-i", input_path,    
            "-vn",    
            "-acodec", "libmp3lame",    
            "-q:a", "2",    
            output_path    
        ]    
            
        await asyncio.to_thread(subprocess.run, cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)    

        if os.path.exists(output_path):    
            bot_username = context.bot.username or "ads_poster1bot"    
            share_url = f"https://t.me/share/url?url=https://t.me/{bot_username}?start=share&text=Try%20this%20awesome%20Video%20to%20Audio%20Converter%20Bot!🔥"    
            keyboard_share = [[InlineKeyboardButton("🔗 Share Bot 🚀", url=share_url)]]    
            reply_markup_share = InlineKeyboardMarkup(keyboard_share)    

            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_DOCUMENT)    
            caption_text = get_trans(user_id, "video_converted").format(bot_username=bot_username)
            with open(output_path, 'rb') as audio_file:    
                await update.message.reply_audio(    
                    audio=audio_file,    
                    caption=caption_text,    
                    reply_markup=reply_markup_share,    
                    parse_mode="HTML"    
                )    
            await status_msg.delete()    
        else:    
            await status_msg.edit_text("😥 <b>Conversion failed!</b>", parse_mode="HTML")    

    except Exception as e:    
        print("Video to Audio Error:", e)    
        await status_msg.edit_text("😥 <b>Error processing video!</b>", parse_mode="HTML")    

    finally:    
        for path in [input_path, output_path]:    
            if os.path.exists(path):    
                try:    
                    os.remove(path)    
                except Exception:    
                    pass

# ==================================================
# ULTRA-ROBUST DOWNLOAD ENGINE (VIDEOS, AUDIOS & PHOTOS)
# ==================================================

def unshorten_url(url: str) -> str:
    try:
        session = requests.Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
        resp = session.head(url, allow_redirects=True, timeout=10)
        return resp.url
    except Exception:
        return url

def clean_url(raw_url: str) -> str:
    return unshorten_url(raw_url)

def get_video_options(url: str, output_template: str, fallback: bool = False):
    opts = {
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'geo_bypass': True,
        'concurrent_fragment_downloads': 5,
        'outtmpl': output_template,
        'merge_output_format': 'mp4',

        'format': 'bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b',

        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web']
            }
        },

        'http_headers': {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/128.0.0.0 Safari/537.36'
            ),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    }

    if "likee" in url or "likee.video" in url:
        opts['http_headers']['Referer'] = 'https://likee.video/'

    elif "vimeo.com" in url:
        opts['http_headers']['Referer'] = 'https://vimeo.com/'

    if os.path.exists('cookies.txt'):
        opts['cookiefile'] = 'cookies.txt'

    return opts

def download_media_func(url: str, output_template: str, fallback: bool = False):
    with yt_dlp.YoutubeDL(get_video_options(url, output_template, fallback)) as ydl:
        ydl.download([url])

def find_downloaded_file(prefix: str):
    for f in os.listdir('.'):
        if f.startswith(prefix) and not f.endswith(('.part', '.ytdl')):
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

    bot_username = context.bot.username or "ads_poster1bot"    
    share_url = f"https://t.me/share/url?url=https://t.me/{bot_username}?start=share&text=Try%20this%20awesome%20Downloader%20Bot!🔥"    
    reply_markup_share = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Share Bot 🚀", url=share_url)]])    

    url = clean_url(raw_url)    

    # PINTEREST REAL PHOTO EXTRACTION    
    if "pinterest.com" in url or "pin.it" in url:    
        try:    
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}    
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

    try:    
        try:    
            await asyncio.to_thread(download_media_func, url, media_template, False)    
        except Exception as err1:
            print("First download attempt failed, retrying with fallback...", err1)
            await asyncio.to_thread(download_media_func, url, media_template, True)    

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
                    with open(actual_file, 'rb') as vf:    
                        await update.message.reply_video(    
                            video=vf,    
                            caption=get_trans(user_id, "download_success").format(bot_username=bot_username),    
                            reply_markup=reply_markup_share,    
                            parse_mode="HTML"    
                        )    
                    sent_any = True    

                    audio_output = f"audio_{user_id}_{update.message.message_id}.mp3"    
                    cmd = ["ffmpeg", "-y", "-i", actual_file, "-vn", "-acodec", "libmp3lame", "-q:a", "2", audio_output]    
                    await asyncio.to_thread(subprocess.run, cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)    

                    if os.path.exists(audio_output):    
                        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_DOCUMENT)    
                        with open(audio_output, 'rb') as af:    
                            await update.message.reply_audio(    
                                audio=af,    
                                caption=get_trans(user_id, "audio_extracted").format(bot_username=bot_username),    
                                reply_markup=reply_markup_share,    
                                parse_mode="HTML"    
                            )    
                        os.remove(audio_output)    
                        sent_any = True    
                else:
                    await status_msg.edit_text(
                        get_trans(user_id, "size_limit"), 
                        parse_mode="HTML"
                    )
                    return
    except Exception as e:    
        print("Media Download Error:", e)    

    finally:
        for f in os.listdir('.'):    
            if f.startswith(media_prefix):    
                try:    
                    os.remove(f)    
                except Exception:    
                    pass    

    if sent_any:    
        await status_msg.delete()    
    else:    
        await status_msg.edit_text(    
            get_trans(user_id, "fail_download"),    
            parse_mode="HTML"    
        )

# ==================================================
# BUTTON CLICK HANDLER
# ==================================================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data    
    user = query.from_user    
    bot_username = context.bot.username or "ads_poster1bot"

    if data.startswith("lang_"):
        lang_code = data.split("_")[1]
        set_user_language(user.id, lang_code)
        
        setup_keyboard = ReplyKeyboardMarkup(    
            [["🏠 Menu"]],    
            resize_keyboard=True,    
            input_field_placeholder="Send link 🔗"    
        )
        await context.bot.send_message(
            chat_id=user.id,
            text="👍",
            reply_markup=setup_keyboard
        )

        await query.edit_message_text(
            get_trans(user.id, "welcome"),
            reply_markup=get_main_menu_keyboard(bot_username, user.id),
            parse_mode="HTML"
        )

    elif data == "cmd_change_lang":
        await query.edit_message_text(
            "<b>Please select your language / እባክዎ ቋንቋ ይምረጡ፦</b>",
            reply_markup=get_language_keyboard(),
            parse_mode="HTML"
        )

    elif data == "cmd_back":    
        await query.edit_message_text(    
            get_trans(user.id, "welcome"),    
            reply_markup=get_main_menu_keyboard(bot_username, user.id),    
            parse_mode="HTML"    
        )    

    elif data == "cmd_price":    
        await query.edit_message_text(    
            get_trans(user.id, "price"),    
            reply_markup=get_back_keyboard(user.id),    
            parse_mode="HTML"    
        )    

    elif data == "cmd_order":    
        await query.edit_message_text(    
            get_trans(user.id, "order"),    
            reply_markup=get_back_keyboard(user.id),    
            parse_mode="HTML"    
        )    

    elif data == "cmd_status":    
        total_users, user_msg_count = get_user_stats(user.id)    
        username_text = f"@{user.username}" if user.username else "የለውም"    

        msg = (    
            f'<tg-emoji emoji-id="5431577498364158238">📊</tg-emoji> <b>የእርስዎ እና የቦቱ Status</b>\n\n'    
            f'<tg-emoji emoji-id="5875078913725571378">👤</tg-emoji> <b>የግል መረጃዎት፦</b>\n'    
            f'<tg-emoji emoji-id="5465638272648617243">✈️</tg-emoji> <b>ስም:</b> {user.full_name}\n'    
            f'<tg-emoji emoji-id="5465638272648617243">✈️</tg-emoji> <b>Username:</b> {username_text}\n'    
            f'<tg-emoji emoji-id="5465638272648617243">✈️</tg-emoji> <b>Telegram ID:</b> <code>{user.id}</code>\n'    
            f'<tg-emoji emoji-id="5465638272648617243">✈️</tg-emoji> <b>የላኳቸው አጠቃላይ መልዕክቶች:</b> <code>{user_msg_count}</code>\n\n'    
                
            f'<tg-emoji emoji-id="5307979128543158051">🤖</tg-emoji> <b>የቦቱ አጠቃላይ መረጃ፦</b>\n'    
            f'<tg-emoji emoji-id="5465638272648617243">✈️</tg-emoji> <b>ሁኔታ:</b> Active <tg-emoji emoji-id="5307976826440687996">🔥</tg-emoji>\n'    
            f'<tg-emoji emoji-id="5465638272648617243">✈️</tg-emoji> <b>ጠቅላላ Users:</b> <code>{total_users}</code> <tg-emoji emoji-id="5305466057278923962">👥</tg-emoji>'    
        )    
            
        await query.edit_message_text(    
            msg,     
            reply_markup=get_back_keyboard(user.id),    
            parse_mode="HTML"    
        )    

    elif data == "cmd_payment":    
        await query.edit_message_text(    
            get_trans(user.id, "payment"),    
            reply_markup=get_back_keyboard(user.id),    
            parse_mode="HTML"    
        )    

    elif data == "cmd_support":    
        await query.edit_message_text(    
            get_trans(user.id, "support"),    
            reply_markup=get_back_keyboard(user.id),    
            parse_mode="HTML"    
        )

# ==================================================
# USER MESSAGES HANDLER
# ==================================================

async def handle_user_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user_id = update.effective_user.id    
    record_user_activity(user_id)    

    text = update.message.text or update.message.caption or ""    
        
    if text == "🏠 Menu":    
        await start(update, context)    
        return    

    valid_domains = [    
        "instagram.com", "tiktok.com", "youtube.com", "youtu.be",     
        "facebook.com", "fb.watch", "twitter.com", "x.com", "pinterest.com", "pin.it",    
        "reddit.com", "redd.it", "twitch.tv", "tumblr.com", "vimeo.com",     
        "threads.net", "soundcloud.com", "likee.video", "likee.com", "l.likee.video", "lk.video"    
    ]    
    is_supported_link = any(domain in text.lower() for domain in valid_domains)    

    if is_supported_link:    
        if not await is_joined(update, context):    
            await show_force_join(update, context)    
            return    

        url_match = re.search(r'https?://[^\s]+', text)    
        target_url = url_match.group(0) if url_match else text    
        await handle_url_download(update, context, target_url)    
        return    

    username = update.effective_user.username    
    username_text = f"@{username}" if username else "No Username"    

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

    forwarded_msg = await update.message.forward(chat_id=ADMIN_ID)    

    if "user_mapping" not in context.bot_data:    
        context.bot_data["user_mapping"] = {}    
        
    context.bot_data["user_mapping"][str(header_msg.message_id)] = user_id    
    context.bot_data["user_mapping"][str(forwarded_msg.message_id)] = user_id    

    await update.message.reply_text(    
        "✅ መልዕክትዎን ተቀብለናል።\n\n"    
        "📩 በቅርቡ እንመልስልዎታለን። ❤️"    
    )

# ==================================================
# ADMIN REPLY HANDLER
# ==================================================

async def admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if update.message and update.message.reply_to_message:    
        replied_msg = update.message.reply_to_message    
        target_user_id = None    
        user_mapping = context.bot_data.get("user_mapping", {})    

        replied_id_str = str(replied_msg.message_id)    
        if replied_id_str in user_mapping:    
            target_user_id = user_mapping[replied_id_str]    

        if not target_user_id and replied_msg.forward_from:    
            target_user_id = replied_msg.forward_from.id    

        if not target_user_id and replied_msg.text and "🆔 ID:" in replied_msg.text:    
            try:    
                user_id_str = replied_msg.text.split("🆔 ID:")[1].split()[0]    
                target_user_id = int(user_id_str.replace("<code>", "").replace("</code>", ""))    
            except Exception:    
                pass    

        if not target_user_id and replied_msg.caption and "🆔 ID:" in replied_msg.caption:    
            try:    
                user_id_str = replied_msg.caption.split("🆔 ID:")[1].split()[0]    
                target_user_id = int(user_id_str.replace("<code>", "").replace("</code>", ""))    
            except Exception:    
                pass    

        if target_user_id:    
            try:    
                await update.message.copy(chat_id=target_user_id)    
                await update.message.reply_text("✅ መልሱ ለተጠቃሚው ተልኳል!")    
            except Exception as e:    
                print("Reply Error:", e)    
                await update.message.reply_text("😭 መልሱን መላክ አልተቻለም። ተጠቃሚው ቦቱን ዘግቶት ሊሆን ይችላል።")    
        else:    
            await update.message.reply_text("⚠️ እባክዎ ከቀረቡት መልእክቶች Reply ያድርጉ።")

# ==================================================
# CHECK JOIN BUTTON
# ==================================================

async def check_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
                "🤖 አሁን /start የሚለውን ተጭነው ቦቱን ይጠቀሙ።",    
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

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print("❌ ERROR:", context.error)

# ==================================================
# MAIN EXECUTION
# ==================================================

def main():
    keep_alive()

    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()    

    # Commands Handlers    
    app.add_handler(CommandHandler("start", start))    
    app.add_handler(CommandHandler("menu", start))    
    app.add_handler(CommandHandler("status", status_command))    
    app.add_handler(CommandHandler("rates", rates_command))    
    app.add_handler(CommandHandler("rate", rates_command))    
    app.add_handler(CommandHandler("payment", payment_command))    
    app.add_handler(CommandHandler("help", help_command))    
    app.add_handler(CommandHandler("broadcast", broadcast_command))    

    app.add_handler(CallbackQueryHandler(check_join, pattern="^check_join$"))    
    app.add_handler(CallbackQueryHandler(button_callback, pattern="^(cmd_|lang_)"))    
        
    admin_filter = filters.User(user_id=ADMIN_ID) & filters.REPLY & ~filters.COMMAND    
    app.add_handler(MessageHandler(admin_filter, admin_reply))    
        
    app.add_handler(MessageHandler(filters.VIDEO | filters.VIDEO_NOTE, convert_video_to_audio))    

    type_filter = (    
        filters.TEXT | filters.PHOTO |     
        filters.Document.ALL | filters.VOICE | filters.AUDIO | filters.Sticker.ALL    
    ) & ~filters.COMMAND    
        
    app.add_handler(MessageHandler(type_filter, handle_user_messages))    
        
    app.add_error_handler(error_handler)    

    print("🤖 Mame Posts Bot is running...")    
    app.run_polling()

if __name__ == '__main__':
    main()
