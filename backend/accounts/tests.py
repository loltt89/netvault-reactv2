"""
Tests for accounts app - User model, authentication, 2FA, AuditLog
"""
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock
import pyotp

from accounts.models import User, AuditLog, SAMLSettings


class UserModelTestCase(TestCase):
    """Tests for User model"""

    def setUp(self):
        self.user_data = {
            'email': 'test@example.com',
            'username': 'testuser',
            'password': 'SecurePass123!',
            'first_name': 'Test',
            'last_name': 'User',
            'role': 'operator'
        }

    def test_create_user(self):
        """Test creating a regular user"""
        User = get_user_model()
        user = User.objects.create_user(**self.user_data)

        self.assertEqual(user.email, self.user_data['email'])
        self.assertEqual(user.username, self.user_data['username'])
        self.assertEqual(user.role, 'operator')
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password(self.user_data['password']))

    def test_create_superuser(self):
        """Test creating a superuser"""
        User = get_user_model()
        admin = User.objects.create_superuser(
            email='admin@example.com',
            username='admin',
            password='AdminPass123!'
        )

        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertEqual(admin.role, 'administrator')

    def test_email_required(self):
        """Test that email is required"""
        User = get_user_model()
        with self.assertRaises(ValueError):
            User.objects.create_user(email='', username='test', password='pass')

    def test_email_normalized(self):
        """Test that email is normalized"""
        User = get_user_model()
        user = User.objects.create_user(
            email='Test@EXAMPLE.COM',
            username='testuser',
            password='pass123'
        )
        self.assertEqual(user.email, 'Test@example.com')

    def test_get_full_name(self):
        """Test get_full_name method"""
        User = get_user_model()
        user = User.objects.create_user(**self.user_data)
        self.assertEqual(user.get_full_name(), 'Test User')

    def test_get_full_name_empty(self):
        """Test get_full_name returns email when names are empty"""
        User = get_user_model()
        user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='pass123'
        )
        self.assertEqual(user.get_full_name(), 'test@example.com')

    def test_get_short_name(self):
        """Test get_short_name method"""
        User = get_user_model()
        user = User.objects.create_user(**self.user_data)
        self.assertEqual(user.get_short_name(), 'Test')


class TwoFactorAuthTestCase(TestCase):
    """Tests for 2FA functionality"""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email='2fa@example.com',
            username='2fauser',
            password='pass123'
        )

    def test_generate_2fa_secret(self):
        """Test 2FA secret generation"""
        secret = self.user.generate_2fa_secret()

        self.assertIsNotNone(secret)
        self.assertEqual(len(secret), 32)  # Base32 encoded
        self.assertEqual(self.user.two_factor_secret, secret)

    def test_get_2fa_uri(self):
        """Test 2FA provisioning URI generation"""
        uri = self.user.get_2fa_uri()

        self.assertIn('otpauth://totp/', uri)
        # Email is URL-encoded in the URI
        self.assertIn('2fa%40example.com', uri)
        self.assertIn('NetVault', uri)

    def test_verify_2fa_token_valid(self):
        """Test valid 2FA token verification"""
        self.user.generate_2fa_secret()
        self.user.two_factor_enabled = True
        self.user.save()

        # Generate current valid token
        totp = pyotp.TOTP(self.user.two_factor_secret)
        token = totp.now()

        self.assertTrue(self.user.verify_2fa_token(token))

    def test_verify_2fa_token_invalid(self):
        """Test invalid 2FA token rejection"""
        self.user.generate_2fa_secret()
        self.user.two_factor_enabled = True
        self.user.save()

        self.assertFalse(self.user.verify_2fa_token('000000'))
        self.assertFalse(self.user.verify_2fa_token('invalid'))

    def test_verify_2fa_disabled(self):
        """Test 2FA verification when disabled"""
        self.user.two_factor_enabled = False
        self.user.save()

        self.assertFalse(self.user.verify_2fa_token('123456'))


