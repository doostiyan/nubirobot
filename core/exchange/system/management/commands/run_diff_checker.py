""" Command: run_checker """
from django.core.management.base import BaseCommand

from exchange.system.checker import DiffChecker


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        DiffChecker().run()
