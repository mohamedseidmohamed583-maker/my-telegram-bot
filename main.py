import os
import json
import asyncio
import io
from threading import Thread
from flask import Flask
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters
)
import yt_dlp
import qrcode
from google import genai

# ==================================================
# FLASK WEB SERVER FOR RENDER
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
TOKEN = "8795814797:AAFZIEMav95Vcm74IigPgwpR5IWH-CCkOdk"
ADMIN_ID = 6753546651

# የወሰድከውን የ Gemini API Key እዚህ ቦታ ላይ ተካው
GEMINI_API_KEY = "AQ.Ab8RN6kKcCUcwPA9V5A1K_KhTMIAnne6gXfYw1DLc2f3GtakZTQ"


FORCE_CHANNEL = "@mame_posts"
FORCE_CHANNEL_LINK = "https://t.me/mame_posts"
DATA_FILE = "user_data.json"

# Gemini AI Client Initialization
try:
    ai_client = genai.Client(api_key=GEMINI_API_KEY)
    print("✅ Gemini AI Client initialized!")
except Exception as e:
    ai_client = None
    print("AI Init Error:", e)


# ==================================================
# DATABASE MANAGEMENT
# ==================================================
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
# KEYBOARDS
# ==================================================
def get_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("📢 ማስታወቂያ ለማሰራት 🪪", callback_data="cmd_order")],
        [
            InlineKeyboardButton("💰 Price | ዋጋ", callback_data="cmd_price"),
            InlineKeyboardButton("💳 Payment Method", callback_data="cmd_payment")
        ],
        [InlineKeyboardButton("👤 My Status & Stats 📊", callback_data="cmd_status")],
        [InlineKeyboardButton("💬 Support | ድጋፍ", callback_data="cmd_support")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_keyboard():
    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="cmd_back")]]
    return InlineKeyboardMarkup(keyboard)

# ==================================================
# BOT COMMANDS REGISTRATION
# ==================================================
async def post_init(application: Application):
    try:
        commands = [
            BotCommand("start", "ቦቱን ለመጀመር"),
            BotCommand("menu", "ዋና ማውጫ"),
            BotCommand("ai", "ከ AI ጋር ለማውራት (/ai ጥያቄህ)"),
            BotCommand("status", "የእርስዎን እና የቦቱን Status ለማየት"),
            BotCommand("rates", "የማስታወቂያ ዋጋዎች"),
            BotCommand("payment", "የከፈያ መንገድ"),
            BotCommand("help", "እርዳታና ድጋፍ"),
        ]
        await application.bot.set_my_commands(commands)
        print("✅ Commands Set Successfully!")
    except Exception as e:
        print("Command Set Error:", e)

