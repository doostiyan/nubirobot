from django.apps import AppConfig


class AuthenticationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'exchange.explorer.authentication'

    def ready(self):
        from django.contrib import admin
        from rest_framework_api_key.models import APIKey

        admin.site.unregister(APIKey)
