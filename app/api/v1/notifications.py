"""Comprehensive notification system API endpoints."""

import uuid
from datetime import datetime, timedelta, UTC
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.core.security import get_current_user, role_required
from app.db.base import get_db
from app.db.models import User, UserRole
from app.db.notification_models import (
    NotificationChannel,
    NotificationPriority,
    NotificationStatus,
    NotificationType,
)
from app.services.engagement_analytics import get_engagement_analytics_service
from app.services.notification_channels import get_notification_channel_service
from app.services.notification_preferences import get_notification_preference_service
from app.services.notification_scheduling import (
    SchedulingStrategy,
    get_notification_scheduling_service,
)
from app.services.notification_templates import get_notification_template_service
from app.services.real_time_notifications import get_real_time_notification_service

router = APIRouter()


# Pydantic models for request/response
class NotificationRequest(BaseModel):
    """Request model for creating notifications."""
    user_id: uuid.UUID
    notification_type: NotificationType
    channel: NotificationChannel
    content: str
    subject: Optional[str] = None
    priority: NotificationPriority = NotificationPriority.NORMAL
    scheduled_at: Optional[datetime] = None
    metadata: Optional[Dict] = None


class BulkNotificationRequest(BaseModel):
    """Request model for bulk notifications."""
    user_ids: List[uuid.UUID]
    notification_type: NotificationType
    channel: NotificationChannel
    content: str
    subject: Optional[str] = None
    priority: NotificationPriority = NotificationPriority.NORMAL
    scheduled_at: Optional[datetime] = None
    metadata: Optional[Dict] = None


class NotificationTemplateRequest(BaseModel):
    """Request model for creating notifications from templates."""
    user_id: uuid.UUID
    template_id: uuid.UUID
    variables: Optional[Dict] = None
    scheduled_at: Optional[datetime] = None


