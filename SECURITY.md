# NetVault Security Features

This document describes the security measures implemented in NetVault.

## Authentication & Authorization

### 1. JWT Token Security (HttpOnly Cookies)
- **Protection**: XSS (Cross-Site Scripting) attacks
- **Implementation**:
  - Refresh tokens stored in HttpOnly cookies (JavaScript cannot access)
  - Access tokens kept in memory (lost on page refresh, auto-refreshed)
  - Secure flag enabled for HTTPS (cookies only sent over secure connections)
  - SameSite=Lax to prevent CSRF attacks

### 2. Rate Limiting (Brute Force Protection)
- **Protection**: Brute force password / 2FA-code attacks
- **Implementation**:
  - Login endpoint: 200 attempts per hour per IP (`LoginRateThrottle`)
  - 2FA code confirmation (`verify_2fa`): 10 attempts per hour **per user**
    (`TwoFactorVerifyThrottle`) — deliberately keyed by user id, not IP:
    this endpoint is only reachable by an already-authenticated request, so
    an IP-based anonymous throttle would silently never apply to it
  - Anonymous users (general API): 10,000 requests per hour
  - Authenticated users (general API): 100,000 requests per hour
- **Configuration**: `backend/accounts/throttling.py`, `DEFAULT_THROTTLE_RATES` in `backend/netvault/settings.py`

### 3. Password Policy Enforcement
- **Protection**: Weak/guessable passwords
- **Implementation**:
  - `AUTH_PASSWORD_VALIDATORS` (minimum length, common-password list,
    not-entirely-numeric, similarity to username/email) enforced on both
    registration and password change via Django's `validate_password()`
- **Configuration**: `AUTH_PASSWORD_VALIDATORS` in `backend/netvault/settings.py`,
  enforced in `backend/accounts/serializers.py` (`UserCreateSerializer`,
  `ChangePasswordSerializer`)

### 4. Role-Based Access Control (RBAC)
- **Protection**: Privilege escalation
- **Implementation**:
  - Self-registration forced to 'viewer' role
  - Only administrators can create users with elevated roles
  - Endpoint-level permission checks
- **Configuration**: `backend/accounts/serializers.py`, `backend/accounts/permissions.py`

### 5. SAML SSO — Account-Link Protection
- **Protection**: Account takeover via a spoofed/asserted email or username
- **Implementation**:
  - A fresh SAML login is matched to an existing account by email/username
    only when that account has no usable local password (SAML-provisioned,
    or deliberately passwordless) — an IdP-asserted attribute alone is
    never trusted to attach to a password-protected account
  - Returning users are matched by their stable `saml_name_id`, not by
    whatever attributes a given assertion happens to carry
  - Attaching SAML to an existing password-protected account requires the
    account owner to be logged in locally first and request the link
    explicitly (`SAMLLinkInitView`), via a short-lived signed token
- **Configuration**: `backend/accounts/saml_views.py`

### 6. LDAP/AD Group-to-Role Mapping (Exact Match)
- **Protection**: Privilege escalation via incidental AD group naming
- **Implementation**:
  - Group names are matched exactly (case-insensitive) against
    `LDAP_ADMIN_GROUPS` / `LDAP_OPERATOR_GROUPS` / `LDAP_AUDITOR_GROUPS` —
    never by substring, so a group merely *containing* a privileged name
    (e.g. "IT-Administrators-Helpdesk") cannot grant that role
- **Configuration**: `LDAP_ADMIN_GROUPS` / `LDAP_OPERATOR_GROUPS` /
  `LDAP_AUDITOR_GROUPS` in `.env`, enforced in `backend/accounts/ldap_backend.py`

### 7. Public Registration Control
- **Protection**: Unauthorized account creation
- **Default**: Disabled (`ALLOW_PUBLIC_REGISTRATION=False`)
- **Configuration**: `.env` file, enforced in `backend/accounts/views.py`

## Network Security

### 8. CORS (Cross-Origin Resource Sharing)
- **Protection**: Unauthorized cross-origin access
- **Implementation**:
  - CORS_ALLOW_ALL_ORIGINS = False
  - Explicit whitelist for allowed origins
  - Regex patterns for private IP ranges (192.168.x.x, 10.x.x.x, 172.16-31.x.x)
- **Configuration**: `backend/netvault/settings.py`

### 9. HTTPS Support with HSTS
- **Protection**: Man-in-the-middle attacks, protocol downgrade
- **Implementation**:
  - USE_HTTPS flag in .env
  - Secure cookies (SESSION_COOKIE_SECURE, CSRF_COOKIE_SECURE)
  - HSTS headers (1 year max-age)
  - Nginx handles HTTP→HTTPS redirect
- **Configuration**: `.env` (USE_HTTPS), `backend/netvault/settings.py`

