# Handlers for managing per-user custom AI prompt via /prompt command

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from logger_config import logger
from db import get_user_custom_prompt, set_user_custom_prompt
from security_utils import InputValidator, SecurityException

# Conversation states (values chosen to avoid collision with AWAITING_APPROVAL = 1)
AWAITING_PROMPT_ACTION = 11
AWAITING_PROMPT_TEXT = 12

MAX_PROMPT_LENGTH = 500


async def show_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE, check_user_access_func) -> int:
    """Handle /prompt command — show current custom prompt with Edit/Clear buttons."""
    if not await check_user_access_func(update, context):
        return ConversationHandler.END

    user_id = update.effective_user.id
    logger.info(f"[PROMPT] Showing prompt menu for user {user_id}")
    current_prompt = get_user_custom_prompt(user_id)

    if current_prompt:
        text = f"Your current AI instructions:\n\n{current_prompt}"
        buttons = [
            [
                InlineKeyboardButton("✏️ Edit", callback_data="prompt_edit"),
                InlineKeyboardButton("🗑 Clear", callback_data="prompt_clear"),
            ]
        ]
    else:
        text = (
            "No custom AI instructions set.\n\n"
            "You can define instructions that apply to every receipt, "
            "e.g. \"Convert all USD to CZK at rate 23.5\"."
        )
        buttons = [[InlineKeyboardButton("✏️ Set instructions", callback_data="prompt_edit")]]

    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    return AWAITING_PROMPT_ACTION


async def handle_prompt_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Callback for Edit button — ask user for new prompt text."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    logger.info(f"[PROMPT] Edit button clicked by user {user_id}")
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception as e:
        logger.warning(f"[PROMPT] Could not remove buttons from prompt message: {e}")
    await query.message.reply_text(
        f"Send me your custom AI instructions (max {MAX_PROMPT_LENGTH} chars).\n"
        "They will be applied to every receipt you add.\n\n"
        "Send /cancel to abort."
    )
    return AWAITING_PROMPT_TEXT


async def handle_prompt_clear_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Callback for Clear button — remove custom prompt immediately."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    set_user_custom_prompt(user_id, None)
    logger.info(f"[PROMPT] Cleared custom AI prompt for user {user_id}")
    try:
        await query.edit_message_text("✅ Custom AI instructions cleared.")
    except Exception as e:
        logger.warning(f"[PROMPT] Could not edit prompt message on clear: {e}")
        await query.message.reply_text("✅ Custom AI instructions cleared.")
    return ConversationHandler.END


async def receive_prompt_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive and save the new custom prompt text."""
    user_id = update.effective_user.id
    raw_text = update.message.text
    logger.info(f"[PROMPT] Received new prompt text from user {user_id}")

    try:
        prompt_text = InputValidator.sanitize_text(raw_text, max_length=MAX_PROMPT_LENGTH)
    except SecurityException as e:
        await update.message.reply_text(f"❌ {e.user_message}")
        return AWAITING_PROMPT_TEXT

    if not prompt_text.strip():
        await update.message.reply_text("❌ Instructions cannot be empty. Please try again or send /cancel.")
        return AWAITING_PROMPT_TEXT

    set_user_custom_prompt(user_id, prompt_text)
    logger.info(f"[PROMPT] Saved custom AI prompt for user {user_id}: {prompt_text[:80]}...")
    await update.message.reply_text(f"✅ Saved:\n\n{prompt_text}")
    return ConversationHandler.END


async def cancel_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the prompt-editing conversation."""
    logger.info(f"[PROMPT] Cancelled by user {update.effective_user.id}")
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


def build_prompt_conv_handler(check_user_access_func) -> ConversationHandler:
    """Build and return the ConversationHandler for /prompt management."""
    # Edit and Clear callbacks are in BOTH entry_points and states so that clicking
    # a button on an old /prompt message (when the user is no longer in an active
    # conversation state) still works correctly.
    return ConversationHandler(
        entry_points=[
            CommandHandler("prompt", lambda u, c: show_prompt(u, c, check_user_access_func)),
            CallbackQueryHandler(handle_prompt_edit_callback, pattern="^prompt_edit$"),
            CallbackQueryHandler(handle_prompt_clear_callback, pattern="^prompt_clear$"),
        ],
        states={
            AWAITING_PROMPT_ACTION: [
                CallbackQueryHandler(handle_prompt_edit_callback, pattern="^prompt_edit$"),
                CallbackQueryHandler(handle_prompt_clear_callback, pattern="^prompt_clear$"),
                CommandHandler("cancel", cancel_prompt),
            ],
            AWAITING_PROMPT_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_prompt_text),
                CommandHandler("cancel", cancel_prompt),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_prompt)],
        per_message=False,
    )
