"""Enhanced access control for HIPAA compliance."""

import uuid
from datetime import datetime, timedelta, UTC
from enum import Enum
from typing import Dict, List, Optional, Set

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.security import get_current_user
from app.db.models import User, UserRole
from app.security.audit import AuditLogger, get_audit_logger

logger = get_logger(__name__)


class Permission(str, Enum):
    """Fine-grained permissions for HIPAA compliance."""
    
    # User management permissions
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    USER_DELETE = "user:delete"
    USER_ACTIVATE = "user:activate"
    USER_DEACTIVATE = "user:deactivate"
    
    # PHI access permissions
    PHI_READ = "phi:read"
    PHI_WRITE = "phi:write"
    PHI_DELETE = "phi:delete"
    PHI_EXPORT = "phi:export"
    
    # Appointment permissions
    APPOINTMENT_READ = "appointment:read"
    APPOINTMENT_WRITE = "appointment:write"
    APPOINTMENT_DELETE = "appointment:delete"
    APPOINTMENT_CANCEL = "appointment:cancel"
    
    # Availability permissions
    AVAILABILITY_READ = "availability:read"
    AVAILABILITY_WRITE = "availability:write"
    AVAILABILITY_DELETE = "availability:delete"
    
    # System permissions
    SYSTEM_ADMIN = "system:admin"
    AUDIT_READ = "audit:read"
    CONFIG_WRITE = "config:write"


class ResourceType(str, Enum):
    """Resource types for access control."""
    USER = "user"
    APPOINTMENT = "appointment"
    AVAILABILITY = "availability"
    AUDIT_LOG = "audit_log"
    SYSTEM_CONFIG = "system_config"


