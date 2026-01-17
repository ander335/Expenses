# Search, summary, and data viewing module

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from logger_config import logger
import calendar
from datetime import datetime
from db import get_last_n_receipts, get_receipts_by_date, get_monthly_summary, get_user, delete_receipt
from ai import format_category_with_emoji

def get_persistent_keyboard():
    """Create persistent buttons that are always available."""
    keyboard = [
        [
            InlineKeyboardButton("📅 Date Search", callback_data="persistent_calendar"),
            InlineKeyboardButton("📊 Summary", callback_data="persistent_summary")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def format_receipts_list(receipts: list, title: str, requesting_user_id: int = None, search_date: str = None) -> str:
    """Format a list of receipts for display with a title, showing user names for group receipts."""
    if not receipts:
        if search_date:
            return f"No receipts found for {search_date}."
        return "No receipts found."
    
    text = f"📈 {title}:\n"
    total_expenses = sum(r.total_amount for r in receipts if not r.is_income)
    total_income = sum(r.total_amount for r in receipts if r.is_income)
    
    text += f"Total receipts: {len(receipts)} | "
    if total_expenses > 0:
        text += f"Expenses: {total_expenses:.1f} | "
    if total_income > 0:
        text += f"Income: {total_income:.1f} | "
    text += "\n\n"
    
    for r in receipts:
        # Show user name if receipt belongs to someone else in the group
        user_info = ""
        if requesting_user_id and r.user_id != requesting_user_id:
            # Get user name from database
            receipt_owner = get_user(r.user_id)
            user_info = f" ({receipt_owner.name if receipt_owner else f'User {r.user_id}'})"
        
        # Add income indicator to category
        category_display = f"{format_category_with_emoji(r.category)} (income 💰)" if r.is_income else format_category_with_emoji(r.category)
        text += f"ID: {r.receipt_id} | {r.date or 'No date'} | {r.merchant} | {category_display} | {r.total_amount:.1f}{user_info}\n"
    
    return text

def create_calendar_keyboard(year: int, month: int) -> InlineKeyboardMarkup:
    """Create a calendar keyboard for date selection."""
    # Calendar header with month/year and navigation
    keyboard = []
    
    # Navigation row with previous/next month
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    
    month_name = calendar.month_name[month]
    keyboard.append([
        InlineKeyboardButton("◀", callback_data=f"cal_nav_{prev_year}_{prev_month}"),
        InlineKeyboardButton(f"{month_name} {year}", callback_data="cal_ignore"),
        InlineKeyboardButton("▶", callback_data=f"cal_nav_{next_year}_{next_month}")
    ])
    
    # Days of week header
    keyboard.append([
        InlineKeyboardButton("Mo", callback_data="cal_ignore"),
        InlineKeyboardButton("Tu", callback_data="cal_ignore"),
        InlineKeyboardButton("We", callback_data="cal_ignore"),
        InlineKeyboardButton("Th", callback_data="cal_ignore"),
        InlineKeyboardButton("Fr", callback_data="cal_ignore"),
        InlineKeyboardButton("Sa", callback_data="cal_ignore"),
        InlineKeyboardButton("Su", callback_data="cal_ignore")
    ])
    
    # Calendar days
    cal = calendar.monthcalendar(year, month)
    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="cal_ignore"))
            else:
                row.append(InlineKeyboardButton(str(day), callback_data=f"cal_date_{year}_{month:02d}_{day:02d}"))
        keyboard.append(row)
    
    # Close button
    keyboard.append([InlineKeyboardButton("❌ Close", callback_data="cal_close")])
    
    return InlineKeyboardMarkup(keyboard)

def calculate_monthly_net_summary(user_id: int, n: int) -> tuple:
    """Calculate monthly net summary with expenses as positive and income as negative.
    Returns (formatted_text, has_data)."""
    expenses = get_monthly_summary(user_id, n, fetch_income=False)
    income = get_monthly_summary(user_id, n, fetch_income=True)
    
    if not expenses and not income:
        return None, False
    
    # Calculate monthly net (expenses positive, income negative)
    all_months = {}
    for month_data in (expenses or []):
        all_months[month_data['month']] = {
            'expenses': month_data['total'], 
            'expenses_count': month_data['count'],
            'income': 0,
            'income_count': 0
        }
    for month_data in (income or []):
        if month_data['month'] not in all_months:
            all_months[month_data['month']] = {
                'expenses': 0,
                'expenses_count': 0,
                'income': month_data['total'],
                'income_count': month_data['count']
            }
        else:
            all_months[month_data['month']]['income'] = month_data['total']
            all_months[month_data['month']]['income_count'] = month_data['count']
    
    text = f"📊 Monthly net expenses:\n\n"
    for month in sorted(all_months.keys(), key=lambda x: datetime.strptime(x, '%m-%Y'), reverse=True):
        net = all_months[month]['expenses'] - all_months[month]['income']
        total_count = all_months[month]['expenses_count'] + all_months[month]['income_count']
        text += f"{month}: {total_count} receipts, total: {net:.1f}\n"
    
    return text, True

