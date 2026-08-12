# Active Directory / LDAP Integration Guide

NetVault supports authentication and authorization via Active Directory (AD) or LDAP servers.

> **Known gap:** the `LDAP_ENABLED` / `LDAP_SERVER_URI` / … fields in System Settings (`.env`)
> only populate the `SystemSettings` DB row shown in the UI — they do **not** configure
> `django-auth-ldap` or `AUTHENTICATION_BACKENDS`. Toggling LDAP on in the UI alone does
> nothing. The steps below (manually editing `settings.py` / `ldap_backend.py` / `apps.py`)
> are currently the *only* way to actually enable LDAP. Tracked for consolidation into one
> config path — until then, follow this guide start to finish, not the UI toggle.

## Features

- **Single Sign-On (SSO)** - Users can log in with their AD credentials
- **Automatic Role Mapping** - AD groups are automatically mapped to NetVault roles
- **User Synchronization** - User information is synced from AD on each login
- **Hybrid Mode** - Mix of local and LDAP users in the same system

## Prerequisites

1. **LDAP Server Access**
   - LDAP server hostname/IP
   - Port (usually 389 for LDAP, 636 for LDAPS)
   - Service account credentials with read access to users and groups

2. **System Dependencies** (already installed by install.sh)
   ```bash
   sudo apt install libldap2-dev libsasl2-dev
   ```

3. **Python Packages** (already in requirements.txt)
   ```
   django-auth-ldap==4.6.0
   python-ldap==3.4.4
   ```

## Configuration Steps

### 1. Configure LDAP Settings

Edit `<project_root>/backend/netvault/settings.py` and add:

```python
# Import LDAP configuration
from netvault.ldap_settings import *
```

### 2. Update LDAP Connection Details

Edit `<project_root>/backend/netvault/ldap_settings.py`:

```python
# LDAP Server URI
AUTH_LDAP_SERVER_URI = "ldap://dc.yourdomain.com:389"
# For secure LDAPS:
# AUTH_LDAP_SERVER_URI = "ldaps://dc.yourdomain.com:636"

# Service Account (with read permissions)
AUTH_LDAP_BIND_DN = "CN=netvault-service,OU=Service Accounts,DC=yourdomain,DC=com"
AUTH_LDAP_BIND_PASSWORD = "your-service-account-password"

# User Search Base
AUTH_LDAP_USER_SEARCH = LDAPSearch(
    "OU=Users,DC=yourdomain,DC=com",  # Base DN for users
    ldap.SCOPE_SUBTREE,
    "(sAMAccountName=%(user)s)"  # Search filter
)

# Group Search Base
AUTH_LDAP_GROUP_SEARCH = LDAPSearch(
    "OU=Groups,DC=yourdomain,DC=com",  # Base DN for groups
    ldap.SCOPE_SUBTREE,
    "(objectClass=group)"
)
```

### 3. Configure AD Groups to NetVault Roles Mapping

Group name matching is **exact** (case-insensitive), not substring — a group
merely *containing* "administrators" in its name (e.g. an unrelated group
like "IT-Administrators-Helpdesk") must never grant the `administrator`
role. Set the group name lists in your environment (`.env`) rather than
editing `accounts/ldap_backend.py`'s matching logic itself:

```bash
# .env — comma-separated AD/LDAP group CNs, one list per role.
# Defaults if unset:
#   LDAP_ADMIN_GROUPS=NetVault-Admins,NetVault Admins,Domain Admins,Administrators
#   LDAP_OPERATOR_GROUPS=NetVault-Operators,NetVault Operators,Network Operators
#   LDAP_AUDITOR_GROUPS=NetVault-Auditors,NetVault Auditors,Security Auditors
# Override to match your AD groups exactly — each entry must equal the
# group's CN exactly (case-insensitive), not just appear inside it.
LDAP_ADMIN_GROUPS=NetVault-Admins,Domain Admins
LDAP_OPERATOR_GROUPS=NetVault-Operators
LDAP_AUDITOR_GROUPS=NetVault-Auditors
```

`accounts/ldap_backend.py`'s `_map_ldap_groups_to_role` reads these from
`settings.LDAP_ADMIN_GROUPS` / `LDAP_OPERATOR_GROUPS` / `LDAP_AUDITOR_GROUPS`
and checks for exact membership — there's nothing left to edit in the method
itself for a normal group-naming change.

### 4. Enable LDAP Backend

In `<project_root>/backend/netvault/settings.py`, add:

```python
AUTHENTICATION_BACKENDS = [
    'accounts.ldap_backend.NetVaultLDAPBackend',  # Try LDAP first
    'django.contrib.auth.backends.ModelBackend',   # Fallback to local auth
]
```

### 5. Connect Signal Handler

In `<project_root>/backend/accounts/apps.py`, add:

```python
from django.apps import AppConfig

class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        # Connect LDAP signal
        from django_auth_ldap.backend import populate_user
        from accounts.ldap_backend import populate_user_from_ldap
        populate_user.connect(populate_user_from_ldap)
```

## Testing LDAP Connection

### Test with Django Shell

```bash
cd <project_root>/backend
source venv/bin/activate
python manage.py shell
```

```python
from django_auth_ldap.backend import LDAPBackend
from django.contrib.auth import authenticate

# Test LDAP connection
backend = LDAPBackend()
user = backend.authenticate(request=None, username='testuser', password='testpass')

if user:
    print(f"Success! User: {user.email}, Role: {user.role}")
    print(f"LDAP DN: {user.ldap_dn}")
    print(f"Groups: {user.ldap_user.group_names}")
else:
    print("Authentication failed")
```

