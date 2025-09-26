from decimal import Decimal

from django.db import models, transaction

from exchange import settings
from exchange.asset_backed_credit.exceptions import AmountIsLargerThanDebtOnUpdateUserService, SettlementError
from exchange.asset_backed_credit.models import UserService
from exchange.asset_backed_credit.models.settlement import SettlementTransaction


class DebitSettlementTransaction(SettlementTransaction):
    pan = models.CharField(max_length=16)
    rrn = models.CharField(max_length=32)
    trace_id = models.CharField(max_length=32)
    terminal_id = models.CharField(max_length=32)
    rid = models.CharField(max_length=32, blank=True)

    class Meta:
        verbose_name = 'تراکنش تسویه نقدی'
        verbose_name_plural = 'تراکنش‌های تسویه نقدی'
        constraints = (models.UniqueConstraint(fields=('pan', 'trace_id', 'terminal_id'), name='unique_id'),)

    @classmethod
    @transaction.atomic
    def create(
        cls, user_service: UserService, amount: Decimal, status: int = SettlementTransaction.STATUS.confirmed, **kwargs
    ):
        """
        Creates a settlement record.
        Args:
            user_service(UserService)
            amount (Decimal)
            status (int)
        Returns:
            SettlementTransaction

        Raises:
            AmountIsLargerThanDebtOnUpdateUserService: when amount bigger than user current debt.
            SettlementError: when an active settlement record exists for user service.

        """
        initiated_settlements_count = (
            cls.objects.filter(user_service=user_service, transaction_datetime__isnull=True)
            .exclude(status=SettlementTransaction.STATUS.unknown_rejected)
            .count()
        )
        if initiated_settlements_count >= settings.ABC_DEBIT_INITIATED_SETTLEMENTS_COUNT:
            raise SettlementError()

        if user_service.current_debt < amount:
            raise AmountIsLargerThanDebtOnUpdateUserService()

        return cls.objects.create(user_service=user_service, amount=amount, status=status, **kwargs)
