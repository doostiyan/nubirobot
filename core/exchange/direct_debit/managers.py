from django.db.models import Count, DecimalField, IntegerField, Manager, OuterRef, QuerySet, Subquery, Sum
from django.db.models.functions import Coalesce

from exchange.base.calendar import get_earliest_time, get_latest_time, ir_now


class DirectDebitContractQuerySet(QuerySet):
    def annotate_today_transaction_count(self):
        from exchange.direct_debit.models import DirectDeposit

        nw = ir_now()
        today_transaction_count = (
            DirectDeposit.objects.filter(
                contract__trace_id=OuterRef('trace_id'),
                deposited_at__range=(get_earliest_time(nw), get_latest_time(nw)),
            )
            .values('contract__trace_id')
            .annotate(count=Count(1))
            .values('count')
        )

        return self.annotate(
            today_transaction_count=Coalesce(Subquery(today_transaction_count), 0, output_field=IntegerField())
        )

    def annotate_today_transaction_amount(self):
        from exchange.direct_debit.models import DirectDeposit

        nw = ir_now()
        today_transaction_amount = (
            DirectDeposit.objects.filter(
                contract__trace_id=OuterRef('trace_id'),
                deposited_at__range=(get_earliest_time(nw), get_latest_time(nw)),
            )
            .values('contract__trace_id')
            .annotate(amount=Sum('amount'))
            .values('amount')
        )

        return self.annotate(
            today_transaction_amount=Coalesce(Subquery(today_transaction_amount), 0, output_field=DecimalField())
        )


class DirectDebitContractManager(Manager):
    def get_queryset(self):
        return DirectDebitContractQuerySet(self.model, using=self._db)
