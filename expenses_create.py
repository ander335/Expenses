# Receipt creation, parsing, and user input processing module

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from logger_config import logger
import time
import json
from parse import parse_receipt_from_gemini
from ai import parse_receipt_image, update_receipt_with_comment, convert_voice_to_text, parse_voice_to_receipt, AIServiceMalformedJSONError, format_category_with_emoji, get_category_emoji
from security_utils import (
    SecurityException, file_handler, InputValidator,
    ALLOWED_IMAGE_TYPES, ALLOWED_AUDIO_TYPES, ALLOWED_DOCUMENT_TYPES
)
from db import add_receipt, get_or_create_user, User

# States for conversation handler
AWAITING_APPROVAL = 1

# Store temporary data
receipt_data = {}

async def handle_ai_service_error(update: Update, e: Exception, operation_type: str = "receipt") -> None:
    """
    Helper function to handle AI service errors with specific messaging for malformed JSON.
    
    Args:
        update: Telegram update object
        e: The exception that occurred
        operation_type: Type of operation (receipt, voice, text, changes, voice_changes)
    """
    if isinstance(e, AIServiceMalformedJSONError):
        if operation_type == "receipt":
            message = "🤖 The AI service returned incorrectly formatted data. Please try uploading your receipt photo one more time - this usually resolves the issue."
        elif operation_type == "voice":
            message = "🤖 The AI service returned incorrectly formatted data. Please try sending your voice message one more time - this usually resolves the issue."
        elif operation_type == "text":
            message = "🤖 The AI service returned incorrectly formatted data. Please try sending your text description one more time - this usually resolves the issue."
        elif operation_type == "changes":
            message = "🤖 The AI service returned incorrectly formatted data. Please try sending your changes one more time - this usually resolves the issue."
        elif operation_type == "voice_changes":
            message = "🤖 The AI service returned incorrectly formatted data. Please try sending your voice message one more time - this usually resolves the issue."
        else:
            message = "🤖 The AI service returned incorrectly formatted data. Please try again - this usually resolves the issue."
        
        # Include full response data for troubleshooting
        if hasattr(e, 'response_data') and e.response_data:
            message += f"\n\n📋 Response data: {e.response_data}"
        
        await update.message.reply_text(message)
    else:
        # Default error messages for other types of errors
        if operation_type == "receipt":
            await update.message.reply_text("❌ Failed to process receipt. Please try again with a clearer photo.")
        elif operation_type == "voice":
            await update.message.reply_text("❌ Failed to process voice receipt. Please try again or use a photo instead.")
        elif operation_type == "text":
            await update.message.reply_text("❌ Failed to process text receipt. Please try again.")
        elif operation_type == "changes":
            await update.message.reply_text("❌ Failed to process your changes. Please try again.")
        elif operation_type == "voice_changes":
            await update.message.reply_text("❌ Failed to process your voice message. Please try typing your changes instead.")
        else:
            await update.message.reply_text("❌ An error occurred. Please try again.")

