"""
Role-based permissions for NetVault
"""
from rest_framework import permissions


class RoleBasedPermission(permissions.BasePermission):
    """
    Base permission class for role-based access control

    Roles hierarchy:
    - Administrator: Full access
    - Operator: Can create, read, update devices and backups
    - Auditor: Read-only access + audit logs
    - Viewer: Read-only access
    """

    # Define allowed methods for each role
    ROLE_PERMISSIONS = {
        'administrator': ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
        'operator': ['GET', 'POST', 'PUT', 'PATCH'],  # No DELETE
        'auditor': ['GET'],  # Read-only
        'viewer': ['GET'],  # Read-only
    }

    def has_permission(self, request, view):
        # Allow authenticated users
        if not request.user or not request.user.is_authenticated:
            return False

        # Superusers have full access
        if request.user.is_superuser:
            return True

        # Check role permissions
        user_role = getattr(request.user, 'role', 'viewer')
        allowed_methods = self.ROLE_PERMISSIONS.get(user_role, [])

        return request.method in allowed_methods


class IsAdministrator(permissions.BasePermission):
    """Only administrators can access"""

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            (request.user.role == 'administrator' or request.user.is_superuser)
        )


class IsOperatorOrAdmin(permissions.BasePermission):
    """Operators and administrators can access"""

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            (request.user.role in ['operator', 'administrator'] or request.user.is_superuser)
        )


class IsAuditorOrAdmin(permissions.BasePermission):
    """Auditors and administrators can access"""

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            (request.user.role in ['auditor', 'administrator'] or request.user.is_superuser)
        )


class CanManageDevices(permissions.BasePermission):
    """
    Permission for device management
    - Administrator: Full access
    - Operator: Can create, read, update, backup
    - Viewer: Read-only
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser or request.user.role == 'administrator':
            return True

        if request.user.role == 'operator':
            # Operators can't delete devices
            return request.method in ['GET', 'POST', 'PUT', 'PATCH']

        if request.user.role in ['viewer', 'auditor']:
            # View-only access
            return request.method == 'GET'

        return False


class CanManageBackups(permissions.BasePermission):
    """
    Permission for backup management
    - Administrator: Full access
    - Operator: Can create, read, download, restore
    - Auditor: Read-only + download
    - Viewer: Read-only
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser or request.user.role == 'administrator':
            return True

        if request.user.role == 'operator':
            # Operators can backup and restore but not delete old backups
            if view.action in ['list', 'retrieve', 'create', 'backup_now', 'restore', 'download', 'compare']:
                return True
            return request.method in ['GET', 'POST']

        if request.user.role == 'auditor':
            # Auditors can view and download for audit purposes
            return view.action in ['list', 'retrieve', 'download', 'compare'] or request.method == 'GET'

        if request.user.role == 'viewer':
            # Viewers can only view
            return view.action in ['list', 'retrieve'] or request.method == 'GET'

        return False


class CanViewAuditLogs(permissions.BasePermission):
    """
    Permission for audit logs
    - Administrator: Full access
    - Auditor: Read access to all logs
    - Others: Read access to own logs only
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Administrators and auditors can view all logs
        if request.user.is_superuser or request.user.role in ['administrator', 'auditor']:
            return True

        # Others can only view their own logs (filtered in queryset)
        return request.method == 'GET'


class CanManageUsers(permissions.BasePermission):
    """
    Permission for user management
    Only administrators can manage users
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Only administrators can manage other users
        if request.user.is_superuser or request.user.role == 'administrator':
            return True

        # Users can view and update their own profile
        if view.action in ['me', 'update_profile', 'change_password', 'enable_2fa', 'verify_2fa', 'disable_2fa']:
            return True

        return False
