import datetime
import os
import socket
import sys
from copy import deepcopy
from decimal import Decimal

import django.utils.translation as original_translation
import pytz
import sentry_sdk
from celery import signals
from decouple import config as decouple_config
from django.utils.translation import gettext_lazy
from google.oauth2 import id_token
from sentry_sdk import configure_scope
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration

from exchange.accounts.fetch_google_oauth2_certs import _fetch_google_oauth2_certs
from exchange.base.config import CONFIG_OPTIONS
from exchange.oauth.constants import Scopes

# Monkypaching
original_translation.ugettext_lazy = gettext_lazy
id_token._fetch_certs = _fetch_google_oauth2_certs

# Autoconf
SERVER_NAME = socket.gethostname()
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
IS_CI_RUNNER = bool(os.environ.get('CIRUNNER'))
IS_TEST_RUNNER = 'pytest' in sys.modules or len(sys.argv) > 1 and sys.argv[1] == 'test'
RUN_ONLY_BLOCKCHAIN_CRONS = bool(os.environ.get('ONLY_BLOCKCHAIN_CRONS'))
BLOCKCHAIN_SERVER = RUN_ONLY_BLOCKCHAIN_CRONS
DB_PORT = os.environ.get('DBPORT')
if DB_PORT and DB_PORT.startswith('54'):
    DB_PORT = int(DB_PORT)
else:
    DB_PORT = 5432
ENV = os.environ.get('ENV') or 'debug'
DEBUG = ENV == 'debug'
IS_PROD = ENV == 'prod'
IS_TESTNET = ENV == 'testnet'
IS_VIP = bool(os.environ.get('IS_VIP'))
NO_INTERNET = True
USE_REDIS2 = IS_PROD and os.environ.get('REDIS2') != 'no'
IS_INTERNAL_INSTANCE = bool(os.environ.get('IS_INTERNAL_INSTANCE')) or IS_TESTNET

# Versioning
RELEASE_VERSION = 'v7.5.0'
CURRENT_COMMIT = '2118948c'

# URLs
DEBUG_API_URL = 'http://127.0.0.1:8000/'
TESTNET_API_URL = 'https://testnetapi.nobitex.ir/'
PROD_API_URL = 'https://api.nobitex1.ir/'
PROD_FRONT_URL = 'https://nobitex.ir/'
TESTNET_FRONT_URL = 'https://testnet.nobitex.ir/'
PROD_DOMAINS = ['nobitex.ir', 'nobitex1.ir', 'nobitex.net']
if IS_PROD:
    ALLOWED_HOSTS = ['api.{}'.format(domain) for domain in PROD_DOMAINS]
    ALLOWED_HOSTS += ['api2.nobitex.ir', 'api-l.nobitex1.ir', 'api-h.nobitex1.ir']
elif IS_TESTNET:
    ALLOWED_HOSTS = ['testnetapi.nobitex.ir', 'testnetapi.nobitex.net']
else:
    ALLOWED_HOSTS = ['127.0.0.1']
ADMIN_URL = 'https://admin.nxbo.ir'
if DEBUG:
    ADMIN_URL = 'http://127.0.0.1:8000'
elif IS_TESTNET:
    ADMIN_URL = 'https://testnetadmin.nxbo.ir'

# Feature Flags
LOAD_LEVEL = 8
LAST_ACCESSIBLE_TRANSACTION_ID = 890_000_000 if IS_PROD else 0  # Day 1400
LAST_ACCESSIBLE_TRANSACTION_DATE = datetime.datetime.fromisoformat(
    '2021-12-16 22:53:49.266002+03:30' if IS_PROD else '2008-09-15 00:00:00+00:00',
)
LAST_RECENT_TRANSACTION_ID = 956_000_000 if IS_PROD else 0  # Esfand 1400
LAST_RECENT_TRANSACTION_DATE = datetime.datetime.fromisoformat(
    '2022-02-19 02:30:07.457732+03:30' if IS_PROD else '2008-09-15 00:00:00+00:00',
)
LAST_SUPPORTED_ANDROID_VERSION = '4.2.0'
# Technical and Special flags only used for some tests or special tunings
ALLOW_SMALL_ORDERS = False
DISABLE_ORDER_PRICE_GUARD = IS_TEST_RUNNER or not IS_PROD
DISABLE_RECAPTCHA = IS_TEST_RUNNER
FULL_LOGGING = not IS_PROD
SET_USER_PROPERTIES_PR = 0.2
# Enabled features
FORCE_SHETAB_CARD_IN_GATEWAY = True
CACHE_VIP_LEVEL = True
SEGWIT_ENABLED = True
MINER_ENABLED = True
ASYNC_TRADE_COMMIT = not IS_TEST_RUNNER
PREVENT_INTERNAL_TRADE = IS_PROD
# Address Types Launch
ADDRESS_CONTRACT_ENABLED = True
ADDRESS_CONTRACT_V2_ENABLED = True
EOA_V1_ENABLED = True

ENABLE_STOP_ORDERS = True
ENABLE_HOT_WALLET_DIFF = True  # Diff hot wallet: To allow crons and websockets to update withdraws status while getting one block info
USE_PROMETHEUS_CLIENT = False  # for blockchain
IS_EXPLORER_WRAPPER_USES_ONLY_SUBMODULE = False
IS_EXPLORER_SERVER = os.environ.get('IS_EXPLORER_SERVER', '').lower() == 'true'
MAIN_SERVER_HTTP_CLIENT = 'https://explorer.nxbo.ir'
DIFF_SERVER_HTTP_CLIENT = 'https://explorer.nxbo.ir'
CERT_KEY_PATH = os.path.join(DATA_DIR, 'explorer.key')
CERT_FILE_PATH = os.path.join(DATA_DIR, 'explorer.crt')

# Timings
NOBITEX_PRE_LAUNCH = datetime.datetime(2017, 12, 10, 6, 30, 0, 0, pytz.utc)
NOBITEX_LAUNCH = datetime.datetime(2018, 3, 3, 0, 0, 0, 0, pytz.utc)
LAST_ADDRESS_ROTATION = datetime.datetime(2021, 6, 7, 0, 0, 0, 0, pytz.utc)
LAST_ADDRESS_ROTATION_LTC = datetime.datetime(2021, 8, 15, 11, 42, 0, 0, pytz.utc)
BSC_NETWORK_LAUNCH = datetime.datetime(2021, 9, 29, 12, 0, 0, 0, pytz.utc)

# Features being tested
DEPOSIT_MIN_CHECK_ENABLED = not IS_PROD
DEPOSIT_FEE_ENABLED = not IS_PROD
CHECK_OTP_DIFFS = not IS_PROD
DO_MERGE_EXCHANGE_TRADES = True
WITHDRAW_CREATE_TX_VERIFY = not IS_PROD
WITHDRAW_ENABLE_CANCEL = True
WITHDRAW_FRAUD_ENABLED = False

# Performance Parameters
CHART_STORAGE_TIME = None if IS_PROD else 604800
TRADING_MINIMIZE_CACHE_USE = True

# Business Logic Parameters
TRADER_PLAN_MONTHLY_LIMIT = 1
GIFT_CARD_PHYSICAL_FEE = Decimal('36_000_0')
GIFT_CARD_PHYSICAL_PRINT_FEE = Decimal('16_000_0')
GIFT_CARD_PHYSICAL_POSTAL_FEE = Decimal('20_000_0')
GIFT_CARD_SEAL_FEE = Decimal('2_000_0')

# Secret Management
MASTER_KEY = (os.environ.get('MASTERKEY') or '').encode('ascii')


def secret_string(s, testnet=None, encoding='ascii'):
    from cryptography.fernet import Fernet
    encryption_key = MASTER_KEY
    if IS_TESTNET:
        secret_string = testnet
    else:
        secret_string = s
    if not encryption_key or not secret_string:
        return ''
    f = Fernet(encryption_key)
    return f.decrypt(secret_string.encode(encoding)).decode(encoding)


def encrypt_secret_string(s, encoding='ascii'):
    from cryptography.fernet import Fernet
    if not MASTER_KEY:
        return s
    f = Fernet(MASTER_KEY)
    return f.encrypt(s.encode(encoding)).decode(encoding)


# Secrets
if IS_PROD:
    SECRET_KEY = secret_string(
        'gAAAAABboN0f-dXPWDzgpKHipftqwoUjLjZ9H8nzWQ9_XPAf7yNSVPxtz5c9MRP_S0OCZp52nZb70xYegQiSdy4ioAQRLyfwSAFrsmxGtbZRZl_RYDuFt8EGBbtF_OMifDhQbwBNM4fWkwO1ttCpQIONmMrcWxxwSQ==')
elif IS_TESTNET:
    SECRET_KEY = '1]UotI)hOa9[I&~K&_wlG8.d?}`hRWI41<o2"tK5a5hu84>j*XJl5j"e+e82'
else:
    SECRET_KEY = 'test'
if IS_PROD:
    NOTIFICATIONS_BOT_TOKEN = secret_string(
        'gAAAAABboN2vayDg4e7J6wxnp8lKJ-H_yyWC6pL7N49a8AlDWLqJYRfQGpNbfrpKTkuYEbXCqq6QJejY6o0vHfvR5LZmNKc5OoqxUgqp81NnIk0HdhL_-3lxB86_aSIF_NA1LozSuABH')
else:
    NOTIFICATIONS_BOT_TOKEN = '555470091:AAGOrbW97TFr7wVgGiJqzHq-ZssEBZxG2Zs'
if IS_PROD:
    LND_SERVER_API_KEY = secret_string(
        'gAAAAABiI0ubGU_ib46pi0CzPyUvWX3y3xa0OxHFf6tAsd2XIowc-aJ_-UvDU7k0DfvDQjxHS0BRYLJeArpFKDcz7FBagmfyZznMofkgNtnTC8_uAMZW7nE=')
else:
    LND_SERVER_API_KEY = 'testauth'

# Internal IPs
NOBITEX_SERVER_IPS = {
    '' if IS_PROD else '31.214.174.64/28',  # Cluster IP
    '' if IS_PROD else '213.233.178.43',  # Server
}

# Internal JWT Public Key
if IS_PROD:
    BLACKLIST_JWTS = set()
    INTERNAL_JWT_PUBLIC_KEYS = {
        '''-----BEGIN PUBLIC KEY-----
MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEAu5XG2JAxjfuhDcOvVOlo
lZekZ/HOEnHFMgPggm51Wo1nOwTaHMpUSIZfcLTKMic9tarvT+BM8jiZCgrh/wXZ
NPC6aOe9iPc5e1fq1oy4+UKkH/WFCnaL0HIuiGn2TBFNYN3YKY6GhPJRiwuJ28JZ
eARRFv8+e3di2a3n1jkgjU8CBt3ONUWmVAiB2k24kWtypxxBNVcR+6eZ3POv3NuI
/QO67uqpKmU2BJbawbqMu05Uw8mXaiFvlbcbbHYiH8PchyT/B2wyOnd8VkRiLngt
l9I2tOB1ZemP+a/5eW1F47OiAOdEX0g3YVWnoMms7Rt8acBuIcKC/mNX1BxwoVGS
stbfCzwpKj+qpyqhIA2NVLhCdwFpXtJOA5TPE899LIx8uOKcpmQW+LChye7J9sf4
uENaxzHsNCAy1nLdxTSjLuyjsLA9wxDGOUjwBJTj2WBjoMmXQIUf58+K7G5Mse41
U/IiaU8r2dpqMOMLIBNUxF3dGPNNcHbYlzW9QkKoOo8dLHXatF8a8IGsuHj8oAJd
DPKleCEi/xjIs7bdersc5GdPZUPOZ1GwESKSkkd6fLy5hLJhKBYbw/190r9fd8eq
RBofzgxFwJuYhbfqJoqKMUPKtHo7nWr6KzVAsfLlGAXNc051fnPwcPSDmvcGk75Q
iUfWtIa1j8r1i9LMmOW2L2sCAwEAAQ==
-----END PUBLIC KEY-----''',
    }
elif IS_TESTNET:
    BLACKLIST_JWTS = set()
    INTERNAL_JWT_PUBLIC_KEYS = {
        '''-----BEGIN PUBLIC KEY-----
MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEAvA5wNGpwUjt4aIbZBqML
k+z105voweLGfqNyFYFWR38WQOyQnYuQUr8eRj5gvF3/95jwqUXkLH+DblLcJnwJ
FPE+8HYPYHsfUr3vt7QK9wfgGf8RAd2z/nu592YrxkdRNdCo+yeYnlOMMUiQap1d
sPLtpGGjgG+P+IeqD1xF7roELUCO7366ffspbbA/ZDK428/yBl7OF3EdaVy6o4pT
V0BfSo5wyL9VjnjyV4SSL8vq7rLEfqZbcRhGl397pE4+03MMR61jHPtvjvuKkD8u
Iyx/siHmM4Esk/Naqjr4E0GQecf92fvfE9e4ZbKaSLJrmCz+14z+LdW2MwEHG9cq
Mo8beuxnwIYRA8WP2AplaGgI9fcY3zKdZbN90NWEspFThvh1ZxEelWtCKyi6cM96
ShgA9OzrSas8Oay/vmEav8sKY2GXk3T7eBYUWT/BzG7giTqF4yTKKYZKgDG5MO25
oRPZGPWgM0sNP+qQE1s7kEPhkdnw0KveeCb5k4Lp1vtothb7Vv4hnsdOrCotCXOR
sv7tec3zCm0Q3Am4hzjDjqBtcT33S3XfEYY9qdhVmdyX9WQyIgyg54Hqybd+DvbW
a2CWJEUkWdJNu0561+LFWJ1GJ1RPG+ahH1Aaz9xDiMokxRVog+5qUALkj1b7RXCH
6F7Euc44T0gQ35Kg46c80l8CAwEAAQ==
-----END PUBLIC KEY-----''',
    }
else:
    BLACKLIST_JWTS = set()
    INTERNAL_JWT_PUBLIC_KEYS = set()

# API Keys
ETHERSCAN_API_KEYS = [
    'KKT5ZNKJNPA8CXGJ9KQTIMVYT86YNESEHH',
] if not IS_VIP else [
    '8BWHU4ZUMK3VH8YXFSE4ST99JJ7UXK35JK',  # Habibi
    'CQZCC6X6QSR6181PWPFTRF2KXAV5X2HYCV',  # Habibi
]

ETHPLORER_API_KEYS = ['freekey']
CRYPTO_COMPARE_API_KEYS = [
    '6bf66e718b2a15e6b08b6c16dd802d6e2eef5a1489b635cbf86ed8808c9fb9aa',
    'f83a7af68ea31b85bc863883db3e5fe93d96d085c44a32e3decb18216b4e9ca5',
    # 'eabeb68ab00dd535baf3a2ca03b5545176ee69c614d90e2603111b07e620ba9b',
]
""" API Keys used for cryptoapis.io site
    Rate limit: 3/second, 500/day
    Multi-accounting is not allowed by this API.
"""
CRYPTOAPIS_API_KEYS = [
    '144ccb596effbe7ad347790de53c3aea7da45812',  # amiraliakbari@gmail.com
] if not IS_VIP else [
    'c2b336ad72ca68af2a236cb1f866f0313c2d31ee',  # Habibi
]

# Aptos
APTOS_CHAINBASE_API_KEY = [
    '2IOf2ZB1k5Vt0gu0uj5shM9PKNw', '2IOfpd4Cpl0CUyPwqA1aNnpd9uX',
    '2IOgBwdgpdHVETnGhWEq1w9cQpp', '2HRseB9nopi7KlZ5rkZ9tDDzuaw',
    '2J7o2EtcLRrE1NGx0CtvL3KLdYx'
] if not IS_VIP else [
    '2LH0ufgthl9fcFwZGjyrmhnokCi',  # Habibi+1
    '2LH16LaJbVjhzENZjtU457o0QLf',  # Habibi+2
    '2LH1KpqIWTyjJtIdd8n0IIvjoDY',  # Habibi+3
]

APTOS_NODEREAL_API_KEY = [
    'cf7eabe66f8c4a98bd261460968864ed', '7864c7c316764c738df5e627c257b5aa',
    'a5207730cf5041ffabaa9dd2b8ee2951', 'dece6790fccd440f9a18720434ecbf0f'
] if not IS_VIP else [
    '9bc68e8e52d64be0ba44fc3888d80e50',  # Habibi
    '54219cb0dcef4181973363ae0599a1be',  # Habibi
]

ARBITRUM_ARBISCAN_API_KEY = [
    'C37RH6WR8DPJCNM4B9U57Z8JDIVZ7WYUPT',
    'BH8KKIUBUEN9DWD976PD5DUMDZ9WJCEUVI',
    'Q7TP63MS6XFH4M92Q7UQXG2XIPPAF15E7A',
] if not IS_VIP else [
    'S6HDQJJNFR174JS2SHVUBFF25HQDPFMXE8',
]

ARBITRUM_COVALENTHQ_API_KEY = [
    'ckey_3a7e76d25cbf4392828933127bf',
] if not IS_VIP else [
    'cqt_rQMQwrwDrbhTkkpPcB747xkkqqtP',
]

# Blockcypher API Keys
BLOCKCYPHER_ENABLED = True
BLOCKCYPHER_API_KEYS = [
    'af4a77db4bae466e8dff0dbe19f25b94',
    '795fc1014344452c897bc9881b6c2ff7',
    'd0be29f912e34f269368e41b34343c42',
    # '3ad363f52c434ffaa333d595fb99d56d',  # amiraliakbari@gmail.com
    # 'd9b74cd3c7db439cb3424502031fc06e',  # ?
    # 'fc437d23e7d04edbb568bcff0af566e0',  # a.akbari@vidad.net
    # 'fd2c2d3424ed4c1aa33db29520c50b36',  # fateme.ragh@gmail.com
    # '3fe3009684934c6d82a99add854c028e',  # a.kharrazi@gmail.com
    # 'e6fda77185144230ba0eaa1a345cfe35',  # xanarahmani1998@gmail.com
]

BSCSCAN_API_KEY = [
    'BRQQN7IKA81SS1NZCETVBTI9GSECK19DJD',
] if not IS_VIP else [
    'IU3ZQEB48HKI2P9MVRWZM4VTCUHQ56X9XW',  # Habibi
    '5V67E7K1JF7W6Z166EJU9BNB7ZCMY3M1EG',  # Habibi
    'ZRACISHI3IJ1I9QC4JRHIQWA89PN5AACWF',  # Habibi
]

MORALIS_API_KEY = [
    'tiMRCpCdCIede1mKeVynUt3UDwzlbZgyMrRMM002XYjueC0exEW7aKpZoEw8i6CL',
    'Wlsuz3NH8bHvtg1HDbXPRIi5A3ksCruv3QfCvKpEF42kSZHLdLYJzfqSann8aI8P',
] if not IS_VIP else [
    'Pv22b1wzWbZtziOMX6MJYsIbIlmxdrLAkDI0fgjelV7z2Gbv8knt84vmZrVHaU9I',  # Habibi
]

SUBSCAN_API_KEY = [
    '9b9e71120870e176b88410a2e8c66f34',  # mehdi
    '2416923bb2b9866a1c3dc2ce3fcb982e',  # m.aghamir
    '7a39a6b2ac54aaf1bcc7d8ab107a745a',  # shahriar
    'eec09fceba2f70239d1b1e9001e1dfad',  # p.hasanizadeh
    'dee8b899eb964cb28a9c151d33668962',
] if not IS_VIP else [
    'a138a6261e4a4222dcd4a0cfc980586e',  # Habibi
    '9eedef99a52648b78b51081ec7fed7ca',  # Habibi
]

HEDERA_LWORKS_API_KEY = [
    '0ca97f501e1146fa9dd0e14bc509b9ed', 'ced7bae4b68d4dd6a95619498c1ee2cb',
    '2de6822848e8443cb95771e21ff2c995', '20c42e3b177946408a0f60eded69049a',
] if not IS_VIP else [
    'fbe830eff027435ba2096f977d69cd73',  # Habibi
    '5a4fab3718ee4fcc8bd3534e697be521',  # Habibi
]

# Solana QuickNode URL (20M request per month) This is just for production, use
# https://morning-late-bush.solana-mainnet.discover.quiknode.pro/ for testing purposes
# SOLANA_QUICK_NODE_URLS = 'https://billowing-bitter-water.solana-mainnet.quiknode.pro/e7d4c6685a99c5d77aeb08e3beacd3cded0db7c0/' if not IS_VIP else ''
SOLANA_QUICK_NODE_URLS = 'https://winter-spring-sunset.solana-mainnet.discover.quiknode.pro/a99581bace947f4b59ccfae74a495ad1f18a4fbe/'

SOLANA_ALCHEMY_URLS = [
    'https://solana-mainnet.g.alchemy.com/v2/ZB4MhPz7qnwwAK8kF6bXBVw_qHomL6YU',
    'https://solana-mainnet.g.alchemy.com/v2/sgFGPAyqiBwvqiEkXHiiSFYkVaNbFOro'
] if not IS_VIP else [
    'https://solana-mainnet.g.alchemy.com/v2/zAXPbOHQv5uZBUD1NG_nLbzip0WKZ5bM'
]
SOL_GETBLOCK_APIKEY = ['a9b62bb25ba34830ae28c9f7f2cf7bba', 'a9b62bb25ba34830ae28c9f7f2cf7bba']

SOLSCAN_APIKEY = [
    'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjcmVhdGVkQXQiOjE2ODA2MDY0NTU0ODAsImVtYWlsIjoiYmhhLjEzNzBAeWFob28uY29tIiwiYWN0aW9uIjoidG9rZW4tYXBpIiwiaWF0IjoxNjgwNjA2NDU1fQ.16A5te-K8663_sYI25rx9RABDbmgTLPWmBE0dhlQwiQ',
    'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjcmVhdGVkQXQiOjE2ODA2NzkxMzY0MTAsImVtYWlsIjoibWFuc29vcmUuc29sdGFuaUBnbWFpbC5jb20iLCJhY3Rpb24iOiJ0b2tlbi1hcGkiLCJpYXQiOjE2ODA2NzkxMzZ9.vS_bgUQOVQfdfrLVIAGXnO7jhRHRsdFlszvEJuagMlY'
] if not IS_VIP else [
    'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjcmVhdGVkQXQiOjE2ODA2NzkyODQzODUsImVtYWlsIjoia2FzcmF6YXJlaTM5QGdtYWlsLmNvbSIsImFjdGlvbiI6InRva2VuLWFwaSIsImlhdCI6MTY4MDY3OTI4NH0.eXcTN7YIau3R2_lra_CFHdCmMKAkbObCyWnp_Zm_Zfg'
]

SOLANABEACH_API_KEY = ['d33f5b95-1dbd-487e-914a-a42ce5673f7a']

# sonic explorer
SONIC_SONICSCAN_APIKEY = (
    [
        'TZK5BZUT59YQESURUWPNIUQWR32B7GTECT',
    ]
    if not IS_VIP
    else ['NDBNT916RCVRVXZY8DAJ7UAHDP5FJAT24D']
)

# avax explorer
AVALANCHE_OKLINK_API_KEY = ['e1aad00f-05d5-4965-af85-a27023a01bac']  # ['5efcf616-09b7-4c5f-8b7d-79d334aad2c5']
AVALANCHE_SCAN_API_KEY = (
    [
        'FARCUX1U11R6KHS89DVVUCIXG9ZZWR9NM7',
        'T9FHHJEA4J6XCSY61X7NB1W5QGU7MT8M3Y',
        'M8EQBDAT9A7PZF4115MFUKTMHI29MK8BAX',
        'UNF1XNA77S5D8VTC64IA78FYMDWHETND45',
        'MXHHKK7KW3ZQ5YSVK1TNMDJYHFKF985TFR',
    ]
    if not IS_VIP
    else [
        '31ASD144NZY8EB4BJP9I4C5E79GUYY3AMW',  # Habibi
        'RC9ZZNJP2RXV9TMGH2HT8CW6EMCPNSBZQ4',  # Habibi
        'VS4XDW7RVHZHPKFSRRIYMCE7T924ZANRIM',  # Habibi
    ]
)

AVAX_GET_BLOCK_API_KEY = [
    '9f3e0279-86c0-41d3-9a3e-eb295439006e', '7bf3be1a-344f-4da8-9e54-cab86fa5428d',
    '76d9699f-67e2-4bed-9628-77b794e95326', '55f0c3ad-3d53-4547-86a7-5dd1c88063fe',
    'aa60b4bc-d15c-4167-b1e4-cfdf28035fe9', '0555d552-e84d-450d-942c-72b4f8d6a66b'
]

GET_BLOCK_API_KEY = ['e473c695-0fb9-4886-b816-8c74a82d20d7']

