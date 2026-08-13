"""
Notification services for email and Telegram
"""
import logging
from django.core.mail import send_mail, EmailMessage
from django.core.mail.backends.smtp import EmailBackend
import requests

# Shared with accounts device-scope RBAC — see core.device_filters for
# the actual implementation and why this lives there, not here.
from core.device_filters import device_matches_filters as _device_matches_filters

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
        from core.models import SystemSettings
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


def send_telegram_notification(message: str, chat_id: str = None):
    """
    Send Telegram notification using system settings from database

    Args:
        message: Message text
        chat_id: Override the globally configured chat ID (used by
            per-rule NotificationRule.telegram_chat_ids). The bot token
            itself is always the one global bot configured in
            SystemSettings — rules don't get their own bot.
    """
    try:
        # Get system settings from database (cached)
        from core.models import SystemSettings
        sys_settings = SystemSettings.get_settings()

        # Check if Telegram is enabled
        if not sys_settings.telegram_enabled:
            logger.debug("Telegram not enabled, skipping notification")
            return False

        bot_token = sys_settings.get_telegram_bot_token()  # Decrypted
        chat_id = chat_id or sys_settings.telegram_chat_id

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


def send_webhook_notification(url: str, payload: dict):
    """
    POST a JSON payload to an arbitrary webhook URL (NotificationRule.webhook_url).

    Args:
        url: Destination webhook URL
        payload: JSON-serializable body (trigger, subject, message, plus
            whatever event-specific fields the caller adds)
    """
    if not url:
        logger.warning("Webhook rule has no URL configured, skipping notification")
        return False

    try:
        response = requests.post(url, json=payload, timeout=10)
        if 200 <= response.status_code < 300:
            logger.info(f"Webhook sent to {url}: HTTP {response.status_code}")
            return True

        logger.error(f"Webhook to {url} returned HTTP {response.status_code}: {response.text[:200]}")
        return False

    except Exception as e:
        logger.error(f"Failed to send webhook to {url}: {e}")
        return False



def dispatch_rules(trigger: str, device=None, subject: str = '', message: str = '',
                    telegram_message: str = None, webhook_payload: dict = None):
    """
    Fan a notification event out to every active NotificationRule matching
    `trigger` (and, if the event is device-scoped, matching the rule's
    device_filters), on top of whatever the flat SystemSettings.notify_on_*
    toggle already sent. Every attempt is logged to Notification, so the
    rule system has its own delivery audit trail independent of app logs.

    A deployment that never creates a rule behaves exactly as before —
    this is purely additive to the existing notify_backup_success/
    notify_backup_failed/etc functions, not a replacement for them.
    """
    from django.utils import timezone
    from .models import NotificationRule, Notification

    rules = NotificationRule.objects.filter(trigger=trigger, is_active=True)

    for rule in rules:
        if not _device_matches_filters(device, rule.device_filters):
            continue

        ok = False
        recipient_desc = ''

        if rule.channel == 'email':
            recipients = rule.email_recipients or None
            ok = send_email_notification(subject, message, recipient_list=recipients)
            recipient_desc = ', '.join(recipients) if recipients else 'default administrator'

        elif rule.channel == 'telegram':
            text = telegram_message or message
            if rule.telegram_chat_ids:
                ok = all(send_telegram_notification(text, chat_id=cid) for cid in rule.telegram_chat_ids)
                recipient_desc = ', '.join(rule.telegram_chat_ids)
            else:
                ok = send_telegram_notification(text)
                recipient_desc = 'default chat'

        elif rule.channel == 'webhook':
            payload = webhook_payload or {'trigger': trigger, 'subject': subject, 'message': message}
            ok = send_webhook_notification(rule.webhook_url, payload)
            recipient_desc = rule.webhook_url

        else:
            continue

        Notification.objects.create(
            rule=rule,
            status='sent' if ok else 'failed',
            title=subject or trigger,
            message=message,
            channel=rule.channel,
            recipient=recipient_desc,
            sent_at=timezone.now() if ok else None,
            error_message='' if ok else 'Delivery failed — see application logs for details',
        )


