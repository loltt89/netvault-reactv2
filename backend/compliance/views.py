import logging
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from accounts.permissions import IsAdministrator, CanManageDevices, IsOperatorOrAdmin
from accounts.models import AuditLog
from core.device_filters import get_scoped_device_ids
from .models import CompliancePolicy, ComplianceViolation
from .serializers import CompliancePolicySerializer, ComplianceViolationSerializer

logger = logging.getLogger(__name__)


class CompliancePolicyViewSet(viewsets.ModelViewSet):
    """
    CRUD for CompliancePolicy — admin-only, same trust level as
    NotificationRule/SystemSettings (defines rules that scan every
    device's configuration).
    """
    queryset = CompliancePolicy.objects.all()
    serializer_class = CompliancePolicySerializer
    permission_classes = [permissions.IsAuthenticated, IsAdministrator]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    filterset_fields = ['is_active', 'severity']

    def perform_create(self, serializer):
        policy = serializer.save(created_by=self.request.user)
        AuditLog.objects.create(
            user=self.request.user, action='create', resource_type='CompliancePolicy',
            resource_id=policy.id, resource_name=policy.name,
            description=f'Created compliance policy with {len(policy.rules)} rule(s)',
            ip_address=self.request.META.get('REMOTE_ADDR'),
            user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
        )
        logger.info(f"Compliance policy '{policy.name}' created by {self.request.user.email}")

    def perform_update(self, serializer):
        policy = serializer.save()
        AuditLog.objects.create(
            user=self.request.user, action='update', resource_type='CompliancePolicy',
            resource_id=policy.id, resource_name=policy.name,
            description=f'Updated compliance policy ({len(policy.rules)} rule(s))',
            ip_address=self.request.META.get('REMOTE_ADDR'),
            user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
        )
        logger.info(f"Compliance policy '{policy.name}' updated by {self.request.user.email}")

    def perform_destroy(self, instance):
        policy_id, policy_name = instance.id, instance.name
        instance.delete()
        AuditLog.objects.create(
            user=self.request.user, action='delete', resource_type='CompliancePolicy',
            resource_id=policy_id, resource_name=policy_name,
            description=f'Deleted compliance policy: {policy_name}',
            ip_address=self.request.META.get('REMOTE_ADDR'),
            user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
        )
        logger.info(f"Compliance policy '{policy_name}' deleted by {self.request.user.email}")


class ComplianceViolationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only violation list, scoped by device_scope RBAC like
    Device/Backup — same trust level as viewing the devices themselves,
    not admin-only like the policies that generate them.
    """
    serializer_class = ComplianceViolationSerializer
    permission_classes = [permissions.IsAuthenticated, CanManageDevices]
    ordering_fields = ['detected_at', 'last_seen_at']
    ordering = ['-detected_at']
    filterset_fields = ['status', 'policy', 'device']

    def get_queryset(self):
        queryset = ComplianceViolation.objects.select_related('policy', 'device')
        scoped_ids = get_scoped_device_ids(self.request.user)
        if scoped_ids is not None:
            queryset = queryset.filter(device_id__in=scoped_ids)

        # filterset_fields above claims 'status'/'policy'/'device' are
        # filterable via DjangoFilterBackend, but that backend is never
        # installed/configured in this project (see DEFAULT_FILTER_BACKENDS
        # in settings.py — only SearchFilter/OrderingFilter are active),
        # so filterset_fields here has always been dead configuration.
        # ComplianceViolations.tsx's status dropdown (defaulting to
        # "open", the exact scenario a compliance reviewer actually
        # wants) sends ?status=<value> and got the full, unfiltered
        # open+resolved list back regardless of selection — same class of
        # bug as BackupViewSet's status/status__in fix.
        status_param = self.request.query_params.get('status', None)
        if status_param:
            queryset = queryset.filter(status=status_param)

        policy_param = self.request.query_params.get('policy', None)
        if policy_param:
            queryset = queryset.filter(policy_id=policy_param)

        device_param = self.request.query_params.get('device', None)
        if device_param:
            queryset = queryset.filter(device_id=device_param)

        return queryset

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Open-violation counts by severity, for a dashboard summary."""
        queryset = self.get_queryset().filter(status='open')
        by_severity = {choice: 0 for choice, _ in CompliancePolicy.SEVERITY_CHOICES}
        for violation in queryset.select_related('policy'):
            by_severity[violation.policy.severity] = by_severity.get(violation.policy.severity, 0) + 1

        return Response({
            'open_total': queryset.count(),
            'by_severity': by_severity,
            'affected_devices': queryset.values('device_id').distinct().count(),
        })

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated, IsOperatorOrAdmin])
    def acknowledge(self, request, pk=None):
        """
        Manually resolve a violation (e.g. accepted risk, false positive).
        Note this is only until the next backup: if the underlying rule
        still fails on re-evaluation, evaluate_backup_compliance() will
        reopen it — acknowledging isn't a permanent suppression, it's
        "stop showing me this until something actually changes".
        """
        violation = self.get_object()
        violation.status = 'resolved'
        violation.resolved_at = timezone.now()
        violation.save(update_fields=['status', 'resolved_at'])

        AuditLog.objects.create(
            user=request.user, action='update', resource_type='ComplianceViolation',
            resource_id=violation.id, resource_name=violation.rule_description[:100],
            description=f'Acknowledged violation for device {violation.device.name}',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )

        return Response(ComplianceViolationSerializer(violation).data)