ATOM_GETBLOCK_APIKEY = [
    '9f3e0279-86c0-41d3-9a3e-eb295439006e', '8d2d2c59-594c-4d57-ad4d-0d5b778a4eae',
    'ce21f58b-7bca-4555-a1e2-3fa4569bd2cb',
] if not IS_VIP else [
    '01084ad4-8090-431d-a981-395c2eaac449'
]

NEAR_GETBLOCK_APIKEY = ['5864466269d54c3eada1a0ec350854bf', '709bd6d9e18e4140b80baa8571154c57',
                        'fb6462138f704989b0f80fd8992299ea', ]

NEAR_BLOCKS_APIKEY = [
    '9F3072D2511246DEA5C77EFCBC478C2C',  # amirhosein
    'C66046F3FE1E404A9A0C4734E217C619',  # mojahed
    'A97F4390E1FA41E3944B3D43FDAABD85',  # kasra
    '4E1EB4F9B63E43BF8FA2A3C510AE8EBD',  # salarvandian
    '823C2C6CFC5245AB95D7941F898716C2',  # soltani
    '9087B7F43FEE4B59BAE2F52451214371',  # alireza
    # 'FF3DF9EF73AF408280AA5849F569AE8C', # kiarash
    # 'E093A3CEDFC249F4927ACAF7C033FE9A', # kiarash
    # 'E44E90E3CFDF4E38A3C034F2CBFD0C19', # mojahed
    # 'B040BA3B7CFC4D5CA6938129572AA706', # mojahed
]

BITQUERY_API_KEY = [
    'BQYbcPqMiyTHs4VRp5ZZ4hKsOMQbGPnh',
] if IS_VIP else [
    'BQYbcPqMiyTHs4VRp5ZZ4hKsOMQbGPnh',
]

POLARIS_API_KEY = '89a1c90a-f839-4b6d-8952-44cf60b1c527'
POLARIS_CARDANO_API_KEY = '61fc87f4-c918-4995-b383-ec278d98d21b'

FILECOIN_BITQUERY_API_KEY = [
    'BQYyk14Ym6j15N7qdVQ2iy3mTx5T274Q'  # kasra zareyi
] if IS_VIP else ['BQYJcUM7vjNNLnKwUP66RktVAi4sOpIT', 'BQYMh3UBWbQMGKnvqmoDch5CqAcz20av']

FLOW_BITQUERY_API_KEY = [
    'ory_at_buHulzFd-4iPQoSbJD8cy7_uVYs0N3MKSvfhpOMfhck.lVNAwpkztf7FmaEhR1436KFvPPESJaUM5PSD0xaYIK4'
]  # ['BQYbcPqMiyTHs4VRp5ZZ4hKsOMQbGPnh']

FLOW_SHROOM_API_KEYS = [
    '681f05a3-9c4f-428a-903f-7f56b7759754',
    '30a2b2f4-cdc3-45bf-9ebf-4b989a78e760',
]
if IS_VIP:
    FLOW_BITQUERY_API_KEY = [
        'BQY7dXOMpA9821goqSGaKkOje098XkZG',
    ]
    FLOW_SHROOM_API_KEYS = ['']

LTC_BITQUERY_API_KEY = ['BQYbcPqMiyTHs4VRp5ZZ4hKsOMQbGPnh']

ELROND_BITQUERY_API_KEY = [
    'BQYu4XD6mmEpwLFAH99lTiX5r9uhXsij'
] if IS_VIP else ['BQYDRTbHPkMw3I1SPxQXPOq7XexD21Gh', 'BQYpNkmXHL7lh8mIGsAnnyG3DgiDqAau']

# NowNodes API key
NOWNODES_API_KEY = 'sRWXErQgbZeUncX1Te7JzqS2BP8mfo8q' if not IS_VIP else 'fb624763-9b3f-4e36-adda-9855e8d1439a'

# Blockfrost API key
BLOCKFROST_API_KEY = (
    [
        # 'mainnet3tsH6ChY7xQr2pyKg9frWetMzMmD5Pma', 'mainnetjvG1N7VAFbQaAbv6Kvkjhx60M8jORVZt',
        # 'mainnetNNSH7bG2TtAzlxuXTFy8FOXLASm9W8mD'
        'mainnetQ8lxlE8JzBxoh6gQ6fysPlUWPJ2wYUMl',
        'mainnetNvyg1qiWkv4I1PRXHd4WyHlwK9KuVAGR',
        'mainnet6MsZ8MprAu2gaUVe3JMZJEmEMw2swfAq',
    ]
    if not IS_VIP
    else [
        'mainnetvvC8SoiLIVXy67D3LqE30frpwQKipdrb',  # Haniyeh Habibi
        'mainnetnWbRXvJ75zYUfTqaOkf3qJRiyQj8Z9k3',  # Mehdi Abdi
        'mainnetjIpDTWcyyNZZdz2uXqfvIEiP2UH5Kx3W',  # Hadi Dadjuy
    ]
)

# Infura API key
WS_INFURA_PROJECT_ID = [
    'd7b5d392abd14546ada1640ed45dea0b',
    '1e1413ee4cd54c6d882fbf2b48aabb0b'
] if not IS_VIP else [
    '40a05d3809c9471cbf3e0db059701a86',  # Habibi
]

WEB3_API_INFURA_PROJECT_ID = [
    '57df6bca71f147fb9931f74d02f00074',
    '20f0ce5d9ee84a47b2b7e9877a72911a'
] if not IS_VIP else [
    'e4edd0f3ac034becb3f9b50564651ad5',  # Habibi
]

# FTM API key
FTMSCAN_API_KEYS = (
    [
        'RQW4I6ZPG4NQZN9DEV7PYR261I5ATDKTGZ',
        'W556RKM9I5V1HE7YK2S5IWQT2CZGT55969',
        'W8IHX1YPFKP1XDYRR65K64S9SSBHPT52QN',
        'F8KSGSYDAR8YSGBWG2PF9SCFQ3CNDAKWY6',
    ]
    if not IS_VIP
    else [
        'S7SNV77EFF19WG5WKGQVMHT3IHBYU8FTDZ',  # Habibi
        'M5IV3QG5AIKGAG89CMVZ2Q1GR1UV57YXU9',  # Habibi
    ]
)
HARMONY_ANKER_API_KEY = ['fa86fd692db89a2fb13a9fef2d3cb4aebea8a613d9cae00fd4e1aa9627527c8b'] if not IS_VIP else []

STAKING_REWARDS_API_KEY = '5a3ec7a1-f786-4217-afea-4daaf1d9584b'

COVALENT_API_KEYS = (
    [
        # 'ckey_e42297ea06dd4988b985ae5c224',  # Zareyi
        # 'ckey_c21ad21439ab4148917a0192af2',  # Heydari
        'cqt_rQHbYFVTCwgPBPBW93Bc4rhdRqhD',  # ghaffari
        'cqt_rQ7JjxHmCWvXGPwRChpXgQkwphbx',  # soltani
        # 'cqt_rQpJq4tpMHDHYW6gkJGWFmyqkGKm',
        'cqt_rQ4YhG7JP8rGQbwF48W98rHgX4bp',  # habibi
        # 'cqt_rQRyCJwpdMcR9DWY469rBbJhRFfr',   # salarvandian
        # 'cqt_rQGfqT8mqp9WTKqDRY8MHyTC3Ybc',
        # 'cqt_rQVGRJgqG7TDxyymHWCJCDHQvVQ4',
    ]
    if not IS_VIP
    else [
    ]
)

POLYGANSCAN_API_KEY = [
    'XYDM7CBCK7AWV82DFVUSJRWYMENHNT57JW',
] if not IS_VIP else [
    'RR2F4YH99QNBISTKKSSVZ93MAY824XSE97',  # Habibi
    'DH2RPBG89J6V9YIEH32VRGPE56QG5BY93C',  # Habibi
    'EBJW4GER1HGEPAHQFQCCGVTMKIM14YMXUV',  # Habibi
]

BLOQ_CLOUD_API_KEYS = ['dove-trade-weapon'] if IS_VIP else ['hope-evil-cute']

TATUM_API_KEYS = [
    't-6697b2ead6756a001c05c626-642887a557574d43850f4e1d',
    't-6697bc79e36e57001c466b74-4c312942143440ecb6a9c922',
    't-6697bd86f37cd3001cf23b28-2990ac5b12694eb0b06a41ea',
    't-67c30786c3ec73aa75c3338b-1015c2ac1907462bad349f07',  # mohamad97mj3
    't-67c308a211b09977b382f094-34f87a6d6a97419796caa653',  # mohamad97mj4
]

# www.purestake.com algorand explorer
PURESTAKE_API_KEYS = [
    'dCf2xHk9UN8ohLTHf7WVg6eAJnKDnZwk7JO0kdrW'
] if not IS_VIP else [
    '0DFhZNMicF5bHFk81z9hw8fmdTgzFOwm34sn9IPL'  # Habibi
]

"""
    API Keys used for figment site (used for cosmos Network)
    3M requests allowed for each API key
"""
# Figment API does NOT support free api keys anymore, hence we can't have api keys for vip
# And better not to use it at all, to avoid usage in vip env empty string is returned
FIGMENT_API_KEY = [
    'bc61773ff9a4de176a26996e4ba53d66', '197548c474e6b692be49caefd3b46d1e',
    'd48b41b7568b0a2380721ced3ea9f325', '4cf118845258913181e6fff98a000fba',
    'ce9c6931140487a49d732c201927dab1', '10234459b8524f8998e76511edf50eb5',
] if not IS_VIP else ['']

"""
    API Keys used for figment site (used for near Network)
    3M requests allowed for each API key
"""
NEAR_FIGMENT_API_KEY = [
    'e6646e929cb9a180b5bdde7b2006d859',
    'd3d834d8761cf0c6675355083772937d', 'ad4c46168b29f2b68037eab280cf095e',
    'a81935fa822c9505610d4b195e4039f4', '814a0dee7f702d1885d3b0dc3c07fd76',
] if not IS_VIP else ['']

DOT_FIGMENT_API_KEY = [
    'b9673e359ba2c052788d03163998cdd7',
    'cdd44d14591bbf17071e67c8f660e9d9',
    '2838c302fc1ad313e03971d9c277a287',
] if not IS_VIP else ['']

DOT_FIGMENTRPC_API_KEY = ['b9673e359ba2c052788d03163998cdd7'] if not IS_VIP else ['']

# Ton
TON_API_APIKEY = [
    'Bearer eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhdWQiOlsiaGFuaXllaF9oYWJpYmkiXSwiZXhwIjoxODM4MjMxMTM2L'
    'CJpc3MiOiJAdG9uYXBpX2JvdCIsImp0aSI6Ilk2VVJRR0k3VDNPQktVNUlQNkhUM1RINyIsInNjb3BlIjoic2VydmVyIiwic3ViIj'
    'oidG9uYXBpIn0.KBwxgtJJ3holp5We-oSS9SHytQI4RjvN_2LsX5WHz9FRn6EIQPJHoI4pa5go7noeY-zJrflqw30THpFwfhKxBg',

    'Bearer eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhdWQiOlsia2FzcmFhX3phcmVpaSJdLCJleHAiO'
    'jE4MzY5MDM0MTcsImlzcyI6IkB0b25hcGlfYm90IiwianRpIjoiNUNBN1ZLQlEzTkdOREkzSEJFM0RRWFdDI'
    'iwic2NvcGUiOiJzZXJ2ZXIiLCJzdWIiOiJ0b25hcGkifQ.Vi_FRhu-xzI5tGDxZtKr-1z3QCZMbDjbEU3q6Ms'
    '36tAYldzOI8_K-Wmzk1mlLhMy3e7kKjl2NOMgwhdq1d_UAg',
] if not IS_VIP else [
    'Bearer eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhdWQiOlsiTmFzZXJpQm9yb3VqZW5pIl0sImV4cCI6MTgzODIz'
    'MTI2NiwiaXNzIjoiQHRvbmFwaV9ib3QiLCJqdGkiOiJCQzdBSVlTN0dRSjZFV0YyNUVEMkdKVUQiLCJzY29wZSI6InNlcnZl'
    'ciIsInN1YiI6InRvbmFwaSJ9.PCwpA30urHrShysr108H-kQy-zZ8onZrjedlEvkonaEmMfQu3BhjQvh1JDp3JjGpKJzhcV'
    'u5YjqKUg_zCo-ZDg'
]

TON_TONCENTER_APIKEY = [
    '95617a338738235354498353508da78e61493de7ede35f9bda0be1255dd01295',
    'cf02653f2b55d6c8037abaa4bef579b4b208a46feca8fc02e7560a7aa87bf7f4',
    'e01cbe1c916a2ed93d2b01eb71b5b159aecac8a7687eaa0b7bc4ed3e290e91e8'
] if not IS_VIP else [
    '316c99b2f636f2f44377df77d88d095f2b0bccd857460347e5d34a6a705a3ba4'
]

TON_API_APIKEY = 'AG2UFJOWP233FCIAAAAFW44CAQ3AKQQFA6CKZAFKTTNUP35R74IHW3NUAYBG3UGKWGHVNZI' if not IS_VIP else ''

TRONSCAN_API_KEYS = ['74d5476c-6b91-4b63-89b4-f0a48819a07e', '09287bd2-284c-4500-b145-dc37ed5a8c7b']

BLOCK_DAEMON_API_KEY = [
    'zpka_be04c34c1d484139ab394bcc07b613ee_4a9b8ef3'
]

BASESCAN_API_KEYS = [
    'INYYR12UYT6Z61G2RAE69BETX4TM673GI2',
]

BASE_TATUM_API_KEYS = [
    't-6794f76b758217afa9cf46e0-8a57e5fc5e624cdbad63618f',
]

DOGE_TATUM_API_KEYS = [
    't-6818784a02b70921207f19fa-2a1b48d1d4e94a1d940b5c90'
]

DOT_POLARIS_APIKEY = ['32418207-6364-4c1b-b885-c9fffc6d5e06']

BASE_ROUTESCAN_API_KEYS = [
    ''
]

ENABLE_BASE_TOKENS = False

# Webhook Secrets
if IS_PROD:
    # Blockcypher
    BLOCKCYPHER_WEBHOOK_SECRET = secret_string(
        'gAAAAABet7-cLQ0VO00pZycREZTh_Xr3g7BDnVrFhpeae6qTQ6oGHIIB5u4XSWzP-H_0hSAC0VLVEsSQgvY71CAzblGLDfpZZOHCc8Ndy6d8N13mjNyQe6g=')
    # moh.aghamir@gmail.com
    BLOCKCYPHER_WEBHOOK_TOKEN = secret_string(
        'gAAAAABestdYDH4QWGVksGtfLmYuAlY8TbxxIshBSXZmB0NHUjl569oGyQR1bCWHWLlg99WGfLA4t3Oc4vp523TvGaqpk5BArkePn2zTX7aKsJbE6KffoM1DyhoCKomHriTC3-dFuBXK')

    # Blocknative
    BLOCKNATIVE_WEBHOOK_USERNAME = secret_string(
        'gAAAAABet77xWq3o0w3w5SLkJaeHNYyGbrsF-Qrnptg1P0qZntldrbwKUCAD5kFYtKsy1FN-zVv-QOjFZPMjTbeqdYDrEOldaQ==')
    BLOCKNATIVE_WEBHOOK_SECRET = secret_string(
        'gAAAAABet7-G_L9rWTafH1griS3nb3z3g8GqdWlu27SfK59Oqd2iCZMvvD6KysRezlcIQ2jGqWz8a0ia4kZ-S0rXzIHGOaIn_tGDa_SXMcRZqEBk1Q086Fc=')

    # XRPL Webhook
    XRPL_WEBHOOK_SECRET = secret_string(
        'gAAAAABeuBwZHF3bImc2Hywt9R34f_7n-Wk2ZKGijQxfYwkjvSc2FCfwOl_2d6nnn7IZ0sgpkCUzCnwoWNHpjWVwTiyAECYPFZiVXWaU6tbcg6b6oXD7evk=')
else:
    # Blockcypher
    BLOCKCYPHER_WEBHOOK_SECRET = "NobitexSecretBlockCYPHER!"

    # Blocknative
    BLOCKNATIVE_WEBHOOK_USERNAME = "test"
    BLOCKNATIVE_WEBHOOK_SECRET = "test1234"

# Services API Keys
FINNOTECH_CLIENT_NID = secret_string(
    'gAAAAABoHzrDXWhnus9K7YlVPQhDgzV3OgxxPqA_K1r23slvw1eU2gFP56BIV2Uh27LCAGkLA8eOLCIfWmg-jz0tusSc3PBj_w==',
)
FINNOTECH_CLIENT_SECRET = secret_string(
    'gAAAAABoHzdgAfHTE0rzg1sI-j_mu8a0lUlLckZ1tgi-xHkLPaA5Ww2pVBYjiDLfd_qGOuCBCV5eLKF36YxqbIOHRFdgPC8Yog_892JBMXhZnJcv1pSGEqg=',
    testnet='gAAAAABk2OP7ZoGfoujM4Ub9joiUyADGkYX3sN42Y2GGUltU28RW8DQbABN0JcvV7RHuG4U9w9OGh3Xlf3rsceqYm2cJnomzdVo39rS7XPww8Dg8T1gexsM=',
)
KAVENEGAR_API_KEY = secret_string(
    'gAAAAABeW5jpVJgfzQJCiOGaCi7uqOcL-yPf2cB1NJEVbsljqHTCNmXwLW8OZBZmr3g9CG9jMZqJgK3-BHZMZ9mFsj7QCq4DgC-ESQSv6Kh7hNz2Njl-vxb_tfbYSw1rR9QBVIUEfWAKyONhh5lAKUDqfTsMk2a4gDLcJIQnbpJglanOMh5vo9PKDomP2JOsNFy_xbfRY8ip')
SERVICE_BASE_API_KEY = [
    secret_string(
        'gAAAAABmVID4IH3SEFJf7sMTmprhwkRhYqJIDqwQ5cptUM4nhdEoIqu1wi3PRDFfKpWt9kkFejbHYX3E6noEdz1Y3wC-lldxaBFz8dCFMgVTyCoyWNcllvqGHMGF2jRzvcOLga9j4XPP'),
]  # for stand-alone explorer

# Critical Shetab API Keys
if IS_PROD:
    PAY_IR_USERNAME = secret_string(
        'gAAAAABfL7GZCYcfx6h60QiCosB3FRI3486Oh1LIVMOtvb9QnjkjNgVjlPf9xa-p_E0kjLNeC5VPoCRC7n5bMTiaWAKWdfHWFw==')
    PAY_IR_PASSWORD = secret_string(
        'gAAAAABgJrHQ7RBspNw9LXWn_dr3DuoajiBM_7myvII7JCmGNFkQnvoojQSBZ5pSFzm22GtSq23AFf2YP10KKM6EfrQTPuFVOA==')
    PAY_IR_API_KEY = secret_string(
        'gAAAAABc8qCZmMioFIFAlaySkUv15Rdc0Nxu7UI0pVqAR_wRpN538dnTuiodmslzhEyHKQK45DfqoM9VmEqc0SRX6ryk89XzgPbyMkUkU4m52KOJWZhkPgG2kciaV0_ZHAB1VzmSdba9')
    PAYPING_API_KEY = secret_string(
        'gAAAAABd-FRP6Umbng7tbDpoTizGrJ8xvul50czoofSu5wLJQ6rR6GlWtYQT_QrMT2Hz_THRKfPuqDgjYu7QZXTtobYWAA39UOnEbYF2kaKmy453gvUgi5ndEXN9yDEnrr3o-HPMzSCUJfIe7Ha17Py_9DHfzoNTDo1bFR2LSgCp5Ajau2NFgII=')
    IDPAY_API_KEY = secret_string(
        'gAAAAABcxcHTi8q8uZilGJ9UmVAECdjVsmRc0knnAH4i1RvHDuAnrQlQ8UPz_tji6qD7Qar2ZQzixBDfUMlX3VpVB0r6YZ1yKl_6bSKpWCd7rDto4w0_pHsbUGB38_t7yKOLG2Uipggl')
    VANDAR_API_KEY = secret_string(
        'gAAAAABdGlG2VUqdM731dH9NyRSuWP7tESb8YpUmHzVe0P1FCkEwzLjftqYpQVc6GO3aDv9e8UBY3YOW6aLsKz_gNYaATbch5r80IWvfoh26t8woxelsYaCzMZVm3G-wypq3jYC8qr-7')
    VANDAR_USERNAME = secret_string(
        'gAAAAABeIGskUQAatvhmn909rJEKPL-R6euzrv56xg5nNyn4IgqRnoEvpq9UQlyZr9Hps_koel1QNEEUIFy43o-DnVc9upLJNg==')
    VANDAR_PASSWORD = secret_string(
        'gAAAAABe8aSjhTO3edqG-B-o6-a7UnsMQhzCQjA-dUrZU9C0xByEugVzoK96tefjn_xpUMVr8e-B8Wa5Lv9we3BekCnCcfBWvg==')
    JIBIT_API_KEY = secret_string(
        'gAAAAABe4iS5Ot3-uIjrbgVA7sUWUKnjCd1aZ0UmtOZvqaUhdDieg_hDPFVmX5-O_qb2hwUYUQ2AzSBZ38M7Ez768G11G190OIbj5RkCXycT9A3DQUGJgZUc4r4HwFfT6FcuDmvaZE3M')
    JIBIT_API_SECRET = secret_string(
        'gAAAAABe4iTAz4V6_uRjbE3Zw-6PxYCF8t8QOA5punrZJtsbN8fBu2ncjXt5yJ9iLzVOdyLkI9YihJwd7-KK92ZE2VxSi_WcnSRhiz8mOf_2fo_U0oQLZsngqpyLgerSLDx-BVvGBNVLI4xE2hLt4PVLklctQsgHBQ==')
    JIBIT_PPG_API_KEY = secret_string(
        'gAAAAABh3sEhFpv33yaOKK8LS6kgAQqHkd5BgnDcfTIxtOLYdcd-1jqS5Px5cjvxlu27V27GBe_1_C3LZ6_qpqAYiLlchmhk8A==')
    JIBIT_PPG_API_SECRET = secret_string(
        'gAAAAABh3sEoXbIXZ-ngpKqtaAaJFG7DzgWCWj3BQcx-zIzeKDZ5bjkiSs4dBe7LZF6Bol9GZpXxcLxh_wqVMeI85zSOdrZwIkkJ_GaeoGEPr3kwbHE0rrAROfYf0E7yvEKPFa8r0E9fMm-UMcffjj38RO-XyqQOxQ==')
    JIBIT_TRF_API_KEY = secret_string(
        'gAAAAABh-ssSbmsVlscNnWMCJpG7_3MfT1Sz2UvMI5szQmlaLnnPcnf_XIcyIlDJEx8ZcWM2vGdHfkCdkwZD22X-caQIAPS0IQ==')
    JIBIT_TRF_API_SECRET = secret_string(
        'gAAAAABh-ssrXtlQdQxNJJ_LaNQARuax4M-pIiNfwZsTo91qzViDCY92p_l8DAVpX5Mb8g9DbYkgvCjf4-J1zlx_99E07xURokMgHW3lcwMc1w1XzCRFy6A=')
    JIBIT_PIP_API_KEY = secret_string(
        'gAAAAABgpoS2n3H2XdEqsDLOcXhUazARXSRJ3A8GDiBsFgKRJ4DrLsjG3zxWE7fq7kcloufrNBwenR-WMcwznnN99r_wgJOj85QQCWnvJQ26_WiE68V900DqW6PmUJqhCfqTn6OxyTI9')
    JIBIT_PIP_API_SECRET = secret_string(
        'gAAAAABgpoTSkioOdtbD9jU95VxdtX5d-P9WrAByHuviJHC7OlzxIlnisjsNPyacCROUbuxXQHRltEMOwzrJHYN0ryJrJEFpyl39HU-dh9mFLy4FLxU8TujOj_FSLZgLuIbZW_idd53C')
    TOMAN_CLIENT_ID = secret_string(
        'gAAAAABkyMEeEjH5YQ60oV0c2y-0bvqf8rnwGXImIfJQeMUGxoOLUSGXry8zgstzDL8dIyARqVil8vB4u-BEWN0UnaI6gIGhMPpu67zPOpwUhyCGfTSO3tCYzGtKhmwss45BkDQ-Eb-B')
    TOMAN_CLIENT_SECRET = secret_string(
        'gAAAAABkyMEwFs7gCAtM5CGsUyWmbkm-a5CpN_96bhlVZ24P7Etgj7vcWkvh02rVRDnaLIbFF0f5PeXcVWmD1XPvtgijXxUjzfUQTIDIvxjrMTYx8Mm9y8SVaAy2YPk015tTyJGaFIJE74zjD7qEQKYUSBppZBfoXKTxUM96MaVvMrzCrdhoOT1lW7BXoJFMcdLC15RWxYFBsf3eblnJFAkkaf9R2RQXhPjlZ3T6z9G2q26rdTZvGA93qugRFr7xT5wX6UJqQCst')
    TOMAN_USERNAME = 'nobitex'
    TOMAN_PASSWORD = secret_string(
        'gAAAAABldHycDljIiWXI4a3X8aMxcSFqokq5yb_Y2lu_fm-M8DsM-OWgcgHUx1iVaIs7iCivugfZuC1DpHhJXPSi65nSJMGjfZIbjsLBQHEFnMcya8raaXA=')
