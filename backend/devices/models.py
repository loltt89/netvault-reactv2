from django.db import models
from django.conf import settings
from cryptography.fernet import Fernet
import json


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


class Vendor(models.Model):
    """Network device vendor"""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    logo_url = models.URLField(blank=True)
    is_predefined = models.BooleanField(default=False)  # Cisco, Huawei, etc.
    backup_commands = models.JSONField(default=list)  # List of commands to run for backup
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'vendors'
        verbose_name = 'Vendor'
        verbose_name_plural = 'Vendors'
        ordering = ['name']

    def __str__(self):
        return self.name


class DeviceType(models.Model):
    """Type of network device"""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, default='router')
    is_predefined = models.BooleanField(default=False)  # Router, Switch, Firewall, etc.

    class Meta:
        db_table = 'device_types'
        verbose_name = 'Device Type'
        verbose_name_plural = 'Device Types'
        ordering = ['name']

    def __str__(self):
        return self.name


class Device(models.Model):
    """Network device"""

    PROTOCOL_CHOICES = (
        ('ssh', 'SSH'),
        ('telnet', 'Telnet'),
    )

    CRITICALITY_CHOICES = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    )

    STATUS_CHOICES = (
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('unknown', 'Unknown'),
    )

    # Basic info
    name = models.CharField(max_length=255, unique=True, db_index=True)
    ip_address = models.GenericIPAddressField(db_index=True)
    description = models.TextField(blank=True)

    # Device details
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name='devices')
    device_type = models.ForeignKey(DeviceType, on_delete=models.PROTECT, related_name='devices')

    # Connection settings
    protocol = models.CharField(max_length=10, choices=PROTOCOL_CHOICES, default='ssh')
    port = models.IntegerField(default=22)
    username = models.CharField(max_length=255)
    password_encrypted = models.TextField()  # Encrypted password
    enable_password_encrypted = models.TextField(blank=True)  # Encrypted enable password for Cisco

    # Organization
    location = models.CharField(max_length=255, blank=True)
    tags = models.JSONField(default=list)  # List of tags
    criticality = models.CharField(max_length=20, choices=CRITICALITY_CHOICES, default='medium')

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unknown')
    last_seen = models.DateTimeField(null=True, blank=True)
    last_backup = models.DateTimeField(null=True, blank=True)
    backup_status = models.CharField(max_length=50, blank=True)

    # Backup settings
    backup_enabled = models.BooleanField(default=True)
    backup_schedule = models.CharField(max_length=255, blank=True)  # Cron expression
    custom_commands = models.JSONField(default=list)  # Custom backup commands

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='devices_created')

    class Meta:
        db_table = 'devices'
        verbose_name = 'Device'
        verbose_name_plural = 'Devices'
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['ip_address']),
            models.Index(fields=['status']),
            models.Index(fields=['vendor', 'device_type']),
        ]

    def __str__(self):
        return f'{self.name} ({self.ip_address})'

    def set_password(self, password):
        """Encrypt and set password"""
        self.password_encrypted = encrypt_data(password)

    def get_password(self):
        """Decrypt and get password"""
        return decrypt_data(self.password_encrypted)

    def set_enable_password(self, password):
        """Encrypt and set enable password"""
        self.enable_password_encrypted = encrypt_data(password)

    def get_enable_password(self):
        """Decrypt and get enable password"""
        return decrypt_data(self.enable_password_encrypted)

    def get_backup_commands(self):
        """Get backup commands for this device"""
        if self.custom_commands:
            return self.custom_commands
        return self.vendor.backup_commands


class DeviceCredential(models.Model):
    """Additional credentials for devices (for privilege escalation, etc.)"""

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='credentials')
    credential_type = models.CharField(max_length=50)  # enable, tacacs, radius, etc.
    username = models.CharField(max_length=255, blank=True)
    password_encrypted = models.TextField()
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'device_credentials'
        verbose_name = 'Device Credential'
        verbose_name_plural = 'Device Credentials'

    def __str__(self):
        return f'{self.device.name} - {self.credential_type}'

    def set_password(self, password):
        """Encrypt and set password"""
        self.password_encrypted = encrypt_data(password)

    def get_password(self):
        """Decrypt and get password"""
        return decrypt_data(self.password_encrypted)
