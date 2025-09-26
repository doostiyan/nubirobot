from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings

from exchange.accounts.models import User
from exchange.base.models import Currencies
from exchange.market.models import Market, Order
from exchange.matcher.matcher import Matcher
from exchange.wallet.models import Wallet
from tests.base.utils import create_order


class MatcherTest(TestCase):
    def assert_matched(self, order, amount, total):
        order.refresh_from_db()
        filled = order.amount == order.matched_amount
        expected_status = Order.STATUS.done if filled else Order.STATUS.active
        if order.is_market and not filled:
            expected_status = Order.STATUS.canceled
        assert order.status == expected_status
        assert order.matched_amount == Decimal(amount)
        assert order.matched_total_price == Decimal(total)

    def test_validate_order(self):
        user1 = User.objects.get(pk=201)
        btc, rls = Currencies.btc, Currencies.rls
        user1_rls = Wallet.get_user_wallet(user1, rls)
        # Validate simple orders
        matcher = Matcher(market=Market.get_for(btc, rls))
        assert matcher.VALIDATED_ORDERS == set()  # noqa: SIM300
        o1 = create_order(user1, btc, rls, Decimal('0.12'), Decimal('40e8'), sell=False)
        assert matcher.validate_order(o1)
        assert o1.id in matcher.VALIDATED_ORDERS
        assert o1.status == Order.STATUS.active
        assert matcher.validate_order(o1)
        # Spend some money from wallet
        user1_rls.refresh_from_db()
        t1 = user1_rls.create_transaction(tp='manual', amount='-48_000_0')
        t1.commit()
        o1.dst_wallet.refresh_from_db()
        assert not matcher.validate_order(o1, use_cache=False)
        assert o1.status == Order.STATUS.canceled
        assert not matcher.validate_order(o1)
        assert o1.id not in matcher.VALIDATED_ORDERS
        matcher.post_process_orders([], [])
        o1.refresh_from_db()
        assert o1.status == Order.STATUS.canceled
        # Validate another order
        o2 = create_order(user1, btc, rls, Decimal('0.12'), Decimal('40e8'), sell=False, charge_ratio=Decimal('0.001'))
        assert matcher.validate_order(o2)

    @override_settings(PREVENT_INTERNAL_TRADE=True)
    @override_settings(TRADER_BOT_IDS=[201, 203])
    def test_check_for_forbidden_matching(self):
        user1 = User.objects.get(pk=201)
        user2 = User.objects.get(pk=202)
        user3 = User.objects.get(pk=203)
        btc, rls = Currencies.btc, Currencies.rls
        o1 = create_order(user1, btc, rls, Decimal('0.12'), Decimal('1_671_691_750_0'), sell=True)
        o2 = create_order(user2, btc, rls, Decimal('0.15'), Decimal('1_671_691_760_0'), sell=False)
        o3 = create_order(user3, btc, rls, Decimal('0.15'), Decimal('1_671_691_760_0'), sell=False)
        # Check when only one side is a bot
        matcher = Matcher(market=Market.get_for(btc, rls))
        assert matcher.check_for_forbidden_matching(o1, o2)
        assert o1.status == Order.STATUS.active
        assert o2.status == Order.STATUS.active
        # Make both sides bot
        assert not matcher.check_for_forbidden_matching(o1, o3)
        assert o1.status == Order.STATUS.canceled
        assert o3.status == Order.STATUS.canceled