else:
    PAY_IR_USERNAME = 'test'
    PAY_IR_PASSWORD = 'test'
    PAY_IR_API_KEY = 'test'
    VANDAR_API_KEY = 'b44fbd8273bd9988900a64c7b969593b5d004046'
    VANDAR_USERNAME = '09204712640'
    VANDAR_PASSWORD = 'pD9HPc62umsFXCc'
    PAYIR_MOBILE = '09120000000'
    PAYPING_API_KEY = 'test'
    IDPAY_API_KEY = '9933fdff-b433-4ba4-b7fb-411869d207cc'
    JIBIT_API_KEY = ''
    JIBIT_API_SECRET = ''
    JIBIT_PPG_API_KEY = '2StWi31Rbe'
    JIBIT_PPG_API_SECRET = 'j7atc2PwfCZC90B4wszvf6U0UOIlUkYc42qawRJHXVCBIitcnc'
    JIBIT_TRF_API_KEY = ''
    JIBIT_TRF_API_SECRET = ''
    JIBIT_PIP_API_KEY = '456dd508-b3a7-445d-9d70-09bca7eb360b'
    JIBIT_PIP_API_SECRET = '6a362b65-8c83-4c03-a84c-57f08a4da8f6'
    TOMAN_CLIENT_ID = '9gLYC788t3lT8c5X5fR37qPaSq7rQjo1sFkuf1RS'
    TOMAN_CLIENT_SECRET = 'qaa7bgR8p0b03w7ks8bvfuUNS410BIPIEANNHmdwTUYPF9XHFt4UJx0InhfFRh8d7bhsLlRZwc4ZroNcOQkoamNkCZU34gtSF2lFBMI1Tj03B8hY4N88mk5hlOBs59RH'
    TOMAN_USERNAME = 'nobitex'
    TOMAN_PASSWORD = 'FOxEeZPgT00gDpXWMKigKdvPl1zyzagl47OSsZogn9k'

DEPOSIT_NEXT_REDIRECT_URL_DOMAINS = {'nobitex.ir', 'nobitex.net'}

JIBIT_IDE_API_KEY = secret_string(
    'gAAAAABmSfMuSS1IH-EL0VlOz9p8ULaZOa6U7PGlQKM8anjizsQGTcxZBVSY4ZKeT4J13cSUmVaqFU4NVeIcyGYm96vwNHG5XA==',
    testnet='gAAAAABmSfXcvbSDLhx7nd-pmAWlRU6QA-VztWT9k-2HlERgTL6PVcd4nwGyr0StiJi6yOmPTSWZl00wHIXgJ9TPbEvqNtZlhA==',
)
JIBIT_IDE_API_SECRET = secret_string(
    'gAAAAABmSfNqSsfz2TWIlDi88gQo3KRXrgtkeDk0_4mJV0aKw1YOeQUtbd3-o0a2sihjrVCngmkr44LEESZ-rxvPu38idar6ot9oaYfwzM5S3YgduOENjoM=',
    testnet='gAAAAABmSfX9e1pGvfmUP5D62gpXmE4M_PGbUffJNX0LN8Wvt4Asro7XB6t-Bp72dNjXqrV6qw2_jDO7J8CK2VEwxZvvYc5e-8pPuwKMZYPm8XyGyuP0QBA=',
)

PADRO_USERNAME = 'test.podro@gmail.com'
PADRO_PASSWORD = 'test.podro'

# Jibit IDE (KYC Verification) Services
if IS_PROD:
    JIBIT_IDE_API_KEY = secret_string(
        'gAAAAABmG7LgSJIczGbvdwgkSXirdPtySo6FQfPKOMT_mUZMoarNKfhb_iA8vIG17vcfy963jnhP_ScvQjD3eb5jFn2dXok4-Q==',
    )
    JIBIT_IDE_SECRET_KEY = secret_string(
        'gAAAAABmG7L_yfB4tn1xWnBE1SG0r6aRFkwCdC_R3hNX9WOT0dF6dlsoxp8l5yEx6kA1RxNn7HY9zFwyGzU4agieswG_R1Q3gW1RWtELqbf10YqLiv6WUGQ=',
    )
else:
    JIBIT_IDE_API_KEY = 'eNAUhJ83EA'
    JIBIT_IDE_SECRET_KEY = 'dByIRKPBnvS1QAYD6vmXMLNvH'

# JIBIT verification api token (KYC) Alpha services
JIBIT_KYC_TOKEN = '2|oz2RgIEktKwzaQYgLwVGXkWV6UhtmD4jT99fJjYF'

# Telegram Bot Key
TELEGRAM_BOT_KEY = 'uINZU5LQfoK7Ix0G'

# Hot Wallet Information
if IS_PROD:
    HOT_SYMMETRIC_KEY = secret_string(
        'gAAAAABlMQ5_Vdpc0B0dFZ7jUNZcJslQWu8phUeEaMKgWlGa121W2952gh5r0MCKiFcwQ3uDpVSJoXlUmwiT0jIGu2INjYJ5sFDnzUDvbZZiMTN4OUgEVaA=')
elif IS_TESTNET:
    HOT_SYMMETRIC_KEY = 'I5xY/9mSzxAqoYN62kqF6bIxgZBPn7xM3A1nb1o6yrDytLfK/M'
else:
    HOT_SYMMETRIC_KEY = '123'

# Cold Wallet Information
if IS_PROD:
    COLD_SYMMETRIC_KEY = secret_string(
        'gAAAAABgasfK0znH7gtJnezujsoVyEEdCt0aL1Gacd884aLLAQ4iZd7eXaE9sCfewNYxiRe_VkxmQxSZ8irjt_DwxI7nYfBE-KMQqaxZCgaNg2KM96acdmo=')
elif IS_TESTNET:
    COLD_SYMMETRIC_KEY = 'I5xY/9mSzxAqoYN62kqF6bIxgZBPn7xM3A1nb1o6yrDytLfK/M'
else:
    COLD_SYMMETRIC_KEY = '123'
if IS_PROD:
    COLD_API_KEY = secret_string(
        'gAAAAABgatxWOghxxZL4f3Pz8PMAqU2SXngUQAFqv-b6zZHJyRDEIrt1p43CxaIJPwmvtQlFl4wbvbYlIWC8GqiG0D3XC2y3RIvuCjg_SFI5rv9xsxQ_Htc=')
elif IS_TESTNET:
    COLD_API_KEY = 'test'
else:
    COLD_API_KEY = ''
MAINNET_COLD_WALLET_URL = 'https://coldui.nxbo.ir'
TESTNET_COLD_WALLET_URL = 'https://t-cold.nobitex.ir'
if IS_PROD:
    COLD_WALLET_URL = MAINNET_COLD_WALLET_URL
elif IS_TESTNET:
    COLD_WALLET_URL = TESTNET_COLD_WALLET_URL
else:
    COLD_WALLET_URL = 'http://127.0.0.1:8001'

# Wallet Information
MAIN_WALLET_SERVER = 'https://wallet-n1mxerp.nobitex1.ir'
SECONDARY_WALLET_SERVER = 'https://wallet-21720116248.nobitex1.ir'
THIRD_WALLET_SERVER = 'https://wallet-px2mxerp.nobitex1.ir'
DIRECT_WALLET_SERVER = 'https://wallet.nobitex1.ir'
DIRECT_SHARIF_SERVER = 'https://wallet2.nobitex1.ir'
DIRECT_WALLET_3_SERVER = 'https://wallet3.nobitex1.ir'
DIRECT_WALLET_3_WS_SERVER = 'wss://wallet3.nobitex1.ir'
DIRECT_NODES_SERVER = 'https://nodes.nobitex1.ir'
DIRECT_NODES_WS_SERVER = 'wss://nodes.nobitex1.ir'
DIRECT_NODES_2_SERVER = 'https://nodes2.nobitex1.ir'
DIRECT_NODES_2_WS_SERVER = 'wss://nodes2.nobitex1.ir'
DIRECT_NODES_4_SERVER = 'https://nodes4.nobitex1.ir'
DIRECT_NODES_4_WS_SERVER = 'wss://nodes4.nobitex1.ir'
DIRECT_WALLET_4_SERVER = 'https://wallet4.nobitex1.ir'
DIRECT_WALLET_5_SERVER = 'https://wallet5.nobitex1.ir'
DIRECT_WALLET_6_SERVER = 'https://wallet6.nobitex.ir'
DIRECT_WALLET_7_SERVER = 'https://wallet7.nobitex.ir'
if IS_PROD:
    DIRECT_LND_SERVER = f'{secret_string("gAAAAABhAaWI9WV0N_XRvv7KO3BPPvNkNtUYrfZBUuhZ6TKmpOSFw4InOtQ_tvrO9tgVeSY35Hvsinp4BfgsRruStw9IyOkWDg==")}:10009'
else:
    DIRECT_LND_SERVER = 'localhost:10009'
WITHDRAW_PROXY = NO_INTERNET

if IS_PROD:
    WALLET_SERVER = DIRECT_WALLET_SERVER
    WITHDRAW_PROXY = False
    # ADA
    ADA_JSONRPC_URL = DIRECT_WALLET_7_SERVER + '/ada/'
    # ALGO
    ALGO_JSONRPC_URL = DIRECT_WALLET_5_SERVER + '/algo/'
    # APT
    APT_JSONRPC_URL = DIRECT_WALLET_5_SERVER + '/apt/'
    # ARB
    ARB_JSONRPC_URL = DIRECT_WALLET_5_SERVER + '/arb/'
    ARB_HD_URL = DIRECT_WALLET_4_SERVER + '/arb-hd/'
    # ATOM
    ATOM_JSONRPC_URL = DIRECT_WALLET_4_SERVER + '/atom/'
    # AVAX
    AVAX_JSONRPC_URL = DIRECT_WALLET_4_SERVER + '/avax/'
    AVAX_ONLY_HD_URL = DIRECT_WALLET_4_SERVER + '/avax-hd/'
    # BCH
    ELECTRON_CASH_JSONRPC_URL = DIRECT_WALLET_7_SERVER + '/bch/'
    # BNB
    BNB_WALLET = 'bnb1990lfutz0f9wza6rsh36ysfwt9xpctxrll884r'
    BNB_RPC_URL = WALLET_SERVER + '/bnb-rpc/'
    BNB_API_SERVER_URL = WALLET_SERVER + '/bnb-api/'
    BNB_JSONRPC_URL = WALLET_SERVER + '/bnb'
    # BSC
    BSC_JSONRPC_URL = WALLET_SERVER + '/bsc/'
    BSC_GETH_WS_URL = DIRECT_NODES_2_WS_SERVER + '/bsc-ws/'
    BSC_GETH_JSONRPC_URL = DIRECT_NODES_2_SERVER + '/bsc/'
    BSC_GETH_ACCOUNT = '0x1a1d9fe7d7bcad73f2d7e2cd734b51373c989df6'
    BSC_GETH_BEP20_ACCOUNT = BSC_GETH_ACCOUNT
    BSC_HD_URL = DIRECT_WALLET_4_SERVER + '/bsc-hd/'
    # BTC
    ELECTRUM_JSONRPC_URL = DIRECT_WALLET_7_SERVER + '/btc/'
    ELECTRUM_WALLET_PATH = '~/.electrum/wallets/wallet_1'
    # DOGE
    DOGE_WALLET_SERVER = DIRECT_WALLET_7_SERVER
    DOGE_JSONRPC_URL = DOGE_WALLET_SERVER + '/doge/'
    # DOT
    DOT_JSONRPC_URL = DIRECT_WALLET_5_SERVER + '/dot/'
    # EGLD
    EGLD_JSONRPC_URL = DIRECT_WALLET_4_SERVER + '/egld/'
    # ENJ
    ENJ_JSONRPC_URL = DIRECT_WALLET_4_SERVER + '/enj/'
    # EOS
    EOS_JSONRPC_URL = DIRECT_WALLET_7_SERVER + '/eos/'
    # ETC
    PARITY_JSONRPC_URL = WALLET_SERVER + '/eth-classic'
    PARITY_ACCOUNT = '0x6637d9b2f3569f8e4998bdcb62769b1cfb3d9c3b'
    ETC_SERVER_NAME = 'nobitex1/nodes-etc'
    ETC_JSONRPC_URL = WALLET_SERVER + '/eth-classic'
    ETC_HD_URL = DIRECT_WALLET_4_SERVER + '/etc-hd/'
    # ETH
    GETH_JSONRPC_URL = DIRECT_NODES_4_SERVER + '/eth-rpc/'
    GETH_ACCOUNT = '0x8D56f551b44a6dA6072a9608d63d664ce67681a5'
    GETH_ERC20_ACCOUNT = '0xD16E4cdb153B2DCc617061174223a6D4BFaE53f5'
    GETH_WS_URL = DIRECT_NODES_4_WS_SERVER + '/eth-ws/'
    ETH_JSONRPC_URL = DIRECT_WALLET_6_SERVER + '/eth/'  # nobitex hot-wallet
    ETH_HD_URL = DIRECT_WALLET_4_SERVER + '/eth-hd/'
    ETH_ONLY_HD_URL = DIRECT_WALLET_4_SERVER + '/eth-only-hd/'
    # FIL
    FIL_JSONRPC_URL = DIRECT_WALLET_5_SERVER + '/fil/'
    # FLR
    FLR_JSONRPC_URL = DIRECT_WALLET_4_SERVER + '/flr/'
    # FLOW
    FLOW_JSONRPC_URL = DIRECT_WALLET_5_SERVER + '/flow/'
    # FTM
    FTM_JSONRPC_URL = WALLET_SERVER + '/ftm/'
    FTM_ONLY_HD_URL = DIRECT_WALLET_4_SERVER + '/ftm-hd/'
    # HARMONY
    HARMONY_JSONRPC_URL = DIRECT_WALLET_4_SERVER + '/harmony/'
    HARMONY_HD_URL = DIRECT_WALLET_4_SERVER + '/one-hd/'
    # Hedera
    HBAR_JSONRPC_URL = DIRECT_WALLET_5_SERVER + '/hbar/'
    # LND
    LND_JSONRPC_URL = DIRECT_WALLET_7_SERVER + '/btcln/'
    LND_URL = DIRECT_LND_SERVER
    # LTC
    ELECTRUM_LTC_JSONRPC_URL = DIRECT_WALLET_7_SERVER + '/ltc/'
    ELECTRUM_LTC_WALLET_PATH = '~/.electrum-ltc/wallets/wallet_1'
    # NEAR
    NEAR_JSONRPC_URL = DIRECT_WALLET_4_SERVER + '/near/'
    # PMN
    PMN_JSONRPC_URL = DIRECT_SHARIF_SERVER + '/pmn/'
    # POLYGON
    POLYGON_JSONRPC_URL = WALLET_SERVER + '/polygon/'
    POLYGON_HD_URL = DIRECT_WALLET_4_SERVER + '/matic-hd/'
    # SOL
    SOLANA_JSONRPC_URL = DIRECT_WALLET_4_SERVER + '/sol/'
    # TON
    TON_JSONRPC_URL = DIRECT_WALLET_4_SERVER + '/ton/'
    TON_HL_V2_JSONRPC_URL = [
        DIRECT_WALLET_4_SERVER + '/tonhlv3/hw1/',
        DIRECT_WALLET_4_SERVER + '/tonhlv3/hw2/',
        DIRECT_WALLET_4_SERVER + '/tonhlv3/hw3/',
        DIRECT_WALLET_4_SERVER + '/tonhlv3/hw4/',
        DIRECT_WALLET_4_SERVER + '/tonhlv3/hw5/',
        DIRECT_WALLET_4_SERVER + '/tonhlv3/hw6/',
        DIRECT_WALLET_4_SERVER + '/tonhlv3/hw7/',
        DIRECT_WALLET_4_SERVER + '/tonhlv3/hw8/',
        DIRECT_WALLET_4_SERVER + '/tonhlv3/hw9/',
        DIRECT_WALLET_4_SERVER + '/tonhlv3/hw10/',
        DIRECT_WALLET_4_SERVER + '/tonhlv3/hw11/',
        DIRECT_WALLET_4_SERVER + '/tonhlv3/hw12/',
        DIRECT_WALLET_4_SERVER + '/tonhlv3/hw13/',
        DIRECT_WALLET_4_SERVER + '/tonhlv3/hw14/',
        DIRECT_WALLET_4_SERVER + '/tonhlv3/hw15/',
        DIRECT_WALLET_4_SERVER + '/tonhlv3/hw16/',
        DIRECT_WALLET_4_SERVER + '/tonhlv3/hw17/',
        DIRECT_WALLET_4_SERVER + '/tonhlv3/hw18/',
        DIRECT_WALLET_4_SERVER + '/tonhlv3/hw19/',
        DIRECT_WALLET_4_SERVER + '/tonhlv3/hw20/',
    ]
    # TRX
    TRX_JSONRPC_URL = WALLET_SERVER + '/trx/'
    TRX_JSONRPC_URL_2 = WALLET_SERVER + '/trx-new/'
    TRX_TRC20_JSONRPC_URL = DIRECT_WALLET_4_SERVER + '/trx/'
    TRX_HD_URL = DIRECT_WALLET_4_SERVER + '/trx-hd/'
    TRX_ONLY_HD_URL = DIRECT_WALLET_4_SERVER + '/trx-only-hd/'
    # XLM
    XLM_JSONRPC_URL = DIRECT_WALLET_7_SERVER + '/xlm/'
    # XMR
    XMR_JSONRPC_URL = DIRECT_WALLET_4_SERVER + '/xmr/'
    XMR_EXPLORER_JSONRPC_URL = DIRECT_WALLET_4_SERVER + '/xmr-explorer/'
    XMR_ADMIN_JSONRPC_URL = DIRECT_WALLET_4_SERVER + '/xmr-admin/'
    # XRP
    RIPPLE_WALLET_SERVER = WALLET_SERVER
    RIPPLE_JSONRPC_URL = RIPPLE_WALLET_SERVER + '/xrp'
    XRP_JSONRPC_URL = DIRECT_WALLET_6_SERVER + '/xrp/'

    # XTZ
    XTZ_JSONRPC_URL = DIRECT_WALLET_4_SERVER + '/xtz/'
    # SONIC
    SONIC_HD_URL = DIRECT_WALLET_6_SERVER + '/s-hd/'
    # BASE
    BASE_HD_URL = DIRECT_WALLET_6_SERVER + '/base-hd/'
    # CONTRACT
    CONTRACT_BSC_JSONRPC_URL = DIRECT_WALLET_7_SERVER + '/contract-bsc/'
    CONTRACT_ETC_JSONRPC_URL = DIRECT_WALLET_7_SERVER + '/contract-etc/'
    CONTRACT_ETH_JSONRPC_URL = DIRECT_WALLET_7_SERVER + '/contract-eth/'
    CONTRACT_FTM_JSONRPC_URL = DIRECT_WALLET_7_SERVER + '/contract-ftm/'
    CONTRACT_POLYGON_JSONRPC_URL = DIRECT_WALLET_7_SERVER + '/contract-polygon/'
    CONTRACT_TRX_JSONRPC_URL = DIRECT_WALLET_7_SERVER + '/contract-trx/'
    # CONTRACT V2
    CONTRACT_V2_ARB_JSONRPC_URL = DIRECT_WALLET_7_SERVER + '/contract-v2-arb/'
    CONTRACT_V2_AVAX_JSONRPC_URL = DIRECT_WALLET_7_SERVER + '/contract-v2-avax/'
    CONTRACT_V2_BSC_JSONRPC_URL = DIRECT_WALLET_7_SERVER + '/contract-v2-bsc/'
    CONTRACT_V2_ETC_JSONRPC_URL = DIRECT_WALLET_7_SERVER + '/contract-v2-etc/'
    CONTRACT_V2_ETH_JSONRPC_URL = DIRECT_WALLET_7_SERVER + '/contract-v2-eth/'
    CONTRACT_V2_FTM_JSONRPC_URL = DIRECT_WALLET_7_SERVER + '/contract-v2-ftm/'
    CONTRACT_V2_HARMONY_JSONRPC_URL = DIRECT_WALLET_7_SERVER + '/contract-v2-harmony/'
    CONTRACT_V2_POLYGON_JSONRPC_URL = DIRECT_WALLET_7_SERVER + '/contract-v2-polygon/'
    # GATEWAY
    GATEWAY_SERVER = 'https://wallet-gateway.nobitex1.ir'
    GATEWAY_BTC_JSONRPC_URL = GATEWAY_SERVER + '/gateway-btc'
    GATEWAY_LTC_JSONRPC_URL = GATEWAY_SERVER + '/gateway-ltc'
    GATEWAY_XRP_JSONRPC_URL = GATEWAY_SERVER + '/gateway-xrp'

