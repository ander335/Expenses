"""
security_utils.py
Security utilities for file handling, input validation, and rate limiting.
"""

import os
import tempfile
import uuid
import time
import mimetypes
from pathlib import Path
from typing import Dict, Any, Optional, Set
from collections import defaultdict, deque
from datetime import datetime, timedelta
import bleach
from logger_config import logger, security_logger

# Security configuration from environment variables
MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', '10485760'))  # 10MB default
MAX_USERS = int(os.getenv('MAX_USERS', '100'))
RATE_LIMIT_REQUESTS = int(os.getenv('RATE_LIMIT_REQUESTS', '10'))  # per minute
RATE_LIMIT_WINDOW = int(os.getenv('RATE_LIMIT_WINDOW', '60'))  # seconds

# Allowed file types
ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
ALLOWED_AUDIO_TYPES = {'audio/ogg', 'audio/mpeg', 'audio/wav', 'audio/m4a'}

class SecurityException(Exception):
    """Custom exception that doesn't expose internal details"""
    def __init__(self, user_message: str, internal_details: str = None):
        self.user_message = user_message
        self.internal_details = internal_details
        super().__init__(user_message)
        if internal_details:
            logger.error(f"Security error internal details: {internal_details}")

class RateLimiter:
    """Rate limiter to prevent abuse"""
    def __init__(self):
        self.requests: Dict[int, deque] = defaultdict(deque)
    
    def is_allowed(self, user_id: int) -> bool:
        """Check if user is within rate limits"""
        now = time.time()
        user_requests = self.requests[user_id]
        
        # Remove old requests outside the window
        while user_requests and user_requests[0] <= now - RATE_LIMIT_WINDOW:
            user_requests.popleft()
        
        # Check if under limit
        if len(user_requests) >= RATE_LIMIT_REQUESTS:
            security_logger.log_rate_limit(user_id, "general")
            return False
        
        # Add current request
        user_requests.append(now)
        return True
    
    def get_remaining_time(self, user_id: int) -> int:
        """Get remaining time in seconds until rate limit resets"""
        if not self.requests[user_id]:
            return 0
        oldest_request = self.requests[user_id][0]
        remaining = RATE_LIMIT_WINDOW - (time.time() - oldest_request)
        return max(0, int(remaining))

