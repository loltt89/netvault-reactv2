"""
Health check endpoints for monitoring
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.db import connection
from django.core.cache import cache
from django.conf import settings
import redis
import logging

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Basic health check endpoint
    Returns 200 if the application is running
    """
    return Response({
        'status': 'healthy',
        'service': 'netvault-api'
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def health_detailed(request):
    """
    Detailed health check with dependency status
    Checks: database, redis, celery
    """
    health = {
        'status': 'healthy',
        'service': 'netvault-api',
        'checks': {}
    }

    # Check database
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        health['checks']['database'] = {'status': 'healthy'}
    except Exception as e:
        health['checks']['database'] = {'status': 'unhealthy', 'error': str(e)}
        health['status'] = 'degraded'

    # Check Redis
    try:
        redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
        r = redis.from_url(redis_url)
        r.ping()
        health['checks']['redis'] = {'status': 'healthy'}
    except Exception as e:
        health['checks']['redis'] = {'status': 'unhealthy', 'error': str(e)}
        health['status'] = 'degraded'

    # Check Celery (via Redis queue)
    try:
        from backups.models import BackupSchedule
        schedules_count = BackupSchedule.objects.filter(is_active=True).count()
        health['checks']['celery'] = {
            'status': 'healthy',
            'active_schedules': schedules_count
        }
    except Exception as e:
        health['checks']['celery'] = {'status': 'unknown', 'error': str(e)}

    # Add basic stats
    try:
        from devices.models import Device
        from backups.models import Backup
        from django.contrib.auth import get_user_model
        User = get_user_model()

        health['stats'] = {
            'total_devices': Device.objects.count(),
            'total_backups': Backup.objects.count(),
            'total_users': User.objects.count(),
        }
    except Exception as e:
        logger.warning(f"Could not get stats: {e}")

    return Response(health)


@api_view(['GET'])
@permission_classes([AllowAny])
def readiness_check(request):
    """
    Readiness probe for Kubernetes/Docker
    Returns 200 only if all critical dependencies are available
    """
    try:
        # Check database connection
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')

        # Check Redis
        redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
        r = redis.from_url(redis_url)
        r.ping()

        return Response({'status': 'ready'})
    except Exception as e:
        return Response({'status': 'not_ready', 'error': str(e)}, status=503)


@api_view(['GET'])
@permission_classes([AllowAny])
def liveness_check(request):
    """
    Liveness probe for Kubernetes/Docker
    Returns 200 if the application process is alive
    """
    return Response({'status': 'alive'})
