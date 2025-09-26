import json
import time

from django.conf import settings
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django_ratelimit.decorators import ratelimit
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from exchange.base.api import ParseError, handle_exception
from exchange.base.helpers import stage_changes
from exchange.base.parsers import parse_limited_length_string
from exchange.charts import common
from exchange.charts.models import Chart


@ratelimit(key='user_or_ip', rate='30/1m', block=True)
@api_view(['POST', 'GET', 'DELETE', 'OPTIONS'])
@permission_classes([IsAuthenticated])
@csrf_exempt
def process_request(request):
    parsed_request = common.parse_request(request, allow_empty_user_id=True)

    if parsed_request['error'] is not None:
        return parsed_request['error']

    if parsed_request['response'] is not None:
        return parsed_request['response']

    client_id = parsed_request['clientId']

    chart_id = request.GET.get('chart', '')
    symbol = request.GET.get('symbol')

    if request.method == 'GET':
        if chart_id == '':
            return get_all_user_charts(client_id, request.user.id, symbol)

        return get_chart_content(client_id, request.user.id, chart_id)

    if request.method == 'DELETE':
        if chart_id == '':
            return common.error('Wrong chart id')

        return remove_chart(client_id, request.user.id, chart_id)


    if request.method == 'POST':
        try:
            chart_name = parse_limited_length_string(request.POST.get('name'), Chart._meta.get_field('name').max_length)
        except ParseError as e:
            return handle_exception(e)
        symbol = request.POST.get('symbol')
        resolution = request.POST.get('resolution')
        content = request.POST.get('content')
        if chart_id == '':
            return save_chart(client_id, request.user.id, chart_name, symbol, resolution, content)
        return rewrite_chart(client_id, request.user.id, chart_id, chart_name, symbol, resolution, content)

    return common.error('Wrong request')


def get_all_user_charts(client_id, user_id, symbol):
    charts_list = Chart.objects.using(settings.READ_DB).defer('content').filter(ownerSource=client_id, user_id=user_id)
    if symbol:
        charts_list = charts_list.filter(symbol=symbol)
    result = [
        {
            'id': x.id,
            'name': x.name,
            'timestamp': time.mktime(x.lastModified.timetuple()),
            'symbol': x.symbol,
            'resolution': x.resolution,
        }
        for x in charts_list
    ]
    return common.response(json.dumps({'status': 'ok', 'data': result}))


def get_chart_content(client_id, user_id, chart_id):
    try:
        chart = Chart.objects.using(settings.READ_DB).get(ownerSource=client_id, user_id=user_id, id=chart_id)
    except Chart.DoesNotExist:
        return common.error('Chart not found')
    result = {
        'status': 'ok',
        'data': {
            'id': chart.id,
            'name': chart.name,
            'timestamp': time.mktime(chart.lastModified.timetuple()),
            'content': chart.content,
        },
    }
    return common.response(json.dumps(result))


def remove_chart(client_id, user_id, chart_id):
    try:
        chart = Chart.objects.using(settings.READ_DB).get(ownerSource=client_id, user_id=user_id, id=chart_id)
    except Chart.DoesNotExist:
        return common.error('Chart not found')

    chart.delete(using=settings.WRITE_DB)
    return common.response(json.dumps({'status': 'ok'}))


def save_chart(client_id, user_id, chart_name, symbol, resolution, content):
    new_chart = Chart(
        ownerSource=client_id,
        ownerId=user_id,
        user_id=user_id,
        name=chart_name,
        content=content,
        lastModified=timezone.now(),
        symbol=symbol,
        resolution=resolution,
    )
    new_chart.save()
    return common.response(json.dumps({'status': 'ok', 'id': new_chart.id}))


def rewrite_chart(client_id, user_id, chart_id, chart_name, symbol, resolution, content):
    try:
        chart = Chart.objects.using(settings.READ_DB).get(ownerSource=client_id, user_id=user_id, id=chart_id)
    except Chart.DoesNotExist:
        return common.error('Chart not found')

    with stage_changes(chart, update_fields=['content', 'name', 'symbol', 'resolution']):
        chart.content = content
        chart.name = chart_name
        chart.symbol = symbol
        chart.resolution = resolution

    return common.response(json.dumps({'status': 'ok'}))
