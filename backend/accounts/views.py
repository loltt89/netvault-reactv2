import logging
from django.middleware.csrf import get_token
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from .models import User, AuditLog, WebAuthnCredential
from .throttling import LoginRateThrottle, RegisterRateThrottle, TwoFactorVerifyThrottle
from . import webauthn_service

logger = logging.getLogger(__name__)
from .permissions import CanManageUsers, CanViewAuditLogs, IsAdministrator
from .serializers import (
    CustomTokenObtainPairSerializer, UserSerializer, UserCreateSerializer,
    UserUpdateSerializer, AdminUserUpdateSerializer, ChangePasswordSerializer,
    Enable2FASerializer, Verify2FASerializer, Disable2FASerializer,
    AuditLogSerializer, WebAuthnCredentialSerializer
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
        # "You need a second factor and haven't supplied one yet" is
        # handled here, before the normal serializer-validation flow,
        # specifically so the response body can carry real JSON types.
        # CustomTokenObtainPairSerializer.validate() raising a
        # ValidationError with this same payload would silently mangle it:
        # DRF's ValidationError stringifies every value in a raised dict
        # (see _get_error_details), turning totp_available=False into the
        # *string* "False" once rendered — truthy in both Python and JS,
        # making the field useless for telling the frontend which methods
        # are actually available.
        email = request.data.get('email')
        password = request.data.get('password')
        if email and password and not request.data.get('two_factor_token') and not request.data.get('webauthn_response'):
            from django.contrib.auth import authenticate
            user = authenticate(username=email, password=password)
            if user and user.is_active and user.has_second_factor:
                payload = {
                    'two_factor_required': True,
                    'message': '2FA token is required',
                    'totp_available': user.two_factor_enabled,
                }
                if user.webauthn_credentials.exists():
                    try:
                        payload['webauthn_options'] = webauthn_service.build_authentication_options(user)
                    except webauthn_service.WebAuthnError:
                        pass  # TOTP-only fallback if options couldn't be built
                return Response(payload, status=status.HTTP_400_BAD_REQUEST)

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

    @action(detail=False, methods=['post'], throttle_classes=[RegisterRateThrottle])
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
            # Admin-only path (CanManageUsers gates 'update'/'partial_update' to
            # administrators) — see AdminUserUpdateSerializer's docstring for why
            # this must NOT be the self-service UserUpdateSerializer used by
            # update_profile.
            return AdminUserUpdateSerializer
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

    @action(detail=True, methods=['patch'], permission_classes=[permissions.IsAuthenticated, IsAdministrator])
    def set_device_scope(self, request, pk=None):
        """
        Restrict (or unrestrict) which devices a non-administrator user
        can see/act on, via the same {"tags": [...], "criticality": [...],
        ...} shape as NotificationRule.device_filters — see
        core.device_filters. Deliberately a separate admin-only action
        rather than a writable field on the normal update path: nothing
        else lets a user touch their own permissions, and device_scope
        shouldn't be the exception.

        Request body: {"device_scope": {"tags": ["core"]}} — pass {} to
        clear the restriction (unrestricted access, subject to role).
        """
        target_user = self.get_object()
        scope = request.data.get('device_scope')

        if not isinstance(scope, dict):
            return Response(
                {'detail': 'device_scope must be an object, e.g. {"tags": ["core"]} or {} to clear it.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target_user.device_scope = scope
        target_user.save(update_fields=['device_scope'])

        AuditLog.objects.create(
            user=request.user,
            action='update',
            resource_type='User',
            resource_id=target_user.id,
            resource_name=target_user.email,
            description=f'Set device_scope for {target_user.email}: {scope!r}',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )
        logger.info(f"device_scope for {target_user.email} set by {request.user.email}: {scope!r}")

        return Response(UserSerializer(target_user).data)

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

    @action(detail=False, methods=['post'])
    def webauthn_register_begin(self, request):
        """
        Start registering a new passkey for the current user. Returns
        options JSON for the frontend to feed straight into
        @simplewebauthn/browser's startRegistration().
        """
        try:
            options = webauthn_service.build_registration_options(request.user)
        except webauthn_service.WebAuthnError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'options': options})

    @action(detail=False, methods=['post'])
    def webauthn_register_complete(self, request):
        """
        Finish passkey registration. Body: {"credential": <attestation
        response from startRegistration()>, "name": "<label>"}.
        """
        credential = request.data.get('credential')
        name = request.data.get('name', '')
        if not credential:
            return Response({'detail': 'credential is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            cred = webauthn_service.complete_registration(request.user, credential, name)
        except webauthn_service.WebAuthnError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        AuditLog.objects.create(
            user=request.user,
            action='update',
            resource_type='User',
            resource_id=request.user.id,
            resource_name=request.user.email,
            description=f'Registered passkey: {cred.name}',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )
        logger.info(f"Passkey '{cred.name}' registered for {request.user.email}")

        return Response(WebAuthnCredentialSerializer(cred).data, status=status.HTTP_201_CREATED)


class WebAuthnCredentialViewSet(viewsets.ModelViewSet):
    """
    Manage the current user's own registered passkeys — list and delete
    only (registration itself is a two-step ceremony, handled by
    UserViewSet.webauthn_register_begin/complete above, not plain create).
    """
    serializer_class = WebAuthnCredentialSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'delete']

    def get_queryset(self):
        return WebAuthnCredential.objects.filter(user=self.request.user)

    def perform_destroy(self, instance):
        name = instance.name
        instance.delete()
        AuditLog.objects.create(
            user=self.request.user,
            action='update',
            resource_type='User',
            resource_id=self.request.user.id,
            resource_name=self.request.user.email,
            description=f'Removed passkey: {name}',
            ip_address=self.request.META.get('REMOTE_ADDR'),
            user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
        )
        logger.info(f"Passkey '{name}' removed for {self.request.user.email}")


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Audit log viewset (read-only)"""

    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated, CanViewAuditLogs]
    # SearchFilter is active project-wide (DEFAULT_FILTER_BACKENDS) — this
    # is all that was ever needed to make AuditLogsPage.tsx's search box
    # work; unlike action/resource_type/success/user below, it needed no
    # manual get_queryset() handling, just this declaration.
    search_fields = ['resource_name', 'description', 'user__email']

    def get_queryset(self):
        """Filter audit logs based on role, then by AuditLogsPage.tsx's filter bar"""
        user = self.request.user

        # Administrators and auditors can see all logs
        if user.role in ['administrator', 'auditor']:
            queryset = AuditLog.objects.all()
        else:
            # Others can only see their own logs
            queryset = AuditLog.objects.filter(user=user)

        # action/resource_type/success/user were declared as query params
        # AuditLogsPage.tsx's filter bar sends, but never actually
        # enforced anywhere — there's no DjangoFilterBackend installed in
        # this project (only SearchFilter/OrderingFilter are active) to
        # give a filterset_fields-style declaration any effect, and this
        # ViewSet never had manual handling for any of them. Every filter
        # selection silently returned the same unfiltered (role-scoped)
        # list.
        action_param = self.request.query_params.get('action', None)
        if action_param:
            queryset = queryset.filter(action=action_param)

        resource_type_param = self.request.query_params.get('resource_type', None)
        if resource_type_param:
            queryset = queryset.filter(resource_type=resource_type_param)

        success_param = self.request.query_params.get('success', None)
        if success_param:
            queryset = queryset.filter(success=success_param.lower() == 'true')

        user_param = self.request.query_params.get('user', None)
        if user_param:
            queryset = queryset.filter(user_id=user_param)

        return queryset
