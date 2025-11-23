"""
Management command to add popular network device vendors
Similar to oxidized's vendor support
"""
from django.core.management.base import BaseCommand
from devices.models import Vendor


class Command(BaseCommand):
    help = 'Add popular network device vendors with backup commands'

    def handle(self, *args, **kwargs):
        vendors_data = [
            # Major vendors
            {
                'name': 'Cisco IOS',
                'slug': 'cisco-ios',
                'description': 'Cisco IOS devices (routers, switches)',
                'backup_commands': {
                    'setup': ['terminal length 0', 'terminal width 0'],
                    'backup': 'show running-config',
                    'enable_mode': True
                }
            },
            {
                'name': 'Cisco IOS-XE',
                'slug': 'cisco-ios-xe',
                'description': 'Cisco IOS-XE devices (ASR, ISR)',
                'backup_commands': {
                    'setup': ['terminal length 0', 'terminal width 0'],
                    'backup': 'show running-config',
                    'enable_mode': True
                }
            },
            {
                'name': 'Cisco IOS-XR',
                'slug': 'cisco-ios-xr',
                'description': 'Cisco IOS-XR devices (CRS, ASR 9000)',
                'backup_commands': {
                    'setup': ['terminal length 0'],
                    'backup': 'show running-config',
                    'enable_mode': False
                }
            },
            {
                'name': 'Cisco NX-OS',
                'slug': 'cisco-nxos',
                'description': 'Cisco Nexus switches',
                'backup_commands': {
                    'setup': ['terminal length 0'],
                    'backup': 'show running-config',
                    'enable_mode': False
                }
            },
            {
                'name': 'Cisco ASA',
                'slug': 'cisco-asa',
                'description': 'Cisco ASA firewalls',
                'backup_commands': {
                    'setup': ['terminal pager 0'],
                    'backup': 'show running-config',
                    'enable_mode': True
                }
            },
            {
                'name': 'Juniper JunOS',
                'slug': 'juniper-junos',
                'description': 'Juniper Networks devices',
                'backup_commands': {
                    'setup': ['set cli screen-length 0'],
                    'backup': 'show configuration',
                    'enable_mode': False
                }
            },
            {
                'name': 'Arista EOS',
                'slug': 'arista-eos',
                'description': 'Arista switches',
                'backup_commands': {
                    'setup': ['terminal length 0'],
                    'backup': 'show running-config',
                    'enable_mode': True
                }
            },
            {
                'name': 'HP ProCurve',
                'slug': 'hp-procurve',
                'description': 'HP ProCurve switches',
                'backup_commands': {
                    'setup': ['no page'],
                    'backup': 'show running-config',
                    'enable_mode': False
                }
            },
            {
                'name': 'HP Comware',
                'slug': 'hp-comware',
                'description': 'HP Comware switches (3Com, H3C)',
                'backup_commands': {
                    'setup': ['screen-length disable'],
                    'backup': 'display current-configuration',
                    'enable_mode': False
                }
            },
            {
                'name': 'Huawei VRP',
                'slug': 'huawei-vrp',
                'description': 'Huawei routers and switches',
                'backup_commands': {
                    'setup': ['screen-length 0 temporary'],
                    'backup': 'display current-configuration',
                    'enable_mode': False
                }
            },
            {
                'name': 'Mikrotik RouterOS',
                'slug': 'mikrotik',
                'description': 'Mikrotik routers and switches',
                'backup_commands': {
                    'setup': [],
                    'backup': '/export',
                    'enable_mode': False
                }
            },
            {
                'name': 'Fortinet FortiGate',
                'slug': 'fortinet-fortigate',
                'description': 'FortiGate firewalls',
                'backup_commands': {
                    'setup': ['config system console', 'set output standard', 'end'],
                    'backup': 'show full-configuration',
                    'enable_mode': False
                }
            },
            {
                'name': 'Palo Alto Networks',
                'slug': 'paloalto',
                'description': 'Palo Alto firewalls',
                'backup_commands': {
                    'setup': ['set cli pager off'],
                    'backup': 'show config running',
                    'enable_mode': False
                }
            },
            {
                'name': 'F5 Networks',
                'slug': 'f5-networks',
                'description': 'F5 BIG-IP load balancers',
                'backup_commands': {
                    'setup': [],
                    'backup': 'tmsh show running-config',
                    'enable_mode': False
                }
            },
            {
                'name': 'Dell Force10',
                'slug': 'dell-force10',
                'description': 'Dell Force10 switches',
                'backup_commands': {
                    'setup': ['terminal length 0'],
                    'backup': 'show running-config',
                    'enable_mode': True
                }
            },
            {
                'name': 'Dell PowerConnect',
                'slug': 'dell-powerconnect',
                'description': 'Dell PowerConnect switches',
                'backup_commands': {
                    'setup': ['terminal datadump'],
                    'backup': 'show running-config',
                    'enable_mode': False
                }
            },
            {
                'name': 'Brocade',
                'slug': 'brocade',
                'description': 'Brocade switches',
                'backup_commands': {
                    'setup': ['skip-page-display'],
                    'backup': 'show running-config',
                    'enable_mode': True
                }
            },
            {
                'name': 'Extreme Networks',
                'slug': 'extreme-networks',
                'description': 'Extreme Networks switches',
                'backup_commands': {
                    'setup': ['disable clipaging'],
                    'backup': 'show configuration',
                    'enable_mode': False
                }
            },
            {
                'name': 'Alcatel-Lucent',
                'slug': 'alcatel-lucent',
                'description': 'Alcatel-Lucent switches',
                'backup_commands': {
                    'setup': [],
                    'backup': 'show configuration snapshot',
                    'enable_mode': False
                }
            },
            {
                'name': 'Ubiquiti EdgeRouter',
                'slug': 'ubiquiti-edgerouter',
                'description': 'Ubiquiti EdgeRouter devices',
                'backup_commands': {
                    'setup': ['set terminal length 0'],
                    'backup': 'show configuration',
                    'enable_mode': False
                }
            },
            {
                'name': 'Ubiquiti UniFi',
                'slug': 'ubiquiti-unifi',
                'description': 'Ubiquiti UniFi switches',
                'backup_commands': {
                    'setup': [],
                    'backup': 'show running-config',
                    'enable_mode': False
                }
            },
            {
                'name': 'Check Point Gaia',
                'slug': 'checkpoint-gaia',
                'description': 'Check Point Gaia OS',
                'backup_commands': {
                    'setup': ['set clienv rows 0'],
                    'backup': 'show configuration',
                    'enable_mode': False
                }
            },
            {
                'name': 'Zyxel',
                'slug': 'zyxel',
                'description': 'Zyxel switches and routers',
                'backup_commands': {
                    'setup': [],
                    'backup': 'show running-config',
                    'enable_mode': False
                }
            },
            {
                'name': 'TP-Link',
                'slug': 'tp-link',
                'description': 'TP-Link switches',
                'backup_commands': {
                    'setup': [],
                    'backup': 'show running-config',
                    'enable_mode': False
                }
            },
            {
                'name': 'D-Link',
                'slug': 'd-link',
                'description': 'D-Link switches',
                'backup_commands': {
                    'setup': [],
                    'backup': 'show config current_config',
                    'enable_mode': False
                }
            },
            {
                'name': 'Netgear',
                'slug': 'netgear',
                'description': 'Netgear switches',
                'backup_commands': {
                    'setup': ['terminal length 0'],
                    'backup': 'show running-config',
                    'enable_mode': False
                }
            },
            {
                'name': 'Allied Telesis',
                'slug': 'allied-telesis',
                'description': 'Allied Telesis switches',
                'backup_commands': {
                    'setup': [],
                    'backup': 'show running-config',
                    'enable_mode': False
                }
            },
            {
                'name': 'Aruba',
                'slug': 'aruba',
                'description': 'Aruba switches and controllers',
                'backup_commands': {
                    'setup': ['no paging'],
                    'backup': 'show running-config',
                    'enable_mode': False
                }
            },
            {
                'name': 'Nokia SR OS',
                'slug': 'nokia-sros',
                'description': 'Nokia Service Router OS',
                'backup_commands': {
                    'setup': ['environment more false'],
                    'backup': 'admin display-config',
                    'enable_mode': False
                }
            },
            {
                'name': 'A10 Networks',
                'slug': 'a10-networks',
                'description': 'A10 Thunder load balancers',
                'backup_commands': {
                    'setup': ['terminal length 0'],
                    'backup': 'show running-config',
                    'enable_mode': True
                }
            },
            {
                'name': 'Citrix NetScaler',
                'slug': 'citrix-netscaler',
                'description': 'Citrix NetScaler load balancers',
                'backup_commands': {
                    'setup': [],
                    'backup': 'show ns runningConfig',
                    'enable_mode': False
                }
            },
            {
                'name': 'VMware NSX',
                'slug': 'vmware-nsx',
                'description': 'VMware NSX network virtualization',
                'backup_commands': {
                    'setup': [],
                    'backup': 'show configuration',
                    'enable_mode': False
                }
            },
            {
                'name': 'Riverbed',
                'slug': 'riverbed',
                'description': 'Riverbed WAN optimization',
                'backup_commands': {
                    'setup': [],
                    'backup': 'show configuration',
                    'enable_mode': False
                }
            },
            {
                'name': 'Ruckus',
                'slug': 'ruckus',
                'description': 'Ruckus wireless controllers',
                'backup_commands': {
                    'setup': [],
                    'backup': 'show running-config',
                    'enable_mode': False
                }
            },
            {
                'name': 'Cambium Networks',
                'slug': 'cambium',
                'description': 'Cambium wireless devices',
                'backup_commands': {
                    'setup': [],
                    'backup': 'show running-config',
                    'enable_mode': False
                }
            },
            {
                'name': 'Adtran',
                'slug': 'adtran',
                'description': 'Adtran routers and switches',
                'backup_commands': {
                    'setup': ['terminal length 0'],
                    'backup': 'show running-config',
                    'enable_mode': True
                }
            },
            {
                'name': 'Ciena',
                'slug': 'ciena',
                'description': 'Ciena optical networking',
                'backup_commands': {
                    'setup': [],
                    'backup': 'configuration show',
                    'enable_mode': False
                }
            },
            {
                'name': 'ZTE',
                'slug': 'zte',
                'description': 'ZTE networking equipment',
                'backup_commands': {
                    'setup': ['screen-length 0 temporary'],
                    'backup': 'show running-config',
                    'enable_mode': False
                }
            },
            {
                'name': 'Ericsson',
                'slug': 'ericsson',
                'description': 'Ericsson networking equipment',
                'backup_commands': {
                    'setup': [],
                    'backup': 'show configuration',
                    'enable_mode': False
                }
            },
            {
                'name': 'Enterasys',
                'slug': 'enterasys',
                'description': 'Enterasys switches',
                'backup_commands': {
                    'setup': ['set length 0'],
                    'backup': 'show configuration',
                    'enable_mode': False
                }
            },
        ]

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for vendor_data in vendors_data:
            slug = vendor_data['slug']

            # Check if vendor already exists
            existing_vendor = Vendor.objects.filter(slug=slug).first()

            if existing_vendor:
                # Update only if backup_commands is empty
                if not existing_vendor.backup_commands:
                    existing_vendor.name = vendor_data['name']
                    existing_vendor.description = vendor_data['description']
                    existing_vendor.backup_commands = vendor_data['backup_commands']
                    existing_vendor.save()
                    updated_count += 1
                    self.stdout.write(self.style.SUCCESS(f'Updated: {vendor_data["name"]}'))
                else:
                    skipped_count += 1
                    self.stdout.write(self.style.WARNING(f'Skipped (already configured): {vendor_data["name"]}'))
            else:
                # Create new vendor
                Vendor.objects.create(**vendor_data)
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Created: {vendor_data["name"]}'))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Summary:'))
        self.stdout.write(self.style.SUCCESS(f'  Created: {created_count}'))
        self.stdout.write(self.style.SUCCESS(f'  Updated: {updated_count}'))
        self.stdout.write(self.style.WARNING(f'  Skipped: {skipped_count}'))
        self.stdout.write(self.style.SUCCESS(f'  Total vendors in DB: {Vendor.objects.count()}'))
