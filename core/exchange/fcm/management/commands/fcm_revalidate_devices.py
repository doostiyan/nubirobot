from django.core.management.base import BaseCommand
from firebase_admin.messaging import UnregisteredError
from tqdm import tqdm

from exchange.base.connections import get_fcm
from exchange.base.logging import metric_incr
from exchange.fcm.models import FCMDevice


class Command(BaseCommand):
    help = 'Import FCM device IDs sent saved in user preferences'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.include_inactive = False
        self.delete_stale = False
        self.inactive_count = 0
        self.delete_count = 0

    def add_arguments(self, parser):
        parser.add_argument('--include-inactive', action='store_true', help='Also reprocess already inactive devices')
        parser.add_argument('--delete-stale', action='store_true',
                            help='Delete inactive devices that still have an error.')

    def process_messages(self, messages):
        fcm = get_fcm()
        invalid_devices = []
        result = fcm.send_each(messages)
        success_count = 0
        for i, response in enumerate(result.responses):
            message = messages[i]
            if response.success:
                success_count += 1
                if self.include_inactive and not message.device.is_active:
                    message.device.is_active = True
                    message.save(update_fields=['is_active'])
            elif isinstance(response.exception, UnregisteredError):
                if self.include_inactive and self.delete_stale and not message.device.is_active:
                    message.device.delete()
                else:
                    invalid_devices.append(message.device.id)
        metric_incr('metric_fcm_send', amount=success_count, labels=('successful',))
        metric_incr('metric_fcm_send', amount=len(result.responses) - success_count, labels=('failed',))
        FCMDevice.objects.filter(id__in=invalid_devices).update(is_active=False)
        self.inactive_count += len(invalid_devices)

    def handle(self, *args, include_inactive=False, delete_stale=False, **options):
        self.include_inactive = include_inactive
        self.delete_stale = delete_stale
        messages = []
        devices = FCMDevice.objects.all()
        if not self.include_inactive:
            devices = devices.filter(is_active=True)
        for device in tqdm(devices):
            messages.append(device.create_notification_push())
            if len(messages) >= 100:
                self.process_messages(messages)
                messages = []
        self.process_messages(messages)
        print('Found {} invalid devices.'.format(self.inactive_count))
        if self.delete_stale:
            print('Deleted {} stale devices.'.format(self.delete_count))
