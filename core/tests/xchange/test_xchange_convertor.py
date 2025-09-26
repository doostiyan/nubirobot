import decimal
import functools
from unittest import mock

import pytest
import requests
from django.test import TestCase

from exchange.base.calendar import ir_now
from exchange.base.models import Currencies
from exchange.xchange.exceptions import ConversionTimeout, FailedConversion
from exchange.xchange.marketmaker.convertor import Conversion, Convertor
from exchange.xchange.marketmaker.quotes import Quote


def _patch_call_convert_api_test(test):
    patch_prefix = 'exchange.xchange.marketmaker.convertor'

    @functools.wraps(test)
    @mock.patch(patch_prefix + '.Client.request')
    @mock.patch(patch_prefix + '.Convertor._check_market_maker_integrity')
    @mock.patch(patch_prefix + '.Convertor._create_conversion_body')
    def decorated(*args, **kwargs):
        return test(*args, **kwargs)

    return decorated


class CallConversionApiTest(TestCase):

    @_patch_call_convert_api_test
    def test_a_successful_call(
        self,
        create_conversion_body_mock: mock.MagicMock,
        check_market_maker_integrity_mock: mock.MagicMock,
        client_request_mock: mock.MagicMock,
    ):
        client_request_mock.return_value = {
            'result': {
                'convertId': '10006',
                'quoteId': 'btcusdt-buy-1705766324543',
                'clientId': '545874968',
                'baseCurrency': 'btc',
                'quoteCurrency': 'usdt',
                'state': 'Filled',
                'side': 'buy',
                'referenceCurrency': 'btc',
                'referenceCurrencyAmount': 255.5,
                'destinationCurrencyAmount': 22,
            },
            'message': 'message',
            'error': 'nadarim',
            'hasError': False,
        }

        quote = object()
        conversion = Conversion(
            quote_id='btcusdt-buy-1705766324543',
            base_currency=Currencies.btc,
            quote_currency=Currencies.usdt,
            reference_currency=Currencies.btc,
            reference_amount=decimal.Decimal('255.5'),
            destination_amount=decimal.Decimal('22'),
            is_sell=False,
            client_order_id='545874968',
            convert_id='10006',
        )
        assert Convertor.call_conversion_api(quote) == conversion
        create_conversion_body_mock.assert_called_once_with(quote)
        check_market_maker_integrity_mock.assert_called_once_with(quote, conversion)

    @_patch_call_convert_api_test
    def test_timeout(
        self,
        create_conversion_body_mock: mock.MagicMock,
        check_market_maker_integrity_mock: mock.MagicMock,
        client_request_mock: mock.MagicMock,
    ):
        client_request_mock.side_effect = requests.Timeout
        with pytest.raises(ConversionTimeout):
            Convertor.call_conversion_api(object())

    @_patch_call_convert_api_test
    def test_bad_request(
        self,
        create_conversion_body_mock: mock.MagicMock,
        check_market_maker_integrity_mock: mock.MagicMock,
        client_request_mock: mock.MagicMock,
    ):
        client_request_mock.side_effect = requests.HTTPError
        with pytest.raises(FailedConversion):
            Convertor.call_conversion_api(object())

    @_patch_call_convert_api_test
    def test_bad_request_with_status_ok(
        self,
        create_conversion_body_mock: mock.MagicMock,
        check_market_maker_integrity_mock: mock.MagicMock,
        client_request_mock: mock.MagicMock,
    ):
        client_request_mock.return_value = {
            'result': {
                'convertId': '10006',
                'quoteId': 'btcusdt-buy-1705766324543',
                'clientId': '545874968',
                'baseCurrency': 'btc',
                'quoteCurrency': 'usdt',
                'state': 'Filled',
                'side': 'buy',
                'referenceCurrency': 'btc',
                'referenceCurrencyAmount': 255.5,
                'destinationCurrencyAmount': 22,
            },
            'message': 'message',
            'error': 'darim',
            'hasError': True,
        }
        with pytest.raises(FailedConversion):
            Convertor.call_conversion_api(object())


