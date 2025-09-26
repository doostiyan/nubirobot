import decimal
import functools
from typing import Optional

from redis.exceptions import RedisError
from django.core.cache import cache
from django.db.models import Sum

from exchange.base.models import get_currency_codename, Currencies
from exchange.base.money import money_is_zero
from exchange.base.decorators import SkipCache
from exchange.accounts.models import User
from exchange.wallet.estimator import PriceEstimator
from exchange.credit import errors
from exchange.credit import models
from exchange.wallet.models import Wallet, WithdrawRequest


@functools.lru_cache(maxsize=1)
def get_system_user_id() -> int:
    '''This method will return credit system user id'''
    return User.objects.get(username='system-vip-credit').id


def get_user_net_worth(user_id: int,) -> decimal.Decimal:
    '''Calling this method return usdt value of the assets 'controlled' by
        user. Note that assets in yield farming and liquidity pool
        are considered here too. Also debt is being considered here too.
        Note that users assets in yield framing and liquidity pool will not
        be considered here.
    '''
    wallets = Wallet.objects.filter(
        user_id=user_id, type=Wallet.WALLET_TYPE.spot,
    ).only('id', 'currency', 'balance',).order_by('currency')

    # Note that We have to subtract users current pending withdraws from his/her net worth
    wallet_id_to_withdraw_blocked_balance_map = dict(WithdrawRequest.get_financially_pending_requests().filter(
        wallet_id__in=[w.id for w in wallets],
    ).values('wallet_id').annotate(total=Sum('amount')).values_list('wallet_id', 'total',))
    net_worth = decimal.Decimal('0')
    for wallet in wallets:
        amount = wallet.balance - wallet_id_to_withdraw_blocked_balance_map.get(wallet.id, decimal.Decimal('0'))
        if money_is_zero(amount):
            continue
        try:
            price = ToUsdtConvertor(wallet.currency).get_price()
        except errors.UnavailablePrice:
            price =  decimal.Decimal('0')
        net_worth += price * amount
    return net_worth


def get_user_debt_worth(user_id: int,) -> decimal.Decimal:
    '''This method returns usdt value of users total debt.'''
    return sum(
        ToUsdtConvertor(currency).get_price() * amount
        for currency, amount in models.CreditPlan.get_user_debts(user_id).items()
        if amount
    ) or decimal.Decimal('0')


class ToUsdtConvertor:
    def __init__(self, currency: int):
        self.currency = currency
        self.currency_codename = get_currency_codename(currency)

    CLOSE_PRICES_LIMIT = .03

    @classmethod
    def _are_prices_close(cls, price: Optional[float], other_price: Optional[float]) -> bool:
        if price is None or other_price is None:
            return False
        return abs(price - other_price) / price < cls.CLOSE_PRICES_LIMIT

    @property
    def binance_price(self) -> Optional[float]:
        return (cache.get('settings_prices_binance_futures') or {}).get(self.currency_codename)

    @property
    def okx_price(self) -> Optional[float]:
        return (cache.get('okx_prices') or {}).get(self.currency_codename)

    @property
    def nobitex_price(self) -> Optional[float]:
        nobitex_buy_price = cache.get(f'orderbook_{self.currency_codename.upper()}USDT_best_active_buy')
        nobitex_sell_price = cache.get(f'orderbook_{self.currency_codename.upper()}USDT_best_active_sell')
        if nobitex_buy_price is not None and nobitex_sell_price is not None:
            nobitex_price = (nobitex_buy_price + nobitex_sell_price) / 2
        else:
            nobitex_price = nobitex_buy_price or nobitex_sell_price
        return float(nobitex_price) if nobitex_price is not None else None

    def get_price(self) -> decimal.Decimal:
        if self.currency == Currencies.usdt:
            return decimal.Decimal('1')

        if self.currency == Currencies.rls:
            try:
                nobitex_price, _ = PriceEstimator.get_price_range(Currencies.usdt)
            except (SkipCache, RedisError) as e:
                raise errors.UnavailablePrice('RLS Price is not available.') from e
            return decimal.Decimal('1') / decimal.Decimal(str(nobitex_price))

        nobitex_price = self.nobitex_price
        binance_price = self.binance_price
        okx_price = self.okx_price

        if self._are_prices_close(binance_price, okx_price):
            return decimal.Decimal(binance_price)

        if self._are_prices_close(binance_price, nobitex_price):
            return decimal.Decimal(binance_price)

        if self._are_prices_close(okx_price, nobitex_price):
            return decimal.Decimal(okx_price)

        raise errors.UnavailablePrice(f'{self.currency_codename} price is not available.')
