"""
Tests for notifications services
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock

from notifications.services import (
    send_email_notification,
    send_telegram_notification,
    notify_backup_success,
    notify_backup_failed,
    notify_multiple_failures,
    notify_device_offline,
    get_current_time
)


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

    @patch('netvault.models.SystemSettings')
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
    @patch('netvault.models.SystemSettings')
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

    @patch('netvault.models.SystemSettings')
    def test_email_send_exception(self, mock_settings):
        """Test handles exception gracefully"""
        mock_settings.get_settings.side_effect = Exception("DB error")

        result = send_email_notification('Test', 'Message')
        self.assertFalse(result)


class SendTelegramNotificationTestCase(TestCase):
    """Tests for Telegram notification service"""

    @patch('netvault.models.SystemSettings')
    def test_telegram_disabled(self, mock_settings):
        """Test returns False when Telegram disabled"""
        mock_settings.get_settings.return_value = MagicMock(
            telegram_enabled=False
        )

        result = send_telegram_notification('Test message')
        self.assertFalse(result)

    @patch('netvault.models.SystemSettings')
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
    @patch('netvault.models.SystemSettings')
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
    @patch('netvault.models.SystemSettings')
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

    @patch('netvault.models.SystemSettings')
    def test_telegram_exception(self, mock_settings):
        """Test handles exception gracefully"""
        mock_settings.get_settings.side_effect = Exception("Connection error")

        result = send_telegram_notification('Test message')
        self.assertFalse(result)


class NotifyBackupSuccessTestCase(TestCase):
    """Tests for backup success notification"""

    @patch('notifications.services.send_telegram_notification')
    @patch('notifications.services.send_email_notification')
    @patch('netvault.models.SystemSettings')
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
    @patch('netvault.models.SystemSettings')
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
    @patch('netvault.models.SystemSettings')
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
    @patch('netvault.models.SystemSettings')
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
