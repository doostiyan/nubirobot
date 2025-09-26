from decimal import Decimal
from typing import List

from pydantic import BaseModel, PositiveInt

from exchange.asset_backed_credit.models import Service, UserFinancialServiceLimit

PROPER_DEBT_TO_LOAN_RATIO = Decimal('1.7')


def set_all_services_options():
    services = Service.objects.filter(tp=Service.TYPES.loan, is_active=True)
    for service in services:
        set_service_options(service)


def set_service_options(service: Service):
    from exchange.asset_backed_credit.services.providers.dispatcher import api_dispatcher_v2

    options = api_dispatcher_v2(provider=service.provider, service_type=service.tp).get_service_options()
    if options is None:
        return

    UserFinancialServiceLimit.set_service_limit(
        service=service,
        min_limit=options.min_principal_limit,
        max_limit=PROPER_DEBT_TO_LOAN_RATIO * options.max_principal_limit,
    )
    service.options.update(
        {
            'min_principal_limit': options.min_principal_limit,
            'max_principal_limit': options.max_principal_limit,
            'periods': options.periods,
        }
    )
    service.save(update_fields=['options'])