### 10. Admin Panel IP Whitelist
- **Protection**: Unauthorized access to Django admin panel
- **Implementation**:
  - Nginx-level IP restriction for `/admin/` (and `/flower/`) endpoints
  - Configured during installation
  - Only whitelisted IPs can access admin panel
- **Configuration**: `/etc/nginx/sites-available/netvault`
- **Modification**: Edit Nginx config, add/remove `allow <IP>;` directives, then `nginx -t && systemctl reload nginx`

Example Nginx configuration:
```nginx
location /admin/ {
    allow 192.168.1.100;
    allow 10.0.0.5;
    deny all;

    proxy_pass http://127.0.0.1:8000;
    # ... proxy headers ...
}
```

### 11. SSH Host Key Pinning (TOFU)
- **Protection**: SSH man-in-the-middle attacks against managed devices
- **Implementation**:
  - Trust-On-First-Use: a device's SSH host key is pinned on its first
    successful connection (`ssh_host_key_type` / `ssh_host_key_fingerprint`)
  - Any later connection presenting a *different* key is refused outright
    (`HostKeyMismatchError`) — no silent fallback, no auto-update — and
    recorded as a pending change plus a notification
  - Only an administrator can resolve a pending mismatch, after verifying
    the new fingerprint out-of-band (device console, not over the network),
    via explicit approve/reject actions
  - Known gap: this only covers the Paramiko connection path. The
    `netvault-ssh` binary fallback (legacy/SSHv1 devices) does not
    currently verify host keys of its own.
- **Configuration**: `backend/devices/connection.py` (`PinnedHostKeyPolicy`),
  `backend/devices/models.py` (`Device.approve_ssh_host_key` /
  `reject_ssh_host_key`)

## Application Security

### 12. SSRF (Server-Side Request Forgery) Prevention
- **Protection**: Internal network scanning, cloud metadata exfiltration, DNS rebinding
- **Implementation**:
  - DNS resolved to a numeric IP once, then validated and connected to by
    that IP — the hostname is never re-resolved, which is what prevents
    DNS-rebinding TOCTOU
  - Loopback, link-local (includes the 169.254.169.254 cloud metadata
    range on AWS/GCP/Azure/OCI), multicast, unspecified, and reserved
    addresses are rejected unconditionally, regardless of any other
    configuration
  - General private ranges (RFC1918 etc.) are allowed by default — this
    product's job is connecting to devices on private LANs — and can be
    further scoped down per deployment via `ALLOWED_PRIVATE_NETWORKS`
  - The same check runs twice: at device creation (immediate form error)
    and at connection time (the actual enforcement point), and on both the
    JSON/API device-create path and CSV import
- **Configuration**: `ALLOWED_PRIVATE_NETWORKS` in `.env`, enforced in
  `backend/devices/connection.py` (`validate_target_host`, `_never_a_device`)