else:
    WALLET_SERVER = 'https://wallet-btc-test.local/'
    WITHDRAW_PROXY = False
    # ADA
    ADA_JSONRPC_URL = 'http://localhost:6071'
    # ALGO
    ALGO_JSONRPC_URL = 'http://localhost:6071'
    # APT
    APT_JSONRPC_URL = 'http://localhost:6071'
    # ARB
    ARB_JSONRPC_URL = 'http://localhost:6071'
    ARB_HD_URL = 'http://localhost:6071'
    # ATOM
    ATOM_JSONRPC_URL = 'http://localhost:6021'
    # AVAX
    AVAX_JSONRPC_URL = 'http://localhost:6071'
    AVAX_ONLY_HD_URL = 'http://localhost:6071'
    # BCH
    ELECTRON_CASH_JSONRPC_URL = 'http://localhost:8888'
    # BNB
    BNB_WALLET = 'tbnb19yjzw0xq2ufulqrp85wt6qnxzxgmkd72hgc2du'
    BNB_RPC_URL = MAIN_WALLET_SERVER + '/tbnb-rpc/'
    BNB_API_SERVER_URL = MAIN_WALLET_SERVER + '/tbnb-api/'
    BNB_JSONRPC_URL = 'http://localhost:6071'
    # BSC
    BSC_JSONRPC_URL = 'http://localhost:6031'
    BSC_GETH_WS_URL = DIRECT_NODES_WS_SERVER + '/bsc-fullnode-ws/'
    BSC_GETH_JSONRPC_URL = 'http://localhost:8545'
    BSC_GETH_ACCOUNT = '0xf72fb5e6ab7444d46ae893508080981f024b1683'
    BSC_GETH_BEP20_ACCOUNT = '0xf72fb5e6ab7444d46ae893508080981f024b1683'
    BSC_HD_URL = 'http://localhost:6051'
    ETH_JSONRPC_URL = 'http://localhost:6051'
    # BTC
    ELECTRUM_JSONRPC_URL = 'http://localhost:6666'
    ELECTRUM_WALLET_PATH = '~/.electrum/testnet/wallets/wallet_1'
    # DOGE
    DOGE_WALLET_SERVER = 'https://wallet-doge-test.local/'
    DOGE_JSONRPC_URL = 'http://localhost:6071'
    # DOT
    DOT_JSONRPC_URL = 'http://localhost:6071'
    # EGLD
    EGLD_JSONRPC_URL = 'http://localhost:3071'
    # ENJ
    ENJ_JSONRPC_URL = 'http://localhost:6071'
    # EOS
    EOS_JSONRPC_URL = 'http://localhost:6071'
    # ETC
    # PARITY_JSONRPC_URL = MAIN_WALLET_SERVER + '/parity-mordor'
    PARITY_JSONRPC_URL = 'http://localhost:8546'
    PARITY_ACCOUNT = '0x43d2c0803b019f1d8b0b8433c9685022679ed1d2'  # pass: hunter2
    ETC_SERVER_NAME = 'nobitex1/nodes-etc'
    ETC_JSONRPC_URL = 'http://localhost:6071'
    ETC_HD_URL = 'http://localhost:6071'
    # ETH
    GETH_JSONRPC_URL = 'http://localhost:8545'
    GETH_ACCOUNT = '0xf72fb5e6ab7444d46ae893508080981f024b1683'
    GETH_WS_URL = 'ws://localhost:8546'
    ETH_HD_URL = 'http://localhost:6051'
    ETH_ONLY_HD_URL = 'http://localhost:6051'
    # FIL
    FIL_JSONRPC_URL = 'http://localhost:6021'
    # FLR
    FLR_JSONRPC_URL = 'http://localhost:6071'
    # FLOW
    FLOW_JSONRPC_URL = 'http://localhost:6071'
    # FTM
    FTM_JSONRPC_URL = 'http://localhost:6071'
    FTM_ONLY_HD_URL = 'http://localhost:6071'
    # HARMONY
    HARMONY_JSONRPC_URL = 'http://localhost:6071'
    HARMONY_HD_URL = 'http://localhost:6071'
    # Hedera
    HBAR_JSONRPC_URL = 'http://localhost:6072'
    # LND
    LND_JSONRPC_URL = 'http://localhost:6071'
    LND_URL = 'localhost:10009'
    # LTC
    ELECTRUM_LTC_JSONRPC_URL = 'http://localhost:7777'
    ELECTRUM_LTC_WALLET_PATH = '~/.electrum-ltc/testnet/wallets/wallet_1'
    # XMR
    XMR_JSONRPC_URL = 'http://localhost:3071'
    XMR_EXPLORER_JSONRPC_URL = 'http://localhost:5071'
    XMR_ADMIN_JSONRPC_URL = 'http://localhost:9071'
    # NEAR
    NEAR_JSONRPC_URL = 'http://localhost:6071'
    # PMN
    PMN_JSONRPC_URL = 'http://wallet-eth-test.local:7071'
    # POLYGON
    POLYGON_JSONRPC_URL = 'http://localhost:6071'
    POLYGON_HD_URL = 'http://localhost:6071'
    # SOL
    SOLANA_JSONRPC_URL = 'http://localhost:3071'
    # TON
    TON_JSONRPC_URL = 'http://localhost:6071'
    TON_HL_V2_JSONRPC_URL = [
        'http://localhost:6071',
        'http://localhost:6072',
        'http://localhost:6073',
    ]
    # TRX
    TRX_JSONRPC_URL_2 = 'http://localhost:6061'
    TRX_TRC20_JSONRPC_URL = 'http://localhost:6061'
    TRX_HD_URL = 'http://localhost:6061'
    TRX_ONLY_HD_URL = 'http://localhost:6061'
    # XLM
    XLM_JSONRPC_URL = 'http://localhost:6071'
    # XRP
    RIPPLE_WALLET_SERVER = 'https://wallet-eth-test.local/'
    RIPPLE_JSONRPC_URL = 'http://localhost:20316'  # Testnet port is set to 20316. Mainnet port is 20315
    XRP_JSONRPC_URL = 'http://localhost:6070'
    # XTZ
    XTZ_JSONRPC_URL = 'http://localhost:6021'
    # SONIC
    SONIC_HD_URL = 'http://localhost:6071'
    # BASE
    BASE_HD_URL = 'http://localhost:6071'
    # CONTRACT
    CONTRACT_BSC_JSONRPC_URL = 'http://localhost:6031'
    CONTRACT_ETC_JSONRPC_URL = 'http://localhost:6071'
    CONTRACT_ETH_JSONRPC_URL = 'http://localhost:6051'
    CONTRACT_FTM_JSONRPC_URL = 'http://localhost:6071'
    CONTRACT_POLYGON_JSONRPC_URL = 'http://localhost:6061'
    CONTRACT_TRX_JSONRPC_URL = 'http://localhost:6061'
    # CONTRACT V2
    CONTRACT_V2_ARB_JSONRPC_URL = 'http://localhost:6071'
    CONTRACT_V2_AVAX_JSONRPC_URL = 'http://localhost:6071'
    CONTRACT_V2_BSC_JSONRPC_URL = 'http://localhost:6031'
    CONTRACT_V2_ETC_JSONRPC_URL = 'http://localhost:6071'
    CONTRACT_V2_ETH_JSONRPC_URL = 'http://localhost:6051'
    CONTRACT_V2_FTM_JSONRPC_URL = 'http://localhost:6071'
    CONTRACT_V2_HARMONY_JSONRPC_URL = 'http://localhost:6071'
    CONTRACT_V2_POLYGON_JSONRPC_URL = 'http://localhost:6061'
    if IS_TESTNET:
        # GATEWAY
        GATEWAY_SERVER = 'https://wallet-gateway.nobitex1.ir'
        GATEWAY_BTC_JSONRPC_URL = GATEWAY_SERVER + '/gateway-btctest'
        GATEWAY_LTC_JSONRPC_URL = GATEWAY_SERVER + '/gateway-ltctest'
        GATEWAY_XRP_JSONRPC_URL = GATEWAY_SERVER + '/gateway-xrptest'
        # TRX
        TRX_JSONRPC_URL = MAIN_WALLET_SERVER + '/trx-testnet/'
    else:
        GATEWAY_SERVER = 'https://wallet-eth-test.local/'
        GATEWAY_BTC_JSONRPC_URL = 'http://localhost:6666'
        GATEWAY_LTC_JSONRPC_URL = 'http://localhost:7777'
        GATEWAY_XRP_JSONRPC_URL = 'http://localhost:20316'
        # TRX
        TRX_JSONRPC_URL = 'http://localhost:6061'

# Social Login OAuth Keys
GOOGLE_CLIENT_IDS = [
    '199423694398-sibiifeubphefrvf46j99klkuciuj60i.apps.googleusercontent.com',
    '1039155241638-5ehvg8etjmdo2i6v7h8553m3hak0n7sp.apps.googleusercontent.com',
    '1039155241638-c5qksis95iv1baf0v8ehdt17167sb4d2.apps.googleusercontent.com',
]
if IS_TESTNET:
    GOOGLE_CLIENT_IDS.append('76175601663-m81vjpu5buesqklevhh34fsqn6m10rrc.apps.googleusercontent.com')

# Proxy and Internet connection config
USE_PROXY = os.environ.get('USE_PROXY') != 'no'
DIRECT_HTTP_PROXY = 'http://proxy.local:1100' if USE_PROXY else None
if USE_PROXY and not DEBUG:
    DEFAULT_PROXY = {
        'http': 'http://proxy.local:1100',
        'https': 'http://proxy.local:1100',
    }
else:
    DEFAULT_PROXY = None
SANCTIONED_APIS_PROXY = DEFAULT_PROXY

# Application definition
INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',

    'snowpenguin.django.recaptcha2',
    'multi_captcha_admin',
    'django.contrib.sites',
    'django.contrib.admin',

    'rest_framework',
    'rest_framework.authtoken',
    'dj_rest_auth',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'dj_rest_auth.registration',
    'post_office',
    'corsheaders',
    'django_cron',
    'django_otp',
    'django_otp.plugins.otp_totp',
    'django_otp.plugins.otp_static',
    'bootstrap4',
    'storages',
    'oauth2_provider',

    'exchange.captcha.apps.CaptchaConfig',
    'exchange.accounts.apps.AccountsConfig',
    'exchange.base.apps.BaseConfig',
    'exchange.market.apps.MarketConfig',
    'exchange.marketing.apps.MarketingConfig',
    'exchange.matcher.apps.MatcherConfig',
    'exchange.shetab.apps.ShetabConfig',
    'exchange.wallet.apps.WalletConfig',
    'exchange.report.apps.ReportConfig',
    'exchange.accounting.apps.AccountingConfig',
    'exchange.audit.apps.AuditConfig',
    'exchange.gateway.apps.GatewayConfig',
    'exchange.promotions.apps.PromotionsConfig',
    'exchange.crm.apps.CrmConfig',
    'exchange.security.apps.SecurityConfig',
    'exchange.usermanagement.apps.UserManagementConfig',
    'exchange.android.apps.AndroidConfig',
    'exchange.system.apps.SystemConfig',
    'exchange.charts.apps.ChartsConfig',
    'exchange.fcm.apps.FCMConfig',
    'exchange.tokens.apps.TokensConfig',
    'exchange.xchange.apps.XchangeConfig',
    'exchange.support.apps.SupportConfig',
    'exchange.pricealert.apps.PriceAlertConfig',
    'exchange.features.apps.FeaturesConfig',
    'exchange.portfolio.apps.PortfolioConfig',
    'exchange.withdraw.apps.WithdrawConfig',
    'exchange.gift.apps.GiftConfig',
    'exchange.ticketing.apps.TicketingConfig',
    'exchange.metrics.apps.MetricsConfig',
    'exchange.web_engage.apps.WebEngageConfig',
    'exchange.integrations.apps.IntegrationsConfig',
    'exchange.pool.apps.PoolConfig',
    'exchange.margin.apps.MarginConfig',
    'exchange.redeem.apps.RedeemConfig',
    'exchange.staking.apps.StakingConfig',
    'exchange.earn.apps.EarnConfig',
    'exchange.credit.apps.CreditConfig',
    'exchange.recovery.apps.RecoveryConfig',
    'exchange.socialtrade.apps.SocialTradeConfig',
    'exchange.subscription.apps.SubscriptionConfig',
    'exchange.oauth.apps.OauthConfig',
    'exchange.asset_backed_credit.apps.AssetBackedCreditConfig',
    'exchange.direct_debit.apps.DirectDebitConfig',
    'exchange.notification.apps.NotificationConfig',
    'exchange.liquidator.apps.LiquidatorConfig',
    'exchange.corporate_banking.apps.CorporateBankingConfig',
    'exchange.apikey.apps.ApikeyConfig',
]
if DEBUG:
    INSTALLED_APPS += ['debug_toolbar', 'django_extensions']

MIDDLEWARE = [
    'exchange.base.middlewares.SentryContextMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'exchange.base.middlewares.DisableSessionForAPIsMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'exchange.base.api.NobitexAPIMiddleware',
]

if DEBUG:
    MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')

ROOT_URLCONF = 'exchange.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'exchange', 'base', 'base_templates')
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'exchange.wsgi.application'

# Database Replication Modes
# 1. RW: Normally the code is only connected to a RW database named 'default'.
# 2. RW+RO: If there is also a RO replica available, the USE_REPLICA env should be set so that
#    it is made available as 'replica' in Django DATABASES. This mode is useful for offloading
#    heavy queries to replicas while still having access to main DB.
# 3. RO: For cases that only a single RO replica should be used, the ONLY_REPLICA parameter should
#    be set. In this mode, only 'default' DATABASE is available and points to the replica.
ONLY_REPLICA = os.environ.get('DB') == 'replicaonly'
USE_REPLICA = ONLY_REPLICA or os.environ.get('DB_USE_REPLICA', 'no') == 'yes' or os.environ.get('DB') == 'replica'

# Database
REPLICA_HOST = os.environ.get('REPLICA_HOST', 'replica.nobitex')
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'CONN_MAX_AGE': 3600,
        'ATOMIC_REQUESTS': True,
        'DISABLE_SERVER_SIDE_CURSORS': True,
    },
}
if IS_PROD:
    DATABASES['default'].update({
        'NAME': 'nobitex',
        'USER': 'nobitex',
        'HOST': 'db.nobitex',
        'PORT': DB_PORT,
        'PASSWORD': secret_string(
            'gAAAAABcsf3w7D8dL6pLlY_kTuqZemIbZmN8-WIcpADEB99wSFrXoUuB9jVpu9ceklxwlNc75O-hnkWgM_xgJIWSaOZ0Xgw0MdogB_0eUAac90xtUW3tnVZ3VlTqXnjx6T2m7YL08utw'),
    })
    if USE_REPLICA:
        DATABASES['default' if ONLY_REPLICA else 'replica'] = {
            'NAME': 'nobitex',
            'USER': 'nobitex',
            'HOST': REPLICA_HOST,
            'PORT': DB_PORT,
            'PASSWORD': secret_string(
                'gAAAAABcsf3w7D8dL6pLlY_kTuqZemIbZmN8-WIcpADEB99wSFrXoUuB9jVpu9ceklxwlNc75O-hnkWgM_xgJIWSaOZ0Xgw0MdogB_0eUAac90xtUW3tnVZ3VlTqXnjx6T2m7YL08utw'),
            'ENGINE': 'django.db.backends.postgresql',
            'CONN_MAX_AGE': 3600,
            'ATOMIC_REQUESTS': True,
            'DISABLE_SERVER_SIDE_CURSORS': True,
        }
elif IS_TESTNET:
    DATABASES['default'].update(
        {
            'NAME': 'testnet',
            'USER': 'testnet',
            'HOST': 'db.testnet',
            'PORT': DB_PORT,
            'PASSWORD': secret_string(
                '',
                testnet='gAAAAABl7bmXVZU-577G-KYU5Td8kG5AlhAveIAs_kPZ0KZsr8cDRNOPkw9xfO0oOXxmMRIe2CoYc-M2-HxTS1Z-Mkr2Kiu7rZRWMVJN_0LE-9dZoNyX2wM=',
            ),
        },
    )
elif IS_CI_RUNNER:
    DATABASES['default'].update(
        {
            'NAME': 'test_nobitex',
            'USER': 'test_nobitex',
            'HOST': 'db.local',
            'PORT': 5432,
            'PASSWORD': 'YxI8MWXFdYALSZlSHR6bdLpvR',
            'TEST': {'NAME': 'test_nobitex', 'USER': 'test_nobitex'},
        }
    )
else:
    DATABASES['default'].update(
        {
            'NAME': 'nobitex',
        }
    )
    if db_host := decouple_config('DATABASE_HOST', default=''):
        DATABASES['default']['HOST'] = db_host

    if db_port := decouple_config('DATABASE_PORT', default=''):
        DATABASES['default']['PORT'] = int(db_port)

    if db_user := decouple_config('DATABASE_USER', default=''):
        DATABASES['default']['USER'] = db_user

    if db_password := decouple_config('DATABASE_PASSWORD', default=''):
        DATABASES['default']['PASSWORD'] = db_password

READ_DB: str = 'replica' if 'replica' in DATABASES else 'default'
WRITE_DB = 'default'

# Cache
if IS_PROD:
    REDIS_DB_NO = 1
    REDIS_HOST = 'redis.nobitex:6379'
    REDIS_REPLICA = 'db.local:6379'
    REDIS_USE_REPLICA = os.environ.get('REDIS_USE_REPLICA', 'yes') != 'no'
    # chart api
    REDIS_CHART_DB_NO = 0
    REDIS_CHART_HOST = 'redis-chart.nobitex:6381'

elif IS_TESTNET or IS_CI_RUNNER:
    REDIS_DB_NO = 3
    REDIS_HOST = 'redis.testnet:6379'
    REDIS_USE_REPLICA = False
    # chart api
    REDIS_CHART_DB_NO = 0
    REDIS_CHART_HOST = 'redis-chart.testnet:6381'
else:
    REDIS_DB_NO = 5
    REDIS_HOST = 'localhost:6379'
    REDIS_USE_REPLICA = False
    # chart api
    REDIS_CHART_DB_NO = 7
    REDIS_CHART_HOST = 'localhost:6379'
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://{}/{}'.format(REDIS_HOST, REDIS_DB_NO),
        'TIMEOUT': None,
        'OPTIONS': {
            'PICKLE_VERSION': 4,
        },
    },
    'chart_api': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f'redis://{REDIS_CHART_HOST}/{REDIS_CHART_DB_NO}',
        'TIMEOUT': None,
        'OPTIONS': {
            'PICKLE_VERSION': 4,
        },
    },
}
if not ONLY_REPLICA:
    CACHES['default']['OPTIONS']['CLIENT_CLASS'] = 'exchange.redis_connection.RedisClient'
if USE_REDIS2:
    CACHES['w2'] = {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://redis2.nobitex:6380/0',
        'TIMEOUT': None,
        'OPTIONS': {
            'PICKLE_VERSION': 4,
        },
    }
if IS_TEST_RUNNER:
    CACHES = {
        'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'OPTIONS': {'MAX_ENTRIES': 10_000}},
        'chart_api': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        },
    }
# Use local redis replica if requested to offload reads
if REDIS_USE_REPLICA:
    MASTER_CACHE = 'redis://{}/{}'.format(REDIS_HOST, REDIS_DB_NO)
    CACHES['default']['LOCATION'] = [
        MASTER_CACHE,
        'redis://{}/{}'.format(REDIS_REPLICA, REDIS_DB_NO),
    ]
    CACHES['default']['OPTIONS']['MASTER_CACHE'] = MASTER_CACHE

# Redis-Publisher
PUBLISHER_REDIS_PASSWORD = secret_string(
    'gAAAAABmnRgTWIaMiGHeaDG8S9ZKzhMNKO0pvvrpAFsysLGOu5THz_1o6WM9FDxttB15gQtqoRYcqPCHqbvD1VN290DJpLW0ZYZlxzLzTqg48lWyH7xA0blNHaGoDb0GUIF1n_nRlBgN',
    testnet='gAAAAABmnRfeT2Py6fy9-k1kBdV4I5Xkk2kD4YGrl45N0SQ7dk7R3ZsgIY5SGYvtZCxsHiLMOgY6n3BhHjvRHCHrgDuq1_pBbr1jqe0qm9mKA6eDwG-20rfqQPgZjSkteH0V-D5pq7mK',
)
if IS_PROD:
    PUBLISHER_REDIS_URL = f'redis://default:{PUBLISHER_REDIS_PASSWORD}@redis-publisher.nobitex:6389/0'
elif IS_TESTNET or IS_CI_RUNNER:
    PUBLISHER_REDIS_URL = f'redis://default:{PUBLISHER_REDIS_PASSWORD}@redis-publisher.testnet:6389/0'
else:
    PUBLISHER_REDIS_URL = f'redis://{REDIS_HOST}/0'

# Kafka configs
KAFKA_BOOTSTRAP_SERVER = 'kafka.nobitex:9092' if IS_PROD else ('kafka.testnet:9092' if IS_TESTNET else 'localhost:9090')
KAFKA_CONFIG = {
    'bootstrap.servers': KAFKA_BOOTSTRAP_SERVER,
    'security.protocol': 'SASL_PLAINTEXT',
    'sasl.mechanism': 'PLAIN',
}
if IS_PROD:
    KAFKA_CONFIG['sasl.username'] = 'kafka'
    KAFKA_CONFIG['sasl.password'] = secret_string(
        'gAAAAABne-PLB0VWcuKS58lPHOGWiD_t0QGxPlpNokp2a_Y7iTnNXOsRh6hxN4dHtV960McW1zSzUIQ3sc_VwqmPCCSd02lq9E77DPwpg8sVht1m4eJswJhk2VPgPO4mHV5lTQtuStol',
    )
else:
    KAFKA_CONFIG['sasl.username'] = 'admin'
    KAFKA_CONFIG['sasl.password'] = 'YhD8Fg5EoV3DTZfn9DqwevDKOPqwy'

KAFKA_PRODUCER_CONFIG = {
    'linger.ms': 0,  # For lowering latency
    'batch.size': '2048',  # For lowering latency
    'acks': 'all',
    'enable.idempotence': True,
    **KAFKA_CONFIG,
}

KAFKA_CONSUMER_CONFIG = {
    'fetch.wait.max.ms': 1,  # For lowering latency
    'fetch.min.bytes': 1,  # For lowering latency
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': True,
    'auto.commit.interval.ms': 100,
    'session.timeout.ms': 10000,  # 10s
    **KAFKA_CONFIG,
}

# Logstash logger config # TODO: encrypt sensitive data
LOGSTASH_LOGGER_CONFIG = {
    'logstash_host': 'logstash-prod.nxbo.ir/core-prod'
    if IS_PROD
    else ('metrics-logs.nxbo.ir/nxbo' if IS_TESTNET else 'localhost'),
    'logstash_port': 443 if IS_PROD or IS_TESTNET else 5044,
    'logstash_username': 'Core-Prod' if IS_PROD else ('logstash-nxbo' if IS_TESTNET else 'elastic'),
    'logstash_password': secret_string(
        'gAAAAABnk2_O0RYrcvbkBYgRyQ0qgUPrRSfvKSWz_RJd1jEXMqXoyBpl2hw-CTJqtZd8sFoYlRYXZGLKI7rlrF7yLDIStLDiMWfZ6mMlmnfwvMT8aBK-6E4=',
    )
    if IS_PROD
    else ('DQbEq0VKKnFnkO' if IS_TESTNET else 'changeme'),
    'logstash_timeout': 5,  # seconds
    'logstash_ssl_enable': IS_PROD or IS_TESTNET,
    'logstash_ssl_verify': IS_PROD or IS_TESTNET,
    'logger_logs_ttl': 5 * 60,  # time in seconds to wait before expiring log messages in the cache
    'logger_database_path': None,  # for failure scenarios. None means using memory cache
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'fa-ir'
TIME_ZONE = 'Asia/Tehran'
USE_I18N = True
USE_TZ = True
LOCALE_PATHS = [
    os.path.join(BASE_DIR, "translations")
]

# Static files (CSS, JavaScript, Images)
STATIC_ROOT = os.path.join(BASE_DIR, 'static')
STATIC_URL = '/cdn/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'

# Django Login Configuration
AUTH_USER_MODEL = 'accounts.User'
LOGIN_URL = '/'
LOGIN_REDIRECT_URL = '/'
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]

# OPTIONS
#   these options are visible to end users, and sent to front app via users/preferences endpoint
NOBITEX_OPTIONS = {
    'currencies': CONFIG_OPTIONS['currencies'],
    'perCurrencyOptions': ['minOrders', 'withdrawFees', 'minWithdraws', 'maxWithdraws'],
    'tradingFees': {
        'levelVolumes': [
            Decimal('0'),
            Decimal('100_000_000_0'),
            Decimal('300_000_000_0'),
            Decimal('1_000_000_000_0'),
            Decimal('5_000_000_000_0'),
            Decimal('20_000_000_000_0'),
            Decimal('80_000_000_000_0'),
        ],
        'takerFees': [
            Decimal('0.25'),
            Decimal('0.2'),
            Decimal('0.19'),
            Decimal('0.175'),
            Decimal('0.155'),
            Decimal('0.145'),
            Decimal('0.135'),
        ],
        'makerFees': [
            Decimal('0.25'),
            Decimal('0.17'),
            Decimal('0.15'),
            Decimal('0.125'),
            Decimal('0.1'),
            Decimal('0.09'),
            Decimal('0.08'),
        ],
        'takerFeesTether': [
            Decimal('0.13'),
            Decimal('0.12'),
            Decimal('0.11'),
            Decimal('0.1'),
            Decimal('0.1'),
            Decimal('0.095'),
            Decimal('0.09'),
        ],
        'makerFeesTether': [
            Decimal('0.1'),
            Decimal('0.095'),
            Decimal('0.09'),
            Decimal('0.08'),
            Decimal('0.07'),
            Decimal('0.065'),
            Decimal('0.06'),
        ],
    },
    'baseReferralPercent': 30,
    'minOrders': {
        2: Decimal('50_000_0'),
        13: Decimal('5'),
    },
    'maxOrders': {
        'default': {
            2: Decimal('1_000_000_000_0'),
            13: Decimal('1_000_000_000_0'),
        },
        'spot': {
            2: Decimal('5_000_000_000_0'),
            13: Decimal('200_000'),
        },
    },
    'positionFeeUnits': {
        2: Decimal('1_000_000_0'),
        13: Decimal('30'),
    },
    'withdrawFees': CONFIG_OPTIONS['withdrawFees'],
    'minWithdraws': CONFIG_OPTIONS['minWithdraws'],
    'maxWithdraws': CONFIG_OPTIONS['maxWithdraws'],
    'requiredConfirms': CONFIG_OPTIONS['requiredConfirms'],
    'shetabFee': {
        'rate': Decimal('0.0002'),
        'min': 120_0,
        'max': 4_000_0,
    },
    'directDebitFee': {
        'rate': Decimal('0.002'),
        'min': 1_000_0,
        'max': 5_000_0,
    },
    'coBankFee': {
        'rate': Decimal('0.0001'),
    },
    'coBankLimits': {
        'minDeposit': 5_000_0,
        'maxDeposit': 5_000_000_000_0,
    },
    'bankFee': Decimal('120e-6'),
    'minBankDeposit': 5_000_0,
    'maxBankDeposit': 1_000_000_000_0,
    'bankDepositAccounts': [],
    'depositLimits': {
        40: Decimal('0'),
        44: Decimal('25_000_000_0'),
        45: Decimal('25_000_000_0'),
        46: Decimal('25_000_000_0'),
        90: Decimal('25_000_000_0'),
    },
    'withdrawLimits': {
        # Normal
        0: {'dailyCoin': Decimal('0'), 'dailyRial': Decimal('0'), 'dailySummation': Decimal('0'),
            'monthlySummation': Decimal('0')},
        # Level0
        40: {'dailyCoin': Decimal('0'), 'dailyRial': Decimal('0'), 'dailySummation': Decimal('0'),
             'monthlySummation': Decimal('0')},
        # Level1P
        42: {'dailyCoin': Decimal('100_000_000_0'), 'dailyRial': Decimal('5_000_000_0'),
             'dailySummation': Decimal('100_000_000_0'), 'monthlySummation': Decimal('1_500_000_000_0')},
        # Level1
        44: {'dailyCoin': Decimal('0'), 'dailyRial': Decimal('50_000_000_0'), 'dailySummation': Decimal('50_000_000_0'),
             'monthlySummation': Decimal('1_500_000_000_0')},
        # Trader
        45: {'dailyCoin': Decimal('0'), 'dailyRial': Decimal('300_000_000_0'),
             'dailySummation': Decimal('300_000_000_0'), 'monthlySummation': Decimal('9_000_000_000_0')},
        # Level2
        46: {'dailyCoin': Decimal('10_000_000_0'), 'dailyRial': Decimal('300_000_000_0'),
             'dailySummation': Decimal('310_000_000_0'), 'monthlySummation': Decimal('9_300_000_000_0')},
        # Level3
        90: {'dailyCoin': Decimal('1_000_000_000_0'), 'dailyRial': Decimal('1_000_000_000_0'),
             'dailySummation': Decimal('2_000_000_000_0'), 'monthlySummation': Decimal('60_000_000_000_0')},
        # Trusted
        92: {
            'dailyCoin': Decimal('600_000_000_000_0'),
            'dailyRial': Decimal('100_000_000_000_0'),
            'dailySummation': Decimal('600_000_000_000_0'),
            'monthlySummation': Decimal('9_000_000_000_000_0'),
        },
    },
    'positionLimits': {
        # Level1
        44: Decimal('0.03'),
        # Trader (and Level2)
        45: Decimal('0.15'),
        # Level3
        90: Decimal('0.30'),
        # Trusted
        92: Decimal('0.50'),
    },
    'liquidityPoolMinDelegationRls': '300_000_0',
    'liquidityPoolDelegateAllowedUserTypes': [
        42,  # Level 1p
        44,  # Level 1
        45,  # Trader
        46,  # Level 2
        90,  # Level3
        92,  # Trusted
    ],
    'features': {
        'fcmEnabled': True,
        'chat': 'livechat',
        'walletsToNet': False,
        'autoKYC': False,
        'enabledFeatures': [
            'PriceAlert',
            'StopLoss',
            'GiftCard',
            'OCO',
            'ShortSell',
            'Staking',
            'Leverage',
            'JibitPIP',
            'LongBuy',
            'AssetBackedCredit',
            'AssetBackedCreditLoan',
            'SocialTradingSubscriber',
            'SocialTradingLeadership',
            'Convert3',
        ],
        'betaFeatures': [],
        # 'walletsRefreshDisabled': False,
    },
    'testingNetworks': [],
    'testingCurrencies': CONFIG_OPTIONS["testingCurrencies"],
    'userTypes': {
        # Level0
        40: 'سطح ۰',
        # Level1
        44: 'سطح ۱',
        # Trader
        45: 'تریدر',
        # Level2
        46: 'سطح ۲',
        # Level3
        90: 'سطح ۳',
    },
    'rialDepositGatewayLimit': Decimal('25_000_000_0'),
}
NOBITEX_OPTIONS['withdrawLimitsWithIdentifiedMobile'] = deepcopy(NOBITEX_OPTIONS['withdrawLimits'])
NOBITEX_OPTIONS['withdrawLimitsWithIdentifiedMobile'].update(
    {
        44: {'dailyCoin': Decimal('1_000_000_0'), 'dailyRial': Decimal('50_000_000_0'),
             'dailySummation': Decimal('51_000_000_0'), 'monthlySummation': Decimal('1_530_000_000_0')},
        46: {
            'dailyCoin': Decimal('300_000_000_0'),
            'dailyRial': Decimal('300_000_000_0'),
            'dailySummation': Decimal('600_000_000_0'),  # this is sum of dailyCoin and dailyRial
            'monthlySummation': Decimal('18_000_000_000_0'),  # this is sum of dailyCoin and dailyRial * 30,
        },
    }
)
NOBITEX_OPTIONS['depositLimitsWithIdentifiedMobile'] = deepcopy(NOBITEX_OPTIONS['depositLimits'])
NOBITEX_OPTIONS['depositLimitsWithIdentifiedMobile'].update({46: Decimal('25_000_000_0')})
if IS_TESTNET:
    NOBITEX_OPTIONS['features']['autoKYC'] = True

