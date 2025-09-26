from django.conf import settings
from django.core.management.base import BaseCommand

from exchange.accounts.models import Notification


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        Notification.notify_admins(
            'Env: {}\nVersion: {}-{}'.format(
                settings.ENV,
                settings.RELEASE_VERSION,
                settings.CURRENT_COMMIT,
            ),
            title='Deployed Backend',
            channel='updates-tech',
        )
