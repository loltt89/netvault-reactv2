"""
SAML 2.0 SSO Views for NetVault
"""
import json
import logging
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, SAMLSettings

logger = logging.getLogger(__name__)


def get_saml_settings(request):
    """Build SAML settings dict from database configuration"""
    saml_config = SAMLSettings.get_settings()

    if not saml_config.enabled:
        return None

    # Build base URL from request
    scheme = 'https' if request.is_secure() else 'http'
    host = request.get_host()
    base_url = f"{scheme}://{host}"

    # SP Entity ID - use configured or generate from base URL
    sp_entity_id = saml_config.sp_entity_id or f"{base_url}/api/v1/saml/metadata/"

    saml_settings = {
        "strict": True,
        "debug": settings.DEBUG,
        "sp": {
            "entityId": sp_entity_id,
            "assertionConsumerService": {
                "url": f"{base_url}/api/v1/saml/acs/",
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
            },
            "singleLogoutService": {
                "url": f"{base_url}/api/v1/saml/sls/",
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
            },
            "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
        },
        "idp": {
            "entityId": saml_config.idp_entity_id,
            "singleSignOnService": {
                "url": saml_config.idp_sso_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
            },
            "singleLogoutService": {
                "url": saml_config.idp_slo_url or "",
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
            },
            "x509cert": saml_config.idp_x509_cert.replace("-----BEGIN CERTIFICATE-----", "").replace("-----END CERTIFICATE-----", "").replace("\n", "").strip(),
        },
        "security": {
            "wantAssertionsSigned": saml_config.want_assertions_signed,
            "wantMessagesSigned": saml_config.want_messages_signed,
            "authnRequestsSigned": False,
            "logoutRequestSigned": False,
            "logoutResponseSigned": False,
            "signMetadata": False,
            "wantNameId": True,
            "wantAttributeStatement": True,
        }
    }

    return saml_settings


def prepare_saml_request(request):
    """Prepare request data for OneLogin SAML toolkit"""
    return {
        'https': 'on' if request.is_secure() else 'off',
        'http_host': request.get_host(),
        'script_name': request.path,
        'get_data': request.GET.copy(),
        'post_data': request.POST.copy(),
    }


class SAMLMetadataView(View):
    """Return SP metadata XML"""

    def get(self, request):
        try:
            from onelogin.saml2.metadata import OneLogin_Saml2_Metadata
            from onelogin.saml2.settings import OneLogin_Saml2_Settings

            saml_settings = get_saml_settings(request)
            if not saml_settings:
                return HttpResponse("SAML is not configured", status=503)

            saml2_settings = OneLogin_Saml2_Settings(saml_settings, sp_validation_only=True)
            metadata = saml2_settings.get_sp_metadata()
            errors = saml2_settings.validate_metadata(metadata)

            if errors:
                logger.error(f"SAML metadata errors: {errors}")
                return HttpResponse(f"Metadata errors: {', '.join(errors)}", status=500)

            return HttpResponse(metadata, content_type='application/xml')

        except ImportError:
            return HttpResponse("python3-saml not installed", status=503)
        except Exception as e:
            # Use logger.error instead of logger.exception to avoid logging SAML config in traceback
            logger.error(f"Error generating SAML metadata: {str(e)}")
            return HttpResponse(f"Error: {str(e)}", status=500)


class SAMLLoginView(View):
    """Initiate SAML SSO login"""

    def get(self, request):
        try:
            from onelogin.saml2.auth import OneLogin_Saml2_Auth

            saml_settings = get_saml_settings(request)
            if not saml_settings:
                return HttpResponse("SAML is not enabled", status=503)

            req = prepare_saml_request(request)
            auth = OneLogin_Saml2_Auth(req, saml_settings)

            # Get return URL from query param or default to dashboard
            return_to = request.GET.get('next', '/')

            # Redirect to IdP
            sso_url = auth.login(return_to=return_to)
            return HttpResponseRedirect(sso_url)

        except ImportError:
            return HttpResponse("python3-saml not installed", status=503)
        except Exception as e:
            logger.error(f"Error initiating SAML login: {str(e)}")
            return HttpResponse(f"Error: {str(e)}", status=500)


