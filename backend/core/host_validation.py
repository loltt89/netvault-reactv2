"""
Lets Django's ALLOWED_HOSTS check also accept any RFC1918 private IP or
loopback address as a valid Host header, on top of the explicit
ALLOWED_HOSTS entries from .env.

This is a self-hosted LAN appliance whose own address moves under DHCP
(already happened once — 192.168.8.124 -> .125), and re-editing
ALLOWED_HOSTS by hand every time it does isn't sustainable. Gated behind
settings.ALLOW_PRIVATE_NETWORK_HOSTS (default off, same opt-in shape as
CORS_ALLOW_PRIVATE_NETWORKS in settings.py — meant to be turned on
together with it).

ALLOWED_HOSTS exists to stop Host-header poisoning of cache keys,
password-reset links, and other absolute URLs built from
request.get_host(). Trusting "any Host header claiming a private IP"
narrows that protection to "an attacker must already be on the LAN",
which is judged an acceptable trade-off for this specific deployment —
not something to default on for everyone installing this app.

Patches django.http.request.validate_host once, at app startup (see
core/apps.py). That's the single choke point HttpRequest.get_host() —
and therefore CommonMiddleware and everything else that calls it — goes
through, so this covers all of them without touching each call site.
"""
import ipaddress

from django.http import request as django_request

_original_validate_host = django_request.validate_host

_PRIVATE_NETWORKS = [
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('127.0.0.0/8'),
]


def _validate_host_allow_private_networks(host, allowed_hosts):
    # By the time validate_host() is called, get_host() has already run
    # split_domain_port() on the raw header — host here is lowercased,
    # stripped of :port, and stripped of a trailing dot. Still strip a
    # bracketed IPv6 literal defensively; ip_address() doesn't accept them.
    try:
        ip = ipaddress.ip_address(host.strip('[]'))
    except ValueError:
        ip = None
    if ip is not None and any(ip in network for network in _PRIVATE_NETWORKS):
        return True
    return _original_validate_host(host, allowed_hosts)


def patch():
    django_request.validate_host = _validate_host_allow_private_networks
