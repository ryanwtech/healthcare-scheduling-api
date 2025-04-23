"""Integration tests for authentication API endpoints."""

import pytest
from fastapi import status

from tests.utils.assertions import TestAssertions
from tests.utils.test_data import SampleData, TestDataFactory


@pytest.mark.integration
@pytest.mark.auth
class TestAuthEndpoints:
    """Integration tests for authentication endpoints."""
    
    def test_login_success(self, test_client, admin_user):
        """Test successful login with valid credentials."""
        login_data = SampleData.ADMIN_USER
        
        response = test_client.post(
            "/api/v1/auth/token",
            data=login_data
        )
        
        TestAssertions.assert_success_response(response, status.HTTP_200_OK)
        
        response_data = response.json()
        TestAssertions.assert_token_response(response_data)
        TestAssertions.assert_user_data(response_data["user"], login_data)
    
    def test_login_json_endpoint(self, test_client, admin_user):
        """Test login using JSON endpoint."""
        login_data = {
            "email": SampleData.ADMIN_USER["email"],
            "password": SampleData.ADMIN_USER["password"]
        }
        
        response = test_client.post(
            "/api/v1/auth/login",
            json=login_data
        )
        
        TestAssertions.assert_success_response(response, status.HTTP_200_OK)
        
        response_data = response.json()
        TestAssertions.assert_token_response(response_data)
    
    def test_login_invalid_credentials(self, test_client):
        """Test login with invalid credentials."""
        login_data = {
            "username": "nonexistent@example.com",
            "password": "wrongpassword"
        }
        
        response = test_client.post(
            "/api/v1/auth/token",
            data=login_data
        )
        
        TestAssertions.assert_error_response(response, status.HTTP_401_UNAUTHORIZED)
    
    def test_login_inactive_user(self, test_client, temp_db):
        """Test login with inactive user."""
        # Create inactive user
        from app.core.security import get_password_hash
        from app.db.models import User, UserRole
        from datetime import datetime, UTC
        import uuid
        
        inactive_user = User(
            id=uuid.uuid4(),
            email="inactive@example.com",
            hashed_password=get_password_hash("password123"),
            full_name="Inactive User",
            role=UserRole.PATIENT,
            is_active=False,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        temp_db.add(inactive_user)
        temp_db.commit()
        
        login_data = {
            "username": "inactive@example.com",
            "password": "password123"
        }
        
        response = test_client.post(
            "/api/v1/auth/token",
            data=login_data
        )
        
        TestAssertions.assert_error_response(response, status.HTTP_401_UNAUTHORIZED)
    
    def test_get_current_user_success(self, test_client, auth_headers_admin):
        """Test getting current user information."""
        response = test_client.get(
            "/api/v1/users/me",
            headers=auth_headers_admin
        )
        
        TestAssertions.assert_success_response(response)
        
        response_data = response.json()
        assert "id" in response_data
        assert "email" in response_data
        assert "full_name" in response_data
        assert "role" in response_data
        assert "is_active" in response_data
    
    def test_get_current_user_unauthorized(self, test_client):
        """Test getting current user without authentication."""
        response = test_client.get("/api/v1/users/me")
        
        TestAssertions.assert_unauthorized(response)
    
    def test_get_current_user_invalid_token(self, test_client):
        """Test getting current user with invalid token."""
        headers = {"Authorization": "Bearer invalid_token"}
        
        response = test_client.get(
            "/api/v1/users/me",
            headers=headers
        )
        
        TestAssertions.assert_unauthorized(response)
    
    def test_admin_create_user_success(self, test_client, auth_headers_admin):
        """Test admin creating a new user."""
        user_data = TestDataFactory.create_user_data(
            email="newuser@example.com",
            full_name="New User",
            role="patient"
        )
        
        response = test_client.post(
            "/api/v1/auth/signup",
            json=user_data,
            headers=auth_headers_admin
        )
        
        TestAssertions.assert_success_response(response, status.HTTP_201_CREATED)
        
        response_data = response.json()
        TestAssertions.assert_user_data(response_data, user_data)
    
    def test_admin_create_doctor_success(self, test_client, auth_headers_admin):
        """Test admin creating a doctor user."""
        user_data = TestDataFactory.create_user_data(
            email="newdoctor@example.com",
            full_name="Dr. New Doctor",
            role="doctor"
        )
        
        response = test_client.post(
            "/api/v1/auth/signup",
            json=user_data,
            headers=auth_headers_admin
        )
        
        TestAssertions.assert_success_response(response, status.HTTP_201_CREATED)
        
        response_data = response.json()
        TestAssertions.assert_user_data(response_data, user_data)
    
    def test_non_admin_cannot_create_doctor(self, test_client, auth_headers_patient):
        """Test that non-admin users cannot create doctor accounts."""
        user_data = TestDataFactory.create_user_data(
            email="newdoctor@example.com",
            full_name="Dr. New Doctor",
            role="doctor"
        )
        
        response = test_client.post(
            "/api/v1/auth/signup",
            json=user_data,
            headers=auth_headers_patient
        )
        
        TestAssertions.assert_forbidden(response)
    
    def test_patient_self_registration_success(self, test_client):
        """Test patient self-registration."""
        user_data = TestDataFactory.create_user_data(
            email="newpatient@example.com",
            full_name="New Patient"
        )
        
        response = test_client.post(
            "/api/v1/auth/signup/patient",
            json=user_data
        )
        
        TestAssertions.assert_success_response(response, status.HTTP_201_CREATED)
        
        response_data = response.json()
        # Role should be forced to patient
        assert response_data["role"] == "patient"
        TestAssertions.assert_user_data(response_data, user_data)
    
    def test_duplicate_email_signup_fails(self, test_client, auth_headers_admin, admin_user):
        """Test that signup with duplicate email fails."""
        user_data = TestDataFactory.create_user_data(
            email=admin_user.email,  # Use existing email
            full_name="Duplicate User"
        )
        
        response = test_client.post(
            "/api/v1/auth/signup",
            json=user_data,
            headers=auth_headers_admin
        )
        
        TestAssertions.assert_error_response(response, status.HTTP_400_BAD_REQUEST)
    
    def test_invalid_email_format(self, test_client, auth_headers_admin):
        """Test signup with invalid email format."""
        user_data = TestDataFactory.create_user_data(
            email="invalid-email-format",
            full_name="Invalid Email User"
        )
        
        response = test_client.post(
            "/api/v1/auth/signup",
            json=user_data,
            headers=auth_headers_admin
        )
        
        TestAssertions.assert_validation_error(response)
    
    def test_short_password_validation(self, test_client, auth_headers_admin):
        """Test signup with password too short."""
        user_data = TestDataFactory.create_user_data(
            email="shortpass@example.com",
            full_name="Short Password User"
        )
        user_data["password"] = "123"  # Too short
        
        response = test_client.post(
            "/api/v1/auth/signup",
            json=user_data,
            headers=auth_headers_admin
        )
        
        TestAssertions.assert_validation_error(response)
    
    def test_token_contains_required_claims(self, test_client, admin_user):
        """Test that JWT token contains required claims."""
        login_data = SampleData.ADMIN_USER
        
        response = test_client.post(
            "/api/v1/auth/token",
            data=login_data
        )
        
        TestAssertions.assert_success_response(response)
        
        response_data = response.json()
        token = response_data["access_token"]
        
        # Decode token to verify claims
        from app.core.security import verify_token
        token_data = verify_token(token)
        
        assert token_data.user_id == str(admin_user.id)
        assert token_data.email == admin_user.email
        assert token_data.role == admin_user.role.value
        assert token_data.exp is not None
    
    def test_token_expiration_handling(self, test_client, admin_user):
        """Test token expiration handling."""
        login_data = SampleData.ADMIN_USER
        
        response = test_client.post(
            "/api/v1/auth/token",
            data=login_data
        )
        
        TestAssertions.assert_success_response(response)
        
        response_data = response.json()
        assert "expires_in" in response_data
        assert response_data["expires_in"] > 0
    
    def test_concurrent_login_attempts(self, test_client, admin_user):
        """Test handling of concurrent login attempts."""
        import threading
        import time
        
        results = []
        
        def login_attempt():
            login_data = SampleData.ADMIN_USER
            response = test_client.post(
                "/api/v1/auth/token",
                data=login_data
            )
            results.append(response.status_code)
        
        # Start multiple concurrent login attempts
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=login_attempt)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All attempts should succeed (no rate limiting on login in current implementation)
        assert all(status_code == 200 for status_code in results)
    
    def test_login_with_missing_credentials(self, test_client):
        """Test login with missing credentials."""
        response = test_client.post("/api/v1/auth/token")
        
        TestAssertions.assert_validation_error(response)
    
    def test_login_with_empty_credentials(self, test_client):
        """Test login with empty credentials."""
        login_data = {
            "username": "",
            "password": ""
        }
        
        response = test_client.post(
            "/api/v1/auth/token",
            data=login_data
        )
        
        TestAssertions.assert_error_response(response, status.HTTP_401_UNAUTHORIZED)
