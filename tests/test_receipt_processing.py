"""
Test receipt processing business logic.
"""

import pytest
import json
import os
from datetime import datetime
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from interfaces import ParsedReceipt
from security_utils import SecurityException


class TestReceiptImageProcessing:
    """Test receipt processing from images."""
    
    def test_process_receipt_image_success(self, expenses_service, temp_image_file, sample_receipt_data):
        """Test successful receipt image processing."""
        user_id = 98336105
        
        # Configure mock AI service to return specific data
        expenses_service.ai_service.set_custom_response(temp_image_file, sample_receipt_data)
        
        result = expenses_service.process_receipt_image(user_id, temp_image_file)
        
        assert isinstance(result, ParsedReceipt)
        assert result.merchant == sample_receipt_data['merchant']
        assert result.total_amount == sample_receipt_data['total_amount']
        assert result.category == sample_receipt_data['category']
        assert len(result.positions) == len(sample_receipt_data['positions'])
        
        # Verify AI service was called
        assert expenses_service.ai_service.get_call_count('parse_image') == 1
    
    def test_process_receipt_image_with_comment(self, expenses_service, temp_image_file):
        """Test receipt processing with user comment."""
        user_id = 98336105
        user_comment = "The total should be 30.00 EUR"
        
        result = expenses_service.process_receipt_image(user_id, temp_image_file, user_comment)
        
        assert isinstance(result, ParsedReceipt)
        assert "Modified by comment" in result.description
        
        # Verify the comment was passed to AI service
        calls = expenses_service.ai_service.parse_image_calls
        assert len(calls) == 1
        assert calls[0]['user_comment'] == user_comment
    
    def test_process_receipt_image_file_too_large(self, expenses_service, temp_image_file):
        """Test processing fails when file is too large."""
        user_id = 98336105
        
        # Configure file service to fail validation
        expenses_service.file_service.set_validation_failure(True, "File too large")
        
        with pytest.raises(SecurityException, match="File too large"):
            expenses_service.process_receipt_image(user_id, temp_image_file)
    
    def test_process_receipt_image_invalid_file_type(self, expenses_service, invalid_file):
        """Test processing fails with invalid file type."""
        user_id = 98336105
        
        with pytest.raises(SecurityException, match="Invalid file type"):
            expenses_service.process_receipt_image(user_id, invalid_file)
    
    def test_process_receipt_image_ai_service_failure(self, expenses_service, temp_image_file):
        """Test handling of AI service failures."""
        user_id = 98336105
        
        # Configure AI service to fail
        expenses_service.ai_service.set_failure_mode(True, "AI service unavailable")
        
        with pytest.raises(RuntimeError, match="AI service unavailable"):
            expenses_service.process_receipt_image(user_id, temp_image_file)


class TestVoiceReceiptProcessing:
    """Test receipt processing from voice messages."""
    
    def test_process_voice_receipt_success(self, expenses_service, temp_voice_file):
        """Test successful voice receipt processing."""
        user_id = 98336105
        
        # Configure AI service responses
        transcribed_text = "I bought groceries for 25 euros at SuperMarket"
        expenses_service.ai_service.set_custom_response(temp_voice_file, transcribed_text)
        
        result = expenses_service.process_voice_receipt(user_id, temp_voice_file)
        
        assert isinstance(result, ParsedReceipt)
        assert result.merchant == "Voice Store"  # From mock
        assert "Created from voice" in result.description
        
        # Verify both AI service calls were made
        assert expenses_service.ai_service.get_call_count('voice_to_text') == 1
        assert expenses_service.ai_service.get_call_count('voice_to_receipt') == 1
    
    def test_process_voice_receipt_with_amount_extraction(self, expenses_service, temp_voice_file):
        """Test voice processing with amount extraction."""
        user_id = 98336105
        
        # Set specific transcription that should be parsed for amount
        transcribed_text = "I spent 20 euros at the grocery store"
        expenses_service.ai_service.set_custom_response(temp_voice_file, transcribed_text)
        
        result = expenses_service.process_voice_receipt(user_id, temp_voice_file)
        
        assert result.total_amount == 20.0  # Should extract this amount
    
    def test_process_voice_receipt_invalid_file(self, expenses_service, invalid_file):
        """Test voice processing with invalid audio file."""
        user_id = 98336105
        
        with pytest.raises(SecurityException, match="Invalid file type"):
            expenses_service.process_voice_receipt(user_id, invalid_file)
    
    def test_process_voice_receipt_transcription_failure(self, expenses_service, temp_voice_file):
        """Test handling of voice transcription failure."""
        user_id = 98336105
        
        # Configure AI service to fail on transcription
        expenses_service.ai_service.set_failure_mode(True, "Voice transcription failed")
        
        with pytest.raises(RuntimeError, match="Voice transcription failed"):
            expenses_service.process_voice_receipt(user_id, temp_voice_file)


