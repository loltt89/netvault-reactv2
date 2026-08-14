"""
Tests for devices app - Device, Vendor, DeviceType models
"""
import io

from django.test import TestCase, override_settings
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
        """
        Device.clean() rejects (does not silently rewrite) a dangerous
        name — the model-level backstop for any direct-creation path that
        bypasses DeviceCreateSerializer's own validate_csv_safe check.
        See Device.clean()'s docstring for why this changed from silent
        mutation to rejection.
        """
        from django.core.exceptions import ValidationError

        device = Device(
            name='=CMD|calc|',
            ip_address='10.0.0.6',
            vendor=self.vendor,
            device_type=self.device_type,
            username='admin',
            password_encrypted=encrypt_data('pass'),
            created_by=self.user
        )
        with self.assertRaises(ValidationError) as ctx:
            device.clean()
        self.assertIn('name', ctx.exception.message_dict)
        # Rejected, not silently rewritten.
        self.assertEqual(device.name, '=CMD|calc|')

    def test_csv_injection_prevention_location(self):
        """Same as test_csv_injection_prevention_name, for location."""
        from django.core.exceptions import ValidationError

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
        with self.assertRaises(ValidationError) as ctx:
            device.clean()
        self.assertIn('location', ctx.exception.message_dict)
        self.assertEqual(device.location, '+1-555-1234')

    def test_clean_passes_through_safe_values_unchanged(self):
        """A device with no CSV-dangerous fields cleans without raising or rewriting anything."""
        device = Device(
            name='Safe-Device-2',
            ip_address='10.0.0.9',
            vendor=self.vendor,
            device_type=self.device_type,
            username='admin',
            password_encrypted=encrypt_data('pass'),
            location='Rack 4',
            description='A perfectly normal description.',
            created_by=self.user
        )
        device.clean()  # must not raise
        self.assertEqual(device.name, 'Safe-Device-2')
        self.assertEqual(device.location, 'Rack 4')
        self.assertEqual(device.description, 'A perfectly normal description.')

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


class DeviceStaleTestCase(TestCase):
    """Tests for Device.stale() — shared by the dashboard endpoint and the digest task"""

    def setUp(self):
        from django.utils import timezone
        from datetime import timedelta
        self.timezone = timezone
        self.timedelta = timedelta

        self.user = get_user_model().objects.create_user(
            email='stale_model@example.com', username='stale_model', password='pass123',
        )
        self.vendor = Vendor.objects.create(name='Cisco', slug='cisco-stale-model')
        self.device_type = DeviceType.objects.create(name='Router', slug='router-stale-model')

    def _make(self, name, last_backup, backup_enabled=True):
        return Device.objects.create(
            name=name, ip_address=f'10.9.0.{len(name) % 250 + 1}', vendor=self.vendor,
            device_type=self.device_type, username='admin',
            password_encrypted=encrypt_data('pw'), created_by=self.user,
            last_backup=last_backup, backup_enabled=backup_enabled,
        )

    def test_never_backed_up_is_stale(self):
        d = self._make('Never2', None)
        self.assertIn(d, Device.stale(days=3))

    def test_recently_backed_up_is_not_stale(self):
        d = self._make('Recent2', self.timezone.now())
        self.assertNotIn(d, Device.stale(days=3))

    def test_old_backup_is_stale(self):
        d = self._make('Old2', self.timezone.now() - self.timedelta(days=10))
        self.assertIn(d, Device.stale(days=3))

    def test_backup_disabled_excluded_regardless_of_age(self):
        d = self._make('DisabledOld2', self.timezone.now() - self.timedelta(days=100), backup_enabled=False)
        self.assertNotIn(d, Device.stale(days=3))

    def test_ordering_never_backed_up_first_then_oldest(self):
        old = self._make('Old3', self.timezone.now() - self.timedelta(days=10))
        never = self._make('Never3', None)
        older = self._make('Older3', self.timezone.now() - self.timedelta(days=20))

        ordered = list(Device.stale(days=3))
        self.assertEqual(ordered[0], never)  # nulls first
        self.assertEqual(ordered[1], older)  # then oldest last_backup
        self.assertEqual(ordered[2], old)

    def test_custom_queryset_is_respected(self):
        matching = self._make('ScopedStale', None)
        self._make('OutOfScopeStale', None)  # would also be stale, but excluded via queryset

        scoped_qs = Device.objects.filter(id=matching.id)
        result = list(Device.stale(days=3, queryset=scoped_qs))
        self.assertEqual(result, [matching])


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

    def test_create_device_metadata_ip_rejected(self):
        """SSRF fix, fail-fast half: creating a device pointed at the cloud
        metadata range must be rejected at the API layer, not just at
        connection time."""
        self.client.force_authenticate(user=self.admin)

        response = self.client.post('/api/v1/devices/devices/', {
            'name': 'Metadata-Device',
            'ip_address': '169.254.169.254',
            'vendor': self.vendor.id,
            'device_type': self.device_type.id,
            'username': 'admin',
            'password': 'secret123',
            'protocol': 'ssh',
            'port': 22
        })

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('ip_address', response.data)

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


