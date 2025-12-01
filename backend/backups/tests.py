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
        response = self.client.post(f'/api/v1/devices/{self.device.id}/backup/')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('backups.views.run_device_backup')
    def test_trigger_backup_success(self, mock_backup):
        """Test successful backup trigger"""
        mock_backup.delay.return_value = MagicMock(id='task-123')

        response = self.client.post(f'/api/v1/devices/{self.device.id}/backup/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
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
