from decimal import Decimal

from django.conf import settings

from exchange.asset_backed_credit.exceptions import ServiceNotFoundError
from exchange.asset_backed_credit.models import Service
from exchange.asset_backed_credit.services.loan.strategy import strategy_map
from exchange.asset_backed_credit.services.price import get_ratios
from exchange.asset_backed_credit.types import LoanCalculationData, ProviderFeeType


def calculate_loan(service_id: int, principal: int, period: int) -> LoanCalculationData:
    service = _get_service(service_id=service_id)
    try:
        strategy_class = strategy_map[service.provider]
    except KeyError:
        raise NotImplementedError('service is not implemented yet.')

    return strategy_class(service=service, principal=principal, period=period).get_loan_calculation_data()


def dummy_calculate_loan(principal: int, period: int, initial_debt: int) -> LoanCalculationData:
    return LoanCalculationData(
        principal=principal,
        period=period,
        interest_rate=0,
        collateral_fee_percent=Decimal(0),
        collateral_fee_amount=0,
        collateral_amount=initial_debt * get_ratios().get('collateral'),
        provider_fee_percent=Decimal(0),
        provider_fee_amount=0,
        provider_fee_type=ProviderFeeType.PRE_PAID,
        installment_amount=int(initial_debt / period),
        total_repayment_amount=initial_debt,
        initial_debt_amount=initial_debt,
        extra_info={},
    )


def _get_service(service_id: int):
    try:
        return Service.objects.get(pk=service_id, is_active=True, tp=Service.TYPES.loan)
    except Service.DoesNotExist as e:
        raise ServiceNotFoundError(message='No Service matches the given query.') from e
