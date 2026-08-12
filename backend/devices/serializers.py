import ipaddress
import re

from rest_framework import serializers
from .models import Vendor, DeviceType, Device
from .connection import _never_a_device
from core.utils import validate_csv_safe

# Pattern for validating network commands (whitelist approach)
SAFE_COMMAND_PATTERN = re.compile(r'^[a-zA-Z0-9\s\-_.:/@#|"\'=]+$')

# Dangerous commands blacklist - can damage device or network
# These commands should NEVER be used in backup operations
DANGEROUS_COMMANDS = [
    # Reboot/shutdown
    'reload', 'reboot', 'shutdown', 'reset', 'restart',
    # Erase config
    'write erase', 'erase startup', 'erase nvram', 'erase flash',
    'delete startup', 'clear startup', 'reset factory',
    # Format/delete
    'format', 'delete', 'remove', 'destroy',
    # Config replacement (can overwrite running config)
    'configure replace', 'copy tftp', 'copy ftp', 'copy scp',
    'copy running', 'copy startup',
    # Debug (can overload CPU)
    'debug all', 'undebug all', 'debug ip packet',
    # Dangerous Huawei
    'reset saved-configuration', 'startup saved-configuration',
    # Dangerous Juniper
    'request system reboot', 'request system halt',
    # Dangerous Nokia
    'admin reboot', 'admin save',
    # Dangerous Fortinet
    'execute reboot', 'execute shutdown', 'execute factoryreset',
    # Dangerous MikroTik
    '/system reset', '/system reboot', '/system shutdown',
]

# Known keys for backup_commands schema
BACKUP_COMMANDS_KEYS = {
    'setup', 'backup', 'enable_mode', 'config_start', 'config_end',
    'skip_patterns', 'exec_mode', 'exec_wrapper', 'logout'
}


def _validate_command(cmd, cmd_type):
    """Validate single command against whitelist and blacklist"""
    if not cmd or not cmd.strip():
        raise serializers.ValidationError(f'{cmd_type} command cannot be empty')
    if len(cmd) > 500:
        raise serializers.ValidationError(f'{cmd_type} command too long (max 500 chars)')
    if not SAFE_COMMAND_PATTERN.match(cmd):
        raise serializers.ValidationError(
            f'{cmd_type} command contains invalid characters. '
            f'Allowed: letters, numbers, spaces, - _ . : / @ # | " \' ='
        )

    # Check against dangerous commands blacklist
    cmd_lower = cmd.lower().strip()
    for dangerous in DANGEROUS_COMMANDS:
        if dangerous in cmd_lower:
            raise serializers.ValidationError(
                f'{cmd_type} command contains dangerous operation "{dangerous}". '
                f'This command can damage device configuration or cause downtime. '
                f'Backup commands should only READ configuration, not modify it.'
            )


