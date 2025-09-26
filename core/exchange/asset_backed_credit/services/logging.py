import json

from django.db import transaction
from django_redis import get_redis_connection

from exchange.asset_backed_credit.api.serializers import OutgoingAPICallLogSerializer
from exchange.asset_backed_credit.constant import API_LOG_CACHE_KEY
from exchange.asset_backed_credit.exceptions import CreateAPILogError
from exchange.asset_backed_credit.models import OutgoingAPICallLog, UserService
from exchange.base.decorators import measure_time_cm
from exchange.base.logging import report_event


@measure_time_cm(metric='abc_createApiLog')
def process_abc_outgoing_api_logs():
    cache = get_redis_connection('default')
    logs = cache.lrange(API_LOG_CACHE_KEY, 0, -1)

    if not logs:
        return

    values = [json.loads(v.decode('utf-8')) for v in logs]
    user_service_ids = [log['user_service_id'] for log in values if log.get('user_service_id')]
    existing_user_service_ids = set(UserService.objects.filter(id__in=user_service_ids).values_list('id', flat=True))
    api_logs = []
    for log in values:
        user_service_id = log.get('user_service_id')
        if user_service_id and user_service_id not in existing_user_service_ids:
            log['user_service_id'] = None
        try:
            api_log_serializer = OutgoingAPICallLogSerializer(data=log)
            api_log_serializer.is_valid(raise_exception=True)
            api_logs.append(OutgoingAPICallLog(**log))
        except Exception as e:
            report_event('ABCTaskAPILogError', extras={'log': log, 'error': e})
            continue

    with transaction.atomic():
        OutgoingAPICallLog.objects.bulk_create(api_logs, batch_size=1000)
        if not cache.ltrim(API_LOG_CACHE_KEY, len(values), -1):
            raise CreateAPILogError('Cache ltrim error')
