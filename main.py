import os
import json
import asyncio
from threading import Thread
from flask import Flask
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
# FLASK WEB SERVER (Fixed Port Binding for Render)
# ==================================================
app_web = Flask('')

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

TOKEN = "8795814797:AAG-d-XOtl-yQfsTnuSSNeErY4b-qesRIhY"
ADMIN_ID = 6753546651

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
        data[uid_str] = {"msg_count": 0}
    
    data[uid_str]["msg_count"] = data[uid_str].get("msg_count", 0) + 1
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
            InlineKeyboardButton("🤖 Add a bot to the chat ➕", url=f"https://t.me/{bot_username}?startgroup=true")
        ],
        [
            InlineKeyboardButton("📢 ማስታወቂያ ለማሰራት 🪪", callback_data="cmd_order")
        ],
        [
            InlineKeyboardButton("💵 Price | ዋጋ", callback_data="cmd_price"),
            InlineKeyboardButton("💳 Payment Method", callback_data="cmd_payment")
        ],
        [
            InlineKeyboardButton("👤 My Status & Stats 📊", callback_data="cmd_status")
        ],
        [
            InlineKeyboardButton("💬 Support | ድጋፍ", callback_data="cmd_support")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("🔙 Back to Menu", callback_data="cmd_back")
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
            "🔒 <b>ቦቱን ለመጠቀም ከታች ያለውን ቻናል መቀላቀል አለብዎት!</b>\n\n"
            "1️⃣ 📢 Join Channel የሚለውን ይጫኑ።\n"
            "2️⃣ ከዚያ ✅ I've Joined ይጫኑ።",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )


# ==================================================
# START & MENU COMMAND
# ==================================================

def get_welcome_text():
    return (
        f'Hello <tg-emoji emoji-id="5305577086478489521">🚨</tg-emoji>\n\n'
        f'<tg-emoji emoji-id="5305739801314501775">✅</tg-emoji> <b>My options:</b>\n\n'
        f'<tg-emoji emoji-id="5305290882742788410">🎵</tg-emoji> | <b>Tiktok: videos & photos</b>\n'
        f'<tg-emoji emoji-id="5305551797711053969">📸</tg-emoji> | <b>Instagram: reels, posts & stories</b>\n'
        f'<tg-emoji emoji-id="5305777524012262308">▶️</tg-emoji> | <b>YouTube: videos & music (Full & Shorts)</b>\n'
        f'<tg-emoji emoji-id="5305474827602140530">✖️</tg-emoji> | <b>Twitter (X): videos & voice</b>\n'
        f'<tg-emoji emoji-id="5305311717629142471">📘</tg-emoji> | <b>Facebook & Pinterest: video</b>\n\n'
        f'<b>And others Social Media:</b> <tg-emoji emoji-id="5305749202997911340">📥</tg-emoji>'
    )


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user_id = update.effective_user.id
    record_user_activity(user_id)

    if not await is_joined(update, context):
        await show_force_join(update, context)
        return

    bot_username = context.bot.username or "mame_posts_bot"
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

    if not await is_joined(update, context):
        await show_force_join(update, context)
        return

    total_users, user_msg_count = get_user_stats(user.id)
    username_text = f"@{user.username}" if user.username else "የለውም"

    msg = (
        f'<tg-emoji emoji-id="5431577498364158238">📊</tg-emoji> <b>የእርስዎ እና የቦቱ Status</b>\n\n'
        f'<tg-emoji emoji-id="5875078913725571378">👤</tg-emoji> <b>የግል መረጃዎት፦</b>\n'
        f'• <b>ስም:</b> {user.full_name}\n'
        f'• <b>Username:</b> {username_text}\n'
        f'• <b>Telegram ID:</b> <code>{user.id}</code>\n'
        f'• <b>የላኳቸው አጠቃላይ መልዕክቶች:</b> <code>{user_msg_count}</code>\n\n'
        f'<tg-emoji emoji-id="5307979128543158051">🤖</tg-emoji> <b>የቦቱ አጠቃላይ መረጃ፦</b>\n'
        f'• <b>አጠቃላይ የቦቱ ተጠቃሚዎች:</b> <code>{total_users} Users</code>\n'
        f'• <b>ሁኔታ:</b> Active <tg-emoji emoji-id="5307976826440687996">🔥</tg-emoji>'
    )

    await update.message.reply_text(msg, parse_mode="HTML")


