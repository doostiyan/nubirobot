from decimal import Decimal, ROUND_DOWN

from django.core.cache import cache
from django.db import models, transaction
from django.utils.timezone import now
from model_utils import Choices

from exchange.accounts.models import User
from exchange.base.models import Currencies
from exchange.market.models import Order
from exchange.wallet.models import Transaction, Wallet


class RedeemRequest(models.Model):
    PLAN = Choices(
        (1, 'pgala2022', 'PGala2020'),
    )
    STATUS = Choices(
        (0, 'new', 'New'),
        (1, 'allowed', 'Allowed'),
        (2, 'confirmed', 'Confirmed'),
        (3, 'done', 'Done'),
        (4, 'rejected', 'Rejected'),
    )
    MAX_AUTO_REDEEM_IRR = Decimal('50_000_000_0')

    plan = models.IntegerField(choices=PLAN)
    user = models.ForeignKey(User, related_name='+', on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=20, decimal_places=10)
    redeem_value = models.DecimalField(max_digits=25, decimal_places=10)
    status = models.IntegerField(choices=STATUS, default=STATUS.new)
    requested_at = models.DateTimeField(null=True, blank=True)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    has_sana = models.BooleanField(default=False)
    src_transaction = models.ForeignKey(Transaction, related_name='+', null=True, blank=True, on_delete=models.SET_NULL)
    dst_transaction = models.ForeignKey(Transaction, related_name='+', null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        verbose_name = 'درخواست بازخرید'
        verbose_name_plural = verbose_name
        unique_together = ['plan', 'user']

    def do_redeem(self):
        """Process the user's redeem request and change funds."""
        if self.plan != self.PLAN.pgala2022:
            return False, 'PlanNotSupported'
        if self.status in [self.STATUS.done, self.STATUS.confirmed]:
            return True, None
        if self.status != self.STATUS.allowed:
            return False, 'StatusNotRedeemable'
        is_big_redeem = self.redeem_value >= self.MAX_AUTO_REDEEM_IRR
        self.requested_at = now()
        self.status = self.STATUS.confirmed if is_big_redeem else self.STATUS.done
        src_transaction, dst_transaction = self.create_transactions()
        if not src_transaction or not dst_transaction:
            return False, 'CreateTransactionFailed'
        self.src_transaction = src_transaction
        self.dst_transaction = dst_transaction
        self.save(update_fields=['requested_at', 'status', 'src_transaction', 'dst_transaction'])
        if is_big_redeem:
            self.create_blocking_order()
        return True, None

    def create_transactions(self):
        """Create change transactions for this redeem request."""
        if self.plan != self.PLAN.pgala2022:
            return None, None
        src_wallet = Wallet.get_user_wallet(self.user, Currencies.gala)
        dst_wallet = Wallet.get_user_wallet(self.user, Currencies.rls)
        if src_wallet.balance < self.amount or dst_wallet.balance < 0:
            return None, None
        tx_description = 'بازخرید پی‌گالا توسط نوبیتکس'
        src_transaction = src_wallet.create_transaction(tp='manual', amount=-self.amount, description=tx_description)
        if not src_transaction:
            return None, None
        src_transaction.commit()
        # Charge
        max_tx_value = Decimal('9999999999')
        if self.redeem_value > max_tx_value:
            self.redeem_value = max_tx_value
        dst_transaction = dst_wallet.create_transaction(tp='manual', amount=self.redeem_value, description=tx_description)
        if not dst_transaction:
            return None, None
        dst_transaction.commit(ref=self)
        return src_transaction, dst_transaction

    def _update_user_orders_cache(self):
        """Update orders list cache keys for the user."""
        cache.set(f'user_{self.user_id}_recent_order', True, 100)
        transaction.on_commit(lambda: cache.set(f'user_{self.user_id}_no_order', False, 60))

    def create_blocking_order(self):
        """Block dst balance for the requesting user. The block is removed manually by admins."""
        if self.plan != self.PLAN.pgala2022:
            raise ValueError
        effective_price = (self.redeem_value / self.amount).quantize(Decimal('1e-8'), rounding=ROUND_DOWN)
        order = Order.objects.create(
            user=self.user,
            order_type=Order.ORDER_TYPES.buy,
            src_currency=Currencies.gala,
            dst_currency=Currencies.rls,
            execution_type=Order.EXECUTION_TYPES.limit,
            amount=self.amount,
            price=effective_price,
            status=Order.STATUS.active,
            channel=Order.CHANNEL.system_block,
        )
        if not order or not order.pk:
            raise ValueError('OrderCreationAssertionFailed')
        self._update_user_orders_cache()

    def do_unblock(self):
        """Unblock dst balance for user."""
        if self.plan != self.PLAN.pgala2022:
            return False, 'PlanNotSupported'
        if self.status != self.STATUS.confirmed:
            return False, 'StatusNotUnblockable'
        if not self.has_sana:
            return False, 'MissingSanaConfirmation'
        order = Order.objects.get(
            user=self.user,
            order_type=Order.ORDER_TYPES.buy,
            src_currency=Currencies.gala,
            dst_currency=Currencies.rls,
            execution_type=Order.EXECUTION_TYPES.limit,
            amount=self.amount,
            status=Order.STATUS.active,
            channel=Order.CHANNEL.system_block,
        )
        if not order:
            return False, 'GetOrderFailed'
        is_canceled = order.do_cancel()
        if not is_canceled:
            return False, 'CannotCancelOrder'
        self._update_user_orders_cache()
        self.terms_accepted_at = now()
        self.status = self.STATUS.done
        self.save(update_fields=['terms_accepted_at', 'status'])
        return True, None
