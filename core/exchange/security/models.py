import datetime
from typing import Optional

import requests
from django.conf import settings
from django.core.cache import cache
from django.db import models, transaction
from django.db.models import Q
from django.utils.timezone import now
from ipware import get_client_ip
from model_utils.models import SoftDeletableModel
from user_agents import parse as parse_ua

from exchange.accounts.models import Notification, User, UserRestriction, UserSms
from exchange.accounts.user_restrictions import UserRestrictionsDescription
from exchange.base.api import SemanticAPIError
from exchange.base.calendar import ir_now
from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.crypto import random_string
from exchange.base.emailmanager import EmailManager
from exchange.base.http import get_client_country
from exchange.base.logging import report_event, report_exception
from exchange.security.helpers import AddressBookNotificationType, AddressBookRestrictionType

TAG_NEEDED_NETWORKS = set()
for currency in CURRENCY_INFO:
    for network_info in CURRENCY_INFO[currency]['network_list']:
        if CURRENCY_INFO[currency]['network_list'][network_info].get('memo_required', False):
            TAG_NEEDED_NETWORKS.add(network_info)

class KnownDevice(models.Model):
    """
    A Device/Browser/App instance used by a user to access her account. Each device is identified by
    a unique DeviceID that is sent after a successful login and save in the client. If the client
    resends an already known DeviceID in future login attempts, those attempts are considered somehow
    more expected and some optional security measures like sending login notification email are
    bypassed for those attempts.

    Note: Currently last_activity field only shows the last login time from this device, and not the
           real last time this device has interacted with API.
    """
    name = models.CharField(max_length=255, blank=True)
    user = models.ForeignKey(User, related_name='known_devices', on_delete=models.CASCADE)
    device_id = models.CharField(max_length=8, unique=True)
    user_agent = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    last_activity = models.DateTimeField(db_index=True)

    class Meta:
        verbose_name = 'دستگاه کاربر'
        verbose_name_plural = verbose_name

    @classmethod
    def get_or_create(cls, attempt, device_id=None):
        known_device = None
        created = False
        user = attempt.user
        if not user:
            return None, False
        if device_id:
            known_device = user.known_devices.select_for_update().filter(device_id=device_id).first()
            if known_device and known_device.user != user:
                known_device = None
                report_event('CommonDeviceUse')
            if known_device:
                known_device.last_activity = attempt.created_at or now()
                known_device.save(update_fields=['last_activity'])
        if not known_device:
            known_device = cls.objects.create(
                name=attempt.get_device_name()[:255],
                user=user,
                device_id=random_string(8),
                user_agent=attempt.user_agent,
                last_activity=attempt.created_at or now(),
            )
            created = True
        return known_device, created


class LoginAttempt(models.Model):
    """
    Stores details of every login data attempted in the system, both for successful and unsuccessful logins.

    #TODO: Failed logins has null user field, it should be fixed for logins for known users.
    """
    user = models.ForeignKey(User, related_name='login_attempts', null=True, blank=True, on_delete=models.CASCADE)
    device = models.ForeignKey(KnownDevice, null=True, blank=True, on_delete=models.SET_NULL)
    username = models.CharField(max_length=100, blank=True, db_column='email')
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    is_successful = models.BooleanField(default=False)
    is_known = models.BooleanField(default=False)
    ip_country = models.CharField(max_length=2, default=None, null=True, blank=True)

    class Meta:
        verbose_name = 'تلاش برای ورود'
        verbose_name_plural = verbose_name

    @property
    def is_unsupported_app(self):
        """Check if this attempt is from an Android app with old version."""
        ua = self.user_agent or ''
        return ua.startswith('Android/') and ua < f'Android/{settings.LAST_SUPPORTED_ANDROID_VERSION}'

    def fill_data_from_request(self, request):
        ip = get_client_ip(request)
        self.ip = ip[0] if ip else None
        self.user_agent = (request.headers.get('user-agent') or 'unknown')[:255]
        self.ip_country = get_client_country(request)
        if self.ip_country:
            self.ip_country = self.ip_country[:2]

    def get_device_name(self):
        if self.device and self.device.name:
            return self.device.name
        if not self.user_agent:
            return 'unknown'
        if self.user_agent.startswith('Android/9'):
            return self.user_agent
        ua = parse_ua(self.user_agent)
        name = '{} {} on {}'.format(
            ua.browser.family,
            ua.browser.version_string,
            ua.os.family,
        )
        if ua.device.brand:
            name += ' ' + ua.device.brand
        return name


