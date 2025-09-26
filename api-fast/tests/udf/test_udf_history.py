import datetime
from typing import Literal, Union, Optional
from unittest.mock import patch


def test_udf_history_wrong_symbol(client):
    response = client.get('/market/udf/history', query_string={'symbol': 'WRONG'})
    assert response.status_code == 400


def test_udf_history_wrong_resolution(client):
    symbol = 'BTCUSDT'
    response = client.get('/market/udf/history', query_string={'symbol': symbol, 'resolution': '1W'})
    assert response.status_code == 200
    assert response.json['s'] == 'error'
    assert response.json['errmsg'] == 'Invalid resolution!'


def test_udf_history_empty_cache(client):
    symbol = 'BTCUSDT'
    with patch('nobitex.api.udf.cache', new={}):
        response = client.get('/market/udf/history', query_string={
            'symbol': symbol, 'resolution': '60', 'from': 1657619856, 'to': 1657630656
        })
    assert response.status_code == 200
    assert response.json['s'] == 'no_data'


def get_sample_bucket_cache(
        symbol: str,
        resolution: Literal['minute', 'hour', 'day'],
        bucket: int,
        avg_price: Union[int, float],
        dst_change_range: Optional[range] = None,
        data_range: Optional[range] = 0,
) -> dict:
    if resolution == 'minute':
        step = 60
    elif resolution == 'hour':
        step = 3600
    elif resolution == 'day':
        step = 24 * 3600
    else:
        step = 1
    start_time = bucket + -(bucket + 12600) % step
    data_range = data_range or range(200)
    result = {
        'time': [i * step + start_time for i in data_range],
        'open': [i + avg_price + 50 for i in data_range],
        'high': [i + avg_price + 250 for i in data_range],
        'low': [i + avg_price - 250 for i in data_range],
        'close': [i + avg_price - 50 for i in data_range],
        'volume': [(i + 1) / 10 for i in data_range],
    }
    if dst_change_range:
        for i in dst_change_range:
            result['time'][i] -= 3600
    return {f'marketdata_{symbol}_{resolution}_{bucket}': result}


def datestr_to_timestamp(datestr_list: list) -> list:
    return [datetime.datetime.fromisoformat(datestr).timestamp() for datestr in datestr_list]


def test_udf_history_minute_resolution(client):
    symbol = 'BTCUSDT'
    with patch('nobitex.api.udf.cache', new=get_sample_bucket_cache(symbol, 'minute', 1657620000, 19650)):
        # Bitcoin-Tether minute candles from 2022-07-12T17:22:36 to 2022-07-12T17:27:36
        response = client.get('/market/udf/history', query_string={
            'symbol': symbol, 'resolution': '1', 'from': 1657630356, 'to': 1657630656
        })
    assert response.status_code == 200
    assert response.json['s'] == 'ok'
    assert response.json['t'] == datestr_to_timestamp([
        '2022-07-12 17:23', '2022-07-12 17:24', '2022-07-12 17:25', '2022-07-12 17:26', '2022-07-12 17:27'
    ])
    assert response.json['o'] == [19873, 19874, 19875, 19876, 19877]
    assert response.json['h'] == [20073, 20074, 20075, 20076, 20077]
    assert response.json['l'] == [19573, 19574, 19575, 19576, 19577]
    assert response.json['c'] == [19773, 19774, 19775, 19776, 19777]
    assert response.json['v'] == [17.4, 17.5, 17.6, 17.7, 17.8]


