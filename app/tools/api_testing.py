"""Comprehensive API testing suite and tools."""

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TestCase:
    """Test case definition."""
    name: str
    method: str
    endpoint: str
    headers: Optional[Dict[str, str]] = None
    params: Optional[Dict[str, Any]] = None
    json_data: Optional[Dict[str, Any]] = None
    form_data: Optional[Dict[str, Any]] = None
    expected_status: Optional[int] = None
    expected_response: Optional[Dict[str, Any]] = None
    expected_fields: Optional[List[str]] = None
    timeout: float = 30.0
    retry_count: int = 0
    retry_delay: float = 1.0


@dataclass
class TestResult:
    """Test result container."""
    test_case: TestCase
    success: bool
    response_time: float
    status_code: int
    response_data: Any = None
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    retry_count: int = 0


class APITestSuite:
    """Comprehensive API test suite."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=30.0)
        self.test_cases: List[TestCase] = []
        self.results: List[TestResult] = []
        self.auth_token: Optional[str] = None
        self.test_data: Dict[str, Any] = {}
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    def add_test_case(self, test_case: TestCase):
        """Add a test case to the suite."""
        self.test_cases.append(test_case)
    
    def create_auth_test_cases(self) -> List[TestCase]:
        """Create authentication test cases."""
        return [
            TestCase(
                name="Health Check",
                method="GET",
                endpoint="/api/v2/health",
                expected_status=200
            ),
            TestCase(
                name="Login with valid credentials",
                method="POST",
                endpoint="/api/v2/auth/token",
                form_data={
                    "username": "admin@example.com",
                    "password": "admin123"
                },
                expected_status=200,
                expected_fields=["access_token", "token_type"]
            ),
            TestCase(
                name="Login with invalid credentials",
                method="POST",
                endpoint="/api/v2/auth/token",
                form_data={
                    "username": "admin@example.com",
                    "password": "wrongpassword"
                },
                expected_status=401
            ),
            TestCase(
                name="Access protected endpoint without token",
                method="GET",
                endpoint="/api/v2/users/me",
                expected_status=401
            )
        ]
    
    def create_user_test_cases(self) -> List[TestCase]:
        """Create user management test cases."""
        return [
            TestCase(
                name="Get current user",
                method="GET",
                endpoint="/api/v2/users/me",
                headers={"Authorization": "Bearer {token}"},
                expected_status=200,
                expected_fields=["id", "email", "full_name", "role"]
            ),
            TestCase(
                name="Get user by ID",
                method="GET",
                endpoint="/api/v2/users/{user_id}",
                headers={"Authorization": "Bearer {token}"},
                expected_status=200,
                expected_fields=["id", "email", "full_name", "role"]
            ),
            TestCase(
                name="Create user (admin only)",
                method="POST",
                endpoint="/api/v2/users",
                headers={"Authorization": "Bearer {token}"},
                json_data={
                    "email": "test@example.com",
                    "full_name": "Test User",
                    "password": "testpassword123",
                    "role": "patient"
                },
                expected_status=201,
                expected_fields=["id", "email", "full_name", "role"]
            )
        ]
    
    def create_appointment_test_cases(self) -> List[TestCase]:
        """Create appointment test cases."""
        return [
            TestCase(
                name="Get appointments",
                method="GET",
                endpoint="/api/v2/appointments",
                headers={"Authorization": "Bearer {token}"},
                expected_status=200
            ),
            TestCase(
                name="Create appointment",
                method="POST",
                endpoint="/api/v2/appointments",
                headers={"Authorization": "Bearer {token}"},
                json_data={
                    "patient_id": "{patient_id}",
                    "doctor_id": "{doctor_id}",
                    "start_time": "2024-01-20T14:00:00Z",
                    "end_time": "2024-01-20T15:00:00Z",
                    "reason_for_visit": "Annual checkup"
                },
                expected_status=201,
                expected_fields=["id", "patient_id", "doctor_id", "start_time", "end_time"]
            ),
            TestCase(
                name="Get appointment by ID",
                method="GET",
                endpoint="/api/v2/appointments/{appointment_id}",
                headers={"Authorization": "Bearer {token}"},
                expected_status=200
            ),
            TestCase(
                name="Cancel appointment",
                method="POST",
                endpoint="/api/v2/appointments/{appointment_id}/cancel",
                headers={"Authorization": "Bearer {token}"},
                expected_status=200
            )
        ]
    
    def create_availability_test_cases(self) -> List[TestCase]:
        """Create availability test cases."""
        return [
            TestCase(
                name="Get doctor availability",
                method="GET",
                endpoint="/api/v2/doctors/{doctor_id}/availability",
                headers={"Authorization": "Bearer {token}"},
                expected_status=200
            ),
            TestCase(
                name="Create doctor availability",
                method="POST",
                endpoint="/api/v2/doctors/{doctor_id}/availability",
                headers={"Authorization": "Bearer {token}"},
                json_data={
                    "start_time": "09:00:00",
                    "end_time": "17:00:00",
                    "day_of_week": 1
                },
                expected_status=201,
                expected_fields=["id", "start_time", "end_time", "day_of_week"]
            ),
            TestCase(
                name="Get available slots",
                method="GET",
                endpoint="/api/v2/doctors/{doctor_id}/availability/slots",
                headers={"Authorization": "Bearer {token}"},
                params={"date": "2024-01-20"},
                expected_status=200
            )
        ]
    
    def create_notification_test_cases(self) -> List[TestCase]:
        """Create notification test cases."""
        return [
            TestCase(
                name="Get notifications",
                method="GET",
                endpoint="/api/v2/notifications",
                headers={"Authorization": "Bearer {token}"},
                expected_status=200
            ),
            TestCase(
                name="Create notification",
                method="POST",
                endpoint="/api/v2/notifications",
                headers={"Authorization": "Bearer {token}"},
                json_data={
                    "user_id": "{user_id}",
                    "notification_type": "appointment_reminder",
                    "channel": "email",
                    "content": "Test notification",
                    "subject": "Test Subject"
                },
                expected_status=201,
                expected_fields=["id", "user_id", "notification_type", "channel"]
            ),
            TestCase(
                name="Mark notification as read",
                method="POST",
                endpoint="/api/v2/notifications/{notification_id}/read",
                headers={"Authorization": "Bearer {token}"},
                expected_status=200
            ),
            TestCase(
                name="Get notification preferences",
                method="GET",
                endpoint="/api/v2/notifications/preferences",
                headers={"Authorization": "Bearer {token}"},
                expected_status=200
            ),
            TestCase(
                name="Update notification preferences",
                method="PUT",
                endpoint="/api/v2/notifications/preferences",
                headers={"Authorization": "Bearer {token}"},
                json_data={
                    "preferences": [
                        {
                            "notification_type": "appointment_reminder",
                            "channel": "email",
                            "is_enabled": True,
                            "quiet_hours_start": "22:00",
                            "quiet_hours_end": "08:00"
                        }
                    ]
                },
                expected_status=200
            )
        ]
    
    def create_analytics_test_cases(self) -> List[TestCase]:
        """Create analytics test cases."""
        return [
            TestCase(
                name="Get engagement analytics",
                method="GET",
                endpoint="/api/v2/notifications/analytics/engagement",
                headers={"Authorization": "Bearer {token}"},
                expected_status=200
            ),
            TestCase(
                name="Get user engagement profile",
                method="GET",
                endpoint="/api/v2/notifications/analytics/user/{user_id}",
                headers={"Authorization": "Bearer {token}"},
                expected_status=200
            ),
            TestCase(
                name="Get channel performance",
                method="GET",
                endpoint="/api/v2/notifications/analytics/channels",
                headers={"Authorization": "Bearer {token}"},
                expected_status=200
            )
        ]
    
    def create_error_handling_test_cases(self) -> List[TestCase]:
        """Create error handling test cases."""
        return [
            TestCase(
                name="Invalid endpoint",
                method="GET",
                endpoint="/api/v2/invalid-endpoint",
                headers={"Authorization": "Bearer {token}"},
                expected_status=404
            ),
            TestCase(
                name="Invalid JSON",
                method="POST",
                endpoint="/api/v2/appointments",
                headers={
                    "Authorization": "Bearer {token}",
                    "Content-Type": "application/json"
                },
                json_data={"invalid": "json"},
                expected_status=422
            ),
            TestCase(
                name="Missing required field",
                method="POST",
                endpoint="/api/v2/appointments",
                headers={"Authorization": "Bearer {token}"},
                json_data={
                    "patient_id": "123e4567-e89b-12d3-a456-426614174000"
                    # Missing doctor_id, start_time, end_time
                },
                expected_status=422
            ),
            TestCase(
                name="Invalid UUID format",
                method="GET",
                endpoint="/api/v2/users/invalid-uuid",
                headers={"Authorization": "Bearer {token}"},
                expected_status=422
            )
        ]
    
    def create_load_test_cases(self, concurrent_users: int = 10, requests_per_user: int = 10) -> List[TestCase]:
        """Create load test cases."""
        test_cases = []
        
        for i in range(concurrent_users):
            for j in range(requests_per_user):
                test_cases.append(TestCase(
                    name=f"Load Test User {i+1} Request {j+1}",
                    method="GET",
                    endpoint="/api/v2/health",
                    timeout=5.0
                ))
        
        return test_cases
    
    async def run_test_case(self, test_case: TestCase) -> TestResult:
        """Run a single test case."""
        start_time = time.time()
        retry_count = 0
        
        while retry_count <= test_case.retry_count:
            try:
                # Prepare request
                url = f"{self.base_url}{test_case.endpoint}"
                
                # Replace placeholders in URL and data
                url = self._replace_placeholders(url)
                headers = self._replace_placeholders_in_dict(test_case.headers or {})
                json_data = self._replace_placeholders_in_dict(test_case.json_data or {})
                form_data = self._replace_placeholders_in_dict(test_case.form_data or {})
                params = self._replace_placeholders_in_dict(test_case.params or {})
                
                # Make request
                if test_case.method.upper() == "GET":
                    response = await self.client.get(url, headers=headers, params=params)
                elif test_case.method.upper() == "POST":
                    if json_data:
                        response = await self.client.post(url, headers=headers, json=json_data, params=params)
                    elif form_data:
                        response = await self.client.post(url, headers=headers, data=form_data, params=params)
                    else:
                        response = await self.client.post(url, headers=headers, params=params)
                elif test_case.method.upper() == "PUT":
                    response = await self.client.put(url, headers=headers, json=json_data, params=params)
                elif test_case.method.upper() == "DELETE":
                    response = await self.client.delete(url, headers=headers, params=params)
                elif test_case.method.upper() == "PATCH":
                    response = await self.client.patch(url, headers=headers, json=json_data, params=params)
                else:
                    raise ValueError(f"Unsupported HTTP method: {test_case.method}")
                
                response_time = time.time() - start_time
                
                # Parse response
                try:
                    response_data = response.json()
                except:
                    response_data = response.text
                
                # Check expected status
                expected_status = test_case.expected_status
                success = True
                error_message = None
                
                if expected_status and response.status_code != expected_status:
                    success = False
                    error_message = f"Expected status {expected_status}, got {response.status_code}"
                
                # Check expected response fields
                if success and test_case.expected_fields:
                    if not self._check_response_fields(response_data, test_case.expected_fields):
                        success = False
                        error_message = f"Missing expected fields: {test_case.expected_fields}"
                
                # Check expected response structure
                if success and test_case.expected_response:
                    if not self._check_response_structure(response_data, test_case.expected_response):
                        success = False
                        error_message = "Response does not match expected structure"
                
                # Store test data for future tests
                if success and isinstance(response_data, dict):
                    if "access_token" in response_data:
                        self.auth_token = response_data["access_token"]
                        self.test_data["token"] = self.auth_token
                    
                    if "id" in response_data:
                        if "user" in test_case.name.lower():
                            self.test_data["user_id"] = response_data["id"]
                        elif "appointment" in test_case.name.lower():
                            self.test_data["appointment_id"] = response_data["id"]
                        elif "doctor" in test_case.name.lower():
                            self.test_data["doctor_id"] = response_data["id"]
                        elif "notification" in test_case.name.lower():
                            self.test_data["notification_id"] = response_data["id"]
                
                return TestResult(
                    test_case=test_case,
                    success=success,
                    response_time=response_time,
                    status_code=response.status_code,
                    response_data=response_data,
                    error_message=error_message,
                    retry_count=retry_count
                )
                
            except Exception as e:
                response_time = time.time() - start_time
                
                if retry_count < test_case.retry_count:
                    retry_count += 1
                    await asyncio.sleep(test_case.retry_delay)
                    continue
                
                return TestResult(
                    test_case=test_case,
                    success=False,
                    response_time=response_time,
                    status_code=0,
                    error_message=str(e),
                    retry_count=retry_count
                )
    
    def _replace_placeholders(self, text: str) -> str:
        """Replace placeholders in text."""
        if not text:
            return text
        
        # Replace common placeholders
        replacements = {
            "{token}": self.auth_token or "",
            "{user_id}": self.test_data.get("user_id", "123e4567-e89b-12d3-a456-426614174000"),
            "{doctor_id}": self.test_data.get("doctor_id", "123e4567-e89b-12d3-a456-426614174001"),
            "{appointment_id}": self.test_data.get("appointment_id", "123e4567-e89b-12d3-a456-426614174002"),
            "{notification_id}": self.test_data.get("notification_id", "123e4567-e89b-12d3-a456-426614174003"),
            "{patient_id}": "123e4567-e89b-12d3-a456-426614174000"
        }
        
        for placeholder, value in replacements.items():
            text = text.replace(placeholder, value)
        
        return text
    
    def _replace_placeholders_in_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Replace placeholders in dictionary values."""
        if not data:
            return data
        
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self._replace_placeholders(value)
            elif isinstance(value, dict):
                result[key] = self._replace_placeholders_in_dict(value)
            elif isinstance(value, list):
                result[key] = [
                    self._replace_placeholders(item) if isinstance(item, str) else item
                    for item in value
                ]
            else:
                result[key] = value
        
        return result
    
    def _check_response_fields(self, response_data: Any, expected_fields: List[str]) -> bool:
        """Check if response contains expected fields."""
        if not isinstance(response_data, dict):
            return False
        
        for field in expected_fields:
            if field not in response_data:
                return False
        
        return True
    
    def _check_response_structure(self, response_data: Any, expected_structure: Dict[str, Any]) -> bool:
        """Check if response matches expected structure."""
        if not isinstance(response_data, dict):
            return False
        
        for key, expected_value in expected_structure.items():
            if key not in response_data:
                return False
            
            if isinstance(expected_value, dict):
                if not self._check_response_structure(response_data[key], expected_value):
                    return False
            elif response_data[key] != expected_value:
                return False
        
        return True
    
    async def run_all_tests(self) -> List[TestResult]:
        """Run all test cases."""
        self.results = []
        
        logger.info(f"Running {len(self.test_cases)} test cases")
        
        for test_case in self.test_cases:
            result = await self.run_test_case(test_case)
            self.results.append(result)
            
            status = "✅ PASS" if result.success else "❌ FAIL"
            logger.info(f"  {status} {result.test_case.name} ({result.response_time:.3f}s)")
            
            if not result.success and result.error_message:
                logger.error(f"    Error: {result.error_message}")
        
        return self.results
    
    def get_summary(self) -> Dict[str, Any]:
        """Get test summary."""
        total_tests = len(self.results)
        passed_tests = len([r for r in self.results if r.success])
        failed_tests = total_tests - passed_tests
        
        avg_response_time = sum(r.response_time for r in self.results) / total_tests if total_tests > 0 else 0
        
        return {
            "total_tests": total_tests,
            "passed": passed_tests,
            "failed": failed_tests,
            "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
            "average_response_time": round(avg_response_time, 3),
            "failed_tests": [
                {
                    "name": r.test_case.name,
                    "error": r.error_message,
                    "status_code": r.status_code
                }
                for r in self.results
                if not r.success
            ]
        }


