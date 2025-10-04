"""
parse.py
Handles parsing of receipt data into domain models.
"""

import json
from typing import Dict, Any
from db import Receipt, Position

def parse_position(position_data: Dict[str, Any]) -> Position:
    """Convert a position dictionary into a Position object."""
    quantity = position_data['quantity']
    if not isinstance(quantity, str):
        quantity = str(quantity)
    return Position(
        description=position_data['description'],
        quantity=quantity,
        category=position_data['category'],
        price=float(position_data['price'])
    )

def parse_receipt_data(data: Dict[str, Any], user_id: int) -> Receipt:
    """Convert raw receipt data into a Receipt object."""
    positions = [parse_position(pos) for pos in data.get('positions', [])]
    
    return Receipt(
        merchant=data.get('merchant', 'Unknown Shop'),
        category=data.get('category', 'Unknown Category'),
        total_amount=float(data.get('total_amount', 0)),
        text=data.get('text'),
        date=data.get('date'),
        positions=positions,
        user_id=user_id
    )

def parse_receipt_from_file(file_path: str, user_id: int) -> Receipt:
    """Read receipt data from a JSON file and convert it to a Receipt object."""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return parse_receipt_data(data, user_id)

def parse_receipt_from_gemini(gemini_output: str, user_id: int) -> Receipt:
    """Parse Gemini's output string into a Receipt object."""
    data = json.loads(gemini_output)
    return parse_receipt_data(data, user_id)