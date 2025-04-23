"""Comprehensive error handling and custom exceptions for better API experience."""

import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from enum import Enum

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError as PydanticValidationError

from app.core.logging import get_logger
from app.core.validation import EnhancedErrorResponse, ValidationErrorResponse

logger = get_logger(__name__)


class ErrorCode(str, Enum):
    """Standardized error codes for the API."""
    
    # Authentication & Authorization
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    TOKEN_INVALID = "TOKEN_INVALID"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"
    ACCOUNT_DISABLED = "ACCOUNT_DISABLED"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    
    # Validation Errors
    VALIDATION_ERROR = "VALIDATION_ERROR"
    REQUIRED_FIELD = "REQUIRED_FIELD"
    INVALID_FORMAT = "INVALID_FORMAT"
    INVALID_TYPE = "INVALID_TYPE"
    VALUE_TOO_LARGE = "VALUE_TOO_LARGE"
    VALUE_TOO_SMALL = "VALUE_TOO_SMALL"
    STRING_TOO_LONG = "STRING_TOO_LONG"
    STRING_TOO_SHORT = "STRING_TOO_SHORT"
    INVALID_EMAIL = "INVALID_EMAIL"
    INVALID_PHONE = "INVALID_PHONE"
    INVALID_UUID = "INVALID_UUID"
    INVALID_DATE = "INVALID_DATE"
    INVALID_TIME = "INVALID_TIME"
    INVALID_TIMEZONE = "INVALID_TIMEZONE"
    
    # Resource Errors
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    RESOURCE_ALREADY_EXISTS = "RESOURCE_ALREADY_EXISTS"
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"
    RESOURCE_LOCKED = "RESOURCE_LOCKED"
    RESOURCE_DELETED = "RESOURCE_DELETED"
    
    # Business Logic Errors
    APPOINTMENT_CONFLICT = "APPOINTMENT_CONFLICT"
    APPOINTMENT_NOT_AVAILABLE = "APPOINTMENT_NOT_AVAILABLE"
    APPOINTMENT_CANNOT_BE_CANCELLED = "APPOINTMENT_CANNOT_BE_CANCELLED"
    APPOINTMENT_CANNOT_BE_RESCHEDULED = "APPOINTMENT_CANNOT_BE_RESCHEDULED"
    DOCTOR_NOT_AVAILABLE = "DOCTOR_NOT_AVAILABLE"
    PATIENT_NOT_ELIGIBLE = "PATIENT_NOT_ELIGIBLE"
    INVALID_APPOINTMENT_TIME = "INVALID_APPOINTMENT_TIME"
    APPOINTMENT_DURATION_INVALID = "APPOINTMENT_DURATION_INVALID"
    
    # Rate Limiting
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    TOO_MANY_REQUESTS = "TOO_MANY_REQUESTS"
    
    # External Service Errors
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    REDIS_ERROR = "REDIS_ERROR"
    EMAIL_SERVICE_ERROR = "EMAIL_SERVICE_ERROR"
    SMS_SERVICE_ERROR = "SMS_SERVICE_ERROR"
    NOTIFICATION_SERVICE_ERROR = "NOTIFICATION_SERVICE_ERROR"
    
    # System Errors
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    
    # HIPAA Compliance
    PHI_ACCESS_DENIED = "PHI_ACCESS_DENIED"
    AUDIT_LOG_ERROR = "AUDIT_LOG_ERROR"
    DATA_RETENTION_ERROR = "DATA_RETENTION_ERROR"
    ENCRYPTION_ERROR = "ENCRYPTION_ERROR"


class APIException(Exception):
    """Base API exception with enhanced error information."""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.INTERNAL_SERVER_ERROR,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        field: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.field = field
        self.context = context or {}
        self.request_id = request_id
        self.details = details or {}
        self.timestamp = datetime.now(timezone.utc)
        
        super().__init__(message)


class ValidationException(APIException):
    """Validation error exception."""
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.VALIDATION_ERROR,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            field=field,
            context=context,
            request_id=request_id
        )


class AuthenticationException(APIException):
    """Authentication error exception."""
    
    def __init__(
        self,
        message: str = "Authentication required",
        error_code: ErrorCode = ErrorCode.AUTHENTICATION_REQUIRED,
        context: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status.HTTP_401_UNAUTHORIZED,
            context=context,
            request_id=request_id
        )


