from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CompliancePolicyViewSet, ComplianceViolationViewSet

router = DefaultRouter()
router.register(r'policies', CompliancePolicyViewSet, basename='compliancepolicy')
router.register(r'violations', ComplianceViolationViewSet, basename='complianceviolation')

urlpatterns = [
    path('', include(router.urls)),
]
