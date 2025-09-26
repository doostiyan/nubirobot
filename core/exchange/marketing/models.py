import re
from typing import Optional

from django.db import IntegrityError, models
from django.db.models.query_utils import Q
from model_utils import Choices

from exchange.accounts.models import User
from exchange.base.api import ParseError
from exchange.base.calendar import ir_now
from exchange.base.parsers import parse_str


class Lead(models.Model):
    CALL_TYPES = Choices(
        (1, 'phone_call', 'تماس تلفنی'),
        (2, 'online_chat', 'چت آنلاین'),
        (3, 'festival', 'نمایشگاه'),
        (4, 'relative', 'ارتباط فردی'),
    )

    first_name = models.CharField(max_length=255, null=True, blank=True, verbose_name='نام')
    last_name = models.CharField(max_length=255, null=True, blank=True, verbose_name='نام خانوادگی')
    national_code = models.CharField(max_length=20, null=True, blank=True, verbose_name='کد ملی')
    phone_number = models.CharField(max_length=12, null=True, blank=True, verbose_name='شماره تلفن / موبایل')
    email = models.EmailField(null=True, blank=True, verbose_name='ایمیل')
    call_type = models.PositiveSmallIntegerField(choices=CALL_TYPES,
                                                 verbose_name='طریقه آشنایی')
    created_at = models.DateTimeField(verbose_name='زمان ایجاد', auto_now_add=True)
    modified_at = models.DateTimeField(verbose_name='زمان تغییر', auto_now=True)
    description = models.TextField(null=True, blank=True, verbose_name='توضیحات')

    def __str__(self):
        return f'مشتری هدف ({self.id})'

    class Meta:
        verbose_name = 'مشتری هدف'
        verbose_name_plural = 'مشتری‌های هدف'


class SuggestionCategory(models.Model):
    TYPES = Choices(
        (1, 'one', 'یک'),
        (2, 'two', 'دو'),
        (3, 'three', 'سه'),
        (4, 'four', 'چهار'),
        (5, 'five', 'پنج'),
    )

    priority = models.IntegerField(choices=TYPES, default=TYPES.one, verbose_name='اولویت')
    title = models.CharField(max_length=500, unique=True, verbose_name='عنوان')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'موضوع انتقادات و پیشنهادات'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.title


class Suggestion(models.Model):
    category = models.ForeignKey(SuggestionCategory, on_delete=models.PROTECT, related_name='suggestion_category', verbose_name='موضوع')
    description = models.TextField(max_length=1000, verbose_name='متن پیشنهاد')
    name = models.CharField(max_length=255, null=True, blank=True, verbose_name='نام و نام خانوادگی')
    mobile = models.CharField(max_length=12, null=True, blank=True, verbose_name='شماره موبایل')
    email = models.EmailField(max_length=50, verbose_name="ایمیل", null=True, blank=True)
    allocated_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True, verbose_name='پشتیبان')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'انتقادات و پیشنهادات'
        verbose_name_plural = verbose_name


class UTMParameter(models.Model):
    user = models.OneToOneField(User, related_name='utm_parameters', on_delete=models.CASCADE)
    source = models.CharField(max_length=255, null=True, blank=True)
    medium = models.CharField(max_length=255, null=True, blank=True)
    campaign = models.CharField(max_length=255, null=True, blank=True)
    term = models.CharField(max_length=255, null=True, blank=True)
    content = models.CharField(max_length=255, null=True, blank=True)
    utm_id = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def clean_utm_parameter(utm_parameter: str) -> Optional[str]:
        try:
            utm_parameter = re.sub(r'\s', '', parse_str(utm_parameter, True, 255))
        except ParseError:
            return None
        if re.match('^[a-zA-Z0-9_.+-]+$', utm_parameter):
            return utm_parameter
        return None

    @classmethod
    def set_user_utm_parameters(
        cls,
        user: User,
        source: Optional[str] = None,
        medium: Optional[str] = None,
        campaign: Optional[str] = None,
        term: Optional[str] = None,
        content: Optional[str] = None,
        utm_id: Optional[str] = None,
    ) -> None:
        if not user:
            return

        params = {
            'source': cls.clean_utm_parameter(source),
            'medium': cls.clean_utm_parameter(medium),
            'campaign': cls.clean_utm_parameter(campaign),
            'term': cls.clean_utm_parameter(term),
            'content': cls.clean_utm_parameter(content),
            'utm_id': cls.clean_utm_parameter(utm_id),
        }

        if not any(params.values()):
            return

        try:
            cls.objects.create(user=user, **params)
        except IntegrityError:
            return


class ExternalDiscount(models.Model):
    user = models.ForeignKey(User, related_name='external_discounts', on_delete=models.CASCADE, null=True)
    campaign_id = models.CharField(max_length=100)
    business_name = models.CharField(max_length=255)
    code = models.CharField(max_length=50)
    description = models.CharField(max_length=255, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    assigned_at = models.DateTimeField(null=True)
    enabled_at = models.DateTimeField(null=False, default=ir_now)

    class Meta:
        indexes = [
            models.Index(
                fields=['enabled_at', 'campaign_id'], name='enabled_at_campaign_id', condition=Q(user__isnull=True)
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'campaign_id'], name='unique_user_id_campaign_id', condition=Q(user__isnull=False)
            ),
            models.UniqueConstraint(fields=['code', 'campaign_id'], name='unique_code_campaign_id'),
        ]
