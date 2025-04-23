"""Advanced appointment features API endpoints."""

import uuid
from datetime import datetime, timedelta, UTC
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.core.security import get_current_user, role_required
from app.db.base import get_db
from app.db.models import User, UserRole
from app.services.appointment_analytics import (
    AnalyticsPeriod,
    get_appointment_analytics_service,
)
from app.services.appointment_templates import (
    AppointmentType,
    get_appointment_template_service,
)
from app.services.conflict_resolution import (
    ResolutionStrategy,
    get_conflict_resolution_service,
)
from app.services.recurring_appointments import (
    RecurrenceEndType,
    RecurrencePattern,
    get_recurring_appointment_service,
)
from app.services.reminders import (
    ReminderType,
    get_reminder_service,
)
from app.services.waitlist import (
    WaitlistStatus,
    get_waitlist_service,
)

router = APIRouter()


# Pydantic models for request/response
class RecurringAppointmentRequest(BaseModel):
    """Request model for creating recurring appointments."""
    doctor_id: uuid.UUID
    patient_id: uuid.UUID
    start_time: datetime
    end_time: datetime
    pattern: RecurrencePattern
    interval: int = Field(1, ge=1, le=52)
    end_type: RecurrenceEndType = RecurrenceEndType.NEVER
    end_count: Optional[int] = Field(None, ge=1, le=100)
    end_date: Optional[datetime] = None
    days_of_week: Optional[List[int]] = Field(None, ge=0, le=6)
    day_of_month: Optional[int] = Field(None, ge=1, le=31)
    notes: Optional[str] = None


class WaitlistRequest(BaseModel):
    """Request model for adding to waitlist."""
    doctor_id: uuid.UUID
    preferred_start_time: datetime
    preferred_end_time: datetime
    notes: Optional[str] = None
    expires_in_hours: int = Field(24, ge=1, le=168)


class AppointmentTemplateRequest(BaseModel):
    """Request model for creating appointment from template."""
    template_id: uuid.UUID
    doctor_id: uuid.UUID
    patient_id: uuid.UUID
    start_time: datetime
    notes: Optional[str] = None


class ConflictResolutionRequest(BaseModel):
    """Request model for conflict resolution."""
    doctor_id: uuid.UUID
    start_time: datetime
    end_time: datetime
    patient_id: Optional[uuid.UUID] = None


class AnalyticsRequest(BaseModel):
    """Request model for analytics."""
    doctor_id: Optional[uuid.UUID] = None
    start_date: datetime
    end_date: datetime
    period: AnalyticsPeriod = AnalyticsPeriod.DAILY
    metrics: Optional[List[str]] = None


class ReminderRequest(BaseModel):
    """Request model for sending reminders."""
    appointment_id: uuid.UUID
    template: str
    reminder_type: ReminderType
    custom_message: Optional[str] = None


