"""Notification service for scheduling and managing appointment reminders."""

from datetime import datetime, timedelta

from app.core.logging import get_logger
from app.db.models import Appointment
from app.workers.tasks import send_appointment_reminder

logger = get_logger(__name__)


def schedule_reminders(appointment: Appointment) -> None:
    """
    Schedule appointment reminders.
    
    Args:
        appointment: The appointment to schedule reminders for
    """
    try:
        # Only schedule reminders for future appointments
        if appointment.start_time <= datetime.utcnow():
            logger.info(
                f"Skipping reminder scheduling for past appointment {appointment.id}"
            )
            return
        
        # Schedule reminder 24 hours before appointment
        reminder_time = appointment.start_time - timedelta(hours=24)
        
        # Only schedule if reminder time is in the future
        if reminder_time <= datetime.utcnow():
            logger.info(
                f"Appointment {appointment.id} is within 24 hours, skipping reminder"
            )
            return
        
        # Schedule the reminder task
        task_result = send_appointment_reminder.apply_async(
            args=[str(appointment.id)],
            eta=reminder_time
        )
        
        logger.info(
            f"Scheduled reminder for appointment {appointment.id} at {reminder_time.isoformat()}Z",
            task_id=task_result.id,
            appointment_id=str(appointment.id),
            reminder_time=reminder_time.isoformat() + "Z"
        )
        
    except Exception as e:
        logger.error(
            f"Failed to schedule reminders for appointment {appointment.id}: {e}",
            appointment_id=str(appointment.id),
            error=str(e)
        )


def cancel_reminders(appointment: Appointment) -> None:
    """
    Cancel scheduled appointment reminders.
    
    Note: This is a best-effort operation. In a production system,
    you would need to store task IDs to properly cancel them.
    
    Args:
        appointment: The appointment to cancel reminders for
    """
    try:
        logger.info(
            f"Cancelling reminders for appointment {appointment.id}",
            appointment_id=str(appointment.id)
        )
        
        # In a real implementation, you would:
        # 1. Store task IDs when scheduling reminders
        # 2. Use revoke() to cancel specific tasks
        # 3. Handle task cancellation gracefully
        
        # For demo purposes, just log the cancellation
        logger.info(
            f"Reminder cancellation requested for appointment {appointment.id} "
            f"(scheduled for {appointment.start_time.isoformat()}Z)"
        )
        
    except Exception as e:
        logger.error(
            f"Failed to cancel reminders for appointment {appointment.id}: {e}",
            appointment_id=str(appointment.id),
            error=str(e)
        )


def schedule_immediate_reminder(appointment: Appointment) -> None:
    """
    Schedule an immediate reminder (for testing purposes).
    
    Args:
        appointment: The appointment to send immediate reminder for
    """
    try:
        logger.info(f"Scheduling immediate reminder for appointment {appointment.id}")
        
        # Schedule task to run immediately
        task_result = send_appointment_reminder.apply_async(
            args=[str(appointment.id)]
        )
        
        logger.info(
            f"Immediate reminder scheduled for appointment {appointment.id}",
            task_id=task_result.id,
            appointment_id=str(appointment.id)
        )
        
    except Exception as e:
        logger.error(
            f"Failed to schedule immediate reminder for appointment {appointment.id}: {e}",
            appointment_id=str(appointment.id),
            error=str(e)
        )
