
"""
gemini.py
Handles integration with Gemini for receipt parsing.
"""

import requests
import base64
from auth_data import GEMINI_API_KEY

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"  # Supported Gemini image endpoint
RECEIPT_PARSE_PROMPT = "Extract the total amount spent from this shop receipt image. Return only the amount as a number."

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
    # Extract amount from result (depends on API response structure)
    try:
        amount = result["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError):
        amount = "No response from Gemini."
    return amount
