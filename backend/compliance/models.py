from django.db import models
from django.conf import settings
from devices.models import Device
from backups.models import Backup


class CompliancePolicy(models.Model):
    """
    A set of pattern-based rules checked against a device's latest
    successful backup — "no telnet enabled", "NTP must be configured",
    etc. Uses the same device_filters shape as NotificationRule and
    User.device_scope (see core.device_filters) so a policy scoped to
    "core routers" means the same thing everywhere else that phrase is
    used in NetVault.

    Each entry in `rules` is:
        {"type": "must_contain" | "must_not_contain",
         "pattern": "...", "is_regex": false,
         "description": "human-readable reason, shown on violations"}
    """
    SEVERITY_CHOICES = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    )

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='medium')

    device_filters = models.JSONField(default=dict, blank=True)
    rules = models.JSONField(default=list)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='compliance_policies_created',
    )

    class Meta:
        db_table = 'compliance_policies'
        verbose_name = 'Compliance Policy'
        verbose_name_plural = 'Compliance Policies'
        ordering = ['name']

    def __str__(self):
        return self.name


class ComplianceViolation(models.Model):
    """
    A single rule, from a single policy, currently failing for a single
    device — as of the most recent backup that was checked. Re-evaluated
    on every new successful backup: still-failing violations are left
    open, newly-failing rules create a new row, and rules that now pass
    auto-resolve their existing open row (resolved_at set, status
    flipped) rather than leaving stale violations around forever.
    """
    STATUS_CHOICES = (
        ('open', 'Open'),
        ('resolved', 'Resolved'),
    )

    policy = models.ForeignKey(CompliancePolicy, on_delete=models.CASCADE, related_name='violations')
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='compliance_violations')
    backup = models.ForeignKey(
        Backup, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='compliance_violations',
        help_text='The backup that was checked when this violation was last (re)detected',
    )

    rule_index = models.IntegerField(help_text='Index into policy.rules — identifies which rule this is')
    rule_description = models.TextField(help_text='Snapshot of the rule description at detection time')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')

    detected_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'compliance_violations'
        verbose_name = 'Compliance Violation'
        verbose_name_plural = 'Compliance Violations'
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['status', '-detected_at']),
            models.Index(fields=['policy', 'device', 'rule_index']),
        ]
        # One open (or resolved) row per (policy, device, rule) at a time —
        # re-evaluation updates this row in place rather than piling up
        # duplicates for a rule that's been failing for months.
        unique_together = [['policy', 'device', 'rule_index']]

    def __str__(self):
        return f'{self.policy.name} / {self.device.name}: {self.rule_description[:50]}'
