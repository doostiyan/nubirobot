from datetime import timedelta

from exchange.base.calendar import get_earliest_time, get_latest_time, ir_now
from exchange.base.constants import ZERO
from exchange.base.crons import CronJob, Schedule
from exchange.base.logging import report_exception
from exchange.socialtrade.functions import update_winrates
from exchange.socialtrade.leaders.trades import LeaderTradesSender
from exchange.socialtrade.models import Leader, SocialTradeSubscription
from exchange.socialtrade.notifs import SocialTradeNotifs
from exchange.socialtrade.tasks import send_pre_renewal_alert, task_renew_subscription
from exchange.socialtrade.utils import format_amount
from exchange.wallet.models import Wallet


class SendPreRenewalNotifCron(CronJob):
    """This cron sends notif to users 1 day before expiring date."""

    schedule = Schedule(run_at_times=('14:30',))
    code = 'send_pre_renewal_notif'

    def run(self):
        target_datetime = ir_now() + timedelta(days=1)
        from_date = get_earliest_time(target_datetime)
        to_date = get_latest_time(target_datetime)

        candid_subscriptions = (
            SocialTradeSubscription.get_actives()
            .filter(
                expires_at__gte=from_date,
                expires_at__lte=to_date,
            )
        )
        for subscription in candid_subscriptions:
            if not subscription.leader.is_active:
                continue

            send_pre_renewal_alert.delay(subscription.pk)


class SendUpcomingRenewalNotifCron(CronJob):
    schedule = Schedule(run_every_mins=60)
    code = 'send_upcoming_renewal_notif'

    def run(self):
        from_date = ir_now() + timedelta(minutes=30)
        to_date = from_date + timedelta(minutes=60)

        candid_subscriptions = (
            SocialTradeSubscription.get_actives()
            .filter(
                is_trial=False,
                is_auto_renewal_enabled=True,
                expires_at__gte=from_date,
                expires_at__lte=to_date,
            )
            .select_related('subscriber', 'leader')
        )

        for subscription in candid_subscriptions:
            if not subscription.is_renewable:
                continue

            if subscription.leader.subscription_fee == ZERO:
                continue

            user_wallet = Wallet.get_user_wallet(
                subscription.subscriber,
                subscription.fee_currency,
                Wallet.WALLET_TYPE.spot,
            )
            if user_wallet.active_balance < subscription.leader.subscription_fee:
                continue

            data = dict(
                expires_at=subscription.shamsi_expire_date,
                nickname=subscription.leader.nickname,
                subscription_fee=format_amount(
                    subscription.leader.subscription_fee,
                    subscription.leader.subscription_currency,
                ),
            )
            SocialTradeNotifs.upcoming_renewal.send(subscription.subscriber, data=data)


class RenewSubscriptionsCron(CronJob):
    schedule = Schedule(run_every_mins=1)
    code = 'renew_subscriptions'
    celery_beat = True
    task_name = 'socialtrade.core.logic.renew_social_trade_subscriptions'

    def run(self):
        now = ir_now()
        from_dt = now - timedelta(minutes=5)
        to_dt = now + timedelta(minutes=5)

        subscription_ids = SocialTradeSubscription.objects.filter(
            is_auto_renewal_enabled=True,
            canceled_at__isnull=True,
            is_renewed__isnull=True,
            expires_at__gte=from_dt,
            expires_at__lte=to_dt,
            leader__deleted_at__isnull=True,
        ).values_list('id', flat=True)

        for subscription_id in subscription_ids:
            try:
                task_renew_subscription(subscription_id)
            except:
                report_exception()


class UpdateWinratesCron(CronJob):
    schedule = Schedule(run_every_mins=15)
    code = 'update_leader_winrates'

    def run(self):
        update_winrates()


class SendLeadersTradesNotifCron(CronJob):
    schedule = Schedule(run_every_mins=1)
    code = 'send_leaders_trades_notif'
    celery_beat = True
    task_name = 'socialtrade.core.notif.send_leader_trades'

    def run(self):
        from_dt = self.last_successful_start
        to_dt = ir_now()

        leaders_id = SocialTradeSubscription.get_actives().values_list('leader_id').distinct()
        leader_trades_sender = LeaderTradesSender(leaders_id, from_dt=from_dt, to_dt=to_dt)
        leader_trades_sender.send()


class UpdateLeaderProfitsCron(CronJob):
    schedule = Schedule(run_at_times=('4:00',))
    code = 'update_leader_profits'

    def run(self):
        for leader in Leader.objects.filter(deleted_at__isnull=True):
            leader.update_profits()
