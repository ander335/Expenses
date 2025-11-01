# Simple Telegram bot that listens and responds

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, ConversationHandler, CallbackQueryHandler
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from auth_data import BOT_TOKEN

import os
import json
from logger_config import logger
import asyncio
import requests
import signal
import sys
from db import cloud_storage  # Import the cloud storage instance
from db import (
    add_receipt, get_or_create_user, User, get_last_n_receipts,
    delete_receipt, get_monthly_summary
)
from parse import parse_receipt_from_gemini
from gemini import parse_receipt_image

# List of allowed Telegram user IDs (integers)
ALLOWED_USERS = [
    98336105,
]

# Common help text for the bot
HELP_TEXT = (
    "Available commands:\n"
    "• Send me a photo of your shop receipt to add it\n"
    "• Send me a voice message describing your purchase to add it\n"
    "• /add TEXT - add a receipt from a text description\n"
    "• Add a caption to your photo/voice to override/correct any details\n"
    "• /list N - show last N expenses\n"
    "• /delete ID - delete receipt with ID\n"
    "• /summary N - show expenses summary for last N months\n"
    "• /flush - upload database to cloud storage\n"
    "\nExamples:\n"
    "- Send /list 5 to see last 5 receipts\n"
    "- Send /summary 3 to see expenses for last 3 months\n"
    "- Send a photo with caption \"Date: 25-10-2024, Total: 15.50\" to correct details\n"
    "- Send a voice message saying \"I bought groceries for 25 euros at Tesco yesterday\"\n"
    "- Send a photo with caption \"Convert euros to CZK using exchange rate from purchase date\"\n"
    "- Send a photo with caption \"Convert to USD\" for currency conversion\n"
    "- Send /flush to backup database to cloud"
)

def get_persistent_keyboard():
    """Create persistent buttons that are always available."""
    keyboard = [
        [
            InlineKeyboardButton("💾 Flush Database", callback_data="persistent_flush"),
            InlineKeyboardButton("📊 Summary", callback_data="persistent_summary")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def check_user_access(update: Update) -> bool:
    """Check if the user is allowed to use the bot."""
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USERS:
        logger.warning(f"Unauthorized access attempt from user {update.effective_user.full_name} (ID: {user_id})")
        await update.message.reply_text("Sorry, you are not authorized to use this bot.")
        return False
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"Start command received from user {user.full_name} (ID: {user.id})")
    
    if not await check_user_access(update):
        return
    
    db_user = User(user_id=user.id, name=user.full_name)
    get_or_create_user(db_user)
    welcome_text = f'Hello {user.full_name}! I am your Expenses bot.\n\n{HELP_TEXT}'
    await update.message.reply_text(welcome_text, reply_markup=get_persistent_keyboard())


async def list_receipts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"List command received from user {user.full_name} (ID: {user.id})")
    
    if not await check_user_access(update):
        return
    
    try:
        n = int(context.args[0]) if context.args else 5  # Default to last 5 receipts
        logger.info(f"Listing last {n} receipts for user {user.id}")
        if n <= 0:
            raise ValueError("Number must be positive")
    except (IndexError, ValueError):
        logger.warning(f"Invalid list command argument from user {user.id}")
        await update.message.reply_text("Please specify a positive number: /list N", reply_markup=get_persistent_keyboard())
        return

    receipts = get_last_n_receipts(update.effective_user.id, n)
    if not receipts:
        await update.message.reply_text("No receipts found.", reply_markup=get_persistent_keyboard())
        return

    text = "Last receipts:\n\n"
    for r in receipts:
        text += f"ID: {r.receipt_id} | {r.date or 'No date'} | {r.merchant} | {r.category} | {r.total_amount:.2f}\n"
    
    await update.message.reply_text(text, reply_markup=get_persistent_keyboard())

