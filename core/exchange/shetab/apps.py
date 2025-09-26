from django.apps import AppConfig


class ShetabConfig(AppConfig):
    name = 'exchange.shetab'
    verbose_name = 'درگاه شتاب'

    def ready(self):
        from . import serializers
        from . import signals
