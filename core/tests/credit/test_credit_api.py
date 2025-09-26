from decimal import Decimal
from datetime import datetime

from django.test import TestCase
from django.utils.timezone import timedelta
from django.core.cache import cache

from exchange.base.calendar import ir_now
from exchange.base.models import Currencies
from exchange.base.money import money_is_close_decimal
from exchange.accounts.models import User
from exchange.wallet.models import Wallet, WithdrawRequest
from exchange.features.models import QueueItem

from exchange.credit import models
from exchange.credit import helpers

from tests.base.utils import set_initial_values
from tests.credit.utils import BaseApiTest


class LendApiTest(BaseApiTest):
    url = '/credit/lend'

    @classmethod
    def setUpTestData(cls) -> None:
        return super().setUpTestData()

    def setUp(self):
        super().setUp()
        set_initial_values()
        cache.set('orderbook_USDTIRT_best_active_buy', Decimal('440_000'))
        self.nobitex_last_order_price = (
            cache.get('settings_prices_binance_futures')['btc'] + cache.get('okx_prices')['btc']
        ) / 2
        cache.set(f'orderbook_BTCUSDT_best_active_buy', Decimal(self.nobitex_last_order_price * 1.005))
        cache.set(f'orderbook_BTCUSDT_best_active_sell', Decimal(self.nobitex_last_order_price * .995))

    def test_successful_call(self):
        response = self.client.post(path=self.url, data={'amount': '.02', 'currency': 'btc'},).json()
        assert response['status'] == 'ok'
        transaction = models.CreditTransaction.objects.order_by('-id').first()
        assert transaction.created_at == datetime.fromisoformat(response['result']['createdAt'])
        del response['result']['createdAt']
        assert response['result'] == {
            'amount': '0.02',
            'currency': 'btc',
            'id': transaction.id,
            'type': 'lend',
        }

    def test_low_user_collateral(self):
        self.wallet.balance = 0
        self.wallet.save(update_fields=('balance',))
        response = self.client.post(path=self.url, data={'amount': '.02', 'currency': 'btc'},).json()
        assert response['status'] == 'failed'
        assert response['code'] == 'NotEnoughCollateral'

    def test_user_lending_limit(self):
        self.plan.credit_limit_in_usdt = Decimal('100')
        self.plan.save()
        response = self.client.post(path=self.url, data={'amount': '.02', 'currency': 'btc'},).json()
        assert response['status'] == 'failed'
        assert response['code'] == 'CreditLimit'

    def test_no_system_budget(self):
        self.system_wallet.balance = 0.01
        self.system_wallet.save(update_fields=('balance',))
        response = self.client.post(path=self.url, data={'amount': '.02', 'currency': 'btc'},).json()
        assert response['status'] == 'failed'
        assert response['code'] == 'CreditLimit'

    def test_no_available_price(self):
        cache.delete('settings_prices_binance_futures')
        cache.delete('okx_prices')
        response = self.client.post(path=self.url, data={'amount': '.02', 'currency': 'btc'},).json()
        assert response['status'] == 'failed'
        assert response['code'] == 'UnavailablePrice'

    def test_no_active_plan(self):
        self.plan.expires_at = ir_now()
        self.plan.save()
        response = self.client.post(path=self.url, data={'amount': '.02', 'currency': 'btc'},).json()
        assert response['status'] == 'failed'
        assert response['code'] == 'NoCreditPlan'


class RepayApiTest(BaseApiTest):
    url = '/credit/repay'

    @classmethod
    def setUpTestData(cls) -> None:
        return super().setUpTestData()

    def setUp(self):
        super().setUp()
        set_initial_values()
        cache.set('orderbook_USDTIRT_best_active_buy', Decimal('440_000'))
        self.nobitex_last_order_price = (
            cache.get('settings_prices_binance_futures')['btc'] + cache.get('okx_prices')['btc']
        ) / 2
        cache.set(f'orderbook_BTCUSDT_best_active_buy', Decimal(self.nobitex_last_order_price * 1.005))
        cache.set(f'orderbook_BTCUSDT_best_active_sell', Decimal(self.nobitex_last_order_price * .995))

        self.client.post(path='/credit/lend', data={'amount': '.03', 'currency': 'btc'},).json()

    def test_successful_call(self):
        response = self.client.post(path=self.url, data={'amount': '.02', 'currency': 'btc'},).json()
        assert response['status'] == 'ok'
        transaction = models.CreditTransaction.objects.order_by('-id').first()
        assert transaction.created_at == datetime.fromisoformat(response['result']['createdAt'])
        del response['result']['createdAt']
        assert response['result'] == {
            'amount': '0.02',
            'currency': 'btc',
            'id': transaction.id,
            'type': 'repay',
        }

    def test_low_user_balance(self):
        self.wallet.balance = 0
        self.wallet.save(update_fields=('balance',))
        response = self.client.post(path=self.url, data={'amount': '.02', 'currency': 'btc'},).json()
        assert response['status'] == 'failed'
        assert response['code'] == 'CantTransferAsset'

    def test_over_repaying(self):
        response = self.client.post(path=self.url, data={'amount': '.04', 'currency': 'btc'},).json()
        assert response['status'] == 'failed'
        assert response['code'] == 'InvalidAmount'


