"""Data encryption utilities for PHI protection."""

import base64
import json
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class PHIEncryption:
    """Encryption utilities for Protected Health Information (PHI)."""
    
    def __init__(self, encryption_key: Optional[str] = None):
        """
        Initialize PHI encryption.
        
        Args:
            encryption_key: Base64 encoded encryption key. If not provided,
                          will be derived from SECRET_KEY.
        """
        self.encryption_key = encryption_key or self._derive_key()
        self.cipher = Fernet(self.encryption_key)
    
    def _derive_key(self) -> str:
        """Derive encryption key from SECRET_KEY."""
        try:
            # Use SECRET_KEY as password for key derivation
            password = settings.secret_key.encode()
            salt = b'healthcare_phi_salt'  # In production, use random salt per encryption
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password))
            return key
        except Exception as e:
            logger.error(f"Failed to derive encryption key: {e}")
            raise
    
    def encrypt_phi(self, data: Any) -> str:
        """
        Encrypt PHI data.
        
        Args:
            data: Data to encrypt (will be JSON serialized)
            
        Returns:
            Base64 encoded encrypted data
        """
        try:
            # Serialize data to JSON
            json_data = json.dumps(data, default=str).encode('utf-8')
            
            # Encrypt the data
            encrypted_data = self.cipher.encrypt(json_data)
            
            # Return base64 encoded result
            return base64.urlsafe_b64encode(encrypted_data).decode('utf-8')
            
        except Exception as e:
            logger.error(f"Failed to encrypt PHI data: {e}")
            raise ValueError(f"Encryption failed: {e}")
    
    def decrypt_phi(self, encrypted_data: str) -> Any:
        """
        Decrypt PHI data.
        
        Args:
            encrypted_data: Base64 encoded encrypted data
            
        Returns:
            Decrypted and deserialized data
        """
        try:
            # Decode base64
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode('utf-8'))
            
            # Decrypt the data
            decrypted_data = self.cipher.decrypt(encrypted_bytes)
            
            # Deserialize JSON
            return json.loads(decrypted_data.decode('utf-8'))
            
        except Exception as e:
            logger.error(f"Failed to decrypt PHI data: {e}")
            raise ValueError(f"Decryption failed: {e}")
    
    def encrypt_field(self, field_value: str) -> str:
        """
        Encrypt a single field value.
        
        Args:
            field_value: String value to encrypt
            
        Returns:
            Encrypted string
        """
        return self.encrypt_phi(field_value)
    
    def decrypt_field(self, encrypted_value: str) -> str:
        """
        Decrypt a single field value.
        
        Args:
            encrypted_value: Encrypted string
            
        Returns:
            Decrypted string
        """
        return self.decrypt_phi(encrypted_value)
    
    def encrypt_sensitive_data(self, data: Dict[str, Any], sensitive_fields: list[str]) -> Dict[str, Any]:
        """
        Encrypt sensitive fields in a data dictionary.
        
        Args:
            data: Dictionary containing data
            sensitive_fields: List of field names to encrypt
            
        Returns:
            Dictionary with sensitive fields encrypted
        """
        encrypted_data = data.copy()
        
        for field in sensitive_fields:
            if field in encrypted_data and encrypted_data[field] is not None:
                try:
                    encrypted_data[field] = self.encrypt_field(str(encrypted_data[field]))
                except Exception as e:
                    logger.error(f"Failed to encrypt field {field}: {e}")
                    # Don't fail the operation, just log the error
                    continue
        
        return encrypted_data
    
    def decrypt_sensitive_data(self, data: Dict[str, Any], sensitive_fields: list[str]) -> Dict[str, Any]:
        """
        Decrypt sensitive fields in a data dictionary.
        
        Args:
            data: Dictionary containing encrypted data
            sensitive_fields: List of field names to decrypt
            
        Returns:
            Dictionary with sensitive fields decrypted
        """
        decrypted_data = data.copy()
        
        for field in sensitive_fields:
            if field in decrypted_data and decrypted_data[field] is not None:
                try:
                    decrypted_data[field] = self.decrypt_field(str(decrypted_data[field]))
                except Exception as e:
                    logger.error(f"Failed to decrypt field {field}: {e}")
                    # Don't fail the operation, just log the error
                    continue
        
        return decrypted_data


# Global encryption instance
_phi_encryption: Optional[PHIEncryption] = None


def get_phi_encryption() -> PHIEncryption:
    """Get global PHI encryption instance."""
    global _phi_encryption
    if _phi_encryption is None:
        _phi_encryption = PHIEncryption()
    return _phi_encryption


def encrypt_phi_field(field_value: str) -> str:
    """Convenience function to encrypt a PHI field."""
    return get_phi_encryption().encrypt_field(field_value)


def decrypt_phi_field(encrypted_value: str) -> str:
    """Convenience function to decrypt a PHI field."""
    return get_phi_encryption().decrypt_field(encrypted_value)


# PHI field definitions for different entities
PHI_FIELDS = {
    "user": ["email", "full_name"],
    "appointment": ["notes"],
    "patient_profile": ["full_name", "email", "phone", "address", "emergency_contact"],
    "medical_record": ["diagnosis", "treatment_notes", "medications", "allergies"]
}


def encrypt_entity_phi(entity_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Encrypt PHI fields for a specific entity type.
    
    Args:
        entity_type: Type of entity (user, appointment, etc.)
        data: Entity data dictionary
        
    Returns:
        Data with PHI fields encrypted
    """
    sensitive_fields = PHI_FIELDS.get(entity_type, [])
    return get_phi_encryption().encrypt_sensitive_data(data, sensitive_fields)


def decrypt_entity_phi(entity_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Decrypt PHI fields for a specific entity type.
    
    Args:
        entity_type: Type of entity (user, appointment, etc.)
        data: Entity data dictionary with encrypted fields
        
    Returns:
        Data with PHI fields decrypted
    """
    sensitive_fields = PHI_FIELDS.get(entity_type, [])
    return get_phi_encryption().decrypt_sensitive_data(data, sensitive_fields)
