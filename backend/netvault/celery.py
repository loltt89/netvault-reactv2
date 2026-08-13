"""
Celery configuration for NetVault
"""
import os
from celery import Celery
from celery.schedules import crontab
from django.conf import settings

# Set default Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netvault.settings')

app = Celery('netvault')

# Load config from Django settings with CELERY namespace
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# Celery Beat schedule for periodic tasks
app.conf.beat_schedule = {
    'run-scheduled-backups': {
        'task': 'backups.tasks.run_scheduled_backups',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    'reap-stale-backups': {
        'task': 'backups.tasks.reap_stale_backups',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
    'cleanup-old-backups': {
        'task': 'backups.tasks.cleanup_old_backups',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM server-local time
    },
    'apply-retention-policies': {
        'task': 'backups.tasks.apply_all_retention_policies',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM server-local, after cleanup above
    },
    'stale-backup-digest': {
        'task': 'backups.tasks.send_stale_backup_digest',
        'schedule': crontab(day_of_week=1, hour=8, minute=0),  # Monday 08:00 server-local time
    },
}

# Follow Django's TIME_ZONE (settings.py: auto-detected from /etc/timezone,
# or a .env TIME_ZONE override — see get_system_timezone()) rather than a
# hardcoded 'UTC'. This used to silently override CELERY_TIMEZONE = TIME_ZONE
# in settings.py (already picked up correctly by config_from_object() above,
# then clobbered back to UTC by this line) — on any deployment whose server
# isn't itself UTC, every crontab(hour=..., minute=...) entry above would
# fire at the wrong server-local wall-clock hour. run_scheduled_backups()'s
# own BackupSchedule.run_time comparison was never affected — it already
# calls timezone.localtime() internally regardless of Celery's timezone.
app.conf.timezone = settings.TIME_ZONE


@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery"""
    pass
