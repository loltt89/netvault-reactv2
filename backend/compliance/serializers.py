from rest_framework import serializers
from .models import CompliancePolicy, ComplianceViolation


RULE_TYPES = ('must_contain', 'must_not_contain')


class CompliancePolicySerializer(serializers.ModelSerializer):
    created_by_email = serializers.CharField(source='created_by.email', read_only=True, allow_null=True)
    open_violation_count = serializers.SerializerMethodField()

    class Meta:
        model = CompliancePolicy
        fields = [
            'id', 'name', 'description', 'is_active', 'severity',
            'device_filters', 'rules',
            'created_at', 'updated_at', 'created_by_email', 'open_violation_count',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by_email', 'open_violation_count']

    def get_open_violation_count(self, obj):
        return obj.violations.filter(status='open').count()

    def validate_device_filters(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError('Must be an object, e.g. {"tags": ["core"]}.')
        return value

    def validate_rules(self, value):
        if not isinstance(value, list) or not value:
            raise serializers.ValidationError('Must be a non-empty list of rule objects.')

        for i, rule in enumerate(value):
            if not isinstance(rule, dict):
                raise serializers.ValidationError(f'Rule {i}: must be an object.')
            if rule.get('type') not in RULE_TYPES:
                raise serializers.ValidationError(
                    f'Rule {i}: "type" must be one of {RULE_TYPES}.'
                )
            if not rule.get('pattern'):
                raise serializers.ValidationError(f'Rule {i}: "pattern" is required.')
            if rule.get('is_regex'):
                import re
                try:
                    re.compile(rule['pattern'])
                except re.error as e:
                    raise serializers.ValidationError(f'Rule {i}: invalid regex — {e}')

        return value


class ComplianceViolationSerializer(serializers.ModelSerializer):
    policy_name = serializers.CharField(source='policy.name', read_only=True)
    policy_severity = serializers.CharField(source='policy.severity', read_only=True)
    device_name = serializers.CharField(source='device.name', read_only=True)
    device_ip = serializers.CharField(source='device.ip_address', read_only=True)

    class Meta:
        model = ComplianceViolation
        fields = [
            'id', 'policy', 'policy_name', 'policy_severity',
            'device', 'device_name', 'device_ip', 'backup',
            'rule_description', 'status', 'detected_at', 'last_seen_at', 'resolved_at',
        ]
        read_only_fields = fields
