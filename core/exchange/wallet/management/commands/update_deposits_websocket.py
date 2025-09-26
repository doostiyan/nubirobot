import time

from django.core.management.base import BaseCommand

from exchange.base.logging import report_exception
from exchange.base.parsers import parse_currency
from exchange.blockchain.ws.update_websocket import run_websocket


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('currency', default='eth', help='Currency to run websocket for')
        parser.add_argument('--network', default='', help='Network to run websocket for')

    def handle(self, *args, **kwargs):
        currency = parse_currency(kwargs.get('currency'))
        network = str(kwargs.get('network'))
        try:
            while True:
                try:
                    run_websocket(currency=currency or None, network=network or None)
                except Exception:
                    report_exception()
                time.sleep(5)
        except KeyboardInterrupt:
            print('bye!')
