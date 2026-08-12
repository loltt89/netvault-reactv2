"""
Device connection utilities for SSH and Telnet
Strategy: Paramiko first (95% devices), netvault-ssh binary fallback (SSH v1)
"""
import telnetlib
import time
import socket
import re
import ipaddress
import logging
import subprocess
import json
import os
from typing import Optional, Tuple, List

# Paramiko for SSH (covers 95%+ of devices)
try:
    import paramiko
    PARAMIKO_AVAILABLE = True
except ImportError:
    PARAMIKO_AVAILABLE = False
    paramiko = None

logger = logging.getLogger(__name__)

# Path to netvault-ssh binaries
# Legacy: libssh 0.8.x with SSH v1 support + older algorithms
# Modern: libssh 0.10.x with modern algorithms (sha256, etc.) but no SSH v1
NETVAULT_SSH_BIN = os.path.join(os.path.dirname(__file__), '..', 'tools', 'netvault-ssh', 'netvault-ssh')
NETVAULT_SSH_MODERN_BIN = os.path.join(os.path.dirname(__file__), '..', 'tools', 'netvault-ssh', 'netvault-ssh-modern')

# Error codes from netvault-ssh (stable across versions)
# These match the codes defined in netvault-ssh.c
ERR_NONE = 0           # No error
ERR_REQUEST_DENIED = 1 # Request was denied
ERR_FATAL = 2          # Fatal error (includes KEX failures, algorithm mismatches)
ERR_AUTH_FAILED = 10   # Authentication failed
ERR_TIMEOUT = 11       # Connection timeout
ERR_CHANNEL = 12       # Channel error

# ===== Compiled Regex Patterns (for performance) =====
ANSI_ESCAPE_PATTERN = re.compile(r'\x1b\[[0-9;]*m')
CARRIAGE_RETURN_PATTERN = re.compile(r'\r')
MORE_PAGING_PATTERN = re.compile(r'--More--|-- More --|<--- More --->')
MIKROTIK_PROMPT_PATTERN = re.compile(r'^\[.*?\]\s*[>\/]')
FORTINET_PROMPT_PATTERN = re.compile(r'^[A-Z0-9]+\s+\(.*\)\s+[#>]')
# Matches prompt with or without command (e.g., "Router#", "Router#show run", "FortiGate # cmd")
DEVICE_PROMPT_PATTERN = re.compile(r'^[^\s#>]+\s*[#>].*$')


class DeviceConnectionError(Exception):
    """Custom exception for device connection errors"""
    pass


class HostKeyMismatchError(DeviceConnectionError):
    """
    Raised when a device presents an SSH host key that doesn't match the
    one pinned in the database. Deliberately a distinct exception type —
    callers must NOT treat this the same as a generic connection failure,
    because SSHConnection.connect() falls back to the netvault-ssh binary
    on generic Paramiko failures, and that binary does no host key
    verification at all. Falling back here would silently defeat the
    whole point of pinning. See _ParamikoSSH.connect()'s handling of this
    exception specifically.
    """
    pass


