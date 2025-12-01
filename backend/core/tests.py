"""
Tests for core module - DeviceLock and utilities
"""
from django.test import TestCase, override_settings
from unittest.mock import patch, MagicMock
import redis

from core.redis_lock import DeviceLock, DeviceLockError
from core.utils import validate_csv_safe, sanitize_csv_value
from core.crypto import encrypt_data, decrypt_data


class DeviceLockTestCase(TestCase):
    """Tests for DeviceLock distributed locking mechanism"""

    def setUp(self):
        """Set up test fixtures"""
        self.device_id = 123
        self.operation = 'backup'

    @patch('core.redis_lock.redis.from_url')
    def test_acquire_lock_success(self, mock_redis):
        """Test successful lock acquisition"""
        mock_client = MagicMock()
        mock_client.set.return_value = True
        mock_redis.return_value = mock_client

        lock = DeviceLock(device_id=self.device_id, operation=self.operation)
        result = lock.acquire()

        self.assertTrue(result)
        self.assertTrue(lock.acquired)
        mock_client.set.assert_called_once()
        # Verify SET NX EX was used
        call_kwargs = mock_client.set.call_args[1]
        self.assertTrue(call_kwargs.get('nx'))
        self.assertIsNotNone(call_kwargs.get('ex'))

    @patch('core.redis_lock.redis.from_url')
    def test_acquire_lock_already_locked(self, mock_redis):
        """Test lock acquisition when device is already locked"""
        mock_client = MagicMock()
        mock_client.set.return_value = False  # Lock not acquired
        mock_redis.return_value = mock_client

        lock = DeviceLock(device_id=self.device_id, operation=self.operation, blocking=False)
        result = lock.acquire()

        self.assertFalse(result)
        self.assertFalse(lock.acquired)

    @patch('core.redis_lock.redis.from_url')
    def test_release_lock_success(self, mock_redis):
        """Test successful lock release"""
        mock_client = MagicMock()
        mock_client.set.return_value = True
        mock_client.eval.return_value = 1  # Lock released
        mock_redis.return_value = mock_client

        lock = DeviceLock(device_id=self.device_id, operation=self.operation)
        lock.acquire()
        result = lock.release()

        self.assertTrue(result)
        self.assertFalse(lock.acquired)
        mock_client.eval.assert_called_once()

    @patch('core.redis_lock.redis.from_url')
    def test_release_lock_not_owned(self, mock_redis):
        """Test release when lock is not owned (expired or stolen)"""
        mock_client = MagicMock()
        mock_client.set.return_value = True
        mock_client.eval.return_value = 0  # Lock not released (token mismatch)
        mock_redis.return_value = mock_client

        lock = DeviceLock(device_id=self.device_id, operation=self.operation)
        lock.acquire()
        result = lock.release()

        self.assertFalse(result)

    @patch('core.redis_lock.redis.from_url')
    def test_context_manager_success(self, mock_redis):
        """Test lock works as context manager"""
        mock_client = MagicMock()
        mock_client.set.return_value = True
        mock_client.eval.return_value = 1
        mock_redis.return_value = mock_client

        with DeviceLock(device_id=self.device_id, operation=self.operation) as lock:
            self.assertTrue(lock.acquired)

        # After exiting context, lock should be released
        mock_client.eval.assert_called_once()

    @patch('core.redis_lock.redis.from_url')
    def test_context_manager_lock_failure(self, mock_redis):
        """Test context manager raises exception when lock fails"""
        mock_client = MagicMock()
        mock_client.set.return_value = False  # Lock not acquired
        mock_redis.return_value = mock_client

        with self.assertRaises(DeviceLockError):
            with DeviceLock(device_id=self.device_id, operation=self.operation):
                pass

    @patch('core.redis_lock.redis.from_url')
    def test_lock_key_format(self, mock_redis):
        """Test lock key is correctly formatted"""
        mock_client = MagicMock()
        mock_client.set.return_value = True
        mock_redis.return_value = mock_client

        lock = DeviceLock(device_id=self.device_id, operation=self.operation)

        self.assertEqual(lock.lock_key, f'device_lock:{self.device_id}')

    @patch('core.redis_lock.redis.from_url')
    def test_unique_token_per_lock(self, mock_redis):
        """Test each lock instance has unique token"""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client

        lock1 = DeviceLock(device_id=self.device_id, operation=self.operation)
        lock2 = DeviceLock(device_id=self.device_id, operation=self.operation)

        self.assertNotEqual(lock1.token, lock2.token)

    @patch('core.redis_lock.redis.from_url')
    def test_extend_lock_success(self, mock_redis):
        """Test extending lock TTL"""
        mock_client = MagicMock()
        mock_client.set.return_value = True
        mock_client.get.return_value = None  # Will be set to lock.token
        mock_redis.return_value = mock_client

        lock = DeviceLock(device_id=self.device_id, operation=self.operation)
        lock.acquire()

        # Mock get to return our token
        mock_client.get.return_value = lock.token

        result = lock.extend(additional_ttl=60)

        self.assertTrue(result)
        mock_client.expire.assert_called_once()


