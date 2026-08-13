"""
Device-filter matching, shared by two otherwise-unrelated features that
both ended up needing "does this device match this set of criteria":

  - notifications.services.dispatch_rules() — NotificationRule.device_filters
    decides which devices a notification rule fires for.
  - accounts device-scope RBAC — User.device_scope restricts which
    devices a non-administrator can see/act on at all.

Both use the identical {"tags": [...], "criticality": [...], ...} shape
on purpose, so "a rule targeting these devices" and "a user scoped to
these devices" mean the same thing — one implementation, not two that
could quietly drift apart.
"""


def device_matches_filters(device, filters):
    """
    Check whether `device` matches a filters dict. Supported keys: tags
    (any overlap with the device's tag list), criticality, vendor_id,
    device_type_id, location — each accepts either a single value or a
    list of acceptable values, AND'd together across keys. Unrecognized
    keys are ignored rather than excluding every device (a typo in a
    filter key shouldn't silently lock everyone out / fire for nobody).

    An empty/falsy filters dict always matches (no restriction).
    """
    if not filters:
        return True
    if device is None:
        return False

    def _as_list(value):
        return value if isinstance(value, list) else [value]

    for key, expected in filters.items():
        if key == 'tags':
            if not set(device.tags or []) & set(_as_list(expected)):
                return False
        elif key == 'criticality':
            if device.criticality not in _as_list(expected):
                return False
        elif key == 'vendor_id':
            if device.vendor_id not in _as_list(expected):
                return False
        elif key == 'device_type_id':
            if device.device_type_id not in _as_list(expected):
                return False
        elif key == 'location':
            if device.location not in _as_list(expected):
                return False
        # unknown key: ignore, don't exclude

    return True


def get_scoped_device_ids(user):
    """
    Return None if `user` has unrestricted device access — superuser,
    'administrator' role, or an empty/unset device_scope — meaning "don't
    filter, use the queryset as-is". Otherwise return the set of Device
    IDs their device_scope permits, for `.filter(id__in=...)` /
    `.filter(device_id__in=...)`.

    Administrators are never restricted by device_scope even if one is
    somehow set on their account — scoping is a way to narrow a
    lesser role, not a way to lock out an admin.
    """
    if user.is_superuser or getattr(user, 'role', None) == 'administrator':
        return None

    scope = getattr(user, 'device_scope', None)
    if not scope:
        return None

    from devices.models import Device
    return {d.id for d in Device.objects.all() if device_matches_filters(d, scope)}
