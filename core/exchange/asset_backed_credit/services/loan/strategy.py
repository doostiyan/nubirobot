from abc import ABC, abstractmethod
from math import ceil

from exchange.asset_backed_credit.exceptions import LoanCalculationError, ThirdPartyError
from exchange.asset_backed_credit.models import Service, UserService
from exchange.asset_backed_credit.services.price import get_ratios
from exchange.asset_backed_credit.services.providers.dispatcher import api_dispatcher_v2
from exchange.asset_backed_credit.types import LoanCalculationData, ProviderFeeType


class BaseLoanCalculationStrategy(ABC):
    def __init__(self, service: Service, principal: int, period: int):
        self.service = service
        self.principal = principal
        self.period = period

    @abstractmethod
    def get_loan_calculation_data(self) -> LoanCalculationData:
        pass


class ProviderBasedLoanCalculationStrategy(BaseLoanCalculationStrategy):
    def get_loan_calculation_data(self) -> LoanCalculationData:
        try:
            data = api_dispatcher_v2(provider=self.service.provider, service_type=self.service.tp,).calculate(
                principal=self.principal,
                period=self.period,
            )
        except ThirdPartyError as e:
            raise LoanCalculationError(message='LoanCalculationError', description='third party error') from e

        collateral_fee_amount = UserService.COLLATERAL_FEE_AMOUNT
        total_repayment_amount = data.total_installments_amount + data.provider_fee_amount + collateral_fee_amount

        if data.provider_fee_type == ProviderFeeType.PRE_PAID:
            initial_debt_amount = total_repayment_amount - data.provider_fee_amount
        elif data.provider_fee_type == ProviderFeeType.ON_INSTALLMENTS:
            initial_debt_amount = total_repayment_amount
        else:
            raise ValueError()

        collateral_ratio = get_ratios().get('collateral')
        collateral_amount = ceil(initial_debt_amount * collateral_ratio)

        return LoanCalculationData(
            principal=self.principal,
            period=self.period,
            interest_rate=int(data.interest_rate),
            collateral_fee_percent=UserService.COLLATERAL_FEE_PERCENT,
            collateral_fee_amount=collateral_fee_amount,
            collateral_amount=collateral_amount,
            provider_fee_percent=data.provider_fee_percent,
            provider_fee_amount=data.provider_fee_amount,
            provider_fee_type=data.provider_fee_type,
            installment_amount=data.installment_amount,
            total_repayment_amount=total_repayment_amount,
            initial_debt_amount=initial_debt_amount,
            extra_info=data.extra_info,
        )


strategy_map = {
    Service.PROVIDERS.vency: ProviderBasedLoanCalculationStrategy,
    Service.PROVIDERS.azki: ProviderBasedLoanCalculationStrategy,
}
