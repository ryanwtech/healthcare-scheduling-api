"""Enhanced validation utilities for better API experience."""

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from decimal import Decimal

from pydantic import BaseModel, Field, validator, root_validator
from pydantic import ValidationError as PydanticValueError
from fastapi import HTTPException, status


class ValidationError(PydanticValueError):
    """Custom validation error with detailed information."""
    
    def __init__(self, field: str, message: str, code: str = "VALIDATION_ERROR"):
        self.field = field
        self.message = message
        self.code = code
        super().__init__(message)


class CustomValidator:
    """Custom validation utilities."""
    
    @staticmethod
    def validate_uuid(value: Any, field_name: str = "id") -> str:
        """Validate UUID format."""
        if isinstance(value, str):
            try:
                uuid.UUID(value)
                return value
            except ValueError:
                raise ValidationError(field_name, f"Invalid UUID format: {value}")
        elif isinstance(value, uuid.UUID):
            return str(value)
        else:
            raise ValidationError(field_name, f"Expected UUID, got {type(value).__name__}")
    
    @staticmethod
    def validate_email(value: str) -> str:
        """Validate email format."""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, value):
            raise ValidationError("email", f"Invalid email format: {value}")
        return value.lower().strip()
    
    @staticmethod
    def validate_phone(value: str) -> str:
        """Validate phone number format."""
        # Remove all non-digit characters
        digits_only = re.sub(r'\D', '', value)
        
        # Check if it's a valid length (10-15 digits)
        if len(digits_only) < 10 or len(digits_only) > 15:
            raise ValidationError("phone", f"Invalid phone number length: {value}")
        
        return digits_only
    
    @staticmethod
    def validate_timezone(value: str) -> str:
        """Validate timezone format."""
        valid_timezones = [
            "UTC", "EST", "PST", "CST", "MST", "EDT", "PDT", "CDT", "MDT",
            "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
            "Europe/London", "Europe/Paris", "Asia/Tokyo", "Asia/Shanghai"
        ]
        
        if value not in valid_timezones:
            raise ValidationError("timezone", f"Invalid timezone: {value}. Must be one of: {', '.join(valid_timezones)}")
        
        return value
    
    @staticmethod
    def validate_datetime_range(start_time: datetime, end_time: datetime, field_prefix: str = "") -> None:
        """Validate that start_time is before end_time."""
        if start_time >= end_time:
            raise ValidationError(
                f"{field_prefix}start_time",
                f"Start time must be before end time. Got start: {start_time}, end: {end_time}"
            )
    
    @staticmethod
    def validate_business_hours(dt: datetime, field_name: str = "datetime") -> datetime:
        """Validate that datetime is within business hours (8 AM - 6 PM)."""
        hour = dt.hour
        if hour < 8 or hour >= 18:
            raise ValidationError(
                field_name,
                f"Time must be within business hours (8 AM - 6 PM). Got: {dt.strftime('%H:%M')}"
            )
        return dt
    
    @staticmethod
    def validate_future_datetime(dt: datetime, field_name: str = "datetime") -> datetime:
        """Validate that datetime is in the future."""
        now = datetime.now(timezone.utc)
        if dt <= now:
            raise ValidationError(
                field_name,
                f"Datetime must be in the future. Got: {dt}, current time: {now}"
            )
        return dt
    
    @staticmethod
    def validate_past_datetime(dt: datetime, field_name: str = "datetime") -> datetime:
        """Validate that datetime is in the past."""
        now = datetime.now(timezone.utc)
        if dt >= now:
            raise ValidationError(
                field_name,
                f"Datetime must be in the past. Got: {dt}, current time: {now}"
            )
        return dt


class EnhancedBaseModel(BaseModel):
    """Enhanced base model with common validation patterns."""
    
    class Config:
        # Use enum values instead of enum objects
        use_enum_values = True
        # Validate assignment
        validate_assignment = True
        # Allow population by field name
        populate_by_name = True
        # Generate example from schema
        json_schema_extra = {
            "examples": []
        }
    
    @validator('*', pre=True)
    def empty_str_to_none(cls, v):
        """Convert empty strings to None."""
        if v == "":
            return None
        return v
    
    @validator('*', pre=True)
    def strip_strings(cls, v):
        """Strip whitespace from strings."""
        if isinstance(v, str):
            return v.strip()
        return v


