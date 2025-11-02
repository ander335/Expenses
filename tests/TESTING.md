# Application-Level Testing for Expenses Bot

This document explains the comprehensive testing framework implemented for the Expenses Bot using dependency injection and mocking to achieve high test coverage without external dependencies.

## Overview

The testing system provides:
- **Application-level testing** of all business logic
- **Complete mocking** of external services (Database, Gemini API, Telegram API, File System)
- **Dependency injection** for easy test configuration
- **High test coverage** without calling real external APIs
- **Fast test execution** suitable for CI/CD pipelines

## Architecture

### Dependency Injection System

The system uses abstract interfaces to decouple business logic from external dependencies:

```
interfaces.py      - Abstract interfaces for all services
services.py        - Production implementations wrapping existing code  
mocks.py          - Mock implementations for testing
```

### Key Interfaces

- `IDatabaseService` - Database operations (users, receipts, summaries)
- `IAIService` - AI operations (Gemini API for receipt parsing, voice transcription)
- `IFileService` - File operations (temp files, validation, cleanup)
- `ISecurityService` - Security operations (rate limiting, sessions)
- `IExpensesService` - Main business logic (receipt processing workflows)

## File Structure

```
tests/
├── conftest.py                    # Pytest configuration and fixtures
├── test_receipt_processing.py     # Receipt processing business logic tests
├── test_user_management.py        # User authorization and management tests  
├── test_expense_tracking.py       # Expense tracking and reporting tests
└── test_integration.py           # End-to-end integration tests

interfaces.py                      # Abstract service interfaces
services.py                        # Production service implementations
mocks.py                          # Mock service implementations for testing
requirements-test.txt              # Test-specific dependencies
pytest.ini                        # Pytest configuration
run_tests.py                      # Test runner script
integration_example.py            # Example of integrating DI into existing code
```

## Running Tests

### Quick Start

1. **Install test dependencies:**
   ```bash
   pip install -r requirements-test.txt
   ```

2. **Run all tests:**
   ```bash
   python run_tests.py
   ```

3. **Run specific test categories:**
   ```bash
   # Unit tests only
   pytest tests/ -m "not integration" -v
   
   # Integration tests only  
   pytest tests/ -m integration -v
   
   # With coverage report
   pytest tests/ --cov=. --cov-report=html
   ```

### Interactive Test Runner

The `run_tests.py` script provides an interactive menu:

```bash
python run_tests.py

Available test options:
1. Unit Tests
2. Integration Tests
3. All Tests  
4. All Tests with Coverage

Select test option (1-4) or press Enter for all tests:
```

### Running Specific Tests

```bash
# Run specific test file
pytest tests/test_receipt_processing.py -v

# Run specific test class
pytest tests/test_receipt_processing.py::TestReceiptImageProcessing -v

# Run specific test method
pytest tests/test_receipt_processing.py::TestReceiptImageProcessing::test_process_receipt_image_success -v

# Run with the test runner
python run_tests.py --specific
```

## Test Categories

### 1. Receipt Processing Tests (`test_receipt_processing.py`)

Tests all receipt processing workflows:

- **Image Processing**: Photo receipt analysis with Gemini AI
- **Voice Processing**: Voice message transcription and receipt creation  
- **Text Processing**: Text description to receipt conversion
- **Receipt Updates**: User feedback and correction handling
- **Receipt Saving**: Database persistence with positions

**Key Test Scenarios:**
- Successful processing with various input types
- File validation (size, type, security)
- AI service failures and error handling
- User comment integration and receipt updates
- End-to-end workflows from input to database

### 2. User Management Tests (`test_user_management.py`)

Tests user authorization and access control:

- **Authorization Logic**: Admin vs regular user permissions
- **User Registration**: New user approval workflow
- **Session Management**: Session creation, validation, authentication
- **Rate Limiting**: Request throttling and abuse prevention

**Key Test Scenarios:**
- Admin user automatic authorization
- New user approval request flow
- Authorized user session management
- Rate limiting enforcement per user
- Database user operations (create, update, authorize)

### 3. Expense Tracking Tests (`test_expense_tracking.py`)

Tests expense management and reporting:

