import re
import time
from abc import ABC
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
from time import sleep
from typing import Any, Dict, List, NoReturn, Optional, Tuple, Union

import coinaddrvalidator
import pytz
import requests
from django.conf import settings
from rest_framework import status

from exchange.base.models import Currencies
from exchange.blockchain.metrics import metric_incr

integer_types = (int,)
string_types = (bytes, str, bytearray)

MAX_RESPONSE_SIZE_TO_LOG = 50_000_000  # 50 MB


def get_address_info(symbol: str, address: str) -> coinaddrvalidator.validation.ValidationResult:
    try:
        return coinaddrvalidator.validate(symbol.lower(), address)
    except TypeError:
        # if validator for symbol doesn't exist return default object;
        # 'valid' attribute is set to True, because there may not exist
        #  validator for every supported coin
        return coinaddrvalidator.validation.ValidationResult(
            name='',
            ticker=symbol,
            address=address.encode(),
            valid=True,
            network='',
            address_type='',
            is_extended=False
        )


class Service(ABC):  # noqa: B024
    """General class for handling blockchain API services."""

    symbol = ''
    _base_url = None
    api_key_header = None
    rate_limit = 0  # request per second
    back_off_time = 60
    backoff = datetime.now()
    timeout = 30
    request_reliability = 1
    reliability_need_status_codes: List[int] = []
    supported_requests: Dict[str, str] = {}

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key
        self.last_response = None
        self.last_response_time = None

    def get_name(self) -> str:
        name = self.__class__.__name__
        name = name.replace('API', 'api')
        return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()

    def build_request_url(self, request_method: str, **params: dict) -> str:
        path_url = self.supported_requests.get(request_method)
        if path_url:
            return self.base_url + path_url.format(**params)
        return self.base_url

    @property
    def base_url(self) -> Optional[str]:
        return self._base_url

    @base_url.setter
    def base_url(self, url: str) -> None:
        if settings.IS_EXPLORER_SERVER:
            from exchange.explorer.networkproviders.models import Provider
            provider = Provider.objects.get(name=self.get_name())
            provider.set_url_as_default(url)
        else:
            self._base_url = url

    def get_header(self) -> Dict[str, str]:
        return {}

    def request(
            self,
            request_method: str,
            with_rate_limit: bool = True,
            body: Optional[Dict[str, Any]] = None,
            headers: Optional[Dict[str, str]] = None,
            timeout: int = 30,
            proxies: Optional[Dict[str, str]] = None,
            force_post: bool = False,
            cert: Optional[str] = None,
            **params: Any
    ) -> Dict[str, Any]:
        request_url = self.build_request_url(request_method, **params)

        if not request_url:
            return {}

        if not body:
            body = {}

        if not headers:
            headers = self.get_header() or {}
        if self.api_key_header:
            headers.update(self.api_key_header)

        if with_rate_limit and self.rate_limit:
            self.wait_for_next_request()

        for i in range(self.request_reliability):
            try:
                start_time = time.time()
                # if body is passed, use post
                if body or force_post:
                    response = requests.post(
                        request_url,
                        data=body,
                        headers=headers,
                        timeout=timeout,
                        cert=cert,
                        proxies=proxies
                    )
                else:
                    response = requests.get(
                        request_url,
                        headers=headers,
                        timeout=timeout,
                        cert=cert,
                        proxies=proxies
                    )

                elapsed_time = time.time() - start_time

                if settings.USE_PROMETHEUS_CLIENT:
                    from exchange.blockchain.metrics import response_time_metric
                    response_time_metric.labels(network=self.symbol.lower(), provider=self.get_name()).observe(
                        amount=elapsed_time)

                if settings.IS_EXPLORER_SERVER:
                    from exchange.blockchain.service_based.logging import logger
                    from exchange.blockchain.tasks import log_provider_request_task

                    try:
                        response_body_size: int = 0
                        if response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]:
                            response_body_size = len(response.content)

                        try:
                            network = self.cache_key
                        except AttributeError:
                            network = ''

                        log_data = {
                            'request_url': request_url,
                            'request_method': 'POST' if (body or force_post) else 'GET',
                            'headers': headers,
                            'body': body if (body or force_post) else None,
                            'attempt': i + 1,
                            'response_status': response.status_code,
                            'response_body_size': response_body_size,
                            'response_time': elapsed_time,
                            'network': network,
                            'provider': self.get_name(),
                            'service': request_method,
                        }

                        log_provider_request_task.delay(message='provider-data', log_data=log_data)

                    except Exception:
                        logger.exception('Cannot prepare log data for ES')

                if response.status_code not in self.reliability_need_status_codes:
                    break
            except ConnectionError:
                metric_incr(
                    name='api_errors_count',
                    labels=[self.symbol.lower(), self.get_name(), 'ApiConnectionError']
                )
                raise

        self.last_response = response
        self.last_response_time = datetime.now()

        if not status.HTTP_200_OK <= response.status_code <= status.HTTP_201_CREATED:
            self.process_error_response(response)

        return response.json()

    def wait_for_next_request(self) -> None:
        if not self.last_response_time:
            return

        diff = (datetime.now() - self.last_response_time).total_seconds()
        wait = self.rate_limit - diff

        if wait > 0:
            sleep(wait)

    def process_error_response(self, response: requests.Response) -> NoReturn:
        if response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR:
            raise InternalServerError('Error 500: Internal Server Error.')
        if response.status_code == status.HTTP_502_BAD_GATEWAY:
            raise BadGateway('Error 502: Bad Gateway.')
        if response.status_code == status.HTTP_504_GATEWAY_TIMEOUT:
            raise GatewayTimeOut('Error 504: Gateway timeout.')
        if response.status_code == status.HTTP_403_FORBIDDEN:
            raise Forbidden('Error 403: Forbidden.')
        if response.status_code == status.HTTP_402_PAYMENT_REQUIRED:
            raise PaymentRequired('Error 402: Payment is required.')
        if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            self.backoff = datetime.now() + timedelta(0, self.back_off_time)
            raise RateLimitError('Too Many Requests.')
        raise APIError(f'Following error occurred: {response.text}, status code: {response.status_code}.')


