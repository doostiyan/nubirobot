"""Market Crons"""
import datetime
from decimal import Decimal

import requests
from django.conf import settings
from django.contrib.postgres.aggregates import ArrayAgg
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils.timezone import now

from exchange.accounts.models import Notification, User
from exchange.base.calendar import ir_now, ir_tz
from exchange.base.conversions import check_usd_price
from exchange.base.crons import CronJob, Schedule
from exchange.base.helpers import context_flag
from exchange.base.logging import metric_gauge, report_event, report_exception
from exchange.base.models import RIAL, TETHER, Currencies, Settings, get_market_symbol
from exchange.market.functions import create_missing_transaction
from exchange.market.marketmanager import MarketManager
from exchange.market.models import FeeTransactionTradeList, Market, Order, OrderMatching
from exchange.market.referral import calculate_referral_fees
from exchange.wallet.models import Transaction, Wallet


class DeleteCanceledOrdersCron(CronJob):
    schedule = Schedule(run_every_mins=71)
    code = 'delete_canceled_orders_cron'

    def run(self):
        """Delete canceled and unfilled orders.

           Note: Only orders for last 7 days are removed, because if the cron is not
           run for a long time, the number of records to delete will become very large
           and may cause DB overload. In such cases, removing the unused records step
           by step in DB is recommended.
        """
        Order.objects.filter(
            status=Order.STATUS.canceled,
            matched_amount=Decimal('0'),
            fee=Decimal('0'),
            created_at__gte=now() - datetime.timedelta(days=7),  # Safeguard
            untracked_changes__isnull=True,  # related position is not updated yet
        ).delete()


class AdminsNotificationCron(CronJob):
    schedule = Schedule(run_every_mins=15)
    code = 'admins_notification_cron'

    def run(self):
        from django_cron.models import CronJobLog
        from post_office.models import Email as SentEmail

        print('Sending admins notifications...')
        nw = ir_now()
        day = nw.replace(hour=0, minute=0, second=0, microsecond=0)

        # Email sending metrics
        failed_sent_emails = SentEmail.objects.filter(created__gte=day).exclude(status=0).count()
        failed_crons = CronJobLog.objects.filter(start_time__gte=day, is_success=False).count()

        bot1 = User.objects.get(email='bot1@nobitex.ir')
        market_usdt_irt = Market.get_for(TETHER, RIAL)
        bot1_trades = OrderMatching.get_trades(
            user=bot1,
            date_from=day,
        ).exclude(market=market_usdt_irt).count()

        # Create message
        title = 'وضعیت سامانه تا {}'.format(nw.strftime('%H:%M'))
        msg = []
        if failed_sent_emails > 10:
            msg.append('*ایمیل‌های ناموفق:* {}'.format(failed_sent_emails))
        if failed_crons > 5:
            msg.append('*کران‌های ناموفق:* {}'.format(failed_crons))
        if bot1_trades:
            msg.append('*معاملات بات یک:* {}'.format(bot1_trades))
        if not msg:
            print('[No Message]')
            return

        # Send message to Telegram or edit existing recent message
        msg = '\n'.join(msg)
        cache_key = 'message-system-notif'
        message_id = cache.get(cache_key)
        Notification.notify_admins(msg, title=title, channel='critical', message_id=message_id, pin=True,
                                   cache_key=cache_key, cache_timeout=6 * 3600)


class SystemFeeWalletChargeCron(CronJob):
    schedule = Schedule(run_at_times=['{}:05'.format(str(i).zfill(2)) for i in range(24)])
    code = 'system_fee_wallet_charge_cron'

    @transaction.atomic
    def run(self):
        # TODO: If this cron is run more than once (e.g. in timezone changes or delayed runs),
        # it will fail in subsequent runs and enter a failing loop. Make it idempotent. #TZ
        print('Charging system fee wallet for trades done the the last hour...')

        # Aggregate market trade fees
        nw = ir_now()
        date_to = nw.replace(minute=0, second=0, microsecond=0)
        date_from = date_to - datetime.timedelta(hours=1)
        market_hour_fees = (
            OrderMatching.objects.filter(
                created_at__gte=date_from,
                created_at__lt=date_to,
            )
            .values('market_id')
            .annotate(
                total_sell_fee=Sum('sell_fee_amount'),
                total_buy_fee=Sum('buy_fee_amount'),
                sell_fee_trade_ids=ArrayAgg('id', filter=Q(sell_fee_amount__gt=0), default=[]),
                buy_fee_trade_ids=ArrayAgg('id', filter=Q(buy_fee_amount__gt=0), default=[]),
            )
        )

        # Calculate total fees for each currency
        fees = {}
        currency_trade_ids = {}
        for market_hour_fee in market_hour_fees:
            market = Market.get_cached(market_hour_fee['market_id'])
            src, dst = market.src_currency, market.dst_currency
            sell_fee = market_hour_fee['total_sell_fee'] or Decimal('0')
            buy_fee = market_hour_fee['total_buy_fee'] or Decimal('0')
            sell_trade_ids = market_hour_fee['sell_fee_trade_ids']
            buy_trade_ids = market_hour_fee['buy_fee_trade_ids']

            if sell_fee:
                fees[dst] = fees.get(dst, Decimal('0')) + sell_fee
                if dst not in currency_trade_ids:
                    currency_trade_ids[dst] = set()
                currency_trade_ids[dst].update(sell_trade_ids)
            if buy_fee:
                fees[src] = fees.get(src, Decimal('0')) + buy_fee
                if src not in currency_trade_ids:
                    currency_trade_ids[src] = set()
                currency_trade_ids[src].update(buy_trade_ids)

        # Create fee transaction for each currency
        transactions_count = 0
        for currency, hour_fee in fees.items():
            fee_wallet = Wallet.get_fee_collector_wallet(currency)
            tx_ref_id = (date_from - settings.NOBITEX_EPOCH).days * 100000 + date_from.hour * 1000 + currency
            fee_transaction = fee_wallet.create_transaction(
                tp='fee',
                amount=hour_fee,
                description='Markets aggregated fees for {}'.format(date_from.strftime('%Y-%m-%d/%H')),
                ref_module=Transaction.REF_MODULES['FeeAggregate'],
                ref_id=tx_ref_id,
            )
            if not fee_transaction:
                report_event('FeeWalletBalanceError', extras={'src': 'SystemFeeWalletChargeCron'})  # unlikely event
            fee_transaction.commit()
            transactions_count += 1
            trade_ids = list(currency_trade_ids.get(currency, []))
            try:
                fee_transaction_trade = FeeTransactionTradeList.objects.create(
                    transaction=fee_transaction,
                    trades=trade_ids,
                    currency=currency,
                    from_datetime=date_from,
                    to_datetime=date_to,
                )
            except Exception as exp:
                report_exception()
        print('Created {} fee transactions!'.format(transactions_count))


