import requests
from django.conf import settings
from django.http import JsonResponse
from rest_framework import status

from exchange.base.api import NobitexAPIError, ParseError
from exchange.base.api_v2_1 import api, public_api
from exchange.base.decorators import measure_api_execution
from exchange.base.models import parse_market_symbol
from exchange.base.parsers import parse_currency, parse_int, parse_money, parse_str
from exchange.base.sentry import sentry_transaction_sample_rate
from exchange.base.serializers import serialize
from exchange.xchange import exceptions
from exchange.xchange.constants import RESTRICTIONS
from exchange.xchange.helpers import detect_user_agent, has_market_access, has_user_beta_market_feature_flag
from exchange.xchange.marketmaker.client import Client
from exchange.xchange.models import ExchangeTrade, MarketStatus
from exchange.xchange.parsers import parse_order_type_is_sell
from exchange.xchange.serializers import serialize_small_asset_convert_result
from exchange.xchange.small_asset_convertor import SmallAssetConvertor
from exchange.xchange.trader import XchangeTrader
from exchange.xchange.types import RequiredCurrenciesInConvert


@measure_api_execution(api_label='xchangeOptions')
@public_api(rate='20/m')
def options(request):
    symbol = request.g('market')
    if symbol:
        base_currency, quote_currency = parse_market_symbol(symbol)
        if not base_currency or not quote_currency:
            raise NobitexAPIError(
                status_code=404, message='InvalidMarket', description='Requested market does not exist.'
            )
        data = MarketStatus.get_market_status(base_currency=base_currency, quote_currency=quote_currency)

        if not data or not has_market_access(data, request.user):
            raise NobitexAPIError(
                status_code=400,
                message='ConvertOnMarketUnavailable',
                description='Convert on market is not currently available.',
            )
    else:
        data = MarketStatus.get_all_markets_statuses(with_beta_markets=has_user_beta_market_feature_flag(request.user))
        if not data:
            raise NobitexAPIError(
                status_code=400, message='ConvertUnavailable', description='Convert is not currently available.'
            )
    return JsonResponse({'status': 'ok', 'result': serialize(data)}, status=status.HTTP_200_OK)


@sentry_transaction_sample_rate(rate=0.3 if settings.IS_TESTNET else 0.003)
@measure_api_execution(api_label='xchangeGetQuote', with_result=True)
@api(POST='15/m')
def get_quote(request):
    if request.user.is_restricted(*RESTRICTIONS):
        raise NobitexAPIError(
            status_code=status.HTTP_403_FORBIDDEN,
            message='ActionIsRestricted',
            description='You can not get the quote due to the restriction.',
        )

    is_sell = parse_order_type_is_sell(request.g('type'), required=True)
    amount = parse_money(request.g('amount'), required=True)
    ref_currency = parse_currency(request.g('refCurrency'), required=True)
    base_currency = parse_currency(request.g('baseCurrency'), required=True)
    quote_currency = parse_currency(request.g('quoteCurrency'), required=True)
    currencies = RequiredCurrenciesInConvert(base_currency, quote_currency, ref_currency)
    market_status = MarketStatus.get_available_market_status_based_on_side_filter(
        currencies.base,
        currencies.quote,
        is_sell=is_sell,
    )

    if market_status is None or not has_market_access(market_status, request.user):
        raise NobitexAPIError(status_code=400, message='MarketUnavailable', description='Market is not available.')
    if not (ref_currency == base_currency or ref_currency == quote_currency):
        raise NobitexAPIError(status_code=400, message='InvalidRefCurrency', description='refCurrency is invalid.')
    if market_status.has_market_exceeded_limit(amount, is_sell, currencies.ref):
        raise NobitexAPIError(
            status_code=422, message='MarketLimitationExceeded', description='Market limitation exceeded.'
        )
    if market_status.has_user_exceeded_limit(request.user.id, amount, is_sell, currencies.ref):
        raise NobitexAPIError(
            status_code=422, message='UserLimitationExceeded', description='User limitation exceeded.'
        )

    server, _ = Client.get_base_url()
    try:
        response = XchangeTrader.get_quote(
            currencies=currencies, is_sell=is_sell, amount=amount, user=request.user, market_status=market_status
        )
        return response
    except exceptions.XchangeError as e:
        raise NobitexAPIError(status_code=400, message=e.__class__.__name__, description=e.message) from e
    except requests.Timeout as e:
        raise NobitexAPIError(
            status_code=400,
            message='UnavailableDestination',
            description='Destination service is not available. please try again.',
        )
    except requests.HTTPError as e:
        raise NobitexAPIError(status_code=422, message='InvalidRequest', description='Invalid request.')
    except requests.RequestException as e:
        raise NobitexAPIError(status_code=500, message='InternalServerError', description='Unexpected error.')