class AuthorizationException(APIException):
    """Authorization error exception."""
    
    def __init__(
        self,
        message: str = "Insufficient permissions",
        context: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.INSUFFICIENT_PERMISSIONS,
            status_code=status.HTTP_403_FORBIDDEN,
            context=context,
            request_id=request_id
        )


class ResourceNotFoundException(APIException):
    """Resource not found exception."""
    
    def __init__(
        self,
        resource_type: str,
        resource_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ):
        message = f"{resource_type} not found"
        if resource_id:
            message += f" with ID: {resource_id}"
        
        super().__init__(
            message=message,
            error_code=ErrorCode.RESOURCE_NOT_FOUND,
            status_code=status.HTTP_404_NOT_FOUND,
            context=context,
            request_id=request_id
        )


class ResourceConflictException(APIException):
    """Resource conflict exception."""
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.RESOURCE_CONFLICT,
            status_code=status.HTTP_409_CONFLICT,
            context=context,
            request_id=request_id
        )


class BusinessLogicException(APIException):
    """Business logic error exception."""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.APPOINTMENT_CONFLICT,
        context: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status.HTTP_400_BAD_REQUEST,
            context=context,
            request_id=request_id
        )


class RateLimitException(APIException):
    """Rate limit exceeded exception."""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.RATE_LIMIT_EXCEEDED,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            context=context,
            request_id=request_id
        )
        
        if retry_after:
            self.context["retry_after"] = retry_after


class ExternalServiceException(APIException):
    """External service error exception."""
    
    def __init__(
        self,
        service_name: str,
        message: str,
        error_code: ErrorCode = ErrorCode.EXTERNAL_SERVICE_ERROR,
        context: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ):
        full_message = f"{service_name} service error: {message}"
        
        super().__init__(
            message=full_message,
            error_code=error_code,
            status_code=status.HTTP_502_BAD_GATEWAY,
            context=context,
            request_id=request_id
        )


class HIPAAComplianceException(APIException):
    """HIPAA compliance error exception."""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.PHI_ACCESS_DENIED,
        context: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status.HTTP_403_FORBIDDEN,
            context=context,
            request_id=request_id
        )


def get_request_id(request: Request) -> str:
    """Get request ID from request state or generate new one."""
    if hasattr(request.state, 'request_id'):
        return request.state.request_id
    return str(uuid.uuid4())


def create_error_response(
    exception: APIException,
    request: Optional[Request] = None,
    include_traceback: bool = False
) -> JSONResponse:
    """Create standardized error response."""
    
    request_id = get_request_id(request) if request else None
    
    # Prepare error response
    error_response = EnhancedErrorResponse(
        detail=exception.message,
        error_code=exception.error_code.value,
        field=exception.field,
        timestamp=exception.timestamp,
        request_id=request_id,
        context={
            **exception.context,
            **exception.details
        }
    )
    
    # Add traceback in development
    if include_traceback:
        error_response.context["traceback"] = traceback.format_exc()
    
    # Log the error
    logger.error(
        f"API Error: {exception.error_code.value}",
        extra={
            "error_code": exception.error_code.value,
            "message": exception.message,
            "field": exception.field,
            "status_code": exception.status_code,
            "request_id": request_id,
            "context": exception.context
        }
    )
    
    return JSONResponse(
        status_code=exception.status_code,
        content=error_response.dict()
    )


