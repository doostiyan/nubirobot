from decimal import Decimal
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from exchange.asset_backed_credit.models import Service, UserFinancialServiceLimit, UserService
from exchange.base.models import Currencies
from tests.asset_backed_credit.helper import ABCMixins


class TestFixPendingDigipayAccountsCommand(ABCMixins, TestCase):
    def setUp(self):
        self.service = self.create_service(provider=Service.PROVIDERS.digipay)
        self.user = self.create_user()
        self.permission = self.create_user_service_permission(user=self.user, service=self.service)
        UserFinancialServiceLimit.set_service_limit(service=self.service, min_limit=1000000, max_limit=1000000000)

    @patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 50_000_0)
    def test_success(self):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('1000'))

        assert not UserService.objects.exists()

        call_command('abc_fix_pending_dp_accounts', '--id', self.user.id)

        user_service = UserService.objects.filter(user=self.user, service=self.service).first()
        assert user_service
        assert user_service.internal_user is None
        assert user_service.initial_debt == Decimal(260000000)
        assert user_service.current_debt == Decimal(260000000)
        assert user_service.account_number == '14339446501740835645163'
        assert user_service.user_service_permission == self.permission
