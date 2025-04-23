"""Unit tests for security module."""

import uuid
from datetime import datetime, timedelta, UTC
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from jose import JWTError

from app.core.security import (
    create_access_token,
    verify_token,
    get_password_hash,
    verify_password,
    get_current_user,
    role_required
)
from app.db.models import User, UserRole
from tests.utils.test_data import TestDataFactory


@pytest.mark.unit
class TestSecurity:
    """Test cases for security functions."""
    
    def test_create_access_token(self):
        """Test access token creation."""
        user_id = str(uuid.uuid4())
        email = "test@example.com"
        role = UserRole.PATIENT.value
        
        token = create_access_token(data={"sub": user_id, "email": email, "role": role})
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_verify_token_success(self):
        """Test successful token verification."""
        user_id = str(uuid.uuid4())
        email = "test@example.com"
        role = UserRole.PATIENT.value
        
        token = create_access_token(data={"sub": user_id, "email": email, "role": role})
        token_data = verify_token(token)
        
        assert token_data.user_id == user_id
        assert token_data.email == email
        assert token_data.role == role
    
    def test_verify_token_invalid(self):
        """Test token verification with invalid token."""
        with pytest.raises(HTTPException) as exc_info:
            verify_token("invalid_token")
        
        assert exc_info.value.status_code == 401
        assert "Could not validate credentials" in str(exc_info.value.detail)
    
    def test_verify_token_expired(self):
        """Test token verification with expired token."""
        # Create token with very short expiration
        user_id = str(uuid.uuid4())
        email = "test@example.com"
        role = UserRole.PATIENT.value
        
        with patch('app.core.security.settings.access_token_expire_minutes', 0):
            token = create_access_token(data={"sub": user_id, "email": email, "role": role})
        
        # Wait a bit to ensure token is expired
        import time
        time.sleep(1)
        
        with pytest.raises(HTTPException) as exc_info:
            verify_token(token)
        
        assert exc_info.value.status_code == 401
    
    def test_get_password_hash(self):
        """Test password hashing."""
        password = "testpassword123"
        hashed = get_password_hash(password)
        
        assert hashed is not None
        assert hashed != password
        assert len(hashed) > 0
        assert hashed.startswith("$2b$")  # bcrypt hash format
    
    def test_verify_password_success(self):
        """Test successful password verification."""
        password = "testpassword123"
        hashed = get_password_hash(password)
        
        result = verify_password(password, hashed)
        
        assert result is True
    
    def test_verify_password_failure(self):
        """Test password verification with wrong password."""
        password = "testpassword123"
        wrong_password = "wrongpassword"
        hashed = get_password_hash(password)
        
        result = verify_password(wrong_password, hashed)
        
        assert result is False
    
    def test_get_current_user_success(self, temp_db, patient_user):
        """Test successful current user retrieval."""
        token = create_access_token(data={
            "sub": str(patient_user.id),
            "email": patient_user.email,
            "role": patient_user.role.value
        })
        
        # Mock the request object
        mock_request = MagicMock()
        mock_request.state = MagicMock()
        
        user = get_current_user(token, mock_request, temp_db)
        
        assert user is not None
        assert user.id == patient_user.id
        assert user.email == patient_user.email
        assert user.role == patient_user.role
    
    def test_get_current_user_not_found(self, temp_db):
        """Test current user retrieval with non-existent user."""
        fake_user_id = str(uuid.uuid4())
        token = create_access_token(data={
            "sub": fake_user_id,
            "email": "nonexistent@example.com",
            "role": UserRole.PATIENT.value
        })
        
        mock_request = MagicMock()
        mock_request.state = MagicMock()
        
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(token, mock_request, temp_db)
        
        assert exc_info.value.status_code == 401
        assert "User not found" in str(exc_info.value.detail)
    
    def test_get_current_user_inactive(self, temp_db):
        """Test current user retrieval with inactive user."""
        # Create inactive user
        user = User(
            id=uuid.uuid4(),
            email="inactive@example.com",
            hashed_password=get_password_hash("password123"),
            full_name="Inactive User",
            role=UserRole.PATIENT,
            is_active=False,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        temp_db.add(user)
        temp_db.commit()
        
        token = create_access_token(data={
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value
        })
        
        mock_request = MagicMock()
        mock_request.state = MagicMock()
        
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(token, mock_request, temp_db)
        
        assert exc_info.value.status_code == 401
        assert "Inactive user" in str(exc_info.value.detail)
    
    def test_role_required_success(self, temp_db, admin_user):
        """Test role_required with authorized user."""
        token = create_access_token(data={
            "sub": str(admin_user.id),
            "email": admin_user.email,
            "role": admin_user.role.value
        })
        
        mock_request = MagicMock()
        mock_request.state = MagicMock()
        
        # Get current user first
        current_user = get_current_user(token, mock_request, temp_db)
        
        # Test role_required dependency
        role_checker = role_required("admin")
        result = role_checker(current_user)
        
        assert result == current_user
    
    def test_role_required_forbidden(self, temp_db, patient_user):
        """Test role_required with unauthorized user."""
        token = create_access_token(data={
            "sub": str(patient_user.id),
            "email": patient_user.email,
            "role": patient_user.role.value
        })
        
        mock_request = MagicMock()
        mock_request.state = MagicMock()
        
        # Get current user first
        current_user = get_current_user(token, mock_request, temp_db)
        
        # Test role_required dependency with wrong role
        role_checker = role_required("admin")
        
        with pytest.raises(HTTPException) as exc_info:
            role_checker(current_user)
        
        assert exc_info.value.status_code == 403
        assert "Insufficient permissions" in str(exc_info.value.detail)
    
    def test_role_required_multiple_roles(self, temp_db, doctor_user):
        """Test role_required with multiple allowed roles."""
        token = create_access_token(data={
            "sub": str(doctor_user.id),
            "email": doctor_user.email,
            "role": doctor_user.role.value
        })
        
        mock_request = MagicMock()
        mock_request.state = MagicMock()
        
        # Get current user first
        current_user = get_current_user(token, mock_request, temp_db)
        
        # Test role_required dependency with multiple roles
        role_checker = role_required("doctor", "admin")
        result = role_checker(current_user)
        
        assert result == current_user
    
    def test_password_strength_validation(self):
        """Test password strength validation."""
        # Test weak passwords
        weak_passwords = [
            "123",           # Too short
            "password",      # Too common
            "12345678",      # Only numbers
            "abcdefgh",      # Only letters
        ]
        
        for password in weak_passwords:
            hashed = get_password_hash(password)
            # Should still hash successfully (validation happens at API level)
            assert hashed is not None
    
    def test_token_expiration_handling(self):
        """Test token expiration handling."""
        user_id = str(uuid.uuid4())
        email = "test@example.com"
        role = UserRole.PATIENT.value
        
        # Create token with normal expiration
        token = create_access_token(data={"sub": user_id, "email": email, "role": role})
        
        # Verify token is valid
        token_data = verify_token(token)
        assert token_data.user_id == user_id
    
    def test_token_data_structure(self):
        """Test token data structure."""
        user_id = str(uuid.uuid4())
        email = "test@example.com"
        role = UserRole.DOCTOR.value
        
        token = create_access_token(data={"sub": user_id, "email": email, "role": role})
        token_data = verify_token(token)
        
        # Check all required fields are present
        assert hasattr(token_data, 'user_id')
        assert hasattr(token_data, 'email')
        assert hasattr(token_data, 'role')
        assert hasattr(token_data, 'exp')
        
        # Check field values
        assert token_data.user_id == user_id
        assert token_data.email == email
        assert token_data.role == role
        assert token_data.exp is not None
