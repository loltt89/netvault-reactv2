"""
Compliance policy evaluation — checks a device's backup configuration
against each active CompliancePolicy that targets it, and reconciles
ComplianceViolation rows to match the current result.
"""
import logging
import re

logger = logging.getLogger(__name__)


def _rule_passes(config_text: str, rule: dict) -> bool:
    """
    Evaluate a single rule dict against the configuration text. Returns
    True if the config satisfies the rule (i.e. NOT a violation).
    Malformed rules (bad regex, unknown type) fail safe by passing —
    a broken rule shouldn't itself become a permanent violation.
    """
    rule_type = rule.get('type')
    pattern = rule.get('pattern', '')
    is_regex = bool(rule.get('is_regex'))

    if not pattern:
        return True

    try:
        if is_regex:
            found = re.search(pattern, config_text, re.MULTILINE) is not None
        else:
            found = pattern in config_text
    except re.error as e:
        logger.warning(f"Compliance rule has invalid regex {pattern!r}: {e}")
        return True

    if rule_type == 'must_contain':
        return found
    elif rule_type == 'must_not_contain':
        return not found

    logger.warning(f"Compliance rule has unknown type {rule_type!r}, treating as pass")
    return True


def evaluate_backup_compliance(backup):
    """
    Run every active CompliancePolicy whose device_filters match
    backup.device against backup's configuration, and reconcile
    ComplianceViolation rows: still/newly-failing rules stay/become
    'open', rules that now pass get their existing open row resolved.

    Called after every successful backup with content — see
    backups.tasks.backup_device. Never raises: a bug in policy
    evaluation shouldn't be able to fail a backup that otherwise
    succeeded.
    """
    from .models import CompliancePolicy, ComplianceViolation
    from core.device_filters import device_matches_filters
    from django.utils import timezone

    device = backup.device

    try:
        config_text = backup.get_configuration()
    except Exception as e:
        logger.error(f"Compliance check: couldn't decrypt config for backup {backup.id}: {e}")
        return

    policies = CompliancePolicy.objects.filter(is_active=True)
    new_violation_count = 0

    for policy in policies:
        if not device_matches_filters(device, policy.device_filters):
            continue

        for index, rule in enumerate(policy.rules or []):
            passes = _rule_passes(config_text, rule)
            description = rule.get('description') or f"{rule.get('type')}: {rule.get('pattern')}"

            if passes:
                # Resolve any existing open violation for this exact rule
                ComplianceViolation.objects.filter(
                    policy=policy, device=device, rule_index=index, status='open',
                ).update(status='resolved', resolved_at=timezone.now())
                continue

            violation, created = ComplianceViolation.objects.update_or_create(
                policy=policy, device=device, rule_index=index,
                defaults={
                    'backup': backup,
                    'rule_description': description,
                    'status': 'open',
                    'resolved_at': None,
                },
            )
            if created:
                new_violation_count += 1

    if new_violation_count:
        logger.info(
            f"Compliance check for {device.name}: {new_violation_count} new violation(s)"
        )
