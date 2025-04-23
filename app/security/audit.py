"""Comprehensive audit logging for HIPAA compliance."""

import json
import uuid
from datetime import datetime, UTC
from enum import Enum
from typing import Any, Dict, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models import User

logger = get_logger(__name__)


class AuditEventType(str, Enum):
    """Types of audit events for HIPAA compliance."""
    
    # Authentication events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    TOKEN_REFRESH = "token_refresh"
    PASSWORD_CHANGE = "password_change"
    
    # User management events
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    USER_DEACTIVATED = "user_deactivated"
    USER_ACTIVATED = "user_activated"
    
    # PHI access events
    PHI_ACCESS = "phi_access"
    PHI_CREATED = "phi_created"
    PHI_UPDATED = "phi_updated"
    PHI_DELETED = "phi_deleted"
    PHI_EXPORTED = "phi_exported"
    
    # Appointment events
    APPOINTMENT_CREATED = "appointment_created"
    APPOINTMENT_UPDATED = "appointment_updated"
    APPOINTMENT_CANCELLED = "appointment_cancelled"
    APPOINTMENT_VIEWED = "appointment_viewed"
    
    # Availability events
    AVAILABILITY_CREATED = "availability_created"
    AVAILABILITY_UPDATED = "availability_updated"
    AVAILABILITY_DELETED = "availability_deleted"
    
    # System events
    SYSTEM_ACCESS = "system_access"
    CONFIGURATION_CHANGE = "configuration_change"
    SECURITY_VIOLATION = "security_violation"
    DATA_BREACH = "data_breach"


