from django.core.management.base import BaseCommand

from exchange.system.scripts.rial_settlement import run_rial_settlement


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--worker', action='store', type=int, default=1)

    def handle(self, *args, worker=1, **kwargs):
        run_rial_settlement(worker=worker)
