from django.apps import AppConfig
from kombu import Queue


class BasisConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'exchange.explorer.basis'

    def ready(self):
        from exchange.celery_app import app
        from exchange.blockchain.apis_conf import APIS_CONF

        networks = APIS_CONF.keys()

        q_names = [f'{network}-fetch' for network in networks] + [f'{network}-insert' for network in networks]

        # Combine custom queues with the default 'celery' queue
        custom_queues = [Queue(q_name) for q_name in q_names]
        custom_queues.append(Queue('celery'))  # Ensure default queue is included

        # Assign to Celery config
        app.conf.task_queues = custom_queues

        # Optionally set the default queue (if needed)
        app.conf.task_default_queue = 'celery'