import math

from django.core.management.base import BaseCommand
from tqdm import tqdm

from exchange.accounts.models import User
from exchange.base.helpers import batcher
from exchange.charts.models import StudyTemplate
from exchange.charts.utils import is_valid_uuid

EXCLUDED_OWNER_ID = 'aee968bae9fc49eab103cde3fa2b5b18'


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', default=False)
        parser.add_argument('--delete-empty-users', action='store_true', default=False)
        parser.add_argument('--batch-size', type=int, default=1024)

    def handle(self, dry_run, delete_empty_users, batch_size, **kwargs):
        if delete_empty_users:
            return self.delete_userless_study_templates()

        study_templates = StudyTemplate.objects.filter(user__isnull=True).defer('content')
        all_owner_ids = [study_template.ownerId for study_template in study_templates]
        self.stdout.write(f'Study templates retrieved - count: {len(study_templates)}')

        numeric_ids, chat_ids = self.separate_numeric_ids_and_chat_ids(all_owner_ids)
        user_ids = self.retrieve_valid_numeral_user_ids(numeric_ids)
        chat_id_to_user_id_mapper = self.retrieve_chat_id_to_user_id_mapper(chat_ids)
        self.stdout.write('User data retrieved')

        updated_templates = []
        updated_by_chat_id = 0
        for i, study_template in enumerate(study_templates):
            if i % 200 == 0:
                self.stdout.write(f'Processing study template No. {i} with id: {study_template.pk}')

            owner_id = study_template.ownerId

            if owner_id.isnumeric():
                user_id = int(owner_id)
                if user_id not in user_ids:
                    continue
                study_template.user_id = user_id
                updated_templates.append(study_template)

            else:
                user_id = chat_id_to_user_id_mapper.get(owner_id)
                if not user_id:
                    continue
                study_template.user_id = user_id
                updated_templates.append(study_template)
                updated_by_chat_id += 1

        total_count = len(updated_templates)

        self.stdout.write(
            f'{total_count} rows will be updated - '
            f'{updated_by_chat_id} by chat_id - '
            f'{total_count - updated_by_chat_id} by user_id'
        )

        if dry_run:
            return None

        for slice_of_charts in tqdm(
            batcher(updated_templates, batch_size=batch_size),
            total=math.ceil(total_count / batch_size),
            unit='rows',
            unit_scale=batch_size,
        ):
            StudyTemplate.objects.bulk_update(slice_of_charts, fields=['user_id'])

    def separate_numeric_ids_and_chat_ids(self, owner_ids):
        numeric_ids = []
        chat_ids = []
        for owner_id in owner_ids:
            if owner_id.isnumeric():
                numeric_ids.append(owner_id)
            elif is_valid_uuid(owner_id):
                chat_ids.append(owner_id)

        return numeric_ids, chat_ids

    def retrieve_valid_numeral_user_ids(self, numeric_ids) -> set:
        users = set(User.objects.filter(pk__in=numeric_ids).values_list('pk', flat=True))
        return users

    def retrieve_chat_id_to_user_id_mapper(self, chat_ids) -> dict:
        users = User.objects.filter(chat_id__in=chat_ids).values('pk', 'chat_id')
        mapper = {}
        for user_data in users:
            mapper[str(user_data['chat_id']).replace('-', '')] = user_data['pk']

        if EXCLUDED_OWNER_ID in mapper:
            del mapper[EXCLUDED_OWNER_ID]

        return mapper

    def delete_userless_study_templates(self):
        qs = StudyTemplate.objects.filter(user__isnull=True).exclude(ownerId=EXCLUDED_OWNER_ID)
        self.stdout.write(f'start to clear templates without owner, count:{qs.count()}')

        deleted, _rows_count = qs.delete()
        self.stdout.write(f'deleted {deleted} records')
