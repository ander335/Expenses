"""
ai.py
Unified AI interface for receipt parsing supporting multiple AI providers.
"""

import os
import json
import base64
import requests
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Tuple

from logger_config import logger, redact_sensitive_data

# =============================================================================
# CUSTOM EXCEPTIONS
# =============================================================================
class AIServiceMalformedJSONError(Exception):
    """Raised when the AI service returns malformed JSON that cannot be parsed."""
    pass

# =============================================================================
# CONFIGURATION
# =============================================================================
# Environment variable to control which AI service to use
AI_PROVIDER = os.environ.get('AI_PROVIDER', 'gemini').lower()  # Default to gemini

# Categories and structure definitions
EXPENSE_CATEGORIES = ["food", "alcohol", "transport", "clothes", "vacation", "sport", "healthcare", "beauty", "household", "car", "cat", "other"]

RECEIPT_JSON_STRUCTURE = """{
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
USER_ADJUSTMENT_INSTRUCTIONS = """IMPORTANT: User comments override image data. Apply these rules:
- Override any field explicitly mentioned by user
- Date without year: use current year, format as DD-MM-YYYY
- Currency conversion: apply to all amounts, use exchange rates from date of purchase
- Note original currency in "text" field if converted

User comments: "{user_comment}\""""

RECEIPT_PARSE_PROMPT_NO_USER_INPUT = """Analyze this receipt image and extract the following information. Current date for reference: {current_date}. Return ONLY a JSON object with these properties:
{receipt_structure}"""

RECEIPT_PARSE_PROMPT_WITH_USER_INPUT = """Analyze this receipt image and extract the following information. Current date for reference: {current_date}. Return ONLY a JSON object with these properties:
{receipt_structure}

Date handling: If receipt shows date without year, use current year. Format as DD-MM-YYYY.

{user_adjustment_instructions}\""""

UPDATE_RECEIPT_PROMPT = """Update this JSON based on user comments: "{user_comment}"

Original JSON: {original_json}
Current date: {current_date}

Return ONLY the updated JSON object, nothing else. Update "description" field to note changes.
Date handling: If user provides date without year, use current year. Format as DD-MM-YYYY.
Language: Keep original language unless explicitly changed. Description field in ENGLISH.

{user_adjustment_instructions}\""""

VOICE_TO_RECEIPT_PROMPT = """Create receipt from purchase description. Rules:
- One position if no items specified, use total as price
- Default date: {current_date}. For dates without year, use current year. Handle relative dates.
- Default merchant: Unknown
- Quantity: 1 if not specified
- Categories from available list
- Extra context goes to description (direct style, no "user" references)
- All output in ENGLISH (translate if needed)

Return ONLY a JSON object with this structure: {receipt_structure}

User description: "{user_text}\""""

VOICE_TRANSCRIPTION_PROMPT = "Transcribe this voice message to text (English or Russian). Return only the transcribed text."

