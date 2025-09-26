from typing import List

from django.db import models
from oauth2_provider.models import (
    AbstractAccessToken,
    AbstractApplication,
    AbstractGrant,
    AbstractRefreshToken,
    ApplicationManager,
)

from exchange.oauth.constants import Scopes

# IMPORTANT NOTE:
# When referencing any of these models by ForeignKeys or so on, try to refer to them directly instead of the format
#     'oauth2_settings.SOME_OAUTH_TOOLKIT_MODEL' that the oauth provider toolkit does.
#     Doing so might cause migration problems due to lazy references and create incomplete migration files.


class Application(AbstractApplication):
    objects = ApplicationManager()

    scope = models.TextField(null=True)  # allowed scopes separated by space, e.g. 'profile-info user-info wallet'
    acceptable_ip = models.GenericIPAddressField(null=True, blank=True, unique=True)

    class Meta(AbstractApplication.Meta):
        abstract = False
        verbose_name = 'اپلیکیشن'
        verbose_name_plural = 'اپلیکیشن‌ها'

    @property
    def natural_key(self):
        return self.client_id

    def has_scope(self, scope: str) -> bool:
        return scope in Scopes.get_all() and scope in self.scope.split()

    def get_common_scopes(self, scopes: str) -> List[str]:
        """
        If scopes is given, returns a subset of them that lie within the application's scopes.
        Otherwise, it returns the app's scopes.
        Args:
            scopes: a string of scopes separated by ' ', e.g. 'profile-info user-info wallet'
        Returns:
            a list of strings including any scope from received scopes within the app's scopes
        """
        if not scopes:
            return []
        scopes_list = set(scopes.split())
        return [scope for scope in scopes_list if self.has_scope(scope)]

    def allow_scopes(self, scopes: str) -> bool:
        """
        Check if the application is allowed to input scopes
        Args:
            scopes: a string of scopes separated by ' ', e.g. 'profile-info user-info'
        Returns:
            True if application is allowed all input scopes otherwise return False
        """
        if not scopes:
            return True
        if not self.scope:
            return False

        provided_scopes = set(self.scope.split())
        resource_scopes = set(scopes.split())

        return resource_scopes.issubset(provided_scopes)

    def accepts_ip(self, ip: str) -> bool:
        if not self.acceptable_ip:
            return True
        return ip == self.acceptable_ip


class Grant(AbstractGrant):
    application = models.ForeignKey(Application, on_delete=models.CASCADE)

    class Meta(AbstractGrant.Meta):
        abstract = False
        verbose_name = 'مجوز'
        verbose_name_plural = 'مجوزها'


class AccessToken(AbstractAccessToken):
    id_token = None
    application = models.ForeignKey(Application, on_delete=models.CASCADE, blank=True, null=True)
    source_refresh_token = models.OneToOneField(
        # unique=True implied by the OneToOneField
        'RefreshToken',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='refreshed_access_token',
    )

    class Meta(AbstractAccessToken.Meta):
        abstract = False
        verbose_name = 'توکن دسترسی'
        verbose_name_plural = 'توکن‌های دسترسی'

    def __init__(self, *args, **kwargs):
        # Django Oauth Toolkit passes `id_token` param to initializer with `None` value on token api tests
        self.id_token = kwargs.pop('id_token', None)
        super().__init__(*args, **kwargs)


class RefreshToken(AbstractRefreshToken):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, blank=True, null=True)
    access_token = models.OneToOneField(
        AccessToken,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='refresh_token',
    )

    class Meta(AbstractRefreshToken.Meta):
        abstract = False
        verbose_name = 'توکن بازیابی'
        verbose_name_plural = 'توکن‌های بازیابی'
