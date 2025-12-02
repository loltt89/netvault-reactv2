"""
Device connection utilities for SSH and Telnet
Uses native netvault-ssh binary for SSH v1/v2 support
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

logger = logging.getLogger(__name__)

# Path to netvault-ssh binary
NETVAULT_SSH_BIN = os.path.join(os.path.dirname(__file__), '..', 'tools', 'netvault-ssh', 'netvault-ssh')

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

    if ip.is_loopback:
        raise DeviceConnectionError(
            f"Connection to loopback address {resolved_ip} is forbidden for security reasons."
        )

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
        'bad command', 'incomplete command', 'command authorization failed'
    ]

    if not config or not config.strip():
        return False, "Configuration is empty"

    lines = []
    for line in config.strip().split('\n'):
        stripped = line.strip()
        if stripped:
            lines.append(line)
            if len(lines) >= 15:
                break

    if len(lines) < 5:
        return False, f"Configuration too short: {len(lines)} lines (minimum 5 required)"

    first_lines = '\n'.join(lines[:5]).lower()
    for pattern in ERROR_PATTERNS:
        if pattern in first_lines:
            return False, f"Error detected in configuration output: '{pattern}'"

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


def clean_device_output(output: str, vendor: str = '', command: str = '') -> str:
    """Clean command output from prompts and control characters"""
    # First, clean control characters
    output = ANSI_ESCAPE_PATTERN.sub('', output)
    output = CARRIAGE_RETURN_PATTERN.sub('', output)
    output = MORE_PAGING_PATTERN.sub('', output)

    vendor = vendor.lower()

    # Normalize vendor slug to base name (e.g., 'fortinet-fortigate' -> 'fortinet')
    vendor_aliases = {
        'fortinet-fortigate': 'fortinet',
        'cisco-ios-xr': 'iosxr',
        'cisco-iosxr': 'iosxr',
        'cisco-nxos': 'nxos',
        'cisco-asa': 'asa',
        'juniper-junos': 'juniper',
        'arista-eos': 'arista',
        'hp-procurve': 'procurve',
        'hp-comware': 'huawei',  # Comware uses VRP-style commands
        'huawei-vrp': 'huawei',
        'extreme-networks': 'extreme',
        'ubiquiti-edgerouter': 'edgeos',
        'ubiquiti-unifi': 'ubiquiti',
        'checkpoint-gaia': 'checkpoint',
        'dell-force10': 'dell',
        'dell-powerconnect': 'powerconnect',
        'f5-networks': 'f5',
        'nokia-sros': 'nokia',
        'allied-telesis': 'allied',
        'a10-networks': 'cisco',  # A10 uses similar commands
        'citrix-netscaler': 'cisco',
    }

    if vendor in vendor_aliases:
        vendor = vendor_aliases[vendor]

    # Config start/end markers by vendor (based on Oxidized models)
    # https://github.com/ytti/oxidized/tree/master/lib/oxidized/model
    config_start_markers = {
        # Cisco family
        'cisco': ['Building configuration', 'Current configuration', '!', 'version '],
        'ios': ['Building configuration', 'Current configuration', '!', 'version '],
        'iosxe': ['Building configuration', 'Current configuration', '!', 'version '],
        'iosxr': ['Building configuration', '!! IOS XR', '!', 'hostname '],
        'nxos': ['!Command:', '!Running configuration', 'version '],
        'asa': ['ASA Version', ': Saved', '!'],
        'catos': ['begin', '#version', 'set '],
        'ciscosmb': ['!Current Configuration', 'sysinfo', 'vlan '],

        # Fortinet
        'fortinet': ['#config-version=', 'config system global', 'config '],
        'fortios': ['#config-version=', 'config system global', 'config '],
        'fortigate': ['#config-version=', 'config system global', 'config '],

        # Juniper
        'juniper': ['## Last commit', 'version ', 'system {', 'groups {'],
        'junos': ['## Last commit', 'version ', 'system {', 'groups {'],
        'screenos': ['set clock', 'set vrouter', 'set hostname'],

        # Huawei
        'huawei': ['#', 'sysname ', 'return', '<', 'version'],
        'vrp': ['#', 'sysname ', 'return', 'software'],

        # HP / Aruba / ProCurve
        'hp': ['Running configuration', ';', 'hostname '],
        'hpe': ['Running configuration', ';', 'hostname '],
        'procurve': ['Running configuration', ';', 'hostname '],
        'aruba': ['Running configuration', 'version', 'hostname '],
        'arubaos': ['Building configuration', 'version', '!'],
        'aoscx': ['Running configuration', 'hostname '],

        # Extreme
        'extreme': ['#', 'Module ', 'configure '],
        'xos': ['#', 'Module ', 'configure '],
        'exos': ['#', 'Module ', 'configure '],
        'enterasys': ['#', 'set '],

        # MikroTik
        'mikrotik': ['# ', '/', '# software id'],
        'routeros': ['# ', '/', '# software id'],

        # Arista
        'arista': ['! Command:', '! device:', '! boot', 'hostname '],
        'eos': ['! Command:', '! device:', '! boot', 'hostname '],

        # Dell
        'dell': ['!Current Configuration', 'hostname '],
        'dellos': ['!Current Configuration', 'hostname '],
        'ftos': ['!Current Configuration', 'hostname '],
        'dnos': ['!Current Configuration', 'hostname '],
        'powerconnect': ['!System Description', 'configure', 'hostname '],

        # Palo Alto
        'paloalto': ['<config ', '<entry ', 'set deviceconfig'],
        'panos': ['<config ', '<entry ', 'set deviceconfig'],

        # Ubiquiti
        'ubiquiti': ['firewall {', 'interfaces {', 'service {'],
        'edgeos': ['firewall {', 'interfaces {', 'service {'],
        'vyatta': ['firewall {', 'interfaces {', 'service {'],
        'vyos': ['firewall {', 'interfaces {', 'service {'],

        # Brocade / Ruckus
        'brocade': ['!', 'ver ', 'module '],
        'fastiron': ['!', 'ver ', 'module '],
        'icx': ['!', 'ver ', 'module '],

        # F5
        'f5': ['#TMSH-VERSION:', 'ltm ', 'sys '],
        'bigip': ['#TMSH-VERSION:', 'ltm ', 'sys '],
        'tmos': ['#TMSH-VERSION:', 'ltm ', 'sys '],

        # Alcatel / Nokia
        'alcatel': ['# TiMOS', 'configure ', 'echo '],
        'nokia': ['# TiMOS', 'configure ', 'echo '],
        'sros': ['# TiMOS', 'configure ', 'echo '],

        # Netgear
        'netgear': ['!Current Configuration', 'vlan ', 'hostname '],

        # Zyxel
        'zyxel': ['!', 'hostname ', 'vlan '],
        'zynos': ['!', 'hostname ', 'vlan '],

        # Allied Telesis
        'allied': ['!', 'hostname ', 'awplus '],
        'awplus': ['!', 'hostname ', 'awplus '],

        # Ciena
        'ciena': ['configuration ', '!', 'system '],
        'saos': ['configuration ', '!', 'system '],

        # Riverbed
        'riverbed': ['## ', 'hostname ', 'config '],

        # CheckPoint
        'checkpoint': [':set ', ':admininfo ', 'config '],
        'gaia': [':set ', ':admininfo ', 'config '],

        # Cumulus / NVIDIA
        'cumulus': ['# ', 'auto ', 'iface '],

        # Linux / OpenWrt
        'linux': ['# ', 'config ', 'option '],
        'openwrt': ['config ', 'option ', 'package '],

        # pfSense / OPNsense
        'pfsense': ['<?xml ', '<pfsense>', '<opnsense>'],
        'opnsense': ['<?xml ', '<pfsense>', '<opnsense>'],

        # Generic
        'generic': ['!', '#', 'hostname ', 'version ', 'config'],
    }

    config_end_markers = {
        # Cisco family
        'cisco': ['end'],
        'ios': ['end'],
        'iosxe': ['end'],
        'iosxr': ['end'],
        'nxos': ['end'],
        'asa': ['end'],
        'catos': ['end'],
        'ciscosmb': ['end'],

        # Arista
        'arista': ['end'],
        'eos': ['end'],

        # Huawei
        'huawei': ['return'],
        'vrp': ['return'],

        # HP
        'hp': [],
        'hpe': [],
        'procurve': [],
        'aruba': [],
        'arubaos': ['end'],
        'aoscx': [],

        # Others with no specific end marker - go to end of output
        'fortinet': [], 'fortios': [], 'fortigate': [],
        'juniper': [], 'junos': [], 'screenos': [],
        'extreme': [], 'xos': [], 'exos': [], 'enterasys': [],
        'mikrotik': [], 'routeros': [],
        'dell': [], 'dellos': [], 'ftos': [], 'dnos': [], 'powerconnect': [],
        'paloalto': [], 'panos': [],
        'ubiquiti': [], 'edgeos': [], 'vyatta': [], 'vyos': [],
        'brocade': [], 'fastiron': [], 'icx': [],
        'f5': [], 'bigip': [], 'tmos': [],
        'alcatel': [], 'nokia': [], 'sros': [],
        'netgear': [], 'zyxel': [], 'zynos': [],
        'allied': [], 'awplus': [],
        'ciena': [], 'saos': [],
        'riverbed': [],
        'checkpoint': [], 'gaia': [],
        'cumulus': [],
        'linux': [], 'openwrt': [],
        'pfsense': [], 'opnsense': [],
        'generic': ['end'],
    }

    lines = output.split('\n')

    # Find config start
    start_idx = 0
    start_markers = config_start_markers.get(vendor, ['!', '#', 'version', 'config'])
    for i, line in enumerate(lines):
        stripped = line.strip()
        for marker in start_markers:
            if stripped.startswith(marker) or marker in stripped:
                start_idx = i
                break
        if start_idx > 0:
            break

    # Find config end (search from the end)
    end_idx = len(lines)
    end_markers = config_end_markers.get(vendor, ['end', 'exit'])
    if end_markers:
        for i in range(len(lines) - 1, start_idx, -1):
            stripped = lines[i].strip().lower()
            if stripped in [m.lower() for m in end_markers]:
                end_idx = i + 1
                break

    # Extract config section
    config_lines = lines[start_idx:end_idx]

    # Final cleanup - remove any remaining prompt lines
    cleaned_lines = []
    for line in config_lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Skip obvious prompt lines (hostname# or hostname>)
        if DEVICE_PROMPT_PATTERN.match(stripped):
            continue

        # Skip command echo lines
        if command and stripped.endswith(command):
            continue

        cleaned_lines.append(line.rstrip())

    return '\n'.join(cleaned_lines).strip()


# ========== SSH Connection using netvault-ssh binary ==========

class SSHConnection:
    """SSH connection handler using netvault-ssh binary (supports SSH v1 and v2)"""

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
        self._connected = False

    def connect(self) -> None:
        """Test SSH connection"""
        result = self._run_ssh(mode='test')
        if not result['success']:
            raise DeviceConnectionError(result.get('error', 'Connection failed'))
        self._connected = True
        logger.info(f"Connected to {self.host} via netvault-ssh")

    def _run_ssh(self, mode: str = 'shell', commands: str = '', idle_ms: int = 500) -> dict:
        """Run netvault-ssh binary"""
        cmd = [
            NETVAULT_SSH_BIN,
            '-host', self.host,
            '-port', str(self.port),
            '-user', self.username,
            '-pass', self.password,
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
                text=True
            )

            # Parse JSON output
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                return {
                    'success': False,
                    'error': f"Invalid response: {result.stdout[:200]}"
                }

        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Command timeout'}
        except FileNotFoundError:
            return {'success': False, 'error': f'netvault-ssh binary not found at {NETVAULT_SSH_BIN}'}
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
        else:
            setup_commands = []
            show_command = 'show running-config'
            need_enable = False

        # Build command sequence
        all_commands = []

        if need_enable and self.enable_password:
            all_commands.extend(['enable', self.enable_password])

        all_commands.extend(setup_commands)

        # MikroTik uses exec mode
        if vendor == 'mikrotik':
            config = self.send_command_exec(show_command, timeout=30)
        else:
            all_commands.append(show_command)
            cmds_str = '|||'.join(all_commands)

            # Longer idle time for config output
            idle_ms = 2000 if vendor in ['mikrotik', 'fortinet'] else 1000

            result = self._run_ssh(mode='shell', commands=cmds_str, idle_ms=idle_ms)

            if not result['success']:
                raise DeviceConnectionError(result.get('error', 'Failed to get config'))

            config = result.get('output', '')

        return clean_device_output(config, vendor, show_command)

    def disconnect(self) -> None:
        """Disconnect (no-op for binary-based connection)"""
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
        """Send command and return output"""
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

            while iteration < max_iterations:
                if time.time() - start_time > read_timeout:
                    break

                try:
                    chunk = self.connection.read_very_eager().decode('utf-8', errors='ignore')
                except EOFError:
                    break

                if chunk:
                    output += chunk

                    if handle_paging and ('--More--' in chunk or '-- More --' in chunk or
                                         '(more)' in chunk.lower() or 'press any key' in chunk.lower()):
                        self.connection.write(b' ')
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

        return clean_device_output(config, vendor, show_command)

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
                   timeout: int = 5) -> Tuple[bool, str]:
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
            # Use shorter timeout for test - just verify we can authenticate
            conn = SSHConnection(resolved_host, port, username, password, enable_password, timeout=5)
            result = conn._run_ssh(mode='test')
            if result['success']:
                return True, "Connection successful"
            else:
                return False, result.get('error', 'Connection failed')
        else:
            with TelnetConnection(resolved_host, port, username, password, enable_password, timeout) as conn:
                return True, "Connection successful"
    except Exception as e:
        return False, str(e)


def backup_device_config(host: str, port: int, protocol: str, username: str,
                        password: str, vendor: str, enable_password: Optional[str] = None,
                        timeout: int = 30, backup_commands: dict = None) -> Tuple[bool, str, str]:
    """Backup device configuration"""
    try:
        resolved_host = validate_target_host(host)
    except DeviceConnectionError as e:
        return False, "", str(e)

    try:
        if protocol.lower() == 'ssh':
            with SSHConnection(resolved_host, port, username, password, enable_password, timeout, vendor) as conn:
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
