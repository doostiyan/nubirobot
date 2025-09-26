""" Price Alert Models """
import datetime
from decimal import Decimal

from django.core.cache import cache
from django.db import models
from django.utils.timezone import now
from model_utils import Choices

from exchange.accounts.models import Notification, User, UserSms
from exchange.base.emailmanager import EmailManager
from exchange.base.models import PRICE_PRECISIONS, Currencies
from exchange.base.money import normalize
from exchange.market.models import Market


class PriceAlert(models.Model):
    """ Model for each alert set by users

        Similar sites: https://cryptocurrencyalerting.com
    """
    TYPES = Choices(
        (1, 'price', 'Price'),
        (2, 'percent', 'Percent'),
        (3, 'periodic', 'Periodic'),
    )
    CHANNELS = Choices(
        (1, 'notif', 'Notif'),
        (2, 'email', 'Email'),
        (3, 'email/notif', 'Email/Notif'),
        (4, 'sms', 'SMS'),
        (5, 'sms/notif', 'SMS/Notif'),
        (6, 'sms/email', 'SMS/Email'),
        (7, 'sms/email/notif', 'SMS/Email/Notif'),
    )

    user = models.ForeignKey(User, verbose_name='کاربر', on_delete=models.CASCADE)
    market = models.ForeignKey(Market, verbose_name='بازار', on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=now, verbose_name='تاریخ ایجاد')
    tp = models.IntegerField(choices=TYPES, db_index=True, verbose_name='نوع اعلان')
    param_direction = models.BooleanField(null=True, verbose_name='پارامتر جهت تغییر')
    param_value = models.DecimalField(max_digits=25, decimal_places=10, db_index=True, verbose_name='پارامتر قیمت')
    description = models.TextField(null=True, blank=True, verbose_name='توضیحات کاربر')
    cooldown = models.IntegerField(null=True, blank=True, verbose_name='زمان تنفس')
    channel = models.IntegerField(choices=CHANNELS, default=0, verbose_name='کانال اطلاع‌رسانی')
    last_alert = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name='آخرین اطلاع‌رسانی')

    class Meta:
        verbose_name = 'اعلان قیمت'
        verbose_name_plural = verbose_name

    @property
    def is_one_time(self):
        """Whether this alert should be deleted after being activated."""
        return self.cooldown == -1

    def get_current_market_price(self):
        """Return effective market price for related market."""
        return cache.get('market_{}_last_price'.format(self.market_id))

    def is_active(self):
        """Check if this alert should be active and notified now."""
        # Check for cooldown period
        if not self.is_one_time:
            interval = self.cooldown or 1440
            interval = datetime.timedelta(minutes=max(interval, 15))
            if self.last_alert and self.last_alert > now() - interval:
                return False
        # Price-based alerts
        if self.tp == self.TYPES.price:
            if self.param_direction is None or not self.param_value:
                return False
            market_price = self.get_current_market_price()
            if not market_price:
                return False
            delta = market_price * Decimal('0.0001')
            if self.param_direction:
                return market_price > self.param_value + delta
            return market_price < self.param_value - delta
        # Time-based alerts
        if self.tp == self.TYPES.periodic:
            return True
        # Other types are not implemented yet
        return False

    def get_text(self):
        """Return notification text for this alert."""
        market_price = self.get_current_market_price()
        param_value = self.param_value or 0
        market_symbol = self.market.symbol
        price_precision = PRICE_PRECISIONS.get(market_symbol, 2)

        user_price = normalize(param_value, price_precision)
        market_price = normalize(market_price, price_precision)

        if self.market.dst_currency == Currencies.rls:  # IRR -> IRT
            market_price /= 10
            user_price /= 10

        if self.tp == self.TYPES.price:
            return 'قیمت در بازار {} به {} از {} رسید. قیمت فعلی: {}'.format(
                market_symbol,
                'بیش' if self.param_direction else 'کمتر',
                user_price,
                market_price,
            )
        return 'قیمت در بازار {}: {}'.format(
            market_symbol,
            market_price,
        )

    def send_notification(self):
        """Send notification for this alert, assuming it is active."""
        text = self.get_text()
        if self.channel in [4, 5, 6, 7]:
            UserSms.objects.create(
                user=self.user,
                tp=UserSms.TYPES.price_alert,
                to=self.user.mobile,
                text=text,
            )
        if self.channel in [2, 3, 6, 7]:
            EmailManager.send_email(
                self.user.email,
                'template',
                data={
                    'title': 'اعلان تغییر قیمت',
                    'content': text,
                },
                priority='medium',
            )
        if self.channel in [1, 3, 5, 7]:
            Notification.objects.create(user=self.user, message=text)
        # Set last alerting time
        if self.is_one_time:
            self.delete()
        else:
            self.last_alert = now()
            self.save(update_fields=['last_alert'])
