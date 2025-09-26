import http.client as http_client
import json

from google.auth import exceptions

GOOGLE_OAUTH2_CERTS_CACHE_KEY = 'google_oauth2_certs'
GOOGLE_OAUTH2_CERTS_TTL = 24 * 3600


def _fetch_google_oauth2_certs(request, certs_url):
    """Fetches certificates.

    Google-style cerificate endpoints return JSON in the format of
    ``{'key id': 'x509 certificate'}`` or a certificate array according
    to the JWK spec (see https://tools.ietf.org/html/rfc7517).

    Args:
        request (google.auth.transport.Request): The object used to make
            HTTP requests.
        certs_url (str): The certificate endpoint URL.

    Returns:
        Mapping[str, str] | Mapping[str, list]: A mapping of public keys
        in x.509 or JWK spec.
    """
    from django.core.cache import cache

    certs = cache.get(GOOGLE_OAUTH2_CERTS_CACHE_KEY)

    if not certs:
        response = request(certs_url, method='GET')

        if response.status != http_client.OK:
            raise exceptions.TransportError(f'Could not fetch certificates at {certs_url}')

        certs = json.loads(response.data.decode('utf-8'))
        cache.set(GOOGLE_OAUTH2_CERTS_CACHE_KEY, certs, GOOGLE_OAUTH2_CERTS_TTL)

    return certs
