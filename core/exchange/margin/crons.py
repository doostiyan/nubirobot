import datetime
from decimal import Decimal

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Case, DecimalField, Expression, F, Q, QuerySet, Sum, When
from django.utils import timezone

from exchange.accounts.models import Notification
from exchange.base.calendar import ir_today
from exchange.base.crons import CronJob, CustomCronLock, Schedule
from exchange.base.emailmanager import EmailManager
from exchange.base.helpers import batcher
from exchange.base.templatetags.nobitex import shamsidateformat
from exchange.margin.models import MarginCall, Position, PositionFee
from exchange.margin.services import MarginManager
from exchange.margin.tasks import task_manage_expired_positions
from exchange.market.inspector import get_markets_last_price_range
from exchange.wallet.models import Transaction, Wallet


class MarginCallManagementCron(CronJob):
    schedule = Schedule(run_every_mins=1)
    code = 'manage_margin_calls'

    def run(self):
        # Important: market data used here does not employ matcher's price filter for stop loss
        market_data = get_markets_last_price_range(since=self.last_successful_start)
        for src_currency, dst_currency, market_high_price, market_low_price, _ in market_data:
            threshold_ratio = self.get_liquidation_threshold_ratio_expression()
            open_positions = Position.objects.filter(
                src_currency=src_currency,
                dst_currency=dst_currency,
                status=Position.STATUS.open,
                pnl__isnull=True,
            )
            for side, market_price, liquidation_price in (
                (Position.SIDES.sell, market_high_price, market_high_price * threshold_ratio),
                (Position.SIDES.buy, market_low_price, market_low_price / threshold_ratio),
            ):
                self.solve_saved_positions_margin_calls(side, open_positions, market_price, liquidation_price)
                self.create_margin_call_for_in_danger_positions(side, open_positions, liquidation_price, market_price)

    @staticmethod
    def solve_saved_positions_margin_calls(
        side: int,
        positions: QuerySet,
        market_price: Decimal,
        liquidation_price: Expression,
    ):
        significant_price_change = Decimal('0.02')
        if side == Position.SIDES.sell:
            lookup = 'gt'
            price_change_ratio = 1 + significant_price_change
        else:
            lookup = 'lt'
            price_change_ratio = 1 - significant_price_change
        MarginCall.objects.filter(
            position__in=positions.filter(**{'side': side, f'liquidation_price__{lookup}': liquidation_price}),
            is_solved=False,
        ).filter(
            Q(**{f'position__liquidation_price__{lookup}': F('liquidation_price')})  # If it's manually handled
            | Q(**{f'market_price__{lookup}': market_price * price_change_ratio})  # or market significantly changed
            | Q(created_at__date__lt=ir_today()),  # or one day's been passed since
        ).update(
            is_solved=True,
        )

    @staticmethod
    def create_margin_call_for_in_danger_positions(
        side: int,
        positions: QuerySet,
        liquidation_price: Expression,
        market_price: Decimal,
    ):
        lookup = 'lte' if side == Position.SIDES.sell else 'gte'
        in_danger_positions = (
            positions.filter(**{'side': side, f'liquidation_price__{lookup}': liquidation_price})
            .exclude(
                margin_calls__is_solved=False,
            )
            .only('id', 'liquidation_price')
        )
        MarginCall.objects.bulk_create(
            (
                MarginCall(position=position, liquidation_price=position.liquidation_price, market_price=market_price)
                for position in in_danger_positions
            ),
            batch_size=20,
        )

    @staticmethod
    def get_liquidation_threshold_ratio_expression() -> Expression:
        """Get margin call price to liquidation price ratio based on leverage"""
        margin_call_ratio = Case(*[
            When(leverage__gte=leverage_lower_bound, then=margin_call_ratio)
            for leverage_lower_bound, margin_call_ratio in sorted(settings.MARGIN_CALL_RATIOS.items(), reverse=True)
        ], output_field=DecimalField())
        return margin_call_ratio / settings.MAINTENANCE_MARGIN_RATIO


class MarginCallSendingCron(CronJob):
    schedule = Schedule(run_every_mins=1)
    code = 'send_margin_call'

    def run(self):
        margin_call_ids = list(MarginCall.objects.filter(is_sent=False, is_solved=False).values_list('id', flat=True))
        for batch in batcher(margin_call_ids, batch_size=500):
            with transaction.atomic():
                margin_call_objects = (
                    MarginCall.objects.filter(id__in=batch, is_sent=False, is_solved=False)
                    .select_related('position__user')
                    .select_for_update(of=('self',), no_key=True)
                )
                MarginCall.bulk_send(margin_call_objects)


