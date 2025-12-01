"""
Tests for netvault core module - dashboard views, system settings
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.utils import timezone
from datetime import timedelta

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
