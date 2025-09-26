import csv
import functools
import hashlib
import json
import re
import time
from collections import defaultdict
from contextlib import ContextDecorator, contextmanager
from decimal import Decimal
from typing import ClassVar, Dict, Iterable, List, Optional, Set, Union
from urllib.parse import urlparse

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models.fields import DeferredAttribute
from django.http import HttpRequest, HttpResponse

from exchange.base.api import compare_versions, is_internal_ip
from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.decorators import ram_cache
from exchange.base.logging import report_exception
from exchange.base.models import Currencies, Settings
from exchange.base.parsers import parse_date, parse_int

JsonAble = Union[None, int, str, bool, float, List['JsonAble'], Dict[str, 'JsonAble']]


def download_csv(file_name, serialized_objects, headers):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename={}.csv'.format(file_name)
    response.write(u'\ufeff'.encode('utf8'))
    writer = csv.writer(response)
    if serialized_objects:
        writer.writerow(header for header in headers)
    for obj in serialized_objects:
        row = writer.writerow(obj[header] for header in headers)
    return response


def export_csv(file_path, serialized_objects, headers, encoding=None):
    with open(file_path, 'w', newline='', encoding=encoding) as csv_file:
        writer = csv.writer(csv_file)
        if serialized_objects:
            writer.writerow(header for header in headers)
        for obj in serialized_objects:
            row = writer.writerow(obj[header] for header in headers)


def paginate(data, page=1, page_size=50, request=None, check_next=False, max_page=None, max_page_size=None):
    if request:
        page = parse_int(request.g('page')) or parse_int(page)
        page_size = parse_int(request.g('pageSize')) or parse_int(page_size)
    else:
        page = parse_int(page) or 1
        page_size = parse_int(page_size) or 50
    if page < 1 or (max_page and page > max_page):
        page = 1
    if page_size < 1 or (max_page_size and page_size > max_page_size):
        page_size = 50
    paged_data = list(data[(page - 1) * page_size:page * page_size + check_next])
    if check_next:
        if len(paged_data) > page_size:
            paged_data.pop()
            has_next = True
        else:
            has_next = False
        return paged_data, has_next
    return paged_data


def is_url_allowed(url: str, allowed_domains: Set[str]) -> bool:
    if url.startswith('https://'):
        return is_domain_allowed(url, allowed_domains)

    if url.startswith('nobitex://'):
        return True

    return False


def is_domain_allowed(url: str, allowed_domains: Set[str]) -> bool:
    """
    Checks if the domain is in allowed domains set.
    NOTE: Current implementation does not support multi-level subdomains
    """
    domain = _get_domain(url)
    if domain is None:
        return False
    return _is_domain_matched(domain, allowed_domains) or _is_subdomain_matched(domain, allowed_domains)


def _get_domain(url):
    try:
        parsed_url = urlparse(url)
        domain = parsed_url.hostname
        return domain.lower().rstrip('.') if domain else None
    except Exception:
        report_exception()
        return None


def _is_domain_matched(domain: str, allowed_domains: Set[str]):
    return domain in allowed_domains


def _is_subdomain_matched(domain: str, allowed_domains: Set[str]):
    return domain[domain.find('.') + 1 :] in allowed_domains


def build_frontend_url(request, path=None, is_devnet=False):
    if not path:
        path = '/'
    if path[0] != '/':
        path = '/' + path
    url = request.build_absolute_uri(path)
    url = url.replace('testnetapi.', 'testnet.')
    url = url.replace('api.', '')
    # Fix links to non-standard frontend urls
    url = url.replace('https://nobitex1.ir/', settings.PROD_FRONT_URL)
    url = url.replace('https://nobitex.market/', settings.PROD_FRONT_URL)
    # Local development special case
    if settings.DEBUG:
        url = url.replace('127.0.0.1:8000', 'localhost:4000')

    if settings.IS_TESTNET and is_devnet:
        return url.replace('testnet.', 'devnet.')
    return url


def called_from_frontend(request):
    frontend_url = build_frontend_url(request)
    referer = request.headers.get('referer', '')
    return referer.startswith(frontend_url)


def get_dollar_sell_rate():
    return Decimal(Settings.get_dict('usd_value')['sell'])


def get_dollar_buy_rate():
    return Decimal(Settings.get_dict('usd_value')['buy'])


def get_min_withdraw_amount(currency):
    """returns minimum withdraw amount possible for a currency in all of it's networks"""
    from exchange.wallet.withdraw_method import AutomaticWithdrawMethod

    currency_networks = CURRENCY_INFO[currency]['network_list']
    min_vals_list = []
    for key in currency_networks.keys():
        min_vals_list.append(AutomaticWithdrawMethod.get_withdraw_min(currency, key))

    return min(min_vals_list)


