import time

from django.core.management.base import BaseCommand

from exchange.market.autotrader import do_autotrade_round
from exchange.market.models import AutoTradingPermit


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        try:
            while True:
                do_autotrade_round(AutoTradingPermit.FREQUENCY.fast)
                do_autotrade_round(AutoTradingPermit.FREQUENCY.normal)
                print('')
                time.sleep(30)
                do_autotrade_round(AutoTradingPermit.FREQUENCY.fast)
                print('')
                time.sleep(40)
        except KeyboardInterrupt:
            print('bye!')