class PaginationParams(EnhancedBaseModel):
    """Enhanced pagination parameters."""
    
    page: int = Field(1, ge=1, description="Page number (1-based)")
    size: int = Field(20, ge=1, le=100, description="Number of items per page")
    sort: Optional[str] = Field(None, description="Sort field and direction (e.g., 'created_at:desc')")
    
    @validator('sort')
    def validate_sort(cls, v):
        """Validate sort parameter format."""
        if v is None:
            return v
        
        # Check format: field:direction
        if ':' not in v:
            raise ValidationError("sort", "Sort parameter must be in format 'field:direction'")
        
        field, direction = v.split(':', 1)
        if direction not in ['asc', 'desc']:
            raise ValidationError("sort", "Sort direction must be 'asc' or 'desc'")
        
        return v


class EnhancedErrorResponse(EnhancedBaseModel):
    """Enhanced error response model."""
    
    detail: str = Field(..., description="Error message")
    error_code: str = Field(..., description="Machine-readable error code")
    field: Optional[str] = Field(None, description="Field that caused the error")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Error timestamp")
    request_id: Optional[str] = Field(None, description="Request ID for tracking")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional error context")
    
    class Config:
        json_schema_extra = {
            "example": {
                "detail": "User not found",
                "error_code": "USER_NOT_FOUND",
                "field": "user_id",
                "timestamp": "2024-01-15T10:30:00Z",
                "request_id": "req_123456789",
                "context": {
                    "searched_id": "123e4567-e89b-12d3-a456-426614174000"
                }
            }
        }


class SuccessResponse(EnhancedBaseModel):
    """Standard success response model."""
    
    success: bool = Field(True, description="Indicates if the operation was successful")
    message: str = Field(..., description="Success message")
    data: Optional[Any] = Field(None, description="Response data")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Response timestamp")
    request_id: Optional[str] = Field(None, description="Request ID for tracking")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Operation completed successfully",
                "data": {"id": "123e4567-e89b-12d3-a456-426614174000"},
                "timestamp": "2024-01-15T10:30:00Z",
                "request_id": "req_123456789"
            }
        }


class ValidationErrorResponse(EnhancedBaseModel):
    """Validation error response model."""
    
    detail: str = Field("Validation error", description="Error message")
    error_code: str = Field("VALIDATION_ERROR", description="Error code")
    errors: List[Dict[str, Any]] = Field(..., description="List of validation errors")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Error timestamp")
    request_id: Optional[str] = Field(None, description="Request ID for tracking")
    
    class Config:
        json_schema_extra = {
            "example": {
                "detail": "Validation error",
                "error_code": "VALIDATION_ERROR",
                "errors": [
                    {
                        "field": "email",
                        "message": "Invalid email format",
                        "code": "INVALID_EMAIL"
                    },
                    {
                        "field": "phone",
                        "message": "Invalid phone number length",
                        "code": "INVALID_PHONE"
                    }
                ],
                "timestamp": "2024-01-15T10:30:00Z",
                "request_id": "req_123456789"
            }
        }


class HealthCheckResponse(EnhancedBaseModel):
    """Enhanced health check response."""
    
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Check timestamp")
    uptime: str = Field(..., description="Service uptime")
    dependencies: Dict[str, str] = Field(..., description="Dependency status")
    metrics: Optional[Dict[str, Any]] = Field(None, description="Service metrics")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "version": "2.0.0",
                "timestamp": "2024-01-15T10:30:00Z",
                "uptime": "5d 12h 30m",
                "dependencies": {
                    "database": "healthy",
                    "redis": "healthy",
                    "celery": "healthy"
                },
                "metrics": {
                    "active_connections": 42,
                    "requests_per_minute": 150,
                    "average_response_time": "120ms"
                }
            }
        }


def create_validation_error_response(
    errors: List[Dict[str, Any]],
    request_id: Optional[str] = None
) -> ValidationErrorResponse:
    """Create a standardized validation error response."""
    return ValidationErrorResponse(
        detail="Validation error",
        error_code="VALIDATION_ERROR",
        errors=errors,
        request_id=request_id
    )


def create_success_response(
    message: str,
    data: Optional[Any] = None,
    request_id: Optional[str] = None
) -> SuccessResponse:
    """Create a standardized success response."""
    return SuccessResponse(
        success=True,
        message=message,
        data=data,
        request_id=request_id
    )


def create_error_response(
    detail: str,
    error_code: str,
    field: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None
) -> EnhancedErrorResponse:
    """Create a standardized error response."""
    return EnhancedErrorResponse(
        detail=detail,
        error_code=error_code,
        field=field,
        context=context,
        request_id=request_id
    )


