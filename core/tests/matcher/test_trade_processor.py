from decimal import Decimal

from django.core.cache import cache
from django.test import TransactionTestCase, override_settings

from exchange.accounts.models import User
from exchange.base.models import Currencies
from exchange.market.models import Market, Order, OrderMatching
from exchange.matcher.matcher import Matcher, post_processing_matcher_round
from exchange.matcher.tradeprocessor import TradeProcessor
from exchange.wallet.models import Wallet
from tests.base.utils import TransactionTestFastFlushMixin


@override_settings(ASYNC_TRADE_COMMIT=True)
class TradeProcessorTest(TransactionTestFastFlushMixin, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.user1, _ = User.objects.get_or_create(username=201)
        self.user2, _ = User.objects.get_or_create(username=202)
        self.user3, _ = User.objects.get_or_create(username=203)
        self.user4, _ = User.objects.get_or_create(username=204)
        self.user5, _ = User.objects.get_or_create(username=205)
        self.user6, _ = User.objects.get_or_create(username=206)

        market1, _ = Market.objects.get_or_create(
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            is_active=True,
        )
        market2, _ = Market.objects.get_or_create(
            src_currency=Currencies.btc,
            dst_currency=Currencies.rls,
            is_active=True,
        )

        cache.set('tradeprocessor_last_trade_id', 0)

        OrderMatching.objects.all().delete()
        for users, market in zip([(self.user1, self.user2), (self.user3, self.user4)], [market1, market2]):
            user_1, user_2 = users
            Wallet.get_user_wallet(user_1, market.dst_currency).create_transaction(
                'manual', Decimal(2_000_000_000)
            ).commit()
            Wallet.get_user_wallet(user_2, market.src_currency).create_transaction(
                'manual', Decimal(2_000_000_000)
            ).commit()

            _ = self.create_order(Order.ORDER_TYPES.buy, Decimal('0.01'), Decimal('2.7e9'), market, user_1.id)
            _ = self.create_order(Order.ORDER_TYPES.sell, Decimal('0.01'), Decimal('2.7e9'), market, user_2.id)

            matcher = Matcher(market)
            matcher.do_matching_round()
            if market.symbol in Matcher.get_symbols_that_use_async_stop_process():
                post_processing_matcher_round(market, matcher.MARKET_PRICE_RANGE.get(market.id))

        self.trade2, self.trade1 = OrderMatching.objects.order_by('-id')[0:2]


    def create_order(self, order_type, amount, price, market, user_id):
        order_params = {
            'user_id': user_id,
            'src_currency': market.src_currency,
            'dst_currency': market.dst_currency,
            'order_type': order_type,
            'amount': amount,
        }

        return Order.objects.create(
            execution_type=Order.EXECUTION_TYPES.limit,
            price=price,
            status=Order.STATUS.active,
            **order_params,
        )

    def test_deposit_transaction_without_wallet(self):

        assert self.trade1
        assert self.trade1.sell_deposit_id is None
        assert self.trade1.buy_deposit_id is None

        self.trade1.sell_order.dst_wallet.delete()
        self.trade1.buy_order.src_wallet.delete()

        processor = TradeProcessor(commit_trade=False)
        processor.do_round()
        processor.bulk_update_trades()

        self.trade1.refresh_from_db()
        assert self.trade1.sell_deposit_id
        assert 'فروش ' in self.trade1.sell_deposit.description
        assert 'فروش ' in self.trade1.sell_withdraw.description
        assert self.trade1.buy_deposit_id
        assert 'خرید ' in self.trade1.buy_deposit.description
        assert 'خرید ' in self.trade1.buy_withdraw.description

        assert (
            self.trade1.sell_order.dst_wallet.balance
            == Decimal('2.7e9') * Decimal('0.01') - self.trade1.sell_fee_amount
        )
        assert self.trade1.buy_order.src_wallet.balance == Decimal('0.01') - self.trade1.buy_fee_amount

    def test_deposit_transaction_with_wallet(self):

        assert self.trade2
        assert self.trade2.sell_deposit_id is None
        assert self.trade2.buy_deposit_id is None

        # create wallet
        self.trade2.sell_order.dst_wallet.balance = Decimal('0.01')
        self.trade2.sell_order.dst_wallet.save()

        # create wallet
        self.trade2.buy_order.src_wallet.balance = Decimal('0.01')
        self.trade2.buy_order.src_wallet.save()

        processor = TradeProcessor(commit_trade=False)
        processor.do_round()
        processor.bulk_update_trades()

        self.trade2.refresh_from_db()
        assert self.trade2.sell_deposit_id
        assert 'فروش ' in self.trade2.sell_deposit.description
        assert 'فروش ' in self.trade2.sell_withdraw.description
        assert self.trade2.buy_deposit_id
        assert 'خرید ' in self.trade2.buy_deposit.description
        assert 'خرید ' in self.trade2.buy_withdraw.description

        assert (
            self.trade2.sell_order.dst_wallet.balance
            == Decimal('0.01') + Decimal('2.7e9') * Decimal('0.01') - self.trade2.sell_fee_amount
        )
        assert (
            self.trade2.buy_order.src_wallet.balance == Decimal('0.01') + Decimal('0.01') - self.trade2.buy_fee_amount
        )

    def test_max_trade_id(self):
        assert cache.get('tradeprocessor_last_trade_id') == 0

        processor = TradeProcessor(commit_trade=False)
        processor.do_round()
        processor.bulk_update_trades()

        assert cache.get('tradeprocessor_last_trade_id') == self.trade1.id
