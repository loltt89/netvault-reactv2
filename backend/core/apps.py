"""
Core application configuration — shared infrastructure (SystemSettings,
crypto helpers, Redis locking, dashboard/health endpoints) used across
the other apps. Formerly split between this app and the netvault
project package; consolidated here so there's one place for
"general infrastructure that doesn't belong to a specific domain app".
"""
from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'NetVault Core'

    def ready(self):
        from django.conf import settings
        if getattr(settings, 'ALLOW_PRIVATE_NETWORK_HOSTS', False):
            from core.host_validation import patch
            patch()
