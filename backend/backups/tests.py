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

    def test_apply_now_requires_admin(self):
        """apply_now actually deletes data now — must be admin-only, like
        deleting an individual backup already is via CanManageBackups."""
        User = get_user_model()
        operator = User.objects.create_user(
            email='ret_operator@example.com', username='retoperator',
            password='TestPass123!', role='operator'
        )
        policy = BackupRetentionPolicy.objects.create(name='Op Policy', keep_last_n=5)

        client = APIClient()
        client.force_authenticate(user=operator)
        response = client.post(f'/api/v1/backups/retention-policies/{policy.id}/apply_now/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_apply_now_actually_deletes(self):
        """The fix: this used to be a stub that returned success without
        doing anything. Now it must actually apply the policy's rules."""
        vendor = Vendor.objects.create(name='Cisco', slug='cisco-apply-now')
        device_type = DeviceType.objects.create(name='Router', slug='router-apply-now')
        device = Device.objects.create(
            name='ApplyNow-Device', ip_address='10.0.9.50', vendor=vendor,
            device_type=device_type, username='admin',
            password_encrypted=encrypt_data('pw'), created_by=self.admin,
        )

        now = timezone.now()
        for i in range(10):
            b = Backup.objects.create(
                device=device, status='success', success=True,
                configuration_encrypted=encrypt_data('config'),
                configuration_hash=f'hash{i}',
            )
            Backup.objects.filter(id=b.id).update(created_at=now - timedelta(days=i * 60))

        policy = BackupRetentionPolicy.objects.create(
            name='Apply-Now Policy', keep_last_n=2, keep_daily=0, keep_weekly=0, keep_monthly=0,
        )

        response = self.client.post(f'/api/v1/backups/retention-policies/{policy.id}/apply_now/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['deleted_count'], 8)
        self.assertEqual(response.data['kept_count'], 2)
        self.assertEqual(Backup.objects.filter(device=device).count(), 2)


class RetentionPolicyApplicationTestCase(TestCase):
    """Tests for the GFS retention algorithm itself
    (_backups_outside_retention / apply_retention_policy) — the fix for
    BackupRetentionPolicy.apply_now being a no-op stub that never read
    keep_last_n/keep_daily/keep_weekly/keep_monthly at all.
    """

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email='gfs@example.com', username='gfsuser', password='TestPass123!'
        )
        self.vendor = Vendor.objects.create(name='Cisco', slug='cisco-gfs')
        self.device_type = DeviceType.objects.create(name='Router', slug='router-gfs')
        self.device = Device.objects.create(
            name='GFS-Device', ip_address='10.0.9.60', vendor=self.vendor,
            device_type=self.device_type, username='admin',
            password_encrypted=encrypt_data('pw'), created_by=self.user,
        )

    def _make_backup(self, days_ago, status='success'):
        b = Backup.objects.create(
            device=self.device, status=status, success=(status == 'success'),
            configuration_encrypted=encrypt_data('config'),
            configuration_hash=f'hash-{days_ago}-{status}',
        )
        Backup.objects.filter(id=b.id).update(created_at=timezone.now() - timedelta(days=days_ago))
        return Backup.objects.get(id=b.id)

    def test_keeps_last_n_regardless_of_age(self):
        from backups.tasks import apply_retention_policy

        for days in [0, 1, 400, 500]:
            self._make_backup(days)

        policy = BackupRetentionPolicy.objects.create(
            name='LastN', keep_last_n=2, keep_daily=0, keep_weekly=0, keep_monthly=0,
        )
        result = apply_retention_policy(policy, dry_run=False)
        self.assertEqual(result['deleted_count'], 2)
        self.assertEqual(result['kept_count'], 2)
        remaining_ages = sorted(
            (timezone.now() - b.created_at).days for b in Backup.objects.filter(device=self.device)
        )
        self.assertEqual(remaining_ages, [0, 1])

    def test_only_one_kept_per_day_in_daily_window(self):
        from backups.tasks import apply_retention_policy

        # Two backups on "day 10" (a few hours apart) inside the daily
        # window. Anchored to a fixed noon-UTC timestamp rather than
        # "now minus N hours" — the latter crosses the UTC calendar-day
        # boundary (landing the two backups in different daily buckets
        # instead of one) whenever the test happens to run within the
        # first few hours of the UTC day.
        day_10_noon = timezone.now().replace(hour=12, minute=0, second=0, microsecond=0) - timedelta(days=10)
        b1 = self._make_backup(10)
        b2 = self._make_backup(10)
        Backup.objects.filter(id=b1.id).update(created_at=day_10_noon)
        Backup.objects.filter(id=b2.id).update(created_at=day_10_noon - timedelta(hours=5))

        policy = BackupRetentionPolicy.objects.create(
            name='Daily', keep_last_n=0, keep_daily=30, keep_weekly=0, keep_monthly=0,
        )
        result = apply_retention_policy(policy, dry_run=False)
        self.assertEqual(result['kept_count'], 1)
        self.assertEqual(result['deleted_count'], 1)

    def test_backup_older_than_every_bucket_is_deleted(self):
        from backups.tasks import apply_retention_policy

        self._make_backup(days_ago=1000)  # far older than any keep window

        policy = BackupRetentionPolicy.objects.create(
            name='Short', keep_last_n=0, keep_daily=7, keep_weekly=4, keep_monthly=1,
        )
        result = apply_retention_policy(policy, dry_run=False)
        self.assertEqual(result['deleted_count'], 1)
        self.assertEqual(Backup.objects.count(), 0)

    def test_dry_run_does_not_delete(self):
        from backups.tasks import apply_retention_policy

        self._make_backup(days_ago=1000)
        policy = BackupRetentionPolicy.objects.create(
            name='DryRun', keep_last_n=0, keep_daily=0, keep_weekly=0, keep_monthly=0,
        )
        result = apply_retention_policy(policy, dry_run=True)
        self.assertEqual(result['deleted_count'], 1)  # reports what *would* be deleted
        self.assertEqual(Backup.objects.count(), 1)  # but nothing actually removed

    def test_only_successful_backups_are_subject_to_retention(self):
        """Failed/partial/pending/running backups aren't config snapshots
        to retain — they must be left alone by this, not silently deleted
        as a side effect of a retention policy meant for successful ones."""
        from backups.tasks import apply_retention_policy

        self._make_backup(days_ago=1000, status='failed')
        self._make_backup(days_ago=1000, status='partial')

        policy = BackupRetentionPolicy.objects.create(
            name='SuccessOnly', keep_last_n=0, keep_daily=0, keep_weekly=0, keep_monthly=0,
        )
        result = apply_retention_policy(policy, dry_run=False)
        self.assertEqual(result['deleted_count'], 0)
        self.assertEqual(Backup.objects.count(), 2)

    def test_policy_with_no_devices_applies_to_all(self):
        from backups.tasks import apply_retention_policy

        self._make_backup(days_ago=1000)
        other_device = Device.objects.create(
            name='Other-GFS-Device', ip_address='10.0.9.61', vendor=self.vendor,
            device_type=self.device_type, username='admin',
            password_encrypted=encrypt_data('pw'), created_by=self.user,
        )
        b = Backup.objects.create(
            device=other_device, status='success', success=True,
            configuration_encrypted=encrypt_data('config'), configuration_hash='other-hash',
        )
        Backup.objects.filter(id=b.id).update(created_at=timezone.now() - timedelta(days=1000))

        policy = BackupRetentionPolicy.objects.create(
            name='Global', keep_last_n=0, keep_daily=0, keep_weekly=0, keep_monthly=0,
        )
        self.assertEqual(policy.devices.count(), 0)  # unscoped

        result = apply_retention_policy(policy, dry_run=False)
        self.assertEqual(result['deleted_count'], 2)  # both devices' backups affected

    def test_policy_scoped_to_specific_device_ignores_others(self):
        from backups.tasks import apply_retention_policy

        self._make_backup(days_ago=1000)
        other_device = Device.objects.create(
            name='Unscoped-Device', ip_address='10.0.9.62', vendor=self.vendor,
            device_type=self.device_type, username='admin',
            password_encrypted=encrypt_data('pw'), created_by=self.user,
        )
        b = Backup.objects.create(
            device=other_device, status='success', success=True,
            configuration_encrypted=encrypt_data('config'), configuration_hash='unscoped-hash',
        )
        Backup.objects.filter(id=b.id).update(created_at=timezone.now() - timedelta(days=1000))

        policy = BackupRetentionPolicy.objects.create(
            name='Scoped', keep_last_n=0, keep_daily=0, keep_weekly=0, keep_monthly=0,
        )
        policy.devices.add(self.device)

        result = apply_retention_policy(policy, dry_run=False)
        self.assertEqual(result['deleted_count'], 1)  # only self.device's backup
        self.assertEqual(Backup.objects.filter(device=other_device).count(), 1)  # untouched


class ReapStaleBackupsTestCase(TestCase):
    """Tests for the fix: a Backup stuck at status='running' forever if the
    worker process died mid-task (OOM, hard CELERY_TASK_TIME_LIMIT SIGKILL,
    pod eviction) — no except/finally block runs in that case, so nothing
    ever revisited the row before this task existed.
    """

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email='reap@example.com', username='reapuser', password='TestPass123!'
        )
        self.vendor = Vendor.objects.create(name='Cisco', slug='cisco-reap')
        self.device_type = DeviceType.objects.create(name='Router', slug='router-reap')
        self.device = Device.objects.create(
            name='Reap-Device', ip_address='10.0.9.70', vendor=self.vendor,
            device_type=self.device_type, username='admin',
            password_encrypted=encrypt_data('pw'), created_by=self.user,
        )

    def _make_running_backup(self, started_ago):
        from django.conf import settings
        b = Backup.objects.create(device=self.device, status='running')
        Backup.objects.filter(id=b.id).update(started_at=timezone.now() - started_ago)
        return Backup.objects.get(id=b.id)

    def test_reaps_backup_stuck_past_time_limit(self):
        from django.conf import settings
        from backups.tasks import reap_stale_backups

        stale = self._make_running_backup(timedelta(seconds=settings.CELERY_TASK_TIME_LIMIT + 600))

        result = reap_stale_backups()
        self.assertEqual(result['reaped_count'], 1)

        stale.refresh_from_db()
        self.assertEqual(stale.status, 'failed')
        self.assertFalse(stale.success)
        self.assertIsNotNone(stale.completed_at)
        self.assertIsNotNone(stale.duration_seconds)
        self.assertIn('worker', stale.error_message.lower())

    def test_does_not_touch_recently_started_running_backup(self):
        """A backup that's genuinely still in progress (well within the
        time limit) must not be falsely marked failed."""
        from backups.tasks import reap_stale_backups

        fresh = self._make_running_backup(timedelta(minutes=2))

        result = reap_stale_backups()
        self.assertEqual(result['reaped_count'], 0)

        fresh.refresh_from_db()
        self.assertEqual(fresh.status, 'running')

    def test_does_not_touch_completed_backups(self):
        from django.conf import settings
        from backups.tasks import reap_stale_backups

        old_success = Backup.objects.create(
            device=self.device, status='success', success=True,
            configuration_encrypted=encrypt_data('cfg'), configuration_hash='h1',
        )
        Backup.objects.filter(id=old_success.id).update(
            started_at=timezone.now() - timedelta(seconds=settings.CELERY_TASK_TIME_LIMIT + 600)
        )

        reap_stale_backups()

        old_success.refresh_from_db()
        self.assertEqual(old_success.status, 'success')


