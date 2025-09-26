from django.core.management import call_command

from exchange.base.crons import CronJob, Schedule


class CleanupCron(CronJob):
    schedule = Schedule(run_at_times=['2:30', '7:31'])
    code = 'cleanup'

    def run(self):
        print('Performing DB cleanup...')
        call_command('cleanup')
