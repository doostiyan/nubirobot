from functools import partial

from exchange.base.formatting import format_money

format_amount = partial(
    format_money,
    show_currency=True,
    use_en=False,
    thousand_separators=True,
)
