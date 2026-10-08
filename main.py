import os
import re
import json
import asyncio
import subprocess
import requests
import static_ffmpeg

static_ffmpeg.add_paths()

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
# FLASK WEB SERVER
# ============================================================

app_web = Flask(__name__)


@app_web.route("/")
def home():
    return "Bot is Alive!"


def run_web():
    port = int(os.environ.get("PORT", 10000))
    app_web.run(
        host="0.0.0.0",
        port=port
    )


def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()


# ============================================================
# CONFIGURATION
# ============================================================

TOKEN = os.environ.get("BOT_TOKEN")

ADMIN_ID = int(
    os.environ.get(
        "ADMIN_ID",
        6753546651
    )
)

FORCE_CHANNEL = "@mame_posts"

FORCE_CHANNEL_LINK = "https://t.me/mame_posts"


# ============================================================
# DATABASE MANAGEMENT
# ============================================================

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
            json.dump(
                data,
                f,
                ensure_ascii=False,
                indent=2
            )

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

    data[uid_str]["msg_count"] = (
        data[uid_str].get("msg_count", 0) + 1
    )

    data[uid_str]["started"] = True

    save_data(data)


def set_user_language(user_id, lang_code):
    data = load_data()

    uid_str = str(user_id)

    if uid_str not in data:
        data[uid_str] = {
            "msg_count": 1,
            "started": True,
            "lang": lang_code
        }

    else:
        data[uid_str]["lang"] = lang_code

    save_data(data)


def get_user_language(user_id):
    data = load_data()

    return data.get(
        str(user_id),
        {}
    ).get(
        "lang",
        None
    )


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


# ============================================================
# TRANSLATIONS
# ============================================================