### 13. RCE (Remote Code Execution) Prevention
- **Protection**: Code injection via device/vendor backup commands
- **Implementation**:
  - Every command field involved in a backup run — `backup`, `setup[]`,
    `logout[]`, and `exec_wrapper` — is checked against a character
    whitelist and a blacklist of destructive operations (`reload`,
    `erase`, `format`, `copy running`, etc.) before it can be saved
  - `Device.custom_commands` is additionally admin-only at the field level
    (an operator's write to it is silently dropped)
  - `Vendor.backup_commands` has no such admin gate — any operator can set
    it — so the whitelist/blacklist validation above is the actual
    protection for that path, not a role restriction
- **Configuration**: `backend/devices/serializers.py`
  (`validate_backup_commands`, `_validate_command`)

### 14. CSV Injection Prevention
- **Protection**: Formula injection in Excel (=, +, -, @)
- **Implementation**:
  - Text fields are validated as CSV-safe at write time — on the JSON/API
    device create/update path, and identically on CSV bulk import
    (both the create and update-existing branches)
  - Values are sanitized (single-quote prefix) separately at CSV *export*
    time; the database itself always stores the raw value
- **Configuration**: `backend/core/utils.py` (`validate_csv_safe`,
  `sanitize_csv_value`), `backend/devices/serializers.py`, `backend/devices/views.py`

### 15. Information Disclosure Prevention
- **Protection**: Stack trace exposure in production
- **Implementation**:
  - DEBUG=False in production
  - Errors logged to file instead of response
  - Generic error messages to users
- **Configuration**: `.env` (DEBUG), `backend/netvault/settings.py`

### 16. File Upload Limits
- **Protection**: Denial of Service via large files
- **Implementation**:
  - CSV uploads limited to 5MB
  - Nginx client_max_body_size: 100MB
- **Configuration**: `backend/devices/views.py`, `/etc/nginx/sites-available/netvault`

## Data Security

### 17. Device Credential Encryption
- **Protection**: Credential theft from database
- **Implementation**:
  - Fernet symmetric encryption for device passwords
  - Encryption key stored in .env (separate from database)
- **Configuration**: `.env` (ENCRYPTION_KEY)

### 18. Database Security
- **Protection**: SQL injection, unauthorized access
- **Implementation**:
  - Django ORM (parameterized queries)
  - MariaDB with dedicated user (no root access)
  - Password authentication required
- **Configuration**: `.env` (DB_USER, DB_PASSWORD)

### 19. Redis Security
- **Protection**: Unauthorized cache/queue access
- **Implementation**:
  - Password authentication (generated during install)
  - Bind to localhost only (127.0.0.1)
  - Protected mode disabled (password used instead)
- **Configuration**: `/etc/redis/redis.conf`, `.env` (REDIS_URL)

## Session Security

### 20. JWT Signing Key Isolation
- **Protection**: Blast-radius containment if a secret leaks
- **Implementation**:
  - JWTs are signed with `JWT_SIGNING_KEY`, a value distinct from
    `SECRET_KEY` — which also signs Django sessions, CSRF tokens, and
    password-reset tokens. A leak of one no longer lets an attacker forge
    the other.
  - Falls back to `SECRET_KEY` only if `JWT_SIGNING_KEY` is left unset, for
    backward compatibility — set it explicitly
  - Rotating `JWT_SIGNING_KEY` invalidates every outstanding access/refresh
    token (forces re-login), same operational caveat as rotating
    `SECRET_KEY` today, just now scoped to auth tokens only
- **Configuration**: `.env` (`JWT_SIGNING_KEY`), `backend/netvault/settings.py`

### 21. JWT Token Blacklisting
- **Protection**: Token reuse after logout
- **Implementation**:
  - Refresh tokens blacklisted on logout
  - Token rotation enabled (new refresh token on access token refresh)
- **Configuration**: `backend/netvault/settings.py` (SIMPLE_JWT)

### 22. Token Expiration
- **Protection**: Long-lived session hijacking
- **Implementation**:
  - Access token: 60 minutes (configurable)
  - Refresh token: 24 hours (configurable)
- **Configuration**: `.env` (JWT_ACCESS_TOKEN_LIFETIME, JWT_REFRESH_TOKEN_LIFETIME)

## Audit & Monitoring

### 23. Audit Logging
- **Protection**: Forensics, compliance
- **Implementation**:
  - All user actions logged (login, logout, CRUD operations, SSH host key
    approve/reject, retention policy application)
  - IP address and user agent captured
  - Read-only audit log viewset
- **Configuration**: `backend/accounts/models.py` (AuditLog)

### 24. Security Headers
- **Protection**: Clickjacking, XSS, MIME sniffing
- **Implementation**:
  - X-Frame-Options: SAMEORIGIN
  - X-Content-Type-Options: nosniff
  - X-XSS-Protection: 1; mode=block
- **Configuration**: `/etc/nginx/sites-available/netvault`

## Configuration Checklist

### Production Deployment
- [ ] Set strong, distinct SECRET_KEY, JWT_SIGNING_KEY, and ENCRYPTION_KEY
- [ ] DEBUG=False
- [ ] ALLOW_PUBLIC_REGISTRATION=False
- [ ] USE_HTTPS=True (if using HTTPS)
- [ ] Configure ALLOWED_HOSTS and CORS_ALLOWED_ORIGINS
- [ ] Set up admin panel IP whitelist
- [ ] Configure rate limiting (adjust if needed)
- [ ] Review JWT token lifetimes
- [ ] Set up email notifications for critical events
- [ ] Enable and configure Redis password
- [ ] Use strong database password
- [ ] If enabling LDAP, set LDAP_ADMIN_GROUPS/LDAP_OPERATOR_GROUPS/LDAP_AUDITOR_GROUPS to your actual AD group names
- [ ] Review audit logs regularly

### Regular Maintenance
- [ ] Update dependencies (security patches)
- [ ] Rotate encryption keys periodically
- [ ] Review and clean up old audit logs
- [ ] Monitor failed login attempts
- [ ] Review pending SSH host key changes (device detail page) promptly
- [ ] Test backup/restore procedures
- [ ] Verify HTTPS certificate renewal (Let's Encrypt)

## Security Best Practices

1. **Least Privilege**: Assign minimum required role to users (viewer by default)
2. **Network Segmentation**: Restrict admin panel to trusted networks
3. **Monitoring**: Enable Telegram/email notifications for backup failures
4. **Updates**: Keep system packages and Python dependencies updated
5. **Backups**: Regularly test backup restoration procedures
6. **Secrets Management**: Never commit .env file to version control
7. **Access Review**: Periodically review user accounts and permissions

## Reporting Security Issues

If you discover a security vulnerability, please report it to the administrator immediately. Do not disclose publicly until a fix is available.

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Django Security](https://docs.djangoproject.com/en/stable/topics/security/)
- [REST Framework Security](https://www.django-rest-framework.org/topics/security/)
