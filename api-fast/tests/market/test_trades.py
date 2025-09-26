from unittest.mock import patch


def test_trades_get_wrong_symbol(client):
    symbol = 'WRONG'
    response = client.get(f'/v2/trades/{symbol}')
    assert response.status_code == 400
    assert response.json['status'] == 'failed'
    assert response.json['code'] == 'InvalidSymbol'


def test_trades_get_market_empty_cache(client):
    symbol = 'BTCUSDT'
    with patch('nobitex.api.market.cache', new={}):
        response = client.get(f'/v2/trades/{symbol}')

    assert response.status_code == 200
    assert response.json['status'] == 'ok'
    assert response.json['trades'] == []


def test_trades_get_market_full_cache(client):
    symbol = 'BTCUSDT'
    with patch('nobitex.api.market.cache', new={
        f'trades_{symbol}': '[{"time":1657621987917,"price":"6415060000","volume":"0.000001","type":"sell"},'
                            '{"time":1657621984697,"price":"6415060000","volume":"0.000383","type":"sell"}]',
    }):
        response = client.get(f'/v2/trades/{symbol}')

    assert response.status_code == 200
    assert response.json['status'] == 'ok'
    assert len(response.json['trades']) == 2
    assert response.json['trades'][0] == {
        'time': 1657621987917, 'price': '6415060000', 'volume': '0.000001', 'type': 'sell'
    }


def test_trades_get_redis_cache(client):
    response = client.get('/v2/trades/BTCIRT')
    assert response.status_code == 200
    assert response.json['status'] == 'ok'
    assert 'trades' in response.json


def test_trades_post_wrong_symbol(client):
    symbol = 'WRONG'
    response = client.post('/v2/trades', data={'symbol': symbol})
    assert response.status_code == 400
    assert response.json['status'] == 'failed'
    assert response.json['code'] == 'InvalidSymbol'


def test_trades_post_market_empty_cache(client):
    symbol = 'BTCUSDT'
    with patch('nobitex.api.market.cache', new={}):
        response = client.post('/v2/trades', data={"symbol": symbol})

    assert response.status_code == 200
    assert response.json['status'] == 'ok'
    assert response.json['trades'] == []


def test_trades_post_market_full_cache(client):
    symbol = 'BTCUSDT'
    with patch('nobitex.api.market.cache', new={
        f'trades_{symbol}': '[{"time":1657621987917,"price":"6415060000","volume":"0.000001","type":"sell"}]',
    }):
        response = client.post('/v2/trades', data={"symbol": symbol})

    assert response.status_code == 200
    assert response.json['status'] == 'ok'
    assert response.json['trades'] == [{
        'time': 1657621987917, 'price': '6415060000', 'volume': '0.000001', 'type': 'sell'
    }]


def test_trades_post_redis_cache(client):
    response = client.post('/v2/trades', data={"symbol": 'BTCIRT'})
    assert response.status_code == 200
    assert response.json['status'] == 'ok'
    assert 'trades' in response.json
