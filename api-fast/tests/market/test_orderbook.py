from unittest.mock import patch

import pytest

from tests.utils import CacheMock


@pytest.mark.parametrize("version", ('v2', 'v3'))
def test_orderbook_get_wrong_symbol(client, version):
    symbol = 'WRONG'
    response = client.get(f'/{version}/orderbook/{symbol}')
    assert response.status_code == 400
    assert response.json['status'] == 'failed'
    assert response.json['code'] == 'InvalidSymbol'


@pytest.mark.parametrize("version", ('v2', 'v3'))
def test_orderbook_get_market_half_empty_cache(client, version):
    symbol = 'BTCUSDT'
    with patch('nobitex.api.market.cache', new=CacheMock({
        f'orderbook_{symbol}_update_time': '1657620166710',
        f'orderbook_{symbol}_last_trade_price': '19595.05',
    })):
        response = client.get(f'/{version}/orderbook/{symbol}')

    assert response.status_code == 500
    assert response.json['status'] == 'failed'
    assert response.json['code'] == 'UnexpectedError'


@pytest.mark.parametrize("version", ('v2', 'v3'))
def test_orderbook_get_market_full_cache(client, version):
    symbol = 'BTCUSDT'
    with patch('nobitex.api.market.cache', new=CacheMock({
        f'orderbook_{symbol}_update_time': '1657620166710',
        f'orderbook_{symbol}_last_trade_price': '19595.05',
        f'orderbook_{symbol}_bids': '[["19630","0.011121"],["19640","0.000771"],["19670","0.047991"]]',
        f'orderbook_{symbol}_asks': '[["19595.05","0.010206"],["19595","0.003"],["19584","0.010563"]]',
    })):
        response = client.get(f'/{version}/orderbook/{symbol}')

    assert response.status_code == 200
    assert response.json['status'] == 'ok'
    assert response.json['lastUpdate'] == 1657620166710
    assert response.json['lastTradePrice'] == '19595.05'
    if version == 'v2':
        assert response.json['bids'] == [['19630', '0.011121'], ['19640', '0.000771'], ['19670', '0.047991']]
        assert response.json['asks'] == [['19595.05', '0.010206'], ['19595', '0.003'], ['19584', '0.010563']]
    else:
        assert response.json['asks'] == [['19630', '0.011121'], ['19640', '0.000771'], ['19670', '0.047991']]
        assert response.json['bids'] == [['19595.05', '0.010206'], ['19595', '0.003'], ['19584', '0.010563']]


@pytest.mark.parametrize("version", ('v2', 'v3'))
def test_orderbook_get_all_empty_cache(client, version):
    with patch('nobitex.api.market.cache', new=CacheMock({})):
        response = client.get(f'/{version}/orderbook/all')

    assert response.status_code == 500
    assert response.json['status'] == 'failed'
    assert response.json['code'] == 'UnexpectedError'


@pytest.mark.parametrize("version", ('v2', 'v3'))
def test_orderbook_get_all_full_cache(client, version):
    with patch('nobitex.api.market.cache', new=CacheMock({
        f'orderbook_BTCUSDT_update_time': '1657620166710',
        f'orderbook_BTCUSDT_last_trade_price': '19595.05',
        f'orderbook_BTCUSDT_bids': '[["19630","0.011121"],["19640","0.000771"],["19670","0.047991"]]',
        f'orderbook_BTCUSDT_asks': '[["19595.05","0.010206"],["19595","0.003"],["19584","0.010563"]]',
        f'orderbook_BTCIRT_update_time': '1657620166702',
        f'orderbook_BTCIRT_last_trade_price': '6423782000',
        f'orderbook_BTCIRT_bids': '[]',
        f'orderbook_BTCIRT_asks': '[]',
    })):
        response = client.get(f'/{version}/orderbook/all')

    assert response.status_code == 200
    assert response.json['status'] == 'ok'
    assert len(response.json.keys()) == 3
    for symbol in ('BTCUSDT', 'BTCIRT'):
        assert symbol in response.json
        market_data = response.json[symbol]
        assert isinstance(market_data['lastUpdate'], int)
        assert isinstance(market_data['lastTradePrice'], str)
        assert isinstance(market_data['bids'], list)
        assert isinstance(market_data['asks'], list)


@pytest.mark.parametrize("version", ('v2', 'v3'))
def test_orderbook_get_redis_cache(client, version):
    with patch('nobitex.api.market.cache', new=CacheMock({
        f'orderbook_BTCIRT_update_time': '1657620166702',
        f'orderbook_BTCIRT_last_trade_price': '6423782000',
        f'orderbook_BTCIRT_bids': '[["19630","0.011121"],["19640","0.000771"],["19670","0.047991"]]',
        f'orderbook_BTCIRT_asks': '[["19595.05","0.010206"],["19595","0.003"],["19584","0.010563"]]',
    })):
        response = client.get(f'/{version}/orderbook/BTCIRT')
    assert response.status_code == 200
    assert response.json['status'] == 'ok'
    for key in ('bids', 'asks'):
        assert key in response.json


@pytest.mark.parametrize("version", ('v2', 'v3'))
def test_orderbook_get_redis_cache_fail(client, version):
    with patch('nobitex.api.market.cache', new=CacheMock({})):
        response = client.get(f'/{version}/orderbook/BTCIRT')
    assert response.status_code == 500
    assert response.json['status'] == 'failed'
    assert response.json['code'] == 'UnexpectedError'
    assert 'message' in response.json


def test_orderbook_post_no_symbol(client):
    response = client.post('/v2/orderbook')
    assert response.status_code == 400
    assert response.json['status'] == 'failed'
    assert response.json['code'] == 'InvalidSymbol'


def test_orderbook_post_wrong_symbol(client):
    symbol = 'WRONG'
    response = client.post('/v2/orderbook', data={'symbol': symbol})
    assert response.status_code == 400
    assert response.json['status'] == 'failed'
    assert response.json['code'] == 'InvalidSymbol'


def test_orderbook_post_market_empty_cache(client):
    symbol = 'BTCUSDT'
    with patch('nobitex.api.market.cache', new={}):
        response = client.post('/v2/orderbook', data={"symbol": symbol})

    assert response.status_code == 200
    assert response.json['status'] == 'ok'
    assert response.json['bids'] == []
    assert response.json['asks'] == []


def test_orderbook_post_market_full_cache(client):
    symbol = 'BTCUSDT'
    with patch('nobitex.api.market.cache', new={
        f'orderbook_{symbol}_bids': '[["19630","0.011121"],["19640","0.000771"]]',
        f'orderbook_{symbol}_asks': '[["19595.05","0.010206"],["19595","0.003"]]',
    }):
        response = client.post('/v2/orderbook', data={"symbol": symbol})

    assert response.status_code == 200
    assert response.json['status'] == 'ok'
    assert response.json['bids'] == [['19630', '0.011121'], ['19640', '0.000771']]
    assert response.json['asks'] == [['19595.05', '0.010206'], ['19595', '0.003']]


def test_orderbook_post_redis_cache(client):
    response = client.post('/v2/orderbook', data={"symbol": 'BTCIRT'})
    assert response.status_code == 200
    assert response.json['status'] == 'ok'
    assert 'bids' in response.json
    assert 'asks' in response.json