TRANSLATIONS = {

    # ========================================================
    # AMHARIC
    # ========================================================

    "am": {
        "btn_add": "Add a bot to the chat",
        "btn_order": "ማስታወቂያ ለማሰራት",
        "btn_price": "Price | ዋጋ",
        "btn_payment": "Payment Method",
        "btn_status": "My Status & Stats",
        "btn_lang": "Language | ቋንቋ",
        "btn_support": "Support | ድጋፍ",
        "btn_back": "Back to Menu",

        "done_msg":
            "✅ <b>ተጠናቋል! ቋንቋዎ ተስተካክሏል።</b>",

        "loading":
            '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> '
            '<b>Loading|ይጠብቁ...</b>',

        "video_converted":
            '<tg-emoji emoji-id="5305534793935527938">🎵</tg-emoji> '
            '<b>ከቪዲዮ የተቀየረው (Extracted Audio)</b>\n\n'
            '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> '
            '<b>Converted with</b> @{bot_username} & @mame_posts',

        "size_limit":
            "⚠️ <b>ቪዲዮው ከ 50MB በላይ ስለሆነ "
            "በቴሌግራም መላክ አይቻልም!</b>",

        "fail_download":
            "💔 <b> የፈለጉትን File ማግኘት አልቻልኩም!</b>\n\n"
            "እባክዎ የላኩት ሊንክ private አለመሆኑን "
            "አረጋግጠው እንደገና ይሞክሩ።",

        "photo_download":
            '📸 <b>Downloaded Photo</b>\n\n'
            '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> '
            '<b>Downloaded with</b> @{bot_username}',

        "welcome": (
            'Hello <tg-emoji emoji-id="5305577086478489521">🚨</tg-emoji>\n\n'

            '<tg-emoji emoji-id="5305739801314501775">✅</tg-emoji> '
            '<b>My options (ከሁሉም Social Media ላይ video, photo እና '
            'audio ማውረድና መቀየር ይችላሉ!) :</b>\n\n'

            '<tg-emoji emoji-id="5305290882742788410">🎵</tg-emoji> | '
            '<b>Tiktok & Likee: videos & photos</b>\n'

            '<tg-emoji emoji-id="5305551797711053969">📸</tg-emoji> | '
            '<b>Pinterest & Instagram: reels, photos & stories</b>\n'

            '<tg-emoji emoji-id="5305777524012262308">▶️</tg-emoji> | '
            '<b>YouTube: videos & music (Full & Shorts)</b>\n'

            '<tg-emoji emoji-id="5305474827602140530">✖️</tg-emoji> | '
            '<b>Twitter (X): videos & voice</b>\n'

            '<tg-emoji emoji-id="5305311717629142471">📘</tg-emoji> | '
            '<b>Facebook, Reddit, Twitch, Vimeo & Others</b>\n'

            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> '
            '<b>Video to Audio Converter: ቪዲዮ ወደ ኦዲዮ '
            'መቀየር ይችላሉ! </b>\n\n'

            '<b>And others Social Media | ሌሎችንም ሶሻል ሚድያ '
            'ማውረድ ይችላሉ!:</b> '
            '<tg-emoji emoji-id="5305466057278923962">📥</tg-emoji>'
        ),

        "price": (
            '<tg-emoji emoji-id="5447458260200214425">💰</tg-emoji> '
            '<b>የማስታወቂያ ዋጋዎች</b>\n\n'

            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> '
            '12 Hours — <b>በስምምነት ETB</b>\n'

            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> '
            '24 Hours — <b>500 ETB</b>\n'

            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> '
            '48 Hours — <b>700 ETB</b>\n\n'

            'የፈለጉትን ምርጫ አሳውቀው የክፍያ አማራጮችን '
            '(payment method) ይጎብኙ '
            '<tg-emoji emoji-id="5463249828450424568">🤝</tg-emoji>'
        ),

        "order": (
            '<tg-emoji emoji-id="5197304993920616826">📢</tg-emoji> '
            '<b> @mame_posts ቻናል ላይ ማስታወቂያ ለማሰራት</b>\n\n'

            '<tg-emoji emoji-id="5305634553140912174">👇</tg-emoji> '
            'እባክዎ ማስታወቂያ ማሰራት የሚፈልጉትን Post '
            'ከስር ልከው የማስታወቂያ ዋጋዎችን ይመልከቱ '
            '<tg-emoji emoji-id="5305739801314501775">ℹ️</tg-emoji>'
        ),

        "payment": (
            '<tg-emoji emoji-id="5186349709169525403">💳</tg-emoji> '
            '<b>Payment Method</b>\n\n'

            '<tg-emoji emoji-id="5961054379350955385">🏦</tg-emoji> '
            '<b>ንግድ ባንክ (CBE)</b>\n'

            '<code>1000528274394</code>\n\n'

            'Mohammed Seid\n\n'

            '<tg-emoji emoji-id="5960632377339285724">📱</tg-emoji> '
            '<b>ቴሌ ብር (TELE BIRR)</b>\n'

            '<code>+251963266849</code>\n\n'

            '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> '
            '<b>ክፍያውን ሲፈጽሙ ስክሪን ሹቱን ከስር ይላኩ!</b>'
        ),

        "support": (
            '<tg-emoji emoji-id="5305545479814161889">💬</tg-emoji> '
            '<b>Support & Downloader Help</b>\n\n'

            '<tg-emoji emoji-id="5305655375142364109">📺</tg-emoji> '
            '<b>ቪዲዮ/ፎቶ ለማውረድ:</b> የ Tiktok, Instagram, '
            'Facebook, Reddit, Twitch, Vimeo, SoundCloud, Threads '
            'እና ሌሎች ሊንክ ቀጥታ ለቦቱ ይላኩ።\n\n'

            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> '
            '<b>Video to Audio:</b> ማናቸውንም ቪዲዮ ከስልክዎ ይላኩ፣ '
            'ወደ MP3 Audio ቀይሮ ይልክልዎታል።\n\n'

            '<tg-emoji emoji-id="5949327894567195412">👩‍💻</tg-emoji> '
            'ለአድሚን መልዕክት ለመላክም እዚሁ መጻፍ ይችላሉ።'
        )
    },


    # ========================================================
    # ENGLISH
    # ========================================================

    "en": {
        "btn_add": "Add a bot to the chat",
        "btn_order": "Promote / Advertise",
        "btn_price": "Price & Rates",
        "btn_payment": "Payment Method",
        "btn_status": "My Status & Stats",
        "btn_lang": "Language | ቋንቋ",
        "btn_support": "Support & Help",
        "btn_back": "Back to Menu",

        "done_msg":
            "✅ <b>Done! Your language has been set.</b>",

        "loading":
            '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> '
            '<b>Loading|Please wait...</b>',

        "video_converted":
            '<tg-emoji emoji-id="5305534793935527938">🎵</tg-emoji> '
            '<b>Extracted Audio</b>\n\n'
            '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> '
            '<b>Converted with</b> @{bot_username}',

        "size_limit":
            "⚠️ <b>File is larger than 50MB! Telegram limit exceeded.</b>",

        "fail_download":
            "💔 <b>Could not download the file! "
            "Please check if link is public.</b>",

        "photo_download":
            '📸 <b>Downloaded Photo</b>\n\n'
            '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> '
            '<b>Downloaded with</b> @{bot_username}',

        "welcome": (
            'Hello <tg-emoji emoji-id="5305577086478489521">🚨</tg-emoji>\n\n'

            '<tg-emoji emoji-id="5305739801314501775">✅</tg-emoji> '
            '<b>My options (You can download video, photo, and audio '
            'from all Social Media):</b>\n\n'

            '<tg-emoji emoji-id="5305290882742788410">🎵</tg-emoji> | '
            '<b>Tiktok & Likee: videos & photos</b>\n'

            '<tg-emoji emoji-id="5305551797711053969">📸</tg-emoji> | '
            '<b>Pinterest & Instagram: reels, photos & stories</b>\n'

            '<tg-emoji emoji-id="5305777524012262308">▶️</tg-emoji> | '
            '<b>YouTube: videos & music (Full & Shorts)</b>\n'

            '<tg-emoji emoji-id="5305474827602140530">✖️</tg-emoji> | '
            '<b>Twitter (X): videos & voice</b>\n'

            '<tg-emoji emoji-id="5305311717629142471">📘</tg-emoji> | '
            '<b>Facebook, Reddit, Twitch, Vimeo & Others</b>\n'

            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> '
            '<b>Video to Audio Converter: Convert video to audio!</b>\n\n'

            '<b>And other Social Media:</b> '
            '<tg-emoji emoji-id="5305466057278923962">📥</tg-emoji>'
        ),

        "price": (
            '<tg-emoji emoji-id="5447458260200214425">💰</tg-emoji> '
            '<b>Advertising Rates</b>\n\n'

            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> '
            '12 Hours — <b>Negotiable ETB</b>\n'

            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> '
            '24 Hours — <b>500 ETB</b>\n'

            '<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> '
            '48 Hours — <b>700 ETB</b>\n\n'

            'Choose your plan and proceed to Payment Method '
            '<tg-emoji emoji-id="5463249828450424568">🤝</tg-emoji>'
        ),

        "order": (
            '<tg-emoji emoji-id="5197304993920616826">📢</tg-emoji> '
            '<b>To Advertise on @mame_posts Channel</b>\n\n'

            '<tg-emoji emoji-id="5305634553140912174">👇</tg-emoji> '
            'Please send your promo post below and view our rates '
            '<tg-emoji emoji-id="5305739801314501775">ℹ️</tg-emoji>'
        ),

        "payment": (
            '<tg-emoji emoji-id="5186349709169525403">💳</tg-emoji> '
            '<b>Payment Method</b>\n\n'

            '<tg-emoji emoji-id="5961054379350955385">🏦</tg-emoji> '
            '<b>Commercial Bank of Ethiopia (CBE)</b>\n'

            '<code>1000528274394</code>\n\n'

            'Mohammed Seid\n\n'

            '<tg-emoji emoji-id="5960632377339285724">📱</tg-emoji> '
            '<b>TELEBIRR</b>\n'

            '<code>+251963266849</code>\n\n'

            '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> '
            '<b>Please send receipt screenshot after payment!</b>'
        ),

        "support": (
            '<tg-emoji emoji-id="5305545479814161889">💬</tg-emoji> '
            '<b>Support & Downloader Help</b>\n\n'

            '<tg-emoji emoji-id="5305655375142364109">📺</tg-emoji> '
            '<b>To Download Video/Photo:</b> Send links from Tiktok, '
            'Instagram, Facebook, Reddit, Twitch, Vimeo, SoundCloud, '
            'Threads, etc.\n\n'

            '<tg-emoji emoji-id="5305289658677108341">📹</tg-emoji> '
            '<b>Video to Audio:</b> Send any video to convert it to MP3 audio.\n\n'

            '<tg-emoji emoji-id="5949327894567195412">👩‍💻</tg-emoji> '
            'You can write messages here to reach out to the Admin.'
        )
    },


    # ========================================================
    # ARABIC
    # ========================================================

    "ar": {
        "btn_add": "إضافة البوت إلى المجموعة",
        "btn_order": "طلب إعلان",
        "btn_price": "أسعار الإعلانات",
        "btn_payment": "طرق الدفع",
        "btn_status": "حسابي وإحصائياتي",
        "btn_lang": "Language | ቋንቋ",
        "btn_support": "الدعم والتعليمات",
        "btn_back": "العودة للقائمة",

        "done_msg":
            "✅ <b>تم! تم تعيين لغتك.</b>",

        "loading":
            '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> '
            '<b>جاري التحميل...</b>',

        "video_converted":
            '<tg-emoji emoji-id="5305534793935527938">🎵</tg-emoji> '
            '<b>الصوت المستخرج</b>\n\n'
            '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> '
            '<b>تم التحويل بواسطة</b> @{bot_username}',

        "size_limit":
            "⚠️ <b>حجم الملف أكبر من 50 ميغابايت!</b>",

        "fail_download":
            "💔 <b>تعذر تحميل الملف!</b>",

        "photo_download":
            '📸 <b>الصورة المحملة</b>\n\n'
            '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> '
            '<b>تم التحميل بواسطة</b> @{bot_username}',

        "welcome":
            'مرحباً <tg-emoji emoji-id="5305577086478489521">🚨</tg-emoji>\n\n'
            'يمكنك تحميل الفيديوهات والصور.',

        "price":
            '<b>أسعار الإعلانات</b>',

        "order":
            '<b>للإعلان على القناة</b>',

        "payment":
            '<b>طرق الدفع</b>',

        "support":
            '<b>الدعم والتعليمات</b>'
    },


    # ========================================================
    # RUSSIAN
    # ========================================================

    "ru": {
        "btn_add": "Добавить бота в чат",
        "btn_order": "Заказать рекламу",
        "btn_price": "Цены и тарифы",
        "btn_payment": "Способ оплаты",
        "btn_status": "Мой статус",
        "btn_lang": "Language | Язык",
        "btn_support": "Помощь",
        "btn_back": "Назад",

        "done_msg":
            "✅ <b>Готово! Ваш язык установлен.</b>",

        "loading":
            '<tg-emoji emoji-id="5305254783542667121">⏳</tg-emoji> '
            '<b>Загрузка...</b>',

        "video_converted":
            'Сконвертировано через @{bot_username}',

        "size_limit":
            "⚠️ <b>Файл превышает 50 МБ!</b>",

        "fail_download":
            "💔 <b>Не удалось скачать!</b>",

        "photo_download":
            'Фото скачано',

        "welcome":
            'Привет <tg-emoji emoji-id="5305577086478489521">🚨</tg-emoji>',

        "price":
            'Цены',

        "order":
            'Заказ рекламы',

        "payment":
            'Оплата',

        "support":
            'Помощь'
    },


    # ========================================================
    # FRENCH
    # ========================================================

    "fr": {
        "btn_add": "Ajouter le bot au groupe",
        "btn_order": "Publicité",
        "btn_price": "Tarifs",
        "btn_payment": "Mode de paiement",
        "btn_status": "Mon statut",
        "btn_lang": "Language | Langue",
        "btn_support": "Aide",
        "btn_back": "Retour",

        "done_msg":
            "✅ <b>Terminé ! Votre langue a été définie.</b>",

        "loading": "Chargement...",
        "video_converted": "Converti",
        "size_limit": "Limite de 50 Mo dépassée",
        "fail_download": "Échec",
        "photo_download": "Photo",
        "welcome": "Bonjour",
        "price": "Tarifs",
        "order": "Pub",
        "payment": "Paiement",
        "support": "Aide"
    },


    # ========================================================
    # SPANISH
    # ========================================================

    "es": {
        "btn_add": "Añadir bot al chat",
        "btn_order": "Publicidad",
        "btn_price": "Precios",
        "btn_payment": "Método de pago",
        "btn_status": "Mi estado",
        "btn_lang": "Language | Idioma",
        "btn_support": "Soporte",
        "btn_back": "Volver",
        "done_msg":
            "✅ <b>¡Listo! Tu idioma ha sido configurado.</b>",
        "loading": "Cargando...",
        "video_converted": "Convertido",
        "size_limit": "Supera 50MB",
        "fail_download": "Error",
        "photo_download": "Foto",
        "welcome": "Hola",
        "price": "Precios",
        "order": "Anuncio",
        "payment": "Pago",
        "support": "Soporte"
    },


    # ========================================================
    # PERSIAN
    # ========================================================

    "fa": {
        "btn_add": "افزودن ربات به گروه",
        "btn_order": "سفارش تبلیغات",
        "btn_price": "قیمت‌ها",
        "btn_payment": "روش پرداخت",
        "btn_status": "وضعیت من",
        "btn_lang": "Language | زبان",
        "btn_support": "پشتیبانی",
        "btn_back": "بازگشت",
        "done_msg":
            "✅ <b>انجام شد! زبان شما تنظیم شد.</b>",
        "loading": "در حال بارگذاری...",
        "video_converted": "تبدیل شد",
        "size_limit": "حجم بیش از حد",
        "fail_download": "خطا",
        "photo_download": "تصویر",
        "welcome": "سلام",
        "price": "قیمت",
        "order": "تبلیغ",
        "payment": "پرداخت",
        "support": "پشتیبانی"
    },


    # ========================================================
    # HINDI
    # ========================================================

    "hi": {
        "btn_add": "चैट में बोट जोड़ें",
        "btn_order": "विज्ञापन दें",
        "btn_price": "कीमत और दरें",
        "btn_payment": "भुगतान का तरीका",
        "btn_status": "मेरा स्टेटस",
        "btn_lang": "Language | भाषा",
        "btn_support": "सहायता",
        "btn_back": "वापस",
        "done_msg":
            "✅ <b>हो गया! आपकी भाषा सेट कर दी गई है।</b>",
        "loading": "लोड हो रहा है...",
        "video_converted": "कन्वर्ट किया गया",
        "size_limit": "फाइल बड़ी है",
        "fail_download": "त्रुटि",
        "photo_download": "फोटो",
        "welcome": "नमस्ते",
        "price": "कीमत",
        "order": "विज्ञापन",
        "payment": "भुगतान",
        "support": "सहायता"
    },


    # ========================================================
    # UZBEK
    # ========================================================

    "uz": {
        "btn_add": "Botni guruhga qo'shish",
        "btn_order": "Reklama berish",
        "btn_price": "Narxlar",
        "btn_payment": "To'lov usuli",
        "btn_status": "Mening statusim",
        "btn_lang": "Language | Til",
        "btn_support": "Yordam",
        "btn_back": "Qaytish",
        "done_msg":
            "✅ <b>Tayyor! Tilingiz o'rnatildi.</b>",
        "loading": "Yuklanmoqda...",
        "video_converted": "Konvert qilindi",
        "size_limit": "Hajmi katta",
        "fail_download": "Xato",
        "photo_download": "Rasm",
        "welcome": "Salom",
        "price": "Narx",
        "order": "Reklama",
        "payment": "To'lov",
        "support": "Yordam"
    },


    # ========================================================
    # PORTUGUESE
    # ========================================================

    "pt": {
        "btn_add": "Adicionar bot ao grupo",
        "btn_order": "Anunciar",
        "btn_price": "Preços",
        "btn_payment": "Método de pagamento",
        "btn_status": "Meu status",
        "btn_lang": "Language | Idioma",
        "btn_support": "Suporte",
        "btn_back": "Voltar",
        "done_msg":
            "✅ <b>Concluído! Seu idioma foi definido.</b>",
        "loading": "Carregando...",
        "video_converted": "Convertido",
        "size_limit": "Arquivo grande",
        "fail_download": "Falha",
        "photo_download": "Foto",
        "welcome": "Olá",
        "price": "Preços",
        "order": "Anúncio",
        "payment": "Pagamento",
        "support": "Suporte"
    },


    # ========================================================
    # CHINESE
    # ========================================================

    "zh": {
        "btn_add": "添加机器人到群组",
        "btn_order": "刊登广告",
        "btn_price": "价格与费率",
        "btn_payment": "付款方式",
        "btn_status": "我的状态",
        "btn_lang": "Language | 语言",
        "btn_support": "帮助与支持",
        "btn_back": "返回",
        "done_msg":
            "✅ <b>完成！您的语言已设置。</b>",
        "loading": "加载中...",
        "video_converted": "已转换",
        "size_limit": "文件过大",
        "fail_download": "失败",
        "photo_download": "照片",
        "welcome": "你好",
        "price": "价格",
        "order": "广告",
        "payment": "付款",
        "support": "支持"
    },


    # ========================================================
    # BENGALI
    # ========================================================

    "bn": {
        "btn_add": "বোট চ্যাটে যুক্ত করুন",
        "btn_order": "বিজ্ঞাপন দিন",
        "btn_price": "মূল্য এবং হার",
        "btn_payment": "পেমেন্ট মাধ্যম",
        "btn_status": "আমার স্ট্যাটাস",
        "btn_lang": "Language | ভাষা",
        "btn_support": "সহায়তা",
        "btn_back": "ফিরে যান",
        "done_msg":
            "✅ <b>সম্পন্ন হয়েছে! আপনার ভাষা সেট করা হয়েছে।</b>",
        "loading": "লোড হচ্ছে...",
        "video_converted": "রূপান্তরিত",
        "size_limit": "বড় ফাইল",
        "fail_download": "ব্যর্থ",
        "photo_download": "ছবি",
        "welcome": "হ্যালো",
        "price": "মূল্য",
        "order": "বিজ্ঞাপন",
        "payment": "পেমেন্ট",
        "support": "সহায়তা"
    },


    # ========================================================
    # INDONESIAN
    # ========================================================

    "id": {
        "btn_add": "Tambahkan bot ke grup",
        "btn_order": "Iklan",
        "btn_price": "Harga & Tarif",
        "btn_payment": "Metode Pembayaran",
        "btn_status": "Status Saya",
        "btn_lang": "Language | Bahasa",
        "btn_support": "Bantuan",
        "btn_back": "Kembali",
        "done_msg":
            "✅ <b>Selesai! Bahasa Anda telah disetel.</b>",
        "loading": "Memuat...",
        "video_converted": "Dikonversi",
        "size_limit": "File terlalu besar",
        "fail_download": "Gagal",
        "photo_download": "Foto",
        "welcome": "Halo",
        "price": "Harga",
        "order": "Iklan",
        "payment": "Pembayaran",
        "support": "Bantuan"
    },


    # ========================================================
    # GERMAN
    # ========================================================

    "de": {
        "btn_add": "Bot zur Gruppe hinzufügen",
        "btn_order": "Werbung buchen",
        "btn_price": "Preise",
        "btn_payment": "Zahlungsmethode",
        "btn_status": "Mein Status",
        "btn_lang": "Language | Sprache",
        "btn_support": "Hilfe",
        "btn_back": "Zurück",
        "done_msg":
            "✅ <b>Fertig! Ihre Sprache wurde eingestellt.</b>",
        "loading": "Laden...",
        "video_converted": "Konvertiert",
        "size_limit": "Datei zu groß",
        "fail_download": "Fehler",
        "photo_download": "Foto",
        "welcome": "Hallo",
        "price": "Preise",
        "order": "Werbung",
        "payment": "Zahlung",
        "support": "Hilfe"
    },


    # ========================================================
    # UKRAINIAN
    # ========================================================

    "uk": {
        "btn_add": "Додати бота в чат",
        "btn_order": "Замовити рекламу",
        "btn_price": "Ціни та тарифи",
        "btn_payment": "Спосіб оплати",
        "btn_status": "Мій статус",
        "btn_lang": "Language | Мова",
        "btn_support": "Допомога",
        "btn_back": "Назад",
        "done_msg":
            "✅ <b>Готово! Вашу мову встановлено.</b>",
        "loading": "Завантаження...",
        "video_converted": "Конвертовано",
        "size_limit": "Великий файл",
        "fail_download": "Помилка",
        "photo_download": "Фото",
        "welcome": "Привіт",
        "price": "Ціни",
        "order": "Реклама",
        "payment": "Оплата",
        "support": "Допомога"
    },


    # ========================================================
    # TURKISH
    # ========================================================

    "tr": {
        "btn_add": "Botu gruba ekle",
        "btn_order": "Reklam ver",
        "btn_price": "Fiyatlar",
        "btn_payment": "Ödeme Yöntemi",
        "btn_status": "Durumum",
        "btn_lang": "Language | Dil",
        "btn_support": "Destek",
        "btn_back": "Geri",
        "done_msg":
            "✅ <b>Tamamlandı! Diliniz ayarlandı.</b>",
        "loading": "Yükleniyor",
        "video_converted": "Dönüştürüldü",
        "size_limit": "Dosya büyük",
        "fail_download": "Hata",
        "photo_download": "Fotoğraf",
        "welcome": "Merhaba",
        "price": "Fiyatlar",
        "order": "Reklam",
        "payment": "Ödeme",
        "support": "Destek"
    },


    # ========================================================
    # KOREAN
    # ========================================================

    "ko": {
        "btn_add": "그룹에 봇 추가",
        "btn_order": "광고 문의",
        "btn_price": "가격 및 요금",
        "btn_payment": "결제 방법",
        "btn_status": "내 상태",
        "btn_lang": "Language | 언어",
        "btn_support": "지원",
        "btn_back": "돌아가기",
        "done_msg":
            "✅ <b>완료되었습니다! 언어가 설정되었습니다.</b>",
        "loading": "로딩 중...",
        "video_converted": "변환됨",
        "size_limit": "파일이 큽니다",
        "fail_download": "실패",
        "photo_download": "사진",
        "welcome": "안녕하세요",
        "price": "가격",
        "order": "광고",
        "payment": "결제",
        "support": "지원"
    },


    # ========================================================
    # ITALIAN
    # ========================================================

    "it": {
        "btn_add": "Aggiungi bot al gruppo",
        "btn_order": "Pubblicità",
        "btn_price": "Prezzi",
        "btn_payment": "Metodo di pagamento",
        "btn_status": "Mio Stato",
        "btn_lang": "Language | Lingua",
        "btn_support": "Supporto",
        "btn_back": "Indietro",
        "done_msg":
            "✅ <b>Fatto! La tua lingua è stata impostata.</b>",
        "loading": "Caricamento...",
        "video_converted": "Convertito",
        "size_limit": "File troppo grande",
        "fail_download": "Errore",
        "photo_download": "Foto",
        "welcome": "Ciao",
        "price": "Prezzi",
        "order": "Pubblicità",
        "payment": "Pagamento",
        "support": "Supporto"
    },


    # ========================================================
    # POLISH
    # ========================================================

    "pl": {
        "btn_add": "Dodaj bota do grupy",
        "btn_order": "Reklama",
        "btn_price": "Cennik",
        "btn_payment": "Metoda płatności",
        "btn_status": "Mój status",
        "btn_lang": "Language | Język",
        "btn_support": "Pomoc",
        "btn_back": "Wróć",
        "done_msg":
            "✅ <b>Gotowe! Twój język został ustawiony.</b>",
        "loading": "Ładowanie...",
        "video_converted": "Skonwertowano",
        "size_limit": "Za duży plik",
        "fail_download": "Błąd",
        "photo_download": "Zdjęcie",
        "welcome": "Cześć",
        "price": "Cennik",
        "order": "Reklama",
        "payment": "Płatność",
        "support": "Pomoc"
    },


    # ========================================================
    # VIETNAMESE
    # ========================================================

    "vi": {
        "btn_add": "Thêm bot vào nhóm",
        "btn_order": "Đặt quảng cáo",
        "btn_price": "Bảng giá",
        "btn_payment": "Phương thức thanh toán",
        "btn_status": "Trạng thái",
        "btn_lang": "Language | Ngôn ngữ",
        "btn_support": "Hỗ trợ",
        "btn_back": "Quay lại",
        "done_msg":
            "✅ <b>Hoàn tất! Ngôn ngữ của bạn đã được đặt.</b>",
        "loading": "Đang tải...",
        "video_converted": "Đã chuyển đổi",
        "size_limit": "Tệp quá lớn",
        "fail_download": "Lỗi",
        "photo_download": "Ảnh",
        "welcome": "Xin chào",
        "price": "Giá",
        "order": "Quảng cáo",
        "payment": "Thanh toán",
        "support": "Hỗ trợ"
    },


    # ========================================================
    # KAZAKH
    # ========================================================

    "kk": {
        "btn_add": "Ботты топқа қосу",
        "btn_order": "Жарнама беру",
        "btn_price": "Бағалар",
        "btn_payment": "Төлем әдісі",
        "btn_status": "Мәртебем",
        "btn_lang": "Language | Тіл",
        "btn_support": "Көмек",
        "btn_back": "Қайту",
        "done_msg":
            "✅ <b>Дайын! Тіліңіз орнатылды.</b>",
        "loading": "Жүктелуде",
        "video_converted": "Айырбасталды",
        "size_limit": "Файл тым үлкен",
        "fail_download": "Қате",
        "photo_download": "Сурет",
        "welcome": "Сәлем",
        "price": "Бағалар",
        "order": "Жарнама",
        "payment": "Төлем",
        "support": "Көмек"
    }
}


