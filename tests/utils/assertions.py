"""Custom assertion helpers for testing."""

from datetime import datetime, UTC
from typing import Any, Dict, List, Optional
from uuid import UUID

import pytest
from fastapi import status
from httpx import Response


class TestAssertions:
    """Custom assertion helpers for API testing."""
    
    @staticmethod
    def assert_success_response(response: Response, expected_status: int = status.HTTP_200_OK):
        """Assert that the response is successful."""
        assert response.status_code == expected_status, f"Expected {expected_status}, got {response.status_code}. Response: {response.text}"
    
    @staticmethod
    def assert_error_response(response: Response, expected_status: int, expected_message: str = None):
        """Assert that the response is an error with expected status and message."""
        assert response.status_code == expected_status, f"Expected {expected_status}, got {response.status_code}. Response: {response.text}"
        
        if expected_message:
            response_data = response.json()
            if "detail" in response_data:
                assert expected_message in str(response_data["detail"]), f"Expected message '{expected_message}' not found in response: {response_data}"
            elif "error" in response_data and "message" in response_data["error"]:
                assert expected_message in str(response_data["error"]["message"]), f"Expected message '{expected_message}' not found in response: {response_data}"
    
    @staticmethod
    def assert_unauthorized(response: Response):
        """Assert that the response indicates unauthorized access."""
        TestAssertions.assert_error_response(response, status.HTTP_401_UNAUTHORIZED)
    
    @staticmethod
    def assert_forbidden(response: Response):
        """Assert that the response indicates forbidden access."""
        TestAssertions.assert_error_response(response, status.HTTP_403_FORBIDDEN)
    
    @staticmethod
    def assert_not_found(response: Response):
        """Assert that the response indicates resource not found."""
        TestAssertions.assert_error_response(response, status.HTTP_404_NOT_FOUND)
    
    @staticmethod
    def assert_validation_error(response: Response):
        """Assert that the response indicates validation error."""
        TestAssertions.assert_error_response(response, status.HTTP_422_UNPROCESSABLE_ENTITY)
    
    @staticmethod
    def assert_rate_limited(response: Response):
        """Assert that the response indicates rate limiting."""
        TestAssertions.assert_error_response(response, status.HTTP_429_TOO_MANY_REQUESTS)
    
    @staticmethod
    def assert_user_data(response_data: Dict[str, Any], expected_user: Dict[str, Any]):
        """Assert that user data matches expected values."""
        assert response_data["email"] == expected_user["email"]
        assert response_data["full_name"] == expected_user["full_name"]
        assert response_data["role"] == expected_user["role"]
        assert response_data["is_active"] == expected_user["is_active"]
        assert "id" in response_data
        assert "created_at" in response_data
        assert "updated_at" in response_data
    
    @staticmethod
    def assert_appointment_data(response_data: Dict[str, Any], expected_appointment: Dict[str, Any]):
        """Assert that appointment data matches expected values."""
        assert response_data["doctor_id"] == str(expected_appointment["doctor_id"])
        assert response_data["patient_id"] == str(expected_appointment["patient_id"])
        assert response_data["start_time"] == expected_appointment["start_time"]
        assert response_data["end_time"] == expected_appointment["end_time"]
        assert response_data["status"] == expected_appointment.get("status", "scheduled")
        assert response_data["notes"] == expected_appointment.get("notes")
        assert "id" in response_data
        assert "created_at" in response_data
        assert "updated_at" in response_data
    
    @staticmethod
    def assert_availability_data(response_data: Dict[str, Any], expected_availability: Dict[str, Any]):
        """Assert that availability data matches expected values."""
        assert response_data["doctor_id"] == str(expected_availability["doctor_id"])
        assert response_data["start_time"] == expected_availability["start_time"]
        assert response_data["end_time"] == expected_availability["end_time"]
        assert "id" in response_data
        assert "created_at" in response_data
    
    @staticmethod
    def assert_paginated_response(response_data: Dict[str, Any], expected_items: int = None):
        """Assert that the response is a valid paginated response."""
        assert "items" in response_data
        assert "total" in response_data
        assert "page" in response_data
        assert "size" in response_data
        assert "pages" in response_data
        
        if expected_items is not None:
            assert len(response_data["items"]) == expected_items
            assert response_data["total"] == expected_items
    
    @staticmethod
    def assert_token_response(response_data: Dict[str, Any]):
        """Assert that the response contains valid token data."""
        assert "access_token" in response_data
        assert "token_type" in response_data
        assert response_data["token_type"] == "bearer"
        assert "expires_in" in response_data
        assert response_data["expires_in"] > 0
    
    @staticmethod
    def assert_health_response(response_data: Dict[str, Any]):
        """Assert that the health check response is valid."""
        assert response_data["status"] == "ok"
        assert "message" in response_data
        assert "uptime_seconds" in response_data
        assert "version" in response_data
        assert "environment" in response_data
    
    @staticmethod
    def assert_metrics_response(response_text: str):
        """Assert that the metrics response contains expected Prometheus metrics."""
        assert "http_requests_total" in response_text
        assert "http_request_duration_seconds" in response_text
        assert "http_active_connections" in response_text
    
    @staticmethod
    def assert_uuid_format(value: str, field_name: str = "ID"):
        """Assert that a value is a valid UUID format."""
        try:
            UUID(value)
        except ValueError:
            pytest.fail(f"{field_name} '{value}' is not a valid UUID format")
    
    @staticmethod
    def assert_datetime_format(value: str, field_name: str = "datetime"):
        """Assert that a value is a valid ISO datetime format."""
        try:
            datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            pytest.fail(f"{field_name} '{value}' is not a valid ISO datetime format")
    
    @staticmethod
    def assert_time_range_valid(start_time: str, end_time: str):
        """Assert that start_time is before end_time."""
        start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        assert start_dt < end_dt, f"Start time {start_time} must be before end time {end_time}"
    
    @staticmethod
    def assert_future_time(time_str: str, field_name: str = "time"):
        """Assert that a time is in the future."""
        time_dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
        now = datetime.now(UTC)
        assert time_dt > now, f"{field_name} {time_str} must be in the future"
    
    @staticmethod
    def assert_no_overlap(times1: List[Dict[str, str]], times2: List[Dict[str, str]]):
        """Assert that two sets of time ranges don't overlap."""
        for t1 in times1:
            for t2 in times2:
                start1 = datetime.fromisoformat(t1["start_time"].replace('Z', '+00:00'))
                end1 = datetime.fromisoformat(t1["end_time"].replace('Z', '+00:00'))
                start2 = datetime.fromisoformat(t2["start_time"].replace('Z', '+00:00'))
                end2 = datetime.fromisoformat(t2["end_time"].replace('Z', '+00:00'))
                
                # Check if ranges overlap
                overlap = start1 < end2 and start2 < end1
                assert not overlap, f"Time ranges overlap: {t1} and {t2}"
