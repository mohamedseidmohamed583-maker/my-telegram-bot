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
# ALL LANGUAGES BUTTONS & TEXTS TRANSLATIONS
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
        "done_msg": "✅ <b>ተጠናቋል! ቋንቋዎ ተስተካክሏል።</b>",
        "loading": '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> <b>Loading|ይጠብቁ...</b>',
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
        "done_msg": "✅ <b>Done! Your language has been set.</b>",
        "loading": '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> <b>Loading|Please wait...</b>',
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
        "btn_back": "العودة للقائمة",
        "done_msg": "✅ <b>تم! تم تعيين لغتك.</b>",
        "loading": '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> <b>جاري التحميل...</b>',
        "video_converted": '<tg-emoji emoji-id="5305534793935527938">🎵</tg-emoji> <b>الصوت المستخرج</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>تم التحويل بواسطة</b> @{bot_username}',
        "size_limit": "⚠️ <b>حجم الملف أكبر من 50 ميغابايت!</b>",
        "fail_download": "💔 <b>تعذر تحميل الملف!</b>",
        "photo_download": '📸 <b>الصورة المحملة</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>تم التحميل بواسطة</b> @{bot_username}',
        "welcome": 'مرحباً <tg-emoji emoji-id="5305577086478489521">🚨</tg-emoji>\n\nيمكنك تحميل الفيديوهات والصور.',
        "price": '<b>أسعار الإعلانات</b>',
        "order": '<b>للإعلان على القناة</b>',
        "payment": '<b>طرق الدفع</b>',
        "support": '<b>الدعم والتعليمات</b>'
    },
    "ru": {
        "btn_add": "Добавить бота в чат",
        "btn_order": "Заказать рекламу",
        "btn_price": "Цены и тарифы",
        "btn_payment": "Способ оплаты",
        "btn_status": "Мой статус",
        "btn_lang": "Language | Язык",
        "btn_support": "Помощь",
        "btn_back": "Назад",
        "done_msg": "✅ <b>Готово! Ваш язык установлен.</b>",
        "loading": '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> <b>Загрузка...</b>',
        "video_converted": 'Сконвертировано через @{bot_username}',
        "size_limit": "⚠️ <b>Файл превышает 50 МБ!</b>",
        "fail_download": "💔 <b>Не удалось скачать!</b>",
        "photo_download": 'Фото скачано',
        "welcome": 'Привет <tg-emoji emoji-id="5305577086478489521">🚨</tg-emoji>',
        "price": 'Цены',
        "order": 'Заказ рекламы',
        "payment": 'Оплата',
        "support": 'Помощь'
    },
    "fr": {
        "btn_add": "Ajouter le bot au groupe",
        "btn_order": "Publicité",
        "btn_price": "Tarifs",
        "btn_payment": "Mode de paiement",
        "btn_status": "Mon statut",
        "btn_lang": "Language | Langue",
        "btn_support": "Aide",
        "btn_back": "Retour",
        "done_msg": "✅ <b>Terminé ! Votre langue a été définie.</b>",
        "loading": 'Chargement...',
        "video_converted": 'Converti',
        "size_limit": "Limite de 50 Mo dépassée",
        "fail_download": "Échec",
        "photo_download": 'Photo',
        "welcome": 'Bonjour',
        "price": 'Tarifs',
        "order": 'Pub',
        "payment": 'Paiement',
        "support": 'Aide'
    },
    "es": {
        "btn_add": "Añadir bot al chat",
        "btn_order": "Publicidad",
        "btn_price": "Precios",
        "btn_payment": "Método de pago",
        "btn_status": "Mi estado",
        "btn_lang": "Language | Idioma",
        "btn_support": "Soporte",
        "btn_back": "Volver",
        "done_msg": "✅ <b>¡Listo! Tu idioma ha sido configurado.</b>",
        "loading": 'Cargando...',
        "video_converted": 'Convertido',
        "size_limit": 'Supera 50MB',
        "fail_download": 'Error',
        "photo_download": 'Foto',
        "welcome": 'Hola',
        "price": 'Precios',
        "order": 'Anuncio',
        "payment": 'Pago',
        "support": 'Soporte'
    },
    "fa": {
        "btn_add": "افزودن ربات به گروه",
        "btn_order": "سفارش تبلیغات",
        "btn_price": "قیمت‌ها",
        "btn_payment": "روش پرداخت",
        "btn_status": "وضعیت من",
        "btn_lang": "Language | زبان",
        "btn_support": "پشتیبانی",
        "btn_back": "بازگشت",
        "done_msg": "✅ <b>انجام شد! زبان شما تنظیم شد.</b>",
        "loading": 'در حال بارگذاری...',
        "video_converted": 'تبدیل شد',
        "size_limit": 'حجم بیش از حد',
        "fail_download": 'خطا',
        "photo_download": 'تصویر',
        "welcome": 'سلام',
        "price": 'قیمت',
        "order": 'تبلیغ',
        "payment": 'پرداخت',
        "support": 'پشتیبانی'
    },
    "hi": {
        "btn_add": "चैट में बोट जोड़ें",
        "btn_order": "विज्ञापन दें",
        "btn_price": "कीमत और दरें",
        "btn_payment": "भुगतान का तरीका",
        "btn_status": "मेरा स्टेटस",
        "btn_lang": "Language | भाषा",
        "btn_support": "सहायता",
        "btn_back": "वापस",
        "done_msg": "✅ <b>हो गया! आपकी भाषा सेट कर दी गई है।</b>",
        "loading": 'लोड हो रहा है...',
        "video_converted": 'कन्वर्ट किया गया',
        "size_limit": 'फाइल बड़ी है',
        "fail_download": 'त्रुटि',
        "photo_download": 'फोटो',
        "welcome": 'नमस्ते',
        "price": 'कीमत',
        "order": 'विज्ञापन',
        "payment": 'भुगतान',
        "support": 'सहायता'
    },
    "uz": {
        "btn_add": "Botni guruhga qo'shish",
        "btn_order": "Reklama berish",
        "btn_price": "Narxlar",
        "btn_payment": "To'lov usuli",
        "btn_status": "Mening statusim",
        "btn_lang": "Language | Til",
        "btn_support": "Yordam",
        "btn_back": "Qaytish",
        "done_msg": "✅ <b>Tayyor! Tilingiz o'rnatildi.</b>",
        "loading": 'Yuklanmoqda...',
        "video_converted": 'Konvert qilindi',
        "size_limit": 'Hajmi katta',
        "fail_download": 'Xato',
        "photo_download": 'Rasm',
        "welcome": 'Salom',
        "price": 'Narx',
        "order": 'Reklama',
        "payment": "To'lov",
        "support": 'Yordam'
    },
    "pt": {
        "btn_add": "Adicionar bot ao grupo",
        "btn_order": "Anunciar",
        "btn_price": "Preços",
        "btn_payment": "Método de pagamento",
        "btn_status": "Meu status",
        "btn_lang": "Language | Idioma",
        "btn_support": "Suporte",
        "btn_back": "Voltar",
        "done_msg": "✅ <b>Concluído! Seu idioma foi definido.</b>",
        "loading": 'Carregando...',
        "video_converted": 'Convertido',
        "size_limit": 'Arquivo grande',
        "fail_download": 'Falha',
        "photo_download": 'Foto',
        "welcome": 'Olá',
        "price": 'Preços',
        "order": 'Anúncio',
        "payment": 'Pagamento',
        "support": 'Suporte'
    },
    "zh": {
        "btn_add": "添加机器人到群组",
        "btn_order": "刊登广告",
        "btn_price": "价格与费率",
        "btn_payment": "付款方式",
        "btn_status": "我的状态",
        "btn_lang": "Language | 语言",
        "btn_support": "帮助与支持",
        "btn_back": "返回",
        "done_msg": "✅ <b>完成！您的语言已设置。</b>",
        "loading": '加载中...',
        "video_converted": '已转换',
        "size_limit": '文件过大',
        "fail_download": '失败',
        "photo_download": '照片',
        "welcome": '你好',
        "price": '价格',
        "order": '广告',
        "payment": '付款',
        "support": '支持'
    },
    "bn": {
        "btn_add": "বোট চ্যাটে যুক্ত করুন",
        "btn_order": "বিজ্ঞাপন দিন",
        "btn_price": "মূল্য এবং হার",
        "btn_payment": "পেমেন্ট মাধ্যম",
        "btn_status": "আমার স্ট্যাটাস",
        "btn_lang": "Language | ভাষা",
        "btn_support": "সহায়তা",
        "btn_back": "ফিরে যান",
        "done_msg": "✅ <b>সম্পন্ন হয়েছে! আপনার ভাষা সেট করা হয়েছে।</b>",
        "loading": 'লোড হচ্ছে...',
        "video_converted": 'রূপান্তরিত',
        "size_limit": 'বড় ফাইল',
        "fail_download": 'ব্যর্থ',
        "photo_download": 'ছবি',
        "welcome": 'হ্যালো',
        "price": 'মূল্য',
        "order": 'বিজ্ঞাপন',
        "payment": 'পেমেন্ট',
        "support": 'সহায়তা'
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
        "done_msg": "✅ <b>Selesai! Bahasa Anda telah disetel.</b>",
        "loading": 'Memuat...',
        "video_converted": 'Dikonversi',
        "size_limit": 'File terlalu besar',
        "fail_download": 'Gagal',
        "photo_download": 'Foto',
        "welcome": 'Halo',
        "price": 'Harga',
        "order": 'Iklan',
        "payment": 'Pembayaran',
        "support": 'Bantuan'
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
        "done_msg": "✅ <b>Fertig! Ihre Sprache wurde eingestellt.</b>",
        "loading": 'Laden...',
        "video_converted": 'Konvertiert',
        "size_limit": 'Datei zu groß',
        "fail_download": 'Fehler',
        "photo_download": 'Foto',
        "welcome": 'Hallo',
        "price": 'Preise',
        "order": 'Werbung',
        "payment": 'Zahlung',
        "support": 'Hilfe'
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
        "done_msg": "✅ <b>Готово! Вашу мову встановлено.</b>",
        "loading": 'Завантаження...',
        "video_converted": 'Конвертовано',
        "size_limit": 'Великий файл',
        "fail_download": 'Помилка',
        "photo_download": 'Фото',
        "welcome": 'Привіт',
        "price": 'Ціни',
        "order": 'Реклама',
        "payment": 'Оплата',
        "support": 'Допомога'
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
        "done_msg": "✅ <b>Tamamlandı! Diliniz ayarlandı.</b>",
        "loading": 'Yükleniyor...',
        "video_converted": 'Dönüştürüldü',
        "size_limit": 'Dosya büyük',
        "fail_download": 'Hata',
        "photo_download": 'Fotoğraf',
        "welcome": 'Merhaba',
        "price": 'Fiyatlar',
        "order": 'Reklam',
        "payment": 'Ödeme',
        "support": 'Destek'
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
        "done_msg": "✅ <b>완료되었습니다! 언어가 설정되었습니다.</b>",
        "loading": '로딩 중...',
        "video_converted": '변환됨',
        "size_limit": '파일이 큽니다',
        "fail_download": '실패',
        "photo_download": '사진',
        "welcome": '안녕하세요',
        "price": '가격',
        "order": '광고',
        "payment": '결제',
        "support": '지원'
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
        "done_msg": "✅ <b>Fatto! La tua lingua è stata impostata.</b>",
        "loading": 'Caricamento...',
        "video_converted": 'Convertito',
        "size_limit": 'File troppo grande',
        "fail_download": 'Errore',
        "photo_download": 'Foto',
        "welcome": 'Ciao',
        "price": 'Prezzi',
        "order": 'Pubblicità',
        "payment": 'Pagamento',
        "support": 'Supporto'
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
        "done_msg": "✅ <b>Gotowe! Twój język został ustawiony.</b>",
        "loading": 'Ładowanie...',
        "video_converted": 'Skonwertowano',
        "size_limit": 'Za duжий plik',
        "fail_download": 'Błąd',
        "photo_download": 'Zdjęcie',
        "welcome": 'Cześć',
        "price": 'Cennik',
        "order": 'Reklama',
        "payment": 'Płatność',
        "support": 'Pomoc'
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
        "done_msg": "✅ <b>Hoàn tất! Ngôn ngữ của bạn đã được đặt.</b>",
        "loading": 'Đang tải...',
        "video_converted": 'Đã chuyển đổi',
        "size_limit": 'Tệp quá lớn',
        "fail_download": 'Lỗi',
        "photo_download": 'Ảnh',
        "welcome": 'Xin chào',
        "price": 'Giá',
        "order": 'Quảng cáo',
        "payment": 'Thanh toán',
        "support": 'Hỗ trợ'
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
        "done_msg": "✅ <b>Дайын! Тіліңіз орнатылды.</b>",
        "loading": 'Жүктелуде...',
        "video_converted": 'Айырбасталды',
        "size_limit": 'Файл тым үлкен',
        "fail_download": 'Қате',
        "photo_download": 'Сурет',
        "welcome": 'Сәлем',
        "price": 'Бағалар',
        "order": 'Жарнама',
        "payment": 'Төлем',
        "support": 'Көмек'
    }
}