def get_persistent_keyboard():
    """Create persistent buttons that are always available."""
    keyboard = [
        [
            InlineKeyboardButton("📅 Date Search", callback_data="persistent_calendar"),
            InlineKeyboardButton("📊 Summary", callback_data="persistent_summary")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def transcribe_voice_and_notify(update: Update, context: ContextTypes.DEFAULT_TYPE, *, voice_file_path: str, heard_prefix: str, next_hint: str, processing_message_id: int = None) -> str:
    """Transcribe voice file and replace processing message with transcription result."""
    logger.info(f"Starting transcription for file: {voice_file_path}")
    transcribed_text, transcription_time = convert_voice_to_text(voice_file_path)
    logger.info(f"Transcription result: {transcribed_text}")

    # Inform user immediately; failure here shouldn't break the flow
    timing_text = f"(transcription took {transcription_time:.1f}s)"
    immediate_message = f"{heard_prefix} \"{transcribed_text}\" {timing_text}\n\n{next_hint}" if next_hint else f"{heard_prefix} \"{transcribed_text}\" {timing_text}"
    
    try:
        if processing_message_id:
            # Replace the existing processing message
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=processing_message_id,
                text=immediate_message
            )
            logger.info("Replaced processing message with transcription feedback")
        else:
            # Fall back to sending a new message if no message ID provided
            await update.message.reply_text(immediate_message)
            logger.info("Sent immediate transcription feedback to user")
    except Exception as e:
        logger.warning(f"Failed to send/edit transcription message: {str(e)}")

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
        output_text += f"💬 Description: {parsed_receipt.description}\n\n"
    output_text += f"Merchant: {parsed_receipt.merchant}\n"
    if parsed_receipt.is_income:
        output_text += f"Category: {format_category_with_emoji(parsed_receipt.category)} (Income 💰)\n"
    else:
        output_text += f"Category: {format_category_with_emoji(parsed_receipt.category)}\n"
    output_text += f"Total Amount: {parsed_receipt.total_amount}\n"
    output_text += f"Date: {parsed_receipt.date or 'Unknown'}\n"
    
    if parsed_receipt.positions and len(parsed_receipt.positions) > 0:
        output_text += f"Items ({len(parsed_receipt.positions)}):\n"
        
        # Group items by category
        items_by_category = {}
        for pos in parsed_receipt.positions:
            category = pos.category
            if category not in items_by_category:
                items_by_category[category] = []
            items_by_category[category].append(pos)
        
        # Sort categories by number of items (descending)
        sorted_categories = sorted(items_by_category.keys(), key=lambda c: len(items_by_category[c]), reverse=True)
        
        # Sort and display items by category
        for category in sorted_categories:
            emoji = get_category_emoji(category)
            category_name = category.capitalize()
            output_text += f"\n{category_name} {emoji}:\n"
            
            # Sort items within category by price (descending)
            sorted_items = sorted(items_by_category[category], key=lambda x: x.price, reverse=True)
            for pos in sorted_items:
                output_text += f"    {pos.description} - {pos.price:.1f}\n"
    
    output_text += f"\n💡 To make changes, just type what you'd like to adjust or send a voice message"

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

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE, check_user_access_func):
    """Handler for photo receipt uploads."""
    return await handle_receipt_file(update, context, check_user_access_func, file_type="photo")


async def handle_receipt_file(update: Update, context: ContextTypes.DEFAULT_TYPE, check_user_access_func, file_type: str = "document"):
    """
    Generic handler for receipt files (photos, PDFs, JPEGs).
    file_type: 'photo' for photos, 'document' for PDFs/JPEGs
    """
    user = update.effective_user
    logger.info(f"[EXPENSES_CREATE] Received {file_type} file from user {user.full_name} (ID: {user.id})")
    
    if not await check_user_access_func(update, context):
        logger.warning(f"[EXPENSES_CREATE] Access denied for {file_type} upload from user {user.id}")
        return ConversationHandler.END
    
    # Get file from appropriate message attribute
    if file_type == "photo":
        file_obj = update.message.photo[-1]  # Get highest resolution photo
        file_extension = ".jpg"
        allowed_types = ALLOWED_IMAGE_TYPES
        source_type = "photo"
    else:  # document (PDF or JPEG)
        file_obj = update.message.document
        # Determine extension based on MIME type
        mime_type = file_obj.mime_type or "application/octet-stream"
        if mime_type == "application/pdf":
            file_extension = ".pdf"
        elif mime_type in ("image/jpeg", "image/jpg"):
            file_extension = ".jpg"
        else:
            file_extension = ""
        allowed_types = ALLOWED_DOCUMENT_TYPES
        source_type = "document"
    
    file = await context.bot.get_file(file_obj.file_id)
    
    # Create secure temporary file
    file_path = file_handler.create_secure_temp_file(file_extension)
    
    try:
        # Get user comment/caption if provided
        user_comment = update.message.caption if update.message.caption else None
        if user_comment:
            user_comment = InputValidator.sanitize_text(user_comment, max_length=500)
            logger.info(f"User provided comment with {source_type}: {user_comment[:100]}...")
        else:
            logger.info(f"No user comment provided with {source_type}")
        
        logger.info(f"Downloading receipt {source_type} (file_id: {file_obj.file_id})")
        await file.download_to_drive(file_path)
        logger.info(f"Receipt {source_type} downloaded to {file_path}")

        # Validate file size and type
        try:
            file_handler.validate_file_size(file_path)
            detected_mime_type = file_handler.validate_file_type(file_path, allowed_types)
            logger.info(f"File validation successful: {detected_mime_type}")
        except SecurityException as e:
            logger.warning(f"File validation failed: {e.user_message}")
            await update.message.reply_text(f"❌ {e.user_message}")
            return ConversationHandler.END

        await update.message.reply_text("Processing your receipt...")

        try:
            # Parse image with Gemini, including user comment if provided
            logger.info(f"Sending receipt {source_type} to AI service for analysis")
            gemini_output, processing_time = parse_receipt_image(file_path, user_comment)
            logger.info("Successfully received response from AI service")
            
            # Validate and sanitize the response
            try:
                raw_data = json.loads(gemini_output)
                validated_data = InputValidator.validate_receipt_data(raw_data)
                gemini_output = json.dumps(validated_data)
            except (json.JSONDecodeError, SecurityException) as e:
                logger.error(f"Invalid data from AI service: {e}")
                await update.message.reply_text("❌ Sorry, I couldn't process the receipt properly. Please try again.")
                return ConversationHandler.END
            
            # Parse the receipt data into object
            user_id = update.effective_user.id
            logger.info(f"Parsing AI service output for user {user_id}")
            parsed_receipt = parse_receipt_from_gemini(gemini_output, user_id)
            logger.info(f"Receipt parsed successfully: {parsed_receipt.merchant}, {parsed_receipt.total_amount:.2f}, {len(parsed_receipt.positions)} items")
            
            # Prepare preface with timing information
            timing_text = f"(AI request took {processing_time:.1f}s)"
            preface_with_timing = f"Here's what I found in your receipt {timing_text}:"
            
            # Present preview with approval buttons using shared presenter
            return await present_parsed_receipt(
                update,
                context,
                parsed_receipt=parsed_receipt,
                original_json=gemini_output,
                preface=preface_with_timing,
                user_text_line=(f"📝 Your comment: {user_comment}" if user_comment else None)
            )
            
        except Exception as e:
            logger.error(f"Failed to process receipt for user {update.effective_user.id}: {str(e)}", exc_info=True)
            await handle_ai_service_error(update, e, "receipt")
        
    except Exception as e:
        logger.error(f"Unexpected error in {source_type} handling: {e}", exc_info=True)
        await update.message.reply_text(f"❌ An error occurred while processing your {source_type}. Please try again.")
    finally:
        # Always clean up the temporary file
        file_handler.cleanup_temp_file(file_path)
        
    return ConversationHandler.END