# ==================================================
# FORCE JOIN CHECK
# ==================================================
async def is_joined(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        member = await context.bot.get_chat_member(chat_id=FORCE_CHANNEL, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        print("Force Join Error:", e)
        return False

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
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    record_user_activity(user_id)

    if not await is_joined(update, context):
        await show_force_join(update, context)
        return

    start_text = (
        "👋 <b>እንኳን ወደ Ad Poster Bot በደህና መጡ!</b> ✨\n\n"
        "የሚፈልጉትን አገልግሎት ሊንክ ወይም ጽሁፍ በቀጥታ ይላኩልኝ፦\n\n"
        "📥 <b>Media Downloader:</b>\n"
        "• የ <b>Instagram Reels</b>፣ <b>TikTok</b> ወይም <b>YouTube</b> ሊንክ ይላኩልኝ።\n\n"
        "🤖 <b>AI Assistant (Smart Chat):</b>\n"
        "• የትኛውንም ጥያቄ በጽሁፍ ይላኩ፤ AI አርቲፊሻል ኢንተለጀንስ ወዲያውኑ ይመልስልዎታል።\n\n"
        "📲 <b>QR Code Generator:</b>\n"
        "• 'qr' ብለው በመጻፍ የትኛውንም ጽሁፍ ወደ QR Code መቀየር ይችላሉ።\n\n"
        "📢 <b>የማስታወቂያ አገልግሎት:</b>\n"
        "• ከታች ያሉትን በተኖች በመጫን ዋጋዎችን እና የክፍያ መንገዶችን ማየት ይችላሉ።"
    )

    await update.message.reply_text(
        start_text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML"
    )

async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    record_user_activity(update.effective_user.id)
    if not await is_joined(update, context):
        await show_force_join(update, context)
        return

    user_query = " ".join(context.args) if context.args else ""
    if not user_query:
        await update.message.reply_text("💡 <b>እባክዎ ከኮማንዱ በኋላ ጥያቄዎን ይጻፉ!</b>\n\n<i>ምሳሌ፦ /ai ስለ ኢትዮጵያ ታሪክ ንገረኝ</i>", parse_mode="HTML")
        return

    await process_ai_chat(update, user_query)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    record_user_activity(user.id)

    if not await is_joined(update, context):
        await show_force_join(update, context)
        return

    total_users, user_msg_count = get_user_stats(user.id)
    username_text = f"@{user.username}" if user.username else "የለውም"

    msg = (
        "📊 <b>የእርስዎ እና የቦቱ Status</b>\n\n"
        "👤 <b>የግል መረጃዎት፦</b>\n"
        f"• <b>ስም:</b> {user.full_name}\n"
        f"• <b>Username:</b> {username_text}\n"
        f"• <b>Telegram ID:</b> <code>{user.id}</code>\n"
        f"• <b>የላኳቸው አጠቃላይ መልዕክቶች:</b> <code>{user_msg_count}</code>\n\n"
        "🤖 <b>የቦቱ አጠቃላይ መረጃ፦</b>\n"
        f"• <b>አጠቃላይ የቦቱ ተጠቃሚዎች:</b> <code>{total_users} Users</code>\n"
        "• <b>ሁኔታ:</b> Active ✅"
    )
    await update.message.reply_text(msg, parse_mode="HTML")

async def rates_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    record_user_activity(update.effective_user.id)
    if not await is_joined(update, context):
        await show_force_join(update, context)
        return
    await update.message.reply_text(
        "💰 <b>የማስታወቂያ ዋጋዎች</b>\n\n"
        "📌 12 Hours — <b> በስምምነት ETB</b>\n"
        "📌 24 Hours — <b> 500 ETB</b>\n"
        "📌 48 Hours — <b> 700 ETB</b>\n\n"
        "የማስታወቂያውን አይነት አይተን አስተያየት እናደርጋለን!🤝።",
        parse_mode="HTML"
    )

async def payment_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    record_user_activity(update.effective_user.id)
    if not await is_joined(update, context):
        await show_force_join(update, context)
        return
    await update.message.reply_text(
        "💳 <b>Payment Method</b>\n\n"
        "🏦 <b>CBE</b>\n1000528274394\nMohammed Seid\n\n"
        "📱 <b>TELE BIRR</b>\n+251963266849\n\n",
        parse_mode="HTML"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    record_user_activity(update.effective_user.id)
    if not await is_joined(update, context):
        await show_force_join(update, context)
        return
    await update.message.reply_text(
        "💬 <b>Support & Help</b>\n\n"
        "📥 <b>ቪዲዮ ለማውረድ:</b> የ Instagram, TikTok ወይም የ YouTube ሊንክ ይላኩ።\n"
        "🤖 <b>AI ለማውራት:</b> የትኛውንም ጥያቄ በጽሁፍ ይላኩ።\n"
        "👨‍💻 ለአድሚን መልዕክት ለመላክ ድጋፍ የሚለውን በተን ይጠቀሙ።",
        parse_mode="HTML"
    )

# ==================================================
# MEDIA DOWNLOAD & AI ENGINE
# ==================================================
def download_media(url: str, output_path: str, is_audio: bool = False):
    ydl_opts = {
        'format': 'bestaudio/best' if is_audio else 'best',
        'outtmpl': output_path,
        'quiet': True,
        'no_warnings': True,
        'max_filesize': 50 * 1024 * 1024,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

def generate_qr_code(text: str):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    bio = io.BytesIO()
    bio.name = 'qrcode.png'
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

async def process_ai_chat(update: Update, prompt: str):
    if not ai_client:
        await update.message.reply_text("⚠️ <b>የ AI አገልግሎት በአሁኑ ወቅት አልተዘጋጀም።</b>", parse_mode="HTML")
        return

    status_msg = await update.message.reply_text("🤖 <b>እያሰበ ነው...</b> 💭", parse_mode="HTML")
    try:
        response = await asyncio.to_thread(
            ai_client.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt
        )
        ai_reply = response.text or "ይቅርታ፣ ለጥያቄዎ መልስ ማግኘት አልቻልኩም።"
        await status_msg.edit_text(f"🤖 <b>AI Answer:</b>\n\n{ai_reply}")
    except Exception as e:
        print("AI Error:", e)
        await status_msg.edit_text("❌ <b>በ AI መልስ አሰጣጥ ላይ ስህተት ተከሰቷል።</b>", parse_mode="HTML")

async def handle_url_download(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    is_youtube = "youtube.com" in url.lower() or "youtu.be" in url.lower()
    status_text = "🎵 <b>Extracting YouTube Audio...</b>" if is_youtube else "🚀 <b>Downloading Media...</b> 📥"
    status_msg = await update.message.reply_text(status_text, parse_mode="HTML")
    
    bot_username = context.bot.username or "mame_posts_bot"
    share_url = f"https://t.me/share/url?url=https://t.me/{bot_username}?start=share&text=Try%20this%20awesome%20Bot!🔥"
    keyboard = [[InlineKeyboardButton("🔗 Share Bot 🚀", url=share_url)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    ext = "mp3" if is_youtube else "mp4"
    file_name = f"file_{update.effective_user.id}_{update.message.message_id}.{ext}"

    try:
        await asyncio.to_thread(download_media, url, file_name, is_youtube)

        if os.path.exists(file_name):
            await status_msg.edit_text("📤 <b>Sending File...</b>", parse_mode="HTML")
            with open(file_name, 'rb') as file_data:
                if is_youtube:
                    await update.message.reply_audio(
                        audio=file_data,
                        caption=f"🎵 <b>Downloaded with</b> @{bot_username}",
                        reply_markup=reply_markup,
                        parse_mode="HTML"
                    )
                else:
                    await update.message.reply_video(
                        video=file_data,
                        caption=f"🚀 <b>Downloaded with</b> @{bot_username}",
                        reply_markup=reply_markup,
                        parse_mode="HTML"
                    )
            await status_msg.delete()
            os.remove(file_name)
        else:
            await status_msg.edit_text("❌ <b>ፋይሉን ማግኘት አልተቻለም።</b>", parse_mode="HTML")

    except Exception as e:
        print("Download Error:", e)
        if os.path.exists(file_name):
            os.remove(file_name)
        await status_msg.edit_text(
            "❌ <b>ማውረድ አልተቻለም!</b>\n\n"
            "📌 ሊንኩ ትክክለኛ መሆኑን እና ፋይሉ ከ 50MB በታች መሆኑን ያረጋግጡ።",
            parse_mode="HTML"
        )

# ==================================================
# CALLBACK QUERY & MESSAGE HANDLERS
# ==================================================
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = query.from_user

    if data == "cmd_back":
        start_text = (
            "👋 <b>እንኳን ወደ Ad Poster Bot በደህና መጡ!</b> ✨\n\n"
            "የሚፈልጉትን አገልግሎት ሊንክ ወይም ጽሁፍ በቀጥታ ይላኩልኝ፦\n\n"
            "📥 <b>Media Downloader:</b>\n"
            "• የ <b>Instagram Reels</b>፣ <b>TikTok</b> ወይም <b>YouTube</b> ሊንክ ይላኩልኝ።\n\n"
            "🤖 <b>AI Assistant (Smart Chat):</b>\n"
            "• የትኛውንም ጥያቄ በጽሁፍ ይላኩ፤ AI አርቲፊሻል ኢንተለጀንስ ወዲያውኑ ይመልስልዎታል።\n\n"
            "📲 <b>QR Code Generator:</b>\n"
            "• 'qr' ብለው በመጻፍ የትኛውንም ጽሁፍ ወደ QR Code መቀየር ይችላሉ።\n\n"
            "📢 <b>የማስታወቂያ አገልግሎት:</b>\n"
            "• ከታች ያሉትን በተኖች በመጫን ዋጋዎችን እና የክፍያ መንገዶችን ማየት ይችላሉ።"
        )
        await query.edit_message_text(start_text, reply_markup=get_main_menu_keyboard(), parse_mode="HTML")
    elif data == "cmd_price":
        await query.edit_message_text(
            "💰 <b>የማስታወቂያ ዋጋዎች</b>\n\n📌 12 Hours — <b> በስምምነት ETB</b>\n📌 24 Hours — <b> 500 ETB</b>\n📌 48 Hours — <b> 700 ETB</b>\n\nየማስታወቂያውን አይነት አይተን አስተያየት እናደርጋለን!🤝።",
            reply_markup=get_back_keyboard(),
            parse_mode="HTML"
        )
    elif data == "cmd_order":
        await query.edit_message_text(
            "📢 <b>ማስታወቂያ ለማሰራት </b>\n\n👇 እባክዎ ማስታወቂያ ማሰራት የሚፈልጉትን Post እዚህ ይላኩ👐 ።\n\n",
            reply_markup=get_back_keyboard(),
            parse_mode="HTML"
        )
    elif data == "cmd_status":
        total_users, user_msg_count = get_user_stats(user.id)
        username_text = f"@{user.username}" if user.username else "የለውም"
        msg = (
            "📊 <b>የእርስዎ እና የቦቱ Status</b>\n\n"
            "👤 <b>የግል መረጃዎት፦</b>\n"
            f"• <b>ስም:</b> {user.full_name}\n"
            f"• <b>Username:</b> {username_text}\n"
            f"• <b>Telegram ID:</b> <code>{user.id}</code>\n"
            f"• <b>የላኳቸው አጠቃላይ መልዕክቶች:</b> <code>{user_msg_count}</code>\n\n"
            "🤖 <b>የቦቱ አጠቃላይ መረጃ፦</b>\n"
            f"• <b>አጠቃላይ የቦቱ ተጠቃሚዎች:</b> <code>{total_users} Users</code>\n"
            "• <b>ሁኔታ:</b> Active ✅"
        )
        await query.edit_message_text(msg, reply_markup=get_back_keyboard(), parse_mode="HTML")
    elif data == "cmd_payment":
        await query.edit_message_text(
            "💳 <b>Payment Method</b>\n\n🏦 <b>CBE</b>\n1000528274394\nMohammed Seid\n\n📱 <b>TELE BIRR</b>\n+251963266849\n\n",
            reply_markup=get_back_keyboard(),
            parse_mode="HTML"
        )
    elif data == "cmd_support":
        await query.edit_message_text(
            "💬 <b>Support</b>\n\nለአድሚን የሚላክ መልዕክት ካለዎት እዚህ ይጻፉ።\n\n👨‍💻 Admin በቅርቡ ይመልስልዎታል።",
            reply_markup=get_back_keyboard(),
            parse_mode="HTML"
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
    text_lower = text.lower()

    # 1. URL Downloader Check (Instagram, TikTok, YouTube)
    if "http://" in text_lower or "https://" in text_lower:
        urls = [word for word in text.split() if word.startswith("http://") or word.startswith("https://")]
        target_url = urls[0] if urls else text
        if any(domain in text_lower for domain in ["instagram.com", "tiktok.com", "youtube.com", "youtu.be"]):
            await handle_url_download(update, context, target_url)
            return

    # 2. QR Code Check ('qr' የሚል ቃል ከጀመረ)
    if text_lower.startswith("qr "):
        qr_text = text[3:].strip()
        if qr_text:
            qr_img = generate_qr_code(qr_text)
            await update.message.reply_photo(
                photo=qr_img,
                caption=f"📲 <b>የእርስዎ QR Code ተዘጋጅቷል!</b>\n\nበ @{context.bot.username} የተሰራ",
                parse_mode="HTML"
            )
            return

    # 3. AI Chat Execution (ለተራ ጽሁፎች/ጥያቄዎች)
    if text and not text.startswith("/"):
        await process_ai_chat(update, text)
        return

    # 4. Non-Text Messages Forwarding to Admin
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

    if not context.bot_data.get("user_mapping"):
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

        if not target_user_id and replied_msg.forward_from:
            target_user_id = replied_msg.forward_from.id

        if not target_user_id and replied_msg.text and "🆔 ID:" in replied_msg.text:
            try:
                user_id_str = replied_msg.text.split("🆔 ID:")[1].split()[0]
                target_user_id = int(user_id_str.replace("<code>", "").replace("</code>", ""))
            except Exception:
                pass

        if target_user_id:
            try:
                await update.message.copy(chat_id=target_user_id)
                await update.message.reply_text("✅ መልሱ ተልኳል!")
            except Exception as e:
                print("Reply Error:", e)
                await update.message.reply_text("❌ መልሱን መላክ አልተቻለም።")

async def check_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    try:
        member = await context.bot.get_chat_member(chat_id=FORCE_CHANNEL, user_id=user_id)
        if member.status in ["member", "administrator", "creator"]:
            await query.edit_message_text(
                "✅ <b>ቻናሉን ተቀላቅለዋል!</b>\n\n🤖 አሁን /start የሚለውን ተጭነው ቦቱን ይጠቀሙ።",
                parse_mode="HTML"
            )
        else:
            await query.answer("እባክዎ መጀመሪያ Channel ይቀላቀሉ!🙂", show_alert=True)
    except Exception as e:
        print("Check Join Error:", e)
        await query.answer("⚠️ አባልነትዎን ማረጋገጥ አልተቻለም🙂።", show_alert=True)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print("❌ ERROR:", context.error)

# ==================================================
# MAIN EXECUTION
# ==================================================
def main():
    keep_alive()

    app = Application.builder().token(TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", start))
    app.add_handler(CommandHandler("ai", ai_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("rates", rates_command))
    app.add_handler(CommandHandler("payment", payment_command))
    app.add_handler(CommandHandler("help", help_command))

    app.add_handler(CallbackQueryHandler(check_join, pattern="^check_join$"))
    app.add_handler(CallbackQueryHandler(button_callback, pattern="^cmd_"))
    
    admin_filter = filters.User(user_id=ADMIN_ID) & filters.REPLY & ~filters.COMMAND
    app.add_handler(MessageHandler(admin_filter, admin_reply))
    
    user_media_filter = (
        filters.TEXT | filters.PHOTO | filters.VIDEO | 
        filters.Document.ALL | filters.VOICE | filters.AUDIO | filters.Sticker.ALL
    ) & ~filters.COMMAND
    
    app.add_handler(MessageHandler(user_media_filter, handle_user_messages))
    
    app.add_error_handler(error_handler)

    print("🤖 Mame Posts Bot with Gemini AI is running...")
    app.run_polling()

if __name__ == '__main__':
    main()