async def list_receipts(update: Update, context: ContextTypes.DEFAULT_TYPE, check_user_access_func):
    user = update.effective_user
    logger.info(f"[EXPENSES_VIEW] List command received from user {user.full_name} (ID: {user.id})")
    
    if not await check_user_access_func(update, context):
        logger.warning(f"[EXPENSES_VIEW] Access denied for list command from user {user.id}")
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
    formatted_text = format_receipts_list(receipts, f"Last {n} receipts", update.effective_user.id)
    
    await update.message.reply_text(formatted_text, reply_markup=get_persistent_keyboard())

async def delete_receipt_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, check_user_access_func):
    user = update.effective_user
    logger.info(f"Delete command received from user {user.full_name} (ID: {user.id})")
    
    if not await check_user_access_func(update, context):
        return
    
    try:
        receipt_id = int(context.args[0])
        logger.info(f"Attempting to delete receipt {receipt_id} for user {user.id}")
    except (IndexError, ValueError):
        logger.warning(f"Invalid delete command argument from user {user.id}")
        await update.message.reply_text("Please specify a receipt ID: /delete ID", reply_markup=get_persistent_keyboard())
        return

    try:
        # Check if user is admin - import here to avoid circular imports
        from auth_data import TELEGRAM_ADMIN_ID
        is_admin = user.id == TELEGRAM_ADMIN_ID
        
        result = delete_receipt(receipt_id, user.id, is_admin=is_admin)
        await update.message.reply_text(result['message'], reply_markup=get_persistent_keyboard())
        
    except Exception as e:
        logger.error(f"Error deleting receipt {receipt_id} for user {user.id}: {str(e)}", exc_info=True)
        await update.message.reply_text(f"Failed to delete receipt: {str(e)}", reply_markup=get_persistent_keyboard())

async def show_receipts_by_date(update: Update, context: ContextTypes.DEFAULT_TYPE, check_user_access_func):
    user = update.effective_user
    logger.info(f"Date command received from user {user.full_name} (ID: {user.id})")
    
    if not await check_user_access_func(update, context):
        return
    
    # Check if user provided a date argument
    if context.args:
        # Manual date input (original functionality)
        date_input = context.args[0]
        
        try:
            # Parse the date input and convert to DD-MM-YYYY format
            if date_input.count('.') == 1:
                # Format: DD.MM (current year)
                day, month = date_input.split('.')
                current_year = datetime.now().year
                formatted_date = f"{int(day):02d}-{int(month):02d}-{current_year}"
            elif date_input.count('.') == 2:
                # Format: DD.MM.YYYY
                day, month, year = date_input.split('.')
                formatted_date = f"{int(day):02d}-{int(month):02d}-{int(year)}"
            else:
                raise ValueError("Invalid date format")
            
            # Validate the date
            datetime.strptime(formatted_date, '%d-%m-%Y')
            
            logger.info(f"Searching receipts for date {formatted_date} for user {user.id}")
            
            receipts = get_receipts_by_date(update.effective_user.id, formatted_date)
            formatted_text = format_receipts_list(receipts, f"Receipts for {date_input}", update.effective_user.id, search_date=date_input)
            
            await update.message.reply_text(formatted_text, reply_markup=get_persistent_keyboard())
            
        except ValueError:
            logger.warning(f"Invalid date format from user {user.id}: {date_input}")
            await update.message.reply_text(
                "❌ Invalid date format. Please use:\n"
                "• DD.MM for current year (e.g., 25.11)\n"
                "• DD.MM.YYYY for specific year (e.g., 5.5.2023)\n\n"
                "Or use /date without arguments to open the date picker.",
                reply_markup=get_persistent_keyboard()
            )
    else:
        # Show date picker (new functionality)
        current_date = datetime.now()
        calendar_keyboard = create_calendar_keyboard(current_date.year, current_date.month)
        
        await update.message.reply_text(
            "📅 Select a date to view receipts:\n\n"
            "💡 Tip: You can also type /date DD.MM or /date DD.MM.YYYY for quick access",
            reply_markup=calendar_keyboard
        )

