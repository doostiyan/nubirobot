import datetime
import hashlib
import random
import time

import django
from django.core.management.base import BaseCommand
from django.utils import timezone

from exchange.base.logging import report_exception
from exchange.captcha.conf import settings as captcha_settings
from exchange.captcha.models import CaptchaStore

if django.VERSION >= (3, 0):
    from django.utils.encoding import smart_str as smart_text
else:
    from django.utils.encoding import smart_text

randrange = random.SystemRandom().randrange if hasattr(random, 'SystemRandom') else random.randrange

MAX_RANDOM_KEY = 18446744073709551616  # 2 << 63


class Command(BaseCommand):
    help = 'Create a pool of random captchas.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--pool-size',
            type=int,
            default=1000,
            help='Number of new captchas to create, default=1000',
        )
        parser.add_argument(
            '--cleanup-expired',
            action='store_true',
            default=True,
            help='Cleanup expired captchas after creating new ones',
        )
        parser.add_argument(
            '--loop',
            action='store_true',
            default=True,
            help='Loop forever',
        )

    @staticmethod
    def create_pool(count=1000):
        assert count > 0

        captcha_args = []
        while count > 0:
            challenge, response = captcha_settings.get_challenge()()
            response = response.lower()
            key_ = (
                smart_text(randrange(0, MAX_RANDOM_KEY))
                + smart_text(time.time())
                + smart_text(challenge, errors='ignore')
                + smart_text(response, errors='ignore')
            ).encode('utf8')
            hashkey = hashlib.sha1(key_).hexdigest()
            del key_

            captcha_args.append(
                CaptchaStore(
                    challenge=challenge,
                    response=response.lower(),
                    expiration=timezone.now() + datetime.timedelta(minutes=int(captcha_settings.get_timeout())),
                    hashkey=hashkey,
                ),
            )
            count -= 1

        CaptchaStore.objects.bulk_create(captcha_args, batch_size=500)

    def handle(self, **options):
        while True:
            count = options.get('pool_size')
            try:
                self.create_pool(count)
            except Exception as ex:
                self.stderr.write(str(ex))
                report_exception()

            self.stdout.write('Created %d new captchas\n' % count)
            options.get('cleanup_expired') and CaptchaStore.remove_expired()
            options.get('cleanup_expired') and self.stdout.write(
                'Expired captchas cleaned up\n',
            )
            if not options.get('loop'):
                break
            self.stdout.write('sleep for 60 seconds')
            time.sleep(60)
