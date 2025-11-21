from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Q
from django.utils import timezone
from accounts.permissions import CanManageBackups, CanManageDevices
from .models import Backup, BackupSchedule, BackupRetentionPolicy
from .serializers import (
    BackupSerializer, BackupDetailSerializer,
    BackupScheduleSerializer, BackupRetentionPolicySerializer
)


class BackupViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Backup CRUD operations
    """
    queryset = Backup.objects.select_related('device', 'triggered_by')
    permission_classes = [IsAuthenticated, CanManageBackups]
    search_fields = ['device__name', 'device__ip_address']
    ordering_fields = ['created_at', 'completed_at', 'size_bytes']
    ordering = ['-created_at']
    filterset_fields = ['device', 'status', 'backup_type', 'success', 'has_changes']

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'retrieve':
            return BackupDetailSerializer
        return BackupSerializer

    def get_queryset(self):
        """Filter queryset based on query params"""
        queryset = super().get_queryset()

        # Filter by device
        device_id = self.request.query_params.get('device', None)
        if device_id:
            queryset = queryset.filter(device_id=device_id)

        # Filter by vendor
        vendor_id = self.request.query_params.get('vendor', None)
        if vendor_id:
            queryset = queryset.filter(device__vendor_id=vendor_id)

        # Filter by device type
        device_type_id = self.request.query_params.get('device_type', None)
        if device_type_id:
            queryset = queryset.filter(device__device_type_id=device_type_id)

        # Filter by success
        success_param = self.request.query_params.get('success', None)
        if success_param is not None:
            queryset = queryset.filter(success=success_param.lower() == 'true')

        # Filter by date range
        date_from = self.request.query_params.get('date_from', None)
        date_to = self.request.query_params.get('date_to', None)
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)

        return queryset

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get backup statistics"""
        total = Backup.objects.count()
        successful = Backup.objects.filter(success=True).count()
        failed = Backup.objects.filter(success=False).count()

        by_status = dict(
            Backup.objects.values('status')
            .annotate(count=Count('id'))
            .values_list('status', 'count')
        )

        total_size = Backup.objects.aggregate(
            total=Count('id'),
            size=Count('size_bytes')
        )

        return Response({
            'total': total,
            'successful': successful,
            'failed': failed,
            'by_status': by_status,
            'total_size_bytes': total_size.get('size', 0),
        })

    @action(detail=True, methods=['get'])
    def configuration(self, request, pk=None):
        """Get backup configuration content"""
        backup = self.get_object()
        config = backup.get_configuration()

        return Response({
            'backup_id': backup.id,
            'device': backup.device.name,
            'created_at': backup.created_at,
            'configuration': config
        })

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Download backup configuration as file"""
        from django.http import HttpResponse

        backup = self.get_object()
        config = backup.get_configuration()

        filename = f'{backup.device.name}_{backup.created_at.strftime("%Y%m%d_%H%M%S")}.txt'

        response = HttpResponse(config, content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response

    @action(detail=True, methods=['get'], url_path='compare/(?P<compare_id>[^/.]+)')
    def compare(self, request, pk=None, compare_id=None):
        """Compare two backups"""
        import difflib

        backup1 = self.get_object()
        try:
            backup2 = Backup.objects.get(id=compare_id)
        except Backup.DoesNotExist:
            return Response(
                {'error': 'Backup not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        config1 = backup1.get_configuration().splitlines()
        config2 = backup2.get_configuration().splitlines()

        # Generate unified diff
        diff = difflib.unified_diff(
            config2,
            config1,
            fromfile=f'{backup2.device.name} ({backup2.created_at})',
            tofile=f'{backup1.device.name} ({backup1.created_at})',
            lineterm=''
        )

        diff_content = '\n'.join(diff)

        return Response({
            'backup1': BackupSerializer(backup1).data,
            'backup2': BackupSerializer(backup2).data,
            'diff': diff_content
        })

    @action(detail=False, methods=['get'])
    def grouped(self, request):
        """Get backups grouped by date, vendor, or device type"""
        from collections import defaultdict
        from datetime import datetime

        group_by = request.query_params.get('group_by', 'date')  # date, vendor, device_type
        queryset = self.filter_queryset(self.get_queryset())

        grouped_data = defaultdict(list)

        for backup in queryset.select_related('device__vendor', 'device__device_type'):
            if group_by == 'date':
                # Group by date (YYYY-MM-DD)
                key = backup.created_at.strftime('%Y-%m-%d')
            elif group_by == 'vendor':
                # Group by vendor
                key = backup.device.vendor.name if backup.device.vendor else 'Unknown'
            elif group_by == 'device_type':
                # Group by device type
                key = backup.device.device_type.name if backup.device.device_type else 'Unknown'
            else:
                key = 'all'

            grouped_data[key].append(BackupSerializer(backup).data)

        # Convert to list format with group info
        result = []
        for group_name, backups in grouped_data.items():
            result.append({
                'group': group_name,
                'count': len(backups),
                'backups': backups,
                'total_size': sum(b['size_bytes'] for b in backups)
            })

        # Sort by group name
        result.sort(key=lambda x: x['group'], reverse=True)

        return Response({
            'group_by': group_by,
            'groups': result,
            'total_groups': len(result),
            'total_backups': sum(g['count'] for g in result)
        })

    @action(detail=False, methods=['post'])
    def download_multiple(self, request):
        """Download multiple backups as a ZIP archive"""
        import zipfile
        import io
        from django.http import HttpResponse

        backup_ids = request.data.get('backup_ids', [])

        if not backup_ids:
            return Response(
                {'error': 'No backup IDs provided'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get backups
        backups = Backup.objects.filter(id__in=backup_ids, success=True)

        if not backups.exists():
            return Response(
                {'error': 'No valid backups found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Create ZIP file in memory
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for backup in backups:
                config = backup.get_configuration()
                filename = f'{backup.device.name}_{backup.created_at.strftime("%Y%m%d_%H%M%S")}.txt'

                # Add to zip with folder structure: vendor/device_name/filename
                if backup.device.vendor:
                    folder_path = f'{backup.device.vendor.name}/{backup.device.name}/{filename}'
                else:
                    folder_path = f'Unknown/{backup.device.name}/{filename}'

                zip_file.writestr(folder_path, config)

        # Prepare response
        zip_buffer.seek(0)
        response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="backups_{timezone.now().strftime("%Y%m%d_%H%M%S")}.zip"'

        return response

    @action(detail=False, methods=['get'])
    def search_configs(self, request):
        """Search through all device configurations"""
        import re

        query = request.query_params.get('q', '').strip()
        case_sensitive = request.query_params.get('case_sensitive', 'false').lower() == 'true'
        regex_mode = request.query_params.get('regex', 'false').lower() == 'true'

        if not query or len(query) < 2:
            return Response(
                {'error': 'Search query must be at least 2 characters'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get latest successful backup for each device
        from django.db.models import Max
        from devices.models import Device

        devices = Device.objects.filter(backups__success=True).distinct()
        results = []

        for device in devices:
            # Get latest successful backup
            latest_backup = device.backups.filter(success=True).order_by('-created_at').first()
            if not latest_backup:
                continue

            try:
                config = latest_backup.get_configuration()
            except Exception:
                continue

            # Search in config
            matches = []
            lines = config.split('\n')

            for line_num, line in enumerate(lines, 1):
                found = False

                if regex_mode:
                    try:
                        flags = 0 if case_sensitive else re.IGNORECASE
                        if re.search(query, line, flags):
                            found = True
                    except re.error:
                        pass
                else:
                    if case_sensitive:
                        found = query in line
                    else:
                        found = query.lower() in line.lower()

                if found:
                    # Get context (2 lines before and after)
                    start = max(0, line_num - 3)
                    end = min(len(lines), line_num + 2)
                    context = '\n'.join(f'{i+1}: {lines[i]}' for i in range(start, end))

                    matches.append({
                        'line_number': line_num,
                        'line': line.strip(),
                        'context': context
                    })

            if matches:
                results.append({
                    'device_id': device.id,
                    'device_name': device.name,
                    'device_ip': device.ip_address,
                    'vendor': device.vendor.name if device.vendor else None,
                    'backup_id': latest_backup.id,
                    'backup_date': latest_backup.created_at,
                    'match_count': len(matches),
                    'matches': matches[:10]  # Limit matches per device
                })

        return Response({
            'query': query,
            'total_devices': len(results),
            'total_matches': sum(r['match_count'] for r in results),
            'results': results
        })


class BackupScheduleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for BackupSchedule CRUD operations
    """
    queryset = BackupSchedule.objects.select_related('created_by').prefetch_related('devices')
    serializer_class = BackupScheduleSerializer
    permission_classes = [IsAuthenticated, CanManageDevices]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'next_run', 'created_at']
    ordering = ['name']
    filterset_fields = ['is_active']

    def perform_create(self, serializer):
        """Set created_by field"""
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """Toggle schedule active status"""
        schedule = self.get_object()
        schedule.is_active = not schedule.is_active
        schedule.save()

        return Response({
            'id': schedule.id,
            'is_active': schedule.is_active,
            'message': f'Schedule {"activated" if schedule.is_active else "deactivated"}'
        })

    @action(detail=True, methods=['post'])
    def run_now(self, request, pk=None):
        """Manually trigger a scheduled backup (runs for all devices with backup_enabled=true)"""
        from .tasks import backup_multiple_devices
        from devices.models import Device

        schedule = self.get_object()

        # Get all devices with backup_enabled=True
        # Manual schedule run also respects backup_enabled setting (use device's Backup Now button for override)
        devices = Device.objects.filter(backup_enabled=True)

        device_ids = list(devices.values_list('id', flat=True))

        if not device_ids:
            return Response(
                {'error': 'No devices found for this schedule'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Trigger backups
        result = backup_multiple_devices.delay(
            device_ids,
            triggered_by_id=request.user.id,
            backup_type='manual'
        )

        return Response({
            'message': f'Started backup for {len(device_ids)} devices',
            'task_id': result.id,
            'device_count': len(device_ids)
        })


class BackupRetentionPolicyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for BackupRetentionPolicy CRUD operations
    """
    queryset = BackupRetentionPolicy.objects.prefetch_related('devices')
    serializer_class = BackupRetentionPolicySerializer
    permission_classes = [IsAuthenticated, CanManageDevices]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    filterset_fields = ['is_active', 'auto_delete']

    @action(detail=True, methods=['post'])
    def apply_now(self, request, pk=None):
        """Apply retention policy immediately"""
        policy = self.get_object()

        # TODO: Implement actual retention policy application
        return Response({
            'success': True,
            'message': f'Retention policy "{policy.name}" applied - Feature coming soon',
            'policy_id': policy.id,
        }, status=status.HTTP_202_ACCEPTED)
