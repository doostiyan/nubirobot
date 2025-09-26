import dataclasses
import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict

from exchange.base.models import get_currency_codename


@dataclasses.dataclass
class PairConfig:
    src_precision: Decimal
    dst_precision: Decimal
    is_closed: bool


@dataclasses.dataclass
class XchangePair:
    src: int
    dst: int

    def __str__(self) -> str:
        return f'{get_currency_codename(self.src)}-{get_currency_codename(self.dst)}'

    def __hash__(self) -> int:
        return hash(str(self))


@dataclasses.dataclass
class RequiredCurrenciesInConvert:
    base: int
    quote: int
    ref: int


@dataclasses.dataclass
class XchangeCurrencyPairPrices:
    buy_price: Decimal
    sell_price: Decimal


@dataclasses.dataclass
class ConsumedPercentageOfMarket:
    symbol: str
    percentage: Decimal
    is_sell: bool


class MarketMakerTradeHistoryItem(BaseModel):
    convertId: str
    referenceCurrencyAmount: Optional[Decimal] = None
    destinationCurrencyAmount: Optional[Decimal] = None
    quoteId: Optional[str] = None
    clientId: Optional[str] = None
    baseCurrency: Optional[str] = None
    quoteCurrency: Optional[str] = None
    status: Optional[str] = None
    side: Optional[str] = None
    createdAt: Optional[int] = None
    referenceCurrency: Optional[str] = None
    response: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra='ignore')


@dataclasses.dataclass
class Quote:
    quote_id: str
    base_currency: int
    quote_currency: int
    reference_currency: int
    reference_amount: Decimal
    destination_amount: Decimal
    is_sell: bool
    client_order_id: str
    expires_at: datetime
    user_id: int

    @property
    def base_currency_code_name(self) -> str:
        return get_currency_codename(self.base_currency)

    @property
    def quote_currency_code_name(self) -> str:
        return get_currency_codename(self.quote_currency)

    @property
    def reference_currency_code_name(self) -> str:
        return get_currency_codename(self.reference_currency)

    @property
    def side(self) -> str:
        return 'sell' if self.is_sell else 'buy'

    @property
    def base_amount(self) -> Decimal:
        return self.reference_amount if self.reference_currency == self.base_currency else self.destination_amount

    @property
    def quote_amount(self) -> Decimal:
        return self.reference_amount if self.reference_currency == self.quote_currency else self.destination_amount
