"""Test data factories and sample data generators."""

import uuid
from datetime import datetime, timedelta, UTC
from typing import Dict, Any

from app.db.models import User, UserRole, DoctorProfile, Availability, Appointment, AppointmentStatus


class TestDataFactory:
    """Factory for creating test data."""
    
    @staticmethod
    def create_user_data(
        email: str = None,
        full_name: str = None,
        role: UserRole = UserRole.PATIENT,
        is_active: bool = True
    ) -> Dict[str, Any]:
        """Create user data for testing."""
        return {
            "email": email or f"test_{uuid.uuid4().hex[:8]}@example.com",
            "full_name": full_name or "Test User",
            "role": role.value,
            "is_active": is_active,
            "password": "testpassword123"
        }
    
    @staticmethod
    def create_doctor_profile_data(
        specialization: str = "Cardiology",
        timezone: str = "America/New_York"
    ) -> Dict[str, Any]:
        """Create doctor profile data for testing."""
        return {
            "specialization": specialization,
            "timezone": timezone
        }
    
    @staticmethod
    def create_availability_data(
        start_time: datetime = None,
        end_time: datetime = None,
        days_ahead: int = 1
    ) -> Dict[str, Any]:
        """Create availability data for testing."""
        if not start_time:
            start_time = datetime.now(UTC) + timedelta(days=days_ahead, hours=9)
        if not end_time:
            end_time = start_time + timedelta(hours=2)
        
        return {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }
    
    @staticmethod
    def create_appointment_data(
        doctor_id: str,
        start_time: datetime = None,
        end_time: datetime = None,
        notes: str = None,
        days_ahead: int = 1
    ) -> Dict[str, Any]:
        """Create appointment data for testing."""
        if not start_time:
            start_time = datetime.now(UTC) + timedelta(days=days_ahead, hours=10)
        if not end_time:
            end_time = start_time + timedelta(minutes=30)
        
        return {
            "doctor_id": doctor_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "notes": notes or "Test appointment"
        }
    
    @staticmethod
    def create_login_data(email: str, password: str) -> Dict[str, str]:
        """Create login data for testing."""
        return {
            "username": email,
            "password": password
        }


class SampleData:
    """Predefined sample data for testing."""
    
    # User samples
    ADMIN_USER = {
        "email": "admin@healthcare.com",
        "full_name": "System Administrator",
        "role": UserRole.ADMIN.value,
        "password": "admin123"
    }
    
    DOCTOR_USER = {
        "email": "doctor@healthcare.com",
        "full_name": "Dr. Jane Smith",
        "role": UserRole.DOCTOR.value,
        "password": "doctor123"
    }
    
    PATIENT_USER = {
        "email": "patient@healthcare.com",
        "full_name": "John Doe",
        "role": UserRole.PATIENT.value,
        "password": "patient123"
    }
    
    # Doctor profile samples
    CARDIOLOGIST_PROFILE = {
        "specialization": "Cardiology",
        "timezone": "America/New_York"
    }
    
    NEUROLOGIST_PROFILE = {
        "specialization": "Neurology",
        "timezone": "America/Los_Angeles"
    }
    
    # Availability samples
    MORNING_AVAILABILITY = {
        "start_time": (datetime.now(UTC) + timedelta(days=1, hours=9)).isoformat(),
        "end_time": (datetime.now(UTC) + timedelta(days=1, hours=12)).isoformat()
    }
    
    AFTERNOON_AVAILABILITY = {
        "start_time": (datetime.now(UTC) + timedelta(days=1, hours=13)).isoformat(),
        "end_time": (datetime.now(UTC) + timedelta(days=1, hours=17)).isoformat()
    }
    
    # Appointment samples
    REGULAR_APPOINTMENT = {
        "start_time": (datetime.now(UTC) + timedelta(days=1, hours=10)).isoformat(),
        "end_time": (datetime.now(UTC) + timedelta(days=1, hours=10, minutes=30)).isoformat(),
        "notes": "Regular checkup"
    }
    
    FOLLOW_UP_APPOINTMENT = {
        "start_time": (datetime.now(UTC) + timedelta(days=7, hours=14)).isoformat(),
        "end_time": (datetime.now(UTC) + timedelta(days=7, hours=14, minutes=45)).isoformat(),
        "notes": "Follow-up appointment"
    }


class TestScenarios:
    """Common test scenarios and edge cases."""
    
    # Time scenarios
    PAST_TIME = datetime.now(UTC) - timedelta(days=1)
    FUTURE_TIME = datetime.now(UTC) + timedelta(days=1)
    FAR_FUTURE_TIME = datetime.now(UTC) + timedelta(days=365)
    
    # Overlapping time scenarios
    OVERLAPPING_START = datetime.now(UTC) + timedelta(days=1, hours=9, minutes=30)
    OVERLAPPING_END = datetime.now(UTC) + timedelta(days=1, hours=10, minutes=30)
    
    # Edge case times
    MIDNIGHT = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    END_OF_DAY = datetime.now(UTC).replace(hour=23, minute=59, second=59, microsecond=999999) + timedelta(days=1)
    
    # Invalid data scenarios
    INVALID_EMAILS = [
        "invalid-email",
        "@invalid.com",
        "invalid@",
        "invalid@.com",
        "invalid@com",
        ""
    ]
    
    INVALID_PASSWORDS = [
        "123",  # Too short
        "",     # Empty
        "a" * 1000,  # Too long
    ]
    
    INVALID_TIMES = [
        "invalid-time",
        "2024-13-01T10:00:00Z",  # Invalid month
        "2024-01-32T10:00:00Z",  # Invalid day
        "2024-01-01T25:00:00Z",  # Invalid hour
    ]
