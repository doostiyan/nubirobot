import datetime
import hashlib
import logging
import random
import time

from django.db import connection, models
from django.utils import timezone
from django.utils.encoding import smart_str

from exchange.base.models import Settings
from exchange.captcha.conf import settings as captcha_settings
from exchange.captcha.tasks import task_create_captcha_pool

# Heavily based on session key generation in Django
# Use the system (hardware-based) random number generator if it exists.
randrange = random.SystemRandom().randrange if hasattr(random, 'SystemRandom') else random.randrange
MAX_RANDOM_KEY = 18446744073709551616  # 2 << 63

logger = logging.getLogger(__name__)


class CaptchaStoreManager(models.Manager):
    def sample(self, minimum_expiration: str, sample_rate=5):
        # Raw SQL query using TABLESAMPLE for random sampling
        cursor = connection.cursor()
        cursor.execute(
            f'''
            SELECT hashkey FROM {self.model._meta.db_table}
            TABLESAMPLE BERNOULLI(%s)
            WHERE expiration > %s
            ORDER BY RANDOM() DESC
            LIMIT 1;
            ''',
            [sample_rate, minimum_expiration],
        )
        return cursor.fetchone()


class CaptchaStore(models.Model):
    id = models.AutoField(primary_key=True)
    challenge = models.CharField(blank=False, max_length=32)
    response = models.CharField(blank=False, max_length=32)
    hashkey = models.CharField(blank=False, max_length=40, unique=True)
    expiration = models.DateTimeField(blank=False)

    objects = CaptchaStoreManager()

    def save(self, *args, **kwargs):
        self.response = self.response.lower()
        if not self.expiration:
            self.expiration = timezone.now() + datetime.timedelta(minutes=int(captcha_settings.get_timeout()))
        if not self.hashkey:
            key_ = (
                smart_str(randrange(0, MAX_RANDOM_KEY))
                + smart_str(time.time())
                + smart_str(self.challenge, errors='ignore')
                + smart_str(self.response, errors='ignore')
            ).encode('utf8')
            self.hashkey = hashlib.sha1(key_).hexdigest()
            del key_
        super().save(*args, **kwargs)

    def __str__(self):
        return self.challenge

    @classmethod
    def remove_expired(cls):
        cls.objects.filter(expiration__lte=timezone.now()).delete()

    @classmethod
    def generate_key(cls, generator=None):
        challenge, response = captcha_settings.get_challenge(generator)()
        store = cls.objects.create(challenge=challenge, response=response)
        return store.hashkey

    @classmethod
    def pick(cls, method: str = 'random_order', sample_rate=1):
        if not captcha_settings.CAPTCHA_GET_FROM_POOL:
            return cls.generate_key()

        def fallback():
            logger.error("Couldn't get a captcha from pool, generating")
            task_create_captcha_pool.apply_async()
            return cls.generate_key()

        # Pick up a random item from pool
        minimum_expiration = timezone.now() + datetime.timedelta(
            minutes=int(captcha_settings.CAPTCHA_GET_FROM_POOL_TIMEOUT),
        )

        if method == 'tablesample':
            store = cls.objects.sample(minimum_expiration=minimum_expiration, sample_rate=sample_rate)
            return (store and store[0]) or fallback()
        else:
            store = cls.objects.filter(expiration__gt=minimum_expiration).order_by('?').values('hashkey').first()
            return (store and store['hashkey']) or fallback()

    @classmethod
    def create_pool(cls, count=1000):
        assert count > 0
        while count > 0:
            cls.generate_key()
            count -= 1
