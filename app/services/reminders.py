"""Enhanced appointment reminder service."""

import uuid
from datetime import datetime, timedelta, UTC
from enum import Enum
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models import Appointment, AppointmentStatus, DoctorProfile, User
from app.security.audit import AuditLogger, get_audit_logger
from app.workers.tasks import send_appointment_reminder

logger = get_logger(__name__)


class ReminderType(str, Enum):
    """Types of appointment reminders."""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    PHONE = "phone"
    IN_APP = "in_app"


class ReminderStatus(str, Enum):
    """Reminder status."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReminderChannel(str, Enum):
    """Reminder delivery channels."""
    EMAIL = "email"
    SMS = "sms"
    PUSH_NOTIFICATION = "push"
    PHONE_CALL = "phone"
    IN_APP_NOTIFICATION = "in_app"


class ReminderTemplate(str, Enum):
    """Reminder message templates."""
    APPOINTMENT_CONFIRMATION = "appointment_confirmation"
    APPOINTMENT_REMINDER_24H = "appointment_reminder_24h"
    APPOINTMENT_REMINDER_2H = "appointment_reminder_2h"
    APPOINTMENT_REMINDER_30M = "appointment_reminder_30m"
    APPOINTMENT_CANCELLATION = "appointment_cancellation"
    APPOINTMENT_RESCHEDULED = "appointment_rescheduled"
    WAITLIST_NOTIFICATION = "waitlist_notification"


class ReminderService:
    """Service for managing appointment reminders."""
    
    def __init__(self, db: Session):
        self.db = db
        self.audit_logger = get_audit_logger(db)
        
        # Reminder schedules (hours before appointment)
        self.reminder_schedules = {
            ReminderTemplate.APPOINTMENT_CONFIRMATION: 0,  # Immediate
            ReminderTemplate.APPOINTMENT_REMINDER_24H: 24,  # 24 hours before
            ReminderTemplate.APPOINTMENT_REMINDER_2H: 2,    # 2 hours before
            ReminderTemplate.APPOINTMENT_REMINDER_30M: 0.5, # 30 minutes before
        }
    
    def schedule_appointment_reminders(
        self,
        appointment: Appointment,
        reminder_types: List[ReminderType] = None,
        custom_schedules: Dict[ReminderTemplate, int] = None
    ) -> List[Dict]:
        """
        Schedule reminders for an appointment.
        
        Args:
            appointment: Appointment to schedule reminders for
            reminder_types: Types of reminders to send
            custom_schedules: Custom reminder schedules
            
        Returns:
            List of scheduled reminder details
        """
        try:
            if not reminder_types:
                reminder_types = [ReminderType.EMAIL, ReminderType.SMS]
            
            scheduled_reminders = []
            schedules = custom_schedules or self.reminder_schedules
            
            for template, hours_before in schedules.items():
                if hours_before == 0:
                    # Send immediately
                    reminder_time = datetime.now(UTC)
                else:
                    # Calculate reminder time
                    reminder_time = appointment.start_time - timedelta(hours=hours_before)
                
                # Only schedule if reminder time is in the future
                if reminder_time > datetime.now(UTC):
                    for reminder_type in reminder_types:
                        reminder_id = uuid.uuid4()
                        
                        # Schedule the reminder task
                        task = send_appointment_reminder.apply_async(
                            args=[str(appointment.id), template.value, reminder_type.value],
                            eta=reminder_time
                        )
                        
                        reminder_info = {
                            "id": reminder_id,
                            "appointment_id": appointment.id,
                            "template": template.value,
                            "type": reminder_type.value,
                            "scheduled_time": reminder_time,
                            "task_id": task.id,
                            "status": ReminderStatus.PENDING.value
                        }
                        
                        scheduled_reminders.append(reminder_info)
                        
                        # Log reminder scheduling
                        self.audit_logger.log_event(
                            event_type="phi_created",
                            user_id=appointment.patient_id,
                            resource_id=appointment.id,
                            resource_type="appointment",
                            action="reminder_scheduled",
                            details={
                                "template": template.value,
                                "type": reminder_type.value,
                                "scheduled_time": reminder_time.isoformat(),
                                "task_id": task.id
                            },
                            success=True
                        )
            
            logger.info(f"Scheduled {len(scheduled_reminders)} reminders for appointment {appointment.id}")
            return scheduled_reminders
            
        except Exception as e:
            logger.error(f"Failed to schedule reminders for appointment {appointment.id}: {e}")
            raise
    
    def send_immediate_reminder(
        self,
        appointment: Appointment,
        template: ReminderTemplate,
        reminder_type: ReminderType,
        custom_message: Optional[str] = None
    ) -> bool:
        """
        Send an immediate reminder.
        
        Args:
            appointment: Appointment to send reminder for
            template: Reminder template
            reminder_type: Type of reminder
            custom_message: Custom message content
            
        Returns:
            True if reminder sent successfully
        """
        try:
            # Get patient and doctor information
            patient = self.db.query(User).filter(User.id == appointment.patient_id).first()
            doctor = self.db.query(User).join(DoctorProfile).filter(
                DoctorProfile.id == appointment.doctor_id
            ).first()
            
            if not patient or not doctor:
                logger.error(f"Patient or doctor not found for appointment {appointment.id}")
                return False
            
            # Generate reminder message
            message = self._generate_reminder_message(
                appointment, patient, doctor, template, custom_message
            )
            
            # Send reminder based on type
            success = self._send_reminder_message(
                patient, doctor, appointment, message, reminder_type
            )
            
            if success:
                # Log reminder sent
                self.audit_logger.log_event(
                    event_type="phi_access",
                    user_id=appointment.patient_id,
                    resource_id=appointment.id,
                    resource_type="appointment",
                    action="reminder_sent",
                    details={
                        "template": template.value,
                        "type": reminder_type.value,
                        "message": message[:100] + "..." if len(message) > 100 else message
                    },
                    success=True
                )
                
                logger.info(f"Sent {reminder_type.value} reminder for appointment {appointment.id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to send immediate reminder: {e}")
            return False
    
    def cancel_appointment_reminders(
        self,
        appointment: Appointment,
        reason: str = "Appointment cancelled"
    ) -> int:
        """
        Cancel all scheduled reminders for an appointment.
        
        Args:
            appointment: Appointment to cancel reminders for
            reason: Reason for cancellation
            
        Returns:
            Number of reminders cancelled
        """
        try:
            # In a real implementation, you would cancel Celery tasks
            # For now, we'll just log the cancellation
            
            cancelled_count = 0
            
            # Log reminder cancellation
            self.audit_logger.log_event(
                event_type="phi_deleted",
                user_id=appointment.patient_id,
                resource_id=appointment.id,
                resource_type="appointment",
                action="reminders_cancelled",
                details={"reason": reason},
                success=True
            )
            
            logger.info(f"Cancelled reminders for appointment {appointment.id}: {reason}")
            return cancelled_count
            
        except Exception as e:
            logger.error(f"Failed to cancel reminders: {e}")
            return 0
    
    def reschedule_appointment_reminders(
        self,
        appointment: Appointment,
        old_start_time: datetime,
        new_start_time: datetime
    ) -> int:
        """
        Reschedule reminders for a rescheduled appointment.
        
        Args:
            appointment: Rescheduled appointment
            old_start_time: Original start time
            new_start_time: New start time
            
        Returns:
            Number of reminders rescheduled
        """
        try:
            # Cancel existing reminders
            self.cancel_appointment_reminders(appointment, "Appointment rescheduled")
            
            # Schedule new reminders
            scheduled_reminders = self.schedule_appointment_reminders(appointment)
            
            # Log rescheduling
            self.audit_logger.log_event(
                event_type="appointment_updated",
                user_id=appointment.patient_id,
                resource_id=appointment.id,
                resource_type="appointment",
                action="reminders_rescheduled",
                details={
                    "old_start_time": old_start_time.isoformat(),
                    "new_start_time": new_start_time.isoformat(),
                    "reminders_scheduled": len(scheduled_reminders)
                },
                success=True
            )
            
            logger.info(f"Rescheduled {len(scheduled_reminders)} reminders for appointment {appointment.id}")
            return len(scheduled_reminders)
            
        except Exception as e:
            logger.error(f"Failed to reschedule reminders: {e}")
            return 0
    
    def send_waitlist_notification(
        self,
        patient: User,
        doctor: User,
        available_start_time: datetime,
        available_end_time: datetime,
        notification_deadline: datetime
    ) -> bool:
        """
        Send waitlist notification to patient.
        
        Args:
            patient: Patient to notify
            doctor: Doctor with available slot
            available_start_time: Available start time
            available_end_time: Available end time
            notification_deadline: Deadline for response
            
        Returns:
            True if notification sent successfully
        """
        try:
            message = self._generate_waitlist_notification_message(
                patient, doctor, available_start_time, available_end_time, notification_deadline
            )
            
            # Send notification via multiple channels
            success = False
            for channel in [ReminderType.EMAIL, ReminderType.SMS, ReminderType.PUSH]:
                if self._send_reminder_message(patient, doctor, None, message, channel):
                    success = True
                    break
            
            if success:
                logger.info(f"Sent waitlist notification to patient {patient.id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to send waitlist notification: {e}")
            return False
    
    def _generate_reminder_message(
        self,
        appointment: Appointment,
        patient: User,
        doctor: User,
        template: ReminderTemplate,
        custom_message: Optional[str] = None
    ) -> str:
        """Generate reminder message based on template."""
        if custom_message:
            return custom_message
        
        templates = {
            ReminderTemplate.APPOINTMENT_CONFIRMATION: (
                f"Appointment Confirmed\n\n"
                f"Hello {patient.full_name},\n\n"
                f"Your appointment with Dr. {doctor.full_name} has been confirmed.\n"
                f"Date: {appointment.start_time.strftime('%A, %B %d, %Y')}\n"
                f"Time: {appointment.start_time.strftime('%I:%M %p')} - {appointment.end_time.strftime('%I:%M %p')}\n"
                f"Location: [Clinic Address]\n\n"
                f"Please arrive 15 minutes early for check-in.\n\n"
                f"Thank you!"
            ),
            ReminderTemplate.APPOINTMENT_REMINDER_24H: (
                f"Appointment Reminder - 24 Hours\n\n"
                f"Hello {patient.full_name},\n\n"
                f"This is a reminder that you have an appointment with Dr. {doctor.full_name} tomorrow.\n"
                f"Date: {appointment.start_time.strftime('%A, %B %d, %Y')}\n"
                f"Time: {appointment.start_time.strftime('%I:%M %p')} - {appointment.end_time.strftime('%I:%M %p')}\n\n"
                f"Please reply 'CONFIRM' to confirm or 'RESCHEDULE' to reschedule.\n\n"
                f"Thank you!"
            ),
            ReminderTemplate.APPOINTMENT_REMINDER_2H: (
                f"Appointment Reminder - 2 Hours\n\n"
                f"Hello {patient.full_name},\n\n"
                f"Your appointment with Dr. {doctor.full_name} is in 2 hours.\n"
                f"Time: {appointment.start_time.strftime('%I:%M %p')} - {appointment.end_time.strftime('%I:%M %p')}\n\n"
                f"Please arrive 15 minutes early for check-in.\n\n"
                f"Thank you!"
            ),
            ReminderTemplate.APPOINTMENT_REMINDER_30M: (
                f"Appointment Reminder - 30 Minutes\n\n"
                f"Hello {patient.full_name},\n\n"
                f"Your appointment with Dr. {doctor.full_name} is in 30 minutes.\n"
                f"Time: {appointment.start_time.strftime('%I:%M %p')} - {appointment.end_time.strftime('%I:%M %p')}\n\n"
                f"Please proceed to check-in.\n\n"
                f"Thank you!"
            ),
            ReminderTemplate.APPOINTMENT_CANCELLATION: (
                f"Appointment Cancelled\n\n"
                f"Hello {patient.full_name},\n\n"
                f"Your appointment with Dr. {doctor.full_name} has been cancelled.\n"
                f"Original Date: {appointment.start_time.strftime('%A, %B %d, %Y')}\n"
                f"Original Time: {appointment.start_time.strftime('%I:%M %p')} - {appointment.end_time.strftime('%I:%M %p')}\n\n"
                f"Please contact us to reschedule.\n\n"
                f"Thank you!"
            ),
            ReminderTemplate.APPOINTMENT_RESCHEDULED: (
                f"Appointment Rescheduled\n\n"
                f"Hello {patient.full_name},\n\n"
                f"Your appointment with Dr. {doctor.full_name} has been rescheduled.\n"
                f"New Date: {appointment.start_time.strftime('%A, %B %d, %Y')}\n"
                f"New Time: {appointment.start_time.strftime('%I:%M %p')} - {appointment.end_time.strftime('%I:%M %p')}\n\n"
                f"Please reply 'CONFIRM' to confirm the new time.\n\n"
                f"Thank you!"
            )
        }
        
        return templates.get(template, "Appointment reminder")
    
    def _generate_waitlist_notification_message(
        self,
        patient: User,
        doctor: User,
        available_start_time: datetime,
        available_end_time: datetime,
        notification_deadline: datetime
    ) -> str:
        """Generate waitlist notification message."""
        return (
            f"Appointment Available - Quick Response Required\n\n"
            f"Hello {patient.full_name},\n\n"
            f"A time slot has become available with Dr. {doctor.full_name}.\n"
            f"Available Time: {available_start_time.strftime('%A, %B %d, %Y at %I:%M %p')} - {available_end_time.strftime('%I:%M %p')}\n"
            f"Response Deadline: {notification_deadline.strftime('%I:%M %p')} today\n\n"
            f"Reply 'BOOK' to book this slot or 'SKIP' to pass.\n\n"
            f"Thank you!"
        )
    
    def _send_reminder_message(
        self,
        patient: User,
        doctor: User,
        appointment: Optional[Appointment],
        message: str,
        reminder_type: ReminderType
    ) -> bool:
        """Send reminder message via specified channel."""
        try:
            if reminder_type == ReminderType.EMAIL:
                return self._send_email_reminder(patient, message)
            elif reminder_type == ReminderType.SMS:
                return self._send_sms_reminder(patient, message)
            elif reminder_type == ReminderType.PUSH:
                return self._send_push_notification(patient, message)
            elif reminder_type == ReminderType.PHONE:
                return self._send_phone_reminder(patient, message)
            elif reminder_type == ReminderType.IN_APP:
                return self._send_in_app_notification(patient, message)
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to send {reminder_type.value} reminder: {e}")
            return False
    
    def _send_email_reminder(self, patient: User, message: str) -> bool:
        """Send email reminder."""
        # In production, integrate with email service (SendGrid, AWS SES, etc.)
        logger.info(f"Email reminder sent to {patient.email}: {message[:50]}...")
        return True
    
    def _send_sms_reminder(self, patient: User, message: str) -> bool:
        """Send SMS reminder."""
        # In production, integrate with SMS service (Twilio, AWS SNS, etc.)
        logger.info(f"SMS reminder sent to {patient.phone or 'N/A'}: {message[:50]}...")
        return True
    
    def _send_push_notification(self, patient: User, message: str) -> bool:
        """Send push notification."""
        # In production, integrate with push notification service (FCM, APNS, etc.)
        logger.info(f"Push notification sent to {patient.id}: {message[:50]}...")
        return True
    
    def _send_phone_reminder(self, patient: User, message: str) -> bool:
        """Send phone call reminder."""
        # In production, integrate with voice service (Twilio Voice, etc.)
        logger.info(f"Phone reminder sent to {patient.phone or 'N/A'}: {message[:50]}...")
        return True
    
    def _send_in_app_notification(self, patient: User, message: str) -> bool:
        """Send in-app notification."""
        # In production, store in database for in-app notification system
        logger.info(f"In-app notification sent to {patient.id}: {message[:50]}...")
        return True


def get_reminder_service(db: Session) -> ReminderService:
    """Get reminder service instance."""
    return ReminderService(db)
