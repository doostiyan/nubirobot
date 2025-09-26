from decimal import Decimal

from django.db import transaction

from exchange.asset_backed_credit.currencies import ABCCurrencies
from exchange.asset_backed_credit.externals.liquidation import LiquidationProvider
from exchange.asset_backed_credit.models.debt_to_asset_margin_call import AssetToDebtMarginCall
from exchange.asset_backed_credit.models.service import Service
from exchange.asset_backed_credit.models.settlement import SettlementTransaction
from exchange.asset_backed_credit.models.wallet import Wallet
from exchange.asset_backed_credit.services.price import PricingService, get_ratios
from exchange.base.calendar import ir_now
from exchange.base.constants import ZERO
from exchange.base.logging import report_event
from exchange.market.models import Order


@transaction.atomic
def liquidate_settlement(settlement_id: int, **options):
    """
    Liquidates the pending amount in a settlement transaction by creating and executing
    sell orders for various currencies.

    Parameters:
    - settlement_id (int): The ID of the settlement transaction to be liquidated.
    - tolerance (Decimal): The percentage tolerance to adjust the estimated source amount
      based on market prices. Defaults to 0.03 (3%).
    - wait_before_retry (Optional[timedelta]): The optional time period to wait before
      retrying the liquidation if there are recent active orders. Defaults to None.

    Returns:
    - SettlementTransaction: The updated settlement transaction object after liquidation.

    Raises:
    - CannotEstimateSrcAmount: If it is not possible to estimate the source amount for a currency.

    The function retrieves the specified settlement transaction and checks if there is a
    pending liquidation amount. If the amount is zero or negative, the function returns
    the settlement transaction as there is nothing to liquidate.

    If a wait_before_retry period is specified and there are active orders created within
    that time frame, the function returns without retrying the liquidation.

    The function then cancels any active orders associated with the settlement and iterates
    through the user's credit wallets for various currencies. For each currency, it estimates
    the source amount based on the remaining destination amount, the current market price,
    and the specified tolerance.

    The liquidation function is called for each currency, and the resulting orders are
    added to the settlement transaction. The remaining destination amount is updated
    accordingly.

    The liquidation process continues until the remaining destination amount is zero or
    negative, at which point the updated settlement transaction is returned.
    """
    tolerance = options.get('tolerance', Decimal('0.03'))
    wait_before_retry = options.get('wait_before_retry')
    settlement = (
        SettlementTransaction.objects.select_related('user_service', 'user_service__user', 'user_service__service')
        .select_for_update(of=('self', 'user_service'), no_key=True)
        .get(pk=settlement_id)
    )
    if (
        wait_before_retry
        and settlement.liquidation_run_at
        and settlement.liquidation_run_at > ir_now() - wait_before_retry
    ):
        return settlement

    if settlement.pending_liquidation_amount <= ZERO or not settlement.should_settle:
        return settlement

    if AssetToDebtMarginCall.user_has_active_liquidation_order(settlement.user_service.user_id):
        return settlement

    if (
        wait_before_retry
        and settlement.orders.filter(status=Order.STATUS.active, created_at__gt=ir_now() - wait_before_retry).exists()
    ):
        # Too soon to retry, there is at least an active order created in recent wait_before_retry param
        return settlement

    LiquidationProvider.cancel_active_settlement_liquidation(settlement)

    orders_matched_total_price = LiquidationProvider.get_orders_matched_total_price(settlement)
    pending_liquidation_amount = settlement.pending_liquidation_amount - orders_matched_total_price
    if pending_liquidation_amount <= ZERO:
        return settlement

    wallet_type = Service.get_related_wallet_type(settlement.user_service.service.tp)
    orders = LiquidationProvider.liquidate(
        user=settlement.user_service.user,
        currencies=ABCCurrencies.get_all_currencies(wallet_type),
        wallet_type=wallet_type,
        amount=pending_liquidation_amount,
        tolerance=tolerance,
    )
    settlement.orders.add(*orders)
    settlement.liquidation_retry += 1
    settlement.liquidation_run_at = ir_now()
    settlement.save(
        update_fields=(
            'liquidation_retry',
            'liquidation_run_at',
        )
    )
    return settlement


@transaction.atomic
def liquidate_margin_call(margin_call_id: int) -> None:
    """
    Liquidates assets to cover a margin call by creating and executing sell orders for
    various currencies.

    Parameters:
    - margin_call_id (int): The ID of the margin call to be liquidated.
    - tolerance (Decimal): The percentage tolerance to adjust the estimated source amount
      based on market prices. Defaults to 0.03 (3%).

    Returns:
    - AssetToDebtMarginCall: The updated margin call object after liquidation.

    Raises:
    - CannotEstimateSrcAmount: If it is not possible to estimate the source amount for a currency.

    The function retrieves the specified margin call and cancels any active settlements
    associated with the user of the margin call. This is done to prevent conflicts between
    the margin call liquidation and ongoing settlement transactions.

    The function then retrieves the user's credit wallets for various currencies and
    iterates through them. For each non-zero balance wallet, it estimates the source amount
    based on the current market price and the specified tolerance.

    The liquidation function is called for each currency, and the resulting orders are
    added to the margin call. The function returns the updated margin call object after
    the liquidation process.
    """
    margin_call = (
        AssetToDebtMarginCall.objects.select_related('user')
        .select_for_update(of=('self',), no_key=True)
        .get(pk=margin_call_id)
    )

    pricing_service = PricingService(user=margin_call.user)
    liquidation_ratio = get_ratios().get('liquidation')
    ratio = pricing_service.get_margin_ratio()
    if ratio > liquidation_ratio:
        return
    price_diff = pricing_service.is_price_diff_high_between_markets()
    if price_diff:
        report_event('ABC.Liquidation.Cancelled.PriceDiffHigh', extras={'price_diff': price_diff})
        return

    margin_call = _cancel_pending_liquidations(margin_call)
    wallet_type = Wallet.WalletType.COLLATERAL
    orders = LiquidationProvider.liquidate(
        user=margin_call.user,
        currencies=ABCCurrencies.get_all_currencies(wallet_type),
        wallet_type=wallet_type,
    )
    margin_call.orders.add(*orders)
    margin_call.last_action = AssetToDebtMarginCall.ACTION.liquidated
    margin_call.save(update_fields=['last_action'])

    from exchange.asset_backed_credit.tasks import task_margin_call_send_liquidation_notifications

    task_margin_call_send_liquidation_notifications.delay(margin_call.id)


def _cancel_pending_liquidations(margin_call: AssetToDebtMarginCall) -> AssetToDebtMarginCall:
    LiquidationProvider.cancel_active_margin_call_liquidation(margin_call)
    active_settlements = (
        SettlementTransaction.get_pending_user_settlements()
        .select_for_update(no_key=True)
        .filter(user_service__user=margin_call.user)
    )
    for active_settlement in active_settlements:
        LiquidationProvider.cancel_active_settlement_liquidation(active_settlement)
    return margin_call
