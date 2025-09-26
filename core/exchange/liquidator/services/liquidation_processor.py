from datetime import timedelta
from typing import Iterable, List

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils.timezone import now

from exchange.accounts.models import Notification
from exchange.base.calendar import ir_now
from exchange.base.logging import report_exception
from exchange.liquidator.broker_apis import SettlementData, SettlementStatus, SettlementStatusEnum
from exchange.liquidator.errors import InvalidAPIResponse, SettlementNotFound
from exchange.liquidator.functions import check_double_spend_in_liquidation
from exchange.liquidator.models import Liquidation
from exchange.market.models import Order


class InternalLiquidationProcessor:
    """
    Manages market orders for liquidations and updates their statuses.

    This class handles the following responsibilities:
    - Identifying liquidations have market orders.
    - Canceling outdated market orders associated with open liquidations.
    - Updating liquidation statuses based on order execution results.
    """

    def process_liquidation_orders(self):
        """
        Processes open liquidations with expired market orders.

        Identifies open liquidations whose associated market orders are older
        than the maximum allowed age (defined by `settings.MARGIN_SYSTEM_ORDERS_MAX_AGE`).
        For each identified liquidation, it cancels the outdated order and update liquidation status
        """
        order_max_age = ir_now() - settings.MARGIN_SYSTEM_ORDERS_MAX_AGE
        liquidations = (
            Liquidation.objects.filter(
                Q(order__created_at__lte=order_max_age)
                | Q(order__status__in=[Order.STATUS.canceled, Order.STATUS.done]),
                market_type=Liquidation.MARKET_TYPES.internal,
                status=Liquidation.STATUS.open,
            )
            .order_by('id')
            .select_for_update(of=('self',), skip_locked=True)
        )
        with transaction.atomic():
            orders = self._cancel_active_orders([liq.order_id for liq in liquidations])
            self._update_liquidations(liquidations, orders)

    def _cancel_active_orders(self, order_ids: List[int]) -> Iterable[Order]:
        """
        Cancels active orders with the specified IDs.

        Args:
            order_ids (List[int]): A list of order IDs to cancel.

        Returns:
            Iterable[Order]: An iterable containing the canceled orders (as QuerySet).
        """
        Order.objects.filter(pk__in=order_ids, status__in=Order.OPEN_STATUSES).update(status=Order.STATUS.canceled)
        return Order.objects.filter(pk__in=order_ids).in_bulk(field_name='pk')

    def _update_liquidations(self, liquidations: List[Liquidation], orders: List[Order]):
        """
        Updates the status and filled amount of liquidations based on order results.
        If the order is still open, the liquidation remains unchanged.
        Otherwise, the liquidation status is set to 'ready_to_share',
        and the filled amount and total price are updated based on the order.

        Args:
            liquidations (List[Liquidation]): A list of liquidations to update.
            orders (Dict[int, Order]): A dictionary mapping liquidation market order IDs to orders.
        """
        updated_liquidations = []
        for liquidation in liquidations:
            order = orders[liquidation.order_id]
            if order.status in Order.OPEN_STATUSES:
                continue

            liquidation.filled_amount = order.matched_amount if order.is_sell else order.matched_amount - order.fee
            if liquidation.filled_amount > liquidation.amount:
                check_double_spend_in_liquidation(liquidation)

            liquidation.filled_total_price = (
                order.net_matched_total_price if order.is_sell else order.matched_total_price
            )
            liquidation.status = Liquidation.STATUS.ready_to_share

            updated_liquidations.append(liquidation)

        Liquidation.objects.bulk_update(updated_liquidations, fields=('status', 'filled_amount', 'filled_total_price'))


class ExternalLiquidationProcessor:
    SLA_TIME: int = 30

    @transaction.atomic
    def update_status(self, liquidation_id: int):
        liquidation = Liquidation.objects.filter(id=liquidation_id).select_for_update(skip_locked=True).first()
        if not liquidation:
            return None

        try:
            data = SettlementStatus().request(liquidation=liquidation)
            self._update_liquidation(liquidation, data)
            return liquidation.save(update_fields=('status', 'filled_amount', 'filled_total_price'))

        except SettlementNotFound:
            liquidation.status = Liquidation.STATUS.ready_to_share
            return liquidation.save(update_fields=('status',))

        except InvalidAPIResponse:
            Notification.notify_admins(
                f'Invalid settlement data. liquidation: #{liquidation.pk}',
                title=f'‼️Settlement Status- {liquidation.symbol}',
                channel='liquidator',
            )
            report_exception()

        except Exception:
            report_exception()

        exceed_sla = liquidation.created_at <= (now() - timedelta(seconds=self.SLA_TIME))
        if exceed_sla:
            liquidation.status = Liquidation.STATUS.overstock
            liquidation.save(update_fields=('status',))

    def _update_liquidation(self, liquidation: Liquidation, data: SettlementData):
        liquidation.filled_amount = data.filled_amount
        liquidation.filled_total_price = data.filled_price * data.filled_amount
        exceed_sla = data.server_time > data.issue_time + timedelta(seconds=self.SLA_TIME)

        if data.status == SettlementStatusEnum.OPEN.value:
            if exceed_sla:
                liquidation.status = Liquidation.STATUS.overstock
            else:
                return
        else:
            liquidation.status = Liquidation.STATUS.ready_to_share
