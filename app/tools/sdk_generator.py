"""SDK generation and code examples for better developer experience."""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)


class SDKGenerator:
    """Generate client SDKs and code examples."""
    
    def __init__(self, base_url: str = "https://api.healthcare.example.com"):
        self.base_url = base_url
        self.api_version = "v2"
    
    def generate_python_sdk(self, output_dir: str = "sdk/python") -> None:
        """Generate Python SDK."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Generate main SDK file
        sdk_content = self._generate_python_sdk_content()
        (output_path / "healthcare_api.py").write_text(sdk_content)
        
        # Generate requirements.txt
        requirements = self._generate_requirements()
        (output_path / "requirements.txt").write_text(requirements)
        
        # Generate setup.py
        setup_content = self._generate_setup_py()
        (output_path / "setup.py").write_text(setup_content)
        
        # Generate README
        readme_content = self._generate_python_readme()
        (output_path / "README.md").write_text(readme_content)
        
        logger.info(f"Python SDK generated in {output_dir}")
    
    def generate_javascript_sdk(self, output_dir: str = "sdk/javascript") -> None:
        """Generate JavaScript SDK."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Generate main SDK file
        sdk_content = self._generate_javascript_sdk_content()
        (output_path / "healthcare-api.js").write_text(sdk_content)
        
        # Generate package.json
        package_json = self._generate_package_json()
        (output_path / "package.json").write_text(json.dumps(package_json, indent=2))
        
        # Generate README
        readme_content = self._generate_javascript_readme()
        (output_path / "README.md").write_text(readme_content)
        
        logger.info(f"JavaScript SDK generated in {output_dir}")
    
    def generate_curl_examples(self, output_dir: str = "examples/curl") -> None:
        """Generate cURL examples."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        examples = self._generate_curl_examples()
        (output_path / "api_examples.sh").write_text(examples)
        
        logger.info(f"cURL examples generated in {output_dir}")
    
    def _generate_python_sdk_content(self) -> str:
        """Generate Python SDK content."""
        return '''"""
