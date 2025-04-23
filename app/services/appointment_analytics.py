"""Appointment analytics and reporting service."""

import uuid
from datetime import datetime, timedelta, UTC
from enum import Enum
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from app.core.logging import get_logger
from app.db.models import Appointment, AppointmentStatus, DoctorProfile, User
from app.security.audit import AuditLogger, get_audit_logger

logger = get_logger(__name__)


class AnalyticsPeriod(str, Enum):
    """Analytics reporting periods."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    CUSTOM = "custom"


class MetricType(str, Enum):
    """Types of analytics metrics."""
    APPOINTMENT_COUNT = "appointment_count"
    UTILIZATION_RATE = "utilization_rate"
    CANCELLATION_RATE = "cancellation_rate"
    NO_SHOW_RATE = "no_show_rate"
    AVERAGE_DURATION = "average_duration"
    REVENUE = "revenue"
    PATIENT_SATISFACTION = "patient_satisfaction"
    WAIT_TIME = "wait_time"


class AppointmentAnalyticsService:
    """Service for appointment analytics and reporting."""
    
    def __init__(self, db: Session):
        self.db = db
        self.audit_logger = get_audit_logger(db)
    
    def get_appointment_analytics(
        self,
        start_date: datetime,
        end_date: datetime,
        doctor_id: Optional[uuid.UUID] = None,
        period: AnalyticsPeriod = AnalyticsPeriod.DAILY,
        metrics: Optional[List[MetricType]] = None
    ) -> Dict:
        """
        Get comprehensive appointment analytics.
        
        Args:
            doctor_id: Doctor ID (None for all doctors)
            start_date: Analytics start date
            end_date: Analytics end date
            period: Reporting period
            metrics: Specific metrics to include
            
        Returns:
            Analytics data
        """
        try:
            if not metrics:
                metrics = [
                    MetricType.APPOINTMENT_COUNT,
                    MetricType.UTILIZATION_RATE,
                    MetricType.CANCELLATION_RATE,
                    MetricType.NO_SHOW_RATE,
                    MetricType.AVERAGE_DURATION
                ]
            
            # Get base data
            appointments = self._get_appointments_for_analysis(doctor_id, start_date, end_date)
            
            # Calculate metrics
            analytics_data = {
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "period_type": period.value
                },
                "doctor_id": str(doctor_id) if doctor_id else "all",
                "metrics": {}
            }
            
            # Calculate each requested metric
            for metric in metrics:
                if metric == MetricType.APPOINTMENT_COUNT:
                    analytics_data["metrics"]["appointment_count"] = self._calculate_appointment_count(
                        appointments, period, start_date, end_date
                    )
                elif metric == MetricType.UTILIZATION_RATE:
                    analytics_data["metrics"]["utilization_rate"] = self._calculate_utilization_rate(
                        appointments, doctor_id, start_date, end_date
                    )
                elif metric == MetricType.CANCELLATION_RATE:
                    analytics_data["metrics"]["cancellation_rate"] = self._calculate_cancellation_rate(
                        appointments, period, start_date, end_date
                    )
                elif metric == MetricType.NO_SHOW_RATE:
                    analytics_data["metrics"]["no_show_rate"] = self._calculate_no_show_rate(
                        appointments, period, start_date, end_date
                    )
                elif metric == MetricType.AVERAGE_DURATION:
                    analytics_data["metrics"]["average_duration"] = self._calculate_average_duration(
                        appointments, period, start_date, end_date
                    )
                elif metric == MetricType.REVENUE:
                    analytics_data["metrics"]["revenue"] = self._calculate_revenue(
                        appointments, period, start_date, end_date
                    )
                elif metric == MetricType.PATIENT_SATISFACTION:
                    analytics_data["metrics"]["patient_satisfaction"] = self._calculate_patient_satisfaction(
                        appointments, period, start_date, end_date
                    )
                elif metric == MetricType.WAIT_TIME:
                    analytics_data["metrics"]["wait_time"] = self._calculate_wait_time(
                        appointments, period, start_date, end_date
                    )
            
            # Add summary statistics
            analytics_data["summary"] = self._calculate_summary_statistics(appointments)
            
            # Add trends
            analytics_data["trends"] = self._calculate_trends(appointments, period, start_date, end_date)
            
            # Log analytics access
            self.audit_logger.log_event(
                event_type="phi_access",
                user_id=doctor_id,
                action="analytics_generated",
                details={
                    "doctor_id": str(doctor_id) if doctor_id else "all",
                    "period": period.value,
                    "metrics_count": len(metrics)
                },
                success=True
            )
            
            logger.info(f"Generated analytics for doctor {doctor_id or 'all'} from {start_date} to {end_date}")
            return analytics_data
            
        except Exception as e:
            logger.error(f"Failed to generate analytics: {e}")
            return {}
    
    def get_doctor_performance_metrics(
        self,
        doctor_id: uuid.UUID,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Get detailed performance metrics for a specific doctor."""
        try:
            appointments = self._get_appointments_for_analysis(doctor_id, start_date, end_date)
            
            # Calculate performance metrics
            performance = {
                "doctor_id": str(doctor_id),
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "appointment_metrics": {
                    "total_appointments": len(appointments),
                    "scheduled": len([apt for apt in appointments if apt.status == AppointmentStatus.SCHEDULED]),
                    "completed": len([apt for apt in appointments if apt.status == AppointmentStatus.COMPLETED]),
                    "cancelled": len([apt for apt in appointments if apt.status == AppointmentStatus.CANCELLED]),
                    "no_show": len([apt for apt in appointments if apt.status == AppointmentStatus.NO_SHOW])
                },
                "efficiency_metrics": {
                    "average_duration_minutes": self._calculate_average_duration_minutes(appointments),
                    "utilization_rate": self._calculate_doctor_utilization_rate(doctor_id, appointments, start_date, end_date),
                    "cancellation_rate": self._calculate_cancellation_rate_percentage(appointments),
                    "no_show_rate": self._calculate_no_show_rate_percentage(appointments)
                },
                "patient_metrics": {
                    "unique_patients": len(set(apt.patient_id for apt in appointments)),
                    "new_patients": self._calculate_new_patients(doctor_id, appointments, start_date),
                    "returning_patients": self._calculate_returning_patients(doctor_id, appointments, start_date)
                },
                "revenue_metrics": {
                    "total_revenue": self._calculate_total_revenue(appointments),
                    "average_revenue_per_appointment": self._calculate_average_revenue_per_appointment(appointments),
                    "revenue_by_status": self._calculate_revenue_by_status(appointments)
                }
            }
            
            # Add recommendations
            performance["recommendations"] = self._generate_performance_recommendations(performance)
            
            logger.info(f"Generated performance metrics for doctor {doctor_id}")
            return performance
            
        except Exception as e:
            logger.error(f"Failed to generate performance metrics: {e}")
            return {}
    
    def get_patient_analytics(
        self,
        patient_id: uuid.UUID,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Get analytics for a specific patient."""
        try:
            appointments = self._get_appointments_for_analysis(None, start_date, end_date)
            patient_appointments = [apt for apt in appointments if apt.patient_id == patient_id]
            
            analytics = {
                "patient_id": str(patient_id),
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "appointment_history": {
                    "total_appointments": len(patient_appointments),
                    "completed": len([apt for apt in patient_appointments if apt.status == AppointmentStatus.COMPLETED]),
                    "cancelled": len([apt for apt in patient_appointments if apt.status == AppointmentStatus.CANCELLED]),
                    "no_show": len([apt for apt in patient_appointments if apt.status == AppointmentStatus.NO_SHOW])
                },
                "attendance_patterns": {
                    "average_interval_days": self._calculate_average_appointment_interval(patient_appointments),
                    "preferred_times": self._calculate_preferred_appointment_times(patient_appointments),
                    "preferred_doctors": self._calculate_preferred_doctors(patient_appointments)
                },
                "health_insights": {
                    "appointment_frequency": self._calculate_appointment_frequency(patient_appointments, start_date, end_date),
                    "cancellation_patterns": self._analyze_cancellation_patterns(patient_appointments),
                    "no_show_patterns": self._analyze_no_show_patterns(patient_appointments)
                }
            }
            
            logger.info(f"Generated patient analytics for patient {patient_id}")
            return analytics
            
        except Exception as e:
            logger.error(f"Failed to generate patient analytics: {e}")
            return {}
    
    def get_system_analytics(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Get system-wide analytics."""
        try:
            appointments = self._get_appointments_for_analysis(None, start_date, end_date)
            
            system_analytics = {
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "overview": {
                    "total_appointments": len(appointments),
                    "active_doctors": len(set(apt.doctor_id for apt in appointments)),
                    "active_patients": len(set(apt.patient_id for apt in appointments)),
                    "total_revenue": self._calculate_total_revenue(appointments)
                },
                "appointment_distribution": {
                    "by_status": self._calculate_appointment_distribution_by_status(appointments),
                    "by_doctor": self._calculate_appointment_distribution_by_doctor(appointments),
                    "by_hour": self._calculate_appointment_distribution_by_hour(appointments),
                    "by_day_of_week": self._calculate_appointment_distribution_by_day_of_week(appointments)
                },
                "performance_metrics": {
                    "average_utilization_rate": self._calculate_system_utilization_rate(appointments, start_date, end_date),
                    "average_cancellation_rate": self._calculate_system_cancellation_rate(appointments),
                    "average_no_show_rate": self._calculate_system_no_show_rate(appointments),
                    "average_appointment_duration": self._calculate_system_average_duration(appointments)
                },
                "trends": {
                    "appointment_growth": self._calculate_appointment_growth_trend(appointments, start_date, end_date),
                    "revenue_growth": self._calculate_revenue_growth_trend(appointments, start_date, end_date),
                    "patient_growth": self._calculate_patient_growth_trend(appointments, start_date, end_date)
                }
            }
            
            logger.info(f"Generated system analytics from {start_date} to {end_date}")
            return system_analytics
            
        except Exception as e:
            logger.error(f"Failed to generate system analytics: {e}")
            return {}
    
    def _get_appointments_for_analysis(
        self,
        doctor_id: Optional[uuid.UUID],
        start_date: datetime,
        end_date: datetime
    ) -> List[Appointment]:
        """Get appointments for analysis."""
        query = self.db.query(Appointment).filter(
            Appointment.start_time >= start_date,
            Appointment.start_time <= end_date
        )
        
        if doctor_id:
            query = query.filter(Appointment.doctor_id == doctor_id)
        
        return query.all()
    
    def _calculate_appointment_count(
        self,
        appointments: List[Appointment],
        period: AnalyticsPeriod,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Calculate appointment count by period."""
        counts = {}
        
        if period == AnalyticsPeriod.DAILY:
            current_date = start_date.date()
            end_date_only = end_date.date()
            
            while current_date <= end_date_only:
                day_appointments = [
                    apt for apt in appointments
                    if apt.start_time.date() == current_date
                ]
                counts[current_date.isoformat()] = len(day_appointments)
                current_date += timedelta(days=1)
        
        elif period == AnalyticsPeriod.WEEKLY:
            current_date = start_date
            while current_date <= end_date:
                week_end = current_date + timedelta(days=6)
                week_appointments = [
                    apt for apt in appointments
                    if current_date <= apt.start_time <= week_end
                ]
                counts[current_date.isoformat()] = len(week_appointments)
                current_date += timedelta(weeks=1)
        
        elif period == AnalyticsPeriod.MONTHLY:
            current_date = start_date.replace(day=1)
            while current_date <= end_date:
                next_month = current_date.replace(day=1) + timedelta(days=32)
                next_month = next_month.replace(day=1)
                month_appointments = [
                    apt for apt in appointments
                    if current_date <= apt.start_time < next_month
                ]
                counts[current_date.strftime("%Y-%m")] = len(month_appointments)
                current_date = next_month
        
        return counts
    
    def _calculate_utilization_rate(
        self,
        appointments: List[Appointment],
        doctor_id: Optional[uuid.UUID],
        start_date: datetime,
        end_date: datetime
    ) -> float:
        """Calculate utilization rate."""
        if not appointments:
            return 0.0
        
        # Calculate total working time
        total_days = (end_date - start_date).days
        working_hours_per_day = 8  # Assuming 8-hour workday
        total_working_minutes = total_days * working_hours_per_day * 60
        
        # Calculate booked time
        total_booked_minutes = sum(
            (apt.end_time - apt.start_time).total_seconds() / 60
            for apt in appointments
        )
        
        return (total_booked_minutes / total_working_minutes) * 100 if total_working_minutes > 0 else 0.0
    
    def _calculate_cancellation_rate(
        self,
        appointments: List[Appointment],
        period: AnalyticsPeriod,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Calculate cancellation rate by period."""
        rates = {}
        
        if period == AnalyticsPeriod.DAILY:
            current_date = start_date.date()
            end_date_only = end_date.date()
            
            while current_date <= end_date_only:
                day_appointments = [
                    apt for apt in appointments
                    if apt.start_time.date() == current_date
                ]
                
                if day_appointments:
                    cancelled = len([apt for apt in day_appointments if apt.status == AppointmentStatus.CANCELLED])
                    rates[current_date.isoformat()] = (cancelled / len(day_appointments)) * 100
                else:
                    rates[current_date.isoformat()] = 0.0
                
                current_date += timedelta(days=1)
        
        return rates
    
    def _calculate_no_show_rate(
        self,
        appointments: List[Appointment],
        period: AnalyticsPeriod,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Calculate no-show rate by period."""
        rates = {}
        
        if period == AnalyticsPeriod.DAILY:
            current_date = start_date.date()
            end_date_only = end_date.date()
            
            while current_date <= end_date_only:
                day_appointments = [
                    apt for apt in appointments
                    if apt.start_time.date() == current_date
                ]
                
                if day_appointments:
                    no_shows = len([apt for apt in day_appointments if apt.status == AppointmentStatus.NO_SHOW])
                    rates[current_date.isoformat()] = (no_shows / len(day_appointments)) * 100
                else:
                    rates[current_date.isoformat()] = 0.0
                
                current_date += timedelta(days=1)
        
        return rates
    
    def _calculate_average_duration(
        self,
        appointments: List[Appointment],
        period: AnalyticsPeriod,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Calculate average appointment duration by period."""
        durations = {}
        
        if period == AnalyticsPeriod.DAILY:
            current_date = start_date.date()
            end_date_only = end_date.date()
            
            while current_date <= end_date_only:
                day_appointments = [
                    apt for apt in appointments
                    if apt.start_time.date() == current_date
                ]
                
                if day_appointments:
                    avg_duration = sum(
                        (apt.end_time - apt.start_time).total_seconds() / 60
                        for apt in day_appointments
                    ) / len(day_appointments)
                    durations[current_date.isoformat()] = round(avg_duration, 2)
                else:
                    durations[current_date.isoformat()] = 0.0
                
                current_date += timedelta(days=1)
        
        return durations
    
    def _calculate_revenue(
        self,
        appointments: List[Appointment],
        period: AnalyticsPeriod,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Calculate revenue by period."""
        # This would require a revenue field in the appointment model
        # For now, return placeholder data
        return {"note": "Revenue calculation requires revenue data in appointment model"}
    
    def _calculate_patient_satisfaction(
        self,
        appointments: List[Appointment],
        period: AnalyticsPeriod,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Calculate patient satisfaction by period."""
        # This would require a satisfaction rating field
        # For now, return placeholder data
        return {"note": "Patient satisfaction calculation requires satisfaction data"}
    
    def _calculate_wait_time(
        self,
        appointments: List[Appointment],
        period: AnalyticsPeriod,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Calculate average wait time by period."""
        # This would require wait time tracking
        # For now, return placeholder data
        return {"note": "Wait time calculation requires wait time tracking"}
    
    def _calculate_summary_statistics(self, appointments: List[Appointment]) -> Dict:
        """Calculate summary statistics."""
        if not appointments:
            return {}
        
        total_appointments = len(appointments)
        completed = len([apt for apt in appointments if apt.status == AppointmentStatus.COMPLETED])
        cancelled = len([apt for apt in appointments if apt.status == AppointmentStatus.CANCELLED])
        no_show = len([apt for apt in appointments if apt.status == AppointmentStatus.NO_SHOW])
        
        return {
            "total_appointments": total_appointments,
            "completed_appointments": completed,
            "cancelled_appointments": cancelled,
            "no_show_appointments": no_show,
            "completion_rate": (completed / total_appointments) * 100 if total_appointments > 0 else 0,
            "cancellation_rate": (cancelled / total_appointments) * 100 if total_appointments > 0 else 0,
            "no_show_rate": (no_show / total_appointments) * 100 if total_appointments > 0 else 0
        }
    
    def _calculate_trends(
        self,
        appointments: List[Appointment],
        period: AnalyticsPeriod,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Calculate trends over time."""
        # This would implement trend analysis
        # For now, return placeholder data
        return {"note": "Trend analysis requires historical data comparison"}
    
    def _calculate_average_duration_minutes(self, appointments: List[Appointment]) -> float:
        """Calculate average appointment duration in minutes."""
        if not appointments:
            return 0.0
        
        total_duration = sum(
            (apt.end_time - apt.start_time).total_seconds() / 60
            for apt in appointments
        )
        
        return total_duration / len(appointments)
    
    def _calculate_doctor_utilization_rate(
        self,
        doctor_id: uuid.UUID,
        appointments: List[Appointment],
        start_date: datetime,
        end_date: datetime
    ) -> float:
        """Calculate doctor utilization rate."""
        return self._calculate_utilization_rate(appointments, doctor_id, start_date, end_date)
    
    def _calculate_cancellation_rate_percentage(self, appointments: List[Appointment]) -> float:
        """Calculate cancellation rate percentage."""
        if not appointments:
            return 0.0
        
        cancelled = len([apt for apt in appointments if apt.status == AppointmentStatus.CANCELLED])
        return (cancelled / len(appointments)) * 100
    
    def _calculate_no_show_rate_percentage(self, appointments: List[Appointment]) -> float:
        """Calculate no-show rate percentage."""
        if not appointments:
            return 0.0
        
        no_shows = len([apt for apt in appointments if apt.status == AppointmentStatus.NO_SHOW])
        return (no_shows / len(appointments)) * 100
    
    def _calculate_new_patients(
        self,
        doctor_id: uuid.UUID,
        appointments: List[Appointment],
        start_date: datetime
    ) -> int:
        """Calculate number of new patients."""
        # This would require historical data to determine new vs returning patients
        # For now, return placeholder
        return 0
    
    def _calculate_returning_patients(
        self,
        doctor_id: uuid.UUID,
        appointments: List[Appointment],
        start_date: datetime
    ) -> int:
        """Calculate number of returning patients."""
        # This would require historical data to determine new vs returning patients
        # For now, return placeholder
        return 0
    
    def _calculate_total_revenue(self, appointments: List[Appointment]) -> float:
        """Calculate total revenue from appointments."""
        # This would require revenue data in the appointment model
        # For now, return placeholder
        return 0.0
    
    def _calculate_average_revenue_per_appointment(self, appointments: List[Appointment]) -> float:
        """Calculate average revenue per appointment."""
        # This would require revenue data in the appointment model
        # For now, return placeholder
        return 0.0
    
    def _calculate_revenue_by_status(self, appointments: List[Appointment]) -> Dict:
        """Calculate revenue by appointment status."""
        # This would require revenue data in the appointment model
        # For now, return placeholder
        return {}
    
    def _generate_performance_recommendations(self, performance: Dict) -> List[Dict]:
        """Generate performance recommendations."""
        recommendations = []
        
        # Check utilization rate
        utilization_rate = performance.get("efficiency_metrics", {}).get("utilization_rate", 0)
        if utilization_rate < 70:
            recommendations.append({
                "type": "utilization",
                "title": "Improve schedule utilization",
                "description": f"Current utilization rate is {utilization_rate:.1f}%. Consider adding more appointments.",
                "priority": "medium"
            })
        
        # Check cancellation rate
        cancellation_rate = performance.get("efficiency_metrics", {}).get("cancellation_rate", 0)
        if cancellation_rate > 20:
            recommendations.append({
                "type": "cancellation",
                "title": "Reduce cancellation rate",
                "description": f"Current cancellation rate is {cancellation_rate:.1f}%. Consider improving scheduling flexibility.",
                "priority": "high"
            })
        
        # Check no-show rate
        no_show_rate = performance.get("efficiency_metrics", {}).get("no_show_rate", 0)
        if no_show_rate > 15:
            recommendations.append({
                "type": "no_show",
                "title": "Reduce no-show rate",
                "description": f"Current no-show rate is {no_show_rate:.1f}%. Consider implementing reminder systems.",
                "priority": "high"
            })
        
        return recommendations
    
    def _calculate_average_appointment_interval(self, appointments: List[Appointment]) -> float:
        """Calculate average interval between appointments for a patient."""
        if len(appointments) < 2:
            return 0.0
        
        intervals = []
        sorted_appointments = sorted(appointments, key=lambda x: x.start_time)
        
        for i in range(1, len(sorted_appointments)):
            interval = (sorted_appointments[i].start_time - sorted_appointments[i-1].start_time).days
            intervals.append(interval)
        
        return sum(intervals) / len(intervals) if intervals else 0.0
    
    def _calculate_preferred_appointment_times(self, appointments: List[Appointment]) -> Dict:
        """Calculate preferred appointment times for a patient."""
        if not appointments:
            return {}
        
        hour_counts = {}
        for apt in appointments:
            hour = apt.start_time.hour
            hour_counts[hour] = hour_counts.get(hour, 0) + 1
        
        return dict(sorted(hour_counts.items(), key=lambda x: x[1], reverse=True))
    
    def _calculate_preferred_doctors(self, appointments: List[Appointment]) -> Dict:
        """Calculate preferred doctors for a patient."""
        if not appointments:
            return {}
        
        doctor_counts = {}
        for apt in appointments:
            doctor_id = apt.doctor_id
            doctor_counts[doctor_id] = doctor_counts.get(doctor_id, 0) + 1
        
        return dict(sorted(doctor_counts.items(), key=lambda x: x[1], reverse=True))
    
    def _calculate_appointment_frequency(
        self,
        appointments: List[Appointment],
        start_date: datetime,
        end_date: datetime
    ) -> float:
        """Calculate appointment frequency for a patient."""
        if not appointments:
            return 0.0
        
        total_days = (end_date - start_date).days
        return len(appointments) / total_days if total_days > 0 else 0.0
    
    def _analyze_cancellation_patterns(self, appointments: List[Appointment]) -> Dict:
        """Analyze cancellation patterns for a patient."""
        cancelled_appointments = [apt for apt in appointments if apt.status == AppointmentStatus.CANCELLED]
        
        if not cancelled_appointments:
            return {"total_cancellations": 0, "cancellation_rate": 0.0}
        
        return {
            "total_cancellations": len(cancelled_appointments),
            "cancellation_rate": (len(cancelled_appointments) / len(appointments)) * 100
        }
    
    def _analyze_no_show_patterns(self, appointments: List[Appointment]) -> Dict:
        """Analyze no-show patterns for a patient."""
        no_show_appointments = [apt for apt in appointments if apt.status == AppointmentStatus.NO_SHOW]
        
        if not no_show_appointments:
            return {"total_no_shows": 0, "no_show_rate": 0.0}
        
        return {
            "total_no_shows": len(no_show_appointments),
            "no_show_rate": (len(no_show_appointments) / len(appointments)) * 100
        }
    
    def _calculate_appointment_distribution_by_status(self, appointments: List[Appointment]) -> Dict:
        """Calculate appointment distribution by status."""
        distribution = {}
        for apt in appointments:
            status = apt.status.value
            distribution[status] = distribution.get(status, 0) + 1
        return distribution
    
    def _calculate_appointment_distribution_by_doctor(self, appointments: List[Appointment]) -> Dict:
        """Calculate appointment distribution by doctor."""
        distribution = {}
        for apt in appointments:
            doctor_id = str(apt.doctor_id)
            distribution[doctor_id] = distribution.get(doctor_id, 0) + 1
        return distribution
    
    def _calculate_appointment_distribution_by_hour(self, appointments: List[Appointment]) -> Dict:
        """Calculate appointment distribution by hour."""
        distribution = {}
        for apt in appointments:
            hour = apt.start_time.hour
            distribution[hour] = distribution.get(hour, 0) + 1
        return distribution
    
    def _calculate_appointment_distribution_by_day_of_week(self, appointments: List[Appointment]) -> Dict:
        """Calculate appointment distribution by day of week."""
        distribution = {}
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        
        for apt in appointments:
            day = days[apt.start_time.weekday()]
            distribution[day] = distribution.get(day, 0) + 1
        
        return distribution
    
    def _calculate_system_utilization_rate(
        self,
        appointments: List[Appointment],
        start_date: datetime,
        end_date: datetime
    ) -> float:
        """Calculate system-wide utilization rate."""
        return self._calculate_utilization_rate(appointments, None, start_date, end_date)
    
    def _calculate_system_cancellation_rate(self, appointments: List[Appointment]) -> float:
        """Calculate system-wide cancellation rate."""
        return self._calculate_cancellation_rate_percentage(appointments)
    
    def _calculate_system_no_show_rate(self, appointments: List[Appointment]) -> float:
        """Calculate system-wide no-show rate."""
        return self._calculate_no_show_rate_percentage(appointments)
    
    def _calculate_system_average_duration(self, appointments: List[Appointment]) -> float:
        """Calculate system-wide average appointment duration."""
        return self._calculate_average_duration_minutes(appointments)
    
    def _calculate_appointment_growth_trend(
        self,
        appointments: List[Appointment],
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Calculate appointment growth trend."""
        # This would implement growth trend analysis
        # For now, return placeholder data
        return {"note": "Growth trend analysis requires historical data comparison"}
    
    def _calculate_revenue_growth_trend(
        self,
        appointments: List[Appointment],
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Calculate revenue growth trend."""
        # This would implement revenue growth trend analysis
        # For now, return placeholder data
        return {"note": "Revenue growth trend analysis requires revenue data"}
    
    def _calculate_patient_growth_trend(
        self,
        appointments: List[Appointment],
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Calculate patient growth trend."""
        # This would implement patient growth trend analysis
        # For now, return placeholder data
        return {"note": "Patient growth trend analysis requires historical data comparison"}


def get_appointment_analytics_service(db: Session) -> AppointmentAnalyticsService:
    """Get appointment analytics service instance."""
    return AppointmentAnalyticsService(db)
