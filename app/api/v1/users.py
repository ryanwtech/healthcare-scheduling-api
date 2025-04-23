"""User management API routes."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user, role_required
from app.db.base import get_db
from app.db.models import User, UserRole
from app.db.schemas import PaginatedResponse, UserCreate, UserOut, UserUpdate

router = APIRouter()


@router.get(
    "/users/me",
    response_model=UserOut,
    summary="Get current user",
    description="Get current authenticated user information."
)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
) -> UserOut:
    """Get current user information."""
    return UserOut.model_validate(current_user)


@router.get(
    "/users/{user_id}",
    response_model=UserOut,
    summary="Get user by ID",
    description="Get user information by ID. Only admins can access other users."
)
async def get_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(role_required([UserRole.ADMIN]))
) -> UserOut:
    """Get user by ID (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if user is active (admins can see inactive users, but log it)
    if not user.is_active:
        # Log that an inactive user was accessed
        from app.core.logging import get_logger
        logger = get_logger(__name__)
        logger.warning(
            "Inactive user accessed",
            user_id=str(user_id),
            accessed_by=str(current_user.id),
            user_email=user.email
        )
    
    return UserOut.model_validate(user)


@router.get(
    "/users",
    response_model=PaginatedResponse[UserOut],
    summary="List users",
    description="List all users with pagination. Only admins can access this endpoint."
)
async def list_users(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=100, description="Page size"),
    role: str | None = Query(None, description="Filter by role"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(role_required([UserRole.ADMIN]))
) -> PaginatedResponse[UserOut]:
    """List all users with optional filters (admin only)."""
    query = db.query(User)
    
    # Apply filters
    if role:
        try:
            role_enum = UserRole(role)
            query = query.filter(User.role == role_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {role}. Valid values: {[r.value for r in UserRole]}"
            ) from None
    
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    offset = (page - 1) * size
    users = (
        query
        .order_by(User.created_at.desc())
        .offset(offset)
        .limit(size)
        .all()
    )
    
    # Convert to output schema
    items = [UserOut.model_validate(user) for user in users]
    
    return PaginatedResponse[UserOut](
        items=items,
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size
    )


@router.post(
    "/users",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create user",
    description="Create a new user. Only admins can create users."
)
async def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(role_required([UserRole.ADMIN]))
) -> UserOut:
    """Create a new user (admin only)."""
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    # Create new user
    from app.core.security import get_password_hash
    hashed_password = get_password_hash(user_data.password)
    
    user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        role=user_data.role,
        is_active=user_data.is_active if user_data.is_active is not None else True
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return UserOut.model_validate(user)


@router.patch(
    "/users/{user_id}",
    response_model=UserOut,
    summary="Update user",
    description="Update user information. Only admins can update users."
)
async def update_user(
    user_id: uuid.UUID,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(role_required([UserRole.ADMIN]))
) -> UserOut:
    """Update user information (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update fields
    if user_data.email is not None:
        # Check if email is already taken by another user
        existing_user = db.query(User).filter(
            User.email == user_data.email,
            User.id != user_id
        ).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already taken by another user"
            )
        user.email = user_data.email
    
    if user_data.full_name is not None:
        user.full_name = user_data.full_name
    
    if user_data.role is not None:
        user.role = user_data.role
    
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
    
    if user_data.password is not None:
        from app.core.security import get_password_hash
        user.hashed_password = get_password_hash(user_data.password)
    
    db.commit()
    db.refresh(user)
    
    return UserOut.model_validate(user)


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete user",
    description="Delete a user. Only admins can delete users."
)
async def delete_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(role_required([UserRole.ADMIN]))
) -> None:
    """Delete a user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent deleting self
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    db.delete(user)
    db.commit()


@router.get(
    "/users/statistics",
    response_model=dict[str, Any],
    summary="Get user statistics",
    description="Get user statistics and counts. Only admins can access this endpoint."
)
async def get_user_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(role_required([UserRole.ADMIN]))
) -> dict[str, Any]:
    """Get user statistics (admin only)."""
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active).count()
    
    # Count by role
    role_counts = {}
    for role in UserRole:
        count = db.query(User).filter(User.role == role).count()
        role_counts[role.value] = count
    
    return {
        "total_users": total_users,
        "active_users": active_users,
        "inactive_users": total_users - active_users,
        "role_breakdown": role_counts,
        "active_percentage": round((active_users / total_users * 100), 2) if total_users > 0 else 0
    }
