""" Command: run_sync_checker """
import time

from django.core.cache import cache
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        print('Syncing time to cache...')
        try:
            while True:
                cache.set('current_time', int(time.time() * 1000))
                time.sleep(0.5)
        except KeyboardInterrupt:
            print('Done.')
