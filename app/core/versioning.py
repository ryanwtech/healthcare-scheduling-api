"""API versioning and deprecation handling for better developer experience."""

import warnings
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from enum import Enum
from functools import wraps

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.core.logging import get_logger
from app.core.exceptions import APIException, ErrorCode

logger = get_logger(__name__)


class APIVersion(str, Enum):
    """Supported API versions."""
    V1 = "v1"
    V2 = "v2"
    LATEST = "v2"


class VersionStatus(str, Enum):
    """Version status types."""
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    SUNSET = "sunset"
    RETIRED = "retired"


class VersionInfo:
    """Version information container."""
    
    def __init__(
        self,
        version: str,
        status: VersionStatus,
        release_date: datetime,
        deprecation_date: Optional[datetime] = None,
        sunset_date: Optional[datetime] = None,
        retirement_date: Optional[datetime] = None,
        migration_guide: Optional[str] = None,
        changelog: Optional[List[Dict[str, Any]]] = None
    ):
        self.version = version
        self.status = status
        self.release_date = release_date
        self.deprecation_date = deprecation_date
        self.sunset_date = sunset_date
        self.retirement_date = retirement_date
        self.migration_guide = migration_guide
        self.changelog = changelog or []
    
    def is_deprecated(self) -> bool:
        """Check if version is deprecated."""
        return self.status in [VersionStatus.DEPRECATED, VersionStatus.SUNSET, VersionStatus.RETIRED]
    
    def is_sunset(self) -> bool:
        """Check if version is in sunset period."""
        return self.status in [VersionStatus.SUNSET, VersionStatus.RETIRED]
    
    def is_retired(self) -> bool:
        """Check if version is retired."""
        return self.status == VersionStatus.RETIRED
    
    def get_deprecation_warning(self) -> Optional[str]:
        """Get deprecation warning message."""
        if not self.is_deprecated():
            return None
        
        warning = f"API version {self.version} is {self.status.value}"
        
        if self.sunset_date:
            warning += f". Sunset date: {self.sunset_date.isoformat()}"
        
        if self.migration_guide:
            warning += f". Migration guide: {self.migration_guide}"
        
        return warning


class APIVersionManager:
    """Manages API versions and deprecation."""
    
    def __init__(self):
        self.versions: Dict[str, VersionInfo] = {}
        self._initialize_versions()
    
    def _initialize_versions(self):
        """Initialize version information."""
        # Version 1 - Deprecated
        self.versions["v1"] = VersionInfo(
            version="v1",
            status=VersionStatus.DEPRECATED,
            release_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
            deprecation_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            sunset_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
            retirement_date=datetime(2024, 12, 31, tzinfo=timezone.utc),
            migration_guide="https://docs.healthcare.example.com/migration/v1-to-v2",
            changelog=[
                {
                    "version": "1.0.0",
                    "date": "2023-01-01",
                    "changes": ["Initial API release"]
                },
                {
                    "version": "1.1.0",
                    "date": "2023-06-01",
                    "changes": ["Added notification system", "Enhanced authentication"]
                },
                {
                    "version": "1.2.0",
                    "date": "2023-12-01",
                    "changes": ["Added advanced appointment features", "HIPAA compliance improvements"]
                }
            ]
        )
        
        # Version 2 - Active
        self.versions["v2"] = VersionInfo(
            version="v2",
            status=VersionStatus.ACTIVE,
            release_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            changelog=[
                {
                    "version": "2.0.0",
                    "date": "2024-01-01",
                    "changes": [
                        "Complete API redesign",
                        "Enhanced validation and error handling",
                        "Improved developer experience",
                        "Better documentation and examples",
                        "Advanced notification system",
                        "Comprehensive analytics"
                    ]
                },
                {
                    "version": "2.1.0",
                    "date": "2024-01-16",
                    "changes": [
                        "Added real-time notifications",
                        "Enhanced engagement analytics",
                        "Improved API versioning",
                        "Better error handling"
                    ]
                }
            ]
        )
    
    def get_version_info(self, version: str) -> Optional[VersionInfo]:
        """Get version information."""
        return self.versions.get(version)
    
    def get_supported_versions(self) -> List[str]:
        """Get list of supported versions."""
        return [v for v in self.versions.keys() if not self.versions[v].is_retired()]
    
    def get_latest_version(self) -> str:
        """Get latest version."""
        active_versions = [v for v in self.versions.keys() if self.versions[v].status == VersionStatus.ACTIVE]
        return active_versions[-1] if active_versions else "v2"
    
    def is_version_supported(self, version: str) -> bool:
        """Check if version is supported."""
        version_info = self.get_version_info(version)
        return version_info is not None and not version_info.is_retired()
    
    def get_version_warning(self, version: str) -> Optional[str]:
        """Get version warning message."""
        version_info = self.get_version_info(version)
        if version_info:
            return version_info.get_deprecation_warning()
        return None


