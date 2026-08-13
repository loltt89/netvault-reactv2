"""
WebAuthn (passkey) registration/authentication ceremonies.

Wraps the `webauthn` (py_webauthn / SimpleWebAuthn-for-Python) library with
this app's own challenge storage and settings. Challenges are short-lived,
single-use, and must survive between two separate HTTP requests (options ->
browser ceremony -> verify) — stored in Redis directly (the same
redis.from_url(settings.REDIS_URL) pattern core.redis_lock.DeviceLock uses),
not Django's cache framework, since nothing in this codebase configures
CACHES explicitly and its implicit LocMemCache default is per-process. A
security-sensitive nonce store shouldn't silently inherit that assumption.
"""
import logging
import redis
import webauthn
from django.conf import settings
from webauthn.helpers.structs import (
    PublicKeyCredentialDescriptor,
    AuthenticatorSelectionCriteria,
    UserVerificationRequirement,
    ResidentKeyRequirement,
)
from webauthn.helpers.exceptions import InvalidRegistrationResponse, InvalidAuthenticationResponse

logger = logging.getLogger(__name__)

CHALLENGE_TTL_SECONDS = 150  # comfortably past the 60s timeout given to the browser ceremony itself

# Atomic "get value and delete key" — GETDEL only exists from Redis 6.2+,
# and this codebase's actual deployed Redis (see core/redis_lock.py's own
# use of Lua rather than assuming a newer server) can't be assumed to have
# it. A plain GET-then-DEL as two round trips has a real, if narrow, race:
# two concurrent requests reusing the same still-valid challenge could
# both read it before either deletes it, defeating "single-use".
_POP_SCRIPT = """
local v = redis.call("get", KEYS[1])
if v then
    redis.call("del", KEYS[1])
end
return v
"""


class WebAuthnError(Exception):
    """Raised for any registration/authentication failure — caught at the view layer."""
    pass


def is_configured() -> bool:
    """
    False if WEBAUTHN_RP_ID couldn't be determined (no real domain
    configured — see settings.py) — the ceremonies below would only ever
    fail in that case, so callers should check this first and respond with
    a clear "not available here" rather than a confusing verification error.
    """
    return bool(settings.WEBAUTHN_RP_ID)


def _redis_client():
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


def _challenge_key(prefix: str, user_id: int) -> str:
    return f'webauthn_challenge:{prefix}:{user_id}'


def _store_challenge(prefix: str, user_id: int, challenge: bytes):
    client = _redis_client()
    client.set(_challenge_key(prefix, user_id), webauthn.helpers.bytes_to_base64url(challenge), ex=CHALLENGE_TTL_SECONDS)


def _pop_challenge(prefix: str, user_id: int) -> bytes:
    """Atomic get-and-delete — a challenge is single-use, whether the ceremony succeeds or not."""
    client = _redis_client()
    key = _challenge_key(prefix, user_id)
    value = client.eval(_POP_SCRIPT, 1, key)
    if not value:
        raise WebAuthnError('Challenge expired or already used — please try again.')
    return webauthn.helpers.base64url_to_bytes(value)


# ---------------------------------------------------------------------------
# Registration (adding a new passkey to an already-authenticated account)
# ---------------------------------------------------------------------------

def build_registration_options(user) -> str:
    """Returns JSON (already in the shape @simplewebauthn/browser expects)."""
    if not is_configured():
        raise WebAuthnError('WebAuthn is not configured on this server (no domain configured).')

    exclude_credentials = [
        PublicKeyCredentialDescriptor(id=webauthn.helpers.base64url_to_bytes(cred.credential_id))
        for cred in user.webauthn_credentials.all()
    ]

    options = webauthn.generate_registration_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        rp_name=settings.WEBAUTHN_RP_NAME,
        user_id=str(user.id).encode(),
        user_name=user.email,
        user_display_name=user.get_full_name(),
        exclude_credentials=exclude_credentials,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )
    _store_challenge('reg', user.id, options.challenge)
    return webauthn.options_to_json(options)


