from decimal import Decimal
from unittest.mock import patch

import responses
from django.test import TestCase
from rest_framework import status

from exchange.accounts.models import User
from exchange.asset_backed_credit.externals.price import PriceProvider
from exchange.asset_backed_credit.externals.wallet import WalletListAPI
from exchange.asset_backed_credit.models import Service, Wallet
from exchange.asset_backed_credit.services.price import PricingService
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies, Settings
from exchange.wallet.models import Wallet as ExchangeWallet
from tests.asset_backed_credit.helper import ABCMixins


@patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 237010)
@patch('exchange.wallet.estimator.PriceEstimator.get_price_range', lambda *_: (237120, _))
class TestPricingService(ABCMixins, TestCase):
    def setUp(self) -> None:
        self.user = User.objects.get(pk=201)
        self.pricing_service = PricingService(self.user)

    def test_get_total_assets(self):
        total_assets = self.pricing_service.get_total_assets(force_update=True)
        assert total_assets.total_mark_price == 0
        assert total_assets.total_nobitex_price == 0
        assert total_assets.weighted_avg is None

        _wallet = self.charge_exchange_wallet(
            self.user, Currencies.doge, Decimal('100'), ExchangeWallet.WALLET_TYPE.spot
        )

        total_assets = self.pricing_service.get_total_assets(force_update=True)
        assert total_assets.total_mark_price == 0
        assert total_assets.total_nobitex_price == 0
        assert total_assets.weighted_avg is None

        _wallet = self.charge_exchange_wallet(
            self.user, Currencies.doge, Decimal('100'), ExchangeWallet.WALLET_TYPE.credit
        )

        total_assets = self.pricing_service.get_total_assets()
        assert total_assets.total_mark_price == 0
        assert total_assets.total_nobitex_price == 0
        assert total_assets.weighted_avg is None

        total_assets = self.pricing_service.get_total_assets(force_update=True)
        assert total_assets.total_mark_price == 23701000
        assert total_assets.total_nobitex_price == 23712000
        assert total_assets.weighted_avg == Decimal('0.0004')

    @responses.activate
    def test_get_total_assets_when_wallets_internal_api_is_enabled(self):
        Settings.set('abc_use_wallet_list_internal_api', 'yes')
        responses.post(
            url=WalletListAPI.url,
            json={str(self.user.uid): [
                {
                    "activeBalance": "100",
                    "balance": "100",
                    "blockedBalance": "0",
                    "currency": "btc",
                    "type": "credit",
                    "userId": str(self.user.uid)
                }
            ]},
            status=status.HTTP_200_OK,
        )

        total_assets = self.pricing_service.get_total_assets()
        assert total_assets.total_mark_price == 0
        assert total_assets.total_nobitex_price == 0
        assert total_assets.weighted_avg is None

        total_assets = self.pricing_service.get_total_assets(force_update=True)
        assert total_assets.total_mark_price == 23701000
        assert total_assets.total_nobitex_price == 23712000
        assert total_assets.weighted_avg == Decimal('0.0004')

    def test_get_available_collateral(self):
        total_assets = self.pricing_service.get_total_assets(force_update=True)
        assert total_assets.total_mark_price == 0
        assert total_assets.total_nobitex_price == 0
        assert total_assets.weighted_avg is None

        _wallet = self.charge_exchange_wallet(
            self.user, Currencies.doge, Decimal('100'), ExchangeWallet.WALLET_TYPE.credit
        )

        total_assets = self.pricing_service.get_total_assets(force_update=True)
        assert total_assets.total_mark_price == 23701000
        assert total_assets.total_nobitex_price == 23712000
        assert total_assets.weighted_avg == Decimal('0.0004')

        self.create_user_service(user=self.user, initial_debt=11850500, current_debt=11850500)

        self.pricing_service.get_total_debt(force_update=True)
        available_collateral = self.pricing_service.get_available_collateral()
        assert available_collateral == 6389500

    def test_get_available_collateral_on_debit_wallet(self):
        pricing_service = PricingService(self.user, wallet_type=Wallet.WalletType.DEBIT)
        total_assets = pricing_service.get_total_assets(force_update=True)
        assert total_assets.total_mark_price == 0
        assert total_assets.total_nobitex_price == 0
        assert total_assets.weighted_avg is None

        _wallet = self.charge_exchange_wallet(
            self.user, Currencies.doge, Decimal('100'), ExchangeWallet.WALLET_TYPE.debit
        )

        total_assets = pricing_service.get_total_assets(force_update=True)
        assert total_assets.total_mark_price == 23701000
        assert total_assets.total_nobitex_price == 23712000
        assert total_assets.weighted_avg == Decimal('0.0004')

        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)
        self.create_user_service(user=self.user, service=service, initial_debt=11850500, current_debt=11850500)

        pricing_service.get_total_debt(force_update=True)
        available_collateral = pricing_service.get_available_collateral()
        assert available_collateral == 9705863

    def test_get_available_collateral_include_blocked_and_inactive_service(self):
        _wallet = self.charge_exchange_wallet(
            self.user, Currencies.doge, Decimal('100'), ExchangeWallet.WALLET_TYPE.credit
        )

        total_assets = self.pricing_service.get_total_assets(force_update=True)
        assert total_assets.total_mark_price == 23701000
        assert total_assets.total_nobitex_price == 23712000
        assert total_assets.weighted_avg == Decimal('0.0004')

        _service = self.create_service(contract_id='12345678')
        self.create_user_service(
            user=self.user,
            initial_debt=11850500,
            current_debt=11850500,
            closed_at=ir_now(),
            service=_service,
        )

        total_assets = self.pricing_service.get_total_assets(force_update=True)
        assert total_assets.total_mark_price == 23701000
        assert total_assets.total_nobitex_price == 23712000
        assert total_assets.weighted_avg == Decimal('0.0004')

        self.create_user_service(
            user=self.user,
            initial_debt=11850500,
            current_debt=11850500,
            service=_service,
        )

        self.pricing_service.get_total_debt(force_update=True)
        available_collateral = self.pricing_service.get_available_collateral()
        assert available_collateral == 6389500

        self.create_user_service(
            user=self.user,
            initial_debt=11850500,
            current_debt=11850500,
            closed_at=ir_now(),
            service=_service,
        )

        self.pricing_service.get_total_debt(force_update=True)
        available_collateral = self.pricing_service.get_available_collateral()
        assert available_collateral == 6389500

    def test_get_available_collateral_keep_ratio_false_and_return_zero(self):
        total_assets = self.pricing_service.get_total_assets(force_update=True)
        assert total_assets.total_mark_price == 0
        assert total_assets.total_nobitex_price == 0
        assert total_assets.weighted_avg is None

        _wallet = self.charge_exchange_wallet(
            self.user, Currencies.doge, Decimal('100'), ExchangeWallet.WALLET_TYPE.credit
        )

        total_assets = self.pricing_service.get_total_assets(force_update=True)
        assert total_assets.total_mark_price == 23701000
        assert total_assets.total_nobitex_price == 23712000
        assert total_assets.weighted_avg == Decimal('0.0004')

        self.create_user_service(user=self.user, initial_debt=27850500, current_debt=27850500)

        self.pricing_service.get_total_debt(force_update=True)
        available_collateral = self.pricing_service.get_available_collateral(keep_ratio=False)
        assert available_collateral == 0

    def test_get_required_collateral(self):
        total_assets = self.pricing_service.get_total_assets(force_update=True)
        assert total_assets.total_mark_price == 0
        assert total_assets.total_nobitex_price == 0
        assert total_assets.weighted_avg is None

        _wallet = self.charge_exchange_wallet(
            self.user, Currencies.doge, Decimal('100'), ExchangeWallet.WALLET_TYPE.credit
        )

        total_assets = self.pricing_service.get_total_assets(force_update=True)
        assert total_assets.total_mark_price == 23701000
        assert total_assets.total_nobitex_price == 23712000
        assert total_assets.weighted_avg == Decimal('0.0004')

        self.create_user_service(user=self.user, initial_debt=27850500, current_debt=27850500)

        self.pricing_service.get_total_debt(force_update=True)
        available_collateral = self.pricing_service.get_required_collateral()
        assert available_collateral == 12493650

    def test_get_required_collateral_keep_ratio_false(self):
        total_assets = self.pricing_service.get_total_assets(force_update=True)
        assert total_assets.total_mark_price == 0
        assert total_assets.total_nobitex_price == 0
        assert total_assets.weighted_avg is None

        _wallet = self.charge_exchange_wallet(
            self.user, Currencies.doge, Decimal('100'), ExchangeWallet.WALLET_TYPE.credit
        )

        total_assets = self.pricing_service.get_total_assets(force_update=True)
        assert total_assets.total_mark_price == 23701000
        assert total_assets.total_nobitex_price == 23712000
        assert total_assets.weighted_avg == Decimal('0.0004')

        self.create_user_service(user=self.user, initial_debt=27850500, current_debt=27850500)

        self.pricing_service.get_total_debt(force_update=True)
        available_collateral = self.pricing_service.get_required_collateral(keep_ratio=False)
        assert available_collateral == 4138500

    @patch.object(PriceProvider, 'get_mark_price')
    @patch.object(PriceProvider, 'get_nobitex_price')
    def test_price_service_when_user_has_some_wallets_with_zero_balance_then_price_provider_is_not_called_for_those(
        self, nobitex_price_mock, mark_price_mock
    ):
        nobitex_price_mock.return_value = 10
        mark_price_mock.return_value = 12

        total_assets = self.pricing_service.get_total_assets()
        assert total_assets.total_mark_price == 0
        assert total_assets.total_nobitex_price == 0
        assert total_assets.weighted_avg is None

        _wallet = self.charge_exchange_wallet(
            self.user, Currencies.btc, amount=Decimal('10'), tp=ExchangeWallet.WALLET_TYPE.spot
        )
        _wallet = self.charge_exchange_wallet(self.user, Currencies.dai, amount=Decimal('0E-10'))
        _wallet = self.charge_exchange_wallet(self.user, Currencies.usdt, amount=Decimal('5'))

        total_assets = self.pricing_service.get_total_assets(force_update=True)
        assert total_assets.total_mark_price == Decimal(60)
        assert total_assets.total_nobitex_price == Decimal(50)
        assert total_assets.weighted_avg == Decimal('0.1666')

        nobitex_price_mock.assert_called_once()
        nobitex_price_mock.assert_called_once()
