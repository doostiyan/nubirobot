import math

from django.core.management.base import BaseCommand
from django.db import connection
from django.db.models import Exists, F, IntegerField, OuterRef, Subquery, UUIDField
from django.db.models.functions import Cast
from tqdm import tqdm

from exchange.accounts.models import User
from exchange.base.helpers import batcher
from exchange.charts.models import Chart


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--batch-size', type=int, default=100)
        parser.add_argument('--dry-run', action='store_true', default=False)
        parser.add_argument('--delete-empty-users', action='store_true', default=False)

    def handle(self, batch_size, dry_run, delete_empty_users, **kwargs):

        if delete_empty_users:
            self.clear_charts_without_owner(batch_size, dry_run)
        else:
            self.fill_user_id_with_owner_id(batch_size, dry_run)
            self.fill_user_id_with_chat_id(batch_size, dry_run)

    def fill_user_id_with_owner_id(self, batch_size, dry_run):

        subquery = User.objects.filter(id=OuterRef('owner_id_int')).values('id')[:1]

        charts = (
            Chart.objects.filter(ownerId__regex=r'^\d+$')
            .annotate(owner_id_int=Cast(F('ownerId'), output_field=IntegerField()))
            .filter(Exists(subquery), user=None)
        )

        total = charts.count()

        self.stdout.write(f'start to fill user_id with owner_id, counts:{total}')

        if dry_run:
            return

        for slice_of_charts in tqdm(
            batcher(charts, batch_size=batch_size, idempotent=True),
            total=math.ceil(total / batch_size),
            unit='rows',
            unit_scale=batch_size,
        ):

            for chart in slice_of_charts:
                chart.user_id = int(chart.ownerId)

            Chart.objects.bulk_create(
                slice_of_charts,
                update_fields=('user_id',),
                update_conflicts=True,
                unique_fields=('id',),
                batch_size=batch_size,
            )


    def fill_user_id_with_chat_id(self, batch_size, dry_run):

        with connection.cursor() as cursor:
            cursor.execute(
                '''
                SELECT COUNT(c.id)
                FROM charts_chart c
                JOIN accounts_user u ON u.chat_id = c.owner_id::uuid
                WHERE c.owner_id::text ~ '^[0-9a-fA-F]{32}$' and c.user_id IS NULL and
                 c.owner_id != 'aee968bae9fc49eab103cde3fa2b5b18';
            '''
            )
            total = cursor.fetchone()[0]

        self.stdout.write(f'start to fill user_id with chat_id, counts:{total}')

        if dry_run:
            return

        success = 0
        while True:
            with connection.cursor() as cursor:
                cursor.execute(
                    '''
                    SELECT c.id, u.id as annotated_user_id
                    FROM charts_chart c
                    JOIN accounts_user u ON u.chat_id = c.owner_id::uuid
                    WHERE c.owner_id::text ~ '^[0-9a-fA-F]{32}$' and c.user_id IS NULL and
                     c.owner_id != 'aee968bae9fc49eab103cde3fa2b5b18'
                    limit %s;
                ''',
                    [batch_size],
                )

                results = cursor.fetchall()

                slice_of_charts = []
                for chart_id, user_id in results:
                    slice_of_charts.append(Chart(id=chart_id, user_id=user_id))

                Chart.objects.bulk_create(
                    slice_of_charts,
                    update_fields=('user_id',),
                    update_conflicts=True,
                    unique_fields=('id',),
                    batch_size=batch_size,
                )
                success += len(results)
                self.stdout.write(f'filled user_id with chat_id, counts: {success}/{total}')

                if len(results) < batch_size:
                    break


    def clear_charts_without_owner(self, batch_size, dry_run):
        to_be_deleted_charts = (
            Chart.objects.filter(user=None)
            .exclude(ownerId='aee968bae9fc49eab103cde3fa2b5b18')
            .values_list('id', flat=True)
        )

        total = to_be_deleted_charts.count()

        self.stdout.write(f'start to clear charts without owner, counts:{total}')

        if dry_run:
            return

        for slice_of_charts in tqdm(
            batcher(to_be_deleted_charts, batch_size=batch_size, idempotent=True),
            total=math.ceil(total / batch_size),
            unit='rows',
            unit_scale=batch_size,
        ):
            Chart.objects.filter(id__in=slice_of_charts).delete()
