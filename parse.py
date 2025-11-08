"""
parse.py
Handles parsing of receipt data into domain models.
"""

import json
from typing import Dict, Any
from db import Receipt, Position
from logger_config import logger
from security_utils import InputValidator, SecurityException

def parse_position(position_data: Dict[str, Any]) -> Position:
    """Convert a position dictionary into a Position object."""
    logger.debug(f"Parsing position: {position_data}")
    
    # Validate position data
    validated_pos = InputValidator.validate_position_data(position_data)
    if not validated_pos:
        raise SecurityException("Invalid position data")
    
    quantity = validated_pos['quantity']
    if not isinstance(quantity, str):
        quantity = str(quantity)
    
    position = Position(
        description=validated_pos['description'],
        quantity=quantity,
        category=validated_pos.get('category', 'other'),
        price=float(validated_pos['price'])
    )
    logger.debug(f"Created Position: {position.description}, {position.price:.2f}")
    return position

def parse_receipt_data(data: Dict[str, Any], user_id: int) -> Receipt:
    """Convert raw receipt data into a Receipt object."""
    # Validate user ID
    validated_user_id = InputValidator.validate_user_id(user_id)
    
    # Validate receipt data
    validated_data = InputValidator.validate_receipt_data(data)
    
    positions = []
    for pos in validated_data.get('positions', []):
        try:
            position = parse_position(pos)
            positions.append(position)
        except SecurityException as e:
            logger.warning(f"Skipping invalid position: {e.user_message}")
            continue
    
    return Receipt(
        merchant=validated_data.get('merchant', 'Unknown Shop'),
        category=validated_data.get('category', 'other'),
        total_amount=float(validated_data.get('total_amount', 0)),
        text='',
        description=validated_data.get('description'),
        date=validated_data.get('date'),
        positions=positions,
        user_id=validated_user_id
    )

def parse_receipt_from_file(file_path: str, user_id: int) -> Receipt:
    """Read receipt data from a JSON file and convert it to a Receipt object."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return parse_receipt_data(data, user_id)
    except (OSError, json.JSONDecodeError) as e:
        logger.error(f"Error reading receipt file {file_path}: {e}")
        raise SecurityException("Could not read receipt file")

def parse_receipt_from_gemini(gemini_output: str, user_id: int) -> Receipt:
    """Parse Gemini's output string into a Receipt object."""
    logger.info(f"Parsing Gemini output for user {user_id}")
    try:
        # Sanitize the JSON string before parsing
        sanitized_output = InputValidator.sanitize_text(gemini_output, max_length=10000)
        data = json.loads(sanitized_output)
        logger.debug("Successfully parsed Gemini JSON output")
        
        receipt = parse_receipt_data(data, user_id)
        logger.info(f"Successfully created Receipt object: {receipt.merchant}, {receipt.total_amount:.2f}")
        return receipt
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Gemini JSON output: {str(e)}")
        logger.debug("Failed Gemini output content:")
        for line_num, line in enumerate(gemini_output.splitlines(), 1):
            logger.debug(f"Line {line_num}: {line}")
        raise SecurityException("Invalid JSON format from AI service")
    except SecurityException:
        raise
    except Exception as e:
        logger.error(f"Error creating Receipt object: {str(e)}", exc_info=True)
        raise SecurityException("Failed to process receipt data")