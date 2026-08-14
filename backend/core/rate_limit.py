"""
Lightweight rate limiting for endpoints that fall outside DRF's throttle
framework entirely.

accounts/saml_views.py's SAMLLoginView/SAMLACSView/SAMLSLSView are plain
Django `View` subclasses (not DRF APIView/ViewSet) — DRF's
DEFAULT_THROTTLE_CLASSES (settings.REST_FRAMEWORK), including the
generous-but-present blanket 'anon' scope everything else gets, never
applies to them at all, since they never go through DRF's dispatch
machinery. SAMLACSView in particular does real work per request (parsing
and cryptographically verifying an external XML SAML assertion) while
being reachable by anyone, unauthenticated — a natural target with
currently zero request-rate defense.

Deliberately reuses Django's cache framework (the same one DRF's own
AnonRateThrottle/UserRateThrottle read/write) rather than a separate
Redis client, so this behaves identically to the rest of the app's
throttling under whatever CACHES backend is configured, and needs no
extra test setup — test_settings.py's LocMemCache already "just works"
here the same way it does for the DRF throttles, with no live Redis
dependency (this app's REDIS_URL, when pointed at a real Redis requiring
auth, is otherwise a known source of environment-specific test failures
completely unrelated to this module).
"""
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)


def check_rate_limit(key: str, limit: int, window_seconds: int) -> bool:
    """
    Fixed-window rate limit check.

    Returns True (and counts this call toward the window) if the caller
    is still within `limit` calls per `window_seconds` for this key;
    False if they've already reached it — the caller should reject the
    request rather than retry.

    Fails open (returns True, request proceeds) on any cache backend
    error. An unavailable or misconfigured cache degrading this to "no
    rate limiting" is the right failure mode: the endpoints calling this
    have their own independent defenses (SAML signature verification,
    etc.) that don't depend on this check passing, and a cache outage
    should not be able to take down SSO login entirely.
    """
    try:
        count = cache.get(key)
        if count is None:
            cache.set(key, 1, timeout=window_seconds)
            return True
        if count >= limit:
            return False
        try:
            cache.incr(key)
        except ValueError:
            # Key expired between the get() and incr() above (race with
            # the window boundary) — safe to treat as a fresh window
            # rather than fail the check.
            cache.set(key, 1, timeout=window_seconds)
        return True
    except Exception as e:
        logger.warning(f"Rate limit check failed for key={key!r}, failing open: {e}")
        return True
