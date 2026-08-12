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
from accounts.saml_views import SAMLACSView, SAMLAccountLinkRequired


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


class Verify2FAThrottleTestCase(APITestCase):
    """Tests for the verify_2fa rate-limit fix.

    verify_2fa used to be throttled by LoginRateThrottle — an
    AnonRateThrottle, whose get_cache_key() returns None (skips throttling
    entirely) once the request is authenticated. Since verify_2fa is only
    reachable authenticated, that throttle never did anything: a stolen
    access token could brute-force the 6-digit TOTP with no limit despite
    the docstring claiming otherwise. TwoFactorVerifyThrottle
    (UserRateThrottle, scope='two_factor_verify', 10/hour per settings.py)
    replaces it.
    """

    def setUp(self):
        from django.core.cache import cache
        cache.clear()  # throttle counters are cache-backed; isolate from other tests

        User = get_user_model()
        self.user = User.objects.create_user(
            email='throttle2fa@example.com', username='throttle2fa', password='TestPass123!'
        )
        self.user.generate_2fa_secret()
        self.user.save()

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_verify_2fa_is_actually_throttled(self):
        """The core regression check: repeated calls must eventually 429,
        not silently allow unlimited attempts (which is what
        AnonRateThrottle did for this authenticated-only endpoint)."""
        responses = [
            self.client.post('/api/v1/users/verify_2fa/', {'token': '000000'})
            for _ in range(15)  # over the 10/hour limit
        ]

        statuses = [r.status_code for r in responses]
        self.assertIn(status.HTTP_429_TOO_MANY_REQUESTS, statuses,
                       f"Expected a 429 among {statuses} — throttle never engaged")
        # Every call before the throttle kicked in should have been a normal
        # rejection (wrong code), not something throttle-unrelated failing.
        first_429 = statuses.index(status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertTrue(all(s == status.HTTP_400_BAD_REQUEST for s in statuses[:first_429]))

    def test_throttle_is_scoped_per_user(self):
        """UserRateThrottle keys by user id — one account's attempts must
        not lock out a different account."""
        User = get_user_model()
        other_user = User.objects.create_user(
            email='other2fa@example.com', username='other2fa', password='TestPass123!'
        )
        other_user.generate_2fa_secret()
        other_user.save()

        for _ in range(10):
            self.client.post('/api/v1/users/verify_2fa/', {'token': '000000'})

        other_client = APIClient()
        other_client.force_authenticate(user=other_user)
        response = other_client.post('/api/v1/users/verify_2fa/', {'token': '000000'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


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


class SAMLAccountLinkingTestCase(TestCase):
    """Tests for the SAML account-takeover fix.

    _get_or_create_user must never silently attach a SAML identity to an
    existing password-protected account just because the IdP asserted a
    matching email/username — that's the account-takeover primitive. It
    should still work transparently for accounts that have no password to
    steal (SAML-provisioned, or explicitly passwordless), for returning
    users already linked by saml_name_id, and for the explicit
    authenticated link flow (link_user_id, from SAMLLinkInitView).
    """

    def setUp(self):
        self.saml_config = SAMLSettings.objects.create(
            enabled=True,
            auto_create_users=True,
            default_role='viewer',
        )
        self.view = SAMLACSView()

    def test_refuses_to_link_existing_password_account(self):
        admin = User.objects.create_user(
            email='admin@example.com', username='admin',
            password='RealPassword123!', role='administrator',
        )

        with self.assertRaises(SAMLAccountLinkRequired):
            self.view._get_or_create_user(
                self.saml_config, 'admin', 'admin@example.com', 'Admin', 'User', 'attacker-nameid'
            )

        admin.refresh_from_db()
        self.assertFalse(admin.is_saml_user)
        self.assertEqual(admin.saml_name_id, '')

    def test_logs_in_existing_saml_only_account_by_email(self):
        """No local password == nothing for a spoofed attribute to steal."""
        user = User.objects.create(email='sso@example.com', username='sso', is_saml_user=True, is_active=True)
        user.set_unusable_password()
        user.save()

        result = self.view._get_or_create_user(
            self.saml_config, 'sso', 'sso@example.com', 'SSO', 'User', 'idp-nameid-1'
        )
        self.assertEqual(result.id, user.id)
        self.assertEqual(result.saml_name_id, 'idp-nameid-1')

    def test_returning_user_matched_by_saml_name_id(self):
        """Already-linked users are found by their stable NameID, not email."""
        user = User.objects.create(
            email='linked@example.com', username='linked',
            is_saml_user=True, saml_name_id='stable-id', is_active=True,
        )
        user.set_unusable_password()
        user.save()

        result = self.view._get_or_create_user(
            self.saml_config, 'linked', 'linked@example.com', '', '', 'stable-id'
        )
        self.assertEqual(result.id, user.id)

    def test_creates_new_user_when_auto_create_enabled(self):
        result = self.view._get_or_create_user(
            self.saml_config, 'newuser', 'newuser@example.com', 'New', 'User', 'idp-nameid-2'
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.email, 'newuser@example.com')
        self.assertTrue(result.is_saml_user)
        self.assertFalse(result.has_usable_password())

    def test_no_auto_create_returns_none_for_unknown_user(self):
        self.saml_config.auto_create_users = False
        self.saml_config.save()

        result = self.view._get_or_create_user(
            self.saml_config, 'ghost', 'ghost@example.com', '', '', 'idp-nameid-3'
        )
        self.assertIsNone(result)

    def test_explicit_link_attaches_to_authenticated_users_own_account(self):
        """The legitimate replacement path: an id proven by SAMLLinkInitView
        (the user was already logged in) may link even a password account."""
        admin = User.objects.create_user(
            email='admin2@example.com', username='admin2',
            password='RealPassword123!', role='administrator',
        )

        result = self.view._get_or_create_user(
            self.saml_config, 'irrelevant', 'irrelevant@example.com', '', '', 'idp-nameid-4',
            link_user_id=admin.id,
        )
        self.assertEqual(result.id, admin.id)
        admin.refresh_from_db()
        self.assertTrue(admin.is_saml_user)
        self.assertEqual(admin.saml_name_id, 'idp-nameid-4')

    def test_explicit_link_refuses_nameid_already_linked_elsewhere(self):
        other = User.objects.create(
            email='other@example.com', username='other',
            is_saml_user=True, saml_name_id='taken-id', is_active=True,
        )
        other.set_unusable_password()
        other.save()
        admin = User.objects.create_user(
            email='admin3@example.com', username='admin3', password='RealPassword123!'
        )

        result = self.view._get_or_create_user(
            self.saml_config, 'admin3', 'admin3@example.com', '', '', 'taken-id',
            link_user_id=admin.id,
        )
        self.assertIsNone(result)
        admin.refresh_from_db()
        self.assertFalse(admin.is_saml_user)


class SAMLLinkInitViewTestCase(APITestCase):
    """Tests for the authenticated account-link token endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='link@example.com', username='linkuser', password='TestPass123!'
        )
        SAMLSettings.objects.create(enabled=True)

    def test_requires_authentication(self):
        response = self.client.post('/api/v1/saml/link-init/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_signed_link_url_for_authenticated_user(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/v1/saml/link-init/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('link_token=', response.data['link_url'])

        # The token must decode back to this user's id and nobody else's.
        from django.core import signing
        from accounts.saml_views import SAML_LINK_SALT
        token = response.data['link_url'].split('link_token=')[1]
        payload = signing.loads(token, salt=SAML_LINK_SALT, max_age=300)
        self.assertEqual(payload['link_user_id'], self.user.id)

    def test_disabled_when_saml_not_enabled(self):
        SAMLSettings.objects.filter(pk=1).update(enabled=False)
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/v1/saml/link-init/')
        self.assertEqual(response.status_code, 503)


class UserCreateSerializerPasswordValidationTestCase(TestCase):
    """Tests for the password-strength-validation fix.

    Neither UserCreateSerializer nor ChangePasswordSerializer used to call
    Django's validate_password(), so settings.AUTH_PASSWORD_VALIDATORS
    (min length, common-password, numeric-only, similarity-to-username/
    email) was configured but never actually enforced on registration or
    admin-created accounts — see UserViewSetTestCase.
    test_change_password_weak_rejected for the change-password half.
    """

    def test_weak_numeric_password_rejected(self):
        from accounts.serializers import UserCreateSerializer

        serializer = UserCreateSerializer(data={
            'email': 'weak@example.com', 'username': 'weakuser', 'password': '12345678',
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('password', serializer.errors)

    def test_password_too_short_rejected(self):
        from accounts.serializers import UserCreateSerializer

        serializer = UserCreateSerializer(data={
            'email': 'short@example.com', 'username': 'shortuser', 'password': 'ab1!',
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('password', serializer.errors)

    def test_password_similar_to_email_rejected(self):
        from accounts.serializers import UserCreateSerializer

        serializer = UserCreateSerializer(data={
            'email': 'similaruser@example.com', 'username': 'similaruser',
            'password': 'similaruser@example.com',
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('password', serializer.errors)

    def test_strong_password_accepted(self):
        from accounts.serializers import UserCreateSerializer

        serializer = UserCreateSerializer(data={
            'email': 'strong@example.com', 'username': 'stronguser',
            'password': 'Xk9#mQ2$vLpZ7!wR',
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)


@override_settings(
    LDAP_ADMIN_GROUPS={'netvault-admins', 'domain admins'},
    LDAP_OPERATOR_GROUPS={'netvault-operators'},
    LDAP_AUDITOR_GROUPS={'netvault-auditors'},
)
class LDAPGroupMappingTestCase(TestCase):
    """Tests for the LDAP role-by-substring-match fix.

    _map_ldap_groups_to_role must match group names *exactly* against the
    configured lists — not substring — so a group that merely contains a
    privileged name as part of a longer, unrelated name can never grant
    that role. This was a real privilege-escalation bug: real AD
    environments accumulate groups like "IT-Administrators-Helpdesk" or
    "Former-Domain-Admins-Readonly" over time.
    """

    def setUp(self):
        from accounts.ldap_backend import NetVaultLDAPBackend
        self.backend = NetVaultLDAPBackend()

    def test_exact_admin_group_grants_administrator(self):
        role = self.backend._map_ldap_groups_to_role(['NetVault-Admins'])
        self.assertEqual(role, 'administrator')

    def test_case_insensitive_exact_match(self):
        role = self.backend._map_ldap_groups_to_role(['NETVAULT-ADMINS'])
        self.assertEqual(role, 'administrator')

    def test_substring_containing_admin_pattern_does_not_escalate(self):
        """The actual bug: a group that merely *contains* 'netvault-admins'
        or 'domain admins' as a substring must NOT grant administrator."""
        role = self.backend._map_ldap_groups_to_role(['IT-Administrators-Helpdesk'])
        self.assertEqual(role, 'viewer')

        role = self.backend._map_ldap_groups_to_role(['Former-Domain-Admins-Readonly'])
        self.assertEqual(role, 'viewer')

        role = self.backend._map_ldap_groups_to_role(['Site-NetVault-Admins-Backup-Viewers'])
        self.assertEqual(role, 'viewer')

    def test_exact_operator_group(self):
        role = self.backend._map_ldap_groups_to_role(['NetVault-Operators'])
        self.assertEqual(role, 'operator')

    def test_exact_auditor_group(self):
        role = self.backend._map_ldap_groups_to_role(['NetVault-Auditors'])
        self.assertEqual(role, 'auditor')

    def test_no_matching_group_defaults_to_viewer(self):
        role = self.backend._map_ldap_groups_to_role(['Some-Other-Group', 'Coffee-Club'])
        self.assertEqual(role, 'viewer')

    def test_empty_groups_defaults_to_viewer(self):
        role = self.backend._map_ldap_groups_to_role([])
        self.assertEqual(role, 'viewer')

    def test_highest_privilege_wins_when_user_in_multiple_groups(self):
        role = self.backend._map_ldap_groups_to_role(['NetVault-Auditors', 'NetVault-Admins'])
        self.assertEqual(role, 'administrator')

    def test_whitespace_around_group_name_still_matches(self):
        role = self.backend._map_ldap_groups_to_role([' NetVault-Admins '])
        self.assertEqual(role, 'administrator')


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


class UserViewSetTestCase(APITestCase):
    """Tests for UserViewSet endpoints"""

    def setUp(self):
        self.client = APIClient()
        User = get_user_model()
        self.admin = User.objects.create_user(
            email='admin@example.com',
            username='admin',
            password='TestPass123!',
            role='administrator'
        )
        self.user = User.objects.create_user(
            email='user@example.com',
            username='testuser',
            password='TestPass123!',
            role='viewer'
        )

    def test_update_profile(self):
        """Test updating own profile"""
        self.client.force_authenticate(user=self.user)
        response = self.client.patch('/api/v1/users/update_profile/', {
            'first_name': 'Updated',
            'last_name': 'Name'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Updated')

    def test_change_password(self):
        """Test changing password"""
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/v1/users/change_password/', {
            'old_password': 'TestPass123!',
            'new_password': 'NewSecurePass456!',
            'new_password_confirm': 'NewSecurePass456!'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewSecurePass456!'))

    def test_change_password_wrong_old(self):
        """Test changing password with wrong old password"""
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/v1/users/change_password/', {
            'old_password': 'WrongPass!',
            'new_password': 'NewPass456!',
            'new_password_confirm': 'NewPass456!'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password_weak_rejected(self):
        """Fix: AUTH_PASSWORD_VALIDATORS (length/common-password/numeric/
        similarity) used to never be enforced here at all."""
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/v1/users/change_password/', {
            'old_password': 'TestPass123!',
            'new_password': '12345678',
            'new_password_confirm': '12345678'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('new_password', response.data)
        self.user.refresh_from_db()
        self.assertFalse(self.user.check_password('12345678'))

    def test_change_password_similar_to_email_rejected(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/v1/users/change_password/', {
            'old_password': 'TestPass123!',
            'new_password': 'user@example.com',
            'new_password_confirm': 'user@example.com'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_users_as_admin(self):
        """Test admin can list all users"""
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/users/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

    def test_list_users_as_viewer(self):
        """Test viewer cannot list all users (permission denied)"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/v1/users/')
        # Viewers don't have CanManageUsers permission
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_enable_2fa(self):
        """Test enabling 2FA"""
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/v1/users/enable_2fa/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('secret', response.data)
        self.assertIn('uri', response.data)


class JWTSigningKeyTestCase(TestCase):
    """Tests for the JWT-signing-key-isolation fix.

    SIMPLE_JWT['SIGNING_KEY'] used to be hardcoded to SECRET_KEY, so any
    leak of SECRET_KEY (which also signs Django sessions, CSRF tokens, and
    password-reset tokens) would let an attacker forge JWTs too. It now
    reads settings.JWT_SIGNING_KEY (falls back to SECRET_KEY only if unset)
    — this confirms that value is what tokens actually get signed with.
    """

    def test_simple_jwt_signing_key_matches_configured_key(self):
        from django.conf import settings
        self.assertEqual(settings.SIMPLE_JWT['SIGNING_KEY'], settings.JWT_SIGNING_KEY)

    def test_issued_token_is_signed_with_configured_key(self):
        import jwt as pyjwt
        from django.conf import settings
        from rest_framework_simplejwt.tokens import RefreshToken

        user = User.objects.create_user(email='jwtkey@example.com', username='jwtkey', password='TestPass123!')
        token = str(RefreshToken.for_user(user).access_token)

        # Decodes cleanly with the configured signing key...
        decoded = pyjwt.decode(token, settings.JWT_SIGNING_KEY, algorithms=[settings.SIMPLE_JWT['ALGORITHM']])
        self.assertEqual(decoded['user_id'], user.id)

        # ...and is rejected with any other key, proving it isn't signed
        # with something unrelated/blank.
        with self.assertRaises(pyjwt.InvalidSignatureError):
            pyjwt.decode(token, 'a-completely-different-key', algorithms=[settings.SIMPLE_JWT['ALGORITHM']])


class AuthLogoutTestCase(APITestCase):
    """Tests for logout functionality"""

    def setUp(self):
        self.client = APIClient()
        User = get_user_model()
        self.user = User.objects.create_user(
            email='logout@example.com',
            username='logoutuser',
            password='TestPass123!'
        )

    def test_logout_authenticated(self):
        """Test logout for authenticated user"""
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/v1/auth/logout/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_logout_unauthenticated(self):
        """Test logout without authentication fails"""
        response = self.client.post('/api/v1/auth/logout/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AuditLogViewSetTestCase(APITestCase):
    """Tests for AuditLog viewset"""

    def setUp(self):
        self.client = APIClient()
        User = get_user_model()
        self.admin = User.objects.create_user(
            email='admin_audit@example.com',
            username='adminaudit',
            password='TestPass123!',
            role='administrator'
        )
        self.auditor = User.objects.create_user(
            email='auditor@example.com',
            username='auditor',
            password='TestPass123!',
            role='auditor'
        )
        self.viewer = User.objects.create_user(
            email='viewer_audit@example.com',
            username='vieweraudit',
            password='TestPass123!',
            role='viewer'
        )
        # Create some audit logs
        AuditLog.objects.create(
            user=self.admin,
            action='login',
            resource_type='User',
            description='Admin logged in'
        )
        AuditLog.objects.create(
            user=self.viewer,
            action='login',
            resource_type='User',
            description='Viewer logged in'
        )

    def test_admin_sees_all_logs(self):
        """Test admin can see all audit logs"""
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/audit-logs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

    def test_auditor_sees_all_logs(self):
        """Test auditor can see all audit logs"""
        self.client.force_authenticate(user=self.auditor)
        response = self.client.get('/api/v1/audit-logs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

    def test_viewer_sees_own_logs(self):
        """Test viewer can only see their own logs"""
        self.client.force_authenticate(user=self.viewer)
        response = self.client.get('/api/v1/audit-logs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)


class PermissionClassesTestCase(TestCase):
    """Tests for permission classes"""

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            email='perm_admin@example.com',
            username='permadmin',
            password='pass123',
            role='administrator'
        )
        self.operator = User.objects.create_user(
            email='perm_op@example.com',
            username='permop',
            password='pass123',
            role='operator'
        )
        self.viewer = User.objects.create_user(
            email='perm_view@example.com',
            username='permview',
            password='pass123',
            role='viewer'
        )
        self.auditor = User.objects.create_user(
            email='perm_audit@example.com',
            username='permaudit',
            password='pass123',
            role='auditor'
        )
        self.superuser = User.objects.create_superuser(
            email='super@example.com',
            username='superuser',
            password='pass123'
        )

    def test_role_based_permission_admin(self):
        """Test RoleBasedPermission for admin"""
        from accounts.permissions import RoleBasedPermission
        from unittest.mock import MagicMock

        perm = RoleBasedPermission()
        request = MagicMock()
        request.user = self.admin
        request.method = 'DELETE'

        self.assertTrue(perm.has_permission(request, None))

    def test_role_based_permission_viewer(self):
        """Test RoleBasedPermission for viewer"""
        from accounts.permissions import RoleBasedPermission
        from unittest.mock import MagicMock

        perm = RoleBasedPermission()
        request = MagicMock()
        request.user = self.viewer
        request.method = 'DELETE'

        self.assertFalse(perm.has_permission(request, None))

    def test_role_based_permission_viewer_get(self):
        """Test RoleBasedPermission for viewer GET"""
        from accounts.permissions import RoleBasedPermission
        from unittest.mock import MagicMock

        perm = RoleBasedPermission()
        request = MagicMock()
        request.user = self.viewer
        request.method = 'GET'

        self.assertTrue(perm.has_permission(request, None))

    def test_is_administrator_permission(self):
        """Test IsAdministrator permission"""
        from accounts.permissions import IsAdministrator
        from unittest.mock import MagicMock

        perm = IsAdministrator()

        request = MagicMock()
        request.user = self.admin
        self.assertTrue(perm.has_permission(request, None))

        request.user = self.viewer
        self.assertFalse(perm.has_permission(request, None))

    def test_is_operator_or_admin_permission(self):
        """Test IsOperatorOrAdmin permission"""
        from accounts.permissions import IsOperatorOrAdmin
        from unittest.mock import MagicMock

        perm = IsOperatorOrAdmin()

        request = MagicMock()
        request.user = self.admin
        self.assertTrue(perm.has_permission(request, None))

        request.user = self.operator
        self.assertTrue(perm.has_permission(request, None))

        request.user = self.viewer
        self.assertFalse(perm.has_permission(request, None))

    def test_superuser_bypass(self):
        """Test superuser bypasses all permissions"""
        from accounts.permissions import RoleBasedPermission
        from unittest.mock import MagicMock

        perm = RoleBasedPermission()
        request = MagicMock()
        request.user = self.superuser
        request.method = 'DELETE'

        self.assertTrue(perm.has_permission(request, None))

    def test_can_manage_devices_operator(self):
        """Test CanManageDevices for operator"""
        from accounts.permissions import CanManageDevices
        from unittest.mock import MagicMock

        perm = CanManageDevices()
        request = MagicMock()
        request.user = self.operator

        request.method = 'POST'
        self.assertTrue(perm.has_permission(request, None))

        request.method = 'DELETE'
        self.assertFalse(perm.has_permission(request, None))

    def test_can_view_audit_logs(self):
        """Test CanViewAuditLogs permission"""
        from accounts.permissions import CanViewAuditLogs
        from unittest.mock import MagicMock

        perm = CanViewAuditLogs()

        request = MagicMock()
        request.user = self.auditor
        self.assertTrue(perm.has_permission(request, None))

        request.user = self.viewer
        request.method = 'GET'
        self.assertTrue(perm.has_permission(request, None))
