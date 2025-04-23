"""Appointments service for booking and managing healthcare appointments."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models import (
    Appointment,
    AppointmentStatus,
    Availability,
    DoctorProfile,
    User,
    UserRole,
)
from app.db.schemas import AppointmentUpdate

logger = get_logger(__name__)


class AppointmentService:
    """Service for managing healthcare appointments."""

    def __init__(self, db: Session):
        self.db = db

    def _check_availability_overlap(
        self, 
        doctor_id: uuid.UUID, 
        start_time: datetime, 
        end_time: datetime
    ) -> bool:
        """
        Check if the requested time slot overlaps with any existing availability.
        
        Args:
            doctor_id: Doctor's ID
            start_time: Requested start time
            end_time: Requested end time
            
        Returns:
            bool: True if there's an overlapping availability slot
        """
        overlapping_availability = (
            self.db.query(Availability)
            .filter(
                Availability.doctor_id == doctor_id,
                Availability.start_time < end_time,
                Availability.end_time > start_time
            )
            .first()
        )
        
        return overlapping_availability is not None

    def _check_appointment_overlap(
        self, 
        doctor_id: uuid.UUID, 
        start_time: datetime, 
        end_time: datetime,
        exclude_id: uuid.UUID | None = None
    ) -> bool:
        """
        Check if the requested time slot overlaps with any existing appointments.
        
        Args:
            doctor_id: Doctor's ID
            start_time: Requested start time
            end_time: Requested end time
            exclude_id: Appointment ID to exclude from check (for updates)
            
        Returns:
            bool: True if there's an overlapping appointment
        """
        query = (
            self.db.query(Appointment)
            .filter(
                Appointment.doctor_id == doctor_id,
                Appointment.status == AppointmentStatus.SCHEDULED,
                Appointment.start_time < end_time,
                Appointment.end_time > start_time
            )
        )
        
        if exclude_id:
            query = query.filter(Appointment.id != exclude_id)
        
        overlapping_appointment = query.first()
        return overlapping_appointment is not None

    def book_appointment(
        self, 
        patient_id: uuid.UUID, 
        doctor_id: uuid.UUID, 
        start_time: datetime, 
        end_time: datetime,
        notes: str | None = None
    ) -> Appointment:
        """
        Book a new appointment for a patient with a doctor.
        
        Uses SERIALIZABLE transaction isolation to prevent race conditions
        when multiple users try to book the same time slot simultaneously.
        
        RACE CONDITION CAVEATS:
        - SERIALIZABLE isolation prevents phantom reads and non-repeatable reads
        - SELECT FOR UPDATE locks prevent concurrent modifications to the same time range
        - However, availability checks are not locked, so there's still a small window
          where two users could book overlapping appointments if they book at the exact
          same time and the availability check passes for both before either commits
        - For production, consider implementing a distributed lock or using a more
          sophisticated conflict detection mechanism
        
        Args:
            patient_id: Patient's ID
            doctor_id: Doctor's ID
            start_time: Appointment start time
            end_time: Appointment end time
            notes: Optional notes for the appointment
            
        Returns:
            Appointment: The created appointment
            
        Raises:
            ValueError: If validation fails
            IntegrityError: If database constraints are violated (race condition)
        """
        # Validate time range
        if start_time >= end_time:
            raise ValueError("Start time must be before end time")
        
        if start_time <= datetime.utcnow():
            raise ValueError("Cannot book appointments in the past")
        
        # Use SERIALIZABLE transaction isolation to prevent race conditions
        try:
            # Set transaction isolation level to SERIALIZABLE
            self.db.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
            
            # Verify doctor exists and is active
            doctor = self.db.query(DoctorProfile).join(User).filter(
                DoctorProfile.id == doctor_id,
                User.is_active
            ).first()
            if not doctor:
                raise ValueError("Doctor not found or inactive")
            
            # Verify patient exists and is active
            patient = self.db.query(User).filter(
                User.id == patient_id,
                User.role == UserRole.PATIENT,
                User.is_active
            ).first()
            if not patient:
                raise ValueError("Patient not found or inactive")
            
            # Check if time slot is within doctor's availability
            if not self._check_availability_overlap(doctor_id, start_time, end_time):
                raise ValueError("Requested time slot is not within doctor's availability")
            
            # Use SELECT FOR UPDATE to lock the time range and prevent concurrent bookings
            # This reduces (but doesn't completely eliminate) race conditions
            overlapping_appointment = (
                self.db.query(Appointment)
                .filter(
                    Appointment.doctor_id == doctor_id,
                    Appointment.status == AppointmentStatus.SCHEDULED,
                    Appointment.start_time < end_time,
                    Appointment.end_time > start_time
                )
                .with_for_update()  # Lock the rows to prevent concurrent modifications
                .first()
            )
            
            if overlapping_appointment:
                raise ValueError("Time slot conflicts with existing appointment")
            
            # Create appointment
            appointment = Appointment(
                doctor_id=doctor_id,
                patient_id=patient_id,
                start_time=start_time,
                end_time=end_time,
                status=AppointmentStatus.SCHEDULED,
                notes=notes
            )
            
            self.db.add(appointment)
            self.db.commit()
            self.db.refresh(appointment)
            
            # Schedule appointment reminders
            from app.services.notifications import schedule_reminders
            schedule_reminders(appointment)
            
            logger.info(f"Booked appointment {appointment.id} for patient {patient_id} with doctor {doctor_id}")
            return appointment
            
        except IntegrityError as e:
            self.db.rollback()
            logger.warning(f"Appointment booking failed due to race condition: {e}")
            raise ValueError("Time slot is no longer available (race condition detected)") from e
        except Exception as e:
            self.db.rollback()
            logger.error(f"Appointment booking failed: {e}")
            raise

    def get_appointment(self, appointment_id: uuid.UUID) -> Appointment | None:
        """Get appointment by ID."""
        return self.db.query(Appointment).filter(Appointment.id == appointment_id).first()

    def cancel_appointment(
        self, 
        appointment_id: uuid.UUID, 
        actor_id: uuid.UUID,
        actor_role: UserRole,
        reason: str | None = None
    ) -> Appointment | None:
        """
        Cancel an appointment.
        
        Args:
            appointment_id: Appointment ID to cancel
            actor_id: ID of the user cancelling
            actor_role: Role of the user cancelling
            reason: Optional cancellation reason
            
        Returns:
            Appointment: The cancelled appointment, or None if not found
            
        Raises:
            ValueError: If cancellation is not allowed
        """
        appointment = self.get_appointment(appointment_id)
        if not appointment:
            return None
        
        # Check if cancellation is allowed
        if appointment.status != AppointmentStatus.SCHEDULED:
            raise ValueError("Only scheduled appointments can be cancelled")
        
        # Check permissions
        can_cancel = (
            actor_role == UserRole.ADMIN or  # Admin can cancel any appointment
            (actor_role == UserRole.DOCTOR and appointment.doctor_id == actor_id) or  # Doctor can cancel their own
            (actor_role == UserRole.PATIENT and appointment.patient_id == actor_id)  # Patient can cancel their own
        )
        
        if not can_cancel:
            raise ValueError("You don't have permission to cancel this appointment")
        
        # Update appointment status
        appointment.status = AppointmentStatus.CANCELLED
        if reason:
            appointment.notes = f"{appointment.notes or ''}\nCancellation reason: {reason}".strip()
        
        self.db.commit()
        self.db.refresh(appointment)
        
        # Cancel appointment reminders
        from app.services.notifications import cancel_reminders
        cancel_reminders(appointment)
        
        logger.info(f"Cancelled appointment {appointment_id} by {actor_role} {actor_id}")
        return appointment

    def update_appointment(
        self, 
        appointment_id: uuid.UUID, 
        appointment_data: AppointmentUpdate,
        actor_id: uuid.UUID,
        actor_role: UserRole
    ) -> Appointment | None:
        """
        Update an appointment.
        
        Args:
            appointment_id: Appointment ID to update
            appointment_data: Update data
            actor_id: ID of the user updating
            actor_role: Role of the user updating
            
        Returns:
            Appointment: The updated appointment, or None if not found
            
        Raises:
            ValueError: If update is not allowed or validation fails
        """
        appointment = self.get_appointment(appointment_id)
        if not appointment:
            return None
        
        # Check permissions
        can_update = (
            actor_role == UserRole.ADMIN or  # Admin can update any appointment
            (actor_role == UserRole.DOCTOR and appointment.doctor_id == actor_id) or  # Doctor can update their own
            (actor_role == UserRole.PATIENT and appointment.patient_id == actor_id)  # Patient can update their own
        )
        
        if not can_update:
            raise ValueError("You don't have permission to update this appointment")
        
        # Store old times for conflict checking (if needed for future validation)
        # old_start_time = appointment.start_time
        # old_end_time = appointment.end_time
        
        # Update fields
        if appointment_data.start_time is not None:
            appointment.start_time = appointment_data.start_time
        if appointment_data.end_time is not None:
            appointment.end_time = appointment_data.end_time
        if appointment_data.status is not None:
            appointment.status = appointment_data.status
        if appointment_data.notes is not None:
            appointment.notes = appointment_data.notes
        
        # Validate updated times
        if appointment.start_time >= appointment.end_time:
            raise ValueError("Start time must be before end time")
        
        # Check for conflicts if times changed
        if (appointment_data.start_time is not None or appointment_data.end_time is not None):
            if not self._check_availability_overlap(appointment.doctor_id, appointment.start_time, appointment.end_time):
                raise ValueError("Updated time slot is not within doctor's availability")
            
            if self._check_appointment_overlap(appointment.doctor_id, appointment.start_time, appointment.end_time, exclude_id=appointment_id):
                raise ValueError("Updated time slot conflicts with existing appointment")
        
        self.db.commit()
        self.db.refresh(appointment)
        
        logger.info(f"Updated appointment {appointment_id} by {actor_role} {actor_id}")
        return appointment

    def list_appointments(
        self,
        doctor_id: uuid.UUID | None = None,
        patient_id: uuid.UUID | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        status: AppointmentStatus | None = None,
        page: int = 1,
        size: int = 50
    ) -> tuple[list[Appointment], int]:
        """
        List appointments with optional filters.
        
        Args:
            doctor_id: Filter by doctor ID
            patient_id: Filter by patient ID
            start_date: Filter by start date (inclusive)
            end_date: Filter by end date (inclusive)
            status: Filter by appointment status
            page: Page number (1-based)
            size: Page size
            
        Returns:
            tuple: (appointments, total_count)
        """
        query = self.db.query(Appointment)
        
        # Apply filters
        if doctor_id:
            query = query.filter(Appointment.doctor_id == doctor_id)
        if patient_id:
            query = query.filter(Appointment.patient_id == patient_id)
        if start_date:
            query = query.filter(Appointment.start_time >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            query = query.filter(Appointment.start_time <= datetime.combine(end_date, datetime.max.time()))
        if status:
            query = query.filter(Appointment.status == status)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        offset = (page - 1) * size
        appointments = (
            query
            .order_by(Appointment.start_time.desc())
            .offset(offset)
            .limit(size)
            .all()
        )
        
        return appointments, total

    def get_appointment_statistics(
        self,
        doctor_id: uuid.UUID | None = None,
        start_date: date | None = None,
        end_date: date | None = None
    ) -> dict[str, Any]:
        """
        Get appointment statistics for a doctor or overall.
        
        Args:
            doctor_id: Doctor ID (optional)
            start_date: Start date for statistics
            end_date: End date for statistics
            
        Returns:
            dict: Statistics including counts by status, total hours, etc.
        """
        query = self.db.query(Appointment)
        
        if doctor_id:
            query = query.filter(Appointment.doctor_id == doctor_id)
        if start_date:
            query = query.filter(Appointment.start_time >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            query = query.filter(Appointment.start_time <= datetime.combine(end_date, datetime.max.time()))
        
        appointments = query.all()
        
        # Calculate statistics
        total_appointments = len(appointments)
        status_counts = {}
        total_hours = 0
        
        for appointment in appointments:
            status = appointment.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
            
            if appointment.status == AppointmentStatus.COMPLETED:
                duration_hours = (appointment.end_time - appointment.start_time).total_seconds() / 3600
                total_hours += duration_hours
        
        return {
            "total_appointments": total_appointments,
            "status_breakdown": status_counts,
            "total_completed_hours": round(total_hours, 2),
            "average_appointment_duration_hours": round(total_hours / max(1, status_counts.get("completed", 0)), 2),
            "completion_rate": round(status_counts.get("completed", 0) / max(1, total_appointments) * 100, 2)
        }
