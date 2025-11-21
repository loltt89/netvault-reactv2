from rest_framework import serializers
from .models import Backup, BackupSchedule, BackupRetentionPolicy
from devices.serializers import DeviceSerializer


class BackupSerializer(serializers.ModelSerializer):
    """Backup serializer for list view"""

    device = serializers.SerializerMethodField()
    triggered_by_email = serializers.CharField(source='triggered_by.email', read_only=True, allow_null=True)

    class Meta:
        model = Backup
        fields = [
            'id', 'device',
            'status', 'backup_type', 'size_bytes',
            'started_at', 'completed_at', 'duration_seconds',
            'success', 'error_message',
            'has_changes', 'changes_summary',
            'triggered_by_email', 'created_at'
        ]
        read_only_fields = [
            'id', 'triggered_by_email',
            'created_at', 'configuration_hash'
        ]

    def get_device(self, obj):
        """Return device info"""
        if obj.device:
            return {
                'id': obj.device.id,
                'name': obj.device.name,
                'ip_address': obj.device.ip_address,
                'vendor': {
                    'id': obj.device.vendor.id,
                    'name': obj.device.vendor.name,
                    'slug': obj.device.vendor.slug
                } if obj.device.vendor else None,
            }
        return None


class BackupDetailSerializer(serializers.ModelSerializer):
    """Detailed backup serializer with configuration"""

    device = DeviceSerializer(read_only=True)
    triggered_by_email = serializers.CharField(source='triggered_by.email', read_only=True, allow_null=True)
    configuration = serializers.SerializerMethodField()

    class Meta:
        model = Backup
        fields = [
            'id', 'device',
            'status', 'backup_type', 'size_bytes', 'configuration_hash',
            'started_at', 'completed_at', 'duration_seconds',
            'success', 'error_message', 'output_log',
            'has_changes', 'changes_summary',
            'triggered_by_email', 'created_at', 'configuration'
        ]
        read_only_fields = ['id', 'created_at']

    def get_configuration(self, obj):
        """Return decrypted configuration if user has permission"""
        try:
            return obj.get_configuration()
        except Exception:
            return None


class BackupScheduleSerializer(serializers.ModelSerializer):
    """Backup Schedule serializer"""

    created_by_email = serializers.CharField(source='created_by.email', read_only=True, allow_null=True)
    devices_count = serializers.SerializerMethodField()

    class Meta:
        model = BackupSchedule
        fields = [
            'id', 'name', 'description',
            'frequency', 'run_time', 'run_days',
            'devices', 'devices_count',
            'is_active',
            'last_run', 'next_run',
            'total_runs', 'successful_runs', 'failed_runs',
            'created_at', 'updated_at', 'created_by_email'
        ]
        read_only_fields = [
            'id', 'devices_count', 'created_by_email',
            'last_run', 'next_run', 'total_runs',
            'successful_runs', 'failed_runs',
            'created_at', 'updated_at'
        ]

    def get_devices_count(self, obj):
        """Return count of devices"""
        return obj.devices.count()


class BackupRetentionPolicySerializer(serializers.ModelSerializer):
    """Backup Retention Policy serializer"""

    devices_count = serializers.IntegerField(read_only=True, source='devices.count')

    class Meta:
        model = BackupRetentionPolicy
        fields = [
            'id', 'name', 'description',
            'keep_last_n', 'keep_daily', 'keep_weekly', 'keep_monthly',
            'is_active', 'auto_delete',
            'devices_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'devices_count', 'created_at', 'updated_at']
