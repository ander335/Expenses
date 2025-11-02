"""
services.py
Concrete implementations of service interfaces.
"""

from typing import List, Optional, Dict, Any, TYPE_CHECKING
from interfaces import (
    IDatabaseService, IAIService, IFileService, ISecurityService, IExpensesService,
    UserData, MonthlyExpense, ParsedReceipt
)

if TYPE_CHECKING:
    from db import Receipt

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import db modules when needed to avoid import-time initialization
from logger_config import logger
import json


# =============================================================================
# DATABASE SERVICE IMPLEMENTATION
# =============================================================================

class DatabaseService(IDatabaseService):
    """Concrete implementation of database operations."""
    
    def get_user(self, user_id: int) -> Optional[UserData]:
        """Get user by ID."""
        from db import get_user
        user = get_user(user_id)
        if user:
            return UserData(
                user_id=user.user_id,
                name=user.name,
                is_authorized=user.is_authorized,
                approval_requested=user.approval_requested
            )
        return None
    
    def create_user_if_missing(self, user_id: int, name: str, *, is_authorized: bool = False, approval_requested: bool = False) -> UserData:
        """Create user if doesn't exist."""
        from db import create_user_if_missing
        user = create_user_if_missing(user_id, name, is_authorized=is_authorized, approval_requested=approval_requested)
        return UserData(
            user_id=user.user_id,
            name=user.name,
            is_authorized=user.is_authorized,
            approval_requested=user.approval_requested
        )
    
    def set_user_authorized(self, user_id: int, authorized: bool) -> None:
        """Set user authorization status."""
        from db import set_user_authorized
        set_user_authorized(user_id, authorized)
    
    def set_user_approval_requested(self, user_id: int, requested: bool = True) -> None:
        """Set user approval request status."""
        from db import set_user_approval_requested
        set_user_approval_requested(user_id, requested)
    
    def add_receipt(self, receipt) -> int:
        """Add receipt and return its ID."""
        from db import add_receipt
        return add_receipt(receipt)
    
    def get_receipt(self, receipt_id: int):
        """Get receipt by ID."""
        from db import get_receipt
        return get_receipt(receipt_id)
    
    def get_user_receipts(self, user_id: int):
        """Get all receipts for a user."""
        from db import get_user_receipts
        return get_user_receipts(user_id)
    
    def get_last_n_receipts(self, user_id: int, n: int):
        """Get last N receipts for a user."""
        from db import get_last_n_receipts
        return get_last_n_receipts(user_id, n)
    
    def delete_receipt(self, receipt_id: int, user_id: int) -> bool:
        """Delete receipt by ID and user ID."""
        from db import delete_receipt
        return delete_receipt(receipt_id, user_id)
    
    def get_monthly_summary(self, user_id: int, n_months: int) -> List[MonthlyExpense]:
        """Get monthly expense summary."""
        from db import get_monthly_summary
        summary_data = get_monthly_summary(user_id, n_months)
        return [
            MonthlyExpense(
                month=month_data['month'],
                total=month_data['total'],
                count=month_data['count']
            )
            for month_data in summary_data
        ]
    
    def backup_database(self) -> bool:
        """Backup database to cloud storage."""
        from db import get_cloud_storage
        cloud_storage = get_cloud_storage()
        if cloud_storage:
            return cloud_storage.check_and_upload_db()
        return False


# =============================================================================
# AI SERVICE IMPLEMENTATION
# =============================================================================

class AIService(IAIService):
    """Concrete implementation of AI operations."""
    
    def parse_receipt_image(self, image_path: str, user_comment: Optional[str] = None) -> str:
        """Parse receipt image and return JSON string."""
        from gemini import parse_receipt_image
        return parse_receipt_image(image_path, user_comment)
    
    def update_receipt_with_comment(self, original_json: str, user_comment: str) -> str:
        """Update receipt data based on user comment."""
        from gemini import update_receipt_with_comment
        return update_receipt_with_comment(original_json, user_comment)
    
    def convert_voice_to_text(self, voice_file_path: str) -> str:
        """Convert voice message to text."""
        from gemini import convert_voice_to_text
        return convert_voice_to_text(voice_file_path)
    
    def parse_voice_to_receipt(self, transcribed_text: str) -> str:
        """Convert transcribed text to receipt structure."""
        from gemini import parse_voice_to_receipt
        return parse_voice_to_receipt(transcribed_text)


