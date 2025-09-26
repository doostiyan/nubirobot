from typing import Optional

from celery import shared_task
from django.db import transaction

from exchange.xchange.constants import GET_MISSED_CONVERSION_STATUS_COUNTDOWN, GET_MISSED_CONVERSION_STATUS_RETRIES
from exchange.xchange.marketmaker.convertor import Convertor
from exchange.xchange.marketmaker.quotes import Estimator
from exchange.xchange.models import ExchangeTrade, SmallAssetConvert


@shared_task(name='xchange.get_missed_conversion_status')
def get_missed_conversion_status_task(exchange_trade_id: int, retry: Optional[int] = 0):
    exchange_trade = ExchangeTrade.objects.get(pk=exchange_trade_id)
    if retry >= GET_MISSED_CONVERSION_STATUS_RETRIES:
        exchange_trade.status = ExchangeTrade.STATUS.failed
        exchange_trade.save()
        return
    try:
        quote = Estimator.get_quote_even_if_its_expired(exchange_trade.quote_id, exchange_trade.user_id)
        conversion = Convertor.get_conversion(quote)
        exchange_trade.convert_id = conversion.convert_id

        from exchange.xchange.trader import XchangeTrader

        with transaction.atomic():
            XchangeTrader.create_and_commit_wallet_transactions(exchange_trade)

    except:
        get_missed_conversion_status_task.apply_async(
            args=(exchange_trade_id, retry + 1),
            countdown=GET_MISSED_CONVERSION_STATUS_COUNTDOWN,
        )


@shared_task(name='xchange.update_small_asset_convert_status')
def update_small_asset_convert_status():
    SmallAssetConvert.objects.filter(
        status=SmallAssetConvert.STATUS.in_progress,
        related_batch_trade__status=ExchangeTrade.STATUS.succeeded,
    ).update(status=SmallAssetConvert.STATUS.succeeded)

    SmallAssetConvert.objects.filter(
        status=SmallAssetConvert.STATUS.in_progress,
        related_batch_trade__status=ExchangeTrade.STATUS.failed,
    ).update(status=SmallAssetConvert.STATUS.failed)