# Exceptions
class NetworkNotExist(Exception):  # noqa: N818
    pass


class APIError(Exception):
    pass


class AddressNotExist(APIError):  # noqa: N818
    pass


class APIKeyMissing(APIError):  # noqa: N818
    pass


class RateLimitError(APIError):
    pass


class InternalServerError(APIError):
    pass


class BadGateway(APIError):  # noqa: N818
    pass


class Forbidden(APIError):  # noqa: N818
    pass


class PaymentRequired(APIError):  # noqa: N818
    pass


class GatewayTimeOut(APIError):  # noqa: N818
    pass


class ValidationError(APIError):
    pass


class ParseError(APIError):
    pass


class UnsupportedStaking(Exception):  # noqa: N818
    pass


class BlockchainUtilsMixin:
    PRECISION: Optional[int] = None
    MIN_UNIT = 1
    MAX_UNIT = 2 ** 256 - 1

    @classmethod
    def is_integer(cls, value: Union[int, str, bool]) -> bool:
        return isinstance(value, integer_types) and not isinstance(value, bool)

    @classmethod
    def is_string(cls, value: Union[str, bytes, bytearray]) -> bool:
        return isinstance(value, string_types)

    @classmethod
    def from_unit(
            cls,
            number: int,
            precision: Optional[int] = None,
            negative_value: bool = False
    ) -> Union[int, Decimal]:
        """Helper function that will convert a value in UNIT to Decimal.

        Args:
            :param negative_value: If true, the function accept negative value to parse
            :param number: Value in UNIT to convert to Decimal
            :param precision: If set precision that will be used for calculation
        """
        if precision is None:
            precision = cls.PRECISION

        if precision is None:
            raise ValueError('Precision is None.')

        if number == 0:
            return Decimal('0.0')
        min_value = -cls.MAX_UNIT if negative_value else cls.MIN_UNIT
        if number < min_value or number > cls.MAX_UNIT:
            raise ValueError('value must be between 1 and 2**256 - 1')

        unit_value = Decimal(f'1e{precision}')

        with localcontext() as ctx:
            ctx.prec = 999
            d_number = Decimal(value=number, context=ctx)
            return d_number / unit_value

    @classmethod
    def to_unit(cls, number: Union[float, str, Decimal], precision: Optional[int] = None) -> int:
        """Helper function that will convert a value in Decimal to UNIT.

        Args:
            :param number: Value in Decimal to convert to UNIT
            :param precision: If set precision that will be used for calculation
        """
        if precision is None:
            precision = cls.PRECISION

        if precision is None:
            raise ValueError('Precision is None.')

        if cls.is_integer(number) or cls.is_string(number):
            d_number = Decimal(value=number)
        elif isinstance(number, float):
            d_number = Decimal(value=str(number))
        elif isinstance(number, Decimal):
            d_number = number
        else:
            raise TypeError('Unsupported type. Must be one of integer, float, or string')

        s_number = str(number)
        unit_value = Decimal(f'1e{precision}')

        if d_number == 0:
            return 0

        if d_number < 1 and '.' in s_number:
            with localcontext() as ctx:
                multiplier = len(s_number) - s_number.index('.') - 1
                ctx.prec = multiplier
                d_number = Decimal(value=number, context=ctx) * 10 ** multiplier
            unit_value /= 10 ** multiplier

        with localcontext() as ctx:
            ctx.prec = 999
            result_value = Decimal(value=d_number, context=ctx) * unit_value

        if result_value < cls.MIN_UNIT or result_value > cls.MAX_UNIT:
            raise ValueError('Resulting wei value must be between 1 and 2**256 - 1')

        return int(result_value)

    @classmethod
    def dict_reset_values(cls, dictionary: Dict[str, Any], reset_value: int = 0) -> Dict[str, Any]:
        """
        Utility method to set all values in dictionary to dummy value.
        Primary usage is comparing two dictionary nested structure, for live test of API responses
        """
        for key, value in dictionary.items():
            if isinstance(value, dict):
                dictionary[key] = cls.dict_reset_values(dictionary[key], reset_value)
            elif isinstance(value, list):
                dictionary[key] = [cls.dict_reset_values(item, reset_value) for item in value]
            else:
                dictionary[key] = reset_value
        return dictionary

    @classmethod
    def compare_dicts_without_order(cls, dict1: dict, dict2: dict) -> bool:
        from exchange.blockchain.service_based.logging import logger as wrapper_logger

        if isinstance(dict1, dict) and isinstance(dict2, dict):
            if set(dict1.keys()) != set(dict2.keys()):
                wrapper_logger.warning(
                    f'Dict keys are not equal: dict1 keys: {dict1.keys()}, dict2 keys: {dict2.keys()}')
                return False
            return all(cls.compare_dicts_without_order(dict1.get(key), dict2.get(key)) for key in dict1)

        if isinstance(dict1, list) and isinstance(dict2, list):
            if len(dict1) != len(dict2):
                return False
            sorted_list1 = sorted(dict1, key=lambda d: cls.replace_none_value_by_str(d))
            sorted_list2 = sorted(dict2, key=lambda d: cls.replace_none_value_by_str(d))
            return all(cls.compare_dicts_without_order(d1, d2) for d1, d2 in zip(sorted_list1, sorted_list2))

        return cls.compare_value_based_on_type(dict1, dict2)

    @classmethod
    def compare_value_based_on_type(cls, val1: Any, val2: Any) -> bool:
        if isinstance(val1, Decimal) and isinstance(val2, Decimal):
            return float(val1) == float(val2)
        if isinstance(val1, datetime) and isinstance(val2, datetime):
            return val1.astimezone(timezone.utc) == val2.astimezone(timezone.utc)
        if isinstance(val1, str) and isinstance(val2, str):
            return val1.casefold() == val2.casefold()
        return val1 == val2

    @staticmethod
    def replace_none_value_by_str(d: Dict[str, Any]) -> Tuple[Tuple[str, Any], ...]:
        """Return a tuple with values replaced by str if they are None"""
        return tuple((k, d[k]) if d[k] is not None else (k, '') for k in sorted(d.keys()))


