from django.core.cache import cache

from exchange.base.coins_info import CURRENCY_INFO
from exchange.wallet.models import AvailableHotWalletAddress


def update_auto_withdraw_status(data, status, error_msg=''):
    if isinstance(data, list):
        withdraws = data
        for withdraw_obj in withdraws:
            if not isinstance(withdraw_obj, tuple):
                continue
            withdraw, log, a_withdraw = withdraw_obj
            a_withdraw.status = status
            a_withdraw.save(update_fields=['status'])
            if error_msg:
                log.description = error_msg
                log.status = 4
                log.save()
        return
    a_withdraw = data
    a_withdraw.status = status
    a_withdraw.save(update_fields=['status'])


def get_hot_wallet_addresses(currency=None, network_symbol=None, limit=None, keep_case=False):
    """
        This function works with network (and not currency) overwrite network_symbol property or this function
        will assume a default network (based on coin) and then all things go up with network
        Returns: all hot wallet addresses on one assumed network in a set (all addresses lowercase in purpose unless
        keep_case parameter is True)
    """
    if network_symbol is None:
        if currency is None:
            raise ValueError('What hot wallet address when neither network symbol passed nor currency')
        network_symbol = CURRENCY_INFO[currency]['default_network']
    network_symbol = network_symbol.upper()
    from_cache = cache.get(f'hot_address_on_{network_symbol}')
    if not from_cache:
        to_cache = set(map(
            lambda address: address if keep_case else address.lower(),
            AvailableHotWalletAddress.objects.filter(
                network__iexact=network_symbol,
                active=True
            ).order_by('-pk').values_list('address', flat=True)
        ))
        cache.set(f'hot_address_on_{network_symbol}', ','.join(to_cache), 24 * 60 * 60)
        return to_cache

    if keep_case:
        return set(from_cache.split(',')[:limit])  # works even if limit is None
    else:
        return set(from_cache.lower().split(',')[:limit])  # works even if limit is None


class NobitexWithdrawException(Exception):
    pass