# ==================================================
# BROADCAST COMMAND
# ==================================================

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    message_to_send = None
    if context.args:
        message_to_send = " ".join(context.args)
    elif update.message.reply_to_message:
        message_to_send = update.message.reply_to_message.text or update.message.reply_to_message.caption

    if not message_to_send:
        await update.message.reply_text("⚠️ እባክዎ የሚተላለፈውን መልዕክት ከኮማንድ ጋር ይጻፉ (ለምሳሌ: `/broadcast ሰላም ለሁላችሁም`) ወይም መልዕክት ሬፕላይ ያድርጉ።")
        return

    data = load_data()
    success_count = 0
    fail_count = 0

    status_msg = await update.message.reply_text("🚀 መልዕክቱን ለተጠቃሚዎች በመላክ ላይ ይገኛል...")

    for uid_str in data.keys():
        try:
            await context.bot.send_message(
                chat_id=int(uid_str),
                text=message_to_send,
                parse_mode="HTML"
            )
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail_count += 1

    await status_msg.edit_text(
        f"✅ <b>ብሮድካስት ተጠናቋል!</b>\n\n"
        f"• የተሳካ: <code>{success_count}</code>\n"
        f"• ያልተሳካ (ቦቱን የዘጉ): <code>{fail_count}</code>",
        parse_mode="HTML"
    )


# ==================================================
# EXTRA COMMAND HANDLERS
# ==================================================

async def rates_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    record_user_activity(update.effective_user.id)
    if not await is_joined(update, context):
        await show_force_join(update, context)
        return
    await update.message.reply_text(
        f'<tg-emoji emoji-id="5447458260200214425">💰</tg-emoji> <b>የማስታወቂያ ዋጋዎች</b>\n\n'
        f'<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 12 Hours — <b>በስምምነት ETB</b>\n'
        f'<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 24 Hours — <b>500 ETB</b>\n'
        f'<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 48 Hours — <b>700 ETB</b>\n\n'
        f'የማስታወቂያውን አይነት አይተን አስተያየት እናደርጋለን! <tg-emoji emoji-id="5463249828450424568">🤝</tg-emoji>',
        parse_mode="HTML"
    )


async def payment_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    record_user_activity(update.effective_user.id)
    if not await is_joined(update, context):
        await show_force_join(update, context)
        return
    await update.message.reply_text(
        f'<tg-emoji emoji-id="5186349709169525403">💳</tg-emoji> <b>Payment Method</b>\n\n'
        f'<tg-emoji emoji-id="5961054379350955385">🏦</tg-emoji> <b>ንግድ ባንክ (CBE)</b>\n'
        f'<code> 1000528274394 </code>\n\n'
        f'Mohammed Seid\n\n'
        f'<tg-emoji emoji-id="5960632377339285724">📱</tg-emoji> <b>ቴሌ ብር (TELE BIRR)</b>\n'
        f'<code> +251963266849 </code>',
        parse_mode="HTML"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    record_user_activity(update.effective_user.id)
    if not await is_joined(update, context):
        await show_force_join(update, context)
        return
    await update.message.reply_text(
        f'<tg-emoji emoji-id="5305545479814161889">💬</tg-emoji> <b>Support & Downloader Help</b>\n\n'
        f' <tg-emoji emoji-id="5305655375142364109">📺</tg-emoji> <b>ቪዲዮ ለማውረድ:</b> የ YouTube, Instagram, TikTok, Facebook, Pinterest እና ሌሎች ሊንክ ቀጥታ ለቦቱ ይላኩ።\n\n'
        f'<tg-emoji emoji-id="5949327894567195412">👩‍💻</tg-emoji>  ለአድሚን መልዕክት ለመላክም እዚሁ መጻፍ ይችላሉ።',
        parse_mode="HTML"
    )


# ==================================================
# ULTIMATE UNLIMITED DOWNLOADER ENGINE (FIXED CLIENTS & HEADERS)
# ==================================================

def get_ydl_options(output_template=None):
    opts = {
        'format': 'bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4] / bv+ba/b',
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'geo_bypass': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['mweb', 'android', 'ios', 'web'],
            }
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Sec-Ch-Ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
        }
    }
    
    # 🍪 cookies.txt ፋይል Render ሰርቨር ላይ ካለ በራሰሰር እንዲጠቀምበት
    if os.path.exists('cookies.txt'):
        opts['cookiefile'] = 'cookies.txt'

    if output_template:
        opts['outtmpl'] = output_template

    return opts

