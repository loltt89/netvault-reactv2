from rest_framework import serializers
from .models import NotificationRule, Notification


class NotificationRuleSerializer(serializers.ModelSerializer):
    """
    CRUD serializer for NotificationRule. created_by is set from the
    request user in the view, not accepted from the client.
    """
    created_by_email = serializers.CharField(source='created_by.email', read_only=True, allow_null=True)

    class Meta:
        model = NotificationRule
        fields = [
            'id', 'name', 'description', 'trigger', 'channel', 'is_active',
            'email_recipients', 'telegram_chat_ids', 'webhook_url',
            'device_filters',
            'created_at', 'updated_at', 'created_by_email',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by_email']

    def validate(self, attrs):
        channel = attrs.get('channel', getattr(self.instance, 'channel', None))

        if channel == 'webhook':
            webhook_url = attrs.get('webhook_url', getattr(self.instance, 'webhook_url', ''))
            if not webhook_url:
                raise serializers.ValidationError({'webhook_url': 'Required when channel is "webhook".'})

        if channel == 'email':
            recipients = attrs.get('email_recipients', getattr(self.instance, 'email_recipients', None))
            if recipients is not None and not isinstance(recipients, list):
                raise serializers.ValidationError({'email_recipients': 'Must be a list of email addresses.'})

        if channel == 'telegram':
            chat_ids = attrs.get('telegram_chat_ids', getattr(self.instance, 'telegram_chat_ids', None))
            if chat_ids is not None and not isinstance(chat_ids, list):
                raise serializers.ValidationError({'telegram_chat_ids': 'Must be a list of chat IDs.'})

        device_filters = attrs.get('device_filters')
        if device_filters is not None and not isinstance(device_filters, dict):
            raise serializers.ValidationError({'device_filters': 'Must be an object, e.g. {"tags": ["core"]}.'})

        return attrs


class NotificationSerializer(serializers.ModelSerializer):
    """Read-only serializer for the notification send log/audit trail."""
    rule_name = serializers.CharField(source='rule.name', read_only=True, allow_null=True)

    class Meta:
        model = Notification
        fields = [
            'id', 'rule', 'rule_name', 'status', 'title', 'message',
            'channel', 'recipient', 'sent_at', 'error_message', 'created_at',
        ]
        read_only_fields = fields
