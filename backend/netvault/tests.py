"""
Tests for netvault core module - dashboard views, system settings
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch, MagicMock

from devices.models import Device, Vendor, DeviceType
from backups.models import Backup
from core.crypto import encrypt_data


class DashboardStatisticsTestCase(APITestCase):
    """Tests for dashboard statistics endpoint"""

    def setUp(self):
        self.client = APIClient()
        User = get_user_model()
        self.user = User.objects.create_user(
            email='dashboard@example.com',
            username='dashboarduser',
            password='TestPass123!'
        )
        self.vendor = Vendor.objects.create(name='Cisco', slug='cisco')
        self.device_type = DeviceType.objects.create(name='Router', slug='router')

    def test_statistics_unauthenticated(self):
        """Test statistics endpoint requires authentication"""
        response = self.client.get('/api/v1/dashboard/statistics/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_statistics_empty(self):
        """Test statistics with no data"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/v1/dashboard/statistics/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_devices'], 0)
        self.assertEqual(response.data['total_backups'], 0)

    def test_statistics_with_data(self):
        """Test statistics with devices and backups"""
        self.client.force_authenticate(user=self.user)

        # Create devices
        device1 = Device.objects.create(
            name='Device-1',
            ip_address='10.0.0.1',
            vendor=self.vendor,
            device_type=self.device_type,
            username='admin',
            password_encrypted=encrypt_data('pass'),
            status='online',
            created_by=self.user
        )
        device2 = Device.objects.create(
            name='Device-2',
            ip_address='10.0.0.2',
            vendor=self.vendor,
            device_type=self.device_type,
            username='admin',
            password_encrypted=encrypt_data('pass'),
            status='offline',
            created_by=self.user
        )

        # Create backups
        Backup.objects.create(
            device=device1,
            status='success',
            success=True,
            configuration_encrypted=encrypt_data('config'),
            configuration_hash='hash1'
        )
        Backup.objects.create(
            device=device2,
            status='failed',
            success=False,
            configuration_encrypted='',
            configuration_hash=''
        )

        response = self.client.get('/api/v1/dashboard/statistics/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_devices'], 2)
        self.assertEqual(response.data['active_devices'], 1)
        self.assertEqual(response.data['inactive_devices'], 1)
        self.assertEqual(response.data['total_backups'], 2)
        self.assertEqual(response.data['successful_backups'], 1)
        self.assertEqual(response.data['failed_backups'], 1)


