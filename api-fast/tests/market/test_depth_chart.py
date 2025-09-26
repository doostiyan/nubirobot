from unittest.mock import patch

from tests.utils import CacheMock


def test_depth_chart(client):
    symbol = 'BTCUSDT'
    with patch('nobitex.api.market.cache', new=CacheMock({
        f'depth_chart_{symbol}': '{"ask": [["818","10"],["820","110"],["821","1120"],["830","4120"]],'
                                 '"bid": [["810","5682"],["815","682"],["816","673"],["817","50"]],'
                                 '"last_trade_price": "831"}',
        f'depth_chart_{symbol}_update_details': '{"update_time": "1657620166710"}',
    })):
        response = client.get(f'/v2/depth/{symbol}')

    assert response.status_code == 200
    assert response.json['status'] == 'ok'
    assert response.json['lastUpdate'] == '1657620166710'
    assert response.json['lastTradePrice'] == '831'
    assert response.json['asks'] == [["818", "10"], ["820", "110"], ["821", "1120"], ["830", "4120"]]
    assert response.json['bids'] == [["810", "5682"], ["815", "682"], ["816", "673"], ["817", "50"]]


def test_depth_chart_without_cache(client):
    symbol = 'BTCUSDT'
    with patch('nobitex.api.market.cache', new=CacheMock({})):
        response = client.get(f'/v2/depth/{symbol}')

    assert response.status_code == 200
    assert response.json['status'] == 'ok'
    assert response.json['lastUpdate'] == ''
    assert response.json['lastTradePrice'] == '0'
    assert response.json['asks'] == []
    assert response.json['bids'] == []
