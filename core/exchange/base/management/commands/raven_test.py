from django.conf import settings
from django.core.management.base import BaseCommand
from sentry_sdk import capture_message


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        if not settings.ENABLE_SENTRY:
            return
        capture_message('SentryTest')
