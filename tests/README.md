# Healthcare Scheduling API - Test Suite

This directory contains a comprehensive test suite for the Healthcare Scheduling API, organized into unit tests, integration tests, and end-to-end tests.

## Test Structure

```
tests/
├── conftest.py                 # Pytest configuration and shared fixtures
├── README.md                   # This file
├── unit/                       # Unit tests
│   ├── services/              # Service layer tests
│   │   ├── test_appointments.py
│   │   └── test_availability.py
│   ├── models/                # Database model tests
│   ├── utils/                 # Utility function tests
│   └── core/                  # Core module tests
│       └── test_security.py
├── integration/               # Integration tests
│   ├── api/                   # API endpoint tests
│   │   ├── test_auth.py
│   │   └── test_appointments.py
│   ├── database/              # Database integration tests
│   └── redis/                 # Redis integration tests
├── e2e/                       # End-to-end tests
│   └── test_complete_workflows.py
├── fixtures/                  # Test data fixtures
└── utils/                     # Test utilities
    ├── test_data.py           # Test data factories
    └── assertions.py          # Custom assertion helpers
```

## Test Categories

### Unit Tests (`pytest -m unit`)
- **Services**: Test business logic in isolation
- **Models**: Test database models and relationships
- **Core**: Test core functionality (security, config, etc.)
- **Utils**: Test utility functions

### Integration Tests (`pytest -m integration`)
- **API**: Test API endpoints with real HTTP requests
- **Database**: Test database operations and migrations
- **Redis**: Test Redis caching and rate limiting

### End-to-End Tests (`pytest -m e2e`)
- **Complete Workflows**: Test full user journeys
- **System Integration**: Test all components working together
- **Performance**: Test system under load

## Test Markers

The test suite uses pytest markers to categorize tests:

- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.e2e` - End-to-end tests
- `@pytest.mark.slow` - Slow tests (>1 second)
- `@pytest.mark.redis` - Tests requiring Redis
- `@pytest.mark.auth` - Authentication tests
- `@pytest.mark.appointments` - Appointment-related tests
- `@pytest.mark.availability` - Availability-related tests

## Running Tests

### Basic Commands

```bash
# Run all tests
make test

# Run with verbose output
make test-verbose

# Run with coverage
make test-coverage

# Run specific test categories
make test-unit
make test-integration
make test-e2e

# Run specific test types
make test-auth
make test-appointments
make test-availability

# Run fast tests only (exclude slow tests)
make test-fast

# Run slow tests only
make test-slow
```

### Advanced Commands

```bash
# Run tests in parallel
pytest -n auto

# Run specific test file
pytest tests/unit/services/test_appointments.py

# Run specific test function
pytest tests/unit/services/test_appointments.py::TestAppointmentService::test_book_appointment_success

# Run tests with specific marker
pytest -m "auth and not slow"

# Run tests with coverage and HTML report
pytest --cov=app --cov-report=html

# Run tests with XML coverage report (for CI)
pytest --cov=app --cov-report=xml
```

### Docker Testing

```bash
# Run tests in Docker
make docker-test

# Run tests with verbose output in Docker
make docker-test-verbose

