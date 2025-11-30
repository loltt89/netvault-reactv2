"""
System-wide settings stored in database
"""
from django.db import models
from django.core.cache import cache
from core.crypto import encrypt_data, decrypt_data


class SystemSettings(models.Model):
    """
    System-wide settings (Singleton model)

    All settings are stored in database and cached for performance.
    Changes take effect immediately without requiring application restart.
    """

    # ===== Email Settings =====
    email_host = models.CharField(max_length=255, default='smtp.gmail.com', blank=True)
    email_port = models.IntegerField(default=587)
    email_use_tls = models.BooleanField(default=True)
    email_host_user = models.CharField(max_length=255, blank=True)
    email_host_password_encrypted = models.TextField(blank=True, help_text='Encrypted email password')
    email_from_address = models.EmailField(default='noreply@netvault.local', blank=True)

    # ===== Telegram Settings =====
    telegram_enabled = models.BooleanField(default=False)
    telegram_bot_token_encrypted = models.TextField(blank=True, help_text='Encrypted Telegram bot token')
    telegram_chat_id = models.CharField(max_length=100, blank=True)

    # ===== Notification Settings =====
    notify_on_backup_success = models.BooleanField(default=False)
    notify_on_backup_failure = models.BooleanField(default=True)
    notify_schedule_summary = models.BooleanField(default=False)

    # ===== LDAP Settings =====
    ldap_enabled = models.BooleanField(default=False)
    ldap_server_uri = models.CharField(max_length=255, blank=True, help_text='e.g., ldap://ldap.example.com:389')
    ldap_bind_dn = models.CharField(max_length=255, blank=True, help_text='e.g., cn=admin,dc=example,dc=com')
    ldap_bind_password_encrypted = models.TextField(blank=True, help_text='Encrypted LDAP bind password')
    ldap_user_search_base = models.CharField(max_length=255, blank=True, help_text='e.g., ou=users,dc=example,dc=com')
    ldap_user_search_filter = models.CharField(max_length=255, default='(uid=%(user)s)', blank=True)

    # ===== Backup Settings =====
    backup_retention_days = models.IntegerField(default=90, help_text='Number of days to keep old backups')
    backup_parallel_workers = models.IntegerField(default=5, help_text='Number of parallel backup workers')

    # ===== JWT Settings =====
    jwt_access_token_lifetime = models.IntegerField(default=60, help_text='Access token lifetime in minutes')
    jwt_refresh_token_lifetime = models.IntegerField(default=1440, help_text='Refresh token lifetime in minutes (24h)')

    # ===== Metadata =====
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'system_settings'
        verbose_name = 'System Settings'
        verbose_name_plural = 'System Settings'

    def __str__(self):
        return 'System Settings'

    def save(self, *args, **kwargs):
        # Ensure only one instance exists (singleton)
        self.pk = 1
        super().save(*args, **kwargs)
        # Clear cache when settings change
        cache.delete('system_settings')

    @classmethod
    def get_settings(cls):
        """
        Get or create system settings singleton with caching

        Returns settings from cache (5 min TTL) or database
        """
        settings = cache.get('system_settings')
        if settings is None:
            settings, created = cls.objects.get_or_create(pk=1)
            # Cache for 5 minutes
            cache.set('system_settings', settings, timeout=300)
        return settings

    # ===== Email Password Methods =====
    def set_email_password(self, password: str):
        """Encrypt and store email password"""
        if password:
            self.email_host_password_encrypted = encrypt_data(password)
        else:
            self.email_host_password_encrypted = ''

    def get_email_password(self) -> str:
        """Decrypt and return email password"""
        if self.email_host_password_encrypted:
            return decrypt_data(self.email_host_password_encrypted)
        return ''

    # ===== Telegram Token Methods =====
    def set_telegram_bot_token(self, token: str):
        """Encrypt and store Telegram bot token"""
        if token:
            self.telegram_bot_token_encrypted = encrypt_data(token)
        else:
            self.telegram_bot_token_encrypted = ''

    def get_telegram_bot_token(self) -> str:
        """Decrypt and return Telegram bot token"""
        if self.telegram_bot_token_encrypted:
            return decrypt_data(self.telegram_bot_token_encrypted)
        return ''

    # ===== LDAP Password Methods =====
    def set_ldap_bind_password(self, password: str):
        """Encrypt and store LDAP bind password"""
        if password:
            self.ldap_bind_password_encrypted = encrypt_data(password)
        else:
            self.ldap_bind_password_encrypted = ''

    def get_ldap_bind_password(self) -> str:
        """Decrypt and return LDAP bind password"""
        if self.ldap_bind_password_encrypted:
            return decrypt_data(self.ldap_bind_password_encrypted)
        return ''
