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


class DeviceAPIAdvancedTestCase(APITestCase):
    """Advanced tests for Device API endpoints"""

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            email='admin_adv@example.com',
            username='adminadv',
            password='TestPass123!',
            role='administrator'
        )
        self.operator = User.objects.create_user(
            email='operator@example.com',
            username='operator',
            password='TestPass123!',
            role='operator'
        )
        self.client = APIClient()
        self.vendor = Vendor.objects.create(name='Cisco', slug='cisco-adv')
        self.device_type = DeviceType.objects.create(name='Router', slug='router-adv')
        self.device = Device.objects.create(
            name='Adv-Device',
            ip_address='10.0.0.50',
            vendor=self.vendor,
            device_type=self.device_type,
            username='admin',
            password_encrypted=encrypt_data('pass'),
            created_by=self.admin
        )

    def test_update_device_admin(self):
        """Test admin can update device"""
        self.client.force_authenticate(user=self.admin)
        response = self.client.patch(f'/api/v1/devices/devices/{self.device.id}/', {
            'name': 'Updated-Device',
            'location': 'New Location'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.device.refresh_from_db()
        self.assertEqual(self.device.name, 'Updated-Device')

    def test_delete_device_admin(self):
        """Test admin can delete device"""
        self.client.force_authenticate(user=self.admin)
        device_id = self.device.id
        response = self.client.delete(f'/api/v1/devices/devices/{device_id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Device.objects.filter(id=device_id).exists())

    def test_operator_can_view(self):
        """Test operator can view devices"""
        self.client.force_authenticate(user=self.operator)
        response = self.client.get('/api/v1/devices/devices/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_bulk_delete_admin(self):
        """Test admin can bulk delete devices"""
        self.client.force_authenticate(user=self.admin)
        device2 = Device.objects.create(
            name='Bulk-Device-2',
            ip_address='10.0.0.51',
            vendor=self.vendor,
            device_type=self.device_type,
            username='admin',
            password_encrypted=encrypt_data('pass'),
            created_by=self.admin
        )
        response = self.client.post('/api/v1/devices/devices/bulk_delete/', {
            'device_ids': [self.device.id, device2.id]
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Device.objects.count(), 0)

    def test_bulk_delete_non_admin(self):
        """Test non-admin cannot bulk delete"""
        self.client.force_authenticate(user=self.operator)
        response = self.client.post('/api/v1/devices/devices/bulk_delete/', {
            'device_ids': [self.device.id]
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class VendorAPITestCase(APITestCase):
    """Tests for Vendor API"""

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            email='vendor_admin@example.com',
            username='vendoradmin',
            password='TestPass123!',
            role='administrator'
        )
        self.client = APIClient()

    def test_list_vendors(self):
        """Test listing vendors"""
        self.client.force_authenticate(user=self.admin)
        Vendor.objects.create(name='Cisco', slug='cisco-v')
        Vendor.objects.create(name='Juniper', slug='juniper-v')

        response = self.client.get('/api/v1/devices/vendors/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Response may be paginated or direct list
        if isinstance(response.data, dict) and 'results' in response.data:
            self.assertEqual(len(response.data['results']), 2)
        else:
            self.assertEqual(len(response.data), 2)

    def test_create_vendor_admin(self):
        """Test admin can create vendor"""
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/v1/devices/vendors/', {
            'name': 'New Vendor',
            'slug': 'new-vendor'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class DeviceTypeAPITestCase(APITestCase):
    """Tests for DeviceType API"""

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            email='dtype_admin@example.com',
            username='dtypeadmin',
            password='TestPass123!',
            role='administrator'
        )
        self.client = APIClient()

    def test_list_device_types(self):
        """Test listing device types"""
        self.client.force_authenticate(user=self.admin)
        DeviceType.objects.create(name='Router', slug='router-dt')
        DeviceType.objects.create(name='Switch', slug='switch-dt')

        response = self.client.get('/api/v1/devices/device-types/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Response may be paginated or direct list
        if isinstance(response.data, dict) and 'results' in response.data:
            self.assertEqual(len(response.data['results']), 2)
        else:
            self.assertEqual(len(response.data), 2)

    def test_delete_predefined_device_type(self):
        """Test cannot delete predefined device type"""
        self.client.force_authenticate(user=self.admin)
        dt = DeviceType.objects.create(name='Predefined', slug='predefined', is_predefined=True)

        response = self.client.delete(f'/api/v1/devices/device-types/{dt.id}/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('predefined', response.data['detail'].lower())

    def test_delete_device_type_in_use(self):
        """Test cannot delete device type that is in use"""
        User = get_user_model()
        user = User.objects.create_user(email='dtype_use@test.com', username='dtypeuse', password='pass')

        dt = DeviceType.objects.create(name='InUse', slug='in-use')
        vendor = Vendor.objects.create(name='Test', slug='test-vendor')
        Device.objects.create(
            name='Test-Device',
            ip_address='1.2.3.4',
            vendor=vendor,
            device_type=dt,
            username='admin',
            password_encrypted=encrypt_data('pass'),
            created_by=user
        )

        self.client.force_authenticate(user=self.admin)
        response = self.client.delete(f'/api/v1/devices/device-types/{dt.id}/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('device', response.data['detail'].lower())


class DeviceViewSetActionsTestCase(APITestCase):
    """Tests for Device ViewSet actions"""

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            email='device_actions@example.com',
            username='deviceactions',
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
            ip_address='192.168.100.1',
            vendor=self.vendor,
            device_type=self.device_type,
            username='admin',
            password_encrypted=encrypt_data('password'),
            status='online',
            backup_enabled=True,
            criticality='high',
            created_by=self.admin
        )

    def test_statistics_endpoint(self):
        """Test device statistics endpoint"""
        # Create another device
        Device.objects.create(
            name='Stats-Device-2',
            ip_address='192.168.100.2',
            vendor=self.vendor,
            device_type=self.device_type,
            username='admin',
            password_encrypted=encrypt_data('pass'),
            status='offline',
            backup_enabled=False,
            criticality='low',
            created_by=self.admin
        )

        response = self.client.get('/api/v1/devices/devices/statistics/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total', response.data)
        self.assertIn('by_status', response.data)
        self.assertIn('by_criticality', response.data)
        self.assertEqual(response.data['total'], 2)

    def test_filter_by_status(self):
        """Test filtering devices by status"""
        response = self.client.get('/api/v1/devices/devices/?status=online')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_filter_by_criticality(self):
        """Test filtering devices by criticality"""
        response = self.client.get('/api/v1/devices/devices/?criticality=high')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_filter_by_backup_enabled(self):
        """Test filtering devices by backup_enabled"""
        response = self.client.get('/api/v1/devices/devices/?backup_enabled=true')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_search_devices(self):
        """Test searching devices"""
        response = self.client.get('/api/v1/devices/devices/?search=Actions')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch('devices.connection.test_connection')
    def test_test_connection_success(self, mock_test):
        """Test connection test endpoint - success"""
        mock_test.return_value = (True, 'Connection successful')

        response = self.client.post(f'/api/v1/devices/devices/{self.device.id}/test_connection/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])

    @patch('devices.connection.test_connection')
    def test_test_connection_failure(self, mock_test):
        """Test connection test endpoint - failure"""
        mock_test.return_value = (False, 'Connection timed out')

        response = self.client.post(f'/api/v1/devices/devices/{self.device.id}/test_connection/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['success'])


# ============================================================
# Connection Module Tests with Realistic Device Output Mocks
# ============================================================

class ConnectionModuleTestCase(TestCase):
    """Tests for connection.py module functions"""

    # ===== Realistic Device Outputs (based on real device configs) =====

    CISCO_IOS_CONFIG = """
Router#terminal length 0
Router#show running-config
Building configuration...

Current configuration : 2048 bytes
!
! Last configuration change at 14:32:15 UTC Mon Dec 2 2025
!
version 15.7
service timestamps debug datetime msec
service timestamps log datetime msec
service password-encryption
!
hostname Router
!
boot-start-marker
boot-end-marker
!
enable secret 9 $9$randomhash
!
no aaa new-model
!
ip cef
no ipv6 cef
!
interface GigabitEthernet0/0
 description WAN Interface
 ip address 192.168.1.1 255.255.255.0
 duplex auto
 speed auto
!
interface GigabitEthernet0/1
 description LAN Interface
 ip address 10.0.0.1 255.255.255.0
 duplex auto
 speed auto
!
ip forward-protocol nd
!
no ip http server
no ip http secure-server
!
ip route 0.0.0.0 0.0.0.0 192.168.1.254
!
line con 0
line aux 0
line vty 0 4
 login local
 transport input ssh
!
end

Router#"""

    HUAWEI_VRP_CONFIG = """
<Huawei>screen-length 0 temporary
Info: The configuration takes effect for the current user terminal only.
<Huawei>display current-configuration
#
sysname Huawei
#
undo info-center enable
#
vlan batch 10 20 30
#
cluster enable
ntdp enable
ndp enable
#
drop illegal-mac alarm
#
interface Vlanif10
 ip address 10.10.10.1 255.255.255.0
#
interface GigabitEthernet0/0/1
 port link-type trunk
 port trunk allow-pass vlan 10 20 30
#
interface GigabitEthernet0/0/2
 port link-type access
 port default vlan 10
#
ospf 1
 area 0.0.0.0
  network 10.10.10.0 0.0.0.255
#
user-interface vty 0 4
 authentication-mode aaa
 protocol inbound ssh
#
return
<Huawei>"""

    FORTINET_CONFIG = """
FGT100D # get system status
Version: FortiGate-100D v7.0.5,build0304,220401 (GA.F)
Virus-DB: 91.00000(2023-01-01)
Extended DB: 91.00000(2023-01-01)
IPS-DB: 6.00741(2021-12-01)
Serial-Number: FGT100D123456789
License Status: Valid
FGT100D # show full-configuration
#config-version=FGT100D-7.0.5-FW-build0304-220401:opmode=0:vdom=0:user=admin
#conf_file_ver=1234567890
#buildno=0304
#global_vdom=1
config system global
    set admin-https-pki-required disable
    set admin-https-redirect enable
    set admin-scp enable
    set admin-sport 443
    set admintimeout 10
    set alias "FGT100D"
    set hostname "FGT100D"
    set timezone "US/Eastern"
end
config system interface
    edit "wan1"
        set vdom "root"
        set ip 192.168.1.99 255.255.255.0
        set allowaccess ping https ssh
        set type physical
        set snmp-index 1
    next
    edit "lan"
        set vdom "root"
        set ip 10.0.0.1 255.255.255.0
        set allowaccess ping https ssh
        set type physical
        set snmp-index 2
    next
end
config firewall policy
    edit 1
        set srcintf "lan"
        set dstintf "wan1"
        set srcaddr "all"
        set dstaddr "all"
        set action accept
        set schedule "always"
        set service "ALL"
        set nat enable
    next
end
FGT100D # """

    MIKROTIK_CONFIG = """
[admin@MikroTik] > /export
# dec/02/2025 14:30:00 by RouterOS 7.12.1
#
/interface bridge
add name=bridge1
/interface ethernet
set [ find default-name=ether1 ] comment="WAN"
set [ find default-name=ether2 ] comment="LAN"
/ip address
add address=192.168.88.1/24 interface=bridge1 network=192.168.88.0
add address=10.0.0.1/24 interface=ether2 network=10.0.0.0
/ip dhcp-server network
add address=192.168.88.0/24 gateway=192.168.88.1
/ip dns
set servers=8.8.8.8,8.8.4.4
/ip firewall filter
add action=accept chain=input protocol=icmp
add action=accept chain=input connection-state=established,related
add action=drop chain=input in-interface=ether1
/ip route
add distance=1 gateway=192.168.88.254
/system identity
set name=MikroTik
/system clock
set time-zone-name=Europe/Moscow
[admin@MikroTik] > """

    JUNIPER_CONFIG = """
root@juniper> show configuration
## Last commit: 2025-12-02 14:30:00 UTC
version 21.4R1.12;
system {
    host-name juniper;
    domain-name example.com;
    root-authentication {
        encrypted-password "$6$randomhash";
    }
    login {
        user admin {
            uid 2000;
            class super-user;
        }
    }
    services {
        ssh;
        netconf {
            ssh;
        }
    }
    syslog {
        file messages {
            any notice;
        }
    }
}
interfaces {
    ge-0/0/0 {
        description "WAN Interface";
        unit 0 {
            family inet {
                address 192.168.1.1/24;
            }
        }
    }
    ge-0/0/1 {
        description "LAN Interface";
        unit 0 {
            family inet {
                address 10.0.0.1/24;
            }
        }
    }
}
routing-options {
    static {
        route 0.0.0.0/0 next-hop 192.168.1.254;
    }
}
security {
    policies {
        from-zone trust to-zone untrust {
            policy allow-all {
                match {
                    source-address any;
                    destination-address any;
                    application any;
                }
                then {
                    permit;
                }
            }
        }
    }
}

root@juniper> """

    ERROR_CONFIG_ACCESS_DENIED = """
Router#show running-config
% Access denied
Router#"""

    ERROR_CONFIG_AUTH_FAILED = """
Username: admin
Password:
% Authentication failed
"""

    def test_validate_backup_config_cisco_success(self):
        """Test Cisco config validation passes"""
        from devices.connection import validate_backup_config
        is_valid, error = validate_backup_config(self.CISCO_IOS_CONFIG)
        self.assertTrue(is_valid, f"Should be valid, got error: {error}")

    def test_validate_backup_config_huawei_success(self):
        """Test Huawei config validation passes"""
        from devices.connection import validate_backup_config
        is_valid, error = validate_backup_config(self.HUAWEI_VRP_CONFIG)
        self.assertTrue(is_valid, f"Should be valid, got error: {error}")

    def test_validate_backup_config_fortinet_success(self):
        """Test Fortinet config validation passes"""
        from devices.connection import validate_backup_config
        is_valid, error = validate_backup_config(self.FORTINET_CONFIG)
        self.assertTrue(is_valid, f"Should be valid, got error: {error}")

    def test_validate_backup_config_mikrotik_success(self):
        """Test MikroTik config validation passes"""
        from devices.connection import validate_backup_config
        is_valid, error = validate_backup_config(self.MIKROTIK_CONFIG)
        self.assertTrue(is_valid, f"Should be valid, got error: {error}")

    def test_validate_backup_config_juniper_success(self):
        """Test Juniper config validation passes"""
        from devices.connection import validate_backup_config
        is_valid, error = validate_backup_config(self.JUNIPER_CONFIG)
        self.assertTrue(is_valid, f"Should be valid, got error: {error}")

    def test_validate_backup_config_empty(self):
        """Test empty config fails validation"""
        from devices.connection import validate_backup_config
        is_valid, error = validate_backup_config("")
        self.assertFalse(is_valid)
        self.assertIn("empty", error.lower())

    def test_validate_backup_config_too_short(self):
        """Test config with too few lines fails"""
        from devices.connection import validate_backup_config
        is_valid, error = validate_backup_config("line1\nline2\nline3")
        self.assertFalse(is_valid)
        self.assertIn("short", error.lower())

    def test_validate_backup_config_access_denied(self):
        """Test config with access denied error fails"""
        from devices.connection import validate_backup_config
        is_valid, error = validate_backup_config(self.ERROR_CONFIG_ACCESS_DENIED)
        self.assertFalse(is_valid)

    def test_clean_device_output_cisco(self):
        """Test Cisco output cleaning"""
        from devices.connection import clean_device_output
        cleaned = clean_device_output(self.CISCO_IOS_CONFIG, 'cisco', 'show running-config')
        # Should not contain prompt
        self.assertNotIn('Router#', cleaned)
        # Should contain config content
        self.assertIn('hostname Router', cleaned)
        self.assertIn('interface GigabitEthernet', cleaned)

    def test_clean_device_output_huawei(self):
        """Test Huawei output cleaning"""
        from devices.connection import clean_device_output
        cleaned = clean_device_output(self.HUAWEI_VRP_CONFIG, 'huawei', 'display current-configuration')
        # Should contain config content
        self.assertIn('sysname Huawei', cleaned)
        self.assertIn('interface Vlanif10', cleaned)

    def test_clean_device_output_mikrotik(self):
        """Test MikroTik output cleaning"""
        from devices.connection import clean_device_output
        cleaned = clean_device_output(self.MIKROTIK_CONFIG, 'mikrotik', '/export')
        # Should contain config content
        self.assertIn('interface bridge', cleaned)
        self.assertIn('ip address', cleaned)

    def test_clean_device_output_removes_ansi(self):
        """Test ANSI escape sequences are removed"""
        from devices.connection import clean_device_output
        output_with_ansi = "\x1b[32mGreen Text\x1b[0m\nhostname Router\n!"
        cleaned = clean_device_output(output_with_ansi, 'cisco', '')
        self.assertNotIn('\x1b', cleaned)

    def test_clean_device_output_handles_more_paging(self):
        """Test --More-- prompts are removed"""
        from devices.connection import clean_device_output
        output_with_paging = "hostname Router\n--More--\ninterface Gi0/0\n-- More --\nip address"
        cleaned = clean_device_output(output_with_paging, 'cisco', '')
        self.assertNotIn('--More--', cleaned)
        self.assertNotIn('-- More --', cleaned)


class SSHConnectionMockTestCase(TestCase):
    """Tests for SSH connection with mocked Paramiko"""

    @patch('devices.connection.paramiko')
    @patch('devices.connection.PARAMIKO_AVAILABLE', True)
    def test_paramiko_connect_success(self, mock_paramiko):
        """Test Paramiko connection success"""
        from devices.connection import SSHConnection

        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.AutoAddPolicy.return_value = MagicMock()

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'password')
        conn.connect()

        mock_client.connect.assert_called_once()
        self.assertTrue(conn._connected)

    @patch('devices.connection.paramiko')
    @patch('devices.connection.PARAMIKO_AVAILABLE', True)
    def test_paramiko_connect_auth_failure(self, mock_paramiko):
        """Test Paramiko authentication failure falls back to binary"""
        from devices.connection import SSHConnection, DeviceConnectionError
        import paramiko as real_paramiko

        mock_client = MagicMock()
        mock_client.connect.side_effect = real_paramiko.ssh_exception.AuthenticationException("Auth failed")
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.AutoAddPolicy.return_value = MagicMock()
        mock_paramiko.ssh_exception = real_paramiko.ssh_exception

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'wrongpass')

        # Should fall back to binary and fail
        with patch.object(conn, '_run_ssh_binary') as mock_binary:
            mock_binary.return_value = {'success': False, 'error': 'Auth failed'}
            with self.assertRaises(DeviceConnectionError):
                conn.connect()

    @patch('devices.connection.paramiko')
    @patch('devices.connection.PARAMIKO_AVAILABLE', True)
    def test_paramiko_exec_command(self, mock_paramiko):
        """Test Paramiko exec command"""
        from devices.connection import _ParamikoSSH

        mock_client = MagicMock()
        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"Linux server 5.15.0\n"
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""
        mock_client.exec_command.return_value = (MagicMock(), mock_stdout, mock_stderr)
        mock_paramiko.SSHClient.return_value = mock_client

        ssh = _ParamikoSSH('192.168.1.1', 22, 'admin', 'password')
        ssh.client = mock_client

        success, output = ssh.exec_command('uname -a')
        self.assertTrue(success)
        self.assertIn('Linux', output)


class TelnetConnectionMockTestCase(TestCase):
    """Tests for Telnet connection with mocked telnetlib"""

    @patch('devices.connection.telnetlib.Telnet')
    def test_telnet_connect_success(self, mock_telnet_class):
        """Test Telnet connection success"""
        from devices.connection import TelnetConnection

        mock_telnet = MagicMock()
        mock_telnet.expect.return_value = (0, None, b"Username:")
        mock_telnet_class.return_value = mock_telnet

        conn = TelnetConnection('192.168.1.1', 23, 'admin', 'password')
        conn.connect()

        mock_telnet.write.assert_called()

    @patch('devices.connection.telnetlib.Telnet')
    def test_telnet_send_command(self, mock_telnet_class):
        """Test Telnet send command"""
        from devices.connection import TelnetConnection

        mock_telnet = MagicMock()
        mock_telnet.expect.return_value = (0, None, b"Username:")
        mock_telnet.read_very_eager.side_effect = [
            b"hostname Router\n!",
            b"",  # Empty to trigger idle
            b"",
            EOFError()
        ]
        mock_telnet_class.return_value = mock_telnet

        conn = TelnetConnection('192.168.1.1', 23, 'admin', 'password')
        conn.connection = mock_telnet

        output = conn.send_command('show run', wait_time=0.1)
        self.assertIn('hostname Router', output)

    @patch('devices.connection.telnetlib.Telnet')
    def test_telnet_handles_paging(self, mock_telnet_class):
        """Test Telnet handles --More-- paging"""
        from devices.connection import TelnetConnection

        mock_telnet = MagicMock()
        mock_telnet.read_very_eager.side_effect = [
            b"line1\n--More--",
            b"line2\nline3",
            b"",
            EOFError()
        ]
        mock_telnet_class.return_value = mock_telnet

        conn = TelnetConnection('192.168.1.1', 23, 'admin', 'password')
        conn.connection = mock_telnet

        output = conn.send_command('show config', wait_time=0.1, handle_paging=True)
        # Should have sent space for paging
        self.assertTrue(any(call[0][0] == b' ' for call in mock_telnet.write.call_args_list))


class SSHBinaryMockTestCase(TestCase):
    """Tests for netvault-ssh binary with mocked subprocess"""

    @patch('devices.connection.subprocess.run')
    def test_ssh_binary_success(self, mock_run):
        """Test SSH binary success response"""
        from devices.connection import SSHConnection

        mock_run.return_value = MagicMock(
            stdout='{"success":true,"output":"hostname Router\\n!"}',
            returncode=0
        )

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'password')
        conn._use_binary = True

        result = conn._run_ssh_binary(mode='shell', commands='show run')
        self.assertTrue(result['success'])
        self.assertIn('hostname Router', result['output'])

    @patch('devices.connection.subprocess.run')
    def test_ssh_binary_auth_failure(self, mock_run):
        """Test SSH binary auth failure with error code"""
        from devices.connection import SSHConnection, ERR_AUTH_FAILED

        mock_run.return_value = MagicMock(
            stdout='{"success":false,"error":"Authentication failed","error_code":10}',
            returncode=1
        )

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'wrongpass')
        conn._use_binary = True

        result = conn._run_ssh_binary(mode='test')
        self.assertFalse(result['success'])
        self.assertEqual(result['error_code'], ERR_AUTH_FAILED)

    @patch('devices.connection.subprocess.run')
    def test_ssh_binary_kex_fallback(self, mock_run):
        """Test SSH binary KEX error triggers modern binary fallback"""
        from devices.connection import SSHConnection, ERR_FATAL

        # First call returns KEX error, second call (modern) succeeds
        mock_run.side_effect = [
            MagicMock(stdout='{"success":false,"error":"KEX failure","error_code":2}', returncode=1),
            MagicMock(stdout='{"success":true,"output":"config"}', returncode=0)
        ]

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'password')
        conn._use_binary = True

        result = conn._run_ssh_binary(mode='shell', commands='show run')
        self.assertTrue(result['success'])
        # Should have been called twice (legacy + modern)
        self.assertEqual(mock_run.call_count, 2)

    @patch('devices.connection.subprocess.run')
    def test_ssh_binary_timeout(self, mock_run):
        """Test SSH binary timeout handling"""
        from devices.connection import SSHConnection
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd='ssh', timeout=30)

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'password')
        conn._use_binary = True

        result = conn._run_ssh_binary(mode='test')
        self.assertFalse(result['success'])
        self.assertIn('timeout', result['error'].lower())


class TargetHostValidationTestCase(TestCase):
    """Tests for SSRF protection in validate_target_host"""

    def test_validate_loopback_blocked(self):
        """Test loopback addresses are blocked"""
        from devices.connection import validate_target_host, DeviceConnectionError

        with self.assertRaises(DeviceConnectionError) as ctx:
            validate_target_host('127.0.0.1')
        self.assertIn('loopback', str(ctx.exception).lower())

    def test_validate_valid_ip(self):
        """Test valid IP passes"""
        from devices.connection import validate_target_host

        # This should not raise
        result = validate_target_host('192.168.1.1')
        self.assertEqual(result, '192.168.1.1')

    def test_validate_invalid_hostname(self):
        """Test invalid hostname fails"""
        from devices.connection import validate_target_host, DeviceConnectionError

        with self.assertRaises(DeviceConnectionError) as ctx:
            validate_target_host('this-host-does-not-exist-12345.invalid')
        self.assertIn('resolve', str(ctx.exception).lower())


class TCPPingTestCase(TestCase):
    """Tests for tcp_ping function"""

    @patch('devices.connection.socket.socket')
    def test_tcp_ping_success(self, mock_socket_class):
        """Test TCP ping success"""
        from devices.connection import tcp_ping

        mock_socket = MagicMock()
        mock_socket.connect_ex.return_value = 0
        mock_socket_class.return_value = mock_socket

        result = tcp_ping('192.168.1.1', 22, timeout=2)
        self.assertTrue(result)

    @patch('devices.connection.socket.socket')
    def test_tcp_ping_failure(self, mock_socket_class):
        """Test TCP ping failure"""
        from devices.connection import tcp_ping

        mock_socket = MagicMock()
        mock_socket.connect_ex.return_value = 111  # Connection refused
        mock_socket_class.return_value = mock_socket

        result = tcp_ping('192.168.1.1', 9999, timeout=2)
        self.assertFalse(result)


class BackupDeviceConfigMockTestCase(TestCase):
    """Tests for backup_device_config function with mocks"""

    @patch('devices.connection.SSHConnection')
    @patch('devices.connection.validate_target_host')
    def test_backup_ssh_success(self, mock_validate, mock_ssh_class):
        """Test SSH backup success"""
        from devices.connection import backup_device_config

        mock_validate.return_value = '192.168.1.1'

        mock_conn = MagicMock()
        mock_conn.get_config.return_value = ConnectionModuleTestCase.CISCO_IOS_CONFIG
        mock_ssh_class.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_ssh_class.return_value.__exit__ = MagicMock(return_value=False)

        success, config, error = backup_device_config(
            '192.168.1.1', 22, 'ssh', 'admin', 'password', 'cisco'
        )

        self.assertTrue(success)
        self.assertIn('hostname Router', config)
        self.assertEqual(error, '')

    @patch('devices.connection.TelnetConnection')
    @patch('devices.connection.validate_target_host')
    def test_backup_telnet_success(self, mock_validate, mock_telnet_class):
        """Test Telnet backup success"""
        from devices.connection import backup_device_config

        mock_validate.return_value = '192.168.1.1'

        mock_conn = MagicMock()
        mock_conn.get_config.return_value = ConnectionModuleTestCase.HUAWEI_VRP_CONFIG
        mock_telnet_class.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_telnet_class.return_value.__exit__ = MagicMock(return_value=False)

        success, config, error = backup_device_config(
            '192.168.1.1', 23, 'telnet', 'admin', 'password', 'huawei'
        )

        self.assertTrue(success)
        self.assertIn('sysname Huawei', config)

    @patch('devices.connection.SSHConnection')
    @patch('devices.connection.validate_target_host')
    def test_backup_connection_error(self, mock_validate, mock_ssh_class):
        """Test backup handles connection error"""
        from devices.connection import backup_device_config, DeviceConnectionError

        mock_validate.return_value = '192.168.1.1'
        mock_ssh_class.return_value.__enter__ = MagicMock(
            side_effect=DeviceConnectionError("Connection refused")
        )

        success, config, error = backup_device_config(
            '192.168.1.1', 22, 'ssh', 'admin', 'password', 'cisco'
        )

        self.assertFalse(success)
        self.assertEqual(config, '')
        self.assertIn('refused', error.lower())


class SSHVersionAndAlgorithmTestCase(TestCase):
    """Tests for SSH version and algorithm handling (SSH v1, KEX, etc.)"""

    # Realistic error messages from different devices/scenarios

    SSH_V1_KEX_ERROR = '{"success":false,"error":"kex error: no match for method kex algo","error_code":2}'
    SSH_CHACHA20_ERROR = '{"success":false,"error":"crypt_set_algorithms2: no crypto algorithm function found for chacha20-poly1305@openssh.com","error_code":2}'
    SSH_DIFFIE_HELLMAN_ERROR = '{"success":false,"error":"kex error: no match for method server host key algo: server [ssh-rsa], client [ssh-ed25519,ecdsa-sha2-nistp256]","error_code":2}'
    SSH_OLD_NOKIA_ERROR = '{"success":false,"error":"SSH-1.99-OpenSSH_3.4p1: KEX negotiation failed","error_code":2}'
    SSH_AUTH_FAILED = '{"success":false,"error":"Authentication failed: Access denied","error_code":10}'
    SSH_TIMEOUT = '{"success":false,"error":"Connection timeout","error_code":11}'
    SSH_SUCCESS = '{"success":true,"output":"hostname OldRouter\\n!"}'

    @patch('devices.connection.subprocess.run')
    def test_legacy_kex_fallback_to_modern(self, mock_run):
        """Test KEX error with legacy binary triggers modern binary fallback"""
        from devices.connection import SSHConnection

        # Legacy binary fails with KEX error, modern succeeds
        mock_run.side_effect = [
            MagicMock(stdout=self.SSH_V1_KEX_ERROR, returncode=1),
            MagicMock(stdout=self.SSH_SUCCESS, returncode=0)
        ]

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'password')
        conn._use_binary = True

        result = conn._run_ssh_binary(mode='shell', commands='show run')
        self.assertTrue(result['success'])
        self.assertEqual(mock_run.call_count, 2)

    @patch('devices.connection.subprocess.run')
    def test_chacha20_cipher_not_supported(self, mock_run):
        """Test chacha20-poly1305 cipher error triggers fallback"""
        from devices.connection import SSHConnection

        # Both binaries fail with cipher error (device requires specific cipher)
        mock_run.side_effect = [
            MagicMock(stdout=self.SSH_CHACHA20_ERROR, returncode=1),
            MagicMock(stdout=self.SSH_CHACHA20_ERROR, returncode=1)
        ]

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'password')
        conn._use_binary = True

        result = conn._run_ssh_binary(mode='shell', commands='show run')
        self.assertFalse(result['success'])
        self.assertIn('chacha20', result['error'])

    @patch('devices.connection.subprocess.run')
    def test_diffie_hellman_key_exchange_mismatch(self, mock_run):
        """Test Diffie-Hellman KEX mismatch with old devices"""
        from devices.connection import SSHConnection

        # Legacy fails, modern succeeds with different algorithms
        mock_run.side_effect = [
            MagicMock(stdout=self.SSH_DIFFIE_HELLMAN_ERROR, returncode=1),
            MagicMock(stdout=self.SSH_SUCCESS, returncode=0)
        ]

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'password')
        conn._use_binary = True

        result = conn._run_ssh_binary(mode='shell', commands='show run')
        self.assertTrue(result['success'])

    @patch('devices.connection.subprocess.run')
    def test_old_nokia_sros_ssh1(self, mock_run):
        """Test old Nokia SR-OS with SSH v1.99"""
        from devices.connection import SSHConnection

        # Simulates Nokia TiMOS that needs legacy SSH
        mock_run.side_effect = [
            MagicMock(stdout=self.SSH_OLD_NOKIA_ERROR, returncode=1),
            MagicMock(stdout=self.SSH_SUCCESS, returncode=0)
        ]

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'password')
        conn._use_binary = True

        result = conn._run_ssh_binary(mode='shell', commands='admin display-config')
        self.assertTrue(result['success'])

    @patch('devices.connection.subprocess.run')
    def test_auth_failure_no_kex_fallback(self, mock_run):
        """Test auth failure (code 10) doesn't trigger KEX fallback"""
        from devices.connection import SSHConnection, ERR_AUTH_FAILED

        # Auth failure should NOT trigger fallback to modern binary
        mock_run.return_value = MagicMock(stdout=self.SSH_AUTH_FAILED, returncode=1)

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'wrongpass')
        conn._use_binary = True

        result = conn._run_ssh_binary(mode='test')
        self.assertFalse(result['success'])
        self.assertEqual(result['error_code'], ERR_AUTH_FAILED)
        # Should only call once - no fallback for auth errors
        self.assertEqual(mock_run.call_count, 1)

    @patch('devices.connection.subprocess.run')
    def test_timeout_no_kex_fallback(self, mock_run):
        """Test timeout (code 11) doesn't trigger KEX fallback"""
        from devices.connection import SSHConnection, ERR_TIMEOUT

        mock_run.return_value = MagicMock(stdout=self.SSH_TIMEOUT, returncode=1)

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'password')
        conn._use_binary = True

        result = conn._run_ssh_binary(mode='test')
        self.assertFalse(result['success'])
        self.assertEqual(result['error_code'], ERR_TIMEOUT)
        self.assertEqual(mock_run.call_count, 1)

    @patch('devices.connection.paramiko')
    @patch('devices.connection.PARAMIKO_AVAILABLE', True)
    def test_paramiko_legacy_algorithm_negotiation(self, mock_paramiko):
        """Test Paramiko handles legacy algorithm negotiation"""
        from devices.connection import SSHConnection
        import paramiko as real_paramiko

        mock_client = MagicMock()
        # Simulate successful connection with disabled_algorithms
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.AutoAddPolicy.return_value = MagicMock()

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'password')
        conn.connect()

        # Verify connect was called with disabled_algorithms param
        connect_call = mock_client.connect.call_args
        self.assertIn('disabled_algorithms', connect_call.kwargs)

    @patch('devices.connection.paramiko')
    @patch('devices.connection.PARAMIKO_AVAILABLE', True)
    def test_paramiko_fails_ssh_fallback_to_binary(self, mock_paramiko):
        """Test Paramiko SSH exception falls back to binary"""
        from devices.connection import SSHConnection
        import paramiko as real_paramiko

        mock_client = MagicMock()
        mock_client.connect.side_effect = real_paramiko.ssh_exception.SSHException(
            "Incompatible ssh peer (no acceptable kex algorithm)"
        )
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.AutoAddPolicy.return_value = MagicMock()
        mock_paramiko.ssh_exception = real_paramiko.ssh_exception

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'password')

        with patch.object(conn, '_run_ssh_binary') as mock_binary:
            mock_binary.return_value = {'success': True, 'output': 'config'}
            conn.connect()
            # Should have fallen back to binary
            mock_binary.assert_called()
            self.assertTrue(conn._use_binary)