# Generic Backend Options
#   these options are internal and end users should not see them directly
MAX_UPLOAD_SIZE = 15 * 2 ** 20  # 15 MB
MAX_TICKET_ATTACHMENT_UPLOAD_SIZE = (2 ** 10) * (2 ** 10)  # 1MB
TRADER_BOT_IDS = (
    [2331, 2369, 2652, 157175, 3503031, 3503085, 4659800, 5009942, 5229928, 5733775, 6747056] if IS_PROD else []
)
TRUSTED_USER_IDS = TRADER_BOT_IDS
ADMIN_OPTIONS = {
    'updateDepositCronIntervalMinutes': 30,
    'minBalanceHotWallets': {
        10: Decimal('0.05'),
        11: Decimal('1'),
        12: Decimal('20'),
        13: Decimal('1000'),
        14: Decimal('3000'),
        15: Decimal('10'),
        16: Decimal('5'),
        17: Decimal('1000'),
        18: Decimal('15000'),
        19: Decimal('10000'),
        20: Decimal('15000'),
        21: Decimal('3000'),
        22: Decimal('10'),
        25: Decimal('50'),
        30: Decimal('1000'),
        31: Decimal('100'),
        32: Decimal('600'),
        33: Decimal('1000'),
        34: Decimal('150'),
        35: Decimal('200'),
        36: Decimal('15'),
        37: Decimal('30'),
        38: Decimal('1300'),
        39: Decimal('300'),
        40: Decimal('8000'),
        42: Decimal('100000'),
        50: Decimal('2000'),
        56: Decimal('100'),
        57: Decimal('50'),
        58: Decimal('60'),
        60: Decimal('150'),
        65: Decimal('1500'),
        61: Decimal('750'),
        62: Decimal('2500'),
        67: Decimal('40000'),
        69: Decimal('20'),
        74: Decimal('100'),
        75: Decimal('3000'),
        76: Decimal('3000'),
        83: Decimal('1.5'),
        82: Decimal('400'),
        84: Decimal('250'),
        90: Decimal('750'),
        94: Decimal('0.2'),
        97: Decimal('1100'),
        98: Decimal('1000'),
        99: Decimal('200'),
        100: Decimal('40000'),
        101: Decimal('0.05'),
        102: Decimal('1000'),
        103: Decimal('3000'),
        106: Decimal('1100'),
        107: Decimal('5000'),
        109: Decimal('10'),
        110: Decimal('1000'),
        111: Decimal('1000'),
        112: Decimal('20000'),
        114: Decimal('3000'),
        117: Decimal('1000'),
        119: Decimal('1500'),
        120: Decimal('1000'),
        122: Decimal('250'),
        125: Decimal('70'),
        126: Decimal('150'),
        127: Decimal('4000'),
        128: Decimal('700'),
        129: Decimal('5000'),
        130: Decimal('800'),
        131: Decimal('10000'),
        132: Decimal('60'),
        133: Decimal('2500'),
        134: Decimal('150'),
        135: Decimal('30000'),
        136: Decimal('300000'),
        138: Decimal('3000'),
        139: Decimal('300'),
        140: Decimal('10'),
        141: Decimal('10000'),
        144: Decimal('300'),
        145: Decimal('500'),
        146: Decimal('300'),
        147: Decimal('4000'),
        148: Decimal('1000'),
        149: Decimal('15000'),
        150: Decimal('1500'),
        151: Decimal('1000'),
        152: Decimal('800'),
        155: Decimal('15'),
        164: Decimal('600'),
        165: Decimal('2000'),
    },
    'minBalanceBinance': 5000,
    'minBalanceKraken': 3000,
    'blockTime': {
        10: 600,
        11: 15,
        12: 150,
        13: 15,
        14: 3,
        15: 600,
        16: 1,
        17: 1,
        18: 60,
        19: 1,
        20: 3,
        21: 20,
        22: 120,
        25: 15,
        30: 13,
        31: 5,
        37: 0.4,
        39: 30,
        56: 6.5,
        74: 6,
        84: 1,
        100: 2,
        111: 1,
        103: 4.5,
        122: 4,
    },
}

# Blockchain Options
BLOCKCHAIN_CACHE_PREFIX = ''
USE_TESTNET_BLOCKCHAINS = not IS_PROD

# Two Factor Auth
OTP_TOTP_SYNC = False
OTP_TOTP_ISSUER = 'Nobitex'  # for display in TFA
if not IS_PROD:
    OTP_TOTP_ISSUER += '-' + ENV

# Crons
DJANGO_CRON_LOCK_TIME = 30 * 60
DJANGO_CRON_LOCK_BACKEND = 'exchange.base.crons.CustomCronLock'
DJANGO_CRON_DELETE_LOGS_OLDER_THAN = 7
VERY_LONG_RUNNING_CRONS = [
    'SaveDailyDirectDeposits',
]
LONG_RUNNING_CRONS = [
    'UpdateWebEngageUserData',
    'UserTradeStatusCron',
    'AutoVerificationCron',
    'SaveDailyUserProfit',
    'UpdateOtherPendingDepositCron',
    'UpdateBtcPendingDepositCron',
    'UpdateTrxPendingDepositCron',
    'UpdateLtcPendingDepositCron',
    'UpdateBchPendingDepositCron',
    'UpdateDogePendingDepositCron',
    'UpdateBscPendingDepositCron',
    'UpdateDepositsCron',
    'UpdateBitcoinCashDepositsCron',
    'UpdateTronDepositsCron',
    'UpdateBitcoinDepositsCron',
    'UpdateDogecoinDepositsCron',
    'UpdateLitecoinDepositsCron',
    'UpdateAdaDepositsCron',
    'UpdateTagDepositsCron',
    'UpdateMoneroDepositCron',
    'UpdateAlgoDepositCron',
    'UpdateFlowDepositCron',
    'UpdateFilecoinDepositCron',
    'UpdateAptosDepositCron',
    'UpdateElrondDepositCron',
    'UpdateTezosDepositCron',
    'UpdatePolkadotDepositCron',
    'UpdateSonicDepositCron',
    'UpdateBaseDepositCron',
    'CheckDepositDiffOthers',
    'CheckDepositDiffTrx',
    'CheckDepositDiffTon',
    'CheckDepositDiffDoge',
    'CheckDepositDiffLtc',
    'CheckDepositDiffBtc', 'CheckDepositDiffBch', 'CheckDepositDiffMatic', 'CheckDepositDiffFtm', 'CheckDepositDiffBsc',
    'CheckDepositDiffEth', 'CheckDepositDiffSol', 'CheckDepositDiffAda', 'CheckDepositDiffNear', 'CheckDepositDiffAvax',
    'CheckDepositDiffAlgo', 'CheckDepositDiffEtc', 'CheckDepositDiffBnb', 'CheckDepositDiffAtom', 'CheckDepositDiffXrp',
    'CheckDepositDiffSonic',
    'CheckDepositDiffBase',
    'CheckDepositDiffStatusCron', 'CheckWithdrawDiffStatusCron', 'CheckBinanceWithdrawDepositCron',
]
CRON_CLASSES = [
    # Activate Portfolio Cron
    'exchange.features.crons.ActiveDailyUserPortfolio',
    # General Crons
    'exchange.accounts.crons.UpdateCacheCron',
    'exchange.accounts.crons.TokenExpiryCron',
    'exchange.base.crons.FetchCurrencyValuesCron',
    'exchange.base.crons.ResetAPILimitsCron',
    'exchange.accounts.crons.DelayedRestrictionRemoval',
    # Captcha Crons
    'exchange.accounts.crons.PopulateCaptchaPool',
    # SystemCron
    'exchange.wallet.crons.CheckWithdrawRequestsCron',
    'exchange.market.crons.SystemFeeWalletChargeCron',
    'exchange.market.crons.ReferralFeeCalculationCron',
    'exchange.market.crons.UserTradeStatusCron',
    'exchange.market.crons.MarketActiveOrdersMetricCron',
    'exchange.report.crons.UpdateDailyStatsCron',
    'exchange.market.crons.FixAddAsyncTradeTransactionCron',
    # Generate Portfo Cron
    'exchange.portfolio.crons.SaveDailyUserProfit',
    # Maintenance Crons
    'exchange.market.crons.DeleteCanceledOrdersCron',
    'exchange.system.crons.CleanupCron',
    # KYC Crons
    'exchange.accounts.crons.AutoVerificationCron',
    'exchange.accounts.crons.DeleteUncompletedMergeRequest',
    'exchange.integrations.crons.FinnotechTokenRefreshCron',
    # Regular Background Checks
    'exchange.market.crons.AdminsNotificationCron',
    'exchange.shetab.crons.CheckInvalidShetabDepositCron',
    # Gift Crons
    'exchange.gift.crons.SendGiftRedeemCodes',
    'exchange.gift.crons.VerifyGifts',
    # Web Engage Crons
    'exchange.web_engage.crons.CreateAndSendBatchSMS',
    'exchange.web_engage.crons.InquireSentBatchSMSStatus',
    'exchange.web_engage.crons.CleanUpEmailLogs',
    'exchange.web_engage.crons.UpdateWebEngageUserData',
    # Margin Crons
    'exchange.margin.crons.PositionExpireCron',
    'exchange.margin.crons.PositionExtensionFeeCron',
    'exchange.margin.crons.MarginCallManagementCron',
    'exchange.margin.crons.MarginCallSendingCron',
    'exchange.margin.crons.CanceledPositionsDeleteCron',
    'exchange.wallet.crons.MarginBlockedBalanceCheckerCron',
    'exchange.margin.crons.NotifyUpcomingPositionsExpirationCron',
    # Staking Crons
    'exchange.staking.crons.UpdatePlansCron',
    'exchange.staking.crons.UserWatchCron',
    # Promotions Crons
    'exchange.promotions.crons.DiscountUpdateCron',
    # Liquidity Pool Crons
    'exchange.pool.crons.CheckDelegationRevokeRequestCron',
    'exchange.pool.crons.UnfilledCapacityAlertCron',
    'exchange.pool.crons.MinimumRatioAvailableCapacityAlertCron',
    'exchange.pool.crons.NotifyPendingDelegationRevokeRequestCron',
    'exchange.pool.crons.CalculateDailyPoolProfitsCron',
    'exchange.pool.crons.DistributeUsersProfitCron',
    'exchange.pool.crons.DelegationLimitsCron',
    # Vandar ID Deposit
    'exchange.shetab.crons.SyncVandarDepositCron',
    # Vip Credit Cron
    'exchange.credit.crons.CreditLimitForAdminNotificationCron',
    # Transaction History Crons
    'exchange.wallet.crons.RemoveOldTransactionHistoriesCron',
    # Convert Crons
    'exchange.xchange.crons.FailOldUnknownTradesCron',
    'exchange.xchange.crons.XchangeNotifyAdminOnMarketApproachingLimitsCron',
    'exchange.xchange.crons.XchangeCollectTradesFromMarketMakerCron',
    # Social Trade
    'exchange.socialtrade.crons.SendPreRenewalNotifCron',
    'exchange.socialtrade.crons.RenewSubscriptionsCron',
    'exchange.socialtrade.crons.SendUpcomingRenewalNotifCron',
    'exchange.socialtrade.crons.UpdateWinratesCron',
    'exchange.socialtrade.crons.SendLeadersTradesNotifCron',
    'exchange.socialtrade.crons.UpdateLeaderProfitsCron',
    # Asset Backed Credit
    # ...
    # Direct Debit Crons
    'exchange.direct_debit.crons.DirectDebitExpiredContracts',
    'exchange.direct_debit.crons.DirectDebitContractCreateOrUpdateTimeoutCron',
    'exchange.direct_debit.crons.DirectDebitCheckTimeoutDepositCron',
    'exchange.report.crons.SaveDailyDirectDeposits',
    # Corporate Banking -- CoBank
    'exchange.corporate_banking.crons.RefreshTokenCron',
    'exchange.corporate_banking.crons.GetStatementsCron',
    'exchange.corporate_banking.crons.GetDailyStatementsCron',
    'exchange.corporate_banking.crons.SettleDepositsCron',
    'exchange.corporate_banking.crons.GetAccountsCron',
    # Corporate Banking -- CoBank - JIBIT
    'exchange.corporate_banking.crons.RefreshJibitTokenCron',
    # Corporate Banking -- CoBank - TOMAN
    'exchange.corporate_banking.crons.RefundRequestsHandlerCron',
    'exchange.corporate_banking.crons.RefundInquiryRequestsHandlerCron',
    # Liquidator
    'exchange.liquidator.crons.DeleteEmptyLiquidation',
]

if IS_TESTNET:
    CRON_CLASSES += [
    ]

if IS_PROD:
    CRON_CLASSES += [
        # Shetab Gateways Crons
        'exchange.shetab.crons.SyncShetabDepositsCron',
        'exchange.shetab.crons.SyncJibitDepositCron',
        # Report Crons
        'exchange.report.crons.SaveDailyDepositsV2',
        'exchange.report.crons.SaveDailyWithdrawsV2',
        'exchange.report.crons.OldDataUpdateDailyWithdraws',
        'exchange.report.crons.SaveBanksGatewayStatsCron',
        'exchange.report.crons.DailyWithdrawsManuallyFailedV2',
        'exchange.report.crons.SaveJibitBankDeposits',
    ]

if DEBUG or IS_TESTNET:
    CRON_CLASSES.append('exchange.market.crons.UpdateUSDValueCron')
if RUN_ONLY_BLOCKCHAIN_CRONS:
    CRON_CLASSES = [
        # Deposit Pending Crons
        'exchange.wallet.crons.UpdateOtherPendingDepositCron',
        'exchange.wallet.crons.UpdateBtcPendingDepositCron',
        'exchange.wallet.crons.UpdateTrxPendingDepositCron',
        'exchange.wallet.crons.UpdateLtcPendingDepositCron',
        'exchange.wallet.crons.UpdateBchPendingDepositCron',
        'exchange.wallet.crons.UpdateDogePendingDepositCron',
        'exchange.wallet.crons.UpdateBscPendingDepositCron',
        # Deposit Crons
        'exchange.wallet.crons.UpdateDepositsCron',
        # Deposit Detection Crons
        'exchange.wallet.crons.UpdateBitcoinCashDepositsCron',
        'exchange.wallet.crons.UpdateTronDepositsCron',
        'exchange.wallet.crons.UpdateBitcoinDepositsCron',
        'exchange.wallet.crons.UpdateDogecoinDepositsCron',
        'exchange.wallet.crons.UpdateLitecoinDepositsCron',
        'exchange.wallet.crons.UpdateAdaDepositsCron',
        'exchange.wallet.crons.UpdateTagDepositsCron',
        'exchange.wallet.crons.UpdateMoneroDepositCron',
        'exchange.wallet.crons.UpdateAlgoDepositCron',
        'exchange.wallet.crons.UpdateFlowDepositCron',
        'exchange.wallet.crons.UpdateFilecoinDepositCron',
        'exchange.wallet.crons.UpdateAptosDepositCron',
        'exchange.wallet.crons.UpdateElrondDepositCron',
        'exchange.wallet.crons.UpdateEnjinDepositCron',
        'exchange.wallet.crons.UpdateTezosDepositCron',
        'exchange.wallet.crons.UpdatePolkadotDepositCron',
        'exchange.wallet.crons.UpdateSonicDepositCron',
        'exchange.wallet.crons.UpdateBaseDepositCron',
        # Deposit Diff Crons
        'exchange.wallet.crons.CheckDepositDiffOthers',
        'exchange.wallet.crons.CheckDepositDiffTrx',
        'exchange.wallet.crons.CheckDepositDiffTon',
        'exchange.wallet.crons.CheckDepositDiffDoge',
        'exchange.wallet.crons.CheckDepositDiffLtc',
        'exchange.wallet.crons.CheckDepositDiffBtc',
        'exchange.wallet.crons.CheckDepositDiffBch',
        'exchange.wallet.crons.CheckDepositDiffMatic',
        'exchange.wallet.crons.CheckDepositDiffFtm',
        'exchange.wallet.crons.CheckDepositDiffBsc',
        'exchange.wallet.crons.CheckDepositDiffEth',
        'exchange.wallet.crons.CheckDepositDiffSol',
        'exchange.wallet.crons.CheckDepositDiffAda',
        'exchange.wallet.crons.CheckDepositDiffNear',
        'exchange.wallet.crons.CheckDepositDiffAvax',
        'exchange.wallet.crons.CheckDepositDiffAlgo',
        'exchange.wallet.crons.CheckDepositDiffEtc',
        'exchange.wallet.crons.CheckDepositDiffBnb',
        'exchange.wallet.crons.CheckDepositDiffAtom',
        'exchange.wallet.crons.CheckDepositDiffXrp',
        'exchange.wallet.crons.CheckDepositDiffSonic',
        'exchange.wallet.crons.CheckDepositDiffBase',
        # Withdraw/Deposit Audit Crons
        'exchange.wallet.crons.CheckDepositDiffStatusCron',
        'exchange.wallet.crons.CheckWithdrawDiffStatusCron',
        'exchange.wallet.crons.CheckBinanceWithdrawDepositCron',
        # Balance Crons
        'exchange.wallet.crons.BalanceCheckerCron',
    ]

# Security
USE_HTTPS = not DEBUG
CSRF_COOKIE_SECURE = USE_HTTPS
SESSION_COOKIE_AGE = 172800
SESSION_COOKIE_SECURE = USE_HTTPS
SESSION_COOKIE_HTTPONLY = True

# DDoS Protection
FILE_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE
RATELIMIT_USE_CACHE = 'w2' if USE_REDIS2 else 'default'
RATELIMIT_FAIL_OPEN = True
RATELIMIT_ENABLE = not IS_TEST_RUNNER

# CORS
from corsheaders.defaults import default_headers

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = default_headers + ('Cache-Control', 'X-TOTP', 'X-SOTP')
CORS_ORIGIN_WHITELIST = [domain.replace('testnetapi.', 'testnet.').replace('api.', '') for domain in ALLOWED_HOSTS]
# Allow main site to connect to testnet APIs, useful for competitions
if IS_TESTNET:
    CORS_ORIGIN_WHITELIST += PROD_DOMAINS
    # Allow Payment Gateway
    CORS_ORIGIN_WHITELIST += ['testnetpay.nobitex.ir', 'devnet.nobitex.ir']
else:
    CORS_ORIGIN_WHITELIST += ['pay.nobitex.ir']
# Qualify domains with https scheme
CORS_ORIGIN_WHITELIST = ['https://' + domain for domain in CORS_ORIGIN_WHITELIST]
# Allow development code to connect directly to testnet as API server
if DEBUG or IS_TESTNET:
    CORS_ORIGIN_WHITELIST.append('http://localhost:4000')
if DEBUG:
    CORS_ORIGIN_WHITELIST.append('https://testnet.nobitex.ir')

