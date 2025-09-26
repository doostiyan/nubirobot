import time
from decimal import Decimal

import requests
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.timezone import now
from django.views.static import serve
from django_ratelimit.decorators import ratelimit

from exchange.base.api import get_user_by_token, public_api, public_get_and_post_api, public_post_api
from exchange.base.http import get_client_country
from exchange.base.models import Currencies, get_currency_codename
from exchange.broker.broker.client.health_check import check_kafka_health
from exchange.wallet.models import AvailableDepositAddress


@ratelimit(key='user_or_ip', rate='60/10m', block=True)
def home(request):
    user = request.user
    has_access = user.is_superuser
    if user.is_authenticated:
        if user.groups.filter(name__in=['Supervisor Support']).exists():
            has_access = True
    if not has_access:
        return render(request, 'base/home.html', {})

    # Wallet Address Usage Stats
    currencies_with_wallet = [Currencies.btc, Currencies.eth, Currencies.ltc, Currencies.trx]
    query = AvailableDepositAddress.objects.values('currency').annotate(Count('id'))
    wallets_all = update_dic_with_query({}, query, 'currency', 'id__count')
    query = AvailableDepositAddress.objects.filter(used_for__isnull=False).values('currency').annotate(Count('id'))
    wallets_used = update_dic_with_query({}, query, 'currency', 'id__count')
    wallet_usage = []
    for currency in currencies_with_wallet:
        wallet_usage.append({
            'name': get_currency_codename(currency).upper(),
            'used': wallets_used.get(currency, 0),
            'total': wallets_all.get(currency, 0),
        })

    return render(request, 'base/home.html', {
        'wallet_usage': wallet_usage,
    })


def update_dic_with_query(dictionary, query, key, value):
    for dic in query:
        dictionary[dic[key]] = dic[value]
    return dictionary


def serve_media(request, path):
    if not request.user.is_staff:
        raise PermissionDenied
    return serve(request, path, document_root=settings.MEDIA_ROOT)


@ratelimit(key='user_or_ip', rate='120/1m', block=True)
@public_api
def ntp(request):
    return JsonResponse({
        'time': int(time.time() * 1000),
    })


@ratelimit(key='user_or_ip', rate='60/1m', block=True)
@public_api
def connectivity(request):
    status = 0
    start_time = time.time()
    try:
        r = requests.get('https://connectivitycheck.gstatic.com/generate_204', timeout=2)
        status = r.status_code
    except:
        pass
    latency = time.time() - start_time
    latency = round(latency * 1000)

    return JsonResponse({
        'status': 'ok' if status == 204 else 'failed',
        'response': status,
        'latency': latency,
    })


@ratelimit(key='user_or_ip', rate='60/1m', block=True)
@public_get_and_post_api
def check_version(request):
    flags = []
    user = get_user_by_token(request)
    if user.is_authenticated:
        flags.append('user')
        nw = now()
        stats = user.stats
        updated_stats = []
        client = request.g('c')
        version = request.g('v')
        if client == 'web':
            stats.last_web_signal = nw
            stats.web_version = version
            updated_stats += ['last_web_signal', 'web_version']
        elif client == 'android':
            stats.last_app_signal = nw
            stats.app_version = version
            updated_stats += ['last_app_signal', 'app_version']
        if updated_stats:
            stats.save(update_fields=updated_stats)
    return JsonResponse({
        'status': 'ok',
        'version': {
            'api': '{}-{}'.format(settings.RELEASE_VERSION, settings.CURRENT_COMMIT),
            'web': 'v2.7-44099ca',
            'android': 9903091,
        },
        'flags': flags,
    })


@ratelimit(key='user_or_ip', rate='60/1m', block=True)
@public_get_and_post_api
def check_debug(request):
    user = get_user_by_token(request)
    return JsonResponse({
        'status': 'ok',
        'userId': user.pk if user.is_authenticated else 0,
        'ip': request.META['REMOTE_ADDR'],
        'country': get_client_country(request),
        'version': '{}-{}'.format(settings.RELEASE_VERSION, settings.CURRENT_COMMIT),
        'server': settings.SERVER_NAME,
    })


@ratelimit(key='user_or_ip', rate='60/m', block=True)
@public_post_api
def check_health(request):
    """Check System Health API"""
    # Execute a simple query to check the database connection
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        db_status = 'ok'
    except Exception:
        db_status = 'failed'
    # Test cache access
    # Note: this only checks main redis and not the w2 redis used in ratelimit
    cache_time = 0
    cache_usdt_price = 0
    try:
        cache_time = cache.get('current_time') or 0
        cache_usdt_price = cache.get('market_4_last_price')
        cache_status = 'ok'
    except Exception:
        cache_status = 'failed'
    # Clean cache data
    try:
        cache_latency = int(time.time() * 1000) - cache_time
    except Exception:
        cache_latency = 3600000
    cache_usdt_price = int(cache_usdt_price) if isinstance(cache_usdt_price, Decimal) else 0

    kafka_latency = None
    kafka_error = None
    try:
        producer_config = settings.KAFKA_PRODUCER_CONFIG
        producer_config['batch.size'] = '1'  # For lowering latency

        kafka_health = check_kafka_health(
            producer_config=producer_config,
            consumer_config=settings.KAFKA_CONSUMER_CONFIG,
            producer_timeout=Decimal('0.5'),
            consumer_timeout=Decimal('0.5'),
        )
        if all((kafka_health.is_producer_healthy, kafka_health.is_consumer_healthy)):
            kafka_status = 'ok' if kafka_health.e2e_latency and kafka_health.e2e_latency < 1000 else 'degraded'
            kafka_latency = str(kafka_health.e2e_latency) if kafka_health.e2e_latency is not None else None
        elif kafka_health.is_producer_healthy:
            kafka_status = 'consumerFailed'
        else:
            kafka_status = 'failed'
    except Exception as ex:  # noqa: BLE001;
        kafka_status = 'failed'
        kafka_error = ex.__class__.__name__

    # Overall status check
    if db_status == 'ok' and cache_status == 'ok':
        status = health = 'ok'
        if cache_usdt_price < 300000 or cache_latency >= 1000 or kafka_status != 'ok':
            health = 'degraded'
    else:
        status = health = 'failed'

    return JsonResponse(
        {
            'status': status,
            'health': health,
            'cache': cache_status,
            'cacheLatency': min(cache_latency, 3600000),
            'cacheUSDTPrice': cache_usdt_price,
            'db': db_status,
            'kafka': kafka_status,
            'kafkaLatency': kafka_latency,
            'kafkaError': kafka_error,
            'server': settings.SERVER_NAME,
        },
    )


@ratelimit(key='user_or_ip', rate='60/1m', block=True)
@public_post_api
def check_token(request):
    token = request.headers.get('authorization')
    if token:
        user = get_user_by_token(request)
        status = 'ok' if user.is_authenticated else 'invalid'
    else:
        status = 'missing'
    return JsonResponse({
        'status': status,
    })
