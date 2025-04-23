"""Waitlist management service for appointment scheduling."""

import uuid
from datetime import datetime, timedelta, UTC
from enum import Enum
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models import Appointment, AppointmentStatus, DoctorProfile, User
from app.security.audit import AuditLogger, get_audit_logger

logger = get_logger(__name__)


class WaitlistStatus(str, Enum):
    """Waitlist entry status."""
    ACTIVE = "active"
    NOTIFIED = "notified"
    BOOKED = "booked"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class WaitlistEntry:
    """Waitlist entry for appointment scheduling."""
    
    def __init__(
        self,
        id: uuid.UUID,
        patient_id: uuid.UUID,
        doctor_id: uuid.UUID,
        preferred_start_time: datetime,
        preferred_end_time: datetime,
        status: WaitlistStatus = WaitlistStatus.ACTIVE,
        created_at: datetime = None,
        notified_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        notes: Optional[str] = None
    ):
        self.id = id
        self.patient_id = patient_id
        self.doctor_id = doctor_id
        self.preferred_start_time = preferred_start_time
        self.preferred_end_time = preferred_end_time
        self.status = status
        self.created_at = created_at or datetime.now(UTC)
        self.notified_at = notified_at
        self.expires_at = expires_at
        self.notes = notes


class WaitlistService:
    """Service for managing appointment waitlists."""
    
    def __init__(self, db: Session):
        self.db = db
        self.audit_logger = get_audit_logger(db)
        self.waitlist_entries: Dict[uuid.UUID, WaitlistEntry] = {}
    
    def add_to_waitlist(
        self,
        patient_id: uuid.UUID,
        doctor_id: uuid.UUID,
        preferred_start_time: datetime,
        preferred_end_time: datetime,
        notes: Optional[str] = None,
        expires_in_hours: int = 24
    ) -> WaitlistEntry:
        """
        Add a patient to the waitlist for a specific time slot.
        
        Args:
            patient_id: Patient ID
            doctor_id: Doctor ID
            preferred_start_time: Preferred start time
            preferred_end_time: Preferred end time
            notes: Optional notes
            expires_in_hours: Hours until waitlist entry expires
            
        Returns:
            WaitlistEntry object
        """
        try:
            # Check if patient is already on waitlist for this time slot
            existing_entry = self._find_existing_entry(patient_id, doctor_id, preferred_start_time)
            if existing_entry:
                raise ValueError("Patient is already on waitlist for this time slot")
            
            # Create waitlist entry
            entry_id = uuid.uuid4()
            expires_at = datetime.now(UTC) + timedelta(hours=expires_in_hours)
            
            waitlist_entry = WaitlistEntry(
                id=entry_id,
                patient_id=patient_id,
                doctor_id=doctor_id,
                preferred_start_time=preferred_start_time,
                preferred_end_time=preferred_end_time,
                status=WaitlistStatus.ACTIVE,
                expires_at=expires_at,
                notes=notes
            )
            
            # Store in memory (in production, use database)
            self.waitlist_entries[entry_id] = waitlist_entry
            
            # Log waitlist addition
            self.audit_logger.log_event(
                event_type="phi_created",
                user_id=patient_id,
                resource_id=entry_id,
                resource_type="waitlist_entry",
                action="waitlist_added",
                details={
                    "doctor_id": str(doctor_id),
                    "preferred_start_time": preferred_start_time.isoformat(),
                    "preferred_end_time": preferred_end_time.isoformat(),
                    "expires_at": expires_at.isoformat()
                },
                success=True
            )
            
            logger.info(f"Added patient {patient_id} to waitlist for doctor {doctor_id}")
            return waitlist_entry
            
        except Exception as e:
            logger.error(f"Failed to add to waitlist: {e}")
            raise
    
    def get_waitlist_for_doctor(
        self,
        doctor_id: uuid.UUID,
        status: Optional[WaitlistStatus] = None
    ) -> List[WaitlistEntry]:
        """Get waitlist entries for a specific doctor."""
        entries = [
            entry for entry in self.waitlist_entries.values()
            if entry.doctor_id == doctor_id
        ]
        
        if status:
            entries = [entry for entry in entries if entry.status == status]
        
        # Sort by creation time (FIFO)
        return sorted(entries, key=lambda x: x.created_at)
    
    def get_waitlist_for_patient(
        self,
        patient_id: uuid.UUID,
        status: Optional[WaitlistStatus] = None
    ) -> List[WaitlistEntry]:
        """Get waitlist entries for a specific patient."""
        entries = [
            entry for entry in self.waitlist_entries.values()
            if entry.patient_id == patient_id
        ]
        
        if status:
            entries = [entry for entry in entries if entry.status == status]
        
        return sorted(entries, key=lambda x: x.created_at)
    
    def notify_waitlist_availability(
        self,
        doctor_id: uuid.UUID,
        available_start_time: datetime,
        available_end_time: datetime,
        notification_window_minutes: int = 15
    ) -> List[WaitlistEntry]:
        """
        Notify waitlist patients when a time slot becomes available.
        
        Args:
            doctor_id: Doctor ID
            available_start_time: Available start time
            available_end_time: Available end time
            notification_window_minutes: Window for notification (minutes)
            
        Returns:
            List of notified waitlist entries
        """
        try:
            # Find matching waitlist entries
            matching_entries = self._find_matching_entries(
                doctor_id, available_start_time, available_end_time
            )
            
            notified_entries = []
            notification_deadline = datetime.now(UTC) + timedelta(minutes=notification_window_minutes)
            
            for entry in matching_entries:
                if entry.status == WaitlistStatus.ACTIVE:
                    # Update entry status
                    entry.status = WaitlistStatus.NOTIFIED
                    entry.notified_at = datetime.now(UTC)
                    entry.expires_at = notification_deadline
                    
                    notified_entries.append(entry)
                    
                    # Log notification
                    self.audit_logger.log_event(
                        event_type="phi_access",
                        user_id=entry.patient_id,
                        resource_id=entry.id,
                        resource_type="waitlist_entry",
                        action="waitlist_notified",
                        details={
                            "available_start_time": available_start_time.isoformat(),
                            "available_end_time": available_end_time.isoformat(),
                            "notification_deadline": notification_deadline.isoformat()
                        },
                        success=True
                    )
            
            logger.info(f"Notified {len(notified_entries)} patients on waitlist for doctor {doctor_id}")
            return notified_entries
            
        except Exception as e:
            logger.error(f"Failed to notify waitlist: {e}")
            raise
    
    def book_from_waitlist(
        self,
        waitlist_entry_id: uuid.UUID,
        actual_start_time: datetime,
        actual_end_time: datetime,
        booked_by: uuid.UUID
    ) -> Optional[Appointment]:
        """
        Book an appointment from waitlist entry.
        
        Args:
            waitlist_entry_id: Waitlist entry ID
            actual_start_time: Actual appointment start time
            actual_end_time: Actual appointment end time
            booked_by: User who booked the appointment
            
        Returns:
            Created appointment or None if entry not found/expired
        """
        try:
            # Get waitlist entry
            entry = self.waitlist_entries.get(waitlist_entry_id)
            if not entry:
                return None
            
            # Check if entry is still valid
            if entry.status != WaitlistStatus.NOTIFIED:
                logger.warning(f"Waitlist entry {waitlist_entry_id} is not in notified status")
                return None
            
            if entry.expires_at and datetime.now(UTC) > entry.expires_at:
                entry.status = WaitlistStatus.EXPIRED
                logger.warning(f"Waitlist entry {waitlist_entry_id} has expired")
                return None
            
            # Create appointment
            appointment = Appointment(
                id=uuid.uuid4(),
                doctor_id=entry.doctor_id,
                patient_id=entry.patient_id,
                start_time=actual_start_time,
                end_time=actual_end_time,
                status=AppointmentStatus.SCHEDULED,
                notes=f"Booked from waitlist. Original notes: {entry.notes or 'None'}",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC)
            )
            
            self.db.add(appointment)
            self.db.commit()
            
            # Update waitlist entry status
            entry.status = WaitlistStatus.BOOKED
            
            # Log appointment booking
            self.audit_logger.log_event(
                event_type="appointment_created",
                user_id=booked_by,
                resource_id=appointment.id,
                resource_type="appointment",
                action="booked_from_waitlist",
                details={
                    "waitlist_entry_id": str(waitlist_entry_id),
                    "original_preferred_start": entry.preferred_start_time.isoformat(),
                    "actual_start_time": actual_start_time.isoformat()
                },
                success=True
            )
            
            logger.info(f"Booked appointment from waitlist entry {waitlist_entry_id}")
            return appointment
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to book from waitlist: {e}")
            raise
    
    def remove_from_waitlist(
        self,
        waitlist_entry_id: uuid.UUID,
        removed_by: uuid.UUID,
        reason: str = "Patient request"
    ) -> bool:
        """Remove a patient from the waitlist."""
        try:
            entry = self.waitlist_entries.get(waitlist_entry_id)
            if not entry:
                return False
            
            # Update entry status
            entry.status = WaitlistStatus.CANCELLED
            
            # Log removal
            self.audit_logger.log_event(
                event_type="phi_deleted",
                user_id=removed_by,
                resource_id=waitlist_entry_id,
                resource_type="waitlist_entry",
                action="waitlist_removed",
                details={"reason": reason},
                success=True
            )
            
            logger.info(f"Removed waitlist entry {waitlist_entry_id}: {reason}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove from waitlist: {e}")
            return False
    
    def cleanup_expired_entries(self) -> int:
        """Clean up expired waitlist entries."""
        try:
            expired_entries = []
            current_time = datetime.now(UTC)
            
            for entry in self.waitlist_entries.values():
                if entry.expires_at and current_time > entry.expires_at:
                    if entry.status in [WaitlistStatus.ACTIVE, WaitlistStatus.NOTIFIED]:
                        entry.status = WaitlistStatus.EXPIRED
                        expired_entries.append(entry)
            
            logger.info(f"Cleaned up {len(expired_entries)} expired waitlist entries")
            return len(expired_entries)
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired waitlist entries: {e}")
            return 0
    
    def _find_existing_entry(
        self,
        patient_id: uuid.UUID,
        doctor_id: uuid.UUID,
        preferred_start_time: datetime
    ) -> Optional[WaitlistEntry]:
        """Find existing waitlist entry for patient and time slot."""
        for entry in self.waitlist_entries.values():
            if (entry.patient_id == patient_id and 
                entry.doctor_id == doctor_id and 
                entry.status in [WaitlistStatus.ACTIVE, WaitlistStatus.NOTIFIED] and
                abs((entry.preferred_start_time - preferred_start_time).total_seconds()) < 3600):  # Within 1 hour
                return entry
        return None
    
    def _find_matching_entries(
        self,
        doctor_id: uuid.UUID,
        available_start_time: datetime,
        available_end_time: datetime
    ) -> List[WaitlistEntry]:
        """Find waitlist entries that match available time slot."""
        matching_entries = []
        
        for entry in self.waitlist_entries.values():
            if (entry.doctor_id == doctor_id and 
                entry.status == WaitlistStatus.ACTIVE and
                self._time_slots_overlap(
                    entry.preferred_start_time,
                    entry.preferred_end_time,
                    available_start_time,
                    available_end_time
                )):
                matching_entries.append(entry)
        
        # Sort by creation time (FIFO)
        return sorted(matching_entries, key=lambda x: x.created_at)
    
    def _time_slots_overlap(
        self,
        start1: datetime,
        end1: datetime,
        start2: datetime,
        end2: datetime
    ) -> bool:
        """Check if two time slots overlap."""
        return start1 < end2 and start2 < end1
    
    def get_waitlist_statistics(
        self,
        doctor_id: Optional[uuid.UUID] = None
    ) -> Dict[str, int]:
        """Get waitlist statistics."""
        entries = self.waitlist_entries.values()
        
        if doctor_id:
            entries = [entry for entry in entries if entry.doctor_id == doctor_id]
        
        stats = {
            "total_entries": len(entries),
            "active_entries": len([e for e in entries if e.status == WaitlistStatus.ACTIVE]),
            "notified_entries": len([e for e in entries if e.status == WaitlistStatus.NOTIFIED]),
            "booked_entries": len([e for e in entries if e.status == WaitlistStatus.BOOKED]),
            "expired_entries": len([e for e in entries if e.status == WaitlistStatus.EXPIRED]),
            "cancelled_entries": len([e for e in entries if e.status == WaitlistStatus.CANCELLED])
        }
        
        return stats


def get_waitlist_service(db: Session) -> WaitlistService:
    """Get waitlist service instance."""
    return WaitlistService(db)