# ============================================================
# TRANSLATION HELPER
# ============================================================

def get_trans(user_id, key):

    lang = get_user_language(user_id)

    if not lang or lang not in TRANSLATIONS:
        lang = "am"

    lang_dict = TRANSLATIONS.get(
        lang,
        TRANSLATIONS["am"]
    )

    return lang_dict.get(
        key,
        TRANSLATIONS["am"].get(
            key,
            ""
        )
    )


# ============================================================
# BOT USERNAME
# ============================================================

def get_bot_username(context):

    username = context.bot.username

    if username:
        return username

    return "mame_posts_bot"


# ============================================================
# MAIN MENU
# ============================================================

def get_main_menu_keyboard(
    bot_username,
    user_id,
    use_custom_emoji=True
):

    def btn(
        text,
        callback_data=None,
        url=None,
        emoji_id=None
    ):

        kwargs = {
            "text": text
        }

        if callback_data:
            kwargs["callback_data"] = callback_data

        if url:
            kwargs["url"] = url

        if use_custom_emoji and emoji_id:
            kwargs["icon_custom_emoji_id"] = emoji_id

        return InlineKeyboardButton(**kwargs)


    keyboard = [

        [
            btn(
                get_trans(user_id, "btn_add"),
                url=(
                    f"https://t.me/"
                    f"{bot_username}"
                    f"?startgroup=true"
                ),
                emoji_id="5305545479814161889"
            )
        ],

        [
            btn(
                get_trans(user_id, "btn_order"),
                callback_data="cmd_order",
                emoji_id="5267442591548320083"
            )
        ],

        [
            btn(
                get_trans(user_id, "btn_price"),
                callback_data="cmd_price",
                emoji_id="5447458260200214425"
            ),

            btn(
                get_trans(user_id, "btn_payment"),
                callback_data="cmd_payment",
                emoji_id="5186349709169525403"
            )
        ],

        [
            btn(
                get_trans(user_id, "btn_status"),
                callback_data="cmd_status",
                emoji_id="5431577498364158238"
            ),

            btn(
                get_trans(user_id, "btn_lang"),
                callback_data="cmd_change_lang",
                emoji_id="5431577498364158238"
            )
        ],

        [
            btn(
                get_trans(user_id, "btn_support"),
                callback_data="cmd_support",
                emoji_id="5949327894567195412"
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


# ============================================================
# LANGUAGE KEYBOARD
# ============================================================

def get_language_keyboard():

    keyboard = [

        [
            InlineKeyboardButton(
                "🇬🇧 English",
                callback_data="lang_en"
            ),

            InlineKeyboardButton(
                "🇪🇹 አማርኛ",
                callback_data="lang_am"
            )
        ],

        [
            InlineKeyboardButton(
                "🇸🇦 العربية",
                callback_data="lang_ar"
            )
        ],

        [
            InlineKeyboardButton(
                "🇷🇺 Русский",
                callback_data="lang_ru"
            ),

            InlineKeyboardButton(
                "🇫🇷 Français",
                callback_data="lang_fr"
            )
        ],

        [
            InlineKeyboardButton(
                "🇪🇸 Español",
                callback_data="lang_es"
            ),

            InlineKeyboardButton(
                "🇮🇷 ایران",
                callback_data="lang_fa"
            )
        ],

        [
            InlineKeyboardButton(
                "🇮🇳 भारत",
                callback_data="lang_hi"
            ),

            InlineKeyboardButton(
                "🇺🇿 O'zbek",
                callback_data="lang_uz"
            )
        ],

        [
            InlineKeyboardButton(
                "🇵🇹 Português",
                callback_data="lang_pt"
            ),

            InlineKeyboardButton(
                "🇨🇳 中文",
                callback_data="lang_zh"
            )
        ],

        [
            InlineKeyboardButton(
                "🇧🇩 বাংলা",
                callback_data="lang_bn"
            ),

            InlineKeyboardButton(
                "🇮🇩 Indonesia",
                callback_data="lang_id"
            )
        ],

        [
            InlineKeyboardButton(
                "🇩🇪 Deutsch",
                callback_data="lang_de"
            ),

            InlineKeyboardButton(
                "🇺🇦 Українська",
                callback_data="lang_uk"
            )
        ],

        [
            InlineKeyboardButton(
                "🇹🇷 Türkçe",
                callback_data="lang_tr"
            ),

            InlineKeyboardButton(
                "🇰🇷 한국어",
                callback_data="lang_ko"
            )
        ],

        [
            InlineKeyboardButton(
                "🇮🇹 Italiano",
                callback_data="lang_it"
            ),

            InlineKeyboardButton(
                "🇵🇱 Polski",
                callback_data="lang_pl"
            )
        ],

        [
            InlineKeyboardButton(
                "🇻🇳 Tiếng Việt",
                callback_data="lang_vi"
            ),

            InlineKeyboardButton(
                "🇰🇿 Қазақша",
                callback_data="lang_kk"
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


# ============================================================
# BACK BUTTON
# ============================================================

def get_back_keyboard(
    user_id,
    use_custom_emoji=True
):

    kwargs = {
        "text": get_trans(user_id, "btn_back"),
        "callback_data": "cmd_back"
    }

    if use_custom_emoji:
        kwargs["icon_custom_emoji_id"] = (
            "5248948801674159296"
        )

    keyboard = [
        [
            InlineKeyboardButton(**kwargs)
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


# ============================================================
# BOT COMMANDS
# ============================================================

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
            "rate",
            "የማስታወቂያ ዋጋዎች"
        ),

        BotCommand(
            "payment",
            "የከፈያ መንገድ"
        ),

        BotCommand(
            "help",
            "እርዳታና ድጋፍ"
        )
    ]

    await application.bot.set_my_commands(commands)


# ============================================================
# FORCE JOIN CHECK
# ============================================================

async def is_joined(update, context):

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

        # Keep original behavior:
        # if Telegram cannot verify, don't block the user.
        return True


# ============================================================
# SHOW FORCE JOIN
# ============================================================

async def show_force_join(update, context):

    text = (
        '<tg-emoji emoji-id="6034962180875490251">🔒</tg-emoji> '
        '<b>ቦቱን ለመጠቀም ከታች ያለውን ቻናል '
        'መቀላቀል አለብዎት!</b>\n\n'
        '1️⃣ '
        '<tg-emoji emoji-id="5267442591548320083">📢</tg-emoji> '
        '<b>Join Channel የሚለውን ይጫኑ::</b>\n'
        '2️⃣ '
        '<tg-emoji emoji-id="5305749202997911340">✅</tg-emoji> '
        '<b>I've Joined የሚለውን ተጭነው የላኩትን '
        'ደግመው ይላኩ '
        '<tg-emoji emoji-id="5217449524410199951">🙂</tg-emoji>::</b>'
    )

    keyboard_custom = [
        [
            InlineKeyboardButton(
                text="Join Channel",
                icon_custom_emoji_id="5767358836134382747",
                url=FORCE_CHANNEL_LINK
            )
        ],
        [
            InlineKeyboardButton(
                text="I've Joined",
                icon_custom_emoji_id="5895288332581082241",
                callback_data="check_join"
            )
        ]
    ]

    keyboard_normal = [
        [
            InlineKeyboardButton(
                text="📢 Join Channel",
                url=FORCE_CHANNEL_LINK
            )
        ],
        [
            InlineKeyboardButton(
                text="✅ I've Joined",
                callback_data="check_join"
            )
        ]
    ]

    try:
        await update.message.reply_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard_custom),
            parse_mode="HTML"
        )

    except Exception as e:
        print("Custom force-join keyboard failed:", e)

        try:
            await update.message.reply_text(
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard_normal),
                parse_mode="HTML"
            )
        except Exception as fallback_error:
            print(
                "Normal force-join keyboard failed:",
                fallback_error
            )
            
# ============================================================
# SEND MAIN MENU SAFELY
# ============================================================

async def send_main_menu(
    chat_id,
    context,
    user_id
):

    bot_username = get_bot_username(context)

    text = get_trans(
        user_id,
        "welcome"
    )

    try:

        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=get_main_menu_keyboard(
                bot_username,
                user_id,
                use_custom_emoji=True
            ),
            parse_mode="HTML"
        )

    except Exception as e:

        print(
            "Custom emoji menu failed:",
            e
        )

        # Fallback without icon_custom_emoji_id
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=get_main_menu_keyboard(
                bot_username,
                user_id,
                use_custom_emoji=False
            ),
            parse_mode="HTML"
        )


# ============================================================
# START
# ============================================================

async def start(update, context):

    if not update.message:
        return

    user_id = update.effective_user.id

    record_user_activity(
        user_id
    )

    setup_keyboard = ReplyKeyboardMarkup(
        [["🏠 Menu"]],
        resize_keyboard=True,
        input_field_placeholder="Send link 🔗"
    )

    user_lang = get_user_language(
        user_id
    )

    if not user_lang:

        await update.message.reply_text(
            "<b>Please select your language / "
            "እባክዎ ቋንቋ ይምረጡ፦</b>",
            reply_markup=get_language_keyboard(),
            parse_mode="HTML"
        )

        return


    # Give the persistent Menu keyboard
    await update.message.reply_text(
        "🏠",
        reply_markup=setup_keyboard
    )


    # Force join
    if not await is_joined(
        update,
        context
    ):

        await show_force_join(
            update,
            context
        )

        return


    await send_main_menu(
        update.effective_chat.id,
        context,
        user_id
    )


# ============================================================
# STATUS
# ============================================================

async def status_command(update, context):

    if not update.message:
        return

    user = update.effective_user

    record_user_activity(
        user.id
    )

    total_users, user_msg_count = (
        get_user_stats(user.id)
    )

    username_text = (
        f"@{user.username}"
        if user.username
        else "የለውም"
    )

    msg = (
        '<tg-emoji emoji-id="5431577498364158238">📊</tg-emoji> '
        '<b>My Status & Stats</b>\n\n'

        f'👤 <b>Username:</b> {username_text}\n'
        f'🆔 <b>ID:</b> <code>{user.id}</code>\n\n'

        f'💬 <b>Your Messages:</b> {user_msg_count}\n'
        f'👥 <b>Bot Users:</b> {total_users}\n\n'

        '🔥 <b>Engagment: Active</b>'
    )

    await update.message.reply_text(
        msg,
        parse_mode="HTML"
    )


# ============================================================
# RATES
# ============================================================

async def rates_command(update, context):

    if not update.message:
        return

    user_id = update.effective_user.id

    record_user_activity(
        user_id
    )

    await update.message.reply_text(
        get_trans(
            user_id,
            "price"
        ),
        parse_mode="HTML"
    )


# ============================================================
# PAYMENT
# ============================================================

async def payment_command(update, context):

    if not update.message:
        return

    user_id = update.effective_user.id

    record_user_activity(
        user_id
    )

    await update.message.reply_text(
        get_trans(
            user_id,
            "payment"
        ),
        parse_mode="HTML"
    )


# ============================================================
# HELP
# ============================================================

async def help_command(update, context):

    if not update.message:
        return

    user_id = update.effective_user.id

    record_user_activity(
        user_id
    )

    await update.message.reply_text(
        get_trans(
            user_id,
            "support"
        ),
        parse_mode="HTML"
    )


# ============================================================
# BROADCAST
# ============================================================

async def broadcast_command(
    update,
    context
):

    if not update.message:
        return

    if update.effective_user.id != ADMIN_ID:
        return

    reply_msg = (
        update.message.reply_to_message
    )

    has_args = bool(
        context.args
    )

    if not reply_msg and not has_args:

        await update.message.reply_text(
            "❌ Reply to a message or use:\n"
            "/broadcast your message"
        )

        return

    data = load_data()

    success_count = 0
    fail_count = 0

    status_msg = await update.message.reply_text(
        "📢 Broadcasting..."
    )

    for uid_str in data.keys():

        try:

            chat_id = int(
                uid_str
            )

            if reply_msg:

                await reply_msg.copy(
                    chat_id=chat_id
                )

            else:

                text_to_send = " ".join(
                    context.args
                )

                await context.bot.send_message(
                    chat_id=chat_id,
                    text=text_to_send,
                    parse_mode="HTML"
                )

            success_count += 1

            await asyncio.sleep(
                0.05
            )

        except Exception as e:

            fail_count += 1

            print(
                "Broadcast error:",
                e
            )

    await status_msg.edit_text(
        f"✅ Broadcast completed.\n\n"
        f"Successful: {success_count}\n"
        f"Failed: {fail_count}"
    )


# ============================================================
# VIDEO TO AUDIO
# ============================================================

async def convert_video_to_audio(
    update,
    context
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


    video = (
        update.message.video
        or update.message.video_note
    )


    # Support video documents too
    if not video:

        document = update.message.document

        if (
            document
            and document.mime_type
            and document.mime_type.startswith(
                "video/"
            )
        ):

            video = document


    if not video:
        return


    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.UPLOAD_AUDIO
    )


    status_msg = await update.message.reply_text(
        get_trans(
            user_id,
            "loading"
        ),
        parse_mode="HTML"
    )


    file_id = update.message.message_id

    input_path = (
        f"input_vid_"
        f"{user_id}_"
        f"{file_id}.mp4"
    )

    output_path = (
        f"output_aud_"
        f"{user_id}_"
        f"{file_id}.mp3"
    )


    try:

        tg_file = await video.get_file()

        await tg_file.download_to_drive(
            input_path
        )


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


        result = await asyncio.to_thread(
            subprocess.run,
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True
        )


        if (
            result.returncode != 0
            or not os.path.exists(output_path)
        ):

            raise RuntimeError(
                "FFmpeg conversion failed"
            )


        bot_username = get_bot_username(
            context
        )


        share_url = (
            "https://t.me/share/url?"
            f"url={quote(f'https://t.me/{bot_username}?start=share')}"
            f"&text={quote('Try this awesome Video to Audio Converter Bot!🔥')}"
        )


        keyboard_share = [
            [
                InlineKeyboardButton(
                    "🔗 Share Bot 🚀",
                    url=share_url
                )
            ]
        ]


        caption_text = get_trans(
            user_id,
            "video_converted"
        ).format(
            bot_username=bot_username
        )


        with open(
            output_path,
            "rb"
        ) as audio_file:

            await update.message.reply_audio(
                audio=audio_file,
                caption=caption_text,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    keyboard_share
                )
            )


        try:
            await status_msg.delete()
        except Exception:
            pass


    except Exception as e:

        print(
            "Video to Audio Error:",
            e
        )

        try:

            await status_msg.edit_text(
                get_trans(
                    user_id,
                    "fail_download"
                ),
                parse_mode="HTML"
            )

        except Exception:
            pass


    finally:

        for path in [
            input_path,
            output_path
        ]:

            try:

                if os.path.exists(path):
                    os.remove(path)

            except Exception:
                pass


