import sys
import traceback
from decimal import Decimal

from django.db import transaction
from django.db.models import F, OuterRef, Subquery, Sum

from exchange.base.logstash_logging.loggers import logstash_logger
from exchange.xchange.constants import (
    SMALL_ASSET_BATCH_CONVERT_MAX_AMOUNT_THRESHOLD_RATIO,
    UPDATE_SMALL_ASSET_CONVERT_STATUS_COUNTDOWN,
)
from exchange.xchange.helpers import get_small_assets_convert_system_user
from exchange.xchange.models import ExchangeTrade, MarketStatus, SmallAssetConvert
from exchange.xchange.tasks import update_small_asset_convert_status
from exchange.xchange.trader import XchangeTrader
from exchange.xchange.types import RequiredCurrenciesInConvert


class SmallAssetBatchConvertor:
    @classmethod
    def batch_convert(cls):
        base_amount_sum_subquery = (
            SmallAssetConvert.objects.filter(
                src_currency=OuterRef('base_currency'),
                dst_currency=OuterRef('quote_currency'),
                status__in=SmallAssetConvert.WAITING_FOR_CONVERT_STATUSES,
            )
            .values('src_currency', 'dst_currency')
            .annotate(base_amount_sum=Sum('src_amount'))
            .values('base_amount_sum')
        )

        market_statuses = (
            MarketStatus.objects.get_available_market_statuses_based_on_side_filter(is_sell=True)
            .annotate(total_src_amount=Subquery(base_amount_sum_subquery))
            .filter(
                min_base_amount__lte=F('total_src_amount'),
            )
        )

        for market_status in market_statuses:
            try:
                cls._batch_convert_by_market_maker(market_status)
            except Exception:
                logstash_logger.error(
                    'Small Asset Batch Convert failed',
                    extra={
                        'params': {
                            'base_currency': market_status.base_currency,
                            'quote_currency': market_status.quote_currency,
                            'error': ''.join(traceback.format_exception(*sys.exc_info())),
                        },
                        'index_name': 'convert.small_asset_batch_convert',
                    },
                )

        update_small_asset_convert_status.apply_async(countdown=UPDATE_SMALL_ASSET_CONVERT_STATUS_COUNTDOWN)

    @classmethod
    @transaction.atomic
    def _batch_convert_by_market_maker(cls, market_status: MarketStatus):
        related_records = (
            SmallAssetConvert.objects.filter(
                src_currency=market_status.base_currency,
                dst_currency=market_status.quote_currency,
                status__in=SmallAssetConvert.WAITING_FOR_CONVERT_STATUSES,
            )
            .select_for_update(no_key=True)
            .order_by('created_at')
        )

        amount_sum = Decimal('0')
        batch_records = []
        for record in related_records:
            if (amount_sum + record.src_amount) > (
                market_status.max_base_amount * SMALL_ASSET_BATCH_CONVERT_MAX_AMOUNT_THRESHOLD_RATIO
            ):
                logstash_logger.info(
                    'Small Asset Convert items are more than market max.',
                    extra={
                        'params': {
                            'base_currency': market_status.base_currency,
                            'quote_currency': market_status.quote_currency,
                            'total_base_amount': amount_sum,
                            'max_base_amount': market_status.max_base_amount,
                        },
                        'index_name': 'convert.small_asset_batch_convert',
                    },
                )

                break

            amount_sum += record.src_amount
            batch_records.append(record)

        currencies = RequiredCurrenciesInConvert(
            base=market_status.base_currency,
            quote=market_status.quote_currency,
            ref=market_status.base_currency,
        )

        quote = XchangeTrader.get_quote(
            currencies=currencies,
            is_sell=True,
            amount=amount_sum,
            user=get_small_assets_convert_system_user(),
            market_status=market_status,
        )

        trade = XchangeTrader.create_trade(
            user_id=get_small_assets_convert_system_user().id,
            quote_id=quote.quote_id,
            user_agent=ExchangeTrade.USER_AGENT.system,
            bypass_market_limit_validation=True,
            allow_user_wallet_negative_balance=True,
        )

        for record in batch_records:
            record.status = SmallAssetConvert.STATUS.in_progress
            record.related_batch_trade = trade

        SmallAssetConvert.objects.bulk_update(batch_records, fields=['status', 'related_batch_trade'])
