"""Secure session management for HIPAA compliance."""

import uuid
from datetime import datetime, timedelta, UTC
from typing import Dict, Optional, Set

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import create_access_token, verify_token
from app.db.models import User
from app.security.audit import AuditLogger, get_audit_logger

logger = get_logger(__name__)


class SessionManager:
    """Secure session management for HIPAA compliance."""
    
    def __init__(self, db: Session):
        self.db = db
        self.audit_logger = get_audit_logger(db)
        
        # In-memory session store (in production, use Redis or database)
        self.active_sessions: Dict[str, SessionInfo] = {}
        
        # Session configuration
        self.max_sessions_per_user = 5
        self.session_timeout_minutes = 30
        self.idle_timeout_minutes = 15
    
    def create_session(
        self,
        user: User,
        request: Optional[Request] = None,
        device_info: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Create a new secure session.
        
        Args:
            user: User for whom to create session
            request: FastAPI request object
            device_info: Device information for session tracking
            
        Returns:
            Session token
        """
        try:
            # Check session limits
            self._enforce_session_limits(user.id)
            
            # Create session token
            session_token = self._generate_session_token()
            
            # Extract session metadata
            ip_address = self._get_client_ip(request) if request else "unknown"
            user_agent = request.headers.get("user-agent", "") if request else ""
            
            # Create session info
            session_info = SessionInfo(
                session_id=str(uuid.uuid4()),
                user_id=user.id,
                token=session_token,
                created_at=datetime.now(UTC),
                last_activity=datetime.now(UTC),
                ip_address=ip_address,
                user_agent=user_agent,
                device_info=device_info or {},
                is_active=True
            )
            
            # Store session
            self.active_sessions[session_token] = session_info
            
            # Log session creation
            self.audit_logger.log_event(
                event_type="login_success",
                user_id=user.id,
                action="session_created",
                details={
                    "session_id": session_info.session_id,
                    "ip_address": ip_address,
                    "user_agent": user_agent,
                    "device_info": device_info
                },
                request=request,
                success=True
            )
            
            logger.info(f"Created session for user {user.id}: {session_info.session_id}")
            return session_token
            
        except Exception as e:
            logger.error(f"Failed to create session for user {user.id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create session"
            )
    
    def validate_session(self, token: str, request: Optional[Request] = None) -> Optional[SessionInfo]:
        """
        Validate session token.
        
        Args:
            token: Session token to validate
            request: FastAPI request object
            
        Returns:
            SessionInfo if valid, None otherwise
        """
        try:
            # Check if session exists
            if token not in self.active_sessions:
                self._log_invalid_session(token, "Session not found", request)
                return None
            
            session_info = self.active_sessions[token]
            
            # Check if session is active
            if not session_info.is_active:
                self._log_invalid_session(token, "Session inactive", request)
                return None
            
            # Check session timeout
            if self._is_session_expired(session_info):
                self._log_invalid_session(token, "Session expired", request)
                self._invalidate_session(token)
                return None
            
            # Check idle timeout
            if self._is_session_idle(session_info):
                self._log_invalid_session(token, "Session idle timeout", request)
                self._invalidate_session(token)
                return None
            
            # Update last activity
            session_info.last_activity = datetime.now(UTC)
            
            # Log session validation
            self.audit_logger.log_event(
                event_type="system_access",
                user_id=session_info.user_id,
                action="session_validated",
                details={
                    "session_id": session_info.session_id,
                    "ip_address": session_info.ip_address
                },
                request=request,
                success=True
            )
            
            return session_info
            
        except Exception as e:
            logger.error(f"Failed to validate session {token}: {e}")
            self._log_invalid_session(token, f"Validation error: {e}", request)
            return None
    
    def invalidate_session(self, token: str, request: Optional[Request] = None) -> bool:
        """
        Invalidate a session.
        
        Args:
            token: Session token to invalidate
            request: FastAPI request object
            
        Returns:
            True if session was invalidated, False otherwise
        """
        try:
            if token in self.active_sessions:
                session_info = self.active_sessions[token]
                
                # Log session invalidation
                self.audit_logger.log_event(
                    event_type="logout",
                    user_id=session_info.user_id,
                    action="session_invalidated",
                    details={
                        "session_id": session_info.session_id,
                        "ip_address": session_info.ip_address
                    },
                    request=request,
                    success=True
                )
                
                # Remove session
                del self.active_sessions[token]
                
                logger.info(f"Invalidated session {session_info.session_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to invalidate session {token}: {e}")
            return False
    
    def invalidate_user_sessions(self, user_id: uuid.UUID, request: Optional[Request] = None) -> int:
        """
        Invalidate all sessions for a user.
        
        Args:
            user_id: User ID whose sessions to invalidate
            request: FastAPI request object
            
        Returns:
            Number of sessions invalidated
        """
        try:
            sessions_to_remove = []
            
            for token, session_info in self.active_sessions.items():
                if session_info.user_id == user_id:
                    sessions_to_remove.append(token)
            
            for token in sessions_to_remove:
                self.invalidate_session(token, request)
            
            logger.info(f"Invalidated {len(sessions_to_remove)} sessions for user {user_id}")
            return len(sessions_to_remove)
            
        except Exception as e:
            logger.error(f"Failed to invalidate sessions for user {user_id}: {e}")
            return 0
    
    def refresh_session(self, token: str, request: Optional[Request] = None) -> Optional[str]:
        """
        Refresh session token.
        
        Args:
            token: Current session token
            request: FastAPI request object
            
        Returns:
            New session token if refresh successful, None otherwise
        """
        try:
            session_info = self.validate_session(token, request)
            if not session_info:
                return None
            
            # Create new token
            new_token = self._generate_session_token()
            
            # Update session info
            old_session_id = session_info.session_id
            session_info.token = new_token
            session_info.session_id = str(uuid.uuid4())
            session_info.last_activity = datetime.now(UTC)
            
            # Update session store
            self.active_sessions[new_token] = session_info
            del self.active_sessions[token]
            
            # Log token refresh
            self.audit_logger.log_event(
                event_type="token_refresh",
                user_id=session_info.user_id,
                action="session_refreshed",
                details={
                    "old_session_id": old_session_id,
                    "new_session_id": session_info.session_id,
                    "ip_address": session_info.ip_address
                },
                request=request,
                success=True
            )
            
            logger.info(f"Refreshed session {old_session_id} -> {session_info.session_id}")
            return new_token
            
        except Exception as e:
            logger.error(f"Failed to refresh session {token}: {e}")
            return None
    
    def get_user_sessions(self, user_id: uuid.UUID) -> list[SessionInfo]:
        """Get all active sessions for a user."""
        return [
            session_info for session_info in self.active_sessions.values()
            if session_info.user_id == user_id and session_info.is_active
        ]
    
    def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions."""
        try:
            expired_tokens = []
            
            for token, session_info in self.active_sessions.items():
                if self._is_session_expired(session_info) or self._is_session_idle(session_info):
                    expired_tokens.append(token)
            
            for token in expired_tokens:
                self._invalidate_session(token)
            
            logger.info(f"Cleaned up {len(expired_tokens)} expired sessions")
            return len(expired_tokens)
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired sessions: {e}")
            return 0
    
    def _enforce_session_limits(self, user_id: uuid.UUID) -> None:
        """Enforce session limits per user."""
        user_sessions = self.get_user_sessions(user_id)
        
        if len(user_sessions) >= self.max_sessions_per_user:
            # Invalidate oldest session
            oldest_session = min(user_sessions, key=lambda s: s.created_at)
            self._invalidate_session(oldest_session.token)
            
            logger.info(f"Enforced session limit for user {user_id}, invalidated oldest session")
    
    def _generate_session_token(self) -> str:
        """Generate a secure session token."""
        return str(uuid.uuid4())
    
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
    
    def _is_session_expired(self, session_info: 'SessionInfo') -> bool:
        """Check if session has expired."""
        expiry_time = session_info.created_at + timedelta(minutes=self.session_timeout_minutes)
        return datetime.now(UTC) > expiry_time
    
    def _is_session_idle(self, session_info: 'SessionInfo') -> bool:
        """Check if session is idle."""
        idle_time = session_info.last_activity + timedelta(minutes=self.idle_timeout_minutes)
        return datetime.now(UTC) > idle_time
    
    def _invalidate_session(self, token: str) -> None:
        """Internal method to invalidate session without logging."""
        if token in self.active_sessions:
            del self.active_sessions[token]
    
    def _log_invalid_session(self, token: str, reason: str, request: Optional[Request] = None) -> None:
        """Log invalid session attempt."""
        self.audit_logger.log_security_violation(
            violation_type="invalid_session",
            details={
                "token": token[:8] + "...",  # Only log first 8 chars
                "reason": reason,
                "ip_address": self._get_client_ip(request) if request else "unknown"
            },
            request=request
        )


class SessionInfo:
    """Session information container."""
    
    def __init__(
        self,
        session_id: str,
        user_id: uuid.UUID,
        token: str,
        created_at: datetime,
        last_activity: datetime,
        ip_address: str,
        user_agent: str,
        device_info: Dict[str, str],
        is_active: bool = True
    ):
        self.session_id = session_id
        self.user_id = user_id
        self.token = token
        self.created_at = created_at
        self.last_activity = last_activity
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.device_info = device_info
        self.is_active = is_active


def get_session_manager(db: Session) -> SessionManager:
    """Get session manager instance."""
    return SessionManager(db)