# ============================================================
# URL CLEANING
# ============================================================

def unshorten_url(url: str) -> str:

    try:

        session = requests.Session()

        session.headers.update({
            "User-Agent":
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/128.0.0.0 Safari/537.36"
        })


        response = session.head(
            url,
            allow_redirects=True,
            timeout=10
        )

        return response.url

    except Exception:

        return url


def clean_url(raw_url: str) -> str:

    raw_url = raw_url.strip()

    return unshorten_url(
        raw_url
    )


# ============================================================
# YT-DLP OPTIONS
# ============================================================

def get_video_options(
    url: str,
    output_template: str,
    fallback=False
):

    opts = {

        "quiet": True,

        "no_warnings": True,

        "nocheckcertificate": True,

        "geo_bypass": True,

        "retries": 3,

        "fragment_retries": 3,

        "file_access_retries": 3,

        "socket_timeout": 30,

        "concurrent_fragment_downloads": 5,

        "continuedl": True,

        "noplaylist": True,

        "outtmpl": output_template,

        "merge_output_format": "mp4",

        "format": (
            "bestvideo[ext=mp4]+"
            "bestaudio[ext=m4a]/"
            "bestvideo+bestaudio/"
            "best[ext=mp4]/"
            "best"
        ),

        "http_headers": {

            "User-Agent":
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/128.0.0.0 Safari/537.36",

            "Accept":
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,image/webp,"
                "*/*;q=0.8",

            "Accept-Language":
                "en-US,en;q=0.9"
        }
    }


    # --------------------------------------------------------
    # YouTube
    # --------------------------------------------------------

    if (
        "youtube.com" in url.lower()
        or "youtu.be" in url.lower()
    ):

        # Do NOT force a specific player client here.
        # yt-dlp's current defaults are safer.

        opts["format"] = (
            "bestvideo[ext=mp4]+"
            "bestaudio[ext=m4a]/"
            "bestvideo+bestaudio/"
            "best[ext=mp4]/"
            "best"
        )


    # --------------------------------------------------------
    # Likee
    # --------------------------------------------------------

    elif (
        "likee" in url.lower()
        or "likee.video" in url.lower()
    ):

        opts["http_headers"]["Referer"] = (
            "https://likee.video/"
        )


    # --------------------------------------------------------
    # Vimeo
    # --------------------------------------------------------

    elif "vimeo.com" in url.lower():

        opts["http_headers"]["Referer"] = (
            "https://vimeo.com/"
        )


    # --------------------------------------------------------
    # Fallback
    # --------------------------------------------------------

    if fallback:

        opts["format"] = (
            "best[ext=mp4]/best"
        )


    # --------------------------------------------------------
    # YouTube Cookies
    # --------------------------------------------------------

    if os.path.exists(
        "cookies.txt"
    ):

        opts["cookiefile"] = (
            "cookies.txt"
        )


    return opts


