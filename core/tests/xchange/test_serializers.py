from datetime import timedelta
from decimal import Decimal
from typing import Dict, List
from unittest.mock import patch

from django.test import TestCase

from exchange.base.calendar import ir_now
from exchange.base.models import Currencies, get_currency_codename
from exchange.base.serializers import serialize
from exchange.xchange.models import MarketStatus
from tests.xchange.helpers import upsert_dict_as_currency_pair_status
from tests.xchange.mocks import BAT_USDT_STATUS, NEAR_USDT_STATUS, SOL_USDT_STATUS


class SerializersTest(TestCase):
    def setUp(self) -> None:
        upsert_dict_as_currency_pair_status(NEAR_USDT_STATUS)
        unavailable_sol_market = dict(SOL_USDT_STATUS)
        unavailable_sol_market['status'] = 'unavailable'
        upsert_dict_as_currency_pair_status(unavailable_sol_market)
        delisted_bat_market = dict(BAT_USDT_STATUS)
        delisted_bat_market['status'] = 'delisted'
        upsert_dict_as_currency_pair_status(delisted_bat_market)

    def test_market_status_serializer(self):
        now = ir_now()
        before_expiration = now + timedelta(minutes=4)
        after_expiration = now + timedelta(minutes=6)

        all_market_statuses = MarketStatus.objects.all()

        expected_results = [
            {
                'baseCurrency': get_currency_codename(Currencies.near),
                'quoteCurrency': get_currency_codename(Currencies.usdt),
                'baseToQuotePriceBuy': str(NEAR_USDT_STATUS['baseToQuotePriceBuy']),
                'quoteToBasePriceBuy': str(NEAR_USDT_STATUS['quoteToBasePriceBuy']),
                'baseToQuotePriceSell': str(NEAR_USDT_STATUS['baseToQuotePriceSell']),
                'quoteToBasePriceSell': str(NEAR_USDT_STATUS['quoteToBasePriceSell']),
                'maxBaseAmount': str(NEAR_USDT_STATUS['maxBaseAmount']),
                'minBaseAmount': str(NEAR_USDT_STATUS['minBaseAmount']),
                'minQuoteAmount': str(NEAR_USDT_STATUS['minQuoteAmount']),
                'maxQuoteAmount': str(NEAR_USDT_STATUS['maxQuoteAmount']),
                'basePrecision': str(NEAR_USDT_STATUS['basePrecision']),
                'quotePrecision': str(NEAR_USDT_STATUS['quotePrecision']),
                'status': 'Available',
                'exchangeSide': 'both_side',
            },
            {
                'baseCurrency': get_currency_codename(Currencies.sol),
                'quoteCurrency': get_currency_codename(Currencies.usdt),
                'baseToQuotePriceBuy': str(SOL_USDT_STATUS['baseToQuotePriceBuy']),
                'quoteToBasePriceBuy': str(SOL_USDT_STATUS['quoteToBasePriceBuy']),
                'baseToQuotePriceSell': str(SOL_USDT_STATUS['baseToQuotePriceSell']),
                'quoteToBasePriceSell': str(SOL_USDT_STATUS['quoteToBasePriceSell']),
                'minBaseAmount': str(SOL_USDT_STATUS['minBaseAmount']),
                'maxBaseAmount': str(SOL_USDT_STATUS['maxBaseAmount']),
                'minQuoteAmount': str(SOL_USDT_STATUS['minQuoteAmount']),
                'maxQuoteAmount': str(SOL_USDT_STATUS['maxQuoteAmount']),
                'basePrecision': str(SOL_USDT_STATUS['basePrecision']),
                'quotePrecision': str(SOL_USDT_STATUS['quotePrecision']),
                'status': 'Unavailable',
                'exchangeSide': 'both_side',
            },
            {
                'baseCurrency': get_currency_codename(Currencies.bat),
                'quoteCurrency': get_currency_codename(Currencies.usdt),
                'baseToQuotePriceBuy': str(BAT_USDT_STATUS['baseToQuotePriceBuy']),
                'quoteToBasePriceBuy': str(BAT_USDT_STATUS['quoteToBasePriceBuy']),
                'baseToQuotePriceSell': str(BAT_USDT_STATUS['baseToQuotePriceSell']),
                'quoteToBasePriceSell': str(BAT_USDT_STATUS['quoteToBasePriceSell']),
                'minBaseAmount': str(BAT_USDT_STATUS['minBaseAmount']),
                'maxBaseAmount': str(BAT_USDT_STATUS['maxBaseAmount']),
                'minQuoteAmount': str(BAT_USDT_STATUS['minQuoteAmount']),
                'maxQuoteAmount': str(BAT_USDT_STATUS['maxQuoteAmount']),
                'basePrecision': str(BAT_USDT_STATUS['basePrecision']),
                'quotePrecision': str(BAT_USDT_STATUS['quotePrecision']),
                'status': 'Delisted',
                'exchangeSide': 'both_side',
            },
        ]

        with patch('exchange.xchange.serializers.ir_now', return_value=before_expiration):
            serialized_market_statuses = serialize(all_market_statuses)
            self._assert_count_equal(serialized_market_statuses, expected_results)

        with patch('exchange.xchange.serializers.ir_now', return_value=after_expiration):
            serialized_market_statuses = serialize(all_market_statuses)
            for expected_result in expected_results:
                if expected_result['status'] == 'Delisted':
                    continue
                expected_result['status'] = 'expired'

            self._assert_count_equal(serialized_market_statuses, expected_results)

    def _assert_count_equal(self, results: List[Dict], expected_results: List[Dict]):
        assert len(results) == len(expected_results)
        for result in results:
            assert {
                'baseCurrency',
                'quoteCurrency',
                'baseToQuotePriceBuy',
                'quoteToBasePriceBuy',
                'baseToQuotePriceSell',
                'quoteToBasePriceSell',
                'minBaseAmount',
                'maxBaseAmount',
                'minQuoteAmount',
                'maxQuoteAmount',
                'basePrecision',
                'quotePrecision',
                'status',
                'exchangeSide',
                'updatedAt',
            }.issubset(result.keys())

            for expected_result in expected_results:
                if (
                    result['baseCurrency'] == expected_result['baseCurrency']
                    and result['quoteCurrency'] == expected_result['quoteCurrency']
                ):
                    for key in expected_result:
                        assert key in result
                        if key in ('basePrecision', 'quotePrecision'):
                            assert result[key] == str(Decimal(f'1e{expected_result[key]}'))
                        elif key in ('baseCurrency', 'quoteCurrency', 'status', 'exchangeSide'):
                            assert result[key].lower() == expected_result[key].lower()
                        else:
                            assert round(Decimal(result[key]), 6) == round(Decimal(expected_result[key]), 6)
