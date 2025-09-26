"""Staking App Config"""
from django.apps import AppConfig


class StakingConfig(AppConfig):
    name = 'exchange.staking'

    def ready(self):
        from . import serializers  # pylint: disable=unused-import,import-outside-toplevel
        from . import signals  # pylint: disable=unused-import,import-outside-toplevel
