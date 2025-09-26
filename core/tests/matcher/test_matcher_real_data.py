import datetime
import re
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.cache import cache

from exchange.accounts.models import User
from exchange.margin.models import Position, PositionOrder
from exchange.market.models import Market, Order, OrderMatching
from exchange.matcher.management.commands.concurrent_matcher import ConcurrentMatcher
from exchange.matcher.matcher import Matcher
from exchange.pool.models import LiquidityPool
from exchange.wallet.models import Wallet
from tests.matcher.base import MultipleFileBasedTestCase


def initializer_process():
    return None

class MarketRound:

    PATTERNS = {
        'MARKET': re.compile(r'Market: (?P<src>\d+) (?P<dst>\d+) (?P<symbol>\w+)'),
        'LAST_PROCESSED': re.compile(r'Last processed time: (?P<dt>.+)'),
        'ORDERBOOK': re.compile(
            r"OrderBook: \{'buy': Decimal\('(?P<best_buy>.+)'\), 'sell': Decimal\('(?P<best_sell>.+)'\)\}"
        ),
        'ORDER': re.compile(
            r'#(?P<id>\d+) (?P<created_at>\S+) (?P<amount>\S+) (?P<price>\S+) (?P<user_id>\d+) (?P<status>\d)'
            r' (?P<execution_type>\d+) (?P<trade_type>\d) (?P<matched_amount>\S+) (?P<param1>\S+) (?P<pair_id>\S+)'
            r' (?P<channel>\S+)'
        ),
        'START_TIME': re.compile(r'Start: (?P<dt>.+)'),
        'MATCH': re.compile(
            r'Match #(?P<sell_order_id>\d+) x #(?P<buy_order_id>\d+) (?P<amount>\S+) (?P<price>\S+)'
            r' (?P<is_seller_maker>\S+)'
        ),
        'WALLET': re.compile(
            r'Wallet: (?P<order_id>\d+) (?P<user_id>\d+) (?P<currency>\d+) (?P<wallet_type>\d+) '
            r'(?P<balance>\S+) (?P<balance_blocked>\S+)'
        ),
    }

    def __init__(self, test_input):
        self.test_input = test_input
        self.market = None
        self.orders_data = {'sells': [], 'buys': []}
        self.matches = []
        self.effective_time = None
        self.final_orders_data = []

    def process_data(self):
        lines = iter(self.test_input.split('\n'))

        self.market = self.create_market(**self.get_data(next(lines), 'MARKET'))

        last_time = self.get_datetime(self.get_data(next(lines), 'LAST_PROCESSED')['dt'])
        Matcher.MARKET_LAST_PROCESSED_TIME[self.market.id] = last_time

        self.set_orderbook_values(self.market.symbol, **self.get_data(next(lines), 'ORDERBOOK'))

        assert next(lines) == 'sells'
        while (line := next(lines))[0] == '#':
            self.orders_data['sells'].append(self.get_data(line, 'ORDER'))
        assert line == 'buys'
        while (line := next(lines))[0] == '#':
            self.orders_data['buys'].append(self.get_data(line, 'ORDER'))
        self.create_orders(self.market, **self.orders_data)

        self.effective_time = self.get_datetime(self.get_data(line, 'START_TIME')['dt'])

        wallets_states = defaultdict(list)
        position_orders = {'sells': [], 'buys': []}
        while line := next(lines):
            if line == 'sells':
                break
            if line.startswith('Wallet'):
                wallet_data = self.get_data(line, 'WALLET')
                wallets_states[tuple(int(wallet_data[key]) for key in ('user_id', 'currency', 'wallet_type'))].append(
                    {key: Decimal(wallet_data[key]) for key in ('balance', 'balance_blocked')}
                )
                user_id = int(wallet_data['user_id'])
                if user_id == 400 + self.market.src_currency:
                    position_orders['sells'].append(wallet_data['order_id'])
                elif user_id == 400 + self.market.dst_currency:
                    position_orders['buys'].append(wallet_data['order_id'])
            if line.startswith('Match'):
                self.matches.append(self.get_data(line, 'MATCH'))

        Position.objects.filter(orders__in=position_orders['sells']).update(side=Position.SIDES.sell)
        Position.objects.filter(orders__in=position_orders['buys']).update(side=Position.SIDES.buy)

        self.final_orders_data = []
        while (line := next(lines))[0] == '#':
            self.final_orders_data.append(self.get_data(line, 'ORDER'))
        assert line == 'buys'
        while (line := next(lines))[0] == '#':
            self.final_orders_data.append(self.get_data(line, 'ORDER'))

        return wallets_states

    @classmethod
    def get_data(cls, line, pattern_type) -> dict:
        result = re.fullmatch(cls.PATTERNS[pattern_type], line)
        if result:
            return result.groupdict()
        raise ValueError(f'Invalid pattern {pattern_type} for "{line}"')

    @classmethod
    def create_market(cls, src, dst, symbol) -> Market:
        market = Market.objects.get_or_create(src_currency=int(src), dst_currency=int(dst))[0]
        for currency in (int(src), int(dst)):
            LiquidityPool.objects.get_or_create(currency=currency, manager=cls.create_user(400 + currency), capacity=10)
        return market

    @staticmethod
    def create_user(user_id) -> User:
        email = f'user-{user_id}@matcher.test'
        return User.objects.get_or_create(pk=user_id, defaults={'username': email, 'email': email})[0]

    @staticmethod
    def get_datetime(datetime_string) -> datetime.datetime:
        if datetime_string == 'None':
            return None
        return datetime.datetime.fromisoformat(datetime_string)

    @staticmethod
    def set_orderbook_values(symbol, best_buy, best_sell) -> dict:
        cache.set(f'orderbook_{symbol}_best_active_buy', Decimal(best_buy))
        cache.set(f'orderbook_{symbol}_best_active_sell', Decimal(best_sell))

    @classmethod
    def create_orders(cls, market, sells, buys):
        orders = []
        positions = []
        position_orders = []

        for order_type, orders_data in ((Order.ORDER_TYPES.sell, sells), (Order.ORDER_TYPES.buy, buys)):
            for order_data in orders_data:
                sub_orders, position = cls.create_order(market=market, order_type=order_type, **order_data)
                orders.extend(sub_orders)
                if position:
                    positions.append(position)
                    position_orders.extend(PositionOrder(position=position, order=order) for order in sub_orders)

        created_times = [order.created_at for order in orders]
        Order.objects.bulk_create(orders)
        for order, created_time in zip(orders, created_times):
            order.created_at = created_time
        Order.objects.bulk_update(orders, fields=('created_at',))

        Position.objects.bulk_create(positions)
        PositionOrder.objects.bulk_create(position_orders)

    @classmethod
    def create_order(
        cls,
        market,
        id,
        created_at,
        amount,
        price,
        user_id,
        status,
        order_type,
        execution_type,
        trade_type,
        matched_amount,
        param1,
        pair_id,
        channel,
    ) -> tuple:
        order = Order(
            id=int(id),
            created_at=cls.get_datetime(created_at),
            src_currency=market.src_currency,
            dst_currency=market.dst_currency,
            amount=Decimal(amount),
            price=Decimal(price),
            user=cls.create_user(user_id),
            status=int(status),
            order_type=order_type,
            execution_type=int(execution_type),
            trade_type=int(trade_type),
            matched_amount=Decimal(matched_amount),
            param1=Decimal(param1) if param1 != 'None' else None,
            channel=int(channel) if channel != 'None' else None,
        )
        position = None

        if order.is_margin:
            position = Position(
                src_currency=market.src_currency,
                dst_currency=market.dst_currency,
                collateral=order.matched_total_price,
                side=order.order_type,
                user_id=order.user_id,
            )

        if pair_id == 'None':
            return (order,), position

        if order.is_sell ^ (order.execution_type in Order.STOP_EXECUTION_TYPES):
            price_change = Decimal('0.9')
        else:
            price_change = Decimal('1.1')
        pair = Order.objects.create(
            id=int(pair_id),
            created_at=order.created_at,
            src_currency=market.src_currency,
            dst_currency=market.dst_currency,
            amount=Decimal(amount),
            price=Decimal(price) * price_change,
            user=order.user,
            status=Order.STATUS.canceled if order.param1 or order.matched_amount else Order.STATUS.inactive,
            order_type=order_type,
            execution_type=Order.EXECUTION_TYPES.limit if order.param1 else Order.EXECUTION_TYPES.stop_limit,
            trade_type=order.trade_type,
            matched_amount=Decimal(0),
            param1=None if order.param1 else Decimal(price) * price_change,
            channel=order.channel,
            pair_id=order.id,
        )
        order.pair = pair
        return (order, pair), position


