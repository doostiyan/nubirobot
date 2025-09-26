"""How to run:

0. Remove ratelimit decorator from /captcha/get-captcha-key API
1. Run the server: ./manage.py runserver --nothreading
2. Run the captcha creator command: ./manage.py runserver --nothreading
3. Let the captcha creator works for 4 min to simulate production env.
4. Run the test: PYTHONPATH=. python tests/manual/captcha/captcha_uniqueness_test.py
"""

import asyncio
import datetime
import os
import random
import statistics
import time
from collections import Counter

import aiohttp
import django
from pytz import UTC

# Initialize Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'exchange.settings')
django.setup()

from exchange.captcha.models import CaptchaStore

# Number of concurrent requests per second
REQUESTS_PER_SECOND = 50
DELETIONS_PER_SECOND = 40

# API URL
API_URL = 'http://127.0.0.1:8000/captcha/get-captcha-key'

# Counter to track the occurrence of each captcha key
key_counter = Counter()

# List to track response times for statistics (in milliseconds)
response_times = []


async def fetch_captcha_key(session):
    try:
        # Introduce random delay between 0 and 1 second before the request
        await asyncio.sleep(random.uniform(0, 0.8))

        # Track the start time of the request
        start_time = time.time()

        # Make the request
        async with session.get(API_URL) as response:
            # Parse the json response
            json_data = await response.json()
            # Calculate the response time in milliseconds
            response_time_ms = (time.time() - start_time) * 1000

            # Add the response time to the list for statistics
            response_times.append(response_time_ms)

            # Return the captcha key
            return json_data.get('captcha', {}).get('key', '')
    except Exception as e:
        print(f'Request failed: {e}')
        return ''


async def send_requests():
    async with aiohttp.ClientSession() as session:
        tasks = []
        for _ in range(REQUESTS_PER_SECOND):
            tasks.append(fetch_captcha_key(session))
        # Execute all tasks concurrently
        captcha_keys = await asyncio.gather(*tasks)

        # Update the key counter with the fetched keys
        key_counter.update(captcha_keys)


async def run_concurrent_requests():
    while True:
        await send_requests()

        # Sleep for 1 second before sending the next batch of requests
        await asyncio.sleep(1)

        # Calculate and display duplicates
        total_keys = sum(key_counter.values())
        unique_keys = len(key_counter)
        duplicates = total_keys - unique_keys

        # Calculate statistics for response times in milliseconds
        if response_times:
            avg_response_time_ms = statistics.mean(response_times)
            std_dev_response_time_ms = statistics.stdev(response_times) if len(response_times) > 1 else 0
        else:
            avg_response_time_ms = 0
            std_dev_response_time_ms = 0

        # Display statistics (time in ms)
        print(
            f'Total keys: {total_keys}, Unique keys: {unique_keys}, Duplicates: {duplicates}, Duplicates %: {round(duplicates * 100/(unique_keys+duplicates), 1)}'
        )
        print(f'Avg response time: {avg_response_time_ms:.2f}ms, Std Dev: {std_dev_response_time_ms:.2f}ms')

        await delete_random_keys()


async def delete_random_keys():
    """Delete keys randomly per second from the database."""

    minimum_expiration = datetime.datetime.now(tz=UTC) + datetime.timedelta(
        minutes=1,
    )
    keys_to_delete = CaptchaStore.objects.filter(
        expiration__gt=minimum_expiration, hashkey__in=key_counter.keys()
    ).values('hashkey')[:DELETIONS_PER_SECOND]

    # Delete keys from the database using Django ORM
    deleted_key_count, _ = await CaptchaStore.objects.filter(hashkey__in=keys_to_delete).adelete()

    # Remove these keys from the unique_keys_set

    print(f'Deleted {deleted_key_count} keys')


async def main():
    # Run both tasks concurrently: making requests and deleting keys
    await asyncio.gather(
        run_concurrent_requests(),
    )


if __name__ == '__main__':
    try:
        print('Starting concurrent requests. Press Ctrl+C to stop.')
        start_time = time.time()
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Process interrupted by user. Exiting...')
        # Final duplicate calculation and statistics before exiting
        total_keys = sum(key_counter.values())
        unique_keys = len(key_counter)
        duplicates = total_keys - unique_keys

        if response_times:
            avg_response_time_ms = statistics.mean(response_times)
            std_dev_response_time_ms = statistics.stdev(response_times) if len(response_times) > 1 else 0
        else:
            avg_response_time_ms = 0
            std_dev_response_time_ms = 0

        print(
            f'Final summary - Total keys: {total_keys}, Unique keys: {unique_keys}, Duplicates: {duplicates}, Duplicates %: {round(duplicates * 100/(unique_keys+duplicates), 1)}'
        )
        print(f'Final Avg response time: {avg_response_time_ms:.2f}ms, Std Dev: {std_dev_response_time_ms:.2f}ms')