if PARAMIKO_AVAILABLE:
    class PinnedHostKeyPolicy(paramiko.MissingHostKeyPolicy):
        """
        Trust-on-first-use SSH host key verification, backed by the
        Device model (see devices/models.py fields ssh_host_key_*).

        - No key on file yet: pin the presented key and allow the
          connection (this is the "first use" — see the SECURITY.md /
          conversation note that this moment can't be secured over the
          same network channel it's protecting; verifying out-of-band
          at device-provisioning time is the only real fix, which is
          outside what an automated connection can do).
        - Key matches what's pinned: allow.
        - Key doesn't match: refuse the connection, record the new key
          as *pending* (not trusted), and notify an administrator. The
          device stays unreachable via NetVault until someone reviews
          the fingerprint out-of-band and calls Device.approve_ssh_host_key().
        """

        def __init__(self, device_id: int):
            self.device_id = device_id

        def missing_host_key(self, client, hostname, key):
            from devices.models import Device
            from django.utils import timezone

            fingerprint = f"SHA256:{key.get_fingerprint().hex()}"
            key_type = key.get_name()

            try:
                device = Device.objects.get(id=self.device_id)
            except Device.DoesNotExist:
                # Fail closed: no device record to pin against, don't connect.
                raise HostKeyMismatchError(
                    f"Cannot verify SSH host key: device {self.device_id} not found"
                )

            if not device.ssh_host_key_fingerprint:
                # First-ever connection to this device: pin it.
                #
                # This runs mid-request, inside client.connect()'s handshake
                # — the caller (devices/views.py's test_connection action,
                # backups/tasks.py's backup task) is holding its own,
                # separately-loaded Device instance for the same row. Only
                # touch these three columns: an unrestricted save() here
                # would be harmless (this instance has no other pending
                # changes), but callers MUST use update_fields on their own
                # subsequent device.save() calls, or they will silently
                # overwrite what gets written here with their stale
                # in-memory copy. (Found the hard way: devices/views.py's
                # test_connection previously did a bare device.save() after
                # this returned, which clobbered the pin on every single
                # first connection.)
                device.ssh_host_key_type = key_type
                device.ssh_host_key_fingerprint = fingerprint
                device.ssh_host_key_verified_at = timezone.now()
                device.save(update_fields=[
                    'ssh_host_key_type', 'ssh_host_key_fingerprint', 'ssh_host_key_verified_at',
                ])
                logger.info(
                    f"Pinned new SSH host key for device '{device.name}' ({hostname}): "
                    f"{key_type} {fingerprint}"
                )
                return

            if device.ssh_host_key_type == key_type and device.ssh_host_key_fingerprint == fingerprint:
                # Matches what's already pinned.
                return

            # Mismatch — refuse, record as pending, notify.
            expected = f"{device.ssh_host_key_type} {device.ssh_host_key_fingerprint}"
            received = f"{key_type} {fingerprint}"

            device.ssh_host_key_pending_type = key_type
            device.ssh_host_key_pending_fingerprint = fingerprint
            device.ssh_host_key_pending_detected_at = timezone.now()
            device.save(update_fields=[
                'ssh_host_key_pending_type', 'ssh_host_key_pending_fingerprint', 'ssh_host_key_pending_detected_at',
            ])

            logger.error(
                f"SSH HOST KEY MISMATCH for device '{device.name}' ({hostname}): "
                f"expected {expected}, received {received}. Refusing connection."
            )

            try:
                from notifications.services import notify_host_key_mismatch
                notify_host_key_mismatch(device.name, hostname, expected, received)
            except Exception:
                logger.exception(f"Failed to send host key mismatch notification for device '{device.name}'")

            raise HostKeyMismatchError(
                f"SSH host key for {hostname} does not match the pinned key "
                f"(expected {expected}, received {received}). Connection refused — "
                f"verify out-of-band and approve the new key in NetVault before retrying."
            )


def _never_a_device(ip) -> Optional[str]:
    """
    Categorize IP ranges that can never legitimately be a network device
    NetVault is asked to SSH/Telnet into — independent of ALLOWED_PRIVATE_NETWORKS
    configuration, independent of whether the address happens to be "private".

    This exists as its own function (rather than being inlined into
    validate_target_host) so devices/serializers.py can run the exact same
    check at device-creation time, for fast feedback, without duplicating
    the range list and risking the two silently drifting apart. The
    connection-time check in validate_target_host is still what actually
    protects against SSRF — this is belt-and-suspenders.

    Returns a human-readable reason string if the IP should be rejected,
    None if this function has no objection (ALLOWED_PRIVATE_NETWORKS may
    still reject it in validate_target_host).
    """
    if ip.is_loopback:
        return "loopback addresses are forbidden"
    if ip.is_link_local:
        # 169.254.0.0/16 and fe80::/10 — this is the range cloud metadata
        # services live in (169.254.169.254 on AWS/GCP/Azure/OCI). Python's
        # ipaddress module already marks link-local as is_private, so with
        # ALLOWED_PRIVATE_NETWORKS left at its empty ("allow all private")
        # default, this range was reachable by default before this check —
        # a textbook SSRF-to-cloud-metadata primitive for any operator who
        # can add a device. No legitimate network device lives here.
        return "link-local addresses are forbidden (this range includes cloud metadata endpoints)"
    if ip.is_multicast:
        return "multicast addresses are forbidden"
    if ip.is_unspecified:
        return "the unspecified address is forbidden"
    if ip.is_reserved:
        return "reserved addresses are forbidden"
    return None


def validate_target_host(host: str) -> str:
    """
    Validate target host to prevent SSRF attacks
    """
    from django.conf import settings

    try:
        ip = ipaddress.ip_address(host)
        resolved_ip = host
    except ValueError:
        try:
            resolved_ip = socket.gethostbyname(host)
            ip = ipaddress.ip_address(resolved_ip)
        except socket.gaierror:
            raise DeviceConnectionError(f"Cannot resolve hostname: {host}")

    reason = _never_a_device(ip)
    if reason:
        raise DeviceConnectionError(f"Connection to {resolved_ip} is forbidden: {reason}.")

    if ip.is_private and settings.ALLOWED_PRIVATE_NETWORKS:
        if not any(ip in network for network in settings.ALLOWED_PRIVATE_NETWORKS):
            raise DeviceConnectionError(
                f"Connection to private address {resolved_ip} is not in allowed network ranges."
            )

    return resolved_ip


