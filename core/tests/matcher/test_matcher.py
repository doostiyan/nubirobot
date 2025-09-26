import datetime
import itertools
import json
import os.path
import pprint
import re
import typing
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings
from django.core.cache import cache
from django.db.models import F, Max, Min, Q, Sum
from django.test import override_settings
from django.utils import timezone
from django.utils.functional import cached_property

from exchange.accounts.models import User
from exchange.base.models import AMOUNT_PRECISIONS, PRICE_PRECISIONS, Currencies, Settings
from exchange.base.publisher import OrderPublishManager
from exchange.market.crons import FixAddAsyncTradeTransactionCron
from exchange.market.marketmanager import MarketManager
from exchange.market.models import Market, Order, OrderMatching
from exchange.market.orderbook import OrderBookGenerator
from exchange.market.tasks import task_batch_commit_trade_async_step, task_update_recent_trades_cache
from exchange.market.ws_serializers import serialize_order_for_user
from exchange.matcher.matcher import Matcher, post_processing_matcher_round
from exchange.usermanagement.block import BalanceBlockManager
from exchange.wallet.models import Wallet
from tests.matcher.base import FileBasedTestCase


class BaseTestMatcher(FileBasedTestCase):
    COMMANDS: typing.ClassVar = {
        'LOAD': re.compile(r'LOAD (?P<base_case>\S+)'),
        'ORDER': re.compile(
            r'(?P<order_id>\d+) (?P<order_type>BUY|SELL) (?P<amount>\S+) (?P<price>\S+)'
            r'(( \| (?P<pair_id>\d+) (?P<pair_price>\S+))? STOP (?P<param1>\S+))?',
        ),
        'MATCH': re.compile(r'MATCH (?P<taker>\d+) <= (?P<maker>\d+) (?P<amount>\S+) (?P<price>\S+)'),
        'CANCEL': re.compile(r'(?P<order_id>\d+) CANCELED'),
        'CHECK': re.compile(r'CHECK'),
        'EXPANSION': re.compile(r'EXPANSION buy (?P<b_len>\d+) sell (?P<s_len>\d+)'),
        'ORDERBOOK': re.compile(
            r'ORDERBOOK (?P<len>\d+)',
        ),
        'COMMENT': re.compile(r'#.*'),
    }

    USER_SIZE = 20

    def __init__(self, *args, **kwargs):
        self.deferred_matches = []
        self.manually_canceled = []

        super().__init__(*args, **kwargs)

    def setUp(self):
        self.deferred_matches = []
        self.manually_canceled = []
        cache.clear()
        Matcher._get_symbols_that_use_runtime_limit_logic.clear()

        super().setUp()

    @classmethod
    def setUpTestData(cls):
        market = Market.objects.create(
            id=0,
            src_currency=Currencies.unknown,
            dst_currency=Currencies.usdt,
            is_active=True,
        )
        AMOUNT_PRECISIONS[market.symbol] = Decimal('1e-1')
        PRICE_PRECISIONS[market.symbol] = Decimal('1e-1')
        if not Settings.get_dict('usd_value'):
            Settings.set_dict('usd_value', {'sell': 278100, 'buy': 277900})
        for i in range(cls.USER_SIZE):
            email = f'user{i}@matcher.test'
            user = User.objects.create(username=email, email=email)
            currency = market.src_currency if i % 2 else market.dst_currency
            balance = 150 if currency == market.src_currency else 15000
            Wallet.get_user_wallet(user, currency).create_transaction('manual', balance).commit()
        cls.market = market

    @cached_property
    def src_wallets(self):
        wallets = list(Wallet.objects.filter(currency=self.market.src_currency))
        for wallet in wallets:
            wallet.key_balance = wallet.balance
        return wallets

    @cached_property
    def dst_wallets(self):
        wallets = list(Wallet.objects.filter(currency=self.market.dst_currency))
        for wallet in wallets:
            wallet.key_balance = wallet.balance
        return wallets

    def get_user_wallet(self, order_type: int) -> Wallet:
        wallets = self.src_wallets if order_type == Order.ORDER_TYPES.sell else self.dst_wallets
        wallets.sort(key=lambda w: w.key_balance, reverse=True)
        return wallets[0]

    def run_test(self, test_input):
        cache.clear()
        Matcher.MARKET_LAST_PROCESSED_TIME = {}

        self.deferred_matches = []
        self.manually_canceled = []

        sell_expansion = None
        buy_expansion = None

        commands = test_input.splitlines()
        if commands and commands[-1] != 'CHECK':
            commands.append('CHECK')
        for command in commands:
            command_type, data = self.decode_command(command)
            if command_type == 'LOAD':
                self.load_base_case(data['base_case'])
            elif command_type == 'ORDER':
                self.create_order(**data)
            elif command_type == 'CANCEL':
                self.cancel_order(data['order_id'])
            elif command_type == 'MATCH':
                self.deferred_matches.append(data)
            elif command_type == 'EXPANSION':
                sell_expansion = int(data['s_len'])
                buy_expansion = int(data['b_len'])
            elif command_type == 'ORDERBOOK':
                self.run_orderbook(int(data['len']))
            elif command_type == 'CHECK':
                start_time = timezone.now()
                if self.deferred_matches:
                    assert Matcher.get_pending_markets().exists()
                while True:
                    matcher = Matcher(self.market)
                    matcher.do_matching_round()
                    if self.market.symbol in Matcher.get_symbols_that_use_async_stop_process():
                        post_processing_matcher_round(self.market, matcher.MARKET_PRICE_RANGE.get(self.market.id))
                    if matcher.report['matches'] < Matcher.MAX_TRADE_PER_ROUND:
                        break
                self.check_market_status(start_time)
                self.deferred_matches.clear()

                assert (
                    sell_expansion is None or matcher.rounds_of_sells_expansion == sell_expansion
                ), f'There are {matcher.rounds_of_sells_expansion} expansion for sells instead of {sell_expansion}'
                assert (
                    buy_expansion is None or matcher.rounds_of_buys_expansion == buy_expansion
                ), f'There are {matcher.rounds_of_buys_expansion} expansion for buys instead of {buy_expansion}'

                sell_expansion = None
                buy_expansion = None

    def decode_command(self, command):
        for command_type, pattern in self.COMMANDS.items():
            result = re.fullmatch(pattern, command)
            if result:
                return command_type, result.groupdict()
        raise ValueError(f'Unknown command: {command}')

    def check_market_status(self, from_time):
        try:
            self.check_order_matches(from_time)
            self.check_order_amounts()
            self.check_order_statuses(to_time=from_time)
        except AssertionError:
            self.print_order_matches()
            raise

    def check_order_matches(self, from_time):
        new_matches = (
            OrderMatching.objects.filter(created_at__gte=from_time)
            .values('sell_order_id', 'buy_order_id', 'matched_amount', 'matched_price', 'is_seller_maker')
            .order_by('id')
        )

        assert len(self.deferred_matches) == len(new_matches)

        for deferred_match, order_matching in zip(self.deferred_matches, new_matches):
            if order_matching['is_seller_maker']:
                assert order_matching['sell_order_id'] == int(deferred_match['maker'])
                assert order_matching['buy_order_id'] == int(deferred_match['taker'])
            else:
                assert order_matching['sell_order_id'] == int(deferred_match['taker'])
                assert order_matching['buy_order_id'] == int(deferred_match['maker'])
            assert order_matching['matched_amount'] == Decimal(deferred_match['amount'])
            assert order_matching['matched_price'] == Decimal(deferred_match['price'])

    @staticmethod
    def check_order_amounts():
        for order_type in ('sell', 'buy'):
            order_matches = (
                OrderMatching.objects.values(f'{order_type}_order_id')
                .annotate(
                    difference=Sum('matched_amount') - F(f'{order_type}_order__matched_amount'),
                )
                .values_list(f'{order_type}_order_id', 'difference')
                .distinct()
            )
            if not order_matches:
                continue
            matched_orders, amount_differences = zip(*list(order_matches))
            assert not any(amount_differences)
            assert not any(
                Order.objects.filter(
                    order_type=getattr(Order.ORDER_TYPES, order_type),
                )
                .exclude(id__in=matched_orders)
                .values_list('matched_amount', flat=True),
            )

    def check_order_statuses(self, to_time):
        for order in Order.objects.exclude(status=Order.STATUS.inactive).filter(created_at__lte=to_time):
            if not order.unmatched_amount:
                assert order.status == Order.STATUS.done
            elif (
                order.is_trivial
                or order.is_market
                or order.id in self.manually_canceled
                or order.pair_id in self.manually_canceled
                or (order.pair and order.pair.status in (Order.STATUS.active, Order.STATUS.done))
            ):
                assert order.status == Order.STATUS.canceled
            else:
                assert order.status == Order.STATUS.active

    def set_order_book_params(
        self,
        order_type: int,
        best_price: typing.Optional[str],
        last_price: typing.Optional[str],
    ):
        cache.set_many(
            {
                f'orderbook_{self.market.symbol}_best_active_{Order.ORDER_TYPES[order_type].lower()}': best_price,
                f'orderbook_{self.market.symbol}_last_active_{Order.ORDER_TYPES[order_type].lower()}': last_price,
            },
        )

    def get_order_book_params(
        self,
        order_type: int,
    ) -> typing.Tuple[str, str]:
        values = cache.get_many(
            [
                f'orderbook_{self.market.symbol}_best_active_{Order.ORDER_TYPES[order_type].lower()}',
                f'orderbook_{self.market.symbol}_last_active_{Order.ORDER_TYPES[order_type].lower()}',
            ],
        )

        return (
            values.get(
                f'orderbook_{self.market.symbol}_best_active_{Order.ORDER_TYPES[order_type].lower()}',
            )
            or '0',
            values.get(
                f'orderbook_{self.market.symbol}_last_active_{Order.ORDER_TYPES[order_type].lower()}',
            )
            or '0',
        )

    def load_base_case(self, base_case):
        path = os.path.join(settings.BASE_DIR, self.root, '..', f'{base_case}.txt')
        with open(path) as file:
            base_cases = file.read().strip().splitlines()
        for command in base_cases:
            command_type, data = self.decode_command(command)
            if command_type == 'ORDER':
                self.create_order(**data)
            elif command_type == 'CANCEL':
                self.cancel_order(data['order_id'])
            elif command_type == 'MATCH':
                self.match_orders(**data)
        self.run_orderbook()
        self.finalize_base_market_status()

    def create_order(self, order_id, order_type, amount, price, param1=None, pair_id=None, pair_price=None):
        order_type = getattr(Order.ORDER_TYPES, order_type.lower())
        wallet = self.get_user_wallet(order_type)
        order_params = {
            'user_id': wallet.user_id,
            'src_currency': self.market.src_currency,
            'dst_currency': self.market.dst_currency,
            'order_type': order_type,
            'amount': amount,
        }
        if not pair_id:
            execution_type = ('stop_' if param1 else '') + ('market' if price == 'MARKET' else 'limit')
            Order.objects.create(
                id=order_id,
                execution_type=getattr(Order.EXECUTION_TYPES, execution_type),
                price=param1 or self.get_order_book_params(3 - order_type)[0] if price == 'MARKET' else price,
                status=Order.STATUS.active if not param1 else Order.STATUS.inactive,
                param1=param1,
                **order_params,
            )
        else:
            Order.objects.create(
                id=order_id,
                execution_type=Order.EXECUTION_TYPES.limit,
                price=price,
                status=Order.STATUS.active,
                **order_params,
            )
            Order.objects.create(
                id=pair_id,
                execution_type=Order.EXECUTION_TYPES.stop_limit,
                price=pair_price,
                status=Order.STATUS.inactive,
                param1=param1,
                **order_params,
                pair_id=order_id,
            )
            Order.objects.filter(id=order_id).update(pair_id=pair_id)
        wallet.key_balance = wallet.balance - BalanceBlockManager.get_balance_in_order(wallet, use_cache=False)

    def cancel_order(self, order_id):
        Order.objects.get(id=order_id).do_cancel(manual=True)
        self.manually_canceled.append(int(order_id))

    def match_orders(self, maker, taker, amount, price):
        maker = Order.objects.get(id=maker)
        taker = Order.objects.get(id=taker)
        if maker.order_type == Order.ORDER_TYPES.sell:
            sell_order, buy_order, is_seller_maker = maker, taker, True
        else:
            sell_order, buy_order, is_seller_maker = taker, maker, False
        matching = OrderMatching.objects.create(
            market=self.market,
            sell_order=sell_order,
            buy_order=buy_order,
            seller_id=sell_order.user_id,
            buyer_id=buy_order.user_id,
            is_seller_maker=is_seller_maker,
            matched_amount=Decimal(amount),
            matched_price=Decimal(price),
            created_at=taker.created_at,
        )
        for order in (maker, taker):
            order.matched_amount += matching.matched_amount
            order.matched_total_price += matching.matched_total_price
            if order.unmatched_amount == 0:
                order.status = Order.STATUS.done
            order.save()

    def finalize_base_market_status(self):
        Order.objects.filter(
            execution_type=Order.EXECUTION_TYPES.market,
            status=Order.STATUS.active,
        ).update(status=Order.STATUS.canceled)
        last_active_order = Order.objects.filter(status=Order.STATUS.active).latest('created_at')

        Matcher.MARKET_LAST_PROCESSED_TIME[self.market.id] = last_active_order.created_at

        last_trade = OrderMatching.objects.last()
        cache.set('market_0_last_price', last_trade.matched_price if last_trade else None)

    def run_orderbook(self, length: int = 75):
        with patch('exchange.market.orderbook.OrderBook.SMALL_MARKET_SIZE', length), patch(
            'exchange.market.orderbook.OrderBook.MAX_ACTIVE_ORDERS',
            length,
        ):
            res = OrderBookGenerator.create_market_orderbooks(self.market)
            assert res is not None, 'failed to create market orderbook'

        # reading cache to log orderbook parameters
        orderbook_cache_keys = [
            f'orderbook_{self.market.symbol}_{kind}_active_{side}'
            for kind, side in itertools.product(('last', 'best'), ('buy', 'sell'))
        ] + [f'orderbook_{self.market.symbol}_update_time']
        print('ORDERBOOK:', pprint.pformat(cache.get_many(orderbook_cache_keys)))

    def update_market_status(
        self,
        best_buy: typing.Optional[str] = None,
        best_sell: typing.Optional[str] = None,
        last_buy: typing.Optional[str] = None,
        last_sell: typing.Optional[str] = None,
    ):
        self.set_order_book_params(Order.ORDER_TYPES.buy, best_buy, last_buy)
        self.set_order_book_params(Order.ORDER_TYPES.sell, best_sell, last_sell)

    @staticmethod
    def print_order_matches():
        current_matches = OrderMatching.objects.order_by('id').values(
            'sell_order_id',
            'buy_order_id',
            'is_seller_maker',
            'matched_amount',
            'matched_price',
        )
        for match in current_matches:
            taker = match['buy_order_id'] if match['is_seller_maker'] else match['sell_order_id']
            maker = match['sell_order_id'] if match['is_seller_maker'] else match['buy_order_id']
            amount = match['matched_amount'].normalize()
            price = match['matched_price'].normalize()
            print(f'MATCH {taker} <= {maker} {amount:f} {price:f}')


