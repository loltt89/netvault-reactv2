from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CustomTokenObtainPairView, CookieTokenRefreshView, AuthViewSet, UserViewSet, AuditLogViewSet
from .saml_views import (
    SAMLMetadataView, SAMLLoginView, SAMLACSView, SAMLSLSView,
    SAMLSettingsAPIView, SAMLStatusView
)

router = DefaultRouter()
router.register(r'auth', AuthViewSet, basename='auth')
router.register(r'users', UserViewSet, basename='users')
router.register(r'audit-logs', AuditLogViewSet, basename='audit-logs')

urlpatterns = [
    # JWT token endpoints
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', CookieTokenRefreshView.as_view(), name='token_refresh'),

    # SAML 2.0 SSO endpoints
    path('saml/metadata/', SAMLMetadataView.as_view(), name='saml_metadata'),
    path('saml/login/', SAMLLoginView.as_view(), name='saml_login'),
    path('saml/acs/', SAMLACSView.as_view(), name='saml_acs'),
    path('saml/sls/', SAMLSLSView.as_view(), name='saml_sls'),
    path('saml/settings/', SAMLSettingsAPIView.as_view(), name='saml_settings'),
    path('saml/status/', SAMLStatusView.as_view(), name='saml_status'),

    # Router URLs
    path('', include(router.urls)),
]
