"""
Tests for backups app - Backup model, encryption, scheduling
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from django.utils import timezone

from backups.models import Backup, BackupSchedule, BackupRetentionPolicy, BackupDiff
from devices.models import Device, Vendor, DeviceType
from core.crypto import encrypt_data, decrypt_data


class BackupModelTestCase(TestCase):
    """Tests for Backup model"""

    def setUp(self):
        """Set up test fixtures"""
        # Create user for device ownership
        User = get_user_model()
        self.user = User.objects.create_user(
            email='backup_model@example.com',
            username='backupmodeluser',
            password='pass123'
        )

        # Create vendor and device type
        self.vendor = Vendor.objects.create(
            name='Cisco',
            slug='cisco',
            backup_commands=['show running-config']
        )
        self.device_type = DeviceType.objects.create(
            name='Router',
            slug='router'
        )

        # Create device
        self.device = Device.objects.create(
            name='Test-Router',
            ip_address='192.168.1.1',
            vendor=self.vendor,
            device_type=self.device_type,
            username='admin',
            password_encrypted=encrypt_data('password123'),
            created_by=self.user
        )

    def test_set_configuration(self):
        """Test configuration encryption and hashing"""
        backup = Backup.objects.create(
            device=self.device,
            status='success',
            configuration_encrypted='',
            configuration_hash=''
        )

        config = 'hostname Test-Router\ninterface Gi0/0\n ip address 192.168.1.1 255.255.255.0'
        backup.set_configuration(config)
        backup.save()

        # Verify encryption
        self.assertNotEqual(backup.configuration_encrypted, config)
        self.assertIsNotNone(backup.configuration_hash)
        self.assertEqual(len(backup.configuration_hash), 64)  # SHA256
        self.assertEqual(backup.size_bytes, len(config))

    def test_get_configuration(self):
        """Test configuration decryption"""
        config = 'hostname Test-Router\ninterface Gi0/0\n ip address 192.168.1.1 255.255.255.0'

        backup = Backup.objects.create(
            device=self.device,
            status='success',
            configuration_encrypted=encrypt_data(config),
            configuration_hash='test_hash'
        )

        decrypted = backup.get_configuration()
        self.assertEqual(decrypted, config)

    def test_compare_with_previous_first_backup(self):
        """Test comparison when this is first backup"""
        backup = Backup.objects.create(
            device=self.device,
            status='success',
            success=True,
            configuration_encrypted=encrypt_data('config1'),
            configuration_hash='hash1'
        )

        result = backup.compare_with_previous()

        self.assertTrue(result)
        self.assertTrue(backup.has_changes)
        self.assertIn('First backup', backup.changes_summary)

    def test_compare_with_previous_no_changes(self):
        """Test comparison when configs are identical"""
        config = 'hostname Router\ninterface Gi0/0'

        # First backup
        backup1 = Backup.objects.create(
            device=self.device,
            status='success',
            success=True,
            configuration_encrypted=encrypt_data(config),
            configuration_hash='same_hash_123'
        )

        # Second backup with same config
        backup2 = Backup.objects.create(
            device=self.device,
            status='success',
            success=True,
            configuration_encrypted=encrypt_data(config),
            configuration_hash='same_hash_123'
        )

        result = backup2.compare_with_previous()

        self.assertFalse(result)
        self.assertFalse(backup2.has_changes)
        self.assertIn('No changes', backup2.changes_summary)

    def test_compare_with_previous_has_changes(self):
        """Test comparison when configs differ"""
        # First backup
        backup1 = Backup.objects.create(
            device=self.device,
            status='success',
            success=True,
            configuration_encrypted=encrypt_data('config1'),
            configuration_hash='hash_1'
        )

        # Second backup with different config
        backup2 = Backup.objects.create(
            device=self.device,
            status='success',
            success=True,
            configuration_encrypted=encrypt_data('config2'),
            configuration_hash='hash_2'
        )

        result = backup2.compare_with_previous()

        self.assertTrue(result)
        self.assertTrue(backup2.has_changes)

    def test_backup_ordering(self):
        """Test backups are ordered by created_at descending"""
        backup1 = Backup.objects.create(
            device=self.device,
            status='success',
            configuration_encrypted='',
            configuration_hash='hash1'
        )
        backup2 = Backup.objects.create(
            device=self.device,
            status='success',
            configuration_encrypted='',
            configuration_hash='hash2'
        )

        backups = Backup.objects.filter(device=self.device)
        self.assertEqual(backups[0].id, backup2.id)  # Newer first


class BackupScheduleTestCase(TestCase):
    """Tests for BackupSchedule model"""

    def setUp(self):
        """Set up test fixtures"""
        User = get_user_model()
        self.user = User.objects.create_user(
            email='schedule@example.com',
            username='scheduleuser',
            password='pass123'
        )

        self.vendor = Vendor.objects.create(name='Cisco', slug='cisco')
        self.device_type = DeviceType.objects.create(name='Router', slug='router')
        self.device = Device.objects.create(
            name='Scheduled-Router',
            ip_address='192.168.1.2',
            vendor=self.vendor,
            device_type=self.device_type,
            username='admin',
            password_encrypted=encrypt_data('pass'),
            created_by=self.user
        )

    def test_create_schedule(self):
        """Test creating a backup schedule"""
        schedule = BackupSchedule.objects.create(
            name='Daily Backup',
            frequency='daily',
            run_time='02:00:00',
            is_active=True
        )
        schedule.devices.add(self.device)

        self.assertEqual(schedule.name, 'Daily Backup')
        self.assertEqual(schedule.frequency, 'daily')
        self.assertTrue(schedule.is_active)
        self.assertIn(self.device, schedule.devices.all())

    def test_schedule_stats(self):
        """Test schedule statistics tracking"""
        schedule = BackupSchedule.objects.create(
            name='Test Schedule',
            frequency='hourly',
            total_runs=10,
            successful_runs=8,
            failed_runs=2
        )

        self.assertEqual(schedule.total_runs, 10)
        self.assertEqual(schedule.successful_runs, 8)
        self.assertEqual(schedule.failed_runs, 2)


class BackupRetentionPolicyTestCase(TestCase):
    """Tests for BackupRetentionPolicy model"""

    def test_create_policy(self):
        """Test creating a retention policy"""
        policy = BackupRetentionPolicy.objects.create(
            name='Standard Policy',
            keep_last_n=20,
            keep_daily=14,
            keep_weekly=8,
            keep_monthly=6,
            is_active=True,
            auto_delete=True
        )

        self.assertEqual(policy.keep_last_n, 20)
        self.assertEqual(policy.keep_daily, 14)
        self.assertTrue(policy.auto_delete)

    def test_policy_defaults(self):
        """Test default retention values"""
        policy = BackupRetentionPolicy.objects.create(name='Default Policy')

        self.assertEqual(policy.keep_last_n, 10)
        self.assertEqual(policy.keep_daily, 7)
        self.assertEqual(policy.keep_weekly, 4)
        self.assertEqual(policy.keep_monthly, 12)


class BackupDiffTestCase(TestCase):
    """Tests for BackupDiff model"""

    def setUp(self):
        """Set up test fixtures"""
        User = get_user_model()
        self.user = User.objects.create_user(
            email='diff@example.com',
            username='diffuser',
            password='pass123'
        )

        self.vendor = Vendor.objects.create(name='Cisco', slug='cisco')
        self.device_type = DeviceType.objects.create(name='Router', slug='router')
        self.device = Device.objects.create(
            name='Diff-Router',
            ip_address='192.168.1.3',
            vendor=self.vendor,
            device_type=self.device_type,
            username='admin',
            password_encrypted=encrypt_data('pass'),
            created_by=self.user
        )

    def test_create_diff(self):
        """Test creating a backup diff"""
        backup_old = Backup.objects.create(
            device=self.device,
            status='success',
            configuration_encrypted=encrypt_data('old config'),
            configuration_hash='old_hash'
        )
        backup_new = Backup.objects.create(
            device=self.device,
            status='success',
            configuration_encrypted=encrypt_data('new config'),
            configuration_hash='new_hash'
        )

        diff = BackupDiff.objects.create(
            backup_old=backup_old,
            backup_new=backup_new,
            diff_content='--- old\n+++ new\n- old config\n+ new config',
            additions=1,
            deletions=1,
            modifications=0
        )

        self.assertEqual(diff.additions, 1)
        self.assertEqual(diff.deletions, 1)
        self.assertIn('old config', diff.diff_content)

    def test_unique_diff_constraint(self):
        """Test unique constraint on backup pairs"""
        backup_old = Backup.objects.create(
            device=self.device,
            status='success',
            configuration_encrypted='',
            configuration_hash='old'
        )
        backup_new = Backup.objects.create(
            device=self.device,
            status='success',
            configuration_encrypted='',
            configuration_hash='new'
        )

        BackupDiff.objects.create(
            backup_old=backup_old,
            backup_new=backup_new,
            diff_content='diff1'
        )

        # Duplicate should fail
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            BackupDiff.objects.create(
                backup_old=backup_old,
                backup_new=backup_new,
                diff_content='diff2'
            )


class BackupAPITestCase(APITestCase):
    """Tests for Backup API endpoints"""

    def setUp(self):
        """Set up test fixtures"""
        User = get_user_model()
        self.user = User.objects.create_user(
            email='backup@example.com',
            username='backupuser',
            password='TestPass123!',
            role='administrator'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.vendor = Vendor.objects.create(
            name='Cisco',
            slug='cisco',
            backup_commands=['show running-config']
        )
        self.device_type = DeviceType.objects.create(name='Router', slug='router')
        self.device = Device.objects.create(
            name='API-Router',
            ip_address='192.168.1.4',
            vendor=self.vendor,
            device_type=self.device_type,
            username='admin',
            password_encrypted=encrypt_data('pass'),
            created_by=self.user
        )

    def test_list_backups(self):
        """Test listing backups"""
        Backup.objects.create(
            device=self.device,
            status='success',
            configuration_encrypted=encrypt_data('config'),
            configuration_hash='hash1'
        )

        response = self.client.get('/api/v1/backups/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_trigger_backup_permission(self):
        """Test backup trigger requires authentication"""
        self.client.logout()
        response = self.client.post(f'/api/v1/devices/devices/{self.device.id}/backup_now/')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('backups.tasks.backup_device')
    def test_trigger_backup_success(self, mock_backup):
        """Test successful backup trigger"""
        mock_backup.delay.return_value = MagicMock(id='task-123')

        response = self.client.post(f'/api/v1/devices/devices/{self.device.id}/backup_now/')

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        mock_backup.delay.assert_called_once()


class BackupSecurityTestCase(TestCase):
    """Tests for backup security features"""

    def setUp(self):
        """Set up test fixtures"""
        User = get_user_model()
        self.user = User.objects.create_user(
            email='security@example.com',
            username='securityuser',
            password='pass123'
        )

        self.vendor = Vendor.objects.create(name='Cisco', slug='cisco')
        self.device_type = DeviceType.objects.create(name='Router', slug='router')
        self.device = Device.objects.create(
            name='Secure-Router',
            ip_address='192.168.1.5',
            vendor=self.vendor,
            device_type=self.device_type,
            username='admin',
            password_encrypted=encrypt_data('pass'),
            created_by=self.user
        )

    def test_configuration_encrypted_at_rest(self):
        """Test configuration is encrypted when stored"""
        config = 'enable secret 5 $1$abc$xyz\npassword supersecret'

        backup = Backup.objects.create(
            device=self.device,
            status='success',
            configuration_encrypted='',
            configuration_hash=''
        )
        backup.set_configuration(config)
        backup.save()

        # Raw encrypted data should not contain plaintext
        self.assertNotIn('supersecret', backup.configuration_encrypted)
        self.assertNotIn('enable secret', backup.configuration_encrypted)

        # But decrypted should have original
        self.assertEqual(backup.get_configuration(), config)

    def test_different_iv_per_encryption(self):
        """Test that same config produces different ciphertext (random IV)"""
        config = 'test configuration data'

        backup1 = Backup.objects.create(
            device=self.device,
            status='success',
            configuration_encrypted=encrypt_data(config),
            configuration_hash='hash1'
        )
        backup2 = Backup.objects.create(
            device=self.device,
            status='success',
            configuration_encrypted=encrypt_data(config),
            configuration_hash='hash2'
        )

        # Same plaintext, different ciphertext
        self.assertNotEqual(
            backup1.configuration_encrypted,
            backup2.configuration_encrypted
        )


class BackupAPIAdvancedTestCase(APITestCase):
    """Advanced tests for Backup API endpoints"""

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            email='backup_adv@example.com',
            username='backupadv',
            password='TestPass123!',
            role='administrator'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

        self.vendor = Vendor.objects.create(
            name='Cisco',
            slug='cisco-adv',
            backup_commands=['show running-config']
        )
        self.device_type = DeviceType.objects.create(name='Router', slug='router-adv')
        self.device = Device.objects.create(
            name='Adv-Backup-Device',
            ip_address='192.168.1.10',
            vendor=self.vendor,
            device_type=self.device_type,
            username='admin',
            password_encrypted=encrypt_data('pass'),
            created_by=self.admin
        )

    def test_get_backup_detail(self):
        """Test getting backup details"""
        backup = Backup.objects.create(
            device=self.device,
            status='success',
            success=True,
            configuration_encrypted=encrypt_data('hostname Router'),
            configuration_hash='abc123'
        )

        response = self.client.get(f'/api/v1/backups/backups/{backup.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], backup.id)

    def test_list_backups_filter_by_device(self):
        """Test filtering backups by device"""
        Backup.objects.create(
            device=self.device,
            status='success',
            configuration_encrypted=encrypt_data('config'),
            configuration_hash='hash1'
        )

        response = self.client.get(f'/api/v1/backups/backups/?device={self.device.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_delete_backup_admin(self):
        """Test admin can delete backup"""
        backup = Backup.objects.create(
            device=self.device,
            status='success',
            configuration_encrypted=encrypt_data('config'),
            configuration_hash='hash1'
        )
        backup_id = backup.id

        response = self.client.delete(f'/api/v1/backups/backups/{backup_id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Backup.objects.filter(id=backup_id).exists())


class BackupScheduleAPITestCase(APITestCase):
    """Tests for BackupSchedule API"""

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            email='sched_admin@example.com',
            username='schedadmin',
            password='TestPass123!',
            role='administrator'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

        self.vendor = Vendor.objects.create(name='Cisco', slug='cisco-sched')
        self.device_type = DeviceType.objects.create(name='Router', slug='router-sched')
        self.device = Device.objects.create(
            name='Sched-Device',
            ip_address='192.168.1.20',
            vendor=self.vendor,
            device_type=self.device_type,
            username='admin',
            password_encrypted=encrypt_data('pass'),
            created_by=self.admin
        )

    def test_list_schedules(self):
        """Test listing backup schedules"""
        schedule = BackupSchedule.objects.create(
            name='Daily Backup',
            frequency='daily',
            run_time='02:00:00',
            is_active=True
        )
        schedule.devices.add(self.device)

        response = self.client.get('/api/v1/backups/schedules/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_schedule(self):
        """Test creating a backup schedule"""
        response = self.client.post('/api/v1/backups/schedules/', {
            'name': 'New Schedule',
            'frequency': 'daily',
            'run_time': '03:00:00',
            'is_active': True,
            'devices': [self.device.id]
        })
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])


class BackupRetentionPolicyAPITestCase(APITestCase):
    """Tests for BackupRetentionPolicy API"""

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            email='ret_admin@example.com',
            username='retadmin',
            password='TestPass123!',
            role='administrator'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_list_policies(self):
        """Test listing retention policies"""
        BackupRetentionPolicy.objects.create(
            name='Standard Policy',
            keep_last_n=20,
            is_active=True
        )

        response = self.client.get('/api/v1/backups/retention-policies/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_policy(self):
        """Test creating a retention policy"""
        response = self.client.post('/api/v1/backups/retention-policies/', {
            'name': 'New Policy',
            'keep_last_n': 30,
            'keep_daily': 14,
            'keep_weekly': 8,
            'keep_monthly': 12,
            'is_active': True
        })
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])


class BackupTasksTestCase(TestCase):
    """Tests for Celery backup tasks"""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email='task_user@example.com',
            username='taskuser',
            password='pass123'
        )
        self.vendor = Vendor.objects.create(
            name='Cisco',
            slug='cisco-task',
            backup_commands=['show running-config']
        )
        self.device_type = DeviceType.objects.create(name='Router', slug='router-task')
        self.device = Device.objects.create(
            name='Task-Device',
            ip_address='192.168.1.100',
            vendor=self.vendor,
            device_type=self.device_type,
            username='admin',
            password_encrypted=encrypt_data('password'),
            created_by=self.user
        )

    def test_update_schedule_stats_success(self):
        """Test updating schedule stats on success"""
        from backups.tasks import update_schedule_stats

        schedule = BackupSchedule.objects.create(
            name='Test Schedule',
            frequency='daily',
            run_time='02:00:00',
            is_active=True
        )
        initial_successful = schedule.successful_runs

        update_schedule_stats(schedule.id, success=True)

        schedule.refresh_from_db()
        self.assertEqual(schedule.successful_runs, initial_successful + 1)

    def test_update_schedule_stats_failure(self):
        """Test updating schedule stats on failure"""
        from backups.tasks import update_schedule_stats

        schedule = BackupSchedule.objects.create(
            name='Test Schedule 2',
            frequency='daily',
            run_time='02:00:00',
            is_active=True
        )
        initial_failed = schedule.failed_runs

        update_schedule_stats(schedule.id, success=False)

        schedule.refresh_from_db()
        self.assertEqual(schedule.failed_runs, initial_failed + 1)

    def test_update_schedule_stats_no_id(self):
        """Test update_schedule_stats with None id does nothing"""
        from backups.tasks import update_schedule_stats
        # Should not raise any exception
        update_schedule_stats(None, success=True)

    @patch('backups.tasks.backup_device_config')
    @patch('backups.tasks.DeviceLock')
    @patch('backups.tasks.get_channel_layer')
    @patch('backups.tasks.notify_backup_success')
    def test_backup_device_success(self, mock_notify, mock_channel, mock_lock_class, mock_backup_config):
        """Test successful device backup"""
        from backups.tasks import backup_device

        # Mock lock
        mock_lock = MagicMock()
        mock_lock.acquire.return_value = True
        mock_lock_class.return_value = mock_lock

        # Mock channel layer
        mock_channel.return_value = None

        # Mock backup config - return success
        mock_backup_config.return_value = (True, 'hostname Router\ninterface GigabitEthernet0/0', None)

        # Call task synchronously
        result = backup_device(
            device_id=self.device.id,
            triggered_by_id=self.user.id,
            backup_type='manual'
        )

        self.assertTrue(result['success'])
        self.assertIn('backup_id', result)
        mock_notify.assert_called_once()

    @patch('backups.tasks.DeviceLock')
    @patch('backups.tasks.get_channel_layer')
    def test_backup_device_locked(self, mock_channel, mock_lock_class):
        """Test backup fails when device is locked"""
        from backups.tasks import backup_device

        # Mock lock - fail to acquire
        mock_lock = MagicMock()
        mock_lock.acquire.return_value = False
        mock_lock_class.return_value = mock_lock

        mock_channel.return_value = None

        result = backup_device(
            device_id=self.device.id,
            triggered_by_id=self.user.id,
            backup_type='manual'
        )

        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Device busy')
        self.assertTrue(result['locked'])

    @patch('backups.tasks.get_channel_layer')
    def test_backup_device_not_found(self, mock_channel):
        """Test backup fails for non-existent device"""
        from backups.tasks import backup_device

        mock_channel.return_value = None

        result = backup_device(
            device_id=99999,  # Non-existent device
            triggered_by_id=self.user.id,
            backup_type='manual'
        )

        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Device not found')

    @patch('backups.tasks.backup_device_config')
    @patch('backups.tasks.DeviceLock')
    @patch('backups.tasks.get_channel_layer')
    @patch('backups.tasks.notify_backup_failed')
    def test_backup_device_connection_failed(self, mock_notify, mock_channel, mock_lock_class, mock_backup_config):
        """Test backup handles connection failure"""
        from backups.tasks import backup_device

        # Mock lock
        mock_lock = MagicMock()
        mock_lock.acquire.return_value = True
        mock_lock_class.return_value = mock_lock

        mock_channel.return_value = None

        # Mock backup config - return failure
        mock_backup_config.return_value = (False, None, 'Connection timed out')

        result = backup_device(
            device_id=self.device.id,
            triggered_by_id=self.user.id,
            backup_type='manual'
        )

        self.assertFalse(result['success'])
        mock_notify.assert_called_once()


class ConfigNormalizerTestCase(TestCase):
    """Tests for config normalizers"""

    def test_generic_normalizer(self):
        """Test generic normalizer doesn't change config"""
        from backups.config_normalizer import GenericNormalizer

        normalizer = GenericNormalizer()
        config = "hostname Router\ninterface GigabitEthernet0/0"

        result = normalizer.normalize(config)
        self.assertEqual(result, config)

    def test_mikrotik_normalizer(self):
        """Test MikroTik normalizer removes timestamps"""
        from backups.config_normalizer import MikrotikNormalizer

        normalizer = MikrotikNormalizer()
        config = """# 2025-11-23 10:17:44 by RouterOS 7.16
/interface ethernet
set [ find default-name=ether1 ] name=WAN"""

        result = normalizer.normalize(config)
        self.assertNotIn('2025-11-23', result)
        self.assertIn('/interface ethernet', result)

    def test_fortinet_normalizer_enc_passwords(self):
        """Test Fortinet normalizer redacts ENC passwords"""
        from backups.config_normalizer import FortinetNormalizer

        normalizer = FortinetNormalizer()
        config = """config system admin
    edit "admin"
        set password ENC SH2j2xXqP+8Fh7Eh
    next
end"""

        result = normalizer.normalize(config)
        self.assertNotIn('SH2j2xXqP+8Fh7Eh', result)
        self.assertIn('[REDACTED]', result)

    def test_fortinet_normalizer_crypto_blocks(self):
        """Test Fortinet normalizer removes crypto blocks"""
        from backups.config_normalizer import FortinetNormalizer

        normalizer = FortinetNormalizer()
        config = """config vpn certificate local
    edit "cert1"
        set certificate "-----BEGIN CERTIFICATE-----
MIICpDCCAYwCCQC8lLlX
-----END CERTIFICATE-----"
    next
end"""

        result = normalizer.normalize(config)
        self.assertIn('[CRYPTO_BLOCK_START]', result)
        self.assertIn('[CRYPTO_BLOCK_END]', result)
        self.assertNotIn('MIICpDCCAYwCCQC8lLlX', result)

    def test_cisco_normalizer_passwords(self):
        """Test Cisco normalizer redacts passwords"""
        from backups.config_normalizer import CiscoNormalizer

        normalizer = CiscoNormalizer()
        config = """hostname Router
username admin password 7 0822455D0A16
enable secret 5 $1$mERr$abc123xyz
interface GigabitEthernet0/0"""

        result = normalizer.normalize(config)
        self.assertNotIn('0822455D0A16', result)
        self.assertNotIn('$1$mERr$abc123xyz', result)
        self.assertIn('[REDACTED]', result)
        self.assertIn('hostname Router', result)

    def test_normalizer_factory_known_vendor(self):
        """Test factory returns correct normalizer for known vendor"""
        from backups.config_normalizer import NormalizerFactory, MikrotikNormalizer

        normalizer = NormalizerFactory.get_normalizer('mikrotik')
        self.assertIsInstance(normalizer, MikrotikNormalizer)

    def test_normalizer_factory_unknown_vendor(self):
        """Test factory returns generic normalizer for unknown vendor"""
        from backups.config_normalizer import NormalizerFactory, GenericNormalizer

        normalizer = NormalizerFactory.get_normalizer('unknown_vendor')
        self.assertIsInstance(normalizer, GenericNormalizer)

    def test_normalizer_factory_none_vendor(self):
        """Test factory handles None vendor"""
        from backups.config_normalizer import NormalizerFactory, GenericNormalizer

        normalizer = NormalizerFactory.get_normalizer(None)
        self.assertIsInstance(normalizer, GenericNormalizer)

    def test_normalize_config_function(self):
        """Test convenience function"""
        from backups.config_normalizer import normalize_config

        config = "# 2025-11-23 10:17:44 by RouterOS 7.16\ntest"
        result = normalize_config(config, 'mikrotik')
        self.assertNotIn('2025-11-23', result)