class UserIP(models.Model):
    """
    Stores details of every login data attempted in the system, both for successful and unsuccessful logins.
    """
    user = models.ForeignKey(User, related_name='ips', on_delete=models.CASCADE)
    ip = models.GenericIPAddressField()
    country = models.CharField(max_length=2, null=True, blank=True, help_text='نام دو حرفی کشور به حروف بزرگ')
    city = models.CharField(max_length=100, default='UN', help_text='نام شهر')
    details = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        verbose_name = 'آی‌پی کاربر'
        verbose_name_plural = verbose_name
        unique_together = ['user', 'ip']

    def update_details(self):
        geo = KnownIP.inspect_ip(self.ip)
        self.country = geo['country']
        self.city = geo['city'][:100]
        self.details = geo.get('response', {}).get('org', 'unknown')
        self.save(update_fields=['country', 'city', 'details'])

    @classmethod
    def report_user_ip(cls, user, ip):
        if not user or not ip:
            return
        for prefix in ['127.', '192.168.', '172.16.', '10.', '46.209.130.106']:
            if ip.startswith(prefix):
                return
        cls.objects.get_or_create(user=user, ip=ip)

    @classmethod
    def analyze_user(cls, user):
        from exchange.shetab.models import ShetabDeposit

        ips = set()
        successful_logins = LoginAttempt.objects.filter(
            user=user,
            is_successful=True,
        ).values('ip').distinct()
        for attempt in successful_logins:
            ips.add(attempt['ip'])
        shetab_deposits = ShetabDeposit.objects.filter(
            user=user,
        ).values('ip').distinct()
        for deposit in shetab_deposits:
            ips.add(deposit['ip'])
        for ip in ips:
            if not ip:
                continue
            cls.report_user_ip(user, ip)


class KnownIP(models.Model):
    ip_range = models.CharField(max_length=20, help_text='آی‌پی یا محدوده آی‌پی')
    range_begin = models.IntegerField(default=0, help_text='معادل عددی شروع گستره، اختیاری')
    range_end = models.IntegerField(default=0, help_text='معادل عددی پایان گستره، اختیاری')
    country = models.CharField(max_length=2, default='UN', help_text='نام دو حرفی کشور به حروف بزرگ')
    city = models.CharField(max_length=100, default='UN', help_text='نام شهر')

    class Meta:
        verbose_name = 'آدرس IP'
        verbose_name_plural = verbose_name

    @classmethod
    def query_ipapi(cls, ip):
        proxies = settings.DEFAULT_PROXY if settings.NO_INTERNET else None
        try:
            r = requests.get(
                'http://ip-api.com/json/{}'.format(ip),
                proxies=proxies,
                timeout=30,
            )
            r.raise_for_status()
            r = r.json()
        except:
            return {
                'ip': ip,
                'country': 'UN',
                'city': 'UN',
                'response': {},
            }
        return {
            'ip': ip,
            'country': r.get('countryCode') or 'UN',
            'city': r.get('city') or 'UN',
            'response': r,
        }

    @classmethod
    def query_ipinfo(cls, ip):
        proxies = settings.DEFAULT_PROXY if settings.NO_INTERNET else None
        try:
            r = requests.get(
                'https://ipinfo.io/{}?token=999892e3095ad3'.format(ip),
                proxies=proxies,
                timeout=30,
            )
            r.raise_for_status()
            r = r.json()
        except:
            return {
                'ip': ip,
                'country': 'UN',
                'city': 'UN',
                'response': {},
            }
        return {
            'ip': ip,
            'country': r.get('country') or 'UN',
            'city': r.get('city') or 'UN',
            'response': r,
        }

    @classmethod
    def inspect_ip(cls, ip):
        # Validate IP
        if not ip or len(ip) < 7:
            return {
                'ip': ip,
                'country': 'UN',
                'city': 'UN',
                'response': {},
            }
        # Local DB
        ip_parts = ip.split('.')
        ip_range = '.'.join(ip_parts[:3])
        known_ip = cls.objects.filter(ip_range=ip_range)
        if known_ip:
            return {
                'ip': ip,
                'country': known_ip[0].country,
                'city': known_ip[0].city,
                'response': {},
            }
        # Online services
        info = cls.query_ipapi(ip)
        if info['country'] != 'IR':
            info = cls.query_ipinfo(ip)
        # Normalize results
        info['city'] = info['city'].replace('ā', 'a')
        return info