Healthcare Scheduling API Python SDK
"""

import httpx
import asyncio
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
import json


class HealthcareAPIError(Exception):
    """Base exception for Healthcare API errors."""
    pass


class HealthcareAPI:
    """Healthcare Scheduling API client."""
    
    def __init__(self, base_url: str = "https://api.healthcare.example.com", api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Content-Type": "application/json"}
        )
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    def _get_headers(self, additional_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Get request headers."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if additional_headers:
            headers.update(additional_headers)
        return headers
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Make HTTP request."""
        url = f"/api/v2{endpoint}"
        request_headers = self._get_headers(headers)
        
        try:
            response = await self.client.request(
                method=method,
                url=url,
                json=data,
                params=params,
                headers=request_headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HealthcareAPIError(f"HTTP {e.response.status_code}: {e.response.text}")
        except Exception as e:
            raise HealthcareAPIError(f"Request failed: {str(e)}")
    
    # Authentication methods
    async def login(self, email: str, password: str) -> Dict[str, Any]:
        """Login and get access token."""
        data = {
            "username": email,
            "password": password
        }
        response = await self.client.post(
            "/api/v2/auth/token",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        response.raise_for_status()
        token_data = response.json()
        self.api_key = token_data["access_token"]
        return token_data
    
    # User methods
    async def get_current_user(self) -> Dict[str, Any]:
        """Get current user information."""
        return await self._make_request("GET", "/users/me")
    
    async def get_user(self, user_id: str) -> Dict[str, Any]:
        """Get user by ID."""
        return await self._make_request("GET", f"/users/{user_id}")
    
    # Appointment methods
    async def get_appointments(
        self,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Get appointments."""
        params = {"limit": limit, "offset": offset}
        if user_id:
            params["user_id"] = user_id
        if status:
            params["status"] = status
        
        return await self._make_request("GET", "/appointments", params=params)
    
    async def create_appointment(
        self,
        patient_id: str,
        doctor_id: str,
        start_time: str,
        end_time: str,
        reason_for_visit: str
    ) -> Dict[str, Any]:
        """Create appointment."""
        data = {
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "start_time": start_time,
            "end_time": end_time,
            "reason_for_visit": reason_for_visit
        }
        return await self._make_request("POST", "/appointments", data=data)
    
    async def cancel_appointment(self, appointment_id: str) -> Dict[str, Any]:
        """Cancel appointment."""
        return await self._make_request("POST", f"/appointments/{appointment_id}/cancel")
    
    # Availability methods
    async def get_doctor_availability(
        self,
        doctor_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get doctor availability."""
        params = {}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        
        return await self._make_request("GET", f"/doctors/{doctor_id}/availability", params=params)
    
    async def create_availability(
        self,
        doctor_id: str,
        start_time: str,
        end_time: str,
        day_of_week: int
    ) -> Dict[str, Any]:
        """Create doctor availability."""
        data = {
            "start_time": start_time,
            "end_time": end_time,
            "day_of_week": day_of_week
        }
        return await self._make_request("POST", f"/doctors/{doctor_id}/availability", data=data)
    
    # Notification methods
    async def get_notifications(
        self,
        notification_type: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Get notifications."""
        params = {"limit": limit, "offset": offset}
        if notification_type:
            params["notification_type"] = notification_type
        
        return await self._make_request("GET", "/notifications", params=params)
    
    async def mark_notification_read(self, notification_id: str) -> Dict[str, Any]:
        """Mark notification as read."""
        return await self._make_request("POST", f"/notifications/{notification_id}/read")
    
    # Health check
    async def health_check(self) -> Dict[str, Any]:
        """Check API health."""
        return await self._make_request("GET", "/health")


# Example usage
async def main():
    """Example usage of the Healthcare API SDK."""
    async with HealthcareAPI() as api:
        # Login
        await api.login("admin@example.com", "admin123")
        
        # Get current user
        user = await api.get_current_user()
        print(f"Logged in as: {user['full_name']}")
        
        # Get appointments
        appointments = await api.get_appointments()
        print(f"Found {len(appointments.get('data', []))} appointments")
        
        # Health check
        health = await api.health_check()
        print(f"API status: {health['status']}")


if __name__ == "__main__":
    asyncio.run(main())
'''
    
    def _generate_javascript_sdk_content(self) -> str:
        """Generate JavaScript SDK content."""
        return '''/**
 * Healthcare Scheduling API JavaScript SDK
 */

class HealthcareAPIError extends Error {
    constructor(message, statusCode) {
        super(message);
        this.name = 'HealthcareAPIError';
        this.statusCode = statusCode;
    }
}

class HealthcareAPI {
    constructor(baseUrl = 'https://api.healthcare.example.com', apiKey = null) {
        this.baseUrl = baseUrl.replace(/\/$/, '');
        this.apiKey = apiKey;
    }
    
    _getHeaders(additionalHeaders = {}) {
        const headers = {
            'Content-Type': 'application/json',
            ...additionalHeaders
        };
        
        if (this.apiKey) {
            headers['Authorization'] = `Bearer ${this.apiKey}`;
        }
        
        return headers;
    }
    
    async _makeRequest(method, endpoint, data = null, params = null, headers = {}) {
        const url = new URL(`/api/v2${endpoint}`, this.baseUrl);
        
        if (params) {
            Object.keys(params).forEach(key => {
                if (params[key] !== null && params[key] !== undefined) {
                    url.searchParams.append(key, params[key]);
                }
            });
        }
        
        const requestOptions = {
            method,
            headers: this._getHeaders(headers)
        };
        
        if (data && method !== 'GET') {
            requestOptions.body = JSON.stringify(data);
        }
        
        try {
            const response = await fetch(url, requestOptions);
            
            if (!response.ok) {
                const errorText = await response.text();
                throw new HealthcareAPIError(
                    `HTTP ${response.status}: ${errorText}`,
                    response.status
                );
            }
            
            return await response.json();
        } catch (error) {
            if (error instanceof HealthcareAPIError) {
                throw error;
            }
            throw new HealthcareAPIError(`Request failed: ${error.message}`);
        }
    }
    
    // Authentication methods
    async login(email, password) {
        const formData = new FormData();
        formData.append('username', email);
        formData.append('password', password);
        
        const response = await fetch(`${this.baseUrl}/api/v2/auth/token`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const errorText = await response.text();
            throw new HealthcareAPIError(`HTTP ${response.status}: ${errorText}`, response.status);
        }
        
        const tokenData = await response.json();
        this.apiKey = tokenData.access_token;
        return tokenData;
    }
    
    // User methods
    async getCurrentUser() {
        return await this._makeRequest('GET', '/users/me');
    }
    
    async getUser(userId) {
        return await this._makeRequest('GET', `/users/${userId}`);
    }
    
    // Appointment methods
    async getAppointments(userId = null, status = null, limit = 20, offset = 0) {
        const params = { limit, offset };
        if (userId) params.user_id = userId;
        if (status) params.status = status;
        
        return await this._makeRequest('GET', '/appointments', null, params);
    }
    
    async createAppointment(patientId, doctorId, startTime, endTime, reasonForVisit) {
        const data = {
            patient_id: patientId,
            doctor_id: doctorId,
            start_time: startTime,
            end_time: endTime,
            reason_for_visit: reasonForVisit
        };
        return await this._makeRequest('POST', '/appointments', data);
    }
    
    async cancelAppointment(appointmentId) {
        return await this._makeRequest('POST', `/appointments/${appointmentId}/cancel`);
    }
    
    // Availability methods
    async getDoctorAvailability(doctorId, startDate = null, endDate = null) {
        const params = {};
        if (startDate) params.start_date = startDate;
        if (endDate) params.end_date = endDate;
        
        return await this._makeRequest('GET', `/doctors/${doctorId}/availability`, null, params);
    }
    
    async createAvailability(doctorId, startTime, endTime, dayOfWeek) {
        const data = {
            start_time: startTime,
            end_time: endTime,
            day_of_week: dayOfWeek
        };
        return await this._makeRequest('POST', `/doctors/${doctorId}/availability`, data);
    }
    
    // Notification methods
    async getNotifications(notificationType = null, limit = 20, offset = 0) {
        const params = { limit, offset };
        if (notificationType) params.notification_type = notificationType;
        
        return await this._makeRequest('GET', '/notifications', null, params);
    }
    
    async markNotificationRead(notificationId) {
        return await this._makeRequest('POST', `/notifications/${notificationId}/read`);
    }
    
    // Health check
    async healthCheck() {
        return await this._makeRequest('GET', '/health');
    }
}

// Example usage
async function example() {
    const api = new HealthcareAPI();
    
    try {
        // Login
        await api.login('admin@example.com', 'admin123');
        
        // Get current user
        const user = await api.getCurrentUser();
        console.log(`Logged in as: ${user.full_name}`);
        
        // Get appointments
        const appointments = await api.getAppointments();
        console.log(`Found ${appointments.data?.length || 0} appointments`);
        
        // Health check
        const health = await api.healthCheck();
        console.log(`API status: ${health.status}`);
    } catch (error) {
        console.error('API Error:', error.message);
    }
}

// Export for use in modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { HealthcareAPI, HealthcareAPIError };
}
'''
    
    def _generate_curl_examples(self) -> str:
        """Generate cURL examples."""
        return '''#!/bin/bash
# Healthcare Scheduling API cURL Examples

BASE_URL="https://api.healthcare.example.com"
API_VERSION="v2"

# Colors for output
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
NC='\\033[0m' # No Color

echo -e "${GREEN}Healthcare Scheduling API cURL Examples${NC}"
echo "================================================"

# 1. Health Check
echo -e "\\n${YELLOW}1. Health Check${NC}"
curl -X GET "${BASE_URL}/api/${API_VERSION}/health" \\
  -H "Content-Type: application/json"

# 2. Login
echo -e "\\n\\n${YELLOW}2. Login${NC}"
LOGIN_RESPONSE=$(curl -s -X POST "${BASE_URL}/api/${API_VERSION}/auth/token" \\
  -H "Content-Type: application/x-www-form-urlencoded" \\
  -d "username=admin@example.com&password=admin123")

echo "$LOGIN_RESPONSE"

# Extract token (requires jq)
TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.access_token')
echo -e "\\nToken: $TOKEN"

# 3. Get Current User
echo -e "\\n\\n${YELLOW}3. Get Current User${NC}"
curl -X GET "${BASE_URL}/api/${API_VERSION}/users/me" \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json"

# 4. Get Appointments
echo -e "\\n\\n${YELLOW}4. Get Appointments${NC}"
curl -X GET "${BASE_URL}/api/${API_VERSION}/appointments" \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json"

# 5. Create Appointment
echo -e "\\n\\n${YELLOW}5. Create Appointment${NC}"
curl -X POST "${BASE_URL}/api/${API_VERSION}/appointments" \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "patient_id": "123e4567-e89b-12d3-a456-426614174000",
    "doctor_id": "123e4567-e89b-12d3-a456-426614174001",
    "start_time": "2024-01-20T14:00:00Z",
    "end_time": "2024-01-20T15:00:00Z",
    "reason_for_visit": "Annual checkup"
  }'

# 6. Get Doctor Availability
echo -e "\\n\\n${YELLOW}6. Get Doctor Availability${NC}"
curl -X GET "${BASE_URL}/api/${API_VERSION}/doctors/123e4567-e89b-12d3-a456-426614174001/availability" \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json"

# 7. Create Doctor Availability
echo -e "\\n\\n${YELLOW}7. Create Doctor Availability${NC}"
curl -X POST "${BASE_URL}/api/${API_VERSION}/doctors/123e4567-e89b-12d3-a456-426614174001/availability" \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "start_time": "09:00:00",
    "end_time": "17:00:00",
    "day_of_week": 1
  }'

# 8. Get Notifications
echo -e "\\n\\n${YELLOW}8. Get Notifications${NC}"
curl -X GET "${BASE_URL}/api/${API_VERSION}/notifications" \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json"

# 9. Update Notification Preferences
echo -e "\\n\\n${YELLOW}9. Update Notification Preferences${NC}"
curl -X PUT "${BASE_URL}/api/${API_VERSION}/notifications/preferences" \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "preferences": [
      {
        "notification_type": "appointment_reminder",
        "channel": "email",
        "is_enabled": true,
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "08:00"
      }
    ]
  }'

# 10. Get Analytics
echo -e "\\n\\n${YELLOW}10. Get Analytics${NC}"
curl -X GET "${BASE_URL}/api/${API_VERSION}/notifications/analytics/engagement" \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json"

echo -e "\\n\\n${GREEN}Examples completed!${NC}"
'''
    
    def _generate_requirements(self) -> str:
        """Generate Python requirements."""
        return '''httpx>=0.24.0
pydantic>=2.0.0
python-dateutil>=2.8.0
'''
    
    def _generate_setup_py(self) -> str:
        """Generate setup.py."""
        return '''from setuptools import setup, find_packages

setup(
    name="healthcare-api",
    version="2.0.0",
    description="Healthcare Scheduling API Python SDK",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Healthcare API Team",
    author_email="api-support@healthcare.example.com",
    url="https://github.com/healthcare/api-python-sdk",
    packages=find_packages(),
    install_requires=[
        "httpx>=0.24.0",
        "pydantic>=2.0.0",
        "python-dateutil>=2.8.0",
    ],
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
'''
    
    def _generate_package_json(self) -> Dict[str, Any]:
        """Generate package.json."""
        return {
            "name": "healthcare-api",
            "version": "2.0.0",
            "description": "Healthcare Scheduling API JavaScript SDK",
            "main": "healthcare-api.js",
            "scripts": {
                "test": "echo \"Error: no test specified\" && exit 1"
            },
            "keywords": [
                "healthcare",
                "api",
                "scheduling",
                "appointments",
                "notifications"
            ],
            "author": "Healthcare API Team",
            "license": "MIT",
            "repository": {
                "type": "git",
                "url": "https://github.com/healthcare/api-javascript-sdk"
            },
            "bugs": {
                "url": "https://github.com/healthcare/api-javascript-sdk/issues"
            },
            "homepage": "https://github.com/healthcare/api-javascript-sdk#readme"
        }
    
    def _generate_python_readme(self) -> str:
        """Generate Python README."""
        return '''# Healthcare Scheduling API Python SDK

A Python SDK for the Healthcare Scheduling API that provides easy access to appointment management, user management, and notification features.

## Installation

```bash
pip install healthcare-api
```

## Quick Start

```python
import asyncio
from healthcare_api import HealthcareAPI

async def main():
    async with HealthcareAPI() as api:
        # Login
        await api.login("admin@example.com", "admin123")
        
        # Get appointments
        appointments = await api.get_appointments()
        print(f"Found {len(appointments['data'])} appointments")

asyncio.run(main())
```

## Features

- **Authentication**: JWT-based authentication
- **Appointments**: Create, read, update, and cancel appointments
- **Users**: User management and profile operations
- **Notifications**: Multi-channel notification system
- **Availability**: Doctor schedule management
- **Analytics**: Comprehensive reporting and analytics

## Documentation

Full documentation is available at [https://docs.healthcare.example.com](https://docs.healthcare.example.com)

## Support

For support and questions, contact api-support@healthcare.example.com
'''
    
    def _generate_javascript_readme(self) -> str:
        """Generate JavaScript README."""
        return '''# Healthcare Scheduling API JavaScript SDK

A JavaScript SDK for the Healthcare Scheduling API that provides easy access to appointment management, user management, and notification features.

## Installation

```bash
npm install healthcare-api
```

## Quick Start

```javascript
import { HealthcareAPI } from 'healthcare-api';

const api = new HealthcareAPI();

async function main() {
    try {
        // Login
        await api.login('admin@example.com', 'admin123');
        
        // Get appointments
        const appointments = await api.getAppointments();
        console.log(`Found ${appointments.data?.length || 0} appointments`);
    } catch (error) {
        console.error('API Error:', error.message);
    }
}

main();
```

## Features

- **Authentication**: JWT-based authentication
- **Appointments**: Create, read, update, and cancel appointments
- **Users**: User management and profile operations
- **Notifications**: Multi-channel notification system
- **Availability**: Doctor schedule management
- **Analytics**: Comprehensive reporting and analytics

## Documentation

Full documentation is available at [https://docs.healthcare.example.com](https://docs.healthcare.example.com)

## Support

For support and questions, contact api-support@healthcare.example.com
'''
