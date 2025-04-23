"""Enhanced OpenAPI/Swagger configuration for better developer experience."""

from typing import Dict, Any, Optional
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.responses import HTMLResponse

from app.core.config import settings


def custom_openapi(app: FastAPI) -> Dict[str, Any]:
    """Generate custom OpenAPI schema with enhanced documentation."""
    
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="Healthcare Scheduling API",
        version="2.0.0",
        description="""
        # Healthcare Scheduling API

        A comprehensive, production-ready API for healthcare appointment scheduling and management.

        ## Features

        - **Appointment Management**: Book, reschedule, and cancel appointments
        - **Doctor Availability**: Manage doctor schedules and availability
        - **User Management**: Patient, doctor, and admin user management
        - **Authentication**: JWT-based authentication with role-based access control
        - **Notifications**: Multi-channel notification system with real-time updates
        - **Analytics**: Comprehensive reporting and analytics
        - **HIPAA Compliance**: Security and audit logging for healthcare data

        ## Authentication

        This API uses JWT (JSON Web Token) authentication. Include the token in the Authorization header:

        ```
        Authorization: Bearer <your-jwt-token>
        ```

        ## Rate Limiting

        API endpoints are rate-limited to prevent abuse. Rate limits vary by endpoint and user role.

        ## Error Handling

        The API uses standard HTTP status codes and returns detailed error information in JSON format.

        ## Support

        For support and questions, contact the development team.
        """,
        routes=app.routes,
        servers=[
            {
                "url": "https://api.healthcare.example.com",
                "description": "Production server"
            },
            {
                "url": "https://staging-api.healthcare.example.com",
                "description": "Staging server"
            },
            {
                "url": "http://localhost:8000",
                "description": "Development server"
            }
        ]
    )
    
    # Add custom tags for better organization
    openapi_schema["tags"] = [
        {
            "name": "authentication",
            "description": "User authentication and authorization endpoints"
        },
        {
            "name": "users",
            "description": "User management and profile operations"
        },
        {
            "name": "availability",
            "description": "Doctor availability and schedule management"
        },
        {
            "name": "appointments",
            "description": "Appointment booking and management"
        },
        {
            "name": "advanced-appointments",
            "description": "Advanced appointment features (recurring, waitlist, templates)"
        },
        {
            "name": "notifications",
            "description": "Notification system and user engagement"
        },
        {
            "name": "admin",
            "description": "Administrative functions and system management"
        }
    ]
    
    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT token for API authentication"
        },
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "API key for service-to-service authentication"
        }
    }
    
    # Add global security requirement
    openapi_schema["security"] = [{"BearerAuth": []}]
    
    # Add examples for common request/response patterns
    openapi_schema["components"]["examples"] = {
        "UserExample": {
            "summary": "Example User",
            "value": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "email": "john.doe@example.com",
                "full_name": "John Doe",
                "role": "patient",
                "is_active": True,
                "created_at": "2024-01-15T10:30:00Z"
            }
        },
        "AppointmentExample": {
            "summary": "Example Appointment",
            "value": {
                "id": "123e4567-e89b-12d3-a456-426614174001",
                "patient_id": "123e4567-e89b-12d3-a456-426614174000",
                "doctor_id": "123e4567-e89b-12d3-a456-426614174002",
                "start_time": "2024-01-20T14:00:00Z",
                "end_time": "2024-01-20T15:00:00Z",
                "status": "scheduled",
                "reason_for_visit": "Annual checkup",
                "created_at": "2024-01-15T10:30:00Z"
            }
        },
        "ErrorExample": {
            "summary": "Example Error Response",
            "value": {
                "detail": "User not found",
                "error_code": "USER_NOT_FOUND",
                "timestamp": "2024-01-15T10:30:00Z",
                "request_id": "req_123456789"
            }
        }
    }
    
    # Add external documentation links
    openapi_schema["externalDocs"] = {
        "description": "API Documentation",
        "url": "https://docs.healthcare.example.com"
    }
    
    # Add contact information
    openapi_schema["info"]["contact"] = {
        "name": "Healthcare API Support",
        "email": "api-support@healthcare.example.com",
        "url": "https://healthcare.example.com/support"
    }
    
    # Add license information
    openapi_schema["info"]["license"] = {
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT"
    }
    
    # Add terms of service
    openapi_schema["info"]["termsOfService"] = "https://healthcare.example.com/terms"
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


