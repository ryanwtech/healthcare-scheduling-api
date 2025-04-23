"""Security configuration for HIPAA compliance."""

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.core.config import settings


class SecurityLevel(str, Enum):
    """Security levels for different environments."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class EncryptionConfig(BaseModel):
    """Encryption configuration."""
    algorithm: str = "AES-256-GCM"
    key_derivation: str = "PBKDF2"
    iterations: int = 100000
    salt_length: int = 32


class SessionConfig(BaseModel):
    """Session management configuration."""
    max_sessions_per_user: int = 5
    session_timeout_minutes: int = 30
    idle_timeout_minutes: int = 15
    token_length: int = 32
    refresh_token_length: int = 64


class AuditConfig(BaseModel):
    """Audit logging configuration."""
    log_phi_access: bool = True
    log_authentication: bool = True
    log_authorization: bool = True
    log_data_modification: bool = True
    log_security_violations: bool = True
    retention_days: int = 2555  # 7 years


class AccessControlConfig(BaseModel):
    """Access control configuration."""
    enable_rbac: bool = True
    enable_phi_protection: bool = True
    enable_session_management: bool = True
    enable_rate_limiting: bool = True
    max_failed_attempts: int = 5
    lockout_duration_minutes: int = 30


class DataRetentionConfig(BaseModel):
    """Data retention configuration."""
    medical_records_days: int = 2190  # 6 years
    appointment_records_days: int = 2190  # 6 years
    audit_logs_days: int = 2555  # 7 years
    user_accounts_days: int = 2555  # 7 years
    system_logs_days: int = 365  # 1 year
    backup_data_days: int = 2190  # 6 years


class SecurityConfig(BaseModel):
    """Main security configuration."""
    level: SecurityLevel = SecurityLevel.PRODUCTION
    encryption: EncryptionConfig = Field(default_factory=EncryptionConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)
    audit: AuditConfig = Field(default_factory=AuditConfig)
    access_control: AccessControlConfig = Field(default_factory=AccessControlConfig)
    data_retention: DataRetentionConfig = Field(default_factory=DataRetentionConfig)
    
    # HIPAA compliance settings
    hipaa_compliant: bool = True
    phi_encryption_required: bool = True
    audit_trail_required: bool = True
    access_controls_required: bool = True
    data_retention_required: bool = True
    
    # Security headers
    security_headers_enabled: bool = True
    https_redirect_enabled: bool = True
    csp_enabled: bool = True
    hsts_enabled: bool = True
    
    # Input validation
    input_sanitization_enabled: bool = True
    sql_injection_protection: bool = True
    xss_protection: bool = True
    csrf_protection: bool = True
    
    # Rate limiting
    rate_limiting_enabled: bool = True
    default_rate_limit: int = 100  # requests per minute
    phi_rate_limit: int = 10  # requests per minute for PHI endpoints
    
    # Password requirements
    password_min_length: int = 8
    password_max_length: int = 128
    password_require_uppercase: bool = True
    password_require_lowercase: bool = True
    password_require_digits: bool = True
    password_require_special: bool = True
    password_history_count: int = 5
    
    # Session security
    session_secure_cookies: bool = True
    session_httponly_cookies: bool = True
    session_samesite: str = "strict"
    
    # Encryption settings
    encrypt_phi_at_rest: bool = True
    encrypt_phi_in_transit: bool = True
    encrypt_sensitive_fields: bool = True
    
    # Audit settings
    audit_all_phi_access: bool = True
    audit_all_authentication: bool = True
    audit_all_authorization: bool = True
    audit_all_data_changes: bool = True
    
    # Data retention
    automatic_data_cleanup: bool = True
    secure_data_deletion: bool = True
    data_anonymization: bool = True
    
    # Security monitoring
    security_monitoring_enabled: bool = True
    threat_detection_enabled: bool = True
    incident_response_enabled: bool = True
    
    # Compliance reporting
    compliance_reporting_enabled: bool = True
    breach_notification_enabled: bool = True
    risk_assessment_enabled: bool = True


def get_security_config() -> SecurityConfig:
    """Get security configuration based on environment."""
    if settings.is_production:
        level = SecurityLevel.PRODUCTION
    elif settings.is_development:
        level = SecurityLevel.DEVELOPMENT
    else:
        level = SecurityLevel.STAGING
    
    return SecurityConfig(level=level)


# Global security configuration
security_config = get_security_config()


# PHI field definitions for different entities
PHI_FIELDS = {
    "user": ["email", "full_name", "phone", "address"],
    "appointment": ["notes", "diagnosis", "treatment_notes"],
    "patient_profile": ["full_name", "email", "phone", "address", "emergency_contact", "medical_history"],
    "medical_record": ["diagnosis", "treatment_notes", "medications", "allergies", "vital_signs"],
    "insurance": ["policy_number", "group_number", "member_id"],
    "billing": ["payment_method", "billing_address", "insurance_info"]
}

# Sensitive endpoints that require enhanced security
SENSITIVE_ENDPOINTS = [
    "/api/v1/users/",
    "/api/v1/appointments/",
    "/api/v1/patients/",
    "/api/v1/medical-records/",
    "/api/v1/audit/",
    "/api/v1/billing/",
    "/api/v1/insurance/"
]

# Security headers configuration
SECURITY_HEADERS = {
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    "Permissions-Policy": "accelerometer=(), ambient-light-sensor=(), autoplay=(), battery=(), camera=(), cross-origin-isolated=(), display-capture=(), document-domain=(), encrypted-media=(), execution-while-not-rendered=(), execution-while-out-of-viewport=(), fullscreen=(), geolocation=(), gyroscope=(), keyboard-map=(), magnetometer=(), microphone=(), midi=(), navigation-override=(), payment=(), picture-in-picture=(), publickey-credentials-get=(), screen-wake-lock=(), sync-xhr=(), usb=(), web-share=(), xr-spatial-tracking=()"
}

# Content Security Policy for different environments
CSP_POLICIES = {
    SecurityLevel.DEVELOPMENT: (
        "default-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self' data:; "
        "connect-src 'self' ws: wss:; "
        "frame-ancestors 'none'"
    ),
    SecurityLevel.STAGING: (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    ),
    SecurityLevel.PRODUCTION: (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
}

# Rate limiting configuration
RATE_LIMITS = {
    "default": {"limit": 100, "window": 60},  # 100 requests per minute
    "auth": {"limit": 10, "window": 60},  # 10 auth attempts per minute
    "phi": {"limit": 10, "window": 60},  # 10 PHI requests per minute
    "appointment": {"limit": 5, "window": 60},  # 5 appointment requests per minute
    "admin": {"limit": 200, "window": 60},  # 200 admin requests per minute
}

# Password complexity requirements
PASSWORD_REQUIREMENTS = {
    "min_length": 8,
    "max_length": 128,
    "require_uppercase": True,
    "require_lowercase": True,
    "require_digits": True,
    "require_special": True,
    "forbidden_patterns": [
        r'password',
        r'123456',
        r'qwerty',
        r'admin',
        r'user',
        r'login'
    ]
}

# Session security configuration
SESSION_CONFIG = {
    "max_sessions_per_user": 5,
    "session_timeout_minutes": 30,
    "idle_timeout_minutes": 15,
    "secure_cookies": True,
    "httponly_cookies": True,
    "samesite": "strict",
    "token_length": 32,
    "refresh_token_length": 64
}

# Data retention periods (in days)
RETENTION_PERIODS = {
    "medical_records": 2190,  # 6 years
    "appointment_records": 2190,  # 6 years
    "audit_logs": 2555,  # 7 years
    "user_accounts": 2555,  # 7 years
    "system_logs": 365,  # 1 year
    "backup_data": 2190,  # 6 years
    "billing_records": 2555,  # 7 years
    "insurance_records": 2555,  # 7 years
}

# Security monitoring thresholds
SECURITY_THRESHOLDS = {
    "max_failed_logins": 5,
    "max_concurrent_sessions": 5,
    "max_requests_per_minute": 100,
    "max_phi_requests_per_minute": 10,
    "session_timeout_minutes": 30,
    "idle_timeout_minutes": 15,
    "password_reset_timeout_minutes": 15,
    "account_lockout_minutes": 30,
}

# Incident response configuration
INCIDENT_RESPONSE = {
    "auto_lockout_enabled": True,
    "breach_notification_timeout_hours": 24,
    "security_alert_recipients": ["security@healthcare-api.com"],
    "compliance_alert_recipients": ["compliance@healthcare-api.com"],
    "incident_escalation_levels": {
        "low": ["security@healthcare-api.com"],
        "medium": ["security@healthcare-api.com", "compliance@healthcare-api.com"],
        "high": ["security@healthcare-api.com", "compliance@healthcare-api.com", "legal@healthcare-api.com"],
        "critical": ["security@healthcare-api.com", "compliance@healthcare-api.com", "legal@healthcare-api.com", "executive@healthcare-api.com"]
    }
}
