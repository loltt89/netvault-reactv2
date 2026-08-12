import logging
from django.middleware.csrf import get_token
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from .models import User, AuditLog
from .throttling import LoginRateThrottle, TwoFactorVerifyThrottle

logger = logging.getLogger(__name__)
from .permissions import CanManageUsers, CanViewAuditLogs
from .serializers import (
    CustomTokenObtainPairSerializer, UserSerializer, UserCreateSerializer,
    UserUpdateSerializer, ChangePasswordSerializer, Enable2FASerializer,
    Verify2FASerializer, Disable2FASerializer, AuditLogSerializer
)


def set_jwt_cookies(response, request, access_token=None, refresh_token=None):
    """
    Helper function to set JWT tokens as HttpOnly cookies (DRY principle)

    Args:
        response: Django Response object
        request: Django Request object
        access_token: Access token string (optional)
        refresh_token: Refresh token string (optional)
    """
    if access_token:
        # Forces Django's CsrfViewMiddleware to include a fresh, JS-readable
        # `csrftoken` cookie on this response — nothing else in this API
        # ever triggers that (there are no server-rendered templates using
        # {% csrf_token %}), so without this call the cookie-authenticated
        # requests CookieJWTAuthentication.enforce_csrf() now requires a
        # valid CSRF token for would have no way to ever obtain one.
        get_token(request)
        response.set_cookie(
            'access_token',
            access_token,
            httponly=True,
            secure=request.is_secure(),
            samesite='Lax',
            max_age=60 * 60,  # 1 hour
            path='/',
        )
    if refresh_token:
        response.set_cookie(
            'refresh_token',
            refresh_token,
            httponly=True,
            secure=request.is_secure(),
            samesite='Lax',
            max_age=24 * 60 * 60,  # 24 hours
            path='/',
        )


