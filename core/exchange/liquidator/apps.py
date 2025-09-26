from django.apps import AppConfig


class LiquidatorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'exchange.liquidator'
    verbose_name = 'Liquidator App'

    def ready(self):
        from . import signals
