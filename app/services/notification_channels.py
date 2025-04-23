"""Notification delivery channels service."""

import uuid
from datetime import datetime, UTC
from enum import Enum
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.notification_models import (
    Notification,
    NotificationChannel,
    NotificationLog,
    NotificationStatus,
)
from app.security.audit import AuditLogger, get_audit_logger

logger = get_logger(__name__)


class ChannelProvider(str, Enum):
    """Notification channel providers."""
    SENDGRID = "sendgrid"
    TWILIO = "twilio"
    FIREBASE = "firebase"
    APNS = "apns"
    FCM = "fcm"
    SMTP = "smtp"
    WEBHOOK = "webhook"


class NotificationChannelService:
    """Service for managing notification delivery channels."""
    
    def __init__(self, db: Session):
        self.db = db
        self.audit_logger = get_audit_logger(db)
        
        # Channel configurations
        self.channel_configs = {
            NotificationChannel.EMAIL: {
                "provider": ChannelProvider.SENDGRID,
                "enabled": True,
                "retry_attempts": 3,
                "timeout_seconds": 30
            },
            NotificationChannel.SMS: {
                "provider": ChannelProvider.TWILIO,
                "enabled": True,
                "retry_attempts": 3,
                "timeout_seconds": 30
            },
            NotificationChannel.PUSH: {
                "provider": ChannelProvider.FIREBASE,
                "enabled": True,
                "retry_attempts": 3,
                "timeout_seconds": 30
            },
            NotificationChannel.IN_APP: {
                "provider": ChannelProvider.WEBHOOK,
                "enabled": True,
                "retry_attempts": 1,
                "timeout_seconds": 10
            },
            NotificationChannel.PHONE: {
                "provider": ChannelProvider.TWILIO,
                "enabled": True,
                "retry_attempts": 2,
                "timeout_seconds": 60
            },
            NotificationChannel.WEBHOOK: {
                "provider": ChannelProvider.WEBHOOK,
                "enabled": True,
                "retry_attempts": 3,
                "timeout_seconds": 30
            }
        }
    
    def send_notification(
        self,
        notification: Notification,
        user_data: Dict,
        channel_override: Optional[NotificationChannel] = None
    ) -> bool:
        """
        Send notification through the specified channel.
        
        Args:
            notification: Notification to send
            user_data: User data for personalization
            channel_override: Override the notification's channel
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            channel = channel_override or notification.channel
            config = self.channel_configs.get(channel)
            
            if not config or not config["enabled"]:
                logger.warning(f"Channel {channel} is not enabled or configured")
                return False
            
            # Log delivery attempt
            self._log_delivery_attempt(notification, channel, "attempting")
            
            # Send based on channel
            success = False
            provider_response = None
            
            if channel == NotificationChannel.EMAIL:
                success, provider_response = self._send_email(notification, user_data)
            elif channel == NotificationChannel.SMS:
                success, provider_response = self._send_sms(notification, user_data)
            elif channel == NotificationChannel.PUSH:
                success, provider_response = self._send_push(notification, user_data)
            elif channel == NotificationChannel.IN_APP:
                success, provider_response = self._send_in_app(notification, user_data)
            elif channel == NotificationChannel.PHONE:
                success, provider_response = self._send_phone(notification, user_data)
            elif channel == NotificationChannel.WEBHOOK:
                success, provider_response = self._send_webhook(notification, user_data)
            
            # Update notification status
            if success:
                notification.status = NotificationStatus.SENT
                notification.sent_at = datetime.now(UTC)
                notification.delivered_at = datetime.now(UTC)
            else:
                notification.delivery_attempts += 1
                if notification.delivery_attempts >= notification.max_attempts:
                    notification.status = NotificationStatus.FAILED
                    notification.error_message = provider_response.get("error", "Max attempts reached")
            
            # Log delivery result
            self._log_delivery_result(
                notification, channel, success, provider_response
            )
            
            self.db.commit()
            
            # Log audit event
            self.audit_logger.log_event(
                event_type="phi_access",
                user_id=notification.user_id,
                resource_id=notification.id,
                resource_type="notification",
                action="notification_sent",
                details={
                    "channel": channel.value,
                    "success": success,
                    "attempt": notification.delivery_attempts
                },
                success=success
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to send notification {notification.id}: {e}")
            self._log_delivery_result(notification, channel, False, {"error": str(e)})
            return False
    
    def send_bulk_notifications(
        self,
        notifications: List[Notification],
        user_data_map: Dict[uuid.UUID, Dict]
    ) -> Dict[str, int]:
        """
        Send multiple notifications in bulk.
        
        Args:
            notifications: List of notifications to send
            user_data_map: Map of user_id to user data
            
        Returns:
            Statistics of bulk send operation
        """
        try:
            stats = {
                "total": len(notifications),
                "sent": 0,
                "failed": 0,
                "skipped": 0
            }
            
            for notification in notifications:
                user_data = user_data_map.get(notification.user_id, {})
                
                # Check if notification should be sent
                if not self._should_send_notification(notification, user_data):
                    stats["skipped"] += 1
                    continue
                
                # Send notification
                success = self.send_notification(notification, user_data)
                
                if success:
                    stats["sent"] += 1
                else:
                    stats["failed"] += 1
            
            logger.info(f"Bulk notification send completed: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to send bulk notifications: {e}")
            return {"total": 0, "sent": 0, "failed": 0, "skipped": 0}
    
    def _send_email(self, notification: Notification, user_data: Dict) -> Tuple[bool, Dict]:
        """Send email notification."""
        try:
            # In production, integrate with SendGrid, AWS SES, or similar
            # For now, simulate email sending
            
            email_data = {
                "to": user_data.get("email", "user@example.com"),
                "subject": notification.subject or "Notification",
                "content": notification.content,
                "html_content": notification.html_content
            }
            
            # Simulate email sending
            logger.info(f"Email sent to {email_data['to']}: {email_data['subject']}")
            
            return True, {
                "provider": "sendgrid",
                "message_id": f"email_{uuid.uuid4()}",
                "status": "sent"
            }
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False, {"error": str(e)}
    
    def _send_sms(self, notification: Notification, user_data: Dict) -> Tuple[bool, Dict]:
        """Send SMS notification."""
        try:
            # In production, integrate with Twilio, AWS SNS, or similar
            # For now, simulate SMS sending
            
            phone_number = user_data.get("phone", "+1234567890")
            
            # Simulate SMS sending
            logger.info(f"SMS sent to {phone_number}: {notification.content[:50]}...")
            
            return True, {
                "provider": "twilio",
                "message_id": f"sms_{uuid.uuid4()}",
                "status": "sent"
            }
            
        except Exception as e:
            logger.error(f"Failed to send SMS: {e}")
            return False, {"error": str(e)}
    
    def _send_push(self, notification: Notification, user_data: Dict) -> Tuple[bool, Dict]:
        """Send push notification."""
        try:
            # In production, integrate with Firebase FCM, APNS, or similar
            # For now, simulate push notification
            
            device_token = user_data.get("device_token", "device_token_123")
            
            push_data = {
                "title": notification.subject or "Notification",
                "body": notification.content,
                "data": notification.metadata or {}
            }
            
            # Simulate push notification
            logger.info(f"Push notification sent to {device_token}: {push_data['title']}")
            
            return True, {
                "provider": "firebase",
                "message_id": f"push_{uuid.uuid4()}",
                "status": "sent"
            }
            
        except Exception as e:
            logger.error(f"Failed to send push notification: {e}")
            return False, {"error": str(e)}
    
    def _send_in_app(self, notification: Notification, user_data: Dict) -> Tuple[bool, Dict]:
        """Send in-app notification."""
        try:
            # In production, this would store the notification in the database
            # and notify the user via WebSocket or similar real-time mechanism
            
            in_app_data = {
                "user_id": str(notification.user_id),
                "title": notification.subject or "Notification",
                "content": notification.content,
                "type": notification.notification_type.value,
                "priority": notification.priority.value,
                "metadata": notification.metadata or {}
            }
            
            # Simulate in-app notification
            logger.info(f"In-app notification created for user {notification.user_id}")
            
            return True, {
                "provider": "in_app",
                "message_id": f"in_app_{uuid.uuid4()}",
                "status": "created"
            }
            
        except Exception as e:
            logger.error(f"Failed to send in-app notification: {e}")
            return False, {"error": str(e)}
    
    def _send_phone(self, notification: Notification, user_data: Dict) -> Tuple[bool, Dict]:
        """Send phone call notification."""
        try:
            # In production, integrate with Twilio Voice, AWS Connect, or similar
            # For now, simulate phone call
            
            phone_number = user_data.get("phone", "+1234567890")
            
            # Simulate phone call
            logger.info(f"Phone call initiated to {phone_number}")
            
            return True, {
                "provider": "twilio_voice",
                "call_id": f"call_{uuid.uuid4()}",
                "status": "initiated"
            }
            
        except Exception as e:
            logger.error(f"Failed to send phone call: {e}")
            return False, {"error": str(e)}
    
    def _send_webhook(self, notification: Notification, user_data: Dict) -> Tuple[bool, Dict]:
        """Send webhook notification."""
        try:
            # In production, send HTTP POST to configured webhook URL
            # For now, simulate webhook call
            
            webhook_url = user_data.get("webhook_url", "https://example.com/webhook")
            
            webhook_data = {
                "notification_id": str(notification.id),
                "user_id": str(notification.user_id),
                "type": notification.notification_type.value,
                "channel": notification.channel.value,
                "content": notification.content,
                "metadata": notification.metadata or {}
            }
            
            # Simulate webhook call
            logger.info(f"Webhook sent to {webhook_url}")
            
            return True, {
                "provider": "webhook",
                "url": webhook_url,
                "status": "sent"
            }
            
        except Exception as e:
            logger.error(f"Failed to send webhook: {e}")
            return False, {"error": str(e)}
    
    def _should_send_notification(self, notification: Notification, user_data: Dict) -> bool:
        """Check if notification should be sent based on user preferences and conditions."""
        try:
            # Check if user has email/phone for the channel
            if notification.channel == NotificationChannel.EMAIL:
                if not user_data.get("email"):
                    return False
            elif notification.channel == NotificationChannel.SMS:
                if not user_data.get("phone"):
                    return False
            elif notification.channel == NotificationChannel.PUSH:
                if not user_data.get("device_token"):
                    return False
            elif notification.channel == NotificationChannel.PHONE:
                if not user_data.get("phone"):
                    return False
            
            # Check quiet hours
            if self._is_quiet_hours(notification, user_data):
                return False
            
            # Check frequency limits
            if self._exceeds_frequency_limit(notification, user_data):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking notification send conditions: {e}")
            return False
    
    def _is_quiet_hours(self, notification: Notification, user_data: Dict) -> bool:
        """Check if current time is within user's quiet hours."""
        try:
            # Get user's quiet hours from preferences
            quiet_start = user_data.get("quiet_hours_start")
            quiet_end = user_data.get("quiet_hours_end")
            
            if not quiet_start or not quiet_end:
                return False
            
            # Parse quiet hours (HH:MM format)
            from datetime import time
            start_time = time.fromisoformat(quiet_start)
            end_time = time.fromisoformat(quiet_end)
            
            current_time = datetime.now(UTC).time()
            
            # Handle quiet hours that span midnight
            if start_time <= end_time:
                return start_time <= current_time <= end_time
            else:
                return current_time >= start_time or current_time <= end_time
            
        except Exception as e:
            logger.error(f"Error checking quiet hours: {e}")
            return False
    
    def _exceeds_frequency_limit(self, notification: Notification, user_data: Dict) -> bool:
        """Check if sending would exceed user's frequency limit."""
        try:
            frequency_limit = user_data.get("frequency_limit")
            if not frequency_limit:
                return False
            
            # Count notifications sent today
            today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
            today_count = (
                self.db.query(Notification)
                .filter(
                    Notification.user_id == notification.user_id,
                    Notification.channel == notification.channel,
                    Notification.created_at >= today_start,
                    Notification.status.in_([NotificationStatus.SENT, NotificationStatus.DELIVERED])
                )
                .count()
            )
            
            return today_count >= frequency_limit
            
        except Exception as e:
            logger.error(f"Error checking frequency limit: {e}")
            return False
    
    def _log_delivery_attempt(self, notification: Notification, channel: NotificationChannel, status: str) -> None:
        """Log delivery attempt."""
        try:
            log_entry = NotificationLog(
                notification_id=notification.id,
                user_id=notification.user_id,
                channel=channel,
                status=status,
                attempt_number=notification.delivery_attempts + 1,
                provider=self.channel_configs[channel]["provider"].value
            )
            
            self.db.add(log_entry)
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to log delivery attempt: {e}")
    
    def _log_delivery_result(
        self,
        notification: Notification,
        channel: NotificationChannel,
        success: bool,
        provider_response: Dict
    ) -> None:
        """Log delivery result."""
        try:
            status = "delivered" if success else "failed"
            error_code = provider_response.get("error_code") if not success else None
            error_message = provider_response.get("error") if not success else None
            
            log_entry = NotificationLog(
                notification_id=notification.id,
                user_id=notification.user_id,
                channel=channel,
                status=status,
                attempt_number=notification.delivery_attempts,
                provider=self.channel_configs[channel]["provider"].value,
                provider_id=provider_response.get("message_id"),
                provider_response=provider_response,
                error_code=error_code,
                error_message=error_message
            )
            
            self.db.add(log_entry)
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to log delivery result: {e}")
    
    def get_delivery_stats(
        self,
        user_id: Optional[uuid.UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict:
        """Get delivery statistics."""
        try:
            query = self.db.query(NotificationLog)
            
            if user_id:
                query = query.filter(NotificationLog.user_id == user_id)
            
            if start_date:
                query = query.filter(NotificationLog.created_at >= start_date)
            
            if end_date:
                query = query.filter(NotificationLog.created_at <= end_date)
            
            logs = query.all()
            
            stats = {
                "total_attempts": len(logs),
                "delivered": len([log for log in logs if log.status == "delivered"]),
                "failed": len([log for log in logs if log.status == "failed"]),
                "by_channel": {},
                "by_provider": {}
            }
            
            # Group by channel
            for log in logs:
                channel = log.channel.value
                if channel not in stats["by_channel"]:
                    stats["by_channel"][channel] = {"total": 0, "delivered": 0, "failed": 0}
                
                stats["by_channel"][channel]["total"] += 1
                if log.status == "delivered":
                    stats["by_channel"][channel]["delivered"] += 1
                elif log.status == "failed":
                    stats["by_channel"][channel]["failed"] += 1
            
            # Group by provider
            for log in logs:
                provider = log.provider or "unknown"
                if provider not in stats["by_provider"]:
                    stats["by_provider"][provider] = {"total": 0, "delivered": 0, "failed": 0}
                
                stats["by_provider"][provider]["total"] += 1
                if log.status == "delivered":
                    stats["by_provider"][provider]["delivered"] += 1
                elif log.status == "failed":
                    stats["by_provider"][provider]["failed"] += 1
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get delivery stats: {e}")
            return {}


def get_notification_channel_service(db: Session) -> NotificationChannelService:
    """Get notification channel service instance."""
    return NotificationChannelService(db)