# =============================================================================
# FILE SERVICE IMPLEMENTATION
# =============================================================================

class FileService(IFileService):
    """Concrete implementation of file operations."""
    
    def create_secure_temp_file(self, suffix: str = "") -> str:
        """Create a secure temporary file."""
        from security_utils import file_handler
        return file_handler.create_secure_temp_file(suffix)
    
    def cleanup_temp_file(self, file_path: str) -> None:
        """Clean up temporary file."""
        from security_utils import file_handler
        file_handler.cleanup_temp_file(file_path)
    
    def cleanup_all_temp_files(self) -> None:
        """Clean up all temporary files."""
        from security_utils import file_handler
        file_handler.cleanup_all_temp_files()
    
    def validate_file_size(self, file_path: str) -> None:
        """Validate file size (raises SecurityException if invalid)."""
        from security_utils import file_handler
        file_handler.validate_file_size(file_path)
    
    def validate_file_type(self, file_path: str, allowed_types: set) -> str:
        """Validate file type and return MIME type."""
        from security_utils import file_handler
        return file_handler.validate_file_type(file_path, allowed_types)


# =============================================================================
# SECURITY SERVICE IMPLEMENTATION
# =============================================================================

class SecurityService(ISecurityService):
    """Concrete implementation of security operations."""
    
    def is_rate_limit_allowed(self, user_id: int) -> bool:
        """Check if user is within rate limits."""
        from security_utils import rate_limiter
        return rate_limiter.is_allowed(user_id)
    
    def get_rate_limit_remaining_time(self, user_id: int) -> int:
        """Get remaining time for rate limit reset."""
        from security_utils import rate_limiter
        return rate_limiter.get_remaining_time(user_id)
    
    def validate_session(self, user_id: int) -> bool:
        """Validate user session."""
        from security_utils import session_manager
        return session_manager.validate_session(user_id)
    
    def create_session(self, user_id: int) -> str:
        """Create new session for user."""
        from security_utils import session_manager
        return session_manager.create_session(user_id)
    
    def authenticate_session(self, user_id: int) -> None:
        """Mark session as authenticated."""
        from security_utils import session_manager
        session_manager.authenticate_session(user_id)
    
    def is_authenticated(self, user_id: int) -> bool:
        """Check if user session is authenticated."""
        from security_utils import session_manager
        return session_manager.is_authenticated(user_id)
    
    def cleanup_expired_sessions(self) -> None:
        """Clean up expired sessions."""
        from security_utils import session_manager
        session_manager.cleanup_expired_sessions()


# =============================================================================
# BUSINESS LOGIC SERVICE IMPLEMENTATION
# =============================================================================

