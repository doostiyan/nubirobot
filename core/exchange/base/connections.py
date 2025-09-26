import json
import os
from abc import ABCMeta, abstractmethod

import requests
from django.conf import settings

from exchange.base.logging import report_exception
from exchange.base.models import ADDRESS_TYPE
from exchange.blockchain.models import CurrenciesNetworkName

clients = {}


def get_telegram_bot():
    global clients

    client = clients.get('telegram-bot')
    if not client:
        from telegram import Bot
        from telegram.utils.request import Request

        clients['telegram-bot'] = client = Bot(settings.NOTIFICATIONS_BOT_TOKEN,
                                               request=Request(proxy_url=settings.DIRECT_HTTP_PROXY))

    return client


def load_key(path):
    try:
        with open(path, 'r') as f:
            key = f.readline().strip()
            secret = f.readline().strip()
        return key, secret
    except FileNotFoundError:
        report_exception()
        return None, None


class NobitexServerException(Exception):
    pass


class JSONRPCClient:
    USE_PROXY = False
    FORCE_NOT_PROXY = False
    __slots__ = 'url', 'headers', 'auth', 'session', 'password', 'verify_ssl', 'wallet_path'

    def __init__(self, url, headers=None, auth=None, password=None, verify_ssl=False, wallet_path=None, hw_index=0):
        if isinstance(url, list):
            url = url[hw_index]
        self.url = url
        self.headers = headers or {'content-type': 'application/json'}
        user, api_password = auth if auth else load_key(os.path.join(settings.DATA_DIR, 'wallet-api.key'))
        self.auth = (user, api_password)
        self.session = requests.session()
        if (not self.FORCE_NOT_PROXY) and (self.USE_PROXY or settings.WITHDRAW_PROXY):
            self.session.proxies.update(settings.DEFAULT_PROXY)
        self.password = password
        self.verify_ssl = verify_ssl
        self.wallet_path = wallet_path

    def request(self, method, params=None, rpc_id="curltext", secret=None):
        payload = {
            "id": rpc_id,
            "method": method,
            "params": params,
            "jsonrpc": "2.0"
        }

        if secret:
            payload['secret'] = secret

        data = json.dumps(payload)
        try:
            response = self.session.post(
                self.url, data=data, headers=self.headers, auth=self.auth, verify=self.verify_ssl
            )
        except Exception as e:
            report_exception()
            raise NobitexServerException("{}".format(e.__str__()))
        if response.status_code == 200:
            return response.json()
        elif response.status_code >= 500:
            raise NobitexServerException("{}: {}".format(response.status_code, response.content))
        else:
            raise Exception("{}: {}".format(response.status_code, response.content))


