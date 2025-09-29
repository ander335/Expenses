# Simple Telegram bot that listens and responds

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from auth_data import BOT_TOKEN
import os
from gemini import parse_receipt_image
from db import add_expense


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
	await update.message.reply_text('Hello! I am your Expenses bot. Send me a photo of your shop receipt.')


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
	# Echoes back any received message
	await update.message.reply_text(f'You said: {update.message.text}')


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
	photo = update.message.photo[-1]  # Get highest resolution photo
	file = await context.bot.get_file(photo.file_id)
	file_path = f"receipt_{photo.file_id}.jpg"
	await file.download_to_drive(file_path)

	await update.message.reply_text("Processing your receipt...")

	# Send image to Gemini for parsing
	try:
		amount = parse_receipt_image(file_path)
		shop_name = "Unknown Shop"
		category = "Unknown Category"
		expense_id = add_expense(shop_name, category, float(amount))
		await update.message.reply_text(f"Expense recorded! Amount: {amount}")
	except Exception as e:
		await update.message.reply_text(f"Failed to process receipt: {e}")
	finally:
		if os.path.exists(file_path):
			os.remove(file_path)


def main():
	app = ApplicationBuilder().token(BOT_TOKEN).build()
	app.add_handler(CommandHandler('start', start))
	app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
	app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
	print('Bot is running...')
	app.run_polling()

if __name__ == '__main__':
	main()
