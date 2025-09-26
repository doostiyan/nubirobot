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

BTC_PRICE = 1_000_000
USDT_PRICE = 50_000
TON_PRICE = 120_000


def mock_get_nobitex_price(self):
    if self.src_currency == Currencies.btc:
        return Decimal(BTC_PRICE)
    elif self.src_currency == Currencies.usdt:
        return Decimal(50_000)
    elif self.src_currency == Currencies.ton:
        return Decimal(120_000)
    raise PriceNotAvailableError


class DebitWalletListAPITestCase(ABCMixins, APITestCase):
    URL = '/asset-backed-credit/wallets/debit'

    @classmethod
    def setUpTestData(cls):
        cls.user, _ = User.objects.get_or_create(username='test-user')
        cls.another_user, _ = User.objects.get_or_create(username='another-user')

    def setUp(self):
        self.client.force_authenticate(user=self.user)

    @patch.object(PriceProvider, 'get_nobitex_price', mock_get_nobitex_price)
    def test_success(self):
        wallet_1 = self.charge_exchange_wallet(
            self.user, currency=Currencies.usdt, amount=1000, tp=ExchangeWallet.WALLET_TYPE.debit
        )
        wallet_2 = self.charge_exchange_wallet(
            self.user, currency=Currencies.btc, amount=2, tp=ExchangeWallet.WALLET_TYPE.debit
        )
        wallet_3 = self.charge_exchange_wallet(
            self.user, currency=Currencies.ton, amount=25, tp=ExchangeWallet.WALLET_TYPE.debit
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
                'type': 20,
                'typeStr': 'DEBIT',
            },
            {
                'activeBalance': '25',
                'balance': '25',
                'blockedBalance': '0',
                'currency': 'TON',
                'id': wallet_3.id,
                'rialBalance': 25 * TON_PRICE,
                'rialBalanceSell': 25 * TON_PRICE,
                'type': 20,
                'typeStr': 'DEBIT',
            },
            {
                'activeBalance': '2',
                'balance': '2',
                'blockedBalance': '0',
                'currency': 'BTC',
                'id': wallet_2.id,
                'rialBalance': 2 * BTC_PRICE,
                'rialBalanceSell': 2 * BTC_PRICE,
                'type': 20,
                'typeStr': 'DEBIT',
            },
        ]

    @patch.object(PriceProvider, 'get_nobitex_price', mock_get_nobitex_price)
    def test_success_with_internal_wallet(self):
        Settings.set('abc_debit_internal_wallet_enabled', 'yes')
        wallet_1, _ = Wallet.objects.update_or_create(
            user=self.user, balance=11, currency=Currencies.usdt, type=Wallet.WalletType.DEBIT
        )
        wallet_2, _ = Wallet.objects.update_or_create(
            user=self.user, balance=12, currency=Currencies.btc, type=Wallet.WalletType.DEBIT
        )
        wallet_3, _ = Wallet.objects.update_or_create(
            user=self.user, balance=13, currency=Currencies.ton, type=Wallet.WalletType.DEBIT
        )

        resp = self.client.get(self.URL)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data['status'] == 'ok'
        assert sorted(data['wallets'], key=lambda w: w['rialBalance'], reverse=True) == [
            {
                'activeBalance': '12',
                'balance': '12',
                'blockedBalance': '0',
                'currency': 'BTC',
                'id': wallet_2.id,
                'rialBalance': 12 * BTC_PRICE,
                'rialBalanceSell': 12 * BTC_PRICE,
                'type': 20,
                'typeStr': 'DEBIT',
            },
            {
                'activeBalance': '13',
                'balance': '13',
                'blockedBalance': '0',
                'currency': 'TON',
                'id': wallet_3.id,
                'rialBalance': 13 * TON_PRICE,
                'rialBalanceSell': 13 * TON_PRICE,
                'type': 20,
                'typeStr': 'DEBIT',
            },
            {
                'activeBalance': '11',
                'balance': '11',
                'blockedBalance': '0',
                'currency': 'USDT',
                'id': wallet_1.id,
                'rialBalance': 11 * USDT_PRICE,
                'rialBalanceSell': 11 * USDT_PRICE,
                'type': 20,
                'typeStr': 'DEBIT',
            },
        ]

    def test_success_no_wallet(self):
        self.charge_exchange_wallet(
            self.another_user, currency=Currencies.usdt, amount=100, tp=ExchangeWallet.WALLET_TYPE.debit
        )
        resp = self.client.get(self.URL)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json() == {
            'status': 'ok',
            'wallets': [],
        }

        Settings.set('abc_debit_internal_wallet_enabled', 'yes')
        Wallet.objects.update_or_create(
            user=self.another_user, balance=100, currency=Currencies.usdt, type=ExchangeWallet.WALLET_TYPE.debit
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
            self.user, currency=Currencies.usdt, amount=100, tp=ExchangeWallet.WALLET_TYPE.debit
        )
        wallet_2 = self.charge_exchange_wallet(
            self.user, currency=Currencies.avax, amount=200, tp=ExchangeWallet.WALLET_TYPE.debit
        )
        wallet_3 = self.charge_exchange_wallet(
            self.user, currency=Currencies.ton, amount=50, tp=ExchangeWallet.WALLET_TYPE.debit
        )

        resp = self.client.get(self.URL)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data['status'] == 'ok'
        assert sorted(data['wallets'], key=lambda w: w['rialBalance'], reverse=True) == [
            {
                'activeBalance': '50',
                'balance': '50',
                'blockedBalance': '0',
                'currency': 'TON',
                'id': wallet_3.id,
                'rialBalance': 50 * TON_PRICE,
                'rialBalanceSell': 50 * TON_PRICE,
                'type': 20,
                'typeStr': 'DEBIT',
            },
            {
                'activeBalance': '100',
                'balance': '100',
                'blockedBalance': '0',
                'currency': 'USDT',
                'id': wallet_1.id,
                'rialBalance': 100 * USDT_PRICE,
                'rialBalanceSell': 100 * USDT_PRICE,
                'type': 20,
                'typeStr': 'DEBIT',
            },
            {
                'activeBalance': '200',
                'balance': '200',
                'blockedBalance': '0',
                'currency': 'AVAX',
                'id': wallet_2.id,
                'rialBalance': 0,
                'rialBalanceSell': 0,
                'type': 20,
                'typeStr': 'DEBIT',
            },
        ]