def complete_registration(user, credential_json, name: str):
    """Verifies the browser's attestation response and stores a new WebAuthnCredential."""
    from .models import WebAuthnCredential

    if not is_configured():
        raise WebAuthnError('WebAuthn is not configured on this server (no domain configured).')

    expected_challenge = _pop_challenge('reg', user.id)

    try:
        verified = webauthn.verify_registration_response(
            credential=credential_json,
            expected_challenge=expected_challenge,
            expected_rp_id=settings.WEBAUTHN_RP_ID,
            expected_origin=settings.WEBAUTHN_ORIGINS,
        )
    except InvalidRegistrationResponse as e:
        raise WebAuthnError(f'Passkey registration failed: {e}')

    credential_id_b64 = webauthn.helpers.bytes_to_base64url(verified.credential_id)
    if WebAuthnCredential.objects.filter(credential_id=credential_id_b64).exists():
        raise WebAuthnError('This passkey is already registered.')

    return WebAuthnCredential.objects.create(
        user=user,
        name=(name or '').strip()[:100] or 'Passkey',
        credential_id=credential_id_b64,
        public_key=webauthn.helpers.bytes_to_base64url(verified.credential_public_key),
        sign_count=verified.sign_count,
        transports=[],
    )


# ---------------------------------------------------------------------------
# Authentication (login — second factor)
# ---------------------------------------------------------------------------

def build_authentication_options(user) -> str:
    """
    Returns JSON for navigator.credentials.get(), scoped to this user's
    already-registered credentials (allow_credentials) — this only ever
    runs after the password has already been verified (see
    CustomTokenObtainPairSerializer), so there's no separate unauthenticated
    "who are you" probe to worry about enumerating.
    """
    if not is_configured():
        raise WebAuthnError('WebAuthn is not configured on this server (no domain configured).')

    allow_credentials = [
        PublicKeyCredentialDescriptor(id=webauthn.helpers.base64url_to_bytes(cred.credential_id))
        for cred in user.webauthn_credentials.all()
    ]
    if not allow_credentials:
        raise WebAuthnError('No passkeys registered for this account.')

    options = webauthn.generate_authentication_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        allow_credentials=allow_credentials,
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    _store_challenge('auth', user.id, options.challenge)
    return webauthn.options_to_json(options)


def verify_authentication(user, credential_json):
    """Verifies a signed assertion against a previously-registered credential. Raises WebAuthnError on failure."""
    from django.utils import timezone
    from .models import WebAuthnCredential

    if not is_configured():
        raise WebAuthnError('WebAuthn is not configured on this server (no domain configured).')

    expected_challenge = _pop_challenge('auth', user.id)

    # credential_json carries the credential's own ID (base64url) — look it
    # up among *this user's* credentials specifically, not any credential
    # in the whole table, so one user's assertion can never be checked
    # against a different user's stored public key.
    try:
        raw_id = webauthn.helpers.parse_authentication_credential_json(credential_json).raw_id
    except Exception as e:
        raise WebAuthnError(f'Malformed passkey response: {e}')

    credential_id_b64 = webauthn.helpers.bytes_to_base64url(raw_id)
    try:
        stored = user.webauthn_credentials.get(credential_id=credential_id_b64)
    except WebAuthnCredential.DoesNotExist:
        raise WebAuthnError('Unrecognized passkey for this account.')

    try:
        verified = webauthn.verify_authentication_response(
            credential=credential_json,
            expected_challenge=expected_challenge,
            expected_rp_id=settings.WEBAUTHN_RP_ID,
            expected_origin=settings.WEBAUTHN_ORIGINS,
            credential_public_key=webauthn.helpers.base64url_to_bytes(stored.public_key),
            credential_current_sign_count=stored.sign_count,
        )
    except InvalidAuthenticationResponse as e:
        raise WebAuthnError(f'Passkey verification failed: {e}')

    stored.sign_count = verified.new_sign_count
    stored.last_used_at = timezone.now()
    stored.save(update_fields=['sign_count', 'last_used_at'])
    return True
