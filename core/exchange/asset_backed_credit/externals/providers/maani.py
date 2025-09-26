from dataclasses import dataclass

from django.conf import settings

from exchange.asset_backed_credit.models import Service
from exchange.asset_backed_credit.services.providers.provider import SignSupportProvider


@dataclass
class MaaniProvider(SignSupportProvider):
    """
    This class inherits SignSupportProvider class.

    Attributes:
        pub_key (str): The public key used for signature verification.

    Use this to login into MAANI account in nobitex:
        testnet_nobitex_username = ''
        testnet_nobitex_password = ''
    """

    contract_id: str
    username: str
    password: str
    client_id: str
    client_secret: str


MAANI = MaaniProvider(
    name='maani',
    ips=(
        []
        if settings.IS_PROD
        else [
            '92.114.18.133',  # MAANI IP
            '5.160.235.50',  # MAANI IP
            '5.160.235.51',  # MAANI IP
        ]
    ),
    pub_key='' if settings.IS_PROD else '',
    id=Service.PROVIDERS.maani,
    contract_id=('' if settings.IS_PROD else ''),
    account_id=(-1 if settings.IS_PROD else 324943 if settings.IS_TESTNET else -1),
    username='' if settings.IS_PROD else '',
    password='' if settings.IS_PROD else '',
    client_id=settings.ABC_MAANI_CLIENT_ID if settings.IS_PROD or settings.IS_TESTNET else 'test-client-id',
    client_secret=settings.ABC_MAANI_CLIENT_SECRET if settings.IS_PROD or settings.IS_TESTNET else 'test-client-secret',
)
