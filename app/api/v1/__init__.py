"""API v1 router configuration."""

from fastapi import APIRouter

from .admin import router as admin_router
from .advanced_appointments import router as advanced_appointments_router
from .appointments import router as appointments_router
from .auth import router as auth_router
from .availability import router as availability_router
from .notifications import router as notifications_router
from .testing import router as testing_router
from .users import router as users_router

# Create the main API router
api_router = APIRouter()

# Health check endpoint
@api_router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "message": "Healthcare Scheduling API is running"}

# Placeholder for future subrouters
# from .providers import router as providers_router
# from .patients import router as patients_router

# Include routers
api_router.include_router(auth_router, tags=["authentication"])
api_router.include_router(users_router, tags=["users"])
api_router.include_router(availability_router, tags=["availability"])
api_router.include_router(appointments_router, tags=["appointments"])
api_router.include_router(advanced_appointments_router, prefix="/advanced", tags=["advanced-appointments"])
api_router.include_router(notifications_router, prefix="/notifications", tags=["notifications"])
api_router.include_router(testing_router, prefix="/testing", tags=["testing"])
api_router.include_router(admin_router, tags=["admin"])

# api_router.include_router(auth_router, prefix="/auth", tags=["authentication"])
# api_router.include_router(users_router, prefix="/users", tags=["users"])
# api_router.include_router(appointments_router, prefix="/appointments", tags=["appointments"])
# api_router.include_router(providers_router, prefix="/providers", tags=["providers"])
# api_router.include_router(patients_router, prefix="/patients", tags=["patients"])