class SecureFileHandler:
    """Secure file handling with proper validation and cleanup"""
    
    def __init__(self):
        self.temp_files: Set[str] = set()
    
    def validate_file_size(self, file_path: str) -> None:
        """Validate file size"""
        if not os.path.exists(file_path):
            raise SecurityException("File not found", f"File path: {file_path}")
        
        file_size = os.path.getsize(file_path)
        if file_size > MAX_FILE_SIZE:
            security_logger.log_validation_error(0, "file_size", f"File size: {file_size}, max: {MAX_FILE_SIZE}")
            raise SecurityException(
                f"File too large. Maximum size allowed: {MAX_FILE_SIZE // 1024 // 1024}MB",
                f"File size: {file_size}, max: {MAX_FILE_SIZE}"
            )
    
    def validate_file_type(self, file_path: str, allowed_types: Set[str]) -> str:
        """Validate file type using both extension and magic bytes"""
        if not os.path.exists(file_path):
            raise SecurityException("File not found", f"File path: {file_path}")
        
        # Check MIME type using Python's built-in mimetypes
        mime_type, _ = mimetypes.guess_type(file_path)
        
        # For files without extension or unknown types, try to detect from content
        if not mime_type:
            # Basic magic byte detection for common types
            with open(file_path, 'rb') as f:
                header = f.read(12)
                if header.startswith(b'\xff\xd8\xff'):
                    mime_type = 'image/jpeg'
                elif header.startswith(b'\x89PNG'):
                    mime_type = 'image/png'
                elif header.startswith(b'OggS'):
                    mime_type = 'audio/ogg'
                elif header.startswith(b'ID3') or header[0:2] == b'\xff\xfb':
                    mime_type = 'audio/mpeg'
        
        if not mime_type or mime_type not in allowed_types:
            security_logger.log_validation_error(0, "file_type", f"Detected MIME type: {mime_type}, allowed: {allowed_types}")
            raise SecurityException(
                "Invalid file type. Only images and audio files are allowed.",
                f"Detected MIME type: {mime_type}, allowed: {allowed_types}"
            )
        
        logger.info(f"File validation successful: {mime_type}")
        return mime_type
    
    def create_secure_temp_file(self, suffix: str = "") -> str:
        """Create a secure temporary file with unique name"""
        # Use secure temporary directory
        temp_dir = tempfile.gettempdir()
        secure_filename = f"expenses_bot_{uuid.uuid4().hex}{suffix}"
        temp_path = os.path.join(temp_dir, secure_filename)
        
        # Track for cleanup
        self.temp_files.add(temp_path)
        logger.debug(f"Created secure temp file: {temp_path}")
        return temp_path
    
    def cleanup_temp_file(self, file_path: str) -> None:
        """Safely remove temporary file"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"Cleaned up temp file: {file_path}")
            self.temp_files.discard(file_path)
        except Exception as e:
            logger.error(f"Failed to cleanup temp file {file_path}: {e}")
    
    def cleanup_all_temp_files(self) -> None:
        """Clean up all tracked temporary files"""
        for file_path in list(self.temp_files):
            self.cleanup_temp_file(file_path)

class InputValidator:
    """Input validation and sanitization"""
    
    @staticmethod
    def sanitize_text(text: str, max_length: int = 1000) -> str:
        """Sanitize text input"""
        if not text:
            return ""
        
        # Limit length
        if len(text) > max_length:
            text = text[:max_length]
            logger.warning(f"Text truncated to {max_length} characters")
        
        # Basic HTML sanitization (remove potentially dangerous tags)
        cleaned = bleach.clean(text, tags=[], strip=True)
        
        # Remove any control characters except common whitespace
        cleaned = ''.join(char for char in cleaned if ord(char) >= 32 or char in '\t\n\r')
        
        return cleaned.strip()
    
    @staticmethod
    def validate_receipt_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize receipt data from API"""
        if not isinstance(data, dict):
            raise SecurityException("Invalid data format", f"Expected dict, got {type(data)}")
        
        # Required fields
        required_fields = ['merchant', 'category', 'total_amount']
        for field in required_fields:
            if field not in data:
                raise SecurityException(f"Missing required field: {field}")
        
        # Validate and sanitize string fields
        string_fields = ['merchant', 'category', 'text', 'description']
        for field in string_fields:
            if field in data and data[field]:
                data[field] = InputValidator.sanitize_text(str(data[field]))
        
        # Validate numeric fields
        try:
            total_amount = float(data['total_amount'])
            if total_amount < 0 or total_amount > 1000000:  # Reasonable limits
                raise SecurityException("Invalid total amount")
            data['total_amount'] = total_amount
        except (ValueError, TypeError):
            raise SecurityException("Invalid total amount format")
        
        # Validate date format
        if 'date' in data and data['date']:
            date_str = str(data['date'])
            if not InputValidator.validate_date_format(date_str):
                logger.warning(f"Invalid date format: {date_str}")
                data['date'] = None
        
        # Validate positions
        if 'positions' in data and isinstance(data['positions'], list):
            validated_positions = []
            for pos in data['positions'][:50]:  # Limit number of positions
                if isinstance(pos, dict):
                    validated_pos = InputValidator.validate_position_data(pos)
                    if validated_pos:
                        validated_positions.append(validated_pos)
            data['positions'] = validated_positions
        
        return data
    
    @staticmethod
    def validate_position_data(pos: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Validate individual position data"""
        try:
            # Required fields for position
            if not all(field in pos for field in ['description', 'price']):
                return None
            
            # Sanitize description
            pos['description'] = InputValidator.sanitize_text(str(pos['description']))
            
            # Validate price
            price = float(pos['price'])
            if price < 0 or price > 100000:  # Reasonable limits for individual items
                return None
            pos['price'] = price
            
            # Sanitize other fields
            if 'quantity' in pos:
                pos['quantity'] = InputValidator.sanitize_text(str(pos['quantity']), max_length=50)
            if 'category' in pos:
                pos['category'] = InputValidator.sanitize_text(str(pos['category']))
            
            return pos
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    def validate_date_format(date_str: str) -> bool:
        """Validate date format (DD-MM-YYYY)"""
        try:
            datetime.strptime(date_str, "%d-%m-%Y")
            return True
        except ValueError:
            return False
    
    @staticmethod
    def validate_user_id(user_id: Any) -> int:
        """Validate Telegram user ID"""
        try:
            uid = int(user_id)
            if uid <= 0 or uid > 2**63:  # Telegram user ID constraints
                raise SecurityException("Invalid user ID")
            return uid
        except (ValueError, TypeError):
            raise SecurityException("Invalid user ID format")

class SessionManager:
    """Simple session management for enhanced security"""
    
    def __init__(self):
        self.sessions: Dict[int, Dict[str, Any]] = {}
        self.session_timeout = timedelta(hours=24)
    
    def create_session(self, user_id: int) -> str:
        """Create a new session for user"""
        session_id = str(uuid.uuid4())
        self.sessions[user_id] = {
            'session_id': session_id,
            'created_at': datetime.now(),
            'last_activity': datetime.now(),
            'is_authenticated': False
        }
        return session_id
    
    def validate_session(self, user_id: int, session_id: str = None) -> bool:
        """Validate user session"""
        if user_id not in self.sessions:
            return False
        
        session = self.sessions[user_id]
        
        # Check timeout
        if datetime.now() - session['last_activity'] > self.session_timeout:
            del self.sessions[user_id]
            return False
        
        # Update last activity
        session['last_activity'] = datetime.now()
        return True
    
    def authenticate_session(self, user_id: int) -> None:
        """Mark session as authenticated"""
        if user_id in self.sessions:
            self.sessions[user_id]['is_authenticated'] = True
    
    def is_authenticated(self, user_id: int) -> bool:
        """Check if user session is authenticated"""
        if user_id not in self.sessions:
            return False
        return self.sessions[user_id].get('is_authenticated', False)
    
    def cleanup_expired_sessions(self) -> None:
        """Clean up expired sessions"""
        now = datetime.now()
        expired_users = [
            user_id for user_id, session in self.sessions.items()
            if now - session['last_activity'] > self.session_timeout
        ]
        for user_id in expired_users:
            del self.sessions[user_id]

# Global instances
rate_limiter = RateLimiter()
file_handler = SecureFileHandler()
session_manager = SessionManager()