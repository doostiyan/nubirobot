import math
from decimal import Decimal
from typing import Dict, List, Literal, Tuple

import tqdm
from django.db import connection, transaction
from django.db.models import Q

from exchange.base.helpers import batcher
from exchange.base.logging import report_event
from exchange.margin.log_functions import log_margin_order_cancel
from exchange.margin.models import MarginOrderChange
from exchange.margin.tasks import task_bulk_update_position_on_order_change
from exchange.market.models import Order, OrderMatching
from exchange.wallet.models import Transaction


def post_process_updated_margin_orders(orders: List[Order]):
    """
    Alternate function for Order's post-save signal in cases the update is performed in bulk:
    - create MarginOrderChange instances for updated margin orders
    - call task to update related positions
    - notify canceled margin settlement orders
    """
    margin_orders = []
    for order in orders:
        if order.is_margin:
            margin_orders.append(order)
            if order.status == Order.STATUS.canceled:
                log_margin_order_cancel(order, inside_matcher=True)

    MarginOrderChange.objects.bulk_create(
        [MarginOrderChange(order=order) for order in margin_orders],
        batch_size=100,
    )
    transaction.on_commit(
        lambda: task_bulk_update_position_on_order_change.delay([margin_order.id for margin_order in margin_orders])
    )


def create_missing_transaction(from_datetime, to_datetime, *, disable_process_bar: bool = True, dry_run: bool = False):
    trades = (
        OrderMatching.objects.filter(
            Q(sell_deposit__isnull=True)
            | Q(sell_withdraw__isnull=True)
            | Q(buy_deposit__isnull=True)
            | Q(buy_withdraw__isnull=True)
        )
        .filter(
            created_at__gte=from_datetime,
            created_at__lt=to_datetime,
        )
        .select_related('market', 'sell_order', 'buy_order')
    )
    ref_modules = [Transaction.REF_MODULES[r] for r in ('TradeSellA', 'TradeSellB', 'TradeBuyA', 'TradeBuyB')]

    trades_count = trades.count()
    if not disable_process_bar:
        print(f'found orderMatching count= {trades_count}')

    if dry_run:
        return

    batch_size = 100
    for trades_batch in tqdm.tqdm(
        batcher(trades, batch_size=batch_size, idempotent=True),
        total=math.ceil(trades_count / batch_size),
        disable=disable_process_bar,
    ):
        trades_map = {trade.id: trade for trade in trades_batch}
        transactions = Transaction.objects.filter(
            ref_id__in=trades_map,
            ref_module__in=ref_modules,
        ).only('id', 'ref_id', 'ref_module')

        for t in transactions:
            if t.ref_module == Transaction.REF_MODULES['TradeSellA']:
                trades_map[t.ref_id].sell_withdraw_id = t.pk

            elif t.ref_module == Transaction.REF_MODULES['TradeBuyA']:
                trades_map[t.ref_id].sell_deposit_id = t.pk

            elif t.ref_module == Transaction.REF_MODULES['TradeSellB']:
                trades_map[t.ref_id].buy_withdraw_id = t.pk

            elif t.ref_module == Transaction.REF_MODULES['TradeBuyB']:
                trades_map[t.ref_id].buy_deposit_id = t.pk

        for trade in trades_map.values():
            if not trade.sell_deposit_id:
                sell_deposit = trade.create_sell_deposit_transaction(set_trade_time=False)
                trade.sell_deposit_id = sell_deposit.id if sell_deposit else None
            if not trade.buy_deposit_id:
                buy_deposit = trade.create_buy_deposit_transaction(set_trade_time=False)
                trade.buy_deposit_id = buy_deposit.id if buy_deposit else None
            tx_ids = (trade.sell_withdraw_id, trade.buy_withdraw_id, trade.sell_deposit_id, trade.buy_deposit_id)
            if not all(tx_ids):
                report_event(
                    message='FailedToFillTransactions',
                    extras={'src': 'SystemFeeWalletChargeCron', 'tx_ids': tx_ids, 'trade_id': trade.id},
                )

        OrderMatching.objects.bulk_create(
            list(trades_map.values()),
            update_fields=('sell_withdraw_id', 'sell_deposit_id', 'buy_withdraw_id', 'buy_deposit_id'),
            update_conflicts=True,
            unique_fields=('id',),
        )


market_liquidity_both_sides_depth_query = '''
WITH orderbook_levels AS (
    SELECT
        src_currency,
        dst_currency,
        order_type,
        price,
        SUM(amount - matched_amount) AS total_amount
    FROM market_order
    WHERE
        status = 1
        AND execution_type NOT IN (2, 12)
    GROUP BY src_currency, dst_currency, order_type, price
),
best_prices AS (
    SELECT
        src_currency,
        dst_currency,
        order_type,
        MAX(CASE WHEN order_type = 2 THEN price ELSE NULL END) AS best_bid,
        MIN(CASE WHEN order_type = 1 THEN price ELSE NULL END) AS best_ask
    FROM orderbook_levels
    GROUP BY src_currency, dst_currency, order_type
)
SELECT
    obl.src_currency,
    obl.dst_currency,
    obl.order_type,
    COALESCE(SUM(obl.total_amount) FILTER (WHERE CASE
        WHEN obl.order_type = 2
            THEN obl.price >= bp.best_bid * {bids_threshold}
        WHEN obl.order_type = 1
            THEN obl.price <= bp.best_ask * {asks_threshold}
        ELSE false
    END), 0) AS total_amount
FROM orderbook_levels obl
NATURAL LEFT JOIN best_prices bp
GROUP BY src_currency, dst_currency, order_type
ORDER BY src_currency, dst_currency, order_type;
'''

Side = Literal['bids', 'asks']


def get_market_liquidity_both_sides_depth(
    bids_threshold: Decimal = Decimal('0.05'),
    asks_threshold: Decimal = Decimal('0.05'),
) -> Dict[Tuple[int, int], Dict[Side, Decimal]]:
    """
    Retrieve aggregated bid and ask order volumes within given thresholds of the best prices for each market.

    Args:
        bids_threshold: Fraction below best bid to include (e.g. 0.05 means price ≥ best_bid * 0.95).
        asks_threshold: Fraction above best ask to include (e.g. 0.05 means price ≤ best_ask * 1.05).

    Returns:
        A dict mapping (src_currency, dst_currency) → {'bids': Decimal, 'asks': Decimal}.
        e.g. {(10,2): {'bids': Decimal('1.2'), 'asks': Decimal('1.3')}
    """

    with connection.cursor() as cursor:
        cursor.execute(
            market_liquidity_both_sides_depth_query.format(
                bids_threshold=Decimal('1') - bids_threshold,
                asks_threshold=Decimal('1') + asks_threshold,
            )
        )
        rows = cursor.fetchall()
    depths = {}
    for src, dst, order_type, total_amount in rows:
        market_key = (src, dst)
        side = 'bids' if order_type == 2 else 'asks'
        depths.setdefault(market_key, {})[side] = Decimal(str(total_amount))
    return depths
