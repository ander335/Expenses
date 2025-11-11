# Simple Telegram bot that listens and responds - Main entry point

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, ConversationHandler, CallbackQueryHandler
from auth_data import BOT_TOKEN, TELEGRAM_ADMIN_ID, AI_PROVIDER

import os
import requests
import signal
import sys
from logger_config import logger
from db import cloud_storage  # Import the cloud storage instance
from db import (
    get_or_create_user, User, get_user, create_user_if_missing, 
    set_user_authorized, set_user_approval_requested
)
from security_utils import (
    SecurityException, RateLimiter, SecureFileHandler, InputValidator, SessionManager,
    rate_limiter, file_handler, session_manager, MAX_USERS
)

# Import the new modular components
from expenses_create import (
    handle_photo, handle_voice_receipt, handle_approval, handle_user_comment, 
    handle_voice_comment, add_text_receipt, AWAITING_APPROVAL
)
from expenses_view import (
    list_receipts, delete_receipt_cmd, show_receipts_by_date, show_summary,
    handle_calendar_callback, handle_persistent_buttons
)
from groups import (
    show_group_info, create_group_cmd, join_group_cmd, leave_group_cmd,
    add_user_to_group_admin, remove_user_from_group_admin, list_all_groups_admin, delete_group_admin
)

def get_admin_user_id() -> int:
    # TELEGRAM_ADMIN_ID is guaranteed valid by auth_data import
    return TELEGRAM_ADMIN_ID

