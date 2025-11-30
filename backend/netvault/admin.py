"""
Django admin configuration for NetVault core models
"""
from django.contrib import admin
from .models import SystemSettings


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    """Admin interface for system settings"""

    list_display = ('id', 'email_host_user', 'telegram_enabled', 'ldap_enabled', 'backup_retention_days', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('Email Settings', {
            'fields': ('email_host', 'email_port', 'email_use_tls', 'email_host_user', 'email_from_address')
        }),
        ('Telegram Settings', {
            'fields': ('telegram_enabled', 'telegram_chat_id')
        }),
        ('Notification Settings', {
            'fields': ('notify_on_backup_success', 'notify_on_backup_failure', 'notify_schedule_summary')
        }),
        ('LDAP Settings', {
            'fields': ('ldap_enabled', 'ldap_server_uri', 'ldap_bind_dn', 'ldap_user_search_base', 'ldap_user_search_filter')
        }),
        ('Backup Settings', {
            'fields': ('backup_retention_days', 'backup_parallel_workers')
        }),
        ('JWT Settings', {
            'fields': ('jwt_access_token_lifetime', 'jwt_refresh_token_lifetime')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    def has_add_permission(self, request):
        # Only allow one instance (singleton)
        return not SystemSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Never allow deletion
        return False