def get_currency_symbol_from_currency_code(currency_code: str) -> Optional[str]:
    for k, v in Currencies._identifier_map.items():  # noqa: SLF001
        if v == currency_code:
            return k.upper()
    return None


# please keep the order alphabetically
EXTRA_FIELD_NEEDED_CURRENCIES: set = {
    '1b_babydoge',
    '1inch',
    '1k_bonk',
    '1m_btt',
    '1m_nft',
    '1m_pepe',
    'aave',
    'ada',
    'aevo',
    'agix',
    'agld',
    'algo',
    'alpha',
    'ankr',
    'ant',
    'ape',
    'api3',
    'apt',
    'arb',
    'auction',
    'avax',
    'axs',
    'badger',
    'bal',
    'band',
    'bat',
    'bch',
    'bico',
    'bigtime',
    'blur',
    'bnb',
    'bnt',
    'btc',
    'busd',
    'celr',
    'chz',
    'comp',
    'crv',
    'cvc',
    'cvx',
    'dai',
    'dao',
    'doge',
    'dot',
    'dydx',
    'egala',
    'egld',
    'elf',
    'enj',
    'ens',
    'etc',
    'eth',
    'ethfi',
    'fet',
    'fil',
    'flow',
    'flr',
    'form',
    'front',
    'ftm',
    'g',
    'gal',
    'glm',
    'gmx',
    'gno',
    'gods',
    'grt',
    'id',
    'ilv',
    'imx',
    'jst',
    'knc',
    'ldo',
    'link',
    'looks',
    'lpt',
    'lrc',
    'ltc',
    'magic',
    'mana',
    'mask',
    'mdt',
    'meme',
    'mkr',
    'near',
    'nmr',
    'om',
    'omg',
    'one',
    'orbs',
    'paxg',
    'perp',
    'pol',
    'qnt',
    'ray',
    'rdnt',
    'ren',
    'render',
    'rsr',
    's',
    'sand',
    'shib',
    'skl',
    'slp',
    'snt',
    'snx',
    'sol',
    'srm',
    'ssv',
    'storj',
    'sushi',
    # 'sui',
    't',
    'trb',
    'trx',
    'tnsr',
    'uma',
    'uni',
    'usdc',
    'usdt',
    'vra',
    'w',
    'waxp',
    'wbtc',
    'weth',
    'wld',
    'woo',
    'wif',
    'xmr',
    'xtz',
    'yfi',
    'ygg',
    'zro',
    'zrx',
}


def v2_parse_int(s: Optional[str], required: bool = False) -> int:
    if not s:
        if required:
            raise ParseError('Missing integer value')
        return None
    s = str(s).strip()
    try:
        # Try to parse as float first to handle float-like strings
        f = float(s)
        if f.is_integer():
            return int(f)
        raise ValueError
    except ValueError as err:
        raise ParseError(f'Invalid integer value: "{s}"') from err


def v2_parse_utc_timestamp(s: Optional[str], required: bool = False) -> Optional[datetime]:
    if not s:
        if required:
            raise ParseError('Missing datetime value')
        return None
    return (datetime(1970, 1, 1, 0, 0, 0, 0, pytz.utc)
            + timedelta(seconds=v2_parse_int(s)))


def split_batch_input_data(input_data: str, splitter: str) -> list:
    parts = []
    current_part = ''

    for i in range(0, len(input_data), 64):
        chunk = input_data[i:i + 64]  # Chunk input data into 64-character part
        if chunk == splitter:  # Check if the chunk is the splitter
            if current_part:
                parts.append(current_part)
            current_part = ''
        else:
            current_part += chunk

    if current_part:
        parts.append(current_part)

    return parts
