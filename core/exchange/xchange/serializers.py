""" Xchange Serializers """
import datetime
from typing import Dict, Union

from exchange.base.calendar import ir_now
from exchange.base.models import get_currency_codename
from exchange.base.serializers import register_serializer
from exchange.xchange.exceptions import XchangeError
from exchange.xchange.models import ExchangeTrade, MarketStatus
from exchange.xchange.types import PairConfig, Quote, XchangePair


def _serialize_trade_base(trade: ExchangeTrade):
    return {
        'id': trade.id,
        'createdAt': trade.created_at,
        'srcSymbol': get_currency_codename(trade.src_currency),
        'dstSymbol': get_currency_codename(trade.dst_currency),
        'srcAmount': trade.src_amount,
        'dstAmount': trade.dst_amount,
        'status': trade.status_code,
    }


@register_serializer(model=ExchangeTrade)
def serialize_exchange_trade(trade, opts=None):
    return {
        **_serialize_trade_base(trade),
        'isSell': trade.is_sell,
    }


@register_serializer(model=PairConfig)
def serialize_pair_config(config, opts=None):
    return {
        'srcPrecision': config.src_precision,
        'dstPrecision': config.dst_precision,
        'isClosed': config.is_closed,
    }


@register_serializer(model=XchangePair)
def serialize_pair(pair, opts=None):
    return str(pair)


@register_serializer(model=MarketStatus)
def serialize_pair_status(pair_status: MarketStatus, opts=None) -> dict:
    is_expired = (
        pair_status.status != MarketStatus.STATUS_CHOICES.delisted  # delisted pairs shouldn't show as expired in client
        and pair_status.updated_at <= (ir_now() - datetime.timedelta(minutes=MarketStatus.EXPIRATION_TIME_IN_MINUTES))
    )

    return {
        'baseCurrency': get_currency_codename(pair_status.base_currency),
        'quoteCurrency': get_currency_codename(pair_status.quote_currency),
        'baseToQuotePriceBuy': pair_status.base_to_quote_price_buy,
        'quoteToBasePriceBuy': pair_status.quote_to_base_price_buy,
        'baseToQuotePriceSell': pair_status.base_to_quote_price_sell,
        'quoteToBasePriceSell': pair_status.quote_to_base_price_sell,
        'minBaseAmount': pair_status.min_base_amount,
        'maxBaseAmount': pair_status.max_base_amount,
        'minQuoteAmount': pair_status.min_quote_amount,
        'maxQuoteAmount': pair_status.max_quote_amount,
        'basePrecision': pair_status.base_precision,
        'quotePrecision': pair_status.quote_precision,
        'status': 'expired' if is_expired else pair_status.get_status_display(),
        'exchangeSide': pair_status.get_exchange_side_display(),
        'updatedAt': pair_status.updated_at,
    }


@register_serializer(model=Quote)
def serialize_quote(quote, opts=None):
    return {
        'baseCurrency': quote.base_currency_code_name,
        'quoteCurrency': quote.quote_currency_code_name,
        'refCurrency': quote.reference_currency_code_name,
        'refAmount': quote.reference_amount,
        'destAmount': quote.destination_amount,
        'quoteId': quote.quote_id,
        'isSell': quote.is_sell,
        'expiresAt': quote.expires_at,
    }


def serialize_small_asset_convert_result(result: Dict[int, Union[str, XchangeError]]) -> Dict[str, Dict[str, str]]:
    return {
        get_currency_codename(currency): {
            'status': 'failed',
            'code': res.__class__.__name__,
            'message': res.message,
        }
        if isinstance(res, XchangeError)
        else {
            'status': 'ok',
            'message': res,
        }
        for currency, res in result.items()
    }
