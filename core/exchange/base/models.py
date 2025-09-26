import json
from decimal import Decimal
from enum import Enum
from typing import ClassVar, Dict, Iterable, List, Optional, Union

from django.conf import settings
from django.core.cache import cache
from django.db import InternalError, models, transaction
from django.forms import model_to_dict
from ipware import get_client_ip
from model_utils import Choices

from exchange.base.config import EXPLORER_URLS
from exchange.base.http import get_client_country
from exchange.base.logstash_logging.mixin import LogModelMixin

# noinspection PyUnresolvedReferences
from exchange.config.config.derived_data import (  # noqa: F401  # pylint: disable=unused-import
    ACTIVE_CRYPTO_CURRENCIES,
    ACTIVE_CRYPTO_CURRENCIES_CHOICES,
    ACTIVE_CURRENCIES,
    ACTIVE_NON_STABLE_CRYPTO_CURRENCIES,
    ADDRESS_REUSED_NETWORK,
    ALL_CRYPTO_CURRENCIES,
    ALL_CRYPTO_CURRENCIES_BINANCE_SYMBOL,
    ALL_CRYPTO_CURRENCIES_CHOICES,
    ALL_CURRENCIES,
    AMOUNT_PRECISIONS,
    AMOUNT_PRECISIONS_V2,
    AVAILABLE_CRYPTO_CURRENCIES,
    AVAILABLE_CURRENCIES,
    AVAILABLE_MARKETS,
    BIP39_CURRENCIES,
    BUY_PROMOTION_CURRENCIES,
    COLD_CURRENCIES,
    CRYPTO_CURRENCIES,
    CURRENCIES_WITHOUT_MARKET,
    DST_CURRENCIES,
    FIAT_CURRENCIES,
    INTEGER_ONLY_TAG_CURRENCIES,
    LAUNCHING_CURRENCIES,
    MAIN_ADDRESS_CURRENCIES,
    MARGIN_CURRENCIES,
    MARKET_TESTING_CURRENCIES,
    PRICE_PRECISIONS,
    PROCESSING_BLOCK_NETWORK,
    STABLE_CRYPTO_CURRENCIES,
    SUPPORTED_INVOICE_CURRENCIES,
    TAG_NEEDED_CURRENCIES,
    TAG_REUSE_MAP,
    TESTING_CURRENCIES,
    TESTNET_SUPPORTED_CURRENCIES,
    TRONZ_CURRENCIES,
    VALID_MARKET_SYMBOLS,
    XCHANGE_ACTIVE_CURRENCIES,
    XCHANGE_CURRENCIES,
    XCHANGE_TESTING_CURRENCIES,
    get_currency_codename,
    get_currency_codename_binance,
    get_market_symbol,
    parse_market_symbol,
)

# noinspection PyUnresolvedReferences
from exchange.config.config.models import (  # noqa: F401  # pylint: disable=unused-import
    BABYDOGE,
    BONK,
    BTT,
    CAT,
    CURRENCY_CODENAMES,
    FLOKI,
    NFT,
    NOT_COIN,
    ONE_INCH,
    PEPE,
    RIAL,
    TETHER,
    Currencies,
)

CREDIT_CURRENCIES = [
    Currencies.usdt,
    Currencies.usdc,
    Currencies.dai,
    Currencies.xaut,
    Currencies.paxg,
    Currencies.btc,
    Currencies.eth,
    Currencies.ton,
    Currencies.doge,
    Currencies.shib,
    Currencies.ftm,
    Currencies.s,
]

DEBIT_CURRENCIES = [
    Currencies.usdt,
    Currencies.usdc,
    Currencies.dai,
    Currencies.xaut,
    Currencies.paxg,
    Currencies.btc,
    Currencies.eth,
]

