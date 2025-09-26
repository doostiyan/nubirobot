from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase

from exchange.base.models import Currencies
from exchange.market.estimators import EstimatedSrcAmountByDstAmount, estimate_market_order_src_amount_by_dst_amount
from exchange.market.models import Market


class TestEstimateMarketOrderSrcAmountByDstAmount(TestCase):
    def setUp(self):
        self.btc_rls_market = Market(src_currency=Currencies.btc, dst_currency=Currencies.rls)
        self.eth_rls_market = Market(src_currency=Currencies.eth, dst_currency=Currencies.rls)

    def set_asks(self, market, asks):
        cache.set(f'orderbook_{market.symbol}_asks', asks)

    def set_bids(self, market, bids):
        cache.set(f'orderbook_{market.symbol}_bids', bids)

    def test_estimate_market_order_src_amount_by_dst_amount_no_market(self):
        result = estimate_market_order_src_amount_by_dst_amount(Currencies.doge, Currencies.usdt, Decimal('10.0'))
        assert result is None

    def test_estimate_market_order_src_amount_by_dst_amount_no_asks(self):
        result = estimate_market_order_src_amount_by_dst_amount(Currencies.eth, Currencies.rls, Decimal('10.0'))
        assert result is None

    def test_estimate_market_order_src_amount_by_dst_amount_successful_estimation(self):
        self.set_asks(self.btc_rls_market, '[[150, 2.0], [145, 3.0]]')

        result = estimate_market_order_src_amount_by_dst_amount(Currencies.btc, Currencies.rls, Decimal('450'))
        expected_result = EstimatedSrcAmountByDstAmount(
            src_amount=Decimal('2') + Decimal(15) / Decimal(14.5),
            actual_dst_amount=Decimal('450'),
            is_max_used=False,
        )
        assert result == expected_result

    def test_estimate_market_order_src_amount_by_dst_amount_max_src_amount_reached(self):
        self.set_asks(self.btc_rls_market, '[[150, 2.0], [145, 3.0]]')
        result = estimate_market_order_src_amount_by_dst_amount(
            Currencies.btc, Currencies.rls, Decimal('500'), Decimal(3)
        )
        expected_result = EstimatedSrcAmountByDstAmount(
            src_amount=Decimal(3),
            actual_dst_amount=Decimal('150') * 2 + Decimal('145'),
            is_max_used=True,
        )
        assert result == expected_result

    def test_estimate_market_order_src_amount_by_dst_amount_low_depth(self):
        self.set_bids(self.btc_rls_market, '[[145, 2.0], [150, 3.0]]')
        # with max_src_amount
        result = estimate_market_order_src_amount_by_dst_amount(
            Currencies.btc,
            Currencies.rls,
            Decimal('5000'),
            Decimal(300),
            is_sell=False,
        )
        expected_result = EstimatedSrcAmountByDstAmount(
            src_amount=Decimal(5),
            actual_dst_amount=Decimal('145') * 2 + Decimal('150') * 3,
            is_max_used=False,
        )
        assert result == expected_result

        # without max_src_amount
        result = estimate_market_order_src_amount_by_dst_amount(
            Currencies.btc,
            Currencies.rls,
            Decimal('5000'),
            is_sell=False,
        )
        assert result == expected_result
