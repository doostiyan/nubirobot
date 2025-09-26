import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone
from requests import HTTPError

from exchange.base.logging import report_exception
from exchange.report.crons import SaveDailyDepositsV1, SaveDailyWithdrawsV1, SaveDailyDepositsV2, SaveDailyWithdrawsV2


class Command(BaseCommand):
    """
    Examples:
        python manage.py fetch_jibit_history -m withdraw -V1 -s 2018-11-01
        python manage.py fetch_jibit_history -m deposit -V2 -b 2022-08-01
    """
    help = 'Fetch Jibit old records of deposit and withdraw transactions.'

    CRON_CLASSES = {
        1: {
            'deposit': SaveDailyDepositsV1,
            'withdraw': SaveDailyWithdrawsV1,
        },
        2: {
            'deposit': SaveDailyDepositsV2,
            'withdraw': SaveDailyWithdrawsV2,
        },
    }

    def add_arguments(self, parser):
        parser.add_argument(
            '-V', '--api-version', default=1, type=int, choices=(1, 2), help='Select Jibit API version',
        )
        parser.add_argument(
            '-m', '--mode', type=str, choices=('deposit', 'withdraw'), required=True,
            help='Limit transactions to deposit/withdraw',
        )
        parser.add_argument(
            '-b', '--before', type=str, help='Continue fetching from specific time back [use YYYY-MM-DD format]',
        )
        parser.add_argument(
            '-s', '--since', type=str, help='Continue fetching from specific time forth [use YYYY-MM-DD format]',
        )
        parser.add_argument(
            '--verbose', action='store_true', default=False, help='Print progress details',
        )

    def handle(self, mode, api_version, before, since, verbose=False, **options):
        cron = self.CRON_CLASSES[api_version][mode]
        from_date = timezone.datetime.fromisoformat(f'{since}T00:00:00+04:30') if since else None
        to_date = timezone.datetime.fromisoformat(f'{before}T00:00:00+04:30') if before else None
        self.fetch_data(cron, from_date, to_date, verbose=verbose)

    @staticmethod
    def fetch_data(
        cron,
        from_date: datetime.datetime,
        to_date: datetime.datetime,
        verbose: bool = False,
    ):
        """Fetch Jibit history in range [from_date, to_date)."""
        has_next = True
        page = 1
        while has_next:
            for _ in range(5):
                try:
                    if verbose:
                        print(f'Fetching Jibit history page {page}')
                    response = cron.api_func(from_date, to_date, page=page) or {}
                    if verbose:
                        print('  n={}, total={}, hasNext={}'.format(
                            len(response.get('elements', [])),
                            response.get('numberOfElements', 0),
                            response.get('hasNext'),
                        ))
                except HTTPError:
                    pass
                else:
                    break
            else:
                raise HTTPError('Multiple HTTPError in a row for Jibit')
            for item in cron.get_items(response):
                try:
                    data = cron.parse_item(item)
                    record, _ = cron.model.objects.get_or_create(**data)
                except:
                    report_exception()
            has_next = cron.has_next(response)
            page += 1
