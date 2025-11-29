"""
Celery configuration for NetVault
"""
import os
from celery import Celery
from celery.schedules import crontab

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
    'cleanup-old-backups': {
        'task': 'backups.tasks.cleanup_old_backups',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
}

app.conf.timezone = 'UTC'


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
