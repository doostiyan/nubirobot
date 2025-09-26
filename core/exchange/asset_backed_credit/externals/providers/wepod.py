from dataclasses import dataclass

from django.conf import settings

from exchange.asset_backed_credit.models import Service
from exchange.asset_backed_credit.services.providers.provider import SignSupportProvider


@dataclass
class WepodProvider(SignSupportProvider):
    """
    This class inherits SignSupportProvider class.

    Attributes:
        pub_key (str): The public key used for signature verification.

    Use this to login into Wepod account in nobitex:
        testnet_nobitex_username = '09999999965'
        testnet_nobitex_password = 'Y8?@}}*x-HYE8@a'
    """

    contract_id: str
    username: str
    password: str


WEPOD = WepodProvider(
    name='wepod',
    ips=(
        []
        if settings.IS_PROD
        else [
            '93.113.229.50',  # Wepod IP
        ]
    ),
    pub_key='' if settings.IS_PROD else '',
    id=Service.PROVIDERS.wepod,
    contract_id=('' if settings.IS_PROD else ''),
    account_id=(-1 if settings.IS_PROD else 320101 if settings.IS_TESTNET else 913),
    username='' if settings.IS_PROD else '',
    password='' if settings.IS_PROD else '',
)