async def show_summary(update: Update, context: ContextTypes.DEFAULT_TYPE, check_user_access_func):
    user = update.effective_user
    logger.info(f"Summary command received from user {user.full_name} (ID: {user.id})")
    
    if not await check_user_access_func(update, context):
        return
    
    try:
        n = int(context.args[0]) if context.args else 6  # Default to last 6 months
        logger.info(f"Generating {n} month summary for user {user.id}")
        if n <= 0:
            raise ValueError("Number must be positive")
    except (IndexError, ValueError):
        logger.warning(f"Invalid summary command argument from user {user.id}")
        await update.message.reply_text("Please specify a positive number: /summary N", reply_markup=get_persistent_keyboard())
        return

    text, has_data = calculate_monthly_net_summary(update.effective_user.id, n)
    
    if not has_data:
        await update.message.reply_text("No data found for the specified period.", reply_markup=get_persistent_keyboard())
        return
    
    await update.message.reply_text(text, reply_markup=get_persistent_keyboard())

async def handle_calendar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, get_admin_user_id_func):
    """Handle calendar date picker interactions."""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    user_id = user.id
    
    # Check authorization first
    if user_id == get_admin_user_id_func():
        # Admin is always authorized
        pass
    else:
        # Check database authorization for non-admin users
        db_user = get_user(user_id)
        if not db_user or not db_user.is_authorized:
            logger.warning(f"Unauthorized calendar access attempt from user {user.full_name} (ID: {user_id})")
            await query.edit_message_text("Sorry, you are not authorized to use this bot.")
            return
    
    callback_data = query.data
    
    if callback_data.startswith("cal_nav_"):
        # Navigation to different month
        _, _, year_str, month_str = callback_data.split("_")
        year, month = int(year_str), int(month_str)
        
        calendar_keyboard = create_calendar_keyboard(year, month)
        await query.edit_message_text(
            "📅 Select a date to view receipts:",
            reply_markup=calendar_keyboard
        )
    
    elif callback_data.startswith("cal_date_"):
        # Date selected
        _, _, year_str, month_str, day_str = callback_data.split("_")
        year, month, day = int(year_str), int(month_str), int(day_str)
        
        # Format date as DD-MM-YYYY for database query
        formatted_date = f"{day:02d}-{month:02d}-{year}"
        display_date = f"{day}.{month}.{year}"
        
        logger.info(f"Calendar date selected: {formatted_date} by user {user_id}")
        
        # Get receipts for the selected date
        receipts = get_receipts_by_date(user_id, formatted_date)
        formatted_text = format_receipts_list(receipts, f"Receipts for {display_date}", user_id, search_date=display_date)
        
        await query.edit_message_text(formatted_text, reply_markup=get_persistent_keyboard())
    
    elif callback_data == "cal_close":
        # Close calendar
        await query.edit_message_text("📅 Calendar closed.", reply_markup=get_persistent_keyboard())
    
    elif callback_data == "cal_ignore":
        # Ignore clicks on header/day labels
        pass

async def handle_persistent_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE, get_admin_user_id_func):
    """Handle clicks on persistent buttons."""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    user_id = user.id
    
    # Use the same authorization logic as other handlers
    # Check if user is admin first
    if user_id == get_admin_user_id_func():
        # Admin is always authorized
        pass
    else:
        # Check database authorization for non-admin users
        db_user = get_user(user_id)
        if not db_user or not db_user.is_authorized:
            logger.warning(f"Unauthorized access attempt from user {user.full_name} (ID: {user_id})")
            await query.edit_message_text("Sorry, you are not authorized to use this bot.")
            return
    
    if query.data == "persistent_calendar":
        logger.info(f"Persistent calendar button clicked by user {user.full_name} (ID: {user_id})")
        
        # Show date picker
        current_date = datetime.now()
        calendar_keyboard = create_calendar_keyboard(current_date.year, current_date.month)
        
        await query.edit_message_text(
            "📅 Select a date to view receipts:\n\n"
            "💡 Tip: You can also type /date DD.MM or /date DD.MM.YYYY for quick access",
            reply_markup=calendar_keyboard
        )
    
    elif query.data == "persistent_summary":
        logger.info(f"Persistent summary button clicked by user {user.full_name} (ID: {user_id})")
        
        try:
            # Default to last 6 months for button click
            n = 6
            logger.info(f"Generating {n} month summary for user {user_id}")
            
            text, has_data = calculate_monthly_net_summary(user_id, n)
            
            if not has_data:
                await query.edit_message_text(f"No data found for the last {n} months.", reply_markup=get_persistent_keyboard())
                return
            
            await query.edit_message_text(text, reply_markup=get_persistent_keyboard())
            
        except Exception as e:
            logger.error(f"Error during summary generation for user {user_id}: {str(e)}", exc_info=True)
            await query.edit_message_text(f"❌ Failed to generate summary: {str(e)}", reply_markup=get_persistent_keyboard())