from django.apps import AppConfig


class PoolConfig(AppConfig):
    name = 'exchange.pool'
    verbose_name = 'مشارکت'

    def ready(self):
        from exchange.pool import serializers, signals
