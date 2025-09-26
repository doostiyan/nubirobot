from django.conf import settings


def check_usd_price(usd_sell_price, usd_buy_price):
    if usd_sell_price is None or usd_buy_price is None:
        return False
    usd_spread = usd_sell_price - usd_buy_price
    min_usd_spread = 500 if settings.IS_PROD else 200
    if usd_spread < min_usd_spread:
        return False
    if usd_sell_price >= 1000000:
        return False
    if usd_buy_price < 70000:
        return False
    return True
