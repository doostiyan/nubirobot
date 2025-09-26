from django.http import HttpResponse

from exchange.metrics.exporter import MetricManager
from exchange.metrics.helpers import monitoring_api


@monitoring_api
def metrics(request):
    data = ''
    for metric in MetricManager.metrics:
        data += f'# HELP {metric.name} {metric.description}\n'
        data += f'# TYPE {metric.name} {metric.type}\n'
        data += f'{metric.name} {metric.get_value()}\n'

    return HttpResponse(data, content_type='text/plain', status=200)
