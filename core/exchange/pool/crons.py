from datetime import timedelta
from decimal import Decimal

import jdatetime
from django.db.models import F, Q, Sum
from django.utils import timezone

from exchange.accounts.models import Notification
from exchange.base.calendar import get_first_and_last_of_jalali_month, ir_today
from exchange.base.crons import CronJob, Schedule
from exchange.base.models import CURRENCY_CODENAMES
from exchange.market.functions import Side, get_market_liquidity_both_sides_depth
from exchange.market.markprice import MarkPriceCalculator
from exchange.market.models import Market, Order
from exchange.pool.constants import VIP_0_LEVERAGE_1, VIP_0_LEVERAGE_5, VIP_6_LEVERAGE_1, VIP_6_LEVERAGE_5
from exchange.pool.functions import distribute_profits_for_target_pools, populate_daily_profit_for_target_pools
from exchange.pool.models import DelegationLimit, DelegationRevokeRequest, LiquidityPool, PoolUnfilledCapacityAlert
from exchange.pool.poolmanager import PoolManager


class CheckDelegationRevokeRequestCron(CronJob):
    """Check delegation revoke request and paid"""

    schedule = Schedule(run_every_mins=15)
    code = 'check_delegation_revoke_request_cron'

    def run(self):
        PoolManager.check_delegation_revoke_request()


class CalculateDailyPoolProfitsCron(CronJob):
    schedule = Schedule(run_at_times=['00:03'])
    code = 'calculate_daily_pool_profits_cron'

    def run(self):
        print('Calculating pool profits...')
        from_date, to_date = get_first_and_last_of_jalali_month(ir_today() - timedelta(days=1))
        populate_daily_profit_for_target_pools(from_date, to_date, LiquidityPool.objects.all())


class DistributeUsersProfitCron(CronJob):
    schedule = Schedule(run_at_times=['00:20'])
    code = 'distribute_users_profit_cron'

    def run(self):
        today_jalali = jdatetime.date.today()
        if today_jalali.day != 1:
            return

        print('Distributing users profit...')
        from_date, to_date = get_first_and_last_of_jalali_month(today_jalali.togregorian() - timedelta(days=1))
        distribute_profits_for_target_pools(from_date, to_date, LiquidityPool.objects.all())


class UnfilledCapacityAlertCron(CronJob):
    """
    1. Check unfilled capacity on pools and if pools have free capacity for delegations,
    send emails and alerts to users.

    2. delete old alerts that have been sent
    """

    schedule = Schedule(run_every_mins=10)
    code = 'send_unfilled_capacity_notification_cron'

    def run(self):
        # send notifications and emails
        PoolUnfilledCapacityAlert.send_alerts()

        # delete old notifications
        sent_at = timezone.now() - timedelta(days=7)
        PoolUnfilledCapacityAlert.objects.filter(sent_at__lte=sent_at).delete()


class MinimumRatioAvailableCapacityAlertCron(CronJob):
    """
    Check minimum available capacity on each pools and if one pool goes under min_available_ratio, send a notif
    """

    schedule = Schedule(run_every_mins=60)
    code = 'send_under_ratio_available_capacity_alert_cron'

    def run(self):
        # remove inactive alerts
        PoolManager.remove_inactive_minimum_available_ratio_alerts()
        # send alerts to admin
        PoolManager.notify_minimum_available_ratio()


class NotifyPendingDelegationRevokeRequestCron(CronJob):
    """Notify system admin of delegation revoke requests not settled automatically

    Delegation revoke requests are expected to get settled within certain interval.
    Otherwise, further actions must be taken manually to revoke them in-time.
    """

    schedule = Schedule(run_every_mins=60)
    code = 'notify_pending_delegation_revoke_request_cron'
    MAX_SUSPENDED_HOURS: int = 16

    def run(self):
        pending_requests = DelegationRevokeRequest.objects.filter(
            status=DelegationRevokeRequest.STATUS.new,
            created_at__lt=timezone.now() - timezone.timedelta(hours=self.MAX_SUSPENDED_HOURS),
        ).values(currency=F('user_delegation__pool__currency')).annotate(total_amount=Sum('amount')).distinct()
        if pending_requests:
            self.send_message(pending_requests)

    def send_message(self, pending_requests: list):
        message = f'Total pending revoke requests over {self.MAX_SUSPENDED_HOURS} hours:'
        for pool_data in pending_requests:
            message += f"\n🔹 {pool_data['total_amount'].normalize():f} {CURRENCY_CODENAMES[pool_data['currency']]}"
        Notification.notify_admins(message, title='‼️Unsettled Delegation Revoke Requests', channel="pool")


