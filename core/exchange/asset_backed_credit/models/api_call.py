from typing import Dict
from uuid import uuid4

from django.db import models
from django.db.models import JSONField
from model_utils import Choices

from exchange.accounts.models import User
from exchange.asset_backed_credit.models.service import Service
from exchange.asset_backed_credit.models.user import InternalUser
from exchange.asset_backed_credit.models.user_service import UserService
from exchange.base.calendar import ir_now


class APICallLog(models.Model):
    STATUS = Choices(
        (0, 'success', 'success'),
        (1, 'failure', 'failure'),
    )
    created_at = models.DateTimeField(default=ir_now, verbose_name='زمان ایجاد')
    api_url = models.CharField(max_length=255)
    request_body = JSONField(blank=True, null=True)
    response_body = JSONField(blank=True, null=True)
    response_code = models.SmallIntegerField(verbose_name='کد پاسخ')
    status = models.SmallIntegerField(verbose_name='وضعیت', choices=STATUS)
    provider = models.SmallIntegerField(null=True, verbose_name='ارائه دهنده', choices=Service.PROVIDERS)
    service = models.SmallIntegerField(null=True, verbose_name='سرویس', choices=Service.TYPES)
    user_service = models.ForeignKey(
        UserService,
        on_delete=models.CASCADE,
        verbose_name='سرویس اعتباری کاربر',
        null=True,
    )
    user = models.ForeignKey(User, on_delete=models.PROTECT, null=True, verbose_name='کاربر')
    internal_user = models.ForeignKey(
        InternalUser,
        on_delete=models.PROTECT,
        verbose_name='کاربر',
        null=True,
        blank=True,
    )

    class Meta:
        abstract = True


class OutgoingAPICallLog(APICallLog):
    retry = models.SmallIntegerField(verbose_name='تکرار فراخوانی', default=0)

    class Meta:
        verbose_name = 'لاگ صدا کردن سرویس دهنده‌های ثالث'
        verbose_name_plural = 'لاگ‌های صدا کردن سرویس دهنده‌های ثالث'


class IncomingAPICallLog(APICallLog):
    uid = models.UUIDField(editable=False, blank=True, null=True, unique=True)

    class Meta:
        verbose_name = 'لاگ صدا شدن توسط سرویس دهنده‌های ثالث'
        verbose_name_plural = 'لاگ‌های صدا شدن توسط سرویس دهنده‌های ثالث'

    @classmethod
    def create(
        cls,
        api_url: str,
        user: User,
        internal_user: InternalUser,
        service: int,
        response_code: int,
        provider: int,
        status: int = None,
        uid: uuid4 = None,
        request_body: Dict = None,
        response_body: Dict = None,
        user_service: UserService = None,
    ):
        """Create log for incoming requests from providers"""

        status = status or (cls.STATUS.success if response_code == 200 else cls.STATUS.failure)
        return cls.objects.create(
            uid=uid,
            user=user,
            internal_user=internal_user,
            api_url=api_url,
            request_body=request_body,
            response_body=response_body,
            response_code=response_code,
            status=status,
            provider=provider,
            service=service,
            user_service=user_service,
        )
