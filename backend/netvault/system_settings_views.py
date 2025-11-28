"""
System-wide settings API views
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.conf import settings
from accounts.permissions import IsAdministrator
import os


@api_view(['GET'])
@permission_classes([IsAdministrator])
def get_system_settings(request):
    """Get current system settings (admin only)"""

    # Read current settings from .env or Django settings
    settings_data = {
        # Email Settings
        'email': {
            'backend': getattr(settings, 'EMAIL_BACKEND', ''),
            'host': getattr(settings, 'EMAIL_HOST', ''),
            'port': getattr(settings, 'EMAIL_PORT', 587),
            'use_tls': getattr(settings, 'EMAIL_USE_TLS', True),
            'host_user': getattr(settings, 'EMAIL_HOST_USER', ''),
            'from_email': getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@netvault.local'),
        },

        # Telegram Settings
        'telegram': {
            'enabled': getattr(settings, 'TELEGRAM_ENABLED', False),
            'bot_token': getattr(settings, 'TELEGRAM_BOT_TOKEN', ''),
            'chat_id': getattr(settings, 'TELEGRAM_CHAT_ID', ''),
        },

        # Notification Settings
        'notifications': {
            'notify_on_success': getattr(settings, 'NOTIFY_ON_BACKUP_SUCCESS', False),
            'notify_on_failure': getattr(settings, 'NOTIFY_ON_BACKUP_FAILURE', True),
            'notify_schedule_summary': getattr(settings, 'NOTIFY_SCHEDULE_SUMMARY', False),
        },

        # LDAP Settings
        'ldap': {
            'enabled': getattr(settings, 'LDAP_ENABLED', False),
            'server_uri': getattr(settings, 'LDAP_SERVER_URI', ''),
            'bind_dn': getattr(settings, 'LDAP_BIND_DN', ''),
            'user_search_base': getattr(settings, 'LDAP_USER_SEARCH_BASE', ''),
        },

        # Redis Settings
        'redis': {
            'url': getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0'),
        },

        # Backup Settings
        'backup': {
            'retention_days': getattr(settings, 'BACKUP_RETENTION_DAYS', 90),
            'parallel_workers': getattr(settings, 'BACKUP_PARALLEL_WORKERS', 5),
        },

        # Device Check Settings (always uses hybrid mode for VTY optimization)
        'device_check': {
            'interval_minutes': getattr(settings, 'DEVICE_CHECK_INTERVAL_MINUTES', 5),
            'tcp_timeout': getattr(settings, 'DEVICE_CHECK_TCP_TIMEOUT', 2),
            'ssh_timeout': getattr(settings, 'DEVICE_CHECK_SSH_TIMEOUT', 5),
        },

        # JWT Session Settings
        'jwt': {
            'access_token_lifetime': int(os.getenv('JWT_ACCESS_TOKEN_LIFETIME', '60')),
            'refresh_token_lifetime': int(os.getenv('JWT_REFRESH_TOKEN_LIFETIME', '1440')),
        },

        # Security Settings
        'security': {
            'session_cookie_secure': getattr(settings, 'SESSION_COOKIE_SECURE', False),
            'csrf_cookie_secure': getattr(settings, 'CSRF_COOKIE_SECURE', False),
            'secure_ssl_redirect': getattr(settings, 'SECURE_SSL_REDIRECT', False),
        },
    }

    return Response(settings_data)


@api_view(['POST'])
@permission_classes([IsAdministrator])
def update_system_settings(request):
    """Update system settings (admin only)"""

    data = request.data
    env_file_path = os.path.join(settings.BASE_DIR, '.env')

    try:
        # Read current .env file
        env_lines = []
        if os.path.exists(env_file_path):
            with open(env_file_path, 'r') as f:
                env_lines = f.readlines()

        # Update settings
        updated_vars = {}

        # Email settings
        if 'email' in data:
            email = data['email']
            if 'host' in email:
                updated_vars['EMAIL_HOST'] = email['host']
            if 'port' in email:
                updated_vars['EMAIL_PORT'] = str(email['port'])
            if 'use_tls' in email:
                updated_vars['EMAIL_USE_TLS'] = str(email['use_tls'])
            if 'host_user' in email:
                updated_vars['EMAIL_HOST_USER'] = email['host_user']
            if 'host_password' in email:
                updated_vars['EMAIL_HOST_PASSWORD'] = email['host_password']

        # Telegram settings
        if 'telegram' in data:
            telegram = data['telegram']
            if 'enabled' in telegram:
                updated_vars['TELEGRAM_ENABLED'] = str(telegram['enabled'])
            if 'bot_token' in telegram:
                updated_vars['TELEGRAM_BOT_TOKEN'] = telegram['bot_token']
            if 'chat_id' in telegram:
                updated_vars['TELEGRAM_CHAT_ID'] = telegram['chat_id']

        # Notification settings
        if 'notifications' in data:
            notifications = data['notifications']
            if 'notify_on_success' in notifications:
                updated_vars['NOTIFY_ON_BACKUP_SUCCESS'] = str(notifications['notify_on_success'])
            if 'notify_on_failure' in notifications:
                updated_vars['NOTIFY_ON_BACKUP_FAILURE'] = str(notifications['notify_on_failure'])
            if 'notify_schedule_summary' in notifications:
                updated_vars['NOTIFY_SCHEDULE_SUMMARY'] = str(notifications['notify_schedule_summary'])

        # LDAP settings
        if 'ldap' in data:
            ldap = data['ldap']
            if 'enabled' in ldap:
                updated_vars['LDAP_ENABLED'] = str(ldap['enabled'])
            if 'server_uri' in ldap:
                updated_vars['LDAP_SERVER_URI'] = ldap['server_uri']
            if 'bind_dn' in ldap:
                updated_vars['LDAP_BIND_DN'] = ldap['bind_dn']
            if 'bind_password' in ldap:
                updated_vars['LDAP_BIND_PASSWORD'] = ldap['bind_password']
            if 'user_search_base' in ldap:
                updated_vars['LDAP_USER_SEARCH_BASE'] = ldap['user_search_base']

        # Device check settings
        if 'device_check' in data:
            device_check = data['device_check']
            if 'interval_minutes' in device_check:
                updated_vars['DEVICE_CHECK_INTERVAL_MINUTES'] = str(device_check['interval_minutes'])
            if 'tcp_timeout' in device_check:
                updated_vars['DEVICE_CHECK_TCP_TIMEOUT'] = str(device_check['tcp_timeout'])
            if 'ssh_timeout' in device_check:
                updated_vars['DEVICE_CHECK_SSH_TIMEOUT'] = str(device_check['ssh_timeout'])

        # Backup settings
        if 'backup' in data:
            backup = data['backup']
            if 'retention_days' in backup:
                updated_vars['BACKUP_RETENTION_DAYS'] = str(backup['retention_days'])
            if 'parallel_workers' in backup:
                updated_vars['BACKUP_PARALLEL_WORKERS'] = str(backup['parallel_workers'])

        # JWT settings
        if 'jwt' in data:
            jwt = data['jwt']
            if 'access_token_lifetime' in jwt:
                updated_vars['JWT_ACCESS_TOKEN_LIFETIME'] = str(jwt['access_token_lifetime'])
            if 'refresh_token_lifetime' in jwt:
                updated_vars['JWT_REFRESH_TOKEN_LIFETIME'] = str(jwt['refresh_token_lifetime'])

        # Redis settings
        if 'redis' in data:
            redis = data['redis']
            if 'url' in redis:
                updated_vars['REDIS_URL'] = redis['url']

        # Update .env file
        new_lines = []
        updated_keys = set()

        for line in env_lines:
            line = line.strip()
            if line and not line.startswith('#'):
                key = line.split('=')[0]
                if key in updated_vars:
                    new_lines.append(f"{key}={updated_vars[key]}\n")
                    updated_keys.add(key)
                else:
                    new_lines.append(line + '\n')
            else:
                new_lines.append(line + '\n' if line else '\n')

        # Add new variables that weren't in the file
        for key, value in updated_vars.items():
            if key not in updated_keys:
                new_lines.append(f"{key}={value}\n")

        # Write back to .env
        with open(env_file_path, 'w') as f:
            f.writelines(new_lines)

        return Response({
            'success': True,
            'message': 'Settings updated successfully. Please restart the application for changes to take effect.'
        })

    except Exception as e:
        return Response(
            {'error': f'Failed to update settings: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAdministrator])
def test_email_settings(request):
    """Test email configuration by sending a test email"""

    try:
        from django.core.mail import send_mail

        test_email = request.data.get('email', request.user.email)

        send_mail(
            'NetVault Test Email',
            'This is a test email from NetVault. Your email configuration is working correctly!',
            settings.DEFAULT_FROM_EMAIL,
            [test_email],
            fail_silently=False,
        )

        return Response({
            'success': True,
            'message': f'Test email sent successfully to {test_email}'
        })
    except Exception as e:
        return Response(
            {'error': f'Failed to send test email: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAdministrator])
def test_telegram_settings(request):
    """Test Telegram configuration"""

    try:
        import requests

        bot_token = request.data.get('bot_token', settings.TELEGRAM_BOT_TOKEN)
        chat_id = request.data.get('chat_id', settings.TELEGRAM_CHAT_ID)

        if not bot_token or not chat_id:
            return Response(
                {'error': 'Bot token and chat ID are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
        response = requests.post(url, json={
            'chat_id': chat_id,
            'text': '✅ NetVault: Telegram configuration test successful!'
        })

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
        return Response(
            {'error': f'Failed to send test message: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