class AccessControl:
    """Enhanced access control system for HIPAA compliance."""
    
    def __init__(self, db: Session):
        self.db = db
        self.audit_logger = get_audit_logger(db)
        
        # Define role-based permissions
        self.role_permissions: Dict[UserRole, Set[Permission]] = {
            UserRole.ADMIN: {
                Permission.USER_READ,
                Permission.USER_WRITE,
                Permission.USER_DELETE,
                Permission.USER_ACTIVATE,
                Permission.USER_DEACTIVATE,
                Permission.PHI_READ,
                Permission.PHI_WRITE,
                Permission.PHI_DELETE,
                Permission.PHI_EXPORT,
                Permission.APPOINTMENT_READ,
                Permission.APPOINTMENT_WRITE,
                Permission.APPOINTMENT_DELETE,
                Permission.APPOINTMENT_CANCEL,
                Permission.AVAILABILITY_READ,
                Permission.AVAILABILITY_WRITE,
                Permission.AVAILABILITY_DELETE,
                Permission.SYSTEM_ADMIN,
                Permission.AUDIT_READ,
                Permission.CONFIG_WRITE
            },
            UserRole.DOCTOR: {
                Permission.USER_READ,  # Can read patient info
                Permission.PHI_READ,  # Can read PHI for their patients
                Permission.PHI_WRITE,  # Can update PHI for their patients
                Permission.APPOINTMENT_READ,
                Permission.APPOINTMENT_WRITE,
                Permission.APPOINTMENT_DELETE,
                Permission.APPOINTMENT_CANCEL,
                Permission.AVAILABILITY_READ,
                Permission.AVAILABILITY_WRITE,
                Permission.AVAILABILITY_DELETE
            },
            UserRole.PATIENT: {
                Permission.USER_READ,  # Can read own info
                Permission.PHI_READ,  # Can read own PHI
                Permission.APPOINTMENT_READ,  # Can read own appointments
                Permission.APPOINTMENT_WRITE,  # Can create appointments
                Permission.APPOINTMENT_CANCEL,  # Can cancel own appointments
                Permission.AVAILABILITY_READ  # Can read doctor availability
            }
        }
    
    def check_permission(
        self,
        user: User,
        permission: Permission,
        resource_type: Optional[ResourceType] = None,
        resource_id: Optional[uuid.UUID] = None,
        request: Optional[Request] = None
    ) -> bool:
        """
        Check if user has permission to perform action.
        
        Args:
            user: User requesting access
            permission: Permission to check
            resource_type: Type of resource being accessed
            resource_id: ID of specific resource
            request: FastAPI request object
            
        Returns:
            True if permission granted, False otherwise
        """
        try:
            # Check if user is active
            if not user.is_active:
                self._log_access_denied(user, permission, "User inactive", request)
                return False
            
            # Check role-based permissions
            user_permissions = self.role_permissions.get(user.role, set())
            if permission not in user_permissions:
                self._log_access_denied(user, permission, "Insufficient role permissions", request)
                return False
            
            # Check resource-specific access
            if resource_type and resource_id:
                if not self._check_resource_access(user, resource_type, resource_id, permission):
                    self._log_access_denied(user, permission, f"No access to {resource_type}:{resource_id}", request)
                    return False
            
            # Log successful access
            self._log_access_granted(user, permission, resource_type, resource_id, request)
            return True
            
        except Exception as e:
            logger.error(f"Error checking permission: {e}")
            self._log_access_denied(user, permission, f"Error: {e}", request)
            return False
    
    def check_phi_access(
        self,
        user: User,
        resource_type: ResourceType,
        resource_id: uuid.UUID,
        action: str,
        request: Optional[Request] = None
    ) -> bool:
        """
        Check PHI access with enhanced logging.
        
        Args:
            user: User requesting PHI access
            resource_type: Type of PHI resource
            resource_id: ID of PHI resource
            action: Action being performed
            request: FastAPI request object
            
        Returns:
            True if PHI access granted, False otherwise
        """
        # Check basic permission
        permission = Permission.PHI_READ if action == "read" else Permission.PHI_WRITE
        
        if not self.check_permission(user, permission, resource_type, resource_id, request):
            return False
        
        # Additional PHI-specific checks
        if not self._check_phi_relationship(user, resource_type, resource_id):
            self._log_access_denied(user, permission, "No PHI relationship", request)
            return False
        
        # Log PHI access
        self.audit_logger.log_phi_access(
            user_id=user.id,
            resource_type=resource_type.value,
            resource_id=resource_id,
            action=action,
            request=request
        )
        
        return True
    
    def _check_resource_access(
        self,
        user: User,
        resource_type: ResourceType,
        resource_id: uuid.UUID,
        permission: Permission
    ) -> bool:
        """Check if user has access to specific resource."""
        try:
            if resource_type == ResourceType.USER:
                return self._check_user_access(user, resource_id, permission)
            elif resource_type == ResourceType.APPOINTMENT:
                return self._check_appointment_access(user, resource_id, permission)
            elif resource_type == ResourceType.AVAILABILITY:
                return self._check_availability_access(user, resource_id, permission)
            elif resource_type == ResourceType.AUDIT_LOG:
                return self._check_audit_access(user, permission)
            elif resource_type == ResourceType.SYSTEM_CONFIG:
                return self._check_system_config_access(user, permission)
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking resource access: {e}")
            return False
    
    def _check_user_access(self, user: User, target_user_id: uuid.UUID, permission: Permission) -> bool:
        """Check user access to another user's data."""
        # Users can always access their own data
        if user.id == target_user_id:
            return True
        
        # Admins can access all users
        if user.role == UserRole.ADMIN:
            return True
        
        # Doctors can access their patients
        if user.role == UserRole.DOCTOR:
            # Check if target user is a patient of this doctor
            from app.db.models import Appointment
            has_appointment = self.db.query(Appointment).filter(
                Appointment.doctor_id == user.id,
                Appointment.patient_id == target_user_id
            ).first() is not None
            return has_appointment
        
        return False
    
    def _check_appointment_access(self, user: User, appointment_id: uuid.UUID, permission: Permission) -> bool:
        """Check user access to appointment."""
        from app.db.models import Appointment
        
        appointment = self.db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            return False
        
        # Users can access their own appointments
        if user.id == appointment.patient_id or user.id == appointment.doctor_id:
            return True
        
        # Admins can access all appointments
        if user.role == UserRole.ADMIN:
            return True
        
        return False
    
    def _check_availability_access(self, user: User, availability_id: uuid.UUID, permission: Permission) -> bool:
        """Check user access to availability."""
        from app.db.models import Availability
        
        availability = self.db.query(Availability).filter(Availability.id == availability_id).first()
        if not availability:
            return False
        
        # Doctors can access their own availability
        if user.id == availability.doctor_id:
            return True
        
        # Admins can access all availability
        if user.role == UserRole.ADMIN:
            return True
        
        # Patients can read availability (but not modify)
        if user.role == UserRole.PATIENT and permission == Permission.AVAILABILITY_READ:
            return True
        
        return False
    
    def _check_audit_access(self, user: User, permission: Permission) -> bool:
        """Check user access to audit logs."""
        # Only admins can access audit logs
        return user.role == UserRole.ADMIN
    
    def _check_system_config_access(self, user: User, permission: Permission) -> bool:
        """Check user access to system configuration."""
        # Only admins can modify system configuration
        return user.role == UserRole.ADMIN
    
    def _check_phi_relationship(self, user: User, resource_type: ResourceType, resource_id: uuid.UUID) -> bool:
        """Check if user has legitimate relationship to PHI."""
        try:
            if resource_type == ResourceType.APPOINTMENT:
                from app.db.models import Appointment
                appointment = self.db.query(Appointment).filter(Appointment.id == resource_id).first()
                if appointment:
                    return user.id == appointment.patient_id or user.id == appointment.doctor_id
            elif resource_type == ResourceType.USER:
                return user.id == resource_id or user.role == UserRole.ADMIN
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking PHI relationship: {e}")
            return False
    
    def _log_access_granted(
        self,
        user: User,
        permission: Permission,
        resource_type: Optional[ResourceType],
        resource_id: Optional[uuid.UUID],
        request: Optional[Request]
    ) -> None:
        """Log granted access."""
        self.audit_logger.log_event(
            event_type="system_access",
            user_id=user.id,
            resource_id=resource_id,
            resource_type=resource_type.value if resource_type else None,
            action=f"permission_granted:{permission.value}",
            request=request,
            success=True
        )
    
    def _log_access_denied(
        self,
        user: User,
        permission: Permission,
        reason: str,
        request: Optional[Request]
    ) -> None:
        """Log denied access."""
        self.audit_logger.log_security_violation(
            violation_type=f"access_denied:{permission.value}",
            user_id=user.id,
            details={"reason": reason},
            request=request
        )


def get_access_control(db: Session) -> AccessControl:
    """Get access control instance."""
    return AccessControl(db)


def require_permission(permission: Permission, resource_type: Optional[ResourceType] = None):
    """Decorator for requiring specific permission."""
    def permission_checker(current_user: User = get_current_user, db: Session = None):
        if not db:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database session required for access control"
            )
        
        access_control = get_access_control(db)
        
        if not access_control.check_permission(current_user, permission, resource_type):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions: {permission.value}"
            )
        
        return current_user
    
    return permission_checker


def require_phi_access(resource_type: ResourceType, action: str = "read"):
    """Decorator for requiring PHI access."""
    def phi_access_checker(current_user: User = get_current_user, db: Session = None):
        if not db:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database session required for access control"
            )
        
        access_control = get_access_control(db)
        
        # Note: This is a simplified check. In practice, you'd need the resource_id
        # which would need to be passed as a parameter to the decorated function
        permission = Permission.PHI_READ if action == "read" else Permission.PHI_WRITE
        
        if not access_control.check_permission(current_user, permission, resource_type):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient PHI access permissions: {action}"
            )
        
        return current_user
    
    return phi_access_checker
