from decimal import ROUND_DOWN, ROUND_UP, Decimal
from typing import List

from django.db import transaction

from exchange.accounts.models import User
from exchange.asset_backed_credit.exceptions import CannotEstimateSrcAmount, CreateLiquidationOrderError
from exchange.asset_backed_credit.externals.price import PriceProvider
from exchange.asset_backed_credit.externals.user import UserProvider
from exchange.asset_backed_credit.models import AssetToDebtMarginCall, SettlementTransaction
from exchange.asset_backed_credit.models.wallet import Wallet
from exchange.asset_backed_credit.services.wallet.wallet import WalletService
from exchange.base.constants import ZERO
from exchange.base.models import AMOUNT_PRECISIONS_V2, RIAL
from exchange.base.money import money_is_zero
from exchange.market.marketmanager import MarketManager
from exchange.market.models import Order, OrderMatching


class LiquidationProvider:
    @staticmethod
    def cancel_active_margin_call_liquidation(margin_call: AssetToDebtMarginCall) -> None:
        margin_call.cancel_active_orders()

    @staticmethod
    def cancel_active_settlement_liquidation(settlement: SettlementTransaction) -> None:
        settlement.cancel_active_orders()

    @staticmethod
    def get_orders_matched_total_price(settlement: SettlementTransaction) -> Decimal:
        """
        get matched total price of orders that their sell deposit transaction is not committed yet!
        (positive transactions may have delays in trade processor)
        """
        total_price = Decimal(0)
        order_ids = settlement.orders.values_list('id', flat=True)
        for order_matching in OrderMatching.objects.filter(
            sell_order__in=order_ids, sell_deposit__isnull=True
        ).select_related('sell_order'):
            total_price += order_matching.sell_order.net_matched_total_price
        return total_price

    @staticmethod
    def liquidate(
        user: User,
        currencies: List[int],
        wallet_type: Wallet.WalletType,
        amount: Decimal = None,
        tolerance=Decimal('0.03'),
    ) -> List[Order]:
        wallets = {
            w.currency: w
            for w in WalletService.get_user_wallets(user_id=user.uid, exchange_user_id=user.id, wallet_type=wallet_type)
        }

        total_amount = amount
        trade_fee = UserProvider.get_user_fee(user)

        orders = []
        for currency in currencies:
            wallet = wallets.get(currency)
            if not wallet or money_is_zero(wallet.balance) or currency == RIAL:
                continue

            price = PriceProvider(src_currency=currency).get_last_trade_price()
            if not price:
                raise CannotEstimateSrcAmount()

            price = price * (1 - tolerance)

            if total_amount:
                estimated_src_amount = (total_amount / price * (1 + trade_fee)).quantize(
                    AMOUNT_PRECISIONS_V2[wallet.currency],
                    ROUND_UP,
                )
                estimated_src_amount = min(estimated_src_amount, wallet.balance)
            else:
                estimated_src_amount = wallet.balance

            _orders = LiquidationProvider._liquidate(
                user=user, currency=currency, amount=estimated_src_amount, price=price, wallet_type=wallet_type
            )
            orders.extend(_orders)

            if total_amount:
                total_price = sum(order.total_price / (1 + trade_fee) for order in _orders)
                total_amount -= total_price.quantize(AMOUNT_PRECISIONS_V2[RIAL], ROUND_DOWN)
                if total_amount <= ZERO:
                    return orders
        return orders

    @staticmethod
    @transaction.atomic
    def _liquidate(
        user: User, currency: int, amount: Decimal, price: Decimal, wallet_type: Wallet.WalletType
    ) -> List[Order]:
        """
        Liquidates a specified amount of a given currency for the user at a specified price.

        Parameters:
        - user (User): The user for whom the liquidation is being performed.
        - currency (int): The currency code to be liquidated.
        - amount (Decimal): The total amount of the currency to be liquidated.
        - price (Decimal): The price at which the liquidation orders should be executed.

        Returns:
        - List[Order]: A list of Order objects representing the executed liquidation orders.

        Raises:
        - CreateLiquidationOrderError: If there is an error creating a liquidation order.

        The function attempts to liquidate the specified amount of currency by creating
        and executing sell orders on the market. It will break orders larger than 1B
        """
        orders = []

        remaining_amount = amount
        max_rial_order_dst_amount = 1_000_000_000_0 - 10
        max_rial_order_src_amount = (max_rial_order_dst_amount / price).quantize(
            AMOUNT_PRECISIONS_V2[currency], ROUND_DOWN
        )

        while remaining_amount > ZERO:
            order, error = MarketManager.create_order(
                user=user,
                src_currency=currency,
                dst_currency=RIAL,
                amount=min(remaining_amount, max_rial_order_src_amount),
                order_type=Order.ORDER_TYPES.sell,
                execution_type=Order.EXECUTION_TYPES.limit,
                channel=Order.CHANNEL.system_abc_liquidate,
                allow_small=True,
                is_credit=wallet_type == Wallet.WalletType.COLLATERAL,
                is_debit=wallet_type == Wallet.WalletType.DEBIT,
                price=price,
            )

            if error:
                raise CreateLiquidationOrderError(error)

            remaining_amount -= order.amount
            orders.append(order)

        return orders
