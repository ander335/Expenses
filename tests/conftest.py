"""
Test configuration and fixtures for the Expenses Bot.
"""

import pytest
import tempfile
import os
from datetime import datetime
from typing import Generator
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from interfaces import IDatabaseService, IAIService, IFileService, ISecurityService, IExpensesService
from mocks import MockDatabaseService, MockAIService, MockFileService, MockSecurityService
from services import ExpensesService
from db import Receipt, Position


# =============================================================================
# PYTEST CONFIGURATION
# =============================================================================

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow running"
    )


# =============================================================================
# SERVICE FIXTURES
# =============================================================================

@pytest.fixture
def mock_db_service() -> Generator[MockDatabaseService, None, None]:
    """Provide a fresh mock database service for each test."""
    service = MockDatabaseService()
    yield service
    service.clear_all_data()


@pytest.fixture
def mock_ai_service() -> Generator[MockAIService, None, None]:
    """Provide a fresh mock AI service for each test."""
    service = MockAIService()
    yield service
    service.clear_call_history()


@pytest.fixture
def mock_file_service() -> Generator[MockFileService, None, None]:
    """Provide a fresh mock file service for each test."""
    service = MockFileService()
    yield service
    service.cleanup_all_temp_files()
    service.clear_call_history()


@pytest.fixture
def mock_security_service() -> Generator[MockSecurityService, None, None]:
    """Provide a fresh mock security service for each test."""
    service = MockSecurityService()
    yield service
    service.clear_all_sessions()
    service.clear_call_history()


@pytest.fixture
def expenses_service(mock_db_service, mock_ai_service, mock_file_service, mock_security_service) -> ExpensesService:
    """Provide a fully configured expenses service with all mocks."""
    return ExpensesService(
        db_service=mock_db_service,
        ai_service=mock_ai_service,
        file_service=mock_file_service,
        security_service=mock_security_service,
        admin_user_id=12345  # Test admin ID
    )


# =============================================================================
# DATA FIXTURES
# =============================================================================

@pytest.fixture
def sample_user_data():
    """Provide sample user data for testing."""
    return {
        'user_id': 98336105,
        'name': 'Test User',
        'is_authorized': True,
        'approval_requested': False
    }


@pytest.fixture
def sample_admin_user_data():
    """Provide sample admin user data for testing."""
    return {
        'user_id': 12345,  # Matches admin_user_id in expenses_service fixture
        'name': 'Admin User',
        'is_authorized': True,
        'approval_requested': False
    }


@pytest.fixture
def sample_unauthorized_user_data():
    """Provide sample unauthorized user data for testing."""
    return {
        'user_id': 67890,
        'name': 'Unauthorized User',
        'is_authorized': False,
        'approval_requested': True
    }


@pytest.fixture
def sample_receipt_data():
    """Provide sample receipt data for testing."""
    return {
        'merchant': 'Test Store',
        'category': 'food',
        'total_amount': 25.50,
        'date': '15-01-2024',
        'text': 'Complete receipt text content',
        'description': 'Groceries and household items',
        'positions': [
            {
                'description': 'Milk 1L',
                'quantity': '1',
                'category': 'food',
                'price': 2.50
            },
            {
                'description': 'Bread',
                'quantity': '2',
                'category': 'food', 
                'price': 3.00
            },
            {
                'description': 'Cleaning supplies',
                'quantity': '1',
                'category': 'household',
                'price': 20.00
            }
        ]
    }


@pytest.fixture
def sample_receipt_json(sample_receipt_data):
    """Provide sample receipt data as JSON string."""
    import json
    return json.dumps(sample_receipt_data)


@pytest.fixture
def sample_receipt_object(sample_user_data, sample_receipt_data):
    """Provide a sample Receipt object for testing."""
    positions = [
        Position(
            description=pos['description'],
            quantity=pos['quantity'],
            category=pos['category'],
            price=pos['price']
        )
        for pos in sample_receipt_data['positions']
    ]
    
    return Receipt(
        user_id=sample_user_data['user_id'],
        merchant=sample_receipt_data['merchant'],
        category=sample_receipt_data['category'],
        total_amount=sample_receipt_data['total_amount'],
        date=sample_receipt_data['date'],
        text=sample_receipt_data['text'],
        description=sample_receipt_data['description'],
        positions=positions
    )


# =============================================================================
# FILE FIXTURES
# =============================================================================

