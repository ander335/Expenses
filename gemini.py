
"""
gemini.py
Handles integration with Gemini for receipt parsing.
"""

import requests
import base64
import json
from auth_data import GEMINI_API_KEY
from logger_config import logger, redact_sensitive_data

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
        raise requests.RequestException(f"API request failed: {error_msg}")

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"  # Supported Gemini image endpoint
RECEIPT_PARSE_PROMPT = """Analyze this receipt image and extract the following information. Return ONLY a JSON object with these properties:
{{
    "text": "full text content of the receipt, exactly as written",
    "description": "brief description of the receipt, and comment on changes due to User comments if there is any",
    "category": "closest matching category from this list: [food, alcohol, transport, clothes, vacation, healthcare, beauty, household, car, cat, other]",
    "merchant": "name of the store or merchant",
    "positions": [
        {{
            "description": "item description",
            "quantity": "item quantity as a number or weight",
            "category": "item category from this list: [food, alcohol, clothes, healthcare, beauty, household, car, cat, other]. Cat food should be categorized as 'cat'",
            "price": "item price as a number. If this value is negative, most likly it is a discount. Ignore negative positions."
        }}
    ],
    "total_amount": "total amount as a number",
    "date": "receipt date in DD-MM-YYYY format if visible, otherwise null. The date migth appear in different formats, convert it to DD-MM-YYYY"
}}

IMPORTANT: If the user provides additional comments below (inserted as {{user_comment}}), use those comments to override or adjust specific extracted fields when they conflict with the image. The user comments should take precedence for any conflicting information. Special instructions:
- DATA OVERRIDE: Use user comments to correct dates, merchant names, amounts, categories, or any other field they explicitly mention.
- CURRENCY CONVERSION: If the user requests currency conversion (e.g., "convert to USD", "convert euros to CZK", "use exchange rate from purchase date"), perform the conversion and return the converted amounts in the JSON. Apply the conversion to both individual item prices and the total_amount. Use realistic exchange rates for the date specified (or current rates if no date specified).
- PRESERVE ORIGINAL: If currency conversion is requested, you may add a comment in the "text" field noting the original currency and amounts for reference.

User comments: "{user_comment}"""

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

    # Always use the single prompt; insert the (possibly empty) user comment
    prompt = RECEIPT_PARSE_PROMPT.format(user_comment=user_comment_text)
    
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
    result = None
    try:
        response = make_secure_request(
            GEMINI_API_URL,
            GEMINI_API_KEY,
            headers=headers,
            json=payload
        )
        logger.info("Successfully received response from Gemini API")
        
        result = response.json()
        parsed_data = result["candidates"][0]["content"]["parts"][0]["text"].strip()
        logger.debug("Successfully extracted text content from Gemini response")
    except requests.RequestException as e:
        error_message = f"Error calling Gemini API: {str(e)}"
        logger.error(redact_sensitive_data(error_message))
        raise
    
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
    logger.debug(f"Cleaned Gemini response (first 100 chars): {cleaned_data[:100]}")
    
    # Validate that we have valid JSON before returning
    try:
        json.loads(cleaned_data)
        logger.debug("JSON validation successful")
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON returned from Gemini: {str(e)}")
        if result:
            logger.error(f"Raw Gemini response: {result['candidates'][0]['content']['parts'][0]['text']}")
        logger.error(f"Cleaned response: {cleaned_data}")
        raise ValueError(f"Gemini returned invalid JSON: {str(e)}")
    
    return cleaned_data

