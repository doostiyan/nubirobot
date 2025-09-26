import datetime

from django.conf import settings

from exchange.accounts.models import Notification
from exchange.base.calendar import ir_now
from exchange.base.crons import CronJob, Schedule
from exchange.base.logging import report_exception
from exchange.base.models import Settings
from exchange.xchange.constants import GET_MISSED_CONVERSION_STATUS_COUNTDOWN, GET_MISSED_CONVERSION_STATUS_RETRIES
from exchange.xchange.helpers import calculate_market_consumption_percentage
from exchange.xchange.models import ExchangeTrade
from exchange.xchange.small_asset_batch_convertor import SmallAssetBatchConvertor
from exchange.xchange.trade_collector import TradeCollector


class FailOldUnknownTradesCron(CronJob):
    schedule = Schedule(run_every_mins=5)
    code = 'fail_old_unknown_exchange_trade'

    def run(self):
        ExchangeTrade.objects.filter(
            status=ExchangeTrade.STATUS.unknown,
            created_at__lt=ir_now() - datetime.timedelta(
                seconds=GET_MISSED_CONVERSION_STATUS_COUNTDOWN * (GET_MISSED_CONVERSION_STATUS_RETRIES + 1),
            ),
        ).update(status=ExchangeTrade.STATUS.failed)


class XchangeNotifyAdminOnMarketApproachingLimitsCron(CronJob):
    schedule = Schedule(run_every_mins=10)
    code = 'xchange_notify_admin_on_market_approaching_limits'

    def run(self):
        consumed_percentages = calculate_market_consumption_percentage()
        threshold = 70
        messages = [
            f'- {percentage.symbol} {"sell" if percentage.is_sell else "buy"} {round(percentage.percentage, 1)}%'
            for percentage in consumed_percentages
            if percentage.percentage >= threshold
        ]
        if messages:
            title_message = '🚨درصد مصرف شده‌ی بازار‌ها🚨:\n'
            message = title_message + '\n'.join(messages)
            Notification.notify_admins(
                message=message,
                title='هشدار بازار‌های صرافی 🔔',
                channel='important_xchange',
            )


class XchangeCollectTradesFromMarketMakerCron(CronJob):
    schedule = Schedule(run_at_times=['00:30'])
    code = 'xchange_collect_trades_from_market_maker'
    celery_beat = True
    task_name = 'xchange.core.task_collect_trades_from_market_maker'

    def run(self):
        if not Settings.get_flag('is_active_collect_trades_from_market_maker_cron'):
            return
        try:
            TradeCollector().run()
        except Exception as e:
            report_exception()


class XchangeBatchConvertSmallAssetsCron(CronJob):
    schedule = Schedule(run_every_mins=5) if settings.IS_TESTNET else Schedule(run_at_times=['05:00', '13:00', '22:00'])
    code = 'xchange_batch_convert_small_assets'
    celery_beat = True
    task_name = 'xchange.core.task_batch_convert_small_assets'

    def run(self):
        SmallAssetBatchConvertor.batch_convert()
