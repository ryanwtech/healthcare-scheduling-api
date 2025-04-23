"""API testing utilities and tools for developers."""

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
class TestResult:
    """Test result container."""
    name: str
    success: bool
    response_time: float
    status_code: int
    response_data: Any = None
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TestSuite:
    """Test suite container."""
    name: str
    tests: List[Dict[str, Any]] = field(default_factory=list)
    results: List[TestResult] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    def add_test(self, name: str, method: str, url: str, **kwargs):
        """Add a test to the suite."""
        self.tests.append({
            "name": name,
            "method": method.upper(),
            "url": url,
            **kwargs
        })
    
    def get_summary(self) -> Dict[str, Any]:
        """Get test suite summary."""
        total_tests = len(self.results)
        passed_tests = len([r for r in self.results if r.success])
        failed_tests = total_tests - passed_tests
        
        avg_response_time = sum(r.response_time for r in self.results) / total_tests if total_tests > 0 else 0
        
        return {
            "suite_name": self.name,
            "total_tests": total_tests,
            "passed": passed_tests,
            "failed": failed_tests,
            "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
            "average_response_time": round(avg_response_time, 3),
            "duration": (self.end_time - self.start_time).total_seconds() if self.start_time and self.end_time else 0
        }


class APITester:
    """API testing utility for developers."""
    
    def __init__(self, base_url: str = "http://localhost:8000", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
        self.test_suites: List[TestSuite] = []
        self.current_suite: Optional[TestSuite] = None
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    def create_test_suite(self, name: str) -> TestSuite:
        """Create a new test suite."""
        suite = TestSuite(name=name)
        self.test_suites.append(suite)
        self.current_suite = suite
        return suite
    
    def add_test(
        self,
        name: str,
        method: str,
        endpoint: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        form_data: Optional[Dict[str, Any]] = None,
        expected_status: Optional[int] = None,
        expected_response: Optional[Dict[str, Any]] = None
    ):
        """Add a test to the current suite."""
        if not self.current_suite:
            raise ValueError("No active test suite. Create one first.")
        
        self.current_suite.add_test(
            name=name,
            method=method,
            endpoint=endpoint,
            headers=headers,
            params=params,
            json_data=json_data,
            form_data=form_data,
            expected_status=expected_status,
            expected_response=expected_response
        )
    
    async def run_test(self, test: Dict[str, Any]) -> TestResult:
        """Run a single test."""
        start_time = time.time()
        
        try:
            # Prepare request
            url = f"{self.base_url}{test['endpoint']}"
            method = test['method']
            headers = test.get('headers', {})
            params = test.get('params')
            json_data = test.get('json_data')
            form_data = test.get('form_data')
            
            # Make request
            if method == "GET":
                response = await self.client.get(url, headers=headers, params=params)
            elif method == "POST":
                if json_data:
                    response = await self.client.post(url, headers=headers, json=json_data, params=params)
                elif form_data:
                    response = await self.client.post(url, headers=headers, data=form_data, params=params)
                else:
                    response = await self.client.post(url, headers=headers, params=params)
            elif method == "PUT":
                response = await self.client.put(url, headers=headers, json=json_data, params=params)
            elif method == "DELETE":
                response = await self.client.delete(url, headers=headers, params=params)
            elif method == "PATCH":
                response = await self.client.patch(url, headers=headers, json=json_data, params=params)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response_time = time.time() - start_time
            
            # Parse response
            try:
                response_data = response.json()
            except:
                response_data = response.text
            
            # Check expected status
            expected_status = test.get('expected_status')
            success = True
            error_message = None
            
            if expected_status and response.status_code != expected_status:
                success = False
                error_message = f"Expected status {expected_status}, got {response.status_code}"
            
            # Check expected response
            expected_response = test.get('expected_response')
            if expected_response and success:
                if not self._check_response_match(response_data, expected_response):
                    success = False
                    error_message = "Response does not match expected format"
            
            return TestResult(
                name=test['name'],
                success=success,
                response_time=response_time,
                status_code=response.status_code,
                response_data=response_data,
                error_message=error_message
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            return TestResult(
                name=test['name'],
                success=False,
                response_time=response_time,
                status_code=0,
                error_message=str(e)
            )
    
    def _check_response_match(self, actual: Any, expected: Dict[str, Any]) -> bool:
        """Check if actual response matches expected format."""
        if not isinstance(actual, dict):
            return False
        
        for key, expected_value in expected.items():
            if key not in actual:
                return False
            
            if isinstance(expected_value, dict):
                if not self._check_response_match(actual[key], expected_value):
                    return False
            elif actual[key] != expected_value:
                return False
        
        return True
    
    async def run_suite(self, suite: TestSuite) -> TestSuite:
        """Run a test suite."""
        suite.start_time = datetime.now(timezone.utc)
        suite.results = []
        
        logger.info(f"Running test suite: {suite.name}")
        
        for test in suite.tests:
            result = await self.run_test(test)
            suite.results.append(result)
            
            status = "✅ PASS" if result.success else "❌ FAIL"
            logger.info(f"  {status} {result.name} ({result.response_time:.3f}s)")
            
            if not result.success and result.error_message:
                logger.error(f"    Error: {result.error_message}")
        
        suite.end_time = datetime.now(timezone.utc)
        
        summary = suite.get_summary()
        logger.info(f"Test suite completed: {summary['passed']}/{summary['total_tests']} passed")
        
        return suite
    
    async def run_all_suites(self) -> List[TestSuite]:
        """Run all test suites."""
        for suite in self.test_suites:
            await self.run_suite(suite)
        return self.test_suites
    
    def get_report(self) -> Dict[str, Any]:
        """Get comprehensive test report."""
        all_results = []
        for suite in self.test_suites:
            all_results.extend(suite.results)
        
        total_tests = len(all_results)
        passed_tests = len([r for r in all_results if r.success])
        failed_tests = total_tests - passed_tests
        
        avg_response_time = sum(r.response_time for r in all_results) / total_tests if total_tests > 0 else 0
        
        return {
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
                "average_response_time": round(avg_response_time, 3)
            },
            "suites": [suite.get_summary() for suite in self.test_suites],
            "failed_tests": [
                {
                    "suite": suite.name,
                    "test": result.name,
                    "error": result.error_message,
                    "status_code": result.status_code
                }
                for suite in self.test_suites
                for result in suite.results
                if not result.success
            ]
        }


class HealthCheckTester:
    """Health check testing utility."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient()
    
    async def check_health(self) -> Dict[str, Any]:
        """Check API health."""
        try:
            response = await self.client.get(f"{self.base_url}/api/v1/health")
            return {
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "status_code": response.status_code,
                "response_time": response.elapsed.total_seconds(),
                "data": response.json() if response.status_code == 200 else None
            }
        except Exception as e:
            return {
                "status": "unreachable",
                "error": str(e)
            }
    
    async def check_dependencies(self) -> Dict[str, Any]:
        """Check API dependencies."""
        try:
            response = await self.client.get(f"{self.base_url}/api/v1/health")
            if response.status_code == 200:
                data = response.json()
                return data.get("dependencies", {})
            return {"error": "Health check failed"}
        except Exception as e:
            return {"error": str(e)}
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()


class LoadTester:
    """Load testing utility."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient()
    
    async def run_load_test(
        self,
        endpoint: str,
        method: str = "GET",
        concurrent_users: int = 10,
        requests_per_user: int = 10,
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Run load test on an endpoint."""
        url = f"{self.base_url}{endpoint}"
        results = []
        
        async def make_request():
            start_time = time.time()
            try:
                if method.upper() == "GET":
                    response = await self.client.get(url, headers=headers)
                elif method.upper() == "POST":
                    response = await self.client.post(url, headers=headers, json=json_data)
                else:
                    raise ValueError(f"Unsupported method: {method}")
                
                response_time = time.time() - start_time
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "response_time": response_time,
                    "timestamp": datetime.now(timezone.utc)
                }
            except Exception as e:
                response_time = time.time() - start_time
                return {
                    "success": False,
                    "error": str(e),
                    "response_time": response_time,
                    "timestamp": datetime.now(timezone.utc)
                }
        
        # Run concurrent requests
        tasks = []
        for _ in range(concurrent_users):
            for _ in range(requests_per_user):
                tasks.append(make_request())
        
        results = await asyncio.gather(*tasks)
        
        # Analyze results
        total_requests = len(results)
        successful_requests = len([r for r in results if r["success"]])
        failed_requests = total_requests - successful_requests
        
        response_times = [r["response_time"] for r in results if r["success"]]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        min_response_time = min(response_times) if response_times else 0
        max_response_time = max(response_times) if response_times else 0
        
        return {
            "endpoint": endpoint,
            "method": method,
            "concurrent_users": concurrent_users,
            "requests_per_user": requests_per_user,
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "success_rate": (successful_requests / total_requests * 100) if total_requests > 0 else 0,
            "average_response_time": round(avg_response_time, 3),
            "min_response_time": round(min_response_time, 3),
            "max_response_time": round(max_response_time, 3),
            "requests_per_second": round(total_requests / (max_response_time - min_response_time), 2) if max_response_time > min_response_time else 0
        }
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()


# Predefined test suites
def create_auth_test_suite(tester: APITester) -> TestSuite:
    """Create authentication test suite."""
    suite = tester.create_test_suite("Authentication Tests")
    
    # Test login
    suite.add_test(
        name="Login with valid credentials",
        method="POST",
        endpoint="/api/v1/auth/token",
        form_data={
            "username": "admin@example.com",
            "password": "admin123"
        },
        expected_status=200
    )
    
    # Test invalid login
    suite.add_test(
        name="Login with invalid credentials",
        method="POST",
        endpoint="/api/v1/auth/token",
        form_data={
            "username": "admin@example.com",
            "password": "wrongpassword"
        },
        expected_status=401
    )
    
    # Test protected endpoint without token
    suite.add_test(
        name="Access protected endpoint without token",
        method="GET",
        endpoint="/api/v1/users/me",
        expected_status=401
    )
    
    return suite


def create_appointment_test_suite(tester: APITester, auth_token: str) -> TestSuite:
    """Create appointment test suite."""
    suite = tester.create_test_suite("Appointment Tests")
    
    headers = {"Authorization": f"Bearer {auth_token}"}
    
    # Test get appointments
    suite.add_test(
        name="Get appointments",
        method="GET",
        endpoint="/api/v1/appointments",
        headers=headers,
        expected_status=200
    )
    
    # Test create appointment
    suite.add_test(
        name="Create appointment",
        method="POST",
        endpoint="/api/v1/appointments",
        headers=headers,
        json_data={
            "patient_id": "123e4567-e89b-12d3-a456-426614174000",
            "doctor_id": "123e4567-e89b-12d3-a456-426614174001",
            "start_time": "2024-01-20T14:00:00Z",
            "end_time": "2024-01-20T15:00:00Z",
            "reason_for_visit": "Annual checkup"
        },
        expected_status=201
    )
    
    return suite


# CLI interface
async def run_api_tests(base_url: str = "http://localhost:8000"):
    """Run API tests from command line."""
    async with APITester(base_url) as tester:
        # Create test suites
        auth_suite = create_auth_test_suite(tester)
        
        # Run tests
        await tester.run_all_suites()
        
        # Generate report
        report = tester.get_report()
        print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(run_api_tests())