def validate_backup_commands(value, field_name='backup_commands'):
    """
    Validate backup_commands JSON structure (used by both Vendor and Device custom_commands)
    Expected format:
    {
        'backup': 'show running-config',      # required, string - main backup command
        'setup': ['terminal length 0'],       # optional, list - pre-commands
        'enable_mode': True,                  # optional, bool - needs enable password
        'config_start': ['!', 'version'],     # optional, list - markers for config start
        'config_end': ['end'],                # optional, list - markers for config end
        'skip_patterns': ['Building config'], # optional, list - lines to skip
        'exec_mode': False,                   # optional, bool - for MikroTik exec mode
        'exec_wrapper': '',                   # optional, string - for VyOS
        'logout': ['exit']                    # optional, list - logout commands
    }
    """
    if not isinstance(value, dict):
        raise serializers.ValidationError(f'{field_name} must be a JSON object')

    # Check required 'backup' field
    if 'backup' not in value:
        raise serializers.ValidationError(f'{field_name} must contain "backup" field')

    if not isinstance(value['backup'], str) or not value['backup'].strip():
        raise serializers.ValidationError('backup command must be a non-empty string')

    # Validate backup command
    _validate_command(value.get('backup', ''), 'Backup')

    # Check list fields
    list_fields = ['setup', 'config_start', 'config_end', 'skip_patterns', 'logout']
    for field in list_fields:
        if field in value:
            if not isinstance(value[field], list):
                raise serializers.ValidationError(f'{field} must be a list')
            if not all(isinstance(item, str) for item in value[field]):
                raise serializers.ValidationError(f'{field} items must be strings')
            # Validate each command/pattern
            for i, item in enumerate(value[field]):
                if field in ['setup', 'logout']:
                    _validate_command(item, f'{field}[{i}]')

    # Check boolean fields
    bool_fields = ['enable_mode', 'exec_mode']
    for field in bool_fields:
        if field in value and not isinstance(value[field], bool):
            raise serializers.ValidationError(f'{field} must be a boolean')

    # Check string fields — exec_wrapper gets concatenated directly onto the
    # backup command and sent to the device shell (devices/connection.py's
    # get_config: f'{exec_wrapper} {show_command}'), exactly like `backup`
    # and the `setup`/`logout` list items above, so it needs the same
    # whitelist/blacklist pass. It used to be type-checked only. This
    # function backs both Device.custom_commands (admin-only, gated in
    # DeviceCreateSerializer._validate_and_sanitize_data) AND
    # Vendor.backup_commands (VendorSerializer — no admin gate at all,
    # writable by any 'operator' via CanManageDevices, and used for every
    # device of that vendor that doesn't set its own custom_commands) — so
    # the unvalidated exec_wrapper was reachable by an operator either way,
    # letting them smuggle a command like 'reload' or 'erase' straight past
    # DANGEROUS_COMMANDS.
    if 'exec_wrapper' in value:
        if not isinstance(value['exec_wrapper'], str):
            raise serializers.ValidationError('exec_wrapper must be a string')
        if value['exec_wrapper'].strip():
            _validate_command(value['exec_wrapper'], 'exec_wrapper')

    # Warn about unknown keys
    unknown_keys = set(value.keys()) - BACKUP_COMMANDS_KEYS
    if unknown_keys:
        raise serializers.ValidationError(
            f'Unknown keys in {field_name}: {", ".join(unknown_keys)}. '
            f'Valid keys are: {", ".join(sorted(BACKUP_COMMANDS_KEYS))}'
        )

    # Check total command chain length (C buffer is 4096, keep margin for ||| separators)
    MAX_TOTAL_CMD_LENGTH = 3500
    total_len = len(value.get('backup', ''))
    for cmd in value.get('setup', []):
        total_len += len(cmd) + 3  # +3 for ||| separator
    for cmd in value.get('logout', []):
        total_len += len(cmd) + 3
    if value.get('exec_wrapper'):
        total_len += len(value['exec_wrapper']) + 3

    if total_len > MAX_TOTAL_CMD_LENGTH:
        raise serializers.ValidationError(
            f'Total command chain too long ({total_len} chars). '
            f'Maximum allowed: {MAX_TOTAL_CMD_LENGTH} chars. '
            f'Reduce number or length of setup/backup/logout commands.'
        )

    return value


def validate_custom_commands(value):
    """Validate custom_commands - wrapper for backward compatibility"""
    return validate_backup_commands(value, field_name='custom_commands')


