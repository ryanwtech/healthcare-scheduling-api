"""Intelligent notification scheduling and timing service."""

import time
import uuid
from datetime import datetime, timedelta, UTC
from enum import Enum
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.notification_models import (
    Notification,
    NotificationChannel,
    NotificationPriority,
    NotificationStatus,
    NotificationType,
)
from app.security.audit import AuditLogger, get_audit_logger

logger = get_logger(__name__)


class SchedulingStrategy(str, Enum):
    """Notification scheduling strategies."""
    IMMEDIATE = "immediate"
    SCHEDULED = "scheduled"
    SMART_TIMING = "smart_timing"
    USER_PREFERENCE = "user_preference"
    OPTIMAL_ENGAGEMENT = "optimal_engagement"


class NotificationSchedulingService:
    """Service for intelligent notification scheduling and timing."""
    
    def __init__(self, db: Session):
        self.db = db
        self.audit_logger = get_audit_logger(db)
        
        # Optimal sending times by user segment
        self.optimal_times = {
            "general": {
                "email": ["09:00", "13:00", "17:00"],
                "sms": ["10:00", "14:00", "18:00"],
                "push": ["08:00", "12:00", "19:00"],
                "in_app": ["09:00", "15:00", "20:00"]
            },
            "healthcare_professionals": {
                "email": ["07:00", "12:00", "18:00"],
                "sms": ["08:00", "13:00", "19:00"],
                "push": ["07:30", "12:30", "18:30"],
                "in_app": ["08:00", "14:00", "19:00"]
            },
            "patients": {
                "email": ["09:00", "14:00", "20:00"],
                "sms": ["10:00", "15:00", "21:00"],
                "push": ["08:30", "13:30", "19:30"],
                "in_app": ["09:30", "15:30", "20:30"]
            }
        }
        
        # Timezone handling
        self.timezone_offsets = {
            "UTC": 0,
            "EST": -5,
            "PST": -8,
            "CST": -6,
            "MST": -7
        }
    
    def schedule_notification(
        self,
        user_id: uuid.UUID,
        notification_type: NotificationType,
        channel: NotificationChannel,
        content: str,
        subject: Optional[str] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        strategy: SchedulingStrategy = SchedulingStrategy.SMART_TIMING,
        user_data: Optional[Dict] = None,
        custom_send_time: Optional[datetime] = None,
        metadata: Optional[Dict] = None
    ) -> Notification:
        """
        Schedule a notification with intelligent timing.
        
        Args:
            user_id: Target user ID
            notification_type: Type of notification
            channel: Delivery channel
            content: Notification content
            subject: Notification subject
            priority: Notification priority
            strategy: Scheduling strategy
            user_data: User data for personalization
            custom_send_time: Custom send time (overrides strategy)
            metadata: Additional metadata
            
        Returns:
            Scheduled notification
        """
        try:
            # Determine optimal send time
            if custom_send_time:
                send_time = custom_send_time
            else:
                send_time = self._calculate_optimal_send_time(
                    user_id, notification_type, channel, strategy, user_data
                )
            
            # Create notification
            notification = Notification(
                id=uuid.uuid4(),
                user_id=user_id,
                notification_type=notification_type,
                channel=channel,
                priority=priority,
                status=NotificationStatus.PENDING,
                subject=subject,
                content=content,
                metadata=metadata or {},
                scheduled_at=send_time
            )
            
            self.db.add(notification)
            self.db.commit()
            
            # Log scheduling
            self.audit_logger.log_event(
                event_type="phi_created",
                user_id=user_id,
                resource_id=notification.id,
                resource_type="notification",
                action="notification_scheduled",
                details={
                    "notification_type": notification_type.value,
                    "channel": channel.value,
                    "strategy": strategy.value,
                    "scheduled_at": send_time.isoformat()
                },
                success=True
            )
            
            logger.info(f"Scheduled notification {notification.id} for user {user_id} at {send_time}")
            return notification
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to schedule notification: {e}")
            raise
    
    def schedule_bulk_notifications(
        self,
        notifications_data: List[Dict],
        strategy: SchedulingStrategy = SchedulingStrategy.SMART_TIMING
    ) -> List[Notification]:
        """Schedule multiple notifications with intelligent timing."""
        try:
            scheduled_notifications = []
            
            for notification_data in notifications_data:
                notification = self.schedule_notification(
                    user_id=notification_data["user_id"],
                    notification_type=notification_data["notification_type"],
                    channel=notification_data["channel"],
                    content=notification_data["content"],
                    subject=notification_data.get("subject"),
                    priority=notification_data.get("priority", NotificationPriority.NORMAL),
                    strategy=strategy,
                    user_data=notification_data.get("user_data"),
                    custom_send_time=notification_data.get("custom_send_time"),
                    metadata=notification_data.get("metadata")
                )
                
                scheduled_notifications.append(notification)
            
            logger.info(f"Scheduled {len(scheduled_notifications)} notifications")
            return scheduled_notifications
            
        except Exception as e:
            logger.error(f"Failed to schedule bulk notifications: {e}")
            return []
    
    def reschedule_notification(
        self,
        notification_id: uuid.UUID,
        new_send_time: datetime,
        reason: str = "User request"
    ) -> Optional[Notification]:
        """Reschedule an existing notification."""
        try:
            notification = self.db.query(Notification).filter(
                Notification.id == notification_id
            ).first()
            
            if not notification:
                return None
            
            old_send_time = notification.scheduled_at
            notification.scheduled_at = new_send_time
            notification.updated_at = datetime.now(UTC)
            
            self.db.commit()
            
            # Log rescheduling
            self.audit_logger.log_event(
                event_type="phi_updated",
                user_id=notification.user_id,
                resource_id=notification_id,
                resource_type="notification",
                action="notification_rescheduled",
                details={
                    "old_send_time": old_send_time.isoformat() if old_send_time else None,
                    "new_send_time": new_send_time.isoformat(),
                    "reason": reason
                },
                success=True
            )
            
            logger.info(f"Rescheduled notification {notification_id} to {new_send_time}")
            return notification
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to reschedule notification: {e}")
            return None
    
    def cancel_notification(
        self,
        notification_id: uuid.UUID,
        reason: str = "User request"
    ) -> bool:
        """Cancel a scheduled notification."""
        try:
            notification = self.db.query(Notification).filter(
                Notification.id == notification_id
            ).first()
            
            if not notification:
                return False
            
            notification.status = NotificationStatus.CANCELLED
            notification.updated_at = datetime.now(UTC)
            
            self.db.commit()
            
            # Log cancellation
            self.audit_logger.log_event(
                event_type="phi_deleted",
                user_id=notification.user_id,
                resource_id=notification_id,
                resource_type="notification",
                action="notification_cancelled",
                details={"reason": reason},
                success=True
            )
            
            logger.info(f"Cancelled notification {notification_id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to cancel notification: {e}")
            return False
    
    def get_due_notifications(
        self,
        current_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Notification]:
        """Get notifications that are due to be sent."""
        try:
            if current_time is None:
                current_time = datetime.now(UTC)
            
            due_notifications = (
                self.db.query(Notification)
                .filter(
                    Notification.status == NotificationStatus.PENDING,
                    Notification.scheduled_at <= current_time
                )
                .order_by(Notification.scheduled_at)
                .limit(limit)
                .all()
            )
            
            return due_notifications
            
        except Exception as e:
            logger.error(f"Failed to get due notifications: {e}")
            return []
    
    def get_user_notification_schedule(
        self,
        user_id: uuid.UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Notification]:
        """Get user's notification schedule."""
        try:
            query = self.db.query(Notification).filter(
                Notification.user_id == user_id
            )
            
            if start_date:
                query = query.filter(Notification.scheduled_at >= start_date)
            
            if end_date:
                query = query.filter(Notification.scheduled_at <= end_date)
            
            return query.order_by(Notification.scheduled_at).all()
            
        except Exception as e:
            logger.error(f"Failed to get user notification schedule: {e}")
            return []
    
    def _calculate_optimal_send_time(
        self,
        user_id: uuid.UUID,
        notification_type: NotificationType,
        channel: NotificationChannel,
        strategy: SchedulingStrategy,
        user_data: Optional[Dict]
    ) -> datetime:
        """Calculate optimal send time for notification."""
        try:
            current_time = datetime.now(UTC)
            
            if strategy == SchedulingStrategy.IMMEDIATE:
                return current_time
            
            elif strategy == SchedulingStrategy.SCHEDULED:
                # Default to 1 hour from now
                return current_time + timedelta(hours=1)
            
            elif strategy == SchedulingStrategy.SMART_TIMING:
                return self._calculate_smart_timing(
                    user_id, notification_type, channel, user_data
                )
            
            elif strategy == SchedulingStrategy.USER_PREFERENCE:
                return self._calculate_user_preference_timing(
                    user_id, notification_type, channel, user_data
                )
            
            elif strategy == SchedulingStrategy.OPTIMAL_ENGAGEMENT:
                return self._calculate_optimal_engagement_timing(
                    user_id, notification_type, channel, user_data
                )
            
            else:
                # Default to smart timing
                return self._calculate_smart_timing(
                    user_id, notification_type, channel, user_data
                )
            
        except Exception as e:
            logger.error(f"Failed to calculate optimal send time: {e}")
            return datetime.now(UTC) + timedelta(hours=1)
    
    def _calculate_smart_timing(
        self,
        user_id: uuid.UUID,
        notification_type: NotificationType,
        channel: NotificationChannel,
        user_data: Optional[Dict]
    ) -> datetime:
        """Calculate smart timing based on user behavior and preferences."""
        try:
            current_time = datetime.now(UTC)
            user_timezone = user_data.get("timezone", "UTC") if user_data else "UTC"
            user_segment = user_data.get("user_segment", "general") if user_data else "general"
            
            # Get optimal times for user segment and channel
            optimal_times = self.optimal_times.get(user_segment, self.optimal_times["general"])
            channel_times = optimal_times.get(channel.value, optimal_times["email"])
            
            # Convert to datetime objects for today
            today = current_time.date()
            optimal_datetimes = []
            
            for time_str in channel_times:
                hour, minute = map(int, time_str.split(":"))
                optimal_time = datetime.combine(today, datetime.min.time().replace(hour=hour, minute=minute))
                optimal_time = optimal_time.replace(tzinfo=UTC)
                
                # If time has passed today, schedule for tomorrow
                if optimal_time <= current_time:
                    optimal_time += timedelta(days=1)
                
                optimal_datetimes.append(optimal_time)
            
            # Choose the earliest optimal time
            if optimal_datetimes:
                return min(optimal_datetimes)
            else:
                # Fallback to 1 hour from now
                return current_time + timedelta(hours=1)
            
        except Exception as e:
            logger.error(f"Failed to calculate smart timing: {e}")
            return datetime.now(UTC) + timedelta(hours=1)
    
    def _calculate_user_preference_timing(
        self,
        user_id: uuid.UUID,
        notification_type: NotificationType,
        channel: NotificationChannel,
        user_data: Optional[Dict]
    ) -> datetime:
        """Calculate timing based on user preferences."""
        try:
            current_time = datetime.now(UTC)
            
            # Get user's quiet hours
            quiet_start = user_data.get("quiet_hours_start") if user_data else None
            quiet_end = user_data.get("quiet_hours_end") if user_data else None
            
            if quiet_start and quiet_end:
                # Parse quiet hours
                from datetime import time
                start_time = time.fromisoformat(quiet_start)
                end_time = time.fromisoformat(quiet_end)
                
                # Find next available time outside quiet hours
                next_available = self._find_next_available_time(
                    current_time, start_time, end_time
                )
                
                return next_available
            else:
                # No quiet hours, use smart timing
                return self._calculate_smart_timing(
                    user_id, notification_type, channel, user_data
                )
            
        except Exception as e:
            logger.error(f"Failed to calculate user preference timing: {e}")
            return datetime.now(UTC) + timedelta(hours=1)
    
    def _calculate_optimal_engagement_timing(
        self,
        user_id: uuid.UUID,
        notification_type: NotificationType,
        channel: NotificationChannel,
        user_data: Optional[Dict]
    ) -> datetime:
        """Calculate timing for optimal engagement based on historical data."""
        try:
            # This would analyze historical engagement data
            # For now, use smart timing as fallback
            return self._calculate_smart_timing(
                user_id, notification_type, channel, user_data
            )
            
        except Exception as e:
            logger.error(f"Failed to calculate optimal engagement timing: {e}")
            return datetime.now(UTC) + timedelta(hours=1)
    
    def _find_next_available_time(
        self,
        current_time: datetime,
        quiet_start: time,
        quiet_end: time
    ) -> datetime:
        """Find next available time outside quiet hours."""
        try:
            from datetime import time
            
            # Check if current time is in quiet hours
            current_time_only = current_time.time()
            
            if quiet_start <= quiet_end:
                # Quiet hours don't span midnight
                if quiet_start <= current_time_only <= quiet_end:
                    # Currently in quiet hours, schedule for after quiet end
                    next_available = current_time.replace(
                        hour=quiet_end.hour,
                        minute=quiet_end.minute,
                        second=0,
                        microsecond=0
                    )
                    if next_available <= current_time:
                        next_available += timedelta(days=1)
                    return next_available
                else:
                    # Not in quiet hours, schedule for next optimal time
                    return current_time + timedelta(hours=1)
            else:
                # Quiet hours span midnight
                if current_time_only >= quiet_start or current_time_only <= quiet_end:
                    # Currently in quiet hours, schedule for after quiet end
                    next_available = current_time.replace(
                        hour=quiet_end.hour,
                        minute=quiet_end.minute,
                        second=0,
                        microsecond=0
                    )
                    if next_available <= current_time:
                        next_available += timedelta(days=1)
                    return next_available
                else:
                    # Not in quiet hours, schedule for next optimal time
                    return current_time + timedelta(hours=1)
            
        except Exception as e:
            logger.error(f"Failed to find next available time: {e}")
            return datetime.now(UTC) + timedelta(hours=1)
    
    def get_scheduling_statistics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict:
        """Get notification scheduling statistics."""
        try:
            query = self.db.query(Notification)
            
            if start_date:
                query = query.filter(Notification.created_at >= start_date)
            
            if end_date:
                query = query.filter(Notification.created_at <= end_date)
            
            notifications = query.all()
            
            stats = {
                "total_scheduled": len(notifications),
                "by_status": {},
                "by_type": {},
                "by_channel": {},
                "by_priority": {},
                "scheduled_today": 0,
                "scheduled_this_week": 0,
                "scheduled_this_month": 0
            }
            
            current_time = datetime.now(UTC)
            today_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
            week_start = today_start - timedelta(days=today_start.weekday())
            month_start = today_start.replace(day=1)
            
            for notification in notifications:
                # Count by status
                status = notification.status.value
                stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
                
                # Count by type
                notification_type = notification.notification_type.value
                stats["by_type"][notification_type] = stats["by_type"].get(notification_type, 0) + 1
                
                # Count by channel
                channel = notification.channel.value
                stats["by_channel"][channel] = stats["by_channel"].get(channel, 0) + 1
                
                # Count by priority
                priority = notification.priority.value
                stats["by_priority"][priority] = stats["by_priority"].get(priority, 0) + 1
                
                # Count by time period
                if notification.scheduled_at:
                    if notification.scheduled_at >= today_start:
                        stats["scheduled_today"] += 1
                    if notification.scheduled_at >= week_start:
                        stats["scheduled_this_week"] += 1
                    if notification.scheduled_at >= month_start:
                        stats["scheduled_this_month"] += 1
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get scheduling statistics: {e}")
            return {}


def get_notification_scheduling_service(db: Session) -> NotificationSchedulingService:
    """Get notification scheduling service instance."""
    return NotificationSchedulingService(db)