# ============================================================
# DOWNLOAD FUNCTION
# ============================================================

def download_media_func(
    url,
    output_template,
    fallback=False
):

    options = get_video_options(
        url,
        output_template,
        fallback=fallback
    )

    with yt_dlp.YoutubeDL(
        options
    ) as ydl:

        ydl.download([
            url
        ])


# ============================================================
# FIND DOWNLOADED FILE
# ============================================================

def find_downloaded_file(prefix):

    try:

        files = os.listdir(
            "."
        )

    except Exception:

        return None


    valid_files = []

    for filename in files:

        if not filename.startswith(
            prefix
        ):
            continue

        if filename.endswith(
            (
                ".part",
                ".ytdl",
                ".temp"
            )
        ):
            continue

        if os.path.isfile(
            filename
        ):

            valid_files.append(
                filename
            )


    if not valid_files:
        return None


    valid_files.sort(
        key=lambda x: os.path.getmtime(x),
        reverse=True
    )

    return valid_files[0]


# ============================================================
# PINTEREST DIRECT IMAGE
# ============================================================

def pinterest_direct_image(url):

    try:

        response = requests.get(
            url,
            headers={
                "User-Agent":
                    "Mozilla/5.0"
            },
            timeout=15
        )

        if response.status_code != 200:
            return None


        html = response.text


        patterns = [

            r'https://i\.pinimg\.com/'
            r'(?:originals|736x)/[^"\']+',

            r'https:\\/\\/i\.pinimg\.com\\/'
            r'(?:originals|736x)\\/[^"\\']+'
        ]


        for pattern in patterns:

            match = re.search(
                pattern,
                html
            )

            if match:

                image_url = match.group(0)

                image_url = (
                    image_url
                    .replace("\\/", "/")
                    .replace("\\u002F", "/")
                )

                return image_url


    except Exception as e:

        print(
            "Pinterest Error:",
            e
        )


    return None


