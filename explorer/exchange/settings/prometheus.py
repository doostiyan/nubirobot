import os

from django.conf import settings
from .main import env

metrics_dir = os.path.join(settings.BASE_DIR, 'metrics')
os.makedirs(metrics_dir, exist_ok=True)
os.environ['PROMETHEUS_MULTIPROC_DIR'] = metrics_dir

PROMETHEUS_DISABLE_CREATED_SERIES = True
PROMETHEUS_LATENCY_BUCKETS = (0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 60, 120, 300, 600, 1800, float("inf"),)
USE_PROMETHEUS_CLIENT = env.bool('USE_PROMETHEUS_CLIENT', True)
