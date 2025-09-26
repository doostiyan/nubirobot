from decimal import Decimal

from django.db import models

from exchange.base.calendar import ir_now
from exchange.base.constants import MONETARY_DECIMAL_PLACES
from exchange.corporate_banking.managers import BulkCobankManager
from exchange.corporate_banking.models import REJECTION_REASONS, STATEMENT_STATUS, STATEMENT_TYPE
from exchange.wallet.constants import DEPOSIT_MAX_DIGITS


class CoBankStatement(models.Model):
    objects = BulkCobankManager()

    POSSIBLE_STATUS_TRANSITIONS = {
        STATEMENT_STATUS.new: {STATEMENT_STATUS.rejected, STATEMENT_STATUS.pending_admin, STATEMENT_STATUS.executed},
        STATEMENT_STATUS.validated: {},
        STATEMENT_STATUS.executed: {},
        STATEMENT_STATUS.rejected: {STATEMENT_STATUS.refunded},
        STATEMENT_STATUS.pending_admin: {STATEMENT_STATUS.executed, STATEMENT_STATUS.rejected},
        STATEMENT_STATUS.refunded: {},
    }

    REASONS_FOR_AUTOMATIC_STATUS_CHECK = {
        REJECTION_REASONS.source_account_not_found,
        REJECTION_REASONS.no_feature_flag,
        REJECTION_REASONS.empty_source_account,
    }

    UPDATABLE_FIELDS = {'source_iban'}
    UPDATABLE_STATUSES = {
        'source_iban': {STATEMENT_STATUS.new, STATEMENT_STATUS.pending_admin, STATEMENT_STATUS.rejected},
    }
    UPDATABLE_AMOUNTS = {'source_iban': {'', None}}

    amount = models.DecimalField(max_digits=DEPOSIT_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES)
    tp = models.SmallIntegerField(choices=STATEMENT_TYPE)
    tracing_number = models.CharField(max_length=100, help_text='Bank-assigned tracing number.', blank=True, null=True, db_index=True)
    transaction_datetime = models.DateTimeField(
        help_text='Date and time when the bank recorded this transaction.',
        blank=True,
        null=True,
    )
    payment_id = models.CharField(max_length=100, blank=True, null=True)
    source_account = models.CharField(
        max_length=25,
        help_text='The account from which the transaction was initiated.',
        blank=True,
        null=True,
    )
    source_iban = models.CharField(max_length=26, blank=True, null=True)
    source_card = models.CharField(max_length=16, blank=True, null=True)
    destination_account = models.ForeignKey('CoBankAccount', on_delete=models.DO_NOTHING)
    provider_statement_id = models.CharField(max_length=64, null=True)
    description = models.CharField(max_length=1000, blank=True, null=True, verbose_name='توضیحات')

    status = models.SmallIntegerField(choices=STATEMENT_STATUS, default=STATEMENT_STATUS.new)
    rejection_reason = models.SmallIntegerField(choices=REJECTION_REASONS, blank=True, null=True)
    created_at = models.DateTimeField(default=ir_now, help_text='The time this item is inserted in our database.')

    api_response = models.JSONField(default=dict)

    class Meta:
        verbose_name = 'صورت‌حساب‌های کوبنک'
        verbose_name_plural = verbose_name

        indexes = [
            models.Index('tp', 'source_account', 'transaction_datetime', name='cobankstatement_search_index'),
            models.Index('tp', 'source_iban', 'transaction_datetime', name='cobankstatement_iban_index'),
            models.Index('tp', 'status', name='cobankstatement_status_index'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['provider_statement_id', 'destination_account'],
                name='cobank_statement_uniqueness',
            ),
        ]

    @property
    def is_deposit(self):
        return self.tp == STATEMENT_TYPE.deposit and self.amount >= Decimal(0)

    def is_updatable(self, field: str):
        return (
            field in self.UPDATABLE_FIELDS
            and self.status in self.UPDATABLE_STATUSES.get(field, {})
            and getattr(self, field) in self.UPDATABLE_AMOUNTS.get(field, {})
        )
