"""
mocks.py
Mock implementations of all external services for testing.
"""

from typing import List, Optional, Dict, Any
from interfaces import (
    IDatabaseService, IAIService, IFileService, ISecurityService,
    UserData, MonthlyExpense
)
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import Receipt, Position
from security_utils import SecurityException
import json
import tempfile
import uuid
from datetime import datetime, timedelta
from collections import defaultdict, deque
import time


# =============================================================================
# MOCK DATABASE SERVICE
# =============================================================================

class MockDatabaseService(IDatabaseService):
    """Mock implementation of database operations for testing."""
    
    def __init__(self):
        self.users: Dict[int, UserData] = {}
        self.receipts: Dict[int, Receipt] = {}
        self.receipt_counter = 1
        self.user_receipts: Dict[int, List[int]] = defaultdict(list)
        self.backup_calls = 0
    
    def get_user(self, user_id: int) -> Optional[UserData]:
        """Get user by ID."""
        return self.users.get(user_id)
    
    def create_user_if_missing(self, user_id: int, name: str, *, is_authorized: bool = False, approval_requested: bool = False) -> UserData:
        """Create user if doesn't exist."""
        if user_id not in self.users:
            self.users[user_id] = UserData(
                user_id=user_id,
                name=name,
                is_authorized=is_authorized,
                approval_requested=approval_requested
            )
        return self.users[user_id]
    
    def set_user_authorized(self, user_id: int, authorized: bool) -> None:
        """Set user authorization status."""
        if user_id in self.users:
            self.users[user_id].is_authorized = authorized
    
    def set_user_approval_requested(self, user_id: int, requested: bool = True) -> None:
        """Set user approval request status."""
        if user_id in self.users:
            self.users[user_id].approval_requested = requested
    
    def add_receipt(self, receipt: Receipt) -> int:
        """Add receipt and return its ID."""
        receipt_id = self.receipt_counter
        self.receipt_counter += 1
        
        # Create a copy with the ID set
        receipt_copy = Receipt(
            receipt_id=receipt_id,
            user_id=receipt.user_id,
            merchant=receipt.merchant,
            category=receipt.category,
            total_amount=receipt.total_amount,
            date=receipt.date,
            text=receipt.text,
            description=receipt.description,
            positions=receipt.positions
        )
        
        self.receipts[receipt_id] = receipt_copy
        self.user_receipts[receipt.user_id].append(receipt_id)
        return receipt_id
    
    def get_receipt(self, receipt_id: int) -> Optional[Receipt]:
        """Get receipt by ID."""
        return self.receipts.get(receipt_id)
    
    def get_user_receipts(self, user_id: int) -> List[Receipt]:
        """Get all receipts for a user."""
        receipt_ids = self.user_receipts.get(user_id, [])
        return [self.receipts[rid] for rid in receipt_ids if rid in self.receipts]
    
    def get_last_n_receipts(self, user_id: int, n: int) -> List[Receipt]:
        """Get last N receipts for a user."""
        receipt_ids = self.user_receipts.get(user_id, [])
        last_n_ids = receipt_ids[-n:] if len(receipt_ids) > n else receipt_ids
        receipts = [self.receipts[rid] for rid in last_n_ids if rid in self.receipts]
        return list(reversed(receipts))  # Most recent first
    
    def delete_receipt(self, receipt_id: int, user_id: int) -> bool:
        """Delete receipt by ID and user ID."""
        if receipt_id in self.receipts and self.receipts[receipt_id].user_id == user_id:
            del self.receipts[receipt_id]
            self.user_receipts[user_id].remove(receipt_id)
            return True
        return False
    
    def get_monthly_summary(self, user_id: int, n_months: int) -> List[MonthlyExpense]:
        """Get monthly expense summary."""
        user_receipt_ids = self.user_receipts.get(user_id, [])
        receipts = [self.receipts[rid] for rid in user_receipt_ids if rid in self.receipts]
        
        # Group by month
        monthly_data = defaultdict(lambda: {'total': 0.0, 'count': 0})
        
        for receipt in receipts:
            if receipt.date:
                try:
                    # Parse DD-MM-YYYY format
                    date_obj = datetime.strptime(receipt.date, "%d-%m-%Y")
                    month_key = date_obj.strftime("%m-%Y")
                    monthly_data[month_key]['total'] += receipt.total_amount
                    monthly_data[month_key]['count'] += 1
                except ValueError:
                    # Skip receipts with invalid dates
                    continue
        
        # Convert to list and sort by month (most recent first)
        result = []
        for month, data in monthly_data.items():
            result.append(MonthlyExpense(
                month=month,
                total=data['total'],
                count=data['count']
            ))
        
        # Sort by month (most recent first)
        result.sort(key=lambda x: datetime.strptime(x.month, "%m-%Y"), reverse=True)
        return result[:n_months]
    
    def backup_database(self) -> bool:
        """Backup database to cloud storage."""
        self.backup_calls += 1
        return True  # Always succeed in tests
    
    # Helper methods for testing
    def clear_all_data(self):
        """Clear all test data."""
        self.users.clear()
        self.receipts.clear()
        self.user_receipts.clear()
        self.receipt_counter = 1
        self.backup_calls = 0
    
    def get_backup_call_count(self) -> int:
        """Get number of times backup was called."""
        return self.backup_calls


