"""
Config Normalization Strategy Pattern
Normalizes device configurations before comparison to ignore dynamic content
"""
import re
from abc import ABC, abstractmethod
from typing import List


class ConfigNormalizer(ABC):
    """
    Base class for configuration normalization strategies

    Each vendor has specific dynamic content that changes on every backup
    but doesn't represent actual configuration changes (timestamps, crypto, etc.)
    """

    @abstractmethod
    def normalize(self, configuration: str) -> str:
        """
        Normalize configuration for comparison

        Args:
            configuration: Raw configuration text

        Returns:
            Normalized configuration (dynamic content removed/redacted)
        """
        pass


class GenericNormalizer(ConfigNormalizer):
    """Generic normalizer for vendors without specific rules"""

    def normalize(self, configuration: str) -> str:
        """Generic normalization - no changes"""
        return configuration


class MikrotikNormalizer(ConfigNormalizer):
    """
    MikroTik RouterOS normalizer

    Removes:
    - Timestamp lines (e.g., "# 2025-11-23 10:17:44 by RouterOS 7.16")
    """

    TIMESTAMP_PATTERN = re.compile(r'^# .+ by RouterOS .+$')

    def normalize(self, configuration: str) -> str:
        """Remove MikroTik timestamp comments"""
        lines = configuration.split('\n')
        normalized_lines = []

        for line in lines:
            # Skip timestamp line (e.g., "# 2025-11-23 10:17:44 by RouterOS 7.16")
            if line.startswith('# ') and ' by RouterOS ' in line:
                continue

            normalized_lines.append(line)

        return '\n'.join(normalized_lines)


class FortinetNormalizer(ConfigNormalizer):
    """
    Fortinet FortiGate normalizer

    Redacts:
    - Encrypted passwords (e.g., "set password ENC xxx" → "set password ENC [REDACTED]")
    - Encrypted secrets (e.g., "set ppk-secret ENC xxx")
    - Certificate/key blocks (-----BEGIN/END-----)
    """

    ENC_PASSWORD_PATTERN = re.compile(r'(set \S+ ENC )\S+')

    def normalize(self, configuration: str) -> str:
        """Redact FortiGate encrypted passwords and crypto blocks"""
        lines = configuration.split('\n')
        normalized_lines = []
        in_crypto_block = False

        for line in lines:
            # Normalize encrypted passwords (they change on every export)
            # Examples: "set password ENC xxx", "set ppk-secret ENC xxx"
            if ' ENC ' in line and not in_crypto_block:
                line = self.ENC_PASSWORD_PATTERN.sub(r'\1[REDACTED]', line)

            # Skip encrypted private keys and certificates content
            if '-----BEGIN' in line:
                in_crypto_block = True
                normalized_lines.append('[CRYPTO_BLOCK_START]')
                continue
            elif '-----END' in line:
                in_crypto_block = False
                normalized_lines.append('[CRYPTO_BLOCK_END]')
                continue

            if in_crypto_block:
                continue  # Skip all lines inside crypto blocks

            normalized_lines.append(line)

        return '\n'.join(normalized_lines)


class CiscoNormalizer(ConfigNormalizer):
    """
    Cisco IOS/IOS-XE normalizer

    Redacts:
    - Encrypted passwords (Type 7, Type 5)
    - Crypto keys
    - Timestamps in comments
    """

    # Common Cisco encrypted password patterns
    PASSWORD_PATTERNS = [
        re.compile(r'(username \S+ (?:password|secret) \d+ )\S+'),  # username admin password 7 xxx
        re.compile(r'(enable (?:password|secret) \d+ )\S+'),         # enable secret 5 xxx
        re.compile(r'((?:password|key-string) \d+ )\S+'),            # password 7 xxx
    ]

    def normalize(self, configuration: str) -> str:
        """Redact Cisco encrypted passwords and keys"""
        lines = configuration.split('\n')
        normalized_lines = []
        in_crypto_block = False

        for line in lines:
            # Skip crypto key blocks
            if line.strip().startswith('crypto ') and 'key' in line.lower():
                in_crypto_block = True
                normalized_lines.append('[CRYPTO_KEY_START]')
                continue
            elif in_crypto_block and line.strip().startswith('!'):
                in_crypto_block = False
                normalized_lines.append('[CRYPTO_KEY_END]')
                continue

            if in_crypto_block:
                continue

            # Redact encrypted passwords
            for pattern in self.PASSWORD_PATTERNS:
                line = pattern.sub(r'\1[REDACTED]', line)

            normalized_lines.append(line)

        return '\n'.join(normalized_lines)


class NormalizerFactory:
    """
    Factory for getting appropriate normalizer based on vendor
    """

    _normalizers = {
        'mikrotik': MikrotikNormalizer,
        'fortinet': FortinetNormalizer,
        'fortigate': FortinetNormalizer,  # Alias
        'cisco': CiscoNormalizer,
    }

    @classmethod
    def get_normalizer(cls, vendor: str) -> ConfigNormalizer:
        """
        Get normalizer for specific vendor

        Args:
            vendor: Vendor slug (e.g., 'mikrotik', 'fortinet', 'cisco')

        Returns:
            ConfigNormalizer instance (GenericNormalizer if vendor unknown)
        """
        vendor_lower = vendor.lower() if vendor else ''
        normalizer_class = cls._normalizers.get(vendor_lower, GenericNormalizer)
        return normalizer_class()

    @classmethod
    def register_normalizer(cls, vendor: str, normalizer_class: type):
        """
        Register custom normalizer for vendor

        Args:
            vendor: Vendor slug
            normalizer_class: ConfigNormalizer subclass
        """
        cls._normalizers[vendor.lower()] = normalizer_class


def normalize_config(configuration: str, vendor: str = None) -> str:
    """
    Convenience function for normalizing configuration

    Args:
        configuration: Configuration text
        vendor: Vendor slug (optional)

    Returns:
        Normalized configuration
    """
    normalizer = NormalizerFactory.get_normalizer(vendor or '')
    return normalizer.normalize(configuration)
