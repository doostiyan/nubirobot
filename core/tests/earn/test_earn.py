import uuid
from decimal import Decimal
from typing import Optional

import responses
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies, Settings
from exchange.earn.external import get_user_abc_debit_wallets_balances
from exchange.pool.models import LiquidityPool, UserDelegation
from exchange.staking.exportables import _get_blocked_balances
from exchange.staking.models import ExternalEarningPlatform, Plan, StakingTransaction
from exchange.wallet.models import Wallet as ExchangeWallet


class EarnBalancesAPITest(APITestCase):
    user: User

    @classmethod
    def setUpTestData(cls):
        now = timezone.now()
        a_day = timezone.timedelta(days=1)

        cls.user = User.objects.get(pk=201)

        # Pool delegations
        pools = [
            LiquidityPool.objects.create(currency=Currencies.btc, capacity=10, manager_id=410, is_active=True, activated_at=ir_now()),
            LiquidityPool.objects.create(currency=Currencies.ltc, capacity=50, manager_id=411, is_active=True, activated_at=ir_now()),
        ]
        UserDelegation.objects.create(pool=pools[0], user=cls.user, balance='0.7')
        UserDelegation.objects.create(pool=pools[1], user=cls.user, balance='0', closed_at=now)
        UserDelegation.objects.create(pool=pools[1], user=cls.user, balance='3.2')
        UserDelegation.objects.create(pool=pools[1], user_id=202, balance='13')

        # Stakings
        external_platforms = [
            ExternalEarningPlatform.objects.create(tp=ExternalEarningPlatform.TYPES.staking, currency=Currencies.sol),
            ExternalEarningPlatform.objects.create(tp=ExternalEarningPlatform.TYPES.staking, currency=Currencies.btc),
        ]
        plan_kwargs = dict(
            announced_at=now, opened_at=now, staked_at=now, request_period=a_day, unstaking_period=a_day,
            reward_announcement_period=a_day, initial_pool_capacity=1000, is_extendable=True,
        )
        staking_plans = [
            Plan.objects.create(external_platform=external_platforms[0], staking_period=7 * a_day, **plan_kwargs),
            Plan.objects.create(external_platform=external_platforms[0], staking_period=30 * a_day, **plan_kwargs),
            Plan.objects.create(external_platform=external_platforms[1], staking_period=14 * a_day, **plan_kwargs),
        ]
        transaction_kwargs = dict(tp=StakingTransaction.TYPES.create_request)
        StakingTransaction.objects.create(plan=staking_plans[0], user=cls.user, amount='36', **transaction_kwargs)
        StakingTransaction.objects.create(plan=staking_plans[1], user=cls.user, amount='52', **transaction_kwargs)
        StakingTransaction.objects.create(plan=staking_plans[2], user=cls.user, amount='0.4', **transaction_kwargs)
        StakingTransaction.objects.create(plan=staking_plans[2], user_id=202, amount='1.2', **transaction_kwargs)

        cls.set_orderbook_prices('btc', 1_580_000_000_0, 1_590_000_000_0)
        cls.set_orderbook_prices('ltc', 4_880_000_0, 4_900_000_0)
        cls.set_orderbook_prices('sol', 1_230_000_0, 1_250_000_0)
        cls.set_orderbook_prices('usdt', 80000, 81000)

    @staticmethod
    def set_orderbook_prices(currency_code: str, best_buy: int, best_sell: int):
        cache.set(f'orderbook_{currency_code.upper()}IRT_best_active_buy', Decimal(best_buy))
        cache.set(f'orderbook_{currency_code.upper()}IRT_best_active_sell', Decimal(best_sell))

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        _get_blocked_balances.cache_clear()

    @responses.activate
    def test_earn_balances(self):
        Settings.set('earn_get_abc_wallets_by_internal_api', 'yes')

        responses.get(
            url='https://testnetapi.nobitex.ir/internal/asset-backed-credit/wallets/debit/balances',
            json={'status': 'ok', 'wallets': {Currencies.usdt: '100', Currencies.btc: '0.1'}},
            match=[responses.matchers.query_param_matcher({'user_id': str(self.user.uid)})],
        )

        response = self.client.get(f'/earn/balances')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'

        assert len(data['balances']) == 4
        for currency in ('btc', 'ltc', 'sol', 'usdt'):
            assert currency in data['balances']

        assert len(data['balances']['btc']) == 3
        assert data['balances']['btc']['staking']['balance'] == '0.4'
        assert data['balances']['btc']['staking']['rialBalance'] == 6320000000
        assert data['balances']['btc']['liquidityPool']['balance'] == '0.7'
        assert data['balances']['btc']['liquidityPool']['rialBalance'] == 11060000000
        assert data['balances']['btc']['debit']['balance'] == '0.1'
        assert data['balances']['btc']['debit']['rialBalance'] == 1580000000
        assert data['balances']['btc']['debit']['rialBalanceSell'] == 1590000000

        assert len(data['balances']['ltc']) == 1
        assert data['balances']['ltc']['liquidityPool']['balance'] == '3.2'
        assert data['balances']['ltc']['liquidityPool']['rialBalance'] == 156160000

        assert len(data['balances']['sol']) == 1
        assert data['balances']['sol']['staking']['balance'] == '88'
        assert data['balances']['sol']['staking']['rialBalance'] == 1082400000

        assert len(data['balances']['usdt']) == 1
        assert data['balances']['usdt']['debit']['balance'] == '100'
        assert data['balances']['usdt']['debit']['rialBalance'] == 8000000
        assert data['balances']['usdt']['debit']['rialBalanceSell'] == 8100000

    def test_earn_balances_with_function_call(self):
        self.charge_debit_wallet(self.user, Currencies.usdt, Decimal('200'))
        self.charge_debit_wallet(self.user, Currencies.btc, Decimal('0.2'))

        response = self.client.get(f'/earn/balances')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'

        assert len(data['balances']) == 4
        for currency in ('btc', 'ltc', 'sol', 'usdt'):
            assert currency in data['balances']

        assert len(data['balances']['btc']) == 3
        assert data['balances']['btc']['staking']['balance'] == '0.4'
        assert data['balances']['btc']['staking']['rialBalance'] == 6320000000
        assert data['balances']['btc']['liquidityPool']['balance'] == '0.7'
        assert data['balances']['btc']['liquidityPool']['rialBalance'] == 11060000000
        assert data['balances']['btc']['debit']['balance'] == '0.2'
        assert data['balances']['btc']['debit']['rialBalance'] == 3160000000
        assert data['balances']['btc']['debit']['rialBalanceSell'] == 3180000000

        assert len(data['balances']['ltc']) == 1
        assert data['balances']['ltc']['liquidityPool']['balance'] == '3.2'
        assert data['balances']['ltc']['liquidityPool']['rialBalance'] == 156160000

        assert len(data['balances']['sol']) == 1
        assert data['balances']['sol']['staking']['balance'] == '88'
        assert data['balances']['sol']['staking']['rialBalance'] == 1082400000

        assert len(data['balances']['usdt']) == 1
        assert data['balances']['usdt']['debit']['balance'] == '200'
        assert data['balances']['usdt']['debit']['rialBalance'] == 16000000
        assert data['balances']['usdt']['debit']['rialBalanceSell'] == 16200000

    @staticmethod
    def charge_debit_wallet(user, currency, amount, tp=ExchangeWallet.WALLET_TYPE.debit):
        wallet = ExchangeWallet.get_user_wallet(user, currency, tp=tp)
        wallet.create_transaction(tp='manual', amount=amount).commit()
        wallet.refresh_from_db()
        return wallet

    @responses.activate
    def test_get_user_abc_debit_wallets_balances_response_not_ok(self):
        Settings.set('earn_get_abc_wallets_by_internal_api', 'yes')
        user_id = uuid.uuid4()

        responses.get(
            url='https://testnetapi.nobitex.ir/internal/asset-backed-credit/wallets/debit/balances',
            json={},
            match=[responses.matchers.query_param_matcher({'user_id': user_id})],
            status=status.HTTP_400_BAD_REQUEST,
        )
        wallets = get_user_abc_debit_wallets_balances(user_id=user_id)
        assert wallets == {}
