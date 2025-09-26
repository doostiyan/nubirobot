from uuid import UUID

from exchange.asset_backed_credit.externals.price import PriceProvider
from exchange.asset_backed_credit.models.wallet import Wallet
from exchange.asset_backed_credit.services.wallet.wallet import WalletService
from exchange.base.models import RIAL


def get_total_wallet_balance(
    user_id: UUID, exchange_user_id: int, wallet_type: Wallet.WalletType, dst_currency: int = RIAL
) -> int:
    total_balance = 0
    wallets = WalletService.get_user_wallets(
        user_id=user_id, exchange_user_id=exchange_user_id, wallet_type=wallet_type
    )

    for wallet in wallets:
        if wallet.currency != dst_currency:
            price = PriceProvider(wallet.currency, dst_currency).get_nobitex_price()
            total_balance += int(wallet.balance * price)
        else:
            total_balance += int(wallet.balance)
    return total_balance
