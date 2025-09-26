from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase

from exchange.accounts.models import User
from exchange.base.models import Currencies
from exchange.market.models import Market, Order
from exchange.wallet.models import Wallet
from tests.base.utils import create_order, do_matching_round


class MatchingTest(TestCase):
    def assert_matched(self, order, amount, total):
        order.refresh_from_db()
        filled = order.amount == order.matched_amount
        expected_status = Order.STATUS.done if filled else Order.STATUS.active
        if order.is_market and not filled:
            expected_status = Order.STATUS.canceled
        assert order.status == expected_status
        assert order.matched_amount == Decimal(amount)
        assert order.matched_total_price == Decimal(total)

    def test_matching_basic_1(self):
        user1 = User.objects.get(pk=201)
        user2 = User.objects.get(pk=202)
        btc, rls = Currencies.btc, Currencies.rls
        market = Market.objects.get(src_currency=btc, dst_currency=rls)
        o1 = create_order(user1, btc, rls, Decimal('0.12'), Decimal('40e6'), sell=True)
        o2 = create_order(user2, btc, rls, Decimal('0.12'), Decimal('40e6'), sell=False)
        do_matching_round(market)
        o1.refresh_from_db()
        o2.refresh_from_db()
        assert o1.status == Order.STATUS.done
        assert o1.unmatched_amount == Decimal(0)
        assert o2.status == Order.STATUS.done
        assert o2.unmatched_amount == Decimal(0)

    def test_matching_basic_2(self):
        user1 = User.objects.get(pk=201)
        user2 = User.objects.get(pk=202)
        eth, rls = Currencies.eth, Currencies.rls
        market = Market.objects.get(src_currency=eth, dst_currency=rls)
        o1 = create_order(user1, eth, rls, Decimal('1.5'), Decimal('11000000'), sell=False)
        o2 = create_order(user2, eth, rls, Decimal('0.7'), Decimal('10500000'), sell=True)
        o3 = create_order(user2, eth, rls, Decimal('1'), Decimal('11000000'), sell=True)
        do_matching_round(market)
        for order in (o1, o2, o3):
            order.refresh_from_db()
        assert o1.status == Order.STATUS.done
        assert o1.unmatched_amount == Decimal(0)
        assert o2.status == Order.STATUS.done
        assert o2.unmatched_amount == Decimal(0)
        assert o3.status == Order.STATUS.active
        assert o3.unmatched_amount == Decimal('0.2')

    def test_matching_market_1(self):
        user1 = User.objects.get(pk=201)
        user2 = User.objects.get(pk=202)
        eth, rls = Currencies.eth, Currencies.rls
        market = Market.objects.get(src_currency=eth, dst_currency=rls)
        best_active_price = Decimal(10999999)
        cache.set('orderbook_ETHIRT_best_active_sell', best_active_price)
        cache.set('orderbook_ETHIRT_best_active_buy', best_active_price)
        o1 = create_order(user1, eth, rls, Decimal('1.4'), Decimal('10749999'), sell=True)
        o2 = create_order(user1, eth, rls, Decimal('1.6'), Decimal('10999999'), sell=True)
        o3 = create_order(user2, eth, rls, Decimal('1.9'), None, balance=Decimal('20425000'), sell=False, market=True)
        do_matching_round(market)
        for order in (o1, o2, o3):
            order.refresh_from_db()
        assert o1.status == Order.STATUS.done
        assert o1.unmatched_amount == Decimal(0)
        assert o2.status == Order.STATUS.active
        assert o2.matched_amount == Decimal('0.48863')
        assert o2.unmatched_amount == Decimal('1.11137')
        assert o3.status == Order.STATUS.canceled
        assert o3.matched_amount == Decimal('1.88863')
        assert o3.unmatched_amount == Decimal('0.01137')
        cache.delete('orderbook_ETHIRT_best_active_sell')
        cache.delete('orderbook_ETHIRT_best_active_buy')

    def test_matching_market_2(self):
        user1 = User.objects.get(pk=201)
        user2 = User.objects.get(pk=202)
        eth, rls = Currencies.eth, Currencies.rls
        market = Market.objects.get(src_currency=eth, dst_currency=rls)
        best_active_price = Decimal(10999999)
        cache.set('orderbook_ETHIRT_best_active_sell', best_active_price)
        cache.set('orderbook_ETHIRT_best_active_buy', best_active_price)
        o1 = create_order(user1, eth, rls, Decimal('1.4'), Decimal('10749999'), sell=True)
        o2 = create_order(user1, eth, rls, Decimal('1.6'), Decimal('10999999'), sell=True)
        o3 = create_order(
            user2,
            eth,
            rls,
            Decimal('1.9'),
            None,
            balance=Decimal('40850000'),
            sell=False,
            market=True,
            charge_ratio=Decimal(2),
        )
        do_matching_round(market)
        for order in (o1, o2, o3):
            order.refresh_from_db()
        assert o1.status == Order.STATUS.done
        assert o1.unmatched_amount == Decimal(0)
        assert o2.status == Order.STATUS.active
        assert o2.unmatched_amount == Decimal('1.1')
        assert o3.status == Order.STATUS.done
        assert o3.unmatched_amount == Decimal(0)
        cache.delete('orderbook_ETHIRT_best_active_sell')
        cache.delete('orderbook_ETHIRT_best_active_buy')

    def test_matching_market_range_buy_whole_balance(self):
        user1 = User.objects.get(pk=201)
        user2 = User.objects.get(pk=202)
        xrp, rls = Currencies.xrp, Currencies.rls
        market = Market.objects.get(src_currency=xrp, dst_currency=rls)
        # Create two orders (ranges)
        o1 = create_order(user1, xrp, rls, Decimal('10301'), Decimal('33970'), sell=True)
        o2 = create_order(user1, xrp, rls, Decimal('20000'), Decimal('34490'), sell=True)
        # Create the market order
        wallet_rls = Wallet.get_user_wallet(user2, rls)
        tr1 = wallet_rls.create_transaction(tp='manual', amount=Decimal('51_199_348_0'))
        tr1.commit()
        o3, o3_status = Order.create(
            user=user2,
            order_type=Order.ORDER_TYPES.buy,
            execution_type=Order.EXECUTION_TYPES.market,
            src_currency=xrp,
            dst_currency=rls,
            amount=Decimal('15000'),
            price=Decimal('34490'),
        )
        assert o3_status is None
        do_matching_round(market)
        for order in (o1, o2, o3):
            order.refresh_from_db()
        assert o1.matched_amount == Decimal('10301')
        assert o1.status == Order.STATUS.done
        assert o2.matched_amount == Decimal('4699')
        assert o2.status == Order.STATUS.active
        assert o3.matched_amount == Decimal('15000')
        assert o3.status == Order.STATUS.done

    def test_matching_market_over_buy(self):
        user1 = User.objects.get(pk=201)
        user2 = User.objects.get(pk=202)
        usdt, rls = Currencies.usdt, Currencies.rls
        market = Market.objects.get(src_currency=usdt, dst_currency=rls)
        # Create orders
        o1 = create_order(user1, usdt, rls, Decimal('20000'), Decimal('11390'), sell=True)
        wallet_rls = Wallet.get_user_wallet(user2, rls)
        tr1 = wallet_rls.create_transaction(tp='manual', amount=Decimal('20_000_000_0'))
        tr1.commit()
        o2, o2_status = Order.create(
            user=user2,
            order_type=Order.ORDER_TYPES.buy,
            execution_type=Order.EXECUTION_TYPES.market,
            src_currency=usdt,
            dst_currency=rls,
            amount=Decimal('17600'),
            price=Decimal('11360'),
        )
        assert o2_status is None
        do_matching_round(market)
        o1.refresh_from_db()
        o2.refresh_from_db()
        assert o1.matched_amount == Decimal('17559.26')
        assert o1.status == Order.STATUS.active
        assert o2.matched_amount == Decimal('17559.26')
        assert o2.status == Order.STATUS.canceled

    def test_matching_creation_priority(self):
        user1 = User.objects.get(pk=201)
        user2 = User.objects.get(pk=202)
        user3 = User.objects.get(pk=203)
        btc, rls = Currencies.btc, Currencies.rls
        market = Market.objects.get(src_currency=btc, dst_currency=rls)
        o1 = create_order(user1, btc, rls, Decimal('0.2'), Decimal('1191482000'), sell=False)
        o2 = create_order(user2, btc, rls, Decimal('0.4'), Decimal('1191482000'), sell=False)
        o3 = create_order(user3, btc, rls, Decimal('0.05'), Decimal('1191482000'), sell=True)
        o4 = create_order(user3, btc, rls, Decimal('0.05'), Decimal('1191482000'), sell=True)
        o5 = create_order(user3, btc, rls, Decimal('0.4'), Decimal('1191482000'), sell=True)
        do_matching_round(market)
        for order in (o1, o2, o3, o4, o5):
            order.refresh_from_db()
        assert o1.status == Order.STATUS.done
        assert o1.matched_amount == Decimal('0.2')
        assert o2.status == Order.STATUS.active
        assert o2.matched_amount == Decimal('0.3')
        assert o3.status == Order.STATUS.done
        assert o3.matched_amount == Decimal('0.05')
        assert o4.status == Order.STATUS.done
        assert o4.matched_amount == Decimal('0.05')
        assert o5.status == Order.STATUS.done
        assert o5.matched_amount == Decimal('0.4')

    def test_matching_small_overbuy(self):
        """There was a bug when a user with balance=165.9708289322USDT placed a limit order of
        9992.2232951896TRX @ 0.01661USDT which was fully matched (OrderMatching#655760) and
        resulted in balance=-0.0000000009USDT for the user.
        Aside from why the user was able to place order with such amount precision, the problem
        checked here is the overbuy. Probably the problem was because of another bug affecting
        active balance calculation. So this test case does not simulate the exact bug that
        resulted in the negative balance, bust just creates same orders to document the case.
        """
        user1 = User.objects.get(pk=201)
        user2 = User.objects.get(pk=202)
        trx, usdt = Currencies.trx, Currencies.usdt
        market = Market.objects.get(src_currency=trx, dst_currency=usdt)
        o1 = create_order(user1, trx, usdt, Decimal('10_000'), Decimal('0.01661'), sell=True)
        o2 = create_order(
            user2,
            trx,
            usdt,
            Decimal('9_992.2232951896'),
            Decimal('0.0166'),
            sell=False,
            balance=Decimal('165.9708289322'),
            market=True,
        )
        do_matching_round(market)
        o2.refresh_from_db()
        assert o2.status == Order.STATUS.done
        assert o2.matched_amount == Decimal('9_992.2')
        assert o2.matched_total_price == Decimal('165.970442')
        o1.refresh_from_db()
        assert o1.status == Order.STATUS.active
        assert o1.matched_amount == Decimal('9_992.2')
        assert o1.matched_total_price == Decimal('165.970442')

    def test_matching_bad_price_with_market_order(self):
        """To prevent shadows because orders with bad price matching with market orders"""
        user1 = User.objects.get(pk=201)
        user2 = User.objects.get(pk=202)
        user3 = User.objects.get(pk=203)
        usdt, rls = Currencies.usdt, Currencies.rls
        market = Market.objects.get(src_currency=usdt, dst_currency=rls)
        o1 = create_order(user1, usdt, rls, '150', '266000', sell=True)
        o2 = create_order(user1, usdt, rls, '50', '265000', sell=True)
        o3 = create_order(user1, usdt, rls, '100', '263000', sell=False)
        o4 = create_order(user1, usdt, rls, '30', '264000', sell=False)
        om1 = create_order(user2, usdt, rls, '12', '266000', sell=False, market=True)
        ob1 = create_order(user3, usdt, rls, '50', '260000', sell=True)
        do_matching_round(market)
        self.assert_matched(ob1, '50', '13180000')
        self.assert_matched(om1, '12', '3180000')
        self.assert_matched(o2, '12', '3180000')
        self.assert_matched(o1, '0', '0')
        self.assert_matched(o4, '30', '7920000')
        self.assert_matched(o3, '20', '5260000')
