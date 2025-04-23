"""Availability API routes for doctor scheduling."""

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user, role_required
from app.db.base import get_db
from app.db.models import User, UserRole
from app.db.schemas import (
    AvailabilityCreate,
    AvailabilityOut,
    AvailabilityUpdate,
    PaginatedResponse,
)
from app.services.availability import AvailabilityService

router = APIRouter()


@router.post(
    "/doctors/{doctor_id}/availability",
    response_model=AvailabilityOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create doctor availability",
    description="Create a new availability slot for a doctor. Only doctors and admins can create availability."
)
async def create_availability(
    doctor_id: uuid.UUID,
    availability_data: AvailabilityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(role_required([UserRole.DOCTOR, UserRole.ADMIN]))
) -> AvailabilityOut:
    """Create new availability slot for doctor."""
    # Check if user is the doctor or admin
    if current_user.role != UserRole.ADMIN and str(current_user.id) != str(doctor_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create availability for yourself"
        )

    service = AvailabilityService(db)
    
    try:
        # Check for time conflicts
        if service.check_availability_conflict(
            doctor_id, 
            availability_data.start_time, 
            availability_data.end_time
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Time slot conflicts with existing availability"
            )

        availability = service.create_availability(doctor_id, availability_data)
        return AvailabilityOut.model_validate(availability)
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        ) from e


@router.get(
    "/doctors/{doctor_id}/availability",
    response_model=PaginatedResponse[AvailabilityOut],
    summary="Get doctor availability",
    description="Get availability slots for a doctor within a date range. Cached with Redis for performance."
)
async def get_doctor_availability(
    doctor_id: uuid.UUID,
    start: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end: date = Query(..., description="End date (YYYY-MM-DD)"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=100, description="Page size"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> PaginatedResponse[AvailabilityOut]:
    """Get doctor availability slots in date range."""
    if start > end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start date must be before end date"
        )

    service = AvailabilityService(db)
    
    # Get availability from database
    availability_list = service.get_doctor_availability(doctor_id, start, end)
    
    # Paginate results
    total = len(availability_list)
    start_idx = (page - 1) * size
    end_idx = start_idx + size
    paginated_items = availability_list[start_idx:end_idx]
    
    # Convert to output schema
    items = [AvailabilityOut.model_validate(avail) for avail in paginated_items]
    
    return PaginatedResponse[AvailabilityOut](
        items=items,
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size
    )


@router.get(
    "/doctors/{doctor_id}/availability/slots",
    response_model=list[dict[str, Any]],
    summary="Get available time slots",
    description="Get cached available time slots for a doctor. Optimized for booking interfaces."
)
async def get_available_slots(
    doctor_id: uuid.UUID,
    start: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end: date = Query(..., description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> list[dict[str, Any]]:
    """Get available time slots with Redis caching."""
    if start > end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start date must be before end date"
        )

    service = AvailabilityService(db)
    return service.get_available_slots(doctor_id, start, end)


@router.get(
    "/doctors/{doctor_id}/availability/summary",
    response_model=dict[str, Any],
    summary="Get availability summary",
    description="Get summary statistics of doctor availability for a date range."
)
async def get_availability_summary(
    doctor_id: uuid.UUID,
    start: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end: date = Query(..., description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """Get availability summary for doctor."""
    if start > end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start date must be before end date"
        )

    service = AvailabilityService(db)
    return service.get_doctor_availability_summary(doctor_id, start, end)


@router.put(
    "/availability/{availability_id}",
    response_model=AvailabilityOut,
    summary="Update availability",
    description="Update an availability slot. Only the owner doctor or admin can update."
)
async def update_availability(
    availability_id: uuid.UUID,
    availability_data: AvailabilityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(role_required([UserRole.DOCTOR, UserRole.ADMIN]))
) -> AvailabilityOut:
    """Update availability slot."""
    service = AvailabilityService(db)
    
    # Get existing availability
    availability = service.get_availability(availability_id)
    if not availability:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Availability not found"
        )

    # Check permissions
    if (current_user.role != UserRole.ADMIN and 
        str(current_user.id) != str(availability.doctor_id)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own availability"
        )

    # Check for conflicts if updating times
    if (availability_data.start_time is not None or 
        availability_data.end_time is not None):
        
        start_time = availability_data.start_time or availability.start_time
        end_time = availability_data.end_time or availability.end_time
        
        if service.check_availability_conflict(
            availability.doctor_id, 
            start_time, 
            end_time,
            exclude_id=availability_id
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Updated time slot conflicts with existing availability"
            )

    updated_availability = service.update_availability(availability_id, availability_data)
    if not updated_availability:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Availability not found"
        )

    return AvailabilityOut.model_validate(updated_availability)


@router.delete(
    "/availability/{availability_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete availability",
    description="Delete an availability slot. Only the owner doctor or admin can delete."
)
async def delete_availability(
    availability_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(role_required([UserRole.DOCTOR, UserRole.ADMIN]))
) -> None:
    """Delete availability slot."""
    service = AvailabilityService(db)
    
    # Get existing availability
    availability = service.get_availability(availability_id)
    if not availability:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Availability not found"
        )

    # Check permissions
    if (current_user.role != UserRole.ADMIN and 
        str(current_user.id) != str(availability.doctor_id)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own availability"
        )

    success = service.delete_availability(availability_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Availability not found"
        )
