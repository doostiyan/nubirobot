from django.apps import AppConfig


class GatewayConfig(AppConfig):
    name = 'exchange.gateway'
    verbose_name = 'درگاه پرداخت ارزی'

    def ready(self):
        from . import serializers
        from . import signals
