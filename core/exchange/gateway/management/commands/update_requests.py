import time

from django.core.management.base import BaseCommand

from exchange.gateway.update_requests import do_update_gateway_requests_round


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        print('Gateway Settlement Update')
        try:
            while True:
                do_update_gateway_requests_round()
                print('.')
                time.sleep(180)
        except KeyboardInterrupt:
            print('bye!')
