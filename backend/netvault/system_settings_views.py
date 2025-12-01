"""
System-wide settings API views

Settings are stored in database and applied immediately without restart
"""
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from accounts.permissions import IsAdministrator
from netvault.models import SystemSettings
import logging

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAdministrator])
def get_system_settings(request):
    """Get current system settings from database (admin only)"""

    try:
        sys_settings = SystemSettings.get_settings()

        settings_data = {
            # Email Settings
            'email': {
                'host': sys_settings.email_host,
                'port': sys_settings.email_port,
                'use_tls': sys_settings.email_use_tls,
                'host_user': sys_settings.email_host_user,
                'from_email': sys_settings.email_from_address,
                # Password not returned for security
            },

            # Telegram Settings
            'telegram': {
                'enabled': sys_settings.telegram_enabled,
                'bot_token': '***' if sys_settings.telegram_bot_token_encrypted else '',  # Masked
                'chat_id': sys_settings.telegram_chat_id,
            },

            # Notification Settings
            'notifications': {
                'notify_on_success': sys_settings.notify_on_backup_success,
                'notify_on_failure': sys_settings.notify_on_backup_failure,
                'notify_schedule_summary': sys_settings.notify_schedule_summary,
            },

            # LDAP Settings
            'ldap': {
                'enabled': sys_settings.ldap_enabled,
                'server_uri': sys_settings.ldap_server_uri,
                'bind_dn': sys_settings.ldap_bind_dn,
                'user_search_base': sys_settings.ldap_user_search_base,
                'user_search_filter': sys_settings.ldap_user_search_filter,
                # Password not returned for security
            },

            # Backup Settings
            'backup': {
                'retention_days': sys_settings.backup_retention_days,
                'parallel_workers': sys_settings.backup_parallel_workers,
            },

            # JWT Session Settings
            'jwt': {
                'access_token_lifetime': sys_settings.jwt_access_token_lifetime,
                'refresh_token_lifetime': sys_settings.jwt_refresh_token_lifetime,
            },

            # Redis Settings (read from Django settings, not editable via UI)
            'redis': {
                'url': getattr(settings, 'CELERY_BROKER_URL', 'redis://localhost:6379/0'),
            },
        }

        return Response(settings_data)

    except Exception as e:
        logger.error(f"Failed to get system settings: {e}")
        return Response(
            {'error': f'Failed to get settings: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAdministrator])
def update_system_settings(request):
    """
    Update system settings in database (admin only)

    Changes take effect immediately without requiring application restart
    """
    data = request.data

    try:
        sys_settings = SystemSettings.get_settings()

        # ===== Email settings =====
        if 'email' in data:
            email = data['email']
            if 'host' in email:
                sys_settings.email_host = email['host']
            if 'port' in email:
                sys_settings.email_port = int(email['port'])
            if 'use_tls' in email:
                sys_settings.email_use_tls = bool(email['use_tls'])
            if 'host_user' in email:
                sys_settings.email_host_user = email['host_user']
            if 'host_password' in email and email['host_password']:
                # Only update if password is provided (not empty)
                sys_settings.set_email_password(email['host_password'])
            if 'from_email' in email:
                sys_settings.email_from_address = email['from_email']

        # ===== Telegram settings =====
        if 'telegram' in data:
            telegram = data['telegram']
            if 'enabled' in telegram:
                sys_settings.telegram_enabled = bool(telegram['enabled'])
            if 'bot_token' in telegram and telegram['bot_token'] and telegram['bot_token'] != '***':
                # Only update if token is provided and not masked
                sys_settings.set_telegram_bot_token(telegram['bot_token'])
            if 'chat_id' in telegram:
                sys_settings.telegram_chat_id = telegram['chat_id']

        # ===== Notification settings =====
        if 'notifications' in data:
            notifications = data['notifications']
            if 'notify_on_success' in notifications:
                sys_settings.notify_on_backup_success = bool(notifications['notify_on_success'])
            if 'notify_on_failure' in notifications:
                sys_settings.notify_on_backup_failure = bool(notifications['notify_on_failure'])
            if 'notify_schedule_summary' in notifications:
                sys_settings.notify_schedule_summary = bool(notifications['notify_schedule_summary'])

        # ===== LDAP settings =====
        if 'ldap' in data:
            ldap = data['ldap']
            if 'enabled' in ldap:
                sys_settings.ldap_enabled = bool(ldap['enabled'])
            if 'server_uri' in ldap:
                sys_settings.ldap_server_uri = ldap['server_uri']
            if 'bind_dn' in ldap:
                sys_settings.ldap_bind_dn = ldap['bind_dn']
            if 'bind_password' in ldap and ldap['bind_password']:
                # Only update if password is provided
                sys_settings.set_ldap_bind_password(ldap['bind_password'])
            if 'user_search_base' in ldap:
                sys_settings.ldap_user_search_base = ldap['user_search_base']
            if 'user_search_filter' in ldap:
                sys_settings.ldap_user_search_filter = ldap['user_search_filter']

        # ===== Backup settings =====
        if 'backup' in data:
            backup = data['backup']
            if 'retention_days' in backup:
                retention = int(backup['retention_days'])
                if retention < 1:
                    return Response(
                        {'error': 'Retention days must be at least 1'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                sys_settings.backup_retention_days = retention
            if 'parallel_workers' in backup:
                workers = int(backup['parallel_workers'])
                if workers < 1 or workers > 50:
                    return Response(
                        {'error': 'Parallel workers must be between 1 and 50'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                sys_settings.backup_parallel_workers = workers

        # ===== JWT settings =====
        if 'jwt' in data:
            jwt = data['jwt']
            if 'access_token_lifetime' in jwt:
                lifetime = int(jwt['access_token_lifetime'])
                if lifetime < 5 or lifetime > 1440:
                    return Response(
                        {'error': 'Access token lifetime must be between 5 and 1440 minutes'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                sys_settings.jwt_access_token_lifetime = lifetime
            if 'refresh_token_lifetime' in jwt:
                lifetime = int(jwt['refresh_token_lifetime'])
                if lifetime < 60 or lifetime > 43200:
                    return Response(
                        {'error': 'Refresh token lifetime must be between 60 and 43200 minutes'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                sys_settings.jwt_refresh_token_lifetime = lifetime

        # Save all changes (cache is automatically cleared on save)
        sys_settings.save()

        logger.info(f"System settings updated by user {request.user.email}")

        return Response({
            'success': True,
            'message': 'Settings updated successfully. Changes are effective immediately.'
        })

    except ValueError as e:
        return Response(
            {'error': f'Invalid value: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Failed to update system settings: {e}")
        return Response(
            {'error': f'Failed to update settings: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAdministrator])
def test_email_settings(request):
    """Test email configuration by sending a test email"""

    try:
        from notifications.services import send_email_notification

        test_email = request.data.get('email', request.user.email)

        # Send test email using current system settings
        success = send_email_notification(
            'Test Email',
            'This is a test email from NetVault. Your email configuration is working correctly!',
            recipient_list=[test_email]
        )

        if success:
            return Response({
                'success': True,
                'message': f'Test email sent successfully to {test_email}'
            })
        else:
            return Response(
                {'error': 'Failed to send test email. Check email settings and logs.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    except Exception as e:
        logger.error(f"Test email failed: {e}")
        return Response(
            {'error': f'Failed to send test email: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAdministrator])
def test_telegram_settings(request):
    """Test Telegram configuration"""

    try:
        from netvault.models import SystemSettings
        import requests

        sys_settings = SystemSettings.get_settings()

        # Allow overriding with test values
        bot_token = request.data.get('bot_token')
        if not bot_token or bot_token == '***':
            bot_token = sys_settings.get_telegram_bot_token()

        chat_id = request.data.get('chat_id', sys_settings.telegram_chat_id)

        if not bot_token or not chat_id:
            return Response(
                {'error': 'Bot token and chat ID are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
        response = requests.post(url, json={
            'chat_id': chat_id,
            'text': '✅ NetVault: Telegram configuration test successful!'
        }, timeout=10)

        if response.status_code == 200:
            return Response({
                'success': True,
                'message': 'Test message sent successfully to Telegram'
            })
        else:
            return Response(
                {'error': f'Telegram API error: {response.text}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    except Exception as e:
        logger.error(f"Test Telegram failed: {e}")
        return Response(
            {'error': f'Failed to send test message: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
