from unittest.mock import patch

from nobitex.api.base import VALID_MARKET_SYMBOLS
from tests.utils import CacheMock


def test_market_stats_empty_src_and_dst(client):
    response = client.get('/market/stats')
    assert response.status_code == 200
    assert response.json['status'] == 'ok'
    assert len(response.json['stats']) >= len(VALID_MARKET_SYMBOLS)


def test_market_stats_wrong_src_currency(client):
    response = client.get('/market/stats', query_string={'srcCurrency': 'wrong'})
    assert response.status_code == 400
    assert response.json['status'] == 'failed'
    assert response.json['code'] == 'InvalidCurrency'
    assert response.json['message'] == 'The symbol \"wrong\" is not a valid currency.'


def test_market_stats_wrong_dst_currency(client):
    response = client.get('/market/stats', query_string={'srcCurrency': 'btc,eth', 'dstCurrency': 'wrong'})
    assert response.status_code == 400
    assert response.json['status'] == 'failed'
    assert response.json['code'] == 'InvalidCurrency'
    assert response.json['message'] == 'The symbol \"wrong\" is not a valid currency.'


def test_market_stats_market_empty_cache(client):
    with patch('nobitex.api.market.cache', new=CacheMock({})):
        response = client.get('/market/stats', query_string={'srcCurrency': 'btc', 'dstCurrency': 'rls'})

    assert response.status_code == 200
    assert response.json['status'] == 'ok'
    assert 'btc-rls' in response.json['stats']
    market_stats = response.json['stats']['btc-rls']
    assert market_stats['isClosed']
    assert market_stats['isClosedReason'] == 'NoData'


def test_market_stats_get_market_full_cache(client):
    with patch('nobitex.api.market.cache', new=CacheMock({
        'market_stats_10-2':
            '{"isClosed": false, "bestSell": "6424900000", "bestBuy": "6423000000", "volumeSrc": "41.4750388836", '
            '"volumeDst": "271406056025.6186773904", "latest": "6423000000", "dayLow": "6405000000", '
            '"dayHigh": "6698999880", "dayOpen": "6630000010", "dayClose": "6423000000", "dayChange": "-3.12"}',
    })):
        response = client.get('/market/stats', query_string={'srcCurrency': 'btc', 'dstCurrency': 'rls'})

    assert response.status_code == 200
    assert response.json['status'] == 'ok'
    assert 'btc-rls' in response.json['stats']
    assert response.json['stats']['btc-rls'] == {
        'isClosed': False,
        'bestSell': '6424900000',
        'bestBuy': '6423000000',
        'volumeSrc': '41.4750388836',
        'volumeDst': '271406056025.6186773904',
        'latest': '6423000000',
        'dayLow': '6405000000',
        'dayHigh': '6698999880',
        'dayOpen': '6630000010',
        'dayClose': '6423000000',
        'dayChange': '-3.12',
    }


def test_market_stats_get_multiple_markets(client):
    with patch('nobitex.api.market.cache', new=CacheMock({
        'market_stats_10-2': '{"isClosed": false}',
        'market_stats_10-13': '{"isClosed": false}',
        'market_stats_11-2': '{"isClosed": false}',
    })):
        response = client.get('/market/stats', query_string={'srcCurrency': 'btc,eth'})

    assert response.status_code == 200
    assert response.json['status'] == 'ok'
    for pair in ('btc-rls', 'btc-usdt', 'eth-rls', 'eth-usdt'):
        assert pair in response.json['stats']
        if pair == 'eth-usdt':
            assert response.json['stats'][pair]['isClosed']
        else:
            assert not response.json['stats'][pair]['isClosed']


def test_market_stats_post(client):
    with patch('nobitex.api.market.cache', new=CacheMock({})):
        response = client.post('/market/stats', data={'srcCurrency': 'btc', 'dstCurrency': 'rls'})

    assert response.status_code == 200
    assert response.json['status'] == 'ok'
    assert response.json['stats']


def test_market_stats_redis_cache(client):
    response = client.post('/market/stats', data={'srcCurrency': 'btc', 'dstCurrency': 'rls'})
    assert response.status_code == 200
    assert response.json['status'] == 'ok'
    assert 'btc-rls' in response.json['stats']
