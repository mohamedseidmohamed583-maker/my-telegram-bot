import os
import json
import io
import re
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import qrcode
import yt_dlp

# ----------------------------------------------------
# FLASK WEB SERVER FOR RENDER
# ----------------------------------------------------
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

# ----------------------------------------------------
# CONFIGURATION
# ----------------------------------------------------
TOKEN = "8795814797:AAEEmRJFtVSHBbjTmj_56kytgUaZtj5YNZ4"
ADMIN_ID = 6753446651

FORCE_CHANNEL = "@mame_posts"
FORCE_CHANNEL_LINK = "https://t.me/mame_posts"
DATA_FILE = "user_data.json"

# ----------------------------------------------------
# DATABASE MANAGEMENT
# ----------------------------------------------------
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

def get_stats():
    data = load_data()
    total_users = len(data)
    total_messages = sum(user.get("msg_count", 0) for user in data.values())
    return total_users, total_messages

# ----------------------------------------------------
# FORCE JOIN CHECK
# ----------------------------------------------------
async def check_force_join(user_id, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id=FORCE_CHANNEL, user_id=user_id)
        if member.status in ['creator', 'administrator', 'member']:
            return True
        return False
    except Exception:
        return True

async def send_force_join_msg(update: Update):
    keyboard = [
        [InlineKeyboardButton("📢 ቻናላችንን ይቀላቀሉ", url=FORCE_CHANNEL_LINK)],
        [InlineKeyboardButton("✅ ተቀላቅያለሁ / Check", callback_data="check_join")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = f"⚠️ **ቦቱን ለመጠቀም አስቀድመው ቻናላችንን ይቀላቀሉ!**\n\nከተቀላቀሉ በኋላ 'Check' የሚለውን ይጫኑ።"
    if update.message:
        await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode="Markdown")

# ----------------------------------------------------
# MAIN MENU KEYBOARD
# ----------------------------------------------------
def get_main_menu_keyboard():
    keyboard = [
        [KeyboardButton("📱 QR Code መፍጠሪያ"), KeyboardButton("💬 ድጋፍ / Support")],
        [KeyboardButton("📊 My Status & Stats")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ----------------------------------------------------
# COMMAND HANDLERS
# ----------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await check_force_join(user.id, context):
        await send_force_join_msg(update)
        return

    record_user_activity(user.id)
    
    welcome_text = (
        f" እንኳን ወደ Ad Poster Bot በሰላም መጡ፣🙂 {user.first_name}! \n\n"
        "ያሉን ዋና ዋና አገልግሎቶች:\n"
        "━━━━━━━\n"
        "📸 Instagram Downloader:👌\n"
        "└ የ Instagram Reel ወይም Post ሊንክ ሲልኩ በከፍተኛ ጥራት ያወርድልዎታል።\n\n"
        "📱 QR Code Generator:\n"
        "└ ከታች '📱 QR Code መፍጠሪያ' የሚለውን በመጫን መጠቀም ይችላሉ።\n\n"
        "💬 የአድሚን ድጋፍ:\n"
        "└ ማንኛውንም ጥያቄ ወይም አስተያየት ቀጥታ እዚህ ይጻፉ፤ ለአስተዳዳሪው ይደርሳል።\n"
        "━━━━━━━"
    )
    await update.message.reply_text(welcome_text, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        return

    total_users, total_messages = get_stats()
    stats_msg = (
        "📊 የቦቱ አጠቃላይ ስታቲስቲክስ (Stats):\n\n"
        f"👥 ጠቅላላ ተጠቃሚዎች: `{total_users}`\n"
        f"💬 የተላኩ አጠቃላይ መልእክቶች: `{total_messages}`"
    )
    await update.message.reply_text(stats_msg, parse_mode="Markdown")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        return

    msg_to_send = " ".join(context.args)
    if not msg_to_send:
        await update.message.reply_text("👐 እባክዎን የሚላከውን መልእክት ያስገቡ።\nምሳሌ: `/broadcast ሰላም ለሁላችሁም!`", parse_mode="Markdown")
        return

    data = load_data()
    success_count = 0
    fail_count = 0

    await update.message.reply_text("⏳ Broadcast መልእክት መላክ ተጀምሯል...")

    for user_id in data.keys():
        try:
            await context.bot.send_message(
                chat_id=int(user_id),
                text=f"📢 **ከአስተዳዳሪው የተላከ ማስታወቂያ:**\n\n{msg_to_send}",
                parse_mode="Markdown"
            )
            success_count += 1
        except Exception:
            fail_count += 1

    await update.message.reply_text(
        f"✅ *Broadcast ተጠናቋል!*\n\n"
        f"🟢 ደርሷቸዋል: `{success_count}` ተጠቃሚዎች\n"
        f"🔴 አልደረሰም: `{fail_count}` ተጠቃሚዎች",
        parse_mode="Markdown"
    )

# ----------------------------------------------------
# QR CODE GENERATOR
# ----------------------------------------------------
async def handle_qr(update: Update, context: ContextTypes.DEFAULT_TYPE, content: str):
    if not content:
        await update.message.reply_text("⁉️ እባክዎን ከ 'qr' በኋላ የሚቀየረውን ጽሁፍ ወይም ሊንክ ያስገቡ።\nምሳሌ: `qr https://t.me/mame_posts`", parse_mode="Markdown")
        return

    img = qrcode.make(content)
    bio = io.BytesIO()
    bio.name = 'qrcode.png'
    img.save(bio, 'PNG')
    bio.seek(0)
    await update.message.reply_photo(photo=bio, caption=f"✅ **የእርስዎ QR Code ተዘጋጅቷል!**", parse_mode="Markdown")

# ----------------------------------------------------
# INSTAGRAM DOWNLOADER
# ----------------------------------------------------
async def handle_instagram_download(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    status_msg = await update.message.reply_text("⏳ **የ Instagram ቪዲዮው በመውረድ ላይ ነው... እባክዎን ይጠብቁ!**", parse_mode="Markdown")
    
    ydl_opts = {
        'format': 'best',
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'max_filesize': 50 * 1024 * 1024,
    }

    try:
        if not os.path.exists('downloads'):
            os.makedirs('downloads')

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        if os.path.exists(filename):
            with open(filename, 'rb') as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption="✅ **የወረደው Instagram ቪዲዮ!**\n\n@mame_posts",
                    parse_mode="Markdown"
                )
            os.remove(filename)
            await status_msg.delete()
        else:
            await status_msg.edit_text("ቪዲዮውን ማግኘት አልቻልኩም😭።")
    except Exception as e:
        await status_msg.edit_text(f" ቪዲዮውን ማውረድ አልቻልኩም ። ሊንኩ ትክክለኛ መሆኑን ወይም ቪድዮው ከ 50 ሜ.ባ በላይ አለመሆኑን ያረጋግጡ።")

# ----------------------------------------------------
# MESSAGE & SUPPORT HANDLER
# ----------------------------------------------------
async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text or ""

    if not await check_force_join(user.id, context):
        await send_force_join_msg(update)
        return

    record_user_activity(user.id)

    # Keyboard Button Clicks
    if text == "📱 QR Code መፍጠሪያ":
        await update.message.reply_text("መፍጠር የሚፈልጉትን ጽሁፍ ወይም ሊንክ ከ 'qr' በኋላ አያይዘው ይላኩ።\n\nምሳሌ፦ `qr https://t.me/mame_posts`", parse_mode="Markdown")
        return

    if text == "💬 ድጋፍ / Support":
        await update.message.reply_text("ለአስተዳዳሪው መላክ የሚፈልጉትን ማንኛውንም መልእክት እዚህ ይጻፉ፤ በቀጥታ ይደርሳቸዋል።")
        return

    if text == "📊 My Status & Stats":
        data = load_data()
        user_info = data.get(str(user.id), {})
        msg_cnt = user_info.get("msg_count", 0)
        await update.message.reply_text(f"👤 **የእርስዎ ስታቲስቲክስ:**\n\n💬 የተጠቀሙበት ብዛት: `{msg_cnt}` ጊዜ", parse_mode="Markdown")
        return

    # QR Request via text
    if text.lower().startswith("qr"):
        content = text[3:].strip()
        await handle_qr(update, context, content)
        return

    # Instagram Link Check
    if "instagram.com" in text.lower():
        url_match = re.search(r'(https?://[^\s]+)', text)
        if url_match:
            await handle_instagram_download(update, context, url_match.group(0))
            return

    # Reply from Admin to User
    if user.id == ADMIN_ID and update.message.reply_to_message:
        reply_to = update.message.reply_to_message
        if reply_to.forward_from:
            try:
                await context.bot.send_message(
                    chat_id=reply_to.forward_from.id,
                    text=f"💬 **ከአስተዳዳሪው የተላከ ምላሽ:**\n\n{text}",
                    parse_mode="Markdown"
                )
                await update.message.reply_text("✅ ምላሽዎ ለተጠቃሚው ደርሷል!")
            except Exception as e:
                await update.message.reply_text(f"❌ ምላሽ መላክ አልተቻለም: {e}")
        return

    # Forward normal user messages to Admin
    if user.id != ADMIN_ID:
        await context.bot.forward_message(
            chat_id=ADMIN_ID,
            from_chat_id=update.effective_chat.id,
            message_id=update.message.message_id
        )
        await update.message.reply_text("✅ **መልእክትዎ ለአስተዳዳሪው ደርሷል!** በቅርቡ ምላሽ ይሰጥዎታል።", parse_mode="Markdown")

# ----------------------------------------------------
# MAIN APPLICATION
# ----------------------------------------------------
if __name__ == "__main__":
    keep_alive()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_messages))

    print("🤖 Bot is running smoothly with Menu Keyboard...")
    app.run_polling()



ይሄንን ነው የምትቀይረው
