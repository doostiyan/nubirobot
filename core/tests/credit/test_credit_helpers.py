from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
import pytest

from exchange.base.calendar import ir_now
from exchange.base.models import Currencies
from exchange.accounts.models import User
from exchange.wallet.models import Wallet, WithdrawRequest
from exchange.credit.helpers import get_user_net_worth, get_user_debt_worth, ToUsdtConvertor
from exchange.credit.models import CreditPlan, CreditTransaction
from exchange.credit import errors

from tests.base.utils import set_initial_values


class GetUserNetWorthTest(TestCase):
    # Due to Sensitivity lets dont mock responses of Wallet and WithdrawRequests queries.

    @classmethod
    def setUpTestData(cls) -> None:
        cls.user_id = User.objects.create_user(username='credit-test-user').id
        Wallet.objects.filter(user_id=cls.user_id).delete()
        cls.currencies = (Currencies.btc, Currencies.eth, Currencies.usdt)
        cls.prices = [Decimal('10'), Decimal('5'), Decimal('1'), ]
        cls.wallets = []
        for currency in cls.currencies:
            wallet = Wallet.objects.create(user_id=cls.user_id, currency=currency, type=Wallet.WALLET_TYPE.spot)
            cls.wallets.append(wallet)

    def setUp(self) -> None:
        for wallet, balance in zip(GetUserNetWorthTest.wallets, (Decimal('1'), Decimal('5'), Decimal('3'),)):
            wallet.balance = balance
        Wallet.objects.bulk_update(GetUserNetWorthTest.wallets, fields=('balance',),)
        self.withdraw_requests = WithdrawRequest.objects.bulk_create([
            WithdrawRequest(wallet=wallet, status=WithdrawRequest.STATUS.sent, amount=amount)
            for wallet, amount in zip(
                (GetUserNetWorthTest.wallets[0], GetUserNetWorthTest.wallets[2],),
                (Decimal('1'), Decimal('1'),),
            )
        ])

    @patch('exchange.credit.helpers.ToUsdtConvertor.get_price')
    def test_a_successful_call(self, get_usdt_price_mock):
        get_usdt_price_mock.side_effect = self.prices[1:]
        assert get_user_net_worth(self.user_id) == Decimal('27')

    @patch('exchange.credit.helpers.ToUsdtConvertor.get_price')
    def test_wallet_type(self, get_usdt_price_mock):
        get_usdt_price_mock.side_effect = self.prices[1:] + [Decimal('2')]
        Wallet.objects.create(
            user_id=self.user_id, currency=Currencies.xrp, type=Wallet.WALLET_TYPE.margin, balance=Decimal('10'),
        )
        assert get_user_net_worth(self.user_id) == Decimal('27')

    @patch('exchange.credit.helpers.ToUsdtConvertor.get_price')
    def test_wallet_blocked_balance(self, get_usdt_price_mock):
        get_usdt_price_mock.side_effect = self.prices[1:]
        for wallet, balance in zip(GetUserNetWorthTest.wallets, (Decimal('2'), Decimal('4'), Decimal('6'),)):
            wallet.balance_blocked = balance
        Wallet.objects.bulk_update(GetUserNetWorthTest.wallets, fields=('balance',),)
        assert get_user_net_worth(self.user_id) == Decimal('27')

    @patch('exchange.credit.helpers.ToUsdtConvertor.get_price')
    def test_wallet_user(self, get_usdt_price_mock):
        get_usdt_price_mock.side_effect = self.prices[1:]
        other_user_id = User.objects.create_user(username='other-credit-test-user').id
        Wallet.objects.filter(user_id=other_user_id).update(balance=Decimal('10'))
        Wallet.objects.bulk_update(GetUserNetWorthTest.wallets, fields=('balance',),)
        assert get_user_net_worth(self.user_id) == Decimal('27')

    @patch('exchange.credit.helpers.ToUsdtConvertor.get_price')
    def test_withdraw_request_inclusive_types(self, get_usdt_price_mock):
        get_usdt_price_mock.side_effect = self.prices[1:]
        wallet = GetUserNetWorthTest.wallets[-1]
        price = self.prices[-1]
        states = [
            WithdrawRequest.STATUS.verified,
            WithdrawRequest.STATUS.accepted,
            WithdrawRequest.STATUS.sent,
            WithdrawRequest.STATUS.done,
            WithdrawRequest.STATUS.processing,
            WithdrawRequest.STATUS.waiting,
            WithdrawRequest.STATUS.manual_accepted,
        ]
        wallet.balance += Decimal(len(states))
        wallet.save(update_fields=('balance',))
        WithdrawRequest.objects.bulk_create([
            WithdrawRequest(wallet=wallet, status=status, amount=Decimal('1'))
            for status in states
        ])
        assert get_user_net_worth(self.user_id) == Decimal('27')

    @patch('exchange.credit.helpers.ToUsdtConvertor.get_price')
    def test_withdraw_request_exclusives_types(self, get_usdt_price_mock):
        get_usdt_price_mock.side_effect = self.prices[1:]
        wallet = GetUserNetWorthTest.wallets[-1]
        states = [WithdrawRequest.STATUS.new, WithdrawRequest.STATUS.canceled, WithdrawRequest.STATUS.rejected]
        WithdrawRequest.objects.bulk_create([
            WithdrawRequest(wallet=wallet, status=status, amount=Decimal('1'))
            for status in states
        ])
        assert get_user_net_worth(self.user_id) == Decimal('27')

    @patch('exchange.credit.helpers.ToUsdtConvertor.get_price')
    def test_withdraw_transaction(self, get_usdt_price_mock):
        get_usdt_price_mock.side_effect = self.prices[1:]
        transaction = self.wallets[2].create_transaction(
            tp='withdraw',
            amount=Decimal('-1'),
        )
        assert transaction is not None
        transaction.save()
        withdraw_request = self.withdraw_requests[-1]
        withdraw_request.transaction = transaction
        withdraw_request.save(update_fields=('transaction',))
        assert get_user_net_worth(self.user_id) == Decimal('27') + self.prices[2] * withdraw_request.amount

    @patch('exchange.credit.helpers.ToUsdtConvertor.get_price')
    def test_withdraw_wallet(self, get_usdt_price_mock):
        get_usdt_price_mock.side_effect = self.prices[1:]
        other_user_id = User.objects.create_user(username='other-credit-test-user').id
        wallet = Wallet.get_user_wallet(user=other_user_id, currency=Currencies.xrp)
        WithdrawRequest.objects.create(wallet=wallet, status=WithdrawRequest.STATUS.sent, amount=Decimal('1'))
        assert get_user_net_worth(self.user_id) == Decimal('27')

    @patch('exchange.credit.helpers.ToUsdtConvertor.get_price')
    def test_unavailable_price(self, get_usdt_price_mock):
        get_usdt_price_mock.side_effect = [errors.UnavailablePrice("")] + self.prices[2:3]
        assert get_user_net_worth(self.user_id) == Decimal('2')