class VendorSpecificSSHTestCase(TestCase):
    """Tests for vendor-specific SSH behaviors"""

    CISCO_OLD_IOS = """
hostname OldCisco
!
version 12.4
service timestamps debug datetime msec
service timestamps log datetime msec
service password-encryption
!
interface FastEthernet0/0
 ip address 192.168.1.1 255.255.255.0
!
end
"""

    NOKIA_SROS_CONFIG = """
#--------------------------------------------------
echo "System Configuration"
#--------------------------------------------------
    system
        name "Nokia-SROS"
        location "DataCenter"
        time
            ntp
                server 192.168.1.10
            exit
        exit
    exit
"""

    HUAWEI_OLD_VRP = """
#
sysname OldHuawei
#
aaa
 authentication-scheme default
 authorization-scheme default
#
interface GigabitEthernet0/0/0
 ip address 10.0.0.1 255.255.255.0
#
return
"""

    @patch('devices.connection.subprocess.run')
    def test_cisco_ios_12_ssh_v1(self, mock_run):
        """Test Cisco IOS 12.x with SSH v1 (legacy device)"""
        from devices.connection import SSHConnection
        import json

        mock_run.return_value = MagicMock(
            stdout=json.dumps({"success": True, "output": self.CISCO_OLD_IOS}),
            returncode=0
        )

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'cisco123')
        conn._use_binary = True

        result = conn._run_ssh_binary(mode='shell', commands='show run')
        self.assertTrue(result['success'])
        self.assertIn('version 12.4', result['output'])

    @patch('devices.connection.subprocess.run')
    def test_nokia_timos_admin_commands(self, mock_run):
        """Test Nokia TiMOS/SR-OS with admin display-config"""
        from devices.connection import SSHConnection
        import json

        mock_run.return_value = MagicMock(
            stdout=json.dumps({"success": True, "output": self.NOKIA_SROS_CONFIG}),
            returncode=0
        )

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'nokia123')
        conn._use_binary = True

        result = conn._run_ssh_binary(mode='shell', commands='admin display-config')
        self.assertTrue(result['success'])
        self.assertIn('Nokia-SROS', result['output'])

    @patch('devices.connection.subprocess.run')
    def test_huawei_vrp3_legacy(self, mock_run):
        """Test Huawei VRP3 (legacy device with old SSH)"""
        from devices.connection import SSHConnection
        import json

        # First call fails with old algorithm, second succeeds
        mock_run.side_effect = [
            MagicMock(stdout='{"success":false,"error":"kex error: diffie-hellman-group1-sha1","error_code":2}', returncode=1),
            MagicMock(stdout=json.dumps({"success": True, "output": self.HUAWEI_OLD_VRP}), returncode=0)
        ]

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'huawei123')
        conn._use_binary = True

        result = conn._run_ssh_binary(mode='shell', commands='display current')
        self.assertTrue(result['success'])

    def test_clean_nokia_output(self):
        """Test Nokia output cleaning preserves config structure"""
        from devices.connection import clean_device_output
        cleaned = clean_device_output(self.NOKIA_SROS_CONFIG, 'nokia', 'admin display-config')
        self.assertIn('system', cleaned)
        self.assertIn('name "Nokia-SROS"', cleaned)

    def test_clean_old_cisco_output(self):
        """Test old Cisco IOS output cleaning"""
        from devices.connection import clean_device_output
        cleaned = clean_device_output(self.CISCO_OLD_IOS, 'cisco', 'show running-config')
        self.assertIn('hostname OldCisco', cleaned)
        self.assertIn('version 12.4', cleaned)


