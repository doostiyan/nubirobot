from collections import defaultdict
from decimal import ROUND_DOWN, Decimal
from typing import Dict, List, Optional

from django.conf import settings

from exchange.accounts.models import User
from exchange.asset_backed_credit.exceptions import InsufficientBalanceError
from exchange.asset_backed_credit.externals.price import PriceProvider
from exchange.asset_backed_credit.externals.wallet import WalletSchema
from exchange.asset_backed_credit.models.user_service import InternalUser, UserService
from exchange.asset_backed_credit.models.wallet import Wallet
from exchange.asset_backed_credit.services.wallet.wallet import WalletService
from exchange.asset_backed_credit.types import AssetPriceData
from exchange.base.constants import ZERO
from exchange.wallet.models import Wallet as ExchangeWallet


class PricingService:
    """
    pricing service manages total_assets, total_debt, margin ratio, and available collateral of the user

    margin ratio is calculated by total_assets / total_debts (simplified)
    available collateral is calculated by (total_assets - total_debts * collateral_ratio) / collateral_ratio
    and is the remaining available collateral the user can use in various places like credit, loan or debit.

    total_assets consists of
    - total_mark_price: calculates total wallet balances in mark price
    - total_nobitex_price: calculates total wallet balances in nobitex price
    - weighted_avg: sum of the multiplication of each wallet balance by the difference between nobitex price and mark price
    divided by total_mark_price
    """

    def __init__(
        self,
        user: User = None,
        internal_user: InternalUser = None,
        wallets: Optional[List[WalletSchema]] = None,
        wallet_type=Wallet.WalletType.COLLATERAL,
        total_assets: Optional[AssetPriceData] = None,
        total_debt: Optional[Decimal] = None,
    ):
        self.user = user
        self.internal_user = internal_user
        self.wallets = wallets
        self.wallet_type = wallet_type
        self.total_assets = total_assets if total_assets is not None else self._update_total_assets()
        self.total_debt = total_debt if total_debt is not None else self._update_total_debt()

    def _update_total_assets(self) -> AssetPriceData:
        wallets = self.wallets or WalletService.get_user_wallets(
            user_id=self.user.uid, exchange_user_id=self.user.pk, wallet_type=self.wallet_type
        )

        total_assets_by_mark_price = ZERO
        total_assets_by_nobitex_price = ZERO
        total_assets_weighted_avg_num = ZERO

        for wallet in wallets:
            if wallet.balance == ZERO:
                continue

            mark_price = PriceProvider(src_currency=wallet.currency).get_mark_price()
            nobitex_price = PriceProvider(src_currency=wallet.currency).get_nobitex_price()
            total_wallet_mark_price = mark_price * wallet.balance
            total_wallet_nobitex_price = nobitex_price * wallet.balance
            diff_percent = abs(mark_price - nobitex_price)

            total_assets_by_mark_price += total_wallet_mark_price
            total_assets_by_nobitex_price += total_wallet_nobitex_price
            total_assets_weighted_avg_num += wallet.balance * diff_percent

        total_assets_weighted_avg = (
            (total_assets_weighted_avg_num / total_assets_by_mark_price).quantize(
                Decimal('1E-4'),
                rounding=ROUND_DOWN,
            )
            if total_assets_by_mark_price != ZERO
            else None
        )

        return AssetPriceData(total_assets_by_mark_price, total_assets_by_nobitex_price, total_assets_weighted_avg)

    def get_total_assets(self, *, force_update: bool = False) -> AssetPriceData:
        if not self.total_assets or force_update:
            self.total_assets = self._update_total_assets() or AssetPriceData(Decimal('0'), Decimal('0'))
        return self.total_assets

    def _update_total_debt(self):
        return UserService.get_total_active_debt(self.user)

    def get_total_debt(self, *, force_update: bool = False) -> Decimal:
        if not self.total_debt or force_update:
            self.total_debt = self._update_total_debt()
        return self.total_debt

    def get_margin_ratio(self, future_service_amount=ZERO, balance_diff=ZERO) -> Decimal:
        if self.total_debt + future_service_amount <= 0:
            return Decimal('infinity')

        return (
            (self.get_total_assets().total_mark_price + balance_diff) / (self.total_debt + future_service_amount)
        ).quantize(
            Decimal('1E-2'),
            rounding=ROUND_DOWN,
        )

    def get_available_collateral(self, keep_ratio=True) -> Decimal:
        collateral_ratio = get_ratios(wallet_type=self.wallet_type).get('collateral') if keep_ratio else 1
        available_collateral = (
            self.get_total_assets().total_nobitex_price - self.total_debt * collateral_ratio
        ) / collateral_ratio
        return max(available_collateral, Decimal('0')).quantize(Decimal('1'), rounding=ROUND_DOWN)

    def get_required_collateral(self, keep_ratio=True, future_service_amount=ZERO) -> Decimal:
        collateral_ratio = get_ratios(wallet_type=self.wallet_type).get('collateral') if keep_ratio else 1
        available_collateral = (
            self.get_total_assets().total_nobitex_price - (self.total_debt + future_service_amount) * collateral_ratio
        )
        return abs(min(available_collateral, Decimal('0')).quantize(Decimal('1'), rounding=ROUND_DOWN))

    def is_price_diff_high_between_markets(self) -> bool:
        """
        Returns true when the price difference between mark price and nobitex price is greater than the current
        acceptable weighted_avg
        """
        return self.get_total_assets().weighted_avg > get_ratios(wallet_type=self.wallet_type).get('weighted_avg')


def get_ratios(wallet_type: Wallet.WalletType = Wallet.WalletType.COLLATERAL) -> Dict[str, Decimal]:
    if wallet_type == Wallet.WalletType.DEBIT:
        return settings.ABC_RATIOS['debit']
    elif wallet_type == Wallet.WalletType.COLLATERAL:
        return settings.ABC_RATIOS['collateral']
    raise ValueError


def get_batch_total_assets(grouped_wallets: Dict[int, List[WalletSchema]]) -> Dict[int, AssetPriceData]:
    total_assets_per_user = defaultdict(lambda: AssetPriceData(Decimal(0), Decimal(0)))
    for user_id, wallets in grouped_wallets.items():
        pricing_service = PricingService(wallets=wallets, total_debt=Decimal(0))
        total_assets_per_user[user_id] = pricing_service.get_total_assets()
    return total_assets_per_user


def get_mark_price_partial_balance(wallets: Dict[ExchangeWallet, Decimal]) -> Decimal:
    """
    :param wallets: a dictionary of wallets with their requested partial amount
    """
    partial_balance_total: int = 0
    for wallet, requested_amount in wallets.items():
        if requested_amount > wallet.balance:
            raise InsufficientBalanceError(currency=wallet.currency, amount=requested_amount)
        partial_balance_total += PriceProvider(wallet.currency).get_mark_price() * requested_amount
    return Decimal(partial_balance_total)
