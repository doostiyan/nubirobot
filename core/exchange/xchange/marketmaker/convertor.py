import dataclasses
import decimal

import requests

from exchange.base.logging import report_exception
from exchange.base.parsers import parse_currency, parse_decimal, parse_str
from exchange.base.serializers import serialize_currency, serialize_decimal
from exchange.xchange.exceptions import ConversionTimeout, FailedConversion
from exchange.xchange.marketmaker.client import Client
from exchange.xchange.types import Quote


@dataclasses.dataclass
class Conversion:
    convert_id: str
    quote_id: str
    base_currency: int
    quote_currency: int
    reference_currency: int
    reference_amount: decimal.Decimal
    destination_amount: decimal.Decimal
    is_sell: bool
    client_order_id: str

    @property
    def side(self) -> str:
        return 'sell' if self.is_sell else 'buy'


class Convertor:
    PATH = '/xconvert/convert'

    @classmethod
    def call_conversion_api(cls, quote: Quote) -> Conversion:
        server, _ = Client.get_base_url()
        try:
            response = Client.request(
                Client.Method.POST,
                cls.PATH,
                cls._create_conversion_body(quote),
            )
        except requests.RequestException as e:
            if isinstance(e, requests.Timeout):
                raise ConversionTimeout('Convert service is not available.') from e
            raise FailedConversion('Convert service is not available.') from e

        if response['hasError']:
            # Should not reach here, but let be safe and check ...
            raise FailedConversion('Convert service is not available.')

        conversion = cls._parse_conversion_response(response['result'])
        cls._check_market_maker_integrity(quote, conversion)
        return conversion

    @classmethod
    def _create_conversion_body(cls, quote: Quote) -> dict:
        return {
            'quoteId': quote.quote_id,
            'clientId': quote.client_order_id,
            'baseCurrency': serialize_currency(quote.base_currency),
            'quoteCurrency': serialize_currency(quote.quote_currency),
            'side': quote.side,
            'referenceCurrencyAmount': serialize_decimal(quote.reference_amount),
            'referenceCurrency': serialize_currency(quote.reference_currency),
        }

    @classmethod
    def _parse_conversion_response(cls, data: dict) -> Conversion:
        return Conversion(
            convert_id=parse_str(data['convertId'], required=True),
            quote_id=data['quoteId'],
            client_order_id=data['clientId'],
            base_currency=parse_currency(data['baseCurrency']),
            quote_currency=parse_currency(data['quoteCurrency']),
            reference_currency=parse_currency(data['referenceCurrency']),
            reference_amount=parse_decimal(data['referenceCurrencyAmount']),
            destination_amount=parse_decimal(data['destinationCurrencyAmount']),
            is_sell=data['side'] == 'sell',
        )

    @classmethod
    def _check_market_maker_integrity(cls, quote: Quote, conversion: Conversion):
        try:
            for key in (
                'quote_id',
                'base_currency',
                'quote_currency',
                'reference_currency',
                'reference_amount',
                'destination_amount',
                'is_sell',
                'client_order_id',
            ):
                assert getattr(quote, key) == getattr(conversion, key)
        except AssertionError:
            report_exception()

    @classmethod
    def get_conversion(cls, quote: Quote) -> Conversion:
        response = Client.request(Client.Method.GET, cls.PATH + f'?clientId={quote.client_order_id}')
        conversion = cls._parse_conversion_response(response['result'])
        cls._check_market_maker_integrity(quote, conversion)
        return conversion
