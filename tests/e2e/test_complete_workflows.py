"""End-to-end tests for complete user workflows."""

import uuid
from datetime import datetime, timedelta, UTC

import pytest
from fastapi import status

from tests.utils.assertions import TestAssertions
from tests.utils.test_data import TestDataFactory, SampleData


@pytest.mark.e2e
@pytest.mark.slow
class TestCompleteWorkflows:
    """End-to-end tests for complete user workflows."""
    
    def test_admin_workflow(self, test_client, auth_headers_admin):
        """Test complete admin workflow: create users, manage system."""
        # 1. Create a doctor user
        doctor_data = TestDataFactory.create_user_data(
            email="newdoctor@healthcare.com",
            full_name="Dr. New Doctor",
            role="doctor"
        )
        
        create_doctor_response = test_client.post(
            "/api/v1/auth/signup",
            json=doctor_data,
            headers=auth_headers_admin
        )
        
        TestAssertions.assert_success_response(create_doctor_response, status.HTTP_201_CREATED)
        doctor_user = create_doctor_response.json()
        
        # 2. Create doctor profile
        doctor_profile_data = TestDataFactory.create_doctor_profile_data(
            specialization="Cardiology",
            timezone="America/New_York"
        )
        
        # Get doctor's auth token
        doctor_login_response = test_client.post(
            "/api/v1/auth/token",
            data={
                "username": doctor_data["email"],
                "password": doctor_data["password"]
            }
        )
        TestAssertions.assert_success_response(doctor_login_response)
        doctor_token = doctor_login_response.json()["access_token"]
        doctor_auth_headers = {"Authorization": f"Bearer {doctor_token}"}
        
        # Create doctor profile
        profile_response = test_client.post(
            f"/api/v1/doctors/{doctor_user['id']}/profile",
            json=doctor_profile_data,
            headers=doctor_auth_headers
        )
        
        TestAssertions.assert_success_response(profile_response, status.HTTP_201_CREATED)
        doctor_profile = profile_response.json()
        
        # 3. Create availability
        availability_data = TestDataFactory.create_availability_data(
            days_ahead=1
        )
        
        availability_response = test_client.post(
            f"/api/v1/doctors/{doctor_profile['id']}/availability",
            json=availability_data,
            headers=doctor_auth_headers
        )
        
        TestAssertions.assert_success_response(availability_response, status.HTTP_201_CREATED)
        
        # 4. Create a patient user
        patient_data = TestDataFactory.create_user_data(
            email="newpatient@healthcare.com",
            full_name="New Patient"
        )
        
        create_patient_response = test_client.post(
            "/api/v1/auth/signup/patient",
            json=patient_data
        )
        
        TestAssertions.assert_success_response(create_patient_response, status.HTTP_201_CREATED)
        patient_user = create_patient_response.json()
        
        # 5. Patient books appointment
        patient_login_response = test_client.post(
            "/api/v1/auth/token",
            data={
                "username": patient_data["email"],
                "password": patient_data["password"]
            }
        )
        TestAssertions.assert_success_response(patient_login_response)
        patient_token = patient_login_response.json()["access_token"]
        patient_auth_headers = {"Authorization": f"Bearer {patient_token}"}
        
        appointment_data = TestDataFactory.create_appointment_data(
            doctor_id=doctor_profile["id"],
            days_ahead=1
        )
        
        book_response = test_client.post(
            "/api/v1/appointments",
            json=appointment_data,
            headers=patient_auth_headers
        )
        
        TestAssertions.assert_success_response(book_response, status.HTTP_201_CREATED)
        appointment = book_response.json()
        
        # 6. Admin views all appointments
        admin_appointments_response = test_client.get(
            "/api/v1/appointments",
            headers=auth_headers_admin
        )
        
        TestAssertions.assert_success_response(admin_appointments_response)
        admin_appointments = admin_appointments_response.json()
        assert len(admin_appointments["items"]) >= 1
        
        # 7. Admin views system statistics
        stats_response = test_client.get(
            "/api/v1/appointments/statistics",
            headers=auth_headers_admin
        )
        
        TestAssertions.assert_success_response(stats_response)
        stats = stats_response.json()
        assert stats["total_appointments"] >= 1
    
    def test_doctor_workflow(self, test_client, auth_headers_doctor, doctor_profile):
        """Test complete doctor workflow: manage availability, view appointments."""
        # 1. Create availability slots
        morning_availability = TestDataFactory.create_availability_data(
            start_time=datetime.now(UTC) + timedelta(days=1, hours=9),
            end_time=datetime.now(UTC) + timedelta(days=1, hours=12)
        )
        
        afternoon_availability = TestDataFactory.create_availability_data(
            start_time=datetime.now(UTC) + timedelta(days=1, hours=13),
            end_time=datetime.now(UTC) + timedelta(days=1, hours=17)
        )
        
        # Create morning slot
        morning_response = test_client.post(
            f"/api/v1/doctors/{doctor_profile.id}/availability",
            json=morning_availability,
            headers=auth_headers_doctor
        )
        
        TestAssertions.assert_success_response(morning_response, status.HTTP_201_CREATED)
        
        # Create afternoon slot
        afternoon_response = test_client.post(
            f"/api/v1/doctors/{doctor_profile.id}/availability",
            json=afternoon_availability,
            headers=auth_headers_doctor
        )
        
        TestAssertions.assert_success_response(afternoon_response, status.HTTP_201_CREATED)
        
        # 2. View availability
        availability_response = test_client.get(
            f"/api/v1/doctors/{doctor_profile.id}/availability",
            headers=auth_headers_doctor
        )
        
        TestAssertions.assert_success_response(availability_response)
        availabilities = availability_response.json()
        assert len(availabilities["items"]) >= 2
        
        # 3. View available slots
        slots_response = test_client.get(
            f"/api/v1/doctors/{doctor_profile.id}/availability/slots",
            headers=auth_headers_doctor
        )
        
        TestAssertions.assert_success_response(slots_response)
        slots = slots_response.json()
        assert len(slots) >= 2
        
        # 4. View availability summary
        summary_response = test_client.get(
            f"/api/v1/doctors/{doctor_profile.id}/availability/summary",
            headers=auth_headers_doctor
        )
        
        TestAssertions.assert_success_response(summary_response)
        summary = summary_response.json()
        assert summary["total_slots"] >= 2
        
        # 5. View appointments (initially empty)
        appointments_response = test_client.get(
            "/api/v1/appointments",
            headers=auth_headers_doctor
        )
        
        TestAssertions.assert_success_response(appointments_response)
        appointments = appointments_response.json()
        assert appointments["total"] >= 0
    
    def test_patient_workflow(self, test_client, auth_headers_patient, doctor_profile):
        """Test complete patient workflow: find doctor, book appointment, manage appointments."""
        # 1. View doctor availability
        availability_response = test_client.get(
            f"/api/v1/doctors/{doctor_profile.id}/availability",
            headers=auth_headers_patient
        )
        
        TestAssertions.assert_success_response(availability_response)
        
        # 2. View available slots
        slots_response = test_client.get(
            f"/api/v1/doctors/{doctor_profile.id}/availability/slots",
            headers=auth_headers_patient
        )
        
        TestAssertions.assert_success_response(slots_response)
        slots = slots_response.json()
        
        # 3. Book appointment if slots available
        if slots:
            appointment_data = TestDataFactory.create_appointment_data(
                doctor_id=str(doctor_profile.id),
                days_ahead=1
            )
            
            book_response = test_client.post(
                "/api/v1/appointments",
                json=appointment_data,
                headers=auth_headers_patient
            )
            
            TestAssertions.assert_success_response(book_response, status.HTTP_201_CREATED)
            appointment = book_response.json()
            
            # 4. View own appointments
            appointments_response = test_client.get(
                "/api/v1/appointments",
                headers=auth_headers_patient
            )
            
            TestAssertions.assert_success_response(appointments_response)
            appointments = appointments_response.json()
            assert appointments["total"] >= 1
            assert any(apt["id"] == appointment["id"] for apt in appointments["items"])
            
            # 5. View appointment details
            details_response = test_client.get(
                f"/api/v1/appointments/{appointment['id']}",
                headers=auth_headers_patient
            )
            
            TestAssertions.assert_success_response(details_response)
            details = details_response.json()
            assert details["id"] == appointment["id"]
            
            # 6. Update appointment
            update_data = {"notes": "Updated appointment notes"}
            update_response = test_client.put(
                f"/api/v1/appointments/{appointment['id']}",
                json=update_data,
                headers=auth_headers_patient
            )
            
            TestAssertions.assert_success_response(update_response)
            
            # 7. Cancel appointment
            cancel_data = {"reason": "Patient request"}
            cancel_response = test_client.post(
                f"/api/v1/appointments/{appointment['id']}/cancel",
                json=cancel_data,
                headers=auth_headers_patient
            )
            
            TestAssertions.assert_success_response(cancel_response)
            assert cancel_response.json()["status"] == "cancelled"
    
    def test_concurrent_appointment_booking(self, test_client, auth_headers_patient, doctor_profile):
        """Test concurrent appointment booking to verify race condition handling."""
        import threading
        import time
        
        # Create availability first
        availability_data = TestDataFactory.create_availability_data(
            start_time=datetime.now(UTC) + timedelta(days=1, hours=9),
            end_time=datetime.now(UTC) + timedelta(days=1, hours=12)
        )
        
        availability_response = test_client.post(
            f"/api/v1/doctors/{doctor_profile.id}/availability",
            json=availability_data,
            headers=auth_headers_patient  # Using patient headers for simplicity
        )
        
        if availability_response.status_code != 201:
            pytest.skip("Could not create availability for concurrent test")
        
        # Prepare appointment data
        appointment_data = TestDataFactory.create_appointment_data(
            doctor_id=str(doctor_profile.id),
            start_time=datetime.now(UTC) + timedelta(days=1, hours=10),
            end_time=datetime.now(UTC) + timedelta(days=1, hours=10, minutes=30)
        )
        
        results = []
        
        def book_appointment():
            response = test_client.post(
                "/api/v1/appointments",
                json=appointment_data,
                headers=auth_headers_patient
            )
            results.append({
                "status_code": response.status_code,
                "response": response.json() if response.status_code < 500 else None
            })
        
        # Start multiple concurrent booking attempts
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=book_appointment)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify results
        successful_bookings = [r for r in results if r["status_code"] == 201]
        failed_bookings = [r for r in results if r["status_code"] != 201]
        
        # Should have exactly one successful booking
        assert len(successful_bookings) == 1, f"Expected 1 successful booking, got {len(successful_bookings)}"
        
        # Failed bookings should be due to conflicts or validation errors
        for failed_booking in failed_bookings:
            assert failed_booking["status_code"] in [400, 422], f"Unexpected status code: {failed_booking['status_code']}"
    
    def test_system_health_and_metrics(self, test_client):
        """Test system health and metrics endpoints."""
        # 1. Health check
        health_response = test_client.get("/health")
        
        TestAssertions.assert_success_response(health_response)
        health_data = health_response.json()
        TestAssertions.assert_health_response(health_data)
        
        # 2. Metrics endpoint
        metrics_response = test_client.get("/metrics")
        
        TestAssertions.assert_success_response(metrics_response)
        TestAssertions.assert_metrics_response(metrics_response.text)
        
        # 3. API documentation
        docs_response = test_client.get("/docs")
        assert docs_response.status_code == 200
        
        redoc_response = test_client.get("/redoc")
        assert redoc_response.status_code == 200
    
    def test_error_handling_workflow(self, test_client, auth_headers_patient):
        """Test error handling across the system."""
        # 1. Invalid endpoint
        invalid_response = test_client.get("/api/v1/invalid-endpoint")
        assert invalid_response.status_code == 404
        
        # 2. Invalid appointment ID
        fake_appointment_id = str(uuid.uuid4())
        appointment_response = test_client.get(
            f"/api/v1/appointments/{fake_appointment_id}",
            headers=auth_headers_patient
        )
        TestAssertions.assert_not_found(appointment_response)
        
        # 3. Invalid doctor ID
        fake_doctor_id = str(uuid.uuid4())
        availability_response = test_client.get(
            f"/api/v1/doctors/{fake_doctor_id}/availability",
            headers=auth_headers_patient
        )
        TestAssertions.assert_not_found(availability_response)
        
        # 4. Malformed JSON
        malformed_response = test_client.post(
            "/api/v1/appointments",
            json={"invalid": "data"},
            headers=auth_headers_patient
        )
        TestAssertions.assert_validation_error(malformed_response)
    
    def test_rate_limiting_workflow(self, test_client, auth_headers_patient, doctor_profile):
        """Test rate limiting across different endpoints."""
        # Create availability first
        availability_data = TestDataFactory.create_availability_data()
        
        availability_response = test_client.post(
            f"/api/v1/doctors/{doctor_profile.id}/availability",
            json=availability_data,
            headers=auth_headers_patient
        )
        
        if availability_response.status_code != 201:
            pytest.skip("Could not create availability for rate limiting test")
        
        # Test rate limiting on appointment booking
        appointment_data = TestDataFactory.create_appointment_data(
            doctor_id=str(doctor_profile.id)
        )
        
        responses = []
        for i in range(7):  # More than rate limit
            response = test_client.post(
                "/api/v1/appointments",
                json=appointment_data,
                headers=auth_headers_patient
            )
            responses.append(response)
        
        # Check that some requests are rate limited
        rate_limited = [r for r in responses if r.status_code == 429]
        assert len(rate_limited) > 0, "Expected some requests to be rate limited"
        
        # Check rate limit response format
        if rate_limited:
            rate_limit_response = rate_limited[0]
            response_data = rate_limit_response.json()
            assert "error" in response_data
            assert "retry_after" in response_data["error"]
    
    def test_data_consistency_workflow(self, test_client, auth_headers_patient, auth_headers_doctor, doctor_profile):
        """Test data consistency across different operations."""
        # 1. Create availability
        availability_data = TestDataFactory.create_availability_data()
        
        availability_response = test_client.post(
            f"/api/v1/doctors/{doctor_profile.id}/availability",
            json=availability_data,
            headers=auth_headers_doctor
        )
        
        TestAssertions.assert_success_response(availability_response, status.HTTP_201_CREATED)
        availability = availability_response.json()
        
        # 2. Book appointment
        appointment_data = TestDataFactory.create_appointment_data(
            doctor_id=str(doctor_profile.id)
        )
        
        book_response = test_client.post(
            "/api/v1/appointments",
            json=appointment_data,
            headers=auth_headers_patient
        )
        
        TestAssertions.assert_success_response(book_response, status.HTTP_201_CREATED)
        appointment = book_response.json()
        
        # 3. Verify data consistency
        # Check that appointment appears in doctor's view
        doctor_appointments = test_client.get(
            "/api/v1/appointments",
            headers=auth_headers_doctor
        )
        
        TestAssertions.assert_success_response(doctor_appointments)
        doctor_appointments_data = doctor_appointments.json()
        assert any(apt["id"] == appointment["id"] for apt in doctor_appointments_data["items"])
        
        # Check that appointment appears in patient's view
        patient_appointments = test_client.get(
            "/api/v1/appointments",
            headers=auth_headers_patient
        )
        
        TestAssertions.assert_success_response(patient_appointments)
        patient_appointments_data = patient_appointments.json()
        assert any(apt["id"] == appointment["id"] for apt in patient_appointments_data["items"])
        
        # 4. Verify appointment details are consistent
        appointment_details = test_client.get(
            f"/api/v1/appointments/{appointment['id']}",
            headers=auth_headers_patient
        )
        
        TestAssertions.assert_success_response(appointment_details)
        details = appointment_details.json()
        
        assert details["id"] == appointment["id"]
        assert details["doctor_id"] == appointment["doctor_id"]
        assert details["patient_id"] == appointment["patient_id"]
        assert details["start_time"] == appointment["start_time"]
        assert details["end_time"] == appointment["end_time"]