# Recurring Appointments Endpoints
@router.post("/recurring")
async def create_recurring_appointments(
    request: RecurringAppointmentRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Create a series of recurring appointments."""
    try:
        recurring_service = get_recurring_appointment_service(db)
        
        # Create base appointment data
        from app.db.schemas import AppointmentCreate
        base_appointment = AppointmentCreate(
            doctor_id=request.doctor_id,
            patient_id=request.patient_id,
            start_time=request.start_time,
            end_time=request.end_time,
            notes=request.notes
        )
        
        # Create recurring appointments
        appointments = recurring_service.create_recurring_appointments(
            base_appointment=base_appointment,
            pattern=request.pattern,
            interval=request.interval,
            end_type=request.end_type,
            end_count=request.end_count,
            end_date=request.end_date,
            days_of_week=request.days_of_week,
            day_of_month=request.day_of_month,
            created_by=current_user.id
        )
        
        return {
            "message": f"Created {len(appointments)} recurring appointments",
            "appointments": [
                {
                    "id": str(apt.id),
                    "start_time": apt.start_time.isoformat(),
                    "end_time": apt.end_time.isoformat(),
                    "status": apt.status.value
                }
                for apt in appointments
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create recurring appointments: {str(e)}"
        )


@router.get("/recurring/{doctor_id}")
async def get_recurring_appointments(
    doctor_id: uuid.UUID,
    start_date: datetime,
    end_date: datetime,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Get recurring appointments for a doctor in a date range."""
    try:
        recurring_service = get_recurring_appointment_service(db)
        
        appointments = recurring_service.get_recurring_appointments(
            doctor_id=doctor_id,
            start_date=start_date,
            end_date=end_date
        )
        
        return {
            "appointments": [
                {
                    "id": str(apt.id),
                    "start_time": apt.start_time.isoformat(),
                    "end_time": apt.end_time.isoformat(),
                    "status": apt.status.value,
                    "patient_id": str(apt.patient_id)
                }
                for apt in appointments
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to get recurring appointments: {str(e)}"
        )


# Waitlist Endpoints
@router.post("/waitlist")
async def add_to_waitlist(
    request: WaitlistRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Add a patient to the waitlist for a specific time slot."""
    try:
        waitlist_service = get_waitlist_service(db)
        
        waitlist_entry = waitlist_service.add_to_waitlist(
            patient_id=current_user.id,
            doctor_id=request.doctor_id,
            preferred_start_time=request.preferred_start_time,
            preferred_end_time=request.preferred_end_time,
            notes=request.notes,
            expires_in_hours=request.expires_in_hours
        )
        
        return {
            "message": "Added to waitlist successfully",
            "waitlist_entry": {
                "id": str(waitlist_entry.id),
                "preferred_start_time": waitlist_entry.preferred_start_time.isoformat(),
                "preferred_end_time": waitlist_entry.preferred_end_time.isoformat(),
                "status": waitlist_entry.status.value,
                "expires_at": waitlist_entry.expires_at.isoformat() if waitlist_entry.expires_at else None
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to add to waitlist: {str(e)}"
        )


@router.get("/waitlist/{doctor_id}")
async def get_waitlist(
    doctor_id: uuid.UUID,
    status: Optional[WaitlistStatus] = None,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Get waitlist entries for a doctor."""
    try:
        waitlist_service = get_waitlist_service(db)
        
        entries = waitlist_service.get_waitlist_for_doctor(
            doctor_id=doctor_id,
            status=status
        )
        
        return {
            "waitlist_entries": [
                {
                    "id": str(entry.id),
                    "patient_id": str(entry.patient_id),
                    "preferred_start_time": entry.preferred_start_time.isoformat(),
                    "preferred_end_time": entry.preferred_end_time.isoformat(),
                    "status": entry.status.value,
                    "created_at": entry.created_at.isoformat(),
                    "expires_at": entry.expires_at.isoformat() if entry.expires_at else None
                }
                for entry in entries
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to get waitlist: {str(e)}"
        )


@router.post("/waitlist/{entry_id}/book")
async def book_from_waitlist(
    entry_id: uuid.UUID,
    actual_start_time: datetime,
    actual_end_time: datetime,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Book an appointment from waitlist entry."""
    try:
        waitlist_service = get_waitlist_service(db)
        
        appointment = waitlist_service.book_from_waitlist(
            waitlist_entry_id=entry_id,
            actual_start_time=actual_start_time,
            actual_end_time=actual_end_time,
            booked_by=current_user.id
        )
        
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Waitlist entry not found or expired"
            )
        
        return {
            "message": "Appointment booked from waitlist",
            "appointment": {
                "id": str(appointment.id),
                "start_time": appointment.start_time.isoformat(),
                "end_time": appointment.end_time.isoformat(),
                "status": appointment.status.value
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to book from waitlist: {str(e)}"
        )


# Appointment Templates Endpoints
@router.get("/templates")
async def get_appointment_templates(
    appointment_type: Optional[AppointmentType] = None,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Get available appointment templates."""
    try:
        template_service = get_appointment_template_service(db)
        
        if appointment_type:
            templates = template_service.get_templates_by_type(appointment_type)
        else:
            templates = template_service.get_all_templates()
        
        return {
            "templates": [
                {
                    "id": str(template.id),
                    "name": template.name,
                    "appointment_type": template.appointment_type.value,
                    "duration_minutes": template.duration_minutes,
                    "description": template.description,
                    "preparation_instructions": template.preparation_instructions,
                    "follow_up_required": template.follow_up_required,
                    "required_documents": template.required_documents,
                    "special_requirements": template.special_requirements
                }
                for template in templates
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to get templates: {str(e)}"
        )


@router.post("/templates/create")
async def create_appointment_from_template(
    request: AppointmentTemplateRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Create an appointment from a template."""
    try:
        template_service = get_appointment_template_service(db)
        
        appointment_data = template_service.create_appointment_from_template(
            template_id=request.template_id,
            doctor_id=request.doctor_id,
            patient_id=request.patient_id,
            start_time=request.start_time,
            notes=request.notes,
            created_by=current_user.id
        )
        
        if not appointment_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found or inactive"
            )
        
        return {
            "message": "Appointment data created from template",
            "appointment_data": {
                "doctor_id": str(appointment_data.doctor_id),
                "patient_id": str(appointment_data.patient_id),
                "start_time": appointment_data.start_time.isoformat(),
                "end_time": appointment_data.end_time.isoformat(),
                "notes": appointment_data.notes
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create appointment from template: {str(e)}"
        )


# Conflict Resolution Endpoints
@router.post("/conflicts/detect")
async def detect_conflicts(
    request: ConflictResolutionRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Detect conflicts for a proposed appointment."""
    try:
        conflict_service = get_conflict_resolution_service(db)
        
        conflicts = conflict_service.detect_conflicts(
            doctor_id=request.doctor_id,
            start_time=request.start_time,
            end_time=request.end_time,
            patient_id=request.patient_id
        )
        
        return {
            "conflicts": conflicts,
            "has_conflicts": len(conflicts) > 0
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to detect conflicts: {str(e)}"
        )


@router.post("/conflicts/resolve")
async def resolve_conflicts(
    request: ConflictResolutionRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Resolve conflicts for a proposed appointment."""
    try:
        conflict_service = get_conflict_resolution_service(db)
        
        # Detect conflicts first
        conflicts = conflict_service.detect_conflicts(
            doctor_id=request.doctor_id,
            start_time=request.start_time,
            end_time=request.end_time,
            patient_id=request.patient_id
        )
        
        # Resolve conflicts
        resolution = conflict_service.resolve_conflicts(
            conflicts=conflicts,
            doctor_id=request.doctor_id,
            patient_id=request.patient_id or current_user.id,
            preferred_start_time=request.start_time,
            preferred_end_time=request.end_time
        )
        
        return resolution
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to resolve conflicts: {str(e)}"
        )


@router.get("/conflicts/suggestions/{doctor_id}")
async def get_alternative_suggestions(
    doctor_id: uuid.UUID,
    preferred_start_time: datetime,
    preferred_end_time: datetime,
    max_suggestions: int = 5,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Get alternative time suggestions for an appointment."""
    try:
        conflict_service = get_conflict_resolution_service(db)
        
        suggestions = conflict_service.suggest_alternative_times(
            doctor_id=doctor_id,
            preferred_start_time=preferred_start_time,
            preferred_end_time=preferred_end_time,
            max_suggestions=max_suggestions
        )
        
        return {
            "suggestions": suggestions
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to get alternative suggestions: {str(e)}"
        )


# Analytics Endpoints
@router.post("/analytics")
async def get_appointment_analytics(
    request: AnalyticsRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Get appointment analytics."""
    try:
        analytics_service = get_appointment_analytics_service(db)
        
        analytics = analytics_service.get_appointment_analytics(
            doctor_id=request.doctor_id,
            start_date=request.start_date,
            end_date=request.end_date,
            period=request.period,
            metrics=request.metrics
        )
        
        return analytics
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to get analytics: {str(e)}"
        )


@router.get("/analytics/doctor/{doctor_id}")
async def get_doctor_performance(
    doctor_id: uuid.UUID,
    start_date: datetime,
    end_date: datetime,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Get doctor performance metrics."""
    try:
        analytics_service = get_appointment_analytics_service(db)
        
        performance = analytics_service.get_doctor_performance_metrics(
            doctor_id=doctor_id,
            start_date=start_date,
            end_date=end_date
        )
        
        return performance
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to get doctor performance: {str(e)}"
        )


@router.get("/analytics/patient/{patient_id}")
async def get_patient_analytics(
    patient_id: uuid.UUID,
    start_date: datetime,
    end_date: datetime,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Get patient analytics."""
    try:
        analytics_service = get_appointment_analytics_service(db)
        
        analytics = analytics_service.get_patient_analytics(
            patient_id=patient_id,
            start_date=start_date,
            end_date=end_date
        )
        
        return analytics
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to get patient analytics: {str(e)}"
        )


@router.get("/analytics/system")
async def get_system_analytics(
    start_date: datetime,
    end_date: datetime,
    current_user: User = Depends(role_required([UserRole.ADMIN])),
    db=Depends(get_db)
):
    """Get system-wide analytics (admin only)."""
    try:
        analytics_service = get_appointment_analytics_service(db)
        
        analytics = analytics_service.get_system_analytics(
            start_date=start_date,
            end_date=end_date
        )
        
        return analytics
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to get system analytics: {str(e)}"
        )


# Reminder Endpoints
@router.post("/reminders/send")
async def send_immediate_reminder(
    request: ReminderRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Send an immediate reminder."""
    try:
        reminder_service = get_reminder_service(db)
        
        # Get appointment
        from app.db.models import Appointment
        appointment = db.query(Appointment).filter(
            Appointment.id == request.appointment_id
        ).first()
        
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found"
            )
        
        # Send reminder
        success = reminder_service.send_immediate_reminder(
            appointment=appointment,
            template=request.template,
            reminder_type=request.reminder_type,
            custom_message=request.custom_message
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send reminder"
            )
        
        return {
            "message": "Reminder sent successfully",
            "appointment_id": str(request.appointment_id),
            "template": request.template,
            "type": request.reminder_type.value
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to send reminder: {str(e)}"
        )


@router.post("/reminders/schedule/{appointment_id}")
async def schedule_appointment_reminders(
    appointment_id: uuid.UUID,
    reminder_types: List[ReminderType] = [ReminderType.EMAIL, ReminderType.SMS],
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Schedule reminders for an appointment."""
    try:
        reminder_service = get_reminder_service(db)
        
        # Get appointment
        from app.db.models import Appointment
        appointment = db.query(Appointment).filter(
            Appointment.id == appointment_id
        ).first()
        
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found"
            )
        
        # Schedule reminders
        scheduled_reminders = reminder_service.schedule_appointment_reminders(
            appointment=appointment,
            reminder_types=reminder_types
        )
        
        return {
            "message": f"Scheduled {len(scheduled_reminders)} reminders",
            "scheduled_reminders": scheduled_reminders
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to schedule reminders: {str(e)}"
        )
