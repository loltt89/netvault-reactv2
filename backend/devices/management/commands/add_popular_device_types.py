"""
Management command to add popular network device types
"""
from django.core.management.base import BaseCommand
from devices.models import DeviceType


class Command(BaseCommand):
    help = 'Add popular network device types'

    def handle(self, *args, **kwargs):
        device_types_data = [
            {
                'name': 'Router',
                'slug': 'router',
                'description': 'Network router',
                'icon': 'router'
            },
            {
                'name': 'Switch',
                'slug': 'switch',
                'description': 'Network switch',
                'icon': 'switch'
            },
            {
                'name': 'Firewall',
                'slug': 'firewall',
                'description': 'Network firewall',
                'icon': 'firewall'
            },
            {
                'name': 'Access Point',
                'slug': 'access-point',
                'description': 'Wireless access point',
                'icon': 'wifi'
            },
            {
                'name': 'Load Balancer',
                'slug': 'load-balancer',
                'description': 'Load balancer',
                'icon': 'balance'
            },
            {
                'name': 'VPN Gateway',
                'slug': 'vpn-gateway',
                'description': 'VPN gateway',
                'icon': 'vpn'
            },
            {
                'name': 'Controller',
                'slug': 'controller',
                'description': 'Network controller (SDN, wireless)',
                'icon': 'controller'
            },
            {
                'name': 'Optical',
                'slug': 'optical',
                'description': 'Optical networking equipment',
                'icon': 'optical'
            },
            {
                'name': 'WAN Optimizer',
                'slug': 'wan-optimizer',
                'description': 'WAN optimization appliance',
                'icon': 'optimize'
            },
            {
                'name': 'Gateway',
                'slug': 'gateway',
                'description': 'Network gateway',
                'icon': 'gateway'
            },
        ]

        created_count = 0
        skipped_count = 0

        for device_type_data in device_types_data:
            slug = device_type_data['slug']

            existing_device_type = DeviceType.objects.filter(slug=slug).first()

            if existing_device_type:
                skipped_count += 1
                self.stdout.write(self.style.WARNING(f'Skipped (already exists): {device_type_data["name"]}'))
            else:
                DeviceType.objects.create(**device_type_data)
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Created: {device_type_data["name"]}'))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Summary:'))
        self.stdout.write(self.style.SUCCESS(f'  Created: {created_count}'))
        self.stdout.write(self.style.WARNING(f'  Skipped: {skipped_count}'))
        self.stdout.write(self.style.SUCCESS(f'  Total device types in DB: {DeviceType.objects.count()}'))
