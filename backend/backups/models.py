from django.db import models
from django.conf import settings
from devices.models import Device
from core.crypto import encrypt_data, decrypt_data
import hashlib


class Backup(models.Model):
    """Configuration backup for a device"""

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('partial', 'Partial'),
    )

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='backups')

    # Backup info
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    configuration_encrypted = models.TextField()  # Encrypted configuration content
    configuration_hash = models.CharField(max_length=64, db_index=True)  # SHA256 hash for deduplication
    size_bytes = models.BigIntegerField(default=0)

    # Timing
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)

    # Result
    success = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    output_log = models.TextField(blank=True)  # Connection/command output logs

    # Metadata
    backup_type = models.CharField(max_length=20, default='manual', choices=[
        ('manual', 'Manual'),
        ('scheduled', 'Scheduled'),
        ('automatic', 'Automatic'),
    ])
    schedule = models.ForeignKey(
        'BackupSchedule',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='backups'
    )
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='backups_triggered'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    # Change detection
    has_changes = models.BooleanField(default=True)  # Compared to previous backup
    changes_summary = models.TextField(blank=True)

    class Meta:
        db_table = 'backups'
        verbose_name = 'Backup'
        verbose_name_plural = 'Backups'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['device', '-created_at']),
            models.Index(fields=['device', 'success', '-created_at']),  # Composite for queries
            models.Index(fields=['status']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['configuration_hash']),
        ]

    def __str__(self):
        return f'{self.device.name} - {self.created_at.strftime("%Y-%m-%d %H:%M:%S")}'

    def _normalize_config_for_comparison(self, configuration):
        """
        Normalize configuration for comparison by removing dynamic lines
        that change on every backup but don't represent actual config changes
        """
        import re

        lines = configuration.split('\n')
        normalized_lines = []
        in_crypto_block = False

        for line in lines:
            # Skip Mikrotik timestamp line (e.g., "# 2025-11-23 10:17:44 by RouterOS 7.16")
            if line.startswith('# ') and ' by RouterOS ' in line:
                continue

            # FortiGate: Normalize encrypted passwords (they change on every export)
            # Examples: "set password ENC xxx", "set ppk-secret ENC xxx"
            if ' ENC ' in line and not in_crypto_block:
                line = re.sub(r'(set \S+ ENC )\S+', r'\1[REDACTED]', line)

            # FortiGate: Skip encrypted private keys and certificates content (they change on every export)
            if '-----BEGIN' in line:
                in_crypto_block = True
                normalized_lines.append('[CRYPTO_BLOCK_START]')
                continue
            elif '-----END' in line:
                in_crypto_block = False
                normalized_lines.append('[CRYPTO_BLOCK_END]')
                continue

            if in_crypto_block:
                continue  # Skip all lines inside crypto blocks

            normalized_lines.append(line)

        return '\n'.join(normalized_lines)

    def set_configuration(self, configuration):
        """Encrypt and set configuration content"""
        self.configuration_encrypted = encrypt_data(configuration)
        # Normalize config before hashing to ignore timestamp-like changes
        normalized_config = self._normalize_config_for_comparison(configuration)
        self.configuration_hash = hashlib.sha256(normalized_config.encode()).hexdigest()
        self.size_bytes = len(configuration)

    def get_configuration(self):
        """Decrypt and get configuration content"""
        return decrypt_data(self.configuration_encrypted)

    def compare_with_previous(self):
        """Compare with previous backup to detect changes"""
        previous = Backup.objects.filter(
            device=self.device,
            success=True,
            created_at__lt=self.created_at
        ).order_by('-created_at').first()

        if not previous:
            self.has_changes = True
            self.changes_summary = 'First backup for this device'
            return True

        if self.configuration_hash == previous.configuration_hash:
            self.has_changes = False
            self.changes_summary = 'No changes detected'
            return False

        self.has_changes = True
        self.changes_summary = 'Configuration changed'
        return True


class BackupSchedule(models.Model):
    """Scheduled backup task"""

    FREQUENCY_CHOICES = (
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    )

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Schedule settings
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='daily')
    run_time = models.TimeField(null=True, blank=True, help_text='Time to run (for daily/weekly/monthly)')
    run_days = models.CharField(max_length=50, blank=True, help_text='Days of week (0=Mon, 6=Sun), comma-separated')

    # Devices to backup
    devices = models.ManyToManyField(Device, related_name='backup_schedules', blank=True)

    is_active = models.BooleanField(default=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='backup_schedules_created'
    )

    # Stats
    last_run = models.DateTimeField(null=True, blank=True)
    next_run = models.DateTimeField(null=True, blank=True)
    total_runs = models.IntegerField(default=0)
    successful_runs = models.IntegerField(default=0)
    failed_runs = models.IntegerField(default=0)

    class Meta:
        db_table = 'backup_schedules'
        verbose_name = 'Backup Schedule'
        verbose_name_plural = 'Backup Schedules'
        ordering = ['name']
        indexes = [
            models.Index(fields=['is_active', 'next_run']),  # For finding active schedules to run
            models.Index(fields=['is_active', 'frequency']),  # For filtering schedules by type
        ]

    def __str__(self):
        return self.name


class BackupRetentionPolicy(models.Model):
    """Policy for automatic backup retention/deletion"""

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)

    # Retention rules
    keep_last_n = models.IntegerField(default=10, help_text='Keep last N backups')
    keep_daily = models.IntegerField(default=7, help_text='Keep daily backups for N days')
    keep_weekly = models.IntegerField(default=4, help_text='Keep weekly backups for N weeks')
    keep_monthly = models.IntegerField(default=12, help_text='Keep monthly backups for N months')

    # Policy settings
    is_active = models.BooleanField(default=True)
    auto_delete = models.BooleanField(default=False, help_text='Automatically delete old backups')

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    devices = models.ManyToManyField(Device, related_name='retention_policies', blank=True)

    class Meta:
        db_table = 'backup_retention_policies'
        verbose_name = 'Backup Retention Policy'
        verbose_name_plural = 'Backup Retention Policies'
        ordering = ['name']

    def __str__(self):
        return self.name


class BackupDiff(models.Model):
    """Stores differences between two backups"""

    backup_new = models.ForeignKey(Backup, on_delete=models.CASCADE, related_name='diffs_as_new')
    backup_old = models.ForeignKey(Backup, on_delete=models.CASCADE, related_name='diffs_as_old')

    # Diff content
    diff_content = models.TextField()  # Unified diff format
    additions = models.IntegerField(default=0)
    deletions = models.IntegerField(default=0)
    modifications = models.IntegerField(default=0)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'backup_diffs'
        verbose_name = 'Backup Diff'
        verbose_name_plural = 'Backup Diffs'
        unique_together = [['backup_new', 'backup_old']]

    def __str__(self):
        return f'Diff: {self.backup_old.id} -> {self.backup_new.id}'
