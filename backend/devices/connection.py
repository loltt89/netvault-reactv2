"""
Device connection utilities for SSH and Telnet
"""
import paramiko
import telnetlib
import time
import socket
import re
import ipaddress
import logging
from typing import Optional, Tuple, List

logger = logging.getLogger(__name__)


class LoggingAutoAddPolicy(paramiko.MissingHostKeyPolicy):
    """Auto-add host keys but log when it happens for security visibility"""
    def missing_host_key(self, client, hostname, key):
        logger.warning(f"SSH: Auto-accepting host key for {hostname} (fingerprint: {key.get_fingerprint().hex()})")
        client.get_host_keys().add(hostname, key.get_name(), key)


class DeviceConnectionError(Exception):
    """Custom exception for device connection errors"""
    pass


def validate_target_host(host: str) -> str:
    """
    Validate target host to prevent SSRF attacks

    Blocks connections to loopback and validates private network ranges
    to prevent attacks on local services (Redis, MariaDB, etc.)

    Args:
        host: Target hostname or IP address

    Returns:
        Resolved IP address to use for connection

    Raises:
        DeviceConnectionError: If host resolves to forbidden address
    """
    from django.conf import settings

    try:
        # Try to parse as IP first
        ip = ipaddress.ip_address(host)
        resolved_ip = host
    except ValueError:
        # It's a hostname - resolve DNS first to prevent DNS rebinding attacks
        try:
            resolved_ip = socket.gethostbyname(host)
            ip = ipaddress.ip_address(resolved_ip)
        except socket.gaierror:
            raise DeviceConnectionError(f"Cannot resolve hostname: {host}")

    # Block loopback addresses (127.0.0.1, ::1, etc.)
    if ip.is_loopback:
        raise DeviceConnectionError(
            f"Connection to loopback address {resolved_ip} is forbidden for security reasons."
        )

    # Check private IP whitelist (if configured)
    if ip.is_private and settings.ALLOWED_PRIVATE_NETWORKS:
        # Whitelist is configured - check if IP is in allowed ranges
        if not any(ip in network for network in settings.ALLOWED_PRIVATE_NETWORKS):
            raise DeviceConnectionError(
                f"Connection to private address {resolved_ip} is not in allowed network ranges. "
                f"Contact administrator to whitelist this network."
            )

    return resolved_ip


def tcp_ping(host: str, port: int, timeout: int = 2) -> bool:
    """
    Quick TCP connection check (does NOT consume VTY lines)

    Args:
        host: Target host IP or hostname
        port: Target port (usually 22 for SSH, 23 for Telnet)
        timeout: Connection timeout in seconds

    Returns:
        True if port is open, False otherwise
    """
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        return result == 0  # 0 means connection successful
    except Exception as e:
        return False
    finally:
        # Always close socket to prevent file descriptor leak
        if sock:
            try:
                sock.close()
            except:
                pass


def clean_device_output(output: str, vendor: str = '', command: str = '') -> str:
    """
    Clean command output from prompts, echo commands, and extra characters

    Args:
        output: Raw command output
        vendor: Device vendor (for vendor-specific cleaning)
        command: The command that was executed (to remove echo)

    Returns:
        Cleaned configuration string
    """
    lines = output.split('\n')
    cleaned_lines = []

    for line in lines:
        # Remove ANSI escape codes
        line = re.sub(r'\x1b\[[0-9;]*m', '', line)
        # Remove carriage returns and other control characters
        line = re.sub(r'\r', '', line)
        # Remove --More-- and similar paging markers
        line = re.sub(r'--More--|-- More --|<--- More --->', '', line)

        # Strip whitespace for checking
        stripped = line.strip()

        # Skip empty lines
        if not stripped:
            continue

        # MikroTik specific cleaning
        if vendor == 'mikrotik':
            # Skip MikroTik prompts: [admin@MikroTik] > or [admin@MikroTik] /export
            if re.match(r'^\[.*?\]\s*[>\/]', stripped):
                continue
            # Keep everything else including comments starting with #
            cleaned_lines.append(line.rstrip())
            continue

        # For Fortinet, skip console config lines
        if vendor == 'fortinet':
            if 'config system console' in stripped.lower():
                continue
            if stripped.lower() in ['set output standard', 'end']:
                continue
            if re.match(r'^[A-Z0-9]+\s+\(.*\)\s+[#>]', stripped):
                continue

        # Skip the command echo (exact match or at end of prompt)
        if command and command in stripped:
            continue

        # Skip device prompts (ending with # or >)
        # Router#, Switch>, etc
        if re.match(r'^[^\s#>]+[#>]\s*$', stripped):
            continue

        # Keep the line
        cleaned_lines.append(line.rstrip())

    # Join lines and remove leading/trailing empty lines
    result = '\n'.join(cleaned_lines)
    return result.strip()


