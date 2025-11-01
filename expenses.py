# Simple Telegram bot that listens and responds

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, ConversationHandler, CallbackQueryHandler
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from auth_data import BOT_TOKEN

import os
import json
from logger_config import logger
import asyncio
from flask import Flask, request
import threading
import requests
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
    "• /list N - show last N expenses\n"
    "• /delete ID - delete receipt with ID\n"
    "• /summary N - show expenses summary for last N months\n"
    "• /flush - upload database to cloud storage\n"
    "\nExamples:\n"
    "- Send /list 5 to see last 5 receipts\n"
    "- Send /summary 3 to see expenses for last 3 months\n"
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

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"Received photo from user {user.full_name} (ID: {user.id})")
    
    if not await check_user_access(update):
        return ConversationHandler.END
    
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
            
            await query.edit_message_text(f"✅ Receipt saved successfully! Receipt ID: {receipt_id}", reply_markup=get_persistent_keyboard())
        except Exception as e:
            logger.error(f"Failed to save receipt for user {user_id}: {str(e)}", exc_info=True)
            await query.edit_message_text(f"Failed to save receipt: {e}", reply_markup=get_persistent_keyboard())
    else:  # reject
        logger.info(f"Receipt rejected by user {user_id}")
        await query.edit_message_text("❌ Receipt rejected. Please try again with a clearer photo if needed.", reply_markup=get_persistent_keyboard())
    
    # Clean up stored data
    if user_id in receipt_data:
        del receipt_data[user_id]
    
    return ConversationHandler.END


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
    
    reminder_text = f"👋 To add an expense, please send me a photo of your receipt.\n\n{HELP_TEXT}"
    await update.message.reply_text(reminder_text, reply_markup=get_persistent_keyboard())

async def backup_task(context: ContextTypes.DEFAULT_TYPE):
    """Background task to check and upload database changes."""
    try:
        if cloud_storage.should_upload():
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

# Flask app for webhook mode
app = Flask(__name__)

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    """Handle incoming webhook requests."""
    try:
        json_data = request.get_json(force=True)
        if json_data:
            logger.debug("Received webhook request")
            update = Update.de_json(json_data, application.bot)
            # Use asyncio to run the async function
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(application.process_update(update))
            loop.close()
            logger.debug("Webhook request processed successfully")
        return 'OK'
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
        return 'Error', 500

@app.route('/health')
def health_check():
    """Health check endpoint."""
    return 'OK'

@app.route('/')
def root():
    """Root endpoint for basic info."""
    return 'Expenses Bot is running in webhook mode'

def run_webhook_server():
    """Run Flask server for webhook mode."""
    logger.info(f"Starting webhook server on port {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)

# Global application instance for webhook mode
application = None

def main():
    global application
    
    if USE_WEBHOOK:
        logger.info("Starting Expenses Bot in webhook mode for Cloud Run Service...")
        logger.info(f"Listening on port: {PORT}")
        # Note: Webhook URL will be auto-detected from Cloud Run metadata
    else:
        logger.info("Starting Expenses Bot in polling mode...")
    
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Create conversation handler for photo processing
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.PHOTO, handle_photo)],
        states={
            AWAITING_APPROVAL: [CallbackQueryHandler(handle_approval)]
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
    
    # Add the backup task to the application
    application.job_queue.run_repeating(backup_task, interval=3600)  # Run every hour
    
    if USE_WEBHOOK:
        # Auto-detect the service URL
        detected_url = get_cloud_run_service_url()
        logger.info(f"Detected webhook URL: {detected_url}")
        
        # Initialize the application
        asyncio.get_event_loop().run_until_complete(application.initialize())
        
        # Set webhook
        webhook_url = f"{detected_url}/{BOT_TOKEN}"
        logger.info(f"Setting webhook URL: {webhook_url}")
        asyncio.get_event_loop().run_until_complete(
            application.bot.set_webhook(url=webhook_url)
        )
        logger.info("Webhook set successfully")
        
        # Start the application (needed for job queue and handlers)
        asyncio.get_event_loop().run_until_complete(application.start())
        logger.info("Application started successfully")
        
        print(f'Bot is running in webhook mode on port {PORT}...')
        logger.info(f'Bot is running in webhook mode on port {PORT}...')
        
        # Run Flask server (this will block)
        run_webhook_server()
    else:
        print('Bot is running in polling mode...')
        logger.info('Bot is running in polling mode...')
        application.run_polling()

if __name__ == '__main__':
	main()
