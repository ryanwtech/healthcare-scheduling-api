"""Recurring appointment scheduling service."""

import uuid
from datetime import datetime, timedelta, UTC
from enum import Enum
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models import Appointment, AppointmentStatus, DoctorProfile, User
from app.db.schemas import AppointmentCreate
from app.security.audit import AuditLogger, get_audit_logger

logger = get_logger(__name__)


class RecurrencePattern(str, Enum):
    """Recurrence patterns for appointments."""
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    CUSTOM = "custom"


class RecurrenceEndType(str, Enum):
    """Recurrence end types."""
    NEVER = "never"
    AFTER_COUNT = "after_count"
    ON_DATE = "on_date"


class RecurringAppointmentService:
    """Service for managing recurring appointments."""
    
    def __init__(self, db: Session):
        self.db = db
        self.audit_logger = get_audit_logger(db)
    
    def create_recurring_appointments(
        self,
        base_appointment: AppointmentCreate,
        pattern: RecurrencePattern,
        interval: int = 1,
        end_type: RecurrenceEndType = RecurrenceEndType.NEVER,
        end_count: Optional[int] = None,
        end_date: Optional[datetime] = None,
        days_of_week: Optional[List[int]] = None,
        day_of_month: Optional[int] = None,
        created_by: uuid.UUID = None
    ) -> List[Appointment]:
        """
        Create a series of recurring appointments.
        
        Args:
            base_appointment: Base appointment data
            pattern: Recurrence pattern
            interval: Interval between occurrences
            end_type: How the recurrence ends
            end_count: Number of occurrences (if end_type is AFTER_COUNT)
            end_date: End date (if end_type is ON_DATE)
            days_of_week: Days of week for weekly patterns (0=Monday, 6=Sunday)
            day_of_month: Day of month for monthly patterns
            created_by: User creating the recurring appointments
            
        Returns:
            List of created appointments
        """
        try:
            # Validate recurrence parameters
            self._validate_recurrence_params(pattern, interval, end_type, end_count, end_date)
            
            # Generate appointment dates
            appointment_dates = self._generate_appointment_dates(
                base_appointment.start_time,
                pattern,
                interval,
                end_type,
                end_count,
                end_date,
                days_of_week,
                day_of_month
            )
            
            created_appointments = []
            
            for appointment_date in appointment_dates:
                # Create appointment for this date
                appointment_data = self._create_appointment_for_date(base_appointment, appointment_date)
                
                # Create the appointment
                appointment = Appointment(
                    id=uuid.uuid4(),
                    doctor_id=base_appointment.doctor_id,
                    patient_id=base_appointment.patient_id,
                    start_time=appointment_data["start_time"],
                    end_time=appointment_data["end_time"],
                    status=AppointmentStatus.SCHEDULED,
                    notes=appointment_data["notes"],
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC)
                )
                
                self.db.add(appointment)
                created_appointments.append(appointment)
            
            self.db.commit()
            
            # Log recurring appointment creation
            self.audit_logger.log_event(
                event_type="appointment_created",
                user_id=created_by,
                action="recurring_appointments_created",
                details={
                    "pattern": pattern.value,
                    "interval": interval,
                    "end_type": end_type.value,
                    "appointment_count": len(created_appointments),
                    "base_appointment_id": str(base_appointment.doctor_id)
                },
                success=True
            )
            
            logger.info(f"Created {len(created_appointments)} recurring appointments with pattern {pattern}")
            return created_appointments
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create recurring appointments: {e}")
            raise
    
    def _validate_recurrence_params(
        self,
        pattern: RecurrencePattern,
        interval: int,
        end_type: RecurrenceEndType,
        end_count: Optional[int],
        end_date: Optional[datetime]
    ) -> None:
        """Validate recurrence parameters."""
        if interval < 1:
            raise ValueError("Interval must be at least 1")
        
        if end_type == RecurrenceEndType.AFTER_COUNT and (end_count is None or end_count < 1):
            raise ValueError("End count must be specified and at least 1")
        
        if end_type == RecurrenceEndType.ON_DATE and end_date is None:
            raise ValueError("End date must be specified")
        
        if end_type == RecurrenceEndType.ON_DATE and end_date <= datetime.now(UTC):
            raise ValueError("End date must be in the future")
    
    def _generate_appointment_dates(
        self,
        start_time: datetime,
        pattern: RecurrencePattern,
        interval: int,
        end_type: RecurrenceEndType,
        end_count: Optional[int],
        end_date: Optional[datetime],
        days_of_week: Optional[List[int]],
        day_of_month: Optional[int]
    ) -> List[datetime]:
        """Generate appointment dates based on recurrence pattern."""
        dates = []
        current_date = start_time
        count = 0
        
        while True:
            # Check end conditions
            if end_type == RecurrenceEndType.AFTER_COUNT and count >= end_count:
                break
            if end_type == RecurrenceEndType.ON_DATE and current_date >= end_date:
                break
            
            # Add current date
            dates.append(current_date)
            count += 1
            
            # Calculate next date
            next_date = self._calculate_next_date(
                current_date, pattern, interval, days_of_week, day_of_month
            )
            
            if next_date is None:
                break
            
            current_date = next_date
            
            # Safety check to prevent infinite loops
            if count > 1000:
                logger.warning("Recurrence generation stopped at 1000 appointments")
                break
        
        return dates
    
    def _calculate_next_date(
        self,
        current_date: datetime,
        pattern: RecurrencePattern,
        interval: int,
        days_of_week: Optional[List[int]],
        day_of_month: Optional[int]
    ) -> Optional[datetime]:
        """Calculate the next appointment date."""
        if pattern == RecurrencePattern.DAILY:
            return current_date + timedelta(days=interval)
        
        elif pattern == RecurrencePattern.WEEKLY:
            if days_of_week:
                # Find next occurrence of specified days
                for _ in range(7 * interval):
                    current_date += timedelta(days=1)
                    if current_date.weekday() in days_of_week:
                        return current_date
                return None
            else:
                return current_date + timedelta(weeks=interval)
        
        elif pattern == RecurrencePattern.BIWEEKLY:
            return current_date + timedelta(weeks=2 * interval)
        
        elif pattern == RecurrencePattern.MONTHLY:
            if day_of_month:
                # Find next occurrence of specified day of month
                next_month = current_date.replace(day=1) + timedelta(days=32)
                next_month = next_month.replace(day=1)
                try:
                    return next_month.replace(day=day_of_month)
                except ValueError:
                    # Handle months with fewer days
                    return next_month.replace(day=1) - timedelta(days=1)
            else:
                # Same day of month, next month
                next_month = current_date.replace(day=1) + timedelta(days=32)
                next_month = next_month.replace(day=1)
                try:
                    return next_month.replace(day=current_date.day)
                except ValueError:
                    # Handle months with fewer days
                    return next_month.replace(day=1) - timedelta(days=1)
        
        elif pattern == RecurrencePattern.QUARTERLY:
            # Add 3 months
            next_date = current_date
            for _ in range(3 * interval):
                next_month = next_date.replace(day=1) + timedelta(days=32)
                next_date = next_month.replace(day=1)
            try:
                return next_date.replace(day=current_date.day)
            except ValueError:
                return next_date.replace(day=1) - timedelta(days=1)
        
        elif pattern == RecurrencePattern.YEARLY:
            # Add 1 year
            try:
                return current_date.replace(year=current_date.year + interval)
            except ValueError:
                # Handle leap year edge case
                return current_date.replace(year=current_date.year + interval, day=28)
        
        return None
    
    def _create_appointment_for_date(
        self,
        base_appointment: AppointmentCreate,
        appointment_date: datetime
    ) -> Dict:
        """Create appointment data for a specific date."""
        # Calculate duration
        duration = base_appointment.end_time - base_appointment.start_time
        
        # Set start time to the appointment date with same time
        start_time = appointment_date.replace(
            hour=base_appointment.start_time.hour,
            minute=base_appointment.start_time.minute,
            second=base_appointment.start_time.second,
            microsecond=base_appointment.start_time.microsecond
        )
        
        # Calculate end time
        end_time = start_time + duration
        
        return {
            "start_time": start_time,
            "end_time": end_time,
            "notes": base_appointment.notes
        }
    
    def get_recurring_appointments(
        self,
        doctor_id: uuid.UUID,
        start_date: datetime,
        end_date: datetime
    ) -> List[Appointment]:
        """Get recurring appointments for a doctor in a date range."""
        return (
            self.db.query(Appointment)
            .filter(
                Appointment.doctor_id == doctor_id,
                Appointment.start_time >= start_date,
                Appointment.start_time <= end_date,
                Appointment.status == AppointmentStatus.SCHEDULED
            )
            .order_by(Appointment.start_time)
            .all()
        )
    
    def cancel_recurring_appointments(
        self,
        appointment_ids: List[uuid.UUID],
        reason: str,
        cancelled_by: uuid.UUID
    ) -> int:
        """Cancel multiple recurring appointments."""
        try:
            cancelled_count = 0
            
            for appointment_id in appointment_ids:
                appointment = self.db.query(Appointment).filter(
                    Appointment.id == appointment_id
                ).first()
                
                if appointment and appointment.status == AppointmentStatus.SCHEDULED:
                    appointment.status = AppointmentStatus.CANCELLED
                    appointment.notes = f"{appointment.notes or ''}\nCancelled: {reason}"
                    appointment.updated_at = datetime.now(UTC)
                    cancelled_count += 1
                    
                    # Log cancellation
                    self.audit_logger.log_event(
                        event_type="appointment_cancelled",
                        user_id=cancelled_by,
                        resource_id=appointment_id,
                        resource_type="appointment",
                        action="recurring_cancelled",
                        details={"reason": reason},
                        success=True
                    )
            
            self.db.commit()
            logger.info(f"Cancelled {cancelled_count} recurring appointments")
            return cancelled_count
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to cancel recurring appointments: {e}")
            raise
    
    def reschedule_recurring_appointments(
        self,
        appointment_ids: List[uuid.UUID],
        new_start_time: datetime,
        new_end_time: datetime,
        rescheduled_by: uuid.UUID
    ) -> int:
        """Reschedule multiple recurring appointments."""
        try:
            rescheduled_count = 0
            
            for appointment_id in appointment_ids:
                appointment = self.db.query(Appointment).filter(
                    Appointment.id == appointment_id
                ).first()
                
                if appointment and appointment.status == AppointmentStatus.SCHEDULED:
                    old_start = appointment.start_time
                    old_end = appointment.end_time
                    
                    appointment.start_time = new_start_time
                    appointment.end_time = new_end_time
                    appointment.updated_at = datetime.now(UTC)
                    rescheduled_count += 1
                    
                    # Log rescheduling
                    self.audit_logger.log_event(
                        event_type="appointment_updated",
                        user_id=rescheduled_by,
                        resource_id=appointment_id,
                        resource_type="appointment",
                        action="recurring_rescheduled",
                        details={
                            "old_start_time": old_start.isoformat(),
                            "old_end_time": old_end.isoformat(),
                            "new_start_time": new_start_time.isoformat(),
                            "new_end_time": new_end_time.isoformat()
                        },
                        success=True
                    )
            
            self.db.commit()
            logger.info(f"Rescheduled {rescheduled_count} recurring appointments")
            return rescheduled_count
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to reschedule recurring appointments: {e}")
            raise


def get_recurring_appointment_service(db: Session) -> RecurringAppointmentService:
    """Get recurring appointment service instance."""
    return RecurringAppointmentService(db)