# Predefined test suites
def create_comprehensive_test_suite(base_url: str = "http://localhost:8000") -> APITestSuite:
    """Create comprehensive test suite."""
    suite = APITestSuite(base_url)
    
    # Add all test cases
    suite.test_cases.extend(suite.create_auth_test_cases())
    suite.test_cases.extend(suite.create_user_test_cases())
    suite.test_cases.extend(suite.create_appointment_test_cases())
    suite.test_cases.extend(suite.create_availability_test_cases())
    suite.test_cases.extend(suite.create_notification_test_cases())
    suite.test_cases.extend(suite.create_analytics_test_cases())
    suite.test_cases.extend(suite.create_error_handling_test_cases())
    
    return suite


def create_smoke_test_suite(base_url: str = "http://localhost:8000") -> APITestSuite:
    """Create smoke test suite."""
    suite = APITestSuite(base_url)
    
    # Add essential test cases
    suite.test_cases.extend(suite.create_auth_test_cases()[:2])  # Health check and login
    suite.test_cases.extend(suite.create_user_test_cases()[:1])  # Get current user
    suite.test_cases.extend(suite.create_appointment_test_cases()[:1])  # Get appointments
    
    return suite


def create_load_test_suite(base_url: str = "http://localhost:8000", concurrent_users: int = 10, requests_per_user: int = 10) -> APITestSuite:
    """Create load test suite."""
    suite = APITestSuite(base_url)
    suite.test_cases.extend(suite.create_load_test_cases(concurrent_users, requests_per_user))
    return suite


# CLI interface
async def run_tests(test_type: str = "comprehensive", base_url: str = "http://localhost:8000"):
    """Run tests from command line."""
    if test_type == "comprehensive":
        suite = create_comprehensive_test_suite(base_url)
    elif test_type == "smoke":
        suite = create_smoke_test_suite(base_url)
    elif test_type == "load":
        suite = create_load_test_suite(base_url)
    else:
        raise ValueError(f"Unknown test type: {test_type}")
    
    async with suite:
        await suite.run_all_tests()
        summary = suite.get_summary()
        print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    import sys
    test_type = sys.argv[1] if len(sys.argv) > 1 else "comprehensive"
    base_url = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8000"
    asyncio.run(run_tests(test_type, base_url))
