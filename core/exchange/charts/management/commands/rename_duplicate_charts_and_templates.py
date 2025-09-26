import math

from django.contrib.postgres.aggregates import ArrayAgg
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count
from tqdm import tqdm

from exchange.base.helpers import batcher
from exchange.charts.models import Chart, StudyTemplate


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--charts', action='store_true', default=False)
        parser.add_argument('--study-templates', action='store_true', default=False)
        parser.add_argument('--batch-size', type=int, default=1024)

    def handle(self, charts, study_templates, batch_size, **kwargs):
        if not charts and not study_templates:
            raise CommandError("At least one of --charts or --study-templates must be specified")

        self.batch_size = batch_size

        if charts:
            self.apply_changes_for_model(Chart)

        if study_templates:
            self.apply_changes_for_model(StudyTemplate)

    def apply_changes_for_model(self, model_class):
        duplicates = (
            model_class.objects.filter(user__isnull=False)
            .values('user', 'name')
            .annotate(cnt=Count('id'), ids_list=ArrayAgg('id'))
            .filter(cnt__gte=2)
        )

        id_name_mapper = {}
        for item in duplicates:
            for i, record_id in enumerate(sorted(item['ids_list'])):
                id_name_mapper[record_id] = f"{item['name']} {i+1}"

        instances = list(model_class.objects.filter(id__in=list(id_name_mapper)).defer('content'))
        for instance in instances:
            instance.name = id_name_mapper[instance.id]

        for slice in tqdm(
            batcher(instances, batch_size=self.batch_size),
            total=math.ceil(len(instances) / self.batch_size),
            unit='rows',
            unit_scale=self.batch_size,
        ):

            model_class.objects.bulk_update(slice, fields=['name'])
