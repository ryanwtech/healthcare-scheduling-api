"""Intelligent conflict resolution for appointment scheduling."""

import uuid
from datetime import datetime, timedelta, UTC
from enum import Enum
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models import Appointment, AppointmentStatus, DoctorProfile, User
from app.security.audit import AuditLogger, get_audit_logger

logger = get_logger(__name__)


class ConflictType(str, Enum):
    """Types of appointment conflicts."""
    TIME_OVERLAP = "time_overlap"
    DOCTOR_UNAVAILABLE = "doctor_unavailable"
    PATIENT_DOUBLE_BOOKING = "patient_double_booking"
    RESOURCE_CONFLICT = "resource_conflict"
    SCHEDULING_RULE_VIOLATION = "scheduling_rule_violation"


class ConflictSeverity(str, Enum):
    """Conflict severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ResolutionStrategy(str, Enum):
    """Conflict resolution strategies."""
    REJECT = "reject"
    SUGGEST_ALTERNATIVE = "suggest_alternative"
    AUTO_RESOLVE = "auto_resolve"
    MANUAL_REVIEW = "manual_review"
    WAITLIST = "waitlist"


class ConflictResolutionService:
    """Service for intelligent conflict resolution."""
    
    def __init__(self, db: Session):
        self.db = db
        self.audit_logger = get_audit_logger(db)
        
        # Scheduling rules
        self.min_appointment_gap_minutes = 15
        self.max_appointment_duration_hours = 8
        self.working_hours_start = 8  # 8 AM
        self.working_hours_end = 18   # 6 PM
        self.lunch_break_start = 12   # 12 PM
        self.lunch_break_end = 13     # 1 PM
    
    def detect_conflicts(
        self,
        doctor_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime,
        patient_id: Optional[uuid.UUID] = None,
        exclude_appointment_id: Optional[uuid.UUID] = None
    ) -> List[Dict]:
        """
        Detect all conflicts for a proposed appointment.
        
        Args:
            doctor_id: Doctor ID
            start_time: Proposed start time
            end_time: Proposed end time
            patient_id: Patient ID (for double booking check)
            exclude_appointment_id: Appointment ID to exclude from conflict check
            
        Returns:
            List of conflict details
        """
        try:
            conflicts = []
            
            # Check time overlap conflicts
            time_conflicts = self._check_time_overlap_conflicts(
                doctor_id, start_time, end_time, exclude_appointment_id
            )
            conflicts.extend(time_conflicts)
            
            # Check doctor availability conflicts
            availability_conflicts = self._check_availability_conflicts(
                doctor_id, start_time, end_time
            )
            conflicts.extend(availability_conflicts)
            
            # Check patient double booking
            if patient_id:
                double_booking_conflicts = self._check_patient_double_booking(
                    patient_id, start_time, end_time, exclude_appointment_id
                )
                conflicts.extend(double_booking_conflicts)
            
            # Check scheduling rule violations
            rule_violations = self._check_scheduling_rules(
                start_time, end_time
            )
            conflicts.extend(rule_violations)
            
            # Log conflict detection
            if conflicts:
                self.audit_logger.log_event(
                    event_type="security_violation",
                    action="conflict_detected",
                    details={
                        "doctor_id": str(doctor_id),
                        "start_time": start_time.isoformat(),
                        "end_time": end_time.isoformat(),
                        "conflict_count": len(conflicts),
                        "conflict_types": [c["type"] for c in conflicts]
                    },
                    success=False
                )
            
            logger.info(f"Detected {len(conflicts)} conflicts for appointment proposal")
            return conflicts
            
        except Exception as e:
            logger.error(f"Failed to detect conflicts: {e}")
            return []
    
    def resolve_conflicts(
        self,
        conflicts: List[Dict],
        doctor_id: uuid.UUID,
        patient_id: uuid.UUID,
        preferred_start_time: datetime,
        preferred_end_time: datetime
    ) -> Dict:
        """
        Resolve conflicts using intelligent strategies.
        
        Args:
            conflicts: List of detected conflicts
            doctor_id: Doctor ID
            patient_id: Patient ID
            preferred_start_time: Preferred start time
            preferred_end_time: Preferred end time
            
        Returns:
            Resolution result with suggested actions
        """
        try:
            if not conflicts:
                return {
                    "resolved": True,
                    "strategy": ResolutionStrategy.AUTO_RESOLVE,
                    "message": "No conflicts detected",
                    "suggested_times": []
                }
            
            # Analyze conflicts
            conflict_analysis = self._analyze_conflicts(conflicts)
            
            # Determine resolution strategy
            strategy = self._determine_resolution_strategy(conflict_analysis)
            
            # Generate resolution suggestions
            suggestions = self._generate_resolution_suggestions(
                conflicts, doctor_id, patient_id, preferred_start_time, preferred_end_time
            )
            
            resolution = {
                "resolved": strategy == ResolutionStrategy.AUTO_RESOLVE,
                "strategy": strategy,
                "conflicts": conflicts,
                "analysis": conflict_analysis,
                "suggested_times": suggestions,
                "message": self._generate_resolution_message(strategy, conflicts)
            }
            
            # Log resolution attempt
            self.audit_logger.log_event(
                event_type="phi_access",
                user_id=patient_id,
                action="conflict_resolution",
                details={
                    "strategy": strategy.value,
                    "conflict_count": len(conflicts),
                    "suggestions_count": len(suggestions),
                    "resolved": resolution["resolved"]
                },
                success=resolution["resolved"]
            )
            
            logger.info(f"Conflict resolution completed: {strategy.value}")
            return resolution
            
        except Exception as e:
            logger.error(f"Failed to resolve conflicts: {e}")
            return {
                "resolved": False,
                "strategy": ResolutionStrategy.MANUAL_REVIEW,
                "message": "Failed to resolve conflicts",
                "suggested_times": []
            }
    
    def suggest_alternative_times(
        self,
        doctor_id: uuid.UUID,
        preferred_start_time: datetime,
        preferred_end_time: datetime,
        max_suggestions: int = 5
    ) -> List[Dict]:
        """
        Suggest alternative appointment times.
        
        Args:
            doctor_id: Doctor ID
            preferred_start_time: Preferred start time
            preferred_end_time: Preferred end time
            max_suggestions: Maximum number of suggestions
            
        Returns:
            List of alternative time suggestions
        """
        try:
            suggestions = []
            duration = end_time - start_time
            
            # Get doctor's existing appointments
            existing_appointments = self._get_doctor_appointments(doctor_id)
            
            # Generate time slots around preferred time
            time_slots = self._generate_time_slots(
                preferred_start_time, duration, max_suggestions * 3
            )
            
            for slot in time_slots:
                # Check if slot is available
                conflicts = self.detect_conflicts(
                    doctor_id, slot["start_time"], slot["end_time"]
                )
                
                if not conflicts:
                    suggestions.append({
                        "start_time": slot["start_time"],
                        "end_time": slot["end_time"],
                        "score": slot["score"],
                        "reason": slot["reason"]
                    })
                
                if len(suggestions) >= max_suggestions:
                    break
            
            # Sort by score (closest to preferred time first)
            suggestions.sort(key=lambda x: x["score"], reverse=True)
            
            logger.info(f"Generated {len(suggestions)} alternative time suggestions")
            return suggestions
            
        except Exception as e:
            logger.error(f"Failed to suggest alternative times: {e}")
            return []
    
    def _check_time_overlap_conflicts(
        self,
        doctor_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime,
        exclude_appointment_id: Optional[uuid.UUID]
    ) -> List[Dict]:
        """Check for time overlap conflicts."""
        conflicts = []
        
        # Query existing appointments
        query = self.db.query(Appointment).filter(
            Appointment.doctor_id == doctor_id,
            Appointment.status == AppointmentStatus.SCHEDULED,
            Appointment.start_time < end_time,
            Appointment.end_time > start_time
        )
        
        if exclude_appointment_id:
            query = query.filter(Appointment.id != exclude_appointment_id)
        
        overlapping_appointments = query.all()
        
        for appointment in overlapping_appointments:
            conflicts.append({
                "type": ConflictType.TIME_OVERLAP,
                "severity": ConflictSeverity.HIGH,
                "message": f"Time overlaps with existing appointment {appointment.id}",
                "conflicting_appointment": {
                    "id": appointment.id,
                    "start_time": appointment.start_time,
                    "end_time": appointment.end_time,
                    "patient_id": appointment.patient_id
                }
            })
        
        return conflicts
    
    def _check_availability_conflicts(
        self,
        doctor_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict]:
        """Check for doctor availability conflicts."""
        conflicts = []
        
        # Check if time is within working hours
        if not self._is_within_working_hours(start_time, end_time):
            conflicts.append({
                "type": ConflictType.DOCTOR_UNAVAILABLE,
                "severity": ConflictSeverity.MEDIUM,
                "message": "Appointment time is outside working hours",
                "working_hours": {
                    "start": self.working_hours_start,
                    "end": self.working_hours_end
                }
            })
        
        # Check for lunch break conflict
        if self._is_during_lunch_break(start_time, end_time):
            conflicts.append({
                "type": ConflictType.DOCTOR_UNAVAILABLE,
                "severity": ConflictSeverity.MEDIUM,
                "message": "Appointment time conflicts with lunch break",
                "lunch_break": {
                    "start": self.lunch_break_start,
                    "end": self.lunch_break_end
                }
            })
        
        return conflicts
    
    def _check_patient_double_booking(
        self,
        patient_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime,
        exclude_appointment_id: Optional[uuid.UUID]
    ) -> List[Dict]:
        """Check for patient double booking."""
        conflicts = []
        
        # Query patient's existing appointments
        query = self.db.query(Appointment).filter(
            Appointment.patient_id == patient_id,
            Appointment.status == AppointmentStatus.SCHEDULED,
            Appointment.start_time < end_time,
            Appointment.end_time > start_time
        )
        
        if exclude_appointment_id:
            query = query.filter(Appointment.id != exclude_appointment_id)
        
        overlapping_appointments = query.all()
        
        for appointment in overlapping_appointments:
            conflicts.append({
                "type": ConflictType.PATIENT_DOUBLE_BOOKING,
                "severity": ConflictSeverity.HIGH,
                "message": f"Patient has overlapping appointment {appointment.id}",
                "conflicting_appointment": {
                    "id": appointment.id,
                    "start_time": appointment.start_time,
                    "end_time": appointment.end_time,
                    "doctor_id": appointment.doctor_id
                }
            })
        
        return conflicts
    
    def _check_scheduling_rules(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict]:
        """Check for scheduling rule violations."""
        conflicts = []
        
        # Check appointment duration
        duration = end_time - start_time
        if duration.total_seconds() > self.max_appointment_duration_hours * 3600:
            conflicts.append({
                "type": ConflictType.SCHEDULING_RULE_VIOLATION,
                "severity": ConflictSeverity.MEDIUM,
                "message": f"Appointment duration exceeds maximum {self.max_appointment_duration_hours} hours",
                "duration_hours": duration.total_seconds() / 3600,
                "max_duration_hours": self.max_appointment_duration_hours
            })
        
        # Check if appointment is in the past
        if start_time < datetime.now(UTC):
            conflicts.append({
                "type": ConflictType.SCHEDULING_RULE_VIOLATION,
                "severity": ConflictSeverity.HIGH,
                "message": "Cannot schedule appointments in the past",
                "start_time": start_time.isoformat(),
                "current_time": datetime.now(UTC).isoformat()
            })
        
        return conflicts
    
    def _analyze_conflicts(self, conflicts: List[Dict]) -> Dict:
        """Analyze conflicts to determine severity and resolution approach."""
        if not conflicts:
            return {"severity": ConflictSeverity.LOW, "resolvable": True}
        
        # Count conflicts by type and severity
        conflict_counts = {}
        severity_counts = {}
        
        for conflict in conflicts:
            conflict_type = conflict["type"]
            severity = conflict["severity"]
            
            conflict_counts[conflict_type] = conflict_counts.get(conflict_type, 0) + 1
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        # Determine overall severity
        if ConflictSeverity.CRITICAL in severity_counts:
            overall_severity = ConflictSeverity.CRITICAL
        elif ConflictSeverity.HIGH in severity_counts:
            overall_severity = ConflictSeverity.HIGH
        elif ConflictSeverity.MEDIUM in severity_counts:
            overall_severity = ConflictSeverity.MEDIUM
        else:
            overall_severity = ConflictSeverity.LOW
        
        # Determine if conflicts are resolvable
        resolvable = overall_severity not in [ConflictSeverity.CRITICAL]
        
        return {
            "severity": overall_severity,
            "resolvable": resolvable,
            "conflict_counts": conflict_counts,
            "severity_counts": severity_counts
        }
    
    def _determine_resolution_strategy(self, analysis: Dict) -> ResolutionStrategy:
        """Determine the best resolution strategy based on conflict analysis."""
        if not analysis["resolvable"]:
            return ResolutionStrategy.REJECT
        
        if analysis["severity"] == ConflictSeverity.CRITICAL:
            return ResolutionStrategy.MANUAL_REVIEW
        
        if analysis["severity"] == ConflictSeverity.HIGH:
            return ResolutionStrategy.SUGGEST_ALTERNATIVE
        
        if analysis["severity"] == ConflictSeverity.MEDIUM:
            return ResolutionStrategy.SUGGEST_ALTERNATIVE
        
        return ResolutionStrategy.AUTO_RESOLVE
    
    def _generate_resolution_suggestions(
        self,
        conflicts: List[Dict],
        doctor_id: uuid.UUID,
        patient_id: uuid.UUID,
        preferred_start_time: datetime,
        preferred_end_time: datetime
    ) -> List[Dict]:
        """Generate resolution suggestions."""
        suggestions = []
        
        # Get alternative times
        alternative_times = self.suggest_alternative_times(
            doctor_id, preferred_start_time, preferred_end_time, 5
        )
        
        for alt_time in alternative_times:
            suggestions.append({
                "start_time": alt_time["start_time"],
                "end_time": alt_time["end_time"],
                "score": alt_time["score"],
                "reason": alt_time["reason"],
                "strategy": "alternative_time"
            })
        
        # Add waitlist option
        suggestions.append({
            "strategy": "waitlist",
            "message": "Add to waitlist for this time slot",
            "reason": "Time slot is currently unavailable"
        })
        
        return suggestions
    
    def _generate_resolution_message(
        self,
        strategy: ResolutionStrategy,
        conflicts: List[Dict]
    ) -> str:
        """Generate human-readable resolution message."""
        if strategy == ResolutionStrategy.REJECT:
            return "Appointment cannot be scheduled due to critical conflicts."
        elif strategy == ResolutionStrategy.MANUAL_REVIEW:
            return "Appointment requires manual review due to complex conflicts."
        elif strategy == ResolutionStrategy.SUGGEST_ALTERNATIVE:
            return "Conflicts detected. Alternative times are suggested below."
        elif strategy == ResolutionStrategy.WAITLIST:
            return "Time slot is unavailable. You can join the waitlist."
        else:
            return "No conflicts detected. Appointment can be scheduled."
    
    def _get_doctor_appointments(self, doctor_id: uuid.UUID) -> List[Appointment]:
        """Get doctor's existing appointments."""
        return (
            self.db.query(Appointment)
            .filter(
                Appointment.doctor_id == doctor_id,
                Appointment.status == AppointmentStatus.SCHEDULED
            )
            .all()
        )
    
    def _generate_time_slots(
        self,
        preferred_start_time: datetime,
        duration: timedelta,
        max_slots: int
    ) -> List[Dict]:
        """Generate alternative time slots."""
        slots = []
        
        # Generate slots around preferred time
        for i in range(max_slots):
            # Try different offsets
            offset_hours = (i + 1) * 0.5  # 30-minute increments
            
            # Try before preferred time
            if i % 2 == 0:
                start_time = preferred_start_time - timedelta(hours=offset_hours)
            else:
                start_time = preferred_start_time + timedelta(hours=offset_hours)
            
            end_time = start_time + duration
            
            # Calculate score based on proximity to preferred time
            time_diff = abs((start_time - preferred_start_time).total_seconds())
            score = max(0, 100 - (time_diff / 3600) * 10)  # Decrease score with time difference
            
            slots.append({
                "start_time": start_time,
                "end_time": end_time,
                "score": score,
                "reason": f"Alternative time slot {i + 1}"
            })
        
        return slots
    
    def _is_within_working_hours(self, start_time: datetime, end_time: datetime) -> bool:
        """Check if appointment is within working hours."""
        start_hour = start_time.hour
        end_hour = end_time.hour
        
        return (self.working_hours_start <= start_hour < self.working_hours_end and
                self.working_hours_start <= end_hour <= self.working_hours_end)
    
    def _is_during_lunch_break(self, start_time: datetime, end_time: datetime) -> bool:
        """Check if appointment conflicts with lunch break."""
        start_hour = start_time.hour
        end_hour = end_time.hour
        
        return (self.lunch_break_start <= start_hour < self.lunch_break_end or
                self.lunch_break_start < end_hour <= self.lunch_break_end)


def get_conflict_resolution_service(db: Session) -> ConflictResolutionService:
    """Get conflict resolution service instance."""
    return ConflictResolutionService(db)
