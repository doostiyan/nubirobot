from typing import List

from django.core.management.base import BaseCommand

from exchange.base.consumer import ConsumerRegistry
from exchange.broker.broker.client.consumer import EventConsumerMultiProcess


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '-s',
            '--scopes',
            type=str,
            nargs='?',
            help='Consumer scopes to run, separated by ,',
        )

    def handle(self, *args, **kwargs):
        consumers: List[EventConsumerMultiProcess] = []

        scopes = kwargs.get('scopes')
        scopes = ConsumerRegistry.consumer_blueprints.keys() if not scopes else scopes.split(',')

        for scope in scopes:
            for consumer_blueprint in ConsumerRegistry.consumer_blueprints[scope]:
                consumer = EventConsumerMultiProcess(
                    consumer_blueprint.config,
                    consumer_blueprint.group_id,
                    auto_ack=consumer_blueprint.auto_ack,
                )
                for i in range(consumer_blueprint.num_processes):
                    print(f'Starting: {consumer_blueprint}, Process #{i + 1}')
                    consumer.consume(
                        topic=consumer_blueprint.topic,
                        callback=consumer_blueprint.callback,
                        poll_rate=consumer_blueprint.poll_rate,
                        schema=consumer_blueprint.schema,
                        on_error_callback=consumer_blueprint.on_error_callback,
                    )
                    consumers.append(consumer)

        for consumer in consumers:
            consumer.wait_to_consume()