# =============================================================================
# MOCK AI SERVICE
# =============================================================================

class MockAIService(IAIService):
    """Mock implementation of AI operations for testing."""
    
    def __init__(self):
        self.parse_image_calls = []
        self.update_comment_calls = []
        self.voice_to_text_calls = []
        self.voice_to_receipt_calls = []
        
        # Default responses
        self.default_receipt_json = {
            "text": "Mock receipt text",
            "description": "Mock receipt description",
            "category": "food",
            "merchant": "Mock Store",
            "positions": [
                {
                    "description": "Mock item",
                    "quantity": "1",
                    "category": "food",
                    "price": 10.50
                }
            ],
            "total_amount": 10.50,
            "date": "01-01-2024"
        }
        
        # Customizable responses for testing scenarios
        self.custom_responses = {}
        self.should_fail = False
        self.failure_message = "Mock AI service failure"
    
    def parse_receipt_image(self, image_path: str, user_comment: Optional[str] = None) -> str:
        """Parse receipt image and return JSON string."""
        self.parse_image_calls.append({
            'image_path': image_path,
            'user_comment': user_comment,
            'timestamp': datetime.now()
        })
        
        if self.should_fail:
            raise RuntimeError(self.failure_message)
        
        # Check for custom response
        if image_path in self.custom_responses:
            return json.dumps(self.custom_responses[image_path])
        
        # Apply user comment modifications to default response
        response = self.default_receipt_json.copy()
        if user_comment:
            response['description'] = f"Modified by comment: {user_comment}"
            if "total" in user_comment.lower():
                response['total_amount'] = 25.99  # Mock modification
        
        return json.dumps(response)
    
    def update_receipt_with_comment(self, original_json: str, user_comment: str) -> str:
        """Update receipt data based on user comment."""
        self.update_comment_calls.append({
            'original_data': original_json,
            'user_comment': user_comment,
            'timestamp': datetime.now()
        })
        
        if self.should_fail:
            raise RuntimeError(self.failure_message)
        
        # Parse original and apply mock modifications
        parsed_data = json.loads(original_json)
        parsed_data['description'] = f"Updated with comment: {user_comment}"
        
        # Mock some common modifications
        if "merchant" in user_comment.lower():
            parsed_data['merchant'] = "Updated Store"
        if "amount" in user_comment.lower() or "total" in user_comment.lower():
            parsed_data['total_amount'] = 15.75
        
        return json.dumps(parsed_data)
    
    def convert_voice_to_text(self, voice_file_path: str) -> str:
        """Convert voice message to text."""
        self.voice_to_text_calls.append({
            'voice_file_path': voice_file_path,
            'timestamp': datetime.now()
        })
        
        if self.should_fail:
            raise RuntimeError(self.failure_message)
        
        # Check for custom response
        if voice_file_path in self.custom_responses:
            return self.custom_responses[voice_file_path]
        
        return "I bought groceries for 20 euros at SuperMarket yesterday"
    
    def parse_voice_to_receipt(self, transcribed_text: str) -> str:
        """Convert transcribed text to receipt structure."""
        self.voice_to_receipt_calls.append({
            'transcribed_text': transcribed_text,
            'timestamp': datetime.now()
        })
        
        if self.should_fail:
            raise RuntimeError(self.failure_message)
        
        # Create receipt based on transcribed text
        response = self.default_receipt_json.copy()
        response['description'] = f"Created from voice: {transcribed_text}"
        response['merchant'] = "Voice Store"
        
        # Extract amount if mentioned
        if "20 euro" in transcribed_text.lower():
            response['total_amount'] = 20.0
            response['positions'][0]['price'] = 20.0
        
        return json.dumps(response)
    
    # Helper methods for testing
    def set_custom_response(self, key: str, response: Any):
        """Set custom response for specific input."""
        self.custom_responses[key] = response
    
    def set_failure_mode(self, should_fail: bool, message: str = "Mock AI service failure"):
        """Configure the service to fail for testing error scenarios."""
        self.should_fail = should_fail
        self.failure_message = message
    
    def clear_call_history(self):
        """Clear all call history."""
        self.parse_image_calls.clear()
        self.update_comment_calls.clear()
        self.voice_to_text_calls.clear()
        self.voice_to_receipt_calls.clear()
    
    def get_call_count(self, method_name: str) -> int:
        """Get number of calls to a specific method."""
        call_lists = {
            'parse_image': self.parse_image_calls,
            'update_comment': self.update_comment_calls,
            'voice_to_text': self.voice_to_text_calls,
            'voice_to_receipt': self.voice_to_receipt_calls
        }
        return len(call_lists.get(method_name, []))


