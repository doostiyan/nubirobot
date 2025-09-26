from django.core.management.base import BaseCommand

from exchange.base.models import parse_market_symbol
from exchange.xchange.models import MarketStatus


class Command(BaseCommand):
    help = 'Delete rows in MarketStatus model where status is delisted or a specific pair'

    def add_arguments(self, parser):
        parser.add_argument(
            '--pair',
            type=str,
            help='Specify a pair to delete regardless of its state (format: BTCUSDT, USDTIRT, etc.)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force delete the specified pair regardless of its status',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Delete all delisted markets',
        )

    def handle(self, *args, **kwargs):
        pair = kwargs.get('pair')
        delete_all = kwargs.get('all')

        if pair and delete_all:
            self.stdout.write(self.style.ERROR('You cannot use --pair and --all together.'))
            return

        if delete_all:
            count, _ = MarketStatus.objects.filter(status=MarketStatus.STATUS_CHOICES.delisted).delete()
            self.stdout.write(self.style.SUCCESS(f'Successfully deleted {count} delisted market(s)'))
        elif pair:
            base_currency, quote_currency = parse_market_symbol(pair)
            specific_market = MarketStatus.objects.filter(
                base_currency=base_currency,
                quote_currency=quote_currency,
            ).first()

            if not specific_market:
                self.stdout.write(self.style.ERROR(f'No market found for pair {pair}'))
                return

            force = kwargs.get('force')
            if not force and specific_market.status != MarketStatus.STATUS_CHOICES.delisted:
                self.stdout.write(
                    self.style.ERROR(
                        f'Market for pair {pair} is not in delisted status. Use --force to delete anyway.',
                    ),
                )
                return

            specific_market.delete()
            self.stdout.write(self.style.SUCCESS(f'Successfully deleted market for pair {pair}'))
        else:
            self.stdout.write(self.style.ERROR('You must specify either --pair or --all.'))