def get_persistent_keyboard():
    """Create persistent buttons that are always available."""
    keyboard = [
        [
            InlineKeyboardButton("📅 Date Search", callback_data="persistent_calendar"),
            InlineKeyboardButton("📊 Summary", callback_data="persistent_summary")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# Common help text for the bot
HELP_TEXT = (
    "💰 How to add expenses:\n"
    "• 📷 Send a photo of your receipt. Add captions like \"Total: 15.50, Date: 25-10-2024\" to correct details\n"
    "• 🎙️ Send a voice message describing your purchase (e.g., \"Bought groceries for 25 euros at Tesco yesterday\")\n"
    "• ✍️ /add TEXT - add from text description (e.g., /add Lunch at restaurant for 12.50 EUR)\n"
    "\n📋 View expenses:\n"
    "• /list N - show last N added expenses\n"
    "• /delete ID - delete your receipt\n"
    "\n👥 Groups:\n"
    "• /group - show current group info\n"
    "• /leavegroup - leave your current group\n"
    "\n💡 When in a group, you'll see expenses from all group members."
)

async def check_user_access(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Enhanced DB-backed access control with rate limiting and session management."""
    user = update.effective_user
    
    try:
        user_id = InputValidator.validate_user_id(user.id)
    except SecurityException as e:
        logger.error(f"Invalid user ID from Telegram: {user.id}")
        await update.message.reply_text("Authentication error. Please try again.")
        return False
    
    # Check rate limiting first
    if not rate_limiter.is_allowed(user_id):
        remaining = rate_limiter.get_remaining_time(user_id)
        logger.warning(f"Rate limit exceeded for user {user.full_name} (ID: {user_id})")
        await update.message.reply_text(
            f"Too many requests. Please wait {remaining} seconds before trying again."
        )
        return False
    
    # Validate session
    if not session_manager.validate_session(user_id):
        session_manager.create_session(user_id)
    
    # Always authorize single configured admin
    if user_id == get_admin_user_id():
        create_user_if_missing(user_id, user.full_name, is_authorized=True, approval_requested=False)
        session_manager.authenticate_session(user_id)
        return True

    db_user = get_user(user_id)
    if db_user and db_user.is_authorized:
        session_manager.authenticate_session(user_id)
        return True

    # Check if we've exceeded max users limit
    # Only count this if it's a new user to prevent existing users from being locked out
    if not db_user:
        # Simple user count check - in production you might want a more sophisticated approach
        try:
            from sqlalchemy import func
            from db import Session, User as DbUser
            session = Session()
            user_count = session.query(func.count(DbUser.user_id)).scalar()
            session.close()
            
            if user_count >= MAX_USERS:
                logger.warning(f"Max users limit ({MAX_USERS}) reached, rejecting new user {user_id}")
                await update.message.reply_text("Sorry, the bot has reached its user limit.")
                return False
        except Exception as e:
            logger.error(f"Error checking user count: {e}")

    # New user: create record and request approval
    if not db_user:
        logger.warning(f"Unauthorized (new) access attempt from {user.full_name} (ID: {user_id}) - requesting admin approval")
        create_user_if_missing(user_id, user.full_name, is_authorized=False, approval_requested=True)
        try:
            buttons = [[
                InlineKeyboardButton("✅ Approve", callback_data=f"auth_approve_{user_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"auth_reject_{user_id}")
            ]]
            admin_message = (
                "🔐 New access request:\n"
                f"User: {InputValidator.sanitize_text(user.full_name)} (ID: {user_id})\n"
                f"Username: @{user.username or 'N/A'}\n\n"
                "Approve this user to allow them to use the bot."
            )
            await context.bot.send_message(
                chat_id=get_admin_user_id(),
                text=admin_message,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        except Exception as e:
            logger.error(f"Failed to send approval request: {e}", exc_info=True)
        await update.message.reply_text("Your access request has been sent to the admin. You'll be notified once approved.")
        return False

    # Existing but not authorized (pending)
    if db_user and not db_user.is_authorized:
        if not db_user.approval_requested:
            set_user_approval_requested(user_id, True)
            try:
                buttons = [[
                    InlineKeyboardButton("✅ Approve", callback_data=f"auth_approve_{user_id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"auth_reject_{user_id}")
                ]]
                admin_message = (
                    "🔐 Access request (re-sent):\n"
                    f"User: {InputValidator.sanitize_text(user.full_name)} (ID: {user_id})\n"
                    f"Username: @{user.username or 'N/A'}"
                )
                await context.bot.send_message(
                    chat_id=get_admin_user_id(),
                    text=admin_message,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            except Exception as e:
                logger.error(f"Failed to re-send approval request: {e}", exc_info=True)
        await update.message.reply_text("Your access is pending admin approval. Please wait.")
        return False

    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"[EXPENSES_MAIN] Start command received from user {user.full_name} (ID: {user.id})")
    
    if not await check_user_access(update, context):
        logger.warning(f"[EXPENSES_MAIN] Access denied for start command from user {user.id}")
        return
    
    db_user = User(user_id=user.id, name=user.full_name)
    get_or_create_user(db_user)
    
    # Add AI provider info to welcome message
    ai_provider_name = "Gemini AI" if AI_PROVIDER == "gemini" else "OpenAI"
    welcome_text = f'Hello {user.full_name}! I am your Expenses bot powered by {ai_provider_name}.\n\n{HELP_TEXT}'
    await update.message.reply_text(welcome_text, reply_markup=get_persistent_keyboard())

async def flush_database(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"Flush command received from user {user.full_name} (ID: {user.id})")
    
    if not await check_user_access(update, context):
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

async def backup_task(context: ContextTypes.DEFAULT_TYPE):
    """Background task to check and upload database changes."""
    try:
        cloud_storage.check_and_upload_db()
        logger.info("Backup task completed successfully")
    except Exception as e:
        logger.error(f"Error in backup task: {str(e)}")

async def cleanup_task(context: ContextTypes.DEFAULT_TYPE):
    """Background task for periodic cleanup."""
    try:
        # Clean up expired sessions
        session_manager.cleanup_expired_sessions()
        logger.debug("Session cleanup completed")
        
        # Clean up any orphaned temporary files
        file_handler.cleanup_all_temp_files()
        logger.debug("Temporary file cleanup completed")
    except Exception as e:
        logger.error(f"Error in cleanup task: {str(e)}")

async def handle_user_auth_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only handler to approve or reject user access requests."""
    query = update.callback_query
    await query.answer()

    admin = update.effective_user
    admin_id = admin.id

    if admin_id != get_admin_user_id():
        logger.warning(f"Non-admin user attempted to manage auth: {admin.full_name} ({admin_id})")
        await query.edit_message_text("Only the admin can manage access requests.")
        return

    try:
        parts = query.data.split('_')  # ["auth", "approve|reject", "<user_id>"]
        if len(parts) != 3:
            await query.edit_message_text("Invalid action.")
            return
        _, action, target_id_str = parts
        target_user_id = int(target_id_str)

        target_user = get_user(target_user_id)
        target_name = target_user.name if target_user else str(target_user_id)

        if action == 'approve':
            set_user_authorized(target_user_id, True)
            set_user_approval_requested(target_user_id, False)
            await query.edit_message_text(f"✅ Approved access for {target_name} (ID: {target_user_id}).")
            # Notify the user
            try:
                await context.bot.send_message(chat_id=target_user_id, text="✅ Your access to Expenses Bot has been approved. Send /start to begin.")
            except Exception as e:
                logger.warning(f"Failed to notify approved user {target_user_id}: {e}")
        elif action == 'reject':
            set_user_authorized(target_user_id, False)
            set_user_approval_requested(target_user_id, False)
            await query.edit_message_text(f"❌ Rejected access for {target_name} (ID: {target_user_id}).")
            # Notify the user
            try:
                await context.bot.send_message(chat_id=target_user_id, text="❌ Your access request was rejected by the admin.")
            except Exception as e:
                logger.warning(f"Failed to notify rejected user {target_user_id}: {e}")
        else:
            await query.edit_message_text("Unknown action.")
    except Exception as e:
        logger.error(f"Error handling user auth decision: {e}", exc_info=True)
        await query.edit_message_text("Failed to process the request.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle any text messages that are not commands."""
    user = update.effective_user
    logger.info(f"Received text message from user {user.full_name} (ID: {user.id})")
    
    if not await check_user_access(update, context):
        return
    
    reminder_text = HELP_TEXT
    
    await update.message.reply_text(reminder_text, reply_markup=get_persistent_keyboard())

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
    
    try:
        # Clean up temporary files
        logger.info("Cleaning up temporary files...")
        file_handler.cleanup_all_temp_files()
        logger.info("Temporary file cleanup completed")
    except Exception as e:
        logger.error(f"Error during temporary file cleanup: {e}")
    
    try:
        # Clean up expired sessions
        logger.info("Cleaning up expired sessions...")
        session_manager.cleanup_expired_sessions()
        logger.info("Session cleanup completed")
    except Exception as e:
        logger.error(f"Error during session cleanup: {e}")
    
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
            MessageHandler(filters.PHOTO, lambda update, context: handle_photo(update, context, check_user_access)),
            MessageHandler(filters.VOICE, lambda update, context: handle_voice_receipt(update, context, check_user_access)),
            CommandHandler('add', lambda update, context: add_text_receipt(update, context, check_user_access)),
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
    application.add_handler(CommandHandler('list', lambda update, context: list_receipts(update, context, check_user_access)))
    application.add_handler(CommandHandler('date', lambda update, context: show_receipts_by_date(update, context, check_user_access)))
    application.add_handler(CommandHandler('delete', lambda update, context: delete_receipt_cmd(update, context, check_user_access)))
    application.add_handler(CommandHandler('summary', lambda update, context: show_summary(update, context, check_user_access)))
    application.add_handler(CommandHandler('flush', flush_database))
    application.add_handler(CommandHandler('group', lambda update, context: show_group_info(update, context, check_user_access)))
    application.add_handler(CommandHandler('creategroup', lambda update, context: create_group_cmd(update, context, check_user_access, get_admin_user_id)))
    # application.add_handler(CommandHandler('joingroup', lambda update, context: join_group_cmd(update, context, check_user_access)))  # SECURITY: Disabled - allows unauthorized access to group expenses
    application.add_handler(CommandHandler('leavegroup', lambda update, context: leave_group_cmd(update, context, check_user_access)))
    # Admin-only group management commands
    application.add_handler(CommandHandler('addusertogroup', lambda update, context: add_user_to_group_admin(update, context, check_user_access, get_admin_user_id)))
    application.add_handler(CommandHandler('removeuserfromgroup', lambda update, context: remove_user_from_group_admin(update, context, check_user_access, get_admin_user_id)))
    application.add_handler(CommandHandler('listallgroups', lambda update, context: list_all_groups_admin(update, context, check_user_access, get_admin_user_id)))
    application.add_handler(CommandHandler('deletegroup', lambda update, context: delete_group_admin(update, context, check_user_access, get_admin_user_id)))
    application.add_handler(conv_handler)
    
    # Handler for persistent buttons
    application.add_handler(CallbackQueryHandler(lambda update, context: handle_persistent_buttons(update, context, get_admin_user_id), pattern="^persistent_"))
    # Handler for calendar interactions
    application.add_handler(CallbackQueryHandler(lambda update, context: handle_calendar_callback(update, context, get_admin_user_id), pattern="^cal_"))
    # Handler for admin approvals
    application.add_handler(CallbackQueryHandler(handle_user_auth_decision, pattern=r"^auth_(approve|reject)_\d+$"))
    
    # Handler for text messages (not commands)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Add the backup task to the application - run every 10 minutes
    application.job_queue.run_repeating(backup_task, interval=600)  # Run every 10 minutes (600 seconds)
    
    # Add cleanup task - run every hour
    application.job_queue.run_repeating(cleanup_task, interval=3600)  # Run every hour
    
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