def test_udf_history_aggregated_minute_resolution(client):
    symbol = 'BTCUSDT'
    with patch('nobitex.api.udf.cache', new=get_sample_bucket_cache(symbol, 'minute', 1657620000, 19650)):
        # Bitcoin-Tether 5-minute candles from 2022-07-12T17:07:36 to 2022-07-12T17:27:36
        response = client.get('/market/udf/history', query_string={
            'symbol': symbol, 'resolution': '5', 'from': 1657629456, 'to': 1657630656
        })
    assert response.status_code == 200
    assert response.json['s'] == 'ok'
    assert response.json['t'] == datestr_to_timestamp([
        '2022-07-12 17:10', '2022-07-12 17:15', '2022-07-12 17:20', '2022-07-12 17:25'
    ])
    assert response.json['o'] == [19860, 19865, 19870, 19875]
    assert response.json['h'] == [20064, 20069, 20074, 20079]
    assert response.json['l'] == [19560, 19565, 19570, 19575]
    assert response.json['c'] == [19764, 19769, 19774, 19779]
    assert response.json['v'] == [81.5, 84, 86.5, 89]


def test_udf_history_minute_resolution_multiple_cache(client):
    symbol = 'BTCUSDT'
    with patch('nobitex.api.udf.cache', new={
        **get_sample_bucket_cache(symbol, 'minute', 1657596000, 19550),
        **get_sample_bucket_cache(symbol, 'minute', 1657608000, 19600),
        **get_sample_bucket_cache(symbol, 'minute', 1657620000, 19650),
    }):
        # Bitcoin-Tether minute candles from 2022-07-12T10:24:17 to 2022-07-12T15:24:17
        response = client.get('/market/udf/history', query_string={
            'symbol': symbol, 'resolution': '1', 'from': 1657605257, 'to': 1657623257
        })
    assert response.status_code == 200
    assert response.json['s'] == 'ok'
    assert len(response.json['t']) == 300
    assert response.json['t'][:3] == datestr_to_timestamp(['2022-07-12 10:25', '2022-07-12 10:26', '2022-07-12 10:27'])
    assert response.json['t'][44:46] == datestr_to_timestamp(['2022-07-12 11:09', '2022-07-12 11:10'])
    assert response.json['t'][244:246] == datestr_to_timestamp(['2022-07-12 14:29', '2022-07-12 14:30'])
    assert response.json['t'][-3:] == datestr_to_timestamp(['2022-07-12 15:22', '2022-07-12 15:23', '2022-07-12 15:24'])
    assert response.json['o'][43:47] == [19798, 19799, 19650, 19651]
    assert response.json['h'][43:47] == [19998, 19999, 19850, 19851]
    assert response.json['l'][43:47] == [19498, 19499, 19350, 19351]
    assert response.json['c'][43:47] == [19698, 19699, 19550, 19551]
    assert response.json['v'][43:47] == [19.9, 20, 0.1, 0.2]
    assert response.json['o'][243:247] == [19848, 19849, 19700, 19701]
    assert response.json['h'][243:247] == [20048, 20049, 19900, 19901]
    assert response.json['l'][243:247] == [19548, 19549, 19400, 19401]
    assert response.json['c'][243:247] == [19748, 19749, 19600, 19601]
    assert response.json['v'][243:247] == [19.9, 20, 0.1, 0.2]


def test_udf_history_hour_resolution(client):
    symbol = 'BTCUSDT'
    with patch('nobitex.api.udf.cache', new=get_sample_bucket_cache(symbol, 'hour', 1657440000, 19650)):
        # Bitcoin-Tether hour candles from 2022-07-12T14:27:36 to 2022-07-12T17:27:36
        response = client.get('/market/udf/history', query_string={
            'symbol': symbol, 'resolution': '60', 'from': 1657619856, 'to': 1657630656
        })
    assert response.status_code == 200
    assert response.json['s'] == 'ok'
    assert response.json['t'] == datestr_to_timestamp(['2022-07-12 15:00', '2022-07-12 16:00', '2022-07-12 17:00'])
    assert response.json['o'] == [19750, 19751, 19752]
    assert response.json['h'] == [19950, 19951, 19952]
    assert response.json['l'] == [19450, 19451, 19452]
    assert response.json['c'] == [19650, 19651, 19652]
    assert response.json['v'] == [5.1, 5.2, 5.3]