class DelegationLimitsCron(CronJob):
    schedule = Schedule(run_every_mins=20)
    code = 'delegation_limits_cron'

    def run(self):
        pool_currencies = LiquidityPool.objects.filter(is_active=True).values_list('currency', flat=True)
        active_margin_markets = Market.objects.filter(is_active=True, allow_margin=True).filter(
            Q(src_currency__in=pool_currencies) | Q(dst_currency__in=pool_currencies)
        )
        margin_markets = {(m.src_currency, m.dst_currency): m for m in active_margin_markets}

        liquidity_depths = get_market_liquidity_both_sides_depth()

        limitations = []
        for (src, dst), market in margin_markets.items():
            if (depth := liquidity_depths.get((src, dst))) is None:
                continue

            mark_price = MarkPriceCalculator.get_mark_price(src, dst) or market.get_last_trade_price() or Decimal('0')

            side: Side
            for side, order_type in [('bids', Order.ORDER_TYPES.sell), ('asks', Order.ORDER_TYPES.buy)]:
                value = depth.get(side, Decimal('0'))
                if side == 'asks':
                    value *= mark_price

                for vip_level in range(6, -1, -1):
                    leverage = Decimal('1')
                    while leverage <= market.max_leverage:
                        limit_fraction = self.get_delegation_limit_fraction(leverage, vip_level)
                        limitation = value * limit_fraction
                        limitations.append(
                            DelegationLimit(
                                vip_level=vip_level,
                                leverage=leverage,
                                market=market,
                                order_type=order_type,
                                limitation=limitation.quantize(Decimal(f'1E{limitation.adjusted() - 2}')),
                            )
                        )
                        leverage += Decimal('0.5')

        DelegationLimit.objects.bulk_create(
            limitations,
            update_fields=('limitation',),
            update_conflicts=True,
            unique_fields=('vip_level', 'leverage', 'market', 'order_type'),
            batch_size=1000,
        )

    @staticmethod
    def get_delegation_limit_fraction(leverage: Decimal, vip_level: int) -> Decimal:
        """
        Calculate the maximum delegation limit fraction based on leverage and VIP level.

        The result is linearly interpolated between the VIP0 upper_bound and the VIP6 upper_bound,
        each of which itself interpolates between their leverage-1 and leverage-5 baselines.

        More info @ https://docs.google.com/document/d/1BonqCJjlXxthHzoCjScAl-h392YIGvJm6wE3ZW84wn8

        Args:
            leverage: Leverage multiplier (≥ 1, ≤ market max).
            vip_level: VIP level from 0 (lowest) to 6 (highest).

        Returns:
            A Decimal from 0 to 1 representing the fraction of the available depth a user may be delegated.
        """
        vip_level_proportion = Decimal(vip_level) / Decimal('6')
        leverage_proportion = (leverage - Decimal('1')) / Decimal('4')

        vip0_upper_bound = VIP_0_LEVERAGE_1 + (VIP_0_LEVERAGE_5 - VIP_0_LEVERAGE_1) * leverage_proportion
        vip6_upper_bound = VIP_6_LEVERAGE_1 + (VIP_6_LEVERAGE_5 - VIP_6_LEVERAGE_1) * leverage_proportion

        delegation_limit_fraction = vip0_upper_bound + (vip6_upper_bound - vip0_upper_bound) * vip_level_proportion
        return delegation_limit_fraction
