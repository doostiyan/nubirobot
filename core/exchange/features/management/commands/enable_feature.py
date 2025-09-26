from django.core.management import BaseCommand
from tqdm import tqdm

from exchange.features.models import QueueItem


class Command(BaseCommand):
    help = 'Activate a feature for the top users of the request queue.'

    def add_arguments(self, parser):
        parser.add_argument('feature', help='Name of the feature to be enabled')
        parser.add_argument('count', type=int, help='Number of users to enable this feature for')

    def handle(self, feature, count, *args, **kwargs):
        skip_count = 0
        enabled_count = 0
        feature_key = getattr(QueueItem.FEATURES, feature)
        items = QueueItem.objects.dequeue(feature=feature_key, count=count)
        for item in tqdm(items):
            enabled = item.enable_feature() if item.is_eligible_to_enable() else False
            if enabled:
                enabled_count += 1
            else:
                skip_count += 1
        self.stdout.write(
            self.style.SUCCESS(f'Successfully enabled {feature} for {enabled_count} users with {skip_count} skips.'),
        )
