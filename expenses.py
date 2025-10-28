# Simple Telegram bot that listens and responds

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, ConversationHandler, CallbackQueryHandler
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from auth_data import BOT_TOKEN
import os
import json
from logger_config import logger
from db import (
    add_receipt, get_or_create_user, User, get_last_n_receipts,
    delete_receipt, get_monthly_summary
)
from parse import parse_receipt_from_gemini
from gemini import parse_receipt_image


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"Start command received from user {user.full_name} (ID: {user.id})")
    
    db_user = User(user_id=user.id, name=user.full_name)
    get_or_create_user(db_user)
    help_text = (
        f'Hello {user.full_name}! I am your Expenses bot.\n\n'
        'Available commands:\n'
        '• Send me a photo of your shop receipt to add it\n'
        '• /list N - show last N expenses\n'
        '• /delete ID - delete receipt with ID\n'
        '• /summary N - show expenses summary for last N months\n'
    )
    await update.message.reply_text(help_text)


async def list_receipts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"List command received from user {user.full_name} (ID: {user.id})")
    
    try:
        n = int(context.args[0]) if context.args else 5  # Default to last 5 receipts
        logger.info(f"Listing last {n} receipts for user {user.id}")
        if n <= 0:
            raise ValueError("Number must be positive")
    except (IndexError, ValueError):
        logger.warning(f"Invalid list command argument from user {user.id}")
        await update.message.reply_text("Please specify a positive number: /list N")
        return

    receipts = get_last_n_receipts(update.effective_user.id, n)
    if not receipts:
        await update.message.reply_text("No receipts found.")
        return

    text = "Last receipts:\n\n"
    for r in receipts:
        text += f"ID: {r.receipt_id} | {r.date or 'No date'} | {r.merchant} | {r.category} | {r.total_amount:.2f}\n"
    
    await update.message.reply_text(text)

async def delete_receipt_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"Delete command received from user {user.full_name} (ID: {user.id})")
    
    try:
        receipt_id = int(context.args[0])
        logger.info(f"Attempting to delete receipt {receipt_id} for user {user.id}")
    except (IndexError, ValueError):
        logger.warning(f"Invalid delete command argument from user {user.id}")
        await update.message.reply_text("Please specify a receipt ID: /delete ID")
        return

    try:
        if delete_receipt(receipt_id, update.effective_user.id):
            await update.message.reply_text(f"Receipt {receipt_id} deleted successfully!")
        else:
            await update.message.reply_text(f"Receipt {receipt_id} not found or not owned by you.")
    except Exception as e:
        await update.message.reply_text(f"Failed to delete receipt: {e}")

async def show_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"Summary command received from user {user.full_name} (ID: {user.id})")
    
    try:
        n = int(context.args[0]) if context.args else 3  # Default to last 3 months
        logger.info(f"Generating {n} month summary for user {user.id}")
        if n <= 0:
            raise ValueError("Number must be positive")
    except (IndexError, ValueError):
        logger.warning(f"Invalid summary command argument from user {user.id}")
        await update.message.reply_text("Please specify a positive number: /summary N")
        return

    summary = get_monthly_summary(update.effective_user.id, n)
    if not summary:
        await update.message.reply_text("No data found for the specified period.")
        return

    text = "Monthly summary:\n\n"
    for month_data in summary:
        text += (f"{month_data['month']}: "
                f"{month_data['count']} receipts, "
                f"total: {month_data['total']:.2f}\n")
    
    await update.message.reply_text(text)


# States for conversation handler
AWAITING_APPROVAL = 1

