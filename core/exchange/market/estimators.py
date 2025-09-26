import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from django.core.cache import cache

from exchange.base.constants import ZERO
from exchange.market.models import Market


@dataclass
class EstimatedSrcAmountByDstAmount:
    src_amount: Decimal
    actual_dst_amount: Decimal
    is_max_used: bool


def estimate_market_order_src_amount_by_dst_amount(
    src_currency: int,
    dst_currency: int,
    dst_amount: Decimal,
    max_src_amount: Optional[Decimal] = None,
    *,
    is_sell: bool = True,
) -> Optional[EstimatedSrcAmountByDstAmount]:
    """
    Estimates the source amount required to obtain a given destination amount in a market order.

    Args:
        src_currency (int): The source currency ID.
        dst_currency (int): The destination currency ID.
        dst_amount (Decimal): The desired destination amount.
        max_src_amount (Optional[Decimal]): The maximum allowed source amount. If None, there is no maximum limit.

    Returns:
        Optional[EstimatedSrcAmountByDstAmount]: An instance of EstimatedSrcAmountByDstAmount if estimation is successful,
        otherwise returns None.
    """

    market = Market.get_for(src_currency, dst_currency)
    if not market:
        return None

    books = cache.get(f'orderbook_{market.symbol}_{"asks" if is_sell else "bids"}')
    if not books:
        return None

    books = json.loads(books)
    matched_src_amount = ZERO
    remaining_dst_amount = dst_amount
    for book_price, book_amount in books:
        book_amount = Decimal(book_amount)
        book_price = Decimal(book_price)

        if max_src_amount and matched_src_amount + book_amount >= max_src_amount:
            # Maximum allowed source amount is reached
            return EstimatedSrcAmountByDstAmount(
                src_amount=max_src_amount,
                actual_dst_amount=dst_amount
                - remaining_dst_amount
                + (max_src_amount - matched_src_amount) * book_price,
                is_max_used=True,
            )

        if (matched_amount := remaining_dst_amount / book_price) <= book_amount:
            # Estimated source amount found without using the maximum allowed source amount
            return EstimatedSrcAmountByDstAmount(
                src_amount=matched_src_amount + matched_amount,
                actual_dst_amount=dst_amount,
                is_max_used=False,
            )

        matched_src_amount += book_amount
        remaining_dst_amount -= book_amount * book_price

    # When market depth is low
    return EstimatedSrcAmountByDstAmount(
        src_amount=matched_src_amount,
        actual_dst_amount=dst_amount - remaining_dst_amount,
        is_max_used=False,
    )
