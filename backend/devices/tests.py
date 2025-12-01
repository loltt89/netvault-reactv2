"""
Tests for devices app - Device, Vendor, DeviceType models
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock

from devices.models import Device, Vendor, DeviceType, DeviceCredential
from core.crypto import encrypt_data, decrypt_data


class VendorModelTestCase(TestCase):
    """Tests for Vendor model"""

    def test_create_vendor(self):
        """Test creating a vendor"""
        vendor = Vendor.objects.create(
            name='Cisco',
            slug='cisco',
            description='Cisco Systems',
            backup_commands=['show running-config', 'show startup-config'],
            is_predefined=True
        )

        self.assertEqual(vendor.name, 'Cisco')
        self.assertEqual(vendor.slug, 'cisco')
        self.assertEqual(len(vendor.backup_commands), 2)
        self.assertTrue(vendor.is_predefined)

    def test_vendor_str(self):
        """Test vendor string representation"""
        vendor = Vendor.objects.create(name='Huawei', slug='huawei')
        self.assertEqual(str(vendor), 'Huawei')

    def test_vendor_ordering(self):
        """Test vendors are ordered by name"""
        Vendor.objects.create(name='Zyxel', slug='zyxel')
        Vendor.objects.create(name='Cisco', slug='cisco')
        Vendor.objects.create(name='Mikrotik', slug='mikrotik')

        vendors = list(Vendor.objects.values_list('name', flat=True))
        self.assertEqual(vendors, ['Cisco', 'Mikrotik', 'Zyxel'])


class DeviceTypeModelTestCase(TestCase):
    """Tests for DeviceType model"""

    def test_create_device_type(self):
        """Test creating a device type"""
        device_type = DeviceType.objects.create(
            name='Router',
            slug='router',
            description='Network router',
            icon='router',
            is_predefined=True
        )

        self.assertEqual(device_type.name, 'Router')
        self.assertEqual(device_type.icon, 'router')

    def test_device_type_str(self):
        """Test device type string representation"""
        device_type = DeviceType.objects.create(name='Switch', slug='switch')
        self.assertEqual(str(device_type), 'Switch')


class DeviceModelTestCase(TestCase):
    """Tests for Device model"""

    def setUp(self):
        """Set up test fixtures"""
        User = get_user_model()
        self.user = User.objects.create_user(
            email='device@example.com',
            username='deviceuser',
            password='pass123'
        )
        self.vendor = Vendor.objects.create(
            name='Cisco',
            slug='cisco',
            backup_commands=['show running-config']
        )
        self.device_type = DeviceType.objects.create(
            name='Router',
            slug='router'
        )

    def test_create_device(self):
        """Test creating a device"""
        device = Device.objects.create(
            name='Core-Router-1',
            ip_address='192.168.1.1',
            vendor=self.vendor,
            device_type=self.device_type,
            protocol='ssh',
            port=22,
            username='admin',
            password_encrypted=encrypt_data('secret123'),
            location='Data Center 1',
            criticality='high',
            created_by=self.user
        )

        self.assertEqual(device.name, 'Core-Router-1')
        self.assertEqual(device.ip_address, '192.168.1.1')
        self.assertEqual(device.protocol, 'ssh')
        self.assertEqual(device.criticality, 'high')

    def test_device_str(self):
        """Test device string representation"""
        device = Device.objects.create(
            name='Test-Device',
            ip_address='10.0.0.1',
            vendor=self.vendor,
            device_type=self.device_type,
            username='admin',
            password_encrypted=encrypt_data('pass'),
            created_by=self.user
        )
        self.assertEqual(str(device), 'Test-Device (10.0.0.1)')

    def test_password_encryption(self):
        """Test password encryption/decryption"""
        device = Device.objects.create(
            name='Encrypted-Device',
            ip_address='10.0.0.2',
            vendor=self.vendor,
            device_type=self.device_type,
            username='admin',
            password_encrypted=encrypt_data('temp'),
            created_by=self.user
        )
        device.set_password('MySecretPassword123!')
        device.save()

        # Encrypted should not be plaintext
        self.assertNotEqual(device.password_encrypted, 'MySecretPassword123!')

        # Decrypted should match original
        self.assertEqual(device.get_password(), 'MySecretPassword123!')

    def test_enable_password_encryption(self):
        """Test enable password encryption/decryption"""
        device = Device.objects.create(
            name='Enable-Device',
            ip_address='10.0.0.3',
            vendor=self.vendor,
            device_type=self.device_type,
            username='admin',
            password_encrypted=encrypt_data('pass'),
            created_by=self.user
        )
        device.set_enable_password('EnableSecret!')
        device.save()

        self.assertEqual(device.get_enable_password(), 'EnableSecret!')

    def test_get_backup_commands_custom(self):
        """Test device returns custom commands if set"""
        device = Device.objects.create(
            name='Custom-Device',
            ip_address='10.0.0.4',
            vendor=self.vendor,
            device_type=self.device_type,
            username='admin',
            password_encrypted=encrypt_data('pass'),
            custom_commands=['custom command 1', 'custom command 2'],
            created_by=self.user
        )

        commands = device.get_backup_commands()
        self.assertEqual(commands, ['custom command 1', 'custom command 2'])

    def test_get_backup_commands_vendor(self):
        """Test device returns vendor commands if no custom"""
        device = Device.objects.create(
            name='Vendor-Device',
            ip_address='10.0.0.5',
            vendor=self.vendor,
            device_type=self.device_type,
            username='admin',
            password_encrypted=encrypt_data('pass'),
            custom_commands=[],
            created_by=self.user
        )

        commands = device.get_backup_commands()
        self.assertEqual(commands, ['show running-config'])

    def test_csv_injection_prevention_name(self):
        """Test CSV injection characters are sanitized in name"""
        device = Device(
            name='=CMD|calc|',
            ip_address='10.0.0.6',
            vendor=self.vendor,
            device_type=self.device_type,
            username='admin',
            password_encrypted=encrypt_data('pass'),
            created_by=self.user
        )
        device.clean()

        self.assertTrue(device.name.startswith("'"))

    def test_csv_injection_prevention_location(self):
        """Test CSV injection characters are sanitized in location"""
        device = Device(
            name='Safe-Device',
            ip_address='10.0.0.7',
            vendor=self.vendor,
            device_type=self.device_type,
            username='admin',
            password_encrypted=encrypt_data('pass'),
            location='+1-555-1234',
            created_by=self.user
        )
        device.clean()

        self.assertTrue(device.location.startswith("'"))

    def test_default_values(self):
        """Test default field values"""
        device = Device.objects.create(
            name='Default-Device',
            ip_address='10.0.0.8',
            vendor=self.vendor,
            device_type=self.device_type,
            username='admin',
            password_encrypted=encrypt_data('pass'),
            created_by=self.user
        )

        self.assertEqual(device.protocol, 'ssh')
        self.assertEqual(device.port, 22)
        self.assertEqual(device.status, 'unknown')
        self.assertEqual(device.criticality, 'medium')
        self.assertTrue(device.backup_enabled)


class DeviceCredentialTestCase(TestCase):
    """Tests for DeviceCredential model"""

    def setUp(self):
        """Set up test fixtures"""
        User = get_user_model()
        self.user = User.objects.create_user(
            email='cred@example.com',
            username='creduser',
            password='pass123'
        )
        self.vendor = Vendor.objects.create(name='Cisco', slug='cisco')
        self.device_type = DeviceType.objects.create(name='Router', slug='router')
        self.device = Device.objects.create(
            name='Cred-Device',
            ip_address='10.0.0.10',
            vendor=self.vendor,
            device_type=self.device_type,
            username='admin',
            password_encrypted=encrypt_data('pass'),
            created_by=self.user
        )

    def test_create_credential(self):
        """Test creating device credential"""
        cred = DeviceCredential.objects.create(
            device=self.device,
            credential_type='enable',
            username='enableuser',
            password_encrypted=encrypt_data('enablepass'),
            description='Enable password'
        )

        self.assertEqual(cred.credential_type, 'enable')
        self.assertEqual(cred.username, 'enableuser')

    def test_credential_encryption(self):
        """Test credential password encryption"""
        cred = DeviceCredential.objects.create(
            device=self.device,
            credential_type='tacacs',
            password_encrypted=encrypt_data('temp')
        )
        cred.set_password('TacacsSecret!')
        cred.save()

        self.assertNotEqual(cred.password_encrypted, 'TacacsSecret!')
        self.assertEqual(cred.get_password(), 'TacacsSecret!')


class DeviceAPITestCase(APITestCase):
    """Tests for Device API endpoints"""

    def setUp(self):
        """Set up test fixtures"""
        User = get_user_model()
        self.admin = User.objects.create_user(
            email='admin@example.com',
            username='admin',
            password='TestPass123!',
            role='administrator'
        )
        self.viewer = User.objects.create_user(
            email='viewer@example.com',
            username='viewer',
            password='TestPass123!',
            role='viewer'
        )

        self.client = APIClient()
        self.vendor = Vendor.objects.create(name='Cisco', slug='cisco')
        self.device_type = DeviceType.objects.create(name='Router', slug='router')

    def test_list_devices_authenticated(self):
        """Test listing devices requires authentication"""
        response = self.client.get('/api/v1/devices/devices/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_devices_success(self):
        """Test listing devices as authenticated user"""
        self.client.force_authenticate(user=self.viewer)

        Device.objects.create(
            name='List-Device',
            ip_address='10.0.0.20',
            vendor=self.vendor,
            device_type=self.device_type,
            username='admin',
            password_encrypted=encrypt_data('pass'),
            created_by=self.admin
        )

        response = self.client.get('/api/v1/devices/devices/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_device_admin(self):
        """Test creating device as admin"""
        self.client.force_authenticate(user=self.admin)

        response = self.client.post('/api/v1/devices/devices/', {
            'name': 'New-Device',
            'ip_address': '10.0.0.21',
            'vendor': self.vendor.id,
            'device_type': self.device_type.id,
            'username': 'admin',
            'password': 'secret123',
            'protocol': 'ssh',
            'port': 22
        })

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New-Device')

    def test_create_device_viewer_forbidden(self):
        """Test creating device as viewer is forbidden"""
        self.client.force_authenticate(user=self.viewer)

        response = self.client.post('/api/v1/devices/devices/', {
            'name': 'Forbidden-Device',
            'ip_address': '10.0.0.22',
            'vendor': self.vendor.id,
            'device_type': self.device_type.id,
            'username': 'admin',
            'password': 'secret123'
        })

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_password_not_exposed_in_api(self):
        """Test password is not exposed in API response"""
        self.client.force_authenticate(user=self.admin)

        device = Device.objects.create(
            name='Secret-Device',
            ip_address='10.0.0.23',
            vendor=self.vendor,
            device_type=self.device_type,
            username='admin',
            password_encrypted=encrypt_data('supersecret'),
            created_by=self.admin
        )

        response = self.client.get(f'/api/v1/devices/devices/{device.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('password_encrypted', response.data)
        self.assertNotIn('supersecret', str(response.data))


class DeviceValidationTestCase(TestCase):
    """Tests for device validation"""

    def setUp(self):
        """Set up test fixtures"""
        User = get_user_model()
        self.user = User.objects.create_user(
            email='valid@example.com',
            username='validuser',
            password='pass123'
        )
        self.vendor = Vendor.objects.create(name='Cisco', slug='cisco')
        self.device_type = DeviceType.objects.create(name='Router', slug='router')

    def test_unique_name(self):
        """Test device name must be unique"""
        Device.objects.create(
            name='Unique-Device',
            ip_address='10.0.0.30',
            vendor=self.vendor,
            device_type=self.device_type,
            username='admin',
            password_encrypted=encrypt_data('pass'),
            created_by=self.user
        )

        # Device.save() calls full_clean() which raises ValidationError
        with self.assertRaises(ValidationError):
            Device.objects.create(
                name='Unique-Device',
                ip_address='10.0.0.31',
                vendor=self.vendor,
                device_type=self.device_type,
                username='admin',
                password_encrypted=encrypt_data('pass'),
                created_by=self.user
            )

    def test_valid_ip_address(self):
        """Test IP address validation"""
        device = Device.objects.create(
            name='Valid-IP-Device',
            ip_address='192.168.1.1',
            vendor=self.vendor,
            device_type=self.device_type,
            username='admin',
            password_encrypted=encrypt_data('pass'),
            created_by=self.user
        )

        self.assertEqual(device.ip_address, '192.168.1.1')

    def test_protocol_choices(self):
        """Test protocol must be valid choice"""
        for protocol in ['ssh', 'telnet']:
            device = Device.objects.create(
                name=f'Protocol-{protocol}-Device',
                ip_address=f'10.0.0.{32 if protocol == "ssh" else 33}',
                vendor=self.vendor,
                device_type=self.device_type,
                protocol=protocol,
                username='admin',
                password_encrypted=encrypt_data('pass'),
                created_by=self.user
            )
            self.assertEqual(device.protocol, protocol)

    def test_criticality_choices(self):
        """Test criticality must be valid choice"""
        valid_choices = ['low', 'medium', 'high', 'critical']

        for i, crit in enumerate(valid_choices):
            device = Device.objects.create(
                name=f'Crit-{crit}-Device',
                ip_address=f'10.0.0.{40 + i}',
                vendor=self.vendor,
                device_type=self.device_type,
                criticality=crit,
                username='admin',
                password_encrypted=encrypt_data('pass'),
                created_by=self.user
            )
            self.assertEqual(device.criticality, crit)
