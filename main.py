import os
from threading import Thread
from flask import Flask
from telegram import (
    Update,
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

TOKEN = "8795814797:AAHT3J4Cdd4DSrq71S-GAyanDkQuJl-9L80"
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

    if update.message:
        await update.message.reply_text(
            "🔒 <b>ቦቱን ለመጠቀም ከታች ያለውን ቻናል መቀላቀል አለብዎት!</b>\n\n"
            "1️⃣ 📢 Join Channel የሚለውን ይጫኑ።\n"
            "2️⃣ ከዚያ ✅ I've Joined ይጫኑ።",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )


# ==================================================
# START COMMAND (With Beautiful Inline Buttons)
# ==================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not await is_joined(update, context):
        await show_force_join(update, context)
        return

    # ያሸበረቁ Inline Buttons
    keyboard = [
        [
            InlineKeyboardButton("📢ማስታወቂያ ለማሰራት🪪 ", callback_data="cmd_order")
        ],
        [
            InlineKeyboardButton("💰Price | ዋጋ ", callback_data="cmd_price"),
            InlineKeyboardButton("💳 Payment Method", callback_data="cmd_payment")
        ],
        [
            InlineKeyboardButton("📊 የቻናሉ Statics 📊 ", callback_data="cmd_statics"),
            InlineKeyboardButton("👤My Order ", callback_data="cmd_myorders")
        ],
        [
            InlineKeyboardButton("💬 Support | ድጋፍ", callback_data="cmd_support")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "👋 <b>እንኳን ደህና መጡ!</b> 🙂\n\n"
        " 👇Choose an option below | ከታች ካሉት አማራጮች ይምረጡ ⚡።\n\n",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )


# ==================================================
# BUTTON CLICK HANDLER (Inline Callback Buttons)
# ==================================================

async def button_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "cmd_price":
        await query.message.reply_text(
            "💰 <b>የማስታወቂያ ዋጋዎች</b>\n\n"
            "📌 12 Hours — <b> በስምምነት ETB</b>\n"
            "📌 24 Hours — <b> 500 ETB</b>\n"
            "📌 48 Hours — <b> 700 ETB</b>\n\n"
            " የ ማስታወቂያውን አይነት አይተን አስተያየት እናደርጋለን!🤝።",
            parse_mode="HTML"
        )

    elif data == "cmd_order":
        await query.message.reply_text(
            "📢 <b>ማስታወቂያ ለማዘዝ</b>\n\n"
            "📝 እባክዎ ማስታወቂያ ማሰራት የሚፈልጉትን Post (ጽሁፍ፣ ፎቶ ወይም ቪዲዮ) እዚህ ይላኩ።\n\n",
            parse_mode="HTML"
        )

    elif data == "cmd_statics":
        await query.message.reply_text(
            "📊 <b>Channel Statistics</b>\n\n"
            "👥 Subscribers: <b>10,000+</b>\n"
            "🔥 Engagement: <b>Active</b>\n\n",
            parse_mode="HTML"
        )

    elif data == "cmd_myorders":
        await query.message.reply_text(
            "👤 <b>My Orders</b>\n\n"
            "📋 እስካሁን ያዘዙት ማስታወቂያ የለም።",
            parse_mode="HTML"
        )

    elif data == "cmd_payment":
        await query.message.reply_text(
            "💳 <b>Payment Method</b>\n\n"
            "🏦 <b>CBE</b>\n"
            "1000528274394\n\n"
            "📱 <b>TELE BIRR</b>\n"
            "0963266849\n\n",
            parse_mode="HTML"
        )

    elif data == "cmd_support":
        await query.message.reply_text(
            "💬 <b>Support</b>\n\n"
            "መልዕክትዎን እዚህ ይላኩ።\n\n"
            "👨‍💻 Admin በቅርቡ ይመልስልዎታል።",
            parse_mode="HTML"
        )


# ==================================================
# USER MESSAGES HANDLER (Forwarding to Admin)
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

    username = update.effective_user.username
    username_text = f"@{username}" if username else "No Username"
    user_id = update.effective_user.id

    # 1. Send User Info Header to Admin
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

    # 2. Forward the user message/media to Admin
    forwarded_msg = await update.message.forward(chat_id=ADMIN_ID)

    # Context save mapping so admin can reply directly
    if not context.bot_data.get("user_mapping"):
        context.bot_data["user_mapping"] = {}
    
    context.bot_data["user_mapping"][str(header_msg.message_id)] = user_id
    context.bot_data["user_mapping"][str(forwarded_msg.message_id)] = user_id

    # Confirm to User
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

        # Method A: Mapping check
        replied_id_str = str(replied_msg.message_id)
        if replied_id_str in user_mapping:
            target_user_id = user_mapping[replied_id_str]

        # Method B: Telegram Forward check
        if not target_user_id and replied_msg.forward_from:
            target_user_id = replied_msg.forward_from.id

        # Method C: Text check
        if not target_user_id and replied_msg.text and "🆔 ID:" in replied_msg.text:
            try:
                user_id_str = replied_msg.text.split("🆔 ID:")[1].split()[0]
                target_user_id = int(user_id_str.replace("<code>", "").replace("</code>", ""))
            except Exception:
                pass

        # Method D: Caption check
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
                await update.message.reply_text("❌ መልሱን መላክ አልተቻለም። ተጠቃሚው ቦቱን ዘግቶት ሊሆን ይችላል።")
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
    
    # Callback handler for menu inline buttons
    app.add_handler(CallbackQueryHandler(button_callback, pattern="^cmd_"))
    
    # Handler for Admin replies
    admin_filter = filters.User(user_id=ADMIN_ID) & filters.REPLY & ~filters.COMMAND
    app.add_handler(MessageHandler(admin_filter, admin_reply))
    
    # Filter for User Messages
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