# ============================================================
# HANDLE URL DOWNLOAD
# ============================================================

async def handle_url_download(
    update,
    context,
    target_url
):

    if not update.message:
        return

    user_id = update.effective_user.id

    record_user_activity(
        user_id
    )


    status_msg = await update.message.reply_text(
        get_trans(
            user_id,
            "loading"
        ),
        parse_mode="HTML"
    )


    media_prefix = (
        f"download_"
        f"{user_id}_"
        f"{update.message.message_id}_"
    )


    output_template = (
        media_prefix
        + "%(id)s.%(ext)s"
    )


    sent_any = False


    try:

        # ----------------------------------------------------
        # Clean URL
        # ----------------------------------------------------

        target_url = target_url.strip()

        target_url = target_url.rstrip(
            ".,!?)]}"
        )

        target_url = clean_url(
            target_url
        )


        # ----------------------------------------------------
        # Pinterest special handling
        # ----------------------------------------------------

        if (
            "pinterest.com" in target_url.lower()
            or "pin.it" in target_url.lower()
        ):

            image_url = pinterest_direct_image(
                target_url
            )

            if image_url:

                try:

                    image_response = requests.get(
                        image_url,
                        headers={
                            "User-Agent":
                                "Mozilla/5.0"
                        },
                        timeout=30
                    )

                    if (
                        image_response.status_code == 200
                        and image_response.content
                    ):

                        temp_image = (
                            media_prefix
                            + "pinterest.jpg"
                        )

                        with open(
                            temp_image,
                            "wb"
                        ) as f:

                            f.write(
                                image_response.content
                            )


                        bot_username = get_bot_username(
                            context
                        )


                        caption = get_trans(
                            user_id,
                            "photo_download"
                        ).format(
                            bot_username=bot_username
                        )


                        with open(
                            temp_image,
                            "rb"
                        ) as photo:

                            await update.message.reply_photo(
                                photo=photo,
                                caption=caption,
                                parse_mode="HTML"
                            )


                        sent_any = True

                        os.remove(
                            temp_image
                        )

                        return

                except Exception as e:

                    print(
                        "Pinterest direct download failed:",
                        e
                    )


        # ----------------------------------------------------
        # Download attempt #1
        # ----------------------------------------------------

        try:

            await asyncio.to_thread(
                download_media_func,
                target_url,
                output_template,
                False
            )

        except Exception as e:

            print(
                "Download attempt 1 failed:",
                e
            )

            # ------------------------------------------------
            # Download attempt #2
            # ------------------------------------------------

            await asyncio.to_thread(
                download_media_func,
                target_url,
                output_template,
                True
            )


        # ----------------------------------------------------
        # Find downloaded media
        # ----------------------------------------------------

        downloaded_file = (
            find_downloaded_file(
                media_prefix
            )
        )


        if not downloaded_file:

            try:

                await status_msg.edit_text(
                    get_trans(
                        user_id,
                        "fail_download"
                    ),
                    parse_mode="HTML"
                )

            except Exception:
                pass

            return


        # ----------------------------------------------------
        # File size
        # ----------------------------------------------------

        file_size = os.path.getsize(
            downloaded_file
        )

        max_size = 50 * 1024 * 1024


        # ----------------------------------------------------
        # 50 MB limit
        # ----------------------------------------------------

        if file_size > max_size:

            try:

                await status_msg.edit_text(
                    get_trans(
                        user_id,
                        "size_limit"
                    ),
                    parse_mode="HTML"
                )

            except Exception:
                pass

            return


        # ----------------------------------------------------
        # IMAGE
        # ----------------------------------------------------

        image_extensions = (
            ".jpg",
            ".jpeg",
            ".png",
            ".webp"
        )


        if downloaded_file.lower().endswith(
            image_extensions
        ):

            bot_username = get_bot_username(
                context
            )

            caption = get_trans(
                user_id,
                "photo_download"
            ).format(
                bot_username=bot_username
            )


            with open(
                downloaded_file,
                "rb"
            ) as photo:

                await update.message.reply_photo(
                    photo=photo,
                    caption=caption,
                    parse_mode="HTML"
                )


            sent_any = True


        # ----------------------------------------------------
        # AUDIO
        # ----------------------------------------------------

        elif downloaded_file.lower().endswith(
            (
                ".mp3",
                ".m4a",
                ".aac",
                ".wav",
                ".ogg",
                ".opus",
                ".flac"
            )
        ):

            bot_username = get_bot_username(
                context
            )

            caption = get_trans(
                user_id,
                "video_converted"
            ).format(
                bot_username=bot_username
            )


            with open(
                downloaded_file,
                "rb"
            ) as audio:

                await update.message.reply_audio(
                    audio=audio,
                    caption=caption,
                    parse_mode="HTML"
                )


            sent_any = True


        # ----------------------------------------------------
        # VIDEO
        # ----------------------------------------------------

        else:

            bot_username = get_bot_username(
                context
            )


            share_url = (
                "https://t.me/share/url?"
                f"url={quote(f'https://t.me/{bot_username}?start=share')}"
                f"&text={quote('Try this awesome Downloader Bot!🔥')}"
            )


            keyboard_share = [
                [
                    InlineKeyboardButton(
                        "🔗 Share Bot 🚀",
                        url=share_url
                    )
                ]
            ]


            with open(
                downloaded_file,
                "rb"
            ) as video_file:

                await update.message.reply_video(
                    video=video_file,
                    supports_streaming=True,
                    reply_markup=InlineKeyboardMarkup(
                        keyboard_share
                    )
                )


            sent_any = True


            # ------------------------------------------------
            # Extract MP3 from downloaded video
            # ------------------------------------------------

            audio_output = (
                media_prefix
                + "audio.mp3"
            )


            ffmpeg_cmd = [
                "ffmpeg",
                "-y",
                "-i",
                downloaded_file,
                "-vn",
                "-acodec",
                "libmp3lame",
                "-q:a",
                "2",
                audio_output
            ]


            try:

                result = await asyncio.to_thread(
                    subprocess.run,
                    ffmpeg_cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True
                )


                if (
                    result.returncode == 0
                    and os.path.exists(
                        audio_output
                    )
                ):

                    caption = get_trans(
                        user_id,
                        "video_converted"
                    ).format(
                        bot_username=bot_username
                    )


                    with open(
                        audio_output,
                        "rb"
                    ) as audio_file:

                        await update.message.reply_audio(
                            audio=audio_file,
                            caption=caption,
                            parse_mode="HTML"
                        )


                    try:

                        os.remove(
                            audio_output
                        )

                    except Exception:
                        pass


            except Exception as e:

                print(
                    "Audio extraction error:",
                    e
                )


    except Exception as e:

        print(
            "Download Error:",
            e
        )

        if not sent_any:

            try:

                await status_msg.edit_text(
                    get_trans(
                        user_id,
                        "fail_download"
                    ),
                    parse_mode="HTML"
                )

            except Exception:
                pass


    finally:

        # ----------------------------------------------------
        # Clean temporary files
        # ----------------------------------------------------

        try:

            for filename in os.listdir(
                "."
            ):

                if filename.startswith(
                    media_prefix
                ):

                    try:

                        os.remove(
                            filename
                        )

                    except Exception:
                        pass

        except Exception:
            pass


        if sent_any:

            try:

                await status_msg.delete()

            except Exception:
                pass


