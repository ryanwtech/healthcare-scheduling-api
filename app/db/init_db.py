"""Database initialization script."""

import uuid

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import get_password_hash
from app.db.base import SessionLocal
from app.db.models import User, UserRole

logger = get_logger(__name__)


def init_db() -> None:
    """Initialize database with admin user if not exists."""
    db = SessionLocal()
    try:
        # Check if admin user already exists
        admin_user = db.query(User).filter(
            User.email == settings.first_superuser_email
        ).first()
        
        if admin_user:
            logger.info("Admin user already exists, skipping creation")
            return
        
        # Create admin user
        admin_user = User(
            id=uuid.uuid4(),
            email=settings.first_superuser_email,
            hashed_password=get_password_hash(settings.first_superuser_password),
            full_name="System Administrator",
            role=UserRole.ADMIN,
            is_active=True
        )
        
        db.add(admin_user)
        db.commit()
        
        logger.info(
            "Admin user created successfully",
            email=settings.first_superuser_email
        )
        
    except Exception as e:
        logger.error("Failed to create admin user", error=str(e))
        db.rollback()
        raise
    finally:
        db.close()


def create_indexes() -> None:
    """Create additional database indexes for performance."""
    db = SessionLocal()
    try:
        # Additional indexes can be created here if needed
        # For now, the basic indexes are created by Alembic
        logger.info("Database indexes are up to date")
        
    except Exception as e:
        logger.error("Failed to create indexes", error=str(e))
        raise
    finally:
        db.close()


def main() -> None:
    """Main initialization function."""
    logger.info("Initializing database...")
    
    try:
        # Create indexes
        create_indexes()
        
        # Create admin user
        init_db()
        
        logger.info("Database initialization completed successfully")
        
    except Exception as e:
        logger.error("Database initialization failed", error=str(e))
        raise


if __name__ == "__main__":
    main()