@pytest.mark.matcher
@patch('exchange.matcher.matcher.MARKET_ORDER_MAX_PRICE_DIFF', Decimal('0.01'))
class TestMatcher(BaseTestMatcher):
    root = 'tests/matcher/test_cases/main'

    def test_matcher_last_price_range(self):
        self.update_market_status(best_buy=99, best_sell=101)
        matcher = Matcher(self.market)
        assert not matcher.LAST_PRICE_RANGE
        matcher.update_last_price(100)
        assert matcher.LAST_PRICE_RANGE == [100, 100]
        matcher.update_last_price(100)
        assert matcher.LAST_PRICE_RANGE == [100, 100]
        matcher.update_last_price(99)
        assert matcher.LAST_PRICE_RANGE == [99, 100]
        matcher.update_last_price(Decimal('99.5'))
        assert matcher.LAST_PRICE_RANGE == [99, 100]
        matcher.update_last_price(98)
        assert matcher.LAST_PRICE_RANGE == [98, 100]
        matcher.update_last_price(101)
        assert matcher.LAST_PRICE_RANGE == [98, 101]
        matcher.update_last_price(100)
        assert matcher.LAST_PRICE_RANGE == [98, 101]
        matcher.update_last_price(0)
        assert matcher.LAST_PRICE_RANGE == [98, 101]

    def test_matcher_last_price_range_orderbook_check(self):
        self.update_market_status(best_buy=None, best_sell=None)
        matcher = Matcher(self.market)
        matcher.update_last_price(70)
        assert matcher.LAST_PRICE_RANGE == [70, 70]
        matcher.update_last_price(130)
        assert matcher.LAST_PRICE_RANGE == [70, 130]

        self.update_market_status(best_buy=99, best_sell=None)
        matcher = Matcher(self.market)
        matcher.update_last_price(70)
        assert matcher.LAST_PRICE_RANGE == []
        matcher.update_last_price(130)
        assert matcher.LAST_PRICE_RANGE == [130, 130]

        self.update_market_status(best_buy=None, best_sell=101)
        matcher = Matcher(self.market)
        matcher.update_last_price(70)
        assert matcher.LAST_PRICE_RANGE == [70, 70]
        matcher.update_last_price(130)
        assert matcher.LAST_PRICE_RANGE == [70, 70]

        self.update_market_status(best_buy=99, best_sell=101)
        matcher = Matcher(self.market)
        matcher.update_last_price(70)
        assert matcher.LAST_PRICE_RANGE == []
        matcher.update_last_price(130)
        assert matcher.LAST_PRICE_RANGE == []
        matcher.update_last_price(80)
        assert matcher.LAST_PRICE_RANGE == [80, 80]
        matcher.update_last_price(120)
        assert matcher.LAST_PRICE_RANGE == [80, 120]

    def test_matcher_inactive_wallets(self):
        self.create_order(1, 'SELL', 10, 101)
        self.create_order(2, 'BUY', 5, 101)
        order1, order2 = Order.objects.all().order_by('pk')
        # Deactivate buy dst wallet
        wallet = Wallet.get_user_wallet(order2.user, currency=self.market.dst_currency)
        wallet.is_active = False
        wallet.save(update_fields=('is_active',))
        # Run matcher
        Matcher(self.market).do_matching_round()
        for order in (order1, order2):
            order.refresh_from_db()
            assert not order.matched_amount
        assert order1.status == Order.STATUS.active
        assert order2.status == Order.STATUS.canceled

    def test_matcher_pending_market_pairs(self):
        matcher = Matcher(self.market)
        assert not Matcher.get_pending_markets().exists()
        self.create_order(1, 'SELL', '10', '100')
        assert not Matcher.get_pending_markets().exists()
        self.create_order(2, 'SELL', '10', '101')
        assert not Matcher.get_pending_markets().exists()
        self.create_order(3, 'BUY', '10', '99')
        assert not Matcher.get_pending_markets().exists()
        self.create_order(4, 'BUY', '10', '100')
        assert Matcher.get_pending_markets().exists()
        matcher.do_matching_round()
        if self.market.symbol in Matcher.get_symbols_that_use_async_stop_process():
            post_processing_matcher_round(self.market, matcher.MARKET_PRICE_RANGE.get(self.market.id))
        assert not Matcher.get_pending_markets().exists()
        self.create_order(5, 'SELL', '5', '99')
        assert Matcher.get_pending_markets().exists()
        matcher.do_matching_round()
        if self.market.symbol in Matcher.get_symbols_that_use_async_stop_process():
            post_processing_matcher_round(self.market, matcher.MARKET_PRICE_RANGE.get(self.market.id))
        assert not Matcher.get_pending_markets().exists()
        self.create_order(6, 'BUY', '5', 'MARKET')
        assert Matcher.get_pending_markets().exists()

    @override_settings(ASYNC_TRADE_COMMIT=True)
    @patch('django.db.transaction.on_commit', lambda t: t())
    def test_trade_transactions(self):
        matcher = Matcher(self.market)
        assert not matcher.get_pending_markets().exists()
        self.create_order(1, 'SELL', '10', '100')
        sell = Order.objects.get(id=1)
        self.create_order(2, 'BUY', '15', '100')
        buy = Order.objects.get(id=2)
        assert matcher.get_pending_markets().exists()
        matcher.do_matching_round()
        if self.market.symbol in Matcher.get_symbols_that_use_async_stop_process():
            post_processing_matcher_round(self.market, matcher.MARKET_PRICE_RANGE.get(self.market.id))
        trade = OrderMatching.objects.order_by('-id').last()
        assert trade
        assert trade.seller_id == sell.user_id
        assert trade.buyer_id == buy.user_id
        assert trade.sell_deposit_id is None
        assert trade.sell_withdraw_id is None
        assert trade.buy_deposit_id is None
        assert trade.buy_withdraw_id is None
        tx_ids = (cache.get(f'trade_{trade.id}_txids') or '').split(',')
        assert len(tx_ids) == 2
        sell_withdraw_id = int(tx_ids[0])
        buy_withdraw_id = int(tx_ids[1])
        # Run fix cron and recheck
        trade.created_at -= datetime.timedelta(minutes=31)
        trade.save(update_fields=['created_at'])
        FixAddAsyncTradeTransactionCron().run()
        trade.refresh_from_db()
        assert trade.sell_deposit_id
        assert 'فروش ' in trade.sell_deposit.description
        assert trade.sell_withdraw_id == sell_withdraw_id
        assert 'فروش ' in trade.sell_withdraw.description
        assert trade.buy_deposit_id
        assert 'خرید ' in trade.buy_deposit.description
        assert trade.buy_withdraw_id == buy_withdraw_id
        assert 'خرید ' in trade.buy_withdraw.description

    @override_settings(ASYNC_TRADE_COMMIT=True)
    @patch.object(task_update_recent_trades_cache, 'delay', task_update_recent_trades_cache)
    @patch('django.db.transaction.on_commit', lambda t: t())
    def test_trade_transactions_cache(self):
        assert not cache.get('trades_UNKNOWNUSDT')
        matcher = Matcher(self.market)
        assert not matcher.get_pending_markets().exists()
        self.create_order(1, 'SELL', '10', '100')
        Order.objects.get(id=1)
        self.create_order(2, 'BUY', '15', '100')
        Order.objects.get(id=2)
        assert matcher.get_pending_markets().exists()
        matcher.do_matching_round()
        if self.market.symbol in Matcher.get_symbols_that_use_async_stop_process():
            post_processing_matcher_round(self.market, matcher.MARKET_PRICE_RANGE.get(self.market.id))
        assert cache.get('trades_UNKNOWNUSDT')

    @patch('django.db.transaction.on_commit', lambda t: t())
    def test_bulk_save_orders(self):
        matcher = Matcher(self.market)
        assert not matcher.get_pending_markets().exists()
        self.create_order(1, 'SELL', '10', '100')
        sell = Order.objects.get(id=1)
        self.create_order(2, 'BUY', '15', '100')
        buy = Order.objects.get(id=2)
        assert matcher.get_pending_markets().exists()
        matcher.do_matching_round()
        if self.market.symbol in Matcher.get_symbols_that_use_async_stop_process():
            post_processing_matcher_round(self.market, matcher.MARKET_PRICE_RANGE.get(self.market.id))

        buy.refresh_from_db()
        sell.refresh_from_db()
        assert buy.fee
        assert sell.fee
        assert buy.status == Order.STATUS.active
        assert sell.status == Order.STATUS.done
        assert sell.matched_amount == 10
        assert buy.matched_amount == 10
        assert sell.matched_total_price == 1000
        assert buy.matched_total_price == 1000

    @patch('django.db.transaction.on_commit', lambda t: t())
    def test_bulk_save_market_orders_status(self):
        matcher = Matcher(self.market)
        assert not matcher.get_pending_markets().exists()
        self.create_order(1, 'SELL', '10', '100')
        sell = Order.objects.get(id=1)
        self.create_order(2, 'BUY', '15', 'MARKET')
        buy = Order.objects.get(id=2)
        self.create_order(3, 'SELL', '10', '200')
        sell2 = Order.objects.get(id=3)
        assert matcher.get_pending_markets().exists()
        matcher.do_matching_round()
        if self.market.symbol in Matcher.get_symbols_that_use_async_stop_process():
            post_processing_matcher_round(self.market, matcher.MARKET_PRICE_RANGE.get(self.market.id))
        buy.refresh_from_db()
        sell.refresh_from_db()
        sell2.refresh_from_db()
        assert buy.fee
        assert sell.fee
        assert buy.status == Order.STATUS.canceled
        assert sell.status == Order.STATUS.done
        assert sell2.status == Order.STATUS.active
        assert sell.matched_amount == 10
        assert sell2.matched_amount == 0
        assert buy.matched_amount == 10
        assert sell.matched_total_price == 1000
        assert buy.matched_total_price == 1000

    @override_settings(ASYNC_TRADE_COMMIT=True)
    @patch('django.db.transaction.on_commit', lambda t: t())
    @patch('exchange.matcher.matcher.task_batch_commit_trade_async_step.delay', new=task_batch_commit_trade_async_step)
    @patch('exchange.market.marketmanager.MarketManager.create_bulk_referral_fee')
    @patch('exchange.market.marketmanager.MarketManager.update_market_statistics')
    @patch('exchange.market.marketmanager.MarketManager.commit_trade_async_step')
    def test_update_market_statistics_be_called_once_per_round(
        self,
        async_step_mock: MagicMock,
        update_market_statistics_mock: MagicMock,
        create_bulk_referral_fee_mock: MagicMock,
    ):
        OrderMatching.objects.all().delete()
        matcher = Matcher(self.market)
        self.create_order(1, 'SELL', '10', '100')
        self.create_order(2, 'BUY', '5', '100')
        self.create_order(3, 'BUY', '5', '100')
        assert update_market_statistics_mock.call_count == 0
        assert async_step_mock.call_count == 0
        matcher.do_matching_round()
        if self.market.symbol in Matcher.get_symbols_that_use_async_stop_process():
            post_processing_matcher_round(self.market, matcher.MARKET_PRICE_RANGE.get(self.market.id))
        update_market_statistics_mock.assert_called_once()
        create_bulk_referral_fee_mock.assert_called_once()
        assert async_step_mock.call_count == 2
        last_trades = list(OrderMatching.objects.all())
        update_market_expected_arg = list(update_market_statistics_mock.call_args[0][0])
        bulk_referral_fee_arg = list(create_bulk_referral_fee_mock.call_args[0][0])
        assert bulk_referral_fee_arg == update_market_expected_arg == last_trades

    @patch('django.db.transaction.on_commit', lambda t: t())
    @patch('exchange.market.marketmanager.Market.by_symbol')
    @patch('exchange.market.marketmanager.cache')
    def test_update_recent_trades_cache_with_recent_trades(self, mock_cache, mock_market_by_symbol):
        symbol = self.market.symbol
        mock_cache.get.return_value = '[]'
        mock_market_by_symbol.return_value = self.market
        self.create_order(1, 'SELL', '10', '100')
        self.create_order(2, 'BUY', '10', '100')
        matcher = Matcher(self.market)
        matcher.do_matching_round()
        if self.market.symbol in Matcher.get_symbols_that_use_async_stop_process():
            post_processing_matcher_round(self.market, matcher.MARKET_PRICE_RANGE.get(self.market.id))
        recent_trades_json = MarketManager.update_recent_trades_cache(symbol)
        mock_cache.get.assert_called_with(f'trades_{symbol}', default='[]')
        mock_cache.set.assert_called_with(f'trades_{symbol}', recent_trades_json)
        recent_trades = json.loads(recent_trades_json)
        assert len(recent_trades) == 1
        trade_data = recent_trades[0]
        expected_keys = {'time', 'price', 'volume', 'type'}
        assert expected_keys.issubset(trade_data.keys())
        trade = OrderMatching.objects.latest('id')
        serialized_trade = MarketManager.serialize_trade_public_data(trade, symbol)
        assert trade_data == serialized_trade

    @patch('django.db.transaction.on_commit', lambda t: t())
    @patch('exchange.market.marketmanager.Market.by_symbol')
    @patch('exchange.market.marketmanager.cache')
    def test_update_recent_trades_cache_with_invalid_cache(self, mock_cache, mock_market_by_symbol):
        symbol = self.market.symbol
        mock_cache.get.return_value = 'invalid json'
        mock_market_by_symbol.return_value = self.market
        self.create_order(3, 'SELL', '5', '101')
        self.create_order(4, 'BUY', '5', '101')
        matcher = Matcher(self.market)
        matcher.do_matching_round()
        if self.market.symbol in Matcher.get_symbols_that_use_async_stop_process():
            post_processing_matcher_round(self.market, matcher.MARKET_PRICE_RANGE.get(self.market.id))
        recent_trades_json = MarketManager.update_recent_trades_cache(symbol)
        mock_cache.get.assert_called_with(f'trades_{symbol}', default='[]')
        mock_cache.set.assert_called_with(f'trades_{symbol}', recent_trades_json)
        recent_trades = json.loads(recent_trades_json)
        assert len(recent_trades) == 1

    @patch('exchange.market.marketmanager.Market.by_symbol')
    @patch('exchange.market.marketmanager.cache')
    def test_update_recent_trades_cache_with_no_trades(self, mock_cache, mock_market_by_symbol):
        symbol = self.market.symbol
        mock_cache.get.return_value = '[]'
        mock_market_by_symbol.return_value = self.market
        recent_trades_json = MarketManager.update_recent_trades_cache(symbol)
        mock_cache.get.assert_called_with(f'trades_{symbol}', default='[]')
        mock_cache.set.assert_called_with(f'trades_{symbol}', '[]')
        assert recent_trades_json == '[]'

    @patch('django.db.transaction.on_commit', lambda t: t())
    @patch('exchange.market.marketmanager.Market.by_symbol')
    @patch('exchange.market.marketmanager.cache')
    def test_update_recent_trades_cache_with_existing_cache(self, mock_cache, mock_market_by_symbol):
        symbol = self.market.symbol
        previous_trades = [
            {
                'time': int((timezone.now() - datetime.timedelta(minutes=1)).timestamp() * 1000),
            },
        ]
        mock_cache.get.return_value = json.dumps(previous_trades)
        mock_market_by_symbol.return_value = self.market
        self.create_order(5, 'SELL', '15', '102')
        self.create_order(6, 'BUY', '15', '102')
        matcher = Matcher(self.market)
        matcher.do_matching_round()
        if self.market.symbol in Matcher.get_symbols_that_use_async_stop_process():
            post_processing_matcher_round(self.market, matcher.MARKET_PRICE_RANGE.get(self.market.id))
        recent_trades_json = MarketManager.update_recent_trades_cache(symbol)
        mock_cache.get.assert_called_with(f'trades_{symbol}', default='[]')
        mock_cache.set.assert_called_with(f'trades_{symbol}', recent_trades_json)
        recent_trades = json.loads(recent_trades_json)
        total_trades = min(OrderMatching.objects.count(), 20)
        assert len(recent_trades) == total_trades
        last_trade_time = recent_trades[0]['time']
        latest_trade = OrderMatching.objects.latest('created_at')
        assert last_trade_time == int(latest_trade.created_at.timestamp() * 1000)

    @patch('django.db.transaction.on_commit', lambda t: t())
    @patch('exchange.market.marketmanager.Market.by_symbol')
    @patch('exchange.market.marketmanager.cache')
    def test_update_recent_trades_cache_created_at_gte(self, mock_cache, mock_market_by_symbol):
        """Test that trades with created_at equal to the boundary time are included."""
        symbol = self.market.symbol
        mock_market_by_symbol.return_value = self.market
        certain_timestamp = int(timezone.now().timestamp() * 1000)

        self.create_order(7, 'SELL', '20', '101')
        for i in range(18):
            self.create_order(i + 8, 'BUY', '1', '101')

        certain_datetime = timezone.datetime.fromtimestamp(certain_timestamp / 1000, tz=datetime.timezone.utc)
        with patch('exchange.matcher.matcher.timezone.now', return_value=certain_datetime):
            matcher = Matcher(self.market)
            matcher.do_matching_round()
            if self.market.symbol in Matcher.get_symbols_that_use_async_stop_process():
                post_processing_matcher_round(self.market, matcher.MARKET_PRICE_RANGE.get(self.market.id))

        mock_cache.get.return_value = '[]'
        recent_trades_json = MarketManager.update_recent_trades_cache(symbol)
        mock_cache.get.return_value = recent_trades_json

        new_trade_certain_datetime = timezone.datetime.fromtimestamp(
            1 + certain_timestamp / 1000,
            tz=datetime.timezone.utc,
        )
        with patch('exchange.matcher.matcher.timezone.now', return_value=new_trade_certain_datetime):
            self.create_order(37, 'SELL', '5', '101')
            self.create_order(38, 'BUY', '5', '101')
            matcher = Matcher(self.market)
            matcher.do_matching_round()
            if self.market.symbol in Matcher.get_symbols_that_use_async_stop_process():
                post_processing_matcher_round(self.market, matcher.MARKET_PRICE_RANGE.get(self.market.id))

        recent_trades_json = MarketManager.update_recent_trades_cache(symbol)
        recent_trades = json.loads(recent_trades_json)

        new_trade_time = int(new_trade_certain_datetime.timestamp() * 1000)

        assert new_trade_time == recent_trades[0]['time']
        assert len(recent_trades) == 19

    @patch('django.db.transaction.on_commit', lambda t: t())
    @patch('exchange.market.marketmanager.Market.by_symbol')
    @patch('exchange.market.marketmanager.cache')
    def test_update_recent_trades_cache_excludes_reversed_trades(self, mock_cache, mock_market_by_symbol):
        """Test that reversed trades (with matched_amount=0) are excluded."""
        symbol = self.market.symbol
        mock_cache.get.return_value = '[]'
        mock_market_by_symbol.return_value = self.market

        self.create_order(9, 'SELL', '10', '102')
        self.create_order(10, 'BUY', '10', '102')
        matcher = Matcher(self.market)
        matcher.do_matching_round()
        if self.market.symbol in Matcher.get_symbols_that_use_async_stop_process():
            post_processing_matcher_round(self.market, matcher.MARKET_PRICE_RANGE.get(self.market.id))

        trade = OrderMatching.objects.latest('id')

        recent_trades_json = MarketManager.update_recent_trades_cache(symbol)
        recent_trades = json.loads(recent_trades_json)
        assert len(recent_trades) == 1

        # reversing the trade
        trade.matched_amount = Decimal('0')
        trade.save(update_fields=['matched_amount'])
        for order in [trade.sell_order, trade.buy_order]:
            order.status = Order.STATUS.canceled
            order.matched_amount = Decimal('0')
            order.matched_total_price = Decimal('0')
            order.save(update_fields=['status', 'matched_amount', 'matched_total_price'])

        recent_trades_json = MarketManager.update_recent_trades_cache(symbol)
        recent_trades = json.loads(recent_trades_json)

        assert len(recent_trades) == 0