def test_udf_history_aggregated_hour_resolution(client):
    symbol = 'BTCUSDT'
    with patch('nobitex.api.udf.cache', new=get_sample_bucket_cache(symbol, 'hour', 1657440000, 19650)):
        # Bitcoin-Tether 3-hour candles from 2022-07-12T11:27:36 to 2022-07-12T17:27:36
        response = client.get('/market/udf/history', query_string={
            'symbol': symbol, 'resolution': '180', 'from': 1657609056, 'to': 1657630656
        })
    assert response.status_code == 200
    assert response.json['s'] == 'ok'
    assert response.json['t'] == datestr_to_timestamp(['2022-07-12 12:00', '2022-07-12 15:00'])
    assert response.json['o'] == [19747, 19750]
    assert response.json['h'] == [19949, 19952]
    assert response.json['l'] == [19447, 19450]
    assert response.json['c'] == [19649, 19652]
    assert response.json['v'] == [14.7, 15.6]


def test_udf_history_aggregated_hour_resolution_with_spring_dst_in_range(client):
    symbol = 'BTCUSDT'
    with patch('nobitex.api.udf.cache', new=get_sample_bucket_cache(symbol, 'hour', 1647360000, 19650)):
        # Bitcoin-Tether 4-hour candles from 2022-03-21T19:06:51 to 2022-03-22T09:06:51
        response = client.get('/market/udf/history', query_string={
            'symbol': symbol, 'resolution': '240', 'from': 1647877011, 'to': 1647923811
        })
    assert response.status_code == 200
    assert response.json['s'] == 'ok'
    assert response.json['t'] == datestr_to_timestamp([
        '2022-03-21 20:00', '2022-03-22 01:00', '2022-03-22 04:00', '2022-03-22 08:00'
    ])
    assert response.json['o'] == [19844, 19848, 19851, 19855]
    assert response.json['h'] == [20047, 20050, 20054, 20058]
    assert response.json['l'] == [19544, 19548, 19551, 19555]
    assert response.json['c'] == [19747, 19750, 19754, 19758]
    assert response.json['v'] == [58.6, 45.0, 61.4, 63.0]


def test_udf_history_aggregated_hour_resolution_with_fall_dst_in_range(client):
    symbol = 'BTCUSDT'
    with patch('nobitex.api.udf.cache', new=get_sample_bucket_cache(symbol, 'hour', 1632240000, 19650)):
        # Bitcoin-Tether 3-hour candles from 2021-09-21T20:06:17 to 2021-09-22T05:06:17
        response = client.get('/market/udf/history', query_string={
            'symbol': symbol, 'resolution': '180', 'from': 1632238577, 'to': 1632274577
        })
    assert response.status_code == 200
    assert response.json['s'] == 'ok'
    assert response.json['t'] == datestr_to_timestamp(['2021-09-21 21:00', '2021-09-22 00:00', '2021-09-22 03:00'])
    assert response.json['o'] == [19700, 19704, 19707]
    assert response.json['h'] == [19903, 19906, 19909]
    assert response.json['l'] == [19400, 19404, 19407]
    assert response.json['c'] == [19603, 19606, 19609]
    assert response.json['v'] == [1, 1.8, 2.7]


def test_udf_history_day_resolution(client):
    symbol = 'BTCUSDT'
    with patch(
        'nobitex.api.udf.cache', new=get_sample_bucket_cache(symbol, 'day', 1641600000, 19650, range(73, 200)),
    ):
        # Bitcoin-Tether day candles from 2022-07-08T17:27:36 to 2022-07-12T17:27:36
        response = client.get('/market/udf/history', query_string={
            'symbol': symbol, 'resolution': 'D', 'from': 1657285056, 'to': 1657630656
        })
    assert response.status_code == 200
    assert response.json['s'] == 'ok'
    assert response.json['t'] == datestr_to_timestamp(['2022-07-09', '2022-07-10', '2022-07-11', '2022-07-12'])
    assert response.json['o'] == [19881, 19882, 19883, 19884]
    assert response.json['h'] == [20081, 20082, 20083, 20084]
    assert response.json['l'] == [19581, 19582, 19583, 19584]
    assert response.json['c'] == [19781, 19782, 19783, 19784]
    assert response.json['v'] == [18.2, 18.3, 18.4, 18.5]


