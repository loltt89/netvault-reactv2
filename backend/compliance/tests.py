"""
Tests for the compliance app: policy evaluation engine + API.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status

from compliance.models import CompliancePolicy, ComplianceViolation
from compliance.services import evaluate_backup_compliance, _rule_passes
from devices.models import Device, Vendor, DeviceType
from backups.models import Backup
from core.crypto import encrypt_data


class RulePassesTestCase(TestCase):
    """Tests for the low-level single-rule matcher"""

    def test_must_contain_passes_when_present(self):
        self.assertTrue(_rule_passes('ntp server 10.0.0.1', {
            'type': 'must_contain', 'pattern': 'ntp server',
        }))

    def test_must_contain_fails_when_absent(self):
        self.assertFalse(_rule_passes('hostname Router1', {
            'type': 'must_contain', 'pattern': 'ntp server',
        }))

    def test_must_not_contain_passes_when_absent(self):
        self.assertTrue(_rule_passes('hostname Router1', {
            'type': 'must_not_contain', 'pattern': 'transport input telnet',
        }))

    def test_must_not_contain_fails_when_present(self):
        self.assertFalse(_rule_passes('line vty 0 4\n transport input telnet', {
            'type': 'must_not_contain', 'pattern': 'transport input telnet',
        }))

    def test_regex_rule(self):
        self.assertFalse(_rule_passes('snmp-server community public RO', {
            'type': 'must_not_contain', 'pattern': r'community\s+public',
            'is_regex': True,
        }))
        self.assertTrue(_rule_passes('snmp-server community S3cr3t RO', {
            'type': 'must_not_contain', 'pattern': r'community\s+public',
            'is_regex': True,
        }))

    def test_invalid_regex_fails_safe_to_pass(self):
        self.assertTrue(_rule_passes('anything', {
            'type': 'must_not_contain', 'pattern': '(unclosed',
            'is_regex': True,
        }))

    def test_unknown_type_fails_safe_to_pass(self):
        self.assertTrue(_rule_passes('anything', {
            'type': 'nonsense', 'pattern': 'x',
        }))

    def test_empty_pattern_passes(self):
        self.assertTrue(_rule_passes('anything', {'type': 'must_contain', 'pattern': ''}))


class EvaluateBackupComplianceTestCase(TestCase):
    """Tests for the policy evaluation + violation reconciliation engine"""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email='compliance_eval@example.com', username='compliance_eval', password='pass123',
        )
        self.vendor = Vendor.objects.create(name='Cisco', slug='cisco-compliance')
        self.device_type = DeviceType.objects.create(name='Router', slug='router-compliance')
        self.device = Device.objects.create(
            name='Compliance-Dev', ip_address='10.6.0.1', vendor=self.vendor,
            device_type=self.device_type, username='admin',
            password_encrypted=encrypt_data('pw'), created_by=self.user, tags=['core'],
        )

    def _make_backup(self, config_text):
        backup = Backup.objects.create(
            device=self.device, status='success', success=True,
            configuration_hash='h', size_bytes=len(config_text),
        )
        backup.set_configuration(config_text)
        backup.save()
        return backup

    def test_failing_rule_creates_open_violation(self):
        policy = CompliancePolicy.objects.create(
            name='No telnet', rules=[
                {'type': 'must_not_contain', 'pattern': 'transport input telnet',
                 'description': 'Telnet must be disabled'},
            ],
        )
        backup = self._make_backup('line vty 0 4\n transport input telnet\n')

        evaluate_backup_compliance(backup)

        violation = ComplianceViolation.objects.get(policy=policy, device=self.device, rule_index=0)
        self.assertEqual(violation.status, 'open')
        self.assertEqual(violation.backup, backup)

    def test_passing_rule_creates_no_violation(self):
        policy = CompliancePolicy.objects.create(
            name='No telnet', rules=[
                {'type': 'must_not_contain', 'pattern': 'transport input telnet'},
            ],
        )
        backup = self._make_backup('line vty 0 4\n transport input ssh\n')

        evaluate_backup_compliance(backup)

        self.assertFalse(ComplianceViolation.objects.filter(policy=policy).exists())

    def test_fixed_violation_auto_resolves_on_next_backup(self):
        policy = CompliancePolicy.objects.create(
            name='No telnet', rules=[{'type': 'must_not_contain', 'pattern': 'telnet'}],
        )
        bad_backup = self._make_backup('transport input telnet')
        evaluate_backup_compliance(bad_backup)
        violation = ComplianceViolation.objects.get(policy=policy, device=self.device, rule_index=0)
        self.assertEqual(violation.status, 'open')

        good_backup = self._make_backup('transport input ssh')
        evaluate_backup_compliance(good_backup)

        violation.refresh_from_db()
        self.assertEqual(violation.status, 'resolved')
        self.assertIsNotNone(violation.resolved_at)

    def test_reoccurring_violation_reopens_existing_row_not_duplicate(self):
        policy = CompliancePolicy.objects.create(
            name='No telnet', rules=[{'type': 'must_not_contain', 'pattern': 'telnet'}],
        )
        evaluate_backup_compliance(self._make_backup('transport input telnet'))
        evaluate_backup_compliance(self._make_backup('transport input ssh'))
        evaluate_backup_compliance(self._make_backup('transport input telnet'))

        self.assertEqual(
            ComplianceViolation.objects.filter(policy=policy, device=self.device, rule_index=0).count(), 1,
        )
        violation = ComplianceViolation.objects.get(policy=policy, device=self.device, rule_index=0)
        self.assertEqual(violation.status, 'open')

    def test_inactive_policy_not_evaluated(self):
        CompliancePolicy.objects.create(
            name='Inactive', is_active=False,
            rules=[{'type': 'must_not_contain', 'pattern': 'telnet'}],
        )
        backup = self._make_backup('transport input telnet')
        evaluate_backup_compliance(backup)
        self.assertFalse(ComplianceViolation.objects.exists())

    def test_device_filters_excludes_non_matching_device(self):
        CompliancePolicy.objects.create(
            name='Edge only', device_filters={'tags': ['edge']},
            rules=[{'type': 'must_not_contain', 'pattern': 'telnet'}],
        )
        # self.device is tagged 'core', not 'edge'
        backup = self._make_backup('transport input telnet')
        evaluate_backup_compliance(backup)
        self.assertFalse(ComplianceViolation.objects.exists())

    def test_multiple_rules_independently_tracked(self):
        policy = CompliancePolicy.objects.create(
            name='Multi', rules=[
                {'type': 'must_not_contain', 'pattern': 'telnet'},
                {'type': 'must_contain', 'pattern': 'ntp server'},
            ],
        )
        backup = self._make_backup('transport input telnet\nhostname R1')

        evaluate_backup_compliance(backup)

        violations = ComplianceViolation.objects.filter(policy=policy, device=self.device)
        self.assertEqual(violations.count(), 2)
        self.assertEqual(set(violations.values_list('rule_index', flat=True)), {0, 1})


class CompliancePolicyAPITestCase(APITestCase):
    """API tests for CompliancePolicyViewSet — admin-only CRUD"""

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            email='policy_admin@example.com', username='policy_admin',
            password='TestPass123!', role='administrator',
        )
        self.operator = User.objects.create_user(
            email='policy_operator@example.com', username='policy_operator',
            password='TestPass123!', role='operator',
        )

    def test_operator_cannot_create_policy(self):
        self.client.force_authenticate(user=self.operator)
        response = self.client.post('/api/v1/compliance/policies/', {
            'name': 'X', 'rules': [{'type': 'must_contain', 'pattern': 'x'}],
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_create_policy(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/v1/compliance/policies/', {
            'name': 'No Telnet', 'severity': 'high',
            'device_filters': {'criticality': ['critical']},
            'rules': [{'type': 'must_not_contain', 'pattern': 'telnet', 'description': 'no telnet'}],
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(CompliancePolicy.objects.get(name='No Telnet').created_by, self.admin)

    def test_empty_rules_rejected(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/v1/compliance/policies/', {
            'name': 'Empty', 'rules': [],
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_rule_type_rejected(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/v1/compliance/policies/', {
            'name': 'Bad type', 'rules': [{'type': 'nonsense', 'pattern': 'x'}],
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_regex_rejected(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/v1/compliance/policies/', {
            'name': 'Bad regex',
            'rules': [{'type': 'must_contain', 'pattern': '(unclosed', 'is_regex': True}],
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ComplianceViolationAPITestCase(APITestCase):
    """API tests for ComplianceViolationViewSet — read + acknowledge + scoping"""

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            email='violation_admin@example.com', username='violation_admin',
            password='TestPass123!', role='administrator',
        )
        self.viewer = User.objects.create_user(
            email='violation_viewer@example.com', username='violation_viewer',
            password='TestPass123!', role='viewer',
        )
        self.scoped_viewer = User.objects.create_user(
            email='violation_scoped@example.com', username='violation_scoped',
            password='TestPass123!', role='viewer', device_scope={'tags': ['core']},
        )

        self.vendor = Vendor.objects.create(name='Cisco', slug='cisco-violation-api')
        self.device_type = DeviceType.objects.create(name='Router', slug='router-violation-api')
        self.core_device = Device.objects.create(
            name='Core-V', ip_address='10.7.0.1', vendor=self.vendor,
            device_type=self.device_type, username='admin',
            password_encrypted=encrypt_data('pw'), created_by=self.admin, tags=['core'],
        )
        self.edge_device = Device.objects.create(
            name='Edge-V', ip_address='10.7.0.2', vendor=self.vendor,
            device_type=self.device_type, username='admin',
            password_encrypted=encrypt_data('pw'), created_by=self.admin, tags=['edge'],
        )

        self.policy = CompliancePolicy.objects.create(
            name='No telnet', severity='high',
            rules=[{'type': 'must_not_contain', 'pattern': 'telnet'}],
        )
        self.core_violation = ComplianceViolation.objects.create(
            policy=self.policy, device=self.core_device, rule_index=0,
            rule_description='no telnet', status='open',
        )
        self.edge_violation = ComplianceViolation.objects.create(
            policy=self.policy, device=self.edge_device, rule_index=0,
            rule_description='no telnet', status='open',
        )

    def test_viewer_can_list_violations(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.get('/api/v1/compliance/violations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)

    def test_scoped_viewer_only_sees_in_scope_violations(self):
        self.client.force_authenticate(user=self.scoped_viewer)
        response = self.client.get('/api/v1/compliance/violations/')
        ids = {v['id'] for v in response.data['results']}
        self.assertEqual(ids, {self.core_violation.id})

    def test_statistics_endpoint(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/compliance/violations/statistics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['open_total'], 2)
        self.assertEqual(response.data['by_severity']['high'], 2)
        self.assertEqual(response.data['affected_devices'], 2)

    def test_operator_can_acknowledge(self):
        User = get_user_model()
        operator = User.objects.create_user(
            email='ack_operator@example.com', username='ack_operator',
            password='TestPass123!', role='operator',
        )
        self.client.force_authenticate(user=operator)
        response = self.client.post(f'/api/v1/compliance/violations/{self.core_violation.id}/acknowledge/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.core_violation.refresh_from_db()
        self.assertEqual(self.core_violation.status, 'resolved')

    def test_viewer_cannot_acknowledge(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.post(f'/api/v1/compliance/violations/{self.core_violation.id}/acknowledge/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
