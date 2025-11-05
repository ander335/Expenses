
"""
gemini.py
Handles integration with Gemini for receipt parsing.
"""

import requests
import base64
import json
from datetime import datetime
from auth_data import GEMINI_API_KEY
from logger_config import logger, redact_sensitive_data

# =============================================================================
# CUSTOM EXCEPTIONS
# =============================================================================
class AIServiceMalformedJSONError(Exception):
    """Raised when the AI service returns malformed JSON that cannot be parsed."""
    pass

# =============================================================================
# GEMINI API CONFIGURATION
# =============================================================================
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

# =============================================================================
# CATEGORIES CONFIGURATION
# =============================================================================
EXPENSE_CATEGORIES = ["food", "alcohol", "transport", "clothes", "vacation", "sport", "healthcare", "beauty", "household", "car", "cat", "other"]

# =============================================================================
# RECEIPT JSON STRUCTURE
# =============================================================================
RECEIPT_JSON_STRUCTURE = """{
    "text": "full text content of the receipt, exactly as written",
    "description": "brief description of the receipt, and comment on changes due to User comments if there is any",
    "category": "closest matching category from this list: """ + str(EXPENSE_CATEGORIES) + """",
    "merchant": "name of the store or merchant",
    "positions": [
        {
            "description": "item description",
            "quantity": "item quantity as a number or weight",
            "category": "item category from this list: """ + str(EXPENSE_CATEGORIES) + """. Cat food should be categorized as 'cat'",
            "price": "item price as a number. If this value is negative, most likly it is a discount. Ignore negative positions."
        }
    ],
    "total_amount": "total amount as a number",
    "date": "receipt date in DD-MM-YYYY format if visible, otherwise null. If you see a date in any other format (like YYYY-MM-DD), convert it to DD-MM-YYYY format. For example: 2024-05-15 should become 15-05-2024"
}"""

# =============================================================================
# PROMPT TEMPLATES
# =============================================================================
USER_ADJUSTMENT_INSTRUCTIONS = """IMPORTANT: If the user provides additional comments below (inserted as {user_comment}), use those comments to override or adjust specific extracted fields when they conflict with the image. The user comments should take precedence for any conflicting information. Special instructions:
- DATA OVERRIDE: Use user comments to correct dates, merchant names, amounts, categories, or any other field they explicitly mention.
- DATE HANDLING: If the user provides a date with day and month but NO YEAR (e.g., "15-05", "May 15", "change date to 15th of May"), use the current year from the current date. Always format as DD-MM-YYYY.
- CURRENCY CONVERSION: If the user requests currency conversion (e.g., "convert to USD", "convert euros to CZK", "use exchange rate from purchase date"), perform the conversion and return the converted amounts in the JSON. Apply the conversion to both individual item prices and the total_amount. Use realistic exchange rates for the date specified (or current rates if no date specified).
- PRESERVE ORIGINAL: If currency conversion is requested, you may add a comment in the "text" field noting the original currency and amounts for reference.

User comments: "{user_comment}"""

RECEIPT_PARSE_PROMPT_NO_USER_INPUT = """Analyze this receipt image and extract the following information. Current date for reference: {current_date}. Return ONLY a JSON object with these properties:
{receipt_structure}"""

RECEIPT_PARSE_PROMPT_WITH_USER_INPUT = """Analyze this receipt image and extract the following information. Current date for reference: {current_date}. Return ONLY a JSON object with these properties:
{receipt_structure}

DATE HANDLING INSTRUCTIONS:
- If the receipt shows a date with day and month but NO YEAR (e.g., "15-05", "May 15", "15/05"), use the current year from the current date provided above.
- Always convert the final date to DD-MM-YYYY format.
- Examples: If current date is "02-11-2025" and receipt shows "15-05", return "15-05-2025".

{user_adjustment_instructions}"""

