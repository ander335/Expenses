"""
parse.py
Handles parsing of receipt data into domain models.
"""

import json
from typing import Dict, Any
from db import ReceiptData, PositionData

def parse_position(position_data: Dict[str, Any]) -> PositionData:
    """Convert a position dictionary into a PositionData object."""
    return PositionData(
        description=position_data['description'],
        quantity=float(position_data['quantity'].split()[0] if isinstance(position_data['quantity'], str) 
                      else position_data['quantity']),
        category=position_data['category'],
        price=float(position_data['price'])
    )

def parse_receipt_data(data: Dict[str, Any], user_id: int) -> ReceiptData:
    """Convert raw receipt data into a ReceiptData object."""
    positions = [parse_position(pos) for pos in data.get('positions', [])]
    
    return ReceiptData(
        merchant=data.get('merchant', 'Unknown Shop'),
        category=data.get('category', 'Unknown Category'),
        total_amount=float(data.get('total_amount', 0)),
        text=data.get('text'),
        date=data.get('date'),
        positions=positions,
        user_id=user_id
    )

def parse_receipt_from_file(file_path: str, user_id: int) -> ReceiptData:
    """Read receipt data from a JSON file and convert it to a ReceiptData object."""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return parse_receipt_data(data, user_id)

def parse_receipt_from_gemini(gemini_output: str, user_id: int) -> ReceiptData:
    """Parse Gemini's output string into a ReceiptData object."""
    data = json.loads(gemini_output)
    return parse_receipt_data(data, user_id)