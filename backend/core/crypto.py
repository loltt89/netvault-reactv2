"""
Encryption utilities for NetVault
Centralized cryptography functions to avoid code duplication
"""
from django.conf import settings
from cryptography.fernet import Fernet


def encrypt_data(data):
    """Encrypt sensitive data"""
    if not settings.ENCRYPTION_KEY:
        raise ValueError('ENCRYPTION_KEY not set in settings')
    f = Fernet(settings.ENCRYPTION_KEY.encode())
    return f.encrypt(data.encode()).decode()


def decrypt_data(encrypted_data):
    """Decrypt sensitive data"""
    if not settings.ENCRYPTION_KEY:
        raise ValueError('ENCRYPTION_KEY not set in settings')
    if not encrypted_data:
        return ''
    f = Fernet(settings.ENCRYPTION_KEY.encode())
    return f.decrypt(encrypted_data.encode()).decode()


class EncryptedFieldMixin:
    """
    Mixin for models with encrypted fields.

    Provides generic set_encrypted/get_encrypted methods.
    Models should define ENCRYPTED_FIELDS mapping:
        ENCRYPTED_FIELDS = {
            'password': 'password_encrypted',
            'enable_password': 'enable_password_encrypted',
        }
    """

    ENCRYPTED_FIELDS = {}

    def set_encrypted(self, field_name: str, value: str):
        """Encrypt and set field value"""
        if field_name not in self.ENCRYPTED_FIELDS:
            raise ValueError(f"Unknown encrypted field: {field_name}")
        encrypted_field = self.ENCRYPTED_FIELDS[field_name]
        if value:
            setattr(self, encrypted_field, encrypt_data(value))
        else:
            setattr(self, encrypted_field, '')

    def get_encrypted(self, field_name: str) -> str:
        """Decrypt and get field value"""
        if field_name not in self.ENCRYPTED_FIELDS:
            raise ValueError(f"Unknown encrypted field: {field_name}")
        encrypted_field = self.ENCRYPTED_FIELDS[field_name]
        encrypted_value = getattr(self, encrypted_field, '')
        if encrypted_value:
            return decrypt_data(encrypted_value)
        return ''
