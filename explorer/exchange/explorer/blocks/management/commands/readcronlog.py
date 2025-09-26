from pprint import pprint

from django.core.management import BaseCommand

from exchange.explorer.utils.iterator import get_ordered_list_options
from django_cron.models import CronJobLog


class Command(BaseCommand):
    help = "Read cron job log from db by code"

    def add_arguments(self, parser):
        parser.add_argument(
            'code',
            type=str,
            nargs='?',
            help='the cron code',
        )

    def handle(self, *args, **kwargs):
        code = kwargs.get('code')
        if not code:
            network = input('Enter network: ')
            network = network.lower()

            crons = [f'get_{network}_block_txs', f'delete_{network}_block_txs', f'update_{network}_block_head_diff', ]
            cron_code = get_cron_from_user_input(crons)

        try:
            cron_job_log = CronJobLog.objects.filter(code=cron_code).order_by('-start_time').values().first()
            if cron_job_log:
                pprint(cron_job_log)
            else:
                print('There is no cron job log with this code in the database')

        except Exception as e:
            print('Exception occurred: {}'.format(e))


def get_cron_from_user_input(crons):
    cron_option_values, cron_options = get_ordered_list_options(crons)
    cron_index = input('Enter cron\noptions:\n{}\n: '.format(cron_option_values))
    cron = cron_options[cron_index].split(')')[1].strip()
    return cron