# =============================================================================
# MOCK FILE SERVICE
# =============================================================================

class MockFileService(IFileService):
    """Mock implementation of file operations for testing."""
    
    def __init__(self):
        self.temp_files = set()
        self.cleanup_calls = []
        self.validation_calls = []
        
        # Configuration for testing
        self.should_fail_validation = False
        self.validation_failure_message = "Mock file validation failure"
        self.max_file_size = 10 * 1024 * 1024  # 10MB
        self.allowed_mime_types = {
            'image/jpeg', 'image/png', 'image/gif', 'image/webp',
            'audio/ogg', 'audio/mpeg', 'audio/wav', 'audio/m4a'
        }
    
    def create_secure_temp_file(self, suffix: str = "") -> str:
        """Create a secure temporary file."""
        # Create actual temp file for more realistic testing
        fd, temp_path = tempfile.mkstemp(suffix=suffix, prefix="test_expenses_")
        os.close(fd)  # Close the file descriptor, keep the file
        
        self.temp_files.add(temp_path)
        return temp_path
    
    def cleanup_temp_file(self, file_path: str) -> None:
        """Clean up temporary file."""
        self.cleanup_calls.append({
            'file_path': file_path,
            'timestamp': datetime.now()
        })
        
        if file_path in self.temp_files:
            try:
                os.remove(file_path)
            except FileNotFoundError:
                pass  # File already removed
            self.temp_files.discard(file_path)
    
    def cleanup_all_temp_files(self) -> None:
        """Clean up all temporary files."""
        for file_path in list(self.temp_files):
            self.cleanup_temp_file(file_path)
    
    def validate_file_size(self, file_path: str) -> None:
        """Validate file size (raises SecurityException if invalid)."""
        self.validation_calls.append({
            'method': 'validate_file_size',
            'file_path': file_path,
            'timestamp': datetime.now()
        })
        
        if self.should_fail_validation:
            raise SecurityException(self.validation_failure_message)
        
        if not os.path.exists(file_path):
            raise SecurityException("File not found")
        
        file_size = os.path.getsize(file_path)
        if file_size > self.max_file_size:
            raise SecurityException(f"File too large: {file_size} bytes")
    
    def validate_file_type(self, file_path: str, allowed_types: set) -> str:
        """Validate file type and return MIME type."""
        self.validation_calls.append({
            'method': 'validate_file_type',
            'file_path': file_path,
            'allowed_types': allowed_types,
            'timestamp': datetime.now()
        })
        
        if self.should_fail_validation:
            raise SecurityException(self.validation_failure_message)
        
        if not os.path.exists(file_path):
            raise SecurityException("File not found")
        
        # Mock MIME type detection based on file extension
        if file_path.endswith(('.jpg', '.jpeg')):
            mime_type = 'image/jpeg'
        elif file_path.endswith('.png'):
            mime_type = 'image/png'
        elif file_path.endswith('.ogg'):
            mime_type = 'audio/ogg'
        elif file_path.endswith('.mp3'):
            mime_type = 'audio/mpeg'
        else:
            mime_type = 'application/octet-stream'
        
        if mime_type not in allowed_types:
            raise SecurityException(f"Invalid file type: {mime_type}")
        
        return mime_type
    
    # Helper methods for testing
    def set_validation_failure(self, should_fail: bool, message: str = "Mock file validation failure"):
        """Configure file validation to fail for testing."""
        self.should_fail_validation = should_fail
        self.validation_failure_message = message
    
    def get_cleanup_call_count(self) -> int:
        """Get number of cleanup calls."""
        return len(self.cleanup_calls)
    
    def get_validation_call_count(self) -> int:
        """Get number of validation calls."""
        return len(self.validation_calls)
    
    def clear_call_history(self):
        """Clear all call history."""
        self.cleanup_calls.clear()
        self.validation_calls.clear()


# =============================================================================
# MOCK SECURITY SERVICE
# =============================================================================