# Run specific test categories in Docker
docker compose exec api pytest -m unit -v
docker compose exec api pytest -m integration -v
```

## Test Configuration

### Pytest Configuration (`pytest.ini`)

- **Async Mode**: Automatically handles async tests
- **Coverage**: Configured for 80% minimum coverage
- **Markers**: Custom markers for test categorization
- **Output**: Verbose output with short tracebacks
- **Warnings**: Filtered to reduce noise

### Test Database

- **SQLite**: Used for fast unit tests
- **PostgreSQL**: Used for integration and e2e tests
- **Isolation**: Each test gets a clean database
- **Fixtures**: Automatic setup and teardown

### Test Data

- **Factories**: `TestDataFactory` for creating test data
- **Samples**: `SampleData` for predefined test data
- **Scenarios**: `TestScenarios` for edge cases
- **Assertions**: `TestAssertions` for custom assertions

## Test Fixtures

### Database Fixtures

- `temp_db`: Temporary SQLite database for each test
- `monkeypatch_db`: Monkeypatch database session
- `test_client`: FastAPI test client
- `async_client`: Async test client

### User Fixtures

- `admin_user`: Admin user for testing
- `doctor_user`: Doctor user for testing
- `patient_user`: Patient user for testing
- `doctor_profile`: Doctor profile for testing

### Authentication Fixtures

- `auth_headers_admin`: Admin authentication headers
- `auth_headers_doctor`: Doctor authentication headers
- `auth_headers_patient`: Patient authentication headers

### Data Fixtures

- `sample_availability`: Sample availability slot
- `sample_appointment`: Sample appointment
- `redis_available`: Check if Redis is available
- `mock_redis`: Mock Redis client

## Writing Tests

### Unit Test Example

```python
@pytest.mark.unit
class TestAppointmentService:
    def test_book_appointment_success(self, temp_db, doctor_profile, patient_user):
        """Test successful appointment booking."""
        service = AppointmentService(temp_db)
        
        start_time = datetime.now(UTC) + timedelta(days=1, hours=10)
        end_time = start_time + timedelta(minutes=30)
        
        appointment = service.book_appointment(
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            start_time=start_time,
            end_time=end_time,
            notes="Test appointment"
        )
        
        assert appointment is not None
        assert appointment.patient_id == patient_user.id
        assert appointment.doctor_id == doctor_profile.id
```

### Integration Test Example

```python
@pytest.mark.integration
@pytest.mark.auth
class TestAuthEndpoints:
    def test_login_success(self, test_client, admin_user):
        """Test successful login with valid credentials."""
        login_data = SampleData.ADMIN_USER
        
        response = test_client.post(
            "/api/v1/auth/token",
            data=login_data
        )
        
        TestAssertions.assert_success_response(response, status.HTTP_200_OK)
        
        response_data = response.json()
        TestAssertions.assert_token_response(response_data)
```

### End-to-End Test Example

```python
@pytest.mark.e2e
@pytest.mark.slow
class TestCompleteWorkflows:
    def test_admin_workflow(self, test_client, auth_headers_admin):
        """Test complete admin workflow: create users, manage system."""
        # 1. Create a doctor user
        doctor_data = TestDataFactory.create_user_data(
            email="newdoctor@healthcare.com",
            full_name="Dr. New Doctor",
            role="doctor"
        )
        
        create_doctor_response = test_client.post(
            "/api/v1/auth/signup",
            json=doctor_data,
            headers=auth_headers_admin
        )
        
        TestAssertions.assert_success_response(create_doctor_response, status.HTTP_201_CREATED)
```

## Test Data Management

### Using Test Data Factories

```python
# Create user data
user_data = TestDataFactory.create_user_data(
    email="test@example.com",
    full_name="Test User",
    role="patient"
)

# Create appointment data
appointment_data = TestDataFactory.create_appointment_data(
    doctor_id=str(doctor_profile.id),
    days_ahead=1
)

# Create availability data
availability_data = TestDataFactory.create_availability_data(
    start_time=datetime.now(UTC) + timedelta(days=1, hours=9),
    end_time=datetime.now(UTC) + timedelta(days=1, hours=12)
)
```

### Using Sample Data

```python
# Use predefined sample data
login_data = SampleData.ADMIN_USER
appointment_data = SampleData.REGULAR_APPOINTMENT
availability_data = SampleData.MORNING_AVAILABILITY
```

### Using Test Scenarios

```python
# Test edge cases
past_time = TestScenarios.PAST_TIME
future_time = TestScenarios.FUTURE_TIME
invalid_emails = TestScenarios.INVALID_EMAILS
```

## Custom Assertions

### Using Test Assertions

```python
# API response assertions
TestAssertions.assert_success_response(response, status.HTTP_200_OK)
TestAssertions.assert_error_response(response, status.HTTP_400_BAD_REQUEST)
TestAssertions.assert_unauthorized(response)
TestAssertions.assert_forbidden(response)

# Data assertions
TestAssertions.assert_user_data(response_data, expected_user)
TestAssertions.assert_appointment_data(response_data, expected_appointment)
TestAssertions.assert_paginated_response(response_data, expected_items=5)