def get_max_withdraw_amount(currency):
    """returns maximum withdraw amount possible for a currency in all of it's networks"""
    from exchange.wallet.withdraw_method import AutomaticWithdrawMethod

    currency_networks = CURRENCY_INFO[currency]['network_list']
    max_vals_list = []
    for key in currency_networks.keys():
        max_vals_list.append(AutomaticWithdrawMethod.get_withdraw_max(currency, key))

    return max(max_vals_list)


def date_filter(data, request=None, field=None, since=None, until=None):
    if not field:
        field = 'created_at'
    if request:
        since = parse_date(request.g('from')) or since
        until = parse_date(request.g('to')) or until
    date_filter = {}
    if since:
        date_filter[f'{field}__gte'] = since
    if until:
        date_filter[f'{field}__lte'] = until
    return data.filter(**date_filter)


def get_base_api_url(trailing_slash=True):
    url = settings.PROD_API_URL
    if settings.IS_TESTNET:
        url = settings.TESTNET_API_URL
    if settings.DEBUG:
        url = settings.DEBUG_API_URL
    if not trailing_slash and url.endswith('/'):
        url = url[:-1]
    return url


@contextmanager
def stage_changes(instance, update_fields):
    old_values = {field: getattr(instance, field) for field in update_fields}
    try:
        yield
    except Exception as e:
        raise e
    else:
        update_fields = [field for field, old_value in old_values.items() if old_value != getattr(instance, field)]

        if update_fields:
            update_fields += [field.name for field in instance._meta.get_fields() if getattr(field, 'auto_now', False)]

        instance.save(update_fields=update_fields, using=settings.WRITE_DB)


def parse_request_channel(request) -> Optional[str]:
    '''
        This function detects source channel of request user-agent and
        converts it to simplified form.
    '''
    try:
        ua = request.headers.get('user-agent') or 'unknown'
    except AttributeError:
        return None
    slash_ind = ua.find('/')
    category = ua[:slash_ind] if slash_ind >= 0 else ''
    category = category.lower()
    if category == 'mozilla':
        return 'w'
    if category == 'android':
        return 'a'
    if category == 'iosapp':
        return 'i'
    if category == 'locketwallet':
        return 'l'
    return None


def get_max_db_value(deferred_field: DeferredAttribute) -> Decimal:
    field = deferred_field.field
    return Decimal(1).scaleb(field.max_digits - field.decimal_places) - Decimal(1).scaleb(-field.decimal_places)


@ram_cache(default={})
def get_individual_ratelimit_throttle_settings() -> dict:
    """Get endpoints ratelimit throttling settings

    It's a dictionary whose keys are ratelimit group names - i.e. view names
     and the values are again a dictionary whose keys are any of the following:
     - `norm`: Throttle rate for normal users
     - `in_bot`: Throttle rate for market making bots
     - `ex_bot`: Throttle rate for user trading bots -- overrides `norm`
     - `vip`: Throttle rate for users who request to vip domain (api2.nobitex.ir) -- overrides `norm`

    Sample: {
        "exchange.market.views.orders_cancel_old": {"norm": 0.04},
        "exchange.market.views.orders_update_status": {"norm": 0.03, "ex_bot": 0.02, "vip": 0.05, "in_bot": 0.06},
        "exchange.market.views.OrderCreateView.OrderCreateView.post": {"norm": 0, "in_bot": 0},
        "exchange.market.views.OrderCreate.create_orders.BTCIRT": {"norm": 0.0}
    }
    """
    return Settings.get_cached_json('throttle_endpoint_rate_limits') or {}


@ram_cache(default={})
def get_global_ratelimit_throttle_settings() -> dict:
    """
    Get throttle settings for all endpoints

    returns a dict with keys:
    - `norm`: Throttle rate for normal users
    - `in_bot`: Throttle rate for market making bots
    - `ex_bot`: Throttle rate for user trading bots
    - `vip`: Throttle rate for users who request to vip domain

    Sample: {"norm": 0.03, "ex_bot": 0.02, "vip": 0.05, "in_bot": 0.06}
    """
    return Settings.get_cached_json('global_throttle_rate_limits') or {}


def throttle_ratelimit(ratelimit: str, individual_throttle_rate, global_throttle_rate) -> str:
    """Change ratelimit str based on the given throttle rate."""
    # Ignore invalid input
    throttle_rate = (
        individual_throttle_rate
        if isinstance(individual_throttle_rate, (int, float)) and 0 <= individual_throttle_rate <= 4
        else 1
    )
    if not isinstance(global_throttle_rate, (int, float)) or global_throttle_rate < 0 or global_throttle_rate > 20:
        global_throttle_rate = 1
    throttle_rate *= global_throttle_rate

    # Most common cases
    if throttle_rate == 1:
        return ratelimit
    if throttle_rate == 0:
        return '0/m'
    # Multiply ratelimit by throttle_rate
    ratelimit_parts = ratelimit.split('/', 1)
    ratelimit_parts[0] = str(int(int(ratelimit_parts[0]) * throttle_rate))
    return '/'.join(ratelimit_parts)