class SSHConnection:
    """SSH connection handler for network devices"""

    def __init__(self, host: str, port: int, username: str, password: str,
                 enable_password: Optional[str] = None, timeout: int = 30, vendor: str = ''):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.enable_password = enable_password
        self.timeout = timeout
        self.vendor = vendor
        self.client: Optional[paramiko.SSHClient] = None
        self.shell: Optional[paramiko.Channel] = None
        self.backup_commands: Optional[dict] = None  # Store backup_commands for logout

    def connect(self) -> None:
        """Establish SSH connection"""
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(LoggingAutoAddPolicy())

            self.client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=self.timeout,
                look_for_keys=False,
                allow_agent=False
            )

            # Open interactive shell
            self.shell = self.client.invoke_shell()
            time.sleep(1)

            # Clear initial output
            if self.shell.recv_ready():
                self.shell.recv(65535)

        except paramiko.AuthenticationException:
            raise DeviceConnectionError(f"Authentication failed for {self.host}")
        except paramiko.SSHException as e:
            raise DeviceConnectionError(f"SSH error connecting to {self.host}: {str(e)}")
        except socket.timeout:
            raise DeviceConnectionError(f"Connection timeout to {self.host}")
        except Exception as e:
            raise DeviceConnectionError(f"Failed to connect to {self.host}: {str(e)}")

    def send_command(self, command: str, wait_time: float = 2, handle_paging: bool = True) -> str:
        """
        Send command and return output

        Args:
            command: Command to execute
            wait_time: Time to wait for output (seconds)
            handle_paging: Automatically handle paging prompts like --More--

        Returns:
            Command output as string
        """
        if not self.shell:
            raise DeviceConnectionError("Not connected")

        try:
            # Send command
            self.shell.send(command + '\n')
            time.sleep(wait_time)

            # Collect output with automatic paging handling
            output = ""
            max_iterations = 100  # Prevent infinite loops
            iteration = 0
            no_data_count = 0

            while iteration < max_iterations:
                if self.shell.recv_ready():
                    chunk = self.shell.recv(65535).decode('utf-8', errors='ignore')
                    if chunk:
                        output += chunk
                        no_data_count = 0
                    time.sleep(0.1)

                    # Check for paging prompts and send space to continue
                    if handle_paging and ('--More--' in chunk or '-- More --' in chunk or
                                         '(more)' in chunk.lower() or 'press any key' in chunk.lower()):
                        self.shell.send(' ')  # Send space to continue
                        time.sleep(0.5)
                        iteration += 1
                        continue
                else:
                    no_data_count += 1
                    # If no data for 3 consecutive checks, consider command done
                    if no_data_count >= 3:
                        break
                    time.sleep(0.2)
                iteration += 1

            return output

        except Exception as e:
            raise DeviceConnectionError(f"Error sending command: {str(e)}")

    def send_command_exec(self, command: str, timeout: int = 30) -> str:
        """
        Send command using exec_command instead of interactive shell
        Used for devices like MikroTik where invoke_shell doesn't work properly

        Args:
            command: Command to execute
            timeout: Command timeout in seconds

        Returns:
            Command output as string
        """
        if not self.client:
            raise DeviceConnectionError("Not connected")

        try:
            stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
            output = stdout.read().decode('utf-8', errors='ignore')
            errors = stderr.read().decode('utf-8', errors='ignore')

            if errors:
                raise DeviceConnectionError(f"Command error: {errors}")

            return output

        except Exception as e:
            raise DeviceConnectionError(f"Error executing command: {str(e)}")

    def send_commands(self, commands: List[str], wait_time: float = 2) -> List[str]:
        """
        Send multiple commands and return their outputs

        Args:
            commands: List of commands to execute
            wait_time: Time to wait between commands

        Returns:
            List of command outputs
        """
        outputs = []
        for command in commands:
            output = self.send_command(command, wait_time)
            outputs.append(output)
        return outputs

    def enable_mode(self) -> str:
        """Enter enable/privileged mode (for Cisco-like devices)"""
        if not self.enable_password:
            return ""

        output = self.send_command("enable", wait_time=1)
        output += self.send_command(self.enable_password, wait_time=1)
        return output

    def get_config(self, vendor: str, backup_commands: dict = None) -> str:
        """
        Get device configuration based on vendor

        Args:
            vendor: Device vendor slug (cisco, juniper, huawei, etc.)
            backup_commands: Optional dict with 'setup' and 'backup' commands
                           Format: {'setup': ['cmd1', 'cmd2'], 'backup': 'show running-config'}

        Returns:
            Configuration as string
        """
        vendor = vendor.lower()

        # Store backup_commands for logout (used in disconnect())
        self.backup_commands = backup_commands

        # Backup commands should come from database (Vendor model)
        # If not provided, use generic fallback
        if backup_commands:
            setup_commands = backup_commands.get('setup', [])
            show_command = backup_commands.get('backup', 'show running-config')
            need_enable = backup_commands.get('enable_mode', False)
        else:
            # Fallback for missing vendor config (should not happen in production)
            setup_commands = []
            show_command = 'show running-config'
            need_enable = False

        # Enable mode if needed
        if need_enable:
            self.enable_mode()

        # Execute setup commands (don't capture output)
        for cmd in setup_commands:
            self.send_command(cmd, wait_time=1)

        # MikroTik requires exec_command instead of invoke_shell for /export
        if vendor == 'mikrotik':
            config = self.send_command_exec(show_command, timeout=30)
        else:
            # Get configuration (different wait times per vendor)
            wait_time = 10 if vendor == 'mikrotik' else 3
            config = self.send_command(show_command, wait_time=wait_time)

        return clean_device_output(config, vendor, show_command)

    def _get_logout_commands(self) -> List[str]:
        """
        Get vendor-specific logout commands from backup_commands or fallback to defaults

        Logout commands can be customized in backup_commands JSON field.
        Structure: {"logout": ["end", "exit"]}

        Returns multiple commands to handle different modes (enable, config, etc.)

        Returns:
            List of logout commands to send sequentially
        """
        # Try to get logout commands from stored backup_commands (from DB)
        if self.backup_commands and isinstance(self.backup_commands, dict):
            logout_cmds = self.backup_commands.get('logout', [])
            if isinstance(logout_cmds, list) and logout_cmds:
                return logout_cmds

        # Fallback to default for backward compatibility and generic devices
        # Default: 'end' to exit config mode, then 'exit' to logout (works for most Cisco-like devices)
        return ['end', 'exit']

    def disconnect(self) -> None:
        """Close SSH connection gracefully with vendor-specific logout commands"""
        try:
            if self.shell and self.shell.get_transport() and self.shell.get_transport().is_active():
                # Send vendor-specific logout commands to gracefully close session
                # This prevents hanging VTY lines and "Connection reset by peer" logs
                try:
                    logout_commands = self._get_logout_commands()
                    for cmd in logout_commands:
                        self.shell.send(f'{cmd}\n')
                        time.sleep(0.3)  # Brief pause between commands
                    time.sleep(0.5)  # Give device time to process logout
                except:
                    pass  # If sending logout commands fails, continue with forced close

            if self.shell:
                self.shell.close()
            if self.client:
                self.client.close()
        except Exception as e:
            # Ensure connection is closed even if graceful exit fails
            try:
                if self.shell:
                    self.shell.close()
            except:
                pass
            try:
                if self.client:
                    self.client.close()
            except:
                pass

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()


