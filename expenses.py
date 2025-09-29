# Simple Telegram bot that listens and responds
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from auth_data import BOT_TOKEN

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
	await update.message.reply_text('Hello! I am your Expenses bot.')

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
	# Echoes back any received message
	await update.message.reply_text(f'You said: {update.message.text}')

def main():
	app = ApplicationBuilder().token(BOT_TOKEN).build()
	app.add_handler(CommandHandler('start', start))
	app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
	print('Bot is running...')
	app.run_polling()

if __name__ == '__main__':
	main()
