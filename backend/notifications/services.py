"""
Notification services for email and Telegram
"""
import logging
from django.conf import settings
from django.core.mail import send_mail
import requests

logger = logging.getLogger(__name__)


def send_email_notification(subject: str, message: str, recipient_list: list = None):
    """
    Send email notification

    Args:
        subject: Email subject
        message: Email body
        recipient_list: List of recipient emails (defaults to admin email)
    """
    try:
        if not getattr(settings, 'EMAIL_HOST', None):
            logger.warning("Email not configured, skipping notification")
            return False

        if not recipient_list:
            # Send to admin user email (first administrator in system)
            from accounts.models import User
            admin = User.objects.filter(role='administrator', is_active=True).first()
            if not admin or not admin.email:
                logger.warning("No administrator email found")
                return False
            recipient_list = [admin.email]

        send_mail(
            subject=f'[NetVault] {subject}',
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            fail_silently=False,
        )

        logger.info(f"Email sent to {recipient_list}: {subject}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False


def send_telegram_notification(message: str):
    """
    Send Telegram notification

    Args:
        message: Message text
    """
    try:
        telegram_enabled = getattr(settings, 'TELEGRAM_ENABLED', False)
        if not telegram_enabled:
            logger.debug("Telegram not enabled, skipping notification")
            return False

        bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
        chat_id = getattr(settings, 'TELEGRAM_CHAT_ID', '')

        if not bot_token or not chat_id:
            logger.warning("Telegram not configured properly")
            return False

        url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
        response = requests.post(url, json={
            'chat_id': chat_id,
            'text': f'🔔 *NetVault Alert*\n\n{message}',
            'parse_mode': 'Markdown'
        }, timeout=10)

        if response.status_code == 200:
            logger.info(f"Telegram message sent: {message[:50]}...")
            return True
        else:
            logger.error(f"Telegram API error: {response.text}")
            return False

    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False


def notify_backup_success(device_name: str, backup_id: int = None, size_bytes: int = 0, has_changes: bool = False):
    """
    Send notification when backup succeeds

    Args:
        device_name: Name of the device
        backup_id: Backup record ID
        size_bytes: Backup size in bytes
        has_changes: Whether config changed
    """
    from django.conf import settings

    # Check if notifications are enabled
    if not getattr(settings, 'NOTIFY_ON_BACKUP_SUCCESS', False):
        return

    subject = f"Backup Success: {device_name}"

    size_kb = size_bytes / 1024 if size_bytes else 0
    changes_text = "✓ Configuration changed" if has_changes else "○ No changes"

    message = f"""Backup completed successfully for device: {device_name}

{changes_text}
Size: {size_kb:.1f} KB
Time: {get_current_time()}
Backup ID: {backup_id if backup_id else 'N/A'}"""

    # Send both email and Telegram
    send_email_notification(subject, message)
    send_telegram_notification(f"✅ Backup success: *{device_name}*\n{changes_text} • {size_kb:.1f} KB")


def notify_backup_failed(device_name: str, error_message: str, backup_id: int = None):
    """
    Send notification when backup fails

    Args:
        device_name: Name of the device
        error_message: Error description
        backup_id: Backup record ID
    """
    from django.conf import settings

    # Check if notifications are enabled
    if not getattr(settings, 'NOTIFY_ON_BACKUP_FAILURE', True):
        return

    subject = f"Backup Failed: {device_name}"

    message = f"""Backup failed for device: {device_name}

Error: {error_message}

Time: {get_current_time()}
Backup ID: {backup_id if backup_id else 'N/A'}

Please check the device status and configuration."""

    # Send both email and Telegram
    send_email_notification(subject, message)
    send_telegram_notification(f"❌ Backup failed: *{device_name}*\n{error_message}")


def notify_multiple_failures(failed_count: int, total_count: int):
    """
    Send notification when multiple backups fail in a scheduled run

    Args:
        failed_count: Number of failed backups
        total_count: Total number of backups
    """
    subject = f"Multiple Backup Failures: {failed_count}/{total_count}"
    
    message = f"""Warning: Multiple backups have failed!

Failed: {failed_count} devices
Total: {total_count} devices
Success rate: {((total_count - failed_count) / total_count * 100):.1f}%

Time: {get_current_time()}

Please check the audit logs for details."""

    send_email_notification(subject, message)
    send_telegram_notification(
        f"⚠️ *Multiple backup failures*\n"
        f"Failed: {failed_count}/{total_count} devices"
    )


def notify_device_offline(device_name: str, last_seen: str):
    """
    Send notification when device goes offline

    Args:
        device_name: Name of the device
        last_seen: Last seen timestamp
    """
    subject = f"Device Offline: {device_name}"
    
    message = f"""Device has gone offline: {device_name}

Last seen: {last_seen}
Time: {get_current_time()}

Please check the device connectivity."""

    # Only send critical device offline notifications for important devices
    # (to avoid spam, you can add device.criticality check in caller)
    send_email_notification(subject, message)
    send_telegram_notification(f"🔴 Device offline: *{device_name}*")


def get_current_time():
    """Get current time as formatted string"""
    from django.utils import timezone
    return timezone.now().strftime("%Y-%m-%d %H:%M:%S")
