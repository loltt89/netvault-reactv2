"""
Distributed lock implementation using Redis

Prevents concurrent device connections that could exhaust VTY lines
"""
import redis
import uuid
import time
import logging
from django.conf import settings
from typing import Optional

logger = logging.getLogger(__name__)


class DeviceLockError(Exception):
    """Exception raised when unable to acquire device lock"""
    pass


class DeviceLock:
    """
    Distributed lock for device operations using Redis

    Prevents concurrent SSH/Telnet connections to the same device
    that could exhaust VTY lines (typically 5 on Cisco devices).

    Features:
    - Atomic acquire with SET NX EX
    - Token-based ownership (only lock owner can release)
    - Automatic expiration (prevents deadlocks)
    - Context manager support
    - Lua script for safe release

    Usage:
        with DeviceLock(device_id=123, operation='backup', ttl=120):
            # perform device operation
            pass
    """

    # Lua script for atomic lock release (check token + delete)
    # Only release if the lock is owned by this token (prevents releasing someone else's lock)
    RELEASE_SCRIPT = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    else
        return 0
    end
    """

    def __init__(self, device_id: int, operation: str = 'operation', ttl: int = 120,
                 blocking: bool = False, blocking_timeout: int = 30):
        """
        Initialize device lock

        Args:
            device_id: Device ID to lock
            operation: Operation name (for logging: 'backup', 'status_check', etc.)
            ttl: Lock time-to-live in seconds (auto-expires to prevent deadlocks)
            blocking: If True, wait for lock to become available
            blocking_timeout: Max seconds to wait for lock (only if blocking=True)
        """
        self.device_id = device_id
        self.operation = operation
        self.ttl = ttl
        self.blocking = blocking
        self.blocking_timeout = blocking_timeout

        # Unique token to identify this lock owner
        self.token = str(uuid.uuid4())

        # Redis key for this device lock
        self.lock_key = f'device_lock:{device_id}'

        # Redis connection (from Celery/Django settings)
        self.redis_client: Optional[redis.Redis] = None
        self.acquired = False

    def _get_redis_client(self) -> redis.Redis:
        """Get Redis client from URL in settings"""
        if not self.redis_client:
            redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
        return self.redis_client

    def acquire(self) -> bool:
        """
        Acquire the lock

        Returns:
            True if lock acquired, False otherwise

        Raises:
            DeviceLockError: If blocking=True and timeout reached
        """
        client = self._get_redis_client()
        start_time = time.time()

        while True:
            # Try to set lock atomically (SET key value NX EX ttl)
            # NX = only set if not exists
            # EX = expiration time in seconds
            acquired = client.set(
                self.lock_key,
                self.token,
                nx=True,  # Only set if not exists
                ex=self.ttl  # Auto-expire after TTL seconds
            )

            if acquired:
                self.acquired = True
                logger.info(
                    f"Lock acquired: device_id={self.device_id}, "
                    f"operation={self.operation}, ttl={self.ttl}s, token={self.token[:8]}"
                )
                return True

            # Lock not acquired
            if not self.blocking:
                logger.warning(
                    f"Lock NOT acquired (device busy): device_id={self.device_id}, "
                    f"operation={self.operation}"
                )
                return False

            # Blocking mode - check timeout
            elapsed = time.time() - start_time
            if elapsed >= self.blocking_timeout:
                raise DeviceLockError(
                    f"Failed to acquire lock for device {self.device_id} "
                    f"after {self.blocking_timeout}s timeout"
                )

            # Wait a bit before retry
            time.sleep(0.5)

    def release(self) -> bool:
        """
        Release the lock (only if we own it)

        Uses Lua script to atomically check token and delete lock.
        This prevents releasing someone else's lock.

        Returns:
            True if lock released, False if we don't own it
        """
        if not self.acquired:
            return False

        try:
            client = self._get_redis_client()

            # Execute Lua script: only delete if token matches
            result = client.eval(
                self.RELEASE_SCRIPT,
                1,  # Number of keys
                self.lock_key,  # KEYS[1]
                self.token  # ARGV[1]
            )

            if result == 1:
                logger.info(
                    f"Lock released: device_id={self.device_id}, "
                    f"operation={self.operation}, token={self.token[:8]}"
                )
                self.acquired = False
                return True
            else:
                logger.warning(
                    f"Lock NOT released (expired or stolen): device_id={self.device_id}, "
                    f"operation={self.operation}, token={self.token[:8]}"
                )
                self.acquired = False
                return False

        except Exception as e:
            logger.error(f"Error releasing lock for device {self.device_id}: {e}")
            self.acquired = False
            return False

    def extend(self, additional_ttl: int = 60) -> bool:
        """
        Extend lock TTL (if we own it)

        Useful for long-running operations.

        Args:
            additional_ttl: Seconds to add to current TTL

        Returns:
            True if extended, False otherwise
        """
        if not self.acquired:
            return False

        try:
            client = self._get_redis_client()

            # Check if we still own the lock
            current_token = client.get(self.lock_key)
            if current_token != self.token:
                logger.warning(
                    f"Cannot extend lock (not owner): device_id={self.device_id}, "
                    f"operation={self.operation}"
                )
                self.acquired = False
                return False

            # Extend TTL
            client.expire(self.lock_key, additional_ttl)
            logger.info(
                f"Lock extended: device_id={self.device_id}, "
                f"operation={self.operation}, additional_ttl={additional_ttl}s"
            )
            return True

        except Exception as e:
            logger.error(f"Error extending lock for device {self.device_id}: {e}")
            return False

    def __enter__(self):
        """Context manager entry - acquire lock"""
        if not self.acquire():
            raise DeviceLockError(
                f"Failed to acquire lock for device {self.device_id} "
                f"(operation: {self.operation})"
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - release lock"""
        self.release()
        return False  # Don't suppress exceptions