class TelnetConnection:
    """Telnet connection handler for network devices"""

    def __init__(self, host: str, port: int, username: str, password: str,
                 enable_password: Optional[str] = None, timeout: int = 30, vendor: str = ''):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.enable_password = enable_password
        self.timeout = timeout
        self.vendor = vendor
        self.connection: Optional[telnetlib.Telnet] = None
        self.backup_commands: Optional[dict] = None  # Store backup_commands for logout

    def connect(self) -> None:
        """Establish Telnet connection"""
        try:
            self.connection = telnetlib.Telnet(self.host, self.port, self.timeout)

            # Wait for login prompt
            self.connection.read_until(b"sername:", timeout=10)
            self.connection.write(self.username.encode('ascii') + b'\n')

            # Wait for password prompt
            self.connection.read_until(b"assword:", timeout=10)
            self.connection.write(self.password.encode('ascii') + b'\n')

            time.sleep(2)

        except socket.timeout:
            raise DeviceConnectionError(f"Connection timeout to {self.host}")
        except Exception as e:
            raise DeviceConnectionError(f"Failed to connect to {self.host}: {str(e)}")

    def send_command(self, command: str, wait_time: float = 2, handle_paging: bool = True) -> str:
        """Send command and return output with automatic paging handling"""
        if not self.connection:
            raise DeviceConnectionError("Not connected")

        try:
            self.connection.write(command.encode('ascii') + b'\n')
            time.sleep(wait_time)

            output = ""
            max_iterations = 100
            iteration = 0

            while iteration < max_iterations:
                chunk = self.connection.read_very_eager().decode('utf-8', errors='ignore')
                if chunk:
                    output += chunk

                    # Check for paging prompts and send space to continue
                    if handle_paging and ('--More--' in chunk or '-- More --' in chunk or
                                         '(more)' in chunk.lower() or 'press any key' in chunk.lower()):
                        self.connection.write(b' ')  # Send space to continue
                        time.sleep(0.5)
                        iteration += 1
                        continue

                    time.sleep(0.1)
                else:
                    break
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

    def get_config(self, vendor: str, backup_commands: dict = None) -> str:
        """
        Get device configuration based on vendor

        Args:
            vendor: Device vendor slug (cisco, juniper, huawei, etc.)
            backup_commands: Optional dict with 'setup' and 'backup' commands
                           Format: {'setup': ['cmd1', 'cmd2'], 'backup': 'show running-config'}

        Returns:
            Configuration as string
        """
        vendor = vendor.lower()

        # Store backup_commands for logout (used in disconnect())
        self.backup_commands = backup_commands

        # Backup commands should come from database (Vendor model)
        # If not provided, use generic fallback
        if backup_commands:
            setup_commands = backup_commands.get('setup', [])
            show_command = backup_commands.get('backup', 'show running-config')
            need_enable = backup_commands.get('enable_mode', False)
        else:
            # Fallback for missing vendor config (should not happen in production)
            setup_commands = []
            show_command = 'show running-config'
            need_enable = False

        # Enable mode if needed
        if need_enable:
            self.enable_mode()

        # Execute setup commands (don't capture output)
        for cmd in setup_commands:
            self.send_command(cmd, wait_time=1)

        # Get configuration (MikroTik needs more time)
        wait_time = 10 if vendor == 'mikrotik' else 3
        config = self.send_command(show_command, wait_time=wait_time)

        # Use the same cleaning method
        return clean_device_output(config, vendor, show_command)

    def _get_logout_commands(self) -> List[str]:
        """
        Get vendor-specific logout commands from backup_commands or fallback to defaults

        Logout commands can be customized in backup_commands JSON field.
        Structure: {"logout": ["end", "exit"]}

        Returns multiple commands to handle different modes (enable, config, etc.)

        Returns:
            List of logout commands to send sequentially
        """
        # Try to get logout commands from stored backup_commands (from DB)
        if self.backup_commands and isinstance(self.backup_commands, dict):
            logout_cmds = self.backup_commands.get('logout', [])
            if isinstance(logout_cmds, list) and logout_cmds:
                return logout_cmds

        # Fallback to default for backward compatibility and generic devices
        # Default: 'end' to exit config mode, then 'exit' to logout (works for most Cisco-like devices)
        return ['end', 'exit']

    def disconnect(self) -> None:
        """Close Telnet connection gracefully with vendor-specific logout commands"""
        try:
            if self.connection:
                # Send vendor-specific logout commands to gracefully close session
                # This prevents hanging VTY lines and "Connection reset by peer" logs
                try:
                    logout_commands = self._get_logout_commands()
                    for cmd in logout_commands:
                        self.connection.write(f'{cmd}\n'.encode('ascii'))
                        time.sleep(0.3)  # Brief pause between commands
                    time.sleep(0.5)  # Give device time to process logout
                except:
                    pass  # If sending logout commands fails, continue with forced close

                self.connection.close()
        except Exception as e:
            # Ensure connection is closed even if graceful exit fails
            try:
                if self.connection:
                    self.connection.close()
            except:
                pass

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()


