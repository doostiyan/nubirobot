from datetime import datetime

from celery import shared_task
from celery.schedules import crontab
from django.utils import timezone

from exchange.accounts.models import Notification
from exchange.base.decorators import measure_time_cm
from exchange.base.formatting import f_m
from exchange.base.models import ACTIVE_CRYPTO_CURRENCIES, CURRENCY_CODENAMES, get_market_symbol
from exchange.base.strings import _t
from exchange.celery import app
from exchange.market.conversion_trade_fees import TradeFeeConversion
from exchange.market.inspector import LongTermCandlesCache, LongTermCandlesCacheChartAPI, UpdateMarketCandles
from exchange.market.marketmanager import MarketManager
from exchange.market.markprice import MarkPriceCalculator
from exchange.market.models import Market, MarketCandle, Order, OrderMatching


@shared_task(name='update_recent_trades_cache')
def task_update_recent_trades_cache(symbol):
    MarketManager.update_recent_trades_cache(symbol)


@shared_task(name='update_user_trades_status')
def task_update_user_trades_status(user_id):
    MarketManager.get_latest_user_stats(user_id, force_update=True)


# TODO: Remove this task after the next release.
#       The task `task_matcher_round_whole_trades_async_steps` was retained
#       to handle any previously pending tasks of this type.
#       After the new release, no new tasks of this type will be created.
#       Once a short period has passed to ensure all pending tasks are processed,
#       this task can be safely deleted.
@shared_task(name='commit_trade_async_step')
def task_commit_trade_async_step(trade_id):
    trade = (
        OrderMatching.objects.filter(
            id=trade_id,
        )
        .select_related('buyer', 'seller', 'sell_order', 'buy_order', 'market')
        .get()
    )
    with measure_time_cm(metric='commit_trade_async', labels=(trade.market.symbol,)):
        MarketManager.publish_orders([trade])
        MarketManager.commit_trade_async_step(trade)
        MarketManager.create_bulk_referral_fee([trade])
        MarketManager.update_market_statistics([trade])


@shared_task(name='batch_commit_trade_async_step')
def task_batch_commit_trade_async_step(effective_date: datetime, market_id: int):
    market = Market.get_cached(market_id)
    with measure_time_cm(metric=f'commit_trade_async__{market.symbol}'):
        trades = (
            OrderMatching.objects.filter(created_at=effective_date, market_id=market_id)
            .select_related('buyer', 'seller', 'sell_order', 'buy_order')
            .order_by('id')
        )
        MarketManager.update_market_statistics(trades)

        MarketManager.publish_orders(trades)
        notifs = []
        for trade in trades:
            trade.market = market
            MarketManager.commit_trade_async_step(trade)

            # Send User Notifications
            msg = 'معامله انجام شد: {} {} {}'.format(
                '{}',
                f_m(trade.matched_amount, c=trade.src_currency, exact=True),
                _t(CURRENCY_CODENAMES.get(trade.src_currency)),
            )
            notifs += [
                Notification(user_id=trade.seller_id, message=msg.format('فروش')),
                Notification(user_id=trade.buyer_id, message=msg.format('خرید')),
            ]

        MarketManager.create_bulk_referral_fee(trades)
        Notification.objects.bulk_create(notifs)


@shared_task(name='cancel_order')
def task_cancel_order(order_id):
    """ Admin task to cancel a open order """
    Order.objects.get(id=order_id).do_cancel()


@shared_task(name='update_chart_cache')
def update_chart_cache(days):
    """Update chart data cache"""
    markets = Market.objects.all()
    since = timezone.now() - timezone.timedelta(days=days)
    for resolution in (MarketCandle.RESOLUTIONS.minute, MarketCandle.RESOLUTIONS.hour, MarketCandle.RESOLUTIONS.day):
        UpdateMarketCandles.clear_caches(markets, resolution, since)


@shared_task(name='init_candles_cache')
def init_candles_cache(market_symbol: str, resolution: int, start_bucket: int, end_bucket: int, bucket_length: int):
    """Update long term candles cache asynchronously"""
    assert end_bucket % bucket_length == 0  # Precondition: end_bucket is a valid bucket
    market = Market.by_symbol(market_symbol)

    for candles_cache in (LongTermCandlesCache, LongTermCandlesCacheChartAPI):
        bucket = end_bucket
        while bucket > start_bucket:
            saved = candles_cache.save_bucket_data(market, resolution, bucket - bucket_length, bucket)
            if not saved:
                break
            bucket -= bucket_length


@shared_task(name='notify_stop_order_activation')
def task_notify_stop_order_activation(order_ids):
    """Send notification to users with recently activated stop orders."""
    orders = Order.objects.filter(id__in=order_ids).only('user_id', 'src_currency', 'dst_currency', 'trade_type')
    for order in orders:
        symbol = get_market_symbol(order.src_currency, order.dst_currency)
        Notification.objects.create(
            user_id=order.user_id,
            message=f'سفارش حد ضرر شما در بازار {"تعهدی " if order.is_margin else ""}{symbol} فعال شد.',
        )


@shared_task(name='update_mark_prices')
def task_update_mark_prices():
    with measure_time_cm(metric='mark_prices_update_milliseconds'):
        calculator = MarkPriceCalculator()
        for src_currency in ACTIVE_CRYPTO_CURRENCIES:
            calculator.set_mark_price(src_currency)


@shared_task(name='clear_mark_prices_spread_cache')
def task_clear_mark_prices_spread_cache():
    MarkPriceCalculator.clear_spread_cache()


@shared_task(name='convert_fee_collector_balance', autoretry_for=(Exception,), default_retry_delay=3600, max_retries=5)
def task_convert_fee_collector_balance():
    TradeFeeConversion.run()


app.add_periodic_task(5, task_update_mark_prices)
app.add_periodic_task(3600, task_clear_mark_prices_spread_cache)
app.add_periodic_task(crontab(minute=30, hour=10), task_convert_fee_collector_balance)