def get_fixed_swagger_ui_html(
    openapi_url: str,
    title: str = "API docs",
    swagger_js_url: str = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
    swagger_css_url: str = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
    swagger_favicon_url: str = "https://fastapi.tiangolo.com/img/favicon.png",
    oauth2_redirect_url: Optional[str] = None,
    init_oauth: Optional[Dict[str, Any]] = None
) -> HTMLResponse:
    """Generate fixed Swagger UI HTML with corrected JavaScript and error handling."""
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <link type="text/css" rel="stylesheet" href="{swagger_css_url}">
    <link rel="shortcut icon" href="{swagger_favicon_url}">
    <title>{title}</title>
    <style>
        .swagger-ui .topbar {{ display: none; }}
        .loading {{ text-align: center; padding: 20px; }}
        .error {{ color: red; padding: 20px; }}
    </style>
    </head>
    <body>
    <div id="swagger-ui">
        <div class="loading">Loading API documentation...</div>
    </div>
    <script src="{swagger_js_url}"></script>
    <script>
    console.log('Swagger UI script loaded');
    
    // Check if SwaggerUIBundle is available
    if (typeof SwaggerUIBundle === 'undefined') {{
        document.getElementById('swagger-ui').innerHTML = '<div class="error">Failed to load Swagger UI. Please check your internet connection.</div>';
        console.error('SwaggerUIBundle is not defined');
    }} else {{
        console.log('SwaggerUIBundle is available, initializing...');
        
        try {{
            const ui = SwaggerUIBundle({{
                url: '{openapi_url}',
                dom_id: '#swagger-ui',
                layout: 'BaseLayout',
                deepLinking: true,
                showExtensions: true,
                showCommonExtensions: true,
                oauth2RedirectUrl: window.location.origin + '/docs/oauth2-redirect',
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIBundle.presets.standalone
                ],
                onComplete: function() {{
                    console.log('Swagger UI loaded successfully');
                }},
                onFailure: function(data) {{
                    console.error('Swagger UI failed to load:', data);
                    document.getElementById('swagger-ui').innerHTML = '<div class="error">Failed to load API documentation. Error: ' + JSON.stringify(data) + '</div>';
                }}
            }});
        }} catch (error) {{
            console.error('Error initializing Swagger UI:', error);
            document.getElementById('swagger-ui').innerHTML = '<div class="error">Error initializing Swagger UI: ' + error.message + '</div>';
        }}
    }}
    </script>
    </body>
    </html>
    """
    
    return HTMLResponse(html)


def get_simple_docs_html(
    openapi_url: str,
    title: str = "API Documentation"
) -> HTMLResponse:
    """Generate a simple documentation page with basic API information."""
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{title}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
            .header {{ background: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
            .endpoint {{ background: #f8f9fa; padding: 15px; margin: 10px 0; border-left: 4px solid #3498db; border-radius: 4px; }}
            .method {{ font-weight: bold; color: #27ae60; }}
            .path {{ font-family: monospace; background: #ecf0f1; padding: 2px 6px; border-radius: 3px; }}
            .description {{ color: #7f8c8d; margin-top: 5px; }}
            .links {{ margin-top: 30px; }}
            .links a {{ display: inline-block; margin: 10px 15px 10px 0; padding: 10px 20px; background: #3498db; color: white; text-decoration: none; border-radius: 5px; }}
            .links a:hover {{ background: #2980b9; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🏥 {title}</h1>
            <p>Comprehensive API for healthcare appointment scheduling and management</p>
        </div>
        
        <h2>📚 Available Documentation</h2>
        <div class="links">
            <a href="/docs" target="_blank">Interactive Swagger UI</a>
            <a href="/redoc" target="_blank">ReDoc Documentation</a>
            <a href="/openapi.json" target="_blank">OpenAPI Schema (JSON)</a>
            <a href="/api-info" target="_blank">API Information</a>
        </div>
        
        <h2>🔗 Quick Links</h2>
        <div class="endpoint">
            <div class="method">GET</div>
            <div class="path">/health</div>
            <div class="description">Health check endpoint</div>
        </div>
        
        <div class="endpoint">
            <div class="method">GET</div>
            <div class="path">/api/v1/health</div>
            <div class="description">API health check</div>
        </div>
        
        <div class="endpoint">
            <div class="method">POST</div>
            <div class="path">/api/v1/auth/token</div>
            <div class="description">Get authentication token</div>
        </div>
        
        <div class="endpoint">
            <div class="method">GET</div>
            <div class="path">/api/v1/appointments</div>
            <div class="description">List appointments (requires authentication)</div>
        </div>
        
        <h2>🔧 Troubleshooting</h2>
        <p>If the interactive documentation is not loading:</p>
        <ul>
            <li>Check your browser's developer console for JavaScript errors</li>
            <li>Ensure you have an active internet connection (Swagger UI loads external resources)</li>
            <li>Try refreshing the page</li>
            <li>Use the <a href="/docs-simple">simple documentation</a> as a fallback</li>
        </ul>
        
        <h2>📖 API Usage</h2>
        <p>To use this API:</p>
        <ol>
            <li>Get an authentication token from <code>/api/v1/auth/token</code></li>
            <li>Include the token in the <code>Authorization: Bearer &lt;token&gt;</code> header</li>
            <li>Make requests to the protected endpoints</li>
        </ol>
        
        <script>
        // Test if OpenAPI schema is accessible
        fetch('{openapi_url}')
            .then(response => response.json())
            .then(data => {{
                console.log('OpenAPI schema loaded successfully:', data.info.title);
                document.body.insertAdjacentHTML('beforeend', '<p style="color: green;">✅ OpenAPI schema is accessible</p>');
            }})
            .catch(error => {{
                console.error('Failed to load OpenAPI schema:', error);
                document.body.insertAdjacentHTML('beforeend', '<p style="color: red;">❌ OpenAPI schema not accessible: ' + error.message + '</p>');
            }});
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(html)


def get_enhanced_swagger_ui_html(
    openapi_url: str,
    title: str = "Healthcare Scheduling API",
    oauth2_redirect_url: Optional[str] = None,
    init_oauth: Optional[Dict[str, Any]] = None,
    swagger_js_url: str = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui-bundle.js",
    swagger_css_url: str = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui.css",
    swagger_favicon_url: str = "https://fastapi.tiangolo.com/img/favicon.png",
    **kwargs
) -> HTMLResponse:
    """Generate enhanced Swagger UI HTML with custom configuration."""
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <link type="text/css" rel="stylesheet" href="{swagger_css_url}">
        <link rel="shortcut icon" href="{swagger_favicon_url}">
        <title>{title}</title>
        <style>
            .swagger-ui .topbar { display: none; }
            .swagger-ui .info { margin: 20px 0; }
            .swagger-ui .info .title { color: #2c3e50; }
            .swagger-ui .scheme-container { background: #f8f9fa; padding: 10px; border-radius: 4px; margin: 10px 0; }
            .swagger-ui .btn.authorize { background-color: #3498db; border-color: #3498db; }
            .swagger-ui .btn.authorize:hover { background-color: #2980b9; border-color: #2980b9; }
            .swagger-ui .btn.execute { background-color: #27ae60; border-color: #27ae60; }
            .swagger-ui .btn.execute:hover { background-color: #229954; border-color: #229954; }
            .custom-header { 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white; 
                padding: 20px; 
                text-align: center; 
                margin-bottom: 20px;
                border-radius: 8px;
            }
            .custom-header h1 { margin: 0; font-size: 2.5em; }
            .custom-header p { margin: 10px 0 0 0; opacity: 0.9; }
            .api-info { 
                background: #f8f9fa; 
                padding: 15px; 
                border-radius: 4px; 
                margin: 20px 0; 
                border-left: 4px solid #3498db;
            }
        </style>
    </head>
    <body>
        <div class="custom-header">
            <h1>🏥 Healthcare Scheduling API</h1>
            <p>Comprehensive API for healthcare appointment management and patient engagement</p>
        </div>
        
        <div class="api-info">
            <h3>🚀 Quick Start</h3>
            <p><strong>Base URL:</strong> <code>https://api.healthcare.example.com</code></p>
            <p><strong>Authentication:</strong> Include JWT token in Authorization header: <code>Bearer &lt;token&gt;</code></p>
            <p><strong>Rate Limiting:</strong> 100 requests per minute per user (varies by endpoint)</p>
            <p><strong>Support:</strong> <a href="mailto:api-support@healthcare.example.com">api-support@healthcare.example.com</a></p>
        </div>
        
        <div id="swagger-ui">
        </div>
        
        <script src="{swagger_js_url}"></script>
        <script>
        const ui = SwaggerUIBundle({{
            url: '{openapi_url}',
            dom_id: '#swagger-ui',
            deepLinking: true,
            presets: [
                SwaggerUIBundle.presets.apis,
                SwaggerUIBundle.SwaggerUIStandalonePreset
            ],
            plugins: [
                SwaggerUIBundle.plugins.DownloadUrl
            ],
            layout: "StandaloneLayout",
            validatorUrl: null,
            oauth2RedirectUrl: '{oauth2_redirect_url or ""}',
            initOAuth: {init_oauth or "{}"},
            docExpansion: "list",
            operationsSorter: "alpha",
            tagsSorter: "alpha",
            filter: true,
            showRequestHeaders: true,
            showCommonExtensions: true,
            tryItOutEnabled: true,
            requestInterceptor: (req) => {{
                // Add custom headers or modify requests
                req.headers['X-Requested-With'] = 'SwaggerUI';
                return req;
            }},
            responseInterceptor: (res) => {{
                // Handle responses
                return res;
            }},
            onComplete: () => {{
                // Custom initialization
                console.log('Healthcare API Documentation loaded');
            }}
        }});
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(html)


def get_enhanced_redoc_html(
    openapi_url: str,
    title: str = "Healthcare Scheduling API",
    redoc_js_url: str = "https://cdn.jsdelivr.net/npm/redoc@2.1.3/bundles/redoc.standalone.js",
    redoc_favicon_url: str = "https://fastapi.tiangolo.com/img/favicon.png",
    **kwargs
) -> HTMLResponse:
    """Generate enhanced ReDoc HTML with custom configuration."""
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{title}</title>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link rel="shortcut icon" href="{redoc_favicon_url}">
        <style>
            body {{
                margin: 0;
                padding: 0;
            }}
            .custom-header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                text-align: center;
                position: sticky;
                top: 0;
                z-index: 1000;
            }}
            .custom-header h1 {{
                margin: 0;
                font-size: 2.5em;
            }}
            .custom-header p {{
                margin: 10px 0 0 0;
                opacity: 0.9;
            }}
        </style>
    </head>
    <body>
        <div class="custom-header">
            <h1>🏥 Healthcare Scheduling API</h1>
            <p>Comprehensive API for healthcare appointment management and patient engagement</p>
        </div>
        <redoc spec-url="{openapi_url}"></redoc>
        <script src="{redoc_js_url}"></script>
    </body>
    </html>
    """
    
    return HTMLResponse(html)