### Test LDAP Bind

```python
import ldap

# Test connection
conn = ldap.initialize("ldap://dc.yourdomain.com:389")
conn.set_option(ldap.OPT_REFERRALS, 0)

try:
    conn.simple_bind_s("CN=service-account,DC=domain,DC=com", "password")
    print("✓ LDAP bind successful")

    # Search for a user
    result = conn.search_s(
        "OU=Users,DC=domain,DC=com",
        ldap.SCOPE_SUBTREE,
        "(sAMAccountName=testuser)"
    )
    print(f"Found {len(result)} users")

    conn.unbind_s()
except ldap.LDAPError as e:
    print(f"✗ LDAP error: {e}")
```

## Active Directory Group Setup

Create the following groups in your Active Directory:

1. **NetVault-Admins**
   - Full access to all NetVault features
   - Can manage users, devices, backups

2. **NetVault-Operators**
   - Can create and manage devices
   - Can run backups and restores
   - Cannot delete or manage users

3. **NetVault-Auditors**
   - Read-only access
   - Can view audit logs
   - Can download backups for compliance

4. **NetVault-Viewers**
   - Read-only access to devices and backups
   - Cannot perform any write operations

## User Login Flow

1. User enters email/username and password
2. System tries LDAP authentication first
3. If LDAP succeeds:
   - User account is created/updated in NetVault
   - User groups are fetched from AD
   - Groups are mapped to NetVault role
   - User is logged in
4. If LDAP fails, fallback to local database authentication

## LDAP Users vs Local Users

### LDAP Users
- ✓ Centralized authentication
- ✓ Password managed in AD
- ✓ Auto-synchronized on login
- ✗ Cannot change password in NetVault
- ✗ Cannot enable 2FA (use AD MFA instead)
- Identified by `is_ldap_user=True` flag

### Local Users
- ✓ Can change password in NetVault
- ✓ Can enable 2FA with TOTP
- ✓ Independent of AD
- ✗ Password managed separately

## Troubleshooting

### Enable Debug Logging

In `settings.py`:

```python
LOGGING = {
    'version': 1,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'loggers': {
        'django_auth_ldap': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

### Common Issues

**1. "Can't contact LDAP server"**
- Check firewall rules
- Verify LDAP_SERVER_URI is correct
- Test with: `telnet dc.yourdomain.com 389`

**2. "Invalid credentials"**
- Verify service account DN and password
- Check account is not locked/expired
- Ensure account has read permissions

**3. "User authenticated but no groups"**
- Check GROUP_SEARCH base DN
- Verify user is member of groups
- Check `memberOf` attribute exists

**4. "User gets wrong role"**
- Review `LDAP_ADMIN_GROUPS` / `LDAP_OPERATOR_GROUPS` / `LDAP_AUDITOR_GROUPS` in `.env`
- Matching is exact (case-insensitive) against the AD group's CN — a group name has
  to match one of these lists *exactly*, not just contain it as a substring
- Log `ldap_user.group_names` for the affected user to see exactly what NetVault received

## Security Best Practices

1. **Use LDAPS (Secure LDAP)**
   ```python
   AUTH_LDAP_SERVER_URI = "ldaps://dc.yourdomain.com:636"
   AUTH_LDAP_START_TLS = False  # Not needed with LDAPS
   ```

2. **Service Account Security**
   - Use dedicated service account
   - Grant minimum required permissions (read-only)
   - Rotate password regularly
   - Store password in environment variable:
   ```python
   import os
   AUTH_LDAP_BIND_PASSWORD = os.getenv('LDAP_BIND_PASSWORD')
   ```

3. **Network Security**
   - Restrict LDAP access to NetVault server IP
   - Use firewall rules
   - Consider VPN for remote access

## Example: Complete Working Configuration

For a company "Example Corp" with domain `example.com`:

```python
# settings.py
AUTH_LDAP_SERVER_URI = "ldaps://dc.example.com:636"
AUTH_LDAP_BIND_DN = "CN=netvault-svc,OU=Service Accounts,DC=example,DC=com"
AUTH_LDAP_BIND_PASSWORD = os.getenv('LDAP_PASSWORD')

AUTH_LDAP_USER_SEARCH = LDAPSearch(
    "OU=Employees,DC=example,DC=com",
    ldap.SCOPE_SUBTREE,
    "(sAMAccountName=%(user)s)"
)

AUTH_LDAP_GROUP_SEARCH = LDAPSearch(
    "OU=Security Groups,DC=example,DC=com",
    ldap.SCOPE_SUBTREE,
    "(objectClass=group)"
)

AUTH_LDAP_USER_ATTR_MAP = {
    "first_name": "givenName",
    "last_name": "sn",
    "email": "mail",
}

AUTHENTICATION_BACKENDS = [
    'accounts.ldap_backend.NetVaultLDAPBackend',
    'django.contrib.auth.backends.ModelBackend',
]
```

## Support

For issues with LDAP integration:
1. Check logs in `<project_root>/backend/logs/`
2. Enable DEBUG logging
3. Test connection with ldapsearch tool
4. Review this guide's troubleshooting section

## Additional Resources

- [Django Auth LDAP Documentation](https://django-auth-ldap.readthedocs.io/)
- [python-ldap Documentation](https://www.python-ldap.org/)
- [Active Directory LDAP Syntax](https://docs.microsoft.com/en-us/windows/win32/adsi/search-filter-syntax)
