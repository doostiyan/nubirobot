from dataclasses import dataclass

from django.conf import settings

from exchange.asset_backed_credit.models import Service
from exchange.asset_backed_credit.services.providers.provider import BasicAuthenticationSupportProvider


@dataclass
class PardakhtNovinProvider(BasicAuthenticationSupportProvider):
    pass


PARDAKHT_NOVIN = PardakhtNovinProvider(
    name='pnovin',
    ips=([] if settings.IS_PROD else []),
    id=Service.PROVIDERS.pnovin,
    account_id=-1 if settings.IS_PROD else 320088 if settings.IS_TESTNET else 914,
    api_username='' if settings.IS_PROD else 'nobitex_debit_pnovin',
    api_password='' if settings.IS_PROD else settings.ABC_DEBIT_PNOVIN_PASSWORD,
    username='',
    password='',
)
