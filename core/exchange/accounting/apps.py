from django.apps import AppConfig


class AccountingConfig(AppConfig):
    name = 'exchange.accounting'
    verbose_name = 'حسابداری'

    def ready(self):
        from . import serializers
