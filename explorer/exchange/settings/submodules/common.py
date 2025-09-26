import os

from exchange.settings import IS_PROD, IS_VIP
from exchange.settings.secret import decrypt_string

MAIN_WALLET_SERVER = '127.0.0.1:8000'

USE_TESTNET_BLOCKCHAINS = not IS_PROD

BLOCKCHAIN_CACHE_PREFIX = ''

DOGE_JSONRPC_URL = ''
ETC_JSONRPC_URL = ''
EOS_JSONRPC_URL = ''

BLOCKCYPHER_ENABLED = False

NO_INTERNET = False

LOG_FAILED_LOGIN_ATTEMPTS = True
LOG_FAILED_APIKey_PERMISSION_REQUESTS = True

# Wallet Information
DIRECT_NODES_SERVER = 'https://nodes.nobitex1.ir'
DIRECT_WALLET_4_SERVER = 'https://wallet4.nobitex1.ir'

DOT_JSONRPC_URL = '?'
ADA_JSONRPC_URL = '?'
BSC_JSONRPC_URL = '?'
TRX_JSONRPC_URL_2 = '?'
LND_JSONRPC_URL = '?'
ONLY_REPLICA = '?'

if IS_PROD:
    XMR_EXPLORER_JSONRPC_URL = DIRECT_WALLET_4_SERVER + '/xmr-explorer/'
else:
    XMR_EXPLORER_JSONRPC_URL = 'http://localhost:5071'

# SOL
# Solana QuickNode URL (20M request per month) This is just for production, use
# https://morning-late-bush.solana-mainnet.discover.quiknode.pro/ for testing purposes
SOLANA_QUICK_NODE_URLS = 'https://fluent-holy-theorem.solana-mainnet.quiknode.pro/33a48955b1ef2a92791c950642557b3b98cbc3c3' if not IS_VIP else ' '

SOLANA_ALCHEMY_URLS = [
    'https://solana-mainnet.g.alchemy.com/v2/ZB4MhPz7qnwwAK8kF6bXBVw_qHomL6YU',
    'https://solana-mainnet.g.alchemy.com/v2/sgFGPAyqiBwvqiEkXHiiSFYkVaNbFOro'
] if not IS_VIP else [
    'https://solana-mainnet.g.alchemy.com/v2/zAXPbOHQv5uZBUD1NG_nLbzip0WKZ5bM'
]

# INFURA
WS_INFURA_PROJECT_ID = [
    'd7b5d392abd14546ada1640ed45dea0b',
    '1e1413ee4cd54c6d882fbf2b48aabb0b'
] if not IS_VIP else [
    '40a05d3809c9471cbf3e0db059701a86',  # Habibi
]

INFURA_PROJECT_ID = ''

# WEB3
WEB3_API_INFURA_PROJECT_ID = [
    '57df6bca71f147fb9931f74d02f00074',
    '20f0ce5d9ee84a47b2b7e9877a72911a'
] if not IS_VIP else [
    'e4edd0f3ac034becb3f9b50564651ad5',  # Habibi
]

IS_EXPLORER_WRAPPER_USES_ONLY_SUBMODULE = False
MAIN_SERVER_HTTP_CLIENT = 'http://127.0.0.1:8000'
DIFF_SERVER_HTTP_CLIENT = 'http://127.0.0.1:8000'

GETH_WS_URL = ''
LND_URL = ''

BLOCKCHAIN_SERVER = False
IS_EXPLORER_SERVER = os.environ.get('IS_EXPLORER_SERVER', '').lower() == 'true'

SERVICE_BASE_API_KEY = [
    decrypt_string(
        os.environ.get('SERVICE_BASE_API_KEY')
    )
]

WITHDRAW_PROXY = ''

ENABLE_BASE_TOKENS = False
