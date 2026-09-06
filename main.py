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
import os
from threading import Thread
from flask import Flask

# ==================================================
# FLASK WEB SERVER (For Render Health Check)
# ==================================================
app_web = Flask('')

@app_web.route('/')
def home():
    return "Bot is Alive!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app_web.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.start()


# ==================================================
# CONFIGURATION
# ==================================================

TOKEN ="8795814797:AAF8zLJ_3x9pDgHODrsNOz9zxyqsCt3l0aE"
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
    # Check Force Join
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
# BUTTON HANDLER & MESSAGES
# ==================================================

async def buttons(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    # Check Force Join
    if not await is_joined(update, context):
        await show_force_join(update, context)
        return

    text = update.message.text

    # PRICE
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

    # ORDER AD
    elif text == "📢 ማስታወቂያ ለማሰራት":
        await update.message.reply_text(
            "📢 <b>ማስታወቂያ ለማዘዝ</b>\n\n"
            "📝 እባክዎ ማስታወቂያ ማሰራት የሚፈልጉትን Post እዚህ ይላኩ።\n\n",
            parse_mode="HTML"
        )

    # STATISTICS
    elif text == "📊 የቻናሉ Statics":
        await update.message.reply_text(
            "📊 <b>Channel Statistics</b>\n\n"
            "👥 Subscribers: <b>10,000+</b>\n"
            "🔥 Engagement: <b>Active</b>\n\n"
            "📢 ማስታወቂያዎ ለብዙ ሰዎች እንዲደርስ ያድርጉ!",
            parse_mode="HTML"
        )

    # MY ORDERS
    elif text == "👤 My Orders":
        await update.message.reply_text(
            "👤 <b>My Orders</b>\n\n"
            "📋 እስካሁን ያዘዙት ማስታወቂያ የለም።",
            parse_mode="HTML"
        )

    # PAYMENT
    elif text == "💳Payment method":
        await update.message.reply_text(
            "💳 <b>Payment Method</b>\n\n"
            "🏦 <b>CBE</b>\n"
            "1000528274394\n\n"
            "📱 <b>TELE BIRR</b>\n"
            "0963266849\n\n",
            parse_mode="HTML"
        )

    # SUPPORT
    elif text == "💬 Support":
        await update.message.reply_text(
            "💬 <b>Support</b>\n\n"
            "መልዕክትዎን እዚህ ይላኩ።\n\n"
            "👨‍💻 Admin በቅርቡ ይመልስልዎታል።",
            parse_mode="HTML"
        )

    # OTHER MESSAGES → FORWARD TO ADMIN
    else:
        username = update.effective_user.username
        username_text = f"@{username}" if username else "No Username"

        # Send info to admin and include User ID for reply identification
        msg = await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                "📩 <b>አዲስ መልዕክት!</b>\n\n"
                f"👤 User: {update.effective_user.full_name}\n"
                f"🔗 Username: {username_text}\n"
                f"🆔 ID: <code>{update.effective_user.id}</code>\n\n"
                f"💬 Message:\n"
                f"{update.message.text}"
            ),
            parse_mode="HTML"
        )

        await update.message.reply_text(
            "✅ መልዕክትዎን ተቀብለናል።\n\n"
            "📩 በቅርቡ እንመልስልዎታለን። ❤️"
        )


# ==================================================
# ADMIN REPLY TO USER HANDLER
# ==================================================

async def admin_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    # Only allow Admin to use this reply logic
    if update.effective_user.id != ADMIN_ID:
        return

    # Check if admin is replying to a message sent by the bot
    if update.message.reply_to_message and update.message.reply_to_message.text:
        original_text = update.message.reply_to_message.text
        
        # Extract User ID from the original message text
        if "🆔 ID:" in original_text:
            try:
                user_id_str = original_text.split("🆔 ID:")[1].split()[0]
                target_user_id = int(user_id_str)

                # Send reply to the target user
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"👨‍💻 <b>ከአድሚን የተላከ መልስ፦</b>\n\n{update.message.text}",
                    parse_mode="HTML"
                )

                await update.message.reply_text("✅ መልሱ ለተጠቃሚው ተልኳል!")
            except Exception as e:
                print("Reply Error:", e)
                await update.message.reply_text("❌ መልሱን መላክ አልተቻለም። User ID መለየት አልተቻለም።")


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
# START BOT
# ==================================================

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(check_join, pattern="^check_join$"))
    
    # Message Handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.User(user_id=ADMIN_ID) & filters.REPLY, admin_reply))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, buttons))
    
    app.add_error_handler(error_handler)

    print("🤖 Mame Posts Bot is running...")

    # Start Web Server
    keep_alive()

    # Start Bot Polling
    app.run_polling()

if __name__ == '__main__':
    main()