async def delete_receipt_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"Delete command received from user {user.full_name} (ID: {user.id})")
    
    if not await check_user_access(update):
        return
    
    try:
        receipt_id = int(context.args[0])
        logger.info(f"Attempting to delete receipt {receipt_id} for user {user.id}")
    except (IndexError, ValueError):
        logger.warning(f"Invalid delete command argument from user {user.id}")
        await update.message.reply_text("Please specify a receipt ID: /delete ID", reply_markup=get_persistent_keyboard())
        return

    try:
        if delete_receipt(receipt_id, update.effective_user.id):
            await update.message.reply_text(f"Receipt {receipt_id} deleted successfully!", reply_markup=get_persistent_keyboard())
        else:
            await update.message.reply_text(f"Receipt {receipt_id} not found or not owned by you.", reply_markup=get_persistent_keyboard())
    except Exception as e:
        await update.message.reply_text(f"Failed to delete receipt: {e}", reply_markup=get_persistent_keyboard())

async def show_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"Summary command received from user {user.full_name} (ID: {user.id})")
    
    if not await check_user_access(update):
        return
    
    try:
        n = int(context.args[0]) if context.args else 3  # Default to last 3 months
        logger.info(f"Generating {n} month summary for user {user.id}")
        if n <= 0:
            raise ValueError("Number must be positive")
    except (IndexError, ValueError):
        logger.warning(f"Invalid summary command argument from user {user.id}")
        await update.message.reply_text("Please specify a positive number: /summary N", reply_markup=get_persistent_keyboard())
        return

    summary = get_monthly_summary(update.effective_user.id, n)
    if not summary:
        await update.message.reply_text("No data found for the specified period.", reply_markup=get_persistent_keyboard())
        return

    text = "Monthly summary:\n\n"
    for month_data in summary:
        text += (f"{month_data['month']}: "
                f"{month_data['count']} receipts, "
                f"total: {month_data['total']:.2f}\n")
    
    await update.message.reply_text(text, reply_markup=get_persistent_keyboard())


async def flush_database(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"Flush command received from user {user.full_name} (ID: {user.id})")
    
    if not await check_user_access(update):
        return
    
    try:
        await update.message.reply_text("Uploading database to cloud storage...")
        logger.info(f"Starting database upload for user {user.id}")
        
        # Force upload the database to Google Cloud Storage
        success = cloud_storage.check_and_upload_db()
        
        if success:
            logger.info(f"Database successfully uploaded to GCS by user {user.id}")
            await update.message.reply_text("✅ Database successfully uploaded to Google Cloud Storage!", reply_markup=get_persistent_keyboard())
        else:
            logger.warning(f"Database upload failed or no changes detected for user {user.id}")
            await update.message.reply_text("⚠️ Database upload failed or no changes were detected.", reply_markup=get_persistent_keyboard())
            
    except Exception as e:
        logger.error(f"Error during database flush for user {user.id}: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ Failed to upload database: {str(e)}", reply_markup=get_persistent_keyboard())


# States for conversation handler
AWAITING_APPROVAL = 1

# Store temporary data
receipt_data = {}

import time

# Import the new update function
from gemini import parse_receipt_image, update_receipt_with_comment, convert_voice_to_text, parse_voice_to_receipt

async def transcribe_voice_and_notify(update: Update, context: ContextTypes.DEFAULT_TYPE, *, voice_file_path: str, heard_prefix: str, next_hint: str) -> str:
    """Shared helper: transcribe a voice file and immediately inform the user.

    Args:
        update: Telegram update
        context: Telegram context
        voice_file_path: Local path to the downloaded .ogg voice file
        heard_prefix: Prefix for the immediate feedback line (e.g., "🎙️ I heard:" or "🎙️ Your voice comment:")
        next_hint: Follow-up hint displayed on a new line to set expectations (e.g., "🛠️ Creating a receipt summary...")

    Returns:
        The transcribed text
    """
    logger.info(f"Starting transcription for file: {voice_file_path}")
    transcribed_text = convert_voice_to_text(voice_file_path)
    logger.info(f"Transcription result: {transcribed_text}")

    # Inform user immediately; failure here shouldn't break the flow
    immediate_message = f"{heard_prefix} \"{transcribed_text}\"\n\n{next_hint}" if next_hint else f"{heard_prefix} \"{transcribed_text}\""
    try:
        await update.message.reply_text(immediate_message)
        logger.info("Sent immediate transcription feedback to user")
    except Exception as e:
        logger.warning(f"Failed to send immediate transcription message: {str(e)}")

    return transcribed_text