class LockHeartbeatTestCase(TestCase):
    """Tests for _lock_heartbeat — the fix for DeviceLock's fixed 120s TTL
    being shorter than a real backup can take (multiple setup commands,
    each with up to 60s of idle-wait budget for paged output, easily
    exceeds 2 minutes) and DeviceLock.extend() existing but never being
    called from production code.
    """

    def test_extends_periodically_until_stopped(self):
        import threading
        import time
        from backups.tasks import _lock_heartbeat

        mock_lock = MagicMock()
        stop_event = threading.Event()

        thread = threading.Thread(
            target=_lock_heartbeat, args=(mock_lock, stop_event), kwargs={'interval': 0.02, 'extend_by': 120}
        )
        thread.start()
        time.sleep(0.1)  # several intervals' worth
        stop_event.set()
        thread.join(timeout=2)

        self.assertFalse(thread.is_alive())
        self.assertGreaterEqual(mock_lock.extend.call_count, 2)
        mock_lock.extend.assert_called_with(120)

    def test_stops_immediately_without_extending_if_already_set(self):
        import threading
        from backups.tasks import _lock_heartbeat

        mock_lock = MagicMock()
        stop_event = threading.Event()
        stop_event.set()  # already stopped before the thread even starts

        thread = threading.Thread(target=_lock_heartbeat, args=(mock_lock, stop_event), kwargs={'interval': 60})
        thread.start()
        thread.join(timeout=2)

        self.assertFalse(thread.is_alive())
        mock_lock.extend.assert_not_called()


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


