# Expenses Bot Tests

This directory contains all test-related code for the Expenses Bot project.

## Structure

```
tests/
├── conftest.py              # Pytest configuration and shared fixtures
├── pytest.ini              # Pytest configuration file
├── requirements-test.txt    # Test-specific dependencies
├── run_tests.py            # Advanced test runner with options
├── interfaces.py           # Abstract interfaces for dependency injection
├── services.py             # Concrete service implementations
├── mocks.py                # Mock implementations for testing
├── test_expense_tracking.py  # Tests for expense tracking functionality
├── test_receipt_processing.py # Tests for receipt processing
├── test_user_management.py   # Tests for user management and auth
├── integration_example.py   # Example of integrating DI into main app
├── test.py                 # Legacy test file
├── TESTING.md              # Detailed testing documentation
└── TEST_RESULTS.md         # Test results and architecture summary
```

## Running Tests

### From Project Root
```bash
# Simple test run
python run_tests.py

# Using pytest directly
python -m pytest tests/

# With coverage
python -m pytest tests/ --cov=. --cov-report=html
```

### From Tests Directory
```bash
cd tests
python run_tests.py    # Advanced runner with options
python -m pytest .     # Direct pytest
```

## Test Categories

### 📊 Expense Tracking (29 tests)
- User expense retrieval and filtering
- Expense deletion and management
- Monthly summaries and analytics
- Receipt validation rules
- Multi-user data isolation

### 📝 Receipt Processing (22 tests)
- Image receipt processing with AI
- Voice message transcription and parsing
- Text-based receipt entry
- Receipt updates with user comments
- Database persistence workflows

### 👥 User Management (20 tests)
- User authorization flows
- Session management and authentication
- Database user operations
- Rate limiting and security
- Admin user handling

## Architecture

### Dependency Injection System
- **interfaces.py**: Abstract interfaces for all services
- **services.py**: Production implementations
- **mocks.py**: Test implementations with controlled behavior

### Testing Philosophy
- **Application-level testing**: Focus on business logic rather than unit tests
- **External dependency mocking**: All external services (DB, AI, File, Security) are mocked
- **Isolated test runs**: Tests can run without external dependencies
- **Comprehensive workflows**: End-to-end business process testing

## Key Features

✅ **Complete Isolation**: Tests run without requiring:
- Database connections
- AI service credentials  
- File system permissions
- Network access

✅ **Fast Execution**: All 71 tests run in under 1 second

✅ **Comprehensive Coverage**: All major business flows tested

✅ **Easy Maintenance**: Clear separation between production and test code

## Development Workflow

1. **Add new feature**: Implement in production services
2. **Add test behavior**: Update mock services as needed
3. **Write tests**: Create comprehensive test scenarios
4. **Run tests**: Verify all functionality works
5. **Deploy**: Confident deployment with test coverage

## Dependencies

Test-specific dependencies are in `requirements-test.txt`:
- pytest (test framework)
- pytest-cov (coverage reporting)
- pytest-asyncio (async test support)
- pytest-mock (mocking utilities)
- pytest-xdist (parallel test execution)

## Integration

See `integration_example.py` for examples of how to integrate the dependency injection system into the main application with minimal changes.