@pytest.mark.interactive
@pytest.mark.matcher
@pytest.mark.matcherFull
class TestMatcherRealData(MultipleFileBasedTestCase):
    """
    Run a round of real matcher data.
    """

    root = 'tests/matcher/logs/simple_test'

    @classmethod
    def run_test(cls, test_inputs):
        cache.clear()
        markets_round = [MarketRound(test_input) for test_input in test_inputs]

        wallets_states = {}
        markets = []
        for market_round in markets_round:
            wallets_states.update(market_round.process_data())
            markets.append(market_round.market)

        get_user_wallet = Wallet.get_user_wallet

        def get_user_wallet_mock(user, currency, tp, *, create=True):
            wallet_states = wallets_states.get((user if isinstance(user, int) else user.id, currency, tp))
            wallet = get_user_wallet(user, currency, tp, create=create)
            if not wallet_states:
                return wallet
            if diff := wallet_states[0]['balance'] - wallet.balance:
                wallet.create_transaction('manual', diff, allow_negative_balance=True).commit(
                    allow_negative_balance=True
                )
            return wallet

        # Run matcher
        with patch.object(Wallet, 'get_user_wallet', get_user_wallet_mock), patch(
            'exchange.matcher.matcher.timezone.now', return_value=markets_round[0].effective_time
        ), patch('exchange.matcher.timer.ENV_TIMING_ENABLED', True):
            cls.run_concurrent_matcher(markets)

        for market_round in markets_round:
            cls.check_matches(market_round.matches, market_round.market)
            orders = Order.objects.in_bulk()
            for order_data in market_round.final_orders_data:
                cls.check_order(orders.get(int(order_data['id'])), **order_data)

    @staticmethod
    @patch(
        'exchange.matcher.divider.CONCURRENT_MATCHER_MARKET_SYMBOLS',
        ('BTCIRT', 'BTCUSDT', 'ETHUSDT', 'ETHIRT'),
    )
    def run_concurrent_matcher(markets):
        with ProcessPoolExecutor(max_workers=2, initializer=initializer_process) as executor:
            executor.submit(print, ('Process Pool Started',))
            ConcurrentMatcher(executor).run_matcher_round(markets, False, time.time())

    @staticmethod
    def check_matches(expected_matches, market):
        matches = OrderMatching.objects.filter(market=market).order_by('id')
        assert len(matches) == len(expected_matches)
        for match, expected_matches in zip(matches, expected_matches):
            assert match.sell_order_id == int(expected_matches['sell_order_id'])
            assert match.buy_order_id == int(expected_matches['buy_order_id'])
            assert match.is_seller_maker == (expected_matches['is_seller_maker'] == 'True')
            assert match.matched_amount == Decimal(expected_matches['amount'])
            assert match.matched_price == Decimal(expected_matches['price'])

    @staticmethod
    def check_order(order, status, matched_amount, **kwargs):
        assert order.status == int(status)
        assert order.matched_amount == Decimal(matched_amount)
