import typing

from django.db import models
from django.http import HttpRequest
from django.conf import settings
from django.contrib import admin, messages
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from rest_framework_api_key.models import AbstractAPIKey, BaseAPIKeyManager, APIKey

from ..utils.cache import CacheUtils
from ..accounts.models import User
from ..accounts.utils.excptions import UserNotFoundException

from .utils.exceptions import APIKeyNotFoundException

APIKey.Meta.abstract = True


class UserAPIKeyManager(BaseAPIKeyManager):

    def _get_api_key_from_db(self, prefix: str):
        queryset = self.get_usable_keys()
        try:
            api_key = queryset.get(prefix=prefix)
            return api_key
        except self.model.DoesNotExist:
            raise APIKeyNotFoundException(
                _('Pass Valid API key in {} header').format(settings.API_KEY_CUSTOM_HEADER_CLIENT_FORMAT))

    def load_api_key_by_prefix(self, prefix):
        api_key = CacheUtils.read_from_local_cache(prefix, 'local__user_api_keys')
        if not api_key:
            api_key = CacheUtils.read_from_external_cache(prefix, 'redis__user_api_keys')
            if not api_key:
                api_key = self._get_api_key_from_db(prefix)
                CacheUtils.write_to_external_cache(prefix, api_key, 'redis__user_api_keys')
            CacheUtils.write_to_local_cache(prefix, api_key, 'local__user_api_keys')
        return api_key

    def get_from_key(self, key: str) -> "UserAPIKey":
        prefix, __, __ = key.partition(".")

        api_key = self.load_api_key_by_prefix(prefix)
        if not api_key.is_valid(key):
            raise APIKeyNotFoundException(
                _('Pass Valid API key in {} header').format(settings.API_KEY_CUSTOM_HEADER_CLIENT_FORMAT))
        else:
            return api_key

    def is_valid(self, api_key) -> bool:
        if api_key.has_expired or api_key.revoked:
            return False
        return True


class UserAPIKey(AbstractAPIKey):
    objects = UserAPIKeyManager()
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_api_keys')
    rate = models.CharField(max_length=20)

    def save(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        self.full_clean()
        return super(UserAPIKey, self).save(*args, **kwargs)

    def clean(self) -> None:
        if not User.objects.filter(id=self.user_id).exists():
            raise UserNotFoundException('کاربر با شناسه {} یافت نشد'.format(self.user_id))
        if not self.rate:
            raise ValueError('The field rate is required')
        num, period = self.rate.split('/')
        if not num.isnumeric or period not in 'month, day, hour, min, sec':
            raise ValueError('The format of field rate is incorrect')
        return super().clean()

    class Meta:
        abstract = False


class UserAPIKeyAdmin(admin.ModelAdmin):
    model: typing.Type[UserAPIKey]

    list_display = (
        "user",
        "prefix",
        "name",
        "created",
        "rate",
        "expiry_date",
        "_has_expired",
        "revoked",
    )
    list_filter = ("created",)
    search_fields = ("name", "prefix")

    def get_readonly_fields(
            self, request: HttpRequest, obj: models.Model = None
    ) -> typing.Tuple[str, ...]:
        obj = typing.cast(AbstractAPIKey, obj)
        fields: typing.Tuple[str, ...]

        fields = ("prefix",)
        if obj is not None and obj.revoked:
            fields += "name", "revoked", "expiry_date"

        return fields

    def save_model(
            self,
            request: HttpRequest,
            obj: AbstractAPIKey,
            form: typing.Any = None,
            change: bool = False,
    ) -> None:
        created = not obj.pk

        if created:
            key = self.model.objects.assign_key(obj)
            obj.save()
            message = (
                    "The API key for {} is: {}. ".format(obj.name, key)
                    + "Please store it somewhere safe: "
                    + "you will not be able to see it again."
            )
            messages.add_message(request, messages.WARNING, message)
        else:
            obj.save()


admin.site.register(UserAPIKey, UserAPIKeyAdmin)


class Call(models.Model):
    network = models.CharField(max_length=10)
    api = models.CharField(max_length=20)
    called_at = models.DateTimeField(default=timezone.now)