@pytest.mark.matcher
class TestMatcherBasics(BaseTestMatcher):
    """Basic and simple matcher tests based on METL tests.

        These tests can be used for including some fast matching test, or for
        developing new tests - put new tests in basics folder and develop them,
        then move them to final folder.
    """
    root = 'tests/matcher/test_cases/basics'


@pytest.mark.matcher
@pytest.mark.matcherFull
@patch('exchange.matcher.matcher.MARKET_ORDER_MAX_PRICE_DIFF', Decimal('0.01'))
class TestMatcherSupplement(BaseTestMatcher):
    root = 'tests/matcher/test_cases/supplement'


@pytest.mark.matcher
@override_settings(ENABLE_STOP_ORDERS=True)
@patch('exchange.matcher.matcher.MARKET_ORDER_MAX_PRICE_DIFF', Decimal('0.01'))
class TestMatcherStopLoss(BaseTestMatcher):
    root = 'tests/matcher/test_cases/stoploss'

    @patch('exchange.market.markprice.MarkPriceCalculator.get_mark_price', lambda *_: Decimal('100'))
    def test_mark_price_guard_activated(self):
        matcher = Matcher(self.market)
        self.create_order(1, 'SELL', '15', '100')
        self.create_order(2, 'BUY', '10', '100')
        self.create_order(3, 'BUY', '5', 'MARKET', '100')
        order = Order.objects.get(id=3)

        matcher.do_matching_round()

        post_processing_matcher_round(self.market, matcher.MARKET_PRICE_RANGE.get(self.market.id))

        order.refresh_from_db()
        assert order.status == Order.STATUS.active

    @patch('exchange.market.markprice.MarkPriceCalculator.get_mark_price', lambda *_: Decimal('10'))
    def test_mark_price_guard_not_activated(self):
        matcher = Matcher(self.market)
        self.create_order(1, 'SELL', '15', '100')
        self.create_order(2, 'BUY', '10', '100')
        self.create_order(3, 'BUY', '5', 'MARKET', '100')
        order = Order.objects.get(id=3)

        matcher.do_matching_round()

        post_processing_matcher_round(self.market, matcher.MARKET_PRICE_RANGE.get(self.market.id))

        order.refresh_from_db()
        assert order.status == Order.STATUS.inactive