class FieldValidator:
    """Field-specific validation utilities."""
    
    @staticmethod
    def validate_required_fields(data: Dict[str, Any], required_fields: List[str]) -> List[Dict[str, Any]]:
        """Validate that required fields are present."""
        errors = []
        for field in required_fields:
            if field not in data or data[field] is None:
                errors.append({
                    "field": field,
                    "message": f"Field '{field}' is required",
                    "code": "REQUIRED_FIELD"
                })
        return errors
    
    @staticmethod
    def validate_field_types(data: Dict[str, Any], field_types: Dict[str, type]) -> List[Dict[str, Any]]:
        """Validate field types."""
        errors = []
        for field, expected_type in field_types.items():
            if field in data and data[field] is not None:
                if not isinstance(data[field], expected_type):
                    errors.append({
                        "field": field,
                        "message": f"Field '{field}' must be of type {expected_type.__name__}",
                        "code": "INVALID_TYPE"
                    })
        return errors
    
    @staticmethod
    def validate_string_lengths(data: Dict[str, Any], length_limits: Dict[str, int]) -> List[Dict[str, Any]]:
        """Validate string field lengths."""
        errors = []
        for field, max_length in length_limits.items():
            if field in data and data[field] is not None:
                if isinstance(data[field], str) and len(data[field]) > max_length:
                    errors.append({
                        "field": field,
                        "message": f"Field '{field}' must be no more than {max_length} characters",
                        "code": "STRING_TOO_LONG"
                    })
        return errors
    
    @staticmethod
    def validate_numeric_ranges(data: Dict[str, Any], ranges: Dict[str, Dict[str, Union[int, float]]]) -> List[Dict[str, Any]]:
        """Validate numeric field ranges."""
        errors = []
        for field, range_config in ranges.items():
            if field in data and data[field] is not None:
                value = data[field]
                if isinstance(value, (int, float, Decimal)):
                    if 'min' in range_config and value < range_config['min']:
                        errors.append({
                            "field": field,
                            "message": f"Field '{field}' must be at least {range_config['min']}",
                            "code": "VALUE_TOO_SMALL"
                        })
                    if 'max' in range_config and value > range_config['max']:
                        errors.append({
                            "field": field,
                            "message": f"Field '{field}' must be no more than {range_config['max']}",
                            "code": "VALUE_TOO_LARGE"
                        })
        return errors


def validate_request_data(
    data: Dict[str, Any],
    required_fields: List[str] = None,
    field_types: Dict[str, type] = None,
    length_limits: Dict[str, int] = None,
    numeric_ranges: Dict[str, Dict[str, Union[int, float]]] = None
) -> List[Dict[str, Any]]:
    """Comprehensive request data validation."""
    errors = []
    
    if required_fields:
        errors.extend(FieldValidator.validate_required_fields(data, required_fields))
    
    if field_types:
        errors.extend(FieldValidator.validate_field_types(data, field_types))
    
    if length_limits:
        errors.extend(FieldValidator.validate_string_lengths(data, length_limits))
    
    if numeric_ranges:
        errors.extend(FieldValidator.validate_numeric_ranges(data, numeric_ranges))
    
    return errors


class APIException(HTTPException):
    """Custom API exception with enhanced error information."""
    
    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: str = "API_ERROR",
        field: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ):
        self.error_code = error_code
        self.field = field
        self.context = context
        self.request_id = request_id
        
        super().__init__(
            status_code=status_code,
            detail=detail
        )


# Common validation patterns
class CommonValidators:
    """Common validation patterns for API endpoints."""
    
    @staticmethod
    def validate_pagination(page: int, size: int) -> None:
        """Validate pagination parameters."""
        if page < 1:
            raise ValidationError("page", "Page must be greater than 0")
        if size < 1 or size > 100:
            raise ValidationError("size", "Size must be between 1 and 100")
    
    @staticmethod
    def validate_date_range(start_date: datetime, end_date: datetime) -> None:
        """Validate date range parameters."""
        if start_date >= end_date:
            raise ValidationError("start_date", "Start date must be before end date")
        
        # Check if range is not too large (e.g., more than 1 year)
        if (end_date - start_date).days > 365:
            raise ValidationError("date_range", "Date range cannot exceed 1 year")
    
    @staticmethod
    def validate_business_hours_range(start_time: datetime, end_time: datetime) -> None:
        """Validate that time range is within business hours."""
        CustomValidator.validate_business_hours(start_time, "start_time")
        CustomValidator.validate_business_hours(end_time, "end_time")
        CustomValidator.validate_datetime_range(start_time, end_time, "appointment_")
    
    @staticmethod
    def validate_appointment_duration(start_time: datetime, end_time: datetime, max_duration_hours: int = 8) -> None:
        """Validate appointment duration."""
        duration = end_time - start_time
        if duration.total_seconds() > max_duration_hours * 3600:
            raise ValidationError(
                "duration",
                f"Appointment duration cannot exceed {max_duration_hours} hours"
            )