# Matcher Currencies
MATCHER_GET_ORDER_MONITORING_SYMBOLS = (
    'SHIBIRT',
    'SHIBUSDT',
    'DOGEIRT',
    'DOGEUSDT',
    'SOLIRT',
    'SOLUSDT',
    'BTCUSDT',
    'BTCIRT',
    'USDTIRT',
    'ADAIRT',
    'ADAUSDT',
    'ENJUSDT',
    'ENJIRT',
    'DAIIRT',
    'DAIUSDT',
    'EGALAUSDT',
    'EGALAIRT',
    'GRTUSDT',
    'GRTIRT',
    '1B_BABYDOGEIRT',
    '1B_BABYDOGEUSDT',
    'LINKIRT',
    'LINKUSDT',
)
MATCHER_MATCH_TIME_MONITORING_SYMBOLS = (
    'BTCUSDT',
    'BTCIRT',
    'USDTIRT',
    'ADAIRT',
    'ADAUSDT',
    'SHIBIRT',
    'SHIBUSDT',
    'LINKIRT',
    'LINKUSDT',
    'SOLIRT',
    'SOLUSDT',
)


""" exchanges deposit addresses for tag required currencies  """
EXCHANGE_ADDRESS_TAG_REQUIRED = {
    Currencies.xrp: [
        # Nobitex
        'rwRmyGRoJkHKtojaC8SH2wxsnB2q3yNopB',
        'rnm3AqXHTAkAPqfHhkVD1mfUnLAV4u9Sbn',
        'rJtRzs2dLFLjHyXS5TS6vEMTqrDRU5yTj1',
        # Binance
        'rEb8TK3gBgk5auZkwc6sHnwrGVJH8DuaLh',
    ],
    Currencies.bnb: [
        # Nobitex
        'bnb1990lfutz0f9wza6rsh36ysfwt9xpctxrll884r',
        'bnb18ajcdmv3c6w08sk8ayv75ks87y2w4hghntcxvd',
        # Binance
        'bnb136ns6lfw4zs5hg4n85vdthaad7hq5m4gtkgf23',
    ],
    Currencies.xlm: [
        # Nobitex
        'GCNZ3SFMGWKHTFFDEAB2QYQRCIZUQ55DULDF775WH7JR77P7UPJLMY2U',
        # Binance
        'GAHK7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DP42RBW3K6BTODB4A',
    ],
    Currencies.eos: [
        # Nobitex
        'nobitexeosw1',
        # Binance
        'binancecleos',
    ],
    Currencies.pmn: [
        # Nobitex
        'GDRSQI67GKRYZWPB75Z3RHMYI54LXAXNS2BK4LC26XSZRABDPLYLPXDT',
    ],
}

# Crypto Deposit Addresses
DERIVED_ADDRESSES = {
    Currencies.bch: Currencies.btc,
    Currencies.usdt: Currencies.eth,
    Currencies.etc: Currencies.eth,
}

# Crypto Address Types
ADDRESS_TYPE = Choices(
    (1, 'standard', 'Standard'),
    (2, 'segwit', 'Segwit'),
    (3, 'contract', 'Contract'),
    (4, 'contract2', 'ContractV2'),
    (5, 'eoa_v1', 'EOA V1'),
    (6, 'miner', 'Miner'),
)

ADDRESS_TYPE_CONTRACT_INDEX = {
    ADDRESS_TYPE.contract2: 1,
    ADDRESS_TYPE.contract: 2,
}
ADDRESS_TYPE_CONTRACT = sorted(ADDRESS_TYPE.subset('contract2', 'contract'), key=lambda x: ADDRESS_TYPE_CONTRACT_INDEX[x[0]])


def get_address_type_codename(addr_type):
    for k, v in ADDRESS_TYPE._identifier_map.items():
        if v == addr_type:
            return k
    return None


