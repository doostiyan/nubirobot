from exchange.settings import MAIN_WALLET_SERVER

WALLET_SERVER = 'https://wallet-btc-test.local/'

# BTC
ELECTRUM_JSONRPC_URL = 'http://localhost:6666'
ELECTRUM_WALLET_PATH = '~/.electrum/testnet/wallets/wallet_1'
# ETH
GETH_JSONRPC_URL = 'http://localhost:8545'
GETH_ACCOUNT = '0xf72fb5e6ab7444d46ae893508080981f024b1683'
# LTC
LTC_WALLET_SERVER = 'https://wallet-ltc-test.local/'
ELECTRUM_LTC_JSONRPC_URL = 'http://localhost:7777'
# XRP
RIPPLE_WALLET_SERVER = 'https://wallet-eth-test.local/'
RIPPLE_JSONRPC_URL = 'http://localhost:20316'  # Testnet port is set to 20316. Mainnet port is 20315
# BNB
BNB_WALLET = 'tbnb19yjzw0xq2ufulqrp85wt6qnxzxgmkd72hgc2du'
BNB_RPC_URL = MAIN_WALLET_SERVER + '/tbnb-rpc/'
BNB_API_SERVER_URL = MAIN_WALLET_SERVER + '/tbnb-api/'
BNB_JSONRPC_URL = MAIN_WALLET_SERVER + '/tbnb/'
# BCH
ELECTRON_CASH_JSONRPC_URL = 'http://localhost:8888'
# ETC
# PARITY_JSONRPC_URL = MAIN_WALLET_SERVER + '/parity-mordor'
PARITY_JSONRPC_URL = 'http://localhost:8546'
PARITY_ACCOUNT = '0x43d2c0803b019f1d8b0b8433c9685022679ed1d2'  # pass: hunter2
ETC_SERVER_NAME = 'nobitex1/nodes-etc'

# PMN
PMN_JSONRPC_URL = 'http://wallet-eth-test.local:7071'

# GATEWAY

GATEWAY_SERVER = 'https://wallet-gateway.nobitex1.ir'
GATEWAY_BTC_JSONRPC_URL = GATEWAY_SERVER + '/gateway-btctest'
GATEWAY_LTC_JSONRPC_URL = GATEWAY_SERVER + '/gateway-ltctest'
GATEWAY_XRP_JSONRPC_URL = GATEWAY_SERVER + '/gateway-xrptest'
# TRX
TRX_JSONRPC_URL = MAIN_WALLET_SERVER + '/trx-testnet/'
# XLM
XLM_JSONRPC_URL = MAIN_WALLET_SERVER + '/xlm-testnet/'
