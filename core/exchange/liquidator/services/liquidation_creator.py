from decimal import ROUND_DOWN, Decimal
from typing import List, Optional, Tuple

from django.db import transaction

from exchange.accounts.models import Notification
from exchange.base.logging import report_exception
from exchange.base.models import AMOUNT_PRECISIONS_V2, DST_CURRENCIES
from exchange.liquidator.broker_apis import BrokerBaseAPI
from exchange.liquidator.constants import (
    LIQUIDATOR_EXTERNAL_CURRENCIES,
    MAX_IN_MARKET_ORDER,
    MAX_ORDER,
    PENDING_LIQUIDATION_REQUESTS_FETCH_LIMIT,
)
from exchange.liquidator.errors import EmptyPrice
from exchange.liquidator.models import Liquidation, LiquidationRequest, LiquidationRequestLiquidationAssociation
from exchange.market.markprice import MarkPriceCalculator
from exchange.market.models import Market


class LiquidationCreator:
    def __init__(self) -> None:
        self.total_dst_amounts = {c: Decimal('0') for c in DST_CURRENCIES}

    def execute(self):
        pending_liquidation_requests = (
            (
                LiquidationRequest.objects.filter(status=LiquidationRequest.STATUS.pending).select_related(
                    'src_wallet',
                    'dst_wallet',
                )
            )
            .select_for_update(of=('self',), skip_locked=True)
            .order_by('id')[:PENDING_LIQUIDATION_REQUESTS_FETCH_LIMIT]
        )

        updated_liquidation_requests = []
        new_liquidations = []
        new_associations = []
        with transaction.atomic():
            for liquidation_request in pending_liquidation_requests:
                try:
                    liquidations, associations = self._process_pending_liquidation_request(liquidation_request)
                    new_liquidations.extend(liquidations)
                    new_associations.extend(associations)
                    if liquidations:
                        updated_liquidation_requests.append(liquidation_request)
                except EmptyPrice:
                    Notification.notify_admins(
                        f'Cannot create liquidation: #{liquidation_request.pk}\nReason: Last price is empty',
                        title=f'‼️LiquidationRequest - {liquidation_request.market_symbol}',
                        channel='liquidator',
                    )
                except Exception:
                    report_exception()

            Liquidation.objects.bulk_create(new_liquidations, batch_size=1000)
            LiquidationRequestLiquidationAssociation.objects.bulk_create(new_associations, batch_size=1000)
            LiquidationRequest.objects.bulk_update(updated_liquidation_requests, fields=('status',))

        self._fire_order_creation_tasks(new_liquidations)

    @transaction.atomic
    def _process_pending_liquidation_request(
        self, liquidation_request: LiquidationRequest
    ) -> Tuple[List[Liquidation], List[LiquidationRequestLiquidationAssociation]]:
        price = self.get_price(market=liquidation_request.market)
        max_amount = self._get_max_amount_per_round(liquidation_request, price)
        if max_amount == Decimal('0'):
            return [], []
        liquidations, associations = self._create_liquidations(liquidation_request, price, max_amount)
        self.total_dst_amounts[liquidation_request.dst_currency] += max_amount * price
        if liquidations:
            liquidation_request.status = LiquidationRequest.STATUS.in_progress
            return liquidations, associations

    def get_price(self, market: Market):
        price = (
            MarkPriceCalculator.get_mark_price(market.src_currency, market.dst_currency)
            or market.get_last_trade_price()
        )
        if not price:
            raise EmptyPrice()
        return price

    def _get_max_amount_per_round(self, liquidation_request: LiquidationRequest, price: Decimal) -> Decimal:
        dst_currency = liquidation_request.dst_currency
        src_currency = liquidation_request.src_currency
        remain_total_amount = max(MAX_IN_MARKET_ORDER[dst_currency] - self.total_dst_amounts[dst_currency], Decimal(0))
        total_amount = liquidation_request.unfilled_amount * price
        if total_amount <= remain_total_amount:
            return liquidation_request.unfilled_amount
        return Decimal(remain_total_amount / price).quantize(AMOUNT_PRECISIONS_V2[src_currency], ROUND_DOWN)

    def _get_max_amount_per_liquidation(self, amount, price, src_currency, dst_currency) -> Decimal:
        total = amount * price
        if total < MAX_ORDER[dst_currency]:
            return amount
        return Decimal(MAX_ORDER[dst_currency] / price).quantize(AMOUNT_PRECISIONS_V2[src_currency], ROUND_DOWN)

    @transaction.atomic
    def _create_liquidations(
        self,
        liquidation_request: LiquidationRequest,
        price: Decimal,
        amount: Decimal,
    ) -> Tuple[List[Liquidation], List[LiquidationRequestLiquidationAssociation]]:

        splitted_amounts = self._split_amount_if_needed(
            amount,
            self._get_max_amount_per_liquidation(
                amount, price, liquidation_request.src_currency, liquidation_request.dst_currency
            ),
        )

        liquidations: List[Liquidation] = []
        for splitted_amount in splitted_amounts:
            liquidations.append(
                Liquidation(
                    src_currency=liquidation_request.src_currency,
                    dst_currency=liquidation_request.dst_currency,
                    side=liquidation_request.side,
                    amount=splitted_amount,
                    primary_price=price,
                )
            )

        associations = []
        for liquidation in liquidations:
            associations.append(
                LiquidationRequestLiquidationAssociation(
                    liquidation=liquidation, liquidation_request=liquidation_request
                )
            )

        return liquidations, associations

    @staticmethod
    def _split_amount_if_needed(amount: Decimal, max_amount_in_order: Decimal) -> Decimal:
        """
        Splits an amount if it exceeds the maximum amount in an order.
        Returns the adjusted amount.

        Args:
            amount (Decimal): The original amount.
            max_amount_in_order (Decimal): The maximum allowed amount in an order.

        Returns:
            Decimal: The adjusted amount.
        """
        splitted_amounts = []
        while max_amount_in_order < amount:
            splitted_amounts.append(max_amount_in_order)
            amount -= max_amount_in_order
        splitted_amounts.append(amount)

        return splitted_amounts

    @staticmethod
    def _fire_order_creation_tasks(liquidations: List[Liquidation]) -> None:
        from exchange.liquidator.tasks import task_create_external_order, task_create_internal_order

        is_broker_active = BrokerBaseAPI.is_active()

        for liquidation in liquidations:
            if is_broker_active and liquidation.src_currency in LIQUIDATOR_EXTERNAL_CURRENCIES:
                transaction.on_commit(lambda: task_create_external_order.delay(liquidation.pk))
            else:
                transaction.on_commit(lambda: task_create_internal_order.delay(liquidation.pk))
