"""
logger_config.py
Configures logging for the application with enhanced security
"""

import logging
import sys
import re
import os
from typing import Any

def redact_sensitive_data(message: str) -> str:
    """Redact sensitive information like API keys, tokens, and personal data from error messages"""
    if not isinstance(message, str):
        message = str(message)
    
    # Redact API keys - matches key=<any characters> pattern
    message = re.sub(r'[?&]key=[^& ]+', '?key=***', message)
    
    # Redact bot tokens
    message = re.sub(r'bot\d+:[A-Za-z0-9_-]{35}', 'bot***:***', message, flags=re.IGNORECASE)
    
    # Redact potential phone numbers
    message = re.sub(r'\+?\d{10,15}', '***', message)
    
    # Redact potential email addresses
    message = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '***@***.***', message)
    
    # Redact file paths that might contain sensitive info
    message = re.sub(r'(/[^/\s]+){3,}', '/***/', message)
    
    # Redact base64 encoded data (likely images or files)
    message = re.sub(r'data:image/[^;]+;base64,[A-Za-z0-9+/=]{50,}', 'data:image/***;base64,***', message)
    
    return message

class SecurityFilter(logging.Filter):
    """Filter to redact sensitive information from log records"""
    
    def filter(self, record: logging.LogRecord) -> bool:
        # Redact sensitive data from the message
        if hasattr(record, 'msg'):
            record.msg = redact_sensitive_data(str(record.msg))
        
        # Redact sensitive data from args
        if hasattr(record, 'args') and record.args:
            try:
                record.args = tuple(redact_sensitive_data(str(arg)) for arg in record.args)
            except (TypeError, AttributeError):
                pass
        
        return True

class SecurityEventLogger:
    """Logger for security-related events"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    def log_auth_attempt(self, user_id: int, username: str, success: bool):
        """Log authentication attempts"""
        status = "SUCCESS" if success else "FAILED"
        self.logger.warning(f"AUTH_ATTEMPT: User {user_id} (@{username or 'unknown'}) - {status}")
    
    def log_rate_limit(self, user_id: int, endpoint: str):
        """Log rate limiting events"""
        self.logger.warning(f"RATE_LIMIT: User {user_id} exceeded limits for {endpoint}")
    
    def log_file_upload(self, user_id: int, file_type: str, file_size: int):
        """Log file upload events"""
        self.logger.info(f"FILE_UPLOAD: User {user_id} uploaded {file_type} ({file_size} bytes)")
    
    def log_validation_error(self, user_id: int, error_type: str, details: str):
        """Log validation errors"""
        self.logger.warning(f"VALIDATION_ERROR: User {user_id} - {error_type}: {redact_sensitive_data(details)}")
    
    def log_api_error(self, service: str, error_code: int, user_id: int = None):
        """Log external API errors"""
        user_info = f" for user {user_id}" if user_id else ""
        self.logger.error(f"API_ERROR: {service} returned {error_code}{user_info}")

def setup_logging():
    """Configure the logging system for the application with enhanced security"""
    # Get log level from environment, default to INFO for production
    log_level_str = os.getenv('LOG_LEVEL', 'DEBUG').upper()
    log_level = getattr(logging, log_level_str, logging.DEBUG)
    
    # Create logger
    logger = logging.getLogger('expenses_bot')
    logger.setLevel(log_level)

    # Create console handler and set level
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # Add security filter to redact sensitive information
    security_filter = SecurityFilter()
    console_handler.addFilter(security_filter)

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Add formatter to console handler
    console_handler.setFormatter(formatter)

    # Add console handler to logger
    logger.addHandler(console_handler)

    # Prevent duplicate logs
    logger.propagate = False

    return logger

# Create and configure the logger
logger = setup_logging()

# Create security event logger instance
security_logger = SecurityEventLogger(logger)