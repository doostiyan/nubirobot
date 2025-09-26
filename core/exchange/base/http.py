import base64
from typing import Optional, Tuple

from django.http import HttpRequest
from ipware import get_client_ip as ipware_get_client_ip


def get_client_country(request) -> str:
    """Detect the Country of user based on its the information provided by the CDN.

    The CDN matches user IP against a geolocation database to find its location. Some
    CDN providers like Sotoon don't support geolocation and usually return IR as country.
    If no location header is available, XX may be returned.
    """
    country = request.headers.get('x-country-code') or request.headers.get('cf-ipcountry')
    return country.upper() if country else 'XX'


def get_client_ip(request) -> Optional[str]:
    """Detect real user IP from the request, considering proxy forwarding and trust of each.

    This method is currently a wrapper over ipware methods, but may be changed later.
    """
    ip = ipware_get_client_ip(request)
    return ip[0] if ip else None


def get_basic_auth_credentials(request: HttpRequest) -> Tuple[str, str]:
    """Extracts Basic Authentication credentials from the request headers.
    Returns a tuple containing the extracted username and password."""
    auth = request.headers.get('Authorization')
    if auth and auth.startswith('Basic '):
        try:
            credentials = base64.b64decode(auth.split()[1]).decode().split(':')
            return credentials[0], credentials[1]
        except (UnicodeDecodeError, IndexError):
            pass
    return '', ''


def get_client_country_from_ip(request) -> str:
    """Detect the Country of user based on their IP address.

    Returns: `'UN'` if country is not found
    """
    from exchange.security.models import KnownIP

    ip = get_client_ip(request)
    ip_details = KnownIP.inspect_ip(ip)
    return ip_details['country']


def is_client_iranian(request) -> bool:
    """Detect whether the client is Iranian based on CDN and IP.

    If CDN doesn't show that the client is Iranian, it also checks if the IP matches
    """
    cdn_country = get_client_country(request)
    return cdn_country == 'IR' or get_client_country_from_ip(request) == 'IR'
