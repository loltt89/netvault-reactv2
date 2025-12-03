"""
Management command to add popular network device vendors
Similar to oxidized's vendor support
"""
from django.core.management.base import BaseCommand
from django.db.models import Q
from devices.models import Vendor


class Command(BaseCommand):
    help = 'Add popular network device vendors with backup commands'

    def handle(self, *args, **kwargs):
        vendors_data = [
            # ===== Cisco family =====
            {
                'name': 'Cisco',
                'slug': 'cisco',
                'description': 'Cisco IOS and IOS-XE devices (routers, switches, ASR, ISR)',
                'backup_commands': {
                    'setup': ['terminal length 0', 'terminal width 0'],
                    'backup': 'show running-config',
                    'enable_mode': True,
                    'config_start': ['Building configuration', 'Current configuration', '!', 'version '],
                    'config_end': ['end'],
                }
            },
            {
                'name': 'Cisco IOS-XR',
                'slug': 'cisco-ios-xr',
                'description': 'Cisco IOS-XR devices (CRS, ASR 9000)',
                'backup_commands': {
                    'setup': ['terminal length 0'],
                    'backup': 'show running-config',
                    'enable_mode': False,
                    'config_start': ['Building configuration', '!! IOS XR', '!', 'hostname '],
                    'config_end': ['end'],
                }
            },
            {
                'name': 'Cisco NX-OS',
                'slug': 'cisco-nxos',
                'description': 'Cisco Nexus switches',
                'backup_commands': {
                    'setup': ['terminal length 0'],
                    'backup': 'show running-config',
                    'enable_mode': False,
                    'config_start': ['!Command:', '!Running configuration', 'version '],
                    'config_end': ['end'],
                }
            },
            {
                'name': 'Cisco ASA',
                'slug': 'cisco-asa',
                'description': 'Cisco ASA firewalls',
                'backup_commands': {
                    'setup': ['terminal pager 0'],
                    'backup': 'show running-config',
                    'enable_mode': True,
                    'config_start': ['ASA Version', ': Saved', '!'],
                    'config_end': ['end'],
                }
            },
            # ===== Juniper =====
            {
                'name': 'Juniper JunOS',
                'slug': 'juniper-junos',
                'description': 'Juniper Networks devices',
                'backup_commands': {
                    'setup': ['set cli screen-length 0'],
                    'backup': 'show configuration',
                    'enable_mode': False,
                    'config_start': ['## Last commit', 'version ', 'system {', 'groups {'],
                    'config_end': [],
                }
            },
            # ===== Arista =====
            {
                'name': 'Arista EOS',
                'slug': 'arista-eos',
                'description': 'Arista switches',
                'backup_commands': {
                    'setup': ['terminal length 0'],
                    'backup': 'show running-config',
                    'enable_mode': True,
                    'config_start': ['! Command:', '! device:', '! boot', 'hostname '],
                    'config_end': ['end'],
                }
            },
            # ===== HP / Aruba =====
            {
                'name': 'HP ProCurve',
                'slug': 'hp-procurve',
                'description': 'HP ProCurve switches',
                'backup_commands': {
                    'setup': ['no page'],
                    'backup': 'show running-config',
                    'enable_mode': False,
                    'config_start': ['Running configuration', ';', 'hostname '],
                    'config_end': [],
                }
            },
            {
                'name': 'HP Comware',
                'slug': 'hp-comware',
                'description': 'HP Comware switches (3Com, H3C)',
                'backup_commands': {
                    'setup': ['screen-length disable'],
                    'backup': 'display current-configuration',
                    'enable_mode': False,
                    'config_start': ['#', 'sysname ', 'return', 'version'],
                    'config_end': ['return'],
                }
            },
            {
                'name': 'Aruba',
                'slug': 'aruba',
                'description': 'Aruba switches and controllers',
                'backup_commands': {
                    'setup': ['no paging'],
                    'backup': 'show running-config',
                    'enable_mode': False,
                    'config_start': ['Running configuration', 'version', 'hostname '],
                    'config_end': [],
                }
            },
            # ===== Huawei =====
            {
                'name': 'Huawei VRP',
                'slug': 'huawei-vrp',
                'description': 'Huawei routers and switches',
                'backup_commands': {
                    'setup': ['screen-length 0 temporary'],
                    'backup': 'display current-configuration',
                    'enable_mode': False,
                    'config_start': ['#', 'sysname ', 'return', 'version'],
                    'config_end': ['return'],
                }
            },
            # ===== MikroTik =====
            {
                'name': 'Mikrotik RouterOS',
                'slug': 'mikrotik',
                'description': 'Mikrotik routers and switches',
                'backup_commands': {
                    'setup': [],
                    'backup': '/export',
                    'enable_mode': False,
                    'exec_mode': True,  # Use exec instead of shell
                    'config_start': ['# ', '/', '# software id'],
                    'config_end': [],
                }
            },
            # ===== Fortinet =====
            {
                'name': 'Fortinet FortiGate',
                'slug': 'fortinet-fortigate',
                'description': 'FortiGate firewalls',
                'backup_commands': {
                    'setup': ['config system console', 'set output standard', 'end'],
                    'backup': 'show full-configuration',
                    'enable_mode': False,
                    'config_start': ['#config-version=', 'config system global', 'config '],
                    'config_end': [],
                }
            },
            # ===== Palo Alto =====
            {
                'name': 'Palo Alto Networks',
                'slug': 'paloalto',
                'description': 'Palo Alto firewalls',
                'backup_commands': {
                    'setup': ['set cli pager off'],
                    'backup': 'show config running',
                    'enable_mode': False,
                    'config_start': ['<config ', '<entry ', 'set deviceconfig'],
                    'config_end': [],
                }
            },
            # ===== F5 =====
            {
                'name': 'F5 Networks',
                'slug': 'f5-networks',
                'description': 'F5 BIG-IP load balancers',
                'backup_commands': {
                    'setup': [],
                    'backup': 'tmsh show running-config',
                    'enable_mode': False,
                    'config_start': ['#TMSH-VERSION:', 'ltm ', 'sys '],
                    'config_end': [],
                }
            },
            # ===== Dell =====
            {
                'name': 'Dell Force10',
                'slug': 'dell-force10',
                'description': 'Dell Force10 switches',
                'backup_commands': {
                    'setup': ['terminal length 0'],
                    'backup': 'show running-config',
                    'enable_mode': True,
                    'config_start': ['!Current Configuration', 'hostname '],
                    'config_end': ['end'],
                }
            },
            {
                'name': 'Dell PowerConnect',
                'slug': 'dell-powerconnect',
                'description': 'Dell PowerConnect switches',
                'backup_commands': {
                    'setup': ['terminal datadump'],
                    'backup': 'show running-config',
                    'enable_mode': False,
                    'config_start': ['!System Description', 'configure', 'hostname '],
                    'config_end': [],
                }
            },
            # ===== Brocade =====
            {
                'name': 'Brocade',
                'slug': 'brocade',
                'description': 'Brocade switches',
                'backup_commands': {
                    'setup': ['skip-page-display'],
                    'backup': 'show running-config',
                    'enable_mode': True,
                    'config_start': ['!', 'ver ', 'module '],
                    'config_end': ['end'],
                }
            },
            # ===== Extreme =====
            {
                'name': 'Extreme Networks',
                'slug': 'extreme',
                'description': 'Extreme Networks EXOS switches',
                'backup_commands': {
                    'setup': ['disable clipaging'],
                    'backup': 'show configuration',
                    'enable_mode': False,
                    'config_start': ['#', 'Module ', 'configure '],
                    'config_end': [],
                    'skip_patterns': ['disable clipaging', 'disable cli paging', 'exos-vm', 'primary.cfg'],
                }
            },
            # ===== Alcatel / Nokia =====
            {
                'name': 'Alcatel-Lucent',
                'slug': 'alcatel-lucent',
                'description': 'Alcatel-Lucent switches',
                'backup_commands': {
                    'setup': [],
                    'backup': 'show configuration snapshot',
                    'enable_mode': False,
                    'config_start': ['# TiMOS', 'configure ', 'echo '],
                    'config_end': [],
                }
            },
            {
                'name': 'Nokia SR OS',
                'slug': 'nokia-sros',
                'description': 'Nokia Service Router OS',
                'backup_commands': {
                    'setup': ['environment no more'],
                    'backup': 'admin display-config',
                    'enable_mode': False,
                    'config_start': ['# TiMOS', 'configure ', 'echo '],
                    'config_end': [],
                }
            },
            # ===== Ubiquiti =====
            {
                'name': 'Ubiquiti EdgeRouter',
                'slug': 'ubiquiti-edgerouter',
                'description': 'Ubiquiti EdgeRouter devices',
                'backup_commands': {
                    'setup': ['set terminal length 0'],
                    'backup': 'show configuration',
                    'enable_mode': False,
                    'config_start': ['firewall {', 'interfaces {', 'service {'],
                    'config_end': [],
                }
            },
            {
                'name': 'Ubiquiti UniFi',
                'slug': 'ubiquiti-unifi',
                'description': 'Ubiquiti UniFi switches',
                'backup_commands': {
                    'setup': [],
                    'backup': 'show running-config',
                    'enable_mode': False,
                    'config_start': ['!', '#', 'hostname '],
                    'config_end': [],
                }
            },
            # ===== VyOS =====
            {
                'name': 'VyOS',
                'slug': 'vyos',
                'description': 'VyOS network operating system',
                'backup_commands': {
                    'setup': [],
                    'backup': 'show configuration',
                    'enable_mode': False,
                    'exec_mode': True,  # Use exec instead of shell
                    'exec_wrapper': '/opt/vyatta/bin/vyatta-op-cmd-wrapper',  # VyOS wrapper
                    'config_start': ['firewall {', 'interfaces {', 'service {', 'system {'],
                    'config_end': [],
                }
            },
            # ===== Check Point =====
            {
                'name': 'Check Point Gaia',
                'slug': 'checkpoint-gaia',
                'description': 'Check Point Gaia OS',
                'backup_commands': {
                    'setup': ['set clienv rows 0'],
                    'backup': 'show configuration',
                    'enable_mode': False,
                    'config_start': [':set ', ':admininfo ', 'config '],
                    'config_end': [],
                }
            },
            # ===== Other vendors =====
            {
                'name': 'Zyxel',
                'slug': 'zyxel',
                'description': 'Zyxel switches and routers',
                'backup_commands': {
                    'setup': [],
                    'backup': 'show running-config',
                    'enable_mode': False,
                    'config_start': ['!', 'hostname ', 'vlan '],
                    'config_end': [],
                }
            },
            {
                'name': 'TP-Link',
                'slug': 'tplink',
                'description': 'TP-Link switches',
                'backup_commands': {
                    'setup': [],
                    'backup': 'show running-config',
                    'enable_mode': False,
                    'config_start': ['!', '#', 'hostname '],
                    'config_end': [],
                }
            },
            {
                'name': 'D-Link',
                'slug': 'dlink',
                'description': 'D-Link switches',
                'backup_commands': {
                    'setup': [],
                    'backup': 'show config current_config',
                    'enable_mode': False,
                    'config_start': ['#', 'config ', 'vlan '],
                    'config_end': [],
                }
            },
            {
                'name': 'Netgear',
                'slug': 'netgear',
                'description': 'Netgear switches',
                'backup_commands': {
                    'setup': ['terminal length 0'],
                    'backup': 'show running-config',
                    'enable_mode': False,
                    'config_start': ['!Current Configuration', 'vlan ', 'hostname '],
                    'config_end': [],
                }
            },
            {
                'name': 'Allied Telesis',
                'slug': 'allied-telesis',
                'description': 'Allied Telesis switches',
                'backup_commands': {
                    'setup': [],
                    'backup': 'show running-config',
                    'enable_mode': False,
                    'config_start': ['!', 'hostname ', 'awplus '],
                    'config_end': [],
                }
            },
            {
                'name': 'A10 Networks',
                'slug': 'a10-networks',
                'description': 'A10 Thunder load balancers',
                'backup_commands': {
                    'setup': ['terminal length 0'],
                    'backup': 'show running-config',
                    'enable_mode': True,
                    'config_start': ['!', 'hostname ', 'version '],
                    'config_end': ['end'],
                }
            },
            {
                'name': 'Citrix NetScaler',
                'slug': 'citrix-netscaler',
                'description': 'Citrix NetScaler load balancers',
                'backup_commands': {
                    'setup': [],
                    'backup': 'show ns runningConfig',
                    'enable_mode': False,
                    'config_start': ['#NS', 'set ', 'add '],
                    'config_end': [],
                }
            },
            {
                'name': 'VMware NSX',
                'slug': 'vmware-nsx',
                'description': 'VMware NSX network virtualization',
                'backup_commands': {
                    'setup': [],
                    'backup': 'show configuration',
                    'enable_mode': False,
                    'config_start': ['!', '#', 'hostname '],
                    'config_end': [],
                }
            },
            {
                'name': 'Riverbed',
                'slug': 'riverbed',
                'description': 'Riverbed WAN optimization',
                'backup_commands': {
                    'setup': [],
                    'backup': 'show configuration',
                    'enable_mode': False,
                    'config_start': ['## ', 'hostname ', 'config '],
                    'config_end': [],
                }
            },
            {
                'name': 'Ruckus',
                'slug': 'ruckus',
                'description': 'Ruckus wireless controllers',
                'backup_commands': {
                    'setup': [],
                    'backup': 'show running-config',
                    'enable_mode': False,
                    'config_start': ['!', 'hostname ', 'version '],
                    'config_end': [],
                }
            },
            {
                'name': 'Cambium Networks',
                'slug': 'cambium',
                'description': 'Cambium wireless devices',
                'backup_commands': {
                    'setup': [],
                    'backup': 'show running-config',
                    'enable_mode': False,
                    'config_start': ['!', '#', 'hostname '],
                    'config_end': [],
                }
            },
            {
                'name': 'Adtran',
                'slug': 'adtran',
                'description': 'Adtran routers and switches',
                'backup_commands': {
                    'setup': ['terminal length 0'],
                    'backup': 'show running-config',
                    'enable_mode': True,
                    'config_start': ['!', 'hostname ', 'version '],
                    'config_end': ['end'],
                }
            },
            {
                'name': 'Ciena',
                'slug': 'ciena',
                'description': 'Ciena optical networking',
                'backup_commands': {
                    'setup': [],
                    'backup': 'configuration show',
                    'enable_mode': False,
                    'config_start': ['configuration ', '!', 'system '],
                    'config_end': [],
                }
            },
            {
                'name': 'ZTE',
                'slug': 'zte',
                'description': 'ZTE networking equipment',
                'backup_commands': {
                    'setup': ['screen-length 0 temporary'],
                    'backup': 'show running-config',
                    'enable_mode': False,
                    'config_start': ['#', 'sysname ', 'version'],
                    'config_end': ['return'],
                }
            },
            {
                'name': 'Ericsson',
                'slug': 'ericsson',
                'description': 'Ericsson networking equipment',
                'backup_commands': {
                    'setup': [],
                    'backup': 'show configuration',
                    'enable_mode': False,
                    'config_start': ['!', '#', 'hostname '],
                    'config_end': [],
                }
            },
            {
                'name': 'Enterasys',
                'slug': 'enterasys',
                'description': 'Enterasys switches',
                'backup_commands': {
                    'setup': ['set length 0'],
                    'backup': 'show configuration',
                    'enable_mode': False,
                    'config_start': ['#', 'set '],
                    'config_end': [],
                }
            },
            {
                'name': 'Grandstream',
                'slug': 'grandstream',
                'description': 'Grandstream network switches (GWN series) and VoIP devices',
                'backup_commands': {
                    'setup': [],
                    'backup': 'show running-config',
                    'enable_mode': False,
                    'config_start': ['!', '#', 'hostname '],
                    'config_end': [],
                }
            },
            {
                'name': 'Eltex',
                'slug': 'eltex',
                'description': 'Eltex network equipment (MES/ESR series)',
                'backup_commands': {
                    'setup': ['terminal datadump'],
                    'backup': 'show running-config',
                    'enable_mode': True,
                    'config_start': ['!', 'hostname ', 'version '],
                    'config_end': ['end'],
                }
            },
            {
                'name': 'OpenWRT',
                'slug': 'openwrt',
                'description': 'OpenWRT firmware for routers and access points',
                'backup_commands': {
                    'setup': [],
                    'backup': 'for file in /etc/config/*; do echo "### $file ###"; cat "$file"; echo ""; done',
                    'enable_mode': False,
                    'config_start': ['### ', 'config ', 'option '],
                    'config_end': [],
                }
            },
            # ===== Cumulus Linux (NVIDIA) =====
            {
                'name': 'Cumulus Linux',
                'slug': 'cumulus',
                'description': 'Cumulus Linux - NVIDIA open network operating system (NVUE CLI)',
                'backup_commands': {
                    'setup': [],
                    'backup': 'nv config show',
                    'enable_mode': False,
                    'config_start': ['- set:', 'set:', 'interface:', 'router:', 'system:'],
                    'config_end': [],
                }
            },
            # ===== SONiC (Microsoft/Azure) =====
            {
                'name': 'SONiC',
                'slug': 'sonic',
                'description': 'SONiC (Software for Open Networking in the Cloud) - Microsoft/Azure open source switch OS',
                'backup_commands': {
                    'setup': [],
                    'backup': 'show runningconfiguration all',
                    'enable_mode': False,
                    'config_start': ['{', '"DEVICE_METADATA"', '"PORT"', '"INTERFACE"'],
                    'config_end': ['}'],
                }
            },
            # ===== Ruijie =====
            {
                'name': 'Ruijie',
                'slug': 'ruijie',
                'description': 'Ruijie Networks - Chinese vendor with Cisco-like CLI',
                'backup_commands': {
                    'setup': ['terminal length 0'],
                    'backup': 'show running-config',
                    'enable_mode': True,
                    'config_start': ['!', 'Building configuration', 'Current configuration', 'version '],
                    'config_end': ['end'],
                }
            },
            {
                'name': 'Generic',
                'slug': 'generic',
                'description': 'Generic network device (SSH/Telnet)',
                'backup_commands': {
                    'setup': [],
                    'backup': 'show running-config',
                    'enable_mode': False,
                    'config_start': ['!', '#', 'hostname ', 'version ', 'config'],
                    'config_end': ['end'],
                }
            },
        ]

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for vendor_data in vendors_data:
            slug = vendor_data['slug']
            name = vendor_data['name']

            # Check if vendor already exists by slug OR name (both are unique)
            existing_vendor = Vendor.objects.filter(
                Q(slug=slug) | Q(name=name)
            ).first()

            if existing_vendor:
                # Update slug if it changed (name matched but slug different)
                if existing_vendor.slug != slug:
                    existing_vendor.slug = slug
                # Update only if backup_commands is empty OR missing new fields
                needs_update = (
                    not existing_vendor.backup_commands or
                    'config_start' not in existing_vendor.backup_commands
                )
                if needs_update:
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