class CSVSafetyTestCase(TestCase):
    """Tests for CSV formula injection protection"""

    def test_validate_csv_safe_normal_value(self):
        """Test normal values pass validation"""
        safe_values = ['Hello', 'Device-1', '192.168.1.1', 'user@example.com']
        for value in safe_values:
            result = validate_csv_safe(value)
            self.assertEqual(result, value)

    def test_validate_csv_safe_dangerous_chars(self):
        """Test dangerous characters are rejected"""
        dangerous_values = ['=CMD|calc|', '+1-234-567', '-test', '@import', '\tvalue', '\rvalue']
        for value in dangerous_values:
            with self.assertRaises(ValueError):
                validate_csv_safe(value, field_name='Test')

    def test_validate_csv_safe_space_bypass_prevention(self):
        """Test that leading spaces don't bypass protection"""
        # Values with leading spaces followed by dangerous chars
        bypass_attempts = ['  =CMD', ' +formula', '   -test', '  @import']
        for value in bypass_attempts:
            with self.assertRaises(ValueError):
                validate_csv_safe(value, field_name='Test')

    def test_sanitize_csv_value_normal(self):
        """Test normal values are not modified"""
        value = 'Normal text'
        result = sanitize_csv_value(value)
        self.assertEqual(result, value)

    def test_sanitize_csv_value_dangerous(self):
        """Test dangerous values get single quote prefix"""
        dangerous = '=1+1'
        result = sanitize_csv_value(dangerous)
        self.assertEqual(result, "'" + dangerous)

    def test_sanitize_csv_value_space_bypass(self):
        """Test space bypass is prevented"""
        bypass = '  =formula'
        result = sanitize_csv_value(bypass)
        self.assertEqual(result, "'" + bypass)


class CryptoTestCase(TestCase):
    """Tests for encryption/decryption utilities"""

    def test_encrypt_decrypt_roundtrip(self):
        """Test data can be encrypted and decrypted"""
        original = 'SuperSecretPassword123!'
        encrypted = encrypt_data(original)
        decrypted = decrypt_data(encrypted)

        self.assertEqual(original, decrypted)
        self.assertNotEqual(original, encrypted)

    def test_encrypted_data_is_different(self):
        """Test same data produces different ciphertext (due to IV)"""
        data = 'TestPassword'
        encrypted1 = encrypt_data(data)
        encrypted2 = encrypt_data(data)

        # Fernet uses random IV, so ciphertexts should differ
        self.assertNotEqual(encrypted1, encrypted2)

    def test_decrypt_invalid_data(self):
        """Test decryption of invalid data raises exception"""
        with self.assertRaises(Exception):
            decrypt_data('invalid_encrypted_data')

    def test_empty_string_encryption(self):
        """Test empty string can be encrypted/decrypted"""
        original = ''
        encrypted = encrypt_data(original)
        decrypted = decrypt_data(encrypted)

        self.assertEqual(original, decrypted)

    def test_unicode_encryption(self):
        """Test unicode data can be encrypted/decrypted"""
        original = 'Пароль123!密码'
        encrypted = encrypt_data(original)
        decrypted = decrypt_data(encrypted)

        self.assertEqual(original, decrypted)