@method_decorator(csrf_exempt, name='dispatch')
class SAMLACSView(View):
    """Assertion Consumer Service - process SAML response"""

    def post(self, request):
        try:
            from onelogin.saml2.auth import OneLogin_Saml2_Auth

            saml_settings = get_saml_settings(request)
            if not saml_settings:
                return HttpResponse("SAML is not enabled", status=503)

            saml_config = SAMLSettings.get_settings()
            req = prepare_saml_request(request)
            auth = OneLogin_Saml2_Auth(req, saml_settings)

            auth.process_response()
            errors = auth.get_errors()

            if errors:
                error_reason = auth.get_last_error_reason()
                logger.error(f"SAML ACS errors: {errors}, reason: {error_reason}")
                return HttpResponseRedirect(f'/login?error=saml_error&message={error_reason}')

            if not auth.is_authenticated():
                logger.warning("SAML: User not authenticated")
                return HttpResponseRedirect('/login?error=not_authenticated')

            # Get user attributes
            attributes = auth.get_attributes()
            name_id = auth.get_nameid()

            logger.info(f"SAML login: NameID={name_id}, attributes={attributes}")

            # Extract user info from attributes
            username = self._get_attribute(attributes, saml_config.attr_username, name_id)
            email = self._get_attribute(attributes, saml_config.attr_email, name_id)
            first_name = self._get_attribute(attributes, saml_config.attr_first_name, '')
            last_name = self._get_attribute(attributes, saml_config.attr_last_name, '')

            # Find or create user
            user = self._get_or_create_user(
                saml_config, username, email, first_name, last_name, name_id
            )

            if not user:
                return HttpResponseRedirect('/login?error=user_creation_failed')

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)
            refresh_token = str(refresh)

            # Update last login
            from django.utils import timezone
            user.last_login = timezone.now()
            user.save(update_fields=['last_login'])

            # Redirect to frontend with tokens
            # Frontend will store these and redirect to dashboard
            redirect_url = f'/sso-callback?access={access_token}&refresh={refresh_token}'

            response = HttpResponseRedirect(redirect_url)
            # Set HttpOnly cookies for XSS protection
            response.set_cookie(
                'access_token', access_token,
                httponly=True, secure=request.is_secure(),
                samesite='Lax', max_age=60 * 60,
                path='/',
            )
            response.set_cookie(
                'refresh_token', refresh_token,
                httponly=True, secure=request.is_secure(),
                samesite='Lax', max_age=24 * 60 * 60,
                path='/',
            )
            return response

        except ImportError:
            return HttpResponse("python3-saml not installed", status=503)
        except Exception as e:
            logger.error(f"Error processing SAML response: {str(e)}")
            return HttpResponseRedirect(f'/login?error=saml_error&message={str(e)}')

    def _get_attribute(self, attributes, attr_name, default=''):
        """Get attribute value from SAML attributes"""
        if not attr_name:
            return default
        value = attributes.get(attr_name, [default])
        return value[0] if isinstance(value, list) and value else default

    def _get_or_create_user(self, saml_config, username, email, first_name, last_name, name_id):
        """Get existing user or create new one"""
        try:
            # Try to find by email first
            user = User.objects.filter(email=email).first()

            if not user:
                # Try by username
                user = User.objects.filter(username=username).first()

            if not user:
                # Try by SAML name ID
                user = User.objects.filter(saml_name_id=name_id).first()

            if user:
                # Update SAML info
                user.is_saml_user = True
                user.saml_name_id = name_id
                if first_name:
                    user.first_name = first_name
                if last_name:
                    user.last_name = last_name
                user.save()
                return user

            # Create new user if auto-create is enabled
            if not saml_config.auto_create_users:
                logger.warning(f"SAML: User not found and auto-create disabled: {email}")
                return None

            # Generate unique username if needed
            base_username = username or email.split('@')[0]
            final_username = base_username
            counter = 1
            while User.objects.filter(username=final_username).exists():
                final_username = f"{base_username}{counter}"
                counter += 1

            user = User.objects.create(
                email=email,
                username=final_username,
                first_name=first_name,
                last_name=last_name,
                role=saml_config.default_role,
                is_saml_user=True,
                saml_name_id=name_id,
                is_active=True,
            )
            user.set_unusable_password()  # SAML users don't have local passwords
            user.save()

            logger.info(f"SAML: Created new user: {email}")
            return user

        except Exception as e:
            logger.error(f"Error getting/creating SAML user: {str(e)}")
            return None


