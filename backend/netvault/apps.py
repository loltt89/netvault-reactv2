"""
NetVault application configuration
"""
from django.apps import AppConfig


class NetvaultConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'netvault'
    verbose_name = 'NetVault Core'
