"""Appointment template service for common appointment types."""

import uuid
from datetime import datetime, timedelta, UTC
from enum import Enum
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models import Appointment, AppointmentStatus, DoctorProfile, User
from app.db.schemas import AppointmentCreate
from app.security.audit import AuditLogger, get_audit_logger

logger = get_logger(__name__)


class AppointmentType(str, Enum):
    """Types of appointment templates."""
    CONSULTATION = "consultation"
    FOLLOW_UP = "follow_up"
    CHECKUP = "checkup"
    EMERGENCY = "emergency"
    PROCEDURE = "procedure"
    THERAPY = "therapy"
    VACCINATION = "vaccination"
    SCREENING = "screening"
    SPECIALIST = "specialist"
    TELEHEALTH = "telehealth"


class AppointmentTemplate:
    """Appointment template for common appointment types."""
    
    def __init__(
        self,
        id: uuid.UUID,
        name: str,
        appointment_type: AppointmentType,
        duration_minutes: int,
        description: str,
        preparation_instructions: Optional[str] = None,
        follow_up_required: bool = False,
        follow_up_days: Optional[int] = None,
        required_documents: Optional[List[str]] = None,
        special_requirements: Optional[List[str]] = None,
        created_by: uuid.UUID = None,
        is_active: bool = True
    ):
        self.id = id
        self.name = name
        self.appointment_type = appointment_type
        self.duration_minutes = duration_minutes
        self.description = description
        self.preparation_instructions = preparation_instructions
        self.follow_up_required = follow_up_required
        self.follow_up_days = follow_up_days
        self.required_documents = required_documents or []
        self.special_requirements = special_requirements or []
        self.created_by = created_by
        self.is_active = is_active
        self.created_at = datetime.now(UTC)


