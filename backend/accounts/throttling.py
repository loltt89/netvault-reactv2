"""
Custom throttling for authentication endpoints
"""
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    """
    Rate limiting for login attempts, by IP.
    Protects against brute-force password attacks.

    AnonRateThrottle-based: get_cache_key() returns None (i.e. skips
    throttling) for any *authenticated* request — by design, since it
    exists to limit attempts before a client has a session at all. Correct
    for the actual login endpoint. Do not reuse this class for an
    IsAuthenticated-only action (see TwoFactorVerifyThrottle below for why
    that's a silent no-op, not stricter throttling).
    """
    scope = 'login'


class TwoFactorVerifyThrottle(UserRateThrottle):
    """
    Rate limiting for confirming a TOTP code (verify_2fa), by user id.

    verify_2fa is only reachable by an already-authenticated request (it's
    the confirmation step of turning 2FA on), so LoginRateThrottle — an
    AnonRateThrottle — used to be applied here and silently never throttled
    anything: AnonRateThrottle.get_cache_key() returns None once
    request.user.is_authenticated is True, so every call skipped the
    counter entirely, despite the docstring claiming otherwise. A stolen
    access token could brute-force the 6-digit code (valid_window=1, ~10^6
    space) with zero rate limit. UserRateThrottle keys by user id instead
    of IP, which is also the more precise scope here: this endpoint is
    inherently per-account, so limiting by the account being targeted
    (rather than the caller's IP) is what actually bounds the attack.
    """
    scope = 'two_factor_verify'
