import datetime
import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.timezone import now

from exchange.accounts.models import Notification
from exchange.fcm.fcm_handler import send_batch_fcm_notifications
from exchange.notification.switches import NotificationConfig


class Command(BaseCommand):
    help = 'Sends FCM messages'

    def add_arguments(self, parser):
        parser.add_argument('--batch_count', nargs='?', default=100, type=int, help='Number of messages in each batch')
        parser.add_argument('--delay_time', nargs='?', default=5 if settings.IS_PROD else 10, type=int,
                            help='Time to delay between each cycle')
        parser.add_argument('--start_id', nargs='?', type=int, help='ID of notification to start from')

    def handle(self, *args, **options):
        start_date = now() - datetime.timedelta(minutes=30)
        start_id = options['start_id']
        if not start_id:
            first_notif = Notification.objects.order_by('id').filter(
                created_at__gte=start_date,
                sent_to_fcm=False,
            ).first()
            start_id = first_notif.id if first_notif else 0

        while True:
            if NotificationConfig.is_notification_broker_enabled():
                self.stdout.write(
                    self.style.SUCCESS('Notification broker is active, Sending Notifications here is disabled.')
                )
                time.sleep(options['delay_time'])
                continue
            try:
                notifications = Notification.objects.order_by('id').filter(
                    id__gte=start_id,
                    created_at__gte=start_date,
                    sent_to_fcm=False,
                )[:options['batch_count']]
                print('Sending {} notifications from #{}...'.format(len(notifications), start_id))
                start_id = send_batch_fcm_notifications(notifications) or start_id
                self.stdout.write(self.style.SUCCESS('Sent.'))
                time.sleep(options['delay_time'])
            except KeyboardInterrupt:
                break
        self.stdout.write(self.style.SUCCESS('Done.'))