class AppointmentTemplateService:
    """Service for managing appointment templates."""
    
    def __init__(self, db: Session):
        self.db = db
        self.audit_logger = get_audit_logger(db)
        self.templates: Dict[uuid.UUID, AppointmentTemplate] = {}
        self._initialize_default_templates()
    
    def _initialize_default_templates(self) -> None:
        """Initialize default appointment templates."""
        default_templates = [
            AppointmentTemplate(
                id=uuid.uuid4(),
                name="General Consultation",
                appointment_type=AppointmentType.CONSULTATION,
                duration_minutes=30,
                description="General medical consultation with doctor",
                preparation_instructions="Please bring your ID and insurance card. Arrive 15 minutes early.",
                follow_up_required=False,
                required_documents=["ID", "Insurance Card"],
                special_requirements=[]
            ),
            AppointmentTemplate(
                id=uuid.uuid4(),
                name="Follow-up Visit",
                appointment_type=AppointmentType.FOLLOW_UP,
                duration_minutes=20,
                description="Follow-up visit to check on previous treatment",
                preparation_instructions="Please bring any test results or reports from your last visit.",
                follow_up_required=False,
                required_documents=["Previous Test Results"],
                special_requirements=[]
            ),
            AppointmentTemplate(
                id=uuid.uuid4(),
                name="Annual Checkup",
                appointment_type=AppointmentType.CHECKUP,
                duration_minutes=60,
                description="Comprehensive annual health checkup",
                preparation_instructions="Please fast for 12 hours before the appointment. Bring a list of current medications.",
                follow_up_required=True,
                follow_up_days=30,
                required_documents=["ID", "Insurance Card", "Medication List"],
                special_requirements=["Fasting Required"]
            ),
            AppointmentTemplate(
                id=uuid.uuid4(),
                name="Emergency Visit",
                appointment_type=AppointmentType.EMERGENCY,
                duration_minutes=45,
                description="Emergency medical consultation",
                preparation_instructions="Please come immediately. Bring any relevant medical records.",
                follow_up_required=True,
                follow_up_days=7,
                required_documents=["ID", "Emergency Contact Info"],
                special_requirements=["Urgent Care"]
            ),
            AppointmentTemplate(
                id=uuid.uuid4(),
                name="Minor Procedure",
                appointment_type=AppointmentType.PROCEDURE,
                duration_minutes=90,
                description="Minor medical procedure",
                preparation_instructions="Please follow pre-procedure instructions provided by your doctor.",
                follow_up_required=True,
                follow_up_days=14,
                required_documents=["ID", "Insurance Card", "Consent Forms"],
                special_requirements=["Procedure Consent", "Pre-procedure Instructions"]
            ),
            AppointmentTemplate(
                id=uuid.uuid4(),
                name="Physical Therapy Session",
                appointment_type=AppointmentType.THERAPY,
                duration_minutes=45,
                description="Physical therapy session",
                preparation_instructions="Wear comfortable clothing suitable for exercise. Bring any assistive devices.",
                follow_up_required=True,
                follow_up_days=7,
                required_documents=["ID", "Insurance Card", "Prescription"],
                special_requirements=["Comfortable Clothing", "Assistive Devices"]
            ),
            AppointmentTemplate(
                id=uuid.uuid4(),
                name="Vaccination",
                appointment_type=AppointmentType.VACCINATION,
                duration_minutes=15,
                description="Vaccination appointment",
                preparation_instructions="Please bring your vaccination record. Inform staff of any allergies.",
                follow_up_required=False,
                required_documents=["ID", "Vaccination Record"],
                special_requirements=["Allergy Information"]
            ),
            AppointmentTemplate(
                id=uuid.uuid4(),
                name="Health Screening",
                appointment_type=AppointmentType.SCREENING,
                duration_minutes=30,
                description="Preventive health screening",
                preparation_instructions="Follow any specific preparation instructions for the screening test.",
                follow_up_required=True,
                follow_up_days=14,
                required_documents=["ID", "Insurance Card"],
                special_requirements=["Screening Preparation"]
            ),
            AppointmentTemplate(
                id=uuid.uuid4(),
                name="Specialist Consultation",
                appointment_type=AppointmentType.SPECIALIST,
                duration_minutes=60,
                description="Consultation with medical specialist",
                preparation_instructions="Please bring referral letter and all relevant medical records.",
                follow_up_required=True,
                follow_up_days=30,
                required_documents=["ID", "Insurance Card", "Referral Letter", "Medical Records"],
                special_requirements=["Referral Required"]
            ),
            AppointmentTemplate(
                id=uuid.uuid4(),
                name="Telehealth Consultation",
                appointment_type=AppointmentType.TELEHEALTH,
                duration_minutes=30,
                description="Remote consultation via video call",
                preparation_instructions="Ensure you have a stable internet connection and a quiet, private space.",
                follow_up_required=False,
                required_documents=["ID"],
                special_requirements=["Stable Internet", "Private Space", "Video Call Capable Device"]
            )
        ]
        
        for template in default_templates:
            self.templates[template.id] = template
    
    def create_template(
        self,
        name: str,
        appointment_type: AppointmentType,
        duration_minutes: int,
        description: str,
        preparation_instructions: Optional[str] = None,
        follow_up_required: bool = False,
        follow_up_days: Optional[int] = None,
        required_documents: Optional[List[str]] = None,
        special_requirements: Optional[List[str]] = None,
        created_by: uuid.UUID = None
    ) -> AppointmentTemplate:
        """Create a new appointment template."""
        try:
            template_id = uuid.uuid4()
            
            template = AppointmentTemplate(
                id=template_id,
                name=name,
                appointment_type=appointment_type,
                duration_minutes=duration_minutes,
                description=description,
                preparation_instructions=preparation_instructions,
                follow_up_required=follow_up_required,
                follow_up_days=follow_up_days,
                required_documents=required_documents or [],
                special_requirements=special_requirements or [],
                created_by=created_by
            )
            
            self.templates[template_id] = template
            
            # Log template creation
            self.audit_logger.log_event(
                event_type="phi_created",
                user_id=created_by,
                resource_id=template_id,
                resource_type="appointment_template",
                action="template_created",
                details={
                    "name": name,
                    "type": appointment_type.value,
                    "duration_minutes": duration_minutes
                },
                success=True
            )
            
            logger.info(f"Created appointment template: {name}")
            return template
            
        except Exception as e:
            logger.error(f"Failed to create appointment template: {e}")
            raise
    
    def get_template(self, template_id: uuid.UUID) -> Optional[AppointmentTemplate]:
        """Get appointment template by ID."""
        return self.templates.get(template_id)
    
    def get_templates_by_type(self, appointment_type: AppointmentType) -> List[AppointmentTemplate]:
        """Get templates by appointment type."""
        return [
            template for template in self.templates.values()
            if template.appointment_type == appointment_type and template.is_active
        ]
    
    def get_all_templates(self) -> List[AppointmentTemplate]:
        """Get all active templates."""
        return [
            template for template in self.templates.values()
            if template.is_active
        ]
    
    def update_template(
        self,
        template_id: uuid.UUID,
        name: Optional[str] = None,
        duration_minutes: Optional[int] = None,
        description: Optional[str] = None,
        preparation_instructions: Optional[str] = None,
        follow_up_required: Optional[bool] = None,
        follow_up_days: Optional[int] = None,
        required_documents: Optional[List[str]] = None,
        special_requirements: Optional[List[str]] = None,
        updated_by: uuid.UUID = None
    ) -> Optional[AppointmentTemplate]:
        """Update an existing template."""
        try:
            template = self.templates.get(template_id)
            if not template:
                return None
            
            # Update fields
            if name is not None:
                template.name = name
            if duration_minutes is not None:
                template.duration_minutes = duration_minutes
            if description is not None:
                template.description = description
            if preparation_instructions is not None:
                template.preparation_instructions = preparation_instructions
            if follow_up_required is not None:
                template.follow_up_required = follow_up_required
            if follow_up_days is not None:
                template.follow_up_days = follow_up_days
            if required_documents is not None:
                template.required_documents = required_documents
            if special_requirements is not None:
                template.special_requirements = special_requirements
            
            # Log template update
            self.audit_logger.log_event(
                event_type="phi_updated",
                user_id=updated_by,
                resource_id=template_id,
                resource_type="appointment_template",
                action="template_updated",
                details={
                    "name": template.name,
                    "duration_minutes": template.duration_minutes
                },
                success=True
            )
            
            logger.info(f"Updated appointment template: {template.name}")
            return template
            
        except Exception as e:
            logger.error(f"Failed to update appointment template: {e}")
            raise
    
    def delete_template(self, template_id: uuid.UUID, deleted_by: uuid.UUID = None) -> bool:
        """Delete (deactivate) a template."""
        try:
            template = self.templates.get(template_id)
            if not template:
                return False
            
            template.is_active = False
            
            # Log template deletion
            self.audit_logger.log_event(
                event_type="phi_deleted",
                user_id=deleted_by,
                resource_id=template_id,
                resource_type="appointment_template",
                action="template_deleted",
                details={"name": template.name},
                success=True
            )
            
            logger.info(f"Deleted appointment template: {template.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete appointment template: {e}")
            return False
    
    def create_appointment_from_template(
        self,
        template_id: uuid.UUID,
        doctor_id: uuid.UUID,
        patient_id: uuid.UUID,
        start_time: datetime,
        notes: Optional[str] = None,
        created_by: uuid.UUID = None
    ) -> Optional[AppointmentCreate]:
        """Create appointment data from template."""
        try:
            template = self.get_template(template_id)
            if not template or not template.is_active:
                return None
            
            # Calculate end time
            end_time = start_time + timedelta(minutes=template.duration_minutes)
            
            # Create appointment data
            appointment_data = AppointmentCreate(
                doctor_id=doctor_id,
                patient_id=patient_id,
                start_time=start_time,
                end_time=end_time,
                notes=notes or template.description
            )
            
            # Log template usage
            self.audit_logger.log_event(
                event_type="phi_access",
                user_id=created_by,
                action="template_used",
                details={
                    "template_id": str(template_id),
                    "template_name": template.name,
                    "appointment_type": template.appointment_type.value,
                    "duration_minutes": template.duration_minutes
                },
                success=True
            )
            
            logger.info(f"Created appointment from template: {template.name}")
            return appointment_data
            
        except Exception as e:
            logger.error(f"Failed to create appointment from template: {e}")
            return None
    
    def get_template_recommendations(
        self,
        patient_id: uuid.UUID,
        doctor_id: uuid.UUID,
        appointment_purpose: Optional[str] = None
    ) -> List[AppointmentTemplate]:
        """Get template recommendations based on context."""
        try:
            recommendations = []
            
            # Get patient's appointment history
            patient_appointments = (
                self.db.query(Appointment)
                .filter(
                    Appointment.patient_id == patient_id,
                    Appointment.doctor_id == doctor_id
                )
                .order_by(Appointment.created_at.desc())
                .limit(5)
                .all()
            )
            
            # Get doctor's specialization
            doctor_profile = (
                self.db.query(DoctorProfile)
                .filter(DoctorProfile.id == doctor_id)
                .first()
            )
            
            # Recommend based on appointment purpose
            if appointment_purpose:
                purpose_lower = appointment_purpose.lower()
                
                if "consultation" in purpose_lower or "general" in purpose_lower:
                    recommendations.extend(self.get_templates_by_type(AppointmentType.CONSULTATION))
                elif "follow" in purpose_lower or "check" in purpose_lower:
                    recommendations.extend(self.get_templates_by_type(AppointmentType.FOLLOW_UP))
                elif "emergency" in purpose_lower or "urgent" in purpose_lower:
                    recommendations.extend(self.get_templates_by_type(AppointmentType.EMERGENCY))
                elif "procedure" in purpose_lower or "surgery" in purpose_lower:
                    recommendations.extend(self.get_templates_by_type(AppointmentType.PROCEDURE))
                elif "therapy" in purpose_lower or "rehabilitation" in purpose_lower:
                    recommendations.extend(self.get_templates_by_type(AppointmentType.THERAPY))
                elif "vaccine" in purpose_lower or "immunization" in purpose_lower:
                    recommendations.extend(self.get_templates_by_type(AppointmentType.VACCINATION))
                elif "screening" in purpose_lower or "test" in purpose_lower:
                    recommendations.extend(self.get_templates_by_type(AppointmentType.SCREENING))
                elif "specialist" in purpose_lower or "referral" in purpose_lower:
                    recommendations.extend(self.get_templates_by_type(AppointmentType.SPECIALIST))
                elif "telehealth" in purpose_lower or "remote" in purpose_lower:
                    recommendations.extend(self.get_templates_by_type(AppointmentType.TELEHEALTH))
            
            # If no specific purpose, recommend based on history
            if not recommendations and patient_appointments:
                # Recommend follow-up if recent appointments
                last_appointment = patient_appointments[0]
                days_since_last = (datetime.now(UTC) - last_appointment.created_at).days
                
                if days_since_last < 30:
                    recommendations.extend(self.get_templates_by_type(AppointmentType.FOLLOW_UP))
                else:
                    recommendations.extend(self.get_templates_by_type(AppointmentType.CHECKUP))
            
            # If still no recommendations, suggest general consultation
            if not recommendations:
                recommendations.extend(self.get_templates_by_type(AppointmentType.CONSULTATION))
            
            # Remove duplicates and limit results
            unique_recommendations = []
            seen_ids = set()
            for template in recommendations:
                if template.id not in seen_ids:
                    unique_recommendations.append(template)
                    seen_ids.add(template.id)
            
            return unique_recommendations[:5]  # Limit to 5 recommendations
            
        except Exception as e:
            logger.error(f"Failed to get template recommendations: {e}")
            return []
    
    def get_template_statistics(self) -> Dict[str, int]:
        """Get template usage statistics."""
        try:
            stats = {
                "total_templates": len(self.templates),
                "active_templates": len([t for t in self.templates.values() if t.is_active]),
                "templates_by_type": {}
            }
            
            # Count by type
            for template in self.templates.values():
                if template.is_active:
                    template_type = template.appointment_type.value
                    stats["templates_by_type"][template_type] = stats["templates_by_type"].get(template_type, 0) + 1
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get template statistics: {e}")
            return {}


def get_appointment_template_service(db: Session) -> AppointmentTemplateService:
    """Get appointment template service instance."""
    return AppointmentTemplateService(db)