class BackupViewSetActionsTestCase(APITestCase):
    """Tests for Backup ViewSet actions: statistics, configuration, download, compare"""

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            email='backup_actions@example.com',
            username='backupactions',
            password='TestPass123!',
            role='administrator'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

        self.vendor = Vendor.objects.create(
            name='Cisco',
            slug='cisco-actions',
            backup_commands=['show running-config']
        )
        self.device_type = DeviceType.objects.create(name='Router', slug='router-actions')
        self.device = Device.objects.create(
            name='Actions-Device',
            ip_address='192.168.1.50',
            vendor=self.vendor,
            device_type=self.device_type,
            username='admin',
            password_encrypted=encrypt_data('pass'),
            created_by=self.admin
        )

    def test_statistics_endpoint(self):
        """Test backup statistics endpoint"""
        # Create some backups
        Backup.objects.create(
            device=self.device,
            status='success',
            success=True,
            configuration_encrypted=encrypt_data('config1'),
            configuration_hash='hash1',
            size_bytes=1024
        )
        Backup.objects.create(
            device=self.device,
            status='failed',
            success=False,
            configuration_encrypted='',
            configuration_hash='',
            size_bytes=0
        )

        response = self.client.get('/api/v1/backups/backups/statistics/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total', response.data)
        self.assertIn('successful', response.data)
        self.assertIn('failed', response.data)
        self.assertEqual(response.data['total'], 2)
        self.assertEqual(response.data['successful'], 1)
        self.assertEqual(response.data['failed'], 1)

    def test_configuration_endpoint(self):
        """Test getting backup configuration"""
        backup = Backup.objects.create(
            device=self.device,
            status='success',
            success=True,
            configuration_encrypted=encrypt_data('hostname Router\ninterface GigabitEthernet0/0'),
            configuration_hash='config_hash'
        )

        response = self.client.get(f'/api/v1/backups/backups/{backup.id}/configuration/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('configuration', response.data)
        self.assertIn('hostname Router', response.data['configuration'])

    def test_download_endpoint(self):
        """Test downloading backup as file"""
        backup = Backup.objects.create(
            device=self.device,
            status='success',
            success=True,
            configuration_encrypted=encrypt_data('hostname Router'),
            configuration_hash='download_hash'
        )

        response = self.client.get(f'/api/v1/backups/backups/{backup.id}/download/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'text/plain')
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertEqual(response.content.decode(), 'hostname Router')

    def test_compare_endpoint(self):
        """Test comparing two backups"""
        backup1 = Backup.objects.create(
            device=self.device,
            status='success',
            success=True,
            configuration_encrypted=encrypt_data('hostname Router1\ninterface eth0'),
            configuration_hash='compare_hash1'
        )
        backup2 = Backup.objects.create(
            device=self.device,
            status='success',
            success=True,
            configuration_encrypted=encrypt_data('hostname Router2\ninterface eth0'),
            configuration_hash='compare_hash2'
        )

        response = self.client.get(f'/api/v1/backups/backups/{backup2.id}/compare/{backup1.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('diff', response.data)

    def test_compare_backup_not_found(self):
        """Test comparing with non-existent backup"""
        backup = Backup.objects.create(
            device=self.device,
            status='success',
            success=True,
            configuration_encrypted=encrypt_data('config'),
            configuration_hash='compare_notfound'
        )

        response = self.client.get(f'/api/v1/backups/backups/{backup.id}/compare/99999/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_filter_by_vendor(self):
        """Test filtering backups by vendor"""
        Backup.objects.create(
            device=self.device,
            status='success',
            success=True,
            configuration_encrypted=encrypt_data('config'),
            configuration_hash='filter_vendor'
        )

        response = self.client.get(f'/api/v1/backups/backups/?vendor={self.vendor.id}')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_filter_by_device_type(self):
        """Test filtering backups by device type"""
        Backup.objects.create(
            device=self.device,
            status='success',
            success=True,
            configuration_encrypted=encrypt_data('config'),
            configuration_hash='filter_type'
        )

        response = self.client.get(f'/api/v1/backups/backups/?device_type={self.device_type.id}')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_filter_by_success(self):
        """Test filtering backups by success status"""
        Backup.objects.create(
            device=self.device,
            status='success',
            success=True,
            configuration_encrypted=encrypt_data('config'),
            configuration_hash='success_filter'
        )
        Backup.objects.create(
            device=self.device,
            status='failed',
            success=False,
            configuration_encrypted='',
            configuration_hash=''
        )

        response = self.client.get('/api/v1/backups/backups/?success=true')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_filter_by_date_range(self):
        """Test filtering backups by date range"""
        Backup.objects.create(
            device=self.device,
            status='success',
            success=True,
            configuration_encrypted=encrypt_data('config'),
            configuration_hash='date_filter'
        )

        today = timezone.now().date().isoformat()
        response = self.client.get(f'/api/v1/backups/backups/?date_from={today}&date_to={today}')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