# =============================================================================
# BASE AI PROVIDER INTERFACE
# =============================================================================
class AIProvider(ABC):
    """Abstract base class for AI service providers."""
    
    @abstractmethod
    def parse_receipt_image(self, image_path: str, user_comment: Optional[str] = None) -> str:
        """Parse receipt image and return JSON string."""
        pass
    
    @abstractmethod
    def update_receipt_with_comment(self, original_json: str, user_comment: str) -> str:
        """Update receipt data based on user comment."""
        pass
    
    @abstractmethod
    def convert_voice_to_text(self, voice_file_path: str) -> str:
        """Convert voice message to text."""
        pass
    
    @abstractmethod
    def parse_voice_to_receipt(self, transcribed_text: str) -> str:
        """Convert transcribed voice text to receipt structure."""
        pass

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================
def time_ai_operation(operation_name: str):
    """
    Decorator to measure and log the time taken for AI operations.
    
    Args:
        operation_name: Name of the AI operation being timed
    
    Returns:
        Decorator function that returns (result, elapsed_time)
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            logger.info(f"Starting {operation_name} operation...")
            
            try:
                result = func(*args, **kwargs)
                elapsed_time = time.time() - start_time
                logger.info(f"{operation_name} completed successfully in {elapsed_time:.1f} seconds")
                return result, elapsed_time
            except Exception as e:
                elapsed_time = time.time() - start_time
                logger.error(f"{operation_name} failed after {elapsed_time:.1f} seconds: {str(e)}")
                raise
                
        return wrapper
    return decorator

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

def parse_json_response(response_text: str, operation_type: str = "parsing") -> str:
    """
    Common function to parse and clean JSON response from AI services.
    Handles code block markers and validates JSON structure.
    
    Args:
        response_text: The text response from AI service
        operation_type: String describing the operation for logging
    
    Returns:
        str: Cleaned JSON string
    """
    parsed_data = response_text.strip()
    logger.debug(f"Successfully extracted text content from AI {operation_type} response")
    
    # Remove JSON code block markers if they exist
    if parsed_data.startswith('```json'):
        parsed_data = parsed_data[7:].lstrip()
    elif parsed_data.startswith('```'):
        parsed_data = parsed_data[3:].lstrip()
    
    if parsed_data.endswith('```'):
        parsed_data = parsed_data[:-3].rstrip()
    
    # Try to find JSON object in the response
    # Look for the first '{' and last '}' to extract JSON
    start_idx = parsed_data.find('{')
    end_idx = parsed_data.rfind('}')
    
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        # Extract potential JSON content
        json_candidate = parsed_data[start_idx:end_idx + 1]
        logger.debug(f"Extracted JSON candidate (first 100 chars): {json_candidate[:100]}")
    else:
        # No clear JSON structure found, use cleaned data as is
        json_candidate = parsed_data.strip()
        logger.debug(f"No clear JSON structure found, using full response")
    
    # Clean up any remaining whitespace
    cleaned_data = json_candidate.strip()
    
    # Log the cleaned response for debugging
    logger.debug(f"Cleaned AI {operation_type} response (first 100 chars): {cleaned_data[:100]}")
    
    # Validate that we have valid JSON before returning
    try:
        json.loads(cleaned_data)
        logger.debug(f"{operation_type.capitalize()} JSON validation successful")
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON returned from AI {operation_type}: {str(e)}")
        logger.error(f"Raw AI {operation_type} response: {response_text}")
        logger.error(f"Cleaned {operation_type} response: {cleaned_data}")
        
        # Try a more aggressive fix by decoding and re-encoding the string
        try:
            logger.info("Attempting aggressive Unicode fix by decoding and re-encoding")
            # Try to decode and re-encode to fix any encoding issues
            fixed_data = cleaned_data.encode('utf-8', errors='ignore').decode('utf-8')
            # Remove any null bytes or other problematic characters
            fixed_data = fixed_data.replace('\x00', '').replace('\r', '\\r').replace('\n', '\\n')
            
            # Try parsing again
            json.loads(fixed_data)
            logger.info("Aggressive Unicode fix successful")
            cleaned_data = fixed_data
        except (json.JSONDecodeError, UnicodeError) as e2:
            logger.error(f"Aggressive fix also failed: {str(e2)}")
            raise AIServiceMalformedJSONError(f"AI service returned invalid JSON for {operation_type}: {str(e)}")
    
    return cleaned_data

# =============================================================================
# GEMINI AI PROVIDER
# =============================================================================
class GeminiProvider(AIProvider):
    """Gemini AI service provider implementation."""
    
    def __init__(self):
        self.api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
        self.api_key = os.environ.get('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")
    
    def _make_request(self, payload: dict) -> dict:
        """Make a request to Gemini API."""
        headers = {"Content-Type": "application/json"}
        
        try:
            response = make_secure_request(
                self.api_url,
                self.api_key,
                headers=headers,
                json=payload
            )
            return response.json()
        except requests.RequestException as e:
            error_message = f"Error calling Gemini API: {str(e)}"
            logger.error(redact_sensitive_data(error_message))
            raise
    
    def parse_receipt_image(self, image_path: str, user_comment: Optional[str] = None) -> str:
        """Parse receipt image using Gemini."""
        logger.info(f"Reading receipt image from {image_path}")
        user_comment_text = user_comment.strip() if user_comment else ""
        if user_comment_text:
            logger.info(f"Processing receipt with user comment: {user_comment_text}")
        else:
            logger.info("Processing receipt without user comment")

        current_date = datetime.now().strftime("%d-%m-%Y")
        logger.debug(f"Using current date: {current_date}")

        # Select appropriate prompt template
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
        
        # Read and encode image
        with open(image_path, "rb") as img_file:
            image_bytes = img_file.read()
            image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        logger.debug("Image successfully encoded to base64")

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

        logger.info("Sending request to Gemini API")
        result = self._make_request(payload)
        logger.info("Successfully received response from Gemini API")
        
        response_text = result["candidates"][0]["content"]["parts"][0]["text"]
        return parse_json_response(response_text, "parsing")
    
    def update_receipt_with_comment(self, original_json: str, user_comment: str) -> str:
        """Update receipt data with user comment using Gemini."""
        logger.info(f"Updating receipt data with user comment: {user_comment}")
        
        current_date = datetime.now().strftime("%d-%m-%Y")
        logger.debug(f"Using current date: {current_date}")
        
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

        logger.info("Sending update request to Gemini API")
        result = self._make_request(payload)
        logger.info("Successfully received update response from Gemini API")
        
        response_text = result["candidates"][0]["content"]["parts"][0]["text"]
        return parse_json_response(response_text, "update")
    
    def convert_voice_to_text(self, voice_file_path: str) -> str:
        """Convert voice message to text using Gemini."""
        logger.info(f"Converting voice message to text from {voice_file_path}")
        
        with open(voice_file_path, "rb") as voice_file:
            voice_bytes = voice_file.read()
            voice_b64 = base64.b64encode(voice_bytes).decode("utf-8")
        logger.debug("Voice file successfully encoded to base64")

        payload = {
            "contents": [
                {
                    "parts": [
                        {"inline_data": {"mime_type": "audio/ogg", "data": voice_b64}},
                        {"text": VOICE_TRANSCRIPTION_PROMPT}
                    ]
                }
            ]
        }

        logger.info("Sending voice transcription request to Gemini API")
        result = self._make_request(payload)
        logger.info("Successfully received voice transcription response from Gemini API")
        
        transcribed_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
        logger.info(f"Voice transcription successful: {transcribed_text[:100]}...")
        
        return transcribed_text
    
    def parse_voice_to_receipt(self, transcribed_text: str) -> str:
        """Convert transcribed voice text to receipt structure using Gemini."""
        logger.info(f"Converting voice text to receipt structure: {transcribed_text[:100]}...")
        
        current_date = datetime.now().strftime("%d-%m-%Y")
        logger.debug(f"Using current date: {current_date}")

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

        logger.info("Sending voice-to-receipt request to Gemini API")
        result = self._make_request(payload)
        logger.info("Successfully received voice-to-receipt response from Gemini API")
        
        response_text = result["candidates"][0]["content"]["parts"][0]["text"]
        return parse_json_response(response_text, "voice-to-receipt parsing")

# =============================================================================
# OPENAI AI PROVIDER
# =============================================================================
class OpenAIProvider(AIProvider):
    """OpenAI/ChatGPT AI service provider implementation."""
    
    def __init__(self):
        self.api_url = "https://api.openai.com/v1/chat/completions"
        self.api_key = os.environ.get('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        
        # Model selection optimized for quality over speed:
        self.vision_model = 'gpt-4.1-mini'
        self.text_model = 'gpt-4.1-mini'
        
        logger.info(f"OpenAI Provider initialized - Vision model: {self.vision_model}, Text model: {self.text_model}")
    
    def _make_request(self, messages: list, max_tokens: int = 4000, model: str = None) -> dict:
        """Make a request to OpenAI API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Use provided model or default to text model
        selected_model = model or self.text_model
        
        payload = {
            "model": selected_model,
            "messages": messages,
            "max_tokens": max_tokens
        }
        
        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            error_message = f"Error calling OpenAI API: {str(e)}"
            logger.error(redact_sensitive_data(error_message))
            raise
    
    def parse_receipt_image(self, image_path: str, user_comment: Optional[str] = None) -> str:
        """Parse receipt image using OpenAI."""
        logger.info(f"Reading receipt image from {image_path}")
        user_comment_text = user_comment.strip() if user_comment else ""
        if user_comment_text:
            logger.info(f"Processing receipt with user comment: {user_comment_text}")
        else:
            logger.info("Processing receipt without user comment")

        current_date = datetime.now().strftime("%d-%m-%Y")
        logger.debug(f"Using current date: {current_date}")

        # Select appropriate prompt template
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
        
        # Read and encode image
        with open(image_path, "rb") as img_file:
            image_bytes = img_file.read()
            image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        logger.debug("Image successfully encoded to base64")

        data_url = f"data:image/jpeg;base64,{image_b64}"
        
        messages = [
            {"role": "system", "content": "You are an expert at analyzing receipt images and extracting structured data."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}}
                ]
            }
        ]

        logger.info("Sending request to OpenAI API")
        logger.debug(f"Using vision model: {self.vision_model} for image recognition")
        result = self._make_request(messages, model=self.vision_model)
        logger.info("Successfully received response from OpenAI API")
        
        response_text = result["choices"][0]["message"]["content"]
        return parse_json_response(response_text, "parsing")
    
    def update_receipt_with_comment(self, original_json: str, user_comment: str) -> str:
        """Update receipt data with user comment using OpenAI."""
        logger.info(f"Updating receipt data with user comment: {user_comment}")
        
        current_date = datetime.now().strftime("%d-%m-%Y")
        logger.debug(f"Using current date: {current_date}")
        
        prompt = UPDATE_RECEIPT_PROMPT.format(
            original_json=original_json,
            user_comment=user_comment,
            user_adjustment_instructions=USER_ADJUSTMENT_INSTRUCTIONS.format(user_comment=user_comment),
            current_date=current_date
        )
        
        messages = [
            {"role": "system", "content": "You are an expert at updating receipt data based on user feedback."},
            {"role": "user", "content": prompt}
        ]

        logger.info("Sending update request to OpenAI API")
        result = self._make_request(messages, model=self.text_model)
        logger.info("Successfully received update response from OpenAI API")
        
        response_text = result["choices"][0]["message"]["content"]
        return parse_json_response(response_text, "update")
    
    def convert_voice_to_text(self, voice_file_path: str) -> str:
        """Convert voice message to text using OpenAI Whisper."""
        logger.info(f"Converting voice message to text from {voice_file_path}")
        logger.debug("Using whisper-1 model for speech recognition (fastest + mid quality)")
        
        # Use OpenAI's Whisper API for transcription
        url = "https://api.openai.com/v1/audio/transcriptions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        
        with open(voice_file_path, "rb") as audio_file:
            files = {
                "file": audio_file,
                "model": (None, "whisper-1"),  # Fastest Whisper model for mid-quality speech recognition
                "response_format": (None, "text")
            }
            
            try:
                response = requests.post(url, headers=headers, files=files)
                response.raise_for_status()
                
                transcribed_text = response.text.strip()
                logger.info(f"Voice transcription successful: {transcribed_text[:100]}...")
                
                return transcribed_text
                
            except requests.RequestException as e:
                error_message = f"Error calling OpenAI Whisper API: {str(e)}"
                logger.error(redact_sensitive_data(error_message))
                raise
    
    def parse_voice_to_receipt(self, transcribed_text: str) -> str:
        """Convert transcribed voice text to receipt structure using OpenAI."""
        logger.info(f"Converting voice text to receipt structure: {transcribed_text[:100]}...")
        
        current_date = datetime.now().strftime("%d-%m-%Y")
        logger.debug(f"Using current date: {current_date}")

        prompt = VOICE_TO_RECEIPT_PROMPT.format(
            receipt_structure=RECEIPT_JSON_STRUCTURE,
            user_text=transcribed_text,
            current_date=current_date
        )
        
        messages = [
            {"role": "system", "content": "You are an expert at converting voice descriptions into structured receipt data."},
            {"role": "user", "content": prompt}
        ]

        logger.info("Sending voice-to-receipt request to OpenAI API")
        logger.debug(f"Using text model: {self.text_model} for voice-to-receipt conversion")
        result = self._make_request(messages, model=self.text_model)
        logger.info("Successfully received voice-to-receipt response from OpenAI API")
        
        response_text = result["choices"][0]["message"]["content"]
        return parse_json_response(response_text, "voice-to-receipt parsing")