def test_udf_history_day_resolution_with_spring_dst_in_range(client):
    symbol = 'BTCUSDT'
    with patch(
        'nobitex.api.udf.cache', new=get_sample_bucket_cache(symbol, 'day', 1641600000, 19650, range(73, 200))
    ):
        # Bitcoin-Tether day candles from 2022-03-20T00:00:42 to 2022-03-25T01:00:42
        response = client.get('/market/udf/history', query_string={
            'symbol': symbol, 'resolution': 'D', 'from': 1647721842, 'to': 1648153842
        })
    assert response.status_code == 200
    assert response.json['s'] == 'ok'
    assert response.json['t'] == datestr_to_timestamp([
        '2022-03-21', '2022-03-22', '2022-03-23', '2022-03-24', '2022-03-25'
    ])
    assert response.json['o'] == [19771, 19772, 19773, 19774, 19775]
    assert response.json['h'] == [19971, 19972, 19973, 19974, 19975]
    assert response.json['l'] == [19471, 19472, 19473, 19474, 19475]
    assert response.json['c'] == [19671, 19672, 19673, 19674, 19675]
    assert response.json['v'] == [7.2, 7.3, 7.4, 7.5, 7.6]


def test_udf_history_day_resolution_with_fall_dst_in_range(client):
    symbol = 'BTCUSDT'
    with patch('nobitex.api.udf.cache', new=get_sample_bucket_cache(symbol, 'day', 1624320000, 19650, range(0, 91))):
        # Bitcoin-Tether day candles from 2021-09-19T00:01:17 to 2021-09-24T00:01:17
        response = client.get('/market/udf/history', query_string={
            'symbol': symbol, 'resolution': 'D', 'from': 1631993477, 'to': 1632429077
        })
    assert response.status_code == 200
    assert response.json['s'] == 'ok'
    assert response.json['t'] == datestr_to_timestamp([
        '2021-09-20', '2021-09-21', '2021-09-22', '2021-09-23', '2021-09-24'
    ])
    assert response.json['o'] == [19789, 19790, 19791, 19792, 19793]
    assert response.json['h'] == [19989, 19990, 19991, 19992, 19993]
    assert response.json['l'] == [19489, 19490, 19491, 19492, 19493]
    assert response.json['c'] == [19689, 19690, 19691, 19692, 19693]
    assert response.json['v'] == [9, 9.1, 9.2, 9.3, 9.4]


def test_udf_history_aggregated_day_resolution(client):
    symbol = 'BTCUSDT'
    with patch(
        'nobitex.api.udf.cache', new=get_sample_bucket_cache(symbol, 'day', 1641600000, 19650, range(73, 200)),
    ):
        # Bitcoin-Tether 2-day candles from 2022-07-06T17:26:52 to 2022-07-12T17:26:52
        response = client.get('/market/udf/history', query_string={
            'symbol': symbol, 'resolution': '2D', 'from': 1657112212, 'to': 1657630612
        })
    assert response.status_code == 200
    assert response.json['s'] == 'ok'
    assert response.json['t'] == datestr_to_timestamp(['2022-07-07', '2022-07-09', '2022-07-11'])
    assert response.json['o'] == [19879, 19881, 19883]
    assert response.json['h'] == [20080, 20082, 20084]
    assert response.json['l'] == [19579, 19581, 19583]
    assert response.json['c'] == [19780, 19782, 19784]
    assert response.json['v'] == [36.1, 36.5, 36.9]


