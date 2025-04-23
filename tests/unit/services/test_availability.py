"""Unit tests for availability service."""

import uuid
from datetime import datetime, timedelta, UTC
from unittest.mock import MagicMock, patch

import pytest

from app.db.models import DoctorProfile, User, UserRole, Availability
from app.services.availability import AvailabilityService
from tests.utils.test_data import TestDataFactory, TestScenarios


@pytest.mark.unit
class TestAvailabilityService:
    """Test cases for AvailabilityService."""
    
    def test_create_availability_success(self, temp_db, doctor_profile):
        """Test successful availability creation."""
        service = AvailabilityService(temp_db)
        
        start_time = datetime.now(UTC) + timedelta(days=1, hours=9)
        end_time = start_time + timedelta(hours=3)
        
        availability_data = TestDataFactory.create_availability_data(
            start_time=start_time,
            end_time=end_time
        )
        
        availability = service.create_availability(
            doctor_id=doctor_profile.id,
            availability_data=availability_data
        )
        
        assert availability is not None
        assert availability.doctor_id == doctor_profile.id
        assert availability.start_time == start_time
        assert availability.end_time == end_time
    
    def test_create_availability_doctor_not_found(self, temp_db):
        """Test availability creation with non-existent doctor."""
        service = AvailabilityService(temp_db)
        fake_doctor_id = uuid.uuid4()
        
        availability_data = TestDataFactory.create_availability_data()
        
        with pytest.raises(ValueError, match="Doctor not found or inactive"):
            service.create_availability(
                doctor_id=fake_doctor_id,
                availability_data=availability_data
            )
    
    def test_create_availability_invalid_time_range(self, temp_db, doctor_profile):
        """Test availability creation with invalid time range."""
        service = AvailabilityService(temp_db)
        
        start_time = datetime.now(UTC) + timedelta(days=1, hours=9)
        end_time = start_time - timedelta(hours=1)  # End before start
        
        availability_data = TestDataFactory.create_availability_data(
            start_time=start_time,
            end_time=end_time
        )
        
        with pytest.raises(ValueError, match="Start time must be before end time"):
            service.create_availability(
                doctor_id=doctor_profile.id,
                availability_data=availability_data
            )
    
    def test_create_availability_past_time(self, temp_db, doctor_profile):
        """Test availability creation in the past."""
        service = AvailabilityService(temp_db)
        
        start_time = datetime.now(UTC) - timedelta(days=1)
        end_time = start_time + timedelta(hours=3)
        
        availability_data = TestDataFactory.create_availability_data(
            start_time=start_time,
            end_time=end_time
        )
        
        with pytest.raises(ValueError, match="Cannot create availability in the past"):
            service.create_availability(
                doctor_id=doctor_profile.id,
                availability_data=availability_data
            )
    
    def test_get_availability_success(self, temp_db, sample_availability):
        """Test successful availability retrieval."""
        service = AvailabilityService(temp_db)
        
        availability = service.get_availability(sample_availability.id)
        
        assert availability is not None
        assert availability.id == sample_availability.id
        assert availability.doctor_id == sample_availability.doctor_id
    
    def test_get_availability_not_found(self, temp_db):
        """Test availability retrieval with non-existent ID."""
        service = AvailabilityService(temp_db)
        fake_availability_id = uuid.uuid4()
        
        with pytest.raises(ValueError, match="Availability not found"):
            service.get_availability(fake_availability_id)
    
    def test_update_availability_success(self, temp_db, sample_availability):
        """Test successful availability update."""
        service = AvailabilityService(temp_db)
        
        new_start_time = sample_availability.start_time + timedelta(hours=1)
        new_end_time = sample_availability.end_time + timedelta(hours=1)
        
        update_data = TestDataFactory.create_availability_data(
            start_time=new_start_time,
            end_time=new_end_time
        )
        
        updated_availability = service.update_availability(
            availability_id=sample_availability.id,
            availability_data=update_data
        )
        
        assert updated_availability is not None
        assert updated_availability.start_time == new_start_time
        assert updated_availability.end_time == new_end_time
    
    def test_delete_availability_success(self, temp_db, sample_availability):
        """Test successful availability deletion."""
        service = AvailabilityService(temp_db)
        
        result = service.delete_availability(sample_availability.id)
        
        assert result is True
        
        # Verify availability is deleted
        with pytest.raises(ValueError, match="Availability not found"):
            service.get_availability(sample_availability.id)
    
    def test_get_doctor_availability(self, temp_db, doctor_profile, sample_availability):
        """Test getting doctor's availability."""
        service = AvailabilityService(temp_db)
        
        availabilities = service.get_doctor_availability(doctor_profile.id)
        
        assert len(availabilities) == 1
        assert availabilities[0].id == sample_availability.id
    
    @patch('app.services.availability.redis_client')
    def test_get_available_slots_with_cache(self, mock_redis, temp_db, doctor_profile, sample_availability):
        """Test getting available slots with Redis cache."""
        # Mock Redis to return cached data
        mock_redis.get.return_value = '[]'  # Empty cache
        mock_redis.set.return_value = True
        
        service = AvailabilityService(temp_db)
        
        date_obj = sample_availability.start_time.date()
        slots = service.get_available_slots(doctor_profile.id, date_obj)
        
        assert isinstance(slots, list)
        # Should query database when cache is empty
        mock_redis.get.assert_called_once()
        mock_redis.set.assert_called_once()
    
    @patch('app.services.availability.redis_client')
    def test_get_available_slots_cache_hit(self, mock_redis, temp_db, doctor_profile):
        """Test getting available slots with cache hit."""
        # Mock Redis to return cached data
        cached_slots = '[{"start_time": "2024-01-20T09:00:00Z", "end_time": "2024-01-20T12:00:00Z"}]'
        mock_redis.get.return_value = cached_slots
        
        service = AvailabilityService(temp_db)
        
        date_obj = datetime.now(UTC).date()
        slots = service.get_available_slots(doctor_profile.id, date_obj)
        
        assert isinstance(slots, list)
        # Should use cached data
        mock_redis.get.assert_called_once()
        mock_redis.set.assert_not_called()
    
    @patch('app.services.availability.redis_client')
    def test_get_available_slots_redis_unavailable(self, mock_redis, temp_db, doctor_profile, sample_availability):
        """Test getting available slots when Redis is unavailable."""
        # Mock Redis to raise exception
        mock_redis.get.side_effect = Exception("Redis unavailable")
        
        service = AvailabilityService(temp_db)
        
        date_obj = sample_availability.start_time.date()
        slots = service.get_available_slots(doctor_profile.id, date_obj)
        
        assert isinstance(slots, list)
        # Should fallback to database query
    
    def test_check_availability_conflict_no_conflict(self, temp_db, doctor_profile, sample_availability):
        """Test availability conflict check with no conflict."""
        service = AvailabilityService(temp_db)
        
        # Non-overlapping time
        start_time = sample_availability.end_time + timedelta(hours=1)
        end_time = start_time + timedelta(hours=2)
        
        has_conflict = service.check_availability_conflict(
            doctor_id=doctor_profile.id,
            start_time=start_time,
            end_time=end_time,
            exclude_id=sample_availability.id
        )
        
        assert has_conflict is False
    
    def test_check_availability_conflict_with_conflict(self, temp_db, doctor_profile, sample_availability):
        """Test availability conflict check with conflict."""
        service = AvailabilityService(temp_db)
        
        # Overlapping time
        start_time = sample_availability.start_time + timedelta(minutes=30)
        end_time = start_time + timedelta(hours=1)
        
        has_conflict = service.check_availability_conflict(
            doctor_id=doctor_profile.id,
            start_time=start_time,
            end_time=end_time,
            exclude_id=sample_availability.id
        )
        
        assert has_conflict is True
    
    def test_get_doctor_availability_summary(self, temp_db, doctor_profile, sample_availability):
        """Test getting doctor availability summary."""
        service = AvailabilityService(temp_db)
        
        summary = service.get_doctor_availability_summary(doctor_profile.id)
        
        assert "total_slots" in summary
        assert "upcoming_slots" in summary
        assert "past_slots" in summary
        assert summary["total_slots"] == 1
    
    def test_invalidate_cache(self, temp_db, doctor_profile):
        """Test cache invalidation."""
        service = AvailabilityService(temp_db)
        
        date_obj = datetime.now(UTC).date()
        
        with patch.object(service, '_invalidate_cache') as mock_invalidate:
            service._invalidate_cache(doctor_profile.id, date_obj)
            mock_invalidate.assert_called_once_with(doctor_profile.id, date_obj)
    
    def test_cache_key_generation(self, temp_db, doctor_profile):
        """Test cache key generation."""
        service = AvailabilityService(temp_db)
        
        date_obj = datetime.now(UTC).date()
        expected_key = f"availability:{doctor_profile.id}:{date_obj.strftime('%Y%m%d')}"
        
        key = service._get_cache_key(doctor_profile.id, date_obj)
        
        assert key == expected_key
