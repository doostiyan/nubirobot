from django_cron import Schedule

from exchange.base.crons import CronJob
from exchange.gateway.update_requests import do_update_gateway_requests_round


class UpdateGatewayRequestsCron(CronJob):
    schedule = Schedule(run_every_mins=3)
    code = 'update_gateway_requests'

    def run(self):
        print('[CRON] {}'.format(self.code))
        do_update_gateway_requests_round()
