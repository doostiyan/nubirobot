from django.apps import AppConfig


class RecoveryConfig(AppConfig):
    name = 'exchange.recovery'

    def ready(self):
        from . import serializers
