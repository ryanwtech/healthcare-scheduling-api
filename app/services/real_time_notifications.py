"""Real-time notifications service with WebSocket support."""

import json
import uuid
from datetime import datetime, UTC
from typing import Dict, List, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.notification_models import (
    Notification,
    NotificationChannel,
    NotificationEngagement,
    NotificationStatus,
    NotificationType,
)
from app.security.audit import AuditLogger, get_audit_logger

logger = get_logger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for real-time notifications."""
    
    def __init__(self):
        # Store active connections by user_id
        self.active_connections: Dict[uuid.UUID, Set[WebSocket]] = {}
        # Store connection metadata
        self.connection_metadata: Dict[WebSocket, Dict] = {}
    
    async def connect(self, websocket: WebSocket, user_id: uuid.UUID, client_info: Optional[Dict] = None) -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        
        self.active_connections[user_id].add(websocket)
        self.connection_metadata[websocket] = {
            "user_id": user_id,
            "connected_at": datetime.now(UTC),
            "client_info": client_info or {}
        }
        
        logger.info(f"WebSocket connected for user {user_id}")
    
    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        metadata = self.connection_metadata.get(websocket)
        if metadata:
            user_id = metadata["user_id"]
            if user_id in self.active_connections:
                self.active_connections[user_id].discard(websocket)
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
            
            del self.connection_metadata[websocket]
            logger.info(f"WebSocket disconnected for user {user_id}")
    
    async def send_personal_message(self, message: Dict, user_id: uuid.UUID) -> bool:
        """Send a message to a specific user."""
        try:
            if user_id not in self.active_connections:
                return False
            
            connections = self.active_connections[user_id].copy()
            if not connections:
                return False
            
            # Send to all connections for this user
            success_count = 0
            for websocket in connections:
                try:
                    await websocket.send_text(json.dumps(message))
                    success_count += 1
                except Exception as e:
                    logger.error(f"Failed to send message to WebSocket: {e}")
                    # Remove failed connection
                    self.disconnect(websocket)
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Failed to send personal message: {e}")
            return False
    
    async def send_broadcast_message(self, message: Dict, user_ids: Optional[List[uuid.UUID]] = None) -> int:
        """Send a message to multiple users or all users."""
        try:
            target_users = user_ids or list(self.active_connections.keys())
            success_count = 0
            
            for user_id in target_users:
                if await self.send_personal_message(message, user_id):
                    success_count += 1
            
            return success_count
            
        except Exception as e:
            logger.error(f"Failed to send broadcast message: {e}")
            return 0
    
    def get_connection_count(self, user_id: Optional[uuid.UUID] = None) -> int:
        """Get the number of active connections."""
        if user_id:
            return len(self.active_connections.get(user_id, set()))
        else:
            return sum(len(connections) for connections in self.active_connections.values())
    
    def get_connected_users(self) -> List[uuid.UUID]:
        """Get list of users with active connections."""
        return list(self.active_connections.keys())


class RealTimeNotificationService:
    """Service for real-time notifications and WebSocket management."""
    
    def __init__(self, db: Session):
        self.db = db
        self.audit_logger = get_audit_logger(db)
        self.connection_manager = ConnectionManager()
    
    async def handle_websocket_connection(
        self,
        websocket: WebSocket,
        user_id: uuid.UUID,
        client_info: Optional[Dict] = None
    ) -> None:
        """Handle a new WebSocket connection."""
        try:
            await self.connection_manager.connect(websocket, user_id, client_info)
            
            # Send welcome message
            welcome_message = {
                "type": "connection_established",
                "message": "Connected to real-time notifications",
                "timestamp": datetime.now(UTC).isoformat(),
                "user_id": str(user_id)
            }
            await websocket.send_text(json.dumps(welcome_message))
            
            # Send any pending notifications
            await self._send_pending_notifications(user_id, websocket)
            
            # Keep connection alive
            await self._keep_connection_alive(websocket)
            
        except WebSocketDisconnect:
            self.connection_manager.disconnect(websocket)
        except Exception as e:
            logger.error(f"Error handling WebSocket connection: {e}")
            self.connection_manager.disconnect(websocket)
    
    async def _keep_connection_alive(self, websocket: WebSocket) -> None:
        """Keep WebSocket connection alive and handle incoming messages."""
        try:
            while True:
                # Wait for messages from client
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Handle different message types
                await self._handle_client_message(websocket, message)
                
        except WebSocketDisconnect:
            self.connection_manager.disconnect(websocket)
        except Exception as e:
            logger.error(f"Error in WebSocket connection: {e}")
            self.connection_manager.disconnect(websocket)
    
    async def _handle_client_message(self, websocket: WebSocket, message: Dict) -> None:
        """Handle incoming message from client."""
        try:
            message_type = message.get("type")
            
            if message_type == "ping":
                # Respond to ping with pong
                pong_message = {
                    "type": "pong",
                    "timestamp": datetime.now(UTC).isoformat()
                }
                await websocket.send_text(json.dumps(pong_message))
            
            elif message_type == "notification_read":
                # Mark notification as read
                notification_id = message.get("notification_id")
                if notification_id:
                    await self._mark_notification_read(notification_id)
            
            elif message_type == "notification_dismissed":
                # Mark notification as dismissed
                notification_id = message.get("notification_id")
                if notification_id:
                    await self._mark_notification_dismissed(notification_id)
            
            elif message_type == "get_notifications":
                # Send recent notifications
                user_id = self.connection_manager.connection_metadata.get(websocket, {}).get("user_id")
                if user_id:
                    await self._send_recent_notifications(user_id, websocket)
            
        except Exception as e:
            logger.error(f"Error handling client message: {e}")
    
    async def send_real_time_notification(
        self,
        user_id: uuid.UUID,
        notification: Notification,
        immediate: bool = True
    ) -> bool:
        """Send a real-time notification to a user."""
        try:
            # Create notification message
            message = {
                "type": "notification",
                "notification_id": str(notification.id),
                "notification_type": notification.notification_type.value,
                "channel": notification.channel.value,
                "priority": notification.priority.value,
                "subject": notification.subject,
                "content": notification.content,
                "metadata": notification.metadata or {},
                "timestamp": notification.created_at.isoformat(),
                "scheduled_at": notification.scheduled_at.isoformat() if notification.scheduled_at else None
            }
            
            # Send via WebSocket if user is connected
            websocket_sent = await self.connection_manager.send_personal_message(message, user_id)
            
            # Update notification status
            if websocket_sent:
                notification.status = NotificationStatus.DELIVERED
                notification.delivered_at = datetime.now(UTC)
                self.db.commit()
                
                # Log delivery
                self.audit_logger.log_event(
                    event_type="phi_access",
                    user_id=user_id,
                    resource_id=notification.id,
                    resource_type="notification",
                    action="real_time_notification_sent",
                    details={
                        "notification_type": notification.notification_type.value,
                        "channel": notification.channel.value,
                        "websocket_delivered": True
                    },
                    success=True
                )
            
            return websocket_sent
            
        except Exception as e:
            logger.error(f"Failed to send real-time notification: {e}")
            return False
    
    async def send_bulk_real_time_notifications(
        self,
        notifications: List[Notification],
        user_ids: Optional[List[uuid.UUID]] = None
    ) -> Dict[str, int]:
        """Send multiple real-time notifications."""
        try:
            stats = {
                "total": len(notifications),
                "sent": 0,
                "failed": 0,
                "users_notified": 0
            }
            
            # Group notifications by user
            notifications_by_user = {}
            for notification in notifications:
                if notification.user_id not in notifications_by_user:
                    notifications_by_user[notification.user_id] = []
                notifications_by_user[notification.user_id].append(notification)
            
            # Send to each user
            for user_id, user_notifications in notifications_by_user.items():
                if user_ids and user_id not in user_ids:
                    continue
                
                user_sent = 0
                for notification in user_notifications:
                    if await self.send_real_time_notification(user_id, notification):
                        user_sent += 1
                        stats["sent"] += 1
                    else:
                        stats["failed"] += 1
                
                if user_sent > 0:
                    stats["users_notified"] += 1
            
            logger.info(f"Bulk real-time notifications sent: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to send bulk real-time notifications: {e}")
            return {"total": 0, "sent": 0, "failed": 0, "users_notified": 0}
    
    async def _send_pending_notifications(self, user_id: uuid.UUID, websocket: WebSocket) -> None:
        """Send pending notifications to a newly connected user."""
        try:
            # Get recent unread notifications
            recent_notifications = (
                self.db.query(Notification)
                .filter(
                    Notification.user_id == user_id,
                    Notification.channel == NotificationChannel.IN_APP,
                    Notification.status.in_([NotificationStatus.SENT, NotificationStatus.DELIVERED])
                )
                .order_by(Notification.created_at.desc())
                .limit(10)
                .all()
            )
            
            for notification in recent_notifications:
                message = {
                    "type": "notification",
                    "notification_id": str(notification.id),
                    "notification_type": notification.notification_type.value,
                    "channel": notification.channel.value,
                    "priority": notification.priority.value,
                    "subject": notification.subject,
                    "content": notification.content,
                    "metadata": notification.metadata or {},
                    "timestamp": notification.created_at.isoformat(),
                    "scheduled_at": notification.scheduled_at.isoformat() if notification.scheduled_at else None
                }
                
                await websocket.send_text(json.dumps(message))
            
            if recent_notifications:
                logger.info(f"Sent {len(recent_notifications)} pending notifications to user {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to send pending notifications: {e}")
    
    async def _send_recent_notifications(self, user_id: uuid.UUID, websocket: WebSocket) -> None:
        """Send recent notifications to client on request."""
        try:
            # Get recent notifications
            recent_notifications = (
                self.db.query(Notification)
                .filter(
                    Notification.user_id == user_id,
                    Notification.channel == NotificationChannel.IN_APP
                )
                .order_by(Notification.created_at.desc())
                .limit(20)
                .all()
            )
            
            message = {
                "type": "notifications_list",
                "notifications": [
                    {
                        "notification_id": str(notification.id),
                        "notification_type": notification.notification_type.value,
                        "channel": notification.channel.value,
                        "priority": notification.priority.value,
                        "subject": notification.subject,
                        "content": notification.content,
                        "metadata": notification.metadata or {},
                        "timestamp": notification.created_at.isoformat(),
                        "status": notification.status.value,
                        "read_at": notification.read_at.isoformat() if notification.read_at else None
                    }
                    for notification in recent_notifications
                ],
                "count": len(recent_notifications)
            }
            
            await websocket.send_text(json.dumps(message))
            
        except Exception as e:
            logger.error(f"Failed to send recent notifications: {e}")
    
    async def _mark_notification_read(self, notification_id: str) -> None:
        """Mark notification as read."""
        try:
            notification = self.db.query(Notification).filter(
                Notification.id == notification_id
            ).first()
            
            if notification:
                notification.read_at = datetime.now(UTC)
                self.db.commit()
                
                # Update engagement tracking
                engagement = self.db.query(NotificationEngagement).filter(
                    NotificationEngagement.notification_id == notification_id
                ).first()
                
                if engagement:
                    engagement.is_read = True
                    engagement.read_at = datetime.now(UTC)
                    self.db.commit()
                
                logger.info(f"Marked notification {notification_id} as read")
            
        except Exception as e:
            logger.error(f"Failed to mark notification as read: {e}")
    
    async def _mark_notification_dismissed(self, notification_id: str) -> None:
        """Mark notification as dismissed."""
        try:
            engagement = self.db.query(NotificationEngagement).filter(
                NotificationEngagement.notification_id == notification_id
            ).first()
            
            if engagement:
                engagement.is_dismissed = True
                engagement.dismissed_at = datetime.now(UTC)
                self.db.commit()
                
                logger.info(f"Marked notification {notification_id} as dismissed")
            
        except Exception as e:
            logger.error(f"Failed to mark notification as dismissed: {e}")
    
    def get_connection_stats(self) -> Dict:
        """Get WebSocket connection statistics."""
        try:
            total_connections = self.connection_manager.get_connection_count()
            connected_users = self.connection_manager.get_connected_users()
            
            return {
                "total_connections": total_connections,
                "connected_users": len(connected_users),
                "user_ids": [str(user_id) for user_id in connected_users]
            }
            
        except Exception as e:
            logger.error(f"Failed to get connection stats: {e}")
            return {}
    
    async def send_system_announcement(
        self,
        message: str,
        title: str = "System Announcement",
        target_users: Optional[List[uuid.UUID]] = None,
        priority: str = "normal"
    ) -> int:
        """Send a system announcement to connected users."""
        try:
            announcement = {
                "type": "system_announcement",
                "title": title,
                "message": message,
                "priority": priority,
                "timestamp": datetime.now(UTC).isoformat()
            }
            
            sent_count = await self.connection_manager.send_broadcast_message(
                announcement, target_users
            )
            
            logger.info(f"System announcement sent to {sent_count} users")
            return sent_count
            
        except Exception as e:
            logger.error(f"Failed to send system announcement: {e}")
            return 0
    
    async def send_appointment_reminder_realtime(
        self,
        user_id: uuid.UUID,
        appointment_data: Dict
    ) -> bool:
        """Send real-time appointment reminder."""
        try:
            message = {
                "type": "appointment_reminder",
                "title": "Appointment Reminder",
                "message": f"Your appointment with Dr. {appointment_data.get('doctor_name')} is in {appointment_data.get('time_until', 'soon')}",
                "appointment_data": appointment_data,
                "priority": "high",
                "timestamp": datetime.now(UTC).isoformat(),
                "actions": [
                    {"type": "view_appointment", "label": "View Details"},
                    {"type": "reschedule", "label": "Reschedule"},
                    {"type": "cancel", "label": "Cancel"}
                ]
            }
            
            return await self.connection_manager.send_personal_message(message, user_id)
            
        except Exception as e:
            logger.error(f"Failed to send real-time appointment reminder: {e}")
            return False
    
    async def send_waitlist_notification_realtime(
        self,
        user_id: uuid.UUID,
        waitlist_data: Dict
    ) -> bool:
        """Send real-time waitlist notification."""
        try:
            message = {
                "type": "waitlist_notification",
                "title": "Appointment Available!",
                "message": f"A time slot with Dr. {waitlist_data.get('doctor_name')} is now available for {waitlist_data.get('appointment_date')} at {waitlist_data.get('appointment_time')}",
                "waitlist_data": waitlist_data,
                "priority": "urgent",
                "timestamp": datetime.now(UTC).isoformat(),
                "expires_at": waitlist_data.get("expires_at"),
                "actions": [
                    {"type": "book_now", "label": "Book Now"},
                    {"type": "skip", "label": "Skip"}
                ]
            }
            
            return await self.connection_manager.send_personal_message(message, user_id)
            
        except Exception as e:
            logger.error(f"Failed to send real-time waitlist notification: {e}")
            return False


def get_real_time_notification_service(db: Session) -> RealTimeNotificationService:
    """Get real-time notification service instance."""
    return RealTimeNotificationService(db)