class ExpensesService(IExpensesService):
    """Concrete implementation of business logic."""
    
    def __init__(self, db_service: IDatabaseService, ai_service: IAIService, 
                 file_service: IFileService, security_service: ISecurityService,
                 admin_user_id: int):
        self.db_service = db_service
        self.ai_service = ai_service
        self.file_service = file_service
        self.security_service = security_service
        self.admin_user_id = admin_user_id
    
    def process_receipt_image(self, user_id: int, image_path: str, user_comment: Optional[str] = None) -> ParsedReceipt:
        """Process receipt image and return parsed data."""
        from security_utils import ALLOWED_IMAGE_TYPES
        from parse import parse_receipt_from_gemini
        from logger_config import logger
        import json
        
        logger.info(f"Processing receipt image for user {user_id}")
        
        # Validate file
        self.file_service.validate_file_size(image_path)
        mime_type = self.file_service.validate_file_type(image_path, ALLOWED_IMAGE_TYPES)
        logger.info(f"File validation successful: {mime_type}")
        
        # Parse with AI
        gemini_output = self.ai_service.parse_receipt_image(image_path, user_comment)
        logger.info("Successfully received response from AI service")
        
        # Parse into receipt object
        receipt = parse_receipt_from_gemini(gemini_output, user_id)
        logger.info(f"Receipt parsed successfully: {receipt.merchant}, {receipt.total_amount:.2f}")
        
        return ParsedReceipt(
            merchant=receipt.merchant,
            category=receipt.category,
            total_amount=receipt.total_amount,
            date=receipt.date,
            text=receipt.text,
            description=receipt.description,
            positions=[{
                'description': pos.description,
                'quantity': pos.quantity,
                'category': pos.category,
                'price': pos.price
            } for pos in receipt.positions]
        )
    
    def process_voice_receipt(self, user_id: int, voice_path: str) -> ParsedReceipt:
        """Process voice message as receipt."""
        from security_utils import ALLOWED_AUDIO_TYPES
        from parse import parse_receipt_from_gemini
        from logger_config import logger
        
        logger.info(f"Processing voice receipt for user {user_id}")
        
        # Validate file
        self.file_service.validate_file_size(voice_path)
        mime_type = self.file_service.validate_file_type(voice_path, ALLOWED_AUDIO_TYPES)
        logger.info(f"Voice file validation successful: {mime_type}")
        
        # Transcribe voice
        transcribed_text = self.ai_service.convert_voice_to_text(voice_path)
        logger.info(f"Voice transcription successful: {transcribed_text[:100]}...")
        
        # Convert to receipt structure
        gemini_output = self.ai_service.parse_voice_to_receipt(transcribed_text)
        logger.info("Successfully received receipt structure from AI service")
        
        # Parse into receipt object
        receipt = parse_receipt_from_gemini(gemini_output, user_id)
        logger.info(f"Receipt parsed successfully: {receipt.merchant}, {receipt.total_amount:.2f}")
        
        return ParsedReceipt(
            merchant=receipt.merchant,
            category=receipt.category,
            total_amount=receipt.total_amount,
            date=receipt.date,
            text=receipt.text,
            description=receipt.description,
            positions=[{
                'description': pos.description,
                'quantity': pos.quantity,
                'category': pos.category,
                'price': pos.price
            } for pos in receipt.positions]
        )
    
    def process_text_receipt(self, user_id: int, text_description: str) -> ParsedReceipt:
        """Process text description as receipt."""
        from parse import parse_receipt_from_gemini
        from logger_config import logger
        
        logger.info(f"Processing text receipt for user {user_id}")
        
        # Convert text to receipt structure
        gemini_output = self.ai_service.parse_voice_to_receipt(text_description)
        logger.info("Successfully received receipt structure from AI service for text input")
        
        # Parse into receipt object
        receipt = parse_receipt_from_gemini(gemini_output, user_id)
        logger.info(f"Receipt parsed successfully: {receipt.merchant}, {receipt.total_amount:.2f}")
        
        return ParsedReceipt(
            merchant=receipt.merchant,
            category=receipt.category,
            total_amount=receipt.total_amount,
            date=receipt.date,
            text=receipt.text,
            description=receipt.description,
            positions=[{
                'description': pos.description,
                'quantity': pos.quantity,
                'category': pos.category,
                'price': pos.price
            } for pos in receipt.positions]
        )
    
    def update_receipt_with_user_comment(self, user_id: int, original_data: str, user_comment: str) -> ParsedReceipt:
        """Update receipt based on user feedback."""
        from parse import parse_receipt_from_gemini
        from logger_config import logger
        import json
        
        logger.info(f"Updating receipt with user comment: {user_comment}")
        
        # Get updated data from AI
        updated_json = self.ai_service.update_receipt_with_comment(original_data, user_comment)
        logger.info("Successfully received updated JSON from AI service")
        
        # Parse into receipt object
        try:
            receipt = parse_receipt_from_gemini(updated_json, user_id)
            
            return ParsedReceipt(
                merchant=receipt.merchant,
                category=receipt.category,
                total_amount=receipt.total_amount,
                date=receipt.date,
                text=receipt.text,
                description=receipt.description,
                positions=[{
                    'description': pos.description,
                    'quantity': pos.quantity,
                    'category': pos.category,
                    'price': pos.price
                } for pos in receipt.positions]
            )
        except Exception as e:
            logger.error(f"Error updating receipt: {e}")
            raise
    
    def save_receipt(self, user_id: int, parsed_receipt: ParsedReceipt) -> int:
        """Save parsed receipt to database."""
        from db import Position, Receipt
        from logger_config import logger
        
        logger.info(f"Saving receipt to database for user {user_id}")
        
        # Convert ParsedReceipt to Receipt object
        positions = [
            Position(
                description=pos['description'],
                quantity=pos['quantity'],
                category=pos['category'],
                price=pos['price']
            )
            for pos in parsed_receipt.positions
        ]
        
        receipt = Receipt(
            user_id=user_id,
            merchant=parsed_receipt.merchant,
            category=parsed_receipt.category,
            total_amount=parsed_receipt.total_amount,
            date=parsed_receipt.date,
            text=parsed_receipt.text,
            description=parsed_receipt.description,
            positions=positions
        )
        
        receipt_id = self.db_service.add_receipt(receipt)
        logger.info(f"Receipt saved successfully with ID: {receipt_id}")
        return receipt_id
    
    def get_user_expenses(self, user_id: int, limit: int = 10) -> List["Receipt"]:
        """Get user's recent expenses."""
        return self.db_service.get_last_n_receipts(user_id, limit)
    
    def delete_user_expense(self, user_id: int, receipt_id: int) -> bool:
        """Delete user's expense."""
        return self.db_service.delete_receipt(receipt_id, user_id)
    
    def get_expense_summary(self, user_id: int, months: int) -> List[MonthlyExpense]:
        """Get expense summary for specified months."""
        return self.db_service.get_monthly_summary(user_id, months)
    
    def check_user_authorization(self, user_id: int, user_name: str) -> tuple[bool, Optional[str]]:
        """Check user authorization status. Returns (is_authorized, message)."""
        # Check rate limiting first
        if not self.security_service.is_rate_limit_allowed(user_id):
            remaining = self.security_service.get_rate_limit_remaining_time(user_id)
            return False, f"Too many requests. Please wait {remaining} seconds before trying again."
        
        # Validate session
        if not self.security_service.validate_session(user_id):
            self.security_service.create_session(user_id)
        
        # Always authorize admin
        if user_id == self.admin_user_id:
            self.db_service.create_user_if_missing(user_id, user_name, is_authorized=True, approval_requested=False)
            self.security_service.authenticate_session(user_id)
            return True, None
        
        # Check database authorization
        user_data = self.db_service.get_user(user_id)
        if user_data and user_data.is_authorized:
            self.security_service.authenticate_session(user_id)
            return True, None
        
        # Handle new or unauthorized users
        if not user_data:
            logger.warning(f"Unauthorized (new) access attempt from {user_name} (ID: {user_id})")
            self.db_service.create_user_if_missing(user_id, user_name, is_authorized=False, approval_requested=True)
            return False, "Your access request has been sent to the admin. You'll be notified once approved."
        
        # Existing but not authorized
        if not user_data.approval_requested:
            self.db_service.set_user_approval_requested(user_id, True)
        
        return False, "Your access is pending admin approval. Please wait."


