""" Command: run_checker """
from django.core.management.base import BaseCommand

from exchange.system.checker import OnlineChecker


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        OnlineChecker().run()