def get_direct_video_url(url: str):
    try:
        with yt_dlp.YoutubeDL(get_ydl_options()) as ydl:
            info = ydl.extract_info(url, download=False)
            if 'url' in info:
                return info['url'], info.get('title', 'Video')
            elif 'formats' in info:
                for f in reversed(info['formats']):
                    if f.get('url') and f.get('ext') == 'mp4':
                        return f['url'], info.get('title', 'Video')
    except Exception as e:
        print("Extract URL Error:", e)
    return None, None

def download_video(url: str, output_template: str):
    with yt_dlp.YoutubeDL(get_ydl_options(output_template)) as ydl:
        ydl.download([url])


async def handle_url_download(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    status_msg = await update.message.reply_text("🚀 <b>ቪዲዮውን በማውረድ ላይ ይገኛል፣ እባክዎ ይጠብቁ...</b> 📥", parse_mode="HTML")

    bot_username = context.bot.username or "mame_posts_bot"
    share_url = f"https://t.me/share/url?url=https://t.me/{bot_username}?start=share&text=Try%20this%20awesome%20Video%20Downloader%20Bot!🔥"

    file_base = f"video_{update.effective_user.id}_{update.message.message_id}"
    output_template = f"{file_base}.%(ext)s"
    expected_file = f"{file_base}.mp4"

    try:
        await asyncio.to_thread(download_video, url, output_template)

        actual_file = expected_file
        if not os.path.exists(actual_file):
            for f in os.listdir('.'):
                if f.startswith(file_base):
                    actual_file = f
                    break

        if os.path.exists(actual_file):
            file_size = os.path.getsize(actual_file)
            
            keyboard_share = [[InlineKeyboardButton("🔗 Share Bot 🚀", url=share_url)]]
            reply_markup_share = InlineKeyboardMarkup(keyboard_share)

            # ከ 50MB በላይ ከሆነ ዳይሬክት ሊንክ ይሰጣል
            if file_size > 50 * 1024 * 1024:
                direct_url, title = await asyncio.to_thread(get_direct_video_url, url)
                await status_msg.delete()
                
                big_file_keyboard = [
                    [InlineKeyboardButton("📥 ቪዲዮውን በቀጥታ አውርድ (Direct Download)", url=direct_url or url)],
                    [InlineKeyboardButton("🔗 Share Bot 🚀", url=share_url)]
                ]
                await update.message.reply_text(
                    f"⚠️ <b>ቪዲዮው ከ 50MB በላይ በመሆኑ (Large File) በቴሌግራም ቻት በቀጥታ መላክ አልተቻለም።</b>\n\n"
                    f"ነገር ግን ከታች ባለው ቁልፍ ተጭነው በከፍተኛ ፍጥነት ማውረድ ይችላሉ! 🔥",
                    reply_markup=InlineKeyboardMarkup(big_file_keyboard),
                    parse_mode="HTML"
                )
                if os.path.exists(actual_file):
                    os.remove(actual_file)
                return

            await status_msg.edit_text("📤 <b>ቪዲዮውን በመላክ ላይ ይገኛል...</b>", parse_mode="HTML")
            with open(actual_file, 'rb') as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption=f'<tg-emoji emoji-id="5305762354187772738">🚀</tg-emoji> <b>Downloaded with</b> @{bot_username} & @mame_posts\n\n <tg-emoji emoji-id="5260463209562776385">✅</tg-emoji> <b>Enjoy! Don\'t forget to share it with your friends.</b>',
                    reply_markup=reply_markup_share,
                    parse_mode="HTML"
                )
            await status_msg.delete()
            os.remove(actual_file)
        else:
            await status_msg.edit_text("💔 <b>ቪዲዮውን ማግኘት አልተቻለም።</b>", parse_mode="HTML")

    except Exception as e:
        print("Download Error:", e)
        for f in os.listdir('.'):
            if f.startswith(file_base):
                try:
                    os.remove(f)
                except:
                    pass
                    
        await status_msg.edit_text(
            "😭 <b>ቪዲዮውን ማውረድ አልተቻለም!</b>\n\n"
            "እባክዎ የላኩት ሊንክ ትክክለኛ መሆኑን አረጋግጠው እንደገና ይሞክሩ። በጣም ይቅርታ 👐",
            parse_mode="HTML"
        )


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
            f'<tg-emoji emoji-id="5447458260200214425">💰</tg-emoji> <b>የማስታወቂያ ዋጋዎች</b>\n\n'
            f'<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 12 Hours — <b>በስምምነት ETB</b>\n'
            f'<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 24 Hours — <b>500 ETB</b>\n'
            f'<tg-emoji emoji-id="5199628545457923796">📌</tg-emoji> 48 Hours — <b>700 ETB</b>\n\n'
            f'የማስታወቂያውን አይነት አይተን አስተያየት እናደርጋለን! 🤝',
            reply_markup=get_back_keyboard(),
            parse_mode="HTML"
        )

    elif data == "cmd_order":
        await query.edit_message_text(
            f'<tg-emoji emoji-id="5197304993920616826">📢</tg-emoji> <b>ማስታወቂያ ለማስታወቅ/ለማሰራት</b>\n\n'
            f'<tg-emoji emoji-id="5305634553140912174">👇</tg-emoji> እባክዎ ማስታወቂያ ማሰራት የሚፈልጉትን Post እዚህ ይላኩ 🙂',
            reply_markup=get_back_keyboard(),
            parse_mode="HTML"
        )

    elif data == "cmd_status":
        total_users, user_msg_count = get_user_stats(user.id)
        username_text = f"@{user.username}" if user.username else "የለውም"

        msg = (
            f'<tg-emoji emoji-id="5431577498364158238">📊</tg-emoji> <b>የእርስዎ እና የቦቱ Status</b>\n\n'
            f'<tg-emoji emoji-id="5875078913725571378">👤</tg-emoji> <b>የግል መረጃዎት፦</b>\n'
            f'• <b>ስም:</b> {user.full_name}\n'
            f'• <b>Username:</b> {username_text}\n'
            f'• <b>Telegram ID:</b> <code>{user.id}</code>\n'
            f'• <b>የላኳቸው አጠቃላይ መልዕክቶች:</b> <code>{user_msg_count}</code>\n\n'
            f'<tg-emoji emoji-id="5307979128543158051">🤖</tg-emoji> <b>የቦቱ አጠቃላይ መረጃ፦</b>\n'
            f'• <b>አጠቃላይ የቦቱ ተጠቃሚዎች:</b> <code>{total_users} Users</code>\n'
            f'• <b>ሁኔታ:</b> Active <tg-emoji emoji-id="5307976826440687996">🔥</tg-emoji>'
        )
        await query.edit_message_text(
            msg, 
            reply_markup=get_back_keyboard(),
            parse_mode="HTML"
        )

    elif data == "cmd_payment":
        await query.edit_message_text(
            f'<tg-emoji emoji-id="5186349709169525403">💳</tg-emoji> <b>Payment Method</b>\n\n'
            f'<tg-emoji emoji-id="5961054379350955385">🏦</tg-emoji> <b>ንግድ ባንክ (CBE)</b>\n'
            f'<code>1000528274394</code>\n\n'
            f'Mohammed Seid\n\n'
            f'<tg-emoji emoji-id="5960632377339285724">📱</tg-emoji> ቴሌ ብር (TELE BIRR)\n'
            f'<code>+251963266849</code>',
            reply_markup=get_back_keyboard(),
            parse_mode="HTML"
        )

    elif data == "cmd_support":
        await query.edit_message_text(
            f'<tg-emoji emoji-id="5305545479814161889">💬</tg-emoji> <b>Support & Downloader Help</b>\n\n'
            f'<tg-emoji emoji-id="5305655375142364109">📺</tg-emoji> <b>ቪዲዮ ለማውረድ:</b> የ YouTube, Instagram, TikTok, Facebook, Pinterest እና ሌሎች ሊንክ ቀጥታ ለቦቱ ይላኩ።\n\n'
            f'<tg-emoji emoji-id="5949327894567195412">👩‍💻</tg-emoji> ለአድሚን መልዕክት ለመላክም እዚሁ መጻፍ ይችላሉ።',
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

    if not await is_joined(update, context):
        await show_force_join(update, context)
        return

    text = update.message.text or ""

    valid_domains = [
        "instagram.com", "tiktok.com", "youtube.com", "youtu.be", 
        "facebook.com", "fb.watch", "twitter.com", "x.com", "pinterest.com", "pin.it"
    ]
    is_supported_link = any(domain in text.lower() for domain in valid_domains)

    if is_supported_link:
        urls = [word for word in text.split() if word.startswith("http://") or word.startswith("https://")]
        target_url = urls[0] if urls else text
        await handle_url_download(update, context, target_url)
        return

    username = update.effective_user.username
    username_text = f"@{username}" if username else "No Username"

    header_msg = await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            "📩 <b>አዲስ መልዕክት!</b>\n\n"
            f"👤 User: {update.effective_user.full_name}\n"
            f"🔗 Username: {username_text}\n"
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

async def admin_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
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
                await update.message.reply_text("✅ መልሱ (ፎቶ/ቪዲዮ/ቮይስ/ጽሁፍ) ለተጠቃሚው ተልኳል!")
            except Exception as e:
                print("Reply Error:", e)
                await update.message.reply_text("😭 መልሱን መላክ አልተቻለም። ተጠቃሚው ቦቱን ዘግቶት ሊሆን ይችላል።")
        else:
            await update.message.reply_text("⚠️ እባክዎ ከቀረቡት መልእክቶች (ወይ ከጽሁፍ መረጃው ወይንም ከፎርዋርድ የተደረገው ፋይል ላይ) Reply ያድርጉ።")


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
    app.add_handler(CallbackQueryHandler(button_callback, pattern="^cmd_"))
    
    admin_filter = filters.User(user_id=ADMIN_ID) & filters.REPLY & ~filters.COMMAND
    app.add_handler(MessageHandler(admin_filter, admin_reply))
    
    type_filter = (
        filters.TEXT | filters.PHOTO | filters.VIDEO | 
        filters.Document.ALL | filters.VOICE | filters.AUDIO | filters.Sticker.ALL
    ) & ~filters.COMMAND
    
    app.add_handler(MessageHandler(type_filter, handle_user_messages))
    
    app.add_error_handler(error_handler)

    print("🤖 Mame Posts Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()
