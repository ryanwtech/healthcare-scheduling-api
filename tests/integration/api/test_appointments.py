"""Integration tests for appointments API endpoints."""

import uuid
from datetime import datetime, timedelta, UTC

import pytest
from fastapi import status

from tests.utils.assertions import TestAssertions
from tests.utils.test_data import TestDataFactory, TestScenarios


@pytest.mark.integration
@pytest.mark.appointments
class TestAppointmentEndpoints:
    """Integration tests for appointment endpoints."""
    
    def test_book_appointment_success(self, test_client, auth_headers_patient, doctor_profile):
        """Test successful appointment booking."""
        appointment_data = TestDataFactory.create_appointment_data(
            doctor_id=str(doctor_profile.id),
            days_ahead=1
        )
        
        response = test_client.post(
            "/api/v1/appointments",
            json=appointment_data,
            headers=auth_headers_patient
        )
        
        TestAssertions.assert_success_response(response, status.HTTP_201_CREATED)
        
        response_data = response.json()
        TestAssertions.assert_appointment_data(response_data, appointment_data)
        TestAssertions.assert_uuid_format(response_data["id"], "Appointment ID")
        TestAssertions.assert_datetime_format(response_data["start_time"], "Start time")
        TestAssertions.assert_datetime_format(response_data["end_time"], "End time")
        TestAssertions.assert_time_range_valid(response_data["start_time"], response_data["end_time"])
        TestAssertions.assert_future_time(response_data["start_time"], "Start time")
    
    def test_book_appointment_outside_availability(self, test_client, auth_headers_patient, doctor_profile):
        """Test booking appointment outside doctor's availability."""
        # Create availability for tomorrow 9-12
        from app.db.models import Availability
        from app.db.base import get_db
        
        db = next(get_db())
        availability = Availability(
            id=uuid.uuid4(),
            doctor_id=doctor_profile.id,
            start_time=datetime.now(UTC) + timedelta(days=1, hours=9),
            end_time=datetime.now(UTC) + timedelta(days=1, hours=12),
            created_at=datetime.now(UTC)
        )
        db.add(availability)
        db.commit()
        
        # Try to book appointment outside availability (2-4 PM)
        appointment_data = TestDataFactory.create_appointment_data(
            doctor_id=str(doctor_profile.id),
            start_time=datetime.now(UTC) + timedelta(days=1, hours=14),
            end_time=datetime.now(UTC) + timedelta(days=1, hours=16)
        )
        
        response = test_client.post(
            "/api/v1/appointments",
            json=appointment_data,
            headers=auth_headers_patient
        )
        
        TestAssertions.assert_error_response(response, status.HTTP_400_BAD_REQUEST)
    
    def test_book_appointment_overlap_prevention(self, test_client, auth_headers_patient, sample_appointment):
        """Test that overlapping appointments are prevented."""
        # Try to book appointment that overlaps with existing one
        appointment_data = TestDataFactory.create_appointment_data(
            doctor_id=str(sample_appointment.doctor_id),
            start_time=sample_appointment.start_time + timedelta(minutes=15),
            end_time=sample_appointment.end_time + timedelta(minutes=15)
        )
        
        response = test_client.post(
            "/api/v1/appointments",
            json=appointment_data,
            headers=auth_headers_patient
        )
        
        TestAssertions.assert_error_response(response, status.HTTP_400_BAD_REQUEST)
    
    def test_book_appointment_past_time(self, test_client, auth_headers_patient, doctor_profile):
        """Test booking appointment in the past."""
        appointment_data = TestDataFactory.create_appointment_data(
            doctor_id=str(doctor_profile.id),
            start_time=TestScenarios.PAST_TIME,
            end_time=TestScenarios.PAST_TIME + timedelta(minutes=30)
        )
        
        response = test_client.post(
            "/api/v1/appointments",
            json=appointment_data,
            headers=auth_headers_patient
        )
        
        TestAssertions.assert_error_response(response, status.HTTP_400_BAD_REQUEST)
    
    def test_book_appointment_invalid_time_range(self, test_client, auth_headers_patient, doctor_profile):
        """Test booking appointment with invalid time range."""
        appointment_data = TestDataFactory.create_appointment_data(
            doctor_id=str(doctor_profile.id),
            start_time=datetime.now(UTC) + timedelta(days=1, hours=10),
            end_time=datetime.now(UTC) + timedelta(days=1, hours=9)  # End before start
        )
        
        response = test_client.post(
            "/api/v1/appointments",
            json=appointment_data,
            headers=auth_headers_patient
        )
        
        TestAssertions.assert_validation_error(response)
    
    def test_book_appointment_unauthorized(self, test_client, doctor_profile):
        """Test booking appointment without authentication."""
        appointment_data = TestDataFactory.create_appointment_data(
            doctor_id=str(doctor_profile.id)
        )
        
        response = test_client.post(
            "/api/v1/appointments",
            json=appointment_data
        )
        
        TestAssertions.assert_unauthorized(response)
    
    def test_book_appointment_wrong_role(self, test_client, auth_headers_doctor, doctor_profile):
        """Test that doctors cannot book appointments for themselves."""
        appointment_data = TestDataFactory.create_appointment_data(
            doctor_id=str(doctor_profile.id)
        )
        
        response = test_client.post(
            "/api/v1/appointments",
            json=appointment_data,
            headers=auth_headers_doctor
        )
        
        TestAssertions.assert_forbidden(response)
    
    def test_list_appointments_as_patient(self, test_client, auth_headers_patient, sample_appointment):
        """Test listing appointments as patient."""
        response = test_client.get(
            "/api/v1/appointments",
            headers=auth_headers_patient
        )
        
        TestAssertions.assert_success_response(response)
        
        response_data = response.json()
        TestAssertions.assert_paginated_response(response_data, expected_items=1)
        
        appointment = response_data["items"][0]
        assert appointment["id"] == str(sample_appointment.id)
        assert appointment["patient_id"] == str(sample_appointment.patient_id)
    
    def test_list_appointments_as_doctor(self, test_client, auth_headers_doctor, sample_appointment):
        """Test listing appointments as doctor."""
        response = test_client.get(
            "/api/v1/appointments",
            headers=auth_headers_doctor
        )
        
        TestAssertions.assert_success_response(response)
        
        response_data = response.json()
        TestAssertions.assert_paginated_response(response_data, expected_items=1)
        
        appointment = response_data["items"][0]
        assert appointment["id"] == str(sample_appointment.id)
        assert appointment["doctor_id"] == str(sample_appointment.doctor_id)
    
    def test_list_appointments_as_admin(self, test_client, auth_headers_admin, sample_appointment):
        """Test listing appointments as admin."""
        response = test_client.get(
            "/api/v1/appointments",
            headers=auth_headers_admin
        )
        
        TestAssertions.assert_success_response(response)
        
        response_data = response.json()
        TestAssertions.assert_paginated_response(response_data, expected_items=1)
    
    def test_list_appointments_with_filters(self, test_client, auth_headers_patient, sample_appointment):
        """Test listing appointments with filters."""
        response = test_client.get(
            "/api/v1/appointments?status=scheduled&page=1&size=10",
            headers=auth_headers_patient
        )
        
        TestAssertions.assert_success_response(response)
        
        response_data = response.json()
        TestAssertions.assert_paginated_response(response_data)
        
        # Check pagination parameters
        assert response_data["page"] == 1
        assert response_data["size"] == 10
    
    def test_get_appointment_details(self, test_client, auth_headers_patient, sample_appointment):
        """Test getting appointment details."""
        response = test_client.get(
            f"/api/v1/appointments/{sample_appointment.id}",
            headers=auth_headers_patient
        )
        
        TestAssertions.assert_success_response(response)
        
        response_data = response.json()
        assert response_data["id"] == str(sample_appointment.id)
        assert response_data["patient_id"] == str(sample_appointment.patient_id)
        assert response_data["doctor_id"] == str(sample_appointment.doctor_id)
    
    def test_get_appointment_not_found(self, test_client, auth_headers_patient):
        """Test getting non-existent appointment."""
        fake_appointment_id = str(uuid.uuid4())
        
        response = test_client.get(
            f"/api/v1/appointments/{fake_appointment_id}",
            headers=auth_headers_patient
        )
        
        TestAssertions.assert_not_found(response)
    
    def test_cancel_appointment_as_patient(self, test_client, auth_headers_patient, sample_appointment):
        """Test cancelling appointment as patient."""
        cancel_data = {"reason": "Patient request"}
        
        response = test_client.post(
            f"/api/v1/appointments/{sample_appointment.id}/cancel",
            json=cancel_data,
            headers=auth_headers_patient
        )
        
        TestAssertions.assert_success_response(response)
        
        response_data = response.json()
        assert response_data["status"] == "cancelled"
        assert response_data["notes"] == "Patient request"
    
    def test_cancel_appointment_as_doctor(self, test_client, auth_headers_doctor, sample_appointment):
        """Test cancelling appointment as doctor."""
        cancel_data = {"reason": "Doctor request"}
        
        response = test_client.post(
            f"/api/v1/appointments/{sample_appointment.id}/cancel",
            json=cancel_data,
            headers=auth_headers_doctor
        )
        
        TestAssertions.assert_success_response(response)
        
        response_data = response.json()
        assert response_data["status"] == "cancelled"
    
    def test_cancel_appointment_unauthorized(self, test_client, sample_appointment):
        """Test cancelling appointment without authentication."""
        cancel_data = {"reason": "Test"}
        
        response = test_client.post(
            f"/api/v1/appointments/{sample_appointment.id}/cancel",
            json=cancel_data
        )
        
        TestAssertions.assert_unauthorized(response)
    
    def test_cancel_appointment_wrong_user(self, test_client, auth_headers_patient, sample_appointment):
        """Test cancelling appointment by wrong user."""
        # Create another patient
        from app.db.models import User, UserRole
        from app.core.security import get_password_hash
        from app.db.base import get_db
        
        db = next(get_db())
        other_patient = User(
            id=uuid.uuid4(),
            email="other@example.com",
            hashed_password=get_password_hash("password123"),
            full_name="Other Patient",
            role=UserRole.PATIENT,
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        db.add(other_patient)
        db.commit()
        
        # Create auth headers for other patient
        from app.core.security import create_access_token
        token = create_access_token(data={
            "sub": str(other_patient.id),
            "email": other_patient.email,
            "role": other_patient.role.value
        })
        other_auth_headers = {"Authorization": f"Bearer {token}"}
        
        cancel_data = {"reason": "Test"}
        
        response = test_client.post(
            f"/api/v1/appointments/{sample_appointment.id}/cancel",
            json=cancel_data,
            headers=other_auth_headers
        )
        
        TestAssertions.assert_forbidden(response)
    
    def test_appointment_statistics(self, test_client, auth_headers_admin, sample_appointment):
        """Test getting appointment statistics."""
        response = test_client.get(
            "/api/v1/appointments/statistics",
            headers=auth_headers_admin
        )
        
        TestAssertions.assert_success_response(response)
        
        response_data = response.json()
        assert "total_appointments" in response_data
        assert "scheduled_appointments" in response_data
        assert "cancelled_appointments" in response_data
        assert "completed_appointments" in response_data
        assert response_data["total_appointments"] >= 1
    
    def test_appointment_statistics_unauthorized(self, test_client, auth_headers_patient):
        """Test getting appointment statistics without admin role."""
        response = test_client.get(
            "/api/v1/appointments/statistics",
            headers=auth_headers_patient
        )
        
        TestAssertions.assert_forbidden(response)
    
    def test_rate_limiting_on_booking(self, test_client, auth_headers_patient, doctor_profile):
        """Test rate limiting on appointment booking."""
        appointment_data = TestDataFactory.create_appointment_data(
            doctor_id=str(doctor_profile.id)
        )
        
        # Make multiple requests quickly
        responses = []
        for i in range(7):  # More than the rate limit of 5
            response = test_client.post(
                "/api/v1/appointments",
                json=appointment_data,
                headers=auth_headers_patient
            )
            responses.append(response)
        
        # Check that some requests are rate limited
        rate_limited_responses = [r for r in responses if r.status_code == 429]
        assert len(rate_limited_responses) > 0
        
        # Check rate limit response format
        if rate_limited_responses:
            rate_limit_response = rate_limited_responses[0]
            response_data = rate_limit_response.json()
            assert "error" in response_data
            assert "retry_after" in response_data["error"]
    
    def test_update_appointment_success(self, test_client, auth_headers_patient, sample_appointment):
        """Test updating appointment."""
        update_data = {
            "notes": "Updated appointment notes"
        }
        
        response = test_client.put(
            f"/api/v1/appointments/{sample_appointment.id}",
            json=update_data,
            headers=auth_headers_patient
        )
        
        TestAssertions.assert_success_response(response)
        
        response_data = response.json()
        assert response_data["notes"] == "Updated appointment notes"
    
    def test_update_appointment_unauthorized(self, test_client, sample_appointment):
        """Test updating appointment without authentication."""
        update_data = {"notes": "Test"}
        
        response = test_client.put(
            f"/api/v1/appointments/{sample_appointment.id}",
            json=update_data
        )
        
        TestAssertions.assert_unauthorized(response)
    
    def test_appointment_workflow_complete(self, test_client, auth_headers_patient, auth_headers_doctor, doctor_profile):
        """Test complete appointment workflow: book -> list -> update -> cancel."""
        # 1. Book appointment
        appointment_data = TestDataFactory.create_appointment_data(
            doctor_id=str(doctor_profile.id)
        )
        
        book_response = test_client.post(
            "/api/v1/appointments",
            json=appointment_data,
            headers=auth_headers_patient
        )
        
        TestAssertions.assert_success_response(book_response, status.HTTP_201_CREATED)
        appointment_id = book_response.json()["id"]
        
        # 2. List appointments
        list_response = test_client.get(
            "/api/v1/appointments",
            headers=auth_headers_patient
        )
        
        TestAssertions.assert_success_response(list_response)
        appointments = list_response.json()["items"]
        assert len(appointments) >= 1
        assert any(apt["id"] == appointment_id for apt in appointments)
        
        # 3. Update appointment
        update_data = {"notes": "Updated notes"}
        update_response = test_client.put(
            f"/api/v1/appointments/{appointment_id}",
            json=update_data,
            headers=auth_headers_patient
        )
        
        TestAssertions.assert_success_response(update_response)
        
        # 4. Cancel appointment
        cancel_data = {"reason": "Patient request"}
        cancel_response = test_client.post(
            f"/api/v1/appointments/{appointment_id}/cancel",
            json=cancel_data,
            headers=auth_headers_patient
        )
        
        TestAssertions.assert_success_response(cancel_response)
        assert cancel_response.json()["status"] == "cancelled"