class NotificationPreferenceRequest(BaseModel):
    """Request model for updating notification preferences."""
    notification_type: NotificationType
    channel: NotificationChannel
    is_enabled: bool = True
    quiet_hours_start: Optional[str] = Field(None, pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$")
    quiet_hours_end: Optional[str] = Field(None, pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$")
    timezone: Optional[str] = "UTC"
    frequency_limit: Optional[int] = Field(None, ge=1, le=100)
    priority_threshold: NotificationPriority = NotificationPriority.LOW


class BulkPreferenceRequest(BaseModel):
    """Request model for bulk preference updates."""
    preferences: List[NotificationPreferenceRequest]


class NotificationResponse(BaseModel):
    """Response model for notifications."""
    id: uuid.UUID
    user_id: uuid.UUID
    notification_type: str
    channel: str
    priority: str
    status: str
    subject: Optional[str]
    content: str
    metadata: Optional[Dict]
    scheduled_at: Optional[datetime]
    sent_at: Optional[datetime]
    delivered_at: Optional[datetime]
    read_at: Optional[datetime]
    created_at: datetime


class EngagementResponse(BaseModel):
    """Response model for engagement data."""
    notification_id: uuid.UUID
    is_read: bool
    is_clicked: bool
    is_responded: bool
    is_dismissed: bool
    read_at: Optional[datetime]
    clicked_at: Optional[datetime]
    responded_at: Optional[datetime]
    dismissed_at: Optional[datetime]


# Notification Management Endpoints
@router.post("/", response_model=NotificationResponse)
async def create_notification(
    request: NotificationRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Create a new notification."""
    try:
        scheduling_service = get_notification_scheduling_service(db)
        
        # Create notification
        notification = scheduling_service.schedule_notification(
            user_id=request.user_id,
            notification_type=request.notification_type,
            channel=request.channel,
            content=request.content,
            subject=request.subject,
            priority=request.priority,
            strategy=SchedulingStrategy.IMMEDIATE if request.scheduled_at is None else SchedulingStrategy.SCHEDULED,
            custom_send_time=request.scheduled_at,
            metadata=request.metadata
        )
        
        return NotificationResponse(
            id=notification.id,
            user_id=notification.user_id,
            notification_type=notification.notification_type.value,
            channel=notification.channel.value,
            priority=notification.priority.value,
            status=notification.status.value,
            subject=notification.subject,
            content=notification.content,
            metadata=notification.metadata,
            scheduled_at=notification.scheduled_at,
            sent_at=notification.sent_at,
            delivered_at=notification.delivered_at,
            read_at=notification.read_at,
            created_at=notification.created_at
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create notification: {str(e)}"
        )


@router.post("/bulk", response_model=List[NotificationResponse])
async def create_bulk_notifications(
    request: BulkNotificationRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Create multiple notifications for multiple users."""
    try:
        scheduling_service = get_notification_scheduling_service(db)
        
        # Prepare notifications data
        notifications_data = []
        for user_id in request.user_ids:
            notifications_data.append({
                "user_id": user_id,
                "notification_type": request.notification_type,
                "channel": request.channel,
                "content": request.content,
                "subject": request.subject,
                "priority": request.priority,
                "custom_send_time": request.scheduled_at,
                "metadata": request.metadata
            })
        
        # Create notifications
        notifications = scheduling_service.schedule_bulk_notifications(
            notifications_data=notifications_data,
            strategy=SchedulingStrategy.IMMEDIATE if request.scheduled_at is None else SchedulingStrategy.SCHEDULED
        )
        
        return [
            NotificationResponse(
                id=notification.id,
                user_id=notification.user_id,
                notification_type=notification.notification_type.value,
                channel=notification.channel.value,
                priority=notification.priority.value,
                status=notification.status.value,
                subject=notification.subject,
                content=notification.content,
                metadata=notification.metadata,
                scheduled_at=notification.scheduled_at,
                sent_at=notification.sent_at,
                delivered_at=notification.delivered_at,
                read_at=notification.read_at,
                created_at=notification.created_at
            )
            for notification in notifications
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create bulk notifications: {str(e)}"
        )


@router.post("/from-template", response_model=NotificationResponse)
async def create_notification_from_template(
    request: NotificationTemplateRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Create a notification from a template."""
    try:
        template_service = get_notification_template_service(db)
        scheduling_service = get_notification_scheduling_service(db)
        
        # Get template
        template = template_service.get_template(request.template_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )
        
        # Get user data for personalization
        user = db.query(User).filter(User.id == request.user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_data = {
            "user_name": user.full_name,
            "user_email": user.email,
            "user_phone": getattr(user, 'phone', None)
        }
        
        # Merge with custom variables
        if request.variables:
            user_data.update(request.variables)
        
        # Personalize content
        personalized_content = template_service.personalize_content(
            template, user_data
        )
        
        # Create notification
        notification = scheduling_service.schedule_notification(
            user_id=request.user_id,
            notification_type=template.notification_type,
            channel=template.channel,
            content=personalized_content["content"],
            subject=personalized_content["subject"],
            priority=NotificationPriority.NORMAL,
            strategy=SchedulingStrategy.IMMEDIATE if request.scheduled_at is None else SchedulingStrategy.SCHEDULED,
            custom_send_time=request.scheduled_at,
            metadata={"template_id": str(request.template_id)}
        )
        
        return NotificationResponse(
            id=notification.id,
            user_id=notification.user_id,
            notification_type=notification.notification_type.value,
            channel=notification.channel.value,
            priority=notification.priority.value,
            status=notification.status.value,
            subject=notification.subject,
            content=notification.content,
            metadata=notification.metadata,
            scheduled_at=notification.scheduled_at,
            sent_at=notification.sent_at,
            delivered_at=notification.delivered_at,
            read_at=notification.read_at,
            created_at=notification.created_at
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create notification from template: {str(e)}"
        )


@router.get("/", response_model=List[NotificationResponse])
async def get_notifications(
    user_id: Optional[uuid.UUID] = None,
    notification_type: Optional[NotificationType] = None,
    channel: Optional[NotificationChannel] = None,
    status: Optional[NotificationStatus] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Get notifications with filters."""
    try:
        from app.db.notification_models import Notification
        
        query = db.query(Notification)
        
        # Apply filters
        if user_id:
            query = query.filter(Notification.user_id == user_id)
        elif current_user.role != UserRole.ADMIN:
            # Non-admin users can only see their own notifications
            query = query.filter(Notification.user_id == current_user.id)
        
        if notification_type:
            query = query.filter(Notification.notification_type == notification_type)
        
        if channel:
            query = query.filter(Notification.channel == channel)
        
        if status:
            query = query.filter(Notification.status == status)
        
        # Apply pagination
        notifications = query.order_by(Notification.created_at.desc()).offset(offset).limit(limit).all()
        
        return [
            NotificationResponse(
                id=notification.id,
                user_id=notification.user_id,
                notification_type=notification.notification_type.value,
                channel=notification.channel.value,
                priority=notification.priority.value,
                status=notification.status.value,
                subject=notification.subject,
                content=notification.content,
                metadata=notification.metadata,
                scheduled_at=notification.scheduled_at,
                sent_at=notification.sent_at,
                delivered_at=notification.delivered_at,
                read_at=notification.read_at,
                created_at=notification.created_at
            )
            for notification in notifications
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to get notifications: {str(e)}"
        )


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(
    notification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Get a specific notification."""
    try:
        from app.db.notification_models import Notification
        
        notification = db.query(Notification).filter(Notification.id == notification_id).first()
        
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        
        # Check permissions
        if current_user.role != UserRole.ADMIN and notification.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this notification"
            )
        
        return NotificationResponse(
            id=notification.id,
            user_id=notification.user_id,
            notification_type=notification.notification_type.value,
            channel=notification.channel.value,
            priority=notification.priority.value,
            status=notification.status.value,
            subject=notification.subject,
            content=notification.content,
            metadata=notification.metadata,
            scheduled_at=notification.scheduled_at,
            sent_at=notification.sent_at,
            delivered_at=notification.delivered_at,
            read_at=notification.read_at,
            created_at=notification.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to get notification: {str(e)}"
        )


@router.put("/{notification_id}/reschedule")
async def reschedule_notification(
    notification_id: uuid.UUID,
    new_send_time: datetime,
    reason: str = "User request",
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Reschedule a notification."""
    try:
        scheduling_service = get_notification_scheduling_service(db)
        
        notification = scheduling_service.reschedule_notification(
            notification_id=notification_id,
            new_send_time=new_send_time,
            reason=reason
        )
        
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        
        return {
            "message": "Notification rescheduled successfully",
            "notification_id": str(notification_id),
            "new_send_time": new_send_time.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to reschedule notification: {str(e)}"
        )


@router.delete("/{notification_id}")
async def cancel_notification(
    notification_id: uuid.UUID,
    reason: str = "User request",
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Cancel a notification."""
    try:
        scheduling_service = get_notification_scheduling_service(db)
        
        success = scheduling_service.cancel_notification(
            notification_id=notification_id,
            reason=reason
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        
        return {
            "message": "Notification cancelled successfully",
            "notification_id": str(notification_id)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to cancel notification: {str(e)}"
        )


# Real-time Notifications Endpoints
@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: uuid.UUID,
    db=Depends(get_db)
):
    """WebSocket endpoint for real-time notifications."""
    try:
        real_time_service = get_real_time_notification_service(db)
        
        # Get client info
        client_info = {
            "user_agent": websocket.headers.get("user-agent"),
            "origin": websocket.headers.get("origin"),
            "connected_at": datetime.now(UTC).isoformat()
        }
        
        await real_time_service.handle_websocket_connection(
            websocket, user_id, client_info
        )
        
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")


# Notification Preferences Endpoints
@router.get("/preferences")
async def get_notification_preferences(
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Get user notification preferences."""
    try:
        preference_service = get_notification_preference_service(db)
        
        preferences = preference_service.get_user_preferences(current_user.id)
        
        return {
            "preferences": [
                {
                    "id": str(pref.id),
                    "notification_type": pref.notification_type.value,
                    "channel": pref.channel.value,
                    "is_enabled": pref.is_enabled,
                    "quiet_hours_start": pref.quiet_hours_start,
                    "quiet_hours_end": pref.quiet_hours_end,
                    "timezone": pref.timezone,
                    "frequency_limit": pref.frequency_limit,
                    "priority_threshold": pref.priority_threshold.value
                }
                for pref in preferences
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to get preferences: {str(e)}"
        )


@router.put("/preferences")
async def update_notification_preferences(
    request: BulkPreferenceRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Update user notification preferences."""
    try:
        preference_service = get_notification_preference_service(db)
        
        # Convert to preference data format
        preferences_data = []
        for pref in request.preferences:
            preferences_data.append({
                "notification_type": pref.notification_type,
                "channel": pref.channel,
                "is_enabled": pref.is_enabled,
                "quiet_hours_start": pref.quiet_hours_start,
                "quiet_hours_end": pref.quiet_hours_end,
                "timezone": pref.timezone,
                "frequency_limit": pref.frequency_limit,
                "priority_threshold": pref.priority_threshold
            })
        
        updated_preferences = preference_service.bulk_update_preferences(
            user_id=current_user.id,
            preferences=preferences_data,
            updated_by=current_user.id
        )
        
        return {
            "message": f"Updated {len(updated_preferences)} preferences",
            "preferences": [
                {
                    "id": str(pref.id),
                    "notification_type": pref.notification_type.value,
                    "channel": pref.channel.value,
                    "is_enabled": pref.is_enabled
                }
                for pref in updated_preferences
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update preferences: {str(e)}"
        )


@router.post("/preferences/reset")
async def reset_notification_preferences(
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Reset notification preferences to defaults."""
    try:
        preference_service = get_notification_preference_service(db)
        
        default_preferences = preference_service.reset_to_defaults(
            user_id=current_user.id,
            updated_by=current_user.id
        )
        
        return {
            "message": "Preferences reset to defaults",
            "preferences_count": len(default_preferences)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to reset preferences: {str(e)}"
        )


# Engagement Tracking Endpoints
@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Mark a notification as read."""
    try:
        from app.db.notification_models import Notification, NotificationEngagement
        
        # Get notification
        notification = db.query(Notification).filter(Notification.id == notification_id).first()
        
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        
        # Check permissions
        if current_user.role != UserRole.ADMIN and notification.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to mark this notification as read"
            )
        
        # Update notification
        notification.read_at = datetime.now(UTC)
        db.commit()
        
        # Update or create engagement record
        engagement = db.query(NotificationEngagement).filter(
            NotificationEngagement.notification_id == notification_id
        ).first()
        
        if not engagement:
            engagement = NotificationEngagement(
                id=uuid.uuid4(),
                notification_id=notification_id,
                user_id=current_user.id,
                is_read=True,
                read_at=datetime.now(UTC)
            )
            db.add(engagement)
        else:
            engagement.is_read = True
            engagement.read_at = datetime.now(UTC)
        
        db.commit()
        
        return {"message": "Notification marked as read"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to mark notification as read: {str(e)}"
        )


@router.post("/{notification_id}/click")
async def mark_notification_clicked(
    notification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Mark a notification as clicked."""
    try:
        from app.db.notification_models import Notification, NotificationEngagement
        
        # Get notification
        notification = db.query(Notification).filter(Notification.id == notification_id).first()
        
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        
        # Check permissions
        if current_user.role != UserRole.ADMIN and notification.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to mark this notification as clicked"
            )
        
        # Update or create engagement record
        engagement = db.query(NotificationEngagement).filter(
            NotificationEngagement.notification_id == notification_id
        ).first()
        
        if not engagement:
            engagement = NotificationEngagement(
                id=uuid.uuid4(),
                notification_id=notification_id,
                user_id=current_user.id,
                is_clicked=True,
                clicked_at=datetime.now(UTC)
            )
            db.add(engagement)
        else:
            engagement.is_clicked = True
            engagement.clicked_at = datetime.now(UTC)
        
        db.commit()
        
        return {"message": "Notification marked as clicked"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to mark notification as clicked: {str(e)}"
        )


@router.post("/{notification_id}/respond")
async def mark_notification_responded(
    notification_id: uuid.UUID,
    response_data: Optional[Dict] = None,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Mark a notification as responded to."""
    try:
        from app.db.notification_models import Notification, NotificationEngagement
        
        # Get notification
        notification = db.query(Notification).filter(Notification.id == notification_id).first()
        
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        
        # Check permissions
        if current_user.role != UserRole.ADMIN and notification.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to mark this notification as responded"
            )
        
        # Update or create engagement record
        engagement = db.query(NotificationEngagement).filter(
            NotificationEngagement.notification_id == notification_id
        ).first()
        
        if not engagement:
            engagement = NotificationEngagement(
                id=uuid.uuid4(),
                notification_id=notification_id,
                user_id=current_user.id,
                is_responded=True,
                responded_at=datetime.now(UTC),
                response_data=response_data
            )
            db.add(engagement)
        else:
            engagement.is_responded = True
            engagement.responded_at = datetime.now(UTC)
            if response_data:
                engagement.response_data = response_data
        
        db.commit()
        
        return {"message": "Notification marked as responded"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to mark notification as responded: {str(e)}"
        )


# Analytics Endpoints
@router.get("/analytics/engagement")
async def get_engagement_analytics(
    user_id: Optional[uuid.UUID] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    notification_type: Optional[NotificationType] = None,
    channel: Optional[NotificationChannel] = None,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Get engagement analytics."""
    try:
        analytics_service = get_engagement_analytics_service(db)
        
        # Check permissions
        if user_id and current_user.role != UserRole.ADMIN and user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view analytics for this user"
            )
        
        metrics = analytics_service.get_engagement_metrics(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            notification_type=notification_type,
            channel=channel
        )
        
        return metrics
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to get engagement analytics: {str(e)}"
        )


@router.get("/analytics/user/{user_id}")
async def get_user_engagement_profile(
    user_id: uuid.UUID,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Get user engagement profile."""
    try:
        # Check permissions
        if current_user.role != UserRole.ADMIN and user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this user's engagement profile"
            )
        
        analytics_service = get_engagement_analytics_service(db)
        
        profile = analytics_service.get_user_engagement_profile(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date
        )
        
        return profile
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to get user engagement profile: {str(e)}"
        )


@router.get("/analytics/channels")
async def get_channel_performance(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(role_required([UserRole.ADMIN])),
    db=Depends(get_db)
):
    """Get channel performance analysis (admin only)."""
    try:
        analytics_service = get_engagement_analytics_service(db)
        
        analysis = analytics_service.get_channel_performance_analysis(
            start_date=start_date,
            end_date=end_date
        )
        
        return analysis
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to get channel performance: {str(e)}"
        )


@router.get("/analytics/trends")
async def get_engagement_trends(
    start_date: datetime,
    end_date: datetime,
    granularity: str = "daily",
    current_user: User = Depends(role_required([UserRole.ADMIN])),
    db=Depends(get_db)
):
    """Get engagement trends over time (admin only)."""
    try:
        analytics_service = get_engagement_analytics_service(db)
        
        trends = analytics_service.get_engagement_trends(
            start_date=start_date,
            end_date=end_date,
            granularity=granularity
        )
        
        return trends
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to get engagement trends: {str(e)}"
        )


# System Endpoints
@router.get("/stats/connection")
async def get_connection_stats(
    current_user: User = Depends(role_required([UserRole.ADMIN])),
    db=Depends(get_db)
):
    """Get WebSocket connection statistics (admin only)."""
    try:
        real_time_service = get_real_time_notification_service(db)
        
        stats = real_time_service.get_connection_stats()
        
        return stats
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to get connection stats: {str(e)}"
        )


@router.post("/system/announcement")
async def send_system_announcement(
    message: str,
    title: str = "System Announcement",
    target_users: Optional[List[uuid.UUID]] = None,
    priority: str = "normal",
    current_user: User = Depends(role_required([UserRole.ADMIN])),
    db=Depends(get_db)
):
    """Send system announcement (admin only)."""
    try:
        real_time_service = get_real_time_notification_service(db)
        
        sent_count = await real_time_service.send_system_announcement(
            message=message,
            title=title,
            target_users=target_users,
            priority=priority
        )
        
        return {
            "message": "System announcement sent",
            "sent_to_users": sent_count
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to send system announcement: {str(e)}"
        )
