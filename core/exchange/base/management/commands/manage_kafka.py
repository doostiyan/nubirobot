from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from exchange.broker.broker.kafka_management import KAFKA_DEFAULT_TOPIC_CONFIGS, apply_kafka_configs
from exchange.kafka_configs import KAFKA_TOPICS


class Command(BaseCommand):
    """
    Django management command to apply Kafka configurations.

    Applies configurations for all topics or a specific topic if provided.
    """

    help = 'Apply Kafka configurations'

    def add_arguments(self, parser):
        parser.add_argument('--topic', type=str, help='Specify a single topic to configure (optional)', required=False)

    def handle(self, *args, **options):
        topic = options['topic']

        if topic:
            if topic not in KAFKA_TOPICS:
                raise CommandError(f'Topic \'{topic}\' not found in configuration')
            topics_config = {topic: KAFKA_TOPICS[topic]}
        else:
            topics_config = KAFKA_TOPICS

        kafka_config = settings.KAFKA_CONFIG
        default_topic_config = KAFKA_DEFAULT_TOPIC_CONFIGS

        results = apply_kafka_configs(
            topics_config,
            kafka_config=kafka_config,
            default_topic_config=default_topic_config,
        )

        for topic, success in results.items():
            if success:
                self.stdout.write(self.style.SUCCESS(f'Successfully configured topic: {topic}'))
            else:
                self.stdout.write(self.style.ERROR(f'Failed to configure topic: {topic}'))

        if not all(results.values()):
            exit(1)