async def handle_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    user = update.effective_user
    logger.info(f"Received receipt approval response from user {user.full_name} (ID: {user_id})")
    
    user_data = receipt_data.get(user_id)
    
    if not user_data:
        # Remove buttons from original message but keep the content
        await query.edit_message_reply_markup(reply_markup=None)
        # Send separate error message
        await query.message.reply_text("❌ Sorry, I couldn't find your receipt data. Please try again.", reply_markup=get_persistent_keyboard())
        return ConversationHandler.END
    
    # Extract action and timestamp from callback data
    callback_parts = query.data.split('_')
    if len(callback_parts) != 2:
        # Remove buttons from original message but keep the content
        await query.edit_message_reply_markup(reply_markup=None)
        # Send separate error message
        await query.message.reply_text("⚠️ This button is no longer active. Please use the buttons from the latest message.", reply_markup=get_persistent_keyboard())
        return ConversationHandler.END
    
    action, timestamp = callback_parts
    latest_timestamp = user_data.get("latest_timestamp")
    
    # Check if this is the latest message
    if timestamp != latest_timestamp:
        # Remove buttons from original message but keep the content
        await query.edit_message_reply_markup(reply_markup=None)
        # Send separate error message
        await query.message.reply_text("⚠️ This button is no longer active. Please use the buttons from the latest message.", reply_markup=get_persistent_keyboard())
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
            
            # Remove buttons from original message but keep the content
            await query.edit_message_reply_markup(reply_markup=None)
            logger.info(f"Removed approval buttons from receipt summary message for user {user_id}")
            # Send separate approval message
            await query.message.reply_text(f"✅ Receipt saved successfully! Receipt ID: {receipt_id}", reply_markup=get_persistent_keyboard())
        except Exception as e:
            logger.error(f"Failed to save receipt for user {user_id}: {str(e)}", exc_info=True)
            # Remove buttons from original message but keep the content
            await query.edit_message_reply_markup(reply_markup=None)
            # Send separate error message
            await query.message.reply_text(f"❌ Failed to save receipt: {e}", reply_markup=get_persistent_keyboard())
        
        # Clean up stored data
        if user_id in receipt_data:
            del receipt_data[user_id]
        return ConversationHandler.END
    
    elif action == "reject":
        logger.info(f"Receipt rejected by user {user_id}")
        # Remove buttons from original message but keep the content
        await query.edit_message_reply_markup(reply_markup=None)
        logger.info(f"Removed approval buttons from receipt summary message for user {user_id}")
        # Send separate rejection message
        await query.message.reply_text("❌ Receipt rejected. Please try again with a clearer photo if needed.", reply_markup=get_persistent_keyboard())
        
        # Clean up stored data
        if user_id in receipt_data:
            del receipt_data[user_id]
        return ConversationHandler.END
    
    else:
        # Remove buttons from original message but keep the content
        await query.edit_message_reply_markup(reply_markup=None)
        # Send separate error message
        await query.message.reply_text("⚠️ Unknown action. Please use the buttons from the latest message.", reply_markup=get_persistent_keyboard())
        return ConversationHandler.END

