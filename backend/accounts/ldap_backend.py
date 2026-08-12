"""
LDAP Authentication Backend for Active Directory integration
"""
from django_auth_ldap.backend import LDAPBackend
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class NetVaultLDAPBackend(LDAPBackend):
    """
    Custom LDAP backend for NetVault
    Handles user creation and updates from Active Directory
    """

    def authenticate_ldap_user(self, ldap_user, password):
        """
        Authenticate user against LDAP and create/update local user
        """
        user = super().authenticate_ldap_user(ldap_user, password)

        if user:
            # Mark as LDAP user
            user.is_ldap_user = True
            user.ldap_dn = ldap_user.dn

            # Map LDAP groups to roles
            ldap_groups = ldap_user.group_names
            user.role = self._map_ldap_groups_to_role(ldap_groups)

            user.save()

            logger.info(f"LDAP user authenticated: {user.email} with role {user.role}")

        return user

    def get_user(self, user_id):
        """Get user by ID"""
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

    def _map_ldap_groups_to_role(self, ldap_groups):
        """
        Map LDAP/AD groups to NetVault roles.

        Matching is exact (case-insensitive), against the group name lists
        in settings.LDAP_ADMIN_GROUPS / LDAP_OPERATOR_GROUPS /
        LDAP_AUDITOR_GROUPS — configure those per deployment, see
        LDAP_SETUP.md, rather than editing this method.

        This used to be a substring check (`pattern in group`), which meant
        any AD group whose name merely *contained* a pattern like
        "administrators" granted that role — a group named e.g.
        "IT-Administrators-Helpdesk" or "Former-Domain-Admins-Readonly"
        would silently escalate its members to NetVault administrator.
        Real AD environments accumulate exactly this kind of incidentally-
        similar group name over time, so this was a live privilege-
        escalation path, not just a theoretical one. Exact matching against
        an explicit, per-deployment configured list closes it.
        """
        if not ldap_groups:
            return 'viewer'

        from django.conf import settings

        groups_lower = {g.strip().lower() for g in ldap_groups}

        if groups_lower & settings.LDAP_ADMIN_GROUPS:
            return 'administrator'
        if groups_lower & settings.LDAP_OPERATOR_GROUPS:
            return 'operator'
        if groups_lower & settings.LDAP_AUDITOR_GROUPS:
            return 'auditor'

        return 'viewer'


def populate_user_from_ldap(sender, user=None, ldap_user=None, **kwargs):
    """
    Signal handler to populate user fields from LDAP
    Called when user is created or updated from LDAP
    """
    if ldap_user:
        # Map LDAP attributes to user model
        user.first_name = ldap_user.attrs.get('givenName', [''])[0]
        user.last_name = ldap_user.attrs.get('sn', [''])[0]
        user.email = ldap_user.attrs.get('mail', [''])[0] or user.username

        # Additional fields
        user.is_ldap_user = True
        user.ldap_dn = ldap_user.dn

        logger.info(f"Populated user from LDAP: {user.email}")
