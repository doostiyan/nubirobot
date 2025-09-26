from django.core.management.base import BaseCommand

from exchange.xchange.status_collector import StatusCollector


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--period',
            default=5,
            type=int,
            help='Determine calling market maker endpoint every [period] seconds.',
        )

    def handle(self, *args, **kwargs):
        StatusCollector(kwargs['period']).run()