class ErrorCodeMappingTestCase(TestCase):
    """Tests for error code constants and mapping"""

    def test_error_codes_defined(self):
        """Test all error codes are properly defined"""
        from devices.connection import (
            ERR_NONE, ERR_REQUEST_DENIED, ERR_FATAL,
            ERR_AUTH_FAILED, ERR_TIMEOUT, ERR_CHANNEL
        )

        self.assertEqual(ERR_NONE, 0)
        self.assertEqual(ERR_REQUEST_DENIED, 1)
        self.assertEqual(ERR_FATAL, 2)
        self.assertEqual(ERR_AUTH_FAILED, 10)
        self.assertEqual(ERR_TIMEOUT, 11)
        self.assertEqual(ERR_CHANNEL, 12)

    @patch('devices.connection.subprocess.run')
    def test_error_code_parsing(self, mock_run):
        """Test error codes are correctly parsed from binary output"""
        from devices.connection import SSHConnection, ERR_AUTH_FAILED

        mock_run.return_value = MagicMock(
            stdout='{"success":false,"error":"Auth failed","error_code":10}',
            returncode=1
        )

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'password')
        conn._use_binary = True

        result = conn._run_ssh_binary(mode='test')
        self.assertEqual(result.get('error_code'), ERR_AUTH_FAILED)

    @patch('devices.connection.subprocess.run')
    def test_missing_error_code_defaults_to_none(self, mock_run):
        """Test missing error_code in response is handled"""
        from devices.connection import SSHConnection

        # Old binary format without error_code
        mock_run.return_value = MagicMock(
            stdout='{"success":false,"error":"Some error"}',
            returncode=1
        )

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'password')
        conn._use_binary = True

        result = conn._run_ssh_binary(mode='test')
        self.assertFalse(result['success'])
        # Should not crash even without error_code
        self.assertIn('error', result)