class ReferralFeeCalculationCron(CronJob):
    schedule = Schedule(run_at_times=['2:00'])
    code = 'referral_fee_calculation_cron'

    def run(self):
        print('calculating users referral fee ...')
        calculate_referral_fees()


class UserTradeStatusCron(CronJob):
    """ Update UserTradeStatus table according to past hour IRT trades

        # TODO: Here the users' trades are summed one by one. It is because of the trader
        plan trades should be excluded from the sum. The better method is to do an aggregate
        query on all month trades here, and then exclude trader volume for users who where
        in the plan.
    """
    schedule = Schedule(run_at_times=['3:00'])
    code = 'user_trade_status_cron'

    def run(self):
        print('Updating users monthly trades status ...')
        midnight = ir_now().replace(hour=0, minute=0, second=0, microsecond=0)
        date_from = (
            self.last_successful_start.astimezone(ir_tz()).replace(hour=0, minute=0, second=0, microsecond=0)
            if self.last_successful_start
            else midnight - datetime.timedelta(days=1)
        )
        missed_days = (midnight - date_from).days
        MarketManager.get_bulk_latest_user_stats(date_from, missed_days)


class UpdateUSDValueCron(CronJob):
    schedule = Schedule(run_every_mins=15)
    code = 'update_usd_value_cron'

    def run(self):
        print('Updating USD-IRR value from production server...')
        if settings.IS_PROD:
            return
        r = requests.post(settings.PROD_API_URL + 'market/usd-value', timeout=10)
        r.raise_for_status()
        system_usd = r.json().get('usdValue')
        usd_sell_price = system_usd.get('sell')
        usd_buy_price = system_usd.get('buy')
        usd_buy_price = usd_sell_price - 200  # Manually set buy price for testnet
        if not check_usd_price(usd_sell_price, usd_buy_price):
            raise ValueError('Invalid USD-IRR value returned from server')
        Settings.set_dict('usd_value', {'sell': usd_sell_price, 'buy': usd_buy_price})


class MarketActiveOrdersMetricCron(CronJob):
    schedule = Schedule(run_every_mins=1)
    code = 'market_active_orders_metric_cron'

    def run(self):
        market_orders_count = (
            Order.objects.filter(status=Order.STATUS.active)
            .values('src_currency', 'dst_currency')
            .annotate(
                sell_count=Count('id', filter=Q(order_type=Order.ORDER_TYPES.sell)),
                buy_count=Count('id', filter=Q(order_type=Order.ORDER_TYPES.buy)),
            )
        )
        for market_data in market_orders_count:
            symbol = get_market_symbol(src=market_data['src_currency'], dst=market_data['dst_currency'])
            for side in ('sell', 'buy'):
                metric_gauge(
                    metric='metric_orderbook_active_orders_total',
                    value=market_data[f'{side}_count'],
                    labels=(symbol, side),
                )


class FixAddAsyncTradeTransactionCron(CronJob):
    schedule = Schedule(run_every_mins=10)
    code = 'fix_add_async_trade_transactions_crons'

    @context_flag(NOTIFY_NON_ATOMIC_TX_COMMIT=False)
    def run(self):

        from_datetime = ir_now() - datetime.timedelta(hours=12)
        to_datetime = ir_now() - datetime.timedelta(seconds=1800)

        create_missing_transaction(from_datetime, to_datetime, dry_run=False, disable_process_bar=True)