UPDATE_RECEIPT_PROMPT = """You previously parsed a receipt and generated this JSON:

{original_json}

The user has provided additional comments or corrections: "{user_comment}"

Current date for reference: {current_date}

Please update the JSON data based on the user's comments. Return ONLY the updated JSON object with the same structure as before. Make sure to:
1. Apply the user's corrections to the appropriate fields
2. Maintain the same JSON structure
3. Update the "description" field to mention what was changed based on user comments
4. If currency conversion is requested, convert all amounts appropriately

DATE HANDLING INSTRUCTIONS:
- If the user provides a date with day and month but NO YEAR (e.g., "15-05", "May 15", "15/05"), use the current year from the current date provided above.
- Always convert the final date to DD-MM-YYYY format.
- Examples: If current date is "02-11-2025" and user mentions "15-05", return "15-05-2025".

Language requirement:
- Do NOT translate existing fields from the original_json. Preserve their original language and values unless explicitly changed by the user comments.
- Apply the user's corrections exactly as given. If the user provides new text in another language, keep it as provided (no translation).
- Write ONLY the "description" field in ENGLISH, appending a concise summary of the changes and any relevant notes. All other fields should remain in their existing language. Keep numeric values and dates unchanged except for requested conversions.

{user_adjustment_instructions}"""

VOICE_TO_RECEIPT_PROMPT = """Based on the text provided by the user describing their purchase, create a receipt structure. Follow these instructions:

- If the user does not mention individual positions in the purchase, create ONE position with the total amount as the price
- If the date wasn't mentioned, use the current date: {current_date} (in DD-MM-YYYY format)
- If any required field is missing, make reasonable assumptions based on the context
- If the merchant name is not specified, use Unknown as the merchant name
- Choose the most appropriate category from the available list
- Set quantity to 1 if not specified
- If the user provides any non-related information to the receipt (context, stories, additional comments), summarize it and put it in the receipt description field. Write the description in a direct, subjectless style without referring to "the user" (e.g., "Not very tasty, caused digestive issues" instead of "The user commented it was not very tasty")

DATE HANDLING INSTRUCTIONS:
- If the user mentions a date with day and month but NO YEAR (e.g., "15-05", "May 15", "15th of May", "yesterday", "today"), use the current year from the current date provided above.
- For relative dates like "yesterday", "today", "last week", calculate the actual date using the current date as reference.
- Always convert the final date to DD-MM-YYYY format.
- Examples: If current date is "02-11-2025" and user says "May 15", return "15-05-2025".

Language requirement:
- Always respond in ENGLISH only. If the user's text is in another language, translate any descriptions and merchant names to English. Ensure all JSON string values (description, category, merchant, positions[].description, positions[].category) are English. Numeric values and dates should not be translated.

Return ONLY a JSON object with this structure:
{receipt_structure}

User's purchase description: "{user_text}" """

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def make_secure_request(url, api_key, **kwargs):
    """
    Make an HTTP request without exposing API key in error messages.
    """
    secure_url = f"{url}?key={api_key}"
    try:
        response = requests.post(secure_url, **kwargs)
        response.raise_for_status()
        return response
    except requests.RequestException as e:
        # Create a new exception without the sensitive URL
        error_msg = str(e)
        if hasattr(e, 'response') and e.response is not None:
            error_msg = f"{e.response.status_code} {e.response.reason}"
        logger.error(f"Secure API request failed: {error_msg}")
        raise requests.RequestException(f"API request failed: {error_msg}")