- **Expense Retrieval**: User-specific expense lists
- **Expense Deletion**: Secure deletion with ownership validation
- **Monthly Summaries**: Expense reporting and aggregation
- **Data Validation**: Amount, category, date validation

**Key Test Scenarios:**
- User isolation (users only see their own data)
- Expense pagination and limiting
- Monthly summary generation with date parsing
- Multi-user data isolation
- Complete expense lifecycle (create, read, update, delete)

### 4. Integration Tests

End-to-end workflow testing:

- **Complete Workflows**: Full receipt processing pipelines
- **Multi-User Scenarios**: Concurrent user operations
- **Error Recovery**: Handling of partial failures
- **Service Integration**: All services working together

## Mock Services

### MockDatabaseService

Provides in-memory database simulation:

```python
# Tracks users, receipts, and relationships
# Supports all database operations without SQLAlchemy
# Includes helper methods for test setup and verification

mock_db = MockDatabaseService()
mock_db.create_user_if_missing(user_id, name, is_authorized=True)
receipt_id = mock_db.add_receipt(receipt)
receipts = mock_db.get_last_n_receipts(user_id, 5)
```

### MockAIService

Simulates Gemini AI responses:

```python
# Configurable responses for different scenarios
# Call tracking for verification
# Failure mode simulation

mock_ai = MockAIService()
mock_ai.set_custom_response("image_path.jpg", custom_receipt_data)
mock_ai.set_failure_mode(True, "AI service unavailable")
call_count = mock_ai.get_call_count('parse_image')
```

### MockFileService

Handles temporary file operations:

```python
# Real temp file creation for realistic testing
# Validation simulation with configurable failures
# Automatic cleanup

mock_file = MockFileService()
temp_path = mock_file.create_secure_temp_file('.jpg')
mock_file.set_validation_failure(True, "File too large")
mock_file.validate_file_size(temp_path)
```

### MockSecurityService

Simulates security operations:

```python
# Rate limiting with configurable thresholds
# Session management
# Call tracking

mock_security = MockSecurityService()
mock_security.set_rate_limit_config(max_requests=5, window_seconds=30)
mock_security.trigger_rate_limit(user_id)  # Force rate limit for testing
```

## Test Fixtures

### Data Fixtures

Pre-configured test data:

```python
@pytest.fixture
def sample_user_data():
    return {
        'user_id': 98336105,
        'name': 'Test User', 
        'is_authorized': True
    }

@pytest.fixture  
def sample_receipt_data():
    return {
        'merchant': 'Test Store',
        'total_amount': 25.50,
        'positions': [...]
    }
```

### Service Fixtures

Pre-configured service instances:

```python
@pytest.fixture
def expenses_service(mock_db_service, mock_ai_service, mock_file_service, mock_security_service):
    return ExpensesService(mock_db_service, mock_ai_service, mock_file_service, mock_security_service, admin_user_id=12345)
```

### File Fixtures

Temporary test files:

```python
@pytest.fixture
def temp_image_file():
    # Creates realistic JPEG file with proper headers
    
@pytest.fixture
def temp_voice_file():
    # Creates realistic OGG file with proper headers
```

### Scenario Fixtures

Pre-populated test scenarios:

```python
@pytest.fixture
def populated_database(mock_db_service):
    # Creates users and receipts for testing
    
@pytest.fixture
def rate_limited_user(mock_security_service):
    # Creates user who has hit rate limit
```

## Coverage and Quality

### Coverage Targets

- **Overall Coverage**: 80%+ required
- **Business Logic**: 95%+ coverage for core services
- **External Dependencies**: 100% mocked, no real API calls

### Quality Checks

```bash
# Run with coverage
pytest tests/ --cov=. --cov-report=html --cov-fail-under=80

# Generate detailed coverage report
coverage html
open htmlcov/index.html
```

### Test Markers

- `@pytest.mark.unit` - Fast unit tests
- `@pytest.mark.integration` - Slower integration tests  
- `@pytest.mark.slow` - Very slow tests (optional)

## Integrating with Existing Code

### Minimal Integration Approach

