from django.core.management.base import BaseCommand

from exchange.accounts.models import Notification


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        Notification.notify_admins('این یک پیام تستی برای اطمینان از سلامت سیستم است.', title='تست اتصال')