@pytest.mark.matcher
class TestMatcherOCO(BaseTestMatcher):
    root = 'tests/matcher/test_cases/oco'


@pytest.mark.matcher
@patch('exchange.matcher.matcher.Matcher._do_expansion', lambda _: True)
@patch('exchange.matcher.matcher.Matcher.EXPANSION_STEP', 2)
class TestMatcherExpansion(BaseTestMatcher):
    """
    Matcher expansion feature tests derived from METL test cases.

    The Matcher will extend its behavior by fetching additional orders to fulfill partially matched ones.
    For more details, refer to: https://github.com/nobitex/core/issues/3639
    """

    root = 'tests/matcher/test_cases/expansion'

    @patch('django.db.transaction.on_commit', lambda t: t())
    def test_partially_filled_orders_expansion_not_enabled(self):
        matcher = Matcher(self.market)
        matcher.price_range_low = Decimal(90)
        matcher.price_range_high = Decimal(100)

        assert not matcher.get_pending_markets().exists()
        self.create_order(0, 'SELL', '10', '110')
        self.create_order(1, 'SELL', '10', '100')
        sell = Order.objects.get(id=1)
        self.create_order(2, 'BUY', '15', '110')
        buy = Order.objects.get(id=2)
        assert matcher.get_pending_markets().exists()

        with patch('exchange.matcher.matcher.Matcher._do_expansion', lambda _: False):
            matcher.do_matching_round()

        buy.refresh_from_db()
        sell.refresh_from_db()
        assert buy.fee
        assert sell.fee
        assert buy.status == Order.STATUS.active
        assert sell.status == Order.STATUS.done
        assert sell.matched_amount == 10
        assert buy.matched_amount == 10
        assert sell.matched_total_price == 1000
        assert buy.matched_total_price == 1000