def test_udf_history_aggregated_day_resolution_with_spring_dst_in_range(client):
    symbol = 'BTCUSDT'
    with patch(
        'nobitex.api.udf.cache', new=get_sample_bucket_cache(symbol, 'day', 1641600000, 19650, range(73, 200)),
    ):
        # Bitcoin-Tether 2-day candles from 2022-03-17T01:00:42 to 2022-03-25T01:00:42
        response_2d = client.get('/market/udf/history', query_string={
            'symbol': symbol, 'resolution': '2D', 'from': 1647466242, 'to': 1648153842
        })
        # Bitcoin-Tether 3-day candles from 2022-03-17T01:00:42 to 2022-03-25T01:00:42
        response_3d = client.get('/market/udf/history', query_string={
            'symbol': symbol, 'resolution': '3D', 'from': 1647466242, 'to': 1648153842
        })
    for response in (response_2d, response_3d):
        assert response.status_code == 200
        assert response.json['s'] == 'ok'
    assert response_2d.json['t'] == datestr_to_timestamp(['2022-03-19', '2022-03-21', '2022-03-23', '2022-03-25'])
    assert response_2d.json['v'] == [14.1, 14.5, 14.9, 15.3]
    assert response_3d.json['t'] == datestr_to_timestamp(['2022-03-20', '2022-03-23'])
    assert response_3d.json['v'] == [21.6, 22.5]


def test_udf_history_aggregated_day_resolution_with_fall_dst_in_range(client):
    symbol = 'BTCUSDT'
    with patch('nobitex.api.udf.cache', new=get_sample_bucket_cache(symbol, 'day', 1624320000, 19650, range(0, 91))):
        # Bitcoin-Tether 2-day candles from 2021-09-18T02:06:17 to 2021-09-24T03:51:17
        response_2d = client.get('/market/udf/history', query_string={
            'symbol': symbol, 'resolution': '2D', 'from': 1631914577, 'to': 1632429077
        })
        # Bitcoin-Tether 3-day candles from 2021-09-18T02:06:17 to 2021-09-24T03:51:17
        response_3d = client.get('/market/udf/history', query_string={
            'symbol': symbol, 'resolution': '3D', 'from': 1631914577, 'to': 1632429077
        })
    for response in (response_2d, response_3d):
        assert response.status_code == 200
        assert response.json['s'] == 'ok'
    assert response_2d.json['t'] == datestr_to_timestamp(['2021-09-20', '2021-09-22', '2021-09-24'])
    assert response_2d.json['v'] == [18.1, 18.5, 18.9]
    assert response_3d.json['t'] == datestr_to_timestamp(['2021-09-21', '2021-09-24'])
    assert response_3d.json['v'] == [27.6, 28.5]


def test_udf_history_before_market_first_candle(client):
    symbol = 'BTCUSDT'
    with patch(
        'nobitex.api.udf.cache',
        new=get_sample_bucket_cache(symbol, 'day', 1641600000, 19650, data_range=range(156, 200)),
    ):
        # Bitcoin-Tether day candles from 2022-03-10T17:27:36 to 2022-03-10T17:27:36
        response = client.get('/market/udf/history', query_string={
            'symbol': symbol, 'resolution': 'D', 'from': 1646917056, 'to': 1647262656
        })
    assert response.status_code == 200
    assert response.json['s'] == 'no_data'


def test_udf_history_after_current_candle(client):
    symbol = 'BTCUSDT'
    with patch(
        'nobitex.api.udf.cache', new=get_sample_bucket_cache(symbol, 'hour', 1657440000, 19650, data_range=range(61))
    ):
        # Bitcoin-Tether hour candles from 2022-07-13T05:27:36 to 2022-07-13T08:27:36
        response = client.get('/market/udf/history', query_string={
            'symbol': symbol, 'resolution': '60', 'from': 1657673856, 'to': 1657684656
        })
    assert response.status_code == 200
    assert response.json['s'] == 'no_data'


