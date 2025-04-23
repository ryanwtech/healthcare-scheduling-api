"""Pydantic v2 schemas for healthcare scheduling API."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

# Type variable for generic pagination
T = TypeVar('T')


class UserRole(str, Enum):
    """User role enumeration."""
    PATIENT = "patient"
    DOCTOR = "doctor"
    ADMIN = "admin"


class AppointmentStatus(str, Enum):
    """Appointment status enumeration."""
    SCHEDULED = "scheduled"
    CANCELED = "canceled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


# Base schemas
class BaseSchema(BaseModel):
    """Base schema with common configuration."""
    model_config = ConfigDict(from_attributes=True)


# User schemas
class UserBase(BaseSchema):
    """Base user schema."""
    email: str = Field(..., max_length=255)
    full_name: str = Field(..., max_length=255)
    role: UserRole = UserRole.PATIENT
    is_active: bool = True


class UserCreate(UserBase):
    """Schema for creating a user."""
    password: str = Field(..., min_length=8, max_length=100)


class UserUpdate(BaseSchema):
    """Schema for updating a user."""
    email: str | None = Field(None, max_length=255)
    full_name: str | None = Field(None, max_length=255)
    role: UserRole | None = None
    is_active: bool | None = None


class UserOut(UserBase):
    """Schema for user output."""
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class UserInDB(UserOut):
    """Schema for user in database (includes hashed password)."""
    hashed_password: str


# Doctor profile schemas
class DoctorProfileBase(BaseSchema):
    """Base doctor profile schema."""
    specialization: str = Field(..., max_length=255)
    timezone: str = Field(default="UTC", max_length=50)


class DoctorProfileCreate(DoctorProfileBase):
    """Schema for creating a doctor profile."""
    user_id: uuid.UUID


class DoctorProfileUpdate(BaseSchema):
    """Schema for updating a doctor profile."""
    specialization: str | None = Field(None, max_length=255)
    timezone: str | None = Field(None, max_length=50)


class DoctorProfileOut(DoctorProfileBase):
    """Schema for doctor profile output."""
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime


class DoctorProfileWithUser(DoctorProfileOut):
    """Schema for doctor profile with user information."""
    user: UserOut


# Availability schemas
class AvailabilityBase(BaseSchema):
    """Base availability schema."""
    start_time: datetime
    end_time: datetime


class AvailabilityCreate(AvailabilityBase):
    """Schema for creating availability."""
    doctor_id: uuid.UUID


class AvailabilityUpdate(BaseSchema):
    """Schema for updating availability."""
    start_time: datetime | None = None
    end_time: datetime | None = None


class AvailabilityOut(AvailabilityBase):
    """Schema for availability output."""
    id: uuid.UUID
    doctor_id: uuid.UUID
    created_at: datetime


class AvailabilityWithDoctor(AvailabilityOut):
    """Schema for availability with doctor information."""
    doctor: DoctorProfileOut


# Appointment schemas
class AppointmentBase(BaseSchema):
    """Base appointment schema."""
    start_time: datetime
    end_time: datetime
    status: AppointmentStatus = AppointmentStatus.SCHEDULED
    notes: str | None = None


class AppointmentCreate(AppointmentBase):
    """Schema for creating an appointment."""
    doctor_id: uuid.UUID
    patient_id: uuid.UUID


class AppointmentUpdate(BaseSchema):
    """Schema for updating an appointment."""
    start_time: datetime | None = None
    end_time: datetime | None = None
    status: AppointmentStatus | None = None
    notes: str | None = None


class AppointmentOut(AppointmentBase):
    """Schema for appointment output."""
    id: uuid.UUID
    doctor_id: uuid.UUID
    patient_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class AppointmentWithDetails(AppointmentOut):
    """Schema for appointment with doctor and patient details."""
    doctor: DoctorProfileWithUser
    patient: UserOut


# Authentication schemas
class Token(BaseSchema):
    """Token schema."""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseSchema):
    """Token data schema."""
    user_id: uuid.UUID | None = None
    email: str | None = None
    roles: list[str] = []


# Login schemas
class LoginRequest(BaseSchema):
    """Login request schema."""
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=8, max_length=100)


class LoginResponse(BaseSchema):
    """Login response schema."""
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# Health check schemas
class HealthCheck(BaseSchema):
    """Health check response schema."""
    status: str
    message: str
    uptime_seconds: float | None = None
    version: str | None = None
    environment: str | None = None


# Pagination schemas
class PaginationParams(BaseSchema):
    """Pagination parameters schema."""
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)


class PaginatedResponse(BaseSchema, Generic[T]):
    """Paginated response schema."""
    items: list[T]
    total: int
    page: int
    size: int
    pages: int


# Error schemas
class ErrorDetail(BaseSchema):
    """Error detail schema."""
    code: int
    message: str
    details: dict | None = None
    request_id: str | None = None


class ErrorResponse(BaseSchema):
    """Error response schema."""
    error: ErrorDetail
