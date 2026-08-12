"""
Rate throttles for operations that are expensive on the server side
(opening a real SSH/Telnet session to a device) rather than just
security-sensitive — DeviceLock already stops two of these from running
concurrently against the *same* device, but nothing previously stopped a
single user from firing off requests against many devices back-to-back,
each one tying up a worker thread/connection for the full connect timeout.
"""
from rest_framework.throttling import UserRateThrottle


class DeviceConnectionTestThrottle(UserRateThrottle):
    """Manual 'Test Connection' clicks — scope='device_connection_test'."""
    scope = 'device_connection_test'


class DeviceBackupNowThrottle(UserRateThrottle):
    """Manual 'Backup Now' triggers — scope='device_backup_now'."""
    scope = 'device_backup_now'
