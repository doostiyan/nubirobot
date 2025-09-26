from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from exchange.accounts.models import User
from exchange.asset_backed_credit.services.price import PricingService
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies
from tests.asset_backed_credit.helper import ABCMixins


@patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 50_000_0)
class MarginCalculatorTest(ABCMixins, TestCase):
    def setUp(self) -> None:
        self.user = User.objects.get(pk=201)
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('100'))

    def test_zero_total_credit_value(self):
        assert PricingService(self.user).get_margin_ratio() == Decimal('Infinity')

    def test_return_margin_ratio_successfully(self):
        service = self.create_service()
        user_service = self.create_user_service(
            self.user,
            initial_debt=Decimal('4_500_000_0'),
            current_debt=Decimal('4_500_000_0'),
            service=service,
        )

        margin_ratio = PricingService(self.user).get_margin_ratio()

        assert margin_ratio == Decimal('1.11')

        user_service.closed_at = ir_now()
        user_service.save()
        self.create_user_service(
            self.user,
            initial_debt=Decimal('4_800_000_0'),
            current_debt=Decimal('4_800_000_0'),
            service=service,
        )

        margin_ratio = PricingService(self.user).get_margin_ratio()
        assert margin_ratio == Decimal('1.04')


    def test_return_margin_ratio_with_future_amount(self):
        service = self.create_service()
        self.create_user_service(
            self.user,
            initial_debt=Decimal('3_500_000_0'),
            current_debt=Decimal('3_500_000_0'),
            service=service,
        )

        margin_ratio = PricingService(self.user).get_margin_ratio()
        assert margin_ratio == Decimal('1.42')
