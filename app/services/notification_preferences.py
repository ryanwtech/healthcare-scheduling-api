"""Notification preferences and settings service."""

import uuid
from datetime import datetime, UTC
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.notification_models import (
    NotificationChannel,
    NotificationPreference,
    NotificationPriority,
    NotificationType,
)
from app.security.audit import AuditLogger, get_audit_logger

logger = get_logger(__name__)


class NotificationPreferenceService:
    """Service for managing user notification preferences."""
    
    def __init__(self, db: Session):
        self.db = db
        self.audit_logger = get_audit_logger(db)
        self._initialize_default_preferences()
    
    def _initialize_default_preferences(self) -> None:
        """Initialize default notification preferences for new users."""
        # This would be called when a new user is created
        pass
    
    def create_default_preferences(
        self,
        user_id: uuid.UUID,
        timezone: str = "UTC"
    ) -> List[NotificationPreference]:
        """Create default notification preferences for a user."""
        try:
            default_preferences = [
                # Email preferences
                {
                    "notification_type": NotificationType.APPOINTMENT_REMINDER,
                    "channel": NotificationChannel.EMAIL,
                    "is_enabled": True,
                    "quiet_hours_start": "22:00",
                    "quiet_hours_end": "08:00",
                    "timezone": timezone,
                    "frequency_limit": 5,
                    "priority_threshold": NotificationPriority.LOW
                },
                {
                    "notification_type": NotificationType.APPOINTMENT_CONFIRMATION,
                    "channel": NotificationChannel.EMAIL,
                    "is_enabled": True,
                    "quiet_hours_start": "22:00",
                    "quiet_hours_end": "08:00",
                    "timezone": timezone,
                    "frequency_limit": 10,
                    "priority_threshold": NotificationPriority.LOW
                },
                {
                    "notification_type": NotificationType.APPOINTMENT_CANCELLATION,
                    "channel": NotificationChannel.EMAIL,
                    "is_enabled": True,
                    "quiet_hours_start": "22:00",
                    "quiet_hours_end": "08:00",
                    "timezone": timezone,
                    "frequency_limit": 10,
                    "priority_threshold": NotificationPriority.LOW
                },
                {
                    "notification_type": NotificationType.WAITLIST_NOTIFICATION,
                    "channel": NotificationChannel.EMAIL,
                    "is_enabled": True,
                    "quiet_hours_start": None,
                    "quiet_hours_end": None,
                    "timezone": timezone,
                    "frequency_limit": 3,
                    "priority_threshold": NotificationPriority.HIGH
                },
                {
                    "notification_type": NotificationType.PAYMENT_REMINDER,
                    "channel": NotificationChannel.EMAIL,
                    "is_enabled": True,
                    "quiet_hours_start": "22:00",
                    "quiet_hours_end": "08:00",
                    "timezone": timezone,
                    "frequency_limit": 2,
                    "priority_threshold": NotificationPriority.NORMAL
                },
                {
                    "notification_type": NotificationType.SYSTEM_ANNOUNCEMENT,
                    "channel": NotificationChannel.EMAIL,
                    "is_enabled": True,
                    "quiet_hours_start": "22:00",
                    "quiet_hours_end": "08:00",
                    "timezone": timezone,
                    "frequency_limit": 1,
                    "priority_threshold": NotificationPriority.NORMAL
                },
                {
                    "notification_type": NotificationType.WELCOME,
                    "channel": NotificationChannel.EMAIL,
                    "is_enabled": True,
                    "quiet_hours_start": None,
                    "quiet_hours_end": None,
                    "timezone": timezone,
                    "frequency_limit": 1,
                    "priority_threshold": NotificationPriority.LOW
                },
                {
                    "notification_type": NotificationType.PROMOTIONAL,
                    "channel": NotificationChannel.EMAIL,
                    "is_enabled": False,
                    "quiet_hours_start": "22:00",
                    "quiet_hours_end": "08:00",
                    "timezone": timezone,
                    "frequency_limit": 1,
                    "priority_threshold": NotificationPriority.LOW
                },
                
                # SMS preferences
                {
                    "notification_type": NotificationType.APPOINTMENT_REMINDER,
                    "channel": NotificationChannel.SMS,
                    "is_enabled": True,
                    "quiet_hours_start": "22:00",
                    "quiet_hours_end": "08:00",
                    "timezone": timezone,
                    "frequency_limit": 3,
                    "priority_threshold": NotificationPriority.NORMAL
                },
                {
                    "notification_type": NotificationType.WAITLIST_NOTIFICATION,
                    "channel": NotificationChannel.SMS,
                    "is_enabled": True,
                    "quiet_hours_start": None,
                    "quiet_hours_end": None,
                    "timezone": timezone,
                    "frequency_limit": 2,
                    "priority_threshold": NotificationPriority.HIGH
                },
                {
                    "notification_type": NotificationType.APPOINTMENT_CANCELLATION,
                    "channel": NotificationChannel.SMS,
                    "is_enabled": True,
                    "quiet_hours_start": "22:00",
                    "quiet_hours_end": "08:00",
                    "timezone": timezone,
                    "frequency_limit": 5,
                    "priority_threshold": NotificationPriority.NORMAL
                },
                {
                    "notification_type": NotificationType.PROMOTIONAL,
                    "channel": NotificationChannel.SMS,
                    "is_enabled": False,
                    "quiet_hours_start": "22:00",
                    "quiet_hours_end": "08:00",
                    "timezone": timezone,
                    "frequency_limit": 1,
                    "priority_threshold": NotificationPriority.LOW
                },
                
                # Push notification preferences
                {
                    "notification_type": NotificationType.APPOINTMENT_REMINDER,
                    "channel": NotificationChannel.PUSH,
                    "is_enabled": True,
                    "quiet_hours_start": "22:00",
                    "quiet_hours_end": "08:00",
                    "timezone": timezone,
                    "frequency_limit": 5,
                    "priority_threshold": NotificationPriority.LOW
                },
                {
                    "notification_type": NotificationType.WAITLIST_NOTIFICATION,
                    "channel": NotificationChannel.PUSH,
                    "is_enabled": True,
                    "quiet_hours_start": None,
                    "quiet_hours_end": None,
                    "timezone": timezone,
                    "frequency_limit": 3,
                    "priority_threshold": NotificationPriority.HIGH
                },
                {
                    "notification_type": NotificationType.SYSTEM_ANNOUNCEMENT,
                    "channel": NotificationChannel.PUSH,
                    "is_enabled": True,
                    "quiet_hours_start": "22:00",
                    "quiet_hours_end": "08:00",
                    "timezone": timezone,
                    "frequency_limit": 2,
                    "priority_threshold": NotificationPriority.NORMAL
                },
                {
                    "notification_type": NotificationType.PROMOTIONAL,
                    "channel": NotificationChannel.PUSH,
                    "is_enabled": False,
                    "quiet_hours_start": "22:00",
                    "quiet_hours_end": "08:00",
                    "timezone": timezone,
                    "frequency_limit": 1,
                    "priority_threshold": NotificationPriority.LOW
                },
                
                # In-app notification preferences
                {
                    "notification_type": NotificationType.APPOINTMENT_REMINDER,
                    "channel": NotificationChannel.IN_APP,
                    "is_enabled": True,
                    "quiet_hours_start": None,
                    "quiet_hours_end": None,
                    "timezone": timezone,
                    "frequency_limit": None,
                    "priority_threshold": NotificationPriority.LOW
                },
                {
                    "notification_type": NotificationType.APPOINTMENT_CONFIRMATION,
                    "channel": NotificationChannel.IN_APP,
                    "is_enabled": True,
                    "quiet_hours_start": None,
                    "quiet_hours_end": None,
                    "timezone": timezone,
                    "frequency_limit": None,
                    "priority_threshold": NotificationPriority.LOW
                },
                {
                    "notification_type": NotificationType.APPOINTMENT_CANCELLATION,
                    "channel": NotificationChannel.IN_APP,
                    "is_enabled": True,
                    "quiet_hours_start": None,
                    "quiet_hours_end": None,
                    "timezone": timezone,
                    "frequency_limit": None,
                    "priority_threshold": NotificationPriority.LOW
                },
                {
                    "notification_type": NotificationType.WAITLIST_NOTIFICATION,
                    "channel": NotificationChannel.IN_APP,
                    "is_enabled": True,
                    "quiet_hours_start": None,
                    "quiet_hours_end": None,
                    "timezone": timezone,
                    "frequency_limit": None,
                    "priority_threshold": NotificationPriority.HIGH
                },
                {
                    "notification_type": NotificationType.PAYMENT_REMINDER,
                    "channel": NotificationChannel.IN_APP,
                    "is_enabled": True,
                    "quiet_hours_start": None,
                    "quiet_hours_end": None,
                    "timezone": timezone,
                    "frequency_limit": None,
                    "priority_threshold": NotificationPriority.NORMAL
                },
                {
                    "notification_type": NotificationType.SYSTEM_ANNOUNCEMENT,
                    "channel": NotificationChannel.IN_APP,
                    "is_enabled": True,
                    "quiet_hours_start": None,
                    "quiet_hours_end": None,
                    "timezone": timezone,
                    "frequency_limit": None,
                    "priority_threshold": NotificationPriority.NORMAL
                },
                {
                    "notification_type": NotificationType.WELCOME,
                    "channel": NotificationChannel.IN_APP,
                    "is_enabled": True,
                    "quiet_hours_start": None,
                    "quiet_hours_end": None,
                    "timezone": timezone,
                    "frequency_limit": None,
                    "priority_threshold": NotificationPriority.LOW
                },
                {
                    "notification_type": NotificationType.PROMOTIONAL,
                    "channel": NotificationChannel.IN_APP,
                    "is_enabled": False,
                    "quiet_hours_start": None,
                    "quiet_hours_end": None,
                    "timezone": timezone,
                    "frequency_limit": None,
                    "priority_threshold": NotificationPriority.LOW
                }
            ]
            
            created_preferences = []
            
            for pref_data in default_preferences:
                # Check if preference already exists
                existing = self.db.query(NotificationPreference).filter(
                    NotificationPreference.user_id == user_id,
                    NotificationPreference.notification_type == pref_data["notification_type"],
                    NotificationPreference.channel == pref_data["channel"]
                ).first()
                
                if not existing:
                    preference = NotificationPreference(
                        id=uuid.uuid4(),
                        user_id=user_id,
                        notification_type=pref_data["notification_type"],
                        channel=pref_data["channel"],
                        is_enabled=pref_data["is_enabled"],
                        quiet_hours_start=pref_data["quiet_hours_start"],
                        quiet_hours_end=pref_data["quiet_hours_end"],
                        timezone=pref_data["timezone"],
                        frequency_limit=pref_data["frequency_limit"],
                        priority_threshold=pref_data["priority_threshold"]
                    )
                    
                    self.db.add(preference)
                    created_preferences.append(preference)
            
            self.db.commit()
            
            # Log preference creation
            self.audit_logger.log_event(
                event_type="phi_created",
                user_id=user_id,
                action="notification_preferences_created",
                details={
                    "preferences_count": len(created_preferences),
                    "timezone": timezone
                },
                success=True
            )
            
            logger.info(f"Created {len(created_preferences)} default notification preferences for user {user_id}")
            return created_preferences
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create default preferences: {e}")
            raise
    
    def get_user_preferences(
        self,
        user_id: uuid.UUID,
        notification_type: Optional[NotificationType] = None,
        channel: Optional[NotificationChannel] = None
    ) -> List[NotificationPreference]:
        """Get user notification preferences."""
        try:
            query = self.db.query(NotificationPreference).filter(
                NotificationPreference.user_id == user_id
            )
            
            if notification_type:
                query = query.filter(NotificationPreference.notification_type == notification_type)
            
            if channel:
                query = query.filter(NotificationPreference.channel == channel)
            
            return query.all()
            
        except Exception as e:
            logger.error(f"Failed to get user preferences: {e}")
            return []
    
    def update_preference(
        self,
        user_id: uuid.UUID,
        notification_type: NotificationType,
        channel: NotificationChannel,
        is_enabled: Optional[bool] = None,
        quiet_hours_start: Optional[str] = None,
        quiet_hours_end: Optional[str] = None,
        timezone: Optional[str] = None,
        frequency_limit: Optional[int] = None,
        priority_threshold: Optional[NotificationPriority] = None,
        updated_by: Optional[uuid.UUID] = None
    ) -> Optional[NotificationPreference]:
        """Update user notification preference."""
        try:
            preference = self.db.query(NotificationPreference).filter(
                NotificationPreference.user_id == user_id,
                NotificationPreference.notification_type == notification_type,
                NotificationPreference.channel == channel
            ).first()
            
            if not preference:
                return None
            
            # Update fields
            if is_enabled is not None:
                preference.is_enabled = is_enabled
            if quiet_hours_start is not None:
                preference.quiet_hours_start = quiet_hours_start
            if quiet_hours_end is not None:
                preference.quiet_hours_end = quiet_hours_end
            if timezone is not None:
                preference.timezone = timezone
            if frequency_limit is not None:
                preference.frequency_limit = frequency_limit
            if priority_threshold is not None:
                preference.priority_threshold = priority_threshold
            
            preference.updated_at = datetime.now(UTC)
            
            self.db.commit()
            
            # Log preference update
            self.audit_logger.log_event(
                event_type="phi_updated",
                user_id=updated_by or user_id,
                resource_id=preference.id,
                resource_type="notification_preference",
                action="preference_updated",
                details={
                    "notification_type": notification_type.value,
                    "channel": channel.value,
                    "is_enabled": preference.is_enabled
                },
                success=True
            )
            
            logger.info(f"Updated notification preference for user {user_id}")
            return preference
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update preference: {e}")
            raise
    
    def bulk_update_preferences(
        self,
        user_id: uuid.UUID,
        preferences: List[Dict],
        updated_by: Optional[uuid.UUID] = None
    ) -> List[NotificationPreference]:
        """Bulk update user notification preferences."""
        try:
            updated_preferences = []
            
            for pref_data in preferences:
                preference = self.db.query(NotificationPreference).filter(
                    NotificationPreference.user_id == user_id,
                    NotificationPreference.notification_type == pref_data["notification_type"],
                    NotificationPreference.channel == pref_data["channel"]
                ).first()
                
                if preference:
                    # Update existing preference
                    if "is_enabled" in pref_data:
                        preference.is_enabled = pref_data["is_enabled"]
                    if "quiet_hours_start" in pref_data:
                        preference.quiet_hours_start = pref_data["quiet_hours_start"]
                    if "quiet_hours_end" in pref_data:
                        preference.quiet_hours_end = pref_data["quiet_hours_end"]
                    if "timezone" in pref_data:
                        preference.timezone = pref_data["timezone"]
                    if "frequency_limit" in pref_data:
                        preference.frequency_limit = pref_data["frequency_limit"]
                    if "priority_threshold" in pref_data:
                        preference.priority_threshold = pref_data["priority_threshold"]
                    
                    preference.updated_at = datetime.now(UTC)
                    updated_preferences.append(preference)
                else:
                    # Create new preference
                    preference = NotificationPreference(
                        id=uuid.uuid4(),
                        user_id=user_id,
                        notification_type=pref_data["notification_type"],
                        channel=pref_data["channel"],
                        is_enabled=pref_data.get("is_enabled", True),
                        quiet_hours_start=pref_data.get("quiet_hours_start"),
                        quiet_hours_end=pref_data.get("quiet_hours_end"),
                        timezone=pref_data.get("timezone", "UTC"),
                        frequency_limit=pref_data.get("frequency_limit"),
                        priority_threshold=pref_data.get("priority_threshold", NotificationPriority.LOW)
                    )
                    
                    self.db.add(preference)
                    updated_preferences.append(preference)
            
            self.db.commit()
            
            # Log bulk update
            self.audit_logger.log_event(
                event_type="phi_updated",
                user_id=updated_by or user_id,
                action="preferences_bulk_updated",
                details={
                    "preferences_count": len(preferences),
                    "updated_count": len(updated_preferences)
                },
                success=True
            )
            
            logger.info(f"Bulk updated {len(updated_preferences)} notification preferences for user {user_id}")
            return updated_preferences
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to bulk update preferences: {e}")
            raise
    
    def get_preference_summary(self, user_id: uuid.UUID) -> Dict:
        """Get user preference summary."""
        try:
            preferences = self.get_user_preferences(user_id)
            
            summary = {
                "user_id": str(user_id),
                "total_preferences": len(preferences),
                "enabled_preferences": len([p for p in preferences if p.is_enabled]),
                "disabled_preferences": len([p for p in preferences if not p.is_enabled]),
                "by_type": {},
                "by_channel": {},
                "channels_enabled": set(),
                "types_enabled": set()
            }
            
            # Group by notification type
            for preference in preferences:
                notification_type = preference.notification_type.value
                if notification_type not in summary["by_type"]:
                    summary["by_type"][notification_type] = {
                        "total": 0,
                        "enabled": 0,
                        "channels": set()
                    }
                
                summary["by_type"][notification_type]["total"] += 1
                if preference.is_enabled:
                    summary["by_type"][notification_type]["enabled"] += 1
                    summary["by_type"][notification_type]["channels"].add(preference.channel.value)
                    summary["channels_enabled"].add(preference.channel.value)
                    summary["types_enabled"].add(notification_type)
            
            # Group by channel
            for preference in preferences:
                channel = preference.channel.value
                if channel not in summary["by_channel"]:
                    summary["by_channel"][channel] = {
                        "total": 0,
                        "enabled": 0,
                        "types": set()
                    }
                
                summary["by_channel"][channel]["total"] += 1
                if preference.is_enabled:
                    summary["by_channel"][channel]["enabled"] += 1
                    summary["by_channel"][channel]["types"].add(preference.notification_type.value)
            
            # Convert sets to lists for JSON serialization
            summary["channels_enabled"] = list(summary["channels_enabled"])
            summary["types_enabled"] = list(summary["types_enabled"])
            
            for type_data in summary["by_type"].values():
                type_data["channels"] = list(type_data["channels"])
            
            for channel_data in summary["by_channel"].values():
                channel_data["types"] = list(channel_data["types"])
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to get preference summary: {e}")
            return {}
    
    def can_send_notification(
        self,
        user_id: uuid.UUID,
        notification_type: NotificationType,
        channel: NotificationChannel,
        priority: NotificationPriority = NotificationPriority.NORMAL
    ) -> bool:
        """Check if notification can be sent based on user preferences."""
        try:
            preference = self.db.query(NotificationPreference).filter(
                NotificationPreference.user_id == user_id,
                NotificationPreference.notification_type == notification_type,
                NotificationPreference.channel == channel
            ).first()
            
            if not preference:
                # No preference found, check if there's a default for this type/channel
                return self._has_default_preference(notification_type, channel)
            
            # Check if enabled
            if not preference.is_enabled:
                return False
            
            # Check priority threshold
            if priority.value < preference.priority_threshold.value:
                return False
            
            # Check quiet hours
            if self._is_quiet_hours(preference):
                return False
            
            # Check frequency limit
            if preference.frequency_limit and self._exceeds_frequency_limit(user_id, channel, preference.frequency_limit):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to check notification permission: {e}")
            return False
    
    def _has_default_preference(self, notification_type: NotificationType, channel: NotificationChannel) -> bool:
        """Check if there's a default preference for this type/channel combination."""
        # Default to allowing if no preference is set
        # In a real implementation, you might have system-wide defaults
        return True
    
    def _is_quiet_hours(self, preference: NotificationPreference) -> bool:
        """Check if current time is within user's quiet hours."""
        try:
            if not preference.quiet_hours_start or not preference.quiet_hours_end:
                return False
            
            # Parse quiet hours (HH:MM format)
            from datetime import time
            start_time = time.fromisoformat(preference.quiet_hours_start)
            end_time = time.fromisoformat(preference.quiet_hours_end)
            
            current_time = datetime.now(UTC).time()
            
            # Handle quiet hours that span midnight
            if start_time <= end_time:
                return start_time <= current_time <= end_time
            else:
                return current_time >= start_time or current_time <= end_time
            
        except Exception as e:
            logger.error(f"Error checking quiet hours: {e}")
            return False
    
    def _exceeds_frequency_limit(
        self,
        user_id: uuid.UUID,
        channel: NotificationChannel,
        frequency_limit: int
    ) -> bool:
        """Check if sending would exceed frequency limit."""
        try:
            # Count notifications sent today
            today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
            
            from app.db.notification_models import Notification, NotificationStatus
            today_count = (
                self.db.query(Notification)
                .filter(
                    Notification.user_id == user_id,
                    Notification.channel == channel,
                    Notification.created_at >= today_start,
                    Notification.status.in_([NotificationStatus.SENT, NotificationStatus.DELIVERED])
                )
                .count()
            )
            
            return today_count >= frequency_limit
            
        except Exception as e:
            logger.error(f"Error checking frequency limit: {e}")
            return False
    
    def reset_to_defaults(
        self,
        user_id: uuid.UUID,
        updated_by: Optional[uuid.UUID] = None
    ) -> List[NotificationPreference]:
        """Reset user preferences to defaults."""
        try:
            # Delete existing preferences
            self.db.query(NotificationPreference).filter(
                NotificationPreference.user_id == user_id
            ).delete()
            
            # Create default preferences
            default_preferences = self.create_default_preferences(user_id)
            
            # Log reset
            self.audit_logger.log_event(
                event_type="phi_updated",
                user_id=updated_by or user_id,
                action="preferences_reset_to_defaults",
                details={"preferences_count": len(default_preferences)},
                success=True
            )
            
            logger.info(f"Reset notification preferences to defaults for user {user_id}")
            return default_preferences
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to reset preferences to defaults: {e}")
            raise


def get_notification_preference_service(db: Session) -> NotificationPreferenceService:
    """Get notification preference service instance."""
    return NotificationPreferenceService(db)
