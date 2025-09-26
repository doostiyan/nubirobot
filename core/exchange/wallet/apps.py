from django.apps import AppConfig


class WalletConfig(AppConfig):
    name = 'exchange.wallet'
    verbose_name = 'Wallet Management'

    def ready(self):
        from . import serializers, signals
        from .internal import serializers