# Global version manager instance
version_manager = APIVersionManager()


def get_api_version(api_version: str = Header("v2", alias="API-Version")) -> str:
    """Dependency to get API version from header."""
    if not version_manager.is_version_supported(api_version):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported API version: {api_version}. Supported versions: {version_manager.get_supported_versions()}"
        )
    
    return api_version


def check_version_deprecation(version: str) -> Optional[str]:
    """Check if version is deprecated and return warning."""
    return version_manager.get_version_warning(version)


def add_version_headers(response: JSONResponse, version: str) -> JSONResponse:
    """Add version headers to response."""
    version_info = version_manager.get_version_info(version)
    if version_info:
        response.headers["API-Version"] = version
        response.headers["API-Status"] = version_info.status.value
        
        if version_info.is_deprecated():
            warning = version_info.get_deprecation_warning()
            if warning:
                response.headers["API-Warning"] = warning
        
        if version_info.sunset_date:
            response.headers["API-Sunset"] = version_info.sunset_date.isoformat()
    
    return response


def deprecated_endpoint(
    deprecated_version: str,
    replacement_version: str,
    removal_date: Optional[datetime] = None,
    migration_guide: Optional[str] = None
):
    """Decorator to mark endpoints as deprecated."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get request from kwargs if available
            request = kwargs.get('request')
            if request:
                # Add deprecation warning to response headers
                warning = f"Endpoint is deprecated in {deprecated_version}. Use {replacement_version} instead."
                if removal_date:
                    warning += f" Will be removed on {removal_date.isoformat()}."
                if migration_guide:
                    warning += f" See {migration_guide} for migration guide."
                
                # Log deprecation warning
                logger.warning(
                    f"Deprecated endpoint accessed: {request.url.path}",
                    extra={
                        "deprecated_version": deprecated_version,
                        "replacement_version": replacement_version,
                        "removal_date": removal_date.isoformat() if removal_date else None,
                        "migration_guide": migration_guide
                    }
                )
            
            return await func(*args, **kwargs)
        
        # Add deprecation metadata to function
        wrapper._deprecated = True
        wrapper._deprecated_version = deprecated_version
        wrapper._replacement_version = replacement_version
        wrapper._removal_date = removal_date
        wrapper._migration_guide = migration_guide
        
        return wrapper
    return decorator


def version_router(
    version: str,
    prefix: str = "",
    tags: Optional[List[str]] = None,
    deprecated: bool = False
) -> APIRouter:
    """Create a versioned router."""
    
    router = APIRouter(
        prefix=f"/{version}{prefix}",
        tags=tags or [f"API {version.upper()}"],
        deprecated=deprecated
    )
    
    # Add version information to router
    router.version = version
    router.version_info = version_manager.get_version_info(version)
    
    return router


class VersionedResponse(JSONResponse):
    """Versioned response with automatic header injection."""
    
    def __init__(
        self,
        content: Any,
        version: str,
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ):
        super().__init__(content, status_code, headers, **kwargs)
        add_version_headers(self, version)


def get_version_info_endpoint(version: str) -> Dict[str, Any]:
    """Get version information endpoint."""
    version_info = version_manager.get_version_info(version)
    if not version_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version} not found"
        )
    
    return {
        "version": version_info.version,
        "status": version_info.status.value,
        "release_date": version_info.release_date.isoformat(),
        "deprecation_date": version_info.deprecation_date.isoformat() if version_info.deprecation_date else None,
        "sunset_date": version_info.sunset_date.isoformat() if version_info.sunset_date else None,
        "retirement_date": version_info.retirement_date.isoformat() if version_info.retirement_date else None,
        "migration_guide": version_info.migration_guide,
        "changelog": version_info.changelog,
        "is_deprecated": version_info.is_deprecated(),
        "is_sunset": version_info.is_sunset(),
        "is_retired": version_info.is_retired()
    }


def get_all_versions_endpoint() -> Dict[str, Any]:
    """Get all versions information endpoint."""
    return {
        "supported_versions": version_manager.get_supported_versions(),
        "latest_version": version_manager.get_latest_version(),
        "versions": {
            version: get_version_info_endpoint(version)
            for version in version_manager.versions.keys()
        }
    }


class VersionMiddleware:
    """Middleware to handle version-specific logic."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            request = Request(scope, receive)
            
            # Extract version from path
            path = request.url.path
            version = self._extract_version_from_path(path)
            
            if version:
                # Check if version is supported
                if not version_manager.is_version_supported(version):
                    response = JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={
                            "detail": f"Unsupported API version: {version}",
                            "supported_versions": version_manager.get_supported_versions()
                        }
                    )
                    await response(scope, receive, send)
                    return
                
                # Check for deprecation warnings
                warning = version_manager.get_version_warning(version)
                if warning:
                    # Add warning to response headers
                    scope["headers"].append((b"api-warning", warning.encode()))
            
            # Add version to request state
            scope["state"]["api_version"] = version
        
        await self.app(scope, receive, send)
    
    def _extract_version_from_path(self, path: str) -> Optional[str]:
        """Extract version from URL path."""
        parts = path.strip("/").split("/")
        if len(parts) > 0 and parts[0].startswith("v") and parts[0][1:].isdigit():
            return parts[0]
        return None


