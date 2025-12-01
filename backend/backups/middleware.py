"""
Custom JWT Authentication Middleware for WebSocket connections.
"""

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from urllib.parse import parse_qs


@database_sync_to_async
def get_user_from_token(token_string):
    """
    Validate JWT token and return the associated user.
    """
    from django.contrib.auth.models import AnonymousUser
    from django.contrib.auth import get_user_model
    from rest_framework_simplejwt.tokens import AccessToken

    try:
        # Validate and decode the JWT token
        access_token = AccessToken(token_string)
        user_id = access_token['user_id']

        # Fetch user from database
        User = get_user_model()
        user = User.objects.get(id=user_id)
        return user
    except Exception:
        # Invalid token or user not found
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """
    Custom middleware that authenticates WebSocket connections using JWT tokens.
    Token is sent via cookie (access_token) for security, with fallback to query parameter.
    """

    async def __call__(self, scope, receive, send):
        from django.contrib.auth.models import AnonymousUser

        token = None

        # 1. Try to get token from cookie header (preferred method)
        headers = dict(scope.get('headers', []))
        cookie_header = headers.get(b'cookie', b'').decode()

        if cookie_header:
            # Parse cookies from header
            cookies = {}
            for cookie_str in cookie_header.split(';'):
                cookie_str = cookie_str.strip()
                if '=' in cookie_str:
                    key, value = cookie_str.split('=', 1)
                    cookies[key.strip()] = value.strip()

            token = cookies.get('access_token')

        # 2. Fallback to query string for backward compatibility
        if not token:
            query_string = scope.get('query_string', b'').decode()
            query_params = parse_qs(query_string)
            token = query_params.get('token', [None])[0]

        # Authenticate user with the token
        if token:
            scope['user'] = await get_user_from_token(token)
        else:
            scope['user'] = AnonymousUser()

        return await super().__call__(scope, receive, send)
