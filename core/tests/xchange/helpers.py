import datetime
import random
import string
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from django.test import TestCase
from django.utils import text

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies
from exchange.xchange.models import ExchangeTrade, MarketStatus
from tests.xchange.mocks import AVAX_USDT_STATUS, BAT_USDT_STATUS, NEAR_USDT_STATUS, SOL_USDT_STATUS, XRP_USDT_STATUS


def update_exchange_side_configs(config_pairs: Dict[Tuple[int, int], int]):
    for key in config_pairs:
        base_currency = key[0]
        quote_currency = key[1]
        (
            MarketStatus.objects.filter(base_currency=base_currency, quote_currency=quote_currency).update(
                exchange_side=config_pairs[key],
            )
        )


def upsert_dict_as_currency_pair_status(pair_status_dict):
    pair_status_dict = {
        text.camel_case_to_spaces(key).replace(' ', '_'): pair_status_dict[key] for key in pair_status_dict
    }
    base_currency = Currencies._identifier_map.get(pair_status_dict.pop('base_currency'))
    quote_currency = Currencies._identifier_map.get(pair_status_dict.pop('quote_currency'))
    for key in pair_status_dict:
        if key in ('base_precision', 'quote_precision'):
            pair_status_dict[key] = Decimal(f'1e{pair_status_dict[key]}')
        elif key == 'status':
            pair_status_dict[key] = MarketStatus.STATUS_CHOICES._identifier_map.get(pair_status_dict[key])
        else:
            pair_status_dict[key] = Decimal(pair_status_dict[key])
    MarketStatus.objects.update_or_create(
        base_currency=base_currency,
        quote_currency=quote_currency,
        defaults=pair_status_dict,
    )


class MarketMakerStatusAPIMixin:
    @classmethod
    def _get_mocked_response(cls, **kwargs) -> dict:
        mock_response = cls._get_mocked_status_pairs_response(
            [('near', 'usdt'), ('sol', 'usdt'), ('xrp', 'usdt'), ('avax', 'usdt'), ('bat', 'usdt')]
        )
        if 'result' in kwargs:
            if isinstance(kwargs['result'], dict):
                mock_response['result'].update(kwargs['result'])
            elif isinstance(kwargs['result'], str):
                mock_response['result'] = kwargs['result']
        mock_response['message'] = kwargs.get('message') or mock_response['message']
        mock_response['error'] = kwargs.get('error') or mock_response['error']
        mock_response['hasError'] = kwargs.get('hasError') or mock_response['hasError']
        return mock_response

    @classmethod
    def _get_mocked_status_pairs_response(cls, currencies: List[Tuple[str, str]] = None) -> dict:
        return {'result': cls._get_currency_statuses(currencies), 'message': 'message', 'error': '', 'hasError': False}

    @classmethod
    def _get_currency_statuses(cls, currencies: List[Tuple[str, str]] = None) -> Optional[List[dict]]:
        currency_statuses = []
        if ('near', 'usdt') in currencies:
            currency_statuses.append(NEAR_USDT_STATUS)
        if ('sol', 'usdt') in currencies:
            currency_statuses.append(SOL_USDT_STATUS)
        if ('xrp', 'usdt') in currencies:
            currency_statuses.append(XRP_USDT_STATUS)
        if ('avax', 'usdt') in currencies:
            currency_statuses.append(AVAX_USDT_STATUS)
        if ('bat', 'usdt') in currencies:
            currency_statuses.append(BAT_USDT_STATUS)
        return currency_statuses


class BaseMarketLimitationTest(TestCase):
    @staticmethod
    def create_btc_usdt_market():
        return MarketStatus.objects.create(
            base_currency=Currencies.btc,
            quote_currency=Currencies.usdt,
            base_to_quote_price_buy=Decimal('71407'),
            quote_to_base_price_buy=Decimal('0.0000140042'),
            base_to_quote_price_sell=Decimal('69986.5254000000'),
            quote_to_base_price_sell=Decimal('0.0000142885'),
            min_base_amount=Decimal('0.0001000000'),
            max_base_amount=Decimal('2.0000000000'),
            min_quote_amount=Decimal('10.0000000000'),
            max_quote_amount=Decimal('1000.0000000000'),
            base_precision=Decimal('0.0000010000'),
            quote_precision=Decimal('0.0001000000'),
            status=MarketStatus.STATUS_CHOICES.available,
        )

    @staticmethod
    def create_usdt_rls_market():
        return MarketStatus.objects.create(
            base_currency=Currencies.usdt,
            quote_currency=Currencies.rls,
            base_to_quote_price_buy=Decimal('700859.2000000000'),
            quote_to_base_price_buy=Decimal('0.0000014268'),
            base_to_quote_price_sell=Decimal('686891.7000000000'),
            quote_to_base_price_sell=Decimal('0.0000014558'),
            min_base_amount=Decimal('1.0000000000'),
            max_base_amount=Decimal('1000.0000000000'),
            min_quote_amount=Decimal('2500000.0000000000'),
            max_quote_amount=Decimal('800000000.0000000000'),
            base_precision=Decimal('0.0100000000'),
            quote_precision=Decimal('0.1000000000'),
            status=MarketStatus.STATUS_CHOICES.available,
        )

    @staticmethod
    def create_trade(
        user: User,
        status: ExchangeTrade.STATUS,
        is_sell: bool,
        src_currency: int,
        dst_currency: int,
        src_amount: Decimal,
        dst_amount: Decimal,
        created_at: datetime = ir_now(),
    ):
        return ExchangeTrade.objects.update_or_create(
            user=user,
            status=status,
            is_sell=is_sell,
            src_currency=src_currency,
            dst_currency=dst_currency,
            src_amount=src_amount,
            dst_amount=dst_amount,
            quote_id='lkasjdflkjalikafyasdf',
            client_order_id=''.join(random.choices(string.ascii_uppercase + string.digits, k=20)),
            created_at=created_at,
        )[0]
