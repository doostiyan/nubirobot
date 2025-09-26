from django.core.management.base import BaseCommand

from exchange.report.models import DailyWithdraw
from exchange.wallet.models import WithdrawRequest


class Command(BaseCommand):
    """
    Examples:
        python manage.py fix_jibit_history
    """
    help = 'Fix Jibit daily withdraws.'

    def handle(self, **options):
        last_id = 0
        while True:
            daily_withdraws = list(
                DailyWithdraw.objects.filter(withdraw__isnull=True, id__gt=last_id).order_by('pk')[:500]
            )
            if not daily_withdraws:
                self.stdout.write('')
                break
            for daily_withdraw in daily_withdraws:
                last_id = daily_withdraw.id
                try:
                    withdraw = WithdrawRequest.objects.get(
                        pk=daily_withdraw.transfer_pk,
                        target_account__shaba_number=daily_withdraw.destination,
                    )
                    if withdraw.amount - withdraw.calculate_fee() == daily_withdraw.amount:
                        daily_withdraw.withdraw = withdraw
                except (ValueError, WithdrawRequest.DoesNotExist):
                    pass
            DailyWithdraw.objects.bulk_update(daily_withdraws, ('withdraw',))
            self.stdout.write('.', ending='')
        self.stdout.write(self.style.SUCCESS('Done'))

