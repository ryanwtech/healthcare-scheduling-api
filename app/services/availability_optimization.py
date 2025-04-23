"""Smart availability optimization and suggestions service."""

import uuid
from datetime import datetime, timedelta, UTC
from enum import Enum
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models import Appointment, AppointmentStatus, DoctorProfile, User
from app.security.audit import AuditLogger, get_audit_logger

logger = get_logger(__name__)


class OptimizationStrategy(str, Enum):
    """Availability optimization strategies."""
    MAXIMIZE_UTILIZATION = "maximize_utilization"
    MINIMIZE_GAPS = "minimize_gaps"
    BALANCE_WORKLOAD = "balance_workload"
    PATIENT_PREFERENCE = "patient_preference"
    REVENUE_OPTIMIZATION = "revenue_optimization"


class TimeSlotType(str, Enum):
    """Types of time slots."""
    AVAILABLE = "available"
    BOOKED = "booked"
    BREAK = "break"
    UNAVAILABLE = "unavailable"
    PREFERRED = "preferred"
    FLEXIBLE = "flexible"


class AvailabilityOptimizationService:
    """Service for optimizing doctor availability and scheduling."""
    
    def __init__(self, db: Session):
        self.db = db
        self.audit_logger = get_audit_logger(db)
        
        # Optimization parameters
        self.working_hours_start = 8  # 8 AM
        self.working_hours_end = 18   # 6 PM
        self.lunch_break_start = 12   # 12 PM
        self.lunch_break_end = 13     # 1 PM
        self.min_slot_duration_minutes = 15
        self.max_slot_duration_minutes = 120
        self.buffer_time_minutes = 15
    
    def analyze_availability_patterns(
        self,
        doctor_id: uuid.UUID,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """
        Analyze doctor's availability patterns for optimization.
        
        Args:
            doctor_id: Doctor ID
            start_date: Analysis start date
            end_date: Analysis end date
            
        Returns:
            Analysis results with optimization suggestions
        """
        try:
            # Get doctor's appointments in the period
            appointments = self._get_doctor_appointments(doctor_id, start_date, end_date)
            
            # Analyze patterns
            patterns = self._analyze_scheduling_patterns(appointments)
            
            # Generate optimization suggestions
            suggestions = self._generate_optimization_suggestions(patterns, doctor_id)
            
            # Calculate utilization metrics
            metrics = self._calculate_utilization_metrics(appointments, start_date, end_date)
            
            analysis = {
                "doctor_id": doctor_id,
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "patterns": patterns,
                "suggestions": suggestions,
                "metrics": metrics
            }
            
            # Log analysis
            self.audit_logger.log_event(
                event_type="phi_access",
                user_id=doctor_id,
                action="availability_analysis",
                details={
                    "doctor_id": str(doctor_id),
                    "appointment_count": len(appointments),
                    "utilization_rate": metrics.get("utilization_rate", 0)
                },
                success=True
            )
            
            logger.info(f"Analyzed availability patterns for doctor {doctor_id}")
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze availability patterns: {e}")
            return {}
    
    def suggest_optimal_schedule(
        self,
        doctor_id: uuid.UUID,
        target_date: datetime,
        strategy: OptimizationStrategy = OptimizationStrategy.MAXIMIZE_UTILIZATION
    ) -> Dict:
        """
        Suggest optimal schedule for a specific date.
        
        Args:
            doctor_id: Doctor ID
            target_date: Target date for optimization
            strategy: Optimization strategy to use
            
        Returns:
            Optimal schedule suggestions
        """
        try:
            # Get existing appointments for the date
            start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1)
            
            existing_appointments = self._get_doctor_appointments(doctor_id, start_of_day, end_of_day)
            
            # Generate time slots
            time_slots = self._generate_optimal_time_slots(
                target_date, existing_appointments, strategy
            )
            
            # Apply optimization strategy
            optimized_slots = self._apply_optimization_strategy(time_slots, strategy)
            
            # Generate recommendations
            recommendations = self._generate_schedule_recommendations(
                optimized_slots, existing_appointments, strategy
            )
            
            schedule = {
                "doctor_id": doctor_id,
                "target_date": target_date.isoformat(),
                "strategy": strategy.value,
                "time_slots": optimized_slots,
                "recommendations": recommendations,
                "existing_appointments": [
                    {
                        "id": str(apt.id),
                        "start_time": apt.start_time.isoformat(),
                        "end_time": apt.end_time.isoformat(),
                        "patient_id": str(apt.patient_id)
                    }
                    for apt in existing_appointments
                ]
            }
            
            logger.info(f"Generated optimal schedule for doctor {doctor_id} on {target_date.date()}")
            return schedule
            
        except Exception as e:
            logger.error(f"Failed to suggest optimal schedule: {e}")
            return {}
    
    def find_best_available_slots(
        self,
        doctor_id: uuid.UUID,
        start_date: datetime,
        end_date: datetime,
        duration_minutes: int,
        preferred_times: Optional[List[datetime]] = None,
        max_suggestions: int = 5
    ) -> List[Dict]:
        """
        Find the best available time slots for an appointment.
        
        Args:
            doctor_id: Doctor ID
            start_date: Search start date
            end_date: Search end date
            duration_minutes: Required appointment duration
            preferred_times: Preferred time slots
            max_suggestions: Maximum number of suggestions
            
        Returns:
            List of best available slots
        """
        try:
            # Get doctor's appointments in the period
            appointments = self._get_doctor_appointments(doctor_id, start_date, end_date)
            
            # Generate available slots
            available_slots = self._generate_available_slots(
                start_date, end_date, duration_minutes, appointments
            )
            
            # Score slots based on preferences
            scored_slots = self._score_available_slots(
                available_slots, preferred_times, duration_minutes
            )
            
            # Sort by score and return top suggestions
            best_slots = sorted(scored_slots, key=lambda x: x["score"], reverse=True)[:max_suggestions]
            
            logger.info(f"Found {len(best_slots)} best available slots for doctor {doctor_id}")
            return best_slots
            
        except Exception as e:
            logger.error(f"Failed to find best available slots: {e}")
            return []
    
    def optimize_existing_schedule(
        self,
        doctor_id: uuid.UUID,
        target_date: datetime,
        optimization_goals: List[str]
    ) -> Dict:
        """
        Optimize existing schedule by suggesting improvements.
        
        Args:
            doctor_id: Doctor ID
            target_date: Target date for optimization
            optimization_goals: List of optimization goals
            
        Returns:
            Optimization suggestions
        """
        try:
            # Get existing appointments
            start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1)
            
            appointments = self._get_doctor_appointments(doctor_id, start_of_day, end_of_day)
            
            # Analyze current schedule
            current_analysis = self._analyze_current_schedule(appointments)
            
            # Generate optimization suggestions
            suggestions = []
            
            for goal in optimization_goals:
                if goal == "minimize_gaps":
                    suggestions.extend(self._suggest_gap_minimization(appointments))
                elif goal == "maximize_utilization":
                    suggestions.extend(self._suggest_utilization_improvements(appointments))
                elif goal == "balance_workload":
                    suggestions.extend(self._suggest_workload_balancing(appointments))
                elif goal == "reduce_travel_time":
                    suggestions.extend(self._suggest_travel_optimization(appointments))
            
            optimization = {
                "doctor_id": doctor_id,
                "target_date": target_date.isoformat(),
                "current_analysis": current_analysis,
                "suggestions": suggestions,
                "optimization_goals": optimization_goals
            }
            
            logger.info(f"Generated optimization suggestions for doctor {doctor_id}")
            return optimization
            
        except Exception as e:
            logger.error(f"Failed to optimize existing schedule: {e}")
            return {}
    
    def _get_doctor_appointments(
        self,
        doctor_id: uuid.UUID,
        start_date: datetime,
        end_date: datetime
    ) -> List[Appointment]:
        """Get doctor's appointments in a date range."""
        return (
            self.db.query(Appointment)
            .filter(
                Appointment.doctor_id == doctor_id,
                Appointment.start_time >= start_date,
                Appointment.start_time < end_date,
                Appointment.status == AppointmentStatus.SCHEDULED
            )
            .order_by(Appointment.start_time)
            .all()
        )
    
    def _analyze_scheduling_patterns(self, appointments: List[Appointment]) -> Dict:
        """Analyze scheduling patterns from appointments."""
        if not appointments:
            return {"total_appointments": 0}
        
        # Calculate time patterns
        start_times = [apt.start_time.hour for apt in appointments]
        durations = [(apt.end_time - apt.start_time).total_seconds() / 60 for apt in appointments]
        
        # Find peak hours
        hour_counts = {}
        for hour in start_times:
            hour_counts[hour] = hour_counts.get(hour, 0) + 1
        
        peak_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        
        # Calculate average duration
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        # Find gaps between appointments
        gaps = []
        for i in range(len(appointments) - 1):
            gap = (appointments[i + 1].start_time - appointments[i].end_time).total_seconds() / 60
            if gap > 0:
                gaps.append(gap)
        
        return {
            "total_appointments": len(appointments),
            "peak_hours": [{"hour": hour, "count": count} for hour, count in peak_hours],
            "average_duration_minutes": round(avg_duration, 2),
            "total_gaps": len(gaps),
            "average_gap_minutes": round(sum(gaps) / len(gaps), 2) if gaps else 0,
            "longest_gap_minutes": round(max(gaps), 2) if gaps else 0
        }
    
    def _generate_optimization_suggestions(self, patterns: Dict, doctor_id: uuid.UUID) -> List[Dict]:
        """Generate optimization suggestions based on patterns."""
        suggestions = []
        
        # Suggest based on peak hours
        if patterns.get("peak_hours"):
            peak_hour = patterns["peak_hours"][0]["hour"]
            if peak_hour < 10:  # Morning peak
                suggestions.append({
                    "type": "schedule_optimization",
                    "title": "Consider extending morning hours",
                    "description": f"Peak activity at {peak_hour}:00 AM. Consider starting earlier or adding more morning slots.",
                    "priority": "medium"
                })
            elif peak_hour > 14:  # Afternoon peak
                suggestions.append({
                    "type": "schedule_optimization",
                    "title": "Consider extending afternoon hours",
                    "description": f"Peak activity at {peak_hour}:00 PM. Consider extending afternoon availability.",
                    "priority": "medium"
                })
        
        # Suggest based on gaps
        avg_gap = patterns.get("average_gap_minutes", 0)
        if avg_gap > 30:
            suggestions.append({
                "type": "gap_optimization",
                "title": "Reduce appointment gaps",
                "description": f"Average gap is {avg_gap:.1f} minutes. Consider shorter buffer times or adding quick appointments.",
                "priority": "high"
            })
        
        # Suggest based on duration
        avg_duration = patterns.get("average_duration_minutes", 0)
        if avg_duration > 60:
            suggestions.append({
                "type": "duration_optimization",
                "title": "Consider shorter appointment slots",
                "description": f"Average duration is {avg_duration:.1f} minutes. Consider offering shorter consultation options.",
                "priority": "low"
            })
        
        return suggestions
    
    def _calculate_utilization_metrics(
        self,
        appointments: List[Appointment],
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Calculate utilization metrics."""
        if not appointments:
            return {"utilization_rate": 0, "total_booked_minutes": 0}
        
        # Calculate total working time
        total_days = (end_date - start_date).days
        working_hours_per_day = self.working_hours_end - self.working_hours_start
        total_working_minutes = total_days * working_hours_per_day * 60
        
        # Calculate booked time
        total_booked_minutes = sum(
            (apt.end_time - apt.start_time).total_seconds() / 60
            for apt in appointments
        )
        
        utilization_rate = (total_booked_minutes / total_working_minutes) * 100 if total_working_minutes > 0 else 0
        
        return {
            "utilization_rate": round(utilization_rate, 2),
            "total_booked_minutes": round(total_booked_minutes, 2),
            "total_working_minutes": total_working_minutes,
            "appointment_count": len(appointments)
        }
    
    def _generate_optimal_time_slots(
        self,
        target_date: datetime,
        existing_appointments: List[Appointment],
        strategy: OptimizationStrategy
    ) -> List[Dict]:
        """Generate optimal time slots for a date."""
        slots = []
        
        # Generate slots for the day
        current_time = target_date.replace(hour=self.working_hours_start, minute=0, second=0, microsecond=0)
        end_time = target_date.replace(hour=self.working_hours_end, minute=0, second=0, microsecond=0)
        
        while current_time < end_time:
            # Check if this time conflicts with existing appointments
            slot_type = self._determine_slot_type(current_time, existing_appointments)
            
            # Skip lunch break
            if self.lunch_break_start <= current_time.hour < self.lunch_break_end:
                current_time += timedelta(minutes=30)
                continue
            
            slot = {
                "start_time": current_time,
                "end_time": current_time + timedelta(minutes=30),  # Default 30-minute slots
                "type": slot_type,
                "score": self._calculate_slot_score(current_time, slot_type, strategy)
            }
            
            slots.append(slot)
            current_time += timedelta(minutes=30)
        
        return slots
    
    def _determine_slot_type(
        self,
        slot_time: datetime,
        existing_appointments: List[Appointment]
    ) -> TimeSlotType:
        """Determine the type of a time slot."""
        for apt in existing_appointments:
            if apt.start_time <= slot_time < apt.end_time:
                return TimeSlotType.BOOKED
        
        # Check if it's lunch break
        if self.lunch_break_start <= slot_time.hour < self.lunch_break_end:
            return TimeSlotType.BREAK
        
        return TimeSlotType.AVAILABLE
    
    def _calculate_slot_score(
        self,
        slot_time: datetime,
        slot_type: TimeSlotType,
        strategy: OptimizationStrategy
    ) -> float:
        """Calculate score for a time slot based on optimization strategy."""
        if slot_type != TimeSlotType.AVAILABLE:
            return 0.0
        
        base_score = 50.0
        
        # Adjust score based on strategy
        if strategy == OptimizationStrategy.MAXIMIZE_UTILIZATION:
            # Prefer slots that fill gaps
            if 9 <= slot_time.hour <= 11 or 14 <= slot_time.hour <= 16:
                base_score += 20
        elif strategy == OptimizationStrategy.PATIENT_PREFERENCE:
            # Prefer common appointment times
            if 9 <= slot_time.hour <= 11 or 14 <= slot_time.hour <= 16:
                base_score += 30
        elif strategy == OptimizationStrategy.BALANCE_WORKLOAD:
            # Prefer slots that balance the day
            if 8 <= slot_time.hour <= 10 or 15 <= slot_time.hour <= 17:
                base_score += 15
        
        return base_score
    
    def _apply_optimization_strategy(
        self,
        time_slots: List[Dict],
        strategy: OptimizationStrategy
    ) -> List[Dict]:
        """Apply optimization strategy to time slots."""
        if strategy == OptimizationStrategy.MAXIMIZE_UTILIZATION:
            # Sort by score descending
            return sorted(time_slots, key=lambda x: x["score"], reverse=True)
        elif strategy == OptimizationStrategy.MINIMIZE_GAPS:
            # Group consecutive available slots
            return self._group_consecutive_slots(time_slots)
        else:
            return time_slots
    
    def _group_consecutive_slots(self, time_slots: List[Dict]) -> List[Dict]:
        """Group consecutive available slots."""
        grouped_slots = []
        current_group = []
        
        for slot in time_slots:
            if slot["type"] == TimeSlotType.AVAILABLE:
                if not current_group or slot["start_time"] == current_group[-1]["end_time"]:
                    current_group.append(slot)
                else:
                    if current_group:
                        grouped_slots.append(self._merge_slot_group(current_group))
                    current_group = [slot]
            else:
                if current_group:
                    grouped_slots.append(self._merge_slot_group(current_group))
                    current_group = []
        
        if current_group:
            grouped_slots.append(self._merge_slot_group(current_group))
        
        return grouped_slots
    
    def _merge_slot_group(self, slots: List[Dict]) -> Dict:
        """Merge a group of consecutive slots."""
        return {
            "start_time": slots[0]["start_time"],
            "end_time": slots[-1]["end_time"],
            "type": TimeSlotType.AVAILABLE,
            "score": sum(slot["score"] for slot in slots),
            "duration_minutes": (slots[-1]["end_time"] - slots[0]["start_time"]).total_seconds() / 60,
            "slot_count": len(slots)
        }
    
    def _generate_schedule_recommendations(
        self,
        optimized_slots: List[Dict],
        existing_appointments: List[Appointment],
        strategy: OptimizationStrategy
    ) -> List[Dict]:
        """Generate schedule recommendations."""
        recommendations = []
        
        # Recommend filling gaps
        gaps = self._find_schedule_gaps(existing_appointments)
        for gap in gaps:
            recommendations.append({
                "type": "fill_gap",
                "title": "Fill schedule gap",
                "description": f"Gap from {gap['start_time'].strftime('%H:%M')} to {gap['end_time'].strftime('%H:%M')}",
                "duration_minutes": gap["duration_minutes"],
                "priority": "high" if gap["duration_minutes"] > 60 else "medium"
            })
        
        # Recommend extending hours
        if strategy == OptimizationStrategy.MAXIMIZE_UTILIZATION:
            recommendations.append({
                "type": "extend_hours",
                "title": "Consider extending working hours",
                "description": "High utilization suggests extending availability",
                "priority": "low"
            })
        
        return recommendations
    
    def _find_schedule_gaps(self, appointments: List[Appointment]) -> List[Dict]:
        """Find gaps in the schedule."""
        gaps = []
        
        if not appointments:
            return gaps
        
        # Sort appointments by start time
        sorted_appointments = sorted(appointments, key=lambda x: x.start_time)
        
        # Check for gaps between appointments
        for i in range(len(sorted_appointments) - 1):
            current_end = sorted_appointments[i].end_time
            next_start = sorted_appointments[i + 1].start_time
            
            gap_duration = (next_start - current_end).total_seconds() / 60
            
            if gap_duration >= 30:  # Only consider gaps of 30+ minutes
                gaps.append({
                    "start_time": current_end,
                    "end_time": next_start,
                    "duration_minutes": gap_duration
                })
        
        return gaps
    
    def _generate_available_slots(
        self,
        start_date: datetime,
        end_date: datetime,
        duration_minutes: int,
        appointments: List[Appointment]
    ) -> List[Dict]:
        """Generate available time slots."""
        slots = []
        current_time = start_date
        
        while current_time < end_date:
            slot_end = current_time + timedelta(minutes=duration_minutes)
            
            # Check if slot is available
            if self._is_slot_available(current_time, slot_end, appointments):
                slots.append({
                    "start_time": current_time,
                    "end_time": slot_end,
                    "duration_minutes": duration_minutes
                })
            
            current_time += timedelta(minutes=30)  # Check every 30 minutes
        
        return slots
    
    def _is_slot_available(
        self,
        start_time: datetime,
        end_time: datetime,
        appointments: List[Appointment]
    ) -> bool:
        """Check if a time slot is available."""
        for apt in appointments:
            if apt.start_time < end_time and apt.end_time > start_time:
                return False
        return True
    
    def _score_available_slots(
        self,
        slots: List[Dict],
        preferred_times: Optional[List[datetime]],
        duration_minutes: int
    ) -> List[Dict]:
        """Score available slots based on preferences."""
        scored_slots = []
        
        for slot in slots:
            score = 50.0  # Base score
            
            # Prefer morning and afternoon slots
            if 9 <= slot["start_time"].hour <= 11 or 14 <= slot["start_time"].hour <= 16:
                score += 20
            
            # Prefer weekdays
            if slot["start_time"].weekday() < 5:  # Monday-Friday
                score += 10
            
            # Prefer specific times if provided
            if preferred_times:
                for preferred_time in preferred_times:
                    time_diff = abs((slot["start_time"] - preferred_time).total_seconds() / 3600)
                    if time_diff < 1:  # Within 1 hour
                        score += 30
                    elif time_diff < 2:  # Within 2 hours
                        score += 15
            
            slot["score"] = score
            scored_slots.append(slot)
        
        return scored_slots
    
    def _analyze_current_schedule(self, appointments: List[Appointment]) -> Dict:
        """Analyze current schedule for optimization opportunities."""
        if not appointments:
            return {"total_appointments": 0}
        
        # Calculate metrics
        total_duration = sum(
            (apt.end_time - apt.start_time).total_seconds() / 60
            for apt in appointments
        )
        
        avg_duration = total_duration / len(appointments)
        
        # Find gaps
        gaps = self._find_schedule_gaps(appointments)
        total_gap_time = sum(gap["duration_minutes"] for gap in gaps)
        
        return {
            "total_appointments": len(appointments),
            "total_duration_minutes": round(total_duration, 2),
            "average_duration_minutes": round(avg_duration, 2),
            "total_gaps": len(gaps),
            "total_gap_time_minutes": round(total_gap_time, 2),
            "utilization_rate": round((total_duration / (8 * 60)) * 100, 2)  # Assuming 8-hour day
        }
    
    def _suggest_gap_minimization(self, appointments: List[Appointment]) -> List[Dict]:
        """Suggest ways to minimize gaps in schedule."""
        suggestions = []
        gaps = self._find_schedule_gaps(appointments)
        
        for gap in gaps:
            if gap["duration_minutes"] > 60:
                suggestions.append({
                    "type": "gap_minimization",
                    "title": "Fill large gap",
                    "description": f"Gap of {gap['duration_minutes']:.0f} minutes from {gap['start_time'].strftime('%H:%M')} to {gap['end_time'].strftime('%H:%M')}",
                    "priority": "high"
                })
        
        return suggestions
    
    def _suggest_utilization_improvements(self, appointments: List[Appointment]) -> List[Dict]:
        """Suggest utilization improvements."""
        suggestions = []
        
        # Check if schedule is underutilized
        total_duration = sum(
            (apt.end_time - apt.start_time).total_seconds() / 60
            for apt in appointments
        )
        
        utilization_rate = (total_duration / (8 * 60)) * 100  # Assuming 8-hour day
        
        if utilization_rate < 70:
            suggestions.append({
                "type": "utilization_improvement",
                "title": "Increase schedule utilization",
                "description": f"Current utilization is {utilization_rate:.1f}%. Consider adding more appointments.",
                "priority": "medium"
            })
        
        return suggestions
    
    def _suggest_workload_balancing(self, appointments: List[Appointment]) -> List[Dict]:
        """Suggest workload balancing improvements."""
        suggestions = []
        
        # Analyze hourly distribution
        hourly_counts = {}
        for apt in appointments:
            hour = apt.start_time.hour
            hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
        
        # Find imbalanced hours
        if hourly_counts:
            max_count = max(hourly_counts.values())
            min_count = min(hourly_counts.values())
            
            if max_count - min_count > 2:
                suggestions.append({
                    "type": "workload_balancing",
                    "title": "Balance workload distribution",
                    "description": "Appointment distribution is uneven across hours. Consider redistributing.",
                    "priority": "low"
                })
        
        return suggestions
    
    def _suggest_travel_optimization(self, appointments: List[Appointment]) -> List[Dict]:
        """Suggest travel optimization improvements."""
        suggestions = []
        
        # This would require location data for appointments
        # For now, suggest general optimization
        suggestions.append({
            "type": "travel_optimization",
            "title": "Optimize appointment sequence",
            "description": "Consider grouping appointments by location to reduce travel time.",
            "priority": "low"
        })
        
        return suggestions


def get_availability_optimization_service(db: Session) -> AvailabilityOptimizationService:
    """Get availability optimization service instance."""
    return AvailabilityOptimizationService(db)
