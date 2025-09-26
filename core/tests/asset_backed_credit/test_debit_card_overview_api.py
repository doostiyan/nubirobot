from decimal import Decimal
from unittest.mock import patch

from rest_framework import status

from exchange.accounts.models import User
from exchange.asset_backed_credit.externals.price import PriceProvider
from exchange.asset_backed_credit.models import CardTransactionLimit, Service
from exchange.asset_backed_credit.types import DEBIT_FEATURE_FLAG
from exchange.base.models import Currencies
from exchange.wallet.models import Wallet as ExchangeWallet
from tests.asset_backed_credit.helper import ABCMixins, APIHelper
from tests.features.utils import BetaFeatureTestMixin


def mock_get_last_trade_price(self):
    return Decimal(100)


@patch.object(PriceProvider, 'get_nobitex_price', mock_get_last_trade_price)
class DebitCardOverviewAPITest(BetaFeatureTestMixin, APIHelper, ABCMixins):
    URL = '/asset-backed-credit/debit/cards/{}/overview'

    feature = DEBIT_FEATURE_FLAG

    def setUp(self) -> None:
        self.user = User.objects.get(pk=201)
        self._change_parameters_in_object(
            self.user.get_verification_profile(),
            {'mobile_confirmed': True, 'identity_confirmed': True},
        )
        self._change_parameters_in_object(
            self.user.get_verification_profile(),
            {'mobile_identity_confirmed': True},
        )
        self._set_client_credentials(self.user.auth_token.key)
        self.card_pan = '6063909010102323'
        self.service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)
        self.user_service = self.create_user_service(user=self.user, service=self.service)
        self.card_level = self.create_card_setting(
            level=100,
            per_trx_limit=10_000_000,
            daily_limit=10_000_000,
            monthly_limit=100_000_000,
            cashback_percentage=Decimal(0.0),
        )
        self.card = self.create_card(pan=self.card_pan, user_service=self.user_service, setting=self.card_level)

    def test_get_card_limits_when_card_has_no_level(self):
        self.request_feature(self.user, 'done')
        self.card.setting = None
        self.card.save()

        response = self.client.get(path=self.URL.format(self.card.id), headers={})

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            'data': {},
            'status': 'ok',
        }

    def test_get_card_limits_success_when_user_has_no_transactions_today_and_this_month(self):
        self.request_feature(self.user, 'done')
        self.charge_exchange_wallet(self.user, Currencies.usdt, 1000, tp=ExchangeWallet.WALLET_TYPE.debit)
        response = self.client.get(path=self.URL.format(self.card.id), headers={})
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            'data': {
                'availableBalance': 100000,
                'limits': {'dailyLimit': 10000000, 'monthlyLimit': 100000000, 'transactionLimit': 10000000},
                'thisMonthCashback': 0,
                'thisMonthCashbackPercentage': '0',
                'thisMonthRemainingSpending': 100000000,
                'thisMonthRemainingSpendingPercent': 100,
                'thisMonthSpending': 0,
                'todayRemainingSpending': 10000000,
                'todayRemainingSpendingPercent': 100,
                'todaySpending': 0,
            },
            'status': 'ok',
        }

    def test_feature_is_not_activated(self):
        url = self.URL.format('10')
        response = self.client.get(path=url, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            'status': 'failed',
            'code': 'FeatureUnavailable',
            'message': 'abc_debit feature is not available for your user',
        }

    def test_get_card_overview_success(self):
        self.request_feature(self.user, 'done')
        self.charge_exchange_wallet(self.user, Currencies.usdt, 1000, tp=ExchangeWallet.WALLET_TYPE.debit)
        amount = 125_000
        CardTransactionLimit.add_card_transaction(self.card, amount)

        response = self.client.get(path=self.URL.format(self.card.id), headers={})

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            'data': {
                'availableBalance': 100000,
                'limits': {'dailyLimit': 10000000, 'monthlyLimit': 100000000, 'transactionLimit': 10000000},
                'thisMonthCashback': 0,
                'thisMonthCashbackPercentage': '0',
                'thisMonthRemainingSpending': 99875000,
                'thisMonthRemainingSpendingPercent': 99,
                'thisMonthSpending': 125000,
                'todayRemainingSpending': 9875000,
                'todayRemainingSpendingPercent': 98,
                'todaySpending': 125000,
            },
            'status': 'ok',
        }

    def test_get_card_limits_success_when_card_has_multiple_transactions_in_this_month_but_no_transaction_today(self):
        self.request_feature(self.user, 'done')
        self.charge_exchange_wallet(self.user, Currencies.usdt, 500_000_000, tp=ExchangeWallet.WALLET_TYPE.debit)
        amount = 1_100_000
        CardTransactionLimit._add_monthly_transaction(self.card, amount)
        CardTransactionLimit._add_monthly_transaction(self.card, amount)
        CardTransactionLimit._add_monthly_transaction(self.card, amount)

        response = self.client.get(path=self.URL.format(self.card.id), headers={})

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            'data': {
                'availableBalance': 50_000_000_000,
                'limits': {'dailyLimit': 10000000, 'monthlyLimit': 100000000, 'transactionLimit': 10000000},
                'thisMonthCashback': 0,
                'thisMonthCashbackPercentage': '0',
                'thisMonthRemainingSpending': 96700000,
                'thisMonthRemainingSpendingPercent': 96,
                'thisMonthSpending': 3300000,
                'todayRemainingSpending': 10000000,
                'todayRemainingSpendingPercent': 100,
                'todaySpending': 0,
            },
            'status': 'ok',
        }

    def test_get_card_limits_success_when_card_has_reached_monthly_limit_then_both_monthly_and_daily_remaining_are_zero(
        self,
    ):
        self.request_feature(self.user, 'done')
        self.charge_exchange_wallet(self.user, Currencies.usdt, 500_00_000_000, tp=ExchangeWallet.WALLET_TYPE.debit)
        CardTransactionLimit._add_monthly_transaction(self.card, self.card.setting.monthly_transaction_amount_limit)

        response = self.client.get(path=self.URL.format(self.card.id), headers={})

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            'data': {
                'availableBalance': 5000000000000,
                'limits': {'dailyLimit': 10000000, 'monthlyLimit': 100000000, 'transactionLimit': 10000000},
                'thisMonthCashback': 0,
                'thisMonthCashbackPercentage': '0',
                'thisMonthRemainingSpending': 0,
                'thisMonthRemainingSpendingPercent': 0,
                'thisMonthSpending': 100000000,
                'todayRemainingSpending': 0,
                'todayRemainingSpendingPercent': 0,
                'todaySpending': 0,
            },
            'status': 'ok',
        }

    def test_success_when_monthly_remaining_is_more_than_daily_remaining_then_daily_remaining(self):
        self.request_feature(self.user, 'done')
        self.charge_exchange_wallet(self.user, Currencies.usdt, 500_00_000_000, tp=ExchangeWallet.WALLET_TYPE.debit)
        CardTransactionLimit._add_monthly_transaction(
            self.card, self.card.setting.monthly_transaction_amount_limit - 100_000
        )

        response = self.client.get(path=self.URL.format(self.card.id), headers={})

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            'data': {
                'availableBalance': 5000000000000,
                'limits': {'dailyLimit': 10000000, 'monthlyLimit': 100000000, 'transactionLimit': 10000000},
                'thisMonthCashback': 0,
                'thisMonthCashbackPercentage': '0',
                'thisMonthRemainingSpending': 100_000,
                'thisMonthRemainingSpendingPercent': 0,
                'thisMonthSpending': 99900000,
                'todayRemainingSpending': 100_000,
                'todayRemainingSpendingPercent': 1,
                'todaySpending': 0,
            },
            'status': 'ok',
        }

    def test_when_user_has_no_such_card(self):
        self.request_feature(self.user, 'done')

        user_service = self.create_user_service(user=self.create_user(), service=self.service)
        card = self.create_card(pan='6063909010103344', user_service=user_service)

        response = self.client.get(path=self.URL.format(card.id), headers={})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_when_service_is_not_active_422_status_code_is_returned(self):
        self.request_feature(self.user, 'done')
        self.service.is_active = False
        self.service.save()

        response = self.client.get(path=self.URL.format(self.card.id), headers={})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def rial_to_toman(self, amount: int):
        return int(amount / 10)
