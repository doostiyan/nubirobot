import contextlib
import importlib

from django.apps import AppConfig, apps


def import_crons_from_apps():
    for app_config in apps.get_app_configs():
        with contextlib.suppress(ModuleNotFoundError):
            # Attempt to import the crons.py module from each app
            importlib.import_module(f'{app_config.name}.crons')


class BaseConfig(AppConfig):
    name = 'exchange.base'
    verbose_name = 'تنظیمات پایه'

    def ready(self) -> None:
        from exchange.base.crons import CronJob

        import_crons_from_apps()

        CronJob.register_beat_crons()
        return super().ready()
