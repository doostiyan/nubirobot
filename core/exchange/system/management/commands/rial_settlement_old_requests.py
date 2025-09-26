import datetime

from django.core.management.base import BaseCommand
from django.utils.timezone import now
from tqdm import tqdm

from exchange.base.logging import report_exception
from exchange.base.models import RIAL
from exchange.wallet.models import WithdrawRequest
from exchange.wallet.tasks import settle_rial_withdraws


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        error_count = 0

        withdraws = (
            WithdrawRequest.objects.filter(
                tp=WithdrawRequest.TYPE.normal,
                status__in=[WithdrawRequest.STATUS.verified, WithdrawRequest.STATUS.accepted],
                wallet__currency=RIAL,
                created_at__lte=now() - datetime.timedelta(hours=7),
                created_at__gte=now() - datetime.timedelta(days=7),
                amount__gte=110000,
            )
            .order_by('created_at')
            .iterator(chunk_size=1000)
        )

        options = {
            'cancellable': False,
        }

        for withdraw in tqdm(withdraws):
            if withdraw.status == WithdrawRequest.STATUS.verified:
                withdraw.status = WithdrawRequest.STATUS.accepted
                withdraw.save(update_fields=('status',))

            try:
                settle_rial_withdraws(str(withdraw.id), WithdrawRequest.SETTLE_METHOD.jibit_v2, options)
            except Exception:
                error_count += 1
                report_exception()

        print('Error Count: ', error_count)
