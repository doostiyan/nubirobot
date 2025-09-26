import math

from django.core.management import BaseCommand
from tqdm import tqdm

from exchange.base.helpers import batcher
from exchange.liquidator.models import Liquidation, LiquidationRequestLiquidationAssociation


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

        associations = LiquidationRequestLiquidationAssociation.objects.filter(
            liquidation__status=Liquidation.STATUS.done,
            amount__isnull=True,
        ).select_related('liquidation')

        for association in associations:
            association.amount = association.liquidation.paid_amount
            association.total_price = association.liquidation.paid_total_price

        for slice_of_charts in tqdm(
            batcher(associations, batch_size=batch_size, idempotent=False),
            total=math.ceil(len(associations) / batch_size),
            unit='rows',
            unit_scale=batch_size,
        ):
            LiquidationRequestLiquidationAssociation.objects.bulk_update(
                slice_of_charts, fields=['amount', 'total_price']
            )
