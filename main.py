import os
import json
import asyncio
from threading import Thread
from flask import Flask
import yt_dlp

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

# ==================================================
# FLASK WEB SERVER (Render Port Binding)
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
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        print("Force Join Error:", e)
        return True

async def show_force_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📢 Join Channel", url=FORCE_CHANNEL_LINK)],
        [InlineKeyboardButton("✅ I've Joined", callback_data="check_join")]
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
# COMMAND HANDLERS
# ==================================================

def get_welcome_text():
    return (
        f'Hello <tg-emoji emoji-id="5305577086478489521">🚨</tg-emoji>\n\n'
        f'<tg-emoji emoji-id="5305739801314501775">✅</tg-emoji> <b>My options (ከሁሉም Social Media ላይ video ያለ watermark ማውረድ ይችላሉ!) :</b>\n\n'
        f'<tg-emoji emoji-id="5305290882742788410">🎵</tg-emoji> | <b>Tiktok: videos & photos</b>\n'
        f'<tg-emoji emoji-id="5305551797711053969">📸</tg-emoji> | <b>Instagram: reels, posts & stories</b>\n'
        f'<tg-emoji emoji-id="5305777524012262308">▶️</tg-emoji> | <b>YouTube: videos & music (Full & Shorts)</b>\n'
        f'<tg-emoji emoji-id="5305474827602140530">✖️</tg-emoji> | <b>Twitter (X): videos & voice</b>\n'
        f'<tg-emoji emoji-id="5305311717629142471">📘</tg-emoji> | <b>Facebook & Pinterest: video</b>\n\n'
        f'<b>And others Social Media:</b> <tg-emoji emoji-id="5305749202997911340">📥</tg-emoji>'
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    record_user_activity(user.id)
    if not await is_joined(update, context):
        await show_force_join(update, context)
        return
    total_users, user_msg_count = get_user_stats(user.id)
    username_text = f"@{user.username}" if user.username else "የለውም"
    msg = (
        f'📊 <b>የእርስዎ እና የቦቱ Status</b>\n\n'
        f'👤 <b>የግል መረጃዎት፦</b>\n'
        f'• <b>ስም:</b> {user.full_name}\n'
        f'• <b>Username:</b> {username_text}\n'
        f'• <b>Telegram ID:</b> <code>{user.id}</code>\n'
        f'• <b>የላኳቸው አጠቃላይ መልዕክቶች:</b> <code>{user_msg_count}</code>\n\n'
        f'🤖 <b>የቦቱ አጠቃላይ መረጃ፦</b>\n'
        f'• <b>ሁኔታ:</b> Active 🔥\n'
        f'• <b>ጠቅላላ Users:</b> <code>{total_users}</code> 👥'
    )
    await update.message.reply_text(msg, parse_mode="HTML")

async def rates_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    record_user_activity(update.effective_user.id)
    if not await is_joined(update, context):
        await show_force_join(update, context)
        return
    await update.message.reply_text(
        f'💰 <b>የማስታወቂያ ዋጋዎች</b>\n\n'
        f'📌 12 Hours — <b>በስምምነት ETB</b>\n'
        f'📌 24 Hours — <b>500 ETB</b>\n'
        f'📌 48 Hours — <b>700 ETB</b>\n\n'
        f'የፈለጉትን ምርጫ አሳውቀው የክፍያ አማራጮችን (payment method) ይጎብኙ! 🤝',
        parse_mode="HTML"
    )

async def payment_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    record_user_activity(update.effective_user.id)
    if not await is_joined(update, context):
        await show_force_join(update, context)
        return
    await update.message.reply_text(
        f'💳 <b>Payment Method</b>\n\n'
        f'🏦 <b>ንግድ ባንክ (CBE)</b>\n'
        f'<code>1000528274394</code>\n\n'
        f'Mohammed Seid\n\n'
        f'📱 <b>ቴሌ ብር (TELE BIRR)</b>\n'
        f'<code>+251963266849</code>\n\n'
        f'✅ <b>ክፍያውን ሲፈጽሙ ስክሪን ሹቱን ይላኩ!</b>',
        parse_mode="HTML"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    record_user_activity(update.effective_user.id)
    if not await is_joined(update, context):
        await show_force_join(update, context)
        return
    await update.message.reply_text(
        f'💬 <b>Support & Downloader Help</b>\n\n'
        f'📺 <b>ቪዲዮ ለማውረድ:</b> የ YouTube, Instagram, TikTok, Facebook, Pinterest እና ሌሎች ሊንክ ቀጥታ ለቦቱ ይላኩ።\n\n'
        f'👩‍💻 ለአድሚን መልዕክት ለመላክም እዚሁ መጻፍ ይችላሉ።',
        parse_mode="HTML"
    )

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    reply_msg = update.message.reply_to_message
    has_args = bool(context.args)
    if not reply_msg and not has_args:
        await update.message.reply_text("⚠️ እባክዎ የሚተላለፈውን መልዕክት ሬፕላይ ያድርጉ ወይም ጽሁፍ ይጻፉ።")
        return

    data = load_data()
    success_count = 0
    fail_count = 0
    status_msg = await update.message.reply_text("🚀 መልዕክቱን ለተጠቃሚዎች በመላክ ላይ ይገኛል...")

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
        f"✅ <b>ብሮድካስት ተጠናቋል!</b>\n\n• የተሳካ: <code>{success_count}</code>\n• ያልተሳካ: <code>{fail_count}</code>",
        parse_mode="HTML"
    )

# ==================================================
# REAL POWERFUL ENGINE (YT-DLP)
# ==================================================

def download_video_ytdlp(url: str, file_name: str):
    """ yt-dlp ተጠቅሞ ቪዲዮውን ቀጥታ ወደ ሰርቨሩ ያወርዳል """
    ydl_opts = {
        'outtmpl': file_name,
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'quiet': True,
        'no_warnings': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

async def handle_url_download(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    status_msg = await update.message.reply_text("🚀 <b>ቪዲዮውን በማውረድ ላይ ይገኛል፣ እባክዎ ትንሽ ይጠብቁ...</b> 📥", parse_mode="HTML")
    bot_username = context.bot.username or "mame_posts_bot"
    file_path = f"video_{update.effective_user.id}.mp4"

    try:
        # ቪዲዮውን በ yt-dlp ማውረድ
        await asyncio.to_thread(download_video_ytdlp, url, file_path)

        if os.path.exists(file_path):
            await status_msg.edit_text("📤 <b>ቪዲዮውን ወደ ቴሌግራም በመላክ ላይ ይገኛል...</b>", parse_mode="HTML")
            
            with open(file_path, 'rb') as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption=f'🚀 <b>Downloaded with</b> @{bot_username} & @mame_posts\n\n✅ <b>Enjoy!</b>',
                    parse_mode="HTML"
                )
            
            await status_msg.delete()
            os.remove(file_path) # ፋይሉን ማጽዳት
            return

    except Exception as err:
        print("YT-DLP Error:", err)
        if os.path.exists(file_path):
            os.remove(file_path)

    await status_msg.edit_text(
        "😭 <b>ቪዲዮውን ማውረድ አልተቻለም!</b>\n\n"
        "የላኩት ሊንክ ትክክል መሆኑን ወይም የቪዲዮው አካውንት Private አለመሆኑን ያረጋግጡ።",
        parse_mode="HTML"
    )

# ==================================================
# BUTTON CLICK & MESSAGE HANDLERS
# ==================================================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = query.from_user

    if data == "cmd_back":
        bot_username = context.bot.username or "mame_posts_bot"
        await query.edit_message_text(get_welcome_text(), reply_markup=get_main_menu_keyboard(bot_username), parse_mode="HTML")
    elif data == "cmd_price":
        await query.edit_message_text(
            f'💰 <b>የማስታወቂያ ዋጋዎች</b>\n\n📌 12 Hours — <b>በስምምነት ETB</b>\n📌 24 Hours — <b>500 ETB</b>\n📌 48 Hours — <b>700 ETB</b>\n\nየፈለጉትን ምርጫ አሳውቀው የክፍያ አማራጮችን ይጎብኙ 🤝',
            reply_markup=get_back_keyboard(), parse_mode="HTML"
        )
    elif data == "cmd_order":
        await query.edit_message_text(
            f'📢 <b>ማስታወቂያ ለማስታወቅ/ለማሰራት</b>\n\n👇 እባክዎ ማስታወቂያ ማሰራት የሚፈልጉትን Post እዚህ ይላኩ 🙂',
            reply_markup=get_back_keyboard(), parse_mode="HTML"
        )
    elif data == "cmd_status":
        total_users, user_msg_count = get_user_stats(user.id)
        username_text = f"@{user.username}" if user.username else "የለውም"
        msg = (
            f'📊 <b>የእርስዎ እና የቦቱ Status</b>\n\n👤 <b>የግል መረጃዎት፦</b>\n• <b>ስም:</b> {user.full_name}\n• <b>Username:</b> {username_text}\n• <b>Telegram ID:</b> <code>{user.id}</code>\n• <b>የላኳቸው መልዕክቶች:</b> <code>{user_msg_count}</code>\n\n🤖 <b>የቦቱ አጠቃላይ መረጃ፦</b>\n• <b>ሁኔታ:</b> Active 🔥\n• <b>ጠቅላላ Users:</b> <code>{total_users}</code> 👥'
        )
        await query.edit_message_text(msg, reply_markup=get_back_keyboard(), parse_mode="HTML")
    elif data == "cmd_payment":
        await query.edit_message_text(
            f'💳 <b>Payment Method</b>\n\n🏦 <b>ንግድ ባንክ (CBE)</b>\n<code>1000528274394</code>\n\nMohammed Seid\n\n📱 <b>ቴሌ ብር (TELE BIRR)</b>\n<code>+251963266849</code>\n\n✅ <b>ክፍያውን ሲፈጽሙ ስክሪን ሹቱን ይላኩ!</b>',
            reply_markup=get_back_keyboard(), parse_mode="HTML"
        )
    elif data == "cmd_support":
        await query.edit_message_text(
            f'💬 <b>Support & Downloader Help</b>\n\n📺 <b>ቪዲዮ ለማውረድ:</b> የ YouTube, Instagram, TikTok, Facebook, Pinterest እና ሌሎች ሊንክ ቀጥታ ለቦቱ ይላኩ።\n\n👩‍💻 ለአድሚን መልዕክት ለመላክም እዚሁ መጻፍ ይችላሉ።',
            reply_markup=get_back_keyboard(), parse_mode="HTML"
        )

async def handle_user_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    user_id = update.effective_user.id
    record_user_activity(user_id)
    if not await is_joined(update, context):
        await show_force_join(update, context)
        return

    text = update.message.text or ""
    valid_domains = ["instagram.com", "tiktok.com", "youtube.com", "youtu.be", "facebook.com", "fb.watch", "twitter.com", "x.com", "pinterest.com", "pin.it"]
    is_supported_link = any(domain in text.lower() for domain in valid_domains)

    if is_supported_link:
        urls = [word for word in text.split() if word.startswith("http://") or word.startswith("https://")]
        target_url = urls[0] if urls else text
        await handle_url_download(update, context, target_url)
        return

    # Forward support message to admin
    username_text = f"@{update.effective_user.username}" if update.effective_user.username else "No Username"
    header_msg = await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"📩 <b>አዲስ መልዕክት!</b>\n\n👤 User: {update.effective_user.full_name}\n🔗 Username: {username_text}\n🆔 ID: <code>{user_id}</code>",
        parse_mode="HTML"
    )
    forwarded_msg = await update.message.forward(chat_id=ADMIN_ID)
    if "user_mapping" not in context.bot_data:
        context.bot_data["user_mapping"] = {}
    context.bot_data["user_mapping"][str(header_msg.message_id)] = user_id
    context.bot_data["user_mapping"][str(forwarded_msg.message_id)] = user_id

    await update.message.reply_text("✅ መልዕክትዎን ተቀብለናል።\n\n📩 በቅርቡ እንመልስልዎታለን። ❤️")

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
        elif replied_msg.forward_from:
            target_user_id = replied_msg.forward_from.id

        if target_user_id:
            try:
                await update.message.copy(chat_id=target_user_id)
                await update.message.reply_text("✅ መልሱ ለተጠቃሚው ተልኳል!")
            except Exception as e:
                await update.message.reply_text("😭 መልሱን መላክ አልተቻለም። ተጠቃሚው ቦቱን ዘግቶት ሊሆን ይችላል።")

async def check_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    try:
        member = await context.bot.get_chat_member(chat_id=FORCE_CHANNEL, user_id=user_id)
        if member.status in ["member", "administrator", "creator"]:
            await query.edit_message_text("✅ <b>ቻናሉን ተቀላቅለዋል!</b>\n\n🤖 አሁን /start የሚለውን ተጭነው ቦቱን ይጠቀሙ።", parse_mode="HTML")
        else:
            await query.answer("እባክዎ መጀመሪያ Channel ይቀላቀሉ! 🙂", show_alert=True)
    except Exception:
        await query.answer("⚠️ አባልነትዎን ማረጋገጥ አልተቻለም። 🙂", show_alert=True)

# ==================================================
# MAIN EXECUTION
# ==================================================

def main():
    keep_alive()
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()

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

    type_filter = (filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL | filters.VOICE | filters.AUDIO | filters.Sticker.ALL) & ~filters.COMMAND
    app.add_handler(MessageHandler(type_filter, handle_user_messages))

    print("🤖 Mame Posts Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()
