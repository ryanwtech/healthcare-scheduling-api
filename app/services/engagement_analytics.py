"""Notification engagement analytics and metrics service."""

import uuid
from datetime import datetime, timedelta, UTC
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

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


class EngagementAnalyticsService:
    """Service for notification engagement analytics and metrics."""
    
    def __init__(self, db: Session):
        self.db = db
        self.audit_logger = get_audit_logger(db)
    
    def get_engagement_metrics(
        self,
        user_id: Optional[uuid.UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        notification_type: Optional[NotificationType] = None,
        channel: Optional[NotificationChannel] = None
    ) -> Dict:
        """
        Get comprehensive engagement metrics.
        
        Args:
            user_id: Specific user ID (None for all users)
            start_date: Analysis start date
            end_date: Analysis end date
            notification_type: Specific notification type
            channel: Specific channel
            
        Returns:
            Engagement metrics dictionary
        """
        try:
            # Build base query
            query = self.db.query(Notification)
            
            if user_id:
                query = query.filter(Notification.user_id == user_id)
            
            if start_date:
                query = query.filter(Notification.created_at >= start_date)
            
            if end_date:
                query = query.filter(Notification.created_at <= end_date)
            
            if notification_type:
                query = query.filter(Notification.notification_type == notification_type)
            
            if channel:
                query = query.filter(Notification.channel == channel)
            
            notifications = query.all()
            
            if not notifications:
                return self._empty_metrics()
            
            # Calculate basic metrics
            total_sent = len([n for n in notifications if n.status in [NotificationStatus.SENT, NotificationStatus.DELIVERED]])
            total_delivered = len([n for n in notifications if n.status == NotificationStatus.DELIVERED])
            total_failed = len([n for n in notifications if n.status == NotificationStatus.FAILED])
            
            # Get engagement data
            engagement_data = self._get_engagement_data(notifications)
            
            # Calculate engagement rates
            delivery_rate = (total_delivered / total_sent * 100) if total_sent > 0 else 0
            read_rate = (engagement_data["read_count"] / total_delivered * 100) if total_delivered > 0 else 0
            click_rate = (engagement_data["clicked_count"] / total_delivered * 100) if total_delivered > 0 else 0
            response_rate = (engagement_data["responded_count"] / total_delivered * 100) if total_delivered > 0 else 0
            dismissal_rate = (engagement_data["dismissed_count"] / total_delivered * 100) if total_delivered > 0 else 0
            
            # Calculate time-based metrics
            time_metrics = self._calculate_time_metrics(engagement_data)
            
            # Calculate channel performance
            channel_metrics = self._calculate_channel_metrics(notifications, engagement_data)
            
            # Calculate type performance
            type_metrics = self._calculate_type_metrics(notifications, engagement_data)
            
            # Calculate user engagement score
            user_engagement_score = self._calculate_user_engagement_score(engagement_data)
            
            metrics = {
                "period": {
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None
                },
                "overview": {
                    "total_notifications": len(notifications),
                    "total_sent": total_sent,
                    "total_delivered": total_delivered,
                    "total_failed": total_failed,
                    "delivery_rate": round(delivery_rate, 2),
                    "failure_rate": round((total_failed / total_sent * 100) if total_sent > 0 else 0, 2)
                },
                "engagement": {
                    "read_count": engagement_data["read_count"],
                    "clicked_count": engagement_data["clicked_count"],
                    "responded_count": engagement_data["responded_count"],
                    "dismissed_count": engagement_data["dismissed_count"],
                    "read_rate": round(read_rate, 2),
                    "click_rate": round(click_rate, 2),
                    "response_rate": round(response_rate, 2),
                    "dismissal_rate": round(dismissal_rate, 2)
                },
                "time_metrics": time_metrics,
                "channel_performance": channel_metrics,
                "type_performance": type_metrics,
                "user_engagement_score": user_engagement_score
            }
            
            # Log analytics access
            self.audit_logger.log_event(
                event_type="phi_access",
                user_id=user_id,
                action="engagement_analytics_generated",
                details={
                    "notifications_analyzed": len(notifications),
                    "engagement_data_points": len(engagement_data.get("engagements", [])),
                    "user_id": str(user_id) if user_id else "all"
                },
                success=True
            )
            
            logger.info(f"Generated engagement metrics for {len(notifications)} notifications")
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to get engagement metrics: {e}")
            return self._empty_metrics()
    
    def get_user_engagement_profile(
        self,
        user_id: uuid.UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict:
        """Get detailed engagement profile for a specific user."""
        try:
            # Get user's notifications
            query = self.db.query(Notification).filter(Notification.user_id == user_id)
            
            if start_date:
                query = query.filter(Notification.created_at >= start_date)
            
            if end_date:
                query = query.filter(Notification.created_at <= end_date)
            
            notifications = query.all()
            
            if not notifications:
                return self._empty_user_profile(user_id)
            
            # Get engagement data
            engagement_data = self._get_engagement_data(notifications)
            
            # Calculate user-specific metrics
            profile = {
                "user_id": str(user_id),
                "period": {
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None
                },
                "notification_activity": {
                    "total_received": len(notifications),
                    "total_read": engagement_data["read_count"],
                    "total_clicked": engagement_data["clicked_count"],
                    "total_responded": engagement_data["responded_count"],
                    "total_dismissed": engagement_data["dismissed_count"]
                },
                "engagement_rates": {
                    "read_rate": round((engagement_data["read_count"] / len(notifications) * 100), 2),
                    "click_rate": round((engagement_data["clicked_count"] / len(notifications) * 100), 2),
                    "response_rate": round((engagement_data["responded_count"] / len(notifications) * 100), 2),
                    "dismissal_rate": round((engagement_data["dismissed_count"] / len(notifications) * 100), 2)
                },
                "preferred_channels": self._get_user_preferred_channels(notifications, engagement_data),
                "preferred_types": self._get_user_preferred_types(notifications, engagement_data),
                "engagement_patterns": self._analyze_user_engagement_patterns(engagement_data),
                "response_times": self._calculate_user_response_times(engagement_data),
                "engagement_score": self._calculate_user_engagement_score(engagement_data),
                "recommendations": self._generate_user_recommendations(notifications, engagement_data)
            }
            
            logger.info(f"Generated engagement profile for user {user_id}")
            return profile
            
        except Exception as e:
            logger.error(f"Failed to get user engagement profile: {e}")
            return self._empty_user_profile(user_id)
    
    def get_channel_performance_analysis(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict:
        """Get detailed channel performance analysis."""
        try:
            # Get all notifications in period
            query = self.db.query(Notification)
            
            if start_date:
                query = query.filter(Notification.created_at >= start_date)
            
            if end_date:
                query = query.filter(Notification.created_at <= end_date)
            
            notifications = query.all()
            
            if not notifications:
                return {"channels": {}}
            
            # Group by channel
            channel_data = {}
            for notification in notifications:
                channel = notification.channel.value
                if channel not in channel_data:
                    channel_data[channel] = {
                        "notifications": [],
                        "engagement_data": None
                    }
                channel_data[channel]["notifications"].append(notification)
            
            # Calculate metrics for each channel
            channel_analysis = {}
            for channel, data in channel_data.items():
                engagement_data = self._get_engagement_data(data["notifications"])
                
                total_sent = len([n for n in data["notifications"] if n.status in [NotificationStatus.SENT, NotificationStatus.DELIVERED]])
                total_delivered = len([n for n in data["notifications"] if n.status == NotificationStatus.DELIVERED])
                
                channel_analysis[channel] = {
                    "total_notifications": len(data["notifications"]),
                    "total_sent": total_sent,
                    "total_delivered": total_delivered,
                    "delivery_rate": round((total_delivered / total_sent * 100) if total_sent > 0 else 0, 2),
                    "read_rate": round((engagement_data["read_count"] / total_delivered * 100) if total_delivered > 0 else 0, 2),
                    "click_rate": round((engagement_data["clicked_count"] / total_delivered * 100) if total_delivered > 0 else 0, 2),
                    "response_rate": round((engagement_data["responded_count"] / total_delivered * 100) if total_delivered > 0 else 0, 2),
                    "dismissal_rate": round((engagement_data["dismissed_count"] / total_delivered * 100) if total_delivered > 0 else 0, 2),
                    "average_response_time": self._calculate_average_response_time(engagement_data),
                    "engagement_score": self._calculate_channel_engagement_score(engagement_data)
                }
            
            # Rank channels by performance
            ranked_channels = sorted(
                channel_analysis.items(),
                key=lambda x: x[1]["engagement_score"],
                reverse=True
            )
            
            return {
                "channels": channel_analysis,
                "rankings": {
                    "by_engagement_score": [{"channel": channel, "score": data["engagement_score"]} for channel, data in ranked_channels],
                    "by_delivery_rate": sorted(channel_analysis.items(), key=lambda x: x[1]["delivery_rate"], reverse=True),
                    "by_read_rate": sorted(channel_analysis.items(), key=lambda x: x[1]["read_rate"], reverse=True),
                    "by_click_rate": sorted(channel_analysis.items(), key=lambda x: x[1]["click_rate"], reverse=True)
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get channel performance analysis: {e}")
            return {"channels": {}}
    
    def get_engagement_trends(
        self,
        start_date: datetime,
        end_date: datetime,
        granularity: str = "daily"
    ) -> Dict:
        """Get engagement trends over time."""
        try:
            # Get notifications in period
            notifications = (
                self.db.query(Notification)
                .filter(
                    Notification.created_at >= start_date,
                    Notification.created_at <= end_date
                )
                .order_by(Notification.created_at)
                .all()
            )
            
            if not notifications:
                return {"trends": []}
            
            # Group by time period
            trends = self._group_by_time_period(notifications, granularity)
            
            # Calculate trend metrics
            trend_analysis = {
                "granularity": granularity,
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "trends": trends,
                "summary": self._calculate_trend_summary(trends)
            }
            
            return trend_analysis
            
        except Exception as e:
            logger.error(f"Failed to get engagement trends: {e}")
            return {"trends": []}
    
    def _get_engagement_data(self, notifications: List[Notification]) -> Dict:
        """Get engagement data for notifications."""
        try:
            notification_ids = [n.id for n in notifications]
            
            # Get engagement records
            engagements = (
                self.db.query(NotificationEngagement)
                .filter(NotificationEngagement.notification_id.in_(notification_ids))
                .all()
            )
            
            # Calculate counts
            read_count = len([e for e in engagements if e.is_read])
            clicked_count = len([e for e in engagements if e.is_clicked])
            responded_count = len([e for e in engagements if e.is_responded])
            dismissed_count = len([e for e in engagements if e.is_dismissed])
            
            return {
                "engagements": engagements,
                "read_count": read_count,
                "clicked_count": clicked_count,
                "responded_count": responded_count,
                "dismissed_count": dismissed_count
            }
            
        except Exception as e:
            logger.error(f"Failed to get engagement data: {e}")
            return {
                "engagements": [],
                "read_count": 0,
                "clicked_count": 0,
                "responded_count": 0,
                "dismissed_count": 0
            }
    
    def _calculate_time_metrics(self, engagement_data: Dict) -> Dict:
        """Calculate time-based engagement metrics."""
        try:
            engagements = engagement_data.get("engagements", [])
            
            if not engagements:
                return {
                    "average_read_time_minutes": 0,
                    "average_click_time_minutes": 0,
                    "average_response_time_minutes": 0
                }
            
            # Calculate average times
            read_times = []
            click_times = []
            response_times = []
            
            for engagement in engagements:
                if engagement.read_at and engagement.notification.sent_at:
                    read_time = (engagement.read_at - engagement.notification.sent_at).total_seconds() / 60
                    read_times.append(read_time)
                
                if engagement.clicked_at and engagement.notification.sent_at:
                    click_time = (engagement.clicked_at - engagement.notification.sent_at).total_seconds() / 60
                    click_times.append(click_time)
                
                if engagement.responded_at and engagement.notification.sent_at:
                    response_time = (engagement.responded_at - engagement.notification.sent_at).total_seconds() / 60
                    response_times.append(response_time)
            
            return {
                "average_read_time_minutes": round(sum(read_times) / len(read_times), 2) if read_times else 0,
                "average_click_time_minutes": round(sum(click_times) / len(click_times), 2) if click_times else 0,
                "average_response_time_minutes": round(sum(response_times) / len(response_times), 2) if response_times else 0
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate time metrics: {e}")
            return {
                "average_read_time_minutes": 0,
                "average_click_time_minutes": 0,
                "average_response_time_minutes": 0
            }
    
    def _calculate_channel_metrics(
        self,
        notifications: List[Notification],
        engagement_data: Dict
    ) -> Dict:
        """Calculate channel-specific metrics."""
        try:
            channel_metrics = {}
            
            # Group by channel
            for notification in notifications:
                channel = notification.channel.value
                if channel not in channel_metrics:
                    channel_metrics[channel] = {
                        "notifications": 0,
                        "delivered": 0,
                        "read": 0,
                        "clicked": 0,
                        "responded": 0
                    }
                
                channel_metrics[channel]["notifications"] += 1
                
                if notification.status == NotificationStatus.DELIVERED:
                    channel_metrics[channel]["delivered"] += 1
            
            # Add engagement data
            for engagement in engagement_data.get("engagements", []):
                channel = engagement.notification.channel.value
                if channel in channel_metrics:
                    if engagement.is_read:
                        channel_metrics[channel]["read"] += 1
                    if engagement.is_clicked:
                        channel_metrics[channel]["clicked"] += 1
                    if engagement.is_responded:
                        channel_metrics[channel]["responded"] += 1
            
            # Calculate rates
            for channel, metrics in channel_metrics.items():
                if metrics["delivered"] > 0:
                    metrics["read_rate"] = round((metrics["read"] / metrics["delivered"] * 100), 2)
                    metrics["click_rate"] = round((metrics["clicked"] / metrics["delivered"] * 100), 2)
                    metrics["response_rate"] = round((metrics["responded"] / metrics["delivered"] * 100), 2)
                else:
                    metrics["read_rate"] = 0
                    metrics["click_rate"] = 0
                    metrics["response_rate"] = 0
            
            return channel_metrics
            
        except Exception as e:
            logger.error(f"Failed to calculate channel metrics: {e}")
            return {}
    
    def _calculate_type_metrics(
        self,
        notifications: List[Notification],
        engagement_data: Dict
    ) -> Dict:
        """Calculate notification type-specific metrics."""
        try:
            type_metrics = {}
            
            # Group by notification type
            for notification in notifications:
                notification_type = notification.notification_type.value
                if notification_type not in type_metrics:
                    type_metrics[notification_type] = {
                        "notifications": 0,
                        "delivered": 0,
                        "read": 0,
                        "clicked": 0,
                        "responded": 0
                    }
                
                type_metrics[notification_type]["notifications"] += 1
                
                if notification.status == NotificationStatus.DELIVERED:
                    type_metrics[notification_type]["delivered"] += 1
            
            # Add engagement data
            for engagement in engagement_data.get("engagements", []):
                notification_type = engagement.notification.notification_type.value
                if notification_type in type_metrics:
                    if engagement.is_read:
                        type_metrics[notification_type]["read"] += 1
                    if engagement.is_clicked:
                        type_metrics[notification_type]["clicked"] += 1
                    if engagement.is_responded:
                        type_metrics[notification_type]["responded"] += 1
            
            # Calculate rates
            for notification_type, metrics in type_metrics.items():
                if metrics["delivered"] > 0:
                    metrics["read_rate"] = round((metrics["read"] / metrics["delivered"] * 100), 2)
                    metrics["click_rate"] = round((metrics["clicked"] / metrics["delivered"] * 100), 2)
                    metrics["response_rate"] = round((metrics["responded"] / metrics["delivered"] * 100), 2)
                else:
                    metrics["read_rate"] = 0
                    metrics["click_rate"] = 0
                    metrics["response_rate"] = 0
            
            return type_metrics
            
        except Exception as e:
            logger.error(f"Failed to calculate type metrics: {e}")
            return {}
    
    def _calculate_user_engagement_score(self, engagement_data: Dict) -> float:
        """Calculate user engagement score (0-100)."""
        try:
            engagements = engagement_data.get("engagements", [])
            
            if not engagements:
                return 0.0
            
            # Weight different engagement types
            read_weight = 0.3
            click_weight = 0.4
            response_weight = 0.3
            
            read_score = (engagement_data["read_count"] / len(engagements)) * 100
            click_score = (engagement_data["clicked_count"] / len(engagements)) * 100
            response_score = (engagement_data["responded_count"] / len(engagements)) * 100
            
            total_score = (
                read_score * read_weight +
                click_score * click_weight +
                response_score * response_weight
            )
            
            return round(total_score, 2)
            
        except Exception as e:
            logger.error(f"Failed to calculate user engagement score: {e}")
            return 0.0
    
    def _calculate_channel_engagement_score(self, engagement_data: Dict) -> float:
        """Calculate channel engagement score."""
        return self._calculate_user_engagement_score(engagement_data)
    
    def _calculate_average_response_time(self, engagement_data: Dict) -> float:
        """Calculate average response time in minutes."""
        try:
            response_times = []
            
            for engagement in engagement_data.get("engagements", []):
                if engagement.responded_at and engagement.notification.sent_at:
                    response_time = (engagement.responded_at - engagement.notification.sent_at).total_seconds() / 60
                    response_times.append(response_time)
            
            return round(sum(response_times) / len(response_times), 2) if response_times else 0.0
            
        except Exception as e:
            logger.error(f"Failed to calculate average response time: {e}")
            return 0.0
    
    def _get_user_preferred_channels(
        self,
        notifications: List[Notification],
        engagement_data: Dict
    ) -> List[Dict]:
        """Get user's preferred channels based on engagement."""
        try:
            channel_engagement = {}
            
            for notification in notifications:
                channel = notification.channel.value
                if channel not in channel_engagement:
                    channel_engagement[channel] = {"total": 0, "engaged": 0}
                
                channel_engagement[channel]["total"] += 1
                
                # Check if this notification was engaged with
                for engagement in engagement_data.get("engagements", []):
                    if (engagement.notification_id == notification.id and
                        (engagement.is_read or engagement.is_clicked or engagement.is_responded)):
                        channel_engagement[channel]["engaged"] += 1
                        break
            
            # Calculate engagement rates and sort
            preferred_channels = []
            for channel, data in channel_engagement.items():
                engagement_rate = (data["engaged"] / data["total"] * 100) if data["total"] > 0 else 0
                preferred_channels.append({
                    "channel": channel,
                    "total_notifications": data["total"],
                    "engaged_notifications": data["engaged"],
                    "engagement_rate": round(engagement_rate, 2)
                })
            
            return sorted(preferred_channels, key=lambda x: x["engagement_rate"], reverse=True)
            
        except Exception as e:
            logger.error(f"Failed to get user preferred channels: {e}")
            return []
    
    def _get_user_preferred_types(
        self,
        notifications: List[Notification],
        engagement_data: Dict
    ) -> List[Dict]:
        """Get user's preferred notification types based on engagement."""
        try:
            type_engagement = {}
            
            for notification in notifications:
                notification_type = notification.notification_type.value
                if notification_type not in type_engagement:
                    type_engagement[notification_type] = {"total": 0, "engaged": 0}
                
                type_engagement[notification_type]["total"] += 1
                
                # Check if this notification was engaged with
                for engagement in engagement_data.get("engagements", []):
                    if (engagement.notification_id == notification.id and
                        (engagement.is_read or engagement.is_clicked or engagement.is_responded)):
                        type_engagement[notification_type]["engaged"] += 1
                        break
            
            # Calculate engagement rates and sort
            preferred_types = []
            for notification_type, data in type_engagement.items():
                engagement_rate = (data["engaged"] / data["total"] * 100) if data["total"] > 0 else 0
                preferred_types.append({
                    "type": notification_type,
                    "total_notifications": data["total"],
                    "engaged_notifications": data["engaged"],
                    "engagement_rate": round(engagement_rate, 2)
                })
            
            return sorted(preferred_types, key=lambda x: x["engagement_rate"], reverse=True)
            
        except Exception as e:
            logger.error(f"Failed to get user preferred types: {e}")
            return []
    
    def _analyze_user_engagement_patterns(self, engagement_data: Dict) -> Dict:
        """Analyze user engagement patterns."""
        try:
            engagements = engagement_data.get("engagements", [])
            
            if not engagements:
                return {"patterns": []}
            
            # Analyze engagement timing patterns
            patterns = {
                "most_engaged_hour": self._get_most_engaged_hour(engagements),
                "most_engaged_day": self._get_most_engaged_day(engagements),
                "engagement_frequency": self._calculate_engagement_frequency(engagements),
                "response_patterns": self._analyze_response_patterns(engagements)
            }
            
            return patterns
            
        except Exception as e:
            logger.error(f"Failed to analyze user engagement patterns: {e}")
            return {"patterns": []}
    
    def _calculate_user_response_times(self, engagement_data: Dict) -> Dict:
        """Calculate user response time metrics."""
        try:
            response_times = []
            read_times = []
            click_times = []
            
            for engagement in engagement_data.get("engagements", []):
                if engagement.notification.sent_at:
                    if engagement.read_at:
                        read_time = (engagement.read_at - engagement.notification.sent_at).total_seconds() / 60
                        read_times.append(read_time)
                    
                    if engagement.clicked_at:
                        click_time = (engagement.clicked_at - engagement.notification.sent_at).total_seconds() / 60
                        click_times.append(click_time)
                    
                    if engagement.responded_at:
                        response_time = (engagement.responded_at - engagement.notification.sent_at).total_seconds() / 60
                        response_times.append(response_time)
            
            return {
                "average_read_time_minutes": round(sum(read_times) / len(read_times), 2) if read_times else 0,
                "average_click_time_minutes": round(sum(click_times) / len(click_times), 2) if click_times else 0,
                "average_response_time_minutes": round(sum(response_times) / len(response_times), 2) if response_times else 0,
                "fastest_response_minutes": round(min(response_times), 2) if response_times else 0,
                "slowest_response_minutes": round(max(response_times), 2) if response_times else 0
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate user response times: {e}")
            return {}
    
    def _generate_user_recommendations(
        self,
        notifications: List[Notification],
        engagement_data: Dict
    ) -> List[Dict]:
        """Generate recommendations for improving user engagement."""
        try:
            recommendations = []
            
            # Analyze engagement rates
            total_notifications = len(notifications)
            read_count = engagement_data["read_count"]
            click_count = engagement_data["clicked_count"]
            response_count = engagement_data["responded_count"]
            
            read_rate = (read_count / total_notifications * 100) if total_notifications > 0 else 0
            click_rate = (click_count / total_notifications * 100) if total_notifications > 0 else 0
            response_rate = (response_count / total_notifications * 100) if total_notifications > 0 else 0
            
            # Generate recommendations based on low engagement
            if read_rate < 50:
                recommendations.append({
                    "type": "improve_readability",
                    "title": "Improve Notification Readability",
                    "description": f"Read rate is {read_rate:.1f}%. Consider shorter, more compelling subject lines and content.",
                    "priority": "high"
                })
            
            if click_rate < 20:
                recommendations.append({
                    "type": "add_clear_cta",
                    "title": "Add Clear Call-to-Action",
                    "description": f"Click rate is {click_rate:.1f}%. Add clear, actionable buttons and links.",
                    "priority": "medium"
                })
            
            if response_rate < 10:
                recommendations.append({
                    "type": "simplify_response",
                    "title": "Simplify Response Process",
                    "description": f"Response rate is {response_rate:.1f}%. Make it easier for users to respond to notifications.",
                    "priority": "high"
                })
            
            # Analyze channel performance
            channel_performance = self._get_user_preferred_channels(notifications, engagement_data)
            if channel_performance:
                best_channel = channel_performance[0]
                worst_channel = channel_performance[-1]
                
                if best_channel["engagement_rate"] - worst_channel["engagement_rate"] > 30:
                    recommendations.append({
                        "type": "optimize_channels",
                        "title": "Optimize Channel Usage",
                        "description": f"Consider focusing on {best_channel['channel']} channel (engagement: {best_channel['engagement_rate']:.1f}%) over {worst_channel['channel']} (engagement: {worst_channel['engagement_rate']:.1f}%).",
                        "priority": "medium"
                    })
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Failed to generate user recommendations: {e}")
            return []
    
    def _group_by_time_period(self, notifications: List[Notification], granularity: str) -> List[Dict]:
        """Group notifications by time period for trend analysis."""
        try:
            # This would implement time-based grouping
            # For now, return empty list
            return []
            
        except Exception as e:
            logger.error(f"Failed to group by time period: {e}")
            return []
    
    def _calculate_trend_summary(self, trends: List[Dict]) -> Dict:
        """Calculate trend summary statistics."""
        try:
            # This would calculate trend summary
            # For now, return empty dict
            return {}
            
        except Exception as e:
            logger.error(f"Failed to calculate trend summary: {e}")
            return {}
    
    def _get_most_engaged_hour(self, engagements: List[NotificationEngagement]) -> Optional[int]:
        """Get the hour with most engagement activity."""
        try:
            hour_counts = {}
            for engagement in engagements:
                if engagement.read_at:
                    hour = engagement.read_at.hour
                    hour_counts[hour] = hour_counts.get(hour, 0) + 1
            
            return max(hour_counts.items(), key=lambda x: x[1])[0] if hour_counts else None
            
        except Exception as e:
            logger.error(f"Failed to get most engaged hour: {e}")
            return None
    
    def _get_most_engaged_day(self, engagements: List[NotificationEngagement]) -> Optional[str]:
        """Get the day of week with most engagement activity."""
        try:
            day_counts = {}
            days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            
            for engagement in engagements:
                if engagement.read_at:
                    day = days[engagement.read_at.weekday()]
                    day_counts[day] = day_counts.get(day, 0) + 1
            
            return max(day_counts.items(), key=lambda x: x[1])[0] if day_counts else None
            
        except Exception as e:
            logger.error(f"Failed to get most engaged day: {e}")
            return None
    
    def _calculate_engagement_frequency(self, engagements: List[NotificationEngagement]) -> Dict:
        """Calculate engagement frequency metrics."""
        try:
            if not engagements:
                return {"daily_average": 0, "weekly_average": 0}
            
            # Calculate daily and weekly averages
            total_engagements = len(engagements)
            days_span = 1  # Default to 1 day if no time span
            
            if len(engagements) > 1:
                earliest = min(e.read_at or e.clicked_at or e.responded_at for e in engagements if e.read_at or e.clicked_at or e.responded_at)
                latest = max(e.read_at or e.clicked_at or e.responded_at for e in engagements if e.read_at or e.clicked_at or e.responded_at)
                days_span = (latest - earliest).days + 1
            
            return {
                "daily_average": round(total_engagements / days_span, 2),
                "weekly_average": round(total_engagements / (days_span / 7), 2)
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate engagement frequency: {e}")
            return {"daily_average": 0, "weekly_average": 0}
    
    def _analyze_response_patterns(self, engagements: List[NotificationEngagement]) -> Dict:
        """Analyze user response patterns."""
        try:
            # This would analyze response patterns
            # For now, return empty dict
            return {}
            
        except Exception as e:
            logger.error(f"Failed to analyze response patterns: {e}")
            return {}
    
    def _empty_metrics(self) -> Dict:
        """Return empty metrics structure."""
        return {
            "overview": {
                "total_notifications": 0,
                "total_sent": 0,
                "total_delivered": 0,
                "total_failed": 0,
                "delivery_rate": 0,
                "failure_rate": 0
            },
            "engagement": {
                "read_count": 0,
                "clicked_count": 0,
                "responded_count": 0,
                "dismissed_count": 0,
                "read_rate": 0,
                "click_rate": 0,
                "response_rate": 0,
                "dismissal_rate": 0
            },
            "time_metrics": {
                "average_read_time_minutes": 0,
                "average_click_time_minutes": 0,
                "average_response_time_minutes": 0
            },
            "channel_performance": {},
            "type_performance": {},
            "user_engagement_score": 0
        }
    
    def _empty_user_profile(self, user_id: uuid.UUID) -> Dict:
        """Return empty user profile structure."""
        return {
            "user_id": str(user_id),
            "notification_activity": {
                "total_received": 0,
                "total_read": 0,
                "total_clicked": 0,
                "total_responded": 0,
                "total_dismissed": 0
            },
            "engagement_rates": {
                "read_rate": 0,
                "click_rate": 0,
                "response_rate": 0,
                "dismissal_rate": 0
            },
            "preferred_channels": [],
            "preferred_types": [],
            "engagement_patterns": {"patterns": []},
            "response_times": {},
            "engagement_score": 0,
            "recommendations": []
        }


def get_engagement_analytics_service(db: Session) -> EngagementAnalyticsService:
    """Get engagement analytics service instance."""
    return EngagementAnalyticsService(db)