# Celery
TELEGRAM_CELERY_QUEUE = 'telegram'
TELEGRAM_ADMIN_CELERY_QUEUE = 'telegram_admin'
CELERY_BROKER_URL = 'redis://{}/{}'.format(REDIS_HOST, 8 + REDIS_DB_NO)
CELERY_TASK_ROUTES = {
    # Queue: market, Usually important market functionalities
    'update_recent_trades_cache': {'queue': 'market'},
    # TODO: Remove this queue after the next release.
    #       This queue was retained to handle any previously pending tasks of this type.
    #       After the new release, no new tasks will append to this queue.
    #       Once a short period has passed to ensure all pending tasks are processed,
    #       this queue can be safely deleted.
    'commit_trade_async_step': {'queue': 'market'},
    'batch_commit_trade_async_step': {'queue': 'market'},
    # Queue: admin, used for administration tasks
    'shetab_deposit_sync': {'queue': 'admin'},
    'shetab_deposit_sync_card': {'queue': 'admin'},
    'update_user_invalid_deposits': {'queue': 'admin'},
    'cancel_order': {'queue': 'admin'},
    'update_withdraw_status': {'queue': 'admin'},
    'generate_addresses': {'queue': 'admin'},
    'create_user_discount': {'queue': 'admin'},
    'nobitex_delegate': {'queue': 'admin'},
    'generate_nobitex_delegator_deposit_address': {'queue': 'admin'},
    'staking.admin.*': {'queue': 'admin'},
    'credit.admin.*': {'queue': 'admin'},
    'update_delegation_revoke_request': {'queue': 'admin'},
    'check_settle_delegation_revoke_request': {'queue': 'admin'},
    'user_merge': {'queue': 'admin'},
    'reject_merge_request': {'queue': 'admin'},
    'deactivate_user_tokens': {'queue': 'admin'},
    'send_feature_web_engage': {'queue': 'admin'},
    'fetch_jibit_history': {'queue': 'admin'},
    'revoke_tasks_sending_sms_by_template': {'queue': 'admin'},
    'direct_debit.admin.update_direct_deposit': {'queue': 'admin'},
    # Queue: accounts, used for registration & user interaction
    'send_user_sms': {'queue': 'accounts'},
    'notify_stop_order_activation': {'queue': 'accounts'},
    'convert_card_number_to_iban': {'queue': 'accounts'},
    'retry_calling_auto_kyc_api': {'queue': 'accounts'},
    'create_captcha_pool': {'queue': 'accounts'},
    # Queue: Withdraw email
    'send_withdraw_email_otp': {'queue': 'withdraw_otp_email'},
    # Queue: cache, can be purged if necessary
    'update_user_trades_status': {'queue': 'cache'},
    'update_chart_cache': {'queue': 'cache'},
    'init_candles_cache': {'queue': 'cache'},
    # Queue: notif, for sending Telegram notifications
    'exchange.base.tasks.send_telegram_message': {'queue': TELEGRAM_CELERY_QUEUE},
    'send_telegram_message': {'queue': TELEGRAM_CELERY_QUEUE},
    'send_email': {'queue': 'notif'},
    # Queue: blockchain, for detecting deposit
    'refresh_address_deposits': {'queue': 'blockchain'},
    'extract_contract_addresses': {'queue': 'blockchain'},
    'refresh_currency_deposits': {'queue': 'blockchain'},
    # Queue: support, for admin's smart support subsystem
    'support.*': {'queue': 'support'},
    # Queue: webengage, for sending events to Web Engage service
    'task_send_user_data_to_web_engage': {'queue': 'webengage'},
    'task_send_event_data_to_web_engage': {'queue': 'webengage'},
    'task_send_user_referral_data_to_web_engage': {'queue': 'webengage'},
    'task_send_user_campaign_data_to_web_engage': {'queue': 'webengage'},
    'task_send_dsn_to_web_engage': {'queue': 'webengage'},
    'web_engage_send_batch_sms_to_ssp': {'queue': 'webengage_ssp'},
    'admin.*': {'queue': 'nxbo'},
    'detectify.*': {'queue': 'detectify'},
    'margin.liquidate_positions': {'queue': 'margin_liquidation'},
    'margin.*': {'queue': 'margin'},
    'staking.core.*': {'queue': 'staking'},
    'shetab.admin.add_vandar_customer': {'queue': 'admin'},
    'credit.core.*': {'queue': 'credit'},
    # Queue: files, for tasks needing access to shared file storage
    'export_transaction_history': {'queue': 'files'},
    # Social Trade Tasks
    'socialtrade.core.notif.*': {'queue': 'notif'},
    'socialtrade.core.logic.*': {'queue': 'socialtrade'},
    'socialtrade.admin.*': {'queue': 'admin'},
    # Asset Backed Credit Tasks
    'abc.core.*': {'queue': 'abc'},
    # Xchange Tasks
    'xchange.*': {'queue': 'xchange'},
    # Direct Debit Tasks
    'direct_debit.notif.*': {'queue': 'notif'},
    'direct_debit.core.*': {'queue': 'direct_debit'},
    'corporate_banking.core.*': {'queue': 'corporate_banking'},
    'corporate_banking.admin.*': {'queue': 'admin'},
    # Integrations
    'integrations.*': {'queue': 'integrations'},
    # Liquidator
    'liquidator.core.create_internal_order': {'queue': 'liquidator_internal_orders'},
    'liquidator.core.*': {'queue': 'liquidator'},
}

CELERY_TIMEZONE = TIME_ZONE

# Rest Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.TokenAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'EXCEPTION_HANDLER': 'exchange.base.api.exception_handler',
}

# Rest Authentication
REST_AUTH = dict(
    USE_JWT=False,
    SESSION_LOGIN=False,
)

AUTH_TOKEN_CACHE = 'default'

# Email (PostOffice)
EMAIL_BACKEND_OPTIONS = {
    'postfix': {
        'host': 'mailer1.nobitex.ir',
        'port': 25,
        'user': 'info@nobitex.ir',
        'password': '',
        'use_tls': False,
    },
    'postfix2': {
        'host': 'mailer2.nobitex.ir',
        'port': 25,
        'user': 'info@nobitex.ir',
        'password': '',
        'use_tls': False,
    },
    'postfix3': {
        'host': 'mailer3.nobitex.ir',
        'port': 25,
        'user': 'info@nobitex.ir',
        'password': '',
        'use_tls': False,
    },
    'postfix4': {
        'host': 'mailer4.nobitex.ir',
        'port': 25,
        'user': 'info@nobitex.ir',
        'password': '',
        'use_tls': False,
    },
    'infobip': {},
    'mailtrap': {
        'host': 'smtp.mailtrap.io',
        'port': 2525,
        'user': os.getenv('MAILTRAP_USER') or '40d7e3a73fd937',
        'password': os.getenv('MAILTRAP_PASSWORD') or '5b5cca448ef121',
    },
}
EMAIL_ACTIVE_BACKEND = 'postfix'
if DEBUG:
    EMAIL_ACTIVE_BACKEND = 'mailtrap'
EMAIL_BACKEND = 'post_office.EmailBackend'
EMAIL_DEFAULT_PRIORITY = 'high'
EMAIL_HOST = EMAIL_BACKEND_OPTIONS[EMAIL_ACTIVE_BACKEND]['host']
EMAIL_PORT = EMAIL_BACKEND_OPTIONS[EMAIL_ACTIVE_BACKEND]['port']
EMAIL_HOST_USER = EMAIL_BACKEND_OPTIONS[EMAIL_ACTIVE_BACKEND]['user']
EMAIL_HOST_PASSWORD = EMAIL_BACKEND_OPTIONS[EMAIL_ACTIVE_BACKEND]['password']
EMAIL_USE_TLS = True
EMAIL_TIMEOUT = 20
EMAIL_FROM = 'Nobitex Updates <notifications@nobitex.ir>'
EMAIL_BATCH_TO = 'info@nobitex.ir'
POST_OFFICE = {
    'SENDING_ORDER': ['created'],
    'BATCH_SIZE': 1000,
    'CELERY_ENABLED': False,
    'BACKENDS': {
        'default': 'exchange.base.emailbackends.NobitexEmailBackend',
        'critical': 'exchange.base.emailbackends.NobitexEmailBackend',
        'postfix': 'exchange.base.emailbackends.NobitexEmailBackend',
        'postfix2': 'exchange.base.emailbackends.NobitexEmailBackend2',
        'postfix3': 'exchange.base.emailbackends.NobitexEmailBackend3',
        'postfix4': 'exchange.base.emailbackends.NobitexEmailBackend4',
        'infobip': 'exchange.base.emailbackends.InfoBipEmailBackend',
    },
}

# SS Hooks
SS_TOKENS = {
    'restart-etc': secret_string(
        'gAAAAABeggQcOzEruYh2C3HRuUh1ljA0uFqcCTrCmeGPnbjH_0yxlY0RvotxcW9hdJd4I85qbyH5qa7yehkiaCERyeWut0t5CE4z3gDKEfdwrzqL15-QSSNfPjEfpX5EjRXpu4gkVrmq'),
}

# Monitoring
MONITORING_USERNAME = secret_string(
    'gAAAAABmHBRoXprsqIsNGWCd4cpMtZVsUwIbXmm6lma0k-SRaA5hdHoNlvU77h7wJuOFE8qj3VPIwThTy3Y0NroWhl6DtvdDnh9cAYgGTs3gZOdDlypOZgFGPOQPqntUWGU7fV49CMt6',
    testnet='gAAAAABmHBRtX4tQMU8yloK0XJx-ZEEDN6OClbbyXTYqe_VkHe24Z8LmNDmRPh2pd-3JYjjdfS6a9pnhAD1aIy6hkIWmQ0Qu4F4FciMxFzXdxQ5Z2qk3TBLJCIzKIlNVPcnkghi7ax5Q',
)
MONITORING_PASSWORD = secret_string(
    'gAAAAABmHBTAMaYnuHziCFGnFdtLT5FbPnXyIJ0cSnrLLAhfhcadkq5SIv6Y3MCgpwf92wKPsnGgS-rCegnUbRAv4c8ZQOXPIBCd4rzsUidkjS6yU0jvZKks9EtkWEfz0P3ogzyQHtD_',
    testnet='gAAAAABmHBTFTm1byvJHen4fKdjSBwtlwDJASt5prEQSwP8DoGR3q_aW-1OYqou6k0GWrmdpzmmAzytruhMaquzwXOyJ8yQPKEpYKbuyErgzGJUqYQ0Lpw8oq6Cxip4QVook1duuPY_Y',
)

# Logging - Sentry
INTERNAL_IPS = ['127.0.0.1'] if DEBUG else []
ENABLE_SENTRY = not DEBUG and LOAD_LEVEL < 10
METRICS_BACKEND = 'sentry' if ENABLE_SENTRY else 'logger'
if ENABLE_SENTRY:
    from exchange.base.sentry import before_send, traces_sampler

    transaction_style = 'function_name'
    if IS_TESTNET:
        dsn = 'https://3c0469bb0db045398dc0ecf48e7c2c78@sentry.hamravesh.com/5604'
        enable_tracing = True
        SENTRY_TRACES_SAMPLE_RATE = 0.0005  # 0.05% chance of sending trace to sentry
        transaction_style = 'url'
    elif BLOCKCHAIN_SERVER:
        dsn = 'https://78d9f5bfbae46fcc14e41f856e17dc2c@sentry.hamravesh.com/7009'
        enable_tracing = False
        SENTRY_TRACES_SAMPLE_RATE = 0
    else:
        dsn = 'https://3c0469bb0db045398dc0ecf48e7c2c78@sentry.hamravesh.com/5604'
        enable_tracing = True
        SENTRY_TRACES_SAMPLE_RATE = 0.00003  # ~3 event per min, with avg ~1600 rps
        transaction_style = 'url'


    @signals.celeryd_init.connect
    def init_sentry(**kwargs):
        sentry_sdk.init(
            dsn=dsn,
            integrations=[
                DjangoIntegration(transaction_style=transaction_style),
                CeleryIntegration(monitor_beat_tasks=True),
            ],
            release=RELEASE_VERSION,
            environment=ENV,
            send_default_pii=True,
            before_send=before_send,
            enable_tracing=enable_tracing,
            traces_sampler=traces_sampler,
        )
        with configure_scope() as sentry_scope:
            sentry_scope.set_tag('commit', CURRENT_COMMIT)


    init_sentry()

# Logging - Telegram
TELEGRAM_MAX_RETRIES = 2
TELEGRAM_GROUPS_IDS = {
    'main': '-1001216698242',  # Nobitex
    'notifications': '-1001379604352',  # Market Message
    'critical': '-1001473957932',  # Critical Messages
    'operation': '-1001728332050',  # Operation Message
    'matcher': '-1001709987697',  # Matcher Message
    'test': '-267453237',  # Testnet Message
    'important': '-1001601869357',  # Important Message
    'important_ton': '-4547398322',  # Important Ton Message
    'important_xchange': '-1002294314212',  # Convert (Xchange) Important Message
    'pool': '-1001910326811',  # Liquidity-Pool Message
    'staking': '-910714306',  # Staking Messages
    'system_diff': '-1001837509509',  # SystemDiff Messages
    'mark_price': '-1002037749368',  # MarkPrice Messages
    'identity_inquiries': '-1002235579770',  # Identity Inquiries Messages
    'liquidator': '-1002298257692',  # Liquidator Massege
}
if IS_PROD:
    ADMINS_TELEGRAM_GROUP = TELEGRAM_GROUPS_IDS['notifications']
else:
    ADMINS_TELEGRAM_GROUP = TELEGRAM_GROUPS_IDS['test']

# Timed Features
NOBITEX_EPOCH = datetime.datetime(2018, 1, 1, 0, 0, 0, 0, pytz.utc)
LAST_DEPLOY_TIME = datetime.datetime.now(pytz.utc)

# Application State Checks
if IS_PROD:
    if SECRET_KEY[0] != '^':
        raise ValueError('Invalid SECRET_KEY')
    if USE_TESTNET_BLOCKCHAINS:
        raise ValueError('Blockchain Testnet Error')

if IS_PROD:
    LND_SERVER_URL = 'https://lnurlapi.nobitex.ir/addgifts'
else:
    LND_SERVER_URL = 'https://tlnurlapi.nobitex.ir/addgifts'

GIFT_CARD_PHYSICAL_AMOUNTS = [
    Decimal('100_000_0'),
    Decimal('200_000_0'),
    Decimal('500_000_0'),
    Decimal('1_000_000_0'),
    Decimal('2_000_000_0'),
]

if IS_PROD:
    WEB_ENGAGE_LICENSE_CODE = secret_string(
        'gAAAAABiy_MFBNg9tOwutvjZ2X9nCCkaICp4jXSrZKjq91TZlXBlPR4KwxgKeNlef_DIhFC_gWVHLBN77Jvj8MyE49YfuvxT0g==')
    WEB_ENGAGE_API_KEY = secret_string(
        'gAAAAABjZVwjtpriu0ZUq069oK7FEQp--0mzbNjBQWt2nojhhklqN8rUX3EjRKgrQSw1K2x9CfK_B_BRF2RSeC3EUR3i29TRHkTwi5ChKPHph4WIEJTlJE2SAxd-oeHpyVUtQKHrVy8t')
else:
    WEB_ENGAGE_LICENSE_CODE = '11b564764'
    WEB_ENGAGE_API_KEY = '395c0fa7-19b5-472c-a70b-f9c3a5699d56'

WEB_ENGAGE_PRIVATE_SSP_WEBHOOK = os.environ.get(
    "WEB_ENGAGE_PRIVATE_SSP_WEBHOOK", "https://st.webengage.com/tracking/privatessp-events"
)
WEB_ENGAGE_PRIVATE_ESP_TOKEN = (
    secret_string(
        'gAAAAABoKzh-ZxJLY36qMFxZqPf4T3cu2jB5anhPHlvI2uNFTH7Fvd26Vr01mnvgnqc_QoDQeruXztz-NtomnCLCV2MHwzuvRw==',
    )
    if IS_PROD
    else '11b564764'
)
WEB_ENGAGE_PRIVATE_ESP_WEBHOOK = f'https://et.webengage.com/tracking/{WEB_ENGAGE_PRIVATE_ESP_TOKEN}/private-esp-events'

# Email Managers config
ESP_INFOBIP_URL = os.environ.get('ESP_Infobip_URL', 'https://gyex56.api.infobip.com')
ESP_LOG = {'max_size': 10000, 'max_history': 90}
ESP_INFOBIP_NOTIFY_URL = (
    f'{PROD_API_URL if IS_PROD else TESTNET_API_URL}/webhooks/webengage/esp_delivery_status_webhook'
)
ESP_INFOBIP_API_KEY = os.environ.get('ESP_INFOBIP_API_KEY', '') or secret_string(
    'gAAAAABndZQ2hKkUad0WoTNzERIEupGtOUzgnlASasqWjenchdbD_0dc7lCwo_6HZDXDw78fQB8BjbxI-HQGLt3C-O1txZGx083N1yOn0UXIjnXXrYwyrYXdrqCChtJWlYfq-O1WncOH5OMrINuDjxY8Pr62nfMPeZOcLEEk3_CoNjJzo-20JGs=',
    testnet='gAAAAABndZRep0EKBquwpzwrYG5O3Z6Q8eoV0-pPWCfjVRk4QEFCUzTfjuotKLyQdMebQPX0gUTIwWMjDcfFY7JJtH9CtqafDzmy15rueiBCqgevWsG9aEVX2AA-MCL-3VANd1YagN7NW90_7_P51io-VQwYb_Um12OKy8ZTUSIOmd2NxmJznUo=',
)

# Third Party Integrations
FATA_API_PUBLIC_KEY = os.environ.get("FATA_API_PUBLIC_KEY", "")
FATA_USERNAME = os.environ.get("FATA_USERNAME", "fata")
FATA_PASSWORD = os.environ.get("FATA_PASSWORD", "")

# Finnotech APIs
MARKETING_FINNOTEXT_CLIENT_ID = os.environ.get('MARKETING_FINNOTEXT_CLIENT_ID', 'nobitex')
MARKETING_FINNOTEXT_FROM_NUMBER = os.environ.get('MARKETING_FINNOTEXT_FROM_NUMBER', '2000256' if IS_PROD else '2000666')

# SMS: sms.ir
SMSIR_API_KEY = secret_string(
    'gAAAAABk0PnNNUxktSQ7SvidAFEqTEhlKql4LzZufqNXBchm8zfOqegTtWHxDInsabqAazYICHCTzlbSfVMVvet9IlA0bdd_FCNXivrjap0CuYuC1DyhiwY=')
SMSIR_SECRET_KEY = secret_string(
    'gAAAAABk0Pm6xuYJgeVJ4EI0wWbCdDioBLMO4vDBBZnfvZrsgBwVMAUSp5QzO5hJzx3CLSrFgMEZWvuG7Q1Jh6H9G3mViKBiOur1IsqBPgfVRRR5f65PqHc=')
NEW_SMSIR_API_KEY = secret_string(
    'gAAAAABmzyMxGZ_E6Mwn7dM3UdeV3vrHZq2pfMdDDJZ1ZaxQvrB2JPL4pNwfBAqvO36upqV2s05pNSMYMS8Dpna-bPxnWAYV2cFi3NJ04FwUMgChzMcsG5Z023c7n_X8QSwv6cSpxWfXPIy7mJW-YDPvk4Vrtrv61Ofi0gC79UqoP4wo_z2JlRw=',
)
KAVENEGAR_SMS_API_KEY = KAVENEGAR_API_KEY

# S3 Storage
USE_S3 = IS_TESTNET or IS_PROD
AWS_S3_ENDPOINT_URL = 'https://s3.ir-thr-at1.arvanstorage.ir'
AWS_S3_REGION_NAME = 'ir-thr-at1'
AWS_S3_ACCESS_KEY_ID = secret_string(
    'gAAAAABk3KEbCmiFhKC_zfE0b8oTxyfX9STiw6jTNl5OhSt-u23wKizt9m00GjHvyF8eE4fWFDfb4f03WpjTlfuI0Rr3EYUqrPyADRtu8Djc1arhFeL70YDgRZ05j6Ybhcm_KMsgvK5i',
    testnet='gAAAAABk3KFhxIqc34hAolLvtZTQZGImIGHGx_wuPGzH8ua0lFdGRWGycFDxQAr4u4Nh3sIEhTReIDkuNRYI5R8c00RP7s8xlSWmkWr2eSFH3qDwBy42m35KizDflVjNNjOyFeyXCRY1',
)
AWS_S3_SECRET_ACCESS_KEY = secret_string(
    'gAAAAABk3KEuIm2uUn3pHz4imfhCwMWBQz8ue5V-AWWHUAuZuHQaus9WuW1JcMtz1rmeWLBfw7lqgmnicUnd1IQtBMgYT_zUZQbRbEB8PmcBwQDYFLgzdKlQ_ladg4XRProDfLRNAI0e',
    testnet='gAAAAABk3KF6LKijDXWq_z9Wjjp9YD_P02DxDAsrQ_qKcEJB7f5A0SLsNOFi5lUUTj0KYAQvVfPoszqSMQYh6qe-7vBjGiQOFdx5b-k92J6n7ahhJvD84iYeVUprenEd18vi-ebv5r0e',
)
if IS_PROD:
    AWS_STORAGE_BUCKET_NAME = 'nobitex-core-static'
else:
    AWS_STORAGE_BUCKET_NAME = 'testnet-core-static'

# To remove AWSAccessKeyId from the url
AWS_QUERYSTRING_AUTH = False

# Captcha: old
# TODO: remove usage of old captcha
RECAPTCHA_PRIVATE_KEY = '6LeZBUIUAAAAAAGc9jxCXrFTF5nO_6VIerP5ZFmK'
RECAPTCHA_PUBLIC_KEY = '6LeZBUIUAAAAADoJ5cIZMrCZ114bLbe-B6vX5zzt'
MULTI_CAPTCHA_ADMIN = {
    'engine': 'recaptcha2',
}

# Captcha: django-captcha
CAPTCHA_CHALLENGE_FUNCT = 'exchange.captcha.helpers.random_char_challenge'
CAPTCHA_NOISE_FUNCTIONS = (
    'exchange.captcha.helpers.noise_arcs',
    'exchange.captcha.helpers.noise_dots',
    'exchange.captcha.helpers.noise_rectangles',
)
CAPTCHA_TIMEOUT = 10
CAPTCHA_LENGTH = [5, 6]
CAPTCHA_FOREGROUND_COLOR = '#001100'
CAPTCHA_FONT_PATH = [
    'assets/fonts/FreeMono.ttf',
    'assets/fonts/zxx-noise.ttf',
]
CAPTCHA_GET_FROM_POOL = True
CAPTCHA_GET_FROM_POOL_TIMEOUT = 1
CAPTCHA_PICK_SAMPLE_RATE = 0.1 if IS_PROD else 10
CAPTCHA_PICK_DEFAULT_METHOD = 'random_order'  # tablesample or random_order

# Captcha: Services
GEETEST_CAPTCHA_ID = ''
FRONT_RECAPTCHA_PRIVATE_KEY = '6LdnUUgUAAAAAFxz4O4GIQ7gnEiCc2qJfVydCHXK'
ANDROID_RECAPTCHA_PRIVATE_KEY = '6LetRLAUAAAAADFHwQMFIltlxjVHF569S-sJU5kL'
if IS_PROD:
    ARCAPTCHA_SITE_KEY = '88bjuhdam4'
    ARCAPTCHA_SECRET_KEY = secret_string(
        'gAAAAABjBMg09ZI3oyfQoy-8RRScIhmvgpGOPraQnJwEtBDL9ponLNXKrkO9CnV9hiH0c__bQANkfJwy99iwahNb71jkPUzcqhtrPSeE9u7sMRlWrXLQ7Ac=')
    HCAPTCHA_SECRET_KEY = secret_string(
        'gAAAAABgQner9owbps4hDFFXUot_VAtW4TmeUTgQcADZNQlKbcD_iH8sLUzQRLxJniLQPL8J3vHf1-q8gyOT020xWbh5qXfHwaE1dfCr_gzH5_rgQd3IxAlVi53oYK8EUzRNTzjdZX1T')
else:
    ARCAPTCHA_SITE_KEY = 'cngpoiymfh'
    ARCAPTCHA_SECRET_KEY = '5fp5wk1b2et1fgik8g0y'
    HCAPTCHA_SECRET_KEY = '0x6A0dF4284c6d6E47320D01E83db3fe3Ce8D9c74C'

# xchange settings
XCHANGE_PRICE_GUARANTEE_TTL = 6 if IS_PROD else 30  # xchange price guarantee token time to live in seconds
XCHANGE_SMALL_ASSETS_CONVERT_USERNAME = 'system-convert-small-assets'
XCHANGE_MARKET_MAKER_USERNAME = 'bot-xchange@nobitex.ir'
XCHANGE_MARKET_MAKER_BASE_URLS = (
    {"direct": "https://mmxconvert.nxbo.ir/api/v1", "hamravesh": "https://ham-mmxconvert.nobitex.ir/api/v1"}
    if IS_PROD
    else {
        "direct": "https://ttxconvert.nxbo.ir/api/v1",
        "sotoon": "https://cttxconvert.nxbo.ir/api/v1",
        "arvan": "https://cttxconvert.nobitex.ir/api/v1",
        "hamravesh": "https://testcttxconvert.nobitex.ir/api/v1",
    }
)
XCHANGE_MARKET_MAKER_API_KEY = (
    secret_string(
        'gAAAAABmQM42uZihVFgRtJ6mc2d2A307iUAMSfLDLLqSeQ-VcSFi8Dg17Je68bZaQKbKEI7stB1gpZTYTDmmx1IRbzIfT9rom51tWVc7wNNqLeComAS1hrDOWP83sO7d-WdTPo5jfdJC',
        testnet='gAAAAABmQM8ZhVP_FTtNmXwMkXkKxAA7V9Zub4wx-WpAGC0zn_XG06-mJpJZok7HMktBqbMh-FkN1SnqXtlHVJUb4-uCVJzSuwk4xaJpM-oZiEpkOWheic6Iiox5umGLTdcTAnv7BBqT',
    )
    if IS_PROD
    else 'apikey'
)
XCHANGE_MARKET_MAKER_SECRET = (
    secret_string(
        'gAAAAABmQM5X83uviYlhfJXIMbu91X4etV3Y2EM8oVxI-Kl3F_hfBwEHntqSreN_6pLFxSOGgozDyvgydQ_s4wKhTUzWTVhnz_bbFwmyXx9_C02NRP6GPZHc6vicJ6fM8pPVeEdi1oye',
        testnet='gAAAAABmQM8fe08SnOWeoLfcIkqcJJWb53zpZ7YtzLgEfv5bja_XBlea16JW7ZkGm4AGLcR5TkcYjSGXHw9SrXj5-lT_Q-7fXPOHTkSBs1bvSDfy94zFDFv5UHiNMIKVID324JvRkrX1',
    )
    if IS_PROD
    else 'secret'
)

