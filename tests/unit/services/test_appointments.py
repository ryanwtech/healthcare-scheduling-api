"""Unit tests for appointment service."""

import uuid
from datetime import datetime, timedelta, UTC
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models import Appointment, AppointmentStatus, User, UserRole
from app.services.appointments import AppointmentService
from tests.utils.test_data import TestDataFactory, TestScenarios


@pytest.mark.unit
class TestAppointmentService:
    """Test cases for AppointmentService."""
    
    def test_book_appointment_success(self, temp_db, doctor_profile, patient_user):
        """Test successful appointment booking."""
        service = AppointmentService(temp_db)
        
        start_time = datetime.now(UTC) + timedelta(days=1, hours=10)
        end_time = start_time + timedelta(minutes=30)
        
        # Mock availability check
        with patch.object(service, '_check_availability_overlap', return_value=True):
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
        assert appointment.start_time == start_time
        assert appointment.end_time == end_time
        assert appointment.status == AppointmentStatus.SCHEDULED
        assert appointment.notes == "Test appointment"
    
    def test_book_appointment_invalid_time_range(self, temp_db, doctor_profile, patient_user):
        """Test appointment booking with invalid time range."""
        service = AppointmentService(temp_db)
        
        start_time = datetime.now(UTC) + timedelta(days=1, hours=10)
        end_time = start_time - timedelta(minutes=30)  # End before start
        
        with pytest.raises(ValueError, match="Start time must be before end time"):
            service.book_appointment(
                patient_id=patient_user.id,
                doctor_id=doctor_profile.id,
                start_time=start_time,
                end_time=end_time
            )
    
    def test_book_appointment_past_time(self, temp_db, doctor_profile, patient_user):
        """Test appointment booking in the past."""
        service = AppointmentService(temp_db)
        
        start_time = datetime.now(UTC) - timedelta(days=1)
        end_time = start_time + timedelta(minutes=30)
        
        with pytest.raises(ValueError, match="Cannot book appointments in the past"):
            service.book_appointment(
                patient_id=patient_user.id,
                doctor_id=doctor_profile.id,
                start_time=start_time,
                end_time=end_time
            )
    
    def test_book_appointment_doctor_not_found(self, temp_db, patient_user):
        """Test appointment booking with non-existent doctor."""
        service = AppointmentService(temp_db)
        
        start_time = datetime.now(UTC) + timedelta(days=1, hours=10)
        end_time = start_time + timedelta(minutes=30)
        fake_doctor_id = uuid.uuid4()
        
        with pytest.raises(ValueError, match="Doctor not found or inactive"):
            service.book_appointment(
                patient_id=patient_user.id,
                doctor_id=fake_doctor_id,
                start_time=start_time,
                end_time=end_time
            )
    
    def test_book_appointment_patient_not_found(self, temp_db, doctor_profile):
        """Test appointment booking with non-existent patient."""
        service = AppointmentService(temp_db)
        
        start_time = datetime.now(UTC) + timedelta(days=1, hours=10)
        end_time = start_time + timedelta(minutes=30)
        fake_patient_id = uuid.uuid4()
        
        with pytest.raises(ValueError, match="Patient not found or inactive"):
            service.book_appointment(
                patient_id=fake_patient_id,
                doctor_id=doctor_profile.id,
                start_time=start_time,
                end_time=end_time
            )
    
    def test_book_appointment_outside_availability(self, temp_db, doctor_profile, patient_user):
        """Test appointment booking outside doctor's availability."""
        service = AppointmentService(temp_db)
        
        start_time = datetime.now(UTC) + timedelta(days=1, hours=10)
        end_time = start_time + timedelta(minutes=30)
        
        # Mock availability check to return False
        with patch.object(service, '_check_availability_overlap', return_value=False):
            with pytest.raises(ValueError, match="Requested time slot is not within doctor's availability"):
                service.book_appointment(
                    patient_id=patient_user.id,
                    doctor_id=doctor_profile.id,
                    start_time=start_time,
                    end_time=end_time
                )
    
    def test_book_appointment_overlapping_appointment(self, temp_db, doctor_profile, patient_user):
        """Test appointment booking with overlapping appointment."""
        service = AppointmentService(temp_db)
        
        start_time = datetime.now(UTC) + timedelta(days=1, hours=10)
        end_time = start_time + timedelta(minutes=30)
        
        # Create existing appointment
        existing_appointment = Appointment(
            id=uuid.uuid4(),
            doctor_id=doctor_profile.id,
            patient_id=patient_user.id,
            start_time=start_time,
            end_time=end_time,
            status=AppointmentStatus.SCHEDULED,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        temp_db.add(existing_appointment)
        temp_db.commit()
        
        # Mock availability check to return True
        with patch.object(service, '_check_availability_overlap', return_value=True):
            with pytest.raises(ValueError, match="Time slot conflicts with existing appointment"):
                service.book_appointment(
                    patient_id=patient_user.id,
                    doctor_id=doctor_profile.id,
                    start_time=start_time,
                    end_time=end_time
                )
    
    def test_cancel_appointment_success(self, temp_db, sample_appointment):
        """Test successful appointment cancellation."""
        service = AppointmentService(temp_db)
        
        result = service.cancel_appointment(
            appointment_id=sample_appointment.id,
            user_id=sample_appointment.patient_id,
            reason="Patient request"
        )
        
        assert result is not None
        assert result.status == AppointmentStatus.CANCELLED
        assert result.notes == "Patient request"
    
    def test_cancel_appointment_not_found(self, temp_db):
        """Test cancelling non-existent appointment."""
        service = AppointmentService(temp_db)
        fake_appointment_id = uuid.uuid4()
        
        with pytest.raises(ValueError, match="Appointment not found"):
            service.cancel_appointment(
                appointment_id=fake_appointment_id,
                user_id=uuid.uuid4(),
                reason="Test"
            )
    
    def test_cancel_appointment_unauthorized(self, temp_db, sample_appointment):
        """Test cancelling appointment by unauthorized user."""
        service = AppointmentService(temp_db)
        other_user_id = uuid.uuid4()
        
        with pytest.raises(ValueError, match="Not authorized to cancel this appointment"):
            service.cancel_appointment(
                appointment_id=sample_appointment.id,
                user_id=other_user_id,
                reason="Test"
            )
    
    def test_list_appointments_patient(self, temp_db, patient_user, sample_appointment):
        """Test listing appointments for patient."""
        service = AppointmentService(temp_db)
        
        appointments = service.list_appointments(
            user_id=patient_user.id,
            user_role=UserRole.PATIENT
        )
        
        assert len(appointments) == 1
        assert appointments[0].id == sample_appointment.id
    
    def test_list_appointments_doctor(self, temp_db, doctor_profile, sample_appointment):
        """Test listing appointments for doctor."""
        service = AppointmentService(temp_db)
        
        appointments = service.list_appointments(
            user_id=doctor_profile.user_id,
            user_role=UserRole.DOCTOR
        )
        
        assert len(appointments) == 1
        assert appointments[0].id == sample_appointment.id
    
    def test_list_appointments_admin(self, temp_db, admin_user, sample_appointment):
        """Test listing appointments for admin."""
        service = AppointmentService(temp_db)
        
        appointments = service.list_appointments(
            user_id=admin_user.id,
            user_role=UserRole.ADMIN
        )
        
        assert len(appointments) == 1
        assert appointments[0].id == sample_appointment.id
    
    def test_list_appointments_with_filters(self, temp_db, patient_user, sample_appointment):
        """Test listing appointments with filters."""
        service = AppointmentService(temp_db)
        
        # Test status filter
        appointments = service.list_appointments(
            user_id=patient_user.id,
            user_role=UserRole.PATIENT,
            status=AppointmentStatus.SCHEDULED
        )
        
        assert len(appointments) == 1
        assert appointments[0].status == AppointmentStatus.SCHEDULED
    
    def test_get_appointment_statistics(self, temp_db, sample_appointment):
        """Test getting appointment statistics."""
        service = AppointmentService(temp_db)
        
        stats = service.get_appointment_statistics()
        
        assert "total_appointments" in stats
        assert "scheduled_appointments" in stats
        assert "cancelled_appointments" in stats
        assert "completed_appointments" in stats
        assert stats["total_appointments"] == 1
        assert stats["scheduled_appointments"] == 1
    
    def test_check_availability_overlap(self, temp_db, doctor_profile, sample_availability):
        """Test availability overlap checking."""
        service = AppointmentService(temp_db)
        
        # Test overlapping time
        start_time = sample_availability.start_time + timedelta(minutes=15)
        end_time = start_time + timedelta(minutes=30)
        
        result = service._check_availability_overlap(
            doctor_id=doctor_profile.id,
            start_time=start_time,
            end_time=end_time
        )
        
        assert result is True
    
    def test_check_availability_no_overlap(self, temp_db, doctor_profile, sample_availability):
        """Test availability check with no overlap."""
        service = AppointmentService(temp_db)
        
        # Test non-overlapping time
        start_time = sample_availability.end_time + timedelta(hours=1)
        end_time = start_time + timedelta(minutes=30)
        
        result = service._check_availability_overlap(
            doctor_id=doctor_profile.id,
            start_time=start_time,
            end_time=end_time
        )
        
        assert result is False
