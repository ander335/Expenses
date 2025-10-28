"""
logger_config.py
Configures logging for the application
"""

import logging
import sys
import re

def redact_sensitive_data(message):
    """Redact sensitive information like API keys from error messages"""
    # Redact API keys - matches key=<any characters> pattern
    message = re.sub(r'[?&]key=[^& ]+', '?key=***', message)
    return message

def setup_logging():
    """Configure the logging system for the application"""
    # Create logger
    logger = logging.getLogger('expenses_bot')
    logger.setLevel(logging.DEBUG)

    # Create console handler and set level to debug
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Add formatter to console handler
    console_handler.setFormatter(formatter)

    # Add console handler to logger
    logger.addHandler(console_handler)

    return logger

# Create and configure the logger
logger = setup_logging()