class MockSecurityService(ISecurityService):
    """Mock implementation of security operations for testing."""
    
    def __init__(self):
        self.rate_limit_requests = defaultdict(deque)
        self.sessions = {}
        self.rate_limit_window = 60  # seconds
        self.max_requests = 10
        self.session_timeout = timedelta(hours=24)
        
        # Call tracking
        self.rate_limit_calls = []
        self.session_calls = []
    
    def is_rate_limit_allowed(self, user_id: int) -> bool:
        """Check if user is within rate limits."""
        self.rate_limit_calls.append({
            'method': 'is_rate_limit_allowed',
            'user_id': user_id,
            'timestamp': datetime.now()
        })
        
        now = time.time()
        user_requests = self.rate_limit_requests[user_id]
        
        # Remove old requests
        while user_requests and user_requests[0] <= now - self.rate_limit_window:
            user_requests.popleft()
        
        # Check limit
        if len(user_requests) >= self.max_requests:
            return False
        
        # Add current request
        user_requests.append(now)
        return True
    
    def get_rate_limit_remaining_time(self, user_id: int) -> int:
        """Get remaining time for rate limit reset."""
        self.rate_limit_calls.append({
            'method': 'get_rate_limit_remaining_time',
            'user_id': user_id,
            'timestamp': datetime.now()
        })
        
        user_requests = self.rate_limit_requests[user_id]
        if not user_requests:
            return 0
        
        oldest_request = user_requests[0]
        remaining = self.rate_limit_window - (time.time() - oldest_request)
        return max(0, int(remaining))
    
    def validate_session(self, user_id: int) -> bool:
        """Validate user session."""
        self.session_calls.append({
            'method': 'validate_session',
            'user_id': user_id,
            'timestamp': datetime.now()
        })
        
        if user_id not in self.sessions:
            return False
        
        session = self.sessions[user_id]
        if datetime.now() - session['last_activity'] > self.session_timeout:
            del self.sessions[user_id]
            return False
        
        session['last_activity'] = datetime.now()
        return True
    
    def create_session(self, user_id: int) -> str:
        """Create new session for user."""
        self.session_calls.append({
            'method': 'create_session',
            'user_id': user_id,
            'timestamp': datetime.now()
        })
        
        session_id = str(uuid.uuid4())
        self.sessions[user_id] = {
            'session_id': session_id,
            'created_at': datetime.now(),
            'last_activity': datetime.now(),
            'is_authenticated': False
        }
        return session_id
    
    def authenticate_session(self, user_id: int) -> None:
        """Mark session as authenticated."""
        self.session_calls.append({
            'method': 'authenticate_session',
            'user_id': user_id,
            'timestamp': datetime.now()
        })
        
        if user_id in self.sessions:
            self.sessions[user_id]['is_authenticated'] = True
    
    def is_authenticated(self, user_id: int) -> bool:
        """Check if user session is authenticated."""
        self.session_calls.append({
            'method': 'is_authenticated',
            'user_id': user_id,
            'timestamp': datetime.now()
        })
        
        if user_id not in self.sessions:
            return False
        return self.sessions[user_id].get('is_authenticated', False)
    
    def cleanup_expired_sessions(self) -> None:
        """Clean up expired sessions."""
        self.session_calls.append({
            'method': 'cleanup_expired_sessions',
            'timestamp': datetime.now()
        })
        
        now = datetime.now()
        expired_users = [
            user_id for user_id, session in self.sessions.items()
            if now - session['last_activity'] > self.session_timeout
        ]
        for user_id in expired_users:
            del self.sessions[user_id]
    
    # Helper methods for testing
    def set_rate_limit_config(self, max_requests: int, window_seconds: int):
        """Configure rate limiting for testing."""
        self.max_requests = max_requests
        self.rate_limit_window = window_seconds
    
    def trigger_rate_limit(self, user_id: int):
        """Force user to hit rate limit for testing."""
        now = time.time()
        user_requests = self.rate_limit_requests[user_id]
        user_requests.clear()
        
        # Add maximum requests
        for i in range(self.max_requests):
            user_requests.append(now)
    
    def clear_all_sessions(self):
        """Clear all sessions."""
        self.sessions.clear()
        self.rate_limit_requests.clear()
    
    def clear_call_history(self):
        """Clear all call history."""
        self.rate_limit_calls.clear()
        self.session_calls.clear()
    
    def get_call_count(self, method_name: str) -> int:
        """Get call count for specific method."""
        rate_limit_methods = {'is_rate_limit_allowed', 'get_rate_limit_remaining_time'}
        session_methods = {'validate_session', 'create_session', 'authenticate_session', 'is_authenticated', 'cleanup_expired_sessions'}
        
        if method_name in rate_limit_methods:
            return len([call for call in self.rate_limit_calls if call['method'] == method_name])
        elif method_name in session_methods:
            return len([call for call in self.session_calls if call['method'] == method_name])
        
        return 0