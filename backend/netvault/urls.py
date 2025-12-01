"""
URL configuration for netvault project.
NetVault - Network Device Configuration Backup System
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from .dashboard_views import dashboard_statistics, backup_trend, recent_backups
from .system_settings_views import (
    get_system_settings,
    update_system_settings,
    test_email_settings,
    test_telegram_settings
)
from .health_views import health_check, health_detailed, readiness_check, liveness_check

urlpatterns = [
    path('admin/', admin.site.urls),

    # API endpoints
    path('api/v1/', include('accounts.urls')),
    path('api/v1/devices/', include('devices.urls')),
    path('api/v1/backups/', include('backups.urls')),
    # path('api/v1/notifications/', include('notifications.urls')),  # Will create later

    # Dashboard endpoints
    path('api/v1/dashboard/statistics/', dashboard_statistics, name='dashboard-statistics'),
    path('api/v1/dashboard/backup-trend/', backup_trend, name='dashboard-backup-trend'),
    path('api/v1/dashboard/recent-backups/', recent_backups, name='dashboard-recent-backups'),

    # System settings endpoints (admin only)
    path('api/v1/settings/system/', get_system_settings, name='get-system-settings'),
    path('api/v1/settings/system/update/', update_system_settings, name='update-system-settings'),
    path('api/v1/settings/test-email/', test_email_settings, name='test-email'),
    path('api/v1/settings/test-telegram/', test_telegram_settings, name='test-telegram'),

    # API Documentation (Swagger/OpenAPI)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # Prometheus metrics endpoint
    path('', include('django_prometheus.urls')),

    # Health check endpoints
    path('api/v1/health/', health_check, name='health-check'),
    path('api/v1/health/detailed/', health_detailed, name='health-detailed'),
    path('api/v1/health/ready/', readiness_check, name='readiness-check'),
    path('api/v1/health/live/', liveness_check, name='liveness-check'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