class BackupTrendTestCase(APITestCase):
    """Tests for backup trend endpoint"""

    def setUp(self):
        self.client = APIClient()
        User = get_user_model()
        self.user = User.objects.create_user(
            email='trend@example.com',
            username='trenduser',
            password='TestPass123!'
        )
        self.vendor = Vendor.objects.create(name='Cisco', slug='cisco-trend')
        self.device_type = DeviceType.objects.create(name='Router', slug='router-trend')
        self.device = Device.objects.create(
            name='Trend-Device',
            ip_address='10.0.0.100',
            vendor=self.vendor,
            device_type=self.device_type,
            username='admin',
            password_encrypted=encrypt_data('pass'),
            created_by=self.user
        )

    def test_trend_unauthenticated(self):
        """Test trend endpoint requires authentication"""
        response = self.client.get('/api/v1/dashboard/backup-trend/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_trend_default_days(self):
        """Test trend with default 7 days"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/v1/dashboard/backup-trend/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 7)

    def test_trend_custom_days(self):
        """Test trend with custom days parameter"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/v1/dashboard/backup-trend/?days=14')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 14)

    def test_trend_with_backups(self):
        """Test trend shows backup data structure"""
        self.client.force_authenticate(user=self.user)

        # Create a backup today
        Backup.objects.create(
            device=self.device,
            status='success',
            success=True,
            configuration_encrypted=encrypt_data('config'),
            configuration_hash='hash1'
        )

        response = self.client.get('/api/v1/dashboard/backup-trend/?days=7')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should have 7 days of data
        self.assertEqual(len(response.data), 7)
        # Each day should have expected keys
        for day in response.data:
            self.assertIn('date', day)
            self.assertIn('successful', day)
            self.assertIn('failed', day)
            self.assertIn('total', day)


class RecentBackupsTestCase(APITestCase):
    """Tests for recent backups endpoint"""

    def setUp(self):
        self.client = APIClient()
        User = get_user_model()
        self.user = User.objects.create_user(
            email='recent@example.com',
            username='recentuser',
            password='TestPass123!'
        )
        self.vendor = Vendor.objects.create(name='Cisco', slug='cisco-recent')
        self.device_type = DeviceType.objects.create(name='Router', slug='router-recent')
        self.device = Device.objects.create(
            name='Recent-Device',
            ip_address='10.0.0.101',
            vendor=self.vendor,
            device_type=self.device_type,
            username='admin',
            password_encrypted=encrypt_data('pass'),
            created_by=self.user
        )

    def test_recent_unauthenticated(self):
        """Test recent backups requires authentication"""
        response = self.client.get('/api/v1/dashboard/recent-backups/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_recent_empty(self):
        """Test recent backups with no data"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/v1/dashboard/recent-backups/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_recent_with_limit(self):
        """Test recent backups respects limit"""
        self.client.force_authenticate(user=self.user)

        # Create multiple backups
        for i in range(15):
            Backup.objects.create(
                device=self.device,
                status='success',
                success=True,
                configuration_encrypted=encrypt_data(f'config{i}'),
                configuration_hash=f'hash{i}'
            )

        response = self.client.get('/api/v1/dashboard/recent-backups/?limit=5')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 5)


class SystemSettingsAPITestCase(APITestCase):
    """Tests for System Settings API endpoints"""

    def setUp(self):
        self.client = APIClient()
        User = get_user_model()
        self.admin = User.objects.create_user(
            email='admin@example.com',
            username='adminuser',
            password='TestPass123!',
            role='administrator'
        )
        self.viewer = User.objects.create_user(
            email='viewer@example.com',
            username='vieweruser',
            password='TestPass123!',
            role='viewer'
        )

    def test_get_settings_unauthenticated(self):
        """Test get settings requires authentication"""
        response = self.client.get('/api/v1/settings/system/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_settings_non_admin(self):
        """Test get settings requires admin role"""
        self.client.force_authenticate(user=self.viewer)
        response = self.client.get('/api/v1/settings/system/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_settings_admin(self):
        """Test admin can get settings"""
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/settings/system/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('email', response.data)
        self.assertIn('telegram', response.data)
        self.assertIn('notifications', response.data)
        self.assertIn('ldap', response.data)
        self.assertIn('backup', response.data)
        self.assertIn('jwt', response.data)

    def test_update_settings_email(self):
        """Test updating email settings"""
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/v1/settings/system/update/', {
            'email': {
                'host': 'smtp.test.com',
                'port': 465,
                'use_tls': False,
                'host_user': 'user@test.com',
                'from_email': 'noreply@test.com'
            }
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])

    def test_update_settings_email_with_password(self):
        """Test updating email settings with password"""
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/v1/settings/system/update/', {
            'email': {
                'host_password': 'secret123'
            }
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_settings_telegram(self):
        """Test updating telegram settings"""
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/v1/settings/system/update/', {
            'telegram': {
                'enabled': True,
                'bot_token': 'bot123456:ABC',
                'chat_id': '123456789'
            }
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_settings_telegram_masked_token(self):
        """Test telegram with masked token (shouldn't update)"""
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/v1/settings/system/update/', {
            'telegram': {
                'bot_token': '***'  # Masked - should be ignored
            }
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_settings_notifications(self):
        """Test updating notification settings"""
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/v1/settings/system/update/', {
            'notifications': {
                'notify_on_success': True,
                'notify_on_failure': True,
                'notify_schedule_summary': True
            }
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_settings_ldap(self):
        """Test updating LDAP settings"""
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/v1/settings/system/update/', {
            'ldap': {
                'enabled': True,
                'server_uri': 'ldap://ldap.example.com:389',
                'bind_dn': 'cn=admin,dc=example,dc=com',
                'bind_password': 'secret',
                'user_search_base': 'ou=users,dc=example,dc=com',
                'user_search_filter': '(uid=%(user)s)'
            }
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_settings_backup_valid(self):
        """Test updating backup settings with valid values"""
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/v1/settings/system/update/', {
            'backup': {
                'retention_days': 30,
                'parallel_workers': 10
            }
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_settings_backup_invalid_retention(self):
        """Test backup settings validation - invalid retention days"""
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/v1/settings/system/update/', {
            'backup': {
                'retention_days': 0  # Invalid - must be at least 1
            }
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_update_settings_backup_invalid_workers(self):
        """Test backup settings validation - invalid workers"""
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/v1/settings/system/update/', {
            'backup': {
                'parallel_workers': 100  # Invalid - max 50
            }
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_settings_jwt_valid(self):
        """Test updating JWT settings with valid values"""
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/v1/settings/system/update/', {
            'jwt': {
                'access_token_lifetime': 30,
                'refresh_token_lifetime': 1440
            }
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_settings_jwt_invalid_access_lifetime(self):
        """Test JWT settings validation - invalid access token lifetime"""
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/v1/settings/system/update/', {
            'jwt': {
                'access_token_lifetime': 2  # Invalid - min 5
            }
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_settings_jwt_invalid_refresh_lifetime(self):
        """Test JWT settings validation - invalid refresh token lifetime"""
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/v1/settings/system/update/', {
            'jwt': {
                'refresh_token_lifetime': 50  # Invalid - min 60
            }
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('notifications.services.send_email_notification')
    def test_test_email_success(self, mock_send):
        """Test email test endpoint - success"""
        mock_send.return_value = True
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/v1/settings/test-email/', {
            'email': 'test@example.com'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])

    @patch('notifications.services.send_email_notification')
    def test_test_email_failure(self, mock_send):
        """Test email test endpoint - failure"""
        mock_send.return_value = False
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/v1/settings/test-email/', {
            'email': 'test@example.com'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def test_test_telegram_missing_config(self):
        """Test Telegram test endpoint - missing config"""
        from netvault.models import SystemSettings
        settings = SystemSettings.get_settings()
        settings.telegram_bot_token_encrypted = ''
        settings.telegram_chat_id = ''
        settings.save()

        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/v1/settings/test-telegram/', format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class SystemSettingsTestCase(TestCase):
    """Tests for SystemSettings model"""

    def test_singleton_pattern(self):
        """Test only one SystemSettings instance exists"""
        from netvault.models import SystemSettings

        # Use get_settings to create first instance
        settings1 = SystemSettings.get_settings()
        settings1.email_host = 'smtp1.example.com'
        settings1.save()

        # Get again and modify
        settings2 = SystemSettings.get_settings()
        settings2.email_host = 'smtp2.example.com'
        settings2.save()

        self.assertEqual(SystemSettings.objects.count(), 1)
        # Both instances have pk=1
        self.assertEqual(settings1.pk, 1)
        self.assertEqual(settings2.pk, 1)

    def test_get_settings_creates_if_not_exists(self):
        """Test get_settings creates settings if not exists"""
        from netvault.models import SystemSettings
        SystemSettings.objects.all().delete()

        settings = SystemSettings.get_settings()

        self.assertIsNotNone(settings)
        self.assertEqual(settings.pk, 1)

    def test_email_password_encryption(self):
        """Test email password encryption/decryption"""
        from netvault.models import SystemSettings

        settings = SystemSettings.get_settings()
        settings.set_email_password('secret_password')
        settings.save()

        # Encrypted password should not be plaintext
        self.assertNotEqual(settings.email_host_password_encrypted, 'secret_password')

        # Decrypted password should match
        self.assertEqual(settings.get_email_password(), 'secret_password')

    def test_email_password_empty(self):
        """Test empty email password handling"""
        from netvault.models import SystemSettings

        settings = SystemSettings.get_settings()
        settings.set_email_password('')
        settings.save()

        self.assertEqual(settings.email_host_password_encrypted, '')
        self.assertEqual(settings.get_email_password(), '')

    def test_telegram_token_encryption(self):
        """Test Telegram token encryption/decryption"""
        from netvault.models import SystemSettings

        settings = SystemSettings.get_settings()
        settings.set_telegram_bot_token('bot123456:ABC')
        settings.save()

        # Encrypted token should not be plaintext
        self.assertNotEqual(settings.telegram_bot_token_encrypted, 'bot123456:ABC')

        # Decrypted token should match
        self.assertEqual(settings.get_telegram_bot_token(), 'bot123456:ABC')

    def test_ldap_password_encryption(self):
        """Test LDAP password encryption/decryption"""
        from netvault.models import SystemSettings

        settings = SystemSettings.get_settings()
        settings.set_ldap_bind_password('ldap_secret')
        settings.save()

        self.assertNotEqual(settings.ldap_bind_password_encrypted, 'ldap_secret')
        self.assertEqual(settings.get_ldap_bind_password(), 'ldap_secret')

    def test_str_representation(self):
        """Test string representation"""
        from netvault.models import SystemSettings

        settings = SystemSettings.get_settings()
        self.assertEqual(str(settings), 'System Settings')
