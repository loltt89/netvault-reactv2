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
- **Protection**: Brute force password attacks
- **Implementation**:
  - Login endpoint: 5 attempts per hour per IP
  - Anonymous users: 10 requests per hour
  - Authenticated users: 1000 requests per hour
- **Configuration**: `backend/accounts/throttling.py`

### 3. Role-Based Access Control (RBAC)
- **Protection**: Privilege escalation
- **Implementation**:
  - Self-registration forced to 'viewer' role
  - Only administrators can create users with elevated roles
  - Endpoint-level permission checks
- **Configuration**: `backend/accounts/serializers.py`

### 4. Public Registration Control
- **Protection**: Unauthorized account creation
- **Default**: Disabled (`ALLOW_PUBLIC_REGISTRATION=False`)
- **Configuration**: `.env` file, enforced in `backend/accounts/views.py`

## Network Security

### 5. CORS (Cross-Origin Resource Sharing)
- **Protection**: Unauthorized cross-origin access
- **Implementation**:
  - CORS_ALLOW_ALL_ORIGINS = False
  - Explicit whitelist for allowed origins
  - Regex patterns for private IP ranges (192.168.x.x, 10.x.x.x, 172.16-31.x.x)
- **Configuration**: `backend/netvault/settings.py`

### 6. HTTPS Support with HSTS
- **Protection**: Man-in-the-middle attacks, protocol downgrade
- **Implementation**:
  - USE_HTTPS flag in .env
  - Secure cookies (SESSION_COOKIE_SECURE, CSRF_COOKIE_SECURE)
  - HSTS headers (1 year max-age)
  - Nginx handles HTTP→HTTPS redirect
- **Configuration**: `.env` (USE_HTTPS), `backend/netvault/settings.py`

### 7. Admin Panel IP Whitelist
- **Protection**: Unauthorized access to Django admin panel
- **Implementation**:
  - Nginx-level IP restriction for `/admin/` endpoint
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

## Application Security

### 8. SSRF (Server-Side Request Forgery) Prevention
- **Protection**: Internal network scanning, DNS rebinding
- **Implementation**:
  - DNS resolution before loopback check
  - Block connections to loopback addresses (127.0.0.1, ::1)
  - Validate all user-supplied hostnames/IPs
- **Configuration**: `backend/devices/connection.py`

### 9. RCE (Remote Code Execution) Prevention
- **Protection**: Code injection via custom commands
- **Implementation**:
  - Only administrators can set `custom_commands` field
  - Operators cannot modify command execution logic
- **Configuration**: `backend/devices/serializers.py`

### 10. CSV Injection Prevention
- **Protection**: Formula injection in Excel (=, +, -, @)
- **Implementation**:
  - Sanitize CSV values at serializer level
  - Sanitize CSV values in bulk import (csv_import)
  - Prepend single quote to suspicious values
- **Configuration**: `backend/devices/serializers.py`, `backend/devices/views.py`

### 11. Information Disclosure Prevention
- **Protection**: Stack trace exposure in production
- **Implementation**:
  - DEBUG=False in production
  - Errors logged to file instead of response
  - Generic error messages to users
- **Configuration**: `.env` (DEBUG), `backend/netvault/settings.py`

### 12. File Upload Limits
- **Protection**: Denial of Service via large files
- **Implementation**:
  - CSV uploads limited to 5MB
  - Nginx client_max_body_size: 100MB
- **Configuration**: `backend/devices/views.py`, `/etc/nginx/sites-available/netvault`

## Data Security

### 13. Device Credential Encryption
- **Protection**: Credential theft from database
- **Implementation**:
  - Fernet symmetric encryption for device passwords
  - Encryption key stored in .env (separate from database)
- **Configuration**: `.env` (ENCRYPTION_KEY)

### 14. Database Security
- **Protection**: SQL injection, unauthorized access
- **Implementation**:
  - Django ORM (parameterized queries)
  - MariaDB with dedicated user (no root access)
  - Password authentication required
- **Configuration**: `.env` (DB_USER, DB_PASSWORD)

### 15. Redis Security
- **Protection**: Unauthorized cache/queue access
- **Implementation**:
  - Password authentication (generated during install)
  - Bind to localhost only (127.0.0.1)
  - Protected mode disabled (password used instead)
- **Configuration**: `/etc/redis/redis.conf`, `.env` (REDIS_URL)

## Session Security

### 16. JWT Token Blacklisting
- **Protection**: Token reuse after logout
- **Implementation**:
  - Refresh tokens blacklisted on logout
  - Token rotation enabled (new refresh token on access token refresh)
- **Configuration**: `backend/netvault/settings.py` (SIMPLE_JWT)

### 17. Token Expiration
- **Protection**: Long-lived session hijacking
- **Implementation**:
  - Access token: 60 minutes (configurable)
  - Refresh token: 24 hours (configurable)
- **Configuration**: `.env` (JWT_ACCESS_TOKEN_LIFETIME, JWT_REFRESH_TOKEN_LIFETIME)

## Audit & Monitoring

### 18. Audit Logging
- **Protection**: Forensics, compliance
- **Implementation**:
  - All user actions logged (login, logout, CRUD operations)
  - IP address and user agent captured
  - Read-only audit log viewset
- **Configuration**: `backend/accounts/models.py` (AuditLog)

### 19. SSH Host Key Logging
- **Protection**: SSH MITM detection
- **Implementation**:
  - First-time host keys logged to file
  - Admins can review for anomalies
- **Configuration**: `backend/devices/connection.py`

### 20. Security Headers
- **Protection**: Clickjacking, XSS, MIME sniffing
- **Implementation**:
  - X-Frame-Options: SAMEORIGIN
  - X-Content-Type-Options: nosniff
  - X-XSS-Protection: 1; mode=block
- **Configuration**: `/etc/nginx/sites-available/netvault`

## Configuration Checklist

### Production Deployment
- [ ] Set strong SECRET_KEY and ENCRYPTION_KEY
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
- [ ] Review audit logs regularly

### Regular Maintenance
- [ ] Update dependencies (security patches)
- [ ] Rotate encryption keys periodically
- [ ] Review and clean up old audit logs
- [ ] Monitor failed login attempts
- [ ] Review SSH host key logs
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