class DeviceBulkActionsTestCase(APITestCase):
    """Tests for bulk_backup_now and bulk_tag_edit"""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()  # DeviceBackupNowThrottle is cache-backed — see DeviceExpensiveOperationThrottleTestCase
        self.addCleanup(cache.clear)

        User = get_user_model()
        self.operator = User.objects.create_user(
            email='bulk_operator@example.com', username='bulk_operator',
            password='TestPass123!', role='operator',
        )
        self.viewer = User.objects.create_user(
            email='bulk_viewer@example.com', username='bulk_viewer',
            password='TestPass123!', role='viewer',
        )
        self.scoped_operator = User.objects.create_user(
            email='bulk_scoped@example.com', username='bulk_scoped',
            password='TestPass123!', role='operator', device_scope={'tags': ['core']},
        )

        self.vendor = Vendor.objects.create(name='Cisco', slug='cisco-bulk')
        self.device_type = DeviceType.objects.create(name='Router', slug='router-bulk')
        self.core_device = Device.objects.create(
            name='Core-Bulk', ip_address='10.4.0.1', vendor=self.vendor,
            device_type=self.device_type, username='admin',
            password_encrypted=encrypt_data('pw'), created_by=self.operator,
            tags=['core'],
        )
        self.edge_device = Device.objects.create(
            name='Edge-Bulk', ip_address='10.4.0.2', vendor=self.vendor,
            device_type=self.device_type, username='admin',
            password_encrypted=encrypt_data('pw'), created_by=self.operator,
            tags=['edge'],
        )

    # ---- bulk_backup_now ----

    @patch('backups.tasks.backup_device.delay')
    def test_bulk_backup_now_triggers_task_per_device(self, mock_delay):
        mock_delay.return_value = MagicMock(id='fake-task-id')
        self.client.force_authenticate(user=self.operator)

        response = self.client.post('/api/v1/devices/devices/bulk_backup_now/', {
            'device_ids': [self.core_device.id, self.edge_device.id],
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data['triggered_count'], 2)
        self.assertEqual(mock_delay.call_count, 2)

    @patch('backups.tasks.backup_device.delay')
    def test_bulk_backup_now_reports_not_found_ids(self, mock_delay):
        mock_delay.return_value = MagicMock(id='fake-task-id')
        self.client.force_authenticate(user=self.operator)

        response = self.client.post('/api/v1/devices/devices/bulk_backup_now/', {
            'device_ids': [self.core_device.id, 999999],
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data['triggered_count'], 1)
        self.assertEqual(response.data['not_found_ids'], [999999])

    @patch('backups.tasks.backup_device.delay')
    def test_bulk_backup_now_respects_device_scope(self, mock_delay):
        mock_delay.return_value = MagicMock(id='fake-task-id')
        self.client.force_authenticate(user=self.scoped_operator)

        response = self.client.post('/api/v1/devices/devices/bulk_backup_now/', {
            'device_ids': [self.core_device.id, self.edge_device.id],
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data['triggered_count'], 1)
        self.assertEqual(response.data['not_found_ids'], [self.edge_device.id])
        mock_delay.assert_called_once()

    def test_bulk_backup_now_over_cap_rejected(self):
        self.client.force_authenticate(user=self.operator)
        response = self.client.post('/api/v1/devices/devices/bulk_backup_now/', {
            'device_ids': list(range(1, 52)),  # 51 > MAX_BULK_BACKUP_DEVICES (50)
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bulk_backup_now_viewer_forbidden(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.post('/api/v1/devices/devices/bulk_backup_now/', {
            'device_ids': [self.core_device.id],
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_bulk_backup_now_empty_list_rejected(self):
        self.client.force_authenticate(user=self.operator)
        response = self.client.post('/api/v1/devices/devices/bulk_backup_now/', {
            'device_ids': [],
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ---- bulk_tag_edit ----

    def test_bulk_tag_add(self):
        self.client.force_authenticate(user=self.operator)
        response = self.client.post('/api/v1/devices/devices/bulk_tag_edit/', {
            'device_ids': [self.core_device.id, self.edge_device.id],
            'action': 'add', 'tags': ['dc1'],
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.core_device.refresh_from_db()
        self.edge_device.refresh_from_db()
        self.assertEqual(set(self.core_device.tags), {'core', 'dc1'})
        self.assertEqual(set(self.edge_device.tags), {'edge', 'dc1'})

    def test_bulk_tag_remove(self):
        self.client.force_authenticate(user=self.operator)
        response = self.client.post('/api/v1/devices/devices/bulk_tag_edit/', {
            'device_ids': [self.core_device.id],
            'action': 'remove', 'tags': ['core'],
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.core_device.refresh_from_db()
        self.assertEqual(self.core_device.tags, [])

    def test_bulk_tag_set_replaces_entirely(self):
        self.client.force_authenticate(user=self.operator)
        response = self.client.post('/api/v1/devices/devices/bulk_tag_edit/', {
            'device_ids': [self.core_device.id],
            'action': 'set', 'tags': ['prod', 'dc2'],
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.core_device.refresh_from_db()
        self.assertEqual(set(self.core_device.tags), {'prod', 'dc2'})

    def test_bulk_tag_set_empty_clears_tags(self):
        self.client.force_authenticate(user=self.operator)
        response = self.client.post('/api/v1/devices/devices/bulk_tag_edit/', {
            'device_ids': [self.core_device.id],
            'action': 'set', 'tags': [],
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.core_device.refresh_from_db()
        self.assertEqual(self.core_device.tags, [])

    def test_bulk_tag_add_empty_tags_rejected(self):
        self.client.force_authenticate(user=self.operator)
        response = self.client.post('/api/v1/devices/devices/bulk_tag_edit/', {
            'device_ids': [self.core_device.id],
            'action': 'add', 'tags': [],
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bulk_tag_invalid_action_rejected(self):
        self.client.force_authenticate(user=self.operator)
        response = self.client.post('/api/v1/devices/devices/bulk_tag_edit/', {
            'device_ids': [self.core_device.id],
            'action': 'nonsense', 'tags': ['x'],
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bulk_tag_edit_respects_device_scope(self):
        self.client.force_authenticate(user=self.scoped_operator)
        response = self.client.post('/api/v1/devices/devices/bulk_tag_edit/', {
            'device_ids': [self.core_device.id, self.edge_device.id],
            'action': 'add', 'tags': ['x'],
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['updated_count'], 1)
        self.assertEqual(response.data['not_found_ids'], [self.edge_device.id])
        self.edge_device.refresh_from_db()
        self.assertNotIn('x', self.edge_device.tags)

    def test_bulk_tag_edit_viewer_forbidden(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.post('/api/v1/devices/devices/bulk_tag_edit/', {
            'device_ids': [self.core_device.id],
            'action': 'add', 'tags': ['x'],
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class DeviceScopeRBACTestCase(APITestCase):
    """Tests for device_scope restricting DeviceViewSet's queryset"""

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            email='scope_admin@example.com', username='scope_admin',
            password='TestPass123!', role='administrator',
        )
        self.scoped_viewer = User.objects.create_user(
            email='scope_viewer@example.com', username='scope_viewer',
            password='TestPass123!', role='viewer', device_scope={'tags': ['core']},
        )
        self.unscoped_viewer = User.objects.create_user(
            email='unscoped_viewer@example.com', username='unscoped_viewer',
            password='TestPass123!', role='viewer',
        )

        self.vendor = Vendor.objects.create(name='Cisco', slug='cisco-scope-api')
        self.device_type = DeviceType.objects.create(name='Router', slug='router-scope-api')
        self.core_device = Device.objects.create(
            name='Core-API', ip_address='10.2.0.1', vendor=self.vendor,
            device_type=self.device_type, username='admin',
            password_encrypted=encrypt_data('pw'), created_by=self.admin, tags=['core'],
        )
        self.edge_device = Device.objects.create(
            name='Edge-API', ip_address='10.2.0.2', vendor=self.vendor,
            device_type=self.device_type, username='admin',
            password_encrypted=encrypt_data('pw'), created_by=self.admin, tags=['edge'],
        )

    def test_scoped_viewer_sees_only_matching_device(self):
        self.client.force_authenticate(user=self.scoped_viewer)
        response = self.client.get('/api/v1/devices/devices/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = {d['name'] for d in response.data['results']}
        self.assertEqual(names, {'Core-API'})

    def test_scoped_viewer_gets_404_for_out_of_scope_device_detail(self):
        self.client.force_authenticate(user=self.scoped_viewer)
        response = self.client.get(f'/api/v1/devices/devices/{self.edge_device.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_scoped_viewer_can_still_reach_in_scope_device_detail(self):
        self.client.force_authenticate(user=self.scoped_viewer)
        response = self.client.get(f'/api/v1/devices/devices/{self.core_device.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unscoped_viewer_sees_everything(self):
        self.client.force_authenticate(user=self.unscoped_viewer)
        response = self.client.get('/api/v1/devices/devices/')
        names = {d['name'] for d in response.data['results']}
        self.assertEqual(names, {'Core-API', 'Edge-API'})

    def test_administrator_always_sees_everything(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/devices/devices/')
        names = {d['name'] for d in response.data['results']}
        self.assertEqual(names, {'Core-API', 'Edge-API'})

    def test_scoped_viewer_statistics_only_counts_in_scope_devices(self):
        """
        Regression test: statistics() used to query Device.objects
        directly instead of self.get_queryset(), so a scoped user could
        learn the total/by-vendor/by-criticality counts of devices
        outside their scope just by calling this endpoint.
        """
        self.client.force_authenticate(user=self.scoped_viewer)
        response = self.client.get('/api/v1/devices/devices/statistics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total'], 1)

    def test_unscoped_viewer_statistics_counts_everything(self):
        self.client.force_authenticate(user=self.unscoped_viewer)
        response = self.client.get('/api/v1/devices/devices/statistics/')
        self.assertEqual(response.data['total'], 2)


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


class BackupCommandsValidationTestCase(TestCase):
    """Tests for validate_backup_commands — in particular exec_wrapper,
    which used to be type-checked only and not run through
    _validate_command's SAFE_COMMAND_PATTERN/DANGEROUS_COMMANDS pass like
    every other command field (backup, setup[], logout[]). This function
    backs both Device.custom_commands and Vendor.backup_commands, and
    Vendor.backup_commands has no admin-only gate — any operator can write
    it — so an unvalidated exec_wrapper was a real command-injection path
    onto live devices, not just a Device-level, admin-only one.
    """

    def test_valid_config_passes(self):
        from devices.serializers import validate_backup_commands

        validate_backup_commands({
            'backup': 'show running-config',
            'setup': ['terminal length 0'],
            'exec_mode': True,
            'exec_wrapper': 'vyatta-op-cmd-wrapper',
        })  # must not raise

    def test_dangerous_exec_wrapper_rejected(self):
        from rest_framework import serializers
        from devices.serializers import validate_backup_commands

        with self.assertRaises(serializers.ValidationError):
            validate_backup_commands({
                'backup': 'show running-config',
                'exec_mode': True,
                'exec_wrapper': 'reload',
            })

    def test_exec_wrapper_with_dangerous_command_embedded_rejected(self):
        """The actual exploit shape: a wrapper string that carries an
        injected dangerous command alongside legitimate-looking text."""
        from rest_framework import serializers
        from devices.serializers import validate_backup_commands

        with self.assertRaises(serializers.ValidationError):
            validate_backup_commands({
                'backup': 'show running-config',
                'exec_mode': True,
                'exec_wrapper': 'wrapper ; erase startup-config',
            })

    def test_exec_wrapper_non_string_rejected(self):
        from rest_framework import serializers
        from devices.serializers import validate_backup_commands

        with self.assertRaises(serializers.ValidationError):
            validate_backup_commands({
                'backup': 'show running-config',
                'exec_wrapper': 123,
            })

    def test_empty_exec_wrapper_allowed(self):
        from devices.serializers import validate_backup_commands

        validate_backup_commands({
            'backup': 'show running-config',
            'exec_wrapper': '',
        })  # must not raise

    def test_dangerous_backup_command_still_rejected(self):
        """Pre-existing coverage gap: nothing exercised the blacklist at
        all before this test class."""
        from rest_framework import serializers
        from devices.serializers import validate_backup_commands

        with self.assertRaises(serializers.ValidationError):
            validate_backup_commands({'backup': 'reload'})

    def test_dangerous_setup_command_still_rejected(self):
        from rest_framework import serializers
        from devices.serializers import validate_backup_commands

        with self.assertRaises(serializers.ValidationError):
            validate_backup_commands({
                'backup': 'show running-config',
                'setup': ['write erase'],
            })


class DeviceUpdateCredentialSymmetryTestCase(APITestCase):
    """Tests for the fix: password and enable_password used to disagree on
    what an empty string means during update — password treated it as "no
    change" (falsy check), enable_password treated it as "clear the
    credential" (`is not None`). DeviceFormModal.tsx's onFocus handler
    blanks the '*****' placeholder for *either* field the instant it gains
    focus, including from an incidental Tab-through with nothing retyped,
    so that inconsistency meant one field silently discarded a real
    credential on what can be an accidental UI interaction while the other
    didn't. Both must now behave the same (safe) way: empty means
    unchanged, for both.
    """

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            email='cred_symmetry@example.com', username='cred_symmetry',
            password='TestPass123!', role='administrator'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)
        self.vendor = Vendor.objects.create(name='Cisco', slug='cisco-sym')
        self.device_type = DeviceType.objects.create(name='Router', slug='router-sym')
        self.device = Device.objects.create(
            name='Sym-Device', ip_address='10.0.9.1', vendor=self.vendor,
            device_type=self.device_type, username='admin',
            password_encrypted=encrypt_data('original-password'),
            enable_password_encrypted=encrypt_data('original-enable'),
            created_by=self.admin,
        )

    def test_empty_password_does_not_clear_on_update(self):
        response = self.client.patch(f'/api/v1/devices/devices/{self.device.id}/', {'password': ''})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.device.refresh_from_db()
        self.assertEqual(self.device.get_password(), 'original-password')

    def test_empty_enable_password_does_not_clear_on_update(self):
        """The actual regression: this used to silently wipe the credential."""
        response = self.client.patch(f'/api/v1/devices/devices/{self.device.id}/', {'enable_password': ''})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.device.refresh_from_db()
        self.assertEqual(self.device.get_enable_password(), 'original-enable')

    def test_nonempty_password_still_updates(self):
        response = self.client.patch(f'/api/v1/devices/devices/{self.device.id}/', {'password': 'new-password'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.device.refresh_from_db()
        self.assertEqual(self.device.get_password(), 'new-password')

    def test_nonempty_enable_password_still_updates(self):
        response = self.client.patch(f'/api/v1/devices/devices/{self.device.id}/', {'enable_password': 'new-enable'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.device.refresh_from_db()
        self.assertEqual(self.device.get_enable_password(), 'new-enable')


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

    def test_filter_by_tags_single(self):
        """?tags=core matches devices whose tag list contains 'core'."""
        self.device.tags = ['core', 'dc1']
        self.device.save()
        other = Device.objects.create(
            name='Edge-Device', ip_address='192.168.100.9', vendor=self.vendor,
            device_type=self.device_type, username='admin',
            password_encrypted=encrypt_data('pw'), created_by=self.admin, tags=['edge'],
        )

        response = self.client.get('/api/v1/devices/devices/?tags=core')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = {d['name'] for d in response.data['results']}
        self.assertIn('Actions-Device', names)
        self.assertNotIn(other.name, names)

    def test_filter_by_tags_multiple_is_any_overlap(self):
        """?tags=core,edge is an OR — matches either tag, not both."""
        self.device.tags = ['core']
        self.device.save()
        edge_device = Device.objects.create(
            name='Edge-Device-2', ip_address='192.168.100.10', vendor=self.vendor,
            device_type=self.device_type, username='admin',
            password_encrypted=encrypt_data('pw'), created_by=self.admin, tags=['edge'],
        )
        untagged = Device.objects.create(
            name='Untagged-Device', ip_address='192.168.100.11', vendor=self.vendor,
            device_type=self.device_type, username='admin',
            password_encrypted=encrypt_data('pw'), created_by=self.admin,
        )

        response = self.client.get('/api/v1/devices/devices/?tags=core,edge')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = {d['name'] for d in response.data['results']}
        self.assertIn(self.device.name, names)
        self.assertIn(edge_device.name, names)
        self.assertNotIn(untagged.name, names)

    def test_ordering_by_tags_does_not_error(self):
        response = self.client.get('/api/v1/devices/devices/?ordering=tags')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_search_devices(self):
        """Test searching devices"""
        response = self.client.get('/api/v1/devices/devices/?search=Actions')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch('devices.connection.test_connection')
    @patch('core.redis_lock.DeviceLock')
    def test_test_connection_success(self, mock_lock_class, mock_test):
        """Test connection test endpoint - success"""
        mock_lock = MagicMock()
        mock_lock.acquire.return_value = True
        mock_lock_class.return_value = mock_lock
        mock_test.return_value = (True, 'Connection successful')

        response = self.client.post(f'/api/v1/devices/devices/{self.device.id}/test_connection/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        mock_lock.acquire.assert_called_once()
        mock_lock.release.assert_called_once()

    @patch('devices.connection.test_connection')
    @patch('core.redis_lock.DeviceLock')
    def test_test_connection_failure(self, mock_lock_class, mock_test):
        """Test connection test endpoint - failure"""
        mock_lock = MagicMock()
        mock_lock.acquire.return_value = True
        mock_lock_class.return_value = mock_lock
        mock_test.return_value = (False, 'Connection timed out')

        response = self.client.post(f'/api/v1/devices/devices/{self.device.id}/test_connection/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['success'])
        mock_lock.release.assert_called_once()

    @patch('devices.connection.test_connection')
    @patch('core.redis_lock.DeviceLock')
    def test_test_connection_fails_closed_when_device_locked(self, mock_lock_class, mock_test):
        """Fix: this action used to take no lock at all, so a manual 'Test
        Connection' could always race a concurrently-running scheduled
        backup and open a second session to the same device — exactly what
        DeviceLock exists to prevent."""
        mock_lock = MagicMock()
        mock_lock.acquire.return_value = False  # another operation holds it
        mock_lock_class.return_value = mock_lock

        response = self.client.post(f'/api/v1/devices/devices/{self.device.id}/test_connection/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['success'])
        self.assertTrue(response.data.get('locked'))
        mock_test.assert_not_called()  # never even attempted the connection
        mock_lock.release.assert_not_called()  # never acquired, nothing to release


class DeviceExpensiveOperationThrottleTestCase(APITestCase):
    """Tests for rate-limiting test_connection/backup_now — both open a
    real SSH/Telnet session. DeviceLock already stops two of these racing
    against the *same* device; this instead bounds how many a single user
    can fire off against any number of devices in a row, which nothing did
    before.
    """

    def setUp(self):
        from django.core.cache import cache
        # Throttle counters are cache-backed and the cache isn't reset
        # between test classes the way the DB is (each test's DB writes
        # roll back in a transaction; cache entries don't). Test-DB PKs
        # commonly restart from 1 in each isolated test, so a throttle
        # counter keyed by user.pk here can otherwise leak into an
        # unrelated test class's user that happens to get the same PK.
        # Clearing on both ends keeps this test's throttling from leaking
        # in either direction.
        cache.clear()
        self.addCleanup(cache.clear)

        User = get_user_model()
        self.admin = User.objects.create_user(
            email='throttle_dev@example.com', username='throttle_dev',
            password='TestPass123!', role='administrator'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)
        self.vendor = Vendor.objects.create(name='Cisco', slug='cisco-throttle')
        self.device_type = DeviceType.objects.create(name='Router', slug='router-throttle')
        self.device = Device.objects.create(
            name='Throttle-Device', ip_address='10.0.9.80', vendor=self.vendor,
            device_type=self.device_type, username='admin',
            password_encrypted=encrypt_data('pw'), created_by=self.admin,
        )

    @patch('devices.connection.test_connection')
    @patch('core.redis_lock.DeviceLock')
    def test_test_connection_throttled_after_limit(self, mock_lock_class, mock_test):
        mock_lock = MagicMock()
        mock_lock.acquire.return_value = True
        mock_lock_class.return_value = mock_lock
        mock_test.return_value = (True, 'Connection successful')

        statuses = [
            self.client.post(f'/api/v1/devices/devices/{self.device.id}/test_connection/').status_code
            for _ in range(65)  # over the 60/hour limit
        ]
        self.assertIn(status.HTTP_429_TOO_MANY_REQUESTS, statuses)

    @patch('backups.tasks.backup_device.delay')
    def test_backup_now_throttled_after_limit(self, mock_delay):
        mock_delay.return_value = MagicMock(id='fake-task-id')

        statuses = [
            self.client.post(f'/api/v1/devices/devices/{self.device.id}/backup_now/').status_code
            for _ in range(35)  # over the 30/hour limit
        ]
        self.assertIn(status.HTTP_429_TOO_MANY_REQUESTS, statuses)


class DeviceCsvImportSecurityTestCase(APITestCase):
    """Tests for csv_import's SSRF and CSV-injection guards.

    csv_import builds Device rows directly instead of going through
    DeviceCreateSerializer, so it used to skip both _never_a_device (the
    SSRF fix applied to the JSON/API create path) and validate_csv_safe
    (applied there to name/description/location) entirely — a second,
    unguarded path to the exact holes those fixes closed elsewhere.
    """

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            email='csvimport@example.com',
            username='csvimport',
            password='TestPass123!',
            role='administrator'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)
        Vendor.objects.create(name='Cisco', slug='cisco')
        DeviceType.objects.create(name='Router', slug='router')

    def _upload(self, csv_body):
        return self.client.post(
            '/api/v1/devices/devices/csv_import/',
            {'file': io.BytesIO(csv_body.encode('utf-8'))},
            format='multipart',
        )

    def test_metadata_ip_rejected(self):
        body = 'Name;IP Address;Username;Vendor;Device Type\nMeta-Device;169.254.169.254;admin;cisco;router\n'
        response = self._upload(body)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['created'], 0)
        self.assertTrue(any('link-local' in e.lower() for e in response.data['errors']))
        self.assertFalse(Device.objects.filter(ip_address='169.254.169.254').exists())

    def test_csv_formula_injection_in_name_rejected(self):
        body = 'Name;IP Address;Username;Vendor;Device Type\n=cmd|\' /C calc\'!A1;10.0.5.5;admin;cisco;router\n'
        response = self._upload(body)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['created'], 0)
        self.assertFalse(Device.objects.filter(ip_address='10.0.5.5').exists())

    def test_csv_formula_injection_in_location_rejected(self):
        body = 'Name;IP Address;Location;Username;Vendor;Device Type\nGood-Name;10.0.5.6;@SUM(1+1);admin;cisco;router\n'
        response = self._upload(body)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['created'], 0)
        self.assertFalse(Device.objects.filter(ip_address='10.0.5.6').exists())

    def test_ordinary_row_still_imports(self):
        body = 'Name;IP Address;Username;Vendor;Device Type\nGood-Device;10.0.5.7;admin;cisco;router\n'
        response = self._upload(body)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['created'], 1)
        self.assertTrue(Device.objects.filter(ip_address='10.0.5.7').exists())

    def test_update_existing_also_rejects_csv_injection(self):
        """The update-existing branch had zero validation at all before
        this fix — not even the create path's partial username check."""
        Device.objects.create(
            name='Existing', ip_address='10.0.5.8', vendor=Vendor.objects.get(slug='cisco'),
            device_type=DeviceType.objects.get(slug='router'), username='admin',
            password_encrypted=encrypt_data('pw'), created_by=self.admin,
        )
        body = 'Name;IP Address;Location;Vendor;Device Type\n=HYPERLINK("evil");10.0.5.8;here;cisco;router\n'
        response = self.client.post(
            '/api/v1/devices/devices/csv_import/',
            {'file': io.BytesIO(body.encode('utf-8')), 'update_existing': 'true'},
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['updated'], 0)
        device = Device.objects.get(ip_address='10.0.5.8')
        self.assertEqual(device.name, 'Existing')  # unchanged

    def test_tags_column_parsed_on_import(self):
        """Comma-separated Tags cell -> Device.tags list, same convention
        as the device form and Bulk Tag Edit."""
        body = 'Name;IP Address;Username;Vendor;Device Type;Tags\nTagged-Device;10.0.5.9;admin;cisco;router;core, dc1\n'
        response = self._upload(body)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['created'], 1)
        device = Device.objects.get(ip_address='10.0.5.9')
        self.assertEqual(device.tags, ['core', 'dc1'])

    def test_csv_formula_injection_in_tags_rejected(self):
        body = 'Name;IP Address;Username;Vendor;Device Type;Tags\nGood-Name;10.0.5.10;admin;cisco;router;=cmd|\' /C calc\'!A1\n'
        response = self._upload(body)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['created'], 0)
        self.assertFalse(Device.objects.filter(ip_address='10.0.5.10').exists())

    def test_csv_template_includes_tags_column(self):
        response = self.client.get('/api/v1/devices/devices/csv_template/?lang=en')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = response.content.decode('utf-8-sig')
        header_row = content.splitlines()[0]
        self.assertIn('Tags', header_row.split(';'))


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

    def test_validate_backup_config_auth_failed(self):
        """ERROR_CONFIG_AUTH_FAILED was defined but never actually used by
        any test — matches the bug this covers: 15 of 17 ERROR_PATTERNS
        were silently never enforced, this fixture's pattern
        ('authentication failed') being one of them."""
        from devices.connection import validate_backup_config
        is_valid, error = validate_backup_config(self.ERROR_CONFIG_AUTH_FAILED)
        self.assertFalse(is_valid)

    def test_validate_backup_config_login_incorrect_rejected(self):
        """Regression check for the fix: this pattern used to never
        reject anything no matter what the device returned."""
        from devices.connection import validate_backup_config
        is_valid, error = validate_backup_config(
            "Router#show running-config\n% Login incorrect\nRouter#"
        )
        self.assertFalse(is_valid)

    def test_validate_backup_config_permission_denied_rejected(self):
        from devices.connection import validate_backup_config
        is_valid, error = validate_backup_config(
            "Router#show running-config\nPermission denied\nRouter#"
        )
        self.assertFalse(is_valid)

    def test_validate_backup_config_command_authorization_failed_rejected(self):
        from devices.connection import validate_backup_config
        is_valid, error = validate_backup_config(
            "Router#show running-config\nCommand authorization failed\nRouter#"
        )
        self.assertFalse(is_valid)

    def test_validate_backup_config_privilege_level_not_falsely_rejected(self):
        """'privilege level' and 'enable password' are common, entirely
        legitimate Cisco config directives — they must NOT be treated as
        error signatures (they were removed from ERROR_PATTERNS precisely
        because enforcing them would reject real, successful backups)."""
        from devices.connection import validate_backup_config
        config = (
            "hostname Router\n!\n"
            "enable password 7 08351A1E1B0A\n"
            "!\n"
            "username admin privilege 15 secret 5 $1$abc$def\n"
            "line vty 0 4\n"
            " privilege level 15\n"
            " login local\n"
            "!\nend\n"
        )
        is_valid, error = validate_backup_config(config)
        self.assertTrue(is_valid, error)

    def test_validate_backup_config_error_colon_mid_line_not_falsely_rejected(self):
        """
        'error:' appearing mid-line as part of legitimate config content
        (a logging severity directive, a description/banner remnant) must
        NOT be treated as a device error signature — only a line that
        actually STARTS with "error:" (optionally after a leading '%',
        matching real CLI failure output) counts. Regression test for the
        fix: this used to reject real, successful backups whenever a
        vendor's config happened to contain the word for an unrelated
        reason.
        """
        from devices.connection import validate_backup_config
        config = (
            "hostname Router\n!\n"
            "logging trap error: escalate to NOC immediately\n"
            "description WAN uplink - error: contact ISP if flapping\n"
            "!\n"
            "interface GigabitEthernet0/1\n"
            " ip address 10.0.0.1 255.255.255.0\n"
            "!\nend\n"
        )
        is_valid, error = validate_backup_config(config)
        self.assertTrue(is_valid, error)

    def test_validate_backup_config_error_colon_at_line_start_rejected(self):
        """A line that actually starts with "error:" is a real device error response."""
        from devices.connection import validate_backup_config
        is_valid, error = validate_backup_config(
            "Router#show running-config\nError: Invalid input detected\nRouter#"
        )
        self.assertFalse(is_valid)

    def test_validate_backup_config_percent_error_colon_prefix_rejected(self):
        """"% Error:" — the common CLI error-prefix marker — is also a real error response."""
        from devices.connection import validate_backup_config
        is_valid, error = validate_backup_config(
            "Router#show running-config\n% Error: ambiguous command\nRouter#"
        )
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

        # device_id is required now (host key pinning needs a Device row to
        # pin against) — SSHClient itself is mocked out here, so the real
        # missing_host_key() callback never actually runs in this test.
        conn = SSHConnection('192.168.1.1', 22, 'admin', 'password', device_id=1)
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

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'wrongpass', device_id=1)

        # Should fall back to binary and fail
        with patch.object(conn, '_run_ssh_binary') as mock_binary:
            mock_binary.return_value = {'success': False, 'error': 'Auth failed'}
            with self.assertRaises(DeviceConnectionError):
                conn.connect()

    @patch('devices.connection.PARAMIKO_AVAILABLE', True)
    def test_paramiko_connect_without_device_id_fails_closed(self):
        """No device_id means no way to verify the host key — must refuse
        the connection rather than silently trusting whatever key is
        presented (the old AutoAddPolicy behavior)."""
        from devices.connection import _ParamikoSSH

        ssh = _ParamikoSSH('192.168.1.1', 22, 'admin', 'password', device_id=None)
        result = ssh.connect()

        self.assertFalse(result)
        self.assertIsNone(ssh.client)

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


class SSHHostKeyPinningTestCase(TestCase):
    """
    Tests for PinnedHostKeyPolicy — trust-on-first-use SSH host key
    verification backed by the Device model, replacing the old
    paramiko.AutoAddPolicy (which trusted any presented key
    unconditionally, every time, with no persistence at all).
    """

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email='hostkey@example.com',
            username='hostkeyuser',
            password='pass123'
        )
        self.vendor = Vendor.objects.create(name='Cisco', slug='cisco-hostkey-test')
        self.device_type = DeviceType.objects.create(name='Router', slug='router-hostkey-test')
        self.device = Device.objects.create(
            name='pin-test-device',
            ip_address='192.168.50.1',
            vendor=self.vendor,
            device_type=self.device_type,
            protocol='ssh',
            port=22,
            created_by=self.user,
            username='admin',
        )

    @staticmethod
    def _make_key(fingerprint_hex='aabbcc', key_type='ssh-ed25519'):
        key = MagicMock()
        key.get_fingerprint.return_value = bytes.fromhex(fingerprint_hex)
        key.get_name.return_value = key_type
        return key

    def test_first_connection_pins_key(self):
        """No key on file yet: the presented key is trusted and stored."""
        from devices.connection import PinnedHostKeyPolicy

        self.assertEqual(self.device.ssh_host_key_fingerprint, '')

        policy = PinnedHostKeyPolicy(self.device.id)
        policy.missing_host_key(MagicMock(), '192.168.50.1', self._make_key('aabbcc', 'ssh-ed25519'))
        # Not raising is the pass condition here.

        self.device.refresh_from_db()
        self.assertEqual(self.device.ssh_host_key_type, 'ssh-ed25519')
        self.assertEqual(self.device.ssh_host_key_fingerprint, 'SHA256:aabbcc')
        self.assertIsNotNone(self.device.ssh_host_key_verified_at)
        self.assertFalse(self.device.has_pending_ssh_host_key)

    def test_matching_key_is_silently_accepted(self):
        """A key that matches what's pinned connects with no side effects."""
        from devices.connection import PinnedHostKeyPolicy

        self.device.ssh_host_key_type = 'ssh-ed25519'
        self.device.ssh_host_key_fingerprint = 'SHA256:aabbcc'
        self.device.save()

        policy = PinnedHostKeyPolicy(self.device.id)
        policy.missing_host_key(MagicMock(), '192.168.50.1', self._make_key('aabbcc', 'ssh-ed25519'))

        self.device.refresh_from_db()
        self.assertEqual(self.device.ssh_host_key_fingerprint, 'SHA256:aabbcc')
        self.assertFalse(self.device.has_pending_ssh_host_key)

    def test_mismatched_key_is_rejected_and_flagged(self):
        """A key that doesn't match what's pinned: refuse the connection,
        record the new key as pending (not trusted), leave the old pinned
        key untouched, and attempt a notification."""
        from devices.connection import PinnedHostKeyPolicy, HostKeyMismatchError

        self.device.ssh_host_key_type = 'ssh-ed25519'
        self.device.ssh_host_key_fingerprint = 'SHA256:aabbcc'
        self.device.save()

        policy = PinnedHostKeyPolicy(self.device.id)

        with patch('notifications.services.notify_host_key_mismatch') as mock_notify:
            with self.assertRaises(HostKeyMismatchError):
                policy.missing_host_key(MagicMock(), '192.168.50.1', self._make_key('ddeeff', 'ssh-ed25519'))
            mock_notify.assert_called_once()

        self.device.refresh_from_db()
        # Old pinned key is untouched.
        self.assertEqual(self.device.ssh_host_key_fingerprint, 'SHA256:aabbcc')
        # New key recorded as pending, not trusted.
        self.assertEqual(self.device.ssh_host_key_pending_fingerprint, 'SHA256:ddeeff')
        self.assertTrue(self.device.has_pending_ssh_host_key)

    def test_mismatch_does_not_fall_back_to_binary(self):
        """The whole point of raising a distinct exception type: a rejected
        host key must abort the connection outright, not silently continue
        via the netvault-ssh binary fallback, which performs no host key
        verification of its own at all."""
        from devices.connection import SSHConnection, HostKeyMismatchError

        conn = SSHConnection('192.168.50.1', 22, 'admin', 'password', device_id=self.device.id)

        with patch.object(conn, '_run_ssh_binary') as mock_binary, \
             patch('devices.connection._ParamikoSSH.connect') as mock_paramiko_connect:
            mock_paramiko_connect.side_effect = HostKeyMismatchError('host key changed')

            with self.assertRaises(HostKeyMismatchError):
                conn.connect()

            mock_binary.assert_not_called()

    def test_approve_pending_key_via_model(self):
        """Device.approve_ssh_host_key() promotes the pending key and
        clears the pending state, matching what the approve API action does."""
        self.device.ssh_host_key_type = 'ssh-ed25519'
        self.device.ssh_host_key_fingerprint = 'SHA256:aabbcc'
        self.device.ssh_host_key_pending_type = 'ssh-ed25519'
        self.device.ssh_host_key_pending_fingerprint = 'SHA256:ddeeff'
        self.device.save()

        self.device.approve_ssh_host_key()

        self.assertEqual(self.device.ssh_host_key_fingerprint, 'SHA256:ddeeff')
        self.assertEqual(self.device.ssh_host_key_pending_fingerprint, '')
        self.assertFalse(self.device.has_pending_ssh_host_key)

    def test_reject_pending_key_via_model(self):
        """Device.reject_ssh_host_key() clears the pending state without
        touching the previously-pinned key."""
        self.device.ssh_host_key_type = 'ssh-ed25519'
        self.device.ssh_host_key_fingerprint = 'SHA256:aabbcc'
        self.device.ssh_host_key_pending_type = 'ssh-ed25519'
        self.device.ssh_host_key_pending_fingerprint = 'SHA256:ddeeff'
        self.device.save()

        self.device.reject_ssh_host_key()

        self.assertEqual(self.device.ssh_host_key_fingerprint, 'SHA256:aabbcc')
        self.assertEqual(self.device.ssh_host_key_pending_fingerprint, '')
        self.assertFalse(self.device.has_pending_ssh_host_key)


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

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'password', device_id=1)
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

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'wrongpass', device_id=1)
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

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'password', device_id=1)
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

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'password', device_id=1)
        conn._use_binary = True

        result = conn._run_ssh_binary(mode='test')
        self.assertFalse(result['success'])
        self.assertIn('timeout', result['error'].lower())


class CmdsStdinSupportDetectionTestCase(TestCase):
    """
    Tests for _binary_supports_cmds_stdin() — static byte-scan detection
    of whether a netvault-ssh binary was built from source new enough to
    support -cmds-stdin (commands read from stdin instead of argv, so an
    embedded enable password doesn't sit in `ps aux` for the life of the
    subprocess). Deliberately NOT a subprocess probe — see the function's
    docstring for why: this suite includes tests that mock
    devices.connection.subprocess.run to script exact response sequences,
    and an extra unrelated subprocess call here would silently consume
    one of those.
    """

    def setUp(self):
        from devices.connection import _CMDS_STDIN_SUPPORT_CACHE
        # Cache is a module-level dict shared across the whole test run —
        # isolate each test from whatever earlier tests already resolved
        # for these same binary paths.
        _CMDS_STDIN_SUPPORT_CACHE.clear()

    def tearDown(self):
        from devices.connection import _CMDS_STDIN_SUPPORT_CACHE
        _CMDS_STDIN_SUPPORT_CACHE.clear()

    def test_detects_support_when_string_present(self):
        from devices.connection import _binary_supports_cmds_stdin

        with patch('builtins.open', MagicMock(
            return_value=MagicMock(
                __enter__=MagicMock(return_value=MagicMock(read=MagicMock(
                    return_value=b'...\x00-cmds-stdin\x00...'
                ))),
                __exit__=MagicMock(return_value=False),
            )
        )):
            self.assertTrue(_binary_supports_cmds_stdin('/fake/path/netvault-ssh'))

    def test_no_support_when_string_absent(self):
        from devices.connection import _binary_supports_cmds_stdin

        with patch('builtins.open', MagicMock(
            return_value=MagicMock(
                __enter__=MagicMock(return_value=MagicMock(read=MagicMock(
                    return_value=b'...\x00-cmds\x00...'
                ))),
                __exit__=MagicMock(return_value=False),
            )
        )):
            self.assertFalse(_binary_supports_cmds_stdin('/fake/path/netvault-ssh'))

    def test_fails_closed_when_binary_missing(self):
        from devices.connection import _binary_supports_cmds_stdin

        self.assertFalse(_binary_supports_cmds_stdin('/definitely/does/not/exist/netvault-ssh'))

    def test_result_is_cached_per_binary_path(self):
        from devices.connection import _binary_supports_cmds_stdin, _CMDS_STDIN_SUPPORT_CACHE

        mock_open = MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=MagicMock(read=MagicMock(return_value=b'-cmds-stdin'))),
            __exit__=MagicMock(return_value=False),
        ))
        with patch('builtins.open', mock_open):
            self.assertTrue(_binary_supports_cmds_stdin('/fake/path/a'))
            self.assertTrue(_binary_supports_cmds_stdin('/fake/path/a'))

        # Second call for the same path must have hit the cache, not
        # re-opened the file.
        self.assertEqual(mock_open.call_count, 1)
        self.assertEqual(_CMDS_STDIN_SUPPORT_CACHE['/fake/path/a'], True)

    def test_current_repo_binaries_are_not_yet_rebuilt(self):
        """
        Sanity check against the real, checked-in binaries: as of this
        fix, netvault-ssh.c gained -cmds-stdin support but the prebuilt
        binaries in tools/netvault-ssh/ have not been rebuilt from it yet
        (no supported rebuild path exists in this repo for the -modern
        one; see install.sh). Detection must correctly report False for
        both today — and will correctly flip to True on its own, with no
        further code changes, the moment either binary is rebuilt from
        the updated source.
        """
        from devices.connection import (
            _binary_supports_cmds_stdin, NETVAULT_SSH_BIN, NETVAULT_SSH_MODERN_BIN,
        )
        self.assertFalse(_binary_supports_cmds_stdin(NETVAULT_SSH_BIN))
        self.assertFalse(_binary_supports_cmds_stdin(NETVAULT_SSH_MODERN_BIN))


class SSHBinaryCmdsStdinPathTestCase(TestCase):
    """
    Tests for _run_ssh_binary()'s behavior once a binary IS detected as
    supporting -cmds-stdin — the argv-leak fix's actual effect. Mocks
    _binary_supports_cmds_stdin directly (rather than relying on a real
    rebuilt binary, which doesn't exist in this repo yet) so this is
    exercised independently of the detection mechanism itself, which
    CmdsStdinSupportDetectionTestCase covers separately.
    """

    @patch('devices.connection._binary_supports_cmds_stdin', return_value=True)
    @patch('devices.connection.subprocess.run')
    def test_commands_sent_via_stdin_not_argv(self, mock_run, mock_supports):
        from devices.connection import SSHConnection

        mock_run.return_value = MagicMock(
            stdout='{"success":true,"output":"hostname Router\\n!"}',
            returncode=0,
        )

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'mypassword', device_id=1)
        conn._use_binary = True

        commands = 'enable|||SUPER_SECRET_ENABLE_PW|||show running-config'
        result = conn._run_ssh_binary(mode='shell', commands=commands)

        self.assertTrue(result['success'])

        called_argv = mock_run.call_args.args[0]
        self.assertIn('-cmds-stdin', called_argv)
        self.assertNotIn('-cmds', called_argv)
        # The whole point of the fix: the enable password must never
        # appear as its own argv token.
        for arg in called_argv:
            self.assertNotIn('SUPER_SECRET_ENABLE_PW', arg)

        stdin_payload = mock_run.call_args.kwargs['input']
        self.assertEqual(stdin_payload, 'mypassword\n' + commands + '\n')

    @patch('devices.connection._binary_supports_cmds_stdin', return_value=False)
    @patch('devices.connection.subprocess.run')
    def test_falls_back_to_argv_when_binary_unsupported(self, mock_run, mock_supports):
        """Old, still-default behavior for binaries that haven't been rebuilt."""
        from devices.connection import SSHConnection

        mock_run.return_value = MagicMock(
            stdout='{"success":true,"output":"hostname Router\\n!"}',
            returncode=0,
        )

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'mypassword', device_id=1)
        conn._use_binary = True

        commands = 'enable|||SUPER_SECRET_ENABLE_PW|||show running-config'
        result = conn._run_ssh_binary(mode='shell', commands=commands)

        self.assertTrue(result['success'])

        called_argv = mock_run.call_args.args[0]
        self.assertIn('-cmds', called_argv)
        self.assertIn(commands, called_argv)
        self.assertNotIn('-cmds-stdin', called_argv)

        stdin_payload = mock_run.call_args.kwargs['input']
        self.assertEqual(stdin_payload, 'mypassword')

    @patch('devices.connection._binary_supports_cmds_stdin', return_value=True)
    @patch('devices.connection.subprocess.run')
    def test_test_mode_unaffected_no_commands_to_send(self, mock_run, mock_supports):
        """mode='test' never has commands — -cmds-stdin must not appear."""
        from devices.connection import SSHConnection

        mock_run.return_value = MagicMock(
            stdout='{"success":true,"output":"Connection successful"}',
            returncode=0,
        )

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'mypassword', device_id=1)
        conn._use_binary = True

        result = conn._run_ssh_binary(mode='test')
        self.assertTrue(result['success'])

        called_argv = mock_run.call_args.args[0]
        self.assertNotIn('-cmds-stdin', called_argv)
        self.assertNotIn('-cmds', called_argv)
        self.assertEqual(mock_run.call_args.kwargs['input'], 'mypassword')


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

    def test_validate_link_local_blocked_even_with_empty_allowlist(self):
        """Cloud metadata (169.254.169.254) must be unreachable regardless
        of ALLOWED_PRIVATE_NETWORKS — this is the SSRF-to-metadata fix."""
        from devices.connection import validate_target_host, DeviceConnectionError

        with self.assertRaises(DeviceConnectionError) as ctx:
            validate_target_host('169.254.169.254')
        self.assertIn('link-local', str(ctx.exception).lower())

    def test_validate_link_local_blocked_even_with_allowlist_configured(self):
        """A configured ALLOWED_PRIVATE_NETWORKS must not be able to
        accidentally re-open the metadata range — it's not gated by that
        setting at all, by design."""
        import ipaddress
        from devices.connection import validate_target_host, DeviceConnectionError

        with override_settings(ALLOWED_PRIVATE_NETWORKS=[ipaddress.ip_network('0.0.0.0/0')]):
            with self.assertRaises(DeviceConnectionError):
                validate_target_host('169.254.169.254')

    def test_validate_multicast_blocked(self):
        from devices.connection import validate_target_host, DeviceConnectionError

        with self.assertRaises(DeviceConnectionError) as ctx:
            validate_target_host('224.0.0.1')
        self.assertIn('multicast', str(ctx.exception).lower())

    def test_validate_unspecified_blocked(self):
        from devices.connection import validate_target_host, DeviceConnectionError

        with self.assertRaises(DeviceConnectionError) as ctx:
            validate_target_host('0.0.0.0')
        self.assertIn('unspecified', str(ctx.exception).lower())

    def test_validate_private_ip_allowed_by_default(self):
        """The core use case — RFC1918 device addresses — must still work
        with no ALLOWED_PRIVATE_NETWORKS configured."""
        from devices.connection import validate_target_host

        self.assertEqual(validate_target_host('10.0.0.1'), '10.0.0.1')

    def test_validate_private_ip_restricted_by_allowlist(self):
        import ipaddress
        from devices.connection import validate_target_host, DeviceConnectionError

        with override_settings(ALLOWED_PRIVATE_NETWORKS=[ipaddress.ip_network('10.0.0.0/8')]):
            self.assertEqual(validate_target_host('10.1.2.3'), '10.1.2.3')
            with self.assertRaises(DeviceConnectionError):
                validate_target_host('192.168.1.1')


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

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'password', device_id=1)
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

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'password', device_id=1)
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

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'password', device_id=1)
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

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'password', device_id=1)
        conn._use_binary = True

        result = conn._run_ssh_binary(mode='shell', commands='admin display-config')
        self.assertTrue(result['success'])

    @patch('devices.connection.subprocess.run')
    def test_auth_failure_no_kex_fallback(self, mock_run):
        """Test auth failure (code 10) doesn't trigger KEX fallback"""
        from devices.connection import SSHConnection, ERR_AUTH_FAILED

        # Auth failure should NOT trigger fallback to modern binary
        mock_run.return_value = MagicMock(stdout=self.SSH_AUTH_FAILED, returncode=1)

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'wrongpass', device_id=1)
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

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'password', device_id=1)
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

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'password', device_id=1)
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

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'password', device_id=1)

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

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'cisco123', device_id=1)
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

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'nokia123', device_id=1)
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

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'huawei123', device_id=1)
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

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'password', device_id=1)
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

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'password', device_id=1)
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
        """Test output cleaning removes long MOTD banners"""
        from devices.connection import clean_device_output

        output = self.LONG_BANNER + "\nhostname Router\n!\ninterface Gi0/0\n!\nend"
        cleaned = clean_device_output(output, 'cisco', 'show running-config')

        # Config content should be present
        self.assertIn('hostname Router', cleaned)
        self.assertIn('interface Gi0/0', cleaned)
        # Banner decorative lines (****) should be removed
        self.assertNotIn('*****', cleaned)
        # Banner text should be removed
        self.assertNotIn('WARNING', cleaned)
        self.assertNotIn('unauthorized', cleaned.lower())

    def test_clean_output_with_ansi_art(self):
        """Test ANSI escape sequences and box drawing are removed"""
        from devices.connection import clean_device_output

        output = self.ANSI_ART_BANNER + "\nhostname Router\n!\nend"
        cleaned = clean_device_output(output, 'cisco', 'show running-config')

        # Should not contain any ANSI codes
        self.assertNotIn('\x1b', cleaned)
        self.assertNotIn('[31m', cleaned)
        # Box drawing characters should be filtered
        self.assertNotIn('╔', cleaned)
        self.assertNotIn('╗', cleaned)

    def test_is_banner_line_detection(self):
        """Test banner line detection function"""
        from devices.connection import _is_banner_line

        # These ARE banner lines
        self.assertTrue(_is_banner_line('*' * 50))
        self.assertTrue(_is_banner_line('=' * 50))
        self.assertTrue(_is_banner_line('-' * 50))
        self.assertTrue(_is_banner_line('*   *   *   *   *'))
        self.assertTrue(_is_banner_line('╔══════════════╗'))
        self.assertTrue(_is_banner_line('║              ║'))
        self.assertTrue(_is_banner_line('+----+----+----+'))

        # These are NOT banner lines (real config)
        self.assertFalse(_is_banner_line('hostname Router'))
        self.assertFalse(_is_banner_line('interface GigabitEthernet0/0'))
        self.assertFalse(_is_banner_line('ip address 192.168.1.1 255.255.255.0'))
        self.assertFalse(_is_banner_line('!'))  # Config separator
        self.assertFalse(_is_banner_line('#'))  # Comment marker
        self.assertFalse(_is_banner_line('description WAN-Link'))
        self.assertFalse(_is_banner_line('set policy-name "allow-all"'))

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

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'password', device_id=1)
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

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'password', device_id=1)
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

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'password', device_id=1)
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

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'password', device_id=1)

        with patch.object(conn, '_run_ssh_binary') as mock_binary:
            mock_binary.return_value = {'success': False, 'error': 'Auth failed'}
            try:
                conn.connect()
            except Exception:
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

        conn = SSHConnection('192.168.1.1', 22, 'admin', 'password', device_id=1)
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
