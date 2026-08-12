"""
Celery tasks for backup operations
"""
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from django.db.models import F
from datetime import timedelta
from devices.models import Device
from devices.connection import backup_device_config
from .models import Backup, BackupSchedule, BackupRetentionPolicy
from core.redis_lock import DeviceLock
import logging
import threading

# Real-time WebSocket log streaming
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

# Notification services
from notifications.services import notify_backup_failed, notify_backup_success

logger = logging.getLogger(__name__)


def update_schedule_stats(schedule_id: int, success: bool):
    """
    Update backup schedule statistics atomically

    Args:
        schedule_id: BackupSchedule ID to update
        success: True for successful run, False for failed run
    """
    if not schedule_id:
        return

    field = 'successful_runs' if success else 'failed_runs'
    BackupSchedule.objects.filter(id=schedule_id).update(
        **{field: F(field) + 1}
    )


def _lock_heartbeat(lock, stop_event, interval=60, extend_by=120):
    """
    Periodically extend `lock` until `stop_event` is set — runs in its own
    thread alongside a long device connection so the lock's TTL can't
    expire out from under a backup that's still genuinely in progress.
    Pulled out as its own function (rather than a closure inline in
    backup_device) so it's directly unit-testable without needing a real
    60-second wait.
    """
    while not stop_event.wait(timeout=interval):
        lock.extend(extend_by)


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

        # ===== Acquire distributed lock to prevent concurrent connections =====
        # This prevents exhausting VTY lines (typically 5 on Cisco devices)
        lock = DeviceLock(
            device_id=device_id,
            operation='backup',
            ttl=120,  # Max 2 minutes for backup operation
            blocking=False  # Don't wait, fail immediately if device is busy
        )

        if not lock.acquire():
            # Device is currently locked by another operation
            error_msg = f"Device {device.name} is currently busy (another backup or check in progress)"
            logger.warning(error_msg)
            send_log('warning', error_msg)

            backup.status = 'failed'
            backup.success = False
            backup.error_message = 'Device locked by another operation'
            backup.completed_at = timezone.now()
            backup.duration_seconds = (backup.completed_at - backup.started_at).total_seconds()
            backup.save()

            return {'success': False, 'error': 'Device busy', 'locked': True}

        # Heartbeat thread to keep the lock alive for however long the
        # connection actually takes. The 120s TTL above is a starting
        # budget, not a hard ceiling — a real backup (enable mode +
        # several setup commands, each with up to 60s of idle-wait budget
        # for paged output) can genuinely run past 2 minutes on a slow or
        # heavily-paged device, and DeviceLock.extend() existed for exactly
        # this case but nothing ever called it: the lock would expire out
        # from under a still-running backup and let a second connection
        # (a retry, a manual "Test Connection", an overlapping schedule)
        # open a second session to the same device, exhausting VTY lines —
        # the exact race this lock exists to prevent. Extending well
        # before the TTL elapses (every 60s, refreshed to 120s) keeps the
        # margin wide even under scheduler jitter.
        stop_heartbeat = threading.Event()
        heartbeat = threading.Thread(target=_lock_heartbeat, args=(lock, stop_heartbeat), daemon=True)
        heartbeat.start()

        try:
            send_log('info', f"Lock acquired, connecting to {device.ip_address}:{device.port} via {device.protocol}...")

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

            # Perform backup (inside lock to prevent concurrent connections)
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
                backup_commands=backup_commands,
                device_id=device.id,
            )
        finally:
            stop_heartbeat.set()
            heartbeat.join(timeout=5)
            # Always release lock, even if backup fails
            lock.release()

        if success and config:
            send_log('info', f"Received configuration ({len(config)} bytes)")
            send_log('info', "Encrypting and saving to database...")

            # Save configuration with transaction
            with transaction.atomic():
                backup.set_configuration(config)
                backup.status = 'success'
                backup.success = True
                backup.completed_at = timezone.now()
                backup.duration_seconds = (backup.completed_at - backup.started_at).total_seconds()

                # Compare with previous backup
                backup.compare_with_previous()
                backup.save()

                # Update schedule statistics if this was a scheduled backup
                update_schedule_stats(schedule_id, success=True)

                # Update device status and last backup time
                device.last_backup = timezone.now()
                device.last_seen = timezone.now()
                device.backup_status = 'success'
                device.status = 'online'
                device.save(update_fields=['last_backup', 'last_seen', 'backup_status', 'status'])

            logger.info(f"Backup completed successfully for {device.name}")
            send_log('success', f"Backup complete! Has Changes: {backup.has_changes}, Size: {backup.size_bytes} bytes")

            # Send success notification
            notify_backup_success(
                device_name=device.name,
                backup_id=backup.id,
                size_bytes=backup.size_bytes,
                has_changes=backup.has_changes
            )

            return {
                'success': True,
                'backup_id': backup.id,
                'has_changes': backup.has_changes,
                'size': backup.size_bytes
            }
        else:
            # Backup failed
            send_log('error', f"Backup failed: {error_message}")

            with transaction.atomic():
                backup.status = 'failed'
                backup.success = False
                backup.error_message = error_message
                backup.completed_at = timezone.now()
                backup.duration_seconds = (backup.completed_at - backup.started_at).total_seconds()
                backup.save()

                # Update schedule statistics if this was a scheduled backup
                update_schedule_stats(schedule_id, success=False)

                device.backup_status = 'failed'
                device.status = 'offline'
                device.save(update_fields=['backup_status', 'status'])

            logger.error(f"Backup failed for {device.name}: {error_message}")

            # Send notification for backup failure
            notify_backup_failed(device.name, error_message, backup.id)

            return {'success': False, 'error': error_message}

    except Exception as e:
        # Use logger.error instead of logger.exception to avoid logging passwords in traceback
        logger.error(f"Error during backup of device {device.name}: {str(e)}")
        send_log('error', f"Critical task error: {str(e)}")

        with transaction.atomic():
            backup.status = 'failed'
            backup.success = False
            backup.error_message = str(e)
            backup.completed_at = timezone.now()
            if backup.started_at:
                backup.duration_seconds = (backup.completed_at - backup.started_at).total_seconds()
            backup.save()

            # Update schedule statistics if this was a scheduled backup (only after all retries exhausted)
            if self.request.retries >= self.max_retries:
                update_schedule_stats(schedule_id, success=False)

            device.backup_status = 'failed'
            device.status = 'offline'
            device.save(update_fields=['backup_status', 'status'])

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
    Backup multiple devices with rate limiting to prevent task storm

    Args:
        device_ids: List of device IDs to backup
        triggered_by_id: User ID who triggered the backups
        backup_type: Type of backup
        schedule_id: BackupSchedule ID if this is a scheduled backup
    """
    from celery import group
    from core.models import SystemSettings

    # Rate limiting: split into chunks to prevent overwhelming the queue
    # Get parallel workers from database settings
    sys_settings = SystemSettings.get_settings()
    chunk_size = sys_settings.backup_parallel_workers
    delay_between_chunks = 5  # seconds between chunk groups

    total_chunks = 0
    for i in range(0, len(device_ids), chunk_size):
        chunk = device_ids[i:i+chunk_size]
        job = group(
            backup_device.s(device_id, triggered_by_id, backup_type, schedule_id)
            for device_id in chunk
        )
        # Stagger chunk execution with countdown
        job.apply_async(countdown=total_chunks * delay_between_chunks)
        total_chunks += 1

    return {
        'success': True,
        'task_count': len(device_ids),
        'chunks': total_chunks,
        'chunk_size': chunk_size
    }


@shared_task
def run_scheduled_backups():
    """
    Run all scheduled backups that are due

    This task is called periodically by Celery Beat
    """
    logger.info("Running scheduled backups check")

    now = timezone.localtime(timezone.now())
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
                run_datetime = now.replace(
                    hour=schedule.run_time.hour,
                    minute=schedule.run_time.minute,
                    second=0,
                    microsecond=0
                )

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
                    run_datetime = now.replace(
                        hour=schedule.run_time.hour,
                        minute=schedule.run_time.minute,
                        second=0,
                        microsecond=0
                    )

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
            schedule.total_runs += 1
            schedule.save(update_fields=['last_run', 'total_runs'])

    logger.info(f"Scheduled backups completed. Triggered {total_backups_triggered} device backups")

    return {'success': True, 'backup_count': total_backups_triggered}


@shared_task
def cleanup_old_backups(retention_days: int = None):
    """
    Delete old backups based on retention policy from system settings

    Args:
        retention_days: Number of days to keep backups (optional, defaults to system settings)
    """
    # Get retention days from system settings if not provided
    if retention_days is None:
        from core.models import SystemSettings
        sys_settings = SystemSettings.get_settings()
        retention_days = sys_settings.backup_retention_days

    logger.info(f"Cleaning up backups older than {retention_days} days")

    cutoff_date = timezone.now() - timedelta(days=retention_days)

    # Delete old backups
    old_backups = Backup.objects.filter(created_at__lt=cutoff_date)
    count = old_backups.count()
    old_backups.delete()

    logger.info(f"Deleted {count} old backups")

    return {'success': True, 'deleted_count': count}


@shared_task
def reap_stale_backups():
    """
    Find Backup rows stuck at status='running' and mark them failed.

    backup_device() sets status='running' before attempting the connection,
    and every code path that can finish the task also flips that status —
    *except* the worker process being killed outright (OOM, the hard
    CELERY_TASK_TIME_LIMIT sending SIGKILL, a pod eviction or deploy
    restart mid-task). None of those go through any except/finally block —
    the process just stops — so the row is left at 'running' forever, with
    nothing else in the codebase that ever revisits it. The dashboard and
    device detail page then show a backup "in progress" indefinitely, with
    no way to clear it short of a manual DB fix.

    A Backup can only legitimately still be 'running' for at most
    CELERY_TASK_TIME_LIMIT — Celery guarantees the worker is killed by
    then, so anything older than that plus a safety margin is provably
    dead, not just slow.
    """
    from django.conf import settings

    cutoff = timezone.now() - timedelta(seconds=settings.CELERY_TASK_TIME_LIMIT + 300)
    stale = Backup.objects.filter(status='running', started_at__lt=cutoff)

    count = 0
    for backup in stale:
        backup.status = 'failed'
        backup.success = False
        backup.error_message = (
            'Backup task did not complete — the worker process likely died '
            'mid-task (killed, OOM, or restarted) before it could report a '
            'result. Automatically marked failed by reap_stale_backups after '
            f'{settings.CELERY_TASK_TIME_LIMIT + 300}s with no update.'
        )
        backup.completed_at = timezone.now()
        backup.duration_seconds = (backup.completed_at - backup.started_at).total_seconds()
        backup.save(update_fields=['status', 'success', 'error_message', 'completed_at', 'duration_seconds'])
        count += 1

    if count:
        logger.warning(f"Reaped {count} stale 'running' backup(s) stuck past their possible lifetime")

    return {'success': True, 'reaped_count': count}


def _backups_outside_retention(backups, keep_last_n, keep_daily, keep_weekly, keep_monthly):
    """
    Grandfather-father-son retention: given a device's successful backups
    ordered newest-first, return the ones that fall outside the policy's
    keep rules (i.e. the ones to delete).

    - The most recent `keep_last_n` are always kept, regardless of age.
    - Of what's left, keep at most one per calendar day for the next
      `keep_daily` days.
    - Then at most one per ISO week for the next `keep_weekly` weeks.
    - Then at most one per calendar month for the next `keep_monthly`
      months.
    - Anything older than every bucket above is deleted.
    """
    backups = list(backups)
    keep_ids = {b.id for b in backups[:keep_last_n]}

    now = timezone.now()
    daily_cutoff = now - timedelta(days=keep_daily)
    weekly_cutoff = daily_cutoff - timedelta(weeks=keep_weekly)
    # Months don't have a fixed length — 31-day buckets slightly
    # overestimate a month, which only errs toward keeping one extra
    # backup at the boundary, never toward deleting one that should
    # have been kept.
    monthly_cutoff = weekly_cutoff - timedelta(days=keep_monthly * 31)

    seen_days, seen_weeks, seen_months = set(), set(), set()

    for backup in backups[keep_last_n:]:
        ts = backup.created_at
        if ts >= daily_cutoff:
            bucket, seen = ts.date(), seen_days
        elif ts >= weekly_cutoff:
            iso = ts.isocalendar()
            bucket, seen = (iso[0], iso[1]), seen_weeks
        elif ts >= monthly_cutoff:
            bucket, seen = (ts.year, ts.month), seen_months
        else:
            continue  # older than every bucket — falls through to delete

        if bucket not in seen:
            seen.add(bucket)
            keep_ids.add(backup.id)

    return [b for b in backups if b.id not in keep_ids]


def apply_retention_policy(policy, dry_run=False):
    """
    Apply a BackupRetentionPolicy's keep_last_n/keep_daily/keep_weekly/
    keep_monthly rules, per device, deleting whatever falls outside them.

    Only `status='success'` backups are subject to keep/delete decisions —
    failed/partial/pending/running rows aren't real config snapshots to
    retain and are left alone here (they're covered, if at all, by the
    separate age-based cleanup_old_backups task).

    policy.devices with no entries means the policy isn't scoped to
    specific devices — treated as applying to every device, which is the
    more useful default for a "default" retention policy than silently
    matching nothing.

    Returns a dict of what happened; deletion only actually occurs when
    dry_run is False.
    """
    devices = policy.devices.all()
    if not devices.exists():
        devices = Device.objects.all()

    total_deleted = 0
    total_kept = 0

    for device in devices:
        backups = list(
            Backup.objects.filter(device=device, status='success').order_by('-created_at')
        )
        to_delete = _backups_outside_retention(
            backups, policy.keep_last_n, policy.keep_daily, policy.keep_weekly, policy.keep_monthly
        )
        total_kept += len(backups) - len(to_delete)
        total_deleted += len(to_delete)

        if not dry_run and to_delete:
            Backup.objects.filter(id__in=[b.id for b in to_delete]).delete()

    return {
        'devices_processed': devices.count(),
        'deleted_count': total_deleted,
        'kept_count': total_kept,
    }


@shared_task
def apply_all_retention_policies():
    """
    Periodic task: apply every active, auto_delete-enabled
    BackupRetentionPolicy. Manually triggering a single policy (the
    "Apply Now" button) goes through apply_retention_policy() directly
    from the view instead — auto_delete only gates this unattended,
    scheduled path, not an explicit admin action.
    """
    results = {}
    for policy in BackupRetentionPolicy.objects.filter(is_active=True, auto_delete=True):
        result = apply_retention_policy(policy, dry_run=False)
        results[policy.name] = result
        logger.info(
            f"Retention policy '{policy.name}' auto-applied: deleted {result['deleted_count']}, "
            f"kept {result['kept_count']} across {result['devices_processed']} device(s)"
        )

    return {'success': True, 'policies_applied': len(results), 'results': results}


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
            timeout=10,
            device_id=device.id,
        )

        return {'success': success, 'message': message}

    except Device.DoesNotExist:
        return {'success': False, 'message': 'Device not found'}
    except Exception as e:
        return {'success': False, 'message': str(e)}
