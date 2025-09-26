import math

from django.core.management.base import BaseCommand
from tqdm import tqdm

from exchange.market.models import OrderMatching


def chunked(queryset, chunk_size=2000):
    class ChunkedQuerySet:
        def __iter__(self):
            while True:
                chunk = queryset[:chunk_size]
                if not chunk:
                    break
                yield chunk

        def __len__(self):
            return math.ceil(queryset.count() / chunk_size)

    return ChunkedQuerySet()


class Command(BaseCommand):
    """
    Examples:
        python manage.py populate_trade_fee_amounts
        python manage.py populate_trade_fee_amounts -b100 -c1000
    """
    help = 'Fills sell_fee_amount/buy_fee_amount columns of order matching table.'

    def add_arguments(self, parser):
        parser.add_argument(
            '-b', '--batch-size', default=250, type=int,
            help='Max batch of trades to be updated in each query',
        )
        parser.add_argument(
            '-c', '--chunk-size', default=10000, type=int,
            help='Max chunk of trades to be retrieved from memory -- i.e. tqdm round',
        )

    def handle(self, batch_size, chunk_size, **options):
        for side in ('sell', 'buy'):
            trades = OrderMatching.objects.filter(**{
                f'{side}_fee_amount__isnull': True,
                f'{side}_fee__isnull': False
            }).select_related(f'{side}_fee').only(f'{side}_fee__amount')

            self.stdout.write(f'[{side} fee processing]:')

            for chunk in tqdm(chunked(trades, chunk_size)):
                for trade in chunk:
                    setattr(trade, f'{side}_fee_amount', getattr(trade, f'{side}_fee').amount)
                OrderMatching.objects.bulk_update(chunk, (f'{side}_fee_amount',), batch_size)
                print(f'.', flush=True, end='')
