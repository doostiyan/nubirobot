from dataclasses import dataclass

from django.conf import settings

from exchange.asset_backed_credit.models import Service
from exchange.asset_backed_credit.services.providers.provider import SignSupportProvider


@dataclass
class DigipayProvider(SignSupportProvider):
    """
    This class inherits SignSupportProvider class.

    Attributes:
        pub_key (str): The public key used for signature verification.

    Use this to login into DIGIPAY account in nobitex:
        testnet_nobitex_username = ''
        testnet_nobitex_password = ''
    """

    contract_id: str
    username: str
    password: str
    client_id: str
    client_secret: str


DIGIPAY = DigipayProvider(
    name='digipay',
    ips=(['93.113.226.194'] if settings.IS_PROD else ['93.113.226.197', '93.113.229.11']),
    pub_key='' if settings.IS_PROD else '',
    id=Service.PROVIDERS.digipay,
    contract_id=('' if settings.IS_PROD else ''),
    account_id=(-1 if settings.IS_PROD else 325643 if settings.IS_TESTNET else -1),
    username=settings.ABC_DIGIPAY_USERNAME,
    password=settings.ABC_DIGIPAY_PASSWORD,
    client_id=settings.ABC_DIGIPAY_CLIENT_ID if settings.IS_PROD or settings.IS_TESTNET else 'test-client-id',
    client_secret=(
        settings.ABC_DIGIPAY_CLIENT_SECRET if settings.IS_PROD or settings.IS_TESTNET else 'test-client-secret'
    ),
)
