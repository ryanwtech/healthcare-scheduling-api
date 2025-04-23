"""Authentication API routes for user signup and token generation."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    get_current_user,
    get_password_hash,
    role_required,
    verify_password,
)
from app.db.base import get_db
from app.db.models import User, UserRole
from app.db.schemas import LoginRequest, LoginResponse, UserCreate, UserOut

router = APIRouter()


class PatientSignupRequest(BaseModel):
    """Patient self-registration request model."""
    email: EmailStr = Field(..., description="Valid email address")
    password: str = Field(..., min_length=8, description="Password (minimum 8 characters)")
    full_name: str = Field(..., min_length=2, max_length=255, description="Full name")


@router.post(
    "/auth/signup",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create new user (Admin only)",
    description="Create a new user account. Only admins can create users with any role."
)
async def admin_create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(role_required([UserRole.ADMIN]))
) -> UserOut:
    """Create a new user account (admin only)."""
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    # Only admins can create users with doctor or admin roles
    if user_data.role in [UserRole.DOCTOR, UserRole.ADMIN]:
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can create doctors and other admins"
            )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        role=user_data.role,
        is_active=True
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return UserOut.model_validate(user)


@router.post(
    "/auth/signup/patient",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Patient self-registration",
    description="Allow patients to self-register. Role is automatically set to 'patient'."
)
async def patient_signup(
    user_data: PatientSignupRequest,
    db: Session = Depends(get_db)
) -> UserOut:
    """Allow patients to self-register."""
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    # Create new patient user (role forced to PATIENT)
    hashed_password = get_password_hash(user_data.password)
    user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        role=UserRole.PATIENT,  # Force role to patient
        is_active=True
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return UserOut.model_validate(user)


@router.post(
    "/auth/token",
    response_model=LoginResponse,
    summary="Get access token",
    description="Authenticate user and return JWT access token using OAuth2 password flow."
)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
) -> LoginResponse:
    """Authenticate user and return access token."""
    # Find user by email
    user = db.query(User).filter(User.email == form_data.username).first()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify password
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value
        },
        expires_delta=access_token_expires
    )
    
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserOut.model_validate(user)
    )


@router.post(
    "/auth/login",
    response_model=LoginResponse,
    summary="Login with email and password",
    description="Alternative login endpoint using JSON body instead of form data."
)
async def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
) -> LoginResponse:
    """Login with email and password using JSON body."""
    # Find user by email
    user = db.query(User).filter(User.email == login_data.email).first()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify password
    if not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value
        },
        expires_delta=access_token_expires
    )
    
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserOut.model_validate(user)
    )


@router.get(
    "/auth/me",
    response_model=UserOut,
    summary="Get current user",
    description="Get current authenticated user information."
)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
) -> UserOut:
    """Get current user information."""
    return UserOut.model_validate(current_user)
