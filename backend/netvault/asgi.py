"""
ASGI config for netvault project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter

# Import our routing configuration
from backups.routing import websocket_urlpatterns
from backups.middleware import JWTAuthMiddleware
from core.asgi_validators import AllowedHostsOrPrivateNetworkOriginValidator

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netvault.settings')

# Initialize Django ASGI application early to ensure models are loaded
django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    # Not channels' own AllowedHostsOriginValidator — see
    # core/asgi_validators.py for why (it doesn't know about
    # ALLOW_PRIVATE_NETWORK_HOSTS, which the HTTP layer already honors).
    "websocket": AllowedHostsOrPrivateNetworkOriginValidator(
        JWTAuthMiddleware(
            URLRouter(
                websocket_urlpatterns
            )
        )
    ),
})
