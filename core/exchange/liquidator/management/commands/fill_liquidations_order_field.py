import math

from django.core.management import BaseCommand
from tqdm import tqdm

from exchange.base.helpers import batcher
from exchange.liquidator.models import Liquidation
from exchange.market.models import Order


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            '-b',
            type=int,
            default=1024,
            help='Specify the batch size for processing (default: 100)',
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']

        liquidator_orders = Order.objects.filter(client_order_id__startswith='!liquidation')

        liquidation_order_mapper = {}
        for order in liquidator_orders:
            try:
                liquidation_id = int(order.client_order_id.split('!liquidation_')[-1])
            except:
                continue

            liquidation_order_mapper[liquidation_id] = order.id

        liquidations = list(
            Liquidation.objects.filter(
                pk__in=list(liquidation_order_mapper.keys()),
                order__isnull=True,
            )
        )
        for liquidation in liquidations:
            liquidation.order_id = liquidation_order_mapper.get(liquidation.id)

        for slice_of_charts in tqdm(
            batcher(liquidations, batch_size=batch_size, idempotent=False),
            total=math.ceil(len(liquidations) / batch_size),
            unit='rows',
            unit_scale=batch_size,
        ):
            Liquidation.objects.bulk_update(slice_of_charts, fields=['order_id'])
