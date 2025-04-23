"""Notification templates and personalization service."""

import uuid
from datetime import datetime, UTC
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.notification_models import (
    NotificationChannel,
    NotificationTemplate,
    NotificationType,
)
from app.security.audit import AuditLogger, get_audit_logger

logger = get_logger(__name__)


class NotificationTemplateService:
    """Service for managing notification templates and personalization."""
    
    def __init__(self, db: Session):
        self.db = db
        self.audit_logger = get_audit_logger(db)
        self._initialize_default_templates()
    
    def _initialize_default_templates(self) -> None:
        """Initialize default notification templates."""
        default_templates = [
            # Appointment Reminders
            {
                "name": "Appointment Reminder - 24 Hours",
                "notification_type": NotificationType.APPOINTMENT_REMINDER,
                "channel": NotificationChannel.EMAIL,
                "subject": "Appointment Reminder - Tomorrow at {{appointment_time}}",
                "content": """
Hello {{patient_name}},

This is a reminder that you have an appointment with Dr. {{doctor_name}} tomorrow.

Appointment Details:
- Date: {{appointment_date}}
- Time: {{appointment_time}}
- Duration: {{appointment_duration}}
- Location: {{clinic_address}}

Please arrive 15 minutes early for check-in.

If you need to reschedule or cancel, please contact us at {{clinic_phone}} or reply to this email.

Thank you!
{{clinic_name}}
                """,
                "html_content": """
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .header { background-color: #f4f4f4; padding: 20px; text-align: center; }
        .content { padding: 20px; }
        .appointment-details { background-color: #e8f4f8; padding: 15px; border-radius: 5px; margin: 20px 0; }
        .footer { background-color: #f4f4f4; padding: 20px; text-align: center; font-size: 12px; }
    </style>
</head>
<body>
    <div class="header">
        <h2>Appointment Reminder</h2>
    </div>
    <div class="content">
        <p>Hello {{patient_name}},</p>
        <p>This is a reminder that you have an appointment with Dr. {{doctor_name}} tomorrow.</p>
        
        <div class="appointment-details">
            <h3>Appointment Details:</h3>
            <p><strong>Date:</strong> {{appointment_date}}</p>
            <p><strong>Time:</strong> {{appointment_time}}</p>
            <p><strong>Duration:</strong> {{appointment_duration}}</p>
            <p><strong>Location:</strong> {{clinic_address}}</p>
        </div>
        
        <p>Please arrive 15 minutes early for check-in.</p>
        <p>If you need to reschedule or cancel, please contact us at {{clinic_phone}} or reply to this email.</p>
        <p>Thank you!</p>
        <p>{{clinic_name}}</p>
    </div>
    <div class="footer">
        <p>This is an automated message. Please do not reply to this email.</p>
    </div>
</body>
</html>
                """,
                "variables": ["patient_name", "doctor_name", "appointment_date", "appointment_time", "appointment_duration", "clinic_address", "clinic_phone", "clinic_name"]
            },
            {
                "name": "Appointment Confirmation",
                "notification_type": NotificationType.APPOINTMENT_CONFIRMATION,
                "channel": NotificationChannel.EMAIL,
                "subject": "Appointment Confirmed - {{appointment_date}}",
                "content": """
Hello {{patient_name}},

Your appointment has been confirmed!

Appointment Details:
- Doctor: Dr. {{doctor_name}}
- Date: {{appointment_date}}
- Time: {{appointment_time}}
- Duration: {{appointment_duration}}
- Location: {{clinic_address}}

Please arrive 15 minutes early for check-in.

Thank you for choosing {{clinic_name}}!
                """,
                "html_content": """
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .header { background-color: #4CAF50; color: white; padding: 20px; text-align: center; }
        .content { padding: 20px; }
        .appointment-details { background-color: #e8f5e8; padding: 15px; border-radius: 5px; margin: 20px 0; }
        .footer { background-color: #f4f4f4; padding: 20px; text-align: center; font-size: 12px; }
    </style>
</head>
<body>
    <div class="header">
        <h2>✅ Appointment Confirmed</h2>
    </div>
    <div class="content">
        <p>Hello {{patient_name}},</p>
        <p>Your appointment has been confirmed!</p>
        
        <div class="appointment-details">
            <h3>Appointment Details:</h3>
            <p><strong>Doctor:</strong> Dr. {{doctor_name}}</p>
            <p><strong>Date:</strong> {{appointment_date}}</p>
            <p><strong>Time:</strong> {{appointment_time}}</p>
            <p><strong>Duration:</strong> {{appointment_duration}}</p>
            <p><strong>Location:</strong> {{clinic_address}}</p>
        </div>
        
        <p>Please arrive 15 minutes early for check-in.</p>
        <p>Thank you for choosing {{clinic_name}}!</p>
    </div>
    <div class="footer">
        <p>This is an automated message. Please do not reply to this email.</p>
    </div>
</body>
</html>
                """,
                "variables": ["patient_name", "doctor_name", "appointment_date", "appointment_time", "appointment_duration", "clinic_address", "clinic_name"]
            },
            {
                "name": "Waitlist Notification",
                "notification_type": NotificationType.WAITLIST_NOTIFICATION,
                "channel": NotificationChannel.SMS,
                "subject": "Appointment Available!",
                "content": "Hi {{patient_name}}! A time slot with Dr. {{doctor_name}} is now available for {{appointment_date}} at {{appointment_time}}. Reply 'BOOK' to confirm or 'SKIP' to pass. Expires in {{expiry_minutes}} minutes.",
                "html_content": None,
                "variables": ["patient_name", "doctor_name", "appointment_date", "appointment_time", "expiry_minutes"]
            },
            {
                "name": "Welcome Message",
                "notification_type": NotificationType.WELCOME,
                "channel": NotificationChannel.EMAIL,
                "subject": "Welcome to {{clinic_name}}!",
                "content": """
Welcome to {{clinic_name}}, {{patient_name}}!

We're excited to have you as a new patient. Here's what you can expect:

1. Easy online appointment booking
2. Appointment reminders via email and SMS
3. Secure access to your health records
4. 24/7 customer support

To get started, please complete your profile and book your first appointment.

If you have any questions, don't hesitate to contact us at {{clinic_phone}}.

Welcome aboard!
The {{clinic_name}} Team
                """,
                "html_content": """
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .header { background-color: #2196F3; color: white; padding: 20px; text-align: center; }
        .content { padding: 20px; }
        .features { background-color: #f0f8ff; padding: 15px; border-radius: 5px; margin: 20px 0; }
        .footer { background-color: #f4f4f4; padding: 20px; text-align: center; font-size: 12px; }
    </style>
</head>
<body>
    <div class="header">
        <h2>🎉 Welcome to {{clinic_name}}!</h2>
    </div>
    <div class="content">
        <p>Welcome to {{clinic_name}}, {{patient_name}}!</p>
        <p>We're excited to have you as a new patient. Here's what you can expect:</p>
        
        <div class="features">
            <h3>Our Services:</h3>
            <ul>
                <li>Easy online appointment booking</li>
                <li>Appointment reminders via email and SMS</li>
                <li>Secure access to your health records</li>
                <li>24/7 customer support</li>
            </ul>
        </div>
        
        <p>To get started, please complete your profile and book your first appointment.</p>
        <p>If you have any questions, don't hesitate to contact us at {{clinic_phone}}.</p>
        <p>Welcome aboard!</p>
        <p>The {{clinic_name}} Team</p>
    </div>
    <div class="footer">
        <p>This is an automated message. Please do not reply to this email.</p>
    </div>
</body>
</html>
                """,
                "variables": ["patient_name", "clinic_name", "clinic_phone"]
            },
            {
                "name": "Payment Reminder",
                "notification_type": NotificationType.PAYMENT_REMINDER,
                "channel": NotificationChannel.EMAIL,
                "subject": "Payment Reminder - {{amount_due}}",
                "content": """
Hello {{patient_name}},

This is a friendly reminder that you have an outstanding balance of {{amount_due}} for services provided on {{service_date}}.

Payment Details:
- Amount Due: {{amount_due}}
- Service Date: {{service_date}}
- Invoice Number: {{invoice_number}}
- Due Date: {{due_date}}

You can pay online at {{payment_url}} or contact us at {{clinic_phone}}.

Thank you for your prompt attention to this matter.

{{clinic_name}}
                """,
                "html_content": """
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .header { background-color: #FF9800; color: white; padding: 20px; text-align: center; }
        .content { padding: 20px; }
        .payment-details { background-color: #fff3e0; padding: 15px; border-radius: 5px; margin: 20px 0; }
        .cta-button { background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 10px 0; }
        .footer { background-color: #f4f4f4; padding: 20px; text-align: center; font-size: 12px; }
    </style>
</head>
<body>
    <div class="header">
        <h2>💳 Payment Reminder</h2>
    </div>
    <div class="content">
        <p>Hello {{patient_name}},</p>
        <p>This is a friendly reminder that you have an outstanding balance of <strong>{{amount_due}}</strong> for services provided on {{service_date}}.</p>
        
        <div class="payment-details">
            <h3>Payment Details:</h3>
            <p><strong>Amount Due:</strong> {{amount_due}}</p>
            <p><strong>Service Date:</strong> {{service_date}}</p>
            <p><strong>Invoice Number:</strong> {{invoice_number}}</p>
            <p><strong>Due Date:</strong> {{due_date}}</p>
        </div>
        
        <p>You can pay online or contact us for assistance.</p>
        <a href="{{payment_url}}" class="cta-button">Pay Now</a>
        <p>Or contact us at {{clinic_phone}}.</p>
        <p>Thank you for your prompt attention to this matter.</p>
        <p>{{clinic_name}}</p>
    </div>
    <div class="footer">
        <p>This is an automated message. Please do not reply to this email.</p>
    </div>
</body>
</html>
                """,
                "variables": ["patient_name", "amount_due", "service_date", "invoice_number", "due_date", "payment_url", "clinic_phone", "clinic_name"]
            }
        ]
        
        # Create templates if they don't exist
        for template_data in default_templates:
            existing = self.db.query(NotificationTemplate).filter(
                NotificationTemplate.name == template_data["name"],
                NotificationTemplate.channel == template_data["channel"]
            ).first()
            
            if not existing:
                template = NotificationTemplate(
                    id=uuid.uuid4(),
                    name=template_data["name"],
                    notification_type=template_data["notification_type"],
                    channel=template_data["channel"],
                    subject=template_data["subject"],
                    content=template_data["content"],
                    html_content=template_data["html_content"],
                    variables=template_data["variables"],
                    is_active=True
                )
                
                self.db.add(template)
        
        self.db.commit()
    
    def create_template(
        self,
        name: str,
        notification_type: NotificationType,
        channel: NotificationChannel,
        subject: Optional[str],
        content: str,
        html_content: Optional[str] = None,
        variables: Optional[List[str]] = None,
        created_by: Optional[uuid.UUID] = None
    ) -> NotificationTemplate:
        """Create a new notification template."""
        try:
            template = NotificationTemplate(
                id=uuid.uuid4(),
                name=name,
                notification_type=notification_type,
                channel=channel,
                subject=subject,
                content=content,
                html_content=html_content,
                variables=variables or [],
                is_active=True
            )
            
            self.db.add(template)
            self.db.commit()
            
            # Log template creation
            self.audit_logger.log_event(
                event_type="phi_created",
                user_id=created_by,
                resource_id=template.id,
                resource_type="notification_template",
                action="template_created",
                details={
                    "name": name,
                    "type": notification_type.value,
                    "channel": channel.value
                },
                success=True
            )
            
            logger.info(f"Created notification template: {name}")
            return template
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create notification template: {e}")
            raise
    
    def get_template(
        self,
        template_id: uuid.UUID
    ) -> Optional[NotificationTemplate]:
        """Get notification template by ID."""
        return self.db.query(NotificationTemplate).filter(
            NotificationTemplate.id == template_id,
            NotificationTemplate.is_active == True
        ).first()
    
    def get_templates_by_type(
        self,
        notification_type: NotificationType,
        channel: Optional[NotificationChannel] = None
    ) -> List[NotificationTemplate]:
        """Get templates by notification type and channel."""
        query = self.db.query(NotificationTemplate).filter(
            NotificationTemplate.notification_type == notification_type,
            NotificationTemplate.is_active == True
        )
        
        if channel:
            query = query.filter(NotificationTemplate.channel == channel)
        
        return query.all()
    
    def get_all_templates(self) -> List[NotificationTemplate]:
        """Get all active templates."""
        return self.db.query(NotificationTemplate).filter(
            NotificationTemplate.is_active == True
        ).all()
    
    def update_template(
        self,
        template_id: uuid.UUID,
        name: Optional[str] = None,
        subject: Optional[str] = None,
        content: Optional[str] = None,
        html_content: Optional[str] = None,
        variables: Optional[List[str]] = None,
        is_active: Optional[bool] = None,
        updated_by: Optional[uuid.UUID] = None
    ) -> Optional[NotificationTemplate]:
        """Update notification template."""
        try:
            template = self.db.query(NotificationTemplate).filter(
                NotificationTemplate.id == template_id
            ).first()
            
            if not template:
                return None
            
            # Update fields
            if name is not None:
                template.name = name
            if subject is not None:
                template.subject = subject
            if content is not None:
                template.content = content
            if html_content is not None:
                template.html_content = html_content
            if variables is not None:
                template.variables = variables
            if is_active is not None:
                template.is_active = is_active
            
            template.updated_at = datetime.now(UTC)
            
            self.db.commit()
            
            # Log template update
            self.audit_logger.log_event(
                event_type="phi_updated",
                user_id=updated_by,
                resource_id=template_id,
                resource_type="notification_template",
                action="template_updated",
                details={"name": template.name},
                success=True
            )
            
            logger.info(f"Updated notification template: {template.name}")
            return template
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update notification template: {e}")
            raise
    
    def delete_template(
        self,
        template_id: uuid.UUID,
        deleted_by: Optional[uuid.UUID] = None
    ) -> bool:
        """Delete (deactivate) notification template."""
        try:
            template = self.db.query(NotificationTemplate).filter(
                NotificationTemplate.id == template_id
            ).first()
            
            if not template:
                return False
            
            template.is_active = False
            template.updated_at = datetime.now(UTC)
            
            self.db.commit()
            
            # Log template deletion
            self.audit_logger.log_event(
                event_type="phi_deleted",
                user_id=deleted_by,
                resource_id=template_id,
                resource_type="notification_template",
                action="template_deleted",
                details={"name": template.name},
                success=True
            )
            
            logger.info(f"Deleted notification template: {template.name}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to delete notification template: {e}")
            return False
    
    def personalize_content(
        self,
        template: NotificationTemplate,
        user_data: Dict,
        custom_variables: Optional[Dict] = None
    ) -> Dict[str, str]:
        """
        Personalize template content with user data.
        
        Args:
            template: Notification template
            user_data: User data for personalization
            custom_variables: Additional custom variables
            
        Returns:
            Dictionary with personalized subject, content, and html_content
        """
        try:
            # Merge user data with custom variables
            variables = {**user_data}
            if custom_variables:
                variables.update(custom_variables)
            
            # Personalize subject
            personalized_subject = self._replace_variables(
                template.subject or "", variables
            )
            
            # Personalize content
            personalized_content = self._replace_variables(
                template.content, variables
            )
            
            # Personalize HTML content
            personalized_html = None
            if template.html_content:
                personalized_html = self._replace_variables(
                    template.html_content, variables
                )
            
            return {
                "subject": personalized_subject,
                "content": personalized_content,
                "html_content": personalized_html
            }
            
        except Exception as e:
            logger.error(f"Failed to personalize content: {e}")
            return {
                "subject": template.subject or "",
                "content": template.content,
                "html_content": template.html_content
            }
    
    def _replace_variables(self, text: str, variables: Dict) -> str:
        """Replace template variables with actual values."""
        try:
            if not text:
                return text
            
            result = text
            
            for key, value in variables.items():
                if value is not None:
                    placeholder = f"{{{{{key}}}}}"
                    result = result.replace(placeholder, str(value))
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to replace variables: {e}")
            return text
    
    def get_template_statistics(self) -> Dict:
        """Get template usage statistics."""
        try:
            templates = self.db.query(NotificationTemplate).filter(
                NotificationTemplate.is_active == True
            ).all()
            
            stats = {
                "total_templates": len(templates),
                "by_type": {},
                "by_channel": {},
                "templates_with_html": len([t for t in templates if t.html_content])
            }
            
            # Count by type
            for template in templates:
                template_type = template.notification_type.value
                stats["by_type"][template_type] = stats["by_type"].get(template_type, 0) + 1
            
            # Count by channel
            for template in templates:
                channel = template.channel.value
                stats["by_channel"][channel] = stats["by_channel"].get(channel, 0) + 1
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get template statistics: {e}")
            return {}
    
    def validate_template(self, template: NotificationTemplate) -> Dict[str, List[str]]:
        """Validate template for completeness and correctness."""
        errors = []
        warnings = []
        
        try:
            # Check required fields
            if not template.name:
                errors.append("Template name is required")
            
            if not template.content:
                errors.append("Template content is required")
            
            if template.channel == NotificationChannel.EMAIL and not template.subject:
                warnings.append("Email templates should have a subject")
            
            # Check for undefined variables
            if template.variables:
                content_variables = self._extract_variables_from_text(template.content)
                subject_variables = self._extract_variables_from_text(template.subject or "")
                html_variables = self._extract_variables_from_text(template.html_content or "")
                
                all_variables = set(content_variables + subject_variables + html_variables)
                defined_variables = set(template.variables)
                
                undefined_variables = all_variables - defined_variables
                if undefined_variables:
                    warnings.append(f"Undefined variables found: {', '.join(undefined_variables)}")
                
                unused_variables = defined_variables - all_variables
                if unused_variables:
                    warnings.append(f"Unused variables defined: {', '.join(unused_variables)}")
            
            return {
                "errors": errors,
                "warnings": warnings,
                "is_valid": len(errors) == 0
            }
            
        except Exception as e:
            logger.error(f"Failed to validate template: {e}")
            return {
                "errors": [f"Validation error: {str(e)}"],
                "warnings": [],
                "is_valid": False
            }
    
    def _extract_variables_from_text(self, text: str) -> List[str]:
        """Extract variable names from template text."""
        import re
        
        if not text:
            return []
        
        # Find all {{variable}} patterns
        pattern = r'\{\{([^}]+)\}\}'
        matches = re.findall(pattern, text)
        
        # Clean up variable names (remove whitespace)
        return [match.strip() for match in matches]


def get_notification_template_service(db: Session) -> NotificationTemplateService:
    """Get notification template service instance."""
    return NotificationTemplateService(db)
