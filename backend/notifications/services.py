"""
Notification services for email and Telegram
"""
import logging
from django.core.mail import send_mail, EmailMessage
from django.core.mail.backends.smtp import EmailBackend
import requests

logger = logging.getLogger(__name__)


def send_email_notification(subject: str, message: str, recipient_list: list = None):
    """
    Send email notification using system settings from database

    Args:
        subject: Email subject
        message: Email body
        recipient_list: List of recipient emails (defaults to admin email)
    """
    try:
        # Get system settings from database (cached)
        from netvault.models import SystemSettings
        sys_settings = SystemSettings.get_settings()

        # Check if email is configured
        if not sys_settings.email_host or not sys_settings.email_host_user:
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

        # Create email backend with settings from database
        connection = EmailBackend(
            host=sys_settings.email_host,
            port=sys_settings.email_port,
            username=sys_settings.email_host_user,
            password=sys_settings.get_email_password(),  # Decrypted
            use_tls=sys_settings.email_use_tls,
            fail_silently=False,
        )

        # Send email using custom backend
        email = EmailMessage(
            subject=f'[NetVault] {subject}',
            body=message,
            from_email=sys_settings.email_from_address,
            to=recipient_list,
            connection=connection,
        )
        email.send()

        logger.info(f"Email sent to {recipient_list}: {subject}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False


def send_telegram_notification(message: str):
    """
    Send Telegram notification using system settings from database

    Args:
        message: Message text
    """
    try:
        # Get system settings from database (cached)
        from netvault.models import SystemSettings
        sys_settings = SystemSettings.get_settings()

        # Check if Telegram is enabled
        if not sys_settings.telegram_enabled:
            logger.debug("Telegram not enabled, skipping notification")
            return False

        bot_token = sys_settings.get_telegram_bot_token()  # Decrypted
        chat_id = sys_settings.telegram_chat_id

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
    # Check if notifications are enabled (from database settings)
    from netvault.models import SystemSettings
    sys_settings = SystemSettings.get_settings()

    if not sys_settings.notify_on_backup_success:
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
    # Check if notifications are enabled (from database settings)
    from netvault.models import SystemSettings
    sys_settings = SystemSettings.get_settings()

    if not sys_settings.notify_on_backup_failure:
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
