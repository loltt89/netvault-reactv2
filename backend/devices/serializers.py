from rest_framework import serializers
from .models import Vendor, DeviceType, Device
from core.utils import validate_csv_safe


def validate_custom_commands(value):
    """
    Validate custom_commands JSON structure
    Expected format:
    {
        'setup': ['cmd1', 'cmd2'],  # optional, list of strings
        'backup': 'show running-config',  # required, string
        'enable_mode': True  # optional, bool
    }
    """
    if not isinstance(value, dict):
        raise serializers.ValidationError('custom_commands must be a JSON object')

    # Check required 'backup' field
    if 'backup' not in value:
        raise serializers.ValidationError('custom_commands must contain "backup" field')

    if not isinstance(value['backup'], str) or not value['backup'].strip():
        raise serializers.ValidationError('backup command must be a non-empty string')

    # Check optional 'setup' field
    if 'setup' in value:
        if not isinstance(value['setup'], list):
            raise serializers.ValidationError('setup must be a list of commands')
        if not all(isinstance(cmd, str) for cmd in value['setup']):
            raise serializers.ValidationError('setup commands must be strings')

    # Check optional 'enable_mode' field
    if 'enable_mode' in value:
        if not isinstance(value['enable_mode'], bool):
            raise serializers.ValidationError('enable_mode must be a boolean')

    # Validate backup command doesn't contain shell metacharacters (security)
    backup_cmd = value.get('backup', '')
    dangerous_chars = ['|', '&', ';', '`', '$', '(', ')']
    if any(char in backup_cmd for char in dangerous_chars):
        raise serializers.ValidationError(
            f'Backup command cannot contain shell metacharacters: {" ".join(dangerous_chars)}'
        )

    # Validate setup commands too
    if 'setup' in value:
        for cmd in value['setup']:
            if any(char in cmd for char in dangerous_chars):
                raise serializers.ValidationError(
                    f'Setup commands cannot contain shell metacharacters: {" ".join(dangerous_chars)}'
                )

    # Warn about unknown keys
    known_keys = {'setup', 'backup', 'enable_mode'}
    unknown_keys = set(value.keys()) - known_keys
    if unknown_keys:
        raise serializers.ValidationError(
            f'Unknown keys in custom_commands: {", ".join(unknown_keys)}. '
            f'Valid keys are: {", ".join(known_keys)}'
        )

    return value


class VendorSerializer(serializers.ModelSerializer):
    """Vendor serializer"""

    class Meta:
        model = Vendor
        fields = [
            'id', 'name', 'slug', 'description', 'logo_url',
            'is_predefined', 'backup_commands', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


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

    password = serializers.CharField(write_only=True, required=True)
    enable_password = serializers.CharField(write_only=True, required=False, allow_blank=True)

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

    class Meta:
        model = Device
        fields = [
            'id', 'name', 'ip_address', 'description',
            'vendor', 'device_type',
            'protocol', 'port', 'username',
            'location', 'tags', 'criticality',
            'status', 'last_seen', 'last_backup', 'backup_status', 'backup_count',
            'backup_enabled', 'backup_schedule', 'custom_commands',
            'created_at', 'updated_at', 'created_by_email'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by_email', 'backup_count']
