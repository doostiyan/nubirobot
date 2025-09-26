import json
import time
from unittest.mock import patch

import pytest

V1_BASE_URL = '/market/udf'


def test_udf_time(client):
    request_time = time.time()
    response = client.get(f'/market/udf/time')
    assert response.status_code == 200
    assert isinstance(response.json, int)
    assert request_time - 1 < response.json < request_time + 1


def test_udf_config(client):
    response = client.get(f'/market/udf/config')
    assert response.status_code == 200
    config = response.json
    assert config['timezone'] == 'Asia/Tehran'
    assert '60' in config['supported_resolutions']
    assert '1D' in config['supported_resolutions']


def test_udf_symbols_no_symbol(client):
    response = client.get(f'/market/udf/symbols')
    assert response.status_code == 400


def test_udf_symbols_wrong_symbol(client):
    response = client.get(f'/market/udf/symbols', query_string={'symbol': 'WRONG'})
    assert response.status_code == 400


def test_udf_symbols_no_cache(client):
    with patch('nobitex.api.udf.cache', new={}):
        response = client.get(f'/market/udf/symbols', query_string={'symbol': 'BTCUSDT'})
    assert response.status_code == 200
    assert 'name' not in response.json


def test_udf_symbols_full_cache(client):
    symbol = 'BTCUSDT'
    with patch('nobitex.api.udf.cache', new={
        f'chart_{symbol}_info':
            '{"name": "BTCUSDT", "ticker": "BTCUSDT", "description": "بیت‌کوین-تتر", "type": "crypto-currency",'
            '"session": "24x7", "has_intraday": true, "supported_resolutions": ["60", "720", "1D", "3D"]}, "daily_multipliers": ["1", "2", "3"]'
    }):
        response = client.get(f'/market/udf/symbols', query_string={'symbol': symbol})
    assert response.status_code == 200
    assert response.json['name'] == symbol
    assert response.json['session'] == '24x7'
    assert '1' not in response.json['supported_resolutions']
    assert '60' in response.json['supported_resolutions']
    assert '1' in response.json['daily_multipliers']


def test_udf_symbols_normalize_symbol(client):
    symbol = 'BTCUSDT'
    with patch(f'nobitex.api.udf.cache', new={
        f'chart_{symbol}_info': '{"name": "BTCUSDT", "ticker": "BTCUSDT", "description": "بیت‌کوین-تتر"}'
    }):
        response = client.get(f'/market/udf/symbols', query_string={'symbol': ':btcusdt'})
    assert response.status_code == 200
    assert response.json['name'] == symbol


def test_udf_symbols_redis_cache(client):
    response = client.get(f'/market/udf/symbols', query_string={'symbol': 'BTCUSDT'})
    assert response.status_code == 200
    assert isinstance(response.json, dict)


def get_sample_search_cache() -> dict:
    symbols = [
        {'name': symbol, 'description': description, 'ticker': symbol, 'exchange': 'نوبیتکس', 'type': 'crypto-currency'}
        for symbol, description in (
            ('AAVEIRT', 'آوه'), ('AAVEUSDT', 'آوه-تتر'),
            ('ADAIRT', 'کاردانو'), ('ADAUSDT', 'کاردانو-تتر'),
            ('BCHIRT', 'بیت\u200cکوین\u200cکش'), ('BCHUSDT', 'بیت\u200cکوین\u200cکش-تتر'),
            ('BNBIRT', 'بایننس کوین'), ('BNBUSDT', 'بایننس کوین-تتر'),
            ('BTCIRT', 'بیت\u200cکوین'), ('BTCUSDT', 'بیت\u200cکوین-تتر'),
            ('DOGEIRT', 'دوج\u200cکوین'), ('DOGEUSDT', 'دوج\u200cکوین-تتر'),
            ('ETCIRT', 'اتریوم کلاسیک'), ('ETCUSDT', 'اتریوم کلاسیک-تتر'),
            ('ETHIRT', 'اتریوم'), ('ETHUSDT', 'اتر-تتر'),
            ('GMTIRT', 'استپن'), ('GMTUSDT', 'استپن-تتر'),
            ('LTCIRT', 'لایت\u200cکوین'), ('LTCUSDT', 'لایت\u200cکوین-تتر'),
            ('PMNUSDT', 'پیمان-تتر'),
            ('SHIBIRT', 'شیبا'), ('SHIBUSDT', 'شیبا-تتر'),
            ('TRXIRT', 'ترون'), ('TRXUSDT', 'ترون-تتر'),
            ('USDTIRT', 'تتر'),
            ('XLMIRT', 'استلار'), ('XLMUSDT', 'استلار-تتر'),
            ('XRPIRT', 'ریپل'), ('XRPUSDT', 'ریپل-تتر'),
        )
    ]

    return {'chart_search_info': json.dumps(symbols)}


