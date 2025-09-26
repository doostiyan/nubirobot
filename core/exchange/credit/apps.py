from django.apps import AppConfig


class CreditConfig(AppConfig):
    name = 'exchange.credit'

    def ready(self):
        from . import serializers  # pylint: disable=unused-import,import-outside-toplevel
