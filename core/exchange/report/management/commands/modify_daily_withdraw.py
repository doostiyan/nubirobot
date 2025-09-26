from django.core.management.base import BaseCommand

from exchange.base.api import ParseError
from exchange.base.logging import log_event
from exchange.base.parsers import parse_int
from exchange.report.models import DailyWithdraw
from exchange.wallet.models import WithdrawRequest
from exchange.wallet.settlement import JibitSettlementV2


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--batch', help='number of the batch', type=int, default=300)

    def handle(self, *args, **kwargs):
        daily_withdraw_updated_ids = []
        daily_withdraw_amount_mismatch_ids = []
        daily_withdraw_matching_withdraw_request_not_found_ids = []
        failed_daily_withdraw_ids = []
        unexpected_transfer_pk_daily_withdraw_ids = []
        while True:
            daily_without_withdraw = (
                DailyWithdraw.objects.filter(withdraw__isnull=True, broker=DailyWithdraw.BROKER.jibit_v2)
                .exclude(id__in=failed_daily_withdraw_ids)
                .exclude(transfer_pk__contains='MAPI')
                .order_by('-pk')[: kwargs['batch']]
            )
            daily_withdraw_for_fix = []
            if not daily_without_withdraw:
                break
            for daily_withdraw in daily_without_withdraw:
                try:
                    transfer_pk = parse_int(daily_withdraw.transfer_pk, required=True)
                except ParseError:
                    unexpected_transfer_pk_daily_withdraw_ids.append(daily_withdraw.id)
                    failed_daily_withdraw_ids.append(daily_withdraw.id)
                    continue
                withdraw_request = WithdrawRequest.objects.filter(pk=transfer_pk).first()
                if withdraw_request and JibitSettlementV2(withdraw_request).net_amount == daily_withdraw.amount:
                    daily_withdraw.withdraw = withdraw_request
                    daily_withdraw_for_fix.append(daily_withdraw)
                else:
                    failed_daily_withdraw_ids.append(daily_withdraw.id)
                    withdraw_request_id = None
                    if withdraw_request:
                        daily_withdraw_amount_mismatch_ids.append(daily_withdraw.id)
                        withdraw_request_id = withdraw_request.id
                    else:
                        daily_withdraw_matching_withdraw_request_not_found_ids.append(daily_withdraw.transfer_pk)
                    log_event(
                        'not_found_diff',
                        level='INFO',
                        module='general',
                        runner='admin',
                        category='general',
                        details='INFO: No withdrawal request records were found matching this daily withdrawal.'
                                f' withdraw_request_id: {str(withdraw_request_id)},'
                                f' daily_withdraw_id: {str(daily_withdraw.id)},'
                                f' transfer_pk: {str(daily_withdraw.transfer_pk)},'
                                f' amount: {str(daily_withdraw.amount)}',
                    )
            DailyWithdraw.objects.bulk_update(daily_withdraw_for_fix, ('withdraw',))
            daily_withdraw_updated_ids.extend([daily.pk for daily in daily_withdraw_for_fix])

        self.stdout.write(self.style.ERROR(f'not match amount ids :{daily_withdraw_amount_mismatch_ids}'))
        self.stdout.write(self.style.ERROR(f'unexpected ids :{unexpected_transfer_pk_daily_withdraw_ids}'))
        self.stdout.write(
            self.style.ERROR(
                f'withdraw request not found ids :{daily_withdraw_matching_withdraw_request_not_found_ids}'
            )
        )
        self.stdout.write(self.style.SUCCESS(f'daily withdraw updated ids: {daily_withdraw_updated_ids}'))
        self.stdout.write(self.style.SUCCESS(f'len daily withdraw updated: {len(daily_withdraw_updated_ids)}'))
        self.stdout.write(self.style.ERROR(f'len daily withdraw failed: {len(failed_daily_withdraw_ids)}'))
        self.stdout.write(self.style.SUCCESS('Done'))
        log_event(
            'diff_withdraw_info',
            level='INFO',
            module='general',
            runner='admin',
            category='general',
            details='INFO:'
            f' not match amount ids :{daily_withdraw_amount_mismatch_ids},'
            f' unexpected ids :{unexpected_transfer_pk_daily_withdraw_ids},'
            f' not found withdraw request ids :{daily_withdraw_matching_withdraw_request_not_found_ids},'
            f' daily withdraw updated ids={daily_withdraw_updated_ids}'
            f' len daily withdraw updated: {len(daily_withdraw_updated_ids)}'
            f' len daily withdraw failed: {len(failed_daily_withdraw_ids)}',
        )
