"""Data retention policies and secure deletion for HIPAA compliance."""

import uuid
from datetime import datetime, timedelta, UTC
from enum import Enum
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.security.audit import AuditLogger, get_audit_logger

logger = get_logger(__name__)


class RetentionPolicy(str, Enum):
    """Data retention policies for different data types."""
    
    # HIPAA requires different retention periods for different data types
    MEDICAL_RECORDS = "medical_records"  # 6 years from last service
    APPOINTMENT_RECORDS = "appointment_records"  # 6 years from last service
    AUDIT_LOGS = "audit_logs"  # 6 years minimum
    USER_ACCOUNTS = "user_accounts"  # 7 years after account closure
    SYSTEM_LOGS = "system_logs"  # 1 year
    BACKUP_DATA = "backup_data"  # 6 years


class DataRetentionManager:
    """Manages data retention policies and secure deletion."""
    
    def __init__(self, db: Session):
        self.db = db
        self.audit_logger = get_audit_logger(db)
        
        # Define retention periods in days
        self.retention_periods: Dict[RetentionPolicy, int] = {
            RetentionPolicy.MEDICAL_RECORDS: 6 * 365,  # 6 years
            RetentionPolicy.APPOINTMENT_RECORDS: 6 * 365,  # 6 years
            RetentionPolicy.AUDIT_LOGS: 6 * 365,  # 6 years
            RetentionPolicy.USER_ACCOUNTS: 7 * 365,  # 7 years
            RetentionPolicy.SYSTEM_LOGS: 365,  # 1 year
            RetentionPolicy.BACKUP_DATA: 6 * 365,  # 6 years
        }
    
    def get_retention_date(self, policy: RetentionPolicy, reference_date: Optional[datetime] = None) -> datetime:
        """
        Get the retention date for a specific policy.
        
        Args:
            policy: Retention policy to apply
            reference_date: Reference date (defaults to now)
            
        Returns:
            Date after which data should be deleted
        """
        if reference_date is None:
            reference_date = datetime.now(UTC)
        
        retention_days = self.retention_periods.get(policy, 365)  # Default to 1 year
        return reference_date - timedelta(days=retention_days)
    
    def identify_expired_data(self, policy: RetentionPolicy) -> List[Dict[str, any]]:
        """
        Identify data that has exceeded retention period.
        
        Args:
            policy: Retention policy to check
            
        Returns:
            List of expired data records
        """
        try:
            retention_date = self.get_retention_date(policy)
            expired_data = []
            
            if policy == RetentionPolicy.APPOINTMENT_RECORDS:
                from app.db.models import Appointment
                expired_appointments = self.db.query(Appointment).filter(
                    Appointment.updated_at < retention_date
                ).all()
                
                for appointment in expired_appointments:
                    expired_data.append({
                        "id": appointment.id,
                        "type": "appointment",
                        "created_at": appointment.created_at,
                        "updated_at": appointment.updated_at,
                        "retention_date": retention_date
                    })
            
            elif policy == RetentionPolicy.USER_ACCOUNTS:
                from app.db.models import User
                expired_users = self.db.query(User).filter(
                    User.updated_at < retention_date,
                    User.is_active == False  # Only inactive users
                ).all()
                
                for user in expired_users:
                    expired_data.append({
                        "id": user.id,
                        "type": "user",
                        "created_at": user.created_at,
                        "updated_at": user.updated_at,
                        "retention_date": retention_date
                    })
            
            elif policy == RetentionPolicy.AUDIT_LOGS:
                # In a real implementation, you'd query an audit log table
                # For now, we'll return empty list
                pass
            
            return expired_data
            
        except Exception as e:
            logger.error(f"Error identifying expired data for policy {policy}: {e}")
            return []
    
    def secure_delete_data(self, data_records: List[Dict[str, any]], policy: RetentionPolicy) -> bool:
        """
        Securely delete data records.
        
        Args:
            data_records: List of data records to delete
            policy: Retention policy being applied
            
        Returns:
            True if deletion successful, False otherwise
        """
        try:
            deleted_count = 0
            
            for record in data_records:
                if record["type"] == "appointment":
                    success = self._delete_appointment(record["id"])
                elif record["type"] == "user":
                    success = self._delete_user(record["id"])
                else:
                    logger.warning(f"Unknown data type for deletion: {record['type']}")
                    continue
                
                if success:
                    deleted_count += 1
                    
                    # Log the deletion
                    self.audit_logger.log_event(
                        event_type="phi_deleted",
                        resource_id=record["id"],
                        resource_type=record["type"],
                        action=f"secure_delete:{policy.value}",
                        details={
                            "retention_policy": policy.value,
                            "retention_date": record["retention_date"].isoformat(),
                            "original_created_at": record["created_at"].isoformat(),
                            "original_updated_at": record["updated_at"].isoformat()
                        },
                        success=True
                    )
            
            logger.info(f"Securely deleted {deleted_count} records for policy {policy}")
            return True
            
        except Exception as e:
            logger.error(f"Error in secure deletion: {e}")
            return False
    
    def _delete_appointment(self, appointment_id: uuid.UUID) -> bool:
        """Securely delete an appointment record."""
        try:
            from app.db.models import Appointment
            
            appointment = self.db.query(Appointment).filter(Appointment.id == appointment_id).first()
            if not appointment:
                return False
            
            # Log before deletion
            logger.info(f"Securely deleting appointment {appointment_id}")
            
            # Delete the record
            self.db.delete(appointment)
            self.db.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting appointment {appointment_id}: {e}")
            self.db.rollback()
            return False
    
    def _delete_user(self, user_id: uuid.UUID) -> bool:
        """Securely delete a user record."""
        try:
            from app.db.models import User
            
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return False
            
            # Log before deletion
            logger.info(f"Securely deleting user {user_id}")
            
            # Delete the record
            self.db.delete(user)
            self.db.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting user {user_id}: {e}")
            self.db.rollback()
            return False
    
    def anonymize_data(self, data_records: List[Dict[str, any]]) -> bool:
        """
        Anonymize data instead of deleting (for certain compliance requirements).
        
        Args:
            data_records: List of data records to anonymize
            
        Returns:
            True if anonymization successful, False otherwise
        """
        try:
            anonymized_count = 0
            
            for record in data_records:
                if record["type"] == "appointment":
                    success = self._anonymize_appointment(record["id"])
                elif record["type"] == "user":
                    success = self._anonymize_user(record["id"])
                else:
                    logger.warning(f"Unknown data type for anonymization: {record['type']}")
                    continue
                
                if success:
                    anonymized_count += 1
                    
                    # Log the anonymization
                    self.audit_logger.log_event(
                        event_type="phi_updated",
                        resource_id=record["id"],
                        resource_type=record["type"],
                        action="anonymize",
                        details={
                            "anonymization_date": datetime.now(UTC).isoformat(),
                            "original_created_at": record["created_at"].isoformat(),
                            "original_updated_at": record["updated_at"].isoformat()
                        },
                        success=True
                    )
            
            logger.info(f"Anonymized {anonymized_count} records")
            return True
            
        except Exception as e:
            logger.error(f"Error in data anonymization: {e}")
            return False
    
    def _anonymize_appointment(self, appointment_id: uuid.UUID) -> bool:
        """Anonymize an appointment record."""
        try:
            from app.db.models import Appointment
            
            appointment = self.db.query(Appointment).filter(Appointment.id == appointment_id).first()
            if not appointment:
                return False
            
            # Anonymize sensitive data
            appointment.notes = "[ANONYMIZED]"
            
            self.db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error anonymizing appointment {appointment_id}: {e}")
            self.db.rollback()
            return False
    
    def _anonymize_user(self, user_id: uuid.UUID) -> bool:
        """Anonymize a user record."""
        try:
            from app.db.models import User
            
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return False
            
            # Anonymize sensitive data
            user.email = f"anonymized_{user_id}@deleted.local"
            user.full_name = "[ANONYMIZED]"
            
            self.db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error anonymizing user {user_id}: {e}")
            self.db.rollback()
            return False
    
    def run_retention_cleanup(self, policy: RetentionPolicy, dry_run: bool = True) -> Dict[str, any]:
        """
        Run retention cleanup for a specific policy.
        
        Args:
            policy: Retention policy to apply
            dry_run: If True, only identify expired data without deleting
            
        Returns:
            Summary of cleanup operation
        """
        try:
            logger.info(f"Starting retention cleanup for policy {policy} (dry_run={dry_run})")
            
            # Identify expired data
            expired_data = self.identify_expired_data(policy)
            
            if not expired_data:
                logger.info(f"No expired data found for policy {policy}")
                return {
                    "policy": policy.value,
                    "expired_count": 0,
                    "processed_count": 0,
                    "success": True,
                    "dry_run": dry_run
                }
            
            logger.info(f"Found {len(expired_data)} expired records for policy {policy}")
            
            if dry_run:
                # Just log what would be deleted
                for record in expired_data:
                    logger.info(f"Would delete {record['type']} {record['id']} (created: {record['created_at']})")
                
                return {
                    "policy": policy.value,
                    "expired_count": len(expired_data),
                    "processed_count": 0,
                    "success": True,
                    "dry_run": True
                }
            else:
                # Actually delete the data
                success = self.secure_delete_data(expired_data, policy)
                
                return {
                    "policy": policy.value,
                    "expired_count": len(expired_data),
                    "processed_count": len(expired_data) if success else 0,
                    "success": success,
                    "dry_run": False
                }
                
        except Exception as e:
            logger.error(f"Error in retention cleanup for policy {policy}: {e}")
            return {
                "policy": policy.value,
                "expired_count": 0,
                "processed_count": 0,
                "success": False,
                "error": str(e),
                "dry_run": dry_run
            }
    
    def run_all_retention_cleanups(self, dry_run: bool = True) -> Dict[str, any]:
        """
        Run retention cleanup for all policies.
        
        Args:
            dry_run: If True, only identify expired data without deleting
            
        Returns:
            Summary of all cleanup operations
        """
        results = {}
        
        for policy in RetentionPolicy:
            results[policy.value] = self.run_retention_cleanup(policy, dry_run)
        
        return results


def get_data_retention_manager(db: Session) -> DataRetentionManager:
    """Get data retention manager instance."""
    return DataRetentionManager(db)