def test_udf_search_empty_cache(client):
    with patch('nobitex.api.udf.cache', new={}):
        response = client.get(f'/market/udf/search')
    assert response.status_code == 200
    assert response.json == []


def test_udf_search_no_filter(client):
    with patch('nobitex.api.udf.cache', new=get_sample_search_cache()):
        response = client.get(f'/market/udf/search')
    assert response.status_code == 200
    assert len(response.json) == 30
    assert response.json[0]['symbol'] == 'AAVEIRT'


def test_udf_search_query_symbol(client):
    with patch('nobitex.api.udf.cache', new=get_sample_search_cache()):
        response = client.get(f'/market/udf/search', query_string={'query': 'et'})
    assert response.status_code == 200
    assert len(response.json) == 4
    assert [item['symbol'] for item in response.json] == ['ETCIRT', 'ETCUSDT', 'ETHIRT', 'ETHUSDT']


def test_udf_search_query_description(client):
    with patch('nobitex.api.udf.cache', new=get_sample_search_cache()):
        response = client.get(f'/market/udf/search', query_string={'query': 'بیت'})
    assert response.status_code == 200
    assert len(response.json) == 4
    assert [item['symbol'] for item in response.json] == ['BCHIRT', 'BCHUSDT', 'BTCIRT', 'BTCUSDT']


def test_udf_search_filter_type_and_exchange(client):
    with patch('nobitex.api.udf.cache', new=get_sample_search_cache()):
        response_1 = client.get(f'/market/udf/search', query_string={'type': 'flat-currency'})
        response_2 = client.get(f'/market/udf/search', query_string={'type': 'crypto-currency'})
        response_3 = client.get(f'/market/udf/search', query_string={'exchange': 'binance'})
        response_4 = client.get(f'/market/udf/search', query_string={'exchange': 'نوبیتکس'})
    for response in (response_1, response_2, response_3, response_4):
        assert response.status_code == 200
    assert len(response_1.json) == 0
    assert len(response_2.json) == 30
    assert len(response_3.json) == 0
    assert len(response_4.json) == 30


def test_udf_search_invalid_market(client):
    with patch('nobitex.api.udf.cache', new=get_sample_search_cache()):
        response = client.get(f'/market/udf/search', query_string={'query': 'پیمان'})
    assert response.status_code == 200
    assert len(response.json) == 1
    assert response.json[0]['symbol'] == 'PMNUSDT'


def test_udf_search_limit(client):
    with patch('nobitex.api.udf.cache', new=get_sample_search_cache()):
        response = client.get(f'/market/udf/search', query_string={'limit': 10})
    assert response.status_code == 200
    assert len(response.json) == 10


@pytest.mark.parametrize('endpoint,result', (('quotes', {}),))
def test_udf_stubs(client, endpoint, result):
    response = client.get(f'/market/udf/{endpoint}', query_string={'symbol': 'BTCUSDT'})
    assert response.status_code == 200
    assert response.json == result