class VendorSerializer(serializers.ModelSerializer):
    """Vendor serializer"""

    class Meta:
        model = Vendor
        fields = [
            'id', 'name', 'slug', 'description', 'logo_url',
            'is_predefined', 'backup_commands', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_backup_commands(self, value):
        """Validate backup_commands JSON structure"""
        if value:
            return validate_backup_commands(value)
        return value


class DeviceTypeSerializer(serializers.ModelSerializer):
    """Device Type serializer"""

    class Meta:
        model = DeviceType
        fields = ['id', 'name', 'slug', 'description', 'icon', 'is_predefined']
        read_only_fields = ['id', 'is_predefined']


class DeviceSerializer(serializers.ModelSerializer):
    """Device serializer for list view"""

    vendor_name = serializers.CharField(source='vendor.name', read_only=True)
    device_type_name = serializers.CharField(source='device_type.name', read_only=True)

    class Meta:
        model = Device
        fields = [
            'id', 'name', 'ip_address', 'description',
            'vendor', 'vendor_name',
            'device_type', 'device_type_name',
            'protocol', 'port', 'username',
            'location', 'tags', 'criticality',
            'status', 'last_seen', 'last_backup', 'backup_status',
            'backup_enabled', 'backup_schedule',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'vendor_name',
            'device_type_name', 'status', 'last_seen',
            'last_backup', 'backup_status'
        ]
        extra_kwargs = {
            'password_encrypted': {'write_only': True},
            'enable_password_encrypted': {'write_only': True},
        }


class DeviceCreateSerializer(serializers.ModelSerializer):
    """Device serializer for create/update with password handling"""

    password = serializers.CharField(write_only=True, required=False, allow_blank=True, default='')
    enable_password = serializers.CharField(write_only=True, required=False, allow_blank=True, default='')

    class Meta:
        model = Device
        fields = [
            'id', 'name', 'ip_address', 'description',
            'vendor', 'device_type',
            'protocol', 'port', 'username', 'password', 'enable_password',
            'location', 'tags', 'criticality',
            'backup_enabled', 'backup_schedule', 'custom_commands',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_ip_address(self, value):
        """
        Reject IP ranges that can never legitimately be a network device —
        same check devices/connection.py's validate_target_host runs before
        actually connecting (see _never_a_device's docstring for why it's
        shared rather than duplicated). This is the fail-fast half of that
        defense: catch it here with an immediate form error instead of only
        discovering it the first time someone clicks "Test connection".
        """
        reason = _never_a_device(ipaddress.ip_address(value))
        if reason:
            raise serializers.ValidationError(f'{value} cannot be used as a device address: {reason}.')
        return value

    def _validate_and_sanitize_data(self, validated_data):
        """
        Validate device data (shared logic for create/update)

        - Restricts custom_commands to administrators only (RCE prevention)
        - Validates text fields for CSV safety (rejects dangerous values)
        - Validates custom_commands structure

        Note: CSV sanitization (adding ' prefix) is done at EXPORT time, not storage time.
        Database stores raw values.
        """
        # Only administrators can set custom_commands (prevents RCE by operators)
        user = self.context['request'].user
        if user.role != 'administrator':
            validated_data.pop('custom_commands', None)

        # Validate text fields are safe for CSV export (reject dangerous values)
        validation_errors = {}

        for field in ['name', 'description', 'location', 'username']:
            if field in validated_data and validated_data[field]:
                try:
                    validate_csv_safe(validated_data[field], field_name=field.capitalize())
                except ValueError as e:
                    validation_errors[field] = str(e)

        if validation_errors:
            raise serializers.ValidationError(validation_errors)

        # Validate custom_commands structure
        if 'custom_commands' in validated_data and validated_data['custom_commands']:
            validate_custom_commands(validated_data['custom_commands'])

    def create(self, validated_data):
        password = validated_data.pop('password')
        enable_password = validated_data.pop('enable_password', '')

        # Validate and sanitize data
        self._validate_and_sanitize_data(validated_data)

        device = Device(**validated_data)
        device.set_password(password)
        if enable_password:
            device.set_enable_password(enable_password)

        device.created_by = self.context['request'].user
        device.save()
        return device

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        enable_password = validated_data.pop('enable_password', None)

        # Validate and sanitize data
        self._validate_and_sanitize_data(validated_data)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)
        if enable_password is not None:
            instance.set_enable_password(enable_password)

        instance.save()
        return instance


class DeviceDetailSerializer(serializers.ModelSerializer):
    """Detailed device serializer"""

    vendor = VendorSerializer(read_only=True)
    device_type = DeviceTypeSerializer(read_only=True)
    created_by_email = serializers.CharField(source='created_by.email', read_only=True, allow_null=True)
    backup_count = serializers.IntegerField(read_only=True, source='backups.count')
    has_pending_ssh_host_key = serializers.BooleanField(read_only=True)

    class Meta:
        model = Device
        fields = [
            'id', 'name', 'ip_address', 'description',
            'vendor', 'device_type',
            'protocol', 'port', 'username',
            'location', 'tags', 'criticality',
            'status', 'last_seen', 'last_backup', 'backup_status', 'backup_count',
            'backup_enabled', 'backup_schedule', 'custom_commands',
            'ssh_host_key_type', 'ssh_host_key_fingerprint', 'ssh_host_key_verified_at',
            'ssh_host_key_pending_type', 'ssh_host_key_pending_fingerprint',
            'ssh_host_key_pending_detected_at', 'has_pending_ssh_host_key',
            'created_at', 'updated_at', 'created_by_email'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'created_by_email', 'backup_count',
            'ssh_host_key_type', 'ssh_host_key_fingerprint', 'ssh_host_key_verified_at',
            'ssh_host_key_pending_type', 'ssh_host_key_pending_fingerprint',
            'ssh_host_key_pending_detected_at', 'has_pending_ssh_host_key',
        ]
