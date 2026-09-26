from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = "8758744215:AAFY1ggabe6AdyRzIGOaGwDPh3D2eNfgXOc"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 ברוך הבא ל-IE Deals!\nשלח לי קישור מעליאקספרס ואחפש עבורך קופונים ומחיר זול יותר 🛒")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if "aliexpress.com" in text or "a.aliexpress.com" in text:
        await update.message.reply_text("🔎 הקישור התקבל! בודק קופונים וחלופות זולות...")
    else:
        await update.message.reply_text("אנא שלח קישור תקין של מוצר מאליאקספרס 🔗")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("Bot is running...")
    app.run_polling()