@pytest.fixture
def temp_image_file() -> Generator[str, None, None]:
    """Create a temporary image file for testing."""
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
        # Write some dummy image data
        f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF')  # JPEG header
        f.write(b'\x00' * 100)  # Dummy content
        temp_path = f.name
    
    yield temp_path
    
    try:
        os.unlink(temp_path)
    except FileNotFoundError:
        pass


@pytest.fixture
def temp_voice_file() -> Generator[str, None, None]:
    """Create a temporary voice file for testing."""
    with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as f:
        # Write OGG header
        f.write(b'OggS\x00\x02\x00\x00')  # OGG header
        f.write(b'\x00' * 100)  # Dummy content
        temp_path = f.name
    
    yield temp_path
    
    try:
        os.unlink(temp_path)
    except FileNotFoundError:
        pass


@pytest.fixture
def invalid_file() -> Generator[str, None, None]:
    """Create a temporary invalid file for testing."""
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
        f.write(b'This is not an image or audio file')
        temp_path = f.name
    
    yield temp_path
    
    try:
        os.unlink(temp_path)
    except FileNotFoundError:
        pass


# =============================================================================
# SCENARIO FIXTURES
# =============================================================================

@pytest.fixture
def populated_database(mock_db_service, sample_user_data, sample_receipt_object):
    """Provide a database with some test data already populated."""
    # Create test user
    mock_db_service.create_user_if_missing(
        sample_user_data['user_id'],
        sample_user_data['name'],
        is_authorized=sample_user_data['is_authorized'],
        approval_requested=sample_user_data['approval_requested']
    )
    
    # Add some receipts
    for i in range(5):
        receipt = Receipt(
            user_id=sample_user_data['user_id'],
            merchant=f"Store {i+1}",
            category='food' if i % 2 == 0 else 'transport',
            total_amount=10.0 + (i * 5),
            date=f"{15+i:02d}-01-2024",
            text=f"Receipt text {i+1}",
            description=f"Test receipt {i+1}",
            positions=[
                Position(
                    description=f"Item {i+1}",
                    quantity="1",
                    category='food' if i % 2 == 0 else 'transport',
                    price=10.0 + (i * 5)
                )
            ]
        )
        mock_db_service.add_receipt(receipt)
    
    return mock_db_service


@pytest.fixture
def rate_limited_user(mock_security_service):
    """Provide a user who has hit the rate limit."""
    user_id = 99999
    mock_security_service.trigger_rate_limit(user_id)
    return user_id


# =============================================================================
# TEST HELPER FIXTURES
# =============================================================================

@pytest.fixture
def assert_logged():
    """Helper to assert that certain log messages were generated."""
    # This would integrate with the logging system to capture and verify logs
    # For now, it's a placeholder that could be extended
    def _assert_logged(level, message_pattern):
        # Implementation would capture logs and verify patterns
        pass
    
    return _assert_logged


@pytest.fixture
def test_config():
    """Provide test configuration constants."""
    return {
        'admin_user_id': 12345,
        'max_file_size': 10 * 1024 * 1024,  # 10MB
        'rate_limit_requests': 10,
        'rate_limit_window': 60,
        'allowed_image_types': {'image/jpeg', 'image/png', 'image/gif', 'image/webp'},
        'allowed_audio_types': {'audio/ogg', 'audio/mpeg', 'audio/wav', 'audio/m4a'},
    }


# =============================================================================
# PARAMETRIZED TEST DATA
# =============================================================================

@pytest.fixture(params=[
    'food', 'transport', 'clothes', 'healthcare', 'beauty', 'household', 'car', 'cat', 'other'
])
def all_categories(request):
    """Parametrize tests across all valid categories."""
    return request.param


@pytest.fixture(params=[
    ('01-01-2024', True),
    ('31-12-2023', True), 
    ('29-02-2024', True),  # Leap year
    ('invalid-date', False),
    ('2024-01-01', False),  # Wrong format
    ('1-1-24', False),      # Wrong format
    (None, True),           # Null dates are allowed
])
def date_validation_cases(request):
    """Parametrize tests for date validation."""
    return request.param


@pytest.fixture(params=[
    (1.00, True),
    (0.01, True),
    (999999.99, True),
    (0.00, True),
    (-1.00, False),
    ('not_a_number', False),
    (None, False),
])
def amount_validation_cases(request):
    """Parametrize tests for amount validation."""
    return request.param