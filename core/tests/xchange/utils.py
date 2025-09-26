from datetime import timedelta
from decimal import Decimal

from exchange.base.models import Currencies
from exchange.xchange.types import PairConfig, XchangePair

xchange_trader_get_pair_configs_return_value = {
    XchangePair(Currencies.btc, Currencies.usdt): PairConfig(Decimal('0.00001'), Decimal('0.01'), False),
    XchangePair(Currencies.eth, Currencies.usdt): PairConfig(Decimal('0.0001'), Decimal('0.01'), False),
    XchangePair(Currencies.eth, Currencies.btc): PairConfig(Decimal('0.0001'), Decimal('0.00001'), False),
    XchangePair(Currencies.sol, Currencies.btc): PairConfig(Decimal('0.001'), Decimal('0.00001'), False),
    XchangePair(Currencies.sol, Currencies.usdt): PairConfig(Decimal('0.001'), Decimal('0.01'), True),
}
xchange_trader_get_quote_return_value = {
    'price': Decimal('1010.2'),
    'min_amount': Decimal('0.5'),
    'max_amount': Decimal('2.3'),
    'token': 'a' * 32,
    'token_ttl': timedelta(seconds=30),
}


class DummyExchangeTrade:
    def __init__(
        self,
        id,
        user_id,
        is_sell,
        src_currency,
        dst_currency,
        amount,
        price,
        settlement_reference,
    ) -> None:
        self.id = id
        self.user_id = user_id
        self.is_sell = is_sell
        self.src_currency = src_currency
        self.dst_currency = dst_currency
        self.amount = amount
        self.price = price
        self.settlement_reference = settlement_reference

    def save(self):
        pass
