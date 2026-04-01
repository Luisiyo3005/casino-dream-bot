from telegram.ext import ApplicationBuilder, CommandHandler
import os

TOKEN = "8633765101:AAHkDeAIZvhhFz91JY_CGxpoxZzvoh-Y8kA"

async def start(update, context):
    await update.message.reply_text("Bot activo 🎰")

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))

app.run_polling()