async def present_parsed_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE, *, parsed_receipt, original_json, preface: str, user_text_line: str | None = None):
    """Send a preview of the parsed receipt with Approve/Reject buttons and store temp data."""
    user_id = update.effective_user.id
    # Store the parsed receipt object and original JSON
    timestamp = str(int(time.time()))
    receipt_data[user_id] = {
        "parsed_receipt": parsed_receipt,
        "original_json": original_json,
        "user_comment": None,
        "latest_timestamp": timestamp,
        "latest_message_id": None
    }

    # Format the output for display
    output_text = f"{preface}\n\n"
    if user_text_line:
        output_text += f"{user_text_line}\n\n"
    if parsed_receipt.description:
        output_text += f"💬 Analysis: {parsed_receipt.description}\n\n"
    output_text += f"Merchant: {parsed_receipt.merchant}\n"
    output_text += f"Category: {parsed_receipt.category}\n"
    output_text += f"Total Amount: {parsed_receipt.total_amount}\n"
    output_text += f"Date: {parsed_receipt.date or 'Unknown'}\n"
    output_text += f"\nNumber of items: {len(parsed_receipt.positions)}\n\n"
    output_text += f"💡 To make changes, just type what you'd like to adjust or send a voice message"

    # Create approval buttons with timestamp
    keyboard = [[
        InlineKeyboardButton("✅ Approve", callback_data=f"approve_{timestamp}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"reject_{timestamp}")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Send the message and store its ID
    sent_message = await update.message.reply_text(output_text, reply_markup=reply_markup)
    receipt_data[user_id]["latest_message_id"] = sent_message.message_id
    logger.info(f"Stored message ID {sent_message.message_id} for user {user_id}")
    return AWAITING_APPROVAL

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"Received photo from user {user.full_name} (ID: {user.id})")
    
    if not await check_user_access(update):
        return ConversationHandler.END
    
    photo = update.message.photo[-1]  # Get highest resolution photo
    file = await context.bot.get_file(photo.file_id)
    file_path = f"receipt_{photo.file_id}.jpg"
    
    # Get user comment/caption if provided
    user_comment = update.message.caption if update.message.caption else None
    if user_comment:
        logger.info(f"User provided comment with photo: {user_comment}")
    else:
        logger.info("No user comment provided with photo")
    
    logger.info(f"Downloading receipt photo (file_id: {photo.file_id})")
    await file.download_to_drive(file_path)
    logger.info(f"Receipt photo downloaded to {file_path}")

    await update.message.reply_text("Processing your receipt...")

    try:
        # Parse image with Gemini, including user comment if provided
        logger.info(f"Sending receipt image to Gemini for analysis")
        gemini_output = parse_receipt_image(file_path, user_comment)
        logger.info("Successfully received response from Gemini")
        
        # Parse the receipt data into object
        user_id = update.effective_user.id
        logger.info(f"Parsing Gemini output for user {user_id}")
        parsed_receipt = parse_receipt_from_gemini(gemini_output, user_id)
        logger.info(f"Receipt parsed successfully: {parsed_receipt.merchant}, {parsed_receipt.total_amount:.2f}, {len(parsed_receipt.positions)} items")
        
        # Present preview with approval buttons using shared presenter
        return await present_parsed_receipt(
            update,
            context,
            parsed_receipt=parsed_receipt,
            original_json=gemini_output,
            preface="Here's what I found in your receipt:",
            user_text_line=(f"📝 Your comment: {user_comment}" if user_comment else None)
        )
        
    except Exception as e:
        logger.error(f"Failed to process receipt for user {update.effective_user.id}: {str(e)}", exc_info=True)
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
    
    # Extract action and timestamp from callback data
    callback_parts = query.data.split('_')
    if len(callback_parts) != 2:
        await query.edit_message_text("⚠️ This button is no longer active. Please use the buttons from the latest message.")
        return ConversationHandler.END
    
    action, timestamp = callback_parts
    latest_timestamp = user_data.get("latest_timestamp")
    
    # Check if this is the latest message
    if timestamp != latest_timestamp:
        await query.edit_message_text("⚠️ This button is no longer active. Please use the buttons from the latest message.")
        return ConversationHandler.END
    
    if action == "approve":
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
            
            # Remove buttons and show success message
            await query.edit_message_text(f"✅ Receipt saved successfully! Receipt ID: {receipt_id}", reply_markup=get_persistent_keyboard())
        except Exception as e:
            logger.error(f"Failed to save receipt for user {user_id}: {str(e)}", exc_info=True)
            await query.edit_message_text(f"Failed to save receipt: {e}", reply_markup=get_persistent_keyboard())
        
        # Clean up stored data
        if user_id in receipt_data:
            del receipt_data[user_id]
        return ConversationHandler.END
    
    elif action == "reject":
        logger.info(f"Receipt rejected by user {user_id}")
        # Remove buttons and show rejection message
        await query.edit_message_text("❌ Receipt rejected. Please try again with a clearer photo if needed.", reply_markup=get_persistent_keyboard())
        
        # Clean up stored data
        if user_id in receipt_data:
            del receipt_data[user_id]
        return ConversationHandler.END
    
    else:
        await query.edit_message_text("⚠️ Unknown action. Please use the buttons from the latest message.")
        return ConversationHandler.END


async def handle_user_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user text comments for receipt adjustments."""
    user_id = update.effective_user.id
    user = update.effective_user
    user_comment = update.message.text
    
    logger.info(f"Received user comment from {user.full_name} (ID: {user_id}): {user_comment}")
    
    user_data = receipt_data.get(user_id)
    if not user_data:
        await update.message.reply_text("Sorry, I couldn't find your receipt data. Please start over by sending a new receipt photo.")
        return ConversationHandler.END
    
    await update.message.reply_text("Processing your changes...")
    
    try:
        # Remove buttons from the previous message if it exists
        old_message_id = user_data.get("latest_message_id")
        if old_message_id:
            try:
                await context.bot.edit_message_reply_markup(
                    chat_id=user_id,
                    message_id=old_message_id,
                    reply_markup=None
                )
                logger.info(f"Removed buttons from previous message {old_message_id} for user {user_id}")
            except Exception as e:
                logger.warning(f"Could not remove buttons from previous message {old_message_id}: {str(e)}")
        
        # Get the original JSON and send update request to Gemini
        original_json = user_data["original_json"]
        logger.info(f"Sending update request to Gemini with user comment: {user_comment}")
        updated_json = update_receipt_with_comment(original_json, user_comment)
        logger.info("Successfully received updated JSON from Gemini")
        
        # Parse the updated receipt data
        updated_receipt = parse_receipt_from_gemini(updated_json, user_id)
        logger.info(f"Updated receipt parsed successfully: {updated_receipt.merchant}, {updated_receipt.total_amount:.2f}")
        
        # Present updated preview using shared presenter
        return await present_parsed_receipt(
            update,
            context,
            parsed_receipt=updated_receipt,
            original_json=updated_json,
            preface="Here's the updated receipt:",
            user_text_line=f"📝 Your changes: {user_comment}"
        )
        
    except Exception as e:
        logger.error(f"Failed to process user comment for user {user_id}: {str(e)}", exc_info=True)
        await update.message.reply_text(f"Failed to process your changes: {e}")
        return ConversationHandler.END


async def handle_voice_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice messages as receipt sources (not just comments)."""
    user = update.effective_user
    logger.info(f"Received voice receipt from user {user.full_name} (ID: {user.id})")
    
    if not await check_user_access(update):
        return ConversationHandler.END
    
    # Get the voice message
    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)
    voice_file_path = f"receipt_voice_{voice.file_id}.ogg"
    
    logger.info(f"Downloading voice receipt (file_id: {voice.file_id})")
    await file.download_to_drive(voice_file_path)
    logger.info(f"Voice receipt downloaded to {voice_file_path}")

    await update.message.reply_text("🎙️ Processing your voice receipt...")

    try:
        # Transcribe and notify user immediately
        transcribed_text = await transcribe_voice_and_notify(
            update,
            context,
            voice_file_path=voice_file_path,
            heard_prefix="🎙️ I heard:",
            next_hint="🛠️ Creating a receipt summary..."
        )
        
        # Convert transcribed text to receipt structure using Gemini
        logger.info("Converting transcribed text to receipt structure")
        gemini_output = parse_voice_to_receipt(transcribed_text)
        logger.info("Successfully received receipt structure from Gemini")
        
        # Parse the receipt data into object
        user_id = update.effective_user.id
        logger.info(f"Parsing Gemini output for user {user_id}")
        parsed_receipt = parse_receipt_from_gemini(gemini_output, user_id)
        logger.info(f"Receipt parsed successfully: {parsed_receipt.merchant}, {parsed_receipt.total_amount:.2f}, {len(parsed_receipt.positions)} items")

        # Present preview with approval buttons
        return await present_parsed_receipt(
            update,
            context,
            parsed_receipt=parsed_receipt,
            original_json=gemini_output,
            preface="Here's what I understood from your voice message:",
            user_text_line=f"🎙️ Your message: \"{transcribed_text}\""
        )
        
    except Exception as e:
        logger.error(f"Failed to process voice receipt for user {update.effective_user.id}: {str(e)}", exc_info=True)
        await update.message.reply_text(f"Failed to process voice receipt: {e}")
    finally:
        # Clean up the voice file
        if os.path.exists(voice_file_path):
            os.remove(voice_file_path)
            logger.info(f"Cleaned up voice file: {voice_file_path}")
        
    return ConversationHandler.END


async def handle_voice_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user voice messages for receipt adjustments."""
    user_id = update.effective_user.id
    user = update.effective_user
    
    logger.info(f"Received voice message from {user.full_name} (ID: {user_id})")
    
    user_data = receipt_data.get(user_id)
    if not user_data:
        await update.message.reply_text("Sorry, I couldn't find your receipt data. Please start over by sending a new receipt photo.")
        return ConversationHandler.END
    
    # Get the voice message
    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)
    voice_file_path = f"voice_{voice.file_id}.ogg"
    
    logger.info(f"Downloading voice message (file_id: {voice.file_id})")
    await file.download_to_drive(voice_file_path)
    logger.info(f"Voice message downloaded to {voice_file_path}")

    await update.message.reply_text("🎙️ Processing your voice message...")
    
    try:
        # Transcribe and notify user immediately
        user_comment = await transcribe_voice_and_notify(
            update,
            context,
            voice_file_path=voice_file_path,
            heard_prefix="🎙️ Your voice comment:",
            next_hint="🛠️ Applying your changes to the receipt..."
        )
        
        # Remove buttons from the previous message if it exists
        old_message_id = user_data.get("latest_message_id")
        if old_message_id:
            try:
                await context.bot.edit_message_reply_markup(
                    chat_id=user_id,
                    message_id=old_message_id,
                    reply_markup=None
                )
                logger.info(f"Removed buttons from previous message {old_message_id} for user {user_id}")
            except Exception as e:
                logger.warning(f"Could not remove buttons from previous message {old_message_id}: {str(e)}")
        
        # Get the original JSON and send update request to Gemini
        original_json = user_data["original_json"]
        logger.info(f"Sending update request to Gemini with transcribed comment: {user_comment}")
        updated_json = update_receipt_with_comment(original_json, user_comment)
        logger.info("Successfully received updated JSON from Gemini")
        
        # Parse the updated receipt data
        updated_receipt = parse_receipt_from_gemini(updated_json, user_id)
        logger.info(f"Updated receipt parsed successfully: {updated_receipt.merchant}, {updated_receipt.total_amount:.2f}")
        
        # Present updated preview using shared presenter
        return await present_parsed_receipt(
            update,
            context,
            parsed_receipt=updated_receipt,
            original_json=updated_json,
            preface="Here's the updated receipt:",
            user_text_line=f"🎙️ Your voice message: \"{user_comment}\""
        )
        
    except Exception as e:
        logger.error(f"Failed to process voice comment for user {user_id}: {str(e)}", exc_info=True)
        await update.message.reply_text(f"Failed to process your voice message: {e}")
        return ConversationHandler.END
    finally:
        # Clean up the voice file
        if os.path.exists(voice_file_path):
            os.remove(voice_file_path)
            logger.info(f"Cleaned up voice file: {voice_file_path}")


async def handle_persistent_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle clicks on persistent buttons."""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    user_id = user.id
    
    # Check user access for callback queries
    if user_id not in ALLOWED_USERS:
        logger.warning(f"Unauthorized access attempt from user {user.full_name} (ID: {user_id})")
        await query.edit_message_text("Sorry, you are not authorized to use this bot.")
        return
    
    if query.data == "persistent_flush":
        logger.info(f"Persistent flush button clicked by user {user.full_name} (ID: {user_id})")
        
        try:
            await query.edit_message_text("Uploading database to cloud storage...")
            logger.info(f"Starting database upload for user {user_id}")
            
            # Force upload the database to Google Cloud Storage
            success = cloud_storage.check_and_upload_db()
            
            if success:
                logger.info(f"Database successfully uploaded to GCS by user {user_id}")
                await query.edit_message_text("✅ Database successfully uploaded to Google Cloud Storage!", reply_markup=get_persistent_keyboard())
            else:
                logger.warning(f"Database upload failed or no changes detected for user {user_id}")
                await query.edit_message_text("⚠️ Database upload failed or no changes were detected.", reply_markup=get_persistent_keyboard())
                
        except Exception as e:
            logger.error(f"Error during database flush for user {user_id}: {str(e)}", exc_info=True)
            await query.edit_message_text(f"❌ Failed to upload database: {str(e)}", reply_markup=get_persistent_keyboard())
    
    elif query.data == "persistent_summary":
        logger.info(f"Persistent summary button clicked by user {user.full_name} (ID: {user_id})")
        
        try:
            # Default to last 3 months for button click
            n = 3
            logger.info(f"Generating {n} month summary for user {user_id}")
            
            summary = get_monthly_summary(user_id, n)
            if not summary:
                await query.edit_message_text("No data found for the last 3 months.", reply_markup=get_persistent_keyboard())
                return

            text = "Monthly summary (last 3 months):\n\n"
            for month_data in summary:
                text += (f"{month_data['month']}: "
                        f"{month_data['count']} receipts, "
                        f"total: {month_data['total']:.2f}\n")
            
            await query.edit_message_text(text, reply_markup=get_persistent_keyboard())
            
        except Exception as e:
            logger.error(f"Error during summary generation for user {user_id}: {str(e)}", exc_info=True)
            await query.edit_message_text(f"❌ Failed to generate summary: {str(e)}", reply_markup=get_persistent_keyboard())


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle any text messages that are not commands."""
    user = update.effective_user
    logger.info(f"Received text message from user {user.full_name} (ID: {user.id})")
    
    if not await check_user_access(update):
        return
    
    reminder_text = f"👋 To add an expense, please send me:\n• 📷 A photo of your receipt, or\n• 🎙️ A voice message describing your purchase, or\n• ✍️ Use /add followed by a text description (e.g., /add Bought sushi for 20 USD at Kyoto)\n\n💡 Tip: Add a caption to your photo/voice to correct any details like date, amount, merchant name, or request currency conversion (e.g., 'convert to USD').\n\n{HELP_TEXT}"

async def add_text_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /add command to create a receipt from a text description."""
    user = update.effective_user
    logger.info(f"Add command received from user {user.full_name} (ID: {user.id})")

    if not await check_user_access(update):
        return

    # Extract the text after /add
    user_text = " ".join(context.args) if context.args else ""
    if not user_text:
        await update.message.reply_text(
            "Please provide a purchase description after /add. Example: /add Bought groceries for 25 EUR at Tesco yesterday",
            reply_markup=get_persistent_keyboard()
        )
        return

    try:
        await update.message.reply_text("📝 Processing your text receipt...")
        logger.info("Converting text to receipt structure via Gemini")
        gemini_output = parse_voice_to_receipt(user_text)
        logger.info("Successfully received receipt structure from Gemini for text input")

        user_id = update.effective_user.id
        logger.info(f"Parsing Gemini output for user {user_id}")
        parsed_receipt = parse_receipt_from_gemini(gemini_output, user_id)
        logger.info(f"Receipt parsed successfully: {parsed_receipt.merchant}, {parsed_receipt.total_amount:.2f}, {len(parsed_receipt.positions)} items")

        return await present_parsed_receipt(
            update,
            context,
            parsed_receipt=parsed_receipt,
            original_json=gemini_output,
            preface="Here's what I understood from your text:",
            user_text_line=f"📝 Your text: \"{user_text}\""
        )
    except Exception as e:
        logger.error(f"Failed to process /add text receipt for user {user.id}: {str(e)}", exc_info=True)
        await update.message.reply_text(f"Failed to process text receipt: {e}")
        return ConversationHandler.END
    await update.message.reply_text(reminder_text, reply_markup=get_persistent_keyboard())

async def backup_task(context: ContextTypes.DEFAULT_TYPE):
    """Background task to check and upload database changes."""
    try:
        cloud_storage.check_and_upload_db()
        logger.info("Backup task completed successfully")
    except Exception as e:
        logger.error(f"Error in backup task: {str(e)}")

# Environment variables
USE_WEBHOOK = os.getenv('USE_WEBHOOK', 'false').lower() == 'true'
WEBHOOK_URL = os.getenv('WEBHOOK_URL', '')
PORT = int(os.getenv('PORT', 8080))

def get_cloud_run_service_url():
    """
    Automatically detect the Cloud Run service URL using metadata service.
    Returns the full HTTPS URL of the current Cloud Run service.
    
    Security Note: Uses HTTP to access Google's internal metadata service
    (metadata.google.internal) which is only accessible from within the
    Cloud Run instance and is Google's intended design.
    """
    try:
        # Cloud Run metadata service endpoint (internal network only)
        headers = {"Metadata-Flavor": "Google"}
        
        # Method 1: Try to construct URL from well-known metadata endpoints
        try:
            # Get project ID (string format)
            project_response = requests.get(
                "http://metadata.google.internal/computeMetadata/v1/project/project-id",
                headers=headers, timeout=5
            )
            
            # Get region from zone info
            zone_response = requests.get(
                "http://metadata.google.internal/computeMetadata/v1/instance/zone",
                headers=headers, timeout=5
            )
            
            if project_response.status_code == 200 and zone_response.status_code == 200:
                project_id = project_response.text.strip()
                zone_path = zone_response.text.strip()
                # Extract region from zone (e.g., "projects/123/zones/europe-central2-a" -> "europe-central2")
                region = zone_path.split('/')[-1].rsplit('-', 1)[0]
                
                # Try to get service name from environment or construct it
                service_name = os.getenv('K_SERVICE', 'expenses-bot')
                
                # Get project number for the actual URL format
                project_num_response = requests.get(
                    "http://metadata.google.internal/computeMetadata/v1/project/numeric-project-id",
                    headers=headers, timeout=5
                )
                
                if project_num_response.status_code == 200:
                    project_number = project_num_response.text.strip()
                    # Construct the HTTPS URL (Cloud Run services always use this format)
                    service_url = f"https://{service_name}-{project_number}.{region}.run.app"
                    logger.info(f"Constructed Cloud Run service URL: {service_url}")
                    return service_url
                else:
                    # Fallback: use project ID instead of number (less common but possible)
                    service_url = f"https://{service_name}-{project_id}.{region}.run.app"
                    logger.info(f"Constructed Cloud Run service URL (fallback): {service_url}")
                    return service_url
                
        except Exception as e:
            logger.debug(f"Could not construct URL from standard metadata: {e}")
        
        # Method 2: Check environment variables that Cloud Run might provide
        k_service = os.getenv('K_SERVICE')
        if k_service:
            # If we have the service name, try to construct a reasonable URL
            # This is a fallback that assumes standard Cloud Run URL format
            service_url = f"https://{k_service}-638029577033.europe-central2.run.app"
            logger.info(f"Using service name from K_SERVICE: {service_url}")
            return service_url
        
        # Method 3: Fallback to environment variable if provided
        if WEBHOOK_URL:
            # Ensure environment variable URL is HTTPS
            webhook_url = WEBHOOK_URL
            if webhook_url.startswith('http://'):
                webhook_url = webhook_url.replace('http://', 'https://', 1)
                logger.warning(f"Converted HTTP environment variable to HTTPS: {webhook_url}")
            logger.info(f"Using webhook URL from environment variable: {webhook_url}")
            return webhook_url
        
        # Method 4: Last resort - use the known working URL pattern
        logger.warning("Using hardcoded URL pattern as last resort")
        return "https://expenses-bot-638029577033.europe-central2.run.app"
        
    except Exception as e:
        logger.error(f"Error detecting Cloud Run service URL: {e}")
        # Return the known working URL as absolute fallback
        return "https://expenses-bot-638029577033.europe-central2.run.app"

# Global application instance
application = None

def graceful_shutdown_handler(signum, frame):
    """Handle graceful shutdown by uploading database before exit."""
    logger.info(f"Received signal {signum}. Starting graceful shutdown...")
    
    try:
        logger.info("Performing final database upload before shutdown...")
        success = cloud_storage.check_and_upload_db()
        if success:
            logger.info("Final database upload completed successfully")
        else:
            logger.warning("Final database upload had no changes or failed")
    except Exception as e:
        logger.error(f"Error during final database upload: {e}")
    
    logger.info("Graceful shutdown complete. Exiting...")
    sys.exit(0)

def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown."""
    signal.signal(signal.SIGTERM, graceful_shutdown_handler)  # Cloud Run sends SIGTERM
    signal.signal(signal.SIGINT, graceful_shutdown_handler)   # Ctrl+C
    logger.info("Signal handlers configured for graceful shutdown")

def main():
    global application
    
    # Setup signal handlers for graceful shutdown
    setup_signal_handlers()
    
    if USE_WEBHOOK:
        logger.info("Starting Expenses Bot in webhook mode for Cloud Run Service...")
        logger.info(f"Listening on port: {PORT}")
        # Note: Webhook URL will be auto-detected from Cloud Run metadata
    else:
        logger.info("Starting Expenses Bot in polling mode...")
    
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Create conversation handler for photo processing
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.PHOTO, handle_photo),
            MessageHandler(filters.VOICE, handle_voice_receipt),
            CommandHandler('add', add_text_receipt),
        ],
        states={
            AWAITING_APPROVAL: [
                CallbackQueryHandler(handle_approval, pattern="^(approve|reject)_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_comment),
                MessageHandler(filters.VOICE, handle_voice_comment)
            ]
        },
        fallbacks=[]
    )
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('list', list_receipts))
    application.add_handler(CommandHandler('delete', delete_receipt_cmd))
    application.add_handler(CommandHandler('summary', show_summary))
    application.add_handler(CommandHandler('flush', flush_database))
    application.add_handler(conv_handler)
    
    # Handler for persistent buttons
    application.add_handler(CallbackQueryHandler(handle_persistent_buttons, pattern="^persistent_"))
    
    # Handler for text messages (not commands)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Add the backup task to the application - run every 10 minutes
    application.job_queue.run_repeating(backup_task, interval=600)  # Run every 10 minutes (600 seconds)
    
    if USE_WEBHOOK:
        # Auto-detect the service URL
        detected_url = get_cloud_run_service_url()
        logger.info(f"Detected webhook URL: {detected_url}")

        # Use PTB's built-in aiohttp webhook server; this manages a single, long-lived event loop.
        webhook_url = f"{detected_url}/{BOT_TOKEN}"
        logger.info(f"Starting built-in webhook server with URL: {webhook_url}")
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=webhook_url,
            drop_pending_updates=True,
        )
    else:
        print('Bot is running in polling mode...')
        logger.info('Bot is running in polling mode...')
        application.run_polling()

if __name__ == '__main__':
	main()