class BackupScopeRBACTestCase(APITestCase):
    """Tests for device_scope restricting BackupViewSet's queryset, and
    the compare endpoint's second backup specifically (it used to fetch
    compare_id from the unscoped Backup.objects manager)."""

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            email='backup_scope_admin@example.com', username='backup_scope_admin',
            password='TestPass123!', role='administrator',
        )
        self.scoped_viewer = User.objects.create_user(
            email='backup_scope_viewer@example.com', username='backup_scope_viewer',
            password='TestPass123!', role='viewer', device_scope={'tags': ['core']},
        )

        self.vendor = Vendor.objects.create(name='Cisco', slug='cisco-backup-scope')
        self.device_type = DeviceType.objects.create(name='Router', slug='router-backup-scope')
        self.core_device = Device.objects.create(
            name='Core-BK', ip_address='10.3.0.1', vendor=self.vendor,
            device_type=self.device_type, username='admin',
            password_encrypted=encrypt_data('pw'), created_by=self.admin, tags=['core'],
        )
        self.edge_device = Device.objects.create(
            name='Edge-BK', ip_address='10.3.0.2', vendor=self.vendor,
            device_type=self.device_type, username='admin',
            password_encrypted=encrypt_data('pw'), created_by=self.admin, tags=['edge'],
        )
        self.core_backup = Backup.objects.create(
            device=self.core_device, status='success', success=True,
            configuration_encrypted=encrypt_data('core config'), configuration_hash='core-hash',
        )
        self.edge_backup = Backup.objects.create(
            device=self.edge_device, status='success', success=True,
            configuration_encrypted=encrypt_data('edge config'), configuration_hash='edge-hash',
        )

    def test_scoped_viewer_list_excludes_out_of_scope_backup(self):
        self.client.force_authenticate(user=self.scoped_viewer)
        response = self.client.get('/api/v1/backups/backups/')
        ids = {b['id'] for b in response.data['results']}
        self.assertIn(self.core_backup.id, ids)
        self.assertNotIn(self.edge_backup.id, ids)

    def test_scoped_viewer_cannot_download_out_of_scope_backup(self):
        self.client.force_authenticate(user=self.scoped_viewer)
        response = self.client.get(f'/api/v1/backups/backups/{self.edge_backup.id}/download/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_scoped_viewer_cannot_leak_out_of_scope_backup_via_compare(self):
        """
        compare_id is a second, attacker-suppliable backup ID on top of
        the URL's own (correctly scoped-by-get_object) pk — regression
        test for the fix that made it use the scoped queryset too.
        """
        self.client.force_authenticate(user=self.scoped_viewer)
        response = self.client.get(
            f'/api/v1/backups/backups/{self.core_backup.id}/compare/{self.edge_backup.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_scoped_viewer_can_compare_two_in_scope_backups(self):
        core_backup2 = Backup.objects.create(
            device=self.core_device, status='success', success=True,
            configuration_encrypted=encrypt_data('core config v2'), configuration_hash='core-hash-2',
        )
        self.client.force_authenticate(user=self.scoped_viewer)
        response = self.client.get(
            f'/api/v1/backups/backups/{core_backup2.id}/compare/{self.core_backup.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class SendStaleBackupDigestTaskTestCase(TestCase):
    """Tests for the weekly stale-backup digest Celery task"""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email='digest_admin@example.com', username='digest_admin', password='pass123',
        )
        self.vendor = Vendor.objects.create(name='Cisco', slug='cisco-digest')
        self.device_type = DeviceType.objects.create(name='Router', slug='router-digest')

    def _make_device(self, name, last_backup):
        return Device.objects.create(
            name=name, ip_address='10.5.0.1', vendor=self.vendor,
            device_type=self.device_type, username='admin',
            password_encrypted=encrypt_data('pw'), created_by=self.user,
            last_backup=last_backup,
        )

    @patch('notifications.services.send_email_notification')
    @patch('core.models.SystemSettings')
    def test_disabled_toggle_sends_nothing(self, mock_settings, mock_email):
        mock_settings.get_settings.return_value = MagicMock(notify_schedule_summary=False)
        self._make_device('Stale4', None)

        from backups.tasks import send_stale_backup_digest
        result = send_stale_backup_digest()

        mock_email.assert_not_called()
        self.assertFalse(result['sent'])

    @patch('notifications.services.send_email_notification')
    @patch('core.models.SystemSettings')
    def test_no_stale_devices_sends_nothing(self, mock_settings, mock_email):
        mock_settings.get_settings.return_value = MagicMock(notify_schedule_summary=True)
        self._make_device('Fresh4', timezone.now())

        from backups.tasks import send_stale_backup_digest
        result = send_stale_backup_digest()

        mock_email.assert_not_called()
        self.assertFalse(result['sent'])

    @patch('notifications.services.send_email_notification', return_value=True)
    @patch('core.models.SystemSettings')
    def test_stale_devices_trigger_email_with_names(self, mock_settings, mock_email):
        mock_settings.get_settings.return_value = MagicMock(notify_schedule_summary=True)
        self._make_device('VeryStaleDevice', timezone.now() - timedelta(days=30))

        from backups.tasks import send_stale_backup_digest
        result = send_stale_backup_digest()

        mock_email.assert_called_once()
        subject, body = mock_email.call_args[0][:2]
        self.assertIn('1', subject)
        self.assertIn('VeryStaleDevice', body)
        self.assertTrue(result['sent'])
        self.assertEqual(result['stale_count'], 1)
