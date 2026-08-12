"""
Custom JWT Authentication that supports HttpOnly cookies.
"""
from rest_framework import exceptions
from rest_framework.authentication import CSRFCheck
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken


class CookieJWTAuthentication(JWTAuthentication):
    """
    JWT Authentication that reads token from:
    1. Authorization header (standard)
    2. HttpOnly cookie (fallback for XSS protection)
    """

    def authenticate(self, request):
        # First try the standard header authentication. A bearer token in
        # an Authorization header can't be attached by a browser
        # automatically the way a cookie can — a cross-site page has no way
        # to read or set it — so this path is already immune to CSRF and
        # doesn't need the check below.
        header = self.get_header(request)
        if header is not None:
            raw_token = self.get_raw_token(header)
            if raw_token is not None:
                validated_token = self.get_validated_token(raw_token)
                return self.get_user(validated_token), validated_token

        # Fallback to cookie. Unlike the header path, this one *is* the
        # thing CSRF protects against: a cookie rides along with any
        # request the browser makes to this origin, cross-site or not.
        # DRF's APIView marks every view csrf_exempt at the Django-
        # middleware level (its own CSRF handling only ever covers
        # SessionAuthentication), so without this, cookie-authenticated
        # state-changing requests had no CSRF check at all — SameSite=Lax
        # on the cookie was the only thing standing in the way, not a
        # second, independent layer. Enforcing it only for the cookie path
        # (not above) is deliberate: the check requires a CSRF token that a
        # pure API client using nothing but Bearer auth would never send.
        raw_token = request.COOKIES.get('access_token')
        if raw_token is not None:
            try:
                validated_token = self.get_validated_token(raw_token.encode())
            except InvalidToken:
                return None
            self.enforce_csrf(request)
            return self.get_user(validated_token), validated_token

        return None

    def enforce_csrf(self, request):
        """Same pattern DRF's own SessionAuthentication uses internally."""
        def dummy_get_response(request):  # pragma: no cover
            return None

        check = CSRFCheck(dummy_get_response)
        check.process_request(request)
        reason = check.process_view(request, None, (), {})
        if reason:
            raise exceptions.PermissionDenied('CSRF Failed: %s' % reason)
