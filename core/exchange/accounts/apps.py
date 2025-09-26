from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = 'exchange.accounts'
    verbose_name = 'حساب‌ها'

    def ready(self):
        from . import serializers
        from . import signals
        from .custom_signals import handlers