def get_trans(user_id, key):
    lang = get_user_language(user_id)
    if not lang or lang not in TRANSLATIONS:
        lang = "am"
    lang_dict = TRANSLATIONS.get(lang, TRANSLATIONS["am"])
    return lang_dict.get(key, TRANSLATIONS["am"].get(key, ""))

# ==================================================
# MAIN MENU KEYBOARD (በሁሉም ቋንቋዎች የተስተካከለ)
# ==================================================

def get_main_menu_keyboard(bot_username):
    keyboard = [
        [
            InlineKeyboardButton(
                text="Add a bot to the chat",
                icon_custom_emoji_id="5305545479814161889",
                url=f"https://t.me/{bot_username}?startgroup=true"
            )
        ],
        [
            InlineKeyboardButton(
                text="ማስታወቂያ ለማሰራት",
                icon_custom_emoji_id="5267442591548320083",
                callback_data="cmd_order"
            )
        ],
        [
            InlineKeyboardButton(
                text="Price | ዋጋ",
                icon_custom_emoji_id="5447458260200214425",
                callback_data="cmd_price"
            ),
            InlineKeyboardButton(
                text="Payment Method",
                icon_custom_emoji_id="5186349709169525403",
                callback_data="cmd_payment"
            )
        ],
        [
            InlineKeyboardButton(
                text="My Status & Stats",
                icon_custom_emoji_id="5431577498364158238",
                callback_data="cmd_status"
            )
        ],
        [
            InlineKeyboardButton(
                text="Support | ድጋፍ",
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
# START & MENU COMMAND
# ==================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    record_user_activity(user_id)

    bot_username = context.bot.username or "mame_posts_bot"
    user_lang = get_user_language(user_id)

    setup_keyboard = ReplyKeyboardMarkup(    
        [["🏠 Menu"]],    
        resize_keyboard=True,    
        input_field_placeholder="Send link 🔗"    
    )

    if not user_lang:
        await update.message.reply_text(
            "<b>Please select your language / እባክዎ ቋንቋ ይምረጡ፦</b>",
            reply_markup=get_language_keyboard(),
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(    
            "<b> @ads_poster1bot !</b>",    
            reply_markup=setup_keyboard,    
            parse_mode="HTML"    
        )    
        await update.message.reply_text(    
            get_trans(user_id, "welcome"),    
            reply_markup=get_main_menu_keyboard(bot_username, user_id),    
            parse_mode="HTML"    
        )

# ==================================================
# MENU BUTTON HANDLER (ለ '🏠 Menu' የተለየ ተግባር)
# ==================================================

async def menu_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    record_user_activity(user_id)
    bot_username = context.bot.username or "mame_posts_bot"
    user_lang = get_user_language(user_id)

    setup_keyboard = ReplyKeyboardMarkup(    
        [["🏠 Menu"]],    
        resize_keyboard=True,    
        input_field_placeholder="Send link 🔗"    
    )

    if not user_lang:
        await update.message.reply_text(
            "<b>Please select your language / እባክዎ ቋንቋ ይምረጡ፦</b>",
            reply_markup=get_language_keyboard(),
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(    
            "<b> @ads_poster1bot !</b>",    
            reply_markup=setup_keyboard,    
            parse_mode="HTML"    
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
            bot_username = context.bot.username or "mame_posts_bot"    
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
        'format': 'bestvideo+bestaudio/best',
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

    if "youtube.com" in url or "youtu.be" in url:
        opts['extractor_args'] = {
            'youtube': {
                'player_client': ['android', 'ios', 'web']
            }
        }
        opts['format'] = 'b/bv*+ba/best'
    elif "likee" in url or "likee.video" in url:
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

    bot_username = context.bot.username or "mame_posts_bot"    
    share_url = f"https://t.me/share/url?url=https://t.me/{bot_username}?start=share&text=Try%20this%20awesome%20Downloader%20Bot!🔥"    
    reply_markup_share = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Share Bot 🚀", url=share_url)]])    

    url = clean_url(raw_url)    

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
                            caption=f'<tg-emoji emoji-id="530762354187772738">🚀</tg-emoji> <b>Downloaded with</b> @{bot_username} & @mame_posts\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Enjoy!</b>',    
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
                                caption=f'<tg-emoji emoji-id="5307705891313721642">🎧</tg-emoji> <b>Extracted Audio (MP3)</b>\n\n<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Downloaded with</b> @{bot_username}',    
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
    bot_username = context.bot.username or "mame_posts_bot"

    if data.startswith("lang_"):
        lang_code = data.split("_")[1]
        set_user_language(user.id, lang_code)
        
        setup_keyboard = ReplyKeyboardMarkup(    
            [["🏠 Menu"]],    
            resize_keyboard=True,    
            input_field_placeholder="Send link 🔗"    
        )
        
        try:
            await query.message.delete()
        except Exception:
            pass

        done_text = get_trans(user.id, "done_msg")
        await context.bot.send_message(
            chat_id=user.id,
            text=done_text,
            reply_markup=setup_keyboard,
            parse_mode="HTML"
        )

        await context.bot.send_message(
            chat_id=user.id,
            text=get_trans(user.id, "welcome"),
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
        await menu_button_handler(update, context)    
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