class GetUserDebtWorthTest(TestCase):
    # Due to Sensitivity lets dont mock responses of DB queries.

    @classmethod
    def setUpTestData(cls) -> None:
        cls.currencies = (Currencies.btc, Currencies.eth,)
        cls.prices = [Decimal('10'), Decimal('3')]
        cls.user_id = 201
        cls.plan = CreditPlan.objects.create(
            user_id=cls.user_id,
            starts_at=ir_now(),
            expires_at=ir_now(),
            maximum_withdrawal_percentage=Decimal('.50'),
            credit_limit_percentage=Decimal('.20'),
            credit_limit_in_usdt=Decimal('1000'),
        )

    @patch('exchange.credit.helpers.ToUsdtConvertor.get_price')
    def test_a_successful_call(self, get_usdt_price_mock,):
        get_usdt_price_mock.side_effect = self.prices
        CreditTransaction.objects.bulk_create([CreditTransaction(
            plan=GetUserDebtWorthTest.plan,
            currency=currency,
            tp=tp,
            amount=amount,
        ) for currency, tp, amount, in (
            (self.currencies[0], CreditTransaction.TYPES.lend, Decimal('1'),),
            (self.currencies[0], CreditTransaction.TYPES.lend, Decimal('8'),),
            (self.currencies[0], CreditTransaction.TYPES.repay, Decimal('2'),),
            (self.currencies[1], CreditTransaction.TYPES.lend, Decimal('15'),),
            (self.currencies[1], CreditTransaction.TYPES.repay, Decimal('12'),),
        )])
        assert get_user_debt_worth(self.user_id) == Decimal('79')


class GetUsdtPriceTest(TestCase):

    def setUp(self) -> None:
        set_initial_values()
        self.nobitex_last_order_price = (
            cache.get('settings_prices_binance_futures')['btc'] + cache.get('okx_prices')['btc']
        ) / 2
        cache.set(f'orderbook_BTCUSDT_best_active_buy', Decimal(self.nobitex_last_order_price * 1.005))
        cache.set(f'orderbook_BTCUSDT_best_active_sell', Decimal(self.nobitex_last_order_price * .995))

    def test_both_binance_and_okx_are_available(self):
        assert ToUsdtConvertor(Currencies.btc).get_price() == Decimal(cache.get('settings_prices_binance_futures')['btc'])

    def test_unavailable_binance_price(self):
        cache.delete('settings_prices_binance_futures')
        assert ToUsdtConvertor(Currencies.btc).get_price() == Decimal(cache.get('okx_prices')['btc'])

    def test_unavailable_okx_price(self):
        cache.delete('okx_prices')
        assert ToUsdtConvertor(Currencies.btc).get_price() == Decimal(cache.get('settings_prices_binance_futures')['btc'])

    def test_invalid_binance_price(self):
        binance_prices = cache.get('settings_prices_binance_futures')
        binance_prices['btc'] *= 1.1
        cache.set('settings_prices_binance_futures', binance_prices)
        assert ToUsdtConvertor(Currencies.btc).get_price() == Decimal(cache.get('okx_prices')['btc'])

    def test_invalid_okx_price(self):
        okx_prices = cache.get('okx_prices')
        okx_prices['btc'] *= 1.1
        cache.set('okx_prices', okx_prices)
        assert ToUsdtConvertor(Currencies.btc).get_price() == Decimal(cache.get('settings_prices_binance_futures')['btc'])

    def test_price_is_not_available(self):
        binance_prices = cache.get('settings_prices_binance_futures')
        binance_prices['btc'] *= 1.1
        cache.set('settings_prices_binance_futures', binance_prices)
        okx_prices = cache.get('okx_prices')
        okx_prices['btc'] /= 1.1
        cache.set('okx_prices', okx_prices)
        with pytest.raises(errors.UnavailablePrice):
            ToUsdtConvertor(Currencies.btc).get_price()
