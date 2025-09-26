from typing import Dict

from django.conf import settings

from .cardano_graphql_new import CardanoGraphqlApi


class CardanoPolarisGraphqlApi(CardanoGraphqlApi):
    instance = None
    _base_url = 'https://graphql.cardano.polareum.com'

    @classmethod
    def get_api_key(cls) -> str:
        return settings.POLARIS_CARDANO_API_KEY

    @classmethod
    def get_headers(cls) -> Dict[str, str]:
        return {
            'Content-Type': 'application/json',
            'X-API-KEY': cls.get_api_key(),
            'accept-encoding': 'gzip'
        }