# =============================================================================
# PROVIDER FACTORY AND PUBLIC INTERFACE
# =============================================================================
def get_ai_provider() -> AIProvider:
    """Factory function to get the appropriate AI provider based on configuration."""
    if AI_PROVIDER == 'openai':
        logger.info("Using OpenAI AI provider")
        return OpenAIProvider()
    elif AI_PROVIDER == 'gemini':
        logger.info("Using Gemini AI provider")
        return GeminiProvider()
    else:
        logger.warning(f"Unknown AI provider: {AI_PROVIDER}, defaulting to Gemini")
        return GeminiProvider()

# Global provider instance
_provider = None

def _get_provider() -> AIProvider:
    """Get or create the AI provider instance."""
    global _provider
    if _provider is None:
        _provider = get_ai_provider()
    return _provider

# =============================================================================
# PUBLIC API FUNCTIONS
# =============================================================================
@time_ai_operation("Receipt image parsing")
def parse_receipt_image(image_path: str, user_comment: Optional[str] = None) -> str:
    """
    Parse receipt image and return structured data as JSON string.
    
    Args:
        image_path: Path to the receipt image file
        user_comment: Optional user comment to override/adjust extracted data
    
    Returns:
        str: JSON string with receipt data
    
    Note: This function returns (result, elapsed_time) due to timing decorator
    """
    return _get_provider().parse_receipt_image(image_path, user_comment)

