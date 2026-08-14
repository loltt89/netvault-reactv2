"""
WebSocket Origin validation that also honors ALLOW_PRIVATE_NETWORK_HOSTS.

channels.security.websocket.AllowedHostsOriginValidator checks a
WebSocket handshake's Origin header against settings.ALLOWED_HOSTS —
but as a literal string list, with none of the private-network handling
core/host_validation.py patches into Django's own HTTP Host-header
check. That patch only touches django.http.request.validate_host, a
function Channels' own OriginValidator never calls — it has its own,
independent implementation. The result: this self-hosted LAN
appliance's own address moving under DHCP (already happened twice) broke
regular page/API access not at all (the HTTP patch covers it) but broke
the backup-log WebSocket specifically, every time, until someone noticed
and manually added the new IP to ALLOWED_HOSTS.

This mirrors that same fix for the WebSocket layer, gated behind the
same settings.ALLOW_PRIVATE_NETWORK_HOSTS flag, using the exact same
PRIVATE_NETWORKS ranges — one flag now genuinely covers "this LAN
appliance's address can move without editing config", not just half of
it.
"""
from channels.security.websocket import OriginValidator
from django.conf import settings

from core.host_validation import is_private_or_loopback_ip


class PrivateNetworkAwareOriginValidator(OriginValidator):
    """OriginValidator that additionally accepts any Origin whose
    hostname is a private/loopback IP, when
    settings.ALLOW_PRIVATE_NETWORK_HOSTS is on — checked before falling
    back to the parent class's exact/wildcard match against
    self.allowed_origins, so a literal ALLOWED_HOSTS entry still works
    too (e.g. a real domain name, which isn't an IP at all and this
    check never matches)."""

    def valid_origin(self, parsed_origin):
        if (
            getattr(settings, 'ALLOW_PRIVATE_NETWORK_HOSTS', False)
            and parsed_origin is not None
            and parsed_origin.hostname
            and is_private_or_loopback_ip(parsed_origin.hostname)
        ):
            return True
        return super().valid_origin(parsed_origin)


def AllowedHostsOrPrivateNetworkOriginValidator(application):
    """
    Drop-in replacement for
    channels.security.websocket.AllowedHostsOriginValidator — same
    settings.ALLOWED_HOSTS/DEBUG fallback behavior, plus the private-
    network check above.
    """
    allowed_hosts = settings.ALLOWED_HOSTS
    if settings.DEBUG and not allowed_hosts:
        allowed_hosts = ["localhost", "127.0.0.1", "[::1]"]
    return PrivateNetworkAwareOriginValidator(application, allowed_hosts)
