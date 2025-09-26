"""How to Run:
>>> PYTHONPATH=. python tests/manual/kafka/kafka_load_test.py
"""

import os
import random
import time
from datetime import datetime

import django
from django.conf import settings
from tqdm import tqdm

from exchange.broker.broker.client.producer import EventProducer
from exchange.broker.broker.schema.notification import NotificationSchema

# Initialize Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'exchange.settings')
django.setup()

# Kafka configuration
TOPIC = 'notification'
NUM_MESSAGES_ASYNC = 1000 * 1000  # Number of messages to send
NUM_MESSAGES_SYNC = 10 * 1000

TEST_USERS_UIDS = [
    '4d96ae76-980f-4296-a303-f5778281c629',  # Delafrouz, del.mirfendereski@gmail.com
    '8f50fa71-3584-406c-a61a-b173e9e80d4a',  # Arash, fatahzade@gmail.com
    '81259ecf-e809-4707-a27b-b6e3d43ac47a',  # Ali, kafyali1377@gmail.com
    'a66afbff-b5b7-421f-939e-710fb9ce0052',  # Zahra, 	zahrafarahany21@gmail.com
]

i = -1


def generate_notif():
    global i
    i += 1
    return NotificationSchema(
        user_id=random.choice(TEST_USERS_UIDS),
        admin='',
        message=f'test {datetime.now()}: notif number {i}',
        sent_to_telegram=False,
        sent_to_fcm=False,
    )


# Kafka producer setup
def produce_messages(sync=False):
    num_messages = NUM_MESSAGES_SYNC if sync else NUM_MESSAGES_ASYNC
    producer = EventProducer(settings.KAFKA_PRODUCER_CONFIG)
    print(f'Starting to {"sync" if sync else "async"} produce {num_messages} messages to topic "{TOPIC}"')

    start_time = time.time()
    for i in tqdm(range(num_messages)):
        notif = generate_notif()
        producer.write_event(TOPIC, notif.serialize())
        if sync or i % 10000 == 0:  # Flush every 1000 messages to avoid buffer issues
            producer._kafka_producer.flush()

    producer.close()  # Ensure all messages are sent
    end_time = time.time()
    elapsed_time = end_time - start_time
    rps = num_messages / elapsed_time

    print(f'Produced {num_messages} messages in {elapsed_time:.2f} seconds. RPS: {rps:.2f}, Sync: {sync}')


# Main
if __name__ == '__main__':
    produce_messages(sync=False)
    print('\n-----------------------------------------\n')
    produce_messages(sync=True)
