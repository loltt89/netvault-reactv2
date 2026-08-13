import logging
from rest_framework import viewsets, permissions
from accounts.permissions import IsAdministrator, IsAuditorOrAdmin
from accounts.models import AuditLog
from .models import NotificationRule, Notification
from .serializers import NotificationRuleSerializer, NotificationSerializer

logger = logging.getLogger(__name__)


class NotificationRuleViewSet(viewsets.ModelViewSet):
    """
    CRUD for NotificationRule — same trust level as SystemSettings
    (defines where alerts, including webhook URLs, get sent), so
    administrator-only like the rest of system config.
    """
    queryset = NotificationRule.objects.all()
    serializer_class = NotificationRuleSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdministrator]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    filterset_fields = ['trigger', 'channel', 'is_active']

    def perform_create(self, serializer):
        rule = serializer.save(created_by=self.request.user)
        AuditLog.objects.create(
            user=self.request.user,
            action='create',
            resource_type='NotificationRule',
            resource_id=rule.id,
            resource_name=rule.name,
            description=f'Created notification rule: {rule.trigger} -> {rule.channel}',
            ip_address=self.request.META.get('REMOTE_ADDR'),
            user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
        )
        logger.info(f"Notification rule '{rule.name}' created by {self.request.user.email}")

    def perform_update(self, serializer):
        rule = serializer.save()
        AuditLog.objects.create(
            user=self.request.user,
            action='update',
            resource_type='NotificationRule',
            resource_id=rule.id,
            resource_name=rule.name,
            description=f'Updated notification rule: {rule.trigger} -> {rule.channel}',
            ip_address=self.request.META.get('REMOTE_ADDR'),
            user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
        )
        logger.info(f"Notification rule '{rule.name}' updated by {self.request.user.email}")

    def perform_destroy(self, instance):
        rule_id, rule_name = instance.id, instance.name
        instance.delete()
        AuditLog.objects.create(
            user=self.request.user,
            action='delete',
            resource_type='NotificationRule',
            resource_id=rule_id,
            resource_name=rule_name,
            description=f'Deleted notification rule: {rule_name}',
            ip_address=self.request.META.get('REMOTE_ADDR'),
            user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
        )
        logger.info(f"Notification rule '{rule_name}' deleted by {self.request.user.email}")


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only send log for NotificationRule deliveries — an audit trail
    for "did the alert actually go out", separate from AuditLog (which
    tracks user actions, not background delivery outcomes).
    """
    queryset = Notification.objects.select_related('rule').all()
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated, IsAuditorOrAdmin]
    ordering_fields = ['created_at', 'sent_at']
    ordering = ['-created_at']
    filterset_fields = ['status', 'channel', 'rule']