1. **Add service imports to expenses.py:**
   ```python
   from services import ExpensesApp
   app = ExpensesApp()
   expenses_service = app.get_expenses_service()
   ```

2. **Replace direct API calls:**
   ```python
   # Before:
   gemini_output = parse_receipt_image(image_path, user_comment)
   
   # After:
   parsed_receipt = expenses_service.process_receipt_image(user_id, image_path, user_comment)
   ```

3. **Use service methods in handlers:**
   ```python
   async def handle_photo(update, context):
       is_authorized, message = expenses_service.check_user_authorization(user.id, user.full_name)
       if not is_authorized:
           await update.message.reply_text(message)
           return
       # ... rest of handler
   ```

### Gradual Migration

You can migrate handlers one by one:

1. Start with critical business logic handlers
2. Test each migrated handler thoroughly  
3. Keep existing handlers working during migration
4. Complete migration over time

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Test Suite
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - uses: actions/setup-python@v4
      with:
        python-version: '3.12'
    - run: pip install -r requirements.txt -r requirements-test.txt
    - run: pytest tests/ --cov=. --cov-report=xml
    - uses: codecov/codecov-action@v3
```

### Local Pre-commit Hook

```bash
#!/bin/sh
# .git/hooks/pre-commit
python run_tests.py --unit-only
if [ $? -ne 0 ]; then
    echo "Tests failed. Commit aborted."
    exit 1
fi
```

## Benefits

### For Development

- **Fast Feedback**: Tests run in seconds, not minutes
- **Reliable**: No flaky network or API dependencies
- **Isolated**: Each test is independent and deterministic
- **Comprehensive**: Test edge cases and error conditions easily

### For Maintenance

- **Refactoring Safety**: Change internal code with confidence
- **Documentation**: Tests serve as executable documentation
- **Regression Prevention**: Catch bugs before deployment
- **Quality Assurance**: Enforce coding standards and practices

### For Team Collaboration

- **Clear Contracts**: Interfaces define clear service contracts
- **Easy Onboarding**: New developers can run tests immediately  
- **Code Reviews**: Test changes are easily reviewable
- **Parallel Development**: Multiple developers can work on different services

## Best Practices

### Writing Tests

1. **Test Behavior, Not Implementation**: Focus on what the service does, not how
2. **Use Descriptive Names**: Test names should explain the scenario
3. **One Assertion Per Test**: Keep tests focused and specific
4. **Test Edge Cases**: Include error conditions and boundary values
5. **Use Fixtures**: Reuse common test setup code

### Maintaining Tests

1. **Keep Tests Simple**: Avoid complex logic in tests
2. **Update Tests with Code**: Keep tests in sync with implementation
3. **Remove Obsolete Tests**: Delete tests for removed functionality
4. **Review Test Coverage**: Regularly check coverage reports
5. **Optimize Slow Tests**: Keep test suite fast and efficient

## Future Enhancements

### Planned Improvements

1. **Performance Testing**: Add load testing for concurrent users
2. **Security Testing**: Add security-focused test scenarios
3. **Database Testing**: Add tests for database migrations and schema changes
4. **API Testing**: Add tests for Telegram webhook endpoints
5. **Error Monitoring**: Integration with error tracking services

### Advanced Features

1. **Property-Based Testing**: Use Hypothesis for generating test cases
2. **Mutation Testing**: Use mutmut to test the quality of tests
3. **Contract Testing**: Add Pact testing for external API contracts
4. **Visual Testing**: Add screenshot testing for error messages
5. **Chaos Engineering**: Add random failure injection for resilience testing

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure all dependencies are installed
2. **File Permission Errors**: Check temp directory permissions
3. **Coverage Too Low**: Add tests for uncovered code paths
4. **Slow Tests**: Check for real API calls or file I/O in tests
5. **Flaky Tests**: Look for time-dependent or order-dependent code

### Debug Mode

```bash
# Run with debug output
pytest tests/ -v -s --tb=long

# Run single test with debugging
pytest tests/test_receipt_processing.py::test_specific -v -s --pdb
```

This testing framework provides a solid foundation for maintaining and improving the Expenses Bot with confidence, ensuring that all business logic is thoroughly tested without depending on external services.