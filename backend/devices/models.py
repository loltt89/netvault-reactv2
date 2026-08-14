from datetime import timedelta
from django.db import models
from django.conf import settings
from django.utils import timezone
from core.crypto import EncryptedFieldMixin


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


class Device(EncryptedFieldMixin, models.Model):
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
    password_encrypted = models.TextField(blank=True, default='')  # Encrypted password (can be empty for some devices)
    enable_password_encrypted = models.TextField(blank=True)  # Encrypted enable password for Cisco

    ENCRYPTED_FIELDS = {
        'password': 'password_encrypted',
        'enable_password': 'enable_password_encrypted',
    }

    # Organization
    location = models.CharField(max_length=255, blank=True)
    tags = models.JSONField(default=list, blank=True)  # List of tags
    criticality = models.CharField(max_length=20, choices=CRITICALITY_CHOICES, default='medium')

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unknown')
    last_seen = models.DateTimeField(null=True, blank=True)
    last_backup = models.DateTimeField(null=True, blank=True)
    backup_status = models.CharField(max_length=50, blank=True)

    # Backup settings
    backup_enabled = models.BooleanField(default=True)
    backup_schedule = models.CharField(max_length=255, blank=True)  # Cron expression
    custom_commands = models.JSONField(default=list, blank=True)  # Custom backup commands

    # SSH host key pinning (see devices/connection.py::PinnedHostKeyPolicy).
    # Pinned on first successful connection (trust-on-first-use); every
    # connection after that must present the same key or is refused.
    ssh_host_key_type = models.CharField(max_length=32, blank=True, help_text='e.g. ssh-ed25519, ssh-rsa')
    ssh_host_key_fingerprint = models.CharField(max_length=128, blank=True, help_text='SHA256 fingerprint of the pinned host key')
    ssh_host_key_verified_at = models.DateTimeField(null=True, blank=True, help_text='When the current key was pinned/approved')
    # Populated when a connection presents a key that doesn't match the
    # pinned one above. Non-empty means connections are being refused
    # pending admin review — see Device.approve_ssh_host_key().
    ssh_host_key_pending_type = models.CharField(max_length=32, blank=True)
    ssh_host_key_pending_fingerprint = models.CharField(max_length=128, blank=True)
    ssh_host_key_pending_detected_at = models.DateTimeField(null=True, blank=True)

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

    def clean(self):
        """
        Reject (not silently rewrite) text fields that would be dangerous
        if ever exported to CSV — same policy DeviceCreateSerializer
        already enforces on the API create/update path and devices/views.py
        csv_import enforces on the CSV-import path (both call
        core.utils.validate_csv_safe explicitly, so the database only ever
        stores what was actually submitted, never a silently-modified
        version of it — this model-level check exists as a backstop for
        any path that creates/updates a Device directly without going
        through either of those, not as the primary defense).
        Previously this method *mutated* the field (prepending a quote)
        instead of rejecting, which — besides silently storing something
        the caller didn't submit — was never actually reachable in
        practice: every real entry point already rejects the same input
        earlier, via validate_csv_safe, before a Device instance with a
        dangerous value could reach save()/clean() at all.
        """
        from django.core.exceptions import ValidationError
        from core.utils import validate_csv_safe

        errors = {}
        for field_name, field_label in (
            ('name', 'Name'), ('location', 'Location'), ('description', 'Description'),
        ):
            value = getattr(self, field_name)
            if value and isinstance(value, str):
                try:
                    validate_csv_safe(value, field_name=field_label)
                except ValueError as e:
                    errors[field_name] = str(e)

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """Override save to call clean()"""
        self.full_clean()
        super().save(*args, **kwargs)

    def set_password(self, password):
        """Encrypt and set password"""
        self.set_encrypted('password', password)

    def get_password(self):
        """Decrypt and get password"""
        return self.get_encrypted('password')

    def set_enable_password(self, password):
        """Encrypt and set enable password"""
        self.set_encrypted('enable_password', password)

    def get_enable_password(self):
        """Decrypt and get enable password"""
        return self.get_encrypted('enable_password')

    def get_backup_commands(self):
        """Get backup commands for this device"""
        if self.custom_commands:
            return self.custom_commands
        if self.vendor:
            return self.vendor.backup_commands
        return None

    @property
    def has_pending_ssh_host_key(self) -> bool:
        """True if a connection presented an SSH host key that didn't match
        the pinned one, and is awaiting admin review."""
        return bool(self.ssh_host_key_pending_fingerprint)

    def approve_ssh_host_key(self):
        """Accept the pending SSH host key as the new trusted one.

        Called from the device's "approve new key" action after an admin
        has verified the new fingerprint out-of-band. Clears the pending
        state so connections (and scheduled backups) resume.
        """
        from django.utils import timezone

        self.ssh_host_key_type = self.ssh_host_key_pending_type
        self.ssh_host_key_fingerprint = self.ssh_host_key_pending_fingerprint
        self.ssh_host_key_verified_at = timezone.now()
        self.ssh_host_key_pending_type = ''
        self.ssh_host_key_pending_fingerprint = ''
        self.ssh_host_key_pending_detected_at = None
        self.save(update_fields=[
            'ssh_host_key_type', 'ssh_host_key_fingerprint', 'ssh_host_key_verified_at',
            'ssh_host_key_pending_type', 'ssh_host_key_pending_fingerprint', 'ssh_host_key_pending_detected_at',
        ])

    def reject_ssh_host_key(self):
        """Discard the pending SSH host key without trusting it.

        Leaves the previously-pinned key (if any) in place, so connections
        stay refused — this just clears the pending/notified state, e.g.
        after confirming out-of-band that the change was NOT expected and
        the device has been isolated/investigated.
        """
        self.ssh_host_key_pending_type = ''
        self.ssh_host_key_pending_fingerprint = ''
        self.ssh_host_key_pending_detected_at = None
        self.save(update_fields=[
            'ssh_host_key_pending_type', 'ssh_host_key_pending_fingerprint', 'ssh_host_key_pending_detected_at',
        ])

    @classmethod
    def stale(cls, days=3, queryset=None):
        """
        backup_enabled devices whose last backup is older than `days` (or
        that have never been backed up at all) — the failure mode a
        backup tool most needs to surface, since a device that silently
        stopped backing up looks identical to one that's fine until the
        day someone actually needs a backup that isn't there.

        One definition of "stale", shared by the dashboard's
        stale-backups endpoint and the weekly digest email task, rather
        than two that could quietly disagree. `queryset` lets a caller
        pass an already-scoped (device_scope RBAC) or otherwise-filtered
        base queryset instead of the full table.

        Ordered most-stale first: never-backed-up devices, then oldest
        last_backup.
        """
        cutoff = timezone.now() - timedelta(days=days)
        base = queryset if queryset is not None else cls.objects.all()
        return base.filter(backup_enabled=True).filter(
            models.Q(last_backup__isnull=True) | models.Q(last_backup__lt=cutoff)
        ).order_by(models.F('last_backup').asc(nulls_first=True))


class DeviceCredential(EncryptedFieldMixin, models.Model):
    """Additional credentials for devices (for privilege escalation, etc.)"""

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='credentials')
    credential_type = models.CharField(max_length=50)  # enable, tacacs, radius, etc.
    username = models.CharField(max_length=255, blank=True)
    password_encrypted = models.TextField(blank=True, default='')
    description = models.TextField(blank=True)

    ENCRYPTED_FIELDS = {
        'password': 'password_encrypted',
    }
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
        self.set_encrypted('password', password)

    def get_password(self):
        """Decrypt and get password"""
        return self.get_encrypted('password')
