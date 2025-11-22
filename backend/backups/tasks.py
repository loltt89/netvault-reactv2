"""
Celery tasks for backup operations
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from devices.models import Device
from devices.connection import backup_device_config
from .models import Backup, BackupSchedule
import logging

# Real-time WebSocket log streaming
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

# Notification services
from notifications.services import notify_backup_failed

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def backup_device(self, device_id: int, triggered_by_id: int = None, backup_type: str = 'manual', schedule_id: int = None):
    """
    Backup a single device configuration

    Args:
        device_id: Device ID to backup
        triggered_by_id: User ID who triggered the backup
        backup_type: Type of backup (manual, scheduled, automatic)
    """
    try:
        device = Device.objects.get(id=device_id)
    except Device.DoesNotExist:
        logger.error(f"Device {device_id} not found")
        return {'success': False, 'error': 'Device not found'}

    # Create backup record
    backup = Backup.objects.create(
        device=device,
        status='running',
        backup_type=backup_type,
        schedule_id=schedule_id,
        triggered_by_id=triggered_by_id,
        started_at=timezone.now()
    )

    # ===== Real-time WebSocket log streaming =====
    channel_layer = get_channel_layer()
    log_group_name = f'user_{triggered_by_id}_logs' if triggered_by_id else None

    def send_log(log_type, text):
        """Send real-time log to user via WebSocket"""
        if log_group_name and channel_layer:
            try:
                async_to_sync(channel_layer.group_send)(
                    log_group_name,
                    {
                        'type': 'send_log_message',
                        'message': {
                            'type': log_type,
                            'text': text,
                            'device_name': device.name,
                            'task_id': self.request.id
                        }
                    }
                )
            except Exception as e:
                logger.error(f"Failed to send WebSocket log: {e}")
    # ===== End WebSocket setup =====

    try:
        logger.info(f"Starting backup for device {device.name} ({device.ip_address})")
        send_log('info', f"Task {self.request.id} received")
        send_log('info', f"Connecting to {device.ip_address}:{device.port} via {device.protocol}...")

        # Get device credentials
        username = device.username
        password = device.get_password()
        enable_password = device.get_enable_password() if device.enable_password_encrypted else None

        # Get backup commands (custom or vendor defaults)
        backup_commands = None
        if device.custom_commands:
            backup_commands = device.custom_commands
        elif device.vendor and device.vendor.backup_commands:
            backup_commands = device.vendor.backup_commands

        # Get vendor slug (with fallback if vendor is None)
        vendor_slug = device.vendor.slug if device.vendor else 'generic'

        # Perform backup
        from django.conf import settings
        success, config, error_message = backup_device_config(
            host=device.ip_address,
            port=device.port,
            protocol=device.protocol,
            username=username,
            password=password,
            vendor=vendor_slug,
            enable_password=enable_password,
            timeout=settings.BACKUP_CONNECTION_TIMEOUT,
            backup_commands=backup_commands
        )

        if success and config:
            send_log('info', f"Received configuration ({len(config)} bytes)")
            send_log('info', "Encrypting and saving to database...")

            # Save configuration
            backup.set_configuration(config)
            backup.status = 'success'
            backup.success = True
            backup.completed_at = timezone.now()
            backup.duration_seconds = (backup.completed_at - backup.started_at).total_seconds()

            # Compare with previous backup
            backup.compare_with_previous()
            backup.save()

            # Update schedule statistics if this was a scheduled backup
            if schedule_id:
                from backups.models import BackupSchedule
                try:
                    schedule = BackupSchedule.objects.get(id=schedule_id)
                    schedule.total_runs += 1
                    schedule.successful_runs += 1
                    schedule.save(update_fields=['total_runs', 'successful_runs'])
                except BackupSchedule.DoesNotExist:
                    pass

            # Update device status and last backup time
            device.last_backup = timezone.now()
            device.last_seen = timezone.now()
            device.backup_status = 'success'
            device.status = 'online'
            device.save()

            logger.info(f"Backup completed successfully for {device.name}")
            send_log('success', f"Backup complete! Has Changes: {backup.has_changes}, Size: {backup.size_bytes} bytes")

            return {
                'success': True,
                'backup_id': backup.id,
                'has_changes': backup.has_changes,
                'size': backup.size_bytes
            }
        else:
            # Backup failed
            send_log('error', f"Backup failed: {error_message}")

            backup.status = 'failed'
            backup.success = False
            backup.error_message = error_message
            backup.completed_at = timezone.now()
            backup.duration_seconds = (backup.completed_at - backup.started_at).total_seconds()
            backup.save()

            # Update schedule statistics if this was a scheduled backup
            if schedule_id:
                from backups.models import BackupSchedule
                try:
                    schedule = BackupSchedule.objects.get(id=schedule_id)
                    schedule.total_runs += 1
                    schedule.failed_runs += 1
                    schedule.save(update_fields=['total_runs', 'failed_runs'])
                except BackupSchedule.DoesNotExist:
                    pass

            device.backup_status = 'failed'
            device.status = 'offline'
            device.save()

            logger.error(f"Backup failed for {device.name}: {error_message}")

            # Send notification for backup failure
            notify_backup_failed(device.name, error_message, backup.id)

            return {'success': False, 'error': error_message}

    except Exception as e:
        # Use logger.error instead of logger.exception to avoid logging passwords in traceback
        logger.error(f"Error during backup of device {device.name}: {str(e)}")
        send_log('error', f"Critical task error: {str(e)}")

        backup.status = 'failed'
        backup.success = False
        backup.error_message = str(e)
        backup.completed_at = timezone.now()
        if backup.started_at:
            backup.duration_seconds = (backup.completed_at - backup.started_at).total_seconds()
        backup.save()

        # Update schedule statistics if this was a scheduled backup (only after all retries exhausted)
        if schedule_id and self.request.retries >= self.max_retries:
            from backups.models import BackupSchedule
            try:
                schedule = BackupSchedule.objects.get(id=schedule_id)
                schedule.failed_runs += 1
                schedule.save(update_fields=['failed_runs'])
            except BackupSchedule.DoesNotExist:
                pass

        device.backup_status = 'failed'
        device.status = 'offline'
        device.save()

        # Retry if possible
        if self.request.retries < self.max_retries:
            send_log('warn', f"Retrying... (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=e, countdown=60)

        # Send notification only after all retries exhausted
        notify_backup_failed(device.name, str(e), backup.id)

        return {'success': False, 'error': str(e)}


@shared_task
def backup_multiple_devices(device_ids: list, triggered_by_id: int = None, backup_type: str = 'manual', schedule_id: int = None):
    """
    Backup multiple devices in parallel

    Args:
        device_ids: List of device IDs to backup
        triggered_by_id: User ID who triggered the backups
        backup_type: Type of backup
        schedule_id: BackupSchedule ID if this is a scheduled backup
    """
    from celery import group

    # Create a group of backup tasks
    job = group(backup_device.s(device_id, triggered_by_id, backup_type, schedule_id) for device_id in device_ids)
    results = job.apply_async()

    return {
        'success': True,
        'task_count': len(device_ids),
        'group_id': results.id
    }


@shared_task
def run_scheduled_backups():
    """
    Run all scheduled backups that are due

    This task is called periodically by Celery Beat
    """
    logger.info("Running scheduled backups check")

    now = timezone.now()
    current_time = now.time()
    current_weekday = now.weekday()  # Monday=0, Sunday=6

    # Find active schedules
    schedules = BackupSchedule.objects.filter(is_active=True)

    total_backups_triggered = 0

    for schedule in schedules:
        should_run = False

        if schedule.frequency == 'hourly':
            # Check if last run was more than 1 hour ago
            if not schedule.last_run or (now - schedule.last_run) >= timedelta(hours=1):
                should_run = True

        elif schedule.frequency == 'daily':
            # Check if it's time and not run today
            if schedule.run_time:
                # Run time must be passed, but not more than 10 minutes ago (2 check cycles)
                run_datetime = timezone.datetime.combine(now.date(), schedule.run_time)

                if now >= run_datetime:
                    time_since_run = (now - run_datetime).total_seconds()
                    # Only run if within 10 minutes of scheduled time (allows 2 check cycles at 5min interval)
                    if time_since_run <= 600:  # 10 minutes
                        if not schedule.last_run or schedule.last_run.date() < now.date():
                            should_run = True

        elif schedule.frequency == 'weekly':
            # Check if it's the right day and time
            if schedule.run_time and schedule.run_days:
                if current_weekday in [int(d) for d in schedule.run_days.split(',')]:
                    # Run time must be passed, but not more than 10 minutes ago
                    run_datetime = timezone.datetime.combine(now.date(), schedule.run_time)

                    if now >= run_datetime:
                        time_since_run = (now - run_datetime).total_seconds()
                        # Only run if within 10 minutes of scheduled time
                        if time_since_run <= 600:  # 10 minutes
                            if not schedule.last_run or schedule.last_run.date() < now.date():
                                should_run = True

        if should_run:
            logger.info(f"Schedule due: {schedule.name}")

            # Get devices for this schedule (with backup_enabled=True)
            from devices.models import Device

            # If schedule has specific devices assigned, use them
            if schedule.devices.exists():
                device_ids = list(schedule.devices.filter(backup_enabled=True).values_list('id', flat=True))
            # Otherwise, backup all devices with backup_enabled=True
            else:
                device_ids = list(Device.objects.filter(backup_enabled=True).values_list('id', flat=True))

            # Trigger backups for this schedule with schedule_id for statistics
            if device_ids:
                logger.info(f"Triggering backup for {len(device_ids)} devices from schedule '{schedule.name}'")
                backup_multiple_devices.delay(device_ids, backup_type='scheduled', schedule_id=schedule.id)
                total_backups_triggered += len(device_ids)

            # Update schedule stats
            schedule.last_run = now
            schedule.save(update_fields=['last_run'])

    logger.info(f"Scheduled backups completed. Triggered {total_backups_triggered} device backups")

    return {'success': True, 'backup_count': total_backups_triggered}


@shared_task
def cleanup_old_backups(retention_days: int = 90):
    """
    Delete old backups based on retention policy

    Args:
        retention_days: Number of days to keep backups
    """
    logger.info(f"Cleaning up backups older than {retention_days} days")

    cutoff_date = timezone.now() - timedelta(days=retention_days)

    # Delete old backups
    old_backups = Backup.objects.filter(created_at__lt=cutoff_date)
    count = old_backups.count()
    old_backups.delete()

    logger.info(f"Deleted {count} old backups")

    return {'success': True, 'deleted_count': count}


@shared_task
def test_device_connection(device_id: int):
    """
    Test connection to a device

    Args:
        device_id: Device ID to test
    """
    from devices.connection import test_connection

    try:
        device = Device.objects.get(id=device_id)

        username = device.username
        password = device.get_password()
        enable_password = device.get_enable_password() if device.enable_password_encrypted else None

        success, message = test_connection(
            host=device.ip_address,
            port=device.port,
            protocol=device.protocol,
            username=username,
            password=password,
            enable_password=enable_password,
            timeout=10
        )

        return {'success': success, 'message': message}

    except Device.DoesNotExist:
        return {'success': False, 'message': 'Device not found'}
    except Exception as e:
        return {'success': False, 'message': str(e)}


@shared_task
def check_single_device_status(device_id: int):
    """
    Check status of a single device using hybrid two-level approach:
    LEVEL 1: Fast TCP check (does NOT consume VTY) - 95% of checks stop here
    LEVEL 2: Full SSH check only if TCP fails (consumes VTY) - catches devices behind firewall

    This approach saves ~95% of VTY lines compared to SSH-only checks.

    Args:
        device_id: Device ID to check
    """
    from devices.connection import test_connection, tcp_ping
    from django.conf import settings

    try:
        device = Device.objects.get(id=device_id)
        old_status = device.status

        tcp_timeout = getattr(settings, 'DEVICE_CHECK_TCP_TIMEOUT', 2)
        ssh_timeout = getattr(settings, 'DEVICE_CHECK_SSH_TIMEOUT', 5)

        # LEVEL 1: Fast TCP check (2 seconds, NO VTY consumption)
        port_open = tcp_ping(device.ip_address, device.port, timeout=tcp_timeout)

        if port_open:
            # Port is open → device is online
            device.status = 'online'
            device.last_seen = timezone.now()

            if old_status != device.status:
                device.save(update_fields=['status', 'last_seen'])
                logger.info(f"Device {device.name} online (TCP check)")
                return {'device_id': device_id, 'status': 'online', 'changed': True, 'method': 'tcp'}

            return {'device_id': device_id, 'status': 'online', 'changed': False, 'method': 'tcp'}

        # LEVEL 2: TCP failed → Full SSH check (may consume VTY)
        logger.info(f"TCP check failed for {device.name}, trying SSH...")

        username = device.username
        password = device.get_password()
        enable_password = device.get_enable_password() if device.enable_password_encrypted else None

        success, message = test_connection(
            host=device.ip_address,
            port=device.port,
            protocol=device.protocol,
            username=username,
            password=password,
            enable_password=enable_password,
            timeout=ssh_timeout
        )

        if success:
            # SSH works (device behind firewall/NAT)
            device.status = 'online'
            device.last_seen = timezone.now()
        else:
            # Both TCP and SSH failed → offline
            device.status = 'offline'

        # Save if status changed
        if old_status != device.status:
            device.save(update_fields=['status', 'last_seen'])
            logger.info(f"Device {device.name} {device.status} (SSH check)")
            return {'device_id': device_id, 'status': device.status, 'changed': True, 'method': 'ssh'}

        return {'device_id': device_id, 'status': device.status, 'changed': False, 'method': 'ssh'}

    except Device.DoesNotExist:
        logger.error(f"Device {device_id} not found")
        return {'device_id': device_id, 'error': 'Device not found'}
    except Exception as e:
        logger.error(f"Error checking status for device {device_id}: {str(e)}")
        try:
            device = Device.objects.get(id=device_id)
            if device.status != 'offline':
                device.status = 'offline'
                device.save(update_fields=['status'])
                return {'device_id': device_id, 'status': 'offline', 'changed': True, 'error': str(e)}
        except:
            pass
        return {'device_id': device_id, 'error': str(e)}


@shared_task
def check_devices_status():
    """
    Check status of all devices by attempting to connect (parallel execution)

    This task runs periodically to update device online/offline status
    """
    logger.info("Starting devices status check")

    device_ids = list(Device.objects.values_list('id', flat=True))

    if not device_ids:
        logger.info("No devices to check")
        return {'success': True, 'total_devices': 0, 'updated_count': 0}

    # Check devices in parallel using Celery group
    from celery import group
    job = group(check_single_device_status.s(device_id) for device_id in device_ids)
    result = job.apply_async()

    # Wait for all checks to complete (with timeout)
    try:
        results = result.get(timeout=60)  # 60 seconds timeout
        updated_count = sum(1 for r in results if r.get('changed', False))

        logger.info(f"Device status check completed. Checked {len(device_ids)} devices, updated {updated_count}")

        return {
            'success': True,
            'total_devices': len(device_ids),
            'updated_count': updated_count
        }
    except Exception as e:
        logger.error(f"Error waiting for device status checks: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'total_devices': len(device_ids)
        }
