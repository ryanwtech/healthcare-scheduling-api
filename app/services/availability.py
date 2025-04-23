"""Availability service with Redis caching for doctor schedules."""

import json
import uuid
from datetime import date, datetime, timedelta
from typing import Any

import redis
from sqlalchemy.orm import Session
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import Availability, DoctorProfile, User
from app.db.schemas import AvailabilityCreate, AvailabilityUpdate

logger = get_logger(__name__)

# Retry configuration for Redis operations
redis_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=0.1, max=1.0),
    retry=retry_if_exception_type((redis.ConnectionError, redis.TimeoutError, redis.RedisError)),
    reraise=True
)

# Redis connection with graceful fallback
try:
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    redis_client.ping()  # Test connection
    REDIS_AVAILABLE = True
    logger.info("Redis connection established")
except Exception as e:
    redis_client = None
    REDIS_AVAILABLE = False
    logger.warning(f"Redis unavailable, caching disabled: {e}")


class AvailabilityService:
    """Service for managing doctor availability with Redis caching."""

    def __init__(self, db: Session):
        self.db = db

    def _get_cache_key(self, doctor_id: uuid.UUID, date_obj: date) -> str:
        """Generate Redis cache key for doctor availability on specific date."""
        return f"availability:{doctor_id}:{date_obj.strftime('%Y%m%d')}"

    @redis_retry
    def _invalidate_cache(self, doctor_id: uuid.UUID, date_obj: date) -> None:
        """Invalidate Redis cache for specific doctor and date."""
        if not REDIS_AVAILABLE:
            return

        try:
            cache_key = self._get_cache_key(doctor_id, date_obj)
            redis_client.delete(cache_key)
            logger.debug(f"Invalidated cache for key: {cache_key}")
        except Exception as e:
            logger.warning(f"Failed to invalidate cache: {e}")

    @redis_retry
    def _get_cached_slots(self, doctor_id: uuid.UUID, date_obj: date) -> list[dict[str, Any]] | None:
        """Get cached availability slots for doctor on specific date."""
        if not REDIS_AVAILABLE:
            return None

        try:
            cache_key = self._get_cache_key(doctor_id, date_obj)
            cached_data = redis_client.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logger.warning(f"Failed to get cached slots: {e}")
        return None

    @redis_retry
    def _cache_slots(self, doctor_id: uuid.UUID, date_obj: date, slots: list[dict[str, Any]]) -> None:
        """Cache availability slots for doctor on specific date."""
        if not REDIS_AVAILABLE:
            return

        try:
            cache_key = self._get_cache_key(doctor_id, date_obj)
            # Cache for 1 hour
            redis_client.setex(cache_key, 3600, json.dumps(slots, default=str))
            logger.debug(f"Cached slots for key: {cache_key}")
        except Exception as e:
            logger.warning(f"Failed to cache slots: {e}")

    def create_availability(self, doctor_id: uuid.UUID, availability_data: AvailabilityCreate) -> Availability:
        """Create new availability slot for doctor."""
        # Verify doctor exists and is active
        doctor = self.db.query(DoctorProfile).join(User).filter(
            DoctorProfile.id == doctor_id,
            User.is_active
        ).first()
        if not doctor:
            raise ValueError("Doctor not found or inactive")

        # Create availability
        availability = Availability(
            doctor_id=doctor_id,
            start_time=availability_data.start_time,
            end_time=availability_data.end_time
        )
        
        self.db.add(availability)
        self.db.commit()
        self.db.refresh(availability)

        # Invalidate cache for the date
        self._invalidate_cache(doctor_id, availability_data.start_time.date())

        logger.info(f"Created availability {availability.id} for doctor {doctor_id}")
        return availability

    def get_availability(self, availability_id: uuid.UUID) -> Availability | None:
        """Get availability by ID."""
        return self.db.query(Availability).filter(Availability.id == availability_id).first()

    def update_availability(
        self, 
        availability_id: uuid.UUID, 
        availability_data: AvailabilityUpdate
    ) -> Availability | None:
        """Update availability slot."""
        availability = self.get_availability(availability_id)
        if not availability:
            return None

        # Store old date for cache invalidation
        old_date = availability.start_time.date()

        # Update fields
        if availability_data.start_time is not None:
            availability.start_time = availability_data.start_time
        if availability_data.end_time is not None:
            availability.end_time = availability_data.end_time

        self.db.commit()
        self.db.refresh(availability)

        # Invalidate cache for both old and new dates
        self._invalidate_cache(availability.doctor_id, old_date)
        if availability_data.start_time:
            self._invalidate_cache(availability.doctor_id, availability_data.start_time.date())

        logger.info(f"Updated availability {availability_id}")
        return availability

    def delete_availability(self, availability_id: uuid.UUID) -> bool:
        """Delete availability slot."""
        availability = self.get_availability(availability_id)
        if not availability:
            return False

        doctor_id = availability.doctor_id
        date_obj = availability.start_time.date()

        self.db.delete(availability)
        self.db.commit()

        # Invalidate cache
        self._invalidate_cache(doctor_id, date_obj)

        logger.info(f"Deleted availability {availability_id}")
        return True

    def get_doctor_availability(
        self, 
        doctor_id: uuid.UUID, 
        start_date: date, 
        end_date: date
    ) -> list[Availability]:
        """Get all availability slots for doctor in date range."""
        return (
            self.db.query(Availability)
            .filter(
                Availability.doctor_id == doctor_id,
                Availability.start_time >= datetime.combine(start_date, datetime.min.time()),
                Availability.start_time <= datetime.combine(end_date, datetime.max.time())
            )
            .order_by(Availability.start_time)
            .all()
        )

    def get_available_slots(
        self, 
        doctor_id: uuid.UUID, 
        start_date: date, 
        end_date: date
    ) -> list[dict[str, Any]]:
        """Get available time slots for doctor in date range with caching."""
        # Check cache first for each date
        all_slots = []
        current_date = start_date

        while current_date <= end_date:
            # Try to get from cache
            cached_slots = self._get_cached_slots(doctor_id, current_date)
            
            if cached_slots is not None:
                all_slots.extend(cached_slots)
                logger.debug(f"Retrieved cached slots for {current_date}")
            else:
                # Get from database and cache
                day_start = datetime.combine(current_date, datetime.min.time())
                day_end = datetime.combine(current_date, datetime.max.time())
                
                day_availability = (
                    self.db.query(Availability)
                    .filter(
                        Availability.doctor_id == doctor_id,
                        Availability.start_time >= day_start,
                        Availability.start_time < day_end
                    )
                    .order_by(Availability.start_time)
                    .all()
                )

                # Convert to serializable format
                day_slots = [
                    {
                        "id": str(avail.id),
                        "start_time": avail.start_time.isoformat() + "Z",
                        "end_time": avail.end_time.isoformat() + "Z",
                        "duration_minutes": int((avail.end_time - avail.start_time).total_seconds() / 60)
                    }
                    for avail in day_availability
                ]

                # Cache the slots
                self._cache_slots(doctor_id, current_date, day_slots)
                all_slots.extend(day_slots)

            current_date += timedelta(days=1)

        logger.info(f"Retrieved {len(all_slots)} available slots for doctor {doctor_id}")
        return all_slots

    def check_availability_conflict(
        self, 
        doctor_id: uuid.UUID, 
        start_time: datetime, 
        end_time: datetime,
        exclude_id: uuid.UUID | None = None
    ) -> bool:
        """Check if there's a time conflict with existing availability."""
        query = (
            self.db.query(Availability)
            .filter(
                Availability.doctor_id == doctor_id,
                Availability.start_time < end_time,
                Availability.end_time > start_time
            )
        )

        if exclude_id:
            query = query.filter(Availability.id != exclude_id)

        return query.first() is not None

    def get_doctor_availability_summary(
        self, 
        doctor_id: uuid.UUID, 
        start_date: date, 
        end_date: date
    ) -> dict[str, Any]:
        """Get summary of doctor availability for date range."""
        availability = self.get_doctor_availability(doctor_id, start_date, end_date)
        
        total_slots = len(availability)
        total_hours = sum(
            (avail.end_time - avail.start_time).total_seconds() / 3600 
            for avail in availability
        )

        # Group by date
        by_date = {}
        for avail in availability:
            date_key = avail.start_time.date().isoformat()
            if date_key not in by_date:
                by_date[date_key] = []
            by_date[date_key].append({
                "id": str(avail.id),
                "start_time": avail.start_time.isoformat() + "Z",
                "end_time": avail.end_time.isoformat() + "Z"
            })

        return {
            "doctor_id": str(doctor_id),
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "summary": {
                "total_slots": total_slots,
                "total_hours": round(total_hours, 2),
                "average_slot_duration_hours": round(total_hours / total_slots, 2) if total_slots > 0 else 0
            },
            "availability_by_date": by_date
        }