# Format assertions
TestAssertions.assert_uuid_format(response_data["id"], "Appointment ID")
TestAssertions.assert_datetime_format(response_data["start_time"], "Start time")
TestAssertions.assert_time_range_valid(start_time, end_time)
```

## Coverage Reports

### HTML Coverage Report

```bash
make test-coverage
# Opens htmlcov/index.html in browser
```

### XML Coverage Report

```bash
make test-coverage-xml
# Generates coverage.xml for CI
```

### Coverage Thresholds

- **Minimum Coverage**: 80%
- **Unit Tests**: 90%+ expected
- **Integration Tests**: 80%+ expected
- **E2E Tests**: 70%+ expected

## Performance Testing

### Load Testing

```bash
# Install locust
pip install locust

# Run load tests
locust -f tests/performance/locustfile.py --host=http://localhost:8000
```

### Benchmarking

```bash
# Run performance benchmarks
pytest tests/performance/test_benchmarks.py -v
```

## Continuous Integration

### GitHub Actions

The CI pipeline runs:
1. **Lint**: Code formatting and style checks
2. **Type Check**: Type checking with mypy
3. **Unit Tests**: Fast unit tests with coverage
4. **Integration Tests**: API and database tests
5. **E2E Tests**: Complete workflow tests
6. **Docker Build**: Build and test Docker image

### Local CI Testing

```bash
# Run the same checks as CI
make test-ci

# Run all quality checks
make test-all
```

## Debugging Tests

### Verbose Output

```bash
# Run with verbose output
pytest -v -s

# Run specific test with verbose output
pytest tests/unit/services/test_appointments.py::TestAppointmentService::test_book_appointment_success -v -s
```

### Debug Mode

```bash
# Run with debug output
pytest --log-cli-level=DEBUG

# Run with pdb debugger
pytest --pdb
```

### Test Isolation

```bash
# Run tests in isolation
pytest --forked

# Run tests with fresh database
pytest --reuse-db
```

## Best Practices

### Test Organization

1. **One test per scenario**: Each test should verify one specific behavior
2. **Descriptive names**: Test names should clearly describe what is being tested
3. **Arrange-Act-Assert**: Structure tests with clear setup, execution, and verification
4. **Independent tests**: Tests should not depend on each other
5. **Clean up**: Tests should clean up after themselves

### Test Data

1. **Use factories**: Create test data using factories for consistency
2. **Minimal data**: Use only the data necessary for the test
3. **Realistic data**: Use realistic test data that matches production
4. **Edge cases**: Test boundary conditions and error cases

### Assertions

1. **Specific assertions**: Use specific assertions rather than generic ones
2. **Custom assertions**: Use custom assertion helpers for complex checks
3. **Error messages**: Include helpful error messages in assertions
4. **Multiple assertions**: Use multiple assertions to verify different aspects

### Performance

1. **Fast tests**: Keep unit tests fast (< 1 second)
2. **Slow tests**: Mark slow tests with `@pytest.mark.slow`
3. **Parallel execution**: Use `pytest -n auto` for parallel test execution
4. **Test isolation**: Ensure tests don't interfere with each other

## Troubleshooting

### Common Issues

1. **Database errors**: Check that test database is properly configured
2. **Redis errors**: Check that Redis is available or use mocks
3. **Import errors**: Check that all dependencies are installed
4. **Timeout errors**: Increase timeout for slow tests

### Debug Commands

```bash
# Check test discovery
pytest --collect-only

# Check test markers
pytest --markers

# Check test configuration
pytest --config

# Run with maximum verbosity
pytest -vvv
```

## Contributing

### Adding New Tests

1. **Choose the right category**: Unit, integration, or e2e
2. **Use appropriate markers**: Mark tests with relevant markers
3. **Follow naming conventions**: Use descriptive test names
4. **Add documentation**: Include docstrings explaining the test
5. **Update this README**: Document new test patterns or utilities

### Test Review Checklist

- [ ] Test covers the intended functionality
- [ ] Test is independent and can run in isolation
- [ ] Test uses appropriate fixtures and data
- [ ] Test has clear assertions and error messages
- [ ] Test is properly marked and categorized
- [ ] Test follows naming conventions
- [ ] Test includes appropriate documentation