def get_explorer_url(currency, txid=None, address=None, is_testnet=None, network=None):
    from exchange.base.coins_info import CURRENCY_INFO
    """Create a link string to the external explorer url for the given parameters.
       Returned link is an str with "https://..." format and refers to an standard
       external (public) explorer for each coin.

       If txid is provided, a link to transaction details page is returned.
       If address is provided, a link to address/wallet details page is returned.
    """
    # Autodetect network if not set
    if is_testnet is None:
        is_testnet = not settings.IS_PROD

    # Special case for 0x prefix in transactions
    if currency in [Currencies.eth, Currencies.etc, Currencies.usdt] and txid:
        if not txid.startswith('0x') and not (currency == Currencies.usdt and network in ['TRX', 'ZTRX']):
            txid = '0x' + txid

    # Determine parameters based on link type
    explorer_key = 'testnet' if is_testnet else 'mainnet'
    if txid:
        args = [txid]
    elif address:
        args = [address]
        explorer_key += '-address'
    else:
        args = []

    network = network or CURRENCY_INFO.get(currency, {}).get('default_network')
    # Get url and format it
    url = EXPLORER_URLS.get(network, {}).get(explorer_key) or ''
    return url.format(*args)


class CacheableSettingPrefixes(Enum):
    position_fee_rate = 'position_fee_rate'


