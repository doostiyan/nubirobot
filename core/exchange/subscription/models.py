from django.db import models
from model_utils import Choices

from exchange.accounts.models import User
from exchange.base.calendar import ir_now, to_shamsi_date
from exchange.base.models import Currencies
from exchange.base.templatetags.nobitex import currencyformat
from exchange.wallet.models import Transaction


class Subscription(models.Model):
    """
    Represents an abstract subscription for a user with various status options and methods for managing the subscription.

    Attributes:
        STATUS (Choices): virtual subscription status
        subscriber (ForeignKey): A foreign key relationship to the User model, indicating the subscriber of the subscription.
        created_at (DateTimeField): The date and time when the subscription was created.
        starts_at (DateTimeField): The date and time when the subscription starts.
        expires_at (DateTimeField): The date and time when the subscription expires.
        is_trial (BooleanField): Indicates if the subscription is a trial or not.
        is_auto_renewal_enabled (BooleanField): Indicates if auto-renewal is enabled for the subscription.
        is_renewed (BooleanField): Indicates if the subscription has been renewed.
        canceled_at (DateTimeField, optional): The date and time when the subscription was canceled, if applicable.
        fee_amount (DecimalField): The fee amount associated with the subscription.
        fee_currency (IntegerField): The currency code chosen for the fee.
        withdraw_transaction (ForeignKey, optional): A foreign key relationship to the Transaction model,
                                                     representing the transaction associated with the subscription withdrawal.

    Meta:
        abstract (bool): Indicates that this class is an abstract model and not meant to be instantiated directly.

    Properties:
        status: A property that returns the current status of the subscription based on its various attributes.
        is_expired: A property that determines if the subscription has expired.
        is_waiting: A property that determines if the subscription is waiting to become active.
        is_active: A property that determines if the subscription is currently active.

    Methods:
        create_transactions(): Abstract method to create transactions related to the subscription.
        renew(): Abstract method to renew the subscription.
        cancel(): Abstract method to cancel the subscription.
        notify_insufficient_balance(): Abstract method to send notifications for insufficient balance.
        notify_upcoming_renewal(): Abstract method to send notifications for upcoming subscription renewal.
        notify_renewal(): Abstract method to send notifications for successful subscription renewal.
    """

    STATUS = Choices(
        (1, 'waiting', 'Waiting'),
        (2, 'active', 'Active'),
        (3, 'expired', 'Expired'),
        (4, 'canceled', 'Canceled'),
    )

    subscriber = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='%(app_label)s_%(class)s_related',
        related_query_name='%(app_label)s_%(class)ss',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    starts_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    is_trial = models.BooleanField()
    is_auto_renewal_enabled = models.BooleanField(default=False)
    is_renewed = models.BooleanField(null=True)
    canceled_at = models.DateTimeField(null=True)
    fee_amount = models.DecimalField(max_digits=30, decimal_places=10)
    fee_currency = models.IntegerField(choices=Currencies)
    withdraw_transaction = models.ForeignKey(Transaction, related_name='+', null=True, on_delete=models.DO_NOTHING)

    class Meta:
        abstract = True
        verbose_name = 'اشتراک'
        verbose_name_plural = 'اشتراک ها'

    @property
    def status(self):
        if self.canceled_at:
            return self.STATUS.canceled
        if self.is_expired:
            return self.STATUS.expired
        if self.is_active:
            return self.STATUS.active
        if self.is_waiting:
            return self.STATUS.waiting

        raise ValueError('Invalid status')

    @property
    def is_expired(self):
        return self.expires_at < ir_now()

    @property
    def is_waiting(self):
        return self.starts_at > ir_now()

    @property
    def is_active(self):
        return not self.canceled_at and not self.is_expired and not self.is_waiting

    @property
    def shamsi_expire_date(self) -> str:
        return to_shamsi_date(self.expires_at)

    @classmethod
    def get_actives(cls):
        now = ir_now()
        return cls.objects.filter(starts_at__lte=now, expires_at__gt=now, canceled_at__isnull=True)

    def create_transactions(self) -> None:
        raise NotImplementedError()

    def renew(self) -> None:
        raise NotImplementedError()

    def cancel(self) -> None:
        raise NotImplementedError()

    def notify_insufficient_balance(self) -> None:
        raise NotImplementedError()

    def notify_renewal(self) -> None:
        raise NotImplementedError()
