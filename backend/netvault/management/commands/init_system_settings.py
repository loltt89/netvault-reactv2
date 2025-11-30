"""
Initialize system settings from environment variables

This command is run during installation to migrate settings from .env to database
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from netvault.models import SystemSettings
import os


class Command(BaseCommand):
    help = 'Initialize system settings from environment variables'

    def handle(self, *args, **options):
        self.stdout.write('Initializing system settings...')

        # Get or create settings singleton
        sys_settings, created = SystemSettings.objects.get_or_create(pk=1)

        if created:
            self.stdout.write(self.style.SUCCESS('Created new SystemSettings record'))
        else:
            self.stdout.write(self.style.WARNING('SystemSettings already exists, updating...'))

        # ===== Email Settings =====
        sys_settings.email_host = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
        sys_settings.email_port = int(os.getenv('EMAIL_PORT', '587'))
        sys_settings.email_use_tls = os.getenv('EMAIL_USE_TLS', 'True') == 'True'
        sys_settings.email_host_user = os.getenv('EMAIL_HOST_USER', '')
        sys_settings.email_from_address = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@netvault.local')

        # Encrypt email password
        email_password = os.getenv('EMAIL_HOST_PASSWORD', '')
        if email_password:
            sys_settings.set_email_password(email_password)

        # ===== Telegram Settings =====
        sys_settings.telegram_enabled = os.getenv('TELEGRAM_ENABLED', 'False') == 'True'
        sys_settings.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')

        # Encrypt Telegram bot token
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        if bot_token:
            sys_settings.set_telegram_bot_token(bot_token)

        # ===== Notification Settings =====
        sys_settings.notify_on_backup_success = os.getenv('NOTIFY_ON_BACKUP_SUCCESS', 'False') == 'True'
        sys_settings.notify_on_backup_failure = os.getenv('NOTIFY_ON_BACKUP_FAILURE', 'True') == 'True'
        sys_settings.notify_schedule_summary = os.getenv('NOTIFY_SCHEDULE_SUMMARY', 'False') == 'True'

        # ===== LDAP Settings =====
        sys_settings.ldap_enabled = os.getenv('LDAP_ENABLED', 'False') == 'True'
        sys_settings.ldap_server_uri = os.getenv('LDAP_SERVER_URI', '')
        sys_settings.ldap_bind_dn = os.getenv('LDAP_BIND_DN', '')
        sys_settings.ldap_user_search_base = os.getenv('LDAP_USER_SEARCH_BASE', '')
        sys_settings.ldap_user_search_filter = os.getenv('LDAP_USER_SEARCH_FILTER', '(uid=%(user)s)')

        # Encrypt LDAP password
        ldap_password = os.getenv('LDAP_BIND_PASSWORD', '')
        if ldap_password:
            sys_settings.set_ldap_bind_password(ldap_password)

        # ===== Backup Settings =====
        sys_settings.backup_retention_days = int(os.getenv('BACKUP_RETENTION_DAYS', '90'))
        sys_settings.backup_parallel_workers = int(os.getenv('BACKUP_PARALLEL_WORKERS', '5'))

        # ===== JWT Settings =====
        sys_settings.jwt_access_token_lifetime = int(os.getenv('JWT_ACCESS_TOKEN_LIFETIME', '60'))
        sys_settings.jwt_refresh_token_lifetime = int(os.getenv('JWT_REFRESH_TOKEN_LIFETIME', '1440'))

        # Save all settings
        sys_settings.save()

        self.stdout.write(self.style.SUCCESS('✓ System settings initialized successfully'))
        self.stdout.write(f'  Email: {sys_settings.email_host_user or "(not configured)"}')
        self.stdout.write(f'  Telegram: {"Enabled" if sys_settings.telegram_enabled else "Disabled"}')
        self.stdout.write(f'  LDAP: {"Enabled" if sys_settings.ldap_enabled else "Disabled"}')
        self.stdout.write(f'  Backup retention: {sys_settings.backup_retention_days} days')
        self.stdout.write(f'  JWT access token: {sys_settings.jwt_access_token_lifetime} minutes')