def validate_backup_config(config: str) -> Tuple[bool, str]:
    """
    Validate backup configuration content
    """
    ERROR_PATTERNS = [
        'access denied', 'permission denied', 'authorization failed',
        'authentication failed', 'invalid command', 'command not found',
        'unknown command', '% invalid', 'error:', 'login incorrect',
        'not authorized', 'privilege level', 'insufficient privilege',
        'bad command', 'incomplete command', 'command authorization failed',
        'invalid password', 'password required', 'enable password'
    ]

    if not config or not config.strip():
        return False, "Configuration is empty"

    # Check entire config for error patterns (not just first lines)
    config_lower = config.lower()
    for pattern in ERROR_PATTERNS:
        if pattern in config_lower:
            # Make sure it's an error, not part of config (e.g., "enable password" in ASA config is ok)
            # Check if error appears without being part of a config line
            lines_with_pattern = [l for l in config.split('\n') if pattern in l.lower()]
            for line in lines_with_pattern:
                # Skip config lines that contain passwords as settings
                if line.strip().startswith(('enable password', 'password', 'username')) and '***' in line:
                    continue
                # Real errors
                if 'invalid password' in line.lower() or 'access denied' in line.lower():
                    return False, f"Error detected: '{line.strip()[:100]}'"

    lines = [l for l in config.strip().split('\n') if l.strip()]

    if len(lines) < 5:
        return False, f"Configuration too short: {len(lines)} lines (minimum 5 required)"

    return True, ""


def tcp_ping(host: str, port: int, timeout: int = 2) -> bool:
    """Quick TCP connection check"""
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        return result == 0
    except Exception:
        return False
    finally:
        if sock:
            try:
                sock.close()
            except Exception:
                pass


def clean_device_output(output: str, vendor: str = '', command: str = '', backup_commands: dict = None) -> str:
    """
    Clean command output from prompts, control characters, and banners.

    Uses config_start, config_end, and skip_patterns from backup_commands if provided.
    Falls back to generic patterns if not specified.
    """
    # First, clean control characters
    output = ANSI_ESCAPE_PATTERN.sub('', output)
    output = CARRIAGE_RETURN_PATTERN.sub('', output)
    output = MORE_PAGING_PATTERN.sub('', output)

    # Get markers from backup_commands or use generic defaults
    if backup_commands and isinstance(backup_commands, dict):
        start_markers = backup_commands.get('config_start', ['!', '#', 'version', 'config', 'hostname'])
        end_markers = backup_commands.get('config_end', [])
        custom_skip = backup_commands.get('skip_patterns', [])
    else:
        start_markers = ['!', '#', 'version', 'config', 'hostname']
        end_markers = []
        custom_skip = []

    lines = output.split('\n')

    # Find REAL config start (skip banners)
    # Config starts at lines like "hostname X", "version X", "!" at line start
    # NOT at banner lines that happen to contain these words
    start_idx = 0
    found_start = False
    for i, line in enumerate(lines):
        stripped = line.strip()

        # Skip empty lines
        if not stripped:
            continue

        # Skip obvious banner lines (decorative characters)
        if _is_banner_line(stripped):
            continue

        # Check for real config start markers
        for marker in start_markers:
            # "hostname X" or "version X" at start of line = config
            if stripped.startswith(marker):
                # Make sure it's not inside a banner (check surrounding context)
                if marker in ['hostname', 'version', 'config']:
                    # These should be followed by actual value, not banner text
                    if len(stripped.split()) >= 2 or stripped == '!':
                        start_idx = i
                        found_start = True
                        break
                else:
                    start_idx = i
                    found_start = True
                    break
        if found_start:
            break

    # Find config end (search from the end)
    end_idx = len(lines)
    if end_markers:
        for i in range(len(lines) - 1, start_idx, -1):
            stripped = lines[i].strip().lower()
            if stripped in [m.lower() for m in end_markers]:
                end_idx = i + 1
                break

    # Extract config section
    config_lines = lines[start_idx:end_idx]

    # Default skip patterns for session messages and banners
    default_skip_patterns = [
        'logoff', 'logout', 'connection closed', 'session ended',
        'type help', 'logins over the last', 'failed logins since',
        'last login:', 'user logged in', 'remember to save',
        'last successful login', 'info: command executed',
        'please use new command', 'do you wish to save',
        # Banner text patterns
        'unauthorized access', 'authorized personnel', 'disconnect immediately',
        'activities on this system', 'logged and monitored', 'consent to',
        'security@', 'contact:', 'prohibited'
    ]

    # Combine default and custom skip patterns
    skip_patterns = default_skip_patterns + custom_skip

    # Final cleanup - remove any remaining prompt lines, session messages, and banners
    cleaned_lines = []
    for line in config_lines:
        stripped = line.strip()
        if not stripped:
            continue

        stripped_lower = stripped.lower()

        # Skip obvious prompt lines (hostname# or hostname>)
        if DEVICE_PROMPT_PATTERN.match(stripped):
            continue

        # Skip command echo lines
        if command and stripped.endswith(command):
            continue

        # Skip session messages and banner text
        if any(p in stripped_lower for p in skip_patterns):
            continue

        # Skip decorative banner lines
        if _is_banner_line(stripped):
            continue

        cleaned_lines.append(line.rstrip())

    return '\n'.join(cleaned_lines).strip()


