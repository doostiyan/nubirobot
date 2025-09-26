from exchange.base.management.commands.send_emails import parse_prices_from_tickers
from .utils import get_data


def test_parse_prices_from_tickers_spot():
    tickers = get_data('binance_tickers_spot')
    prices = parse_prices_from_tickers(tickers, tickers)
    assert prices['usdtSpot']['usdt'] == 1
    assert prices['usdtSpot']['btc'] == 59898.45
    assert prices['usdtSpot']['trx'] == 0.09793
    assert prices['usdtSpot']['xrp'] == 1.06840
    assert prices['usdtSpot']['doge'] == 0.2598
    assert prices['usdtSpot']['shib'] == 0.03614
    assert prices['btcSpot']['eth'] == 0.06637


def test_parse_prices_from_tickers_futures():
    tickers = get_data('binance_tickers_futures')
    prices = parse_prices_from_tickers(tickers, tickers)
    assert prices['usdtFutures']['usdt'] == 1
    assert prices['usdtFutures']['btc'] == 60564.99
    assert prices['usdtFutures']['trx'] == 0.09831
    assert prices['usdtFutures']['xrp'] == 1.0720
    assert prices['usdtFutures']['doge'] == 0.26244
    assert prices['usdtFutures']['shib'] == 0.039561
    assert prices['btcSpot']['btc'] == 1
