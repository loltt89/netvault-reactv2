from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NotificationRuleViewSet, NotificationViewSet

router = DefaultRouter()
router.register(r'rules', NotificationRuleViewSet, basename='notificationrule')
router.register(r'log', NotificationViewSet, basename='notification')

urlpatterns = [
    path('', include(router.urls)),
]