def add_enhanced_docs_routes(app: FastAPI) -> None:
    """Add enhanced documentation routes to the FastAPI app."""
    
    # Fix the broken default FastAPI Swagger UI by providing a corrected version
    @app.get("/docs", include_in_schema=False)
    async def fixed_swagger_ui_html():
        return get_fixed_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=app.title + " - Swagger UI",
            oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        )
    
    # Add a simple fallback docs page
    @app.get("/docs-simple", include_in_schema=False)
    async def simple_docs_html():
        return get_simple_docs_html(
            openapi_url=app.openapi_url,
            title=app.title
        )
    
    @app.get("/redoc", include_in_schema=False)
    async def custom_redoc_html():
        return get_enhanced_redoc_html(
            openapi_url=app.openapi_url,
            title="Healthcare Scheduling API"
        )
    
    @app.get("/openapi.json", include_in_schema=False)
    async def get_openapi_json():
        """Get OpenAPI schema as JSON."""
        return app.openapi()
    
    @app.get("/api-info", include_in_schema=False)
    async def get_api_info():
        """Get API information and status."""
        return {
            "name": "Healthcare Scheduling API",
            "version": "2.0.0",
            "description": "Comprehensive API for healthcare appointment management",
            "status": "operational",
            "uptime": "99.9%",
            "last_updated": "2024-01-16T00:00:00Z",
            "endpoints": {
                "total": len(app.routes),
                "documented": len([r for r in app.routes if hasattr(r, 'endpoint')]),
                "authentication_required": len([r for r in app.routes if hasattr(r, 'dependencies')])
            },
            "features": [
                "JWT Authentication",
                "Role-based Access Control",
                "Rate Limiting",
                "Real-time Notifications",
                "Comprehensive Analytics",
                "HIPAA Compliance",
                "Multi-channel Communication"
            ],
            "documentation": {
                "swagger_ui": "/docs",
                "redoc": "/redoc",
                "openapi_json": "/openapi.json"
            }
        }
