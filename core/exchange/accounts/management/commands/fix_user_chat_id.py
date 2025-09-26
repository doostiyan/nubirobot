import math
import uuid

from django.core.management.base import BaseCommand
from django.db.models import Count
from tqdm import tqdm

from exchange.accounts.models import User
from exchange.base.helpers import batcher


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', default=False)
        parser.add_argument('--batch-size', type=int, default=1024)

    def handle(self, dry_run, batch_size, **kwargs):

        round_number = 0
        while True:
            round_number += 1
            print(f'========= Round: {round_number} =========')

            non_unique_chat_ids, non_unique_chat_id_count = self.get_non_unique_chat_ids()
            print(f'number of user with non unique ids: {non_unique_chat_id_count}')
            print(f'non unique ids: {non_unique_chat_ids}')

            if not non_unique_chat_id_count or dry_run:
                return

            for non_unique_chat_id in non_unique_chat_ids:
                self.fix_non_unique_chat_id(non_unique_chat_id, batch_size)

    def get_non_unique_chat_ids(self):
        users = (
            User.objects.values('chat_id')
            .annotate(chat_id_count=Count('chat_id'))
            .filter(chat_id_count__gt=1)
            .values_list('chat_id', 'chat_id_count')
        )
        return [user_chat_id for user_chat_id, _ in users], sum(chat_id_count for _, chat_id_count in users)

    def fix_non_unique_chat_id(self, non_unique_chat_id, batch_size: int):
        print(f'non unique id is = {non_unique_chat_id}')
        users = User.objects.filter(chat_id=non_unique_chat_id).only('pk').order_by('pk')
        self.stdout.write(f'User data retrieved: {len(users)}')

        if len(users) < 2:
            return

        for user in tqdm(users[1:], desc='Assigning UUIDs'):
            user.chat_id = uuid.uuid4()

        for slice_of_charts in tqdm(
            batcher(users, batch_size=batch_size),
            total=math.ceil(len(users) / batch_size),
            unit='rows',
            unit_scale=batch_size,
            desc='Write in DB',
        ):
            User.objects.bulk_update(slice_of_charts, fields=('chat_id',))
