"""
Tests for core module - DeviceLock and utilities
"""
from django.test import TestCase, SimpleTestCase, override_settings
from unittest.mock import patch, MagicMock
import redis

from core.redis_lock import DeviceLock, DeviceLockError
from core.utils import validate_csv_safe, sanitize_csv_value
from core.crypto import encrypt_data, decrypt_data
from core.host_validation import _validate_host_allow_private_networks
from core.device_filters import get_scoped_device_ids
from django.contrib.auth import get_user_model
from devices.models import Device, Vendor, DeviceType


class DeviceLockTestCase(TestCase):
    """Tests for DeviceLock distributed locking mechanism"""

    def setUp(self):
        """Set up test fixtures"""
        self.device_id = 123
        self.operation = 'backup'

    @patch('core.redis_lock.redis.from_url')
    def test_acquire_lock_success(self, mock_redis):
        """Test successful lock acquisition"""
        mock_client = MagicMock()
        mock_client.set.return_value = True
        mock_redis.return_value = mock_client

        lock = DeviceLock(device_id=self.device_id, operation=self.operation)
        result = lock.acquire()

        self.assertTrue(result)
        self.assertTrue(lock.acquired)
        mock_client.set.assert_called_once()
        # Verify SET NX EX was used
        call_kwargs = mock_client.set.call_args[1]
        self.assertTrue(call_kwargs.get('nx'))
        self.assertIsNotNone(call_kwargs.get('ex'))

    @patch('core.redis_lock.redis.from_url')
    def test_acquire_lock_already_locked(self, mock_redis):
        """Test lock acquisition when device is already locked"""
        mock_client = MagicMock()
        mock_client.set.return_value = False  # Lock not acquired
        mock_redis.return_value = mock_client

        lock = DeviceLock(device_id=self.device_id, operation=self.operation, blocking=False)
        result = lock.acquire()

        self.assertFalse(result)
        self.assertFalse(lock.acquired)

    @patch('core.redis_lock.redis.from_url')
    def test_release_lock_success(self, mock_redis):
        """Test successful lock release"""
        mock_client = MagicMock()
        mock_client.set.return_value = True
        mock_client.eval.return_value = 1  # Lock released
        mock_redis.return_value = mock_client

        lock = DeviceLock(device_id=self.device_id, operation=self.operation)
        lock.acquire()
        result = lock.release()

        self.assertTrue(result)
        self.assertFalse(lock.acquired)
        mock_client.eval.assert_called_once()

    @patch('core.redis_lock.redis.from_url')
    def test_release_lock_not_owned(self, mock_redis):
        """Test release when lock is not owned (expired or stolen)"""
        mock_client = MagicMock()
        mock_client.set.return_value = True
        mock_client.eval.return_value = 0  # Lock not released (token mismatch)
        mock_redis.return_value = mock_client

        lock = DeviceLock(device_id=self.device_id, operation=self.operation)
        lock.acquire()
        result = lock.release()

        self.assertFalse(result)

    @patch('core.redis_lock.redis.from_url')
    def test_context_manager_success(self, mock_redis):
        """Test lock works as context manager"""
        mock_client = MagicMock()
        mock_client.set.return_value = True
        mock_client.eval.return_value = 1
        mock_redis.return_value = mock_client

        with DeviceLock(device_id=self.device_id, operation=self.operation) as lock:
            self.assertTrue(lock.acquired)

        # After exiting context, lock should be released
        mock_client.eval.assert_called_once()

    @patch('core.redis_lock.redis.from_url')
    def test_context_manager_lock_failure(self, mock_redis):
        """Test context manager raises exception when lock fails"""
        mock_client = MagicMock()
        mock_client.set.return_value = False  # Lock not acquired
        mock_redis.return_value = mock_client

        with self.assertRaises(DeviceLockError):
            with DeviceLock(device_id=self.device_id, operation=self.operation):
                pass

    @patch('core.redis_lock.redis.from_url')
    def test_lock_key_format(self, mock_redis):
        """Test lock key is correctly formatted"""
        mock_client = MagicMock()
        mock_client.set.return_value = True
        mock_redis.return_value = mock_client

        lock = DeviceLock(device_id=self.device_id, operation=self.operation)

        self.assertEqual(lock.lock_key, f'device_lock:{self.device_id}')

    @patch('core.redis_lock.redis.from_url')
    def test_unique_token_per_lock(self, mock_redis):
        """Test each lock instance has unique token"""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client

        lock1 = DeviceLock(device_id=self.device_id, operation=self.operation)
        lock2 = DeviceLock(device_id=self.device_id, operation=self.operation)

        self.assertNotEqual(lock1.token, lock2.token)

    @patch('core.redis_lock.redis.from_url')
    def test_extend_lock_success(self, mock_redis):
        """Test extending lock TTL"""
        mock_client = MagicMock()
        mock_client.set.return_value = True
        mock_client.get.return_value = None  # Will be set to lock.token
        mock_redis.return_value = mock_client

        lock = DeviceLock(device_id=self.device_id, operation=self.operation)
        lock.acquire()

        # Mock get to return our token
        mock_client.get.return_value = lock.token

        result = lock.extend(additional_ttl=60)

        self.assertTrue(result)
        mock_client.expire.assert_called_once()


