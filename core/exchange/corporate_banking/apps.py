from django.apps import AppConfig


class CorporateBankingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'exchange.corporate_banking'
    verbose_name = 'Corporate Banking App'

    def ready(self):
        from .api import serializers
