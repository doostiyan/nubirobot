from typing import Dict

from django.conf import settings

from exchange.broker.broker.kafka_management import KafkaTopicType

KAFKA_TOPICS: Dict[str, KafkaTopicType] = {
    'admin_telegram_notification': {
        'num_partitions': 10,
        'replication_factor': 2,
        'config': {
            'retention.ms': 172800000,  # 2 days
            'cleanup.policy': 'delete',
        },
    },
    'email': {
        'num_partitions': 10,
        'replication_factor': 2,
        'config': {
            'retention.ms': 172800000,  # 2 days
            'cleanup.policy': 'delete',
        },
    },
    'fast_sms': {
        'num_partitions': 10,
        'replication_factor': 2,
        'config': {
            'retention.ms': 172800000,  # 2 days
            'cleanup.policy': 'delete',
        },
    },
    'fast_telegram_notification': {
        'num_partitions': 10,
        'replication_factor': 2,
        'config': {
            'retention.ms': 172800000,  # 2 days
            'cleanup.policy': 'delete',
        },
    },
    'health-check-topic': {
        'num_partitions': 5,
        'replication_factor': 2,
        'config': {
            'retention.ms': 600000,  # 10 minutes
            'cleanup.policy': 'delete',
        },
    },
    'metric': {
        'num_partitions': 10,
        'replication_factor': 2,
        'config': {
            'retention.ms': 86400000 if settings.IS_PROD else 3600000,  # 1 day for prod, 1h for testnet
            'cleanup.policy': 'delete',
        },
    },
    'notification': {
        'num_partitions': 10,
        'replication_factor': 2,
        'config': {
            'retention.ms': 172800000,  # 2 days
            'cleanup.policy': 'delete',
        },
    },
    'sms': {
        'num_partitions': 10,
        'replication_factor': 2,
        'config': {
            'retention.ms': 172800000,  # 2 days
            'cleanup.policy': 'delete',
        },
    },
    'telegram_notification': {
        'num_partitions': 10,
        'replication_factor': 2,
        'config': {
            'retention.ms': 172800000,  # 2 days
            'cleanup.policy': 'delete',
        },
    },
}