class EmergencyCancelCode(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    cancel_code = models.CharField(max_length=10, db_index=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'کد لغو اضطراری برداشت'
        verbose_name_plural = verbose_name

    @classmethod
    def make_unique_cancel_code(cls):
        for _ in range(10):
            cancel_code = random_string(10)
            try:
                cls.objects.get(cancel_code=cancel_code)
            except cls.DoesNotExist:
                return cancel_code
        return None

    @classmethod
    def get_emergency_cancel_code(cls, user):
        try:
            return cls.objects.get(user=user).cancel_code
        except cls.DoesNotExist:
            return None


class IPBlackList(models.Model):
    """
        List of white and black IPs based on is_active field
    """
    CACHE_KEY = 'blacklisted_ips'

    ip = models.GenericIPAddressField(verbose_name='آی‌پی')
    description = models.TextField(blank=True, verbose_name='توضیحات')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخرین بروزرسانی')
    allocated_by = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name='پشتیبان')

    class Meta:
        verbose_name = 'لیست سیاه آی‌پی'
        verbose_name_plural = verbose_name

    @classmethod
    def contains(cls, ip):
        blacklisted_ips = cache.get(cls.CACHE_KEY)
        if blacklisted_ips is None:
            blacklisted_ips = list(cls.objects.filter(is_active=True).values_list('ip', flat=True))
            cache.set(cls.CACHE_KEY, blacklisted_ips, timeout=3600)
        return ip in blacklisted_ips


class AddressBook(models.Model):
    user = models.OneToOneField(User, related_name='address_book', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def whitelist_mode(self) -> bool:
        whitelist = self.whitelist_mode_logs.order_by('-created_at').first()
        return whitelist.is_active if whitelist is not None else False

    @classmethod
    def get(cls, user: User) -> Optional['AddressBook']:
        try:
            return cls.objects.get(user=user)
        except cls.DoesNotExist:
            return None

    @classmethod
    def create(cls, user: User, whitelist: bool = False) -> 'AddressBook':
        try:
            address_book = cls.objects.get(user=user)
        except cls.DoesNotExist:
            address_book: cls = cls.objects.create(user=user)
            address_book._change_white_list_mode(is_active=whitelist)
        return address_book

    def get_address(self, address: str, network: str, tag: str = None) -> Optional['AddressBookItem']:
        tag = self._get_refined_tag(network, tag)
        try:
            return AddressBookItem.available_objects.get(address_book=self, address=address, network=network, tag=tag)
        except AddressBookItem.DoesNotExist:
            return None

    def _add_restriction(self, restriction_type: AddressBookRestrictionType = AddressBookRestrictionType.DISABLE_WHITELIST_MODE) -> None:
        if restriction_type == AddressBookRestrictionType.DISABLE_WHITELIST_MODE:
            duration = datetime.timedelta(hours=24)
            considerations = 'ایجاد محدودیت برداشت ۲۴ ساعته به علت غیرفعال کردن حالت برداشت امن توسط کاربر'
            description = UserRestrictionsDescription.INACTIVE_SECURE_WITHDRAWAL
        else:  # add address when whitelist mode is enabled, restriction_type == AddressBookRestrictionType.NEW_ADDRESS
            duration = datetime.timedelta(hours=1)
            considerations = 'ایجاد محدودیت برداشت ۱ ساعته به علت افزودن آدرس به دفتر آدرس در حین فعال بودن حالت برداشت امن'
            description = UserRestrictionsDescription.ADD_ADDRESS_BOOK
        if AddressBookRestrictionType.has_value(restriction_type.value):
            UserRestriction.add_restriction(
                user=self.user,
                restriction=UserRestriction.RESTRICTION.WithdrawRequestCoin,
                considerations=considerations,
                duration=duration,
                description=description,
            )

    def _send_notification(
        self,
        notification_type: AddressBookNotificationType = AddressBookNotificationType.DEACTIVATED,
        address_book_item: 'AddressBookItem' = None,
    ) -> None:
        if notification_type == AddressBookNotificationType.DEACTIVATED:
            email_template = 'addressbook/deactivate_whitelist_mode'
            email_data = {}
            sms_template = UserSms.TEMPLATES.deactivate_whitelist_mode
            sms_type = UserSms.TYPES.deactivate_whitelist_mode
            sms_text = '۲۴ساعت'
            notification_message = '۲۴ ساعت محدودیت برداشت به دلیل غیرفعال‌سازی حالت برداشت امن'

        else:  # notif_type == AddressBookNotifType.NEW_ADDRESS
            email_template = 'addressbook/new_address_in_address_book'
            email_data = {
                'address_book_address': address_book_item.address,
                'address_book_tag': address_book_item.tag,
                'whitelist_mode': self.whitelist_mode if self.whitelist_mode else None
            }
            sms_template = UserSms.TEMPLATES.default
            sms_type = UserSms.TYPES.new_address_in_address_book
            sms_text = UserSms.TEXTS[sms_type]
            notification_message = 'یک آدرس به دفتر آدرس شما اضافه شد.'
            if self.whitelist_mode:
                notification_message += '\nیک ساعت محدودیت برداشت رمزارز به دلیل فعال بودن حالت برداشت امن'

        if AddressBookNotificationType.has_value(notification_type.value):
            vp = self.user.get_verification_profile()
            if self.user.mobile and vp.mobile_confirmed:
                UserSms.objects.create(
                    user=self.user,
                    tp=sms_type,
                    to=self.user.mobile,
                    template=sms_template,
                    text=sms_text,
                )
            if self.user.email and vp.email_confirmed:
                EmailManager.send_email(
                    email=self.user.email,
                    template=email_template,
                    data=email_data,
                    priority='medium',
                )
            Notification.objects.create(
                user=self.user,
                message=notification_message,
            )

    def _change_white_list_mode(self, is_active) -> 'WhiteListModeLog':
        whitelist_mode_log = WhiteListModeLog.objects.create(
            is_active=is_active,
            address_book=self,
            last_login_attempt=self.user.login_attempts.order_by('-created_at').first(),
        )
        return whitelist_mode_log

    @classmethod
    def activate_address_book(cls, user: User) -> 'AddressBook':
        address_book: AddressBook = cls.get(user=user)
        if not address_book:
            address_book: AddressBook = cls.create(user, whitelist=True)

        if address_book.whitelist_mode:
            return address_book

        address_book._change_white_list_mode(is_active=True)
        return address_book

    @classmethod
    def deactivate_address_book(cls, user: User) -> Optional['AddressBook']:
        address_book: AddressBook = cls.get(user=user)
        if not address_book:
            return None

        if not address_book.whitelist_mode:
            return address_book

        address_book._change_white_list_mode(is_active=False)

        address_book._add_restriction()
        address_book._send_notification()
        return address_book

    @classmethod
    def add_address(cls, user: User, title: str, address: str, user_agent: str, network: str,
                    ip: str = None, tag: str = None) -> 'AddressBookItem':
        address_book: AddressBook = cls.get(user)
        if not address_book:
            address_book: AddressBook = cls.create(user=user)

        tag = cls._get_refined_tag(network, tag)
        similar_addresses = AddressBookItem.available_objects.filter(
            address_book=address_book, address=address, network=network
        )
        if network in TAG_NEEDED_NETWORKS:
            similar_addresses = AddressBookItem.available_objects.filter(
                address_book=address_book, address=address, network=network, tag=tag
            )
        if similar_addresses.exists():
            raise SemanticAPIError(message="DuplicatedAddress", description="Duplicated Address!")
        with transaction.atomic():
            last_login_attempt = user.login_attempts.order_by('-created_at').first()
            address_obj = AddressBookItem.available_objects.create(
                address_book=address_book,
                title=title,
                address=address,
                tag=tag,
                agent_ip=ip,
                last_login_attempt=last_login_attempt,
                user_agent=user_agent,
                network=network,
            )
            if address_book.whitelist_mode:
                address_book._add_restriction(restriction_type=AddressBookRestrictionType.NEW_ADDRESS)
            address_book._send_notification(
                notification_type=AddressBookNotificationType.NEW_ADDRESS,
                address_book_item=address_obj,
            )
            return address_obj

    @classmethod
    def delete_address(cls, user: User, address_id: int) -> None:
        address_book: AddressBook = cls.get(user)
        if not address_book:
            return
        address = AddressBookItem.available_objects.get(pk=address_id, address_book=address_book)
        address.delete()

    @classmethod
    def is_address_ok_to_withdraw(cls, user: User, address: str, network: str, tag: str = None) -> bool:
        """
        check target address is whitelisted or not
        if whitelist mode is ON
        """
        if network == 'BTCLN':
            return True

        address_book = cls.get(user)

        if not address_book:
            return True

        if not address_book.whitelist_mode:
            return True

        tag = cls._get_refined_tag(network, tag)
        if address_book.get_address(address=address, network=network, tag=tag):
            return True

        return False

    @classmethod
    def are_2fa_and_otp_required(
        cls, user: User, address: str, network: str, tag: str = None, is_crypto_currency=True
    ) -> bool:
        if not is_crypto_currency or network == 'BTCLN':
            return True

        address_book: AddressBook = cls.get(user=user)
        if not address_book:
            return True

        if not address_book.get_address(address, network, tag):
            return True

        return False

    @classmethod
    def send_addressbook_withdraw_request_affirmation(cls, user: User):
        if user.has_verified_mobile_number:
            UserSms.objects.create(
                user=user,
                tp=UserSms.TYPES.affirm_withdraw,
                to=user.mobile,
                text=UserSms.TEXTS[UserSms.TYPES.affirm_withdraw],
            )

    @classmethod
    def _get_refined_tag(cls, network: str, tag: str) -> Optional[str]:
        # For networks without tag, we change all tags to None.
        # For networks with tag, we change None to '' and the rest remain the same
        if network not in TAG_NEEDED_NETWORKS:
            return None
        return tag or ''


class AddressBookItem(SoftDeletableModel):
    title = models.CharField(null=False, blank=False, max_length=500)
    address = models.CharField(max_length=200)
    tag = models.CharField(max_length=100, null=True, blank=True)
    agent_ip = models.GenericIPAddressField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    network = models.CharField(max_length=200)

    address_book = models.ForeignKey(AddressBook, related_name='addresses', on_delete=models.CASCADE)
    last_login_attempt = models.ForeignKey(LoginAttempt, related_name='+', on_delete=models.SET_NULL, null=True)
    user_agent = models.CharField(max_length=255, null=False, blank=False)

    def __str__(self):
        return self.title

    class Meta:
        default_manager_name = 'available_objects'
        constraints = (
            models.UniqueConstraint(
                fields=['address', 'address_book', 'network'],
                condition=Q(is_removed=False, tag=None),
                name='addrssbk_unique_if_not_deleted_no_tag'
            ),
            models.UniqueConstraint(
                fields=['address', 'address_book', 'network', 'tag'],
                condition=Q(is_removed=False, tag__isnull=False),
                name='addrssbk_unique_if_not_deleted_tag'
            ),
        )

    def delete(self, *args, **kwargs):
        self.deleted_at = ir_now()
        return super().delete(*args, **kwargs)


class WhiteListModeLog(models.Model):
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    address_book = models.ForeignKey(AddressBook, related_name='whitelist_mode_logs', on_delete=models.CASCADE)
    last_login_attempt = models.ForeignKey(LoginAttempt, related_name='+', on_delete=models.SET_NULL, null=True)