def _is_banner_line(line: str) -> bool:
    """
    Detect decorative banner lines (asterisks, dashes, equals, box drawing).

    Returns True if line is likely a banner decoration, not config content.
    """
    if not line:
        return False

    # Count decorative characters
    decorative_chars = set('*=-_+|╔╗╚╝║═│┌┐└┘├┤┬┴┼')
    decorative_count = sum(1 for c in line if c in decorative_chars)

    # If >60% of non-space chars are decorative, it's a banner
    non_space = len(line.replace(' ', ''))
    if non_space > 0 and decorative_count / non_space > 0.6:
        return True

    # Lines that are ONLY decorative chars and spaces
    if all(c in decorative_chars or c.isspace() for c in line):
        return True

    return False


# ========== Paramiko SSH Helper (primary method) ==========

class _ParamikoSSH:
    """
    Paramiko-based SSH client - primary method for 95%+ of devices.
    Simpler to debug than C binary, works everywhere Python runs.
    """

    # Disable Paramiko's verbose logging
    logging.getLogger('paramiko').setLevel(logging.WARNING)

    def __init__(self, host: str, port: int, username: str, password: str, timeout: int = 30, device_id: Optional[int] = None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout
        self.device_id = device_id
        self.client: Optional[paramiko.SSHClient] = None
        self.channel: Optional[paramiko.Channel] = None

    def connect(self) -> bool:
        """Connect to device. Returns True on success, False on failure.

        Raises HostKeyMismatchError (not just False) when the device's SSH
        host key has changed — that must NOT be treated like an ordinary
        connection failure, because SSHConnection.connect() falls back to
        the netvault-ssh binary on an ordinary failure, and that binary
        performs no host key verification at all. See PinnedHostKeyPolicy.
        """
        if not PARAMIKO_AVAILABLE:
            return False

        if not self.device_id:
            # Fail closed rather than silently accepting any host key.
            logger.error(f"Refusing Paramiko connection to {self.host}: no device_id supplied for host key verification")
            self.client = None
            return False

        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(PinnedHostKeyPolicy(self.device_id))

            # Enable legacy algorithms for older devices
            self.client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=self.timeout,
                look_for_keys=False,
                allow_agent=False,
                # Enable legacy algorithms
                disabled_algorithms={
                    'pubkeys': [],  # Don't disable any
                    'keys': [],
                }
            )
            return True

        except HostKeyMismatchError:
            # Re-raise as-is — do not let this fall through to the
            # generic handlers below, which would return False and send
            # the caller straight into the unverified binary fallback.
            self.client = None
            raise
        except paramiko.ssh_exception.SSHException as e:
            logger.debug(f"Paramiko SSH error for {self.host}: {e}")
            self.client = None
            return False
        except socket.timeout:
            logger.debug(f"Paramiko timeout for {self.host}")
            self.client = None
            return False
        except Exception as e:
            logger.debug(f"Paramiko error for {self.host}: {e}")
            self.client = None
            return False

    def exec_command(self, command: str, timeout: int = 30) -> Tuple[bool, str]:
        """Execute single command via exec channel. Returns (success, output)."""
        if not self.client:
            return False, "Not connected"

        try:
            stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
            output = stdout.read().decode('utf-8', errors='ignore')
            error = stderr.read().decode('utf-8', errors='ignore')
            return True, output + error
        except Exception as e:
            return False, str(e)

    def shell_commands(self, commands: List[str], idle_ms: int = 500) -> Tuple[bool, str]:
        """Execute commands in interactive shell with idle detection."""
        if not self.client:
            return False, "Not connected"

        try:
            # Open interactive shell with PTY
            self.channel = self.client.invoke_shell(term='xterm', width=200, height=50)
            self.channel.settimeout(0.1)  # Non-blocking reads

            output = ""
            idle_threshold = idle_ms / 1000.0  # Convert to seconds
            max_idle_cycles = 5  # Wait up to 5 * idle_threshold before considering done

            # Wait for initial prompt
            output += self._read_until_idle(idle_threshold, max_idle_cycles)

            # Send each command
            for cmd in commands:
                cmd = cmd.strip()
                if not cmd:
                    continue

                self.channel.send(cmd + '\n')
                time.sleep(0.1)  # Brief delay after sending

                # Read response with idle detection
                output += self._read_until_idle(idle_threshold, max_idle_cycles)

            # Send exit
            try:
                self.channel.send('exit\n')
                time.sleep(0.2)
                output += self._read_available()
            except Exception:
                pass

            return True, output

        except Exception as e:
            return False, str(e)
        finally:
            if self.channel:
                try:
                    self.channel.close()
                except Exception:
                    pass
                self.channel = None

    def _read_until_idle(self, idle_threshold: float, max_idle_cycles: int) -> str:
        """Read from channel until idle (no data for idle_threshold * max_idle_cycles)."""
        output = ""
        idle_count = 0
        start_time = time.time()
        max_time = 60  # Absolute timeout

        while idle_count < max_idle_cycles and (time.time() - start_time) < max_time:
            chunk = self._read_available()
            if chunk:
                output += chunk
                idle_count = 0  # Reset idle counter

                # Handle --More-- paging
                if '--More--' in chunk or '-- More --' in chunk:
                    self.channel.send(' ')
                    time.sleep(0.1)
            else:
                idle_count += 1
                time.sleep(idle_threshold)

        return output

    def _read_available(self) -> str:
        """Read all available data from channel (non-blocking)."""
        data = ""
        try:
            while self.channel.recv_ready():
                chunk = self.channel.recv(4096).decode('utf-8', errors='ignore')
                # Filter out NULL bytes (some devices send them)
                chunk = chunk.replace('\x00', '')
                data += chunk
        except socket.timeout:
            pass
        except Exception:
            pass
        return data

    def disconnect(self):
        """Close connection."""
        if self.channel:
            try:
                self.channel.close()
            except Exception:
                pass
            self.channel = None

        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
            self.client = None