# Margin Flags and Params
MARGIN_ENABLED = True
MAINTENANCE_MARGIN_RATIO = Decimal('1.1')
MARGIN_CALL_RATIOS = {
    # Leverage lower bound: margin call ratio
    Decimal('1'): Decimal('1.2'),
    Decimal('4.5'): Decimal('1.15'),
}
POSITION_EXTENSION_LIMIT = 30  # times
MARGIN_SYSTEM_ORDERS_MAX_AGE = datetime.timedelta(minutes=2)

POOL_MAX_PROFIT_REPARATION_RATE = Decimal('1')  # Temporarily %100 of profit can be repaired by loss

JIBIT_PIP_FEE_RATE = Decimal('0.0001')
JIBIT_WITHDRAW_SHABA = {'name': 'ایوان رایان پیام', 'shaba': 'IR760120020000008992439961'}

VANDAR_SHABA_NUMBER = 'IR260620000000203443585001'
VANDAR_ACCOUNT_NUMBER = '0203443585001'
VANDAR_ID_DEPOSIT_PREFIX = 'وندار'

VANDAR_WITHDRAW_MAX_FEE_DEFAULT = 5_000_0
VANDAR_WITHDRAW_MAX_SETTLEMENT_DEFAULT = 100_000_000_0

# Django 3.2 configuration
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

VANDAR_DEPOSIT_FEE_RATE = Decimal('0.0002')
VANDAR_DEPOSIT_FEE_MAX = Decimal('20_000_0')

# Social Trade
SOCIAL_TRADE = dict(
    fee_user=987,
    default_fee_boundary={
        'max': {
            'rls': '3000000',  # 30k Toman
            'usdt': '10',
        },
        'min': {
            'rls': '0',
            'usdt': '0',
        },
    },
    minNicknameLength=4,
    maxNicknameLength=12,
    subscriptionPeriod=2 if IS_TESTNET else 30,  # days
    subscriptionTrialPeriod=2 if IS_TESTNET else 5,  # days
    delayWhenSubscribed=datetime.timedelta(days=0),
    delayWhenUnsubscribed=datetime.timedelta(days=1),
    durationWhenSubscribed=datetime.timedelta(days=90),
    durationWhenUnsubscribed=datetime.timedelta(days=7),
)

# Transaction Hisotry
TRANSACTION_HISTORY_MAX_DELTA_DAYS = 90

# OAuth configs
OAUTH2_PROVIDER_APPLICATION_MODEL = 'oauth.Application'
OAUTH2_PROVIDER_GRANT_MODEL = 'oauth.Grant'
OAUTH2_PROVIDER_ACCESS_TOKEN_MODEL = 'oauth.AccessToken'
OAUTH2_PROVIDER_REFRESH_TOKEN_MODEL = 'oauth.RefreshToken'
OAUTH2_PROVIDER = {
    'APPLICATION_ADMIN_CLASS': None,
    'GRANT_ADMIN_CLASS': None,
    'ACCESS_TOKEN_ADMIN_CLASS': None,
    'REFRESH_TOKEN_ADMIN_CLASS': None,
    'ACCESS_TOKEN_EXPIRE_SECONDS': 3600,
    'REFRESH_TOKEN_GRACE_PERIOD_SECONDS': 60,
    'SCOPES': Scopes.get_all(),
}

# Core Internal Private Key
CORE_PRIVATE_KEY = secret_string(
    s='',
    testnet='gAAAAABlZHahGQevp0ta0XVj2CtahHtvu_X6MCiKBFYQvRQpySyJMZ9QdHbdeKT9pMYyWQ4LqCqNcFzTUUet-PVkp2Q5KsOVwwdCgVXhTvgtc90rmMe86mmik5xw1dc7YRPx05e5_X9Zrng7hF7sDxyhksFi2ngSVloqzuAdKMzbKBFHcK3pfqIKajM984zjpyM8k9b2tqsCESBdfMtK6mrGuH_SMHmz-zYPKfu0ATM7thRzFNDxflaum2gK1pVhk0CE-9vTZW3ycTBJ4GSeDfAAbIF4qq0ITPe1I_-zRmoBrPf1a9sZQrD2LGcSs7ikEzetKfj4NNQaRNPx9B3ttpssBXX5JwbjzwSLBuCSvAUA6VJKb8S4HZpX8zxncSAkTVwPGt24dHovrTEHJxscuVrTQfJRJ2_ChcOHlrn3b3I21l-HU-1Rm3plfWr3zn5Tb86z9lpLMf926adzY69GYcnwJsOXuEiBIJ_Z8jHoaRuDM4BH4WXT-GCui3gW5EhUF52Y17ZZQIdITZJcNmO6VFlU4JzrgDxUKyeTssv1NNkp8XWZTBii5myhOlSABySfF0r-cyQffTDGZFfoelBBTdr0fVODOzZkSJBSFPX2m3_NVQY9vjCw0HhFIDWT9tTtO-aRjeoBJVwNMy1j3bKYWT7sx66C88i9fAVj8Nk9fE4IRT6Hxdz5cpvKlP6A26h9pmkjYq75k5dw75vfZmRknjUrA-7_GgjbaTIqPPmY3qe1XlZ6lTweGHMLmmtpJQExKr9ZJseRvUKIwLZdIUzYhd41XX0hB2bGQgRDxg2Y0rL2SonB8-sKoc24HuklCpKMiG0U9fVON2LsLDC59Ypfr-MzOe7iJssWxi4mzbgV1d1QQ8JpkpITbzmzA9f8-M-wMb4ebRH1G4EVEmmGgO329aCy4u-M1iZerocufvIrekyrZBPt9KckHJB_wDwhjtkC7F19Q7HtB2LoLDa7_GIs4Uv8WKrUf5fHkCCl-OiTSFc0HQOYsz1uyBc7Fsrmjmv3D0Jfxy_2M55Drv9g1NPDIJWcj54ypgtlMoHSs7IVyy_qQIXqteBhPtirTGWe1R2kODar9D_GeDifxIiMjXCsMNXUceRfLVSkZ_TJiBetdl08veZhEvk3hSOIh-P_2AFXnEMrMGVMsf2cMUqioXCNIbjvW0yHb2XVJia_ABMOsZaRbteozuq79xCmMCaFj_bhsdZZ4VxUXyQTgxO9BK_x0CCNd-jeklCVZJhwsYA7eQogrCx9jyu644fpz9JiL_nGl6UUkevbx1LlpX_KKeB_Bu1xM9FCrmc4rqY_Fygax4p-GSfWwJN4LwsiV3EkN-WGQLQNL0iQsyIzgUycLh8pqPsGNTATEk49ozq-GVd1s080JXD6FHSaGdxW4w86ozR0UvMX6G3jNdlBqxaK9TYa7uDaI-TnvsEDYyjiiP-fysLEmCDwuqZlxAGGQXEzGubE_KlgffP94p2vsWOR9HHMP-ZUg5LbiPR9xx8_aDRGCVDDdKkEh9aba-txTA0N5ChZNuV8u-PvsxucX6KNCErIM23DS3wLVe0__RXetifKgrimAhX97we6hAw_0wmh5q13LzGNDVmgtjSlGdS914FynOmgwOcy5WsJq103kQ2fA-XjWbcwX_DpBOoGa0xisooeVUkzU8ICx1hkv_maSKO-b5cUxpqrrup2M6yGkBxUTKmS4-6S8D6ACZs0qJnnQMaavVHC-mZUEf9mUOjF_80GjiWg9detO_ylahxiaAJHHSIG3Boc90Mz4AUsJwZJUgZRQq2S9SPiqFJnA0ox4iUaCMP64ILpweUhjgaGp9bu501yUQC6t8yhwksLGav9Q5PnQg_ZbLGf-lAqhZ5fsScOiyK5EjNMoFzC5Uqnxh10diLv8OLiNPipNjrfhj7H0gwdUSrs_Cfkp1EawvWyge6dSpn7qNLbn-BkVm_bEAwsj8C0TpWT1Qja--ny45NtxFjHXwyj4wWVoALC7KyMEdeUAl9pkA9Rc-8iScCLYWOjotCPm64V_hmTIj9QThYDLkGEm5EjH60UekYKgpufjOebhjA8WCkwD9h8EJm6ZlNzfK-IZWLy-0Byl_AWcO3DxpoALRUyWk6HdBcC2HPlaeupRSvaYOCUv6h54jmm0ekSffaaigdsDn9T7D3HrpgShDd1uK6UDECWUQI_1TZX27nJ_MwbyrYvIkS442tcsx77meM9wueD34jVo9qOuOmWhGFSftOc0QbDrbIF-FxSzwBWDTnm37byHyoK84zAOWa5fvi-gD7jU9l_V2IBEiMo5Sf7HFc3mxQlVXK8FKQuOvoqcUrzJlYffMzZ0gKWgPtgcDEXyz5-NHX8ETM=',
)

# ABC (asset backed credit) configs
ABC_PRIVATE_KEY = secret_string(
    s='gAAAAABlZJ6ucEEWIeuve5M-s1_7Z1k6Z88qXYM9Yk4wnzJqeDl8wtSiwrzNFVBrtj6-LYqWid9Z8wErdpuXjDGFv555L-Ndi2uB3Vrqo5OSoGlH_SQuq_TumtpLMuGhlyeA3Mz07-EGdQio_F6TVI49LbRCFnzZ8GFVviPPhf9Q2DzEOvWWb-uHYv3TWg1FL0dApjMEhIgL9esAFA9PtfEJc8sECZre-e9oMn2kzJ_xldNWPqhKX-73pOH3vWth3U-LUz7gBYAqY0g6im_aP4viY7pRPX9qCtW-i1RNmt0que4T_Qi2nkDD33JfZWoAW23D9nEzbZLnkqwFu6I4xtsof2nzFP1b5oN_h57r1y9cmdhVguA24MFfigBdAAv2hxHFKp1u_mOP4xBrXtmBbrDmlNbTtOTGdqic2sHHG3n1dPU0Z7fQASWkK22UN0-4VpbMO2Y5XY7v-8vJjSFlkUNhwR5nW515fXzwnDeHblmBhKN3lquGcu3-kY5fjMCBVEZVkLTG1IKcDZzNDiapRRJZVxhWa53hCOunJZD1x7zBZiy_P_HAWeJGCIgsvEscyKUHuQ9navg0HcfbQa0DE-NxscLDVqUuXwcBi3vaFFJ8obEd93SBDlWtDkMcab_WTdtwvZHn0aXWxtTQgfHXeWHS3TM0zUzEibtiYBj98zXIMMMg69lX0FaREsHWkKTtUpNzW6GNZxiLZJ0ZEKJM39qxJFpz5m55bXiQHUSBQNROXIYriKYV7qxhj5EZfLqVFtsxdPb8nd-11PFd3GU8_0sztRmSAw0uN6t2SqvOWL2VZbkepi-Utdz2GxBTr3r6E3PiWllwlBPbAiFLGOR_6lpjrKusCpWgaDfVRxbysZKXyZyHJ1HjJMi0sW_xxwLFx5E-ftNBPeC_xIw2k863lxZbXvAcBLBijDgsUrlxtX512r6ITitAU6aAOBgK-i9oObsji6YrwRGrD2c66skZr0rj_9-JLmCSMGjRurMzgaz-YtKg6WRMpaCa7EKWblw-rVIifL0ujIe-rf7o7LAmXMcjQWZyhsghzCwXYHG2LNnFv5LQcJUcb2tGrdPgzCUmE8Eo4CR4vrnxLConuKNrZeoFE9giGSr6IQlPejs9_v29t2jW06RnxwEIg-tQIDjjmrS8d-Tzjo5GIXo2czVFBfAVIVxc0HnSCTia7pfdu8j3LLiwvDLdr-nBysTLcyyol5eS1fLWZ12wPzMY20_zkmDkMRfabaETGul42w_gdc2CLT3G-5_S-LHJkRTD7xOC2UNZ4AXOx1KDjJUokChzSJ7G71WOwd4vMN6hxCZYU6VyIluoKzdYbbR3rJ19P1DgW-qVuUTKGfOWteGzNOWeC7szpsaZ8evVsizy5adHFcnfRUiqs8_kuuQQxRfKT2V3j_BrEJ_45-Q-aNEEJrTvuJfiRxHNcp6hXD-zaS_cr3dsHa48FHWN4YZuw6QJnkYXwR8R2_r5y-P1_0wPjeu5PwLSNDUsIWMeRJV_t60LnoujWJQd5ECV6w-_FJT-puhjzMjtfE5ijt3p6kd5AuBqUkO3BUjI-OQ_ih_lRFSmirc7MHe_fSpczh1HVZf-01qYZA5ozNrC-7wQtOV1lNz_sAVEKHX_J0ysom2Yo-M3F5Bp1lX2U1ddC-Vd-sYDfntIFafL8lWVxoyouBLol0LV4d65YIAcFNQWRWGPYLrxellGCV-Y5LOuORN5_aIBkwov3zBgLEvzfHYTYq-5tWAlE57J6ULCtbGHDvRnhqryv15aTWLWYq5pkusnPVmtEkW-i6GizwT8tfGtDT9mRS3inA3zjXjow8ZltTYIP6WoK8GmFrdoUG0OPe6wQXn1d7c9rB0U92sKF1H4bcDCPfNocvtUnCwrCzzp8hRU0dbj5i5jpRqrZR3u0_8a5-f8vNO5RquCJ4iaXoSgYIkUj9blahvEH9cnckk4BPy3ctlqvOGpYPno05xxHBYbElxzkX9ehQ5xp0ZMfbCbwdK_Tr1w8ir8t_4EedWlLnAodFQtYqEV307P2JXCT7OCotbR35UW_-jxoPyZRRVlwb-xHy43NuidfOOXgnZaIRuZa9HH--OvxhNf18LXpbFwSYK2vgthGwyTZY23jEmTqeYcMLPCwrG0W_xdIrg3TgMXIr4da4B5wZnQbA_rqKyky7IA4M45nmL4QKU2sxFvMz3eWfawU8G7HHHfFsmYVcSyL8bg6dYLQXBJrlARRj_9OxFguKWvR6UZaK46nWnAvBXuk84VFn2dPu-aWoD83yxi6d-0zl5Z_JQgj4MwnX-LiAqD1IVcKyaPQEbYUg5NIikwziNUcqnPkmk6SFlWAoJTcMB8W8JstsQCJL8EhBQ=',
    testnet='gAAAAABlZHahGQevp0ta0XVj2CtahHtvu_X6MCiKBFYQvRQpySyJMZ9QdHbdeKT9pMYyWQ4LqCqNcFzTUUet-PVkp2Q5KsOVwwdCgVXhTvgtc90rmMe86mmik5xw1dc7YRPx05e5_X9Zrng7hF7sDxyhksFi2ngSVloqzuAdKMzbKBFHcK3pfqIKajM984zjpyM8k9b2tqsCESBdfMtK6mrGuH_SMHmz-zYPKfu0ATM7thRzFNDxflaum2gK1pVhk0CE-9vTZW3ycTBJ4GSeDfAAbIF4qq0ITPe1I_-zRmoBrPf1a9sZQrD2LGcSs7ikEzetKfj4NNQaRNPx9B3ttpssBXX5JwbjzwSLBuCSvAUA6VJKb8S4HZpX8zxncSAkTVwPGt24dHovrTEHJxscuVrTQfJRJ2_ChcOHlrn3b3I21l-HU-1Rm3plfWr3zn5Tb86z9lpLMf926adzY69GYcnwJsOXuEiBIJ_Z8jHoaRuDM4BH4WXT-GCui3gW5EhUF52Y17ZZQIdITZJcNmO6VFlU4JzrgDxUKyeTssv1NNkp8XWZTBii5myhOlSABySfF0r-cyQffTDGZFfoelBBTdr0fVODOzZkSJBSFPX2m3_NVQY9vjCw0HhFIDWT9tTtO-aRjeoBJVwNMy1j3bKYWT7sx66C88i9fAVj8Nk9fE4IRT6Hxdz5cpvKlP6A26h9pmkjYq75k5dw75vfZmRknjUrA-7_GgjbaTIqPPmY3qe1XlZ6lTweGHMLmmtpJQExKr9ZJseRvUKIwLZdIUzYhd41XX0hB2bGQgRDxg2Y0rL2SonB8-sKoc24HuklCpKMiG0U9fVON2LsLDC59Ypfr-MzOe7iJssWxi4mzbgV1d1QQ8JpkpITbzmzA9f8-M-wMb4ebRH1G4EVEmmGgO329aCy4u-M1iZerocufvIrekyrZBPt9KckHJB_wDwhjtkC7F19Q7HtB2LoLDa7_GIs4Uv8WKrUf5fHkCCl-OiTSFc0HQOYsz1uyBc7Fsrmjmv3D0Jfxy_2M55Drv9g1NPDIJWcj54ypgtlMoHSs7IVyy_qQIXqteBhPtirTGWe1R2kODar9D_GeDifxIiMjXCsMNXUceRfLVSkZ_TJiBetdl08veZhEvk3hSOIh-P_2AFXnEMrMGVMsf2cMUqioXCNIbjvW0yHb2XVJia_ABMOsZaRbteozuq79xCmMCaFj_bhsdZZ4VxUXyQTgxO9BK_x0CCNd-jeklCVZJhwsYA7eQogrCx9jyu644fpz9JiL_nGl6UUkevbx1LlpX_KKeB_Bu1xM9FCrmc4rqY_Fygax4p-GSfWwJN4LwsiV3EkN-WGQLQNL0iQsyIzgUycLh8pqPsGNTATEk49ozq-GVd1s080JXD6FHSaGdxW4w86ozR0UvMX6G3jNdlBqxaK9TYa7uDaI-TnvsEDYyjiiP-fysLEmCDwuqZlxAGGQXEzGubE_KlgffP94p2vsWOR9HHMP-ZUg5LbiPR9xx8_aDRGCVDDdKkEh9aba-txTA0N5ChZNuV8u-PvsxucX6KNCErIM23DS3wLVe0__RXetifKgrimAhX97we6hAw_0wmh5q13LzGNDVmgtjSlGdS914FynOmgwOcy5WsJq103kQ2fA-XjWbcwX_DpBOoGa0xisooeVUkzU8ICx1hkv_maSKO-b5cUxpqrrup2M6yGkBxUTKmS4-6S8D6ACZs0qJnnQMaavVHC-mZUEf9mUOjF_80GjiWg9detO_ylahxiaAJHHSIG3Boc90Mz4AUsJwZJUgZRQq2S9SPiqFJnA0ox4iUaCMP64ILpweUhjgaGp9bu501yUQC6t8yhwksLGav9Q5PnQg_ZbLGf-lAqhZ5fsScOiyK5EjNMoFzC5Uqnxh10diLv8OLiNPipNjrfhj7H0gwdUSrs_Cfkp1EawvWyge6dSpn7qNLbn-BkVm_bEAwsj8C0TpWT1Qja--ny45NtxFjHXwyj4wWVoALC7KyMEdeUAl9pkA9Rc-8iScCLYWOjotCPm64V_hmTIj9QThYDLkGEm5EjH60UekYKgpufjOebhjA8WCkwD9h8EJm6ZlNzfK-IZWLy-0Byl_AWcO3DxpoALRUyWk6HdBcC2HPlaeupRSvaYOCUv6h54jmm0ekSffaaigdsDn9T7D3HrpgShDd1uK6UDECWUQI_1TZX27nJ_MwbyrYvIkS442tcsx77meM9wueD34jVo9qOuOmWhGFSftOc0QbDrbIF-FxSzwBWDTnm37byHyoK84zAOWa5fvi-gD7jU9l_V2IBEiMo5Sf7HFc3mxQlVXK8FKQuOvoqcUrzJlYffMzZ0gKWgPtgcDEXyz5-NHX8ETM='
)

ABC_PUBLIC_KEY = {
    'testnet': '''-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0Ym1N8GwKL+DfHxsDZLE
IFMdFsOofkqtIXwY9M0f5GJHbk96bRrTOaKxDMvIYG91yGBAEM4bmgSTX3jTHPqA
c0gaMX5/TNJ4YTc6egGM91QYfHF8oyeLX7eGHUi9DNOH9A9ok6b6kKJxJyW3lSHR
5PqsqBht9YejXsrRHJLaoHTf5Ams6mOVRtAw/p5rIfJJb2sy/BBpiJWisy3fOjXm
uGHOMj3g4FgS+6oZqd7MsSOyXI/AP3UTXBhEz7ADnzC6s9ncau3X03JUW7wA0dr1
MXUVp8/r+EumpW7654yAHuJiehC7c78XB3UcQAUcLJE0EFY5zLEfKdgojCT2+JMa
SwIDAQAB
-----END PUBLIC KEY-----''',
    'mainnet': '''-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAkWkwfCNqjjNbK0IKyoxy
qUGV3EwxRmXLkPBTFBC3O1hX+eI9amP+JK8lFryKt2yhsLhzDX3K556MbJ5Ay78m
NS9gvucgjaXHwU8BnDhGo02yzWueH0dp4EWmGI2b/6XeoXCBklvNZDGdc/zUD23O
LzQ3P3Hyc92NfZ/kuqbyZ/bvr9nSYzQofyBnMwYZjRZo77aCMrM9vvusBsn0v6A3
31dHYVCPRdxq4qqU/IQ/plmtX4VSRtBnMUmB1xYdBAShBGDP2NiZqhqzcFakS2IL
lVAqJmdoUQbCDULXfcuSaNFKUqilEcRJHKXMk2vrWb5hNR5/8bhIfBNfUU9eWTkh
wwIDAQAB
-----END PUBLIC KEY-----'''
}
ABC_DEBIT_PNOVIN_PASSWORD = secret_string(
    'gAAAAABl1H6pRErR1_M2qBM76PNLC8Jm4t1LzRZg3e81AxdvYyQC1bMU0p-OvZHMjTQVDP_ghp4_4gthaJZxwWlLnGOq8x_qeShao6XVsJXJrnxvLcvVAHzOahucUTUanfx5I7h6TOs-',
    testnet='gAAAAABl1H2YHwD8obxWJE9KCcTCSpnxyBss8Kg8TzWl8cpPvAhRQFo0QUiy_8eOYnUneZ4hI5uftAWOceLGcuKFLEufJ1GBOmDOvaj7pmLBmpsmayTyCVxziXWNxs2IZFqIeuHJvgro',
)
ABC_DEBIT_API_PARSIAN_USERNAME = 'nobitex_debit_parsian_live' if IS_PROD else 'nobitex_debit_parsian'
ABC_DEBIT_API_PARSIAN_PASSWORD = secret_string(
    'gAAAAABl8YKd0-dm3BEPV8CE8Jm70tKsyu2dDH2vjGwhEX3SOOpg1ylEVCsRl1gckOQbRGVbxl3gfkClNVW7lSuZM6I0lPxTDx6AR3LpteT0K8zGjNB4xQlOPZ9hAdcljxoTNW0yNl9i',
    testnet='gAAAAABl8YIoHSgPUIi2mtS_Oo9608S_jQgCmoGp1u-y_t43zOmKqjzylh5jZBpnB0HWRVlHXZN70BfLf8JKw-OBSERhx22PTLZEUvR14C0smxQPJg3Oc5YqSZJXT6QCF63OucWGEZs_',
)
ABC_DEBIT_PARSIAN_USERNAME = 'NobitexUser'
ABC_DEBIT_PARSIAN_PASSWORD = secret_string(
    'gAAAAABnRbnl6bbyhomST2NYVErMzuqS9wHoQ-GpsyAAErtsDyYiiZheZDcH0Dl1m6P71deao3GeitmrsvljRdOAxvgZJIfzPw==',
    testnet='gAAAAABnRbmY2wfYZbAgmCXN78vS_6TXuQ5IL_BI310Lhne836WKaAsXo-q10UMesxXXIy7mSkiydoB1TRe2JU4l-iq_LDcE1A==',
)
ABC_DEBIT_PARSIAN_PARENT_CARD_NUMBER = secret_string(
    'gAAAAABndZTzwBvlxl9yLWZ5ZxcYRHl6FH6NMXWyR_8fiY1SSCvtAyjub2QvjU0CfOvwcb4JCi-rBIBPGHZD42m4FtkbFzO_4W6UPsgeUGMSOFF3zz1vckg=',
    testnet='gAAAAABndZTgrefknZr_tHgVX-m1dQajUWGvM4A9P0ipWQfoCNgVy2BExDNyk-aBhxus9UvldnbQN8pyl1Ncbn7E_GAcMW6Zqml5T_CecUqhXPm7a0kxJEk=',
)
ABC_DEBIT_PARSIAN_PARENT_CARD_PASSWORD = secret_string(
    'gAAAAABndZUbnu6MVf2p_4kZi763hEkX6Cv63tjL6Qo-fpfTBqxJLhXdCVTjYN3iUx5-FYVBM5w4IKXrHKZ9uM0yhutXREmmlQ==',
    testnet='gAAAAABndZUguN-fl6Gi0Srnoukqtu6vtyO6ziMgSu9bxu4Dx_VRUIL6bV0VLZU3NrgfRWQ3isOnuH6lvEeW3wWcd2yc_-AJVw==',
)