class AuditLogger:
    """Comprehensive audit logger for HIPAA compliance."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def log_event(
        self,
        event_type: AuditEventType,
        user_id: Optional[uuid.UUID] = None,
        resource_id: Optional[uuid.UUID] = None,
        resource_type: Optional[str] = None,
        action: str = "",
        details: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None,
        success: bool = True,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> None:
        """
        Log an audit event with comprehensive details.
        
        Args:
            event_type: Type of audit event
            user_id: ID of user performing the action
            resource_id: ID of resource being accessed/modified
            resource_type: Type of resource (e.g., 'appointment', 'user')
            action: Description of the action performed
            details: Additional details about the event
            request: FastAPI request object for extracting metadata
            success: Whether the action was successful
            ip_address: IP address of the request
            user_agent: User agent string
        """
        try:
            # Extract metadata from request if provided
            if request:
                ip_address = ip_address or self._get_client_ip(request)
                user_agent = user_agent or request.headers.get("user-agent", "")
            
            # Create audit log entry
            audit_entry = {
                "event_id": str(uuid.uuid4()),
                "timestamp": datetime.now(UTC).isoformat(),
                "event_type": event_type.value,
                "user_id": str(user_id) if user_id else None,
                "resource_id": str(resource_id) if resource_id else None,
                "resource_type": resource_type,
                "action": action,
                "success": success,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "details": details or {},
                "severity": self._get_severity(event_type, success)
            }
            
            # Log to structured logger
            logger.info(
                "Audit event logged",
                **audit_entry
            )
            
            # Store in database for compliance
            self._store_audit_entry(audit_entry)
            
        except Exception as e:
            # Never fail the main operation due to audit logging issues
            logger.error(f"Failed to log audit event: {e}")
    
    def log_phi_access(
        self,
        user_id: uuid.UUID,
        resource_type: str,
        resource_id: uuid.UUID,
        action: str,
        request: Optional[Request] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log PHI access events with enhanced security."""
        self.log_event(
            event_type=AuditEventType.PHI_ACCESS,
            user_id=user_id,
            resource_id=resource_id,
            resource_type=resource_type,
            action=action,
            details=details,
            request=request,
            success=True
        )
    
    def log_authentication(
        self,
        user_id: Optional[uuid.UUID],
        success: bool,
        email: Optional[str] = None,
        request: Optional[Request] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log authentication events."""
        event_type = AuditEventType.LOGIN_SUCCESS if success else AuditEventType.LOGIN_FAILED
        
        self.log_event(
            event_type=event_type,
            user_id=user_id,
            action="authentication",
            details={
                "email": email,
                **(details or {})
            },
            request=request,
            success=success
        )
    
    def log_user_management(
        self,
        admin_user_id: uuid.UUID,
        target_user_id: uuid.UUID,
        action: str,
        details: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None
    ) -> None:
        """Log user management events."""
        event_type_map = {
            "create": AuditEventType.USER_CREATED,
            "update": AuditEventType.USER_UPDATED,
            "delete": AuditEventType.USER_DELETED,
            "deactivate": AuditEventType.USER_DEACTIVATED,
            "activate": AuditEventType.USER_ACTIVATED
        }
        
        event_type = event_type_map.get(action, AuditEventType.USER_UPDATED)
        
        self.log_event(
            event_type=event_type,
            user_id=admin_user_id,
            resource_id=target_user_id,
            resource_type="user",
            action=action,
            details=details,
            request=request,
            success=True
        )
    
    def log_appointment_event(
        self,
        user_id: uuid.UUID,
        appointment_id: uuid.UUID,
        action: str,
        details: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None
    ) -> None:
        """Log appointment-related events."""
        event_type_map = {
            "create": AuditEventType.APPOINTMENT_CREATED,
            "update": AuditEventType.APPOINTMENT_UPDATED,
            "cancel": AuditEventType.APPOINTMENT_CANCELLED,
            "view": AuditEventType.APPOINTMENT_VIEWED
        }
        
        event_type = event_type_map.get(action, AuditEventType.APPOINTMENT_VIEWED)
        
        self.log_event(
            event_type=event_type,
            user_id=user_id,
            resource_id=appointment_id,
            resource_type="appointment",
            action=action,
            details=details,
            request=request,
            success=True
        )
    
    def log_security_violation(
        self,
        violation_type: str,
        user_id: Optional[uuid.UUID] = None,
        details: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None
    ) -> None:
        """Log security violations."""
        self.log_event(
            event_type=AuditEventType.SECURITY_VIOLATION,
            user_id=user_id,
            action=violation_type,
            details=details,
            request=request,
            success=False
        )
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check for forwarded headers first
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # Fall back to direct client IP
        return request.client.host if request.client else "unknown"
    
    def _get_severity(self, event_type: AuditEventType, success: bool) -> str:
        """Determine severity level for audit event."""
        if not success:
            return "high"
        
        high_severity_events = {
            AuditEventType.PHI_ACCESS,
            AuditEventType.PHI_CREATED,
            AuditEventType.PHI_UPDATED,
            AuditEventType.PHI_DELETED,
            AuditEventType.USER_DELETED,
            AuditEventType.SECURITY_VIOLATION,
            AuditEventType.DATA_BREACH
        }
        
        if event_type in high_severity_events:
            return "high"
        
        medium_severity_events = {
            AuditEventType.LOGIN_FAILED,
            AuditEventType.USER_CREATED,
            AuditEventType.USER_UPDATED,
            AuditEventType.APPOINTMENT_CREATED,
            AuditEventType.APPOINTMENT_UPDATED,
            AuditEventType.APPOINTMENT_CANCELLED
        }
        
        if event_type in medium_severity_events:
            return "medium"
        
        return "low"
    
    def _store_audit_entry(self, audit_entry: Dict[str, Any]) -> None:
        """Store audit entry in database for compliance."""
        try:
            # In a real implementation, you would store this in a dedicated audit table
            # For now, we'll just ensure it's logged with high priority
            logger.info(
                "AUDIT_STORE",
                audit_entry=json.dumps(audit_entry, default=str),
                level="audit"
            )
        except Exception as e:
            logger.error(f"Failed to store audit entry: {e}")


def get_audit_logger(db: Session) -> AuditLogger:
    """Get audit logger instance."""
    return AuditLogger(db)