def parse_gemini_json_response(result, operation_type="parsing"):
    """
    Common function to parse and clean JSON response from Gemini API.
    Handles code block markers and validates JSON structure.
    
    Args:
        result: The JSON response from Gemini API
        operation_type: String describing the operation for logging (e.g., "parsing", "update")
    
    Returns:
        str: Cleaned JSON string
    """
    parsed_data = result["candidates"][0]["content"]["parts"][0]["text"].strip()
    logger.debug(f"Successfully extracted text content from Gemini {operation_type} response")
    
    # Remove JSON code block markers if they exist
    # Handle various markdown code block formats
    if parsed_data.startswith('```json'):
        # Remove ```json and any following whitespace/newlines
        parsed_data = parsed_data[7:].lstrip()
    elif parsed_data.startswith('```'):
        # Remove ``` and any following whitespace/newlines  
        parsed_data = parsed_data[3:].lstrip()
    
    if parsed_data.endswith('```'):
        # Remove trailing ``` and any preceding whitespace/newlines
        parsed_data = parsed_data[:-3].rstrip()
    
    # Clean up any remaining whitespace and ensure we have valid JSON
    cleaned_data = parsed_data.strip()
    
    # Log the cleaned response for debugging
    logger.debug(f"Cleaned Gemini {operation_type} response (first 100 chars): {cleaned_data[:100]}")
    
    # Validate that we have valid JSON before returning
    try:
        json.loads(cleaned_data)
        logger.debug(f"{operation_type.capitalize()} JSON validation successful")
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON returned from Gemini {operation_type}: {str(e)}")
        logger.error(f"Raw Gemini {operation_type} response: {result['candidates'][0]['content']['parts'][0]['text']}")
        logger.error(f"Cleaned {operation_type} response: {cleaned_data}")
        # Raise custom exception for JSON parsing issues
        raise AIServiceMalformedJSONError(f"Gemini returned invalid JSON for {operation_type}: {str(e)}")
    
    return cleaned_data


def convert_voice_to_text(voice_file_path):
    """
    Converts a voice message file to text using Gemini API.
    
    Args:
        voice_file_path: Path to the voice message file (OGG format from Telegram)
    
    Returns:
        str: Transcribed text from the voice message
    """
    logger.info(f"Converting voice message to text from {voice_file_path}")
    
    # Read voice file and encode as base64
    with open(voice_file_path, "rb") as voice_file:
        voice_bytes = voice_file.read()
        voice_b64 = base64.b64encode(voice_bytes).decode("utf-8")
    logger.debug("Voice file successfully encoded to base64")

    # Prepare the prompt for voice transcription
    prompt = "Please transcribe this voice message into text. Most likely it's either English or Russian language. Return only the transcribed text without any additional formatting or explanation."

    payload = {
        "contents": [
            {
                "parts": [
                    {"inline_data": {"mime_type": "audio/ogg", "data": voice_b64}},
                    {"text": prompt}
                ]
            }
        ]
    }
    headers = {
        "Content-Type": "application/json"
    }

    logger.info("Sending voice transcription request to Gemini API")
    try:
        response = make_secure_request(
            GEMINI_API_URL,
            GEMINI_API_KEY,
            headers=headers,
            json=payload
        )
        logger.info("Successfully received voice transcription response from Gemini API")
        
        result = response.json()
        transcribed_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
        logger.info(f"Voice transcription successful: {transcribed_text[:100]}...")
        
        return transcribed_text
        
    except requests.RequestException as e:
        error_message = f"Error calling Gemini API for voice transcription: {str(e)}"
        logger.error(redact_sensitive_data(error_message))
        raise


def parse_voice_to_receipt(transcribed_text):
    """
    Converts transcribed voice text to a receipt structure using Gemini API.
    
    Args:
        transcribed_text: The text transcribed from voice message
    
    Returns:
        str: JSON string with receipt structure
    """
    logger.info(f"Converting voice text to receipt structure: {transcribed_text[:100]}...")
    
    logger.info("Processing voice text to create receipt structure")

    # Get current date in DD-MM-YYYY format
    current_date = datetime.now().strftime("%d-%m-%Y")
    logger.debug(f"Using current date: {current_date}")

    # Use the voice-to-receipt prompt
    prompt = VOICE_TO_RECEIPT_PROMPT.format(
        receipt_structure=RECEIPT_JSON_STRUCTURE,
        user_text=transcribed_text,
        current_date=current_date
    )
    
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }
    headers = {
        "Content-Type": "application/json"
    }

    logger.info("Sending voice-to-receipt request to Gemini API")
    try:
        response = make_secure_request(
            GEMINI_API_URL,
            GEMINI_API_KEY,
            headers=headers,
            json=payload
        )
        logger.info("Successfully received voice-to-receipt response from Gemini API")
        
        result = response.json()
        return parse_gemini_json_response(result, "voice-to-receipt parsing")
        
    except requests.RequestException as e:
        error_message = f"Error calling Gemini API for voice-to-receipt: {str(e)}"
        logger.error(redact_sensitive_data(error_message))
        raise


