from decimal import Decimal
from typing import Optional

from django.core.cache import cache
from django.db.models import F, Sum, Case, When, Q

from exchange.accounts.models import User
from exchange.margin.models import Position
from exchange.market.models import Order
from exchange.wallet.models import WithdrawRequest


class BalanceBlockManager:
    @classmethod
    def get_blocked_balance(cls, wallet):
        v = Decimal('0')
        # Withdraws
        if wallet.type == wallet.WALLET_TYPE.spot:
            active_withdraws = WithdrawRequest.get_financially_pending_requests(wallet=wallet)
            v += active_withdraws.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        elif wallet.type == wallet.WALLET_TYPE.margin:
            active_positions = Position.objects.filter(
                dst_currency=wallet.currency, user_id=wallet.user_id, pnl__isnull=True
            )
            v += active_positions.aggregate(total=Sum('collateral'))['total'] or Decimal('0')
        return v

    @classmethod
    def get_balance_in_order(cls, wallet, use_cache=True):
        """ Return total amount of balance blocked in the given wallet because of open orders
        """
        if wallet.type != wallet.WALLET_TYPE.spot:
            return Decimal(0)

        # Check if user does not have any order
        uid = wallet.user_id
        user_has_recent_order = None
        user_has_no_order = cache.get('user_{}_no_order'.format(uid)) if use_cache else False

        # Check if user has no orders
        if user_has_no_order and use_cache:
            user_has_recent_order = cache.get('user_{}_recent_order'.format(uid))
            if user_has_recent_order:
                # Cache is not reliable if user has a recent order
                cache.set(f'user_{uid}_no_order', False, 60)
                user_has_no_order = False
                use_cache = False
            else:
                return Decimal('0')

        # We only use cache for users with no order if order caching flag is not set
        #  Calculate open orders sum
        #  This is still relatively fast because it uses user_actives3 index (with a final Filter)
        #  and the DB query time should be less than 0.1ms for most users.
        f_unmatched_amount = F('amount') - F('matched_amount')
        user_orders = Order.objects.filter(
            user_id=wallet.user_id,
            status__in=[Order.STATUS.active, Order.STATUS.inactive],
            trade_type=Order.TRADE_TYPES.spot,
        ).exclude(
            # Exclude one pair of OCO orders from blocked balance
            pair__isnull=False, matched_amount=0, execution_type=Order.EXECUTION_TYPES.limit,
        )
        in_order = user_orders.aggregate(in_order=Sum(Case(
            When(order_type=Order.ORDER_TYPES.buy, dst_currency=wallet.currency, then=f_unmatched_amount * F('price')),
            When(order_type=Order.ORDER_TYPES.sell, src_currency=wallet.currency, then=f_unmatched_amount),
        )))['in_order'] or Decimal('0')
        return in_order

    @staticmethod
    def _get_margin_blocking_orders():
        is_buy = Q(order_type=Order.ORDER_TYPES.buy)
        return (
            Order.objects.filter(
                status__in=[Order.STATUS.active, Order.STATUS.inactive],
                trade_type=Order.TRADE_TYPES.margin,
                position__side=F('order_type'),
            )
            .exclude(
                # Exclude one pair of OCO orders from blocked balance
                pair__isnull=False,
                matched_amount=0,
                execution_type=Order.EXECUTION_TYPES.limit,
            )
            .annotate(
                currency=Case(When(is_buy, then=F('dst_currency')), default=F('src_currency')),
                blocked=(F('amount') - F('matched_amount')) * Case(When(is_buy, then=F('price')), default=Decimal(1)),
            )
        )

    @classmethod
    def get_margin_balance_in_order(cls, currency: int, user: Optional[User] = None):
        """Return one pool's blocked balance because of open margin orders"""
        margin_orders = cls._get_margin_blocking_orders().filter(currency=currency)
        if user:
            margin_orders = margin_orders.filter(user=user)
        return margin_orders.aggregate(in_order=Sum('blocked'))['in_order'] or Decimal('0')

    @classmethod
    def get_margin_balances_in_order(cls) -> dict:
        """Return all pools blocked balances because of open margin orders"""
        balances_in_order = cls._get_margin_blocking_orders().values('currency').annotate(in_order=Sum('blocked'))
        return {row['currency']: row['in_order'] or Decimal('0') for row in balances_in_order}

    @staticmethod
    def _get_margin_blocking_unsettled_profits():
        return Position.objects.filter(
            Q(pnl__isnull=True) | Q(pnl__isnull=False, pnl__gt=0, pnl_transaction__isnull=True),
            side=Position.SIDES.buy,
            earned_amount__gt=0,
        )

    @classmethod
    def get_margin_balance_in_temporal_assessment(cls, currency: int):
        """Return one pool's blocked balance because of unsettled profits of open margin buy positions"""
        margin_orders = cls._get_margin_blocking_unsettled_profits().filter(dst_currency=currency)
        return margin_orders.aggregate(total=Sum('earned_amount'))['total'] or Decimal('0')

    @classmethod
    def get_margin_balances_in_temporal_assessment(cls) -> dict:
        """Return all pools blocked balances because of unsettled profits of open margin buy positions"""
        balances_in_order = (
            cls._get_margin_blocking_unsettled_profits().values('dst_currency').annotate(total=Sum('earned_amount'))
        )
        return {row['dst_currency']: row['total'] or Decimal('0') for row in balances_in_order}