# ============================================================
# CALLBACK QUERY
# ============================================================

async def button_callback(
    update,
    context
):

    query = update.callback_query

    data = query.data

    user = query.from_user

    user_id = user.id

    bot_username = get_bot_username(
        context
    )


    # ========================================================
    # LANGUAGE
    # ========================================================

    if data.startswith(
        "lang_"
    ):

        lang_code = data.split(
            "_",
            1
        )[1]


        if lang_code not in TRANSLATIONS:

            await query.answer(
                "Language unavailable.",
                show_alert=True
            )

            return


        set_user_language(
            user_id,
            lang_code
        )


        await query.answer()


        try:

            await query.message.delete()

        except Exception:
            pass


        setup_keyboard = ReplyKeyboardMarkup(
            [["🏠 Menu"]],
            resize_keyboard=True,
            input_field_placeholder="Send link 🔗"
        )


        await context.bot.send_message(
            chat_id=user_id,
            text=get_trans(
                user_id,
                "done_msg"
            ),
            reply_markup=setup_keyboard,
            parse_mode="HTML"
        )


        # Force join after selecting language
        try:

            member = await context.bot.get_chat_member(
                chat_id=FORCE_CHANNEL,
                user_id=user_id
            )

            joined = member.status in [
                "member",
                "administrator",
                "creator"
            ]

        except Exception as e:

            print(
                "Language force join check:",
                e
            )

            joined = True


        if not joined:

            text = (
                '<tg-emoji emoji-id="6034962180875490251">🔒</tg-emoji> '
                '<b>ቦቱን ለመጠቀም ከታች ያለውን '
                'ቻናል መቀላቀል አለብዎት!</b>'
            )


            keyboard = [
                [
                    InlineKeyboardButton(
                        text="Join Channel",
                        icon_custom_emoji_id=(
                            "5767358836134382747"
                        ),
                        url=FORCE_CHANNEL_LINK
                    )
                ],

                [
                    InlineKeyboardButton(
                        text="I've Joined",
                        icon_custom_emoji_id=(
                            "5895288332581082241"
                        ),
                        callback_data="check_join"
                    )
                ]
            ]


            try:

                await context.bot.send_message(
                    chat_id=user_id,
                    text=text,
                    reply_markup=InlineKeyboardMarkup(
                        keyboard
                    ),
                    parse_mode="HTML"
                )

            except Exception:

                await context.bot.send_message(
                    chat_id=user_id,
                    text=text,
                    reply_markup=InlineKeyboardMarkup([
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
                    ]),
                    parse_mode="HTML"
                )

            return


        await send_main_menu(
            user_id,
            context,
            user_id
        )

        return


    # ========================================================
    # CHANGE LANGUAGE
    # ========================================================

    if data == "cmd_change_lang":

        await query.answer()

        await query.edit_message_text(
            "<b>Please select your language / "
            "እባክዎ ቋንቋ ይምረጡ፦</b>",
            reply_markup=get_language_keyboard(),
            parse_mode="HTML"
        )

        return


    # ========================================================
    # BACK
    # ========================================================

    if data == "cmd_back":

        await query.answer()

        text = get_trans(
            user_id,
            "welcome"
        )

        try:

            await query.edit_message_text(
                text=text,
                reply_markup=get_main_menu_keyboard(
                    bot_username,
                    user_id,
                    True
                ),
                parse_mode="HTML"
            )

        except Exception as e:

            print(
                "Back custom emoji failed:",
                e
            )

            await query.edit_message_text(
                text=text,
                reply_markup=get_main_menu_keyboard(
                    bot_username,
                    user_id,
                    False
                ),
                parse_mode="HTML"
            )

        return


    # ========================================================
    # PRICE
    # ========================================================

    if data == "cmd_price":

        await query.answer()

        text = get_trans(
            user_id,
            "price"
        )

        try:

            await query.edit_message_text(
                text=text,
                reply_markup=get_back_keyboard(
                    user_id,
                    True
                ),
                parse_mode="HTML"
            )

        except Exception as e:

            print(
                "Price custom emoji failed:",
                e
            )

            await query.edit_message_text(
                text=text,
                reply_markup=get_back_keyboard(
                    user_id,
                    False
                ),
                parse_mode="HTML"
            )

        return


    # ========================================================
    # ORDER
    # ========================================================

    if data == "cmd_order":

        await query.answer()

        text = get_trans(
            user_id,
            "order"
        )

        try:

            await query.edit_message_text(
                text=text,
                reply_markup=get_back_keyboard(
                    user_id,
                    True
                ),
                parse_mode="HTML"
            )

        except Exception as e:

            print(
                "Order custom emoji failed:",
                e
            )

            await query.edit_message_text(
                text=text,
                reply_markup=get_back_keyboard(
                    user_id,
                    False
                ),
                parse_mode="HTML"
            )

        return


    # ========================================================
    # PAYMENT
    # ========================================================

    if data == "cmd_payment":

        await query.answer()

        text = get_trans(
            user_id,
            "payment"
        )

        try:

            await query.edit_message_text(
                text=text,
                reply_markup=get_back_keyboard(
                    user_id,
                    True
                ),
                parse_mode="HTML"
            )

        except Exception as e:

            print(
                "Payment custom emoji failed:",
                e
            )

            await query.edit_message_text(
                text=text,
                reply_markup=get_back_keyboard(
                    user_id,
                    False
                ),
                parse_mode="HTML"
            )

        return


    # ========================================================
    # SUPPORT
    # ========================================================

    if data == "cmd_support":

        await query.answer()

        text = get_trans(
            user_id,
            "support"
        )

        try:

            await query.edit_message_text(
                text=text,
                reply_markup=get_back_keyboard(
                    user_id,
                    True
                ),
                parse_mode="HTML"
            )

        except Exception as e:

            print(
                "Support custom emoji failed:",
                e
            )

            await query.edit_message_text(
                text=text,
                reply_markup=get_back_keyboard(
                    user_id,
                    False
                ),
                parse_mode="HTML"
            )

        return


    # ========================================================
    # STATUS
    # ========================================================

    if data == "cmd_status":

        await query.answer()

        total_users, user_msg_count = (
            get_user_stats(user_id)
        )

        username_text = (
            f"@{user.username}"
            if user.username
            else "የለውም"
        )


        msg = (
            '<tg-emoji emoji-id="5431577498364158238">📊</tg-emoji> '
            '<b>My Status & Stats</b>\n\n'

            f'👤 <b>Username:</b> {username_text}\n'
            f'🆔 <b>ID:</b> <code>{user_id}</code>\n\n'

            f'💬 <b>Your Messages:</b> {user_msg_count}\n'
            f'👥 <b>Bot Users:</b> {total_users}\n\n'

            '🔥 <b>Engagment: Active</b>'
        )


        try:

            await query.edit_message_text(
                text=msg,
                reply_markup=get_back_keyboard(
                    user_id,
                    True
                ),
                parse_mode="HTML"
            )

        except Exception as e:

            print(
                "Status custom emoji failed:",
                e
            )

            await query.edit_message_text(
                text=msg,
                reply_markup=get_back_keyboard(
                    user_id,
                    False
                ),
                parse_mode="HTML"
            )

        return


# ============================================================
# CHECK JOIN
# ============================================================

