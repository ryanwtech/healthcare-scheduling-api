"""Celery tasks for background processing."""

import uuid
from datetime import datetime

from sqlalchemy.orm import sessionmaker

from app.core.logging import get_logger
from app.db.base import engine
from app.db.models import Appointment, User
from app.workers.celery_app import celery_app

logger = get_logger(__name__)

# Create session factory for database access in tasks
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@celery_app.task
def send_appointment_reminder(appointment_id: str) -> dict:
    """
    Send appointment reminder to patient and doctor.
    
    Args:
        appointment_id: UUID string of the appointment
        
    Returns:
        dict: Task result with status and details
    """
    logger.info(f"Processing appointment reminder for ID: {appointment_id}")
    
    try:
        # Parse appointment ID
        appointment_uuid = uuid.UUID(appointment_id)
        
        # Create database session
        db = SessionLocal()
        
        try:
            # Fetch appointment with related user data
            appointment = (
                db.query(Appointment)
                .join(User, Appointment.patient_id == User.id)
                .filter(Appointment.id == appointment_uuid)
                .first()
            )
            
            if not appointment:
                logger.warning(f"Appointment {appointment_id} not found")
                return {
                    "status": "error",
                    "message": "Appointment not found",
                    "appointment_id": appointment_id
                }
            
            # Get doctor information
            doctor = (
                db.query(User)
                .join(Appointment, User.id == Appointment.doctor_id)
                .filter(Appointment.id == appointment_uuid)
                .first()
            )
            
            if not doctor:
                logger.warning(f"Doctor not found for appointment {appointment_id}")
                return {
                    "status": "error",
                    "message": "Doctor not found",
                    "appointment_id": appointment_id
                }
            
            # Format appointment time for display
            start_time_utc = appointment.start_time.strftime("%Y-%m-%d %H:%M UTC")
            
            # Log reminder details
            logger.info(
                "Appointment reminder details",
                appointment_id=appointment_id,
                patient_email=appointment.patient.email,
                patient_name=appointment.patient.full_name,
                doctor_email=doctor.email,
                doctor_name=doctor.full_name,
                start_time=start_time_utc,
                status=appointment.status.value
            )
            
            # TODO: Integrate with email/SMS providers here
            # For now, just log the reminder details
            logger.info(
                f"REMINDER: Patient {appointment.patient.full_name} ({appointment.patient.email}) "
                f"has an appointment with Dr. {doctor.full_name} ({doctor.email}) "
                f"on {start_time_utc}"
            )
            
            return {
                "status": "success",
                "appointment_id": appointment_id,
                "patient_email": appointment.patient.email,
                "patient_name": appointment.patient.full_name,
                "doctor_email": doctor.email,
                "doctor_name": doctor.full_name,
                "start_time": start_time_utc,
                "reminder_sent_at": datetime.utcnow().isoformat() + "Z"
            }
            
        finally:
            db.close()
            
    except ValueError as e:
        logger.error(f"Invalid appointment ID format: {appointment_id}, error: {e}")
        return {
            "status": "error",
            "message": "Invalid appointment ID format",
            "appointment_id": appointment_id
        }
    except Exception as e:
        logger.error(f"Error processing appointment reminder {appointment_id}: {e}")
        return {
            "status": "error",
            "message": str(e),
            "appointment_id": appointment_id
        }


@celery_app.task
def debug_task():
    """Debug task to test Celery functionality."""
    logger.info("Debug task executed successfully")
    return {"status": "success", "message": "Debug task completed"}


@celery_app.task
def health_check():
    """Health check task for monitoring."""
    logger.info("Celery worker health check")
    return {
        "status": "healthy",
        "worker": "healthcare_scheduling",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }