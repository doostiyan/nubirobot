from decimal import Decimal
from typing import TypedDict

from exchange.wallet.models import Wallet


class TransferResult(TypedDict):
    src_wallet: Wallet
    dst_wallet: Wallet
    amount: Decimal
