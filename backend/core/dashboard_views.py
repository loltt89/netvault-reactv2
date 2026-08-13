"""
Dashboard API views
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from devices.models import Device
from backups.models import Backup


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_statistics(request):
    """Get dashboard statistics"""

    # Device statistics
    total_devices = Device.objects.count()
    active_devices = Device.objects.filter(status='online').count()
    inactive_devices = Device.objects.filter(Q(status='offline') | Q(status='unknown')).count()

    # Backup statistics
    total_backups = Backup.objects.count()
    successful_backups = Backup.objects.filter(success=True).count()
    failed_backups = Backup.objects.filter(success=False).count()

    # Backups in last 24 hours
    last_24h = timezone.now() - timedelta(hours=24)
    backups_last_24h = Backup.objects.filter(created_at__gte=last_24h).count()

    return Response({
        'total_devices': total_devices,
        'active_devices': active_devices,
        'inactive_devices': inactive_devices,
        'total_backups': total_backups,
        'successful_backups': successful_backups,
        'failed_backups': failed_backups,
        'last_24h_backups': backups_last_24h,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def backup_trend(request):
    """Get backup trend data for last N days (optimized with single query)"""
    from django.db.models import Count, Q
    from django.db.models.functions import TruncDate

    days = int(request.query_params.get('days', 7))
    now = timezone.now()
    start_date = now - timedelta(days=days)

    # Single optimized query with aggregation
    trend = Backup.objects.filter(
        created_at__gte=start_date
    ).annotate(
        date=TruncDate('created_at')
    ).values('date').annotate(
        successful=Count('id', filter=Q(success=True)),
        failed=Count('id', filter=Q(success=False))
    ).order_by('date')

    # Convert to dict for fast lookup
    trend_dict = {
        item['date']: {
            'successful': item['successful'],
            'failed': item['failed'],
            'total': item['successful'] + item['failed']
        }
        for item in trend
    }

    # Fill in missing dates with zeros
    trend_data = []
    for i in range(days):
        day = (now - timedelta(days=days-i)).date()
        if day in trend_dict:
            trend_data.append({
                'date': day.strftime('%Y-%m-%d'),
                **trend_dict[day]
            })
        else:
            trend_data.append({
                'date': day.strftime('%Y-%m-%d'),
                'successful': 0,
                'failed': 0,
                'total': 0
            })

    return Response(trend_data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def stale_backups(request):
    """
    backup_enabled devices that haven't been backed up in `days` (default
    3) — or ever. The #1 silent failure mode of any backup tool: nobody
    notices a device stopped backing up until the day its backup is
    actually needed.
    """
    try:
        days = int(request.query_params.get('days', 3))
    except (TypeError, ValueError):
        days = 3
    days = max(1, days)

    from core.device_filters import get_scoped_device_ids
    queryset = Device.objects.select_related('vendor', 'device_type')
    scoped_ids = get_scoped_device_ids(request.user)
    if scoped_ids is not None:
        queryset = queryset.filter(id__in=scoped_ids)

    stale = Device.stale(days=days, queryset=queryset)

    now = timezone.now()
    results = [
        {
            'id': d.id,
            'name': d.name,
            'ip_address': d.ip_address,
            'vendor': d.vendor.name if d.vendor else None,
            'device_type': d.device_type.name if d.device_type else None,
            'tags': d.tags,
            'criticality': d.criticality,
            'last_backup': d.last_backup.isoformat() if d.last_backup else None,
            'days_since_backup': (now - d.last_backup).days if d.last_backup else None,
        }
        for d in stale
    ]

    return Response({
        'threshold_days': days,
        'count': len(results),
        'devices': results,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def recent_backups(request):
    """Get recent backups"""

    limit = int(request.query_params.get('limit', 10))

    backups = Backup.objects.select_related('device', 'triggered_by')\
        .order_by('-created_at')[:limit]

    from backups.serializers import BackupSerializer
    serializer = BackupSerializer(backups, many=True)

    return Response(serializer.data)