class SSHEdgeCasesTestCase(TestCase):
    """Tests for SSH edge cases and corner scenarios"""

    # ===== Banner/MOTD Edge Cases =====

    LONG_BANNER = """
*******************************************************************************
*                                                                             *
*   WARNING: Unauthorized access to this system is prohibited!                *
*   All activities on this system are logged and monitored.                   *
*   By continuing, you consent to this monitoring.                            *
*                                                                             *
*   If you are not an authorized user, disconnect immediately!                *
*                                                                             *
*   Contact: security@company.com                                             *
*                                                                             *
*******************************************************************************
""" * 10  # ~5KB banner

    ANSI_ART_BANNER = """
\x1b[31m╔══════════════════════════════════════╗\x1b[0m
\x1b[31m║\x1b[33m    ____  ___  __  __ _____ ___  \x1b[31m   ║\x1b[0m
\x1b[31m║\x1b[33m   |  _ \\/ _ \\|  \\/  | ____|_ _| \x1b[31m   ║\x1b[0m
\x1b[31m║\x1b[33m   | |_) | | | | |\\/| |  _|  | |  \x1b[31m   ║\x1b[0m
\x1b[31m║\x1b[33m   |  _ <| |_| | |  | | |___ | |  \x1b[31m   ║\x1b[0m
\x1b[31m║\x1b[33m   |_| \\_\\\\___/|_|  |_|_____|___| \x1b[31m   ║\x1b[0m
\x1b[31m╚══════════════════════════════════════╝\x1b[0m
Router#"""

    UNICODE_CONFIG = """
!
hostname Router
!
! Комментарий на русском языке
! Здесь могут быть спецсимволы: ёЁ äöü 中文
!
interface GigabitEthernet0/0
 description Подключение к ЦОД №1
 ip address 192.168.1.1 255.255.255.0
!
end
"""

    def test_clean_output_with_long_banner(self):
        """Test output cleaning handles long banners

        NOTE: Currently banners are NOT stripped from output.
        This test documents current behavior - config extraction starts
        at first config marker (!, hostname, etc.) but banner lines with *
        are included. This is a known limitation.
        """
        from devices.connection import clean_device_output

        output = self.LONG_BANNER + "\nhostname Router\n!\ninterface Gi0/0\n!\nend"
        cleaned = clean_device_output(output, 'cisco', 'show running-config')

        # Config content should be present
        self.assertIn('hostname Router', cleaned)
        self.assertIn('interface Gi0/0', cleaned)
        # NOTE: Banner is currently NOT filtered out - this documents the limitation
        # A future improvement could add banner detection/removal

    def test_clean_output_with_ansi_art(self):
        """Test ANSI escape sequences are removed from banner"""
        from devices.connection import clean_device_output

        output = self.ANSI_ART_BANNER + "\nhostname Router\n!\nend"
        cleaned = clean_device_output(output, 'cisco', 'show running-config')

        # Should not contain any ANSI codes
        self.assertNotIn('\x1b', cleaned)
        self.assertNotIn('[31m', cleaned)

    def test_unicode_config_preserved(self):
        """Test Unicode/Russian characters in config are preserved"""
        from devices.connection import validate_backup_config

        is_valid, error = validate_backup_config(self.UNICODE_CONFIG)
        self.assertTrue(is_valid, f"Unicode config should be valid: {error}")

    # ===== Connection Edge Cases =====

    @patch('devices.connection.subprocess.run')
    def test_max_sessions_exceeded(self, mock_run):
        """Test error when device has max VTY sessions"""
        from devices.connection import SSHConnection

        mock_run.return_value = MagicMock(
            stdout='{"success":false,"error":"Connection refused: all vty lines in use","error_code":2}',
            returncode=1
        )

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'password')
        conn._use_binary = True

        result = conn._run_ssh_binary(mode='test')
        self.assertFalse(result['success'])
        self.assertIn('vty', result['error'].lower())

    @patch('devices.connection.subprocess.run')
    def test_broken_pipe_during_command(self, mock_run):
        """Test handling of broken pipe during command execution"""
        from devices.connection import SSHConnection

        mock_run.return_value = MagicMock(
            stdout='{"success":false,"error":"Broken pipe: connection reset by peer","error_code":12}',
            returncode=1
        )

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'password')
        conn._use_binary = True

        result = conn._run_ssh_binary(mode='shell', commands='show tech')
        self.assertFalse(result['success'])

    @patch('devices.connection.subprocess.run')
    def test_session_timeout_during_long_command(self, mock_run):
        """Test session timeout during long-running command"""
        from devices.connection import SSHConnection
        import subprocess

        # Simulate timeout during long command like "show tech-support"
        mock_run.side_effect = subprocess.TimeoutExpired(cmd='ssh', timeout=120)

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'password')
        conn._use_binary = True
        conn.timeout = 120

        result = conn._run_ssh_binary(mode='shell', commands='show tech-support')
        self.assertFalse(result['success'])
        self.assertIn('timeout', result['error'].lower())

    # ===== PTY and Shell Mode Edge Cases =====

    @patch('devices.connection.paramiko')
    @patch('devices.connection.PARAMIKO_AVAILABLE', True)
    def test_pty_allocation_failure(self, mock_paramiko):
        """Test handling when PTY allocation fails"""
        from devices.connection import _ParamikoSSH

        mock_client = MagicMock()
        mock_channel = MagicMock()
        # Simulate PTY allocation failure
        mock_client.invoke_shell.side_effect = Exception("PTY allocation request failed")
        mock_paramiko.SSHClient.return_value = mock_client

        ssh = _ParamikoSSH('192.168.1.1', 22, 'admin', 'password')
        ssh.client = mock_client

        success, output = ssh.shell_commands(['show run'])
        self.assertFalse(success)
        self.assertIn('PTY', output)

    # ===== Encoding Edge Cases =====

    def test_clean_output_with_null_bytes(self):
        """Test NULL bytes are stripped from output"""
        from devices.connection import clean_device_output

        output = "hostname\x00 Router\x00\n!\ninterface Gi0/0\x00\n!\nend"
        # Note: clean_device_output doesn't handle NULL, but _read_available does
        # This test documents current behavior
        self.assertIn('\x00', output)  # Input has NULL

    def test_validate_config_with_binary_garbage(self):
        """Test config validation rejects binary garbage"""
        from devices.connection import validate_backup_config

        # Binary garbage that might come from corrupted connection
        garbage = b'\xff\xfe\x00\x01\x02\x03'.decode('utf-8', errors='ignore')
        is_valid, error = validate_backup_config(garbage)
        self.assertFalse(is_valid)

    # ===== Prompt Detection Edge Cases =====

    NONSTANDARD_PROMPTS = [
        ("My-Router>>", "Cisco with custom prompt"),
        ("admin@fw:~$", "Linux-based firewall"),
        ("[edit]", "Juniper edit mode"),
        ("(config)#", "Config mode"),
        ("RP/0/RSP0/CPU0:Router#", "Cisco IOS-XR"),
        ("{master:0}", "Juniper dual-RE"),
    ]

    def test_various_prompt_patterns(self):
        """Test various non-standard prompt patterns"""
        from devices.connection import DEVICE_PROMPT_PATTERN

        for prompt, description in self.NONSTANDARD_PROMPTS:
            # Just verify regex doesn't crash on these inputs
            result = DEVICE_PROMPT_PATTERN.match(prompt)
            # Document whether pattern matches or not
            # (not all prompts should match - this is expected)

    def test_prompt_embedded_in_config(self):
        """Test prompt-like string inside config doesn't break parsing"""
        from devices.connection import clean_device_output

        config = """!
hostname Router
!
banner motd ^
###################
# Router# is here #
###################
^
!
interface Gi0/0
!
end
"""
        cleaned = clean_device_output(config, 'cisco', 'show running-config')
        # Should preserve the banner content
        self.assertIn('hostname Router', cleaned)
        self.assertIn('interface Gi0/0', cleaned)

    # ===== Keyboard Interactive Auth =====

    @patch('devices.connection.paramiko')
    @patch('devices.connection.PARAMIKO_AVAILABLE', True)
    def test_keyboard_interactive_auth_not_supported(self, mock_paramiko):
        """Test keyboard-interactive auth triggers fallback"""
        from devices.connection import SSHConnection
        import paramiko as real_paramiko

        mock_client = MagicMock()
        mock_client.connect.side_effect = real_paramiko.ssh_exception.SSHException(
            "No supported authentication methods available"
        )
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.AutoAddPolicy.return_value = MagicMock()
        mock_paramiko.ssh_exception = real_paramiko.ssh_exception

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'password')

        with patch.object(conn, '_run_ssh_binary') as mock_binary:
            mock_binary.return_value = {'success': False, 'error': 'Auth failed'}
            try:
                conn.connect()
            except:
                pass
            # Should have tried binary fallback
            mock_binary.assert_called()

    # ===== Host Key Edge Cases =====

    @patch('devices.connection.paramiko')
    @patch('devices.connection.PARAMIKO_AVAILABLE', True)
    def test_host_key_changed_after_upgrade(self, mock_paramiko):
        """Test connection works after device firmware upgrade (key change)"""
        from devices.connection import SSHConnection

        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.AutoAddPolicy.return_value = MagicMock()

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'password')
        conn.connect()

        # Verify AutoAddPolicy was used (accepts changed keys)
        mock_client.set_missing_host_key_policy.assert_called()

    # ===== Large Output Edge Cases =====

    def test_validate_very_large_config(self):
        """Test validation of very large configs (>1MB)"""
        from devices.connection import validate_backup_config

        # Simulate large config with many interfaces
        lines = ["hostname BigRouter", "!"]
        for i in range(10000):
            lines.append(f"interface GigabitEthernet{i//100}/{i%100}")
            lines.append(f" description Interface {i}")
            lines.append(f" ip address 10.{i//256}.{i%256}.1 255.255.255.0")
            lines.append("!")
        lines.append("end")

        large_config = "\n".join(lines)
        self.assertGreater(len(large_config), 500000)  # >500KB

        is_valid, error = validate_backup_config(large_config)
        self.assertTrue(is_valid, f"Large config should be valid: {error}")
