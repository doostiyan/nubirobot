import json
from decimal import ROUND_DOWN, Decimal

from django.db import DatabaseError, models, transaction
from django.utils.functional import cached_property
from model_utils import Choices

from exchange.accounts.models import User
from exchange.base.constants import ZERO
from exchange.base.logging import report_event, report_exception
from exchange.base.models import AMOUNT_PRECISIONS_V2, AVAILABLE_MARKETS, Settings
from exchange.base.money import money_is_zero
from exchange.config.config.derived_data import get_market_symbol
from exchange.liquidator import errors
from exchange.liquidator.errors import IncompatibleAmountAndPriceError, LiquidationRequestTransactionCommitError
from exchange.market.models import Market, Order
from exchange.wallet.models import Transaction, Wallet


class LiquidationRequest(models.Model):
    CACHE_KEY = 'liquidator_enabled_markets'

    SERVICE_TYPES = Choices(
        (1, 'margin', 'margin'),
        (2, 'abc', 'asset backed credit'),
        (3, 'fee_collector', 'fee collector'),
    )

    STATUS = Choices(
        (1, 'pending', 'pending'),
        (2, 'in_progress', 'in progress'),
        (3, 'done', 'done'),
        (4, 'waiting_for_transactions', 'waiting for transactions'),
        (5, 'transactions_failed', 'transactions failed'),
    )
    SIDES = Order.ORDER_TYPES
    OPEN_STATUSES = (STATUS.pending, STATUS.in_progress)

    created_at = models.DateTimeField(
        auto_now_add=True, null=True, blank=True, db_index=True, verbose_name='تاریخ ایجاد'
    )
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True, verbose_name='تاریخ تغییر')

    service = models.SmallIntegerField(choices=SERVICE_TYPES, default=SERVICE_TYPES.margin)
    src_wallet = models.ForeignKey(Wallet, related_name='+', on_delete=models.PROTECT, verbose_name='کیف مبدا')
    dst_wallet = models.ForeignKey(Wallet, related_name='+', on_delete=models.PROTECT, verbose_name='کیف مقصد')

    side = models.SmallIntegerField(choices=SIDES, verbose_name='جهت')

    status = models.SmallIntegerField(choices=STATUS, default=STATUS.pending, db_index=True, verbose_name='وضعیت')
    amount = models.DecimalField(max_digits=30, decimal_places=10, null=True, verbose_name='مقدار ارز مبدا')
    filled_amount = models.DecimalField(max_digits=30, decimal_places=10, verbose_name='مقدار پر شده', default=ZERO)
    filled_total_price = models.DecimalField(max_digits=30, decimal_places=10, verbose_name='ارزش نهایی', default=ZERO)
    fee = models.DecimalField(max_digits=30, decimal_places=10, verbose_name='کارمزد', default=ZERO)

    @property
    def price(self) -> Decimal:
        if not self.filled_amount:
            return ZERO
        return (self.filled_total_price / self.filled_amount).quantize(
            AMOUNT_PRECISIONS_V2[self.src_currency],
            ROUND_DOWN,
        )

    @property
    def net_total_price(self) -> Decimal:
        return self.filled_total_price + (-self.fee if self.is_sell else self.fee)

    @property
    def is_sell(self) -> bool:
        return self.side == Order.ORDER_TYPES.sell

    @property
    def is_open(self) -> bool:
        return self.status in self.OPEN_STATUSES

    @property
    def src_currency(self) -> int:
        return self.src_wallet.currency

    @property
    def dst_currency(self) -> int:
        return self.dst_wallet.currency

    @cached_property
    def market(self) -> Market:
        return Market.get_for(self.src_currency, self.dst_currency)

    @cached_property
    def market_symbol(self):
        return get_market_symbol(self.src_currency, self.dst_currency)

    @property
    def user(self) -> User:
        return self.src_wallet.user

    @property
    def unfilled_amount(self) -> Decimal:
        return self.amount - self.filled_amount

    @classmethod
    @transaction.atomic
    def create(
        cls,
        user_id: int,
        src_currency: int,
        dst_currency: int,
        side: int,
        amount: Decimal,
        wallet_type: int = Wallet.WALLET_TYPE.spot,
        service: SERVICE_TYPES = SERVICE_TYPES.margin,
    ) -> 'LiquidationRequest':

        if amount <= ZERO or money_is_zero(amount):
            raise errors.InvalidAmount

        if [src_currency, dst_currency] not in AVAILABLE_MARKETS:
            raise errors.UnsupportedPair

        obj = cls(side=side, amount=amount, service=service)

        src_wallet = Wallet.get_user_wallet(user_id, src_currency, tp=wallet_type, create=not obj.is_sell)
        dst_wallet = Wallet.get_user_wallet(user_id, dst_currency, tp=wallet_type, create=obj.is_sell)

        if not src_wallet or not dst_wallet:
            raise errors.InsufficientBalance

        obj.src_wallet = src_wallet
        obj.dst_wallet = dst_wallet

        if obj.is_sell:
            if amount > obj.src_wallet.active_balance:
                raise errors.InsufficientBalance
        else:
            last_price = obj.market.get_last_trade_price()
            if amount * last_price > obj.dst_wallet.active_balance:
                raise errors.InsufficientBalance

        obj.save()
        return obj

    def commit_wallet_transactions_for_external_liquidations(self) -> None:
        request_external_filled_amount = Decimal('0')
        request_external_total_price = Decimal('0')

        for association in self.liquidation_associations.all():
            if association.liquidation.market_type != association.liquidation.MARKET_TYPES.external:
                continue

            if self.side == LiquidationRequest.SIDES.buy:
                # position was sell (short) - crypto must be given to the requester
                filled_amount = association.amount
                filled_total_price = -association.total_price
            else:
                # position was buy (long) - fiat must be given to the requester
                filled_amount = -association.amount
                filled_total_price = association.total_price

            request_external_filled_amount += filled_amount
            request_external_total_price += filled_total_price

        trx_values = [request_external_filled_amount, request_external_total_price]
        if any(trx_values):
            if not all(trx_values):
                raise IncompatibleAmountAndPriceError(trx_values)
        else:
            return

        try:
            with transaction.atomic():
                trx1 = self.src_wallet.create_transaction(
                    'external_liquidation',
                    amount=request_external_filled_amount,
                    ref_module=Transaction.REF_MODULES['LiquidationRequestSrc'],
                    ref_id=self.pk,
                    description=f'External liquidation trx for request #{self.pk}',
                )
                trx2 = self.dst_wallet.create_transaction(
                    'external_liquidation',
                    amount=request_external_total_price,
                    ref_module=Transaction.REF_MODULES['LiquidationRequestDst'],
                    ref_id=self.pk,
                    description=f'External liquidation trx for request #{self.pk}',
                )
                trx1.commit()
                trx2.commit()
        except (DatabaseError, AttributeError, ValueError) as e:
            raise LiquidationRequestTransactionCommitError(f'Commit failed due to: {e}') from e

    @classmethod
    def is_market_enabled_in_liquidator(cls, market: Market) -> bool:
        enabled_markets = Settings.get_value(cls.CACHE_KEY, default='[]')
        try:
            enabled_markets = json.loads(enabled_markets)
        except json.JSONDecodeError:
            report_exception()
            return False

        if not isinstance(enabled_markets, list):
            report_event('Liquidator enabled markets is not a list')
            return False

        return enabled_markets == ['all'] or market.symbol in enabled_markets