def test_create_conversion_body():
    assert Convertor._create_conversion_body(
        Quote(
            quote_id='dogeusdt-sell-1705762466449',
            base_currency=Currencies.btc,
            quote_currency=Currencies.usdt,
            reference_currency=Currencies.usdt,
            reference_amount=decimal.Decimal('11.222'),
            destination_amount=decimal.Decimal('11'),
            is_sell=True,
            client_order_id='cl',
            expires_at=ir_now(),
            user_id=1111,
        )
    ) == {
        'quoteId': 'dogeusdt-sell-1705762466449',
        'baseCurrency': 'btc',
        'quoteCurrency': 'usdt',
        'referenceCurrency': 'usdt',
        'referenceCurrencyAmount': '11.222',
        'side': 'sell',
        'clientId': 'cl',
    }


def test_parse_convert_response():
    assert Convertor._parse_conversion_response(
        {
            'convertId': '10005',
            'quoteId': 'dogeusdt-sell-1705762466449',
            'clientId': 'cl22222',
            'baseCurrency': 'doge',
            'quoteCurrency': 'usdt',
            'state': 'Filled',
            'side': 'sell',
            'referenceCurrency': 'usdt',
            'referenceCurrencyAmount': 5000,
            'destinationCurrencyAmount': 63576.34756426297,
        }
    ) == Conversion(
        quote_id='dogeusdt-sell-1705762466449',
        base_currency=Currencies.doge,
        quote_currency=Currencies.usdt,
        reference_currency=Currencies.usdt,
        reference_amount=decimal.Decimal('5000'),
        destination_amount=decimal.Decimal('63576.34756426297'),
        is_sell=True,
        client_order_id='cl22222',
        convert_id='10005',
    )


def generate_check_market_maker_integrity_test():
    common_kwargs = {
        'quote_id': 'agki2oyu3b42gi',
        'base_currency': Currencies.usdt,
        'quote_currency': Currencies.doge,
        'reference_currency': Currencies.doge,
        'reference_amount': decimal.Decimal('1234'),
        'destination_amount': decimal.Decimal('123421233'),
        'is_sell': True,
        'client_order_id': 'g132gh',
    }
    conversion_kwargs = {
        'convert_id': 'g132gh',
    }
    quote_kwargs = {
        'expires_at': ir_now(),
        'user_id': 10006016,
    }
    test_cases = [
        (
            Conversion(**{**common_kwargs, **conversion_kwargs}),
            Quote(**{**common_kwargs, **quote_kwargs}),
            False,
        ),
    ]

    def append_to_test_cases(diff):
        test_cases.append(
            (
                Conversion(**{**common_kwargs, **conversion_kwargs, **diff}),
                Quote(**{**common_kwargs, **quote_kwargs}),
                True,
            )
        )

    append_to_test_cases({'quote_id': 'agki2oyu3b42g125r125r15rti'})
    append_to_test_cases({'base_currency': Currencies.rls})
    append_to_test_cases({'quote_currency': Currencies.shib})
    append_to_test_cases({'reference_currency': Currencies.btc})
    append_to_test_cases({'reference_amount': decimal.Decimal('111234')})
    append_to_test_cases({'destination_amount': decimal.Decimal('1233')})
    append_to_test_cases({'is_sell': False})
    append_to_test_cases({'client_order_id': 'xoaef'})

    return test_cases


@pytest.mark.parametrize(
    (
        'quote',
        'conversion',
        'should_report_exception',
    ),
    generate_check_market_maker_integrity_test(),
)
@mock.patch('exchange.xchange.marketmaker.convertor.report_exception')
def test_check_market_maker_integrity(
    report_exception_mock: mock.MagicMock,
    quote,
    conversion,
    should_report_exception,
):
    Convertor._check_market_maker_integrity(quote, conversion)
    if should_report_exception:
        report_exception_mock.assert_called_once_with()
    else:
        report_exception_mock.assert_not_called()