def test_udf_history_price_precision(client):
    with patch('nobitex.api.udf.cache', new=get_sample_bucket_cache('BTCUSDT', 'minute', 1657620000, 19650.345)):
        # Bitcoin-Tether minute candles from 2022-07-12T17:22:36 to 2022-07-12T17:25:36
        response = client.get('/market/udf/history', query_string={
            'symbol': 'BTCUSDT', 'resolution': '1', 'from': 1657630356, 'to': 1657630536
        })
    assert response.status_code == 200 and response.json['s'] == 'ok'
    assert response.json['o'] == [19873.35, 19874.35, 19875.35]

    with patch('nobitex.api.udf.cache', new=get_sample_bucket_cache('DOGEIRT', 'hour', 1657440000, 20156)):
        # Doge-Toman hour candles from 2022-07-12T14:27:36 to 2022-07-12T17:27:36
        response = client.get('/market/udf/history', query_string={
            'symbol': 'DOGEIRT', 'resolution': '60', 'from': 1657619856, 'to': 1657630656
        })
    assert response.status_code == 200 and response.json['s'] == 'ok'
    assert response.json['h'] == [2045.6, 2045.7, 2045.8]

    with patch(
        'nobitex.api.udf.cache', new=get_sample_bucket_cache('USDTIRT', 'day', 1641600000, 332058, range(73, 200)),
    ):
        # 1000Shiba-Toman day candles from 2022-07-04T23:27:36 to 2022-07-07T23:27:36
        response = client.get('/market/udf/history', query_string={
            'symbol': 'USDTIRT', 'resolution': 'D', 'from': 1656961056, 'to': 1657220256
        })
    assert response.status_code == 200 and response.json['s'] == 'ok'
    assert response.json['c'] == [33218, 33219, 33219]

    with patch('nobitex.api.udf.cache', new=get_sample_bucket_cache('BNBUSDT', 'minute', 1657620000, 293.87654)):
        # BinanceCoin-Tether minute candles from 2022-07-12T17:22:36 to 2022-07-12T17:25:36
        response = client.get('/market/udf/history', query_string={
            'symbol': 'BNBUSDT', 'resolution': '1', 'from': 1657630356, 'to': 1657630536
        })
    assert response.status_code == 200 and response.json['s'] == 'ok'
    assert response.json['l'] == [216.8765, 217.8765, 218.8765]


def test_udf_history_count_back(client):
    with patch('nobitex.api.udf.cache', new=get_sample_bucket_cache('BTCUSDT', 'minute', 1657620000, 19650.345)):
        # Bitcoin-Tether minute candles 5 before 2022-07-12T17:25:36
        response = client.get('/market/udf/history', query_string={
            'symbol': 'BTCUSDT', 'resolution': '1', 'to': 1657630536, 'countback': 5
        })
    assert response.status_code == 200 and response.json['s'] == 'ok'
    assert response.json['o'] == [19871.35, 19872.35, 19873.35, 19874.35, 19875.35]


def test_udf_history_count_back_precedence(client):
    with patch('nobitex.api.udf.cache', new=get_sample_bucket_cache('DOGEIRT', 'hour', 1657440000, 20156)):
        # Doge-Toman hour candles 4 before 2022-07-12T17:27:36 from 2022-07-12T14:27:36
        response = client.get('/market/udf/history', query_string={
            'symbol': 'DOGEIRT', 'resolution': '60', 'from': 1657619856, 'to': 1657630656, 'countback': 4
        })
    assert response.status_code == 200 and response.json['s'] == 'ok'
    assert response.json['t'] == datestr_to_timestamp([
        '2022-07-12 14', '2022-07-12 15', '2022-07-12 16', '2022-07-12 17'
    ])
    assert response.json['h'] == [2045.5, 2045.6, 2045.7, 2045.8]

    with patch(
        'nobitex.api.udf.cache', new=get_sample_bucket_cache('USDTIRT', 'day', 1641600000, 332058, range(73, 200)),
    ):
        # 1000Shiba-Toman day candles 2 before 2022-07-07T23:27:36 from 2022-07-04T23:27:36
        response = client.get('/market/udf/history', query_string={
            'symbol': 'USDTIRT', 'resolution': 'D', 'from': 1656961056, 'to': 1657220256, 'countback': 2
        })
    assert response.status_code == 200 and response.json['s'] == 'ok'
    assert response.json['t'] == datestr_to_timestamp(['2022-07-06', '2022-07-07'])
    assert response.json['c'] == [33219, 33219]