class AuditLogTestCase(TestCase):
    """Tests for AuditLog model"""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email='audit@example.com',
            username='audituser',
            password='pass123'
        )

    def test_create_audit_log(self):
        """Test creating an audit log entry"""
        log = AuditLog.objects.create(
            user=self.user,
            action='login',
            resource_type='User',
            resource_id=self.user.id,
            resource_name=self.user.email,
            description='User logged in',
            ip_address='192.168.1.1',
            success=True
        )

        self.assertEqual(log.action, 'login')
        self.assertEqual(log.resource_type, 'User')
        self.assertTrue(log.success)
        self.assertIsNotNone(log.timestamp)

    def test_audit_log_ordering(self):
        """Test audit logs are ordered by timestamp descending"""
        AuditLog.objects.create(
            user=self.user,
            action='login',
            resource_type='User',
            description='First log'
        )
        AuditLog.objects.create(
            user=self.user,
            action='logout',
            resource_type='User',
            description='Second log'
        )

        logs = AuditLog.objects.all()
        self.assertEqual(logs[0].action, 'logout')
        self.assertEqual(logs[1].action, 'login')

    def test_audit_log_user_deletion(self):
        """Test audit log preserved when user is deleted"""
        log = AuditLog.objects.create(
            user=self.user,
            action='create',
            resource_type='Device',
            resource_name='Router-1'
        )
        log_id = log.id
        self.user.delete()

        # Log should still exist
        log = AuditLog.objects.get(id=log_id)
        self.assertIsNone(log.user)
        self.assertEqual(log.resource_name, 'Router-1')


class SAMLSettingsTestCase(TestCase):
    """Tests for SAML SSO settings singleton"""

    def test_singleton_pattern(self):
        """Test only one SAMLSettings instance can exist"""
        # First instance using get_or_create
        settings1, created1 = SAMLSettings.objects.get_or_create(pk=1, defaults={'enabled': False})
        self.assertTrue(created1)

        # Second call should return existing, not create new
        settings2, created2 = SAMLSettings.objects.get_or_create(pk=1, defaults={'enabled': True})
        self.assertFalse(created2)

        self.assertEqual(SAMLSettings.objects.count(), 1)
        # Both refer to pk=1
        self.assertEqual(settings1.pk, 1)
        self.assertEqual(settings2.pk, 1)
        # First value should be preserved (not overwritten by defaults)
        self.assertFalse(settings2.enabled)

    def test_get_settings(self):
        """Test get_settings class method"""
        settings = SAMLSettings.get_settings()
        self.assertIsNotNone(settings)
        self.assertFalse(settings.enabled)  # Default

    def test_get_settings_existing(self):
        """Test get_settings returns existing settings"""
        SAMLSettings.objects.create(
            enabled=True,
            idp_entity_id='https://idp.example.com'
        )

        settings = SAMLSettings.get_settings()
        self.assertTrue(settings.enabled)
        self.assertEqual(settings.idp_entity_id, 'https://idp.example.com')


class AuthAPITestCase(APITestCase):
    """Tests for authentication API endpoints"""

    def setUp(self):
        self.client = APIClient()
        User = get_user_model()
        self.user = User.objects.create_user(
            email='api@example.com',
            username='apiuser',
            password='TestPass123!'
        )

    def test_login_success(self):
        """Test successful login"""
        response = self.client.post('/api/v1/token/', {
            'email': 'api@example.com',
            'password': 'TestPass123!'
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('user', response.data)

    def test_login_wrong_password(self):
        """Test login with wrong password"""
        response = self.client.post('/api/v1/token/', {
            'email': 'api@example.com',
            'password': 'WrongPassword!'
        })

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_nonexistent_user(self):
        """Test login with nonexistent user"""
        response = self.client.post('/api/v1/token/', {
            'email': 'nonexistent@example.com',
            'password': 'SomePass123!'
        })

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_me_endpoint_authenticated(self):
        """Test /me endpoint with authenticated user"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/v1/users/me/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'api@example.com')

    def test_me_endpoint_unauthenticated(self):
        """Test /me endpoint without authentication"""
        response = self.client.get('/api/v1/users/me/')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class UserRoleTestCase(TestCase):
    """Tests for user roles and permissions"""

    def test_role_choices(self):
        """Test all role choices are valid"""
        User = get_user_model()
        valid_roles = ['administrator', 'operator', 'viewer', 'auditor']

        for role in valid_roles:
            user = User.objects.create_user(
                email=f'{role}@example.com',
                username=f'{role}user',
                password='pass123',
                role=role
            )
            self.assertEqual(user.role, role)

    def test_default_role(self):
        """Test default role is viewer"""
        User = get_user_model()
        user = User.objects.create_user(
            email='default@example.com',
            username='defaultuser',
            password='pass123'
        )
        self.assertEqual(user.role, 'viewer')