# ========== SSH Connection (Paramiko first, binary fallback) ==========

class SSHConnection:
    """
    SSH connection handler with "Paramiko first, binary fallback" strategy.
    - Paramiko: covers 95%+ devices, easier to debug, no Core Dumps
    - netvault-ssh binary: fallback for SSH v1 devices (rare)
    """

    def __init__(self, host: str, port: int, username: str, password: str,
                 enable_password: Optional[str] = None, timeout: int = 30, vendor: str = '',
                 device_id: Optional[int] = None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password or ''
        self.enable_password = enable_password
        self.timeout = timeout
        self.vendor = vendor
        self.device_id = device_id
        self.backup_commands: Optional[dict] = None
        self._connected = False
        self._use_binary = False  # Flag: if True, skip Paramiko and use binary directly
        self._paramiko: Optional[_ParamikoSSH] = None

    def connect(self) -> None:
        """Test SSH connection (Paramiko first, binary fallback).

        Note: a HostKeyMismatchError from the Paramiko attempt propagates
        straight out of this method rather than triggering the binary
        fallback below — see _ParamikoSSH.connect()'s docstring for why.
        """
        # Try Paramiko first
        if PARAMIKO_AVAILABLE and not self._use_binary:
            self._paramiko = _ParamikoSSH(self.host, self.port, self.username, self.password, self.timeout, self.device_id)
            if self._paramiko.connect():
                self._connected = True
                logger.info(f"Connected to {self.host} via Paramiko")
                return
            else:
                logger.debug(f"Paramiko failed for {self.host}, falling back to netvault-ssh")
                self._paramiko = None

        # Fallback to binary (supports SSH v1)
        result = self._run_ssh_binary(mode='test')
        if not result['success']:
            raise DeviceConnectionError(result.get('error', 'Connection failed'))
        self._connected = True
        self._use_binary = True
        logger.info(f"Connected to {self.host} via netvault-ssh binary")

    def _run_ssh(self, mode: str = 'shell', commands: str = '', idle_ms: int = 500) -> dict:
        """Run SSH command - Paramiko first, binary fallback."""
        # If we have a working Paramiko connection, use it
        if self._paramiko and self._paramiko.client:
            return self._run_ssh_paramiko(mode, commands, idle_ms)

        # Otherwise use binary
        return self._run_ssh_binary(mode, commands, idle_ms)

    def _run_ssh_paramiko(self, mode: str, commands: str, idle_ms: int) -> dict:
        """Run SSH via Paramiko."""
        try:
            if mode == 'test':
                # Already connected if we're here
                return {'success': True, 'output': 'Connection successful', 'error_code': ERR_NONE}

            elif mode == 'exec':
                # Single command exec mode
                success, output = self._paramiko.exec_command(commands, timeout=self.timeout)
                return {
                    'success': success,
                    'output': output if success else '',
                    'error': '' if success else output,
                    'error_code': ERR_NONE if success else ERR_CHANNEL
                }

            else:  # shell mode
                # Split commands by ||| separator
                cmd_list = [c.strip() for c in commands.split('|||') if c.strip()]
                success, output = self._paramiko.shell_commands(cmd_list, idle_ms)
                return {
                    'success': success,
                    'output': output if success else '',
                    'error': '' if success else output,
                    'error_code': ERR_NONE if success else ERR_CHANNEL
                }

        except Exception as e:
            logger.warning(f"Paramiko error for {self.host}: {e}, falling back to binary")
            # On Paramiko error, switch to binary mode
            self._paramiko.disconnect()
            self._paramiko = None
            self._use_binary = True
            return self._run_ssh_binary(mode, commands, idle_ms)

    def _run_ssh_binary(self, mode: str = 'shell', commands: str = '', idle_ms: int = 500, use_modern: bool = False) -> dict:
        """Run netvault-ssh binary with automatic fallback to modern version on KEX errors."""
        ssh_bin = NETVAULT_SSH_MODERN_BIN if use_modern else NETVAULT_SSH_BIN

        # Use -pass-stdin for security (password not visible in ps aux)
        cmd = [
            ssh_bin,
            '-host', self.host,
            '-port', str(self.port),
            '-user', self.username,
            '-pass-stdin',  # Read password from stdin (secure)
            '-timeout', str(self.timeout),
            '-idle', str(idle_ms),
            '-mode', mode,
        ]

        if commands:
            cmd.extend(['-cmds', commands])

        try:
            # For test mode use shorter subprocess timeout
            proc_timeout = self.timeout + 5 if mode == 'test' else self.timeout * 2 + 10
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=proc_timeout,
                text=True,
                input=self.password  # Pass password via stdin
            )

            # Parse JSON output
            try:
                parsed = json.loads(result.stdout)
            except json.JSONDecodeError:
                return {
                    'success': False,
                    'error': f"Invalid response: {result.stdout[:200]}"
                }

            # Fallback to modern binary on KEX/algorithm errors (only if not already using modern)
            if not parsed.get('success') and not use_modern:
                error_code = parsed.get('error_code', 0)

                # ERR_FATAL (2) indicates KEX/algorithm failure - try modern binary
                # Modern libssh 0.10.x supports more algorithms than legacy 0.7.x
                if error_code == ERR_FATAL:
                    logger.info(f"KEX/algorithm error (code={error_code}) with legacy SSH, trying modern binary for {self.host}")
                    return self._run_ssh_binary(mode, commands, idle_ms, use_modern=True)

            return parsed

        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Command timeout'}
        except FileNotFoundError:
            # If legacy not found, try modern
            if not use_modern and os.path.exists(NETVAULT_SSH_MODERN_BIN):
                return self._run_ssh_binary(mode, commands, idle_ms, use_modern=True)
            return {'success': False, 'error': f'netvault-ssh binary not found'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def send_command(self, command: str, wait_time: float = 2, handle_paging: bool = True) -> str:
        """Send command and return output"""
        result = self._run_ssh(
            mode='shell',
            commands=command,
            idle_ms=int(wait_time * 500)  # Convert to idle detection time
        )

        if not result['success']:
            raise DeviceConnectionError(result.get('error', 'Command failed'))

        return result.get('output', '')

    def send_command_exec(self, command: str, timeout: int = 30) -> str:
        """Send command using exec mode (for MikroTik)"""
        old_timeout = self.timeout
        self.timeout = timeout

        result = self._run_ssh(mode='exec', commands=command)

        self.timeout = old_timeout

        if not result['success']:
            raise DeviceConnectionError(result.get('error', 'Command failed'))

        return result.get('output', '')

    def send_commands(self, commands: List[str], wait_time: float = 2) -> List[str]:
        """Send multiple commands"""
        # Join commands with ||| separator
        cmds_str = '|||'.join(commands)
        result = self._run_ssh(
            mode='shell',
            commands=cmds_str,
            idle_ms=int(wait_time * 500)
        )

        if not result['success']:
            raise DeviceConnectionError(result.get('error', 'Commands failed'))

        # Return single output (commands are executed sequentially)
        return [result.get('output', '')]

    def enable_mode(self) -> str:
        """Enter enable mode"""
        if not self.enable_password:
            return ""

        result = self._run_ssh(
            mode='shell',
            commands=f'enable|||{self.enable_password}',
            idle_ms=500
        )
        return result.get('output', '')

    def _get_logout_commands(self) -> List[str]:
        """Get vendor-specific logout commands"""
        if self.backup_commands and isinstance(self.backup_commands, dict):
            logout_cmds = self.backup_commands.get('logout', [])
            if isinstance(logout_cmds, list) and logout_cmds:
                return logout_cmds
        return ['end', 'exit']

    def get_config(self, vendor: str, backup_commands: dict = None) -> str:
        """Get device configuration"""
        vendor = vendor.lower()
        self.backup_commands = backup_commands

        if backup_commands:
            setup_commands = backup_commands.get('setup', [])
            show_command = backup_commands.get('backup', 'show running-config')
            need_enable = backup_commands.get('enable_mode', False)
            use_exec_mode = backup_commands.get('exec_mode', False)
            exec_wrapper = backup_commands.get('exec_wrapper', '')
        else:
            setup_commands = []
            show_command = 'show running-config'
            need_enable = False
            use_exec_mode = False
            exec_wrapper = ''

        # Build command sequence
        all_commands = []

        if need_enable and self.enable_password:
            all_commands.extend(['enable', self.enable_password])

        all_commands.extend(setup_commands)

        # Use exec mode if specified in backup_commands
        if use_exec_mode:
            if exec_wrapper:
                # Use wrapper (e.g., VyOS vyatta-op-cmd-wrapper)
                exec_command = f'{exec_wrapper} {show_command}'
            else:
                exec_command = show_command
            config = self.send_command_exec(exec_command, timeout=30)
        else:
            all_commands.append(show_command)
            cmds_str = '|||'.join(all_commands)

            # Default idle time
            idle_ms = 1000

            result = self._run_ssh(mode='shell', commands=cmds_str, idle_ms=idle_ms)

            if not result['success']:
                raise DeviceConnectionError(result.get('error', 'Failed to get config'))

            config = result.get('output', '')

        return clean_device_output(config, vendor, show_command, backup_commands)

    def disconnect(self) -> None:
        """Disconnect SSH connection."""
        if self._paramiko:
            self._paramiko.disconnect()
            self._paramiko = None
        self._connected = False

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


# ========== Telnet Connection ==========

class TelnetConnection:
    """Telnet connection handler for network devices"""

    def __init__(self, host: str, port: int, username: str, password: str,
                 enable_password: Optional[str] = None, timeout: int = 30, vendor: str = ''):
        self.host = host
        self.port = port
        self.username = username
        self.password = password or ''
        self.enable_password = enable_password
        self.timeout = timeout
        self.vendor = vendor
        self.backup_commands: Optional[dict] = None
        self.connection: Optional[telnetlib.Telnet] = None

    def connect(self) -> None:
        """Establish Telnet connection"""
        try:
            self.connection = telnetlib.Telnet(self.host, self.port, self.timeout)

            # Quick initial read to check if connection is alive
            time.sleep(0.5)

            # Wait for login prompt with shorter timeout
            login_timeout = min(self.timeout, 5)
            index, match, text = self.connection.expect(
                [b"sername:", b"ogin:", b"[#>$]"], timeout=login_timeout
            )

            if index == 2:
                # Already at prompt, no login needed
                return
            elif index in (0, 1):
                # Login prompt
                self.connection.write(self.username.encode('ascii') + b'\n')
            else:
                # No prompt found, try sending username anyway
                self.connection.write(self.username.encode('ascii') + b'\n')

            # Wait for password prompt or command prompt
            index, match, text = self.connection.expect(
                [b"assword:", b"[#>$]"], timeout=login_timeout
            )

            if index == 0:  # Password prompt
                self.connection.write(self.password.encode('ascii') + b'\n')
                time.sleep(1)
            # If index == 1, we got a prompt directly (no password needed)

        except EOFError:
            raise DeviceConnectionError(f"Connection closed by {self.host}")
        except socket.timeout:
            raise DeviceConnectionError(f"Connection timeout to {self.host}")
        except Exception as e:
            raise DeviceConnectionError(f"Failed to connect to {self.host}: {str(e)}")

    def send_command(self, command: str, wait_time: float = 2, handle_paging: bool = True) -> str:
        """Send command and return output with idle detection"""
        if not self.connection:
            raise DeviceConnectionError("Not connected")

        try:
            self.connection.write(command.encode('ascii') + b'\n')
            time.sleep(wait_time)

            output = ""
            max_iterations = 100
            iteration = 0
            start_time = time.time()
            read_timeout = 60

            # Idle detection: wait for N consecutive empty reads before finishing
            # This prevents premature exit if device "thinks" for a moment
            # Network devices can pause 2-3+ seconds when generating heavy configs
            idle_count = 0
            max_idle = 20  # 20 * 0.2s = 4 seconds of idle before considering done
            idle_sleep = 0.2  # Time to wait between reads

            while iteration < max_iterations:
                if time.time() - start_time > read_timeout:
                    break

                try:
                    chunk = self.connection.read_very_eager().decode('utf-8', errors='ignore')
                except EOFError:
                    break

                if chunk:
                    output += chunk
                    idle_count = 0  # Reset idle counter - we got data

                    if handle_paging and ('--More--' in chunk or '-- More --' in chunk or
                                         '(more)' in chunk.lower() or 'press any key' in chunk.lower()):
                        self.connection.write(b' ')
                        time.sleep(0.5)
                        iteration += 1
                        continue

                    time.sleep(0.1)
                else:
                    # No data - increment idle counter
                    idle_count += 1
                    if idle_count >= max_idle:
                        break  # Enough idle cycles - we're done
                    time.sleep(idle_sleep)  # Wait before next attempt
                iteration += 1

            return output

        except Exception as e:
            raise DeviceConnectionError(f"Error sending command: {str(e)}")

    def send_commands(self, commands: List[str], wait_time: float = 2) -> List[str]:
        """Send multiple commands"""
        outputs = []
        for command in commands:
            output = self.send_command(command, wait_time)
            outputs.append(output)
        return outputs

    def enable_mode(self) -> str:
        """Enter enable mode"""
        if not self.enable_password:
            return ""

        output = self.send_command("enable", wait_time=1)
        output += self.send_command(self.enable_password, wait_time=1)
        return output

    def _get_logout_commands(self) -> List[str]:
        """Get vendor-specific logout commands"""
        if self.backup_commands and isinstance(self.backup_commands, dict):
            logout_cmds = self.backup_commands.get('logout', [])
            if isinstance(logout_cmds, list) and logout_cmds:
                return logout_cmds
        return ['end', 'exit']

    def get_config(self, vendor: str, backup_commands: dict = None) -> str:
        """Get device configuration"""
        vendor = vendor.lower()
        self.backup_commands = backup_commands

        if backup_commands:
            setup_commands = backup_commands.get('setup', [])
            show_command = backup_commands.get('backup', 'show running-config')
            need_enable = backup_commands.get('enable_mode', False)
        else:
            setup_commands = []
            show_command = 'show running-config'
            need_enable = False

        if need_enable:
            self.enable_mode()

        for cmd in setup_commands:
            self.send_command(cmd, wait_time=1)

        wait_time = 10 if vendor == 'mikrotik' else 3
        config = self.send_command(show_command, wait_time=wait_time)

        return clean_device_output(config, vendor, show_command, backup_commands)

    def disconnect(self) -> None:
        """Close Telnet connection"""
        try:
            if self.connection:
                try:
                    logout_commands = self._get_logout_commands()
                    for cmd in logout_commands:
                        self.connection.write(f'{cmd}\n'.encode('ascii'))
                        time.sleep(0.3)
                    time.sleep(0.5)
                except Exception:
                    pass

                self.connection.close()
        except Exception:
            try:
                if self.connection:
                    self.connection.close()
            except Exception:
                pass

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


# ========== Public API Functions ==========

def test_connection(host: str, port: int, protocol: str, username: str,
                   password: str, enable_password: Optional[str] = None,
                   timeout: int = 5, device_id: Optional[int] = None) -> Tuple[bool, str]:
    """Test device connection"""
    try:
        resolved_host = validate_target_host(host)
    except DeviceConnectionError as e:
        return False, str(e)

    # Quick TCP check first
    if not tcp_ping(resolved_host, port, timeout=2):
        return False, f"Port {port} is not reachable on {host}"

    try:
        if protocol.lower() == 'ssh':
            # Use shorter timeout for test - just verify we can authenticate.
            # connect() itself already performs and verifies the connection
            # (Paramiko first, binary fallback) and raises on failure — a
            # second _run_ssh(mode='test') call here would just repeat
            # whichever one of those two actually succeeded.
            conn = SSHConnection(resolved_host, port, username, password, enable_password, timeout=5, device_id=device_id)
            conn.connect()
            return True, "Connection successful"
        else:
            with TelnetConnection(resolved_host, port, username, password, enable_password, timeout) as conn:
                return True, "Connection successful"
    except Exception as e:
        return False, str(e)


def backup_device_config(host: str, port: int, protocol: str, username: str,
                        password: str, vendor: str, enable_password: Optional[str] = None,
                        timeout: int = 30, backup_commands: dict = None,
                        device_id: Optional[int] = None) -> Tuple[bool, str, str]:
    """Backup device configuration"""
    try:
        resolved_host = validate_target_host(host)
    except DeviceConnectionError as e:
        return False, "", str(e)

    try:
        if protocol.lower() == 'ssh':
            with SSHConnection(resolved_host, port, username, password, enable_password, timeout, vendor, device_id=device_id) as conn:
                config = conn.get_config(vendor, backup_commands)

                is_valid, error_msg = validate_backup_config(config)
                if not is_valid:
                    return False, "", error_msg

                return True, config, ""
        else:
            with TelnetConnection(resolved_host, port, username, password, enable_password, timeout, vendor) as conn:
                config = conn.get_config(vendor, backup_commands)

                is_valid, error_msg = validate_backup_config(config)
                if not is_valid:
                    return False, "", error_msg

                return True, config, ""
    except Exception as e:
        return False, "", str(e)
