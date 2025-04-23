"""Enhanced input validation and sanitization for security."""

import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from fastapi import HTTPException, status
from pydantic import BaseModel, Field, validator
from pydantic.validators import str_validator

from app.core.logging import get_logger

logger = get_logger(__name__)


class SecurityValidationError(HTTPException):
    """Custom exception for security validation errors."""
    
    def __init__(self, detail: str, field: Optional[str] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Security validation failed",
                "message": detail,
                "field": field
            }
        )


class SecureString(str):
    """String type with security validation."""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if isinstance(v, str):
            # Sanitize the string
            sanitized = cls.sanitize(v)
            return cls(sanitized)
        return v
    
    @classmethod
    def sanitize(cls, value: str) -> str:
        """Sanitize string input."""
        if not value:
            return value
        
        # Remove null bytes
        value = value.replace('\x00', '')
        
        # Remove control characters except newlines and tabs
        value = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', value)
        
        # Normalize whitespace
        value = re.sub(r'\s+', ' ', value).strip()
        
        return value


class SecureEmail(str):
    """Email type with enhanced validation."""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if isinstance(v, str):
            # Basic email validation
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, v):
                raise SecurityValidationError("Invalid email format")
            
            # Sanitize email
            sanitized = SecureString.sanitize(v.lower())
            
            # Additional security checks
            if cls._contains_suspicious_patterns(sanitized):
                raise SecurityValidationError("Email contains suspicious patterns")
            
            return cls(sanitized)
        return v
    
    @classmethod
    def _contains_suspicious_patterns(cls, email: str) -> bool:
        """Check for suspicious patterns in email."""
        suspicious_patterns = [
            r'<script',
            r'javascript:',
            r'data:',
            r'vbscript:',
            r'onload=',
            r'onerror=',
            r'<iframe',
            r'<object',
            r'<embed',
            r'<link',
            r'<meta',
            r'<style',
        ]
        
        email_lower = email.lower()
        return any(re.search(pattern, email_lower) for pattern in suspicious_patterns)


class SecurePassword(str):
    """Password type with security requirements."""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if isinstance(v, str):
            # Check password strength
            cls._validate_strength(v)
            
            # Check for common passwords
            if cls._is_common_password(v):
                raise SecurityValidationError("Password is too common")
            
            return cls(v)
        return v
    
    @classmethod
    def _validate_strength(cls, password: str) -> None:
        """Validate password strength."""
        if len(password) < 8:
            raise SecurityValidationError("Password must be at least 8 characters long")
        
        if len(password) > 128:
            raise SecurityValidationError("Password must be less than 128 characters")
        
        # Check for required character types
        has_lower = re.search(r'[a-z]', password)
        has_upper = re.search(r'[A-Z]', password)
        has_digit = re.search(r'\d', password)
        has_special = re.search(r'[!@#$%^&*(),.?":{}|<>]', password)
        
        if not (has_lower and has_upper and has_digit and has_special):
            raise SecurityValidationError(
                "Password must contain at least one lowercase letter, "
                "one uppercase letter, one digit, and one special character"
            )
        
        # Check for common patterns
        if cls._has_common_patterns(password):
            raise SecurityValidationError("Password contains common patterns")
    
    @classmethod
    def _is_common_password(cls, password: str) -> bool:
        """Check if password is common."""
        common_passwords = [
            "password", "123456", "123456789", "qwerty", "abc123",
            "password123", "admin", "letmein", "welcome", "monkey",
            "1234567890", "password1", "qwerty123", "dragon", "master"
        ]
        
        return password.lower() in common_passwords
    
    @classmethod
    def _has_common_patterns(cls, password: str) -> bool:
        """Check for common password patterns."""
        # Sequential characters
        if re.search(r'(.)\1{2,}', password):
            return True
        
        # Keyboard patterns
        keyboard_patterns = [
            r'qwerty', r'asdf', r'zxcv', r'1234', r'5678', r'90',
            r'qwertyuiop', r'asdfghjkl', r'zxcvbnm'
        ]
        
        password_lower = password.lower()
        return any(re.search(pattern, password_lower) for pattern in keyboard_patterns)


class SecureUUID(str):
    """UUID type with validation."""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if isinstance(v, str):
            try:
                # Validate UUID format
                uuid.UUID(v)
                return cls(v)
            except ValueError:
                raise SecurityValidationError("Invalid UUID format")
        elif isinstance(v, uuid.UUID):
            return cls(str(v))
        return v


class SecureDateTime(str):
    """DateTime type with validation."""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if isinstance(v, str):
            try:
                # Parse ISO format datetime
                datetime.fromisoformat(v.replace('Z', '+00:00'))
                return cls(v)
            except ValueError:
                raise SecurityValidationError("Invalid datetime format")
        elif isinstance(v, datetime):
            return cls(v.isoformat())
        return v


