from datetime import timedelta

from django.db import transaction
from django.db.models import Prefetch

from exchange.base.calendar import ir_now
from exchange.base.crons import CronJob, Schedule
from exchange.liquidator.models import Liquidation, LiquidationRequest


class DeleteEmptyLiquidation(CronJob):
    schedule = Schedule(run_every_mins=5)
    code = 'delete_empty_liquidation'

    def run(self):
        with transaction.atomic():
            liquidations = (
                Liquidation.objects.filter(
                    status=Liquidation.STATUS.new,
                    updated_at__lt=ir_now() - timedelta(minutes=5),
                )
                .prefetch_related(
                    Prefetch(
                        'liquidation_requests',
                        queryset=LiquidationRequest.objects.order_by('id').only('id'),
                    ),
                )
                .order_by('id')
                .select_for_update(of=('self',), skip_locked=True)
            )

            liquidation_requests_ids = set()
            liquidation_ids = []

            for liquidation in liquidations:
                liquidation_requests = liquidation.liquidation_requests.all()
                for liquidation_request in liquidation_requests:
                    liquidation_requests_ids.add(liquidation_request.id)
                liquidation_ids.append(liquidation.pk)

            Liquidation.objects.filter(id__in=liquidation_ids).delete()
            LiquidationRequest.objects.filter(id__in=liquidation_requests_ids).exclude(
                liquidations__status__in=Liquidation.ACTIVE_STATUSES,
            ).update(
                status=LiquidationRequest.STATUS.pending,
            )