def notify_backup_success(device_name: str, backup_id: int = None, size_bytes: int = 0,
                           has_changes: bool = False, device=None):
    """
    Send notification when backup succeeds

    Args:
        device_name: Name of the device
        backup_id: Backup record ID
        size_bytes: Backup size in bytes
        has_changes: Whether config changed
        device: The Device instance (optional) — enables per-rule
            device_filters matching in dispatch_rules(); the flat
            SystemSettings toggle below doesn't need it.
    """
    subject = f"Backup Success: {device_name}"

    size_kb = size_bytes / 1024 if size_bytes else 0
    changes_text = "✓ Configuration changed" if has_changes else "○ No changes"

    message = f"""Backup completed successfully for device: {device_name}

{changes_text}
Size: {size_kb:.1f} KB
Time: {get_current_time()}
Backup ID: {backup_id if backup_id else 'N/A'}"""

    telegram_message = f"✅ Backup success: *{device_name}*\n{changes_text} • {size_kb:.1f} KB"

    # Check if notifications are enabled (from database settings)
    from core.models import SystemSettings
    sys_settings = SystemSettings.get_settings()

    if sys_settings.notify_on_backup_success:
        send_email_notification(subject, message)
        send_telegram_notification(telegram_message)

    dispatch_rules(
        'backup_success', device=device, subject=subject, message=message,
        telegram_message=telegram_message,
        webhook_payload={
            'trigger': 'backup_success', 'device': device_name, 'backup_id': backup_id,
            'has_changes': has_changes, 'size_bytes': size_bytes,
        },
    )


def notify_backup_failed(device_name: str, error_message: str, backup_id: int = None, device=None):
    """
    Send notification when backup fails

    Args:
        device_name: Name of the device
        error_message: Error description
        backup_id: Backup record ID
        device: The Device instance (optional) — enables per-rule
            device_filters matching in dispatch_rules().
    """
    subject = f"Backup Failed: {device_name}"

    message = f"""Backup failed for device: {device_name}

Error: {error_message}

Time: {get_current_time()}
Backup ID: {backup_id if backup_id else 'N/A'}

Please check the device status and configuration."""

    telegram_message = f"❌ Backup failed: *{device_name}*\n{error_message}"

    # Check if notifications are enabled (from database settings)
    from core.models import SystemSettings
    sys_settings = SystemSettings.get_settings()

    if sys_settings.notify_on_backup_failure:
        send_email_notification(subject, message)
        send_telegram_notification(telegram_message)

    dispatch_rules(
        'backup_failed', device=device, subject=subject, message=message,
        telegram_message=telegram_message,
        webhook_payload={
            'trigger': 'backup_failed', 'device': device_name, 'backup_id': backup_id,
            'error': error_message,
        },
    )


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


def notify_device_offline(device_name: str, last_seen: str, device=None):
    """
    Send notification when device goes offline

    Args:
        device_name: Name of the device
        last_seen: Last seen timestamp
        device: The Device instance (optional) — enables per-rule
            device_filters matching in dispatch_rules(), e.g. a rule
            scoped to criticality=critical devices only.
    """
    subject = f"Device Offline: {device_name}"

    message = f"""Device has gone offline: {device_name}

Last seen: {last_seen}
Time: {get_current_time()}

Please check the device connectivity."""

    telegram_message = f"🔴 Device offline: *{device_name}*"

    # Unlike backup success/failure there's no flat SystemSettings toggle
    # for this one — it always sends via the global email+Telegram config.
    # If that's too noisy, scope a device_offline rule to just the
    # devices that matter (criticality filter) instead of a global switch.
    send_email_notification(subject, message)
    send_telegram_notification(telegram_message)

    dispatch_rules(
        'device_offline', device=device, subject=subject, message=message,
        telegram_message=telegram_message,
        webhook_payload={'trigger': 'device_offline', 'device': device_name, 'last_seen': last_seen},
    )


def notify_host_key_mismatch(device_name: str, ip_address: str, expected: str, received: str):
    """
    Send notification when a device's SSH host key changes unexpectedly.

    Unlike backup-failure notifications, this always fires regardless of the
    notify_on_backup_failure setting — a host key mismatch is a potential
    MITM indicator, not a routine operational failure, and connections to
    the device are refused until an administrator reviews and approves the
    new key from the device detail page.

    Args:
        device_name: Name of the device
        ip_address: Device IP address
        expected: Previously pinned key, as "type fingerprint"
        received: Newly presented key, as "type fingerprint"
    """
    subject = f"SSH Host Key Changed: {device_name}"

    message = f"""The SSH host key presented by a device no longer matches the one NetVault has on file.

Device: {device_name} ({ip_address})
Expected: {expected}
Received: {received}

Time: {get_current_time()}

This can happen after a legitimate device replacement, IOS upgrade, or
manual key regeneration — but it is also exactly what a machine-in-the-
middle attack looks like. Connections to this device (including scheduled
backups) will be refused until you verify the new key out-of-band (e.g.
via the device's console, not over the network) and approve it from the
device's detail page in NetVault."""

    send_email_notification(subject, message)
    send_telegram_notification(
        f"🔑⚠️ *SSH host key changed*\n"
        f"Device: *{device_name}* ({ip_address})\n"
        f"Expected: `{expected}`\n"
        f"Received: `{received}`\n"
        f"Connections refused until approved in NetVault."
    )


def get_current_time():
    """Get current time as formatted string"""
    from django.utils import timezone
    return timezone.now().strftime("%Y-%m-%d %H:%M:%S")
