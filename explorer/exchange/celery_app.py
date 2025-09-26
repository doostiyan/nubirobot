from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'exchange.settings')

app = Celery('explorer')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')
app.conf.task_create_missing_queues = True

# Auto-discover tasks from installed apps.
app.autodiscover_tasks()
app.autodiscover_tasks(['exchange.blockchain.tasks'])


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
