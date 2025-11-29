from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
import pyotp


class UserManager(BaseUserManager):
    """Custom user manager"""

    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular user"""
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a superuser"""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'administrator')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom user model"""

    ROLE_CHOICES = (
        ('administrator', 'Administrator'),
        ('operator', 'Operator'),
        ('viewer', 'Viewer'),
        ('auditor', 'Auditor'),
    )

    email = models.EmailField(unique=True, db_index=True)
    username = models.CharField(max_length=150, unique=True, db_index=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='viewer')

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    # 2FA fields
    two_factor_enabled = models.BooleanField(default=False)
    two_factor_secret = models.CharField(max_length=32, blank=True)

    # LDAP integration
    is_ldap_user = models.BooleanField(default=False)
    ldap_dn = models.CharField(max_length=255, blank=True)

    # SAML SSO integration
    is_saml_user = models.BooleanField(default=False)
    saml_name_id = models.CharField(max_length=255, blank=True)

    # Timestamps
    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(null=True, blank=True)
    last_password_change = models.DateTimeField(default=timezone.now)

    # Settings
    preferred_language = models.CharField(max_length=10, default='en', choices=[
        ('en', 'English'),
        ('ru', 'Russian'),
        ('kk', 'Kazakh'),
    ])
    theme = models.CharField(max_length=20, default='light', choices=[
        ('light', 'Light'),
        ('dark_blue', 'Dark Blue'),
        ('teal_light', 'Teal Light'),
        ('deep_dark', 'Deep Dark'),
    ])

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-date_joined']
        indexes = [
            models.Index(fields=['role']),  # For filtering by role
            models.Index(fields=['is_active', 'role']),  # For filtering active users by role
            models.Index(fields=['-date_joined']),  # For sorting by join date
        ]

    def __str__(self):
        return self.email

    def get_full_name(self):
        """Return the first_name plus the last_name, with a space in between."""
        full_name = f'{self.first_name} {self.last_name}'
        return full_name.strip() or self.email

    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name or self.email

    def generate_2fa_secret(self):
        """Generate a new 2FA secret"""
        self.two_factor_secret = pyotp.random_base32()
        self.save()
        return self.two_factor_secret

    def get_2fa_uri(self):
        """Get the provisioning URI for 2FA QR code"""
        if not self.two_factor_secret:
            self.generate_2fa_secret()
        return pyotp.totp.TOTP(self.two_factor_secret).provisioning_uri(
            name=self.email,
            issuer_name='NetVault'
        )

    def verify_2fa_token(self, token):
        """Verify a 2FA token (90-second window for clock skew tolerance)"""
        if not self.two_factor_enabled or not self.two_factor_secret:
            return False
        totp = pyotp.TOTP(self.two_factor_secret)
        # valid_window=1 allows ±30 seconds (industry standard for clock skew)
        return totp.verify(token, valid_window=1)


class AuditLog(models.Model):
    """Audit log for tracking user actions"""

    ACTION_CHOICES = (
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('backup', 'Backup'),
        ('restore', 'Restore'),
        ('download', 'Download'),
        ('view', 'View'),
    )

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    resource_type = models.CharField(max_length=50)  # Device, Backup, User, etc.
    resource_id = models.IntegerField(null=True, blank=True)
    resource_name = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)

    class Meta:
        db_table = 'audit_logs'
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['resource_type', 'resource_id']),
            models.Index(fields=['action', '-timestamp']),  # For filtering by action type
            models.Index(fields=['success', '-timestamp']),  # For filtering failed/successful actions
        ]

    def __str__(self):
        return f'{self.user} - {self.action} - {self.resource_type} - {self.timestamp}'


class SAMLSettings(models.Model):
    """SAML SSO Configuration - Singleton model"""

    # General settings
    enabled = models.BooleanField(default=False)

    # Service Provider (SP) settings
    sp_entity_id = models.CharField(
        max_length=255,
        blank=True,
        help_text='Unique identifier for NetVault SP (e.g., https://netvault.example.com/saml/metadata/)'
    )

    # Identity Provider (IdP) settings
    idp_entity_id = models.CharField(
        max_length=255,
        blank=True,
        help_text='Entity ID of the Identity Provider'
    )
    idp_sso_url = models.URLField(
        max_length=500,
        blank=True,
        help_text='IdP Single Sign-On URL'
    )
    idp_slo_url = models.URLField(
        max_length=500,
        blank=True,
        help_text='IdP Single Logout URL (optional)'
    )
    idp_x509_cert = models.TextField(
        blank=True,
        help_text='IdP X.509 certificate (PEM format)'
    )

    # Attribute mapping
    attr_username = models.CharField(
        max_length=100,
        default='http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name',
        help_text='SAML attribute for username'
    )
    attr_email = models.CharField(
        max_length=100,
        default='http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress',
        help_text='SAML attribute for email'
    )
    attr_first_name = models.CharField(
        max_length=100,
        default='http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname',
        blank=True,
        help_text='SAML attribute for first name'
    )
    attr_last_name = models.CharField(
        max_length=100,
        default='http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname',
        blank=True,
        help_text='SAML attribute for last name'
    )

    # User provisioning
    auto_create_users = models.BooleanField(
        default=True,
        help_text='Automatically create users on first SAML login'
    )
    default_role = models.CharField(
        max_length=20,
        choices=User.ROLE_CHOICES,
        default='viewer',
        help_text='Default role for auto-created users'
    )

    # Security settings
    want_assertions_signed = models.BooleanField(default=True)
    want_messages_signed = models.BooleanField(default=False)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'saml_settings'
        verbose_name = 'SAML Settings'
        verbose_name_plural = 'SAML Settings'

    def __str__(self):
        return f'SAML Settings ({"Enabled" if self.enabled else "Disabled"})'

    def save(self, *args, **kwargs):
        # Ensure only one instance exists (singleton)
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        """Get or create SAML settings singleton"""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