class CreditGetApisTest(TestCase):

    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = User.objects.get(pk=201)
        QueueItem.objects.create(feature=QueueItem.FEATURES.vip_credit, user=cls.user, status=QueueItem.STATUS.done,)
        cls.plan = models.CreditPlan.objects.create(**{
            'user': cls.user,
            'starts_at': ir_now() - timedelta(days=1),
            'expires_at': ir_now() + timedelta(days=1),
            'maximum_withdrawal_percentage': Decimal('.5'),
            'credit_limit_percentage': Decimal('.3'),
            'credit_limit_in_usdt': Decimal('1000'),
        })

        set_initial_values()
        binance_prices = cache.get('settings_prices_binance_futures')
        binance_prices['btc'] = Decimal('10')
        binance_prices['eth'] = Decimal('3')
        binance_prices['xrp'] = Decimal('.2')
        cache.set('settings_prices_binance_futures', binance_prices)
        okx_prices = cache.get('okx_prices')
        okx_prices['btc'] = Decimal('10.02')
        okx_prices['eth'] = Decimal('3.001')
        okx_prices['xrp'] = Decimal('.2')
        cache.set('okx_prices', okx_prices)
        Wallet.objects.filter(user_id__in=(cls.user.id, helpers.get_system_user_id(),)).update(balance=Decimal('0'))
        _ = Wallet.get_user_wallet(user=cls.user, currency=Currencies.btc)
        _ = Wallet.get_user_wallet(user=cls.user, currency=Currencies.eth)
        _ = Wallet.get_user_wallet(user=cls.user, currency=Currencies.usdt)
        _ = Wallet.get_user_wallet(user=helpers.get_system_user_id(), currency=Currencies.btc)
        _ = Wallet.get_user_wallet(user=helpers.get_system_user_id(), currency=Currencies.eth)
        _ = Wallet.get_user_wallet(user=helpers.get_system_user_id(), currency=Currencies.xrp)
        Wallet.objects.filter(
            user_id=cls.user.id, currency=Currencies.btc, type=Wallet.WALLET_TYPE.spot,
        ).update(balance=Decimal('3'))
        Wallet.objects.filter(
            user_id=cls.user.id, currency=Currencies.eth, type=Wallet.WALLET_TYPE.spot,
        ).update(balance=Decimal('10'))
        Wallet.objects.filter(
            user_id=cls.user.id, currency=Currencies.usdt, type=Wallet.WALLET_TYPE.spot,
        ).update(balance=Decimal('1173'))
        Wallet.objects.filter(
            user_id=helpers.get_system_user_id(), currency=Currencies.btc, type=Wallet.WALLET_TYPE.spot,
        ).update(balance=Decimal('1'))
        Wallet.objects.filter(
            user_id=helpers.get_system_user_id(), currency=Currencies.eth, type=Wallet.WALLET_TYPE.spot,
        ).update(balance=Decimal('1000'))
        Wallet.objects.filter(
            user_id=helpers.get_system_user_id(), currency=Currencies.xrp, type=Wallet.WALLET_TYPE.spot,
        ).update(balance=Decimal('151'))

        cls.transactions = models.CreditTransaction.objects.bulk_create((models.CreditTransaction(
            plan=cls.plan, currency=Currencies.btc, tp=models.CreditTransaction.TYPES.lend, amount=Decimal('11'),
        ), models.CreditTransaction(
            plan=cls.plan, currency=Currencies.btc, tp=models.CreditTransaction.TYPES.lend, amount=Decimal('12'),
        ), models.CreditTransaction(
            plan=cls.plan, currency=Currencies.btc, tp=models.CreditTransaction.TYPES.repay, amount=Decimal('3'),
        ), models.CreditTransaction(
            plan=cls.plan, currency=Currencies.eth, tp=models.CreditTransaction.TYPES.lend, amount=Decimal('11'),
        ),),)

    def setUp(self) -> None:
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.user.auth_token.key}'

    def test_user_debt_detail_view(self):
        url = '/credit/debt-detail'
        assert self.client.get(path=url).json()['result'] == {
            'totalAssetsValue': '1000',
            'totalDebtValue': '233',
            'debts': {
                'btc': {
                    'amount': '20',
                    'value': '200'
                },
                'eth': {
                    'amount': '11',
                    'value': '33'
                },
            }
        }

    def test_user_credit_plan_view(self):
        url = '/credit/plan'
        response = self.client.get(url).json()['result']
        assert datetime.fromisoformat(response['startsAt']) == self.plan.starts_at
        assert datetime.fromisoformat(response['expiresAt']) == self.plan.expires_at
        assert response['maximumWithdrawalPercentage'] == str(self.plan.maximum_withdrawal_percentage)
        assert response['creditLimitPercentage'] == str(self.plan.credit_limit_percentage)
        assert response['creditLimitInUsdt'] == str(self.plan.credit_limit_in_usdt)

    def test_user_history_view(self):
        url = '/credit/transactions'
        assert self.client.get(url).json()['hasNext'] is False
        assert len(self.client.get(url).json()['result']) == 4
        received = self.client.get(url).json()['result'][0]
        trx = models.CreditTransaction.objects.order_by('created_at').last()
        assert received == {
            'id': trx.id,
            'type': 'lend',
            'currency': 'eth',
            'createdAt': trx.created_at.isoformat(),
            'amount': '11',
        }

    def test_lending_calculator_view(self):
        url = '/credit/lend-calculator'
        lending_amounts = self.client.get(url).json()['result']
        assert set(lending_amounts.keys()) == {'btc', 'eth', 'xrp'}
        for currency, amount in (
            ('btc', Decimal('1'),),
            ('eth', Decimal('22.27763923524'),),
            ('xrp', Decimal('151'),),
        ):
            assert money_is_close_decimal(Decimal(lending_amounts[currency]), amount)

    def test_withdraw_calculator_view(self):
        url = '/credit/withdraw-calculator'
        assert self.client.get(url).json()['result'] == {
            'btc': '3',
            'eth': '10',
            'usdt': '532.6683291771',
        }