class Settings(models.Model):
    RELATED_CACHE_KEYS: ClassVar = {
        'usd_value': ('settings_usd_value', None),
        'webengage_enabled': ('settings_webengage_enabled', 24 * 60 * 60),
        'webengage_ssp_api_key': ('settings_webengage_ssp_api_key', 24 * 60 * 60),
        'webengage_esp_api_key': ('settings_webengage_esp_api_key', 24 * 60 * 60),
        'webengage_journey_api_key': ('settings_webengage_journey_api_key', 24 * 60 * 60),
        'send_new_device_sms_notification': ('settings_send_new_device_sms_notification', 5 * 60),
        'send_new_device_email_notification': ('settings_send_new_device_email_notification', 5 * 60),
        'feature_login': ('settings_feature_login', 60),
        'feature_login_ip_blacklist': ('settings_feature_login_ip_blacklist', 10 * 60),
        'mobile_login': ('settings_mobile_login', 5 * 60),
        'mobile_register': ('settings_mobile_register', 5 * 60),
        'email_register': ('settings_email_register', 5 * 60),
        'mobile_forget_password': ('settings_mobile_forget_password', 5 * 60),
        'prices_binance': ('binance_prices', None),
        'prices_binance_futures': ('settings_prices_binance_futures', None),
        'prices_binance_btc': ('settings_prices_binance_btc', None),
        'prices_binance_last_update': ('settings_prices_binance_last_update', None),
        'prices_binance_futures_last_update': ('settings_prices_binance_futures_last_update', None),
        'liquidity_pool_day_in_row_factor': ('settings_liquidity_pool_day_in_row_factor', 60 * 60),
        'kyc_skip_email': ('settings_kyc_skip_email', 2 * 60),
        'social_trade_fee_boundary': ('settings_social_trade_fee_boundary', 60),
        'staking_v1_end_staking': ('settings_staking_v1_end_staking', 60),
        'staking_use_api_dual_write': ('settings_staking_use_api_dual_write', 60),
        'staking_use_cronjob_dual_write': ('settings_staking_use_cronjob_dual_write', 60),
        'abc_currencies': ('settings_abc_currencies', 60 * 5),
        'abc_minimum_debt': ('settings_abc_minimum_debt', 60 * 5),
        'abc_is_activated_apis': ('settings_abc_is_activated_apis', 5 * 60),
        'abc_test_net_providers': ('settings_abc_test_net_providers', 60 * 5),
        'abc_use_restriction_internal_api': ('settings_abc_use_restriction_internal_api', 60 * 5),
        'abc_use_send_otp_internal_api': ('settings_abc_use_send_otp_internal_api', 60 * 5),
        'abc_use_verify_otp_internal_api': ('settings_abc_use_verify_otp_internal_api', 60 * 5),
        'abc_use_notification_kafka': ('settings_abc_use_notification_kafka', 60 * 5),
        'abc_use_market_stats_api': ('settings_abc_use_market_stats_api', 60 * 5),
        'abc_debit_recon_enabled': ('settings_abc_debit_recon_enabled', 60 * 5),
        'abc_debit_recon_ftp_process_enabled': ('settings_abc_debit_recon_ftp_process_enabled', 60 * 5),
        'abc_debit_recon_settlement_evaluation_enabled': (
            'settings_abc_debit_recon_settlement_evaluation_enabled',
            60 * 5,
        ),
        'abc_debit_recon_settlement_process_enabled': ('settings_abc_debit_recon_settlement_process_enabled', 60 * 5),
        'abc_debit_recon_settlement_process_reverse_enabled': (
            'abc_debit_recon_settlement_process_reverse_enabled',
            60 * 5,
        ),
        'vandar_withdraw_max_fee': ('settings_vandar_withdraw_max_fee', 2 * 60),
        'abc_use_wallet_transfer_internal_api': ('settings_abc_use_wallet_transfer_internal_api', 60 * 5),
        'abc_use_rial_withdraw_request_internal_api': ('settings_abc_use_rial_withdraw_request_internal_api', 60 * 5),
        'abc_use_wallet_list_internal_api': ('settings_abc_use_wallet_list_internal_api', 60 * 5),
        'abc_use_internal_user_eligibility': ('settings_abc_use_internal_user_eligibility', 60 * 5),
        'abc_use_internal_user_profile_api': ('settings_abc_use_internal_user_profile_api', 60 * 5),
        'abc_use_transaction_batch_create_internal_api': (
            'settings_abc_use_transaction_batch_create_internal_api',
            60 * 5,
        ),
        'abc_enable_debit_weekly_invoice_cron': ('settings_abc_enable_debit_weekly_invoice_cron', 60 * 5),
        'abc_debit_wallet_enabled': ('settings_abc_debit_wallet_enabled', 60 * 5),
        'abc_debit_internal_wallet_enabled': ('settings_abc_debit_internal_wallet_enabled', 60 * 5),
        'abc_use_internal_users_update_cron': ('settings_abc_use_internal_users_update_cron', 60 * 5),
        'abc_debit_card_creation_enabled': ('settings_abc_debit_card_creation_enabled', 60 * 5),
        'abc_debit_card_initiate_transaction_enabled': ('settings_abc_debit_card_initiate_transaction_enabled', 60 * 5),
        'abc_margin_call_sentry_transaction_enabled': ('settings_abc_margin_call_sentry_transaction_enabled', 60 * 15),
        'abc_wallet_cache_read_enabled': ('settings_abc_wallet_cache_read_enabled', 60 * 15),
        'abc_wallet_cache_write_enabled': ('settings_abc_wallet_cache_write_enabled', 60 * 15),
        'abc_wallets_cache_consistency_checker_enabled': (
            'settings_abc_wallets_cache_consistency_checker_enabled',
            60 * 15,
        ),
        'earn_get_abc_wallets_by_internal_api': ('settings_earn_get_abc_wallets_by_internal_api', 60 * 5),
        'vandar_withdraw_max_settlement': ('settings_vandar_withdraw_max_settlement', 2 * 60),
        'max_rial_withdrawal': ('settings_max_rial_withdrawal', 2 * 60),
        'max_verified_withdrawal_request': ('settings_max_verified_withdrawal_request', 2 * 60),
        'max_new_withdrawal_request': ('settings_max_new_withdrawal_request', 2 * 60),
        'verification_providers': ('settings_verification_providers', 1 * 60),
        'scrubber_sensitive_fields': ('settings_scrubber_sensitive_fields', 2 * 60 * 60),
        'is_kafka_enabled': ('settings_kafka_broker_enabled', 1 * 60),
        'is_sms_logging_enabled': ('settings_is_sms_logging_enabled', 1 * 60),
        'is_sms_broker_enabled': ('settings_is_sms_broker_enabled', 1 * 60),
        'is_notification_logging_enabled': ('settings_is_notification_logging_enabled', 1 * 60),
        'is_notification_broker_enabled': ('settings_is_notification_broker_enabled', 1 * 60),
        'is_email_logging_enabled': ('settings_is_email_logging_enabled', 1 * 60),
        'is_email_broker_enabled': ('settings_is_email_broker_enabled', 1 * 60),
        'direct_debit_min_amount_in_deposit': ('settings_direct_debit_min_amount_in_deposit', 1 * 60),
        'direct_debit_testnet_client_id': ('settings_direct_debit_test_net_client_id', 5 * 60),
        'direct_debit_testnet_client_secret': ('settings_direct_debit_testnet_client_secret', 5 * 60),
        'direct_debit_testnet_base_url': ('settings_direct_debit_testnet_base_url', 5 * 60),
        'direct_debit_testnet_app_key': ('settings_direct_debit_testnet_app_key', 5 * 60),
        'direct_deposit_skip_banks_sync': ('settings_direct_deposit_skip_banks_sync', 5 * 60),
        'direct_debit_throttled_banks': ('settings_direct_debit_throttled_banks', 1 * 60),
        'direct_debit_check_feature_flag': ('settings_direct_debit_check_feature_flag', 10 * 60),
        'django_captcha_settings': ('settings_django_captcha_setting', 2 * 60),
        'captcha_usage_configs': ('settings_captcha_usage_types', 2 * 60),
        'captcha_usage_configs_v2': ('settings_captcha_usage_types_v2', 2 * 60),
        'captcha_pick_method': ('settings_captcha_pick_method', 2 * 60),
        'captcha_arcaptcha_base_url': ('settings_captcha_arcaptcha_base_url', 2 * 60),
        'smsir_new_api_active_templates_list': ('settings_smsir_new_api_active_templates_list', 2 * 60),
        'email_backends': ('settings_email_backends', 2 * 60),
        'webengage_stopped_events': ('settings_webengage_stopped_events', 2 * 60),
        'withdraw_otp_email_task_countdown': ('settings_withdraw_otp_email_task_countdown', 2 * 60),
        'is_enabled_esp': ('settings_is_enabled_esp', 1 * 60),
        'is_enabled_ssp': ('settings_is_enabled_ssp', 1 * 60),
        'merge_daily_max_request_count': ('settings_merge_daily_max_request_count', 20 * 60),
        'merge_max_request_count': ('settings_merge_max_request_count', 20 * 60),
        'internal_ip_whitelist': ('settings_internal_ip_whitelist', 1 * 60),
        'market_execution_disabled_market_list': ('settings_market_execution_disabled_market_list', 1 * 60),
        'capture_matcher_sentry_transaction': ('settings_capture_matcher_sentry_transaction', 1 * 60),
        'ideposit_nobitex_destination_iban': ('settings_ideposit_nobitex_destination_iban', 1 * 60),
        'cobank_toman_access_token': ('settings_cobank_toman_access_token', 10 * 60),
        'cobank_toman_refresh_token': ('settings_cobank_toman_refresh_token', 10 * 60),
        'cobank_jibit_access_token': ('settings_cobank_jibit_access_token', 10 * 60),
        'cobank_jibit_refresh_token': ('settings_cobank_jibit_refresh_token', 10 * 60),
        'cobank_qa_test_server': ('settings_cobank_qa_test_server', 10 * 60),
        'cobank_check_feature_flag': ('settings_cobank_check_feature_flag', 10 * 60),
        'cobank_card_check_feature_flag': ('settings_cobank_card_check_feature_flag', 10 * 60),
        'is_enabled_logstash_logger': ('settings_is_enabled_logstash_logger', 1 * 60),
        'active_campaigns': ('settings_active_campaigns', 10 * 60),
        'campaigns': ('settings_campaigns', 10 * 60),
        'referral_fee_restrictions': ('referral_fee_restrictions', 10 * 60),
        'marketmaker_sentry_transactions_capture_sample_rate': (
            'settings_marketmaker_sentry_transactions_capture_sample_rate',
            1 * 60,
        ),
        'is_enabled_celery_monitoring': ('settings_is_enabled_celery_monitoring', 1 * 60),
        'celery_monitoring_sample_rate': ('settings_celery_monitoring_sample_rate', 1 * 60),
        'is_enabled_celery_running_monitoring': ('settings_is_enabled_celery_running_monitoring', 1 * 60),
        'concurrent_matcher_status': ('settings_concurrent_matcher_status', 2 * 60),
        'testnet_external_exchange_prices_base_url': ('settings_testnet_external_exchange_prices_base_url', 5 * 60),
        'finnotech_api_access_token': ('settings_finnotech_api_access_token', 2 * 60),
        'liquidator_enabled_markets': ('settings_liquidator_enabled_markets', 2 * 60),
        'metrics_handler': ('settings_metrics_handler', 2 * 60),
    }

    CACHEABLE_PREFIXES = CacheableSettingPrefixes

    FEATURE_AUTO_KYC = 'auto_key'

    key = models.CharField(max_length=255, unique=True)
    value = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = 'تنظیمات سیستم'
        verbose_name_plural = verbose_name

    @classmethod
    def is_cacheable(cls, key: str) -> bool:
        for prefix in cls.CACHEABLE_PREFIXES:
            if key.startswith(prefix.value):
                return True

        return False

    @classmethod
    def get(cls, key, default=None):
        is_cacheable = cls.is_cacheable(key)

        if is_cacheable:
            cached_date = cache.get(f'setting_{key}')
            if cached_date is not None:
                return cached_date

        s = cls.objects.get_or_create(key=key, defaults={'value': default})[0]

        if is_cacheable:
            cache.set(f'setting_{key}', s.value, timeout=60)

        return s.value

    @classmethod
    @transaction.atomic
    def get_many(cls, keys: List[str], default=None) -> Dict[str, str]:
        from exchange.base.logging import report_exception

        cacheable_keys = [key for key in keys if cls.is_cacheable(key)]

        cache_keys = [f'setting_{key}' for key in cacheable_keys]
        cached_data = cache.get_many(cache_keys)

        if cached_data and len(cached_data) == len(keys):
            return cls.extract_cache_data(cached_data)

        missing_keys = {key for key in keys if f'setting_{key}' not in cached_data}
        setting_instances = list(cls.objects.filter(key__in=missing_keys))

        missing_keys -= {instance.key for instance in setting_instances}
        if missing_keys:
            missing_instances = [cls(key=key, value=default) for key in missing_keys]
            try:
                cls.objects.bulk_create(missing_instances, ignore_conflicts=True)
            except InternalError:
                report_exception()
            setting_instances += missing_instances

        to_be_cached_settings = {
            f'setting_{instance.key}': instance.value
            for instance in setting_instances
            if cls.is_cacheable(instance.key)
        }
        cache.set_many(to_be_cached_settings, timeout=60)

        fetched_settings = {instance.key: instance.value for instance in setting_instances}
        cached_result = cls.extract_cache_data(cached_data)

        return {**fetched_settings, **cached_result}

    @classmethod
    def extract_cache_data(cls, data: Dict[str, str]) -> Dict[str, str]:
        result = {}
        for key in data:
            result[key[len('setting_') :]] = data[key]

        return result

    @classmethod
    def get_value(cls, key, default=None):
        cache_settings = cls.RELATED_CACHE_KEYS.get(key)
        if cache_settings:
            cached_value = cache.get(cache_settings[0])
            if cached_value:
                return cached_value
        s = cls.objects.get_or_create(key=key, defaults={'value': default})[0]
        if cache_settings:
            cache.set(cache_settings[0], s.value, cache_settings[1])
        return s.value

    @classmethod
    def get_decimal(cls, key, default='0'):
        return Decimal(cls.get(key, default))

    @classmethod
    def get_float(cls, key, default='0'):
        return float(cls.get_value(key, default=default))

    @classmethod
    def get_flag(cls, key, default='no'):
        return cls.get(key, default=default) == 'yes'

    @classmethod
    def get_trio_flag(cls, key, default='no', third_option_value=None):
        value = cls.get(key, default=default)
        if value == 'yes' or (value == 'auto' and third_option_value):
            return True
        return False

    @classmethod
    def is_disabled(cls, key):
        return cls.get(key, default='enabled') == 'disabled'

    @classmethod
    def get_json_object(cls, key, default=None):
        return json.loads(cls.get(key, default=default))

    @classmethod
    def get_cached_json(cls, key: str, default=None):
        """Return a settings value, using JSON for saving and loading the value,
        and a default caching time of one minute.

        Note: "None" can be used for default value, but no caching is done while the settings
        value is None.
        """
        cache_key_and_timeout = cls.RELATED_CACHE_KEYS.get(key)
        if cache_key_and_timeout is None:
            cache_key = 'settings_' + key
            cache_timeout = 60
        else:
            cache_key, cache_timeout = cache_key_and_timeout

        cached_value = cache.get(cache_key)
        if cached_value is not None:
            return cached_value
        try:
            settings_obj = cls.objects.get(key=key)
        except cls.DoesNotExist:
            settings_obj = cls.objects.create(key=key, value=json.dumps(default))
        value = json.loads(settings_obj.value or 'null')
        if value is None:
            value = default
        else:
            cache.set(cache_key, value, cache_timeout)
        return value

    @classmethod
    def set_cached_json(cls, key: str, value: Union[dict, list]):
        """Could be used for storing cacheable 'dict' or 'list' Settings.
        default cache timeout is one minute.
        """
        cache_key_and_timeout = cls.RELATED_CACHE_KEYS.get(key)
        if cache_key_and_timeout is None:
            cache_key = 'settings_' + key
            cache_timeout = 60
        else:
            cache_key, cache_timeout = cache_key_and_timeout
        cache.set(cache_key, value, cache_timeout)
        if cls.objects.filter(key=key).update(value=json.dumps(value)) == 0:
            cls.objects.create(
                key=key,
                value=json.dumps(value),
            )

    @classmethod
    def get_dict(cls, key):
        return cls.get_json_object(key, default='{}')

    @classmethod
    def get_datetime(cls, key, default=None):
        from .parsers import parse_iso_date
        return parse_iso_date(cls.get(key)) or default

    @classmethod
    def get_list(cls, key):
        return cls.get_json_object(key, default='[]')

    @classmethod
    def set(cls, key, value):
        try:
            s = cls.objects.get(key=key)
        except cls.DoesNotExist:
            s = cls(key=key)
        s.value = str(value)
        s.save()
        # Invalidate related caches
        cache_settings = cls.RELATED_CACHE_KEYS.get(key)
        if cache_settings:
            cache.set(cache_settings[0], str(value), cache_settings[1])

    @classmethod
    def set_dict(cls, key, value):
        cls.set(key, json.dumps(value))

    @classmethod
    def set_datetime(cls, key, value):
        cls.set(key, value.isoformat())

    @classmethod
    def is_feature_active(cls, feature: str) -> bool:
        """
        Check if a feature is enabled in Settings.
        """
        feature_cache_key = f'is_{feature}_feature_enabled'
        feature_setting = cache.get(feature_cache_key)
        if feature_setting is None:
            feature_key = f'{feature}_feature_status'
            feature_setting = not cls.is_disabled(feature_key)
            cache.set(feature_cache_key, feature_setting, 600)
        return feature_setting


