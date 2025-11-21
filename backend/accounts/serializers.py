from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate
from .models import User, AuditLog
import pyotp
import qrcode
import io
import base64


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom JWT token serializer with 2FA support"""

    two_factor_token = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        # Get credentials
        email = attrs.get('email')
        password = attrs.get('password')
        two_factor_token = attrs.get('two_factor_token', '')

        # Authenticate user
        user = authenticate(username=email, password=password)

        if not user:
            raise serializers.ValidationError('Invalid credentials')

        if not user.is_active:
            raise serializers.ValidationError('User account is disabled')

        # Check 2FA if enabled
        if user.two_factor_enabled:
            if not two_factor_token:
                raise serializers.ValidationError({
                    'two_factor_required': True,
                    'message': '2FA token is required'
                })

            if not user.verify_2fa_token(two_factor_token):
                raise serializers.ValidationError('Invalid 2FA token')

        # Generate tokens
        refresh = self.get_token(user)

        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserSerializer(user).data
        }

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Add custom claims
        token['email'] = user.email
        token['role'] = user.role
        token['username'] = user.username

        return token


class UserSerializer(serializers.ModelSerializer):
    """User serializer"""

    full_name = serializers.CharField(source='get_full_name', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name', 'full_name',
            'role', 'is_active', 'two_factor_enabled', 'is_ldap_user',
            'date_joined', 'last_login', 'preferred_language', 'theme'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login', 'is_ldap_user']


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new users"""

    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    password_confirm = serializers.CharField(write_only=True, required=False, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = [
            'email', 'username', 'first_name', 'last_name', 'password',
            'password_confirm', 'role', 'is_active', 'preferred_language', 'theme'
        ]

    def validate(self, attrs):
        # Only check password_confirm if it's provided
        if 'password_confirm' in attrs and attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password': 'Passwords do not match'})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm', None)
        password = validated_data.pop('password')
        # Force viewer role on self-registration to prevent privilege escalation
        # Only admins can set role via UserViewSet
        if not self.context.get('is_admin_request'):
            validated_data['role'] = 'viewer'
        user = User.objects.create_user(password=password, **validated_data)
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile"""

    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'preferred_language', 'theme'
        ]


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for password change"""

    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True)
    new_password_confirm = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({'new_password': 'Passwords do not match'})
        return attrs

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Old password is incorrect')
        return value


class Enable2FASerializer(serializers.Serializer):
    """Serializer for enabling 2FA"""

    def create(self, validated_data):
        user = self.context['request'].user
        secret = user.generate_2fa_secret()

        # Generate QR code
        uri = user.get_2fa_uri()
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(uri)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()

        return {
            'secret': secret,
            'qr_code': f'data:image/png;base64,{qr_code_base64}',
            'uri': uri
        }


class Verify2FASerializer(serializers.Serializer):
    """Serializer for verifying and activating 2FA"""

    token = serializers.CharField(required=True, max_length=6, min_length=6)

    def validate_token(self, value):
        user = self.context['request'].user

        if not user.two_factor_secret:
            raise serializers.ValidationError('2FA secret not found. Please enable 2FA first.')

        totp = pyotp.TOTP(user.two_factor_secret)
        if not totp.verify(value, valid_window=1):
            raise serializers.ValidationError('Invalid 2FA token')

        return value

    def save(self):
        user = self.context['request'].user
        user.two_factor_enabled = True
        user.save()
        return user


class Disable2FASerializer(serializers.Serializer):
    """Serializer for disabling 2FA"""

    password = serializers.CharField(required=True, write_only=True)

    def validate_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Password is incorrect')
        return value

    def save(self):
        user = self.context['request'].user
        user.two_factor_enabled = False
        user.two_factor_secret = ''
        user.save()
        return user


class AuditLogSerializer(serializers.ModelSerializer):
    """Audit log serializer"""

    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id', 'user', 'user_email', 'action', 'resource_type',
            'resource_id', 'resource_name', 'description', 'ip_address',
            'user_agent', 'timestamp', 'success', 'error_message'
        ]
        read_only_fields = ['id', 'timestamp']