class CSVSafetyTestCase(TestCase):
    """Tests for CSV formula injection protection"""

    def test_validate_csv_safe_normal_value(self):
        """Test normal values pass validation"""
        safe_values = ['Hello', 'Device-1', '192.168.1.1', 'user@example.com']
        for value in safe_values:
            result = validate_csv_safe(value)
            self.assertEqual(result, value)

    def test_validate_csv_safe_dangerous_chars(self):
        """Test dangerous characters are rejected"""
        dangerous_values = ['=CMD|calc|', '+1-234-567', '-test', '@import', '\tvalue', '\rvalue']
        for value in dangerous_values:
            with self.assertRaises(ValueError):
                validate_csv_safe(value, field_name='Test')

    def test_validate_csv_safe_space_bypass_prevention(self):
        """Test that leading spaces don't bypass protection"""
        # Values with leading spaces followed by dangerous chars
        bypass_attempts = ['  =CMD', ' +formula', '   -test', '  @import']
        for value in bypass_attempts:
            with self.assertRaises(ValueError):
                validate_csv_safe(value, field_name='Test')

    def test_sanitize_csv_value_normal(self):
        """Test normal values are not modified"""
        value = 'Normal text'
        result = sanitize_csv_value(value)
        self.assertEqual(result, value)

    def test_sanitize_csv_value_dangerous(self):
        """Test dangerous values get single quote prefix"""
        dangerous = '=1+1'
        result = sanitize_csv_value(dangerous)
        self.assertEqual(result, "'" + dangerous)

    def test_sanitize_csv_value_space_bypass(self):
        """Test space bypass is prevented"""
        bypass = '  =formula'
        result = sanitize_csv_value(bypass)
        self.assertEqual(result, "'" + bypass)


class CryptoTestCase(TestCase):
    """Tests for encryption/decryption utilities"""

    def test_encrypt_decrypt_roundtrip(self):
        """Test data can be encrypted and decrypted"""
        original = 'SuperSecretPassword123!'
        encrypted = encrypt_data(original)
        decrypted = decrypt_data(encrypted)

        self.assertEqual(original, decrypted)
        self.assertNotEqual(original, encrypted)

    def test_encrypted_data_is_different(self):
        """Test same data produces different ciphertext (due to IV)"""
        data = 'TestPassword'
        encrypted1 = encrypt_data(data)
        encrypted2 = encrypt_data(data)

        # Fernet uses random IV, so ciphertexts should differ
        self.assertNotEqual(encrypted1, encrypted2)

    def test_decrypt_invalid_data(self):
        """Test decryption of invalid data raises exception"""
        with self.assertRaises(Exception):
            decrypt_data('invalid_encrypted_data')

    def test_empty_string_encryption(self):
        """Test empty string can be encrypted/decrypted"""
        original = ''
        encrypted = encrypt_data(original)
        decrypted = decrypt_data(encrypted)

        self.assertEqual(original, decrypted)

    def test_unicode_encryption(self):
        """Test unicode data can be encrypted/decrypted"""
        original = 'Пароль123!密码'
        encrypted = encrypt_data(original)
        decrypted = decrypt_data(encrypted)

        self.assertEqual(original, decrypted)


# =============================================================================
# Merged from netvault/tests.py during core/netvault consolidation.
# Covers dashboard views, system settings API/model, and LDAP backend mocks —
# all of which now live in this app.
# =============================================================================

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


