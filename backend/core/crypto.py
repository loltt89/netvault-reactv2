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
