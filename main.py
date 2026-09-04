from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters
)

TOKEN = "8795814797:AAHT2yUzqo9U_3vow0InIxoMnfrOhr23JTQ"
ADMIN_ID = 6753546651


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        ["📢 ማስታወቂያ ለማሰራት"],
        ["💰 Price"],
        ["💳Payment method"],
        ["📊 የቻናሉ Statics" ],
        ["👤 My Orders"],
        ["💬 Support"], 
        
    ]

    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )

    await update.message.reply_text(
        "👋 እንኳን ደህና መጡ! 🙂\n\n"
        "📢 በቻናላችን ላይ ማስታወቂያችሁን በቀላሉ ያሰሩ።\n\n"
        "👇 ከታች ያሉትን አማራጮች ይጠቀሙ",
        reply_markup=reply_markup
    )


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = update.message.text

    if text == "💰 Price":

        await update.message.reply_text(
            "💰 የማስታወቂያ ዋጋዎች\n\n"
            "📌 12 hours — 300 ETB\n"
            "📌 24 Hours — 500 ETB\n"
            "📌 48 Hours — 700 ETB\n\n"
            "📢 ማስታወቂያ ለማስያዝ\n"
            "👉 📢 ማስታወቂያ እዘዝ የሚለውን ይጫኑ።"
        )

    elif text == "📢 ማስታወቂያ ለማሰራት":

        await update.message.reply_text(
            "📢 ማስታወቂያ ለማዘዝ\n\n"
            "📝 እባክዎ ማሰራት የምትፈልጉትን post ይላኩ።"
        )

    elif text == "📊 የቻናሉ Statics":

        await update.message.reply_text(
            "📊 Channel Statistics\n\n"
            "👥 Subscribers: 10,000+\n"
            " Engagment: Active 🔥"
        )

    elif text == "👤 My Orders":

        await update.message.reply_text(
            "👤 My Orders\n\n"
            "እስካሁን ያዘዙት ማስታወቂያ የለም።"
        )

    elif text == "💳Payment method":

        await update.message.reply_text(
            "💳Payment method\n\n"
            "የክፍያ አማራጮች"
            "CBE: 1000528274394"
            "TELE BIRR: 0963266849"
        )

    elif text == "💬 Support":

        await update.message.reply_text(
            "💬 Support\n\n"
            "መልዕክትዎን ያስቀምጡልኝ!።"
        )

    else:

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                "📩 አዲስ መልዕክት!\n\n"
                f"👤 User: {update.effective_user.full_name}\n"
                f"🔗 Username: @{update.effective_user.username if update.effective_user.username else 'No Username'}\n"
                f"🆔 ID: {update.effective_user.id}\n\n"
                f"💬 Message:\n{update.message.text}"
        )    
        
)
        await update.message.reply_text(
            "✅ መልዕክትዎ ተቀብለናል።\n"
            "በቅርቡ እንመልስልዎታለን። ❤️"
        )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print("❌ ERROR:", context.error)


app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))

app.add_handler(
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        buttons
    )
)

app.add_error_handler(error_handler)

print("🤖 Bot is running...")

app.run_polling()
