
"""
gemini.py
Handles integration with Gemini for receipt parsing.
"""

import requests
import base64
from auth_data import GEMINI_API_KEY

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"  # Supported Gemini image endpoint
RECEIPT_PARSE_PROMPT = """Analyze this receipt image and extract the following information. Return ONLY a JSON object with these properties:
{
    "text": "full text content of the receipt, exactly as written",
    "category": "closest matching category from this list: [food, alcohol, transport, clothes, vacation, healthcare, beauty, household, car, cat, other]",
    "merchant": "name of the store or merchant",
    "positions": [
        {
            "description": "item description",
            "quantity": "item quantity as a number or weight",
            "category": "item category from this list: [food, alcohol, clothes, healthcare, beauty, household, car, cat, other]. Cat food should be categorized as 'cat'",
            "price": "item price as a number. If this value is negative, most likly it is a discount. Ignore negative positions."
        }
    ],
    "total_amount": "total amount as a number",
    "date": "receipt date in DD-MM-YYYY format if visible, otherwise null. The date migth appear in different formats, convert it to DD-MM-YYYY"
}"""

def parse_receipt_image(image_path):
    """
    Sends the receipt image to Gemini and returns the parsed total amount.
    """
    # Read image and encode as base64
    with open(image_path, "rb") as img_file:
        image_bytes = img_file.read()
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    # Prepare image as data URL
    data_url = f"data:image/jpeg;base64,{image_b64}"

    payload = {
        "contents": [
            {
                "parts": [
                    {"inline_data": {"mime_type": "image/jpeg", "data": image_b64}},
                    {"text": RECEIPT_PARSE_PROMPT}
                ]
            }
        ]
    }
    headers = {
        "Content-Type": "application/json"
    }

    response = requests.post(
        f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
        headers=headers,
        json=payload
    )
    response.raise_for_status()
    result = response.json()
    parsed_data = result["candidates"][0]["content"]["parts"][0]["text"].strip()
    return parsed_data  # Returns the full JSON response from Gemini