@time_ai_operation("Receipt update with comment")
def update_receipt_with_comment(original_json: str, user_comment: str) -> str:
    """
    Update receipt data based on user comment.
    
    Args:
        original_json: Original JSON string from previous parsing
        user_comment: User's correction or adjustment comment
    
    Returns:
        str: Updated JSON string with receipt data
    
    Note: This function returns (result, elapsed_time) due to timing decorator
    """
    return _get_provider().update_receipt_with_comment(original_json, user_comment)

@time_ai_operation("Voice to text conversion")
def convert_voice_to_text(voice_file_path: str) -> str:
    """
    Convert voice message file to text.
    
    Args:
        voice_file_path: Path to the voice message file
    
    Returns:
        str: Transcribed text from the voice message
    
    Note: This function returns (result, elapsed_time) due to timing decorator
    """
    return _get_provider().convert_voice_to_text(voice_file_path)

@time_ai_operation("Voice to receipt parsing")
def parse_voice_to_receipt(transcribed_text: str) -> str:
    """
    Convert transcribed voice text to structured receipt data.
    
    Args:
        transcribed_text: Text transcribed from voice message
    
    Returns:
        str: JSON string with receipt data
    
    Note: This function returns (result, elapsed_time) due to timing decorator
    """
    return _get_provider().parse_voice_to_receipt(transcribed_text)