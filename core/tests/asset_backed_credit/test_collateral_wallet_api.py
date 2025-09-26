from decimal import Decimal
from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.asset_backed_credit.exceptions import PriceNotAvailableError
from exchange.asset_backed_credit.externals.price import PriceProvider
from exchange.asset_backed_credit.models import Wallet
from exchange.base.models import Currencies, Settings
from exchange.wallet.models import Wallet as ExchangeWallet
from tests.asset_backed_credit.helper import ABCMixins, APIHelper

BTC_PRICE = 2_000_000
USDT_PRICE = 100_000
ETH_PRICE = 250_000


def mock_get_nobitex_price(self):
    if self.src_currency == Currencies.btc:
        return Decimal(BTC_PRICE)
    elif self.src_currency == Currencies.usdt:
        return Decimal(USDT_PRICE)
    elif self.src_currency == Currencies.eth:
        return Decimal(ETH_PRICE)
    raise PriceNotAvailableError


class CollateralWalletListAPITestCase(ABCMixins, APITestCase):
    URL = '/asset-backed-credit/wallets/collateral'

    @classmethod
    def setUpTestData(cls):
        cls.user, _ = User.objects.get_or_create(username='test-user')
        cls.another_user, _ = User.objects.get_or_create(username='another-user')

    def setUp(self):
        self.client.force_authenticate(user=self.user)

    @patch.object(PriceProvider, 'get_nobitex_price', mock_get_nobitex_price)
    def test_first_time_from_db_second_time_from_cache_success(self):
        wallet_1 = self.charge_exchange_wallet(
            self.user, currency=Currencies.usdt, amount=1000, tp=ExchangeWallet.WALLET_TYPE.credit
        )
        wallet_2 = self.charge_exchange_wallet(
            self.user, currency=Currencies.btc, amount=2, tp=ExchangeWallet.WALLET_TYPE.credit
        )
        wallet_3 = self.charge_exchange_wallet(
            self.user, currency=Currencies.eth, amount=25, tp=ExchangeWallet.WALLET_TYPE.credit
        )

        resp = self.client.get(self.URL)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data['status'] == 'ok'
        assert sorted(data['wallets'], key=lambda w: w['rialBalance'], reverse=True) == [
            {
                'activeBalance': '1000',
                'balance': '1000',
                'blockedBalance': '0',
                'currency': 'USDT',
                'id': wallet_1.id,
                'rialBalance': 1000 * USDT_PRICE,
                'rialBalanceSell': 1000 * USDT_PRICE,
                'type': 10,
                'typeStr': 'COLLATERAL',
            },
            {
                'activeBalance': '25',
                'balance': '25',
                'blockedBalance': '0',
                'currency': 'ETH',
                'id': wallet_3.id,
                'rialBalance': 25 * ETH_PRICE,
                'rialBalanceSell': 25 * ETH_PRICE,
                'type': 10,
                'typeStr': 'COLLATERAL',
            },
            {
                'activeBalance': '2',
                'balance': '2',
                'blockedBalance': '0',
                'currency': 'BTC',
                'id': wallet_2.id,
                'rialBalance': 2 * BTC_PRICE,
                'rialBalanceSell': 2 * BTC_PRICE,
                'type': 10,
                'typeStr': 'COLLATERAL',
            },
        ]

        with patch(
            'exchange.asset_backed_credit.externals.wallet.ExchangeWallet.objects.filter'
        ) as mock_exchange_filter:
            resp = self.client.get(self.URL)
            assert resp.status_code == status.HTTP_200_OK
            data = resp.json()
            assert data['status'] == 'ok'
            assert sorted(data['wallets'], key=lambda w: w['rialBalance'], reverse=True) == [
                {
                    'activeBalance': '1000',
                    'balance': '1000',
                    'blockedBalance': '0',
                    'currency': 'USDT',
                    'id': wallet_1.id,
                    'rialBalance': 1000 * USDT_PRICE,
                    'rialBalanceSell': 1000 * USDT_PRICE,
                    'type': 10,
                    'typeStr': 'COLLATERAL',
                },
                {
                    'activeBalance': '25',
                    'balance': '25',
                    'blockedBalance': '0',
                    'currency': 'ETH',
                    'id': wallet_3.id,
                    'rialBalance': 25 * ETH_PRICE,
                    'rialBalanceSell': 25 * ETH_PRICE,
                    'type': 10,
                    'typeStr': 'COLLATERAL',
                },
                {
                    'activeBalance': '2',
                    'balance': '2',
                    'blockedBalance': '0',
                    'currency': 'BTC',
                    'id': wallet_2.id,
                    'rialBalance': 2 * BTC_PRICE,
                    'rialBalanceSell': 2 * BTC_PRICE,
                    'type': 10,
                    'typeStr': 'COLLATERAL',
                },
            ]
            mock_exchange_filter.assert_not_called()

    def test_success_no_wallet(self):
        self.charge_exchange_wallet(
            self.another_user, currency=Currencies.eth, amount=200, tp=ExchangeWallet.WALLET_TYPE.credit
        )
        resp = self.client.get(self.URL)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json() == {
            'status': 'ok',
            'wallets': [],
        }

        Settings.set('abc_debit_internal_wallet_enabled', 'yes')
        Wallet.objects.update_or_create(
            user=self.another_user, balance=200, currency=Currencies.eth, type=Wallet.WalletType.COLLATERAL
        )
        resp = self.client.get(self.URL)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json() == {
            'status': 'ok',
            'wallets': [],
        }

    @patch.object(PriceProvider, 'get_nobitex_price', mock_get_nobitex_price)
    def test_success_price_not_available(self):
        wallet_1 = self.charge_exchange_wallet(
            self.user, currency=Currencies.usdt, amount=10, tp=ExchangeWallet.WALLET_TYPE.credit
        )
        wallet_2 = self.charge_exchange_wallet(
            self.user, currency=Currencies.avax, amount=20, tp=ExchangeWallet.WALLET_TYPE.credit
        )
        wallet_3 = self.charge_exchange_wallet(
            self.user, currency=Currencies.eth, amount=5, tp=ExchangeWallet.WALLET_TYPE.credit
        )

        resp = self.client.get(self.URL)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data['status'] == 'ok'
        assert sorted(data['wallets'], key=lambda w: w['rialBalance'], reverse=True) == [
            {
                'activeBalance': '5',
                'balance': '5',
                'blockedBalance': '0',
                'currency': 'ETH',
                'id': wallet_3.id,
                'rialBalance': 5 * ETH_PRICE,
                'rialBalanceSell': 5 * ETH_PRICE,
                'type': 10,
                'typeStr': 'COLLATERAL',
            },
            {
                'activeBalance': '10',
                'balance': '10',
                'blockedBalance': '0',
                'currency': 'USDT',
                'id': wallet_1.id,
                'rialBalance': 10 * USDT_PRICE,
                'rialBalanceSell': 10 * USDT_PRICE,
                'type': 10,
                'typeStr': 'COLLATERAL',
            },
            {
                'activeBalance': '20',
                'balance': '20',
                'blockedBalance': '0',
                'currency': 'AVAX',
                'id': wallet_2.id,
                'rialBalance': 0,
                'rialBalanceSell': 0,
                'type': 10,
                'typeStr': 'COLLATERAL',
            },
        ]