@method_decorator(csrf_exempt, name='dispatch')
class SAMLSLSView(View):
    """Single Logout Service - process logout request/response"""

    def get(self, request):
        return self._process_logout(request)

    def post(self, request):
        return self._process_logout(request)

    def _process_logout(self, request):
        try:
            from onelogin.saml2.auth import OneLogin_Saml2_Auth

            saml_settings = get_saml_settings(request)
            if not saml_settings:
                return HttpResponseRedirect('/login')

            req = prepare_saml_request(request)
            auth = OneLogin_Saml2_Auth(req, saml_settings)

            url = auth.process_slo(delete_session_cb=lambda: None)
            errors = auth.get_errors()

            if errors:
                logger.error(f"SAML SLS errors: {errors}")

            if url:
                return HttpResponseRedirect(url)

            return HttpResponseRedirect('/login?logout=success')

        except Exception as e:
            logger.error(f"Error processing SAML logout: {str(e)}")
            return HttpResponseRedirect('/login')


class SAMLSettingsAPIView(APIView):
    """API for managing SAML settings"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get current SAML settings"""
        # Check if user is admin
        if request.user.role != 'administrator':
            return Response({'detail': 'Admin access required'}, status=403)

        config = SAMLSettings.get_settings()

        # Build SP metadata URL
        scheme = 'https' if request.is_secure() else 'http'
        host = request.get_host()
        base_url = f"{scheme}://{host}"

        return Response({
            'enabled': config.enabled,
            'sp_entity_id': config.sp_entity_id or f"{base_url}/api/v1/saml/metadata/",
            'sp_acs_url': f"{base_url}/api/v1/saml/acs/",
            'sp_sls_url': f"{base_url}/api/v1/saml/sls/",
            'sp_metadata_url': f"{base_url}/api/v1/saml/metadata/",
            'idp_entity_id': config.idp_entity_id,
            'idp_sso_url': config.idp_sso_url,
            'idp_slo_url': config.idp_slo_url,
            'idp_x509_cert': config.idp_x509_cert,
            'attr_username': config.attr_username,
            'attr_email': config.attr_email,
            'attr_first_name': config.attr_first_name,
            'attr_last_name': config.attr_last_name,
            'auto_create_users': config.auto_create_users,
            'default_role': config.default_role,
            'want_assertions_signed': config.want_assertions_signed,
            'want_messages_signed': config.want_messages_signed,
        })

    def post(self, request):
        """Update SAML settings"""
        # Check if user is admin
        if request.user.role != 'administrator':
            return Response({'detail': 'Admin access required'}, status=403)

        config = SAMLSettings.get_settings()
        data = request.data

        # Update fields
        if 'enabled' in data:
            config.enabled = data['enabled']
        if 'sp_entity_id' in data:
            config.sp_entity_id = data['sp_entity_id']
        if 'idp_entity_id' in data:
            config.idp_entity_id = data['idp_entity_id']
        if 'idp_sso_url' in data:
            config.idp_sso_url = data['idp_sso_url']
        if 'idp_slo_url' in data:
            config.idp_slo_url = data['idp_slo_url']
        if 'idp_x509_cert' in data:
            config.idp_x509_cert = data['idp_x509_cert']
        if 'attr_username' in data:
            config.attr_username = data['attr_username']
        if 'attr_email' in data:
            config.attr_email = data['attr_email']
        if 'attr_first_name' in data:
            config.attr_first_name = data['attr_first_name']
        if 'attr_last_name' in data:
            config.attr_last_name = data['attr_last_name']
        if 'auto_create_users' in data:
            config.auto_create_users = data['auto_create_users']
        if 'default_role' in data:
            config.default_role = data['default_role']
        if 'want_assertions_signed' in data:
            config.want_assertions_signed = data['want_assertions_signed']
        if 'want_messages_signed' in data:
            config.want_messages_signed = data['want_messages_signed']

        config.save()

        return Response({'success': True, 'message': 'SAML settings updated'})


class SAMLStatusView(APIView):
    """Public endpoint to check if SAML is enabled"""
    permission_classes = [AllowAny]

    def get(self, request):
        config = SAMLSettings.get_settings()
        return Response({
            'enabled': config.enabled,
            'login_url': '/api/v1/saml/login/' if config.enabled else None,
        })
