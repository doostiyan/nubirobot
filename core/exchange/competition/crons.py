from exchange.base.crons import CronJob, Schedule
from exchange.competition.models import Competition


class UpdateCompetitionResultsCron(CronJob):
    schedule = Schedule(run_every_mins=60)
    code = 'update_competition_results'

    def run(self):
        print('Updating competition results...')
        competition = Competition.get_active_competition()
        if not competition:
            return
        registrations = competition.registrations.filter(is_active=True)
        for rc in registrations:
            rc.update_current_balance()