# Version-specific utilities
class VersionUtils:
    """Utilities for version-specific functionality."""
    
    @staticmethod
    def get_version_specific_config(version: str, config_key: str, default: Any = None) -> Any:
        """Get version-specific configuration."""
        version_configs = {
            "v1": {
                "max_page_size": 50,
                "default_page_size": 20,
                "rate_limit_per_minute": 100,
                "enable_websockets": False,
                "enable_analytics": False
            },
            "v2": {
                "max_page_size": 100,
                "default_page_size": 20,
                "rate_limit_per_minute": 200,
                "enable_websockets": True,
                "enable_analytics": True
            }
        }
        
        version_config = version_configs.get(version, {})
        return version_config.get(config_key, default)
    
    @staticmethod
    def get_version_specific_validation_rules(version: str) -> Dict[str, Any]:
        """Get version-specific validation rules."""
        validation_rules = {
            "v1": {
                "email_validation": "basic",
                "phone_validation": "basic",
                "uuid_validation": "strict",
                "date_validation": "basic"
            },
            "v2": {
                "email_validation": "strict",
                "phone_validation": "international",
                "uuid_validation": "strict",
                "date_validation": "strict",
                "timezone_validation": "enabled",
                "business_hours_validation": "enabled"
            }
        }
        
        return validation_rules.get(version, validation_rules["v2"])
    
    @staticmethod
    def get_version_specific_features(version: str) -> List[str]:
        """Get version-specific features."""
        features = {
            "v1": [
                "basic_appointments",
                "user_management",
                "authentication",
                "basic_notifications"
            ],
            "v2": [
                "basic_appointments",
                "advanced_appointments",
                "user_management",
                "authentication",
                "comprehensive_notifications",
                "real_time_notifications",
                "analytics",
                "engagement_tracking",
                "api_versioning",
                "enhanced_validation",
                "comprehensive_error_handling"
            ]
        }
        
        return features.get(version, features["v2"])


# Version compatibility utilities
class CompatibilityUtils:
    """Utilities for handling version compatibility."""
    
    @staticmethod
    def transform_request_data(data: Dict[str, Any], from_version: str, to_version: str) -> Dict[str, Any]:
        """Transform request data between versions."""
        if from_version == to_version:
            return data
        
        # Transform from v1 to v2
        if from_version == "v1" and to_version == "v2":
            return CompatibilityUtils._transform_v1_to_v2(data)
        
        # Transform from v2 to v1
        if from_version == "v2" and to_version == "v1":
            return CompatibilityUtils._transform_v2_to_v1(data)
        
        return data
    
    @staticmethod
    def _transform_v1_to_v2(data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform v1 data to v2 format."""
        transformed = data.copy()
        
        # Add version-specific transformations here
        # Example: field name changes, structure changes, etc.
        
        return transformed
    
    @staticmethod
    def _transform_v2_to_v1(data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform v2 data to v1 format."""
        transformed = data.copy()
        
        # Add version-specific transformations here
        # Example: field name changes, structure changes, etc.
        
        return transformed
    
    @staticmethod
    def get_compatibility_matrix() -> Dict[str, Dict[str, bool]]:
        """Get compatibility matrix between versions."""
        return {
            "v1": {
                "v1": True,
                "v2": True  # v1 can be transformed to v2
            },
            "v2": {
                "v1": False,  # v2 cannot be transformed to v1 (loss of features)
                "v2": True
            }
        }