# =============================================================================
# APPLICATION SERVICE FACTORY
# =============================================================================

class ExpensesApp:
    """Main application class that provides access to all services."""
    
    def __init__(self):
        # Initialize all services
        from auth_data import TELEGRAM_ADMIN_ID
        
        self._db_service = DatabaseService()
        self._ai_service = AIService()
        self._file_service = FileService()
        self._security_service = SecurityService()
        self._expenses_service = ExpensesService(
            self._db_service, 
            self._ai_service, 
            self._file_service, 
            self._security_service,
            TELEGRAM_ADMIN_ID
        )
    
    def get_database_service(self) -> IDatabaseService:
        """Get database service instance."""
        return self._db_service
    
    def get_ai_service(self) -> IAIService:
        """Get AI service instance."""
        return self._ai_service
    
    def get_file_service(self) -> IFileService:
        """Get file service instance."""
        return self._file_service
    
    def get_security_service(self) -> ISecurityService:
        """Get security service instance."""
        return self._security_service
    
    def get_expenses_service(self) -> IExpensesService:
        """Get business logic service instance."""
        return self._expenses_service
    
    def get_admin_user_id(self) -> int:
        """Get admin user ID."""
        from auth_data import TELEGRAM_ADMIN_ID
        return TELEGRAM_ADMIN_ID