def test_connection(host: str, port: int, protocol: str, username: str,
                   password: str, enable_password: Optional[str] = None,
                   timeout: int = 10) -> Tuple[bool, str]:
    """
    Test device connection

    Returns:
        Tuple of (success: bool, message: str)
    """
    # SSRF protection - resolve DNS and block loopback addresses
    try:
        resolved_host = validate_target_host(host)
    except DeviceConnectionError as e:
        return False, str(e)

    try:
        if protocol.lower() == 'ssh':
            with SSHConnection(resolved_host, port, username, password, enable_password, timeout) as conn:
                output = conn.send_command('show version', wait_time=1)
                return True, "Connection successful"
        else:
            with TelnetConnection(resolved_host, port, username, password, enable_password, timeout) as conn:
                output = conn.send_command('show version', wait_time=1)
                return True, "Connection successful"
    except Exception as e:
        return False, str(e)


def backup_device_config(host: str, port: int, protocol: str, username: str,
                        password: str, vendor: str, enable_password: Optional[str] = None,
                        timeout: int = 30, backup_commands: dict = None) -> Tuple[bool, str, str]:
    """
    Backup device configuration

    Args:
        host: Device IP address
        port: Connection port
        protocol: ssh or telnet
        username: Login username
        password: Login password
        vendor: Vendor slug
        enable_password: Optional enable password
        timeout: Connection timeout
        backup_commands: Optional dict with custom commands
                        Format: {'setup': ['cmd1'], 'backup': 'show config', 'enable_mode': True}

    Returns:
        Tuple of (success: bool, config: str, error_message: str)
    """
    # SSRF protection - resolve DNS and block loopback addresses
    try:
        resolved_host = validate_target_host(host)
    except DeviceConnectionError as e:
        return False, "", str(e)

    try:
        if protocol.lower() == 'ssh':
            with SSHConnection(resolved_host, port, username, password, enable_password, timeout, vendor) as conn:
                config = conn.get_config(vendor, backup_commands)
                return True, config, ""
        else:
            with TelnetConnection(resolved_host, port, username, password, enable_password, timeout, vendor) as conn:
                config = conn.get_config(vendor, backup_commands)
                return True, config, ""
    except Exception as e:
        return False, "", str(e)
