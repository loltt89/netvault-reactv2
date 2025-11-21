from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import VendorViewSet, DeviceTypeViewSet, DeviceViewSet

router = DefaultRouter()
router.register(r'vendors', VendorViewSet, basename='vendor')
router.register(r'device-types', DeviceTypeViewSet, basename='devicetype')
router.register(r'devices', DeviceViewSet, basename='device')

urlpatterns = [
    path('', include(router.urls)),
]
