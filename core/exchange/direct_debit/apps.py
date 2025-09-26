from django.apps import AppConfig


class DirectDebitConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'exchange.direct_debit'

    def ready(self):
        from .api import serializers