@sentry_transaction_sample_rate(rate=0.3 if settings.IS_TESTNET else 0.003)
@measure_api_execution(api_label='xchangeCreateTrade', with_result=True)
@api(POST='15/m')
def create_trade(request):
    if request.user.is_restricted(*RESTRICTIONS):
        raise NobitexAPIError(
            status_code=status.HTTP_403_FORBIDDEN,
            message='ActionIsRestricted',
            description='You can not create the trade due to the restriction.',
        )

    try:
        quote_id = parse_str(request.g('quoteId'), required=True)
    except ParseError:
        raise ParseError('quoteId is required')

    try:
        return XchangeTrader.create_trade(request.user.id, quote_id, detect_user_agent(request))
    except (
        exceptions.QuoteIsNotAvailable,
        exceptions.FailedConversion,
        exceptions.FailedAssetTransfer,
        exceptions.PairIsClosed,
        exceptions.MarketUnavailable,
    ) as e:
        raise NobitexAPIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=e.__class__.__name__,
            description=e.message,
        ) from e
    except (
        exceptions.UserLimitationExceeded,
        exceptions.MarketLimitationExceeded,
    ) as e:
        raise NobitexAPIError(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, message=e.__class__.__name__, description=e.message
        ) from e


@measure_api_execution(api_label='xchangeGetTrade')
@api(GET='20/m')
def get_trade(request):
    trade_id = parse_int(request.g('id'), required=True)
    try:
        return XchangeTrader.get_trade(request.user.id, trade_id)
    except ExchangeTrade.DoesNotExist as e:
        raise NobitexAPIError(
            status_code=404,
            message='DoesNotExist',
            description='There is no trade with the given id.',
        ) from e


@measure_api_execution(api_label='xchangeGetTradeHistory')
@api(GET='15/m')
def trades_history(request):
    # TODO add pagination
    return XchangeTrader.trades_history(user_id=request.user.id)


@measure_api_execution(api_label='xchangeSmallAssetsConvert')
@api(POST='10/10m')
def convert_small_assets(request):
    if request.user.is_restricted(*RESTRICTIONS):
        raise NobitexAPIError(
            status_code=status.HTTP_403_FORBIDDEN,
            message='ActionIsRestricted',
            description='You can not convert small assets due to the restriction.',
        )

    dst_currency = parse_currency(request.g('dstCurrency'), required=True)

    sources = request.g('srcCurrencies')
    if not sources:
        raise NobitexAPIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            message='RequiredParameter',
            description='srcCurrencies parameter is required',
        )
    sources = [parse_currency(src, required=True) for src in sources]

    try:
        result = SmallAssetConvertor.convert(request.user, sources, dst_currency)

        serialized_result = serialize_small_asset_convert_result(result)

        all_failed = all(isinstance(result[x], exceptions.XchangeError) for x in result)
        if all_failed:
            return JsonResponse(
                {
                    'status': 'failed',
                    'result': serialized_result,
                    'code': 'ConversionFailed',
                    'message': 'All src conversion failed. Check result for more detail.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return JsonResponse({'status': 'ok', 'result': serialized_result}, status=status.HTTP_200_OK)
    except (
        exceptions.InvalidPair,
        exceptions.MarketUnavailable,
    ) as e:
        raise NobitexAPIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=e.__class__.__name__,
            description=e.message,
        ) from e