class PositionExpireCron(CronJob):
    schedule = Schedule(run_at_times=('00:00',))
    code = 'expire_old_positions'

    def run(self):
        expire_start_date = ir_today() - timezone.timedelta(days=settings.POSITION_EXTENSION_LIMIT)
        expired_count = Position.objects.filter(
            status__in=Position.STATUS_ONGOING,
            created_at__date__lt=expire_start_date,
            pnl__isnull=True,
        ).update(status=Position.STATUS.expired, freezed_at=timezone.now())
        if expired_count:
            Notification.notify_admins(
                f'Tonight expired positions: {expired_count}',
                title='🧭 Margin Expiration',
                channel='pool',
            )
        task_manage_expired_positions.delay()


class NotifyUpcomingPositionsExpirationCron(CronJob):
    schedule = Schedule(run_at_times=('11:00',))
    code = 'notify_upcoming_positions_expiration'

    def run(self):
        soon_to_be_expired_start_date = ir_today() - timezone.timedelta(days=settings.POSITION_EXTENSION_LIMIT + 1 - 3)
        soon_to_be_expired_positions = list(
            Position.objects.filter(
                status__in=Position.STATUS_ONGOING,
                pnl__isnull=True,
                created_at__date=soon_to_be_expired_start_date,
            )
            .select_related('user')
        )

        for batch in batcher(soon_to_be_expired_positions, batch_size=500):
            notifs_to_be_created = []
            emails_to_be_send = []
            for position in batch:
                notif_message = (
                    'موقعیت {} شما در بازار {} '
                    'در تاریخ {} منقضی خواهد شد. '
                    'لطفاً اقدامات لازم را جهت بستن موقعیت خود انجام دهید.'.format(
                        'فروش' if position.is_short else 'خرید',
                        position.market.market_display,
                        shamsidateformat(position.expiration_date),
                    )
                )
                notifs_to_be_created.append(Notification(user_id=position.user_id, message=notif_message))
                emails_to_be_send.extend(
                    EmailManager.create_email(
                        email=position.user.email,
                        template='notify_upcoming_margin_expiration',
                        data={
                            'position_side': 'فروش' if position.is_short else 'خرید',
                            'market': position.market.market_display,
                            'expiration_date': shamsidateformat(position.expiration_date),
                            'leverage': position.leverage.normalize(),
                            'liability': position.liability.normalize(),
                            'domain': settings.PROD_FRONT_URL,
                        },
                        priority='high',
                    )
                )
            EmailManager.send_mail_many(emails_to_be_send)
            Notification.objects.bulk_create(notifs_to_be_created)


class PositionExtensionFeeCron(CronJob):
    schedule = Schedule(run_at_times=('00:00',))
    code = 'claim_positions_extension_fees'

    def run(self):
        today = ir_today()
        position_ids = (
            Position.objects.filter(
                status__in=Position.STATUS_ONGOING,
                created_at__date__lt=today,
                created_at__date__gte=today - timezone.timedelta(days=settings.POSITION_EXTENSION_LIMIT),
                pnl__isnull=True,
            )
            .exclude(fees__date=today)
            .values_list('id', flat=True)
            .distinct()
        )
        Notification.notify_admins(
            f'{len(position_ids)} extended positions' + ('\n[Check cron time!]' if len(position_ids) > 4e4 else ''),
            title='🧭 Position Extension Fee',
            channel='pool',
        )
        for pid in position_ids:
            MarginManager.extend_position(pid, today)

        self.charge_system_fee_wallet(today)

        # Expire positions that failed to pay extension fee
        task_manage_expired_positions.delay()

    @staticmethod
    def charge_system_fee_wallet(date: datetime.datetime):
        system_fees = (
            PositionFee.objects.filter(
                date=date,
                transaction__isnull=False,
            )
            .values(
                currency=F('position__dst_currency'),
            )
            .annotate(
                total_fee=Sum('amount'),
            )
        )
        for system_fee in system_fees:
            fee_wallet = Wallet.get_fee_collector_wallet(system_fee['currency'])
            dst_transaction = fee_wallet.create_transaction(
                tp='fee',
                amount=system_fee['total_fee'],
                description='کارمزدهای تجمیعی تمدید موقعیت',
            )
            tx_ref_id = (date - settings.NOBITEX_EPOCH.date()).days * 1000 + system_fee['currency']
            try:
                with transaction.atomic():
                    dst_transaction.commit(ref=Transaction.Ref('PositionFeeAggregate', tx_ref_id))
            except IntegrityError:
                pass  # Already claimed


EXTEND_CRON_LOCK = CustomCronLock(PositionExtensionFeeCron, silent=True)


class CanceledPositionsDeleteCron(CronJob):
    """Delete canceled and unfilled positions

    Because of the cron deleting canceled orders, canceled positions carry no useful data,
    since they got no orders and no collaterals.
    """
    schedule = Schedule(run_every_mins=120)
    code = 'delete_canceled_positions_cron'

    def run(self):
        Position.objects.filter(status=Position.STATUS.canceled, fees__isnull=True).delete()