def create_validation_error_response(
    errors: List[Dict[str, Any]],
    request: Optional[Request] = None
) -> JSONResponse:
    """Create validation error response."""
    
    request_id = get_request_id(request) if request else None
    
    error_response = ValidationErrorResponse(
        errors=errors,
        request_id=request_id
    )
    
    # Log validation errors
    logger.warning(
        "Validation errors",
        extra={
            "errors": errors,
            "request_id": request_id
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response.dict()
    )


def create_http_exception_response(
    exception: HTTPException,
    request: Optional[Request] = None
) -> JSONResponse:
    """Create response for HTTPException."""
    
    request_id = get_request_id(request) if request else None
    
    # Determine error code based on status code
    error_code = ErrorCode.INTERNAL_SERVER_ERROR
    if exception.status_code == 401:
        error_code = ErrorCode.AUTHENTICATION_REQUIRED
    elif exception.status_code == 403:
        error_code = ErrorCode.INSUFFICIENT_PERMISSIONS
    elif exception.status_code == 404:
        error_code = ErrorCode.RESOURCE_NOT_FOUND
    elif exception.status_code == 409:
        error_code = ErrorCode.RESOURCE_CONFLICT
    elif exception.status_code == 422:
        error_code = ErrorCode.VALIDATION_ERROR
    elif exception.status_code == 429:
        error_code = ErrorCode.RATE_LIMIT_EXCEEDED
    elif exception.status_code >= 500:
        error_code = ErrorCode.INTERNAL_SERVER_ERROR
    
    error_response = EnhancedErrorResponse(
        detail=str(exception.detail),
        error_code=error_code.value,
        timestamp=datetime.now(timezone.utc),
        request_id=request_id
    )
    
    # Log the error
    logger.error(
        f"HTTP Exception: {exception.status_code}",
        extra={
            "status_code": exception.status_code,
            "detail": str(exception.detail),
            "request_id": request_id
        }
    )
    
    return JSONResponse(
        status_code=exception.status_code,
        content=error_response.dict()
    )


def create_unhandled_exception_response(
    exception: Exception,
    request: Optional[Request] = None
) -> JSONResponse:
    """Create response for unhandled exceptions."""
    
    request_id = get_request_id(request) if request else None
    
    error_response = EnhancedErrorResponse(
        detail="An unexpected error occurred",
        error_code=ErrorCode.INTERNAL_SERVER_ERROR.value,
        timestamp=datetime.now(timezone.utc),
        request_id=request_id,
        context={
            "exception_type": type(exception).__name__,
            "traceback": traceback.format_exc()
        }
    )
    
    # Log the error
    logger.error(
        f"Unhandled exception: {type(exception).__name__}",
        extra={
            "exception": str(exception),
            "request_id": request_id,
            "traceback": traceback.format_exc()
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.dict()
    )


# Exception handlers
async def api_exception_handler(request: Request, exc: APIException) -> JSONResponse:
    """Handle APIException."""
    return create_error_response(exc, request)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle FastAPI validation errors."""
    errors = []
    
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field,
            "message": error["msg"],
            "code": error["type"].upper(),
            "input": error.get("input")
        })
    
    return create_validation_error_response(errors, request)


async def pydantic_validation_exception_handler(request: Request, exc: PydanticValidationError) -> JSONResponse:
    """Handle Pydantic validation errors."""
    errors = []
    
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field,
            "message": error["msg"],
            "code": error["type"].upper(),
            "input": error.get("input")
        })
    
    return create_validation_error_response(errors, request)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTPException."""
    return create_http_exception_response(exc, request)


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle general exceptions."""
    return create_unhandled_exception_response(exc, request)


# Error context utilities
class ErrorContext:
    """Utilities for adding context to errors."""
    
    @staticmethod
    def add_user_context(context: Dict[str, Any], user_id: Optional[str] = None, user_role: Optional[str] = None) -> Dict[str, Any]:
        """Add user context to error."""
        if user_id:
            context["user_id"] = user_id
        if user_role:
            context["user_role"] = user_role
        return context
    
    @staticmethod
    def add_request_context(context: Dict[str, Any], request: Request) -> Dict[str, Any]:
        """Add request context to error."""
        context.update({
            "method": request.method,
            "url": str(request.url),
            "headers": dict(request.headers),
            "client_ip": request.client.host if request.client else None
        })
        return context
    
    @staticmethod
    def add_resource_context(context: Dict[str, Any], resource_type: str, resource_id: Optional[str] = None) -> Dict[str, Any]:
        """Add resource context to error."""
        context["resource_type"] = resource_type
        if resource_id:
            context["resource_id"] = resource_id
        return context
    
    @staticmethod
    def add_business_context(context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Add business-specific context to error."""
        context.update(kwargs)
        return context


# Error recovery utilities
class ErrorRecovery:
    """Utilities for error recovery and retry logic."""
    
    @staticmethod
    def is_retryable_error(exception: Exception) -> bool:
        """Check if an error is retryable."""
        if isinstance(exception, APIException):
            return exception.error_code in [
                ErrorCode.EXTERNAL_SERVICE_ERROR,
                ErrorCode.DATABASE_ERROR,
                ErrorCode.REDIS_ERROR,
                ErrorCode.TIMEOUT_ERROR,
                ErrorCode.SERVICE_UNAVAILABLE
            ]
        return False
    
    @staticmethod
    def get_retry_delay(attempt: int, base_delay: float = 1.0, max_delay: float = 60.0) -> float:
        """Calculate retry delay with exponential backoff."""
        delay = base_delay * (2 ** attempt)
        return min(delay, max_delay)
    
    @staticmethod
    def should_retry(attempt: int, max_attempts: int = 3) -> bool:
        """Check if should retry based on attempt count."""
        return attempt < max_attempts
