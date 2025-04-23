"""Pytest configuration and shared fixtures for the healthcare scheduling API."""

import asyncio
import os
import tempfile
import uuid
from datetime import datetime, timedelta, UTC
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.db.base import get_db
from app.db.models import Base
from app.db.models import DoctorProfile, User, UserRole, Availability, Appointment, AppointmentStatus
from app.main import app


# Test database configuration
TEST_DATABASE_URL = "sqlite:///./test_healthcare.db"
TEST_ENGINE = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
def temp_db() -> Generator[Session, None, None]:
    """Create a temporary database for each test function."""
    # Create all tables
    Base.metadata.create_all(bind=TEST_ENGINE)
    
    # Create a database session
    db = TestingSessionLocal()
    
    try:
        yield db
    finally:
        db.close()
        # Drop all tables after test
        Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture(scope="function")
def monkeypatch_db(monkeypatch, temp_db):
    """Monkeypatch the database session to use test database."""
    def override_get_db():
        try:
            yield temp_db
        finally:
            pass
    
    monkeypatch.setattr("app.db.base.get_db", override_get_db)
    monkeypatch.setattr("app.core.config.settings.database_url", TEST_DATABASE_URL)
    return override_get_db


@pytest.fixture
def test_client(monkeypatch_db) -> TestClient:
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
async def async_client(monkeypatch_db) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client for the FastAPI app."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver"
    ) as client:
        yield client


@pytest.fixture
def admin_user(temp_db: Session) -> User:
    """Create an admin user for testing."""
    user = User(
        id=uuid.uuid4(),
        email="admin@test.com",
        hashed_password=get_password_hash("admin123"),
        full_name="Test Admin",
        role=UserRole.ADMIN,
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC)
    )
    temp_db.add(user)
    temp_db.commit()
    temp_db.refresh(user)
    return user


@pytest.fixture
def doctor_user(temp_db: Session) -> User:
    """Create a doctor user for testing."""
    user = User(
        id=uuid.uuid4(),
        email="doctor@test.com",
        hashed_password=get_password_hash("doctor123"),
        full_name="Dr. Test Doctor",
        role=UserRole.DOCTOR,
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC)
    )
    temp_db.add(user)
    temp_db.commit()
    temp_db.refresh(user)
    return user


@pytest.fixture
def patient_user(temp_db: Session) -> User:
    """Create a patient user for testing."""
    user = User(
        id=uuid.uuid4(),
        email="patient@test.com",
        hashed_password=get_password_hash("patient123"),
        full_name="Test Patient",
        role=UserRole.PATIENT,
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC)
    )
    temp_db.add(user)
    temp_db.commit()
    temp_db.refresh(user)
    return user


@pytest.fixture
def doctor_profile(temp_db: Session, doctor_user: User) -> DoctorProfile:
    """Create a doctor profile for testing."""
    profile = DoctorProfile(
        id=uuid.uuid4(),
        user_id=doctor_user.id,
        specialization="Cardiology",
        timezone="America/New_York",
        created_at=datetime.now(UTC)
    )
    temp_db.add(profile)
    temp_db.commit()
    temp_db.refresh(profile)
    return profile


@pytest.fixture
def auth_headers_admin(admin_user: User) -> dict:
    """Create authentication headers for admin user."""
    token = create_access_token(data={"sub": str(admin_user.id), "email": admin_user.email, "role": admin_user.role.value})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_doctor(doctor_user: User) -> dict:
    """Create authentication headers for doctor user."""
    token = create_access_token(data={"sub": str(doctor_user.id), "email": doctor_user.email, "role": doctor_user.role.value})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_patient(patient_user: User) -> dict:
    """Create authentication headers for patient user."""
    token = create_access_token(data={"sub": str(patient_user.id), "email": patient_user.email, "role": patient_user.role.value})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_availability(temp_db: Session, doctor_profile: DoctorProfile) -> Availability:
    """Create sample availability for testing."""
    start_time = datetime.now(UTC) + timedelta(days=1)
    end_time = start_time + timedelta(hours=2)
    
    availability = Availability(
        id=uuid.uuid4(),
        doctor_id=doctor_profile.id,
        start_time=start_time,
        end_time=end_time,
        created_at=datetime.now(UTC)
    )
    temp_db.add(availability)
    temp_db.commit()
    temp_db.refresh(availability)
    return availability


@pytest.fixture
def sample_appointment(temp_db: Session, doctor_profile: DoctorProfile, patient_user: User) -> Appointment:
    """Create sample appointment for testing."""
    start_time = datetime.now(UTC) + timedelta(days=1, hours=1)
    end_time = start_time + timedelta(minutes=30)
    
    appointment = Appointment(
        id=uuid.uuid4(),
        doctor_id=doctor_profile.id,
        patient_id=patient_user.id,
        start_time=start_time,
        end_time=end_time,
        status=AppointmentStatus.SCHEDULED,
        notes="Test appointment",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC)
    )
    temp_db.add(appointment)
    temp_db.commit()
    temp_db.refresh(appointment)
    return appointment


@pytest.fixture
def redis_available() -> bool:
    """Check if Redis is available for testing."""
    try:
        import redis
        r = redis.from_url(settings.redis_url)
        r.ping()
        return True
    except Exception:
        return False


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing when Redis is not available."""
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True
    mock_redis.get.return_value = None
    mock_redis.set.return_value = True
    mock_redis.delete.return_value = 1
    mock_redis.zadd.return_value = 1
    mock_redis.zcard.return_value = 0
    mock_redis.zremrangebyscore.return_value = 0
    mock_redis.expire.return_value = True
    mock_redis.pipeline.return_value.__enter__.return_value = mock_redis
    mock_redis.pipeline.return_value.__exit__.return_value = None
    return mock_redis


def skip_if_no_redis(redis_available: bool):
    """Skip test if Redis is not available."""
    if not redis_available:
        pytest.skip("Redis not available")


# Test markers
pytest_plugins = ["pytest_asyncio"]


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "slow: Slow tests")
    config.addinivalue_line("markers", "redis: Tests requiring Redis")
    config.addinivalue_line("markers", "auth: Authentication tests")
    config.addinivalue_line("markers", "appointments: Appointment tests")
    config.addinivalue_line("markers", "availability: Availability tests")
