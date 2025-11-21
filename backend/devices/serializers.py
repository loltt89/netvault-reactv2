from rest_framework import serializers
from .models import Vendor, DeviceType, Device


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

    def create(self, validated_data):
        password = validated_data.pop('password')
        enable_password = validated_data.pop('enable_password', '')

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
