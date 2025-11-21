import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count
from django.http import HttpResponse
from accounts.permissions import CanManageDevices
import csv
import io
import re

logger = logging.getLogger(__name__)
from .models import Vendor, DeviceType, Device
from .serializers import (
    VendorSerializer, DeviceTypeSerializer,
    DeviceSerializer, DeviceCreateSerializer, DeviceDetailSerializer
)


class VendorViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Vendor CRUD operations
    """
    queryset = Vendor.objects.all()
    serializer_class = VendorSerializer
    permission_classes = [IsAuthenticated, CanManageDevices]
    search_fields = ['name', 'slug']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    pagination_class = None  # Disable pagination for vendors


class DeviceTypeViewSet(viewsets.ModelViewSet):
    """
    ViewSet for DeviceType CRUD operations
    """
    queryset = DeviceType.objects.all()
    serializer_class = DeviceTypeSerializer
    permission_classes = [IsAuthenticated, CanManageDevices]
    search_fields = ['name', 'slug']
    ordering_fields = ['name']
    ordering = ['name']
    pagination_class = None  # Disable pagination for device types

    def destroy(self, request, *args, **kwargs):
        """Prevent deletion of predefined device types"""
        device_type = self.get_object()

        # Check if predefined
        if device_type.is_predefined:
            return Response(
                {'error': 'Cannot delete predefined device type'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if in use by devices
        if device_type.devices.exists():
            return Response(
                {'error': f'Cannot delete device type. It is used by {device_type.devices.count()} device(s).'},
                status=status.HTTP_400_BAD_REQUEST
            )

        return super().destroy(request, *args, **kwargs)


class DeviceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Device CRUD operations
    """
    queryset = Device.objects.select_related('vendor', 'device_type', 'created_by')
    permission_classes = [IsAuthenticated, CanManageDevices]
    search_fields = ['name', 'ip_address', 'location', 'description']
    ordering_fields = ['name', 'ip_address', 'created_at', 'last_backup']
    ordering = ['name']
    filterset_fields = ['vendor', 'device_type', 'group', 'status', 'criticality', 'protocol']

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'retrieve':
            return DeviceDetailSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return DeviceCreateSerializer
        return DeviceSerializer

    def get_queryset(self):
        """Filter queryset based on query params"""
        queryset = super().get_queryset()

        # Filter by status
        status_param = self.request.query_params.get('status', None)
        if status_param:
            queryset = queryset.filter(status=status_param)

        # Filter by criticality
        criticality = self.request.query_params.get('criticality', None)
        if criticality:
            queryset = queryset.filter(criticality=criticality)

        # Filter by backup enabled
        backup_enabled = self.request.query_params.get('backup_enabled', None)
        if backup_enabled is not None:
            queryset = queryset.filter(backup_enabled=backup_enabled.lower() == 'true')

        # Search across multiple fields
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(ip_address__icontains=search) |
                Q(location__icontains=search) |
                Q(description__icontains=search)
            )

        return queryset

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get device statistics"""
        total = Device.objects.count()
        by_status = dict(Device.objects.values('status').annotate(count=Count('id')).values_list('status', 'count'))
        by_criticality = dict(Device.objects.values('criticality').annotate(count=Count('id')).values_list('criticality', 'count'))
        by_vendor = list(Device.objects.values('vendor__name').annotate(count=Count('id')).values('vendor__name', 'count'))

        backup_enabled = Device.objects.filter(backup_enabled=True).count()

        return Response({
            'total': total,
            'by_status': by_status,
            'by_criticality': by_criticality,
            'by_vendor': by_vendor,
            'backup_enabled': backup_enabled,
        })

    @action(detail=True, methods=['post'])
    def test_connection(self, request, pk=None):
        """Test connection to device"""
        from .connection import test_connection
        from django.utils import timezone

        device = self.get_object()

        try:
            username = device.username
            password = device.get_password()
            enable_password = device.get_enable_password() if device.enable_password_encrypted else None

            success, message = test_connection(
                host=device.ip_address,
                port=device.port,
                protocol=device.protocol,
                username=username,
                password=password,
                enable_password=enable_password,
                timeout=30
            )

            # Update device status based on connection test result
            if success:
                device.status = 'online'
                device.last_seen = timezone.now()
            else:
                device.status = 'offline'
            device.save()

            return Response({
                'success': success,
                'message': message,
                'device_id': device.id,
                'device_name': device.name,
                'status': device.status,
            })

        except Exception as e:
            # Update device status to offline on exception
            device.status = 'offline'
            device.save()

            return Response({
                'success': False,
                'message': str(e),
                'device_id': device.id,
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def backup_now(self, request, pk=None):
        """Trigger immediate backup for device (works regardless of backup_enabled status)"""
        from backups.tasks import backup_device

        device = self.get_object()

        # Manual backup works regardless of backup_enabled setting
        # Only automatic scheduled backups respect backup_enabled

        # Trigger backup task
        task = backup_device.delay(
            device_id=device.id,
            triggered_by_id=request.user.id,
            backup_type='manual'
        )

        return Response({
            'success': True,
            'message': f'Backup initiated for {device.name}',
            'device_id': device.id,
            'task_id': task.id,
        }, status=status.HTTP_202_ACCEPTED)

    # CSV Header mappings for different languages
    CSV_HEADERS = {
        'en': {
            'name': 'Name',
            'ip_address': 'IP Address',
            'vendor': 'Vendor',
            'device_type': 'Device Type',
            'protocol': 'Protocol',
            'port': 'Port',
            'username': 'Username',
            'password': 'Password',
            'enable_password': 'Enable Password',
            'location': 'Location',
            'description': 'Description',
            'backup_enabled': 'Backup Enabled',
            'criticality': 'Criticality',
        },
        'ru': {
            'name': 'Название',
            'ip_address': 'IP адрес',
            'vendor': 'Производитель',
            'device_type': 'Тип устройства',
            'protocol': 'Протокол',
            'port': 'Порт',
            'username': 'Имя пользователя',
            'password': 'Пароль',
            'enable_password': 'Enable пароль',
            'location': 'Расположение',
            'description': 'Описание',
            'backup_enabled': 'Бэкап включен',
            'criticality': 'Критичность',
        },
        'kk': {
            'name': 'Атауы',
            'ip_address': 'IP мекенжайы',
            'vendor': 'Өндіруші',
            'device_type': 'Құрылғы түрі',
            'protocol': 'Протокол',
            'port': 'Порт',
            'username': 'Пайдаланушы аты',
            'password': 'Құпия сөз',
            'enable_password': 'Enable құпия сөзі',
            'location': 'Орналасуы',
            'description': 'Сипаттама',
            'backup_enabled': 'Бэкап қосулы',
            'criticality': 'Маңыздылығы',
        },
    }

    # Reverse mapping for import (header -> field name)
    @classmethod
    def get_reverse_header_mapping(cls):
        """Build reverse mapping from localized headers to field names"""
        reverse_map = {}
        for lang, headers in cls.CSV_HEADERS.items():
            for field, header in headers.items():
                reverse_map[header.lower()] = field
        return reverse_map

    @action(detail=False, methods=['get'], permission_classes=[])
    def csv_template(self, request):
        """Download CSV template with localized headers (public - no auth required)"""
        lang = request.query_params.get('lang', 'en')
        if lang not in self.CSV_HEADERS:
            lang = 'en'

        headers = self.CSV_HEADERS[lang]

        # Create CSV response
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="devices_template_{lang}.csv"'
        response.write('\ufeff')  # UTF-8 BOM for Excel

        writer = csv.writer(response, delimiter=';')

        # Write headers
        writer.writerow([
            headers['name'],
            headers['ip_address'],
            headers['vendor'],
            headers['device_type'],
            headers['protocol'],
            headers['port'],
            headers['username'],
            headers['password'],
            headers['enable_password'],
            headers['location'],
            headers['description'],
            headers['backup_enabled'],
            headers['criticality'],
        ])

        # Write example row
        examples = {
            'en': ['Router-Core', '192.168.1.1', 'cisco', 'router', 'ssh', '22', 'admin', 'password123', 'enable123', 'Data Center 1', 'Main core router', 'yes', 'critical'],
            'ru': ['Роутер-Ядро', '192.168.1.1', 'cisco', 'router', 'ssh', '22', 'admin', 'password123', 'enable123', 'Дата-центр 1', 'Основной роутер', 'да', 'critical'],
            'kk': ['Роутер-Ядро', '192.168.1.1', 'cisco', 'router', 'ssh', '22', 'admin', 'password123', 'enable123', 'Дата-орталық 1', 'Негізгі роутер', 'иә', 'critical'],
        }
        writer.writerow(examples.get(lang, examples['en']))

        return response

    @action(detail=False, methods=['post'])
    def csv_preview(self, request):
        """Preview CSV import with validation"""
        if 'file' not in request.FILES:
            return Response({'error': 'No file uploaded'}, status=status.HTTP_400_BAD_REQUEST)

        csv_file = request.FILES['file']
        if not csv_file.name.endswith('.csv'):
            return Response({'error': 'File must be CSV'}, status=status.HTTP_400_BAD_REQUEST)

        # Limit file size to 5MB to prevent memory exhaustion
        max_size = 5 * 1024 * 1024
        if csv_file.size > max_size:
            return Response({'error': 'CSV file too large (max 5MB)'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Read file content
            content = csv_file.read().decode('utf-8-sig')  # Handle BOM
            reader = csv.DictReader(io.StringIO(content), delimiter=';')

            # Get reverse mapping
            reverse_map = self.get_reverse_header_mapping()

            # Map headers to field names
            if not reader.fieldnames:
                return Response({'error': 'Empty CSV file'}, status=status.HTTP_400_BAD_REQUEST)

            field_mapping = {}
            for header in reader.fieldnames:
                field = reverse_map.get(header.lower().strip())
                if field:
                    field_mapping[header] = field

            if not field_mapping:
                return Response({'error': 'Could not recognize CSV headers'}, status=status.HTTP_400_BAD_REQUEST)

            # Get existing data for validation
            existing_ips = set(Device.objects.values_list('ip_address', flat=True))
            existing_names = set(Device.objects.values_list('name', flat=True))
            valid_vendors = {v.slug: v.id for v in Vendor.objects.all()}
            valid_device_types = {dt.slug: dt.id for dt in DeviceType.objects.all()}

            # Process rows
            preview_rows = []
            for row_num, row in enumerate(reader, start=2):
                mapped_row = {}
                for header, value in row.items():
                    field = field_mapping.get(header)
                    if field:
                        mapped_row[field] = value.strip() if value else ''

                # Validate row
                errors = []
                warnings = []

                # Required fields
                if not mapped_row.get('name'):
                    errors.append('Name is required')
                if not mapped_row.get('ip_address'):
                    errors.append('IP address is required')
                elif not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', mapped_row.get('ip_address', '')):
                    errors.append('Invalid IP address format')

                # Check duplicates
                if mapped_row.get('ip_address') in existing_ips:
                    warnings.append('IP already exists')
                if mapped_row.get('name') in existing_names:
                    warnings.append('Name already exists')

                # Validate vendor
                vendor_slug = mapped_row.get('vendor', '').lower()
                if vendor_slug and vendor_slug not in valid_vendors:
                    errors.append(f'Unknown vendor: {vendor_slug}')

                # Validate device type
                device_type_slug = mapped_row.get('device_type', '').lower()
                if device_type_slug and device_type_slug not in valid_device_types:
                    errors.append(f'Unknown device type: {device_type_slug}')

                # Validate protocol
                protocol = mapped_row.get('protocol', 'ssh').lower()
                if protocol not in ['ssh', 'telnet']:
                    errors.append(f'Invalid protocol: {protocol}')

                # Validate port
                port = mapped_row.get('port', '22')
                try:
                    port_int = int(port) if port else 22
                    if not (1 <= port_int <= 65535):
                        errors.append('Port must be 1-65535')
                except ValueError:
                    errors.append('Invalid port number')

                preview_rows.append({
                    'row_number': row_num,
                    'data': mapped_row,
                    'errors': errors,
                    'warnings': warnings,
                    'valid': len(errors) == 0,
                })

            # Summary
            valid_count = sum(1 for r in preview_rows if r['valid'])
            duplicate_count = sum(1 for r in preview_rows if r['warnings'])
            error_count = sum(1 for r in preview_rows if not r['valid'])

            return Response({
                'total_rows': len(preview_rows),
                'valid_rows': valid_count,
                'duplicate_rows': duplicate_count,
                'error_rows': error_count,
                'rows': preview_rows,
                'vendors': list(valid_vendors.keys()),
                'device_types': list(valid_device_types.keys()),
            })

        except Exception as e:
            logger.error(f"CSV preview error: {e}")
            return Response({'error': 'Failed to process CSV file'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def csv_import(self, request):
        """Import devices from CSV"""
        if 'file' not in request.FILES:
            return Response({'error': 'No file uploaded'}, status=status.HTTP_400_BAD_REQUEST)

        csv_file = request.FILES['file']
        skip_duplicates = request.data.get('skip_duplicates', True)
        update_existing = request.data.get('update_existing', False)

        # Limit file size to 5MB to prevent memory exhaustion
        max_size = 5 * 1024 * 1024
        if csv_file.size > max_size:
            return Response({'error': 'CSV file too large (max 5MB)'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            content = csv_file.read().decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(content), delimiter=';')

            reverse_map = self.get_reverse_header_mapping()

            field_mapping = {}
            for header in reader.fieldnames:
                field = reverse_map.get(header.lower().strip())
                if field:
                    field_mapping[header] = field

            # Get existing data
            existing_devices = {d.ip_address: d for d in Device.objects.all()}
            valid_vendors = {v.slug: v for v in Vendor.objects.all()}
            valid_device_types = {dt.slug: dt for dt in DeviceType.objects.all()}

            created = 0
            updated = 0
            skipped = 0
            errors = []

            for row_num, row in enumerate(reader, start=2):
                mapped_row = {}
                for header, value in row.items():
                    field = field_mapping.get(header)
                    if field:
                        mapped_row[field] = value.strip() if value else ''

                ip_address = mapped_row.get('ip_address', '')
                name = mapped_row.get('name', '')

                if not ip_address or not name:
                    errors.append(f'Row {row_num}: Missing required fields')
                    continue

                # Check if exists
                existing = existing_devices.get(ip_address)

                if existing:
                    if update_existing:
                        # Update existing device
                        existing.name = name
                        if mapped_row.get('location'):
                            existing.location = mapped_row['location']
                        if mapped_row.get('description'):
                            existing.description = mapped_row['description']
                        existing.save()
                        updated += 1
                    else:
                        skipped += 1
                    continue

                # Create new device
                try:
                    vendor_slug = mapped_row.get('vendor', 'other').lower()
                    device_type_slug = mapped_row.get('device_type', 'router').lower()

                    vendor = valid_vendors.get(vendor_slug)
                    device_type = valid_device_types.get(device_type_slug)

                    if not vendor or not device_type:
                        errors.append(f'Row {row_num}: Invalid vendor or device type')
                        continue

                    protocol = mapped_row.get('protocol', 'ssh').lower()
                    port = int(mapped_row.get('port', 22) or 22)

                    backup_enabled_val = mapped_row.get('backup_enabled', 'yes').lower()
                    backup_enabled = backup_enabled_val in ['yes', 'да', 'иә', 'true', '1']

                    device = Device(
                        name=name,
                        ip_address=ip_address,
                        vendor=vendor,
                        device_type=device_type,
                        protocol=protocol,
                        port=port,
                        location=mapped_row.get('location', ''),
                        description=mapped_row.get('description', ''),
                        backup_enabled=backup_enabled,
                        criticality=mapped_row.get('criticality', 'medium'),
                        created_by=request.user,
                    )

                    # Set credentials
                    if mapped_row.get('username'):
                        device.username = mapped_row['username']
                    if mapped_row.get('password'):
                        device.set_password(mapped_row['password'])
                    if mapped_row.get('enable_password'):
                        device.set_enable_password(mapped_row['enable_password'])

                    device.save()
                    created += 1

                except Exception as e:
                    errors.append(f'Row {row_num}: {str(e)}')

            return Response({
                'success': True,
                'created': created,
                'updated': updated,
                'skipped': skipped,
                'errors': errors,
            })

        except Exception as e:
            logger.error(f"CSV import error: {e}")
            return Response({'error': 'Failed to import CSV file'}, status=status.HTTP_400_BAD_REQUEST)
