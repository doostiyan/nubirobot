from decimal import Decimal
from typing import Dict, List, Optional, Union

from cachetools import TTLCache
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from exchange.asset_backed_credit.currencies import ABCCurrencies
from exchange.asset_backed_credit.exceptions import (
    ClientError,
    FeatureUnavailable,
    InternalAPIError,
    PriceNotAvailableError,
)
from exchange.asset_backed_credit.externals.base import NOBITEX_BASE_URL, PublicAPI
from exchange.base.decorators import measure_time_cm
from exchange.base.logging import report_event
from exchange.base.models import RIAL, Currencies, Settings, get_currency_codename
from exchange.market.markprice import MarkPriceCalculator
from exchange.market.models import Market
from exchange.wallet.estimator import PriceEstimator


class PriceProvider:
    def __init__(self, src_currency: int, dst_currency: int = RIAL):
        self.src_currency = src_currency
        self.dst_currency = dst_currency

    def get_nobitex_price(self) -> Decimal:
        if self.src_currency == self.dst_currency:
            return Decimal(1)

        if self.is_market_api_enabled():
            return self._get_market_price_item_key('bestBuy')

        buy_price, _ = PriceEstimator.get_price_range(self.src_currency, self.dst_currency)
        return Decimal(buy_price)

    def get_last_trade_price(self) -> Decimal:
        if self.src_currency == self.dst_currency:
            return Decimal(1)

        if self.is_market_api_enabled():
            return self._get_market_price_item_key('latest')

        return Market.get_for(self.src_currency, self.dst_currency).get_last_trade_price()

    def get_mark_price(self) -> Decimal:
        if self.src_currency == self.dst_currency:
            return Decimal(1)

        if self.is_market_api_enabled():
            return self._get_market_price_item_key('mark')

        mark_price = MarkPriceCalculator.get_mark_price(self.src_currency, self.dst_currency)

        if not mark_price:
            raise PriceNotAvailableError()
        return mark_price

    def is_market_api_enabled(self) -> bool:
        return Settings.get_flag('abc_use_market_stats_api')

    def _get_market_price_item(self, cache_abc_currencies: bool = True) -> Union['MarketStatsItem', None]:
        src_currency_codename = get_currency_codename(self.src_currency)
        dst_currency_codename = get_currency_codename(self.dst_currency)
        try:
            market_schema = MarketStatAPI(cache_abc_currencies=cache_abc_currencies).request(
                src_currencies=[src_currency_codename],
                dst_currencies=[dst_currency_codename],
            )
        except InternalAPIError as _:
            return None
        return market_schema.get_pair_price_item(src_currency_codename, dst_currency_codename)

    def _get_market_price_item_key(self, key: str) -> Decimal:
        price_item = self._get_market_price_item()
        if price_item is None and price_cache.get(MarketStatAPI.abc_currencies_cache_key) is not None:
            # retrying once more by getting prices of current pairs once more, by ignoring current all abc currencies cache
            price_item = self._get_market_price_item(cache_abc_currencies=False)

        if not price_item:
            raise PriceNotAvailableError()

        price = getattr(price_item, key, None)

        if not price:
            raise PriceNotAvailableError()
        return price


class MarketStatsRequest(BaseModel):
    srcCurrency: Optional[str] = None
    dstCurrency: Optional[str] = None

    model_config = ConfigDict(
        frozen=True,
    )


class MarketStatsItem(BaseModel):
    isClosed: bool
    isClosedReason: Optional[str] = None
    bestSell: Optional[Decimal] = None
    bestBuy: Optional[Decimal] = None
    volumeSrc: Optional[Decimal] = None
    volumeDst: Optional[Decimal] = None
    latest: Optional[Decimal] = None
    mark: Optional[Decimal] = None
    dayLow: Optional[Decimal] = None
    dayHigh: Optional[Decimal] = None
    dayOpen: Optional[Decimal] = None
    dayClose: Optional[Decimal] = None
    dayChange: Optional[Decimal] = None


class MarketGlobalItem(BaseModel):
    binance: Dict[str, Decimal]


class MarketStatsSchema(BaseModel):
    stats: Dict[str, MarketStatsItem]
    global_: MarketGlobalItem = Field(..., alias='global')

    def get_pair_price_item(self, src_currency: str, dst_currency: str) -> Union[MarketStatsItem, None]:
        return self.stats.get(src_currency + '-' + dst_currency, None)

    model_config = ConfigDict(
        frozen=True,
    )


price_cache = TTLCache(maxsize=128, ttl=30)  # seconds


class MarketStatAPI(PublicAPI):
    url = NOBITEX_BASE_URL + '/market/stats'
    method = 'get'
    need_auth = False
    service_name = 'market'
    endpoint_key = 'marketStats'
    error_message = 'MarketStats'
    abc_currencies_cache_key = "abc_market_stats_api_src_all_dst_all"

    def __init__(self, cache_abc_currencies=False):
        super().__init__()
        self.cache_abc_currencies = cache_abc_currencies

    @measure_time_cm(metric='abc_market_stats')
    def request(self, src_currencies: List[str] = [], dst_currencies: List[str] = []) -> MarketStatsSchema:
        if not Settings.get_flag('abc_use_market_stats_api'):
            raise FeatureUnavailable('Market stats API is not enabled')

        params = self._parse_api_params(src_currencies, dst_currencies)

        cached_result = self._get_cached_result(params)
        if cached_result:
            return cached_result

        try:
            response = self._request(params=params)
            response_schema = MarketStatsSchema.model_validate(self.jsonify_response_data(response))
            self._cache_api_result(params, response_schema.model_dump(mode='json', by_alias=True))
            return response_schema
        except (ValueError, ClientError, TypeError, ValidationError) as e:
            report_event(
                f'{self.error_message}: request exception',
                extras={'exception': str(e), 'params': params, 'response': self.response},
            )
            raise InternalAPIError(f'{self.error_message}: Failed to get market stats data') from e

    def _cache_api_result(self, params: dict, response_data: dict):
        key = self._get_cache_key(params)
        price_cache[key] = response_data

    def _get_cached_result(self, params: dict) -> Union[MarketStatsSchema, None]:
        cached = price_cache.get(self._get_cache_key(params))
        if cached:
            return MarketStatsSchema.model_validate(cached)

        return None

    def _get_cache_key(self, params: dict) -> str:
        if self.cache_abc_currencies:
            return self.abc_currencies_cache_key
        src_currency, dst_currency = params.get('srcCurrency', 'all').replace(',', '_'), params.get(
            'dstCurrency', 'all'
        ).replace(',', '_')
        return f"abc_market_stats_api_src_{src_currency}_dst_{dst_currency}"

    def _parse_api_params(self, src_currencies: List[str], dst_currencies: List[str]) -> Dict[str, str]:
        if self.cache_abc_currencies:
            src_currencies = [get_currency_codename(currency_id) for currency_id in ABCCurrencies.get_all_currencies()]
            dst_currencies = None

        parsed_src_currency = ",".join(src_currencies if src_currencies else [])
        parsed_dst_currency = ",".join(dst_currencies if dst_currencies else [])

        return MarketStatsRequest(
            srcCurrency=parsed_src_currency or None, dstCurrency=parsed_dst_currency or None
        ).model_dump(mode='json', exclude_none=True)