class InputSanitizer:
    """Input sanitization utilities."""
    
    @staticmethod
    def sanitize_string(value: str) -> str:
        """Sanitize string input."""
        if not value:
            return value
        
        # Remove potentially dangerous characters
        value = re.sub(r'[<>"\']', '', value)
        
        # Remove SQL injection patterns
        sql_patterns = [
            r'union\s+select',
            r'drop\s+table',
            r'delete\s+from',
            r'insert\s+into',
            r'update\s+set',
            r'exec\s*\(',
            r'execute\s*\(',
            r'script\s*>',
            r'<script',
            r'javascript:',
            r'vbscript:',
            r'onload\s*=',
            r'onerror\s*=',
        ]
        
        value_lower = value.lower()
        for pattern in sql_patterns:
            if re.search(pattern, value_lower):
                logger.warning(f"Potential injection attempt detected: {pattern}")
                raise SecurityValidationError("Input contains potentially dangerous content")
        
        return SecureString.sanitize(value)
    
    @staticmethod
    def sanitize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize dictionary input."""
        sanitized = {}
        
        for key, value in data.items():
            # Sanitize key
            sanitized_key = InputSanitizer.sanitize_string(str(key))
            
            # Sanitize value based on type
            if isinstance(value, str):
                sanitized[sanitized_key] = InputSanitizer.sanitize_string(value)
            elif isinstance(value, dict):
                sanitized[sanitized_key] = InputSanitizer.sanitize_dict(value)
            elif isinstance(value, list):
                sanitized[sanitized_key] = InputSanitizer.sanitize_list(value)
            else:
                sanitized[sanitized_key] = value
        
        return sanitized
    
    @staticmethod
    def sanitize_list(data: List[Any]) -> List[Any]:
        """Sanitize list input."""
        sanitized = []
        
        for item in data:
            if isinstance(item, str):
                sanitized.append(InputSanitizer.sanitize_string(item))
            elif isinstance(item, dict):
                sanitized.append(InputSanitizer.sanitize_dict(item))
            elif isinstance(item, list):
                sanitized.append(InputSanitizer.sanitize_list(item))
            else:
                sanitized.append(item)
        
        return sanitized


class SecurityValidators:
    """Security validation utilities."""
    
    @staticmethod
    def validate_phi_access(user_id: uuid.UUID, resource_owner_id: uuid.UUID, user_role: str) -> bool:
        """Validate PHI access permissions."""
        # Users can access their own data
        if user_id == resource_owner_id:
            return True
        
        # Admins can access all data
        if user_role == "admin":
            return True
        
        # Doctors can access their patients' data
        if user_role == "doctor":
            # In a real implementation, you'd check if the resource_owner is a patient
            # of this doctor by querying appointments
            return True
        
        return False
    
    @staticmethod
    def validate_appointment_time(start_time: datetime, end_time: datetime) -> bool:
        """Validate appointment time constraints."""
        now = datetime.now(start_time.tzinfo)
        
        # Appointment must be in the future
        if start_time <= now:
            raise SecurityValidationError("Appointment must be in the future")
        
        # End time must be after start time
        if end_time <= start_time:
            raise SecurityValidationError("End time must be after start time")
        
        # Appointment duration must be reasonable (max 8 hours)
        duration = end_time - start_time
        if duration.total_seconds() > 8 * 3600:
            raise SecurityValidationError("Appointment duration cannot exceed 8 hours")
        
        return True
    
    @staticmethod
    def validate_rate_limit(identifier: str, limit: int, window_seconds: int) -> bool:
        """Validate rate limiting."""
        # This would integrate with your rate limiting system
        # For now, just return True
        return True
    
    @staticmethod
    def validate_file_upload(filename: str, content_type: str, size: int) -> bool:
        """Validate file upload security."""
        # Check file extension
        allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx']
        file_ext = '.' + filename.split('.')[-1].lower()
        
        if file_ext not in allowed_extensions:
            raise SecurityValidationError(f"File type {file_ext} not allowed")
        
        # Check content type
        allowed_types = [
            'application/pdf',
            'image/jpeg',
            'image/png',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        ]
        
        if content_type not in allowed_types:
            raise SecurityValidationError(f"Content type {content_type} not allowed")
        
        # Check file size (max 10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        if size > max_size:
            raise SecurityValidationError("File size exceeds maximum allowed size")
        
        return True


def validate_input(data: Any, input_type: str = "general") -> Any:
    """Validate and sanitize input data."""
    try:
        if isinstance(data, str):
            return InputSanitizer.sanitize_string(data)
        elif isinstance(data, dict):
            return InputSanitizer.sanitize_dict(data)
        elif isinstance(data, list):
            return InputSanitizer.sanitize_list(data)
        else:
            return data
    except SecurityValidationError:
        raise
    except Exception as e:
        logger.error(f"Input validation error: {e}")
        raise SecurityValidationError("Input validation failed")


def sanitize_for_logging(data: Any) -> Any:
    """Sanitize data for safe logging."""
    if isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            if key.lower() in ['password', 'token', 'secret', 'key']:
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = sanitize_for_logging(value)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_for_logging(item) for item in data]
    elif isinstance(data, str):
        # Remove potential sensitive data
        sensitive_patterns = [
            r'password["\']?\s*[:=]\s*["\']?[^"\']+["\']?',
            r'token["\']?\s*[:=]\s*["\']?[^"\']+["\']?',
            r'secret["\']?\s*[:=]\s*["\']?[^"\']+["\']?',
            r'key["\']?\s*[:=]\s*["\']?[^"\']+["\']?',
        ]
        
        sanitized = data
        for pattern in sensitive_patterns:
            sanitized = re.sub(pattern, r'\1[REDACTED]', sanitized, flags=re.IGNORECASE)
        
        return sanitized
    else:
        return data
