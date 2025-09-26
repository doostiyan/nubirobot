from dataclasses import dataclass

from django.conf import settings

from exchange.asset_backed_credit.models import Service
from exchange.asset_backed_credit.services.providers.provider import SignSupportProvider


@dataclass
class BaloanProvider(SignSupportProvider):
    """
    This class inherits Provider class.

    Attributes:
        pub_key (str): The public key used for signature verification.

    Use this to login into tara account in nobitex:
        testnet_nobitex_username = '09999999963'
        testnet_nobitex_password = 'ebdhP7zZTQm#SsUDjrWg2L3'
    """

    contract_id: str
    username: str
    password: str


BALOAN = BaloanProvider(
    name='baloan',
    ips=(
        []
        if settings.IS_PROD
        else [
            '213.207.198.154',
            '78.158.166.186',
            '78.158.166.187',
        ]
    ),
    pub_key='' if settings.IS_PROD else '',
    id=Service.PROVIDERS.baloan,
    contract_id=('' if settings.IS_PROD else ''),
    account_id=(-1 if settings.IS_PROD else 321547 if settings.IS_TESTNET else 911),
    username='' if settings.IS_PROD else '',
    password='' if settings.IS_PROD else '',
)