async def check_join(
    update,
    context
):

    query = update.callback_query

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

            # Answer ONCE
            await query.answer()

            try:

                await query.edit_message_text(
                    '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> '
                    '<b>አሁን ቻናሉን ተቀላቅለዋል።</b>\n\n'
                    'እባክዎ <b>/start</b> ይጫኑ።',
                    parse_mode="HTML"
                )

            except Exception as e:

                print(
                    "Join success edit error:",
                    e
                )

        else:

            # Answer ONCE with alert
            await query.answer(
                "❌ እባክዎ መጀመሪያ Channel ይቀላቀሉ!",
                show_alert=True
            )


    except Exception as e:

        print(
            "Check Join Error:",
            e
        )

        await query.answer(
            "⚠️ Channel membership could not be verified.",
            show_alert=True
        )


# ============================================================
# SUPPORTED DOMAINS
# ============================================================

SUPPORTED_DOMAINS = [

    "youtube.com",
    "youtu.be",

    "tiktok.com",

    "likee.video",
    "likee.com",

    "pinterest.com",
    "pin.it",

    "instagram.com",

    "twitter.com",
    "x.com",

    "facebook.com",
    "fb.watch",

    "reddit.com",
    "redd.it",

    "twitch.tv",

    "vimeo.com",

    "vk.com",

    "ok.ru",

    "tumblr.com",

    "soundcloud.com",

    "threads.net",

    "spotify.com",

    "open.spotify.com",

    "music.apple.com"
]


# ============================================================
# USER MESSAGE HANDLER
# ============================================================

async def handle_user_messages(
    update,
    context
):

    if not update.message:
        return


    user_id = update.effective_user.id

    record_user_activity(
        user_id
    )


    # --------------------------------------------------------
    # Video document -> Video to Audio
    # --------------------------------------------------------

    document = update.message.document

    if (
        document
        and document.mime_type
        and document.mime_type.startswith(
            "video/"
        )
    ):

        await convert_video_to_audio(
            update,
            context
        )

        return


    # --------------------------------------------------------
    # Text / Caption
    # --------------------------------------------------------

    text = (
        update.message.text
        or update.message.caption
        or ""
    )


    # --------------------------------------------------------
    # Main Menu button
    # --------------------------------------------------------

    if text.strip() == "🏠 Menu":

        if not await is_joined(
            update,
            context
        ):

            await show_force_join(
                update,
                context
            )

            return


        await send_main_menu(
            update.effective_chat.id,
            context,
            user_id
        )

        return


    # --------------------------------------------------------
    # Check supported social-media URL
    # --------------------------------------------------------

    text_lower = text.lower()

    is_supported_link = any(
        domain in text_lower
        for domain in SUPPORTED_DOMAINS
    )


    if is_supported_link:

        if not await is_joined(
            update,
            context
        ):

            await show_force_join(
                update,
                context
            )

            return


        url_match = re.search(
            r"https?://[^\s]+",
            text
        )


        if url_match:

            target_url = (
                url_match.group(0)
                .rstrip(".,!?)]}")
            )

        else:

            target_url = text.strip()


        await handle_url_download(
            update,
            context,
            target_url
        )

        return


    # ========================================================
    # SUPPORT / ADMIN MESSAGE
    # ========================================================

    username = (
        f"@{update.effective_user.username}"
        if update.effective_user.username
        else "No username"
    )


    header_text = (
        "📩 <b>New User Message</b>\n\n"
        f"👤 <b>Name:</b> "
        f"{update.effective_user.full_name}\n"
        f"🔗 <b>Username:</b> {username}\n"
        f"🆔 <b>ID:</b> "
        f"<code>{user_id}</code>"
    )


    try:

        header_msg = await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=header_text,
            parse_mode="HTML"
        )


        forwarded_msg = await update.message.forward(
            chat_id=ADMIN_ID
        )


        if "user_mapping" not in context.bot_data:

            context.bot_data[
                "user_mapping"
            ] = {}


        user_mapping = context.bot_data[
            "user_mapping"
        ]


        user_mapping[
            str(header_msg.message_id)
        ] = user_id


        user_mapping[
            str(forwarded_msg.message_id)
        ] = user_id


        await update.message.reply_text(
            "✅ መልዕክትዎ ተቀብለናል። "
            "Admin ያነበበውን መልስ ይልክልዎታል።"
        )


    except Exception as e:

        print(
            "Admin forwarding error:",
            e
        )

        try:

            await update.message.reply_text(
                "⚠️ መልዕክቱን መላክ አልተቻለም። "
                "እባክዎ እንደገና ይሞክሩ።"
            )

        except Exception:
            pass


# ============================================================
# ADMIN REPLY
# ============================================================

async def admin_reply(
    update,
    context
):

    if not update.message:
        return


    if update.effective_user.id != ADMIN_ID:
        return


    replied_msg = (
        update.message.reply_to_message
    )


    if not replied_msg:
        return


    user_mapping = context.bot_data.get(
        "user_mapping",
        {}
    )


    target_user_id = None


    # --------------------------------------------------------
    # Mapping by message ID
    # --------------------------------------------------------

    replied_id_str = str(
        replied_msg.message_id
    )


    if replied_id_str in user_mapping:

        target_user_id = user_mapping[
            replied_id_str
        ]


    # --------------------------------------------------------
    # Try forward_from
    # --------------------------------------------------------

    if (
        not target_user_id
        and replied_msg.forward_from
    ):

        target_user_id = (
            replied_msg.forward_from.id
        )


    # --------------------------------------------------------
    # Try ID from text
    # --------------------------------------------------------

    if (
        not target_user_id
        and replied_msg.text
        and "🆔 ID:" in replied_msg.text
    ):

        match = re.search(
            r"🆔 ID:\s*<code>(\d+)</code>",
            replied_msg.text
        )

        if match:

            target_user_id = int(
                match.group(1)
            )


    # --------------------------------------------------------
    # Try ID from caption
    # --------------------------------------------------------

    if (
        not target_user_id
        and replied_msg.caption
        and "🆔 ID:" in replied_msg.caption
    ):

        match = re.search(
            r"🆔 ID:\s*<code>(\d+)</code>",
            replied_msg.caption
        )

        if match:

            target_user_id = int(
                match.group(1)
            )


    # --------------------------------------------------------
    # Send reply
    # --------------------------------------------------------

    if target_user_id:

        try:

            await update.message.copy(
                chat_id=target_user_id
            )


            await update.message.reply_text(
                "✅ Reply sent to the user."
            )


        except Exception as e:

            print(
                "Admin reply error:",
                e
            )

            await update.message.reply_text(
                f"❌ Could not send reply.\n"
                f"{e}"
            )

    else:

        await update.message.reply_text(
            "❌ User ID could not be found.\n"
            "Please reply directly to the user's "
            "forwarded message or header."
        )


# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    print(
        "❌ ERROR:",
        context.error
    )


# ============================================================
# MAIN
# ============================================================

def main():

    if not TOKEN:

        raise RuntimeError(
            "❌ BOT_TOKEN environment variable is missing!"
        )


    # Start Flask before Telegram polling
    keep_alive()


    application = (
        ApplicationBuilder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )


    # --------------------------------------------------------
    # Commands
    # --------------------------------------------------------

    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )


    application.add_handler(
        CommandHandler(
            "menu",
            start
        )
    )


    application.add_handler(
        CommandHandler(
            "status",
            status_command
        )
    )


    application.add_handler(
        CommandHandler(
            "rates",
            rates_command
        )
    )


    application.add_handler(
        CommandHandler(
            "rate",
            rates_command
        )
    )


    application.add_handler(
        CommandHandler(
            "payment",
            payment_command
        )
    )


    application.add_handler(
        CommandHandler(
            "help",
            help_command
        )
    )


    application.add_handler(
        CommandHandler(
            "broadcast",
            broadcast_command
        )
    )


    # --------------------------------------------------------
    # Force Join callback
    # --------------------------------------------------------

    application.add_handler(
        CallbackQueryHandler(
            check_join,
            pattern=r"^check_join$"
        )
    )


    # --------------------------------------------------------
    # Main menu callbacks
    # --------------------------------------------------------

    application.add_handler(
        CallbackQueryHandler(
            button_callback,
            pattern=r"^(cmd_|lang_)"
        )
    )


    # --------------------------------------------------------
    # Admin replies
    # --------------------------------------------------------

    admin_filter = (
        filters.User(
            user_id=ADMIN_ID
        )
        & filters.REPLY
        & ~filters.COMMAND
    )


    application.add_handler(
        MessageHandler(
            admin_filter,
            admin_reply
        )
    )


    # --------------------------------------------------------
    # Video -> Audio
    # --------------------------------------------------------

    application.add_handler(
        MessageHandler(
            filters.VIDEO
            | filters.VIDEO_NOTE,
            convert_video_to_audio
        )
    )


    # --------------------------------------------------------
    # Other messages
    # --------------------------------------------------------

    type_filter = (
        filters.TEXT
        | filters.PHOTO
        | filters.Document.ALL
        | filters.VOICE
        | filters.AUDIO
        | filters.Sticker.ALL
    ) & ~filters.COMMAND


    application.add_handler(
        MessageHandler(
            type_filter,
            handle_user_messages
        )
    )


    # --------------------------------------------------------
    # Error handler
    # --------------------------------------------------------

    application.add_error_handler(
        error_handler
    )


    print(
        "🤖 Mame Posts Bot is running..."
    )


    application.run_polling(
        drop_pending_updates=True
    )


# ============================================================
# START PROGRAM
# ============================================================

if __name__ == "__main__":
    main()