class Log(LogModelMixin, models.Model):
    LOG_TYPE = 'log'

    CATEGORY_CHOICES = Choices(
        (0, 'general', 'general'),
        (1, 'update', 'update'),
        (2, 'notice', 'notice'),
        (3, 'history', 'history'),
    )
    MODULE_CHOICES = Choices(
        (0, 'general', 'general'),
        (1, 'wallet', 'wallet'),
        (2, 'market', 'market'),
        (3, 'shetab', 'shetab'),
        (4, 'settlement', 'settlement'),
        (5, 'apicall', 'apicall'),
        (6, 'cache', 'cache'),
        (7, 'authentication', 'authentication'),
        (8, 'webengage', 'webengage'),
        (9, 'fcm_notification', 'fcm_notification'),
    )
    LEVEL_CHOICES = Choices(
        (0, 'NOTSET', 'NOTSET'),
        (10, 'DEBUG', 'DEBUG'),
        (20, 'INFO', 'INFO'),
        (30, 'WARNING', 'WARNING'),
        (40, 'ERROR', 'ERROR'),
        (50, 'CRITICAL', 'CRITICAL'),
    )
    RUNNER_CHOICES = Choices(
        (0, 'generic', 'generic'),
        (1, 'workers', 'workers'),
        (2, 'cron', 'cron'),
        (3, 'matcher', 'matcher'),
        (4, 'autotrader', 'autotrader'),
        (5, 'stats', 'stats'),
        (6, 'telegram', 'telegram'),
        (7, 'kraken', 'kraken'),
        (8, 'deposit', 'deposit'),
        (9, 'api', 'api'),
        (10, 'admin', 'admin'),
        (11, 'apicall', 'apicall'),
        (12, 'celery', 'celery'),
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    level = models.IntegerField(choices=LEVEL_CHOICES, default=LEVEL_CHOICES.DEBUG)
    category = models.IntegerField(choices=CATEGORY_CHOICES, default=CATEGORY_CHOICES.general)
    module = models.IntegerField(choices=MODULE_CHOICES, default=MODULE_CHOICES.general)
    runner = models.IntegerField(choices=RUNNER_CHOICES, default=RUNNER_CHOICES.generic)
    message = models.CharField(max_length=1000, default='', blank=True)
    details = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'لاگ سیستم'
        verbose_name_plural = verbose_name

    def log_message(self) -> str:
        return self.message

    def log_params(self):
        return model_to_dict(self)


class IPLogged(models.Model):
    ip = models.GenericIPAddressField(null=True, blank=True)
    is_iranian = models.BooleanField(default=True)

    class Meta:
        abstract = True

    def fill_ip_from_request(self, request):
        from exchange.security.models import KnownIP

        ip = get_client_ip(request)
        self.ip = ip[0] if ip else None
        country = get_client_country(request)
        if country == 'IR':
            self.is_iranian = True
        else:
            ip_details = KnownIP.inspect_ip(self.ip)
            self.is_iranian = ip_details['country'] == 'IR'


class ObjectReference(models.Model):
    MODULES = Choices(
    )
    ref_module = models.IntegerField(choices=MODULES, null=True, blank=True)
    ref_id = models.IntegerField(null=True, blank=True)

    class Meta:
        abstract = True


class Exchange:
    NONE = 0
    KRAKEN = 1
    BINANCE = 2
    USD = 3
    NOBITEX = 4
    BINANCE_FUTURES = 5
    BINANCE_MARGIN = 6
    OKX_SPOT = 7
    OKX_FUTURES = 8

    CHOICES = [
        [NONE, 'None'],
        [KRAKEN, 'Kraken'],
        [BINANCE, 'BinanceSpot'],
        [USD, 'USD'],
        [NOBITEX, 'Nobitex'],
        [BINANCE_FUTURES, 'BinanceFutures'],
        [BINANCE_MARGIN, 'BinanceMargin'],
        [OKX_SPOT, 'OkxSpot'],
        [OKX_FUTURES, 'OkxFutures'],
    ]


def get_exchange_name(e: int) -> str:
    for exchange, exchange_name in Exchange.CHOICES:
        if e == exchange:
            return exchange_name
    return None


def has_changed_field(change_dict: dict, field_name: str, update_fields: Optional[Iterable]):
    return field_name in change_dict and (
        update_fields is None or field_name in update_fields
    )


class APILog(models.Model):
    timestamp = models.DateTimeField(db_index=True)
    path = models.CharField(max_length=255, db_index=True)
    method = models.CharField(max_length=10)
    src_ip = models.CharField(max_length=45)
    process_time = models.PositiveIntegerField()
    server = models.CharField(max_length=32)
    is_internal = models.BooleanField(default=False)
    status = models.IntegerField(null=True, blank=True)
    src_service = models.CharField(max_length=32, blank=True, default='')
    extras = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f'{self.method} {self.path} - {self.status} - {self.src_ip}'
