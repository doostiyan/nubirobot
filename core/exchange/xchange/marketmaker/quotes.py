import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from django.core.cache import cache
from django.utils.timezone import make_aware

from exchange.base.calendar import ir_now
from exchange.base.models import Currencies, get_currency_codename
from exchange.xchange.exceptions import QuoteIsNotAvailable
from exchange.xchange.marketmaker.client import Client
from exchange.xchange.types import Quote


class Estimator:
    CACHE_KEY_TEMPLATE = 'xchange_quote_{user_id}_{quote_id}'

    @classmethod
    def estimate(
        cls,
        base_currency: int,
        quote_currency: int,
        is_sell: bool,
        reference_currency: int,
        amount: Decimal,
        user_id: int,
    ) -> Quote:
        client_order_id = uuid.uuid4()
        data = {
            'clientId': client_order_id.hex,
            'baseCurrency': get_currency_codename(base_currency),
            'quoteCurrency': get_currency_codename(quote_currency),
            'side': 'sell' if is_sell else 'buy',
            'referenceCurrency': get_currency_codename(reference_currency),
            'referenceCurrencyAmount': str(amount),
        }
        quote = cls._extract_quote(
            Client().request(Client.Method.POST, '/xconvert/estimate', data),
            user_id=user_id,
        )
        cls.set_quote(quote, user_id)
        return quote

    @classmethod
    def set_quote(cls, quote: Quote, user_id: int):
        cache.set(
            cls.CACHE_KEY_TEMPLATE.format(user_id=user_id, quote_id=quote.quote_id),
            vars(quote),
            (quote.expires_at - ir_now()).total_seconds() + 10 * 60,
        )

    @classmethod
    def invalidate_quote(cls, quote_id: str, user_id: int) -> None:
        try:
            quote = cls.get_quote_even_if_its_expired(quote_id, user_id)
        except QuoteIsNotAvailable:
            return
        quote.expires_at = ir_now()
        cls.set_quote(quote, user_id)

    @classmethod
    def get_quote(cls, quote_id: str, user_id: int) -> Quote:
        quote = cls.get_quote_even_if_its_expired(quote_id, user_id)
        if quote.expires_at < ir_now():
            raise QuoteIsNotAvailable('There is no quote available.')
        return quote

    @classmethod
    def get_quote_even_if_its_expired(cls, quote_id: str, user_id: int) -> Quote:
        raw_quote = cache.get(cls.CACHE_KEY_TEMPLATE.format(user_id=user_id, quote_id=quote_id))
        if raw_quote is None:
            raise QuoteIsNotAvailable('There is no quote available.')
        return Quote(
            quote_id=raw_quote['quote_id'],
            base_currency=raw_quote['base_currency'],
            quote_currency=raw_quote['quote_currency'],
            reference_currency=raw_quote['reference_currency'],
            reference_amount=raw_quote['reference_amount'],
            destination_amount=raw_quote['destination_amount'],
            is_sell=raw_quote['is_sell'],
            client_order_id=raw_quote['client_order_id'],
            expires_at=raw_quote['expires_at'],
            user_id=raw_quote['user_id'],
        )

    @classmethod
    def _extract_quote(cls, response: dict, user_id: int) -> Quote:
        result = response.get('result')
        expiration = make_aware(
            datetime.fromtimestamp(int(result.get('creationTime')) / 1000)  # creationTime is in milliseconds
            + timedelta(milliseconds=result.get('validationTTL'))  # validationTTL is in milliseconds
        )
        return Quote(
            quote_id=result.get('quoteId'),
            base_currency=getattr(Currencies, result.get('baseCurrency')),
            quote_currency=getattr(Currencies, result.get('quoteCurrency')),
            reference_currency=getattr(Currencies, result.get('referenceCurrency')),
            reference_amount=Decimal(result.get('referenceCurrencyRealAmount')),
            destination_amount=Decimal(result.get('destinationCurrencyAmount')),
            is_sell=True if result.get('side') == 'sell' else False,
            client_order_id=result.get('clientId'),
            expires_at=expiration,
            user_id=user_id,
        )
