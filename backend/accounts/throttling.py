"""
Custom throttling for authentication endpoints
"""
from rest_framework.throttling import AnonRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    """
    Strict rate limiting for login attempts (5 per hour per IP)
    Protects against brute-force password attacks
    """
    scope = 'login'
