"""Appointments API routes for booking and managing healthcare appointments."""

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.rate_limit import user_rate_limit_dependency
from app.core.security import get_current_user, role_required
from app.db.base import get_db
from app.db.models import User, UserRole
from app.db.schemas import AppointmentCreate, AppointmentOut, AppointmentUpdate, PaginatedResponse
from app.services.appointments import AppointmentService

router = APIRouter()


@router.post(
    "/appointments",
    response_model=AppointmentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Book a new appointment",
    description="Book a new appointment with a doctor. Rate limited to 5 requests per minute per user."
)
async def book_appointment(
    appointment_data: AppointmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(role_required([UserRole.PATIENT])),
    __: None = Depends(user_rate_limit_dependency(limit=5, window_seconds=60, endpoint="book_appointment"))
) -> AppointmentOut:
    """Book a new appointment for the current user."""
    service = AppointmentService(db)
    
    try:
        appointment = service.book_appointment(
            patient_id=current_user.id,
            doctor_id=appointment_data.doctor_id,
            start_time=appointment_data.start_time,
            end_time=appointment_data.end_time,
            notes=appointment_data.notes
        )
        return AppointmentOut.model_validate(appointment)
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e


@router.get(
    "/appointments",
    response_model=PaginatedResponse[AppointmentOut],
    summary="List appointments",
    description="List appointments with optional filters. Users can only see their own appointments unless they are admin."
)
async def list_appointments(
    me: bool = Query(True, description="Filter to current user's appointments"),
    doctor_id: uuid.UUID | None = Query(None, description="Filter by doctor ID"),
    patient_id: uuid.UUID | None = Query(None, description="Filter by patient ID"),
    start_date: date | None = Query(None, description="Filter by start date (YYYY-MM-DD)"),
    end_date: date | None = Query(None, description="Filter by end date (YYYY-MM-DD)"),
    status: str | None = Query(None, description="Filter by status (scheduled, cancelled, completed, no_show)"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=100, description="Page size"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> PaginatedResponse[AppointmentOut]:
    """List appointments with optional filters."""
    service = AppointmentService(db)
    
    # Apply role-based filtering
    if me:
        if current_user.role == UserRole.PATIENT:
            patient_id = current_user.id
        elif current_user.role == UserRole.DOCTOR:
            doctor_id = current_user.id
        # Admin can see all appointments
    
    # Convert status string to enum if provided
    status_enum = None
    if status:
        try:
            status_enum = UserRole(status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status}. Valid values: scheduled, cancelled, completed, no_show"
            ) from None
    
    appointments, total = service.list_appointments(
        doctor_id=doctor_id,
        patient_id=patient_id,
        start_date=start_date,
        end_date=end_date,
        status=status_enum,
        page=page,
        size=size
    )
    
    # Convert to output schema
    items = [AppointmentOut.model_validate(appointment) for appointment in appointments]
    
    return PaginatedResponse[AppointmentOut](
        items=items,
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size
    )


@router.get(
    "/appointments/{appointment_id}",
    response_model=AppointmentOut,
    summary="Get appointment details",
    description="Get details of a specific appointment. Users can only see their own appointments unless they are admin."
)
async def get_appointment(
    appointment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> AppointmentOut:
    """Get appointment details."""
    service = AppointmentService(db)
    
    appointment = service.get_appointment(appointment_id)
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found"
        )
    
    # Check permissions
    can_view = (
        current_user.role == UserRole.ADMIN or
        appointment.patient_id == current_user.id or
        appointment.doctor_id == current_user.id
    )
    
    if not can_view:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view this appointment"
        )
    
    return AppointmentOut.model_validate(appointment)


@router.put(
    "/appointments/{appointment_id}",
    response_model=AppointmentOut,
    summary="Update appointment",
    description="Update an appointment. Only the patient, doctor, or admin can update."
)
async def update_appointment(
    appointment_id: uuid.UUID,
    appointment_data: AppointmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(role_required([UserRole.PATIENT, UserRole.DOCTOR, UserRole.ADMIN]))
) -> AppointmentOut:
    """Update an appointment."""
    service = AppointmentService(db)
    
    try:
        appointment = service.update_appointment(
            appointment_id=appointment_id,
            appointment_data=appointment_data,
            actor_id=current_user.id,
            actor_role=current_user.role
        )
        
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found"
            )
        
        return AppointmentOut.model_validate(appointment)
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e


@router.post(
    "/appointments/{appointment_id}/cancel",
    response_model=AppointmentOut,
    summary="Cancel appointment",
    description="Cancel an appointment. Only the patient, doctor, or admin can cancel."
)
async def cancel_appointment(
    appointment_id: uuid.UUID,
    reason: str | None = Query(None, description="Cancellation reason"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(role_required([UserRole.PATIENT, UserRole.DOCTOR, UserRole.ADMIN]))
) -> AppointmentOut:
    """Cancel an appointment."""
    service = AppointmentService(db)
    
    try:
        appointment = service.cancel_appointment(
            appointment_id=appointment_id,
            actor_id=current_user.id,
            actor_role=current_user.role,
            reason=reason
        )
        
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found"
            )
        
        return AppointmentOut.model_validate(appointment)
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e


@router.get(
    "/appointments/statistics",
    response_model=dict[str, Any],
    summary="Get appointment statistics",
    description="Get appointment statistics. Doctors can see their own stats, admins can see all stats."
)
async def get_appointment_statistics(
    doctor_id: uuid.UUID | None = Query(None, description="Doctor ID for statistics"),
    start_date: date | None = Query(None, description="Start date for statistics (YYYY-MM-DD)"),
    end_date: date | None = Query(None, description="End date for statistics (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(role_required([UserRole.DOCTOR, UserRole.ADMIN]))
) -> dict[str, Any]:
    """Get appointment statistics."""
    service = AppointmentService(db)
    
    # Apply role-based filtering
    if current_user.role == UserRole.DOCTOR:
        doctor_id = current_user.id
    # Admin can specify any doctor_id or None for overall stats
    
    return service.get_appointment_statistics(
        doctor_id=doctor_id,
        start_date=start_date,
        end_date=end_date
    )
