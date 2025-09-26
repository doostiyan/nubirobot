from typing import TYPE_CHECKING, Optional

from django.conf import settings

from exchange.asset_backed_credit.exceptions import InvalidIPError, InvalidSignatureError, MissingSignatureError
from exchange.asset_backed_credit.externals.providers import (
    AZKI,
    BALOAN,
    DIGIPAY,
    MAANI,
    PARDAKHT_NOVIN,
    PARSIAN,
    TARA,
    VENCY,
    WEPOD,
)
from exchange.base.cryptography.rsa import RSAVerifier
from exchange.base.models import Settings

if TYPE_CHECKING:
    from exchange.asset_backed_credit.services.providers.provider import Provider


class ProviderManager:
    """
    A class responsible for managing providers and verifying incoming requests.

    Class Attributes:
        providers (List[Provider]): A list of supported providers.

    """

    providers = (TARA, PARDAKHT_NOVIN, VENCY, WEPOD, PARSIAN, BALOAN, MAANI, DIGIPAY, AZKI)

    @classmethod
    def get_provider(cls, ip: str) -> Optional['Provider']:
        """
        Retrieves the provider associated with the given IP address.
        """
        for provider in cls.providers:
            if ip in provider.ips:
                return provider
        return None

    @classmethod
    def get_provider_by_id(cls, provider_id: int) -> 'Provider':
        for provider in cls.providers:
            if provider_id == provider.id:
                return provider

    @classmethod
    def _get_provider_by_ips_allowed_in_testnet(cls, ip: str):
        if not settings.IS_TESTNET:
            raise InvalidIPError()

        test_net_providers = Settings.get_cached_json('abc_test_net_providers', {})
        for provider_id, ips in test_net_providers.items():
            if ip in ips:
                provider = cls.get_provider_by_id(int(provider_id))
                if provider:
                    return provider
        raise InvalidIPError()

    @classmethod
    def get_provider_by_ip(cls, ip: str) -> 'Provider':
        provider = cls.get_provider(ip)
        if not provider:
            return cls._get_provider_by_ips_allowed_in_testnet(ip)
        return provider

    @classmethod
    def _validate_signature(cls, message: str, signature: str, pub_key: str) -> None:
        if not RSAVerifier(pub_key).verify(message, signature):
            raise ValueError('signature not verified')

    @classmethod
    def verify_signature(cls, signature: str, pub_key: str, body_data: dict):
        """
        Verifies the incoming request by checking its signature.

            Params:
                signature (str): The signature provided with the request.
                pub_key (str): The public key of the provider
                body_data (dict): The data contained in the request body.

            Raises:
                MissingSignatureError: If the request signature is missing.
                InvalidSignatureError: If the request signature is not valid.
        """
        if not signature:
            raise MissingSignatureError('x-request-signature parameter is required!')

        values_to_sign = [str(value) for _, value in sorted(body_data.items())]
        message = '|'.join(values_to_sign)

        # Verify the signature
        if settings.IS_TESTNET and message == signature:
            return

        try:
            cls._validate_signature(message, signature, pub_key)
        except (ValueError, TypeError) as ex:
            raise InvalidSignatureError('The signature is not valid!') from ex


provider_manager = ProviderManager()
