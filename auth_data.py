import os

BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is not set")

# Keep this for backward compatibility but it's not used currently
CHATGPT_API_KEY = ""

# Optional: Telegram admin user ID who can approve new users
# Set environment variable TELEGRAM_ADMIN_ID to a numeric Telegram user ID.
_admin_id_str = os.environ.get('TELEGRAM_ADMIN_ID')
if not _admin_id_str or not _admin_id_str.isdigit():
    raise ValueError("TELEGRAM_ADMIN_ID environment variable is not set or invalid")
TELEGRAM_ADMIN_ID = int(_admin_id_str)