"""
ai.py
Handles integration with ChatGPT for receipt parsing.
"""

import requests
import base64

from auth_data import CHATGPT_API_KEY

CHATGPT_API_URL = "https://api.openai.com/v1/chat/completions"  # Example endpoint
RECEIPT_PARSE_PROMPT = "Extract the total amount spent from this shop receipt image. Return only the amount as a number."

def parse_receipt_image(image_path):
    """
    Sends the receipt image to ChatGPT and returns the parsed total amount.
    """
    # Read image and encode as base64
    with open(image_path, "rb") as img_file:
        image_bytes = img_file.read()
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    # Prepare image as data URL
    data_url = f"data:image/jpeg;base64,{image_b64}"

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": RECEIPT_PARSE_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Here is a shop receipt image."},
                    {"type": "image_url", "image_url": {"url": data_url}}
                ]
            }
        ],
        "max_tokens": 50
    }
    headers = {
        "Authorization": f"Bearer {CHATGPT_API_KEY}",
        "Content-Type": "application/json"
    }

    response = requests.post(
        CHATGPT_API_URL,
        headers=headers,
        json=payload
    )
    response.raise_for_status()
    result = response.json()
    # Extract amount from result (depends on API response structure)
    amount = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    return amount
