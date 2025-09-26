from django.apps import AppConfig


class MarginConfig(AppConfig):
    name = 'exchange.margin'
    verbose_name = 'Margin App'

    def ready(self):
        from exchange.margin import serializers, signals