class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom JWT token obtain view with 2FA support and rate limiting"""

    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [LoginRateThrottle]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)

        if response.status_code == 200:
            # Set tokens as HttpOnly cookies for XSS protection
            set_jwt_cookies(
                response,
                request,
                access_token=response.data.get('access'),
                refresh_token=response.data.get('refresh')
            )
            # The refresh token now lives only in the HttpOnly cookie.
            # Returning it in the JSON body too was redundant exposure —
            # readable by any script with access to the response (a
            # network tab, an APM tool that logs response bodies, an XSS
            # that only needs to read fetch results, not cookies) for a
            # value the frontend never actually persists anyway.
            response.data.pop('refresh', None)

        return response


class CookieTokenRefreshView(TokenRefreshView):
    """Token refresh view that reads from HttpOnly cookie"""

    def post(self, request, *args, **kwargs):
        # Try to get refresh token from cookie first
        refresh_token = request.COOKIES.get('refresh_token')

        if refresh_token:
            # Inject into request data. request.data is only a QueryDict
            # (immutable by default, needs the _mutable toggle) for
            # multipart/form bodies — for a JSON body, which is what
            # axios sends by default and so is what the real frontend
            # actually uses for this call, DRF's JSONParser hands back a
            # plain (already-mutable) dict that has no `_mutable`
            # attribute at all. Blindly setting it unconditionally raised
            # AttributeError on every real refresh call.
            if hasattr(request.data, '_mutable'):
                request.data._mutable = True
                request.data['refresh'] = refresh_token
                request.data._mutable = False
            else:
                request.data['refresh'] = refresh_token

        try:
            response = super().post(request, *args, **kwargs)

            if response.status_code == 200:
                # ROTATE_REFRESH_TOKENS=True means every refresh issues a
                # brand new refresh token and — because
                # BLACKLIST_AFTER_ROTATION=True — blacklists the one that
                # was just used. This used to only refresh the access_token
                # cookie; the refresh_token cookie was never updated with
                # the new value, so it kept holding the now-blacklisted
                # token. The *next* refresh attempt would then present that
                # blacklisted token, get rejected, and force a full
                # re-login — every session was silently killed exactly one
                # ACCESS_TOKEN_LIFETIME after its first refresh, regardless
                # of the much longer REFRESH_TOKEN_LIFETIME. Found while
                # checking whether the refresh token still needed to be in
                # the JSON body at all.
                set_jwt_cookies(
                    response,
                    request,
                    access_token=response.data.get('access'),
                    refresh_token=response.data.get('refresh'),
                )
                # Same reasoning as CustomTokenObtainPairView: the cookie
                # is authoritative now, don't also hand the (rotated)
                # refresh token to JS.
                response.data.pop('refresh', None)

            return response
        except (InvalidToken, TokenError) as e:
            # Clear cookies on invalid refresh token
            response = Response({'detail': 'Token is invalid or expired'}, status=status.HTTP_401_UNAUTHORIZED)
            response.delete_cookie('access_token')
            response.delete_cookie('refresh_token')
            return response


class AuthViewSet(viewsets.GenericViewSet):
    """Authentication viewset"""

    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=['post'])
    def register(self, request):
        """Register a new user (only if ALLOW_PUBLIC_REGISTRATION=True)"""
        from django.conf import settings

        if not settings.ALLOW_PUBLIC_REGISTRATION:
            return Response(
                {'detail': 'Public registration is disabled. Contact administrator.'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Generate tokens for the new user
        refresh = RefreshToken.for_user(user)

        # Log audit
        AuditLog.objects.create(
            user=user,
            action='create',
            resource_type='User',
            resource_id=user.id,
            resource_name=user.email,
            description='User registered',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )

        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        # refresh_token is intentionally not in the body — it only goes into
        # the HttpOnly cookie below (see CustomTokenObtainPairView for why).
        response = Response({
            'user': UserSerializer(user).data,
            'access': access_token,
        }, status=status.HTTP_201_CREATED)

        # Set HttpOnly cookies for XSS protection
        set_jwt_cookies(response, request, access_token=access_token, refresh_token=refresh_token)

        return response

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def logout(self, request):
        """Logout user"""
        try:
            # Try to get refresh token from cookie first, then from body
            refresh_token = request.COOKIES.get('refresh_token') or request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()

            # Log audit
            AuditLog.objects.create(
                user=request.user,
                action='logout',
                resource_type='User',
                resource_id=request.user.id,
                resource_name=request.user.email,
                description='User logged out',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
            )

            response = Response({'detail': 'Successfully logged out'}, status=status.HTTP_200_OK)
            # Clear cookies
            response.delete_cookie('access_token')
            response.delete_cookie('refresh_token')
            return response
        except Exception as e:
            logger.error(f"Logout error: {e}")
            return Response({'detail': 'Logout failed'}, status=status.HTTP_400_BAD_REQUEST)


class UserViewSet(viewsets.ModelViewSet):
    """User management viewset"""

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, CanManageUsers]

    def get_queryset(self):
        """Filter users based on role"""
        user = self.request.user

        # Administrators can see all users
        if user.role == 'administrator':
            return User.objects.all()

        # Others can only see themselves
        return User.objects.filter(id=user.id)

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        return UserSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        # Allow admins to set role when creating users
        if self.request.user.is_authenticated and self.request.user.role == 'administrator':
            context['is_admin_request'] = True
        return context

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user profile"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['patch'])
    def update_profile(self, request):
        """Update current user profile"""
        serializer = UserUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Log audit
        AuditLog.objects.create(
            user=request.user,
            action='update',
            resource_type='User',
            resource_id=request.user.id,
            resource_name=request.user.email,
            description='User updated profile',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )

        return Response(UserSerializer(request.user).data)

    @action(detail=False, methods=['post'])
    def change_password(self, request):
        """Change user password"""
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()

        # Log audit
        AuditLog.objects.create(
            user=user,
            action='update',
            resource_type='User',
            resource_id=user.id,
            resource_name=user.email,
            description='User changed password',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )

        return Response({'detail': 'Password changed successfully'})

    @action(detail=False, methods=['post'])
    def enable_2fa(self, request):
        """Enable 2FA for current user"""
        serializer = Enable2FASerializer(data={}, context={'request': request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()

        return Response(result)

    @action(detail=False, methods=['post'], throttle_classes=[TwoFactorVerifyThrottle])
    def verify_2fa(self, request):
        """Verify and activate 2FA (rate limited to prevent brute force)"""
        serializer = Verify2FASerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Log audit
        AuditLog.objects.create(
            user=user,
            action='update',
            resource_type='User',
            resource_id=user.id,
            resource_name=user.email,
            description='User enabled 2FA',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )

        return Response({'detail': '2FA enabled successfully'})

    @action(detail=False, methods=['post'])
    def disable_2fa(self, request):
        """Disable 2FA for current user"""
        serializer = Disable2FASerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Log audit
        AuditLog.objects.create(
            user=user,
            action='update',
            resource_type='User',
            resource_id=user.id,
            resource_name=user.email,
            description='User disabled 2FA',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )

        return Response({'detail': '2FA disabled successfully'})


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Audit log viewset (read-only)"""

    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated, CanViewAuditLogs]

    def get_queryset(self):
        """Filter audit logs based on role"""
        user = self.request.user

        # Administrators and auditors can see all logs
        if user.role in ['administrator', 'auditor']:
            return AuditLog.objects.all()

        # Others can only see their own logs
        return AuditLog.objects.filter(user=user)
