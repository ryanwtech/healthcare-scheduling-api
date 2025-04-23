"""Security headers and HTTPS enforcement for HIPAA compliance."""

from typing import Dict, List

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers for HIPAA compliance."""
    
    def __init__(self, app, app_name: str = "healthcare_api"):
        super().__init__(app)
        self.app_name = app_name
    
    async def dispatch(self, request: Request, call_next):
        """Add security headers to response."""
        response = await call_next(request)
        
        # Add security headers
        self._add_security_headers(response)
        
        return response
    
    def _add_security_headers(self, response: Response) -> None:
        """Add comprehensive security headers."""
        headers = self._get_security_headers()
        
        for header_name, header_value in headers.items():
            response.headers[header_name] = header_value
    
    def _get_security_headers(self) -> Dict[str, str]:
        """Get security headers configuration."""
        return {
            # Prevent clickjacking
            "X-Frame-Options": "DENY",
            
            # Prevent MIME type sniffing
            "X-Content-Type-Options": "nosniff",
            
            # Enable XSS protection
            "X-XSS-Protection": "1; mode=block",
            
            # Referrer policy
            "Referrer-Policy": "strict-origin-when-cross-origin",
            
            # Content Security Policy
            "Content-Security-Policy": self._get_csp_header(),
            
            # Strict Transport Security (HTTPS only)
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
            
            # Permissions Policy
            "Permissions-Policy": self._get_permissions_policy(),
            
            # Cache control for sensitive data
            "Cache-Control": "no-store, no-cache, must-revalidate, private",
            "Pragma": "no-cache",
            "Expires": "0",
            
            # Server information hiding
            "Server": self.app_name,
            
            # Cross-Origin policies
            "Cross-Origin-Embedder-Policy": "require-corp",
            "Cross-Origin-Opener-Policy": "same-origin",
            "Cross-Origin-Resource-Policy": "same-origin",
        }
    
    def _get_csp_header(self) -> str:
        """Get Content Security Policy header."""
        # In production, you'd want to be more restrictive
        if settings.is_production:
            return (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; "
                "font-src 'self'; "
                "connect-src 'self'; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'"
            )
        else:
            # More permissive for development - allow external CDN resources for Swagger UI
            return (
                "default-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
                "img-src 'self' data: blob: https://fastapi.tiangolo.com; "
                "font-src 'self' data: https://fonts.gstatic.com; "
                "connect-src 'self' ws: wss:; "
                "frame-ancestors 'none'"
            )
    
    def _get_permissions_policy(self) -> str:
        """Get Permissions Policy header."""
        return (
            "accelerometer=(), "
            "ambient-light-sensor=(), "
            "autoplay=(), "
            "battery=(), "
            "camera=(), "
            "cross-origin-isolated=(), "
            "display-capture=(), "
            "document-domain=(), "
            "encrypted-media=(), "
            "execution-while-not-rendered=(), "
            "execution-while-out-of-viewport=(), "
            "fullscreen=(), "
            "geolocation=(), "
            "gyroscope=(), "
            "keyboard-map=(), "
            "magnetometer=(), "
            "microphone=(), "
            "midi=(), "
            "navigation-override=(), "
            "payment=(), "
            "picture-in-picture=(), "
            "publickey-credentials-get=(), "
            "screen-wake-lock=(), "
            "sync-xhr=(), "
            "usb=(), "
            "web-share=(), "
            "xr-spatial-tracking=()"
        )


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """Middleware to redirect HTTP to HTTPS in production."""
    
    def __init__(self, app):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next):
        """Redirect HTTP to HTTPS in production."""
        # Only redirect in production
        if settings.is_production and request.url.scheme == "http":
            # Redirect to HTTPS
            https_url = request.url.replace(scheme="https")
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url=str(https_url), status_code=301)
        
        return await call_next(request)


class HIPAAComplianceMiddleware(BaseHTTPMiddleware):
    """Middleware for HIPAA-specific compliance measures."""
    
    def __init__(self, app):
        super().__init__(app)
        self.sensitive_paths = [
            "/api/v1/users/",
            "/api/v1/appointments/",
            "/api/v1/patients/",
            "/api/v1/medical-records/",
            "/api/v1/audit/"
        ]
    
    async def dispatch(self, request: Request, call_next):
        """Apply HIPAA compliance measures."""
        response = await call_next(request)
        
        # Add HIPAA-specific headers for sensitive endpoints
        if self._is_sensitive_endpoint(request.url.path):
            self._add_hipaa_headers(response)
        
        return response
    
    def _is_sensitive_endpoint(self, path: str) -> bool:
        """Check if endpoint contains PHI."""
        return any(sensitive_path in path for sensitive_path in self.sensitive_paths)
    
    def _add_hipaa_headers(self, response: Response) -> None:
        """Add HIPAA-specific security headers."""
        # Additional headers for PHI endpoints
        response.headers.update({
            # Ensure no caching of PHI
            "Cache-Control": "no-store, no-cache, must-revalidate, private, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            
            # Prevent PHI from being indexed
            "X-Robots-Tag": "noindex, nofollow, nosnippet, noarchive",
            
            # Additional security for PHI
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            
            # Ensure secure transmission
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
        })


def get_security_headers() -> Dict[str, str]:
    """Get security headers for manual application."""
    middleware = SecurityHeadersMiddleware(None)
    return middleware._get_security_headers()


def get_hipaa_headers() -> Dict[str, str]:
    """Get HIPAA-specific headers."""
    return {
        "Cache-Control": "no-store, no-cache, must-revalidate, private, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
        "X-Robots-Tag": "noindex, nofollow, nosnippet, noarchive",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    }


def is_secure_request(request: Request) -> bool:
    """Check if request is secure (HTTPS)."""
    return (
        request.url.scheme == "https" or
        request.headers.get("x-forwarded-proto") == "https" or
        request.headers.get("x-forwarded-ssl") == "on"
    )


def require_https(request: Request) -> bool:
    """Check if request requires HTTPS (for PHI endpoints)."""
    sensitive_paths = [
        "/api/v1/users/",
        "/api/v1/appointments/",
        "/api/v1/patients/",
        "/api/v1/medical-records/",
        "/api/v1/audit/"
    ]
    
    return any(sensitive_path in request.url.path for sensitive_path in sensitive_paths)
