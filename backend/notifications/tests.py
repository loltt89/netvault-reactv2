"""
Tests for notifications services
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch, MagicMock

from notifications.services import (
    send_email_notification,
    send_telegram_notification,
    send_webhook_notification,
    _device_matches_filters,
    dispatch_rules,
    notify_backup_success,
    notify_backup_failed,
    notify_multiple_failures,
    notify_device_offline,
    get_current_time
)
from notifications.models import NotificationRule, Notification
from devices.models import Device, Vendor, DeviceType
from core.crypto import encrypt_data


class GetCurrentTimeTestCase(TestCase):
    """Tests for get_current_time utility"""

    def test_returns_formatted_string(self):
        """Test get_current_time returns properly formatted string"""
        result = get_current_time()
        self.assertIsInstance(result, str)
        # Should be YYYY-MM-DD HH:MM:SS format
        self.assertRegex(result, r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}')


class SendEmailNotificationTestCase(TestCase):
    """Tests for email notification service"""

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            email='admin_notify@example.com',
            username='adminnotify',
            password='pass123',
            role='administrator'
        )

    @patch('core.models.SystemSettings')
    def test_email_not_configured(self, mock_settings):
        """Test returns False when email not configured"""
        mock_settings.get_settings.return_value = MagicMock(
            email_host='',
            email_host_user=''
        )

        result = send_email_notification('Test', 'Message')
        self.assertFalse(result)

    @patch('notifications.services.EmailBackend')
    @patch('notifications.services.EmailMessage')
    @patch('core.models.SystemSettings')
    def test_email_send_success(self, mock_settings, mock_email, mock_backend):
        """Test successful email sending"""
        mock_settings.get_settings.return_value = MagicMock(
            email_host='smtp.example.com',
            email_host_user='user@example.com',
            email_port=587,
            email_use_tls=True,
            email_from_address='noreply@example.com',
            get_email_password=MagicMock(return_value='password')
        )
        mock_email_instance = MagicMock()
        mock_email.return_value = mock_email_instance

        result = send_email_notification('Test Subject', 'Test Message', ['test@example.com'])

        self.assertTrue(result)
        mock_email_instance.send.assert_called_once()

    @patch('core.models.SystemSettings')
    def test_email_send_exception(self, mock_settings):
        """Test handles exception gracefully"""
        mock_settings.get_settings.side_effect = Exception("DB error")

        result = send_email_notification('Test', 'Message')
        self.assertFalse(result)


class SendTelegramNotificationTestCase(TestCase):
    """Tests for Telegram notification service"""

    @patch('core.models.SystemSettings')
    def test_telegram_disabled(self, mock_settings):
        """Test returns False when Telegram disabled"""
        mock_settings.get_settings.return_value = MagicMock(
            telegram_enabled=False
        )

        result = send_telegram_notification('Test message')
        self.assertFalse(result)

    @patch('core.models.SystemSettings')
    def test_telegram_not_configured(self, mock_settings):
        """Test returns False when Telegram not configured"""
        mock_settings.get_settings.return_value = MagicMock(
            telegram_enabled=True,
            telegram_chat_id='',
            get_telegram_bot_token=MagicMock(return_value='')
        )

        result = send_telegram_notification('Test message')
        self.assertFalse(result)

    @patch('notifications.services.requests')
    @patch('core.models.SystemSettings')
    def test_telegram_send_success(self, mock_settings, mock_requests):
        """Test successful Telegram sending"""
        mock_settings.get_settings.return_value = MagicMock(
            telegram_enabled=True,
            telegram_chat_id='123456',
            get_telegram_bot_token=MagicMock(return_value='bot_token_123')
        )
        mock_requests.post.return_value = MagicMock(status_code=200)

        result = send_telegram_notification('Test message')

        self.assertTrue(result)
        mock_requests.post.assert_called_once()

    @patch('notifications.services.requests')
    @patch('core.models.SystemSettings')
    def test_telegram_api_error(self, mock_settings, mock_requests):
        """Test handles Telegram API error"""
        mock_settings.get_settings.return_value = MagicMock(
            telegram_enabled=True,
            telegram_chat_id='123456',
            get_telegram_bot_token=MagicMock(return_value='bot_token_123')
        )
        mock_requests.post.return_value = MagicMock(status_code=400, text='Bad Request')

        result = send_telegram_notification('Test message')
        self.assertFalse(result)

    @patch('core.models.SystemSettings')
    def test_telegram_exception(self, mock_settings):
        """Test handles exception gracefully"""
        mock_settings.get_settings.side_effect = Exception("Connection error")

        result = send_telegram_notification('Test message')
        self.assertFalse(result)


class NotifyBackupSuccessTestCase(TestCase):
    """Tests for backup success notification"""

    @patch('notifications.services.send_telegram_notification')
    @patch('notifications.services.send_email_notification')
    @patch('core.models.SystemSettings')
    def test_notification_disabled(self, mock_settings, mock_email, mock_telegram):
        """Test no notification when disabled"""
        mock_settings.get_settings.return_value = MagicMock(
            notify_on_backup_success=False
        )

        notify_backup_success('Device-1', 123, 1024, True)

        mock_email.assert_not_called()
        mock_telegram.assert_not_called()

    @patch('notifications.services.send_telegram_notification')
    @patch('notifications.services.send_email_notification')
    @patch('core.models.SystemSettings')
    def test_notification_enabled(self, mock_settings, mock_email, mock_telegram):
        """Test sends notification when enabled"""
        mock_settings.get_settings.return_value = MagicMock(
            notify_on_backup_success=True
        )

        notify_backup_success('Device-1', 123, 2048, True)

        mock_email.assert_called_once()
        mock_telegram.assert_called_once()


class NotifyBackupFailedTestCase(TestCase):
    """Tests for backup failure notification"""

    @patch('notifications.services.send_telegram_notification')
    @patch('notifications.services.send_email_notification')
    @patch('core.models.SystemSettings')
    def test_notification_disabled(self, mock_settings, mock_email, mock_telegram):
        """Test no notification when disabled"""
        mock_settings.get_settings.return_value = MagicMock(
            notify_on_backup_failure=False
        )

        notify_backup_failed('Device-1', 'Connection timeout')

        mock_email.assert_not_called()
        mock_telegram.assert_not_called()

    @patch('notifications.services.send_telegram_notification')
    @patch('notifications.services.send_email_notification')
    @patch('core.models.SystemSettings')
    def test_notification_enabled(self, mock_settings, mock_email, mock_telegram):
        """Test sends notification when enabled"""
        mock_settings.get_settings.return_value = MagicMock(
            notify_on_backup_failure=True
        )

        notify_backup_failed('Device-1', 'Connection timeout', 456)

        mock_email.assert_called_once()
        mock_telegram.assert_called_once()


class NotifyMultipleFailuresTestCase(TestCase):
    """Tests for multiple failures notification"""

    @patch('notifications.services.send_telegram_notification')
    @patch('notifications.services.send_email_notification')
    def test_sends_notifications(self, mock_email, mock_telegram):
        """Test sends both email and Telegram"""
        notify_multiple_failures(3, 10)

        mock_email.assert_called_once()
        mock_telegram.assert_called_once()

        # Check message contains counts
        call_args = mock_email.call_args[0]
        self.assertIn('3', call_args[0])  # subject
        self.assertIn('10', call_args[0])  # subject


class NotifyDeviceOfflineTestCase(TestCase):
    """Tests for device offline notification"""

    @patch('notifications.services.send_telegram_notification')
    @patch('notifications.services.send_email_notification')
    def test_sends_notifications(self, mock_email, mock_telegram):
        """Test sends both email and Telegram"""
        notify_device_offline('Core-Router', '2024-01-15 10:30:00')

        mock_email.assert_called_once()
        mock_telegram.assert_called_once()

        # Check device name in subject
        call_args = mock_email.call_args[0]
        self.assertIn('Core-Router', call_args[0])


class SendWebhookNotificationTestCase(TestCase):
    """Tests for the webhook delivery channel"""

    def test_no_url_returns_false(self):
        self.assertFalse(send_webhook_notification('', {'a': 1}))

    @patch('notifications.services.requests')
    def test_success_2xx(self, mock_requests):
        mock_requests.post.return_value = MagicMock(status_code=200)
        result = send_webhook_notification('https://example.com/hook', {'a': 1})
        self.assertTrue(result)
        mock_requests.post.assert_called_once_with(
            'https://example.com/hook', json={'a': 1}, timeout=10
        )

    @patch('notifications.services.requests')
    def test_non_2xx_returns_false(self, mock_requests):
        mock_requests.post.return_value = MagicMock(status_code=500, text='boom')
        result = send_webhook_notification('https://example.com/hook', {'a': 1})
        self.assertFalse(result)

    @patch('notifications.services.requests')
    def test_exception_returns_false(self, mock_requests):
        mock_requests.post.side_effect = Exception('network error')
        result = send_webhook_notification('https://example.com/hook', {'a': 1})
        self.assertFalse(result)


class DeviceMatchesFiltersTestCase(TestCase):
    """Tests for NotificationRule.device_filters matching"""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email='filtertest@example.com', username='filtertest', password='pass123',
        )
        self.vendor = Vendor.objects.create(name='Cisco', slug='cisco-notif')
        self.device_type = DeviceType.objects.create(name='Router', slug='router-notif')
        self.device = Device.objects.create(
            name='Core-SW', ip_address='10.0.0.1', vendor=self.vendor,
            device_type=self.device_type, username='admin',
            password_encrypted=encrypt_data('pw'), created_by=self.user,
            tags=['core', 'datacenter'], criticality='critical', location='DC1',
        )

    def test_no_filters_always_matches(self):
        self.assertTrue(_device_matches_filters(self.device, {}))
        self.assertTrue(_device_matches_filters(self.device, None))

    def test_none_device_fails_when_filters_present(self):
        self.assertFalse(_device_matches_filters(None, {'tags': ['core']}))

    def test_tag_overlap_matches(self):
        self.assertTrue(_device_matches_filters(self.device, {'tags': ['core', 'edge']}))

    def test_tag_no_overlap_fails(self):
        self.assertFalse(_device_matches_filters(self.device, {'tags': ['edge']}))

    def test_criticality_single_value(self):
        self.assertTrue(_device_matches_filters(self.device, {'criticality': 'critical'}))
        self.assertFalse(_device_matches_filters(self.device, {'criticality': 'low'}))

    def test_criticality_list_value(self):
        self.assertTrue(_device_matches_filters(self.device, {'criticality': ['high', 'critical']}))

    def test_vendor_id_filter(self):
        self.assertTrue(_device_matches_filters(self.device, {'vendor_id': self.vendor.id}))
        self.assertFalse(_device_matches_filters(self.device, {'vendor_id': self.vendor.id + 999}))

    def test_unknown_key_ignored_not_excluded(self):
        self.assertTrue(_device_matches_filters(self.device, {'nonsense_key': 'whatever'}))

    def test_combined_filters_all_must_match(self):
        self.assertTrue(_device_matches_filters(
            self.device, {'tags': ['core'], 'criticality': 'critical', 'location': 'DC1'}
        ))
        self.assertFalse(_device_matches_filters(
            self.device, {'tags': ['core'], 'location': 'DC2'}
        ))


class DispatchRulesTestCase(TestCase):
    """Tests for the NotificationRule fan-out + Notification audit log"""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email='dispatchtest@example.com', username='dispatchtest', password='pass123',
        )
        self.vendor = Vendor.objects.create(name='Cisco', slug='cisco-dispatch')
        self.device_type = DeviceType.objects.create(name='Router', slug='router-dispatch')
        self.device = Device.objects.create(
            name='Edge-Router', ip_address='10.0.0.2', vendor=self.vendor,
            device_type=self.device_type, username='admin',
            password_encrypted=encrypt_data('pw'), created_by=self.user, tags=['edge'],
        )

    @patch('notifications.services.send_webhook_notification', return_value=True)
    def test_matching_webhook_rule_fires_and_logs_sent(self, mock_webhook):
        rule = NotificationRule.objects.create(
            name='Edge webhook', trigger='backup_failed', channel='webhook',
            webhook_url='https://example.com/hook', device_filters={'tags': ['edge']},
        )

        dispatch_rules('backup_failed', device=self.device, subject='S', message='M')

        mock_webhook.assert_called_once()
        notif = Notification.objects.get(rule=rule)
        self.assertEqual(notif.status, 'sent')
        self.assertEqual(notif.channel, 'webhook')
        self.assertIsNotNone(notif.sent_at)

    @patch('notifications.services.send_webhook_notification', return_value=False)
    def test_failed_delivery_logs_failed_status(self, mock_webhook):
        rule = NotificationRule.objects.create(
            name='Edge webhook', trigger='backup_failed', channel='webhook',
            webhook_url='https://example.com/hook',
        )

        dispatch_rules('backup_failed', device=self.device, subject='S', message='M')

        notif = Notification.objects.get(rule=rule)
        self.assertEqual(notif.status, 'failed')
        self.assertIsNone(notif.sent_at)
        self.assertTrue(notif.error_message)

    @patch('notifications.services.send_webhook_notification')
    def test_non_matching_device_filter_skips_rule(self, mock_webhook):
        NotificationRule.objects.create(
            name='DC-only webhook', trigger='backup_failed', channel='webhook',
            webhook_url='https://example.com/hook', device_filters={'tags': ['datacenter']},
        )

        dispatch_rules('backup_failed', device=self.device, subject='S', message='M')

        mock_webhook.assert_not_called()
        self.assertEqual(Notification.objects.count(), 0)

    @patch('notifications.services.send_webhook_notification', return_value=True)
    def test_inactive_rule_never_fires(self, mock_webhook):
        NotificationRule.objects.create(
            name='Disabled rule', trigger='backup_failed', channel='webhook',
            webhook_url='https://example.com/hook', is_active=False,
        )

        dispatch_rules('backup_failed', device=self.device, subject='S', message='M')

        mock_webhook.assert_not_called()
        self.assertEqual(Notification.objects.count(), 0)

    @patch('notifications.services.send_webhook_notification', return_value=True)
    def test_different_trigger_does_not_fire(self, mock_webhook):
        NotificationRule.objects.create(
            name='Success only', trigger='backup_success', channel='webhook',
            webhook_url='https://example.com/hook',
        )

        dispatch_rules('backup_failed', device=self.device, subject='S', message='M')

        mock_webhook.assert_not_called()

    @patch('notifications.services.send_telegram_notification', return_value=True)
    def test_telegram_rule_uses_per_rule_chat_ids_not_global(self, mock_telegram):
        NotificationRule.objects.create(
            name='Ops telegram', trigger='backup_failed', channel='telegram',
            telegram_chat_ids=['111', '222'],
        )

        dispatch_rules('backup_failed', device=self.device, subject='S', message='M',
                        telegram_message='hi')

        self.assertEqual(mock_telegram.call_count, 2)
        called_chat_ids = {call.kwargs.get('chat_id') for call in mock_telegram.call_args_list}
        self.assertEqual(called_chat_ids, {'111', '222'})

    def test_end_to_end_backup_failed_creates_notification(self):
        """notify_backup_failed() -> dispatch_rules() -> Notification, no mocking of the chain itself."""
        rule = NotificationRule.objects.create(
            name='Any backup failure', trigger='backup_failed', channel='webhook',
            webhook_url='https://example.com/hook',
        )

        with patch('notifications.services.send_webhook_notification', return_value=True) as mock_webhook, \
             patch('notifications.services.send_email_notification'), \
             patch('notifications.services.send_telegram_notification'), \
             patch('core.models.SystemSettings') as mock_settings:
            mock_settings.get_settings.return_value = MagicMock(notify_on_backup_failure=False)
            notify_backup_failed('Edge-Router', 'timeout', backup_id=1, device=self.device)

        mock_webhook.assert_called_once()
        self.assertTrue(Notification.objects.filter(rule=rule, status='sent').exists())


class NotificationRuleViewSetTestCase(APITestCase):
    """API tests for NotificationRule CRUD — administrator-only"""

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            email='ruleadmin@example.com', username='ruleadmin',
            password='TestPass123!', role='administrator',
        )
        self.operator = User.objects.create_user(
            email='ruleoperator@example.com', username='ruleoperator',
            password='TestPass123!', role='operator',
        )

    def test_operator_cannot_list_rules(self):
        self.client.force_authenticate(user=self.operator)
        response = self.client.get('/api/v1/notifications/rules/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_create_rule(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/v1/notifications/rules/', {
            'name': 'Critical failures to Slack',
            'trigger': 'backup_failed',
            'channel': 'webhook',
            'webhook_url': 'https://hooks.example.com/x',
            'device_filters': {'criticality': ['critical']},
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        rule = NotificationRule.objects.get(name='Critical failures to Slack')
        self.assertEqual(rule.created_by, self.admin)

    def test_webhook_channel_requires_webhook_url(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/v1/notifications/rules/', {
            'name': 'Missing URL',
            'trigger': 'backup_failed',
            'channel': 'webhook',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('webhook_url', response.data)

    def test_admin_can_delete_rule(self):
        rule = NotificationRule.objects.create(
            name='To delete', trigger='backup_failed', channel='webhook',
            webhook_url='https://example.com/hook',
        )
        self.client.force_authenticate(user=self.admin)
        response = self.client.delete(f'/api/v1/notifications/rules/{rule.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(NotificationRule.objects.filter(id=rule.id).exists())


class NotificationLogViewSetTestCase(APITestCase):
    """API tests for the read-only Notification send-log endpoint"""

    def setUp(self):
        User = get_user_model()
        self.viewer = User.objects.create_user(
            email='logviewer@example.com', username='logviewer',
            password='TestPass123!', role='viewer',
        )
        self.auditor = User.objects.create_user(
            email='logauditor@example.com', username='logauditor',
            password='TestPass123!', role='auditor',
        )
        rule = NotificationRule.objects.create(
            name='Some rule', trigger='backup_failed', channel='webhook',
            webhook_url='https://example.com/hook',
        )
        Notification.objects.create(
            rule=rule, status='sent', title='T', message='M',
            channel='webhook', recipient='https://example.com/hook',
        )

    def test_viewer_forbidden(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.get('/api/v1/notifications/log/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_auditor_can_read(self):
        self.client.force_authenticate(user=self.auditor)
        response = self.client.get('/api/v1/notifications/log/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