class TestTextReceiptProcessing:
    """Test receipt processing from text descriptions."""
    
    def test_process_text_receipt_success(self, expenses_service):
        """Test successful text receipt processing."""
        user_id = 98336105
        text_description = "Bought lunch for 15 USD at Pizza Place"
        
        result = expenses_service.process_text_receipt(user_id, text_description)
        
        assert isinstance(result, ParsedReceipt)
        assert result.merchant == "Voice Store"  # From mock response
        assert "Created from voice" in result.description
        
        # Verify AI service was called
        assert expenses_service.ai_service.get_call_count('voice_to_receipt') == 1
        
        # Check the text was passed correctly
        calls = expenses_service.ai_service.voice_to_receipt_calls
        assert calls[0]['transcribed_text'] == text_description
    
    def test_process_text_receipt_with_special_characters(self, expenses_service):
        """Test text processing with special characters and unicode."""
        user_id = 98336105
        text_description = "Купил продукты на 500₽ в магазине Пятёрочка"
        
        result = expenses_service.process_text_receipt(user_id, text_description)
        
        assert isinstance(result, ParsedReceipt)
        # The mock should handle this text appropriately
    
    def test_process_text_receipt_ai_failure(self, expenses_service):
        """Test handling of AI service failure during text processing."""
        user_id = 98336105
        text_description = "Test receipt"
        
        expenses_service.ai_service.set_failure_mode(True, "Text processing failed")
        
        with pytest.raises(RuntimeError, match="Text processing failed"):
            expenses_service.process_text_receipt(user_id, text_description)


class TestReceiptUpdates:
    """Test receipt updates based on user feedback."""
    
    def test_update_receipt_with_user_comment(self, expenses_service, sample_receipt_json):
        """Test updating receipt with user comment."""
        user_comment = "Change merchant to 'Corrected Store' and total to 35.00"
        
        result = expenses_service.update_receipt_with_user_comment(123, sample_receipt_json, user_comment)
        
        assert isinstance(result, ParsedReceipt)
        assert "Updated with comment" in result.description
        
        # Verify AI service was called with correct parameters
        assert expenses_service.ai_service.get_call_count('update_comment') == 1
        calls = expenses_service.ai_service.update_comment_calls
        assert calls[0]['user_comment'] == user_comment
        assert calls[0]['original_data'] == sample_receipt_json
    
    def test_update_receipt_with_merchant_change(self, expenses_service, sample_receipt_json):
        """Test updating receipt with merchant name change."""
        user_comment = "The merchant name should be 'New Store Name'"
        
        result = expenses_service.update_receipt_with_user_comment(456, sample_receipt_json, user_comment)
        
        # Mock should detect 'merchant' in comment and update accordingly
        assert result.merchant == "Updated Store"  # From mock logic
    
    def test_update_receipt_with_amount_change(self, expenses_service, sample_receipt_json):
        """Test updating receipt with amount change."""
        user_comment = "The total amount is wrong, it should be 42.99"
        
        result = expenses_service.update_receipt_with_user_comment(789, sample_receipt_json, user_comment)
        
        # Mock should detect 'amount'/'total' in comment and update accordingly
        assert result.total_amount == 15.75  # From mock logic
    
    def test_update_receipt_ai_failure(self, expenses_service, sample_receipt_json):
        """Test handling of AI service failure during update."""
        user_comment = "Change something"
        
        expenses_service.ai_service.set_failure_mode(True, "Update failed")
        
        with pytest.raises(RuntimeError, match="Update failed"):
            expenses_service.update_receipt_with_user_comment(999, sample_receipt_json, user_comment)


