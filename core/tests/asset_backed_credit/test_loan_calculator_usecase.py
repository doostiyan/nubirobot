from dataclasses import asdict
from unittest import TestCase, mock

from exchange.asset_backed_credit.models import Service
from exchange.asset_backed_credit.services.loan.calculation import calculate_loan
from exchange.asset_backed_credit.types import ProviderBasedLoanCalculationData


class TestLoanCalculatorUseCase(TestCase):
    def setUp(self):
        self.vency_service = self._create_service(provider=Service.PROVIDERS.vency)
        self.tara_service = self._create_service(provider=Service.PROVIDERS.tara)

    @staticmethod
    def _create_service(provider):
        service, _ = Service.objects.get_or_create(provider=provider, tp=Service.TYPES.loan, is_active=True)
        return service

    @mock.patch(
        'exchange.asset_backed_credit.services.providers.dispatcher.VencyLoanAPIs.calculate',
        lambda *_, **__: ProviderBasedLoanCalculationData(
            **{
                'principal': 1000,
                'period': 6,
                'interest_rate': 18,
                'provider_fee_percent': 10.0,
                'provider_fee_amount': 100,
                'provider_fee_type': 'PRE_PAID',
                'installment_amount': 200,
                'total_installments_amount': 1200,
                'extra_info': {'loanPrincipalSupplyPlanId': '1', 'collaboratorLoanPlanId': '2'},
            }
        ),
    )
    def test_success(self):
        result = calculate_loan(service_id=self.vency_service.id, principal=1000, period=6)
        assert result.model_dump() == {
            'principal': 1000,
            'period': 6,
            'interest_rate': 18,
            'collateral_fee_percent': '0.0',
            'collateral_fee_amount': 0,
            'collateral_amount': 1560,
            'provider_fee_percent': '10.0',
            'provider_fee_amount': 100,
            'provider_fee_type': 'PRE_PAID',
            'installment_amount': 200,
            'initial_debt_amount': 1200,
            'total_repayment_amount': 1300,
            'extra_info': {'loanPrincipalSupplyPlanId': '1', 'collaboratorLoanPlanId': '2'},
        }

    def test_failure(self):
        with self.assertRaises(NotImplementedError) as cm:
            calculate_loan(service_id=self.tara_service.id, principal=1000, period=6)

        assert str(cm.exception) == 'service is not implemented yet.'