# Store temporary data
receipt_data = {}

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"Received photo from user {user.full_name} (ID: {user.id})")
    
    photo = update.message.photo[-1]  # Get highest resolution photo
    file = await context.bot.get_file(photo.file_id)
    file_path = f"receipt_{photo.file_id}.jpg"
    
    logger.info(f"Downloading receipt photo (file_id: {photo.file_id})")
    await file.download_to_drive(file_path)
    logger.info(f"Receipt photo downloaded to {file_path}")

    await update.message.reply_text("Processing your receipt...")

    try:
        # Parse image with Gemini
        logger.info(f"Sending receipt image to Gemini for analysis")
        gemini_output = parse_receipt_image(file_path)
        logger.info("Successfully received response from Gemini")
        
        # Parse the receipt data into object
        user_id = update.effective_user.id
        logger.info(f"Parsing Gemini output for user {user_id}")
        parsed_receipt = parse_receipt_from_gemini(gemini_output, user_id)
        logger.info(f"Receipt parsed successfully: {parsed_receipt.merchant}, {parsed_receipt.total_amount:.2f}, {len(parsed_receipt.positions)} items")
        
        # Store the parsed receipt object
        receipt_data[user_id] = {
            "parsed_receipt": parsed_receipt
        }
        logger.info(f"Temporary receipt data stored for user {user_id}")
        
        # Format the output for display
        output_text = f"Here's what I found in your receipt:\n\n"
        output_text += f"Merchant: {parsed_receipt.merchant}\n"
        output_text += f"Category: {parsed_receipt.category}\n"
        output_text += f"Total Amount: {parsed_receipt.total_amount}\n"
        output_text += f"Date: {parsed_receipt.date or 'Unknown'}\n"
        output_text += f"\nNumber of items: {len(parsed_receipt.positions)}"

        # Create approval buttons
        keyboard = [[
            InlineKeyboardButton("✅ Approve", callback_data="approve"),
            InlineKeyboardButton("❌ Reject", callback_data="reject")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(output_text, reply_markup=reply_markup)
        
        return AWAITING_APPROVAL
        
    except Exception as e:
        await update.message.reply_text(f"Failed to process receipt: {e}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
        
    return ConversationHandler.END

async def handle_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    user = update.effective_user
    logger.info(f"Received receipt approval response from user {user.full_name} (ID: {user_id})")
    
    user_data = receipt_data.get(user_id)
    
    if not user_data:
        await query.edit_message_text("Sorry, I couldn't find your receipt data. Please try again.")
        return ConversationHandler.END
    
    if query.data == "approve":
        try:
            # Get or create user
            user = User(user_id=user_id, name=update.effective_user.full_name)
            get_or_create_user(user)
            logger.info(f"User verified/created in database: {user.name} (ID: {user.user_id})")
            
            # Get the already parsed receipt and save it
            receipt = user_data["parsed_receipt"]
            logger.info(f"Saving receipt to database: {receipt.merchant}, {receipt.total_amount:.2f}")
            receipt_id = add_receipt(receipt)
            logger.info(f"Receipt saved successfully with ID: {receipt_id}")
            
            await query.edit_message_text(f"✅ Receipt saved successfully! Receipt ID: {receipt_id}")
        except Exception as e:
            logger.error(f"Failed to save receipt for user {user_id}: {str(e)}", exc_info=True)
            await query.edit_message_text(f"Failed to save receipt: {e}")
    else:  # reject
        logger.info(f"Receipt rejected by user {user_id}")
        await query.edit_message_text("❌ Receipt rejected. Please try again with a clearer photo if needed.")
    
    # Clean up stored data
    if user_id in receipt_data:
        del receipt_data[user_id]
    
    return ConversationHandler.END


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Create conversation handler for photo processing
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.PHOTO, handle_photo)],
        states={
            AWAITING_APPROVAL: [CallbackQueryHandler(handle_approval)]
        },
        fallbacks=[]
    )
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('list', list_receipts))
    app.add_handler(CommandHandler('delete', delete_receipt_cmd))
    app.add_handler(CommandHandler('summary', show_summary))
    app.add_handler(conv_handler)
    
    print('Bot is running...')
    app.run_polling()

if __name__ == '__main__':
	main()