ABC_CREDIT_TARA_USERNAME = 'nobitex_credit_live'
ABC_CREDIT_TARA_PASSWORD = secret_string(
    'gAAAAABmJnkcKN-ecZIdY74PdJnznYmJIjxpkVsyWEMh7xDgxD0kEL_GzLmDjMSGhQTVJDuB9hssb0DguSm0-TdEug6FPfPOeyCVoDgcRPU32iB4d6AWlgA='
)

ABC_VENCY_CLIENT_ID = 'NOBITEX'
ABC_VENCY_CLIENT_SECRET = secret_string(
    'gAAAAABmtQJrMU2oZZ9iYtg5gRO75VQVLK74Vu6Ezg6K_Y65HRc2PyiqA4diFIEfocRnzWvxUPukfLaTxV_AjNTyTbB2WK4xGPyDvqQfOOcmGMOewkO4AFB3YHupR4jhFiuTo4LiGP6GY0Nc55ziTGqQAy3VpxaV0RLUkr_-WQxEdEcWPKMfK7yj7Qjo5nc4rop_TChArj-IeLSAzkkR9FRXWL0CqEzspjLdBn5G0uXCFN4GKtcEpRf1XYehF6vELhueugCQnQUU',
    testnet='gAAAAABmP30hLFQuedBRIFzrHR0xAmgCCSHc-gHr09pdVZg9Dd4ezNgT3brRoKOwTx2LuU8bsc0CsffcJuNEhTxEfSdNrO4F60xZPpmO46pMniAy3SOIItk1dF3lsy1mwmqxgdwa0JfX',
)

ABC_MAANI_CLIENT_ID = ''
ABC_MAANI_CLIENT_SECRET = ''

ABC_DIGIPAY_USERNAME = secret_string(
    'gAAAAABnvvGN3poNRQYg6MzHucNoe5jmZ1rdniCFpHKMS6cJzsoS6_vk5ZMDq49EZ6fsRoRQ0e-VCHgqqY9Ga5HvqURNC0V8tw==',
    testnet='gAAAAABni9rK8NRziU-o4APlfL99M39mRO3_wfN16nO1QU_lI73h6hKQo-CgZqLWQfh7I773H5OJ1NwTsvaIHoszChs7RP6ep7IPCqdN9myzv1WvJ8aM3RVGXia3i6N4DENqu3qVojyp',
)
ABC_DIGIPAY_PASSWORD = secret_string(
    'gAAAAABnvu3U4GL1zPBS-_zeEME3H1-v_tldNe09cZAfCwUeacyfwRN9Qx8as2xFbzT4Z-J77zLKuQd9J5frtFhoOnWuD4bt5g==',
    testnet='gAAAAABni9rY7P5259A6x85t3nTxB5uCVamTy7U4iYFlBflKlXee4j2xQ86xqA3_2EAM6tCyxnAPK-HT7UO_bpWyLG-HsjDzgQ==',
)
ABC_DIGIPAY_CLIENT_ID = secret_string(
    'gAAAAABnvvIJdj9djNuNwtr_R4VZMhX0E5T7MJvsowhfcH98tRu2Kk969SZjd_8R-BgjuQWd25lV0s6El69KYD0-XsnPXUEpl79J7F0hWnJNKx_bvYnTOjc=',
    testnet='gAAAAABni9roLEt3HJRvjxDHplNJcdH472NUzJLLyY2cK3pvWa0_v59jzHHPairiwi5HZGdOK2DXFusw6hRBTLTDCLxoj998JvSTATqYdaNgkiDvgEF7wO0=',
)
ABC_DIGIPAY_CLIENT_SECRET = secret_string(
    'gAAAAABnvvIe0W0Ic9Hh_5ul6l9H4-iZPCUkUPBBYY6jvx1r81oUSjD4YjKAH7HqwEww4mb-38TeAyQO54OFq5mH87odFQosSA==',
    testnet='gAAAAABni9r2UZnYnwa9zETSZJyZvM7_4Wl6P-aJ8rX6-8TgG8cXE-1LJ1YrLuj6Wklqknjxv8rLmVinzJqu958Tu899y4o7Ng==',
)

ABC_AZKI_USERNAME = 'nobitex'
if IS_PROD:
    ABC_AZKI_PASSWORD = secret_string(
        'gAAAAABoLJdZYy9LCGusxX5UYGKZ4XhOdTc5yOElPQB4w2VeeAAKRSE4s7feNcNgg7lASwiNp8eoZzoB_kEDmAapXKbOZyEfoA==',
        encoding='utf8',
    )
else:
    ABC_AZKI_PASSWORD = secret_string(
        '',
        testnet='gAAAAABoDMnSxT-mT97AOyYVx1rgLXifIcAzrkbMW--AiUJmkn52AFpDTaJKQ3v08lIFMJtN15cp7A_avQyig6K43L-zJbRkoQ==',
    )
ABC_AZKI_FINANCIER_ID = secret_string(
    'gAAAAABoLJXb4z9WPpTg146dB_OKR32dyHDRukvkK2SG4dXCwb8tfaNCwR1OnjZhWhQu75_T6wOpUB8y2kvTf0tsSXEKmbo70g==',
    testnet='gAAAAABoDMokl1BaCpG_aIypDKG7qqs9qdTiHJmiOBMZaScs9tIbYa2SHz0-xIC001P2-xHOORj4i9poMtuKuaJ_x9m5HVbiiw==',
)

ABC_DEBIT_INITIATED_SETTLEMENTS_COUNT = 5

ABC_RATIOS = {
    'debit': {
        'collateral': Decimal('1.1'),
        'collateral_ratio_for_lock': Decimal('1.05'),
        'margin_call': Decimal('1.1'),
        'liquidation': Decimal('1.05'),
        'weighted_avg': Decimal('0.04'),
    },
    'collateral': {
        'collateral': Decimal('1.3'),
        'collateral_ratio_for_lock': Decimal('1.25'),
        'margin_call': Decimal('1.1'),
        'liquidation': Decimal('1.05'),
        'weighted_avg': Decimal('0.04'),
    },
}

ABC_INSURANCE_FUND_ACCOUNT_ID = 990
ABC_FEE_ACCOUNT_ID = 984
ABC_WITHDRAW_DELAY = datetime.timedelta(minutes=10)
ABC_AUTHENTICATION_ENABLED = True
ABC_AUTHENTICATION_INTERNAL_USER_ENABLED = False
ABC_INTERNAL_API_JWT_TOKEN = secret_string(
    'gAAAAABmri35799vfAN8vOFagKBEsErUa6GEAGTMr9ptdSwfyMxD50lVXnjqyUEWhAvbqnh1D3eJDZHMLQIJsduROHnI49FTNep6Z4FMMoRTQJ-U6mALqGqFzsLajJHIlePXNW2F5hgGLwx-VaPZOK7qJd-CfzVVaqBzb6avZMZQ-kz26WnK-ViCn-Vc76YKkdmi-WOzgBE-VGeYs8bKNVwTFw4vb2NhtiQGXE4k4AFOqa6Q1_kdjIpIgSTDJM4Rcq3AkP_VHLWwTsFpqUMpRtiNX7ko9fX9hNLcl4L7xnMl4fZreyhDU0ACgvk8z6XQztsTiSYxdmDVHmnbcOu2CM91YTQZOuajx6O5rNBMY6ce7yMY5zBHXMuvTEp3ImIVlkdYHC18VzM7bB1otG8xlt6yuQCR8wskcdntm-C85EB7Ezuy-tjPzYFsOo6NA7iU7gd2q13Vr4DE5qzgwnOzTY9MJbrozQza8skdIP4iqKFK7QNUXEPwG_qtxA8FBkHJuyP7urlgScdlsbF25ex8tFREFJvvLboWrjBdxqA3P7HHfSY6ZofWzOjfBHWMFrch-g8bsY_i1Tzr9-59_hlzOWkpePGs9M7zDLyMGipSElOcBaGWlp1xjut7KxKivBxDKb_XKnhdPT2yXG_FFPW9pP6C-A26PRAqZy_zNz8HKZUn0gZ9X0DLZg11Kwjmn8yOtWt4-3xfoUB23OGQDvVH2r9TcoHIkpItyHv8TXz5sbGC6CKpFIcuJSSTTyDKVz0oLOwOqzb5ryct7n1sEe4GC2z3TBgNSQTb7mu4l-qXpD3p9FsGs9EpZ-Tyjb0jRoOFM9nuVimT6kCvaS_tcr9mL2aLuS_G67NCfjN7Nw6vIoVPFpH-KdMm31jvJXET2WagpIpVsZE_IfJZZL1JjryW3G2PCG6n_FeR7sc7WsrWcjII_RNExZDsO-YVWYlMAwc0B_WRXWompFFCsgWTfSzm6T-_DTNIWJYixwljLT4HlhPxiLh49cyZpw2iC2dE1ahuMeHUD46j-OH8ae2y12Hh1OY5HC9JFKYDQw0kh8BpU7f5eWgV9Gc3DYqF4Qz4OHi_N4k4bNKtJawUEv_C23Vi1CzbAZnHkxiqYBPwC5ICo6ENEB-jwivpKxyEQxk5IE7D7nNUxhZdtEU1zPfKzJZ0VZoqGBO2RKQXZQ==',
    testnet='gAAAAABmr52B4aAEaILlrc7EmhR_JyNbv8T0Glmivs8u5yrb7C5yTORXX8fA3G186lQcZCcp9mW7WuNeUQcKUltYNbX0qdtW3Y3cTP4JXC4m5LbiJUXrWmOy5jfHLj00IQDIbZJpHbgx_-y7K9yreLyU8_tGfKJE1QBm7RCiJOHtJRp5ILAHADJhmiyQ4L1zQ1F8lAiN4JUyb8JTUVtAXQA_HXJaZGFFlY2Qyz7dqxsQkA06qANyVElaEh2uURHL-lAfjkz6Yp5L6aQrA7yLn3UMxPsz1vLy9-8fm4YpKNMcN2D6hjXACbjy5PxdTYw4Y3SlL8nUo-wAWGvNh6dgxvCF44sjxUIFXti3HIDrYFqSNo-7w6uRdRBgu7UpzOGFafoxpviKf_63VOWx7lCZV-jWHIckPqjfCcIaKaqqNzTKJQw3K9zh84OGeqvu1ZNFkkGxdE4x54m62AGAMxEm8Togr2PhRZs__AvMU8Mw3CQ1Cuz9WeTpvQCBuMQaaVKgt70IFvC01rgaHevUxo0pKj1gnMTIzqM30CkvNy1LUNL0AZ4GuQvz24u-X9pr_YHj9sgvmOlrmlUcLeI7PN4OCf2SkpHW1hULz4829vltVLVh35FN9Z8yl3Cw8rgt69M2ZblLdA4A7YEyE8zf7i5HXj5MJjfKeb-gT2S3PgXjwtwnGhq_WRA2x1VcIqFpFZCFMxaHpcTut3m39NNmgtv00U7iMZl7BdSatba2fhhfuXwnTGbbY5UgVLFBRV27YDdnbMRyyPEBibyoIQ-OTwkZmh8jf2a5LMVYpBsSQj3DBYmin3YVlcftkJJiNtJKldbJDauR8dMuXnqN5xdO2J45wga9q4JtBIcSitUs92m2Vi4eIoy_1oZxt9njL9jVaGx84JQOH-R0zGnM10ouBF8Se2t8dMCdPEnr6logY9sWC4wu83d1_XbDJYzStBTUNS5gS9TNCvwG8xWcwZeXD3iHJ4jBRHZ49CLdZYcbQVkWzjjEBtX-pRMD-KOkrofQ9IuwUcx18O05Y5zIgCJ-du5EG75oEPevk9De1ZHOMhSco-eSH85BrgHUvEtgk4k0oitAEnJA4jkG_vDQYXAcrHn79Pjhq7wekGmYaP2UCZXxzrqXQwsaDQLvh7anYgsRJ5pVUtstkeZgflOL54unSd2fPMA175QTXxLf9Q==',
)
ABC_ACTIVE_DEBIT_SERVICE_PROVIDER_ID = 5
ABC_USE_RESTRICTION_INTERNAL_API = False
ABC_DEBIT_RECON_SFTP_PROPS = {
    'host': '212.80.25.199',
    'port': 22,
    'username': 'nobitex',
    'password': secret_string(
        'gAAAAABn_Qmo6DKbRTsq9DzMpnaeeBPqCg4wZ-cUHoSuvNTxqQV_756qn6xWX3IbWNvEDfumnxz2qZcNrqvqltjWo6r2_0CJqQ==',
        testnet='gAAAAABnubgdlysvnRfRCYU9oJlfwd5pMmOOOwvUBRXqP4MKBtgBbBxFUstzZbuoIMh0ZlSs5bWxKEvzZsuELqEwG5OhH0XwsQ==',
    ),
    'base_dir': '/FromPec',
}

if DEBUG:
    ABC_INTERNAL_API_JWT_TOKEN = 'Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiI1NjQyNTM0OEQzNDE4NjZBMzRDQjY4RDUzNDc3QTE3NCIsImV4cCI6MTc1NDIyMDIwOCwic2VydmljZSI6ImFiYyJ9.Smyi2E_vNUiL_Q-ZEcghtiCZSoohkQ4i13vOHzAJ-yIp9FytPZQv2iANMMp3cHBayJvLomGXH-q5pzl4w9upSJBI1RcukQ7ah4_7QHc6OMn9xE_2WIbpHCIIDrho_I1M4uHUhczrR7VslDp3eaWBoGW8WFrnFuW9nFiUh_M-VJFRjV4HW_WXZpTiy5ea-RIdmh6jJ0fGOXWHZEF8cmn0VrEq6AM3odfw4KGX47jsn_Sc645_D45mCI1kyxYnI4B4lFNAfB1ke2NS5qee8ClWmtXt3tCflgzlYB7YGZFsGXEgMNaGCLR7CYw3nHlCljbLnMa8URr_eIgllX1bR8Fd3l3cfdP_Z8BtH3_WOV0q6UrJeapiPE3aG34hFMEVGkfGuScewHPoi-UwWiBoK5bvgFMcesVZwhmCXz0GF73tQX2TB79IqbkR-5ajhiG7iMF8nqHNLqF-CiWy3CckaG0acf3usSroqv-Ik0v54jWjK5UPGOpbOkgjT7a9kTOnkvLgoSv2fFUreAOUg_In5vbEavv8zA0haDeDg4pzwC8exQWWdC3fS4MxoZlH0wQNZBOeE5btAN4OSLpxLXALAgo4IgD2-Y2SjO9SOxwegZwT1lF5gj9ef7iuF4gYkSWfG4TDUc-Jkxl75ktixwXFlIn8cYOoo7eqUSZ_gQS4mwEh1ac'

CORE_INTERNAL_API_JWT_TOKEN = secret_string(
    '',
    testnet='gAAAAABnq0NlOIhTeQ0Gul7Kat79B5TCk4uTer4cNG0i_swglPplo5cB5ptNHRm4Pa__vRA4Y30iLTXGF7y2MNO8Z_680-LMO25QZpKH1TFS1YbXKBPU9m0gm_0CJ85SUuj3V8wVB1PACFDUFwyHIPmuxX4Trc_QDmOs19eFIGF8SCmsbuwn-Icn8FDkY0cldL8S8JR7Di3CmoAiMchhwQLXM4YRBJnZKySuP8eqcp6h1DJPs3IdH5xhQ3hkEAodMHlbV6MMcOEiDlavj0E9SPVFOK78Fjwo551os560qZRc83fpJFMe4AQ3dD1uULKtKEX6vGiXoyqDVfYvV91Q8AKtN-20v6cXK4f5DV8lu5lg7Zcx1SevMdlMfenFYsYJ7gIFyf_63SdxUl51XjbfnlOYdLx9m3T8-j9tRGb_pdr6Tq2lTDNphyL45b_bDL3L4BFvjRsRX-x5ee7ZmXlIASgfzqlS2DusgiP0J5h_VW_nF8HKvOUZB0lLjBQpqw2uC1a5Tq3Dlo69-v-HyQnAahoq1t5mVH58wV7wXqn55Ck5cqmd7mbrNMClKt4GC_-z9Dmngm864Wr7Vemp-X5UfmjvROimEhgCDthDJVPG3fBCSk4U8pR4hbmailqNGsOjaahuLVm9TQDov6yWZlTVmcnWhGmk5oii30I1bTVZsuc4RM1lFfYlGCLTlWXBfBG2UgSlNCjhsCJxJcRmfOjs9JpxMAXLIF-Bb5o2rRWxa98Pe-j4sH8TwJQynFL5CLAJ_EXpHBglAwAxCeaVWHlFaJapbyNtvtgr1LH_o9vOhUqIOSNe2EjC0ESweU0khKBeIQYcIIihGN9cdIu8uuSaNt7vIaK-Wm3AqWtLpZf7NCFz50qv2h4Wgl_YvQ6JUbbrghoatdutFOmBOedpKHlrhWhi9OwoueJdDa0KtItQh1_ZD1R9SndZOf_Bgo3OoiMwgxZ7K3bJJ62bEmiO_Hgsc1-8VIx-sQjdkrZy8g1UAlZ8eX98Q1MzRrUpq2Uqx_MovR8Jq1vx1nIcR05MQRNL-QdXJOTtyPWqp7NWferRCSrbAGstjKhh7jkPHg2moM65C1klbDjftjEh1Ri43JMttkRcfIc-N7S8t1jATrv4epHX9sexi51mixtt1BR3cCaLjgB5u6eSHpbBpXDRQA8aH0A3c1cuzAs6_g==',
)

# Direct Debit Configs
if IS_PROD:
    DIRECT_DEBIT_CLIENT_ID = 'nobitex'
    DIRECT_DEBIT_CLIENT_SECRET = secret_string(
        'gAAAAABmpMqGa21H64BjYHaBmJUR7Bqip3LO0Y1QDzLyiU_q0dv_IZIzEcdXw9orWfiQnlki5bYTLs3xooQK4G0TDQAzWlEPug==',
    )
    FARABOOM_APP_KEY = 'nobitex'
    FARABOOM_APIS_BASE_URL = 'https://paymanpay.com'
else:
    DIRECT_DEBIT_CLIENT_ID = 'nobitex'
    DIRECT_DEBIT_CLIENT_SECRET = 'a_8_D85A'
    FARABOOM_APP_KEY = 'nobitex'
    FARABOOM_APIS_BASE_URL = 'https://payman2.sandbox.faraboom.co'

SCRUBBER_SENSITIVE_FIELDS = [
    'username',
    'password',
    'principal',
    'ParentCardNumber',
    'SecondPassword',
    'access_token',
    'refresh_token',
]

if not IS_TESTNET:
    SCRUBBER_SENSITIVE_FIELDS += [
        'NationalCode',
        'HashCode',
        'CardNumberHash',
        'ChildCardNumber',
        'CardNumber',
    ]

# Caching task ids for sending sms so we can later revoke them in emergency
CACHE_TASK_IDS_FOR_SENDING_SMS = True

if IS_PROD:
    WS_URL = 'wss://wss.nobitex.ir/connection/websocket'
elif IS_TESTNET:
    WS_URL = 'wss://testwss.nobitex.ir/connection/websocket'
else:
    WS_URL = 'ws://localhost:8001/connection/websocket'

if IS_PROD or IS_TESTNET:
    WEBSOCKET_AUTH_SECRET = secret_string(
        'gAAAAABnIPGv7BabGjks4MyZri-h3k1wZrmilFk-he4EkmSw8ixCufWcGdrgmbAUdjqwNW0VfnoJL8gWnYa1xwgR5spd-KDlG4WTr90i_0OpmkwEdVyWNp6a7JOrFQC_4IXg6djU2STHXODW3Po-UvR4MkUVt_kjnU0nY7Xtm7Ghb6Yj5JstLh1XaFK3rGXpNusnTZe4JaZxS2mgSJ7L9oPw_221zQybUsXBlxoLUCCSRXxAZu837T2gJLkmPEtoStRM9SzMDnPqUZsKBC8afgKbyFmDCJZcoe7V4Ezx439LjtHj2JgoOpkcq5wItjevFnnJ4XCbx6noMd7jKmljU6KNma49qx0jK3oBJO4hphriW8QHMlfsuOMemNRX2CtQX5pS5K4KEJN7zmF5j95ppQnxW_GCjCs8tG-u86QgMOVNMT6stnOqHNyf0hIuwWwjeFuZV_VU5X77slNDkTyK_H9bBkAOXg3zddloDumRzCwU0hcVBE3jSgu-F0Sy_pl6w16AH9B-iXnx2rnZNjzYRsf_iSKGCNwMCfRHJQJAWQJACGoSVxE7nUI=',
        testnet='gAAAAABnINUfTlIcOngldNt36UJ5j__zLSAA83ZImLeUupVVDoR5lNB3BTt8rbqIxFZlOMg8rX4a1GTKgNwAlBo3b2nS80D78TfVdlEiL30PsbkWsxElcISWAM6g3XdKbVsLe-zjn_qkj2bdUZ-HOSkRWP7S8X08SAHBgzmAYVs-PGTI4CpAgXjLFk1b1XFlZpjHX9AnqwlLjnB0TBHXaoAj-30nkQQhqSp9qr5_uDDEhpT9X0GmwOH9_XAigYH3wjFE-IY7A4DQuMXBB5OhWtG1HWtt4E5i2GhIEbX5Zc_6IQbxvLeMErsk17YN5-tFVqNIw3ySkWTsewjAOVJc5zB3znRdB7OGIRyLwuxN0AY6n4XEQ9_qVLOExQygikct-Lbi5sRv4JQZ3vI69krgSnFajKBn-wOW8GZt2gFVyRvTVlNUJD4IxL-XDMboQwYCSH11LA6liuupvfJtAgyJUUsd5955bZrSJAdLWhr7gpuH6j6qbaxgshKQz9R8aJgZLH5J1YW_jrcEB68tKHlyVEgjPUxOW-DZh_EHNCkUkoI08Ca5aryN81c=',
    )
else:
    # For testing purposes:
    WEBSOCKET_AUTH_SECRET = '''-----BEGIN EC PRIVATE KEY-----
MIHcAgEBBEIAuVux2BkQfDNVHQjAFplRVZ/c6ywkURjeltIKU9v72izXNwJn8Jz0
acgdt5nevzFk4z0b3fd8nw0HpDharocK05mgBwYFK4EEACOhgYkDgYYABABUFh1z
UGPYS9WrOx3aVnHlemGGnW4a/GHYF0cxPV40KSVHhBWVfCFpjKTR5qDw/7gd7sAz
d8avlJA3TZwKJWGSIQBD96+TnEDs3h50z9VDxY1erDVqGDkMWvcsotUB6ICIEWMs
uDItN6DEab9QMZ8mwWRj5Ys5TbgnyZf5MY54/2TWKw==
-----END EC PRIVATE KEY-----'''

    # Its corresponding pubkey (to be set in Centrifugo or any other place):
    # -----BEGIN PUBLIC KEY-----
    # MIGbMBAGByqGSM49AgEGBSuBBAAjA4GGAAQAVBYdc1Bj2EvVqzsd2lZx5Xphhp1u
    # Gvxh2BdHMT1eNCklR4QVlXwhaYyk0eag8P+4He7AM3fGr5SQN02cCiVhkiEAQ/ev
    # k5xA7N4edM/VQ8WNXqw1ahg5DFr3LKLVAeiAiBFjLLgyLTegxGm/UDGfJsFkY+WL
    # OU24J8mX+TGOeP9k1is=
    # -----END PUBLIC KEY-----

EXTERNAL_LIQUIDATION_MARKETMAKER_USERNAME = 'liquidator-external-marketmaker'

LIQUIDATOR_MARKET_MAKER_BASE_URLS = (
    {"direct": "https://ttsettlement.nxbo.ir/api/v1", "hamravesh": ""}
    if IS_PROD
    else {
        "direct": "https://ttsettlement.nxbo.ir/api/v1",
        "sotoon": "https://ttsettlement.nxbo.ir/api/v1",
        "arvan": "https://ttsettlement.nxbo.ir/api/v1",
        "hamravesh": "https://ttsettlement.nxbo.ir/api/v1",
    }
)
LIQUIDATOR_MARKET_MAKER_API_KEY = (
    secret_string(
        '',
        testnet='',
    )
    if IS_PROD
    else 'apikey'
)
LIQUIDATOR_MARKET_MAKER_SECRET = (
    secret_string(
        '',
        testnet='',
    )
    if IS_PROD
    else 'secret'
)

FIXTURE_DIRS = [os.path.join(BASE_DIR, 'exchange', 'config', 'fixtures', 'market')]
