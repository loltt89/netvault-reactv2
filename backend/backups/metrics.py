"""
Custom Prometheus metrics for NetVault backups
"""
from prometheus_client import Counter, Histogram, Gauge

# Backup task metrics
BACKUP_TASKS_TOTAL = Counter(
    'netvault_backup_tasks_total',
    'Total number of backup tasks executed',
    ['status', 'vendor']
)

BACKUP_DURATION_SECONDS = Histogram(
    'netvault_backup_duration_seconds',
    'Time spent executing backup tasks',
    ['vendor'],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600]
)

BACKUP_SIZE_BYTES = Histogram(
    'netvault_backup_size_bytes',
    'Size of backup configurations',
    ['vendor'],
    buckets=[1024, 10240, 102400, 1048576, 10485760]
)

# Device metrics
DEVICES_TOTAL = Gauge(
    'netvault_devices_total',
    'Total number of devices',
    ['status', 'vendor']
)

DEVICES_BACKUP_ENABLED = Gauge(
    'netvault_devices_backup_enabled',
    'Number of devices with backup enabled'
)

# Schedule metrics
ACTIVE_SCHEDULES = Gauge(
    'netvault_active_schedules',
    'Number of active backup schedules'
)


def record_backup_success(vendor: str, duration: float, size_bytes: int):
    """Record a successful backup"""
    BACKUP_TASKS_TOTAL.labels(status='success', vendor=vendor).inc()
    BACKUP_DURATION_SECONDS.labels(vendor=vendor).observe(duration)
    BACKUP_SIZE_BYTES.labels(vendor=vendor).observe(size_bytes)


def record_backup_failure(vendor: str, duration: float = 0):
    """Record a failed backup"""
    BACKUP_TASKS_TOTAL.labels(status='failure', vendor=vendor).inc()
    if duration > 0:
        BACKUP_DURATION_SECONDS.labels(vendor=vendor).observe(duration)


def update_device_metrics():
    """Update device gauge metrics"""
    from devices.models import Device, Vendor
    from django.db.models import Count

    # Count by status and vendor
    stats = Device.objects.values('status', 'vendor__slug').annotate(count=Count('id'))

    # Reset all gauges
    for vendor in Vendor.objects.all():
        for status in ['online', 'offline', 'unknown']:
            DEVICES_TOTAL.labels(status=status, vendor=vendor.slug).set(0)

    # Set actual values
    for stat in stats:
        vendor_slug = stat['vendor__slug'] or 'unknown'
        status = stat['status'] or 'unknown'
        DEVICES_TOTAL.labels(status=status, vendor=vendor_slug).set(stat['count'])

    # Backup enabled count
    enabled_count = Device.objects.filter(backup_enabled=True).count()
    DEVICES_BACKUP_ENABLED.set(enabled_count)


def update_schedule_metrics():
    """Update schedule gauge metrics"""
    from backups.models import BackupSchedule

    active_count = BackupSchedule.objects.filter(is_active=True).count()
    ACTIVE_SCHEDULES.set(active_count)
