"""Database seeding script for development and testing."""

import sys
import uuid
from datetime import datetime, timedelta, UTC
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.base import SessionLocal, engine
from app.db.models import Base, DoctorProfile, User, UserRole, Availability


def create_tables():
    """Create all database tables if they don't exist."""
    Base.metadata.create_all(bind=engine)


def get_db_session() -> Session:
    """Get database session."""
    return SessionLocal()


def seed_admin_user(db: Session) -> User:
    """Create or get admin user from environment variables."""
    # Check if admin already exists
    admin = db.query(User).filter(User.email == settings.first_superuser_email).first()
    
    if admin:
        print(f"✓ Admin user already exists: {admin.email}")
        return admin
    
    # Create admin user
    admin = User(
        id=uuid.uuid4(),
        email=settings.first_superuser_email,
        hashed_password=get_password_hash(settings.first_superuser_password),
        full_name="System Administrator",
        role=UserRole.ADMIN,
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC)
    )
    
    db.add(admin)
    db.commit()
    db.refresh(admin)
    
    print(f"✓ Created admin user: {admin.email}")
    return admin


def seed_sample_doctor(db: Session) -> tuple[User, DoctorProfile]:
    """Create or get sample doctor (Dr. Ada Lovelace)."""
    doctor_email = "ada.lovelace@healthcare.com"
    
    # Check if doctor already exists
    doctor_user = db.query(User).filter(User.email == doctor_email).first()
    
    if doctor_user:
        print(f"✓ Doctor user already exists: {doctor_user.email}")
        doctor_profile = db.query(DoctorProfile).filter(DoctorProfile.user_id == doctor_user.id).first()
        if doctor_profile:
            print(f"✓ Doctor profile already exists for: {doctor_user.email}")
            return doctor_user, doctor_profile
    else:
        # Create doctor user
        doctor_user = User(
            id=uuid.uuid4(),
            email=doctor_email,
            hashed_password=get_password_hash("doctor123"),
            full_name="Dr. Ada Lovelace",
            role=UserRole.DOCTOR,
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.utcnow()
        )
        
        db.add(doctor_user)
        db.commit()
        db.refresh(doctor_user)
        print(f"✓ Created doctor user: {doctor_user.email}")
    
    # Create doctor profile
    doctor_profile = DoctorProfile(
        id=uuid.uuid4(),
        user_id=doctor_user.id,
        specialization="Cardiology",
        timezone="America/Chicago",
        created_at=datetime.now(UTC)
    )
    
    db.add(doctor_profile)
    db.commit()
    db.refresh(doctor_profile)
    
    print(f"✓ Created doctor profile: {doctor_profile.specialization}")
    return doctor_user, doctor_profile


def seed_sample_patient(db: Session) -> User:
    """Create or get sample patient."""
    patient_email = "john.doe@example.com"
    
    # Check if patient already exists
    patient = db.query(User).filter(User.email == patient_email).first()
    
    if patient:
        print(f"✓ Patient user already exists: {patient.email}")
        return patient
    
    # Create patient user
    patient = User(
        id=uuid.uuid4(),
        email=patient_email,
        hashed_password=get_password_hash("patient123"),
        full_name="John Doe",
        role=UserRole.PATIENT,
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC)
    )
    
    db.add(patient)
    db.commit()
    db.refresh(patient)
    
    print(f"✓ Created patient user: {patient.email}")
    return patient


def seed_doctor_availability(db: Session, doctor_profile: DoctorProfile, days: int = 7):
    """Create availability slots for the doctor for the next N days."""
    # Check if availability already exists for this doctor
    existing_availability = db.query(Availability).filter(
        Availability.doctor_id == doctor_profile.id
    ).first()
    
    if existing_availability:
        print(f"✓ Availability already exists for doctor: {doctor_profile.user.full_name}")
        return
    
    # Create availability for the next N days
    base_date = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    
    for day_offset in range(days):
        current_date = base_date + timedelta(days=day_offset)
        
        # Skip weekends (Saturday=5, Sunday=6)
        if current_date.weekday() >= 5:
            continue
        
        # Morning slot: 9:00 AM - 12:00 PM
        morning_start = current_date.replace(hour=9, minute=0)
        morning_end = current_date.replace(hour=12, minute=0)
        
        morning_availability = Availability(
            id=uuid.uuid4(),
            doctor_id=doctor_profile.id,
            start_time=morning_start,
            end_time=morning_end,
            created_at=datetime.now(UTC)
        )
        
        # Afternoon slot: 1:00 PM - 5:00 PM
        afternoon_start = current_date.replace(hour=13, minute=0)
        afternoon_end = current_date.replace(hour=17, minute=0)
        
        afternoon_availability = Availability(
            id=uuid.uuid4(),
            doctor_id=doctor_profile.id,
            start_time=afternoon_start,
            end_time=afternoon_end,
            created_at=datetime.now(UTC)
        )
        
        db.add(morning_availability)
        db.add(afternoon_availability)
        
        print(f"✓ Created availability for {current_date.strftime('%Y-%m-%d')}: 9:00-12:00, 13:00-17:00")
    
    db.commit()
    print(f"✓ Created {days} days of availability for Dr. {doctor_profile.user.full_name}")


def main():
    """Main seeding function."""
    print("🌱 Starting database seeding...")
    
    try:
        # Create tables
        create_tables()
        print("✓ Database tables created/verified")
        
        # Get database session
        db = get_db_session()
        
        try:
            # Seed admin user
            admin = seed_admin_user(db)
            
            # Seed sample doctor
            doctor_user, doctor_profile = seed_sample_doctor(db)
            
            # Seed sample patient
            patient = seed_sample_patient(db)
            
            # Seed doctor availability
            seed_doctor_availability(db, doctor_profile, days=7)
            
            print("\n🎉 Database seeding completed successfully!")
            print("\n📋 Created users:")
            print(f"  • Admin: {admin.email} (password: {settings.first_superuser_password})")
            print(f"  • Doctor: {doctor_user.email} (password: doctor123)")
            print(f"  • Patient: {patient.email} (password: patient123)")
            print(f"\n📅 Doctor availability: 7 days with 2 slots per day (9:00-12:00, 13:00-17:00)")
            print(f"🏥 Specialization: {doctor_profile.specialization}")
            print(f"🌍 Timezone: {doctor_profile.timezone}")
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ Error during seeding: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
