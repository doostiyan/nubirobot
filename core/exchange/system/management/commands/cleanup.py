import datetime

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils.timezone import now
from post_office.models import Email, Log as EmailSendingLog

from exchange.base.models import Log
from exchange.accounts.models import Notification, UserOTP
from exchange.security.models import LoginAttempt


class Command(BaseCommand):
    """ Remove old DB rows that are not used anymore and can be safely deleted
    """

    def handle(self, *args, **kwargs):
        nw = now()
        date_1h = nw - datetime.timedelta(hours=1)
        date_1d = nw - datetime.timedelta(days=1)
        date_3d = nw - datetime.timedelta(days=3)
        date_1w = nw - datetime.timedelta(days=7)
        date_2w = nw - datetime.timedelta(days=14)
        date_2y = nw - datetime.timedelta(weeks=104)
        print('Clearing old sessions...')
        call_command('clearsessions')
        print('Removing email logs...')
        EmailSendingLog.objects.filter(date__lt=date_1h).delete()
        print('Removing old emails...')
        Email.objects.filter(created__lt=date_1d).filter(
            Q(scheduled_time__isnull=True) | Q(scheduled_time__lt=date_1d)
        ).delete()
        print('Removing old system logs...')
        settlement_history = Q(category=Log.CATEGORY_CHOICES.history, module=Log.MODULE_CHOICES.settlement)
        Log.objects.filter(created_at__lt=date_3d).exclude(settlement_history).delete()
        Log.objects.filter(Q(created_at__lt=date_1w) & settlement_history).delete()
        print('Removing old failed login attempts...')
        LoginAttempt.objects.filter(is_successful=False, created_at__lt=date_2w).delete()
        LoginAttempt.objects.filter(is_successful=True, created_at__lt=date_2y).delete()
        print('Removing old notifications...')
        Notification.objects.filter(created_at__lt=date_2w).delete()
        print('Removing old OTPs...')
        UserOTP.objects.filter(created_at__lt=date_2w).delete()
