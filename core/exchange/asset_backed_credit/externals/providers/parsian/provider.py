from dataclasses import dataclass

from django.conf import settings

from exchange.asset_backed_credit.models import Service
from exchange.asset_backed_credit.services.providers.provider import BasicAuthenticationSupportProvider


@dataclass
class ParsianProvider(BasicAuthenticationSupportProvider):
    pass


PARSIAN = ParsianProvider(
    name='parsian',
    ips=(['212.80.26.13'] if settings.IS_PROD else []),  # Parsian Top IP
    id=Service.PROVIDERS.parsian,
    account_id=7589040 if settings.IS_PROD else 320103 if settings.IS_TESTNET else 915,
    api_username=settings.ABC_DEBIT_API_PARSIAN_USERNAME,
    api_password=settings.ABC_DEBIT_API_PARSIAN_PASSWORD,
    username=settings.ABC_DEBIT_PARSIAN_USERNAME,
    password=settings.ABC_DEBIT_PARSIAN_PASSWORD,
)