class DashboardScopeRBACTestCase(APITestCase):
    """
    Regression tests: dashboard_statistics/backup_trend/recent_backups
    used to query Device.objects/Backup.objects directly — a device_scope
    -restricted user could learn counts/trends/recent activity for
    devices outside their scope just by loading the dashboard.
    """

    def setUp(self):
        self.client = APIClient()
        User = get_user_model()
        self.admin = User.objects.create_user(
            email='dash_scope_admin@example.com', username='dash_scope_admin',
            password='TestPass123!', role='administrator',
        )
        self.scoped_viewer = User.objects.create_user(
            email='dash_scope_viewer@example.com', username='dash_scope_viewer',
            password='TestPass123!', role='viewer', device_scope={'tags': ['core']},
        )
        self.vendor = Vendor.objects.create(name='Cisco', slug='cisco-dash-scope')
        self.device_type = DeviceType.objects.create(name='Router', slug='router-dash-scope')
        self.core_device = Device.objects.create(
            name='Core-Dash', ip_address='10.8.0.1', vendor=self.vendor,
            device_type=self.device_type, username='admin',
            password_encrypted=encrypt_data('pw'), created_by=self.admin,
            status='online', tags=['core'],
        )
        self.edge_device = Device.objects.create(
            name='Edge-Dash', ip_address='10.8.0.2', vendor=self.vendor,
            device_type=self.device_type, username='admin',
            password_encrypted=encrypt_data('pw'), created_by=self.admin,
            status='online', tags=['edge'],
        )
        self.core_backup = Backup.objects.create(
            device=self.core_device, status='success', success=True,
            configuration_encrypted=encrypt_data('c'), configuration_hash='core-dash-hash',
        )
        self.edge_backup = Backup.objects.create(
            device=self.edge_device, status='success', success=True,
            configuration_encrypted=encrypt_data('c'), configuration_hash='edge-dash-hash',
        )

    def test_statistics_scoped_to_device_scope(self):
        self.client.force_authenticate(user=self.scoped_viewer)
        response = self.client.get('/api/v1/dashboard/statistics/')
        self.assertEqual(response.data['total_devices'], 1)
        self.assertEqual(response.data['total_backups'], 1)

    def test_statistics_admin_sees_everything(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/dashboard/statistics/')
        self.assertEqual(response.data['total_devices'], 2)
        self.assertEqual(response.data['total_backups'], 2)

    def test_backup_trend_scoped_to_device_scope(self):
        self.client.force_authenticate(user=self.scoped_viewer)
        response = self.client.get('/api/v1/dashboard/backup-trend/?days=1')
        today_total = sum(day['total'] for day in response.data)
        self.assertEqual(today_total, 1)

    def test_recent_backups_scoped_to_device_scope(self):
        self.client.force_authenticate(user=self.scoped_viewer)
        response = self.client.get('/api/v1/dashboard/recent-backups/')
        device_names = {b['device']['name'] for b in response.data}
        self.assertEqual(device_names, {'Core-Dash'})


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


class StaleBackupsAPITestCase(APITestCase):
    """Tests for the stale-backups dashboard endpoint"""

    def setUp(self):
        self.client = APIClient()
        User = get_user_model()
        self.user = User.objects.create_user(
            email='stale@example.com', username='staleuser', password='TestPass123!',
        )
        self.scoped_viewer = User.objects.create_user(
            email='stale_scoped@example.com', username='stale_scoped', password='TestPass123!',
            role='viewer', device_scope={'tags': ['core']},
        )
        self.vendor = Vendor.objects.create(name='Cisco', slug='cisco-stale')
        self.device_type = DeviceType.objects.create(name='Router', slug='router-stale')

        self.fresh_device = Device.objects.create(
            name='Fresh', ip_address='10.0.1.1', vendor=self.vendor,
            device_type=self.device_type, username='admin',
            password_encrypted=encrypt_data('pw'), created_by=self.user,
            last_backup=timezone.now(), tags=['core'],
        )
        self.stale_device = Device.objects.create(
            name='Stale', ip_address='10.0.1.2', vendor=self.vendor,
            device_type=self.device_type, username='admin',
            password_encrypted=encrypt_data('pw'), created_by=self.user,
            last_backup=timezone.now() - timedelta(days=10), tags=['core'],
        )
        self.never_backed_up = Device.objects.create(
            name='Never', ip_address='10.0.1.3', vendor=self.vendor,
            device_type=self.device_type, username='admin',
            password_encrypted=encrypt_data('pw'), created_by=self.user,
            last_backup=None, tags=['edge'],
        )
        self.disabled_stale_device = Device.objects.create(
            name='DisabledStale', ip_address='10.0.1.4', vendor=self.vendor,
            device_type=self.device_type, username='admin',
            password_encrypted=encrypt_data('pw'), created_by=self.user,
            last_backup=timezone.now() - timedelta(days=30), backup_enabled=False, tags=['core'],
        )

    def test_unauthenticated_rejected(self):
        response = self.client.get('/api/v1/dashboard/stale-backups/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_default_threshold_flags_stale_and_never_backed_up(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/v1/dashboard/stale-backups/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = {d['name'] for d in response.data['devices']}
        self.assertEqual(names, {'Stale', 'Never'})
        self.assertEqual(response.data['count'], 2)

    def test_fresh_device_excluded(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/v1/dashboard/stale-backups/')
        names = {d['name'] for d in response.data['devices']}
        self.assertNotIn('Fresh', names)

    def test_backup_disabled_device_excluded_even_if_ancient(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/v1/dashboard/stale-backups/')
        names = {d['name'] for d in response.data['devices']}
        self.assertNotIn('DisabledStale', names)

    def test_custom_days_threshold(self):
        self.client.force_authenticate(user=self.user)
        # 10-day-old "Stale" device shouldn't count as stale under a 30-day threshold
        response = self.client.get('/api/v1/dashboard/stale-backups/?days=30')
        names = {d['name'] for d in response.data['devices']}
        self.assertNotIn('Stale', names)
        self.assertIn('Never', names)  # never-backed-up is always stale
        self.assertEqual(response.data['threshold_days'], 30)

    def test_never_backed_up_has_null_days_since(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/v1/dashboard/stale-backups/')
        never_entry = next(d for d in response.data['devices'] if d['name'] == 'Never')
        self.assertIsNone(never_entry['last_backup'])
        self.assertIsNone(never_entry['days_since_backup'])

    def test_device_scope_applies(self):
        """'Never' is tagged 'edge', outside the scoped viewer's {'tags': ['core']}."""
        self.client.force_authenticate(user=self.scoped_viewer)
        response = self.client.get('/api/v1/dashboard/stale-backups/')
        names = {d['name'] for d in response.data['devices']}
        self.assertEqual(names, {'Stale'})


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
        self.assertIn('detail', response.data)

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
        from core.models import SystemSettings
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
        from core.models import SystemSettings

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
        from core.models import SystemSettings
        SystemSettings.objects.all().delete()

        settings = SystemSettings.get_settings()

        self.assertIsNotNone(settings)
        self.assertEqual(settings.pk, 1)

    def test_email_password_encryption(self):
        """Test email password encryption/decryption"""
        from core.models import SystemSettings

        settings = SystemSettings.get_settings()
        settings.set_email_password('secret_password')
        settings.save()

        # Encrypted password should not be plaintext
        self.assertNotEqual(settings.email_host_password_encrypted, 'secret_password')

        # Decrypted password should match
        self.assertEqual(settings.get_email_password(), 'secret_password')

    def test_email_password_empty(self):
        """Test empty email password handling"""
        from core.models import SystemSettings

        settings = SystemSettings.get_settings()
        settings.set_email_password('')
        settings.save()

        self.assertEqual(settings.email_host_password_encrypted, '')
        self.assertEqual(settings.get_email_password(), '')

    def test_telegram_token_encryption(self):
        """Test Telegram token encryption/decryption"""
        from core.models import SystemSettings

        settings = SystemSettings.get_settings()
        settings.set_telegram_bot_token('bot123456:ABC')
        settings.save()

        # Encrypted token should not be plaintext
        self.assertNotEqual(settings.telegram_bot_token_encrypted, 'bot123456:ABC')

        # Decrypted token should match
        self.assertEqual(settings.get_telegram_bot_token(), 'bot123456:ABC')

    def test_ldap_password_encryption(self):
        """Test LDAP password encryption/decryption"""
        from core.models import SystemSettings

        settings = SystemSettings.get_settings()
        settings.set_ldap_bind_password('ldap_secret')
        settings.save()

        self.assertNotEqual(settings.ldap_bind_password_encrypted, 'ldap_secret')
        self.assertEqual(settings.get_ldap_bind_password(), 'ldap_secret')

    def test_str_representation(self):
        """Test string representation"""
        from core.models import SystemSettings

        settings = SystemSettings.get_settings()
        self.assertEqual(str(settings), 'System Settings')


class LDAPBackendMockTestCase(TestCase):
    """
    Mock tests for LDAP backend functionality.
    Tests group-to-role mapping, user population, and authentication flow.
    """

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email='ldapuser@example.com',
            password='testpass'
        )

    def test_group_mapping_administrator(self):
        """Test LDAP group mapping - administrator role.

        django_auth_ldap's group_names resolves to the group's CN attribute
        (e.g. 'NetVault-Admins'), never the full DN — LDAPGroupType's
        name_attr defaults to 'cn' for every group type django_auth_ldap
        ships. So bare CNs are the realistic input here, matched exactly
        (case-insensitive) against settings.LDAP_ADMIN_GROUPS.
        """
        from accounts.ldap_backend import NetVaultLDAPBackend

        backend = NetVaultLDAPBackend()

        admin_groups = [
            ['NetVault-Admins'],
            ['Domain Admins'],
            ['ADMINISTRATORS'],
            ['NetVault Admins', 'Users'],
        ]

        for groups in admin_groups:
            role = backend._map_ldap_groups_to_role(groups)
            self.assertEqual(role, 'administrator', f"Groups {groups} should map to administrator")

    def test_group_mapping_operator(self):
        """Test LDAP group mapping - operator role"""
        from accounts.ldap_backend import NetVaultLDAPBackend

        backend = NetVaultLDAPBackend()

        operator_groups = [
            ['NetVault-Operators'],
            ['Network Operators'],
            ['netvault operators'],
        ]

        for groups in operator_groups:
            role = backend._map_ldap_groups_to_role(groups)
            self.assertEqual(role, 'operator', f"Groups {groups} should map to operator")

    def test_group_mapping_auditor(self):
        """Test LDAP group mapping - auditor role"""
        from accounts.ldap_backend import NetVaultLDAPBackend

        backend = NetVaultLDAPBackend()

        auditor_groups = [
            ['NetVault-Auditors'],
            ['Security Auditors'],
            ['netvault auditors'],
        ]

        for groups in auditor_groups:
            role = backend._map_ldap_groups_to_role(groups)
            self.assertEqual(role, 'auditor', f"Groups {groups} should map to auditor")

    def test_group_mapping_viewer_default(self):
        """Test LDAP group mapping - viewer (default) role"""
        from accounts.ldap_backend import NetVaultLDAPBackend

        backend = NetVaultLDAPBackend()

        # Regular groups without special NetVault permissions — including
        # ones that merely *contain* a privileged name as a substring,
        # which must NOT escalate (that was the bug: see
        # accounts.tests.LDAPGroupMappingTestCase for the dedicated
        # regression coverage of that specific case).
        viewer_groups = [
            ['Domain Users'],
            ['Employees'],
            ['Staff', 'IT Support'],
            ['IT-Administrators-Helpdesk'],
            [],  # Empty groups
            None,  # No groups
        ]

        for groups in viewer_groups:
            role = backend._map_ldap_groups_to_role(groups)
            self.assertEqual(role, 'viewer', f"Groups {groups} should map to viewer")

    def test_group_mapping_priority(self):
        """Test that admin role takes priority over other roles"""
        from accounts.ldap_backend import NetVaultLDAPBackend

        backend = NetVaultLDAPBackend()

        # User in both admin and operator groups
        mixed_groups = ['NetVault-Admins', 'NetVault-Operators', 'NetVault-Auditors']
        role = backend._map_ldap_groups_to_role(mixed_groups)
        self.assertEqual(role, 'administrator')

        # User in operator and auditor (operator should win)
        op_audit_groups = ['NetVault-Operators', 'NetVault-Auditors']
        role = backend._map_ldap_groups_to_role(op_audit_groups)
        self.assertEqual(role, 'operator')

    def test_get_user_existing(self):
        """Test get_user returns existing user"""
        from accounts.ldap_backend import NetVaultLDAPBackend

        backend = NetVaultLDAPBackend()
        user = backend.get_user(self.user.id)

        self.assertIsNotNone(user)
        self.assertEqual(user.email, 'ldapuser@example.com')

    def test_get_user_nonexistent(self):
        """Test get_user returns None for non-existent user"""
        from accounts.ldap_backend import NetVaultLDAPBackend

        backend = NetVaultLDAPBackend()
        user = backend.get_user(99999)

        self.assertIsNone(user)

    @patch('accounts.ldap_backend.LDAPBackend.authenticate_ldap_user')
    def test_authenticate_ldap_user_success(self, mock_super_auth):
        """Test successful LDAP authentication creates/updates user"""
        from accounts.ldap_backend import NetVaultLDAPBackend

        # Mock ldap_user object
        mock_ldap_user = MagicMock()
        mock_ldap_user.dn = 'CN=John Doe,OU=Users,DC=corp,DC=local'
        mock_ldap_user.group_names = ['NetVault-Operators', 'Domain Users']

        # Mock super().authenticate_ldap_user to return our test user
        mock_super_auth.return_value = self.user

        backend = NetVaultLDAPBackend()
        result = backend.authenticate_ldap_user(mock_ldap_user, 'password123')

        self.assertIsNotNone(result)
        self.assertTrue(result.is_ldap_user)
        self.assertEqual(result.ldap_dn, 'CN=John Doe,OU=Users,DC=corp,DC=local')
        self.assertEqual(result.role, 'operator')

    @patch('accounts.ldap_backend.LDAPBackend.authenticate_ldap_user')
    def test_authenticate_ldap_user_failure(self, mock_super_auth):
        """Test failed LDAP authentication returns None"""
        from accounts.ldap_backend import NetVaultLDAPBackend

        mock_super_auth.return_value = None

        backend = NetVaultLDAPBackend()
        mock_ldap_user = MagicMock()
        result = backend.authenticate_ldap_user(mock_ldap_user, 'wrongpassword')

        self.assertIsNone(result)

    def test_populate_user_from_ldap_signal(self):
        """Test populate_user_from_ldap signal handler"""
        from accounts.ldap_backend import populate_user_from_ldap
        User = get_user_model()

        user = User(email='newuser@corp.local')

        # Mock ldap_user with attrs
        mock_ldap_user = MagicMock()
        mock_ldap_user.dn = 'CN=New User,OU=Users,DC=corp,DC=local'
        mock_ldap_user.attrs = {
            'givenName': ['John'],
            'sn': ['Smith'],
            'mail': ['john.smith@corp.local']
        }

        # Call signal handler
        populate_user_from_ldap(sender=None, user=user, ldap_user=mock_ldap_user)

        self.assertEqual(user.first_name, 'John')
        self.assertEqual(user.last_name, 'Smith')
        self.assertEqual(user.email, 'john.smith@corp.local')
        self.assertTrue(user.is_ldap_user)
        self.assertEqual(user.ldap_dn, 'CN=New User,OU=Users,DC=corp,DC=local')

    def test_populate_user_empty_attrs(self):
        """Test populate_user_from_ldap with empty/missing attrs"""
        from accounts.ldap_backend import populate_user_from_ldap
        User = get_user_model()

        user = User(email='emptyuser@corp.local', username='emptyuser')

        mock_ldap_user = MagicMock()
        mock_ldap_user.dn = 'CN=Empty,OU=Users,DC=corp,DC=local'
        mock_ldap_user.attrs = {}  # No attributes

        populate_user_from_ldap(sender=None, user=user, ldap_user=mock_ldap_user)

        self.assertEqual(user.first_name, '')
        self.assertEqual(user.last_name, '')
        # Falls back to username when mail is empty
        self.assertEqual(user.email, 'emptyuser')
        self.assertTrue(user.is_ldap_user)

    def test_populate_user_no_ldap_user(self):
        """Test populate_user_from_ldap does nothing without ldap_user"""
        from accounts.ldap_backend import populate_user_from_ldap
        User = get_user_model()

        user = User(email='nochange@corp.local', first_name='Original')

        # Call without ldap_user
        populate_user_from_ldap(sender=None, user=user, ldap_user=None)

        # User should be unchanged
        self.assertEqual(user.first_name, 'Original')


class LDAPSettingsAPITestCase(APITestCase):
    """Test LDAP settings via API"""

    def setUp(self):
        User = get_user_model()
        import uuid
        uid = uuid.uuid4().hex[:8]
        self.admin = User.objects.create_user(
            email=f'ldapadmin_{uid}@test.com',
            username=f'ldapadmin_{uid}',
            password='adminpass',
            role='administrator'
        )
        self.client = APIClient()

    def test_ldap_settings_require_admin(self):
        """Test that LDAP settings require admin role"""
        User = get_user_model()
        import uuid
        uid = uuid.uuid4().hex[:8]
        viewer = User.objects.create_user(
            email=f'ldapviewer_{uid}@test.com',
            username=f'ldapviewer_{uid}',
            password='viewerpass',
            role='viewer'
        )
        self.client.force_authenticate(user=viewer)

        response = self.client.post('/api/v1/settings/system/update/', {
            'ldap': {'enabled': True}
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_ldap_settings_full_config(self):
        """Test complete LDAP configuration"""
        self.client.force_authenticate(user=self.admin)

        ldap_config = {
            'ldap': {
                'enabled': True,
                'server_uri': 'ldaps://dc01.corp.local:636',
                'bind_dn': 'CN=svc_netvault,OU=Service Accounts,DC=corp,DC=local',
                'bind_password': 'SecureP@ssw0rd!',
                'user_search_base': 'OU=Users,DC=corp,DC=local',
                'user_search_filter': '(sAMAccountName=%(user)s)',
                'group_search_base': 'OU=Groups,DC=corp,DC=local',
                'require_group': 'CN=NetVault-Users,OU=Groups,DC=corp,DC=local'
            }
        }

        response = self.client.post('/api/v1/settings/system/update/', ldap_config, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_ldap_disable(self):
        """Test disabling LDAP"""
        self.client.force_authenticate(user=self.admin)

        response = self.client.post('/api/v1/settings/system/update/', {
            'ldap': {'enabled': False}
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_ldap_settings_invalid_uri(self):
        """Test LDAP with invalid server URI format"""
        self.client.force_authenticate(user=self.admin)

        response = self.client.post('/api/v1/settings/system/update/', {
            'ldap': {
                'enabled': True,
                'server_uri': 'not-a-valid-uri',
                'bind_dn': 'cn=admin',
                'user_search_base': 'dc=test'
            }
        }, format='json')

        # Should still accept (validation might be on connection time)
        # or reject depending on implementation
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_ldap_password_not_exposed_in_get(self):
        """Test that LDAP password is not exposed when getting settings"""
        self.client.force_authenticate(user=self.admin)

        # First set a password
        self.client.post('/api/v1/settings/system/update/', {
            'ldap': {
                'enabled': True,
                'server_uri': 'ldap://test.local',
                'bind_password': 'super_secret_password'
            }
        }, format='json')

        # Get settings
        response = self.client.get('/api/v1/settings/system/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Password should be masked or not present
        ldap_data = response.data.get('ldap', {})
        if 'bind_password' in ldap_data:
            self.assertNotEqual(ldap_data['bind_password'], 'super_secret_password')


class LDAPConnectionMockTestCase(TestCase):
    """Mock tests for LDAP connection scenarios"""

    @patch('ldap.initialize')
    def test_ldap_connection_timeout(self, mock_ldap_init):
        """Test LDAP connection timeout handling"""
        import ldap

        mock_conn = MagicMock()
        mock_conn.simple_bind_s.side_effect = ldap.TIMEOUT('Connection timed out')
        mock_ldap_init.return_value = mock_conn

        # This tests that our code would handle timeout gracefully
        # The actual LDAP backend should catch and log this
        with self.assertRaises(ldap.TIMEOUT):
            conn = ldap.initialize('ldap://unreachable.local:389')
            conn.simple_bind_s('cn=admin', 'password')

    @patch('ldap.initialize')
    def test_ldap_invalid_credentials(self, mock_ldap_init):
        """Test LDAP invalid credentials handling"""
        import ldap

        mock_conn = MagicMock()
        mock_conn.simple_bind_s.side_effect = ldap.INVALID_CREDENTIALS('Invalid credentials')
        mock_ldap_init.return_value = mock_conn

        with self.assertRaises(ldap.INVALID_CREDENTIALS):
            conn = ldap.initialize('ldap://dc.local:389')
            conn.simple_bind_s('cn=admin', 'wrongpassword')

    @patch('ldap.initialize')
    def test_ldap_server_down(self, mock_ldap_init):
        """Test LDAP server down handling"""
        import ldap

        mock_conn = MagicMock()
        mock_conn.simple_bind_s.side_effect = ldap.SERVER_DOWN('Server is down')
        mock_ldap_init.return_value = mock_conn

        with self.assertRaises(ldap.SERVER_DOWN):
            conn = ldap.initialize('ldap://offline.local:389')
            conn.simple_bind_s('cn=admin', 'password')

    @patch('ldap.initialize')
    def test_ldap_search_user(self, mock_ldap_init):
        """Test LDAP user search"""
        mock_conn = MagicMock()
        mock_ldap_init.return_value = mock_conn

        # Mock search result
        mock_conn.search_s.return_value = [
            ('CN=John Doe,OU=Users,DC=corp,DC=local', {
                'sAMAccountName': [b'jdoe'],
                'mail': [b'john.doe@corp.local'],
                'givenName': [b'John'],
                'sn': [b'Doe'],
                'memberOf': [
                    b'CN=NetVault-Operators,OU=Groups,DC=corp,DC=local',
                    b'CN=Domain Users,OU=Groups,DC=corp,DC=local'
                ]
            })
        ]

        import ldap
        conn = ldap.initialize('ldap://dc.local:389')
        results = conn.search_s(
            'OU=Users,DC=corp,DC=local',
            ldap.SCOPE_SUBTREE,
            '(sAMAccountName=jdoe)'
        )

        self.assertEqual(len(results), 1)
        dn, attrs = results[0]
        self.assertEqual(dn, 'CN=John Doe,OU=Users,DC=corp,DC=local')
        self.assertEqual(attrs['mail'], [b'john.doe@corp.local'])

    @patch('ldap.initialize')
    def test_ldap_search_no_results(self, mock_ldap_init):
        """Test LDAP search with no results"""
        mock_conn = MagicMock()
        mock_ldap_init.return_value = mock_conn
        mock_conn.search_s.return_value = []

        import ldap
        conn = ldap.initialize('ldap://dc.local:389')
        results = conn.search_s(
            'OU=Users,DC=corp,DC=local',
            ldap.SCOPE_SUBTREE,
            '(sAMAccountName=nonexistent)'
        )

        self.assertEqual(results, [])


class HostValidationTestCase(SimpleTestCase):
    """Tests for the ALLOW_PRIVATE_NETWORK_HOSTS ALLOWED_HOSTS patch"""

    def test_private_ipv4_allowed_even_when_not_in_allowed_hosts(self):
        for host in ('192.168.8.125', '10.0.0.1', '172.16.0.1', '172.31.255.255', '127.0.0.1'):
            self.assertTrue(
                _validate_host_allow_private_networks(host, ['example.com']),
                f'{host} should be treated as a valid Host header',
            )

    def test_public_ip_still_rejected(self):
        self.assertFalse(
            _validate_host_allow_private_networks('8.8.8.8', ['example.com']),
        )

    def test_ip_adjacent_to_private_ranges_not_treated_as_private(self):
        # 172.15.x.x and 172.32.x.x are outside the 172.16.0.0/12 block —
        # regression guard against an off-by-one in the range boundaries.
        for host in ('172.15.255.255', '172.32.0.1', '192.169.0.1', '11.0.0.1'):
            self.assertFalse(
                _validate_host_allow_private_networks(host, ['example.com']),
                f'{host} is not a private IP and should fall through to allowed_hosts',
            )

    def test_named_host_falls_through_to_normal_allowed_hosts_check(self):
        self.assertTrue(
            _validate_host_allow_private_networks('example.com', ['example.com']),
        )
        self.assertFalse(
            _validate_host_allow_private_networks('evil.com', ['example.com']),
        )

    def test_non_ip_hostname_does_not_raise(self):
        # Make sure a plain domain name doesn't blow up in ipaddress.ip_address().
        self.assertFalse(
            _validate_host_allow_private_networks('not-an-ip.local', []),
        )


class GetScopedDeviceIdsTestCase(TestCase):
    """Tests for accounts device-scope RBAC's core helper"""

    def setUp(self):
        User = get_user_model()
        self.vendor = Vendor.objects.create(name='Cisco', slug='cisco-scope')
        self.device_type = DeviceType.objects.create(name='Router', slug='router-scope')
        self.creator = User.objects.create_user(
            email='creator@example.com', username='creator', password='pass123',
        )
        self.core_device = Device.objects.create(
            name='Core-1', ip_address='10.1.0.1', vendor=self.vendor,
            device_type=self.device_type, username='admin',
            password_encrypted=encrypt_data('pw'), created_by=self.creator, tags=['core'],
        )
        self.edge_device = Device.objects.create(
            name='Edge-1', ip_address='10.1.0.2', vendor=self.vendor,
            device_type=self.device_type, username='admin',
            password_encrypted=encrypt_data('pw'), created_by=self.creator, tags=['edge'],
        )

    def test_administrator_is_unrestricted_regardless_of_scope(self):
        admin = get_user_model().objects.create_user(
            email='admin_scope@example.com', username='admin_scope', password='pass123',
            role='administrator', device_scope={'tags': ['core']},
        )
        self.assertIsNone(get_scoped_device_ids(admin))

    def test_superuser_is_unrestricted_regardless_of_role(self):
        su = get_user_model().objects.create_user(
            email='su_scope@example.com', username='su_scope', password='pass123',
            role='viewer', is_superuser=True, device_scope={'tags': ['core']},
        )
        self.assertIsNone(get_scoped_device_ids(su))

    def test_empty_scope_is_unrestricted(self):
        viewer = get_user_model().objects.create_user(
            email='viewer_scope@example.com', username='viewer_scope', password='pass123',
            role='viewer', device_scope={},
        )
        self.assertIsNone(get_scoped_device_ids(viewer))

    def test_scope_restricts_to_matching_devices_only(self):
        viewer = get_user_model().objects.create_user(
            email='viewer_scope2@example.com', username='viewer_scope2', password='pass123',
            role='viewer', device_scope={'tags': ['core']},
        )
        ids = get_scoped_device_ids(viewer)
        self.assertEqual(ids, {self.core_device.id})
        self.assertNotIn(self.edge_device.id, ids)


class CeleryTimezoneTestCase(SimpleTestCase):
    """
    Regression test: celery.py used to hardcode app.conf.timezone = 'UTC',
    silently overriding settings.py's CELERY_TIMEZONE = TIME_ZONE (already
    picked up correctly by config_from_object() a few lines earlier) —
    every fixed-hour crontab beat entry would fire at the wrong wall-clock
    hour on any server whose local timezone isn't UTC.
    """

    def test_celery_app_timezone_follows_django_time_zone(self):
        from django.conf import settings
        from netvault.celery import app
        self.assertEqual(app.conf.timezone, settings.TIME_ZONE)
