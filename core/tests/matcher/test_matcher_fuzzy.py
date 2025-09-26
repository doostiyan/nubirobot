import os.path
import random
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils.functional import cached_property

from exchange.market.constants import MARKET_ORDER_MAX_PRICE_DIFF
from exchange.market.models import Order
from tests.matcher.test_matcher import BaseTestMatcher


class FuzzyOrder:
    def __init__(self, pk):
        self.pk = pk
        self.matched_amount = 0
        self.guard_price = 0

    @cached_property
    def is_sell(self):
        return random.choice([True, False])

    @cached_property
    def is_market(self):
        return random.choices([True, False], weights=[0.3, 0.7])[0]

    @cached_property
    def order_type(self):
        return 'SELL' if self.is_sell else 'BUY'

    @cached_property
    def amount(self):
        values = list(range(5, 50))
        weights = [1 / (abs(v - 10) or 1) for v in values]
        return random.choices(values, weights=weights)[0]

    @cached_property
    def price(self):
        if self.is_market:
            return 'MARKET'
        values = [v / 10 for v in range(850, 1150)]
        weights = [1 / (abs(v - 100) or 0.1) + 1 - (v % 1) for v in values]
        return Decimal(f'{random.choices(values, weights=weights)[0]}')

    @property
    def unmatched_amount(self):
        return self.amount - self.matched_amount

    def __str__(self):
        return f'{self.order_type}: {self.price} ({self.unmatched_amount})'


class FuzzyMatcher:
    def __init__(self):
        self.sell_orders = []
        self.buy_orders = []
        self.recent_matches = set()
        self.best_sell = 0
        self.best_buy = 0

    def calculate_order_book(self):
        self.best_sell = self.sell_orders[0].price if self.sell_orders else 0
        self.best_buy = self.buy_orders[0].price if self.buy_orders else 0

    @property
    def min_market_sell(self):
        return (Decimal('1') - MARKET_ORDER_MAX_PRICE_DIFF) * self.best_buy

    @property
    def max_market_buy(self):
        return (Decimal('1') + MARKET_ORDER_MAX_PRICE_DIFF) * self.best_sell

    def match_order(self, order):
        matches = []
        if order.is_sell:
            makers = self.buy_orders
            order.guard_price = order.price if not order.is_market else self.min_market_sell
        else:
            makers = self.sell_orders
            order.guard_price = order.price if not order.is_market else self.max_market_buy
        if order.unmatched_amount:
            for maker in makers[:]:
                if not self.can_make_deal(order, maker):
                    break
                matching = self.deal_orders(order, maker)
                matches.append(matching)
                if not maker.unmatched_amount:
                    makers.remove(maker)
                if not order.unmatched_amount:
                    break
        self.add_order(order)
        return matches

    @staticmethod
    def can_make_deal(taker, maker):
        bad_price = (taker.guard_price > maker.price) if taker.is_sell else (taker.guard_price < maker.price)
        skip_price_check = taker.is_market and not taker.guard_price
        return skip_price_check or not bad_price

    def deal_orders(self, taker, maker):
        matched_amount = min(taker.unmatched_amount, maker.unmatched_amount)
        taker.matched_amount += matched_amount
        maker.matched_amount += matched_amount
        self.recent_matches |= {taker.pk, maker.pk}
        return taker, maker, matched_amount

    def add_order(self, order):
        if not order.unmatched_amount or order.is_market:
            return
        orders = self.sell_orders if order.is_sell else self.buy_orders
        orders.append(order)
        orders.sort(key=lambda o: o.price, reverse=not order.is_sell)

    def cancel_order(self, order):
        if order.is_sell:
            self.sell_orders.remove(order)
        else:
            self.buy_orders.remove(order)

    @property
    def active_orders(self):
        return self.sell_orders + self.buy_orders

    @property
    def has_orders(self):
        return bool(self.sell_orders or self.buy_orders)


@pytest.mark.interactive
@pytest.mark.matcher
@pytest.mark.matcherFull
class TestMatcherFuzzily(BaseTestMatcher):
    """
    Create random testcase of size `TEST_ORDER_SIZE` orders and evaluate them one after the other.
    To finish testcase generation, press `Ctrl+C`.
    On failure, testcase is saved in root folder. On next run, previously failed test is run instead.
    To restart normal behavior after a failure is resolved, delete the test-fuzzy.txt file.
    """

    root = 'tests/matcher/test_cases/fuzzy'
    TEST_ORDER_SIZE = 400
    BASE_ORDER_SIZE = 100

    @classmethod
    def setUpClass(cls):
        super(TestMatcherFuzzily, cls).setUpClass()
        if not os.path.exists(cls.root):
            os.mkdir(cls.root)

    def test_fuzzy(self):
        try:
            while True:
                test_input = self.create_test_case()
                try:
                    self.run_test(test_input)
                except AssertionError as e:
                    self.write_to_file(test_input, 'test-fuzzy')
                    raise e
                self.clean_up()
                input('PASS [Enter to continue, Ctrl+C to break]')
        except KeyboardInterrupt:
            print('Terminating...')

    def create_test_case(self):
        matcher = FuzzyMatcher()
        commands = ['# fuzzy test']
        base_test = self.create_base_case(matcher)
        self.write_to_file(base_test, '../base-fuzzy')
        commands.append('LOAD base-fuzzy')
        for i in range(self.BASE_ORDER_SIZE, self.TEST_ORDER_SIZE):
            order = FuzzyOrder(i)
            commands.append(self.get_order_command(order))
            commands.extend(self.get_match_commands(matcher, order))
            if random.random() < 0.5:
                commands.append(self.get_check_command(matcher))
            if random.random() < 0.5:
                commands.append(self.get_orderbook_command(matcher))
            if random.random() < 0.1:
                commands.extend(self.get_cancel_commands(matcher))
        return '\n'.join(commands)

    def create_base_case(self, matcher):
        commands = ['# fuzzy base test']
        for i in range(1, self.BASE_ORDER_SIZE):
            order = FuzzyOrder(i)
            commands.append(self.get_order_command(order))
            commands.extend(self.get_match_commands(matcher, order))
            matcher.calculate_order_book()
            if random.random() < 0.1:
                commands.extend(self.get_cancel_commands(matcher))
        return '\n'.join(commands)

    @staticmethod
    def get_order_command(order):
        return f'{order.pk} {order.order_type} {order.amount} {order.price}'

    @staticmethod
    def get_match_commands(matcher, order):
        matches = matcher.match_order(order)
        return [f'MATCH {taker.pk} <= {maker.pk} {amount} {maker.price}' for taker, maker, amount in matches]

    @staticmethod
    def get_orderbook_command(matcher):
        matcher.calculate_order_book()
        return f'ORDERBOOK active buy {matcher.best_buy} sell {matcher.best_sell}'

    @staticmethod
    def get_check_command(matcher):
        matcher.recent_matches.clear()
        return 'CHECK'

    @classmethod
    def get_cancel_commands(cls, matcher):
        commands = []
        if matcher.has_orders:
            active_order = random.choice(matcher.active_orders)
            if active_order.pk in matcher.recent_matches:
                commands.append(cls.get_check_command(matcher))
            matcher.cancel_order(active_order)
            commands.append(f'{active_order.pk} CANCELED')
        return commands

    def write_to_file(self, data, name):
        with open(os.path.join(self.root, f'{name}.txt'), 'w+') as file:
            file.write(data)
            file.write('\n')

    def remove_file(self, name):
        os.remove(os.path.join(self.root, f'{name}.txt'))

    def clean_up(self):
        Order.objects.all().delete()
        self.remove_file('../base-fuzzy')
