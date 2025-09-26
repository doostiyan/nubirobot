from django.apps import AppConfig


class AssetBackedCreditConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'exchange.asset_backed_credit'

    def ready(self):
        from . import signals
