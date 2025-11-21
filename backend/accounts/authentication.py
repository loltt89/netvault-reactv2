"""
Custom JWT Authentication that supports HttpOnly cookies.
"""
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken


class CookieJWTAuthentication(JWTAuthentication):
    """
    JWT Authentication that reads token from:
    1. Authorization header (standard)
    2. HttpOnly cookie (fallback for XSS protection)
    """

    def authenticate(self, request):
        # First try the standard header authentication
        header = self.get_header(request)
        if header is not None:
            raw_token = self.get_raw_token(header)
            if raw_token is not None:
                validated_token = self.get_validated_token(raw_token)
                return self.get_user(validated_token), validated_token

        # Fallback to cookie
        raw_token = request.COOKIES.get('access_token')
        if raw_token is not None:
            try:
                validated_token = self.get_validated_token(raw_token.encode())
                return self.get_user(validated_token), validated_token
            except InvalidToken:
                return None

        return None
