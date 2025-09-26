from django.apps import AppConfig


class OauthConfig(AppConfig):
    name = 'exchange.oauth'
    verbose_name = 'OAuth'

    def ready(self):
        from exchange.oauth.api import serializers
