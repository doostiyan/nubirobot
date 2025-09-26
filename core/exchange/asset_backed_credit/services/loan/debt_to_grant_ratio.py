from decimal import ROUND_DOWN, Decimal

from django.core.cache import cache

from exchange.asset_backed_credit.exceptions import ThirdPartyError
from exchange.asset_backed_credit.models import Service
from exchange.asset_backed_credit.services.providers.dispatcher import api_dispatcher_v2
from exchange.base.logging import report_event

CACHE_KEY = 'MIN-LOAN-DEBT-TO-GRANT-RATIO'


def set_vency_min_debt_to_grant_ratio():
    service = Service.objects.get(provider=Service.PROVIDERS.vency, tp=Service.TYPES.loan)
    try:
        ratio = api_dispatcher_v2(provider=service.provider, service_type=service.tp).get_min_debt_to_grant_ration()
    except ThirdPartyError as e:
        report_event('ThirdPartyError', extras={'usage': 'loan-ratio', 'error': str(e)})
        return None

    service.options.update({'debt_to_grant_ratio': str(ratio)})
    service.save(update_fields=['options'])
    return ratio


def cache_min_loan_debt_to_grant_ratio():
    mapping = {
        'vency': set_vency_min_debt_to_grant_ratio(),
    }
    try:
        min_ratio = min(val for val in mapping.values() if val is not None)
    except ValueError:
        min_ratio = None

    cache.set(CACHE_KEY, min_ratio, timeout=6 * 60 * 60)


def get_max_available_loan(available_collateral: Decimal) -> Decimal:
    ratio = Decimal(cache.get(CACHE_KEY) or 1).quantize(Decimal('0.01'))
    return Decimal(available_collateral / ratio).quantize(Decimal('1'), rounding=ROUND_DOWN)
