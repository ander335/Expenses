"""
interfaces.py
Abstract interfaces for dependency injection and testing.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from dataclasses import dataclass

# Import types conditionally to avoid runtime import issues
if TYPE_CHECKING:
    from db import User, Receipt, Position


# =============================================================================
# DATA TRANSFER OBJECTS
# =============================================================================

@dataclass
class ParsedReceipt:
    """Data transfer object for parsed receipt data."""
    merchant: str
    category: str
    total_amount: float
    date: Optional[str] = None
    text: Optional[str] = None
    description: Optional[str] = None
    positions: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.positions is None:
            self.positions = []


@dataclass
class UserData:
    """Data transfer object for user information."""
    user_id: int
    name: str
    is_authorized: bool = False
    approval_requested: bool = False


@dataclass
class MonthlyExpense:
    """Data transfer object for monthly expense summary."""
    month: str
    total: float
    count: int


# =============================================================================
# DATABASE INTERFACE
# =============================================================================

class IDatabaseService(ABC):
    """Abstract interface for database operations."""
    
    @abstractmethod
    def get_user(self, user_id: int) -> Optional[UserData]:
        """Get user by ID."""
        pass
    
    @abstractmethod
    def create_user_if_missing(self, user_id: int, name: str, *, is_authorized: bool = False, approval_requested: bool = False) -> UserData:
        """Create user if doesn't exist."""
        pass
    
    @abstractmethod
    def set_user_authorized(self, user_id: int, authorized: bool) -> None:
        """Set user authorization status."""
        pass
    
    @abstractmethod
    def set_user_approval_requested(self, user_id: int, requested: bool = True) -> None:
        """Set user approval request status."""
        pass
    
    @abstractmethod
    def add_receipt(self, receipt: 'Receipt') -> int:
        """Add receipt and return its ID."""
        pass
    
    @abstractmethod
    def get_receipt(self, receipt_id: int) -> Optional['Receipt']:
        """Get receipt by ID."""
        pass
    
    @abstractmethod
    def get_user_receipts(self, user_id: int) -> List['Receipt']:
        """Get all receipts for a user."""
        pass
    
    @abstractmethod
    def get_last_n_receipts(self, user_id: int, n: int) -> List['Receipt']:
        """Get last N receipts for a user."""
        pass
    
    @abstractmethod
    def delete_receipt(self, receipt_id: int, user_id: int) -> bool:
        """Delete receipt by ID and user ID."""
        pass
    
    @abstractmethod
    def get_monthly_summary(self, user_id: int, n_months: int) -> List[MonthlyExpense]:
        """Get monthly expense summary."""
        pass
    
    @abstractmethod
    def backup_database(self) -> bool:
        """Backup database to cloud storage."""
        pass


# =============================================================================
# AI SERVICE INTERFACE
# =============================================================================

class IAIService(ABC):
    """Abstract interface for AI operations (Gemini API)."""
    
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
        """Convert transcribed text to receipt structure."""
        pass


# =============================================================================
# FILE HANDLING INTERFACE
# =============================================================================

class IFileService(ABC):
    """Abstract interface for file operations."""
    
    @abstractmethod
    def create_secure_temp_file(self, suffix: str = "") -> str:
        """Create a secure temporary file."""
        pass
    
    @abstractmethod
    def cleanup_temp_file(self, file_path: str) -> None:
        """Clean up temporary file."""
        pass
    
    @abstractmethod
    def cleanup_all_temp_files(self) -> None:
        """Clean up all temporary files."""
        pass
    
    @abstractmethod
    def validate_file_size(self, file_path: str) -> None:
        """Validate file size (raises SecurityException if invalid)."""
        pass
    
    @abstractmethod
    def validate_file_type(self, file_path: str, allowed_types: set) -> str:
        """Validate file type and return MIME type."""
        pass


# =============================================================================
# SECURITY INTERFACE
# =============================================================================

class ISecurityService(ABC):
    """Abstract interface for security operations."""
    
    @abstractmethod
    def is_rate_limit_allowed(self, user_id: int) -> bool:
        """Check if user is within rate limits."""
        pass
    
    @abstractmethod
    def get_rate_limit_remaining_time(self, user_id: int) -> int:
        """Get remaining time for rate limit reset."""
        pass
    
    @abstractmethod
    def validate_session(self, user_id: int) -> bool:
        """Validate user session."""
        pass
    
    @abstractmethod
    def create_session(self, user_id: int) -> str:
        """Create new session for user."""
        pass
    
    @abstractmethod
    def authenticate_session(self, user_id: int) -> None:
        """Mark session as authenticated."""
        pass
    
    @abstractmethod
    def is_authenticated(self, user_id: int) -> bool:
        """Check if user session is authenticated."""
        pass
    
    @abstractmethod
    def cleanup_expired_sessions(self) -> None:
        """Clean up expired sessions."""
        pass


# =============================================================================
# BUSINESS LOGIC INTERFACE
# =============================================================================

class IExpensesService(ABC):
    """Abstract interface for main business logic."""
    
    @abstractmethod
    def process_receipt_image(self, user_id: int, image_path: str, user_comment: Optional[str] = None) -> ParsedReceipt:
        """Process receipt image and return parsed data."""
        pass
    
    @abstractmethod
    def process_voice_receipt(self, user_id: int, voice_path: str) -> ParsedReceipt:
        """Process voice message as receipt."""
        pass
    
    @abstractmethod
    def process_text_receipt(self, user_id: int, text_description: str) -> ParsedReceipt:
        """Process text description as receipt."""
        pass
    
    @abstractmethod
    def update_receipt_with_user_comment(self, user_id: int, original_data: str, user_comment: str) -> ParsedReceipt:
        """Update receipt based on user feedback."""
        pass
    
    @abstractmethod
    def save_receipt(self, user_id: int, parsed_receipt: ParsedReceipt) -> int:
        """Save parsed receipt to database."""
        pass
    
    @abstractmethod
    def get_user_expenses(self, user_id: int, limit: int = 10) -> List["Receipt"]:
        """Get user's recent expenses."""
        pass
    
    @abstractmethod
    def delete_user_expense(self, user_id: int, receipt_id: int) -> bool:
        """Delete user's expense."""
        pass
    
    @abstractmethod
    def get_expense_summary(self, user_id: int, months: int) -> List[MonthlyExpense]:
        """Get expense summary for specified months."""
        pass
    
    @abstractmethod
    def check_user_authorization(self, user_id: int, user_name: str) -> tuple[bool, Optional[str]]:
        """Check user authorization status. Returns (is_authorized, message)."""
        pass


# =============================================================================
# APPLICATION INTERFACE
# =============================================================================

class IExpensesApp(ABC):
    """Abstract interface for the main application."""
    
    @abstractmethod
    def get_database_service(self) -> IDatabaseService:
        """Get database service instance."""
        pass
    
    @abstractmethod
    def get_ai_service(self) -> IAIService:
        """Get AI service instance."""
        pass
    
    @abstractmethod
    def get_file_service(self) -> IFileService:
        """Get file service instance."""
        pass
    
    @abstractmethod
    def get_security_service(self) -> ISecurityService:
        """Get security service instance."""
        pass
    
    @abstractmethod
    def get_expenses_service(self) -> IExpensesService:
        """Get business logic service instance."""
        pass
    
    @abstractmethod
    def get_admin_user_id(self) -> int:
        """Get admin user ID."""
        pass