def get_api_ratelimit(base_rate: str, *, default_none: bool = False):
    def sub_func_ratelimit(group, request):
        individual_throttle_rates = get_individual_ratelimit_throttle_settings().get(group, {})

        if not individual_throttle_rates and default_none:
            return None
        global_throttle_rates = get_global_ratelimit_throttle_settings()
        service_type = get_throttle_rates_service_type(request)
        rate = throttle_ratelimit(
            base_rate,
            individual_throttle_rates.get(service_type),
            global_throttle_rates.get(service_type),
        )
        return rate
    return sub_func_ratelimit


def get_throttle_rates_service_type(request):
    ip = request.META['REMOTE_ADDR']
    host = request.get_host()
    user_agent = str(request.headers.get('user-agent'))
    if is_internal_ip(ip):
        service_type = 'in_bot'
    elif host == 'api2.nobitex.ir':
        service_type = 'vip'
    elif user_agent.startswith('TraderBot/'):
        service_type = 'ex_bot'
    else:
        service_type = 'norm'
    return service_type


def is_from_unsupported_app(request: HttpRequest, feature: str) -> bool:
    """Check if the request is from client app with old version3
    Args:
        request (HttpRequest)
        feature (str): feature name that needs to check minimum acceptable version from it
    Examples:
        {'Android': '2.4.1', 'iOSApp': '1.1.0'}
    """
    user_agent = request.headers.get('user-agent') or 'unknown'
    acceptable_versions = {
        'remove_rial_otp': {'Android': '5.7.2', 'iOSApp': '2.5.0'},
        'long_buy': {'Android': '5.6.0', 'iOSApp': '2.4.0'},
        'percentage_fee': {'Android': '5.0.1', 'iOSApp': '1.9.3'},
        'forget_password': {'Android': '6.2.2'},
        'bigint_order_id': {'Android': '6.4.3'},
        'change_mobile': {'Android': '7.0.0', 'iOSApp': '7.0.0'},  # todo: set correct versions
    }
    min_acceptable_versions = acceptable_versions[feature]
    result = re.match(r'(Android|iOSApp)/(\d+.\d+.\d)', user_agent)
    if result:
        client, version = result.groups()
        if client in min_acceptable_versions:
            return compare_versions(version, min_acceptable_versions[client]) == -1
    return False


def get_symbol_from_currency_code(currency_code):
    for k, v in Currencies._identifier_map.items():
        if v == currency_code:
            return k.lower()
    return None


class _ContextFlag(ContextDecorator):
    """Set a flag for the context of the code flow from a block

    Examples:
        @context_flag(MY_FLAG=True)
        def func():
            do_sth()

        or

        with context_flag(MY_FLAG=True):
            do_sth()

        def do_sth():
            context_flag.get('MY_FLAG', False)
    """

    _flags: ClassVar[defaultdict] = defaultdict(list)

    def __init__(self, **flags):
        self._custom_flags = flags

    def __enter__(self):
        for flag_name, flag_value in self._custom_flags.items():
            self._flags[flag_name].append(flag_value)

    def __exit__(self, exc_type, exc_val, exc_tb):
        for flag_name in self._custom_flags:
            self._flags[flag_name].pop()

    @classmethod
    def get(cls, flag_name, default=None):
        if cls._flags[flag_name]:
            return cls._flags[flag_name][-1]
        return default


context_flag = _ContextFlag


def deterministic_hash(data: Union[bytes, JsonAble]) -> int:
    hasher = hashlib.sha256()
    hasher.update(data if isinstance(data, bytes) else json.dumps(data).encode())
    return int(hasher.hexdigest(), 16)


@contextmanager
def sleep_remaining(seconds):
    start = time.time()
    yield
    duration = time.time() - start
    if duration < seconds:
        time.sleep(seconds - duration)


class CacheItem:
    key: str
    default = None

    def __init__(self):
        self.value = self.get_value()

    def __del__(self):
        self.set_value(self.value)

    @classmethod
    def get_value(cls) -> dict:
        return cache.get(cls.key) or cls.default

    @classmethod
    def set_value(cls, value):
        cache.set(cls.key, value)

    @classmethod
    def clear(cls):
        cache.delete(cls.key)


def batcher(iterable: Iterable, batch_size: int, idempotent: bool = False) -> Iterable:
    """Group a list or a Queryset into batches

    :param iterable: Input list
    :param batch_size: Size of each batch
    :param idempotent: True if each batch is removed from iterable after processing
    :return: an iterable of batches of specified size
    """
    batch_id = 0
    while batch := iterable[batch_id * batch_size : (batch_id + 1) * batch_size]:
        yield batch
        if not idempotent:
            batch_id += 1
        if len(batch) < batch_size:
            return


def atomic_if_is_not_already(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if transaction.get_connection().in_atomic_block:
            return func(*args, **kwargs)

        with transaction.atomic():
            return func(*args, **kwargs)

    return wrapper
