from nobitex.api.base import CURRENCIES, VALID_MARKET_SYMBOLS


def test_currencies_codes():
    assert CURRENCIES['btc'] == 10
    assert CURRENCIES['usdt'] == 13
    assert CURRENCIES['shib'] == 42
    assert CURRENCIES['ftm'] == 75
    assert CURRENCIES['one'] == 100


def test_market_symbols():
    assert 'BTCIRT' in VALID_MARKET_SYMBOLS
    assert 'BTCUSDT' in VALID_MARKET_SYMBOLS
    assert 'BTCCIRT' not in VALID_MARKET_SYMBOLS
    assert 'USDTUSDT' not in VALID_MARKET_SYMBOLS
    assert 'PMNIRT' not in VALID_MARKET_SYMBOLS