async def handle_user_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user text comments for receipt adjustments."""
    user_id = update.effective_user.id
    user = update.effective_user
    user_comment = update.message.text
    
    logger.info(f"Received user comment from {user.full_name} (ID: {user_id}): {user_comment[:100]}...")
    
    user_data = receipt_data.get(user_id)
    if not user_data:
        await update.message.reply_text("Sorry, I couldn't find your receipt data. Please start over by sending a new receipt photo.")
        return ConversationHandler.END
    
    # Sanitize user input
    try:
        user_comment = InputValidator.sanitize_text(user_comment, max_length=500)
        if not user_comment.strip():
            await update.message.reply_text("❌ Your comment appears to be empty. Please try again.")
            return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error sanitizing user comment: {e}")
        await update.message.reply_text("❌ Invalid comment. Please try again.")
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
        updated_json, processing_time = update_receipt_with_comment(original_json, user_comment)
        logger.info("Successfully received updated JSON from Gemini")
        
        # Validate and sanitize the response
        try:
            raw_data = json.loads(updated_json)
            validated_data = InputValidator.validate_receipt_data(raw_data)
            updated_json = json.dumps(validated_data)
        except (json.JSONDecodeError, SecurityException) as e:
            logger.error(f"Invalid updated data from Gemini API: {e}")
            await update.message.reply_text("❌ Sorry, I couldn't apply your changes properly. Please try again.")
            return ConversationHandler.END
        
        # Parse the updated receipt data
        updated_receipt = parse_receipt_from_gemini(updated_json, user_id)
        logger.info(f"Updated receipt parsed successfully: {updated_receipt.merchant}, {updated_receipt.total_amount:.2f}")
        
        # Prepare preface with timing information
        timing_text = f"(AI request took {processing_time:.1f}s)"
        preface_with_timing = f"Here's the updated receipt {timing_text}:"
        
        # Present updated preview using shared presenter
        return await present_parsed_receipt(
            update,
            context,
            parsed_receipt=updated_receipt,
            original_json=updated_json,
            preface=preface_with_timing,
            user_text_line=f"📝 Your changes: {user_comment}"
        )
        
    except Exception as e:
        logger.error(f"Failed to process user comment for user {user_id}: {str(e)}", exc_info=True)
        await handle_ai_service_error(update, e, "changes")
        return ConversationHandler.END

async def handle_voice_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE, check_user_access_func):
    """Handle voice messages as receipt sources (not just comments)."""
    user = update.effective_user
    logger.info(f"Received voice receipt from user {user.full_name} (ID: {user.id})")
    
    if not await check_user_access_func(update, context):
        return ConversationHandler.END
    
    # Get the voice message
    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)
    voice_file_path = file_handler.create_secure_temp_file(".ogg")
    
    try:
        logger.info(f"Downloading voice receipt (file_id: {voice.file_id})")
        await file.download_to_drive(voice_file_path)
        logger.info(f"Voice receipt downloaded to {voice_file_path}")

        # Validate file size and type
        try:
            file_handler.validate_file_size(voice_file_path)
            detected_mime_type = file_handler.validate_file_type(voice_file_path, ALLOWED_AUDIO_TYPES)
            logger.info(f"Voice file validation successful: {detected_mime_type}")
        except SecurityException as e:
            logger.warning(f"Voice file validation failed: {e.user_message}")
            await update.message.reply_text(f"❌ {e.user_message}")
            return ConversationHandler.END

        processing_message = await update.message.reply_text("🎙️ Processing your voice receipt...")

        try:
            # Transcribe and notify user immediately, replacing the processing message
            transcribed_text = await transcribe_voice_and_notify(
                update,
                context,
                voice_file_path=voice_file_path,
                heard_prefix="🎙️ I heard:",
                next_hint="🛠️ Creating a receipt summary...",
                processing_message_id=processing_message.message_id
            )
            
            # Sanitize transcribed text
            transcribed_text = InputValidator.sanitize_text(transcribed_text, max_length=1000)
            
            # Convert transcribed text to receipt structure using Gemini
            logger.info("Converting transcribed text to receipt structure")
            gemini_output, processing_time = parse_voice_to_receipt(transcribed_text)
            logger.info("Successfully received receipt structure from Gemini")
            
            # Validate and sanitize the response
            try:
                raw_data = json.loads(gemini_output)
                validated_data = InputValidator.validate_receipt_data(raw_data)
                gemini_output = json.dumps(validated_data)
            except (json.JSONDecodeError, SecurityException) as e:
                logger.error(f"Invalid data from Gemini API: {e}")
                await update.message.reply_text("❌ Sorry, I couldn't understand your voice message properly. Please try again.")
                return ConversationHandler.END
            
            # Parse the receipt data into object
            user_id = update.effective_user.id
            logger.info(f"Parsing Gemini output for user {user_id}")
            parsed_receipt = parse_receipt_from_gemini(gemini_output, user_id)
            logger.info(f"Receipt parsed successfully: {parsed_receipt.merchant}, {parsed_receipt.total_amount:.2f}, {len(parsed_receipt.positions)} items")

            # Prepare preface with timing information
            timing_text = f"(AI request took {processing_time:.1f}s)"
            preface_with_timing = f"Here's what I understood from your voice message {timing_text}:"

            # Present preview with approval buttons
            return await present_parsed_receipt(
                update,
                context,
                parsed_receipt=parsed_receipt,
                original_json=gemini_output,
                preface=preface_with_timing,
                user_text_line=f"🎙️ Your message: \"{transcribed_text}\""
            )
            
        except Exception as e:
            logger.error(f"Failed to process voice receipt for user {update.effective_user.id}: {str(e)}", exc_info=True)
            await handle_ai_service_error(update, e, "voice")
    
    except Exception as e:
        logger.error(f"Unexpected error in voice receipt handling: {e}", exc_info=True)
        await update.message.reply_text("❌ An error occurred while processing your voice message. Please try again.")
    finally:
        # Clean up the voice file
        file_handler.cleanup_temp_file(voice_file_path)
        
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
    voice_file_path = file_handler.create_secure_temp_file(".ogg")
    
    try:
        logger.info(f"Downloading voice message (file_id: {voice.file_id})")
        await file.download_to_drive(voice_file_path)
        logger.info(f"Voice message downloaded to {voice_file_path}")

        # Validate file size and type
        try:
            file_handler.validate_file_size(voice_file_path)
            detected_mime_type = file_handler.validate_file_type(voice_file_path, ALLOWED_AUDIO_TYPES)
            logger.info(f"Voice file validation successful: {detected_mime_type}")
        except SecurityException as e:
            logger.warning(f"Voice file validation failed: {e.user_message}")
            await update.message.reply_text(f"❌ {e.user_message}")
            return ConversationHandler.END

        processing_message = await update.message.reply_text("Processing your voice message...")
        
        try:
            # Transcribe and notify user immediately, replacing the processing message
            user_comment = await transcribe_voice_and_notify(
                update,
                context,
                voice_file_path=voice_file_path,
                heard_prefix="🎙️ Your voice comment:",
                next_hint="🛠️ Applying your changes to the receipt...",
                processing_message_id=processing_message.message_id
            )
            
            # Sanitize transcribed text
            user_comment = InputValidator.sanitize_text(user_comment, max_length=500)
            
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
            updated_json, processing_time = update_receipt_with_comment(original_json, user_comment)
            logger.info("Successfully received updated JSON from Gemini")
            
            # Validate and sanitize the response
            try:
                raw_data = json.loads(updated_json)
                validated_data = InputValidator.validate_receipt_data(raw_data)
                updated_json = json.dumps(validated_data)
            except (json.JSONDecodeError, SecurityException) as e:
                logger.error(f"Invalid updated data from Gemini API: {e}")
                await update.message.reply_text("❌ Sorry, I couldn't apply your changes properly. Please try again.")
                return ConversationHandler.END
            
            # Parse the updated receipt data
            updated_receipt = parse_receipt_from_gemini(updated_json, user_id)
            logger.info(f"Updated receipt parsed successfully: {updated_receipt.merchant}, {updated_receipt.total_amount:.2f}")
            
            # Prepare preface with timing information
            timing_text = f"(AI request took {processing_time:.1f}s)"
            preface_with_timing = f"Here's the updated receipt {timing_text}:"
            
            # Present updated preview using shared presenter
            return await present_parsed_receipt(
                update,
                context,
                parsed_receipt=updated_receipt,
                original_json=updated_json,
                preface=preface_with_timing,
                user_text_line=f"🎙️ Your voice message: \"{user_comment}\""
            )
            
        except Exception as e:
            logger.error(f"Failed to process voice comment for user {user_id}: {str(e)}", exc_info=True)
            await handle_ai_service_error(update, e, "voice_changes")
            return ConversationHandler.END
    
    except Exception as e:
        logger.error(f"Unexpected error in voice comment handling: {e}", exc_info=True)
        await update.message.reply_text("❌ An error occurred while processing your voice message. Please try again.")
        return ConversationHandler.END
    finally:
        # Clean up the voice file
        file_handler.cleanup_temp_file(voice_file_path)

async def add_text_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE, check_user_access_func):
    """Handle /add command to create a receipt from a text description."""
    user = update.effective_user
    logger.info(f"Add command received from user {user.full_name} (ID: {user.id})")

    if not await check_user_access_func(update, context):
        return

    # Extract the text after /add
    user_text = " ".join(context.args) if context.args else ""
    if not user_text:
        await update.message.reply_text(
            "Please provide a purchase description after /add. Example: /add Bought groceries for 25 EUR at Tesco yesterday",
            reply_markup=get_persistent_keyboard()
        )
        return

    # Sanitize and validate user input
    try:
        user_text = InputValidator.sanitize_text(user_text, max_length=1000)
        if not user_text.strip():
            await update.message.reply_text(
                "❌ Your description appears to be empty. Please try again.",
                reply_markup=get_persistent_keyboard()
            )
            return
    except Exception as e:
        logger.error(f"Error sanitizing user text: {e}")
        await update.message.reply_text(
            "❌ Invalid description. Please try again.",
            reply_markup=get_persistent_keyboard()
        )
        return

    try:
        await update.message.reply_text("📝 Processing your text receipt...")
        logger.info("Converting text to receipt structure via Gemini")
        gemini_output, processing_time = parse_voice_to_receipt(user_text)
        logger.info("Successfully received receipt structure from Gemini for text input")

        # Validate and sanitize the response
        try:
            raw_data = json.loads(gemini_output)
            validated_data = InputValidator.validate_receipt_data(raw_data)
            gemini_output = json.dumps(validated_data)
        except (json.JSONDecodeError, SecurityException) as e:
            logger.error(f"Invalid data from Gemini API: {e}")
            await update.message.reply_text("❌ Sorry, I couldn't process your description properly. Please try again.")
            return ConversationHandler.END

        user_id = update.effective_user.id
        logger.info(f"Parsing Gemini output for user {user_id}")
        parsed_receipt = parse_receipt_from_gemini(gemini_output, user_id)
        logger.info(f"Receipt parsed successfully: {parsed_receipt.merchant}, {parsed_receipt.total_amount:.2f}, {len(parsed_receipt.positions)} items")

        # Prepare preface with timing information
        timing_text = f"(AI request took {processing_time:.1f}s)"
        preface_with_timing = f"Here's what I understood from your text {timing_text}:"

        return await present_parsed_receipt(
            update,
            context,
            parsed_receipt=parsed_receipt,
            original_json=gemini_output,
            preface=preface_with_timing,
            user_text_line=f"📝 Your text: \"{user_text}\""
        )
    except Exception as e:
        logger.error(f"Failed to process /add text receipt for user {user.id}: {str(e)}", exc_info=True)
        await handle_ai_service_error(update, e, "text")
        return ConversationHandler.END