from django.apps.config import AppConfig
from django.utils.translation import gettext_lazy as _


class CoreConfig(AppConfig):
    name = 'exchange.explorer.core'
    app_label = 'core'
    verbose_name = _('Core')
    verbose_name_plural = _('Core')
