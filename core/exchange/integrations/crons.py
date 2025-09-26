from exchange import settings
from exchange.base.crons import CronJob, Schedule
from exchange.integrations.finnotech import FinnotechTokenAPI

token_api = FinnotechTokenAPI()


class FinnotechTokenRefreshCron(CronJob):
    schedule = Schedule(run_every_mins=3 * 24 * 60)
    code = 'finnotech_api_token_refresh'
    celery_beat = True
    task_name = 'integrations.task_finnotech_refresh_token'

    def run(self):
        if not settings.IS_PROD:
            return
        r = token_api.refresh_token()
        if not r.get('result'):
            # If refresh token fails, call get_token
            r = token_api.get_token()
        if not r.get('result'):
            raise ValueError(str(r))