class HotWalletClient(JSONRPCClient):
    __metaclass__ = ABCMeta

    @property
    @abstractmethod
    def hot_wallet_url(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def key_file_name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def client_name(self) -> str:
        raise NotImplementedError

    def __init__(self, url=None, headers=None, password_required=True, hw_index=0):
        password = None
        if password_required:
            _, password = load_key(os.path.join(settings.DATA_DIR, self.key_file_name))
        super().__init__(
            url=url or self.hot_wallet_url,
            headers=headers or {'content-type': 'application/json'},
            password=password,
            verify_ssl=True,
            hw_index=hw_index,
        )

    @classmethod
    def get_client(cls, url=None, headers=None, hw_index=0):
        if url or headers:
            return cls(url=url, headers=headers, hw_index=hw_index)

        global clients
        client_name = cls.client_name
        if hw_index > 0:
            client_name += f'#{hw_index}'
        client = clients.get(client_name)

        if not client:
            clients[client_name] = client = cls(url=url, headers=headers, hw_index=hw_index)
        return client


class DogeClient(HotWalletClient):
    hot_wallet_url = settings.DOGE_JSONRPC_URL
    key_file_name = 'doge.key'
    client_name = 'doge'


class BinanceChainClient(HotWalletClient):
    hot_wallet_url = settings.BNB_JSONRPC_URL
    key_file_name = 'bnb.key'
    client_name = 'binance_chain'


class StellarClient(HotWalletClient):
    hot_wallet_url = settings.XLM_JSONRPC_URL
    key_file_name = 'xlm.key'
    client_name = 'stellar_hotwallet'


class EthereumClassicClient(HotWalletClient):
    hot_wallet_url = settings.ETC_JSONRPC_URL
    key_file_name = 'etc.key'
    client_name = 'ether_classic_hotwallet'


class EthereumClassicHDClient(HotWalletClient):
    hot_wallet_url = settings.ETC_HD_URL
    key_file_name = 'etc-hd.key'
    client_name = 'etc_hd_hotwallet'


class EosClient(HotWalletClient):
    hot_wallet_url = settings.EOS_JSONRPC_URL
    key_file_name = 'eos.key'
    client_name = 'eos_hotwallet'


class DotClient(HotWalletClient):
    hot_wallet_url = settings.DOT_JSONRPC_URL
    key_file_name = 'dot.key'
    client_name = 'dot_hotwallet'


class AdaClient(HotWalletClient):
    hot_wallet_url = settings.ADA_JSONRPC_URL
    key_file_name = 'ada.key'
    client_name = 'ada_hotwallet'


class EthClient(HotWalletClient):
    hot_wallet_url = settings.ETH_JSONRPC_URL
    key_file_name = 'eth.key'
    client_name = 'eth_hotwallet'


class EthHDClient(HotWalletClient):
    hot_wallet_url = settings.ETH_HD_URL
    key_file_name = 'eth-hd.key'
    client_name = 'eth_hd_hotwallet'


class EthOnlyHDClient(EthHDClient):
    hot_wallet_url = settings.ETH_ONLY_HD_URL
    client_name = 'eth_only_hd_hotwallet'


class BscClient(HotWalletClient):
    hot_wallet_url = settings.BSC_JSONRPC_URL
    key_file_name = 'bsc.key'
    client_name = 'bsc_hotwallet'


class BscHDClient(HotWalletClient):
    hot_wallet_url = settings.BSC_HD_URL
    key_file_name = 'bsc-hd.key'
    client_name = 'bsc_hd_hotwallet'


class TrxClient(HotWalletClient):
    hot_wallet_url = settings.TRX_JSONRPC_URL_2
    key_file_name = 'trx.key'
    client_name = 'trx_hotwallet_new'


class TRXHDClient(HotWalletClient):
    hot_wallet_url = settings.TRX_HD_URL
    key_file_name = 'trx-hd.key'
    client_name = 'trx_hd_hotwallet'


class TRXOnlyHDClient(TRXHDClient):
    hot_wallet_url = settings.TRX_ONLY_HD_URL
    client_name = 'trx_only_hd_hotwallet'


class LndClient(HotWalletClient):
    hot_wallet_url = settings.LND_JSONRPC_URL
    key_file_name = 'lnd.key'
    client_name = 'lnd_hotwallet'


class RippleClient(HotWalletClient):
    hot_wallet_url = settings.XRP_JSONRPC_URL
    key_file_name = 'xrp.key'
    client_name = 'xrp_hotwallet'


class AvaxClient(HotWalletClient):
    hot_wallet_url = settings.AVAX_JSONRPC_URL
    key_file_name = 'avax.key'
    client_name = 'avax_hotwallet'


class AvaxOnlyHDClient(HotWalletClient):
    hot_wallet_url = settings.AVAX_ONLY_HD_URL
    key_file_name = 'avax-hd.key'
    client_name = 'avax_only_hd_hotwallet'


class HarmonyClient(HotWalletClient):
    hot_wallet_url = settings.HARMONY_JSONRPC_URL
    key_file_name = 'harmony.key'
    client_name = 'harmony_hotwallet'


class HarmonyHDClient(HotWalletClient):
    hot_wallet_url = settings.HARMONY_HD_URL
    key_file_name = 'harmony-hd.key'
    client_name = 'harmony_hd_hotwallet'


class NearClient(HotWalletClient):
    hot_wallet_url = settings.NEAR_JSONRPC_URL
    key_file_name = 'near.key'
    client_name = 'near_hotwallet'


class AtomClient(HotWalletClient):
    hot_wallet_url = settings.ATOM_JSONRPC_URL
    key_file_name = 'atom.key'
    client_name = 'atom_hotwallet'


class AlgoClient(HotWalletClient):
    hot_wallet_url = settings.ALGO_JSONRPC_URL
    key_file_name = 'algo.key'
    client_name = 'algo_hotwallet'


class HederaClient(HotWalletClient):
    hot_wallet_url = settings.HBAR_JSONRPC_URL
    key_file_name = 'hbar.key'
    client_name = 'hbar_hotwallet'


class FlowClient(HotWalletClient):
    hot_wallet_url = settings.FLOW_JSONRPC_URL
    key_file_name = 'flow.key'
    client_name = 'flow_hotwallet'


class FilecoinClient(HotWalletClient):
    hot_wallet_url = settings.FIL_JSONRPC_URL
    key_file_name = 'fil.key'
    client_name = 'fil_hotwallet'


class AptosClient(HotWalletClient):
    hot_wallet_url = settings.APT_JSONRPC_URL
    key_file_name = 'aptos.key'
    client_name = 'aptos_hotwallet'


class FlareClient(HotWalletClient):
    hot_wallet_url = settings.FLR_JSONRPC_URL
    key_file_name = 'flare.key'
    client_name = 'flare_hotwallet'


class TRC20Client(HotWalletClient):
    hot_wallet_url = settings.TRX_TRC20_JSONRPC_URL
    key_file_name = 'trx_trc20.key'
    client_name = 'trx_trc20_hotwallet'


class ElrondClient(HotWalletClient):
    hot_wallet_url = settings.EGLD_JSONRPC_URL
    key_file_name = 'egld.key'
    client_name = 'egld_hotwallet'


class EnjinClient(HotWalletClient):
    hot_wallet_url = settings.ENJ_JSONRPC_URL
    key_file_name = 'enj.key'
    client_name = 'enj_hotwallet'


class ArbitrumClient(HotWalletClient):
    hot_wallet_url = settings.ARB_JSONRPC_URL
    key_file_name = 'arb.key'
    client_name = 'arb_hotwallet'


class ArbitrumHDClient(HotWalletClient):
    hot_wallet_url = settings.ARB_HD_URL
    key_file_name = 'arb-hd.key'
    client_name = 'arb_hd_hotwallet'


class ToncoinClient(HotWalletClient):
    hot_wallet_url = settings.TON_JSONRPC_URL
    key_file_name = 'ton.key'
    client_name = 'ton_hotwallet'


class ToncoinHLv2Client(HotWalletClient):
    hot_wallet_url = settings.TON_HL_V2_JSONRPC_URL
    key_file_name = 'ton.key'
    client_name = 'ton_hl_v2_hotwallet'


class TezosClient(HotWalletClient):
    hot_wallet_url = settings.XTZ_JSONRPC_URL
    key_file_name = 'xtz.key'
    client_name = 'xtz_hotwallet'


class SonicHDClient(HotWalletClient):
    hot_wallet_url = settings.SONIC_HD_URL
    key_file_name = 's-hd.key'
    client_name = 's_hd_hotwallet'


class BaseHDClient(HotWalletClient):
    hot_wallet_url = settings.BASE_HD_URL
    key_file_name = 'base-hd.key'
    client_name = 'base_hd_hotwallet'


class MoneroClient(HotWalletClient):
    """
        client to handle withdraws for monero like other coins
    """
    hot_wallet_url = settings.XMR_JSONRPC_URL
    key_file_name = 'monero.key'
    client_name = 'monero_hotwallet'


class MoneroExplorerClient(HotWalletClient):
    """
        client to handle exploring monero network like block processing and ...
    """
    hot_wallet_url = settings.XMR_EXPLORER_JSONRPC_URL
    key_file_name = 'monero-explorer.key'
    client_name = 'monero_explorer_hotwallet'


class MoneroAdminClient(HotWalletClient):
    """
        client to handle exploring monero network like block processing and ...
    """
    hot_wallet_url = settings.XMR_ADMIN_JSONRPC_URL
    key_file_name = 'monero-admin.key'
    client_name = 'monero_admin_hotwallet'


class ContractEthClient(HotWalletClient):
    hot_wallet_url = settings.CONTRACT_ETH_JSONRPC_URL
    key_file_name = 'contract.key'
    client_name = 'contract_eth_hotwallet'


class ContractV2EthClient(HotWalletClient):
    hot_wallet_url = settings.CONTRACT_V2_ETH_JSONRPC_URL
    key_file_name = 'contract.key'
    client_name = 'contract_v2_eth_hotwallet'


class ContractBscClient(HotWalletClient):
    hot_wallet_url = settings.CONTRACT_BSC_JSONRPC_URL
    key_file_name = 'contract.key'
    client_name = 'contract_bsc_hotwallet'


class ContractV2BscClient(HotWalletClient):
    hot_wallet_url = settings.CONTRACT_V2_BSC_JSONRPC_URL
    key_file_name = 'contract.key'
    client_name = 'contract_v2_bsc_hotwallet'


class ContractEtcClient(HotWalletClient):
    hot_wallet_url = settings.CONTRACT_ETC_JSONRPC_URL
    key_file_name = 'contract.key'
    client_name = 'contract_etc_hotwallet'


class ContractV2EtcClient(HotWalletClient):
    hot_wallet_url = settings.CONTRACT_V2_ETC_JSONRPC_URL
    key_file_name = 'contract.key'
    client_name = 'contract_v2_etc_hotwallet'


class ContractTrxClient(HotWalletClient):
    hot_wallet_url = settings.CONTRACT_TRX_JSONRPC_URL
    key_file_name = 'contract.key'
    client_name = 'contract_trx_hotwallet'


class ContractFtmClient(HotWalletClient):
    hot_wallet_url = settings.CONTRACT_FTM_JSONRPC_URL
    key_file_name = 'contract.key'
    client_name = 'contract_ftm_hotwallet'


class ContractV2FtmClient(HotWalletClient):
    hot_wallet_url = settings.CONTRACT_V2_FTM_JSONRPC_URL
    key_file_name = 'contract.key'
    client_name = 'contract_v2_ftm_hotwallet'


class ContractPolygonClient(HotWalletClient):
    hot_wallet_url = settings.CONTRACT_POLYGON_JSONRPC_URL
    key_file_name = 'contract.key'
    client_name = 'contract_polygon_hotwallet'


class ContractV2PolygonClient(HotWalletClient):
    hot_wallet_url = settings.CONTRACT_V2_POLYGON_JSONRPC_URL
    key_file_name = 'contract.key'
    client_name = 'contract_v2_polygon_hotwallet'


class ContractV2AvaxClient(HotWalletClient):
    hot_wallet_url = settings.CONTRACT_V2_AVAX_JSONRPC_URL
    key_file_name = 'contract.key'
    client_name = 'contract_v2_avax_hotwallet'


class ContractV2HarmonyClient(HotWalletClient):
    hot_wallet_url = settings.CONTRACT_V2_HARMONY_JSONRPC_URL
    key_file_name = 'contract.key'
    client_name = 'contract_v2_harmony_hotwallet'


class ContractV2ArbitrumClient(HotWalletClient):
    hot_wallet_url = settings.CONTRACT_V2_ARB_JSONRPC_URL
    key_file_name = 'contract.key'
    client_name = 'contract_v2_arb_hotwallet'


class FtmClient(HotWalletClient):
    hot_wallet_url = settings.FTM_JSONRPC_URL
    key_file_name = 'ftm.key'
    client_name = 'ftm_hotwallet'


class FtmOnlyHDClient(HotWalletClient):
    hot_wallet_url = settings.FTM_ONLY_HD_URL
    key_file_name = 'ftm-hd.key'
    client_name = 'ftm_only_hd_hotwallet'


class PolygonClient(HotWalletClient):
    hot_wallet_url = settings.POLYGON_JSONRPC_URL
    key_file_name = 'polygon.key'
    client_name = 'polygon_hotwallet'


class PolygonHDClient(HotWalletClient):
    hot_wallet_url = settings.POLYGON_HD_URL
    key_file_name = 'matic-hd.key'
    client_name = 'matic_hd_hotwallet'


class SolanaClient(HotWalletClient):
    hot_wallet_url = settings.SOLANA_JSONRPC_URL
    key_file_name = 'solana.key'
    client_name = 'solana_hotwallet'


CONTRACT_CLIENT = {
    CurrenciesNetworkName.ETH: {
        ADDRESS_TYPE.contract: ContractEthClient,
        ADDRESS_TYPE.contract2: ContractV2EthClient,
    },
    CurrenciesNetworkName.BSC: {
        ADDRESS_TYPE.contract: ContractBscClient,
        ADDRESS_TYPE.contract2: ContractV2BscClient,
    },
    CurrenciesNetworkName.ETC: {
        ADDRESS_TYPE.contract: ContractEtcClient,
        ADDRESS_TYPE.contract2: ContractV2EtcClient,
    },
    CurrenciesNetworkName.TRX: {
        ADDRESS_TYPE.contract: ContractTrxClient,
    },
    CurrenciesNetworkName.FTM: {
        ADDRESS_TYPE.contract: ContractFtmClient,
        ADDRESS_TYPE.contract2: ContractV2FtmClient,
    },
    CurrenciesNetworkName.MATIC: {
        ADDRESS_TYPE.contract: ContractPolygonClient,
        ADDRESS_TYPE.contract2: ContractV2PolygonClient,
    },
    CurrenciesNetworkName.AVAX: {
        ADDRESS_TYPE.contract2: ContractV2AvaxClient,
    },
    CurrenciesNetworkName.ONE: {
        ADDRESS_TYPE.contract2: ContractV2HarmonyClient,
    },
    CurrenciesNetworkName.ARB: {
        ADDRESS_TYPE.contract2: ContractV2ArbitrumClient,
    },
}


class ElectrumClient(JSONRPCClient):
    FORCE_NOT_PROXY = True

    def __init__(self, url=None, headers=None, password_required=True):
        headers = headers or {}
        headers.setdefault('content-type', 'application/json')
        # Wallet Password
        password = None
        if password_required:
            _, password = load_key(os.path.join(settings.DATA_DIR, 'electrum.key'))
        # Initialize JSONRPC
        super().__init__(
            url=url or settings.ELECTRUM_JSONRPC_URL,
            headers=headers,
            password=password,
            verify_ssl=True,
            wallet_path=settings.ELECTRUM_WALLET_PATH,
        )


class ElectrumLTCClient(JSONRPCClient):
    def __init__(self, url=None, headers=None, password_required=True):
        headers = headers or {}
        headers.setdefault('content-type', 'application/json')
        # Wallet Password
        password = None
        if password_required:
            _, password = load_key(os.path.join(settings.DATA_DIR, 'electrum-ltc.key'))
        # Initialize JSONRPC
        super().__init__(
            url=url or settings.ELECTRUM_LTC_JSONRPC_URL,
            headers=headers,
            password=password,
            verify_ssl=True,
            wallet_path=settings.ELECTRUM_LTC_WALLET_PATH,
        )


class ElectronCashClient(JSONRPCClient):
    def __init__(self, url=None, headers=None, password_required=True):
        headers = headers or {}
        headers.setdefault('content-type', 'application/json')
        # Wallet Password
        password = None
        if password_required:
            _, password = load_key(os.path.join(settings.DATA_DIR, 'electron-cash.key'))
        # Initialize JSONRPC
        super().__init__(
            url=url or settings.ELECTRON_CASH_JSONRPC_URL,
            headers=headers,
            password=password,
            verify_ssl=True,
        )


def get_electrum(url=None, headers=None):
    global clients

    client = clients.get('electrum')
    if not client:
        clients['electrum'] = client = ElectrumClient(url, headers)

    return client


def get_electrum_ltc(url=None, headers=None):
    global clients

    client = clients.get('electrum-ltc')
    if not client:
        clients['electrum-ltc'] = client = ElectrumLTCClient(url, headers)

    return client


def get_bnb_api_client():
    """
        This client is connected to binance full node and is not secure for sending information.
        just use for getting accounts.
    """
    global clients

    client = clients.get('bnb_api_client')
    if not client:
        from binance_chain.environment import BinanceEnvironment
        from binance_chain.http import HttpApiClient

        host = settings.BNB_API_SERVER_URL
        _hrp = 'tbnb' if settings.USE_TESTNET_BLOCKCHAINS else 'bnb'
        cli_env = BinanceEnvironment(api_url=host, wss_url='wss://{}/api/'.format(host), hrp=_hrp)
        client = HttpApiClient(env=cli_env)

        """ setting user and password for basic authentication """
        user, api_password = load_key(os.path.join(settings.DATA_DIR, 'wallet-api.key'))
        client.session.auth = (user, api_password)

        clients['bnb_api_client'] = client

    return client


def get_bnb_external_client():
    global clients

    client = clients.get('bnb_external_client')
    if not client:
        from binance_chain.environment import BinanceEnvironment
        from binance_chain.http import HttpApiClient

        if settings.USE_TESTNET_BLOCKCHAINS:
            env = BinanceEnvironment.get_testnet_env()
        else:
            production_env_data = {
                'api_url': 'https://dex-atlantic.binance.org',
                'wss_url': 'wss://dex-atlantic.binance.org/api/',
                'hrp': 'bnb'
            }
            env = BinanceEnvironment(**production_env_data)

        clients['bnb_external_client'] = client = HttpApiClient(env=env, request_params={'proxies': settings.DEFAULT_PROXY})

    return client


class BnbAPIClient(JSONRPCClient):

    def __init__(self, url=None, headers=None, password_required=True):
        password = None
        if password_required:
            _, password = load_key(os.path.join(settings.DATA_DIR, 'bnb-api.key'))
        super().__init__(
            url=url or settings.BNB_JSONRPC_URL,
            headers=headers or {'content-type': 'application/json'},
            password=password,
            verify_ssl=True,
        )


def get_bnb_hot_wallet_api(url=None, headers=None):
    global clients

    client = clients.get('bnb_hot_wallet_api')
    if not client:
        clients['bnb_hot_wallet_api'] = client = BnbAPIClient(url, headers)

    return client


class TrxAPIClient(JSONRPCClient):

    def __init__(self, url=None, headers=None, password_required=True):
        password = None
        if password_required:
            _, password = load_key(os.path.join(settings.DATA_DIR, 'trx-api.key'))
        super().__init__(
            url=url or settings.TRX_JSONRPC_URL,
            headers=headers or {'content-type': 'application/json'},
            password=password,
            verify_ssl=True,
        )


def get_trx_hotwallet(url=None, headers=None):
    global clients

    client = clients.get('trx_hotwallet')
    if not client:
        clients['trx_hotwallet'] = client = TrxAPIClient(url, headers)

    return client

class PmnAPIClient(JSONRPCClient):

    def __init__(self, url=None, headers=None, password_required=True):
        password = None
        if password_required:
            _, password = load_key(os.path.join(settings.DATA_DIR, 'pmn-api.key'))
        super().__init__(
            url=url or settings.PMN_JSONRPC_URL,
            headers=headers or {'content-type': 'application/json'},
            password=password,
            verify_ssl=False,
        )


def get_pmn_hotwallet(url=None, headers=None):
    global clients

    client = clients.get('pmn_hotwallet')
    if not client:
        clients['pmn_hotwallet'] = client = PmnAPIClient(url, headers)

    return client


def get_electron_cash(url=None, headers=None):
    global clients

    client_key = 'electron-cash'
    client = clients.get(client_key)
    if not client:
        clients[client_key] = client = ElectronCashClient(url, headers)
    return client


class GethClient(JSONRPCClient):
    def __init__(self, url=None, headers=None):
        headers = headers or {}
        headers.setdefault('content-type', 'application/json')
        _, password = load_key(os.path.join(settings.DATA_DIR, 'geth.key'))
        super().__init__(
            url=url or settings.GETH_JSONRPC_URL,
            headers=headers,
            password=password,
            verify_ssl=True,
        )


class BscGethClient(JSONRPCClient):
    def __init__(self, url=None, headers=None):
        headers = headers or {}
        headers.setdefault('content-type', 'application/json')
        _, password = load_key(os.path.join(settings.DATA_DIR, 'bsc-geth.key'))
        super().__init__(
            url=url or settings.BSC_GETH_JSONRPC_URL,
            headers=headers,
            password=password,
            verify_ssl=True,
        )


def get_geth(url=None, headers=None):
    global clients

    client = clients.get('geth')
    if not client:
        clients['geth'] = client = GethClient(url, headers)

    return client


def get_bsc_geth(url=None, headers=None):
    global clients

    client = clients.get('bsc-geth')
    if not client:
        clients['bsc-geth'] = client = BscGethClient(url, headers)

    return client


class ParityClient(JSONRPCClient):
    def __init__(self, url=None, headers=None, password_required=True):
        headers = headers or {}
        headers.setdefault('content-type', 'application/json')
        password = None
        if password_required:
            _, password = load_key(os.path.join(settings.DATA_DIR, 'parity.key'))
        super().__init__(
            url=url or settings.PARITY_JSONRPC_URL,
            headers=headers,
            password=password,
            verify_ssl=True,
        )


def get_parity(url=None, headers=None):
    global clients

    client = clients.get('parity')
    if not client:
        clients['parity'] = client = ParityClient(url, headers)

    return client


class RippleAPIClient(JSONRPCClient):

    def __init__(self, url=None, headers=None, password_required=True):
        password = None
        if password_required:
            space, password = load_key(os.path.join(settings.DATA_DIR, 'ripple-api.key'))
        super().__init__(
            url=url or settings.RIPPLE_JSONRPC_URL,
            headers=headers or {'content-type': 'application/json'},
            password=password
        )


def get_ripple_api(url=None, headers=None):
    global clients

    client = clients.get('ripple-api')
    if not client:
        clients['ripple-api'] = client = RippleAPIClient(url, headers)

    return client


def get_electrum_gateway(headers=None):
    global clients
    client = clients.get('electrum-gateway')
    if not client:
        clients['electrum-gateway'] = client = ElectrumClient(settings.GATEWAY_BTC_JSONRPC_URL, headers, False)

    return client


def get_electrum_ltc_gateway(headers=None):
    global clients
    client = clients.get('electrum-ltc-gateway')
    if not client:
        clients['electrum-ltc-gateway'] = client = ElectrumLTCClient(settings.GATEWAY_LTC_JSONRPC_URL, headers, False)

    return client


def get_ripple_gateway(url=None, headers=None):
    global clients

    client = clients.get('ripple-gateway')
    if not client:
        clients['ripple-gateway'] = client = RippleAPIClient(url, headers, False)

    return client


def run_hook(server, command):
    cert_file = os.path.join(settings.DATA_DIR, 'ws.crt')
    cert_key = os.path.join(settings.DATA_DIR, 'ws.key')
    if not os.path.exists(cert_file) or not os.path.exists(cert_key):
        return False
    token = settings.SS_TOKENS.get(command) or 'NOBITEX'
    try:
        host, vm = server.split('/', maxsplit=1)
        r = requests.post(
            'https://ss-{}.nobitex.ir/{}/hooks/{}'.format(host, vm, command),
            headers={
                'Authorization': 'Token {}'.format(token),
            },
            cert=(cert_file, cert_key),
            timeout=30,
        )
        r.raise_for_status()
        if r.text != 'ok':
            raise ValueError(r.text or 'no response')
        return True
    except:
        report_exception()
        return False


def get_fcm():
    global clients

    client = clients.get('fcm')
    if not client:
        import firebase_admin
        from firebase_admin import credentials, messaging

        fcm_credentials = credentials.Certificate(os.path.join(settings.DATA_DIR, 'FCM_serviceAccountKey.json'))
        firebase_admin.initialize_app(fcm_credentials)
        clients['fcm'] = client = messaging

    return client


def get_market_bot_redis():
    global clients

    client = clients.get('market_bot_redis')
    if not client:
        import redis
        redis_host, redis_port = settings.REDIS_HOST.split(':')
        if settings.USE_REDIS2:
            redis_port = '6380'
        clients['market_bot_redis'] = client = redis.Redis(host=redis_host, port=int(redis_port), db=0)
    return client
