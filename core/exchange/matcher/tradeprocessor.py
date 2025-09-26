"""Trade Processor"""
import datetime
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

from django.core.cache import cache
from django.db.models import Q
from django.utils.timezone import now

from exchange.base.decorators import measure_function_execution, ram_cache
from exchange.base.helpers import context_flag, stage_changes
from exchange.base.logging import metric_incr, report_exception
from exchange.base.models import DST_CURRENCIES, Settings
from exchange.margin.models import Position, PositionOrder
from exchange.market.models import Order, OrderMatching
from exchange.pool.models import LiquidityPool
from exchange.wallet.models import Wallet


class TradeProcessor:
    """Trade processor is a process that runs alongside the matcher and
    performs the parts of trading logic that can be done outside of the
    matching DB transaction."""

    def __init__(self, batch_size=100, commit_trade=True) -> None:
        self.batch_size = batch_size
        self.trades_count = 0
        self.commit_trade = commit_trade
        self.trades = []

    @measure_function_execution(metric_prefix='tradeprocessor', metric='txids', metrics_flush_interval=10)
    @context_flag(NOTIFY_NON_ATOMIC_TX_COMMIT=False)
    def fill_trade_transactions(self, trade: OrderMatching, sell_deposit_wallet, buy_deposit_wallet, tx_ids):
        """Fill the four transaction references in trade object based on
        the cached txids value set in matcher.
        To avoid possible deadlock in matcher, the view is not atomic.
        """
        tx_fields = ('sell_withdraw_id', 'buy_withdraw_id', 'sell_deposit_id', 'buy_deposit_id')

        if tx_ids is None:
            tx_ids = (cache.get(f'trade_{trade.id}_txids') or '').split(',')
        if len(tx_ids) != 2:
            raise AssertionError('Empty cache or changed contract for tx_ids')

        noop_context = contextmanager(lambda: (yield))
        context_manager = stage_changes(trade, update_fields=tx_fields) if self.commit_trade else noop_context()

        with context_manager:
            trade.sell_withdraw_id = int(tx_ids[0])
            trade.buy_withdraw_id = int(tx_ids[1])
            trade.sell_deposit = trade.create_sell_deposit_transaction(set_trade_time=False, wallet=sell_deposit_wallet)
            trade.buy_deposit = trade.create_buy_deposit_transaction(set_trade_time=False, wallet=buy_deposit_wallet)

        if not self.commit_trade:
            self.trades.append(trade)

    def process_trade(
        self, trade: OrderMatching, sell_deposit_wallet=None, buy_deposit_wallet=None, tx_ids=None
    ) -> bool:
        """Process a trade, including actions like filling transaction ids. This method
        should be idempotent and in rare situations may be called multiple times for a
        trade."""
        success = True
        if not all((trade.sell_deposit_id, trade.sell_withdraw_id, trade.buy_deposit_id, trade.buy_withdraw_id)):
            try:
                self.fill_trade_transactions(trade, sell_deposit_wallet, buy_deposit_wallet, tx_ids)
            except Exception as e:  # noqa: BLE001
                success = False
                print(f'[T#{trade.id}] Error in filling transactions:', e)
                report_exception()
        return success

    @staticmethod
    @ram_cache(timeout=300)
    def check_activation():
        return Settings.is_disabled('trade_processor_activation')

    @staticmethod
    def create_wallets(query_dict, wallets):
        to_be_create_wallets = [
            Wallet(user_id=key[0], currency=key[1], type=key[2]) for key in query_dict if key not in wallets
        ]

        created_wallets = Wallet.objects.bulk_create(to_be_create_wallets, ignore_conflicts=True)
        if created_wallets:
            criteria = Q()
            for wallet in created_wallets:
                criteria |= Q(
                    user_id=wallet.user_id,
                    currency=wallet.currency,
                    type=wallet.type,
                )
            created_wallets = Wallet.objects.filter(criteria)

        new_wallets = {(wallet.user_id, wallet.currency, wallet.type): wallet for wallet in created_wallets}

        return new_wallets

    def preload_wallets(self, trades_batch):
        pools = LiquidityPool.objects.in_bulk(field_name='currency')
        query_dict = set()
        order_to_provider_id = {}
        orders = {order for trade in trades_batch for order in (trade.sell_order, trade.buy_order)}

        position_orders = (
            PositionOrder.objects.filter(order__in=[order for order in orders if order.is_margin])
            .select_related('position')
            .in_bulk(field_name='order_id')
        )

        for order in orders:
            order: Order
            currency = order.src_currency if order.is_buy else order.dst_currency
            if order.is_margin:
                position_order = position_orders.get(order.id)
                if position_order is None:
                    continue
                position: Position = position_order.position
                pool_currency = order.src_currency if position.is_short else order.dst_currency
                pool: LiquidityPool = pools[pool_currency]
                provider_id = pool.manager_id
            else:
                provider_id = order.user_id

            order_to_provider_id[order.id] = provider_id
            query_dict.add((provider_id, currency, order.wallet_type))

        criteria = Q()
        for user_id, currency, wallet_type in query_dict:
            criteria |= Q(
                user_id=user_id,
                currency=currency,
                type=wallet_type,
            )

        wallets = {(wallet.user_id, wallet.currency, wallet.type): wallet for wallet in Wallet.objects.filter(criteria)}
        new_wallets = self.create_wallets(query_dict, wallets)

        return {**wallets, **new_wallets}, order_to_provider_id

    @staticmethod
    def preload_tx_ids(trades):
        keys = [trade.tx_ids_cache_key for trade in trades]
        tx_ids_values = cache.get_many(keys)
        return tx_ids_values

    def bulk_update_trades(self):
        if self.trades:
            OrderMatching.objects.bulk_create(
                self.trades,
                update_fields=('sell_withdraw_id', 'sell_deposit_id', 'buy_withdraw_id', 'buy_deposit_id'),
                update_conflicts=True,
                unique_fields=('id',),
            )
        self.trades = []

    def fetch_trades(self, last_trade_id):
        return (
            OrderMatching.objects.filter(
                id__gt=last_trade_id,
                created_at__gte=now() - datetime.timedelta(hours=12),
            )
            .filter(Q(sell_deposit__isnull=True) | Q(buy_deposit__isnull=True))
            .select_related('market', 'sell_order', 'buy_order')
            .order_by('id')[: self.batch_size]
        )

    @staticmethod
    def get_deposit_wallets(wallets, order_to_provider_id, trade):
        sell_deposit_wallet = wallets.get(
            (order_to_provider_id[trade.sell_order_id], trade.sell_order.dst_currency, trade.sell_order.wallet_type)
        )
        buy_deposit_wallet = wallets.get(
            (order_to_provider_id[trade.buy_order_id], trade.buy_order.src_currency, trade.buy_order.wallet_type)
        )
        return sell_deposit_wallet, buy_deposit_wallet

    def do_round(self):
        """Process a batch of trades"""
        if self.check_activation():
            return
        trade_id_cache_key = 'tradeprocessor_last_trade_id'
        last_trade_id = cache.get(trade_id_cache_key) or 0
        trades_batch = self.fetch_trades(last_trade_id)
        print(f'Processing {len(trades_batch)} trades from T#{last_trade_id}…')
        count_success = count_fail = 0

        if len(trades_batch) == 0:
            return

        wallets, order_to_provider_id = self.preload_wallets(trades_batch)
        tx_ids_values = self.preload_tx_ids(trades_batch)

        last_trade_ids = {currency: last_trade_id for currency in DST_CURRENCIES}
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = []
            for trade in trades_batch:
                trade: OrderMatching
                sell_deposit_wallet, buy_deposit_wallet = self.get_deposit_wallets(wallets, order_to_provider_id, trade)
                tx_ids = (tx_ids_values.get(trade.tx_ids_cache_key) or '').split(',')

                futures += [executor.submit(self.process_trade, trade, sell_deposit_wallet, buy_deposit_wallet, tx_ids)]

            for future, trade in zip(futures, trades_batch):
                success = future.result()
                if success:
                    count_success += 1
                else:
                    count_fail += 1
                print(f'    {"+" if success else "-"} {trade.id}')

                last_trade_ids[trade.market.dst_currency] = max(trade.id, last_trade_ids[trade.market.dst_currency])

        # Update metrics and last_id for this batch
        last_trade_id = min(last_trade_ids.values())
        cache.set(trade_id_cache_key, last_trade_id)

        if count_success:
            metric_incr('metric_trade_processor_runs_total__ok', amount=count_success)
        if count_fail:
            metric_incr('metric_trade_processor_runs_total__exception', amount=count_fail)

        self.trades_count = count_success + count_fail