class TestReceiptSaving:
    """Test saving processed receipts to database."""
    
    def test_save_receipt_success(self, expenses_service, sample_receipt_data):
        """Test successful receipt saving."""
        user_id = 98336105
        
        parsed_receipt = ParsedReceipt(
            merchant=sample_receipt_data['merchant'],
            category=sample_receipt_data['category'],
            total_amount=sample_receipt_data['total_amount'],
            date=sample_receipt_data['date'],
            text=sample_receipt_data['text'],
            description=sample_receipt_data['description'],
            positions=sample_receipt_data['positions']
        )
        
        receipt_id = expenses_service.save_receipt(user_id, parsed_receipt)
        
        assert isinstance(receipt_id, int)
        assert receipt_id > 0
        
        # Verify receipt was saved in database
        saved_receipt = expenses_service.db_service.get_receipt(receipt_id)
        assert saved_receipt is not None
        assert saved_receipt.user_id == user_id
        assert saved_receipt.merchant == sample_receipt_data['merchant']
        assert saved_receipt.total_amount == sample_receipt_data['total_amount']
        assert len(saved_receipt.positions) == len(sample_receipt_data['positions'])
    
    def test_save_receipt_with_positions(self, expenses_service, sample_receipt_data):
        """Test saving receipt with multiple positions."""
        user_id = 98336105
        
        parsed_receipt = ParsedReceipt(
            merchant=sample_receipt_data['merchant'],
            category=sample_receipt_data['category'],
            total_amount=sample_receipt_data['total_amount'],
            positions=sample_receipt_data['positions']
        )
        
        receipt_id = expenses_service.save_receipt(user_id, parsed_receipt)
        saved_receipt = expenses_service.db_service.get_receipt(receipt_id)
        
        assert len(saved_receipt.positions) == 3
        
        # Check position details
        position_descriptions = [pos.description for pos in saved_receipt.positions]
        assert "Milk 1L" in position_descriptions
        assert "Bread" in position_descriptions
        assert "Cleaning supplies" in position_descriptions
    
    def test_save_receipt_empty_positions(self, expenses_service):
        """Test saving receipt with no positions."""
        user_id = 98336105
        
        parsed_receipt = ParsedReceipt(
            merchant="Simple Store",
            category="other",
            total_amount=10.0,
            positions=[]
        )
        
        receipt_id = expenses_service.save_receipt(user_id, parsed_receipt)
        saved_receipt = expenses_service.db_service.get_receipt(receipt_id)
        
        assert saved_receipt is not None
        assert len(saved_receipt.positions) == 0


@pytest.mark.integration
class TestFullReceiptWorkflow:
    """Integration tests for complete receipt processing workflows."""
    
    def test_image_to_database_workflow(self, expenses_service, temp_image_file, sample_user_data):
        """Test complete workflow from image processing to database storage."""
        user_id = sample_user_data['user_id']
        
        # Create user first
        expenses_service.db_service.create_user_if_missing(
            user_id, sample_user_data['name'], is_authorized=True
        )
        
        # Process image
        parsed_receipt = expenses_service.process_receipt_image(user_id, temp_image_file)
        
        # Save to database
        receipt_id = expenses_service.save_receipt(user_id, parsed_receipt)
        
        # Verify complete workflow
        saved_receipt = expenses_service.db_service.get_receipt(receipt_id)
        assert saved_receipt.user_id == user_id
        assert saved_receipt.merchant == parsed_receipt.merchant
        
        # Verify user can retrieve their receipts
        user_receipts = expenses_service.get_user_expenses(user_id, 10)
        assert len(user_receipts) == 1
        assert user_receipts[0].receipt_id == receipt_id
    
    def test_voice_to_database_workflow(self, expenses_service, temp_voice_file, sample_user_data):
        """Test complete workflow from voice processing to database storage."""
        user_id = sample_user_data['user_id']
        
        # Create user
        expenses_service.db_service.create_user_if_missing(
            user_id, sample_user_data['name'], is_authorized=True
        )
        
        # Process voice
        parsed_receipt = expenses_service.process_voice_receipt(user_id, temp_voice_file)
        
        # Save and verify
        receipt_id = expenses_service.save_receipt(user_id, parsed_receipt)
        user_receipts = expenses_service.get_user_expenses(user_id, 10)
        
        assert len(user_receipts) == 1
        assert user_receipts[0].merchant == "Voice Store"  # From mock
    
    def test_receipt_update_workflow(self, expenses_service, temp_image_file, sample_user_data):
        """Test workflow of processing, updating, and saving receipt."""
        user_id = sample_user_data['user_id']
        
        # Initial processing
        parsed_receipt = expenses_service.process_receipt_image(user_id, temp_image_file)
        original_merchant = parsed_receipt.merchant
        
        # Simulate getting original JSON (in real app this would be stored)
        original_json = json.dumps({
            'merchant': parsed_receipt.merchant,
            'total_amount': parsed_receipt.total_amount,
            'category': parsed_receipt.category
        })
        
        # Update with user comment
        updated_receipt = expenses_service.update_receipt_with_user_comment(
            user_id, original_json, "Change merchant to 'Updated Store'"
        )
        
        # Save updated version
        receipt_id = expenses_service.save_receipt(user_id, updated_receipt)
        
        # Verify the update was applied
        saved_receipt = expenses_service.db_service.get_receipt(receipt_id)
        assert "Updated with comment" in saved_receipt.description