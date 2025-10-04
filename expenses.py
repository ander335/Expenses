# Simple Telegram bot that listens and responds

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from auth_data import BOT_TOKEN
import os
from db import add_receipt, get_or_create_user, UserData
from parse import parse_receipt_from_file


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
	user = update.effective_user
	get_or_create_user(user.id, user.full_name)
	await update.message.reply_text(f'Hello {user.full_name}! I am your Expenses bot. Send me a photo of your shop receipt.')


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
	# Echoes back any received message
	await update.message.reply_text(f'You said: {update.message.text}')


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
	photo = update.message.photo[-1]  # Get highest resolution photo
	file = await context.bot.get_file(photo.file_id)
	file_path = f"receipt_{photo.file_id}.jpg"
	await file.download_to_drive(file_path)

	await update.message.reply_text("Processing your receipt...")

	# Read from JSON file instead of parsing image
	try:
		user_id = update.effective_user.id
		user = UserData(user_id=user_id, name=update.effective_user.full_name)
		get_or_create_user(user)  # Ensure user exists
		
		# Parse and save the receipt
		receipt = parse_receipt_from_file('receipt_analysis_20251004_171452.json', user_id)
		receipt_id = add_receipt(receipt)
		await update.message.reply_text(f"Receipt recorded! Amount: {receipt.total_amount}")
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
