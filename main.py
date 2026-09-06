import os
from threading import Thread
from flask import Flask
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters
)

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

TOKEN = "8795814797:AAF8zLJ_3x9pDgHODrsNOz9zxyqsCt3l0aE"
ADMIN_ID = 6753546651

# Force Join Channel
FORCE_CHANNEL = "@mame_posts"
FORCE_CHANNEL_LINK = "https://t.me/mame_posts"


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
        return False


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

    await update.message.reply_text(
        "🔒 <b>ቦቱን ለመጠቀም ከታች ያለውን ቻናል መቀላቀል አለብዎት!</b>\n\n"
        "1️⃣ 📢 Join Channel የሚለውን ይጫኑ።\n"
        "2️⃣ ከዚያ ✅ I've Joined ይጫኑ።",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )


# ==================================================
# START COMMAND
# ==================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not await is_joined(update, context):
        await show_force_join(update, context)
        return

    keyboard = [
        ["📢 ማስታወቂያ ለማሰራት"],
        ["💰 Price"],
        ["💳Payment method"],
        ["📊 የቻናሉ Statics"],
        ["👤 My Orders"], 
        ["💬 Support"]
    ]

    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )

    await update.message.reply_text(
        "👋 <b>እንኳን ደህና መጡ!</b> 🙂\n\n"
        "📢 በቻናላችን ላይ ማስታወቂያዎን በቀላሉ ያሰሩ።\n\n"
        "👇 ከታች ያሉትን አማራጮች ይጠቀሙ።",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )


# ==================================================
# BUTTON HANDLER & USER MESSAGES
# ==================================================

async def handle_user_messages(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not update.message:
        return

    if not await is_joined(update, context):
        await show_force_join(update, context)
        return

    text = update.message.text

    if text == "💰 Price":
        await update.message.reply_text(
            "💰 <b>የማስታወቂያ ዋጋዎች</b>\n\n"
            "📌 12 Hours — <b>300 ETB</b>\n"
            "📌 24 Hours — <b>500 ETB</b>\n"
            "📌 48 Hours — <b>700 ETB</b>\n\n"
            "📢 ማስታወቂያ ለማዘዝ\n"
            "👉 📢 ማስታወቂያ ለማሰራት የሚለውን ይጫኑ።",
            parse_mode="HTML"
        )
        return

    elif text == "📢 ማስታወቂያ ለማሰራት":
        await update.message.reply_text(
            "📢 <b>ማስታወቂያ ለማዘዝ</b>\n\n"
            "📝 እባክዎ ማስታወቂያ ማሰራት የሚፈልጉትን Post (ጽሁፍ፣ ፎቶ ወይም ቪዲዮ) እዚህ ይላኩ።\n\n",
            parse_mode="HTML"
        )
        return

    elif text == "📊 የቻናሉ Statics":
        await update.message.reply_text(
            "📊 <b>Channel Statistics</b>\n\n"
            "👥 Subscribers: <b>10,000+</b>\n"
            "🔥 Engagement: <b>Active</b>\n\n"
            "📢 ማስታወቂያዎ ለብዙ ሰዎች እንዲደርስ ያድርጉ!",
            parse_mode="HTML"
        )
        return

    elif text == "👤 My Orders":
        await update.message.reply_text(
            "👤 <b>My Orders</b>\n\n"
            "📋 እስካሁን ያዘዙት ማስታወቂያ የለም።",
            parse_mode="HTML"
        )
        return

    elif text == "💳Payment method":
        await update.message.reply_text(
            "💳 <b>Payment Method</b>\n\n"
            "🏦 <b>CBE</b>\n"
            "1000528274394\n\n"
            "📱 <b>TELE BIRR</b>\n"
            "0963266849\n\n",
            parse_mode="HTML"
        )
        return

    elif text == "💬 Support":
        await update.message.reply_text(
            "💬 <b>Support</b>\n\n"
            "መልዕክትዎን እዚህ ይላኩ።\n\n"
            "👨‍💻 Admin በቅርቡ ይመልስልዎታል።",
            parse_mode="HTML"
        )
        return

    username = update.effective_user.username
    username_text = f"@{username}" if username else "No Username"

    # Send User Info to Admin
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            "📩 <b>አዲስ መልዕክት!</b>\n\n"
            f"👤 User: {update.effective_user.full_name}\n"
            f"🔗 Username: {username_text}\n"
            f"🆔 ID: <code>{update.effective_user.id}</code>"
        ),
        parse_mode="HTML"
    )

    # Forward user content
    await update.message.forward(chat_id=ADMIN_ID)

    # Confirm to user
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

        if replied_msg.forward_from:
            target_user_id = replied_msg.forward_from.id
        elif replied_msg.text and "🆔 ID:" in replied_msg.text:
            try:
                user_id_str = replied_msg.text.split("🆔 ID:")[1].split()[0]
                target_user_id = int(user_id_str)
            except Exception:
                pass

        if target_user_id:
            try:
                await update.message.copy(chat_id=target_user_id)
                await update.message.reply_text("✅ መልሱ ለተጠቃሚው ተልኳል!")
            except Exception as e:
                print("Reply Error:", e)
                await update.message.reply_text("❌ መልሱን መላክ አልተቻለም። ተጠቃሚው ቦቱን ዘግቶት ሊሆን ይችላል።")
        else:
            await update.message.reply_text("⚠️ እባክዎ ከአድሚን መረጃው (Header) መልእክት ወይም Forward ከሆነው ፋይል ላይ Reply ያድርጉ።")


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
                " እባክዎ መጀመሪያ Channel ይቀላቀሉ!🙂",
                show_alert=True
            )

    except Exception as e:
        print("Check Join Error:", e)
        await query.answer(
            "⚠️ አባልነትዎን ማረጋገጥ አልተቻለም🙂።",
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

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(check_join, pattern="^check_join$"))
    
    app.add_handler(MessageHandler(filters.User(user_id=ADMIN_ID) & filters.REPLY, admin_reply))
    
    # Corrected filter: ALL Media & Text
    user_media_filter = (
        filters.TEXT | filters.PHOTO | filters.VIDEO | 
        filters.Document.ALL | filters.VOICE | filters.AUDIO | filters.Sticker.ALL
    ) & ~filters.COMMAND
    
    app.add_handler(MessageHandler(user_media_filter, handle_user_messages))
    
    app.add_error_handler(error_handler)

    print("🤖 Mame Posts Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()