@pytest.mark.matcher
@override_settings(ASYNC_TRADE_COMMIT=False)
class TestMatcherWebsocket(BaseTestMatcher):
    @patch('exchange.market.marketmanager.trades_publisher')
    def test_trades_publisher(self, mock_trades_publisher):
        matcher = Matcher(self.market)
        self.create_order(1, 'SELL', '10', '100')
        self.create_order(2, 'BUY', '15', '100')
        assert mock_trades_publisher.call_count == 0
        matcher.do_matching_round()
        if self.market.symbol in Matcher.get_symbols_that_use_async_stop_process():
            post_processing_matcher_round(self.market, matcher.MARKET_PRICE_RANGE.get(self.market.id))
        assert mock_trades_publisher.call_count == 1
        trade = OrderMatching.objects.order_by('-id').last()
        assert trade is not None
        mock_trades_publisher.assert_called_once_with(
            self.market.symbol,
            MarketManager.serialize_trade_public_data(trade, trade.symbol),
        )

    @patch('exchange.market.marketmanager.trades_publisher')
    def test_trades_publisher_on_multiple_trades(self, mock_trades_publisher):
        matcher = Matcher(self.market)
        self.create_order(1, 'SELL', '10', '100')
        self.create_order(2, 'BUY', '15', '100')
        self.create_order(3, 'SELL', '5', '100')
        self.create_order(4, 'BUY', '7', '100')
        self.create_order(5, 'SELL', '7', '100')
        assert mock_trades_publisher.call_count == 0
        matcher.do_matching_round()
        if self.market.symbol in Matcher.get_symbols_that_use_async_stop_process():
            post_processing_matcher_round(self.market, matcher.MARKET_PRICE_RANGE.get(self.market.id))
        assert mock_trades_publisher.call_count == 3
        trades = OrderMatching.objects.order_by('id')[:3]
        for trade in trades:
            mock_trades_publisher.assert_any_call(
                self.market.symbol,
                MarketManager.serialize_trade_public_data(trade, trade.symbol),
            )

    @patch.object(timezone, 'now', return_value=timezone.now())
    @patch.object(
        OrderPublishManager, 'add_order', wraps=lambda order, last_trade, user_uid: OrderPublishManager.add_order
    )
    @patch.object(OrderPublishManager, 'publish', wraps=lambda **kwargs: OrderPublishManager.publish)
    def test_order_publisher(self, mocked_publish, mocked_add_order, *_):

        matcher = Matcher(self.market)
        self.create_order(1, 'SELL', '10', '100')
        self.create_order(2, 'BUY', '10', '100')
        self.create_order(3, 'SELL', '5', '100')
        self.create_order(4, 'BUY', '5', '100')
        assert mocked_publish.call_count == 0
        matcher.do_matching_round()

        assert mocked_publish.call_count == 2
        assert mocked_add_order.call_count == 4
        trades = OrderMatching.objects.order_by('id')[:2]

        for trade in trades:
            mocked_add_order.assert_any_call(trade.buy_order, trade, trade.buy_order.user.uid)
            mocked_add_order.assert_any_call(trade.sell_order, trade, trade.sell_order.user.uid)

        serialized_order = serialize_order_for_user(trade.buy_order, trade)
        expected_data = {
            'orderId': trade.buy_order.id,
            'tradeId': trade.id,
            'clientOrderId': None,
            'srcCurrency': 'unknown',
            'dstCurrency': 'usdt',
            'eventTime': int(timezone.now().timestamp() * 1000),
            'lastFillTime': int(timezone.now().timestamp() * 1000),
            'side': 'Buy',
            'status': 'Done',
            'fee': '0.0065',
            'price': '100',
            'avgFilledPrice': '100',
            'tradePrice': '100',
            'amount': '5',
            'tradeAmount': '5',
            'filledAmount': '5',
            'param1': None,
            'orderType': 'Limit',
            'marketType': 'Spot',
        }
        assert serialized_order == expected_data

    @patch.object(timezone, 'now', return_value=timezone.now())
    @patch.object(OrderPublishManager, 'add_order')
    @patch.object(OrderPublishManager, 'publish')
    def test_orders_publisher_on_stop_orders(self, mocked_publish, mocked_add_order, *_):
        matcher = Matcher(self.market)
        self.create_order(1, 'SELL', '10', '100')
        self.create_order(2, 'BUY', '10', '100')

        self.create_order(3, 'SELL', '10', '99', param1='100')

        order = Order.objects.get(id=3)
        assert order.status == Order.STATUS.inactive
        matcher.do_matching_round()
        if self.market.symbol in Matcher.get_symbols_that_use_async_stop_process():
            post_processing_matcher_round(self.market, matcher.MARKET_PRICE_RANGE.get(self.market.id))

        order.refresh_from_db()
        assert order.status == Order.STATUS.active
        assert mocked_add_order.call_count == 3
        assert mocked_publish.call_count == 2

        mocked_add_order.assert_called_with(order, None, order.user.uid)

        serialized_order = serialize_order_for_user(order, None)
        expected_data = {
            'orderId': order.id,
            'tradeId': None,
            'clientOrderId': None,
            'srcCurrency': 'unknown',
            'dstCurrency': 'usdt',
            'eventTime': int(timezone.now().timestamp() * 1000),
            'lastFillTime': None,
            'side': 'Sell',
            'status': 'Active',
            'fee': '0',
            'price': '99',
            'avgFilledPrice': None,
            'tradePrice': None,
            'amount': '10',
            'tradeAmount': None,
            'filledAmount': '0',
            'param1': '100',
            'orderType': 'StopLimit',
            'marketType': 'Spot',
        }

        assert serialized_order == expected_data