def parse_receipt_image(image_path, user_comment=None):
    """
    Sends the receipt image to Gemini and returns the parsed total amount.
    If user_comment is provided, it will be included in the prompt to override image data.
    """
    logger.info(f"Reading receipt image from {image_path}")
    # Normalize the user comment to an empty string when not provided
    user_comment_text = user_comment.strip() if user_comment else ""
    if user_comment_text:
        logger.info(f"Processing receipt with user comment: {user_comment_text}")
    else:
        logger.info("Processing receipt without user comment")

    # Get current date in DD-MM-YYYY format
    current_date = datetime.now().strftime("%d-%m-%Y")
    logger.debug(f"Using current date: {current_date}")

    # Select appropriate prompt template based on whether user input is provided
    if user_comment_text:
        prompt = RECEIPT_PARSE_PROMPT_WITH_USER_INPUT.format(
            receipt_structure=RECEIPT_JSON_STRUCTURE,
            user_adjustment_instructions=USER_ADJUSTMENT_INSTRUCTIONS.format(user_comment=user_comment_text),
            current_date=current_date
        )
    else:
        prompt = RECEIPT_PARSE_PROMPT_NO_USER_INPUT.format(
            receipt_structure=RECEIPT_JSON_STRUCTURE,
            current_date=current_date
        )
    
    # Read image and encode as base64
    with open(image_path, "rb") as img_file:
        image_bytes = img_file.read()
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    logger.debug("Image successfully encoded to base64")

    # Prepare image as data URL
    data_url = f"data:image/jpeg;base64,{image_b64}"

    payload = {
        "contents": [
            {
                "parts": [
                    {"inline_data": {"mime_type": "image/jpeg", "data": image_b64}},
                    {"text": prompt}
                ]
            }
        ]
    }
    headers = {
        "Content-Type": "application/json"
    }

    logger.info("Sending request to Gemini API")
    try:
        response = make_secure_request(
            GEMINI_API_URL,
            GEMINI_API_KEY,
            headers=headers,
            json=payload
        )
        logger.info("Successfully received response from Gemini API")
        
        result = response.json()
        return parse_gemini_json_response(result, "parsing")
        
    except requests.RequestException as e:
        error_message = f"Error calling Gemini API: {str(e)}"
        logger.error(redact_sensitive_data(error_message))
        raise


def update_receipt_with_comment(original_json: str, user_comment: str):
    """
    Sends the original JSON parsing result and user comment to Gemini to get updated parsing.
    Used for iterative improvements based on user feedback.
    """
    logger.info(f"Updating receipt data with user comment: {user_comment}")
    
    # Get current date in DD-MM-YYYY format
    current_date = datetime.now().strftime("%d-%m-%Y")
    logger.debug(f"Using current date: {current_date}")
    
    # Prepare the prompt with original JSON, user comment, and current date
    prompt = UPDATE_RECEIPT_PROMPT.format(
        original_json=original_json,
        user_comment=user_comment,
        user_adjustment_instructions=USER_ADJUSTMENT_INSTRUCTIONS.format(user_comment=user_comment),
        current_date=current_date
    )
    
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }
    headers = {
        "Content-Type": "application/json"
    }

    logger.info("Sending update request to Gemini API")
    try:
        response = make_secure_request(
            GEMINI_API_URL,
            GEMINI_API_KEY,
            headers=headers,
            json=payload
        )
        logger.info("Successfully received update response from Gemini API")
        
        result = response.json()
        return parse_gemini_json_response(result, "update")
        
    except requests.RequestException as e:
        error_message = f"Error calling Gemini API for update: {str(e)}"
        logger.error(redact_sensitive_data(error_message))
        raise

