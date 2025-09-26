from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.utils.timezone import now

from exchange.base.constants import MAX_PRECISION
from exchange.base.models import CURRENCY_CODENAMES


class UserStatsManager:
    @classmethod
    def get_last_activity(cls, user):
        last_activity = cache.get('user_{}_last_activity'.format(user.pk))
        if not last_activity:
            return user.last_login or user.date_joined
        return last_activity

    @classmethod
    def update_last_activity(cls, user, last_activity=None):
        last_activity = last_activity or now()
        cache.set('user_{}_last_activity'.format(user.pk), last_activity, 43200)

    @classmethod
    def get_user_vip_level(cls, user_id: int, *, force_update: bool = False):
        """
        Return user VIP level based on monthly trade volume.

        This method tries to use cache and sets it in case of cache miss.
        """
        from exchange.market.models import UserTradeStatus

        # Get cached fee rate if available
        vip_level_cache_key = f'user_{user_id}_vipLevel'
        if settings.CACHE_VIP_LEVEL and not force_update:
            user_vip_level = cache.get(vip_level_cache_key)
            if isinstance(user_vip_level, int) and 0 <= user_vip_level <= 6:
                return user_vip_level
        # Step Fee: Determine final fee based on trade volume steps
        try:
            user_vip_level = UserTradeStatus.objects.get(user_id=user_id).vip_level
        except UserTradeStatus.DoesNotExist:
            user_vip_level = 0
        cache.set(vip_level_cache_key, user_vip_level, 26 * 3600)
        return user_vip_level

    @classmethod
    def get_user_fee_by_fields(
        cls,
        *,
        amount=None,
        is_maker=False,
        is_usdt=False,
        user_vip_level=None,
        user_fee=None,
        user_fee_usdt=None,
        user_maker_fee=None,
        user_maker_fee_usdt=None,
    ) -> Decimal:
        """Calculate user trade fee based on the given field values. This method
        only performs basic calculation and does not access DB or cache. It is a
        very low level method and is only intended for use in specific use cases
        like the matcher. It also does minimal input checking and may raise any
        exception if input is invalid."""
        # Determine base fee
        options_key = 'makerFees' if is_maker else 'takerFees'
        if is_usdt:
            options_key += 'Tether'
        fee_rate = settings.NOBITEX_OPTIONS['tradingFees'][options_key][user_vip_level]

        # Check any fixed fees for this user
        if is_usdt:
            if is_maker and user_maker_fee_usdt is not None:
                fee_rate = min(fee_rate, user_maker_fee_usdt)
            elif user_fee_usdt is not None:
                fee_rate = min(fee_rate, user_fee_usdt)
        else:
            if is_maker and user_maker_fee is not None:
                fee_rate = min(fee_rate, user_maker_fee)
            elif user_fee is not None:
                fee_rate = min(fee_rate, user_fee)

        # Calculate total fee amount
        fee = fee_rate * Decimal('0.01') * amount
        return fee.quantize(MAX_PRECISION)

    @classmethod
    def get_user_fee(cls, user=None, amount=None, is_maker=False, is_usdt=False) -> Decimal:
        """
        Calculate user trade fee based on user level and trade parameters.

        Note: This is a low level method that only considers the user, usually the
        MarketManager.get_trade_fee method is preferable.
        """
        return cls.get_user_fee_by_fields(
            amount=amount or Decimal('1'),
            is_maker=is_maker,
            is_usdt=is_usdt,
            user_vip_level=cls.get_user_vip_level(user.id) if user else 0,
            user_fee=user.base_fee if user else None,
            user_fee_usdt=user.base_fee_usdt if user else None,
            user_maker_fee=user.base_maker_fee if user else None,
            user_maker_fee_usdt=user.base_maker_fee_usdt if user else None,
        )

    @classmethod
    def get_user_total_balance_irr(cls, user):
        """ Return overall balance of all user wallets estimated in IRR
        """
        total_value_irr = Decimal('0')
        for wallet in user.wallets.all():
            if wallet.is_rial:
                irr_price = Decimal('1')
            else:
                currency_name = CURRENCY_CODENAMES.get(wallet.currency)
                irr_price = cache.get('orderbook_{}IRT_best_buy'.format(currency_name)) or Decimal('0')
            total_value_irr += wallet.balance * irr_price
        return total_value_irr
