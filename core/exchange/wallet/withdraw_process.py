import sys
import traceback
from collections import defaultdict
from typing import Dict

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction

from exchange.accounts.models import User, UserRestriction
from exchange.base.api import ParseError
from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.logging import report_event, report_exception
from exchange.base.models import ALL_CRYPTO_CURRENCIES, BABYDOGE, Currencies, Settings, get_currency_codename
from exchange.blockchain.contracts_conf import (
    BASE_ERC20_contract_info,
    BEP20_contract_info,
    ERC20_contract_info,
    TRC20_contract_info,
    arbitrum_ERC20_contract_info,
    opera_ftm_contract_info,
    polygon_ERC20_contract_info,
    sol_contract_info,
    ton_contract_info,
)
from exchange.usermanagement.diff import get_user_diff
from exchange.wallet.estimator import PriceEstimator
from exchange.wallet.models import (
    AutomaticWithdraw,
    AutomaticWithdrawLog,
    ConfirmedWalletDeposit,
    Transaction,
    Wallet,
    WalletDepositTag,
    WithdrawRequest,
)
from exchange.wallet.withdraw_commons import NobitexWithdrawException, update_auto_withdraw_status
from exchange.wallet.withdraw_method import (
    AdaWithdraw,
    AlgoWithdraw,
    AptosWithdraw,
    ArbERC20HDWithdraw,
    ArbERC20Withdraw,
    ArbHDWithdraw,
    ArbWithdraw,
    AtomWithdraw,
    AvaxOnlyHDWithdraw,
    AvaxWithdraw,
    BaseERC20HDWithdraw,
    BaseHDWithdraw,
    BinanceChainWithdraw,
    BscBep20HDWithdraw,
    BscBep20Withdraw,
    BscGethBEP20Withdraw,
    BscGethWithdraw,
    BscHDWithdraw,
    BscWithdraw,
    DogeWithdraw,
    DotWithdraw,
    ElectronCashWithdraw,
    ElectrumLTCWithdraw,
    ElectrumWithdraw,
    ElrondWithdraw,
    EnjinWithdraw,
    EosWithdraw,
    EthERC20HDN2Withdraw,
    EthERC20HDWithdraw,
    EthERC20Withdraw,
    EthereumClassicHDWithdraw,
    EthereumClassicWithdraw,
    EthHDWithdraw,
    EthOnlyHDWithdraw,
    EthWithdraw,
    FakeBatchWithdraw,
    FakeWithdraw,
    FilecoinWithdraw,
    FlareWithdraw,
    FlowWithdraw,
    FtmERC20Withdraw,
    FtmOnlyHDWithdraw,
    FtmWithdraw,
    GethERC20Withdraw,
    GethTetherWithdraw,
    GethWithdraw,
    HarmonyHDWithdraw,
    HarmonyWithdraw,
    HederaWithdraw,
    LndWithdraw,
    MoneroWithdraw,
    NearWithdraw,
    ParityWithdraw,
    PMNAPIWithdraw,
    PolygonERC20HDWithdraw,
    PolygonERC20Withdraw,
    PolygonHDWithdraw,
    PolygonWithdraw,
    RippleWithdraw,
    SolanaTokenWithdraw,
    SolanaWithdraw,
    SonicHDWithdraw,
    StellarWithdraw,
    TezosWithdraw,
    ToncoinHLv2Withdraw,
    ToncoinTokenHLv2Withdraw,
    ToncoinWithdraw,
    TRC20WithdrawNew,
    TRXAPIWithdraw,
    TrxOnlyHDWithdraw,
    TrxTRC20HDWithdraw,
    USDTArbERC20Withdraw,
    USDTTRC20Withdraw,
    VandarAPIWithdraw,
    ZTrxWithdraw,
)

########################################
# Core Withdraw Processing
########################################

withdraw_type = {
    'fake': AutomaticWithdraw.TYPE.fake,
    'fake_batch': AutomaticWithdraw.TYPE.fake_batch,
    'electrum': AutomaticWithdraw.TYPE.electrum,
    'electrum_ltc': AutomaticWithdraw.TYPE.electrum_ltc,
    'electron_cash': AutomaticWithdraw.TYPE.electron_cash,
    'binance': AutomaticWithdraw.TYPE.binance,
    'geth': AutomaticWithdraw.TYPE.geth,
    'eth_hotwallet': AutomaticWithdraw.TYPE.eth_hotwallet,
    'eth_erc20_hotwallet': AutomaticWithdraw.TYPE.eth_erc20_hotwallet,
    'eth_hd_hotwallet': AutomaticWithdraw.TYPE.eth_hd_hotwallet,
    'eth_only_hd_hotwallet': AutomaticWithdraw.TYPE.eth_only_hd_hotwallet,
    'eth_hd_hotwallet_erc20': AutomaticWithdraw.TYPE.eth_hd_hotwallet_erc20,
    'eth_hd_hotwallet_erc20_n2': AutomaticWithdraw.TYPE.eth_hd_hotwallet_erc20_n2,
    'parity': AutomaticWithdraw.TYPE.parity,
    'bnb_hot_wallet_api': AutomaticWithdraw.TYPE.bnb_hot_wallet_api,
    'trx_hotwallet': AutomaticWithdraw.TYPE.trx_hotwallet,
    'trx_trc20_hotwallet': AutomaticWithdraw.TYPE.trx_trc20_hotwallet,
    'trx_only_hd_hotwallet': AutomaticWithdraw.TYPE.trx_only_hd_hotwallet,
    'trx_hd_hotwallet_trc20': AutomaticWithdraw.TYPE.trx_hd_hotwallet_trc20,
    'ztrx_hotwallet': AutomaticWithdraw.TYPE.ztrx_hotwallet,
    'xlm_hotwallet': AutomaticWithdraw.TYPE.xlm_hotwallet,
    'pmn_hotwallet': AutomaticWithdraw.TYPE.pmn_hotwallet,
    'etc_hotwallet': AutomaticWithdraw.TYPE.etc_hotwallet,
    'etc_hd_hotwallet': AutomaticWithdraw.TYPE.etc_hd_hotwallet,
    'eos_hotwallet': AutomaticWithdraw.TYPE.eos_hotwallet,
    'tether_erc20': AutomaticWithdraw.TYPE.tether_erc20,
    'usdt_trx': AutomaticWithdraw.TYPE.usdt_trx,
    'vandar_api': AutomaticWithdraw.TYPE.vandar_api,
    'doge_hotwallet': AutomaticWithdraw.TYPE.doge_hotwallet,
    'geth_erc20': AutomaticWithdraw.TYPE.geth_erc20,
    'dot_hotwallet': AutomaticWithdraw.TYPE.dot_hotwallet,
    'bsc_hotwallet': AutomaticWithdraw.TYPE.bsc_hotwallet,
    'bsc_hotwallet_bep20': AutomaticWithdraw.TYPE.bsc_hotwallet_bep20,
    'bsc_geth': AutomaticWithdraw.TYPE.bsc_geth,
    'bsc_geth_bep20': AutomaticWithdraw.TYPE.bsc_geth_bep20,
    'bsc_hd_hotwallet': AutomaticWithdraw.TYPE.bsc_hd_hotwallet,
    'bsc_hd_hotwallet_bep20': AutomaticWithdraw.TYPE.bsc_hd_hotwallet_bep20,
    'lnd_hotwallet': AutomaticWithdraw.TYPE.lnd_hotwallet,
    'ada_hotwallet': AutomaticWithdraw.TYPE.ada_hotwallet,
    'xrp_hotwallet': AutomaticWithdraw.TYPE.xrp_hotwallet,
    'ftm_hotwallet': AutomaticWithdraw.TYPE.ftm_hotwallet,
    'ftm_hotwallet_erc20': AutomaticWithdraw.TYPE.ftm_hotwallet_erc20,
    'ftm_hd_hotwallet': AutomaticWithdraw.TYPE.ftm_hd_hotwallet,
    'polygon_hotwallet': AutomaticWithdraw.TYPE.polygon_hotwallet,
    'polygon_hotwallet_erc20': AutomaticWithdraw.TYPE.polygon_hotwallet_erc20,
    'matic_hd_hotwallet': AutomaticWithdraw.TYPE.matic_hd_hotwallet,
    'matic_hd_hotwallet_erc20': AutomaticWithdraw.TYPE.matic_hd_hotwallet_erc20,
    'avax_hotwallet': AutomaticWithdraw.TYPE.avax_hotwallet,
    'avax_hd_hotwallet': AutomaticWithdraw.TYPE.avax_hd_hotwallet,
    'harmony_hotwallet': AutomaticWithdraw.TYPE.harmony_hotwallet,
    'harmony_hd_hotwallet': AutomaticWithdraw.TYPE.harmony_hd_hotwallet,
    'atom_hotwallet': AutomaticWithdraw.TYPE.atom_hotwallet,
    'near_hotwallet': AutomaticWithdraw.TYPE.near_hotwallet,
    'solana_hotwallet': AutomaticWithdraw.TYPE.solana_hotwallet,
    'monero_hotwallet': AutomaticWithdraw.TYPE.monero_hotwallet,
    'algo_hotwallet': AutomaticWithdraw.TYPE.algo_hotwallet,
    'hbar_hotwallet': AutomaticWithdraw.TYPE.hbar_hotwallet,
    'flow_hotwallet': AutomaticWithdraw.TYPE.flow_hotwallet,
    'aptos_hotwallet': AutomaticWithdraw.TYPE.aptos_hotwallet,
    'fil_hotwallet': AutomaticWithdraw.TYPE.fil_hotwallet,
    'flare_hotwallet': AutomaticWithdraw.TYPE.flare_hotwallet,
    'egld_hotwallet': AutomaticWithdraw.TYPE.egld_hotwallet,
    'arb_hotwallet': AutomaticWithdraw.TYPE.arb_hotwallet,
    'arb_hotwallet_erc20': AutomaticWithdraw.TYPE.arb_hotwallet_erc20,
    'usdt_arbitrum': AutomaticWithdraw.TYPE.usdt_arbitrum,
    'arb_hd_hotwallet': AutomaticWithdraw.TYPE.arb_hd_hotwallet,
    'arb_hd_hotwallet_erc20': AutomaticWithdraw.TYPE.arb_hd_hotwallet_erc20,
    'ton_hotwallet': AutomaticWithdraw.TYPE.ton_hotwallet,
    'ton_hlv2_hotwallet': AutomaticWithdraw.TYPE.ton_hlv2_hotwallet,
    'ton_token_hlv2_hotwallet': AutomaticWithdraw.TYPE.ton_token_hlv2_hotwallet,
    'xtz_hotwallet': AutomaticWithdraw.TYPE.xtz_hotwallet,
    'enj_hotwallet': AutomaticWithdraw.TYPE.enj_hotwallet,
    's_hd_hotwallet': AutomaticWithdraw.TYPE.s_hd_hotwallet,
    'solana_hotwallet_tokens': AutomaticWithdraw.TYPE.solana_hotwallet_tokens,
    'base_hd_hotwallet': AutomaticWithdraw.TYPE.base_hd_hotwallet,
    'base_hd_hotwallet_erc20': AutomaticWithdraw.TYPE.base_hd_hotwallet_erc20,
}

DEFAULT_WITHDRAW_METHODS = {
    Currencies.btc: {
        'BTC': 'electrum',
        'BTCLN': 'lnd_hotwallet',
    },
    Currencies.eth: {
        'ETH': 'geth',  # alternative: 'eth_hotwallet'
        'ARB': 'arb_hotwallet',
        'BASE': 'base_hd_hotwallet',
    },
    Currencies.ltc: {
        'LTC': 'electrum_ltc',
    },
    Currencies.usdt: {
        'ETH': 'tether_erc20',
        'TRX': 'usdt_trx',
        'ZTRX': 'ztrx_hotwallet',
        'ARB': 'usdt_arbitrum',
    },
    Currencies.xrp: {
        'XRP': 'xrp_hotwallet',
    },
    Currencies.bch: {
        'BCH': 'electron_cash',
    },
    Currencies.bnb: {
        'BNB': 'bnb_hot_wallet_api',
        'BSC': 'bsc_hd_hotwallet',
    },
    Currencies.trx: {
        'TRX': 'trx_hotwallet',
    },
    Currencies.xlm: {
        'XLM': 'xlm_hotwallet',
    },
    Currencies.pmn: {
        'PMN': 'pmn_hotwallet',
    },
    Currencies.etc: {
        'ETC': 'etc_hotwallet',
    },
    Currencies.eos: {
        'EOS': 'eos_hotwallet',
    },
    Currencies.rls: 'vandar_api',
    Currencies.doge: {
        'DOGE': 'doge_hotwallet',
    },
    Currencies.dot: {
        'DOT': 'dot_hotwallet',
    },
    Currencies.ada: {
        'ADA': 'ada_hotwallet',
    },
    Currencies.ftm: {
        'FTM': 'ftm_hotwallet',
    },
    Currencies.pol: {
        'MATIC': 'matic_hd_hotwallet',
    },
    Currencies.avax: {
        'AVAX': 'avax_hotwallet',
    },
    Currencies.one: {
        'ONE': 'harmony_hotwallet',
    },
    Currencies.atom: {
        'ATOM': 'atom_hotwallet',
    },
    Currencies.near: {
        'NEAR': 'near_hotwallet',
    },
    Currencies.sol: {
        'SOL': 'solana_hotwallet',
    },
    Currencies.xmr: {
        'XMR': 'monero_hotwallet',
    },
    Currencies.algo: {
        'ALGO': 'algo_hotwallet',
    },
    Currencies.hbar: {
        'HBAR': 'hbar_hotwallet',
    },
    Currencies.flow: {
        'FLOW': 'flow_hotwallet',
    },
    Currencies.apt: {
        'APT': 'aptos_hotwallet',
    },
    Currencies.fil: {
        'FIL': 'fil_hotwallet',
    },
    Currencies.flr: {
        'FLR': 'flare_hotwallet',
    },
    Currencies.egld: {
        'EGLD': 'egld_hotwallet',
    },
    Currencies.enj: {
        'ENJ': 'enj_hotwallet',
    },
    Currencies.ton: {
        'TON': 'ton_hlv2_hotwallet',
    },
    Currencies.xtz: {
        'XTZ': 'xtz_hotwallet',
    },
    Currencies.s: {
        'SONIC': 's_hd_hotwallet',
    },
}

# Usually mainnet has complete list of bep20 tokens
for currency in BEP20_contract_info['mainnet'].keys() & ALL_CRYPTO_CURRENCIES:
    if currency not in DEFAULT_WITHDRAW_METHODS:
        DEFAULT_WITHDRAW_METHODS[currency] = {}
    if currency == BABYDOGE:
        DEFAULT_WITHDRAW_METHODS[currency]['BSC'] = 'bsc_hotwallet_bep20'
    else:
        DEFAULT_WITHDRAW_METHODS[currency]['BSC'] = 'bsc_hd_hotwallet_bep20'

# Usually mainnet has complete list of erc20 tokens
for currency in ERC20_contract_info['mainnet'].keys() & ALL_CRYPTO_CURRENCIES:
    if currency not in DEFAULT_WITHDRAW_METHODS:
        DEFAULT_WITHDRAW_METHODS[currency] = {}
    DEFAULT_WITHDRAW_METHODS[currency]['ETH'] = 'eth_hd_hotwallet_erc20'  # alternative: 'eth_erc20_hotwallet'

for currency in opera_ftm_contract_info['mainnet'].keys() & ALL_CRYPTO_CURRENCIES:
    if currency not in DEFAULT_WITHDRAW_METHODS:
        DEFAULT_WITHDRAW_METHODS[currency] = {}
    DEFAULT_WITHDRAW_METHODS[currency]['FTM'] = 'ftm_hotwallet_erc20'

for currency in polygon_ERC20_contract_info['mainnet'].keys() & ALL_CRYPTO_CURRENCIES:
    if currency not in DEFAULT_WITHDRAW_METHODS:
        DEFAULT_WITHDRAW_METHODS[currency] = {}
    DEFAULT_WITHDRAW_METHODS[currency]['MATIC'] = 'matic_hd_hotwallet_erc20'

for currency in TRC20_contract_info['mainnet'].keys() & ALL_CRYPTO_CURRENCIES:
    if currency not in DEFAULT_WITHDRAW_METHODS:
        DEFAULT_WITHDRAW_METHODS[currency] = {}
    if not currency == Currencies.usdt:
        DEFAULT_WITHDRAW_METHODS[currency]['TRX'] = 'trx_hd_hotwallet_trc20'

for currency in arbitrum_ERC20_contract_info['mainnet'].keys() & ALL_CRYPTO_CURRENCIES:
    if currency not in DEFAULT_WITHDRAW_METHODS:
        DEFAULT_WITHDRAW_METHODS[currency] = {}
    if not currency == Currencies.usdt:
        DEFAULT_WITHDRAW_METHODS[currency]['ARB'] = 'arb_hd_hotwallet_erc20'

for currency in ton_contract_info['mainnet'].keys() & ALL_CRYPTO_CURRENCIES:
    if currency not in DEFAULT_WITHDRAW_METHODS:
        DEFAULT_WITHDRAW_METHODS[currency] = {}
    DEFAULT_WITHDRAW_METHODS[currency]['TON'] = 'ton_token_hlv2_hotwallet'

for currency in sol_contract_info['mainnet'].keys() & ALL_CRYPTO_CURRENCIES:
    if currency not in DEFAULT_WITHDRAW_METHODS:
        DEFAULT_WITHDRAW_METHODS[currency] = {}
    DEFAULT_WITHDRAW_METHODS[currency]['SOL'] = 'solana_hotwallet_tokens'

for currency in BASE_ERC20_contract_info['mainnet'].keys() & ALL_CRYPTO_CURRENCIES:
    if currency not in DEFAULT_WITHDRAW_METHODS:
        DEFAULT_WITHDRAW_METHODS[currency] = {}
    DEFAULT_WITHDRAW_METHODS[currency]['BASE'] = 'base_hd_hotwallet_erc20'

withdraw_method = {
    'fake': FakeWithdraw(),
    'fake_batch': FakeBatchWithdraw(running_with_queue=settings.IS_TESTNET),
    'electrum': ElectrumWithdraw(),
    'electrum_ltc': ElectrumLTCWithdraw(),
    'electron_cash': ElectronCashWithdraw(),
    'geth': GethWithdraw(),
    'geth_erc20': GethERC20Withdraw(),
    'eth_hotwallet': EthWithdraw(),  # only use for omg
    'eth_erc20_hotwallet': EthERC20Withdraw(),
    'eth_hd_hotwallet': EthHDWithdraw(),
    'eth_only_hd_hotwallet': EthOnlyHDWithdraw(),
    'eth_hd_hotwallet_erc20': EthERC20HDWithdraw(),
    'eth_hd_hotwallet_erc20_n2': EthERC20HDN2Withdraw(),
    'parity': ParityWithdraw(),
    'bnb_hot_wallet_api': BinanceChainWithdraw(),
    'trx_hotwallet': TRXAPIWithdraw(),
    'trx_trc20_hotwallet': TRC20WithdrawNew(),
    'trx_only_hd_hotwallet': TrxOnlyHDWithdraw(),
    'trx_hd_hotwallet_trc20': TrxTRC20HDWithdraw(),
    'ztrx_hotwallet': ZTrxWithdraw(),
    'xlm_hotwallet': StellarWithdraw(),
    'pmn_hotwallet': PMNAPIWithdraw(),
    'tether_erc20': GethTetherWithdraw(),
    'usdt_trx': USDTTRC20Withdraw(),
    'vandar_api': VandarAPIWithdraw(),
    'doge_hotwallet': DogeWithdraw(),
    'etc_hotwallet': EthereumClassicWithdraw(),
    'etc_hd_hotwallet': EthereumClassicHDWithdraw(),
    'eos_hotwallet': EosWithdraw(),
    'dot_hotwallet': DotWithdraw(),
    'bsc_hotwallet': BscWithdraw(),
    'bsc_hotwallet_bep20': BscBep20Withdraw(),
    'bsc_hd_hotwallet': BscHDWithdraw(),
    'bsc_hd_hotwallet_bep20': BscBep20HDWithdraw(),
    'bsc_geth': BscGethWithdraw(),
    'bsc_geth_bep20': BscGethBEP20Withdraw(),
    'lnd_hotwallet': LndWithdraw(),
    'ada_hotwallet': AdaWithdraw(),
    'xrp_hotwallet': RippleWithdraw(),
    'ftm_hotwallet': FtmWithdraw(),
    'ftm_hotwallet_erc20': FtmERC20Withdraw(),
    'ftm_hd_hotwallet': FtmOnlyHDWithdraw(),
    'polygon_hotwallet': PolygonWithdraw(),
    'polygon_hotwallet_erc20': PolygonERC20Withdraw(),
    'matic_hd_hotwallet': PolygonHDWithdraw(),
    'matic_hd_hotwallet_erc20': PolygonERC20HDWithdraw(),
    'avax_hotwallet': AvaxWithdraw(),
    'avax_hd_hotwallet': AvaxOnlyHDWithdraw(),
    'harmony_hotwallet': HarmonyWithdraw(),
    'harmony_hd_hotwallet': HarmonyHDWithdraw(),
    'atom_hotwallet': AtomWithdraw(),
    'near_hotwallet': NearWithdraw(),
    'solana_hotwallet': SolanaWithdraw(),
    'monero_hotwallet': MoneroWithdraw(),
    'algo_hotwallet': AlgoWithdraw(),
    'hbar_hotwallet': HederaWithdraw(),
    'flow_hotwallet': FlowWithdraw(),
    'aptos_hotwallet': AptosWithdraw(),
    'fil_hotwallet': FilecoinWithdraw(),
    'flare_hotwallet': FlareWithdraw(),
    'egld_hotwallet': ElrondWithdraw(),
    'arb_hotwallet': ArbWithdraw(),
    'arb_hotwallet_erc20': ArbERC20Withdraw(),
    'arb_hd_hotwallet': ArbHDWithdraw(),
    'arb_hd_hotwallet_erc20': ArbERC20HDWithdraw(),
    'usdt_arbitrum': USDTArbERC20Withdraw(),
    'ton_hotwallet': ToncoinWithdraw(),
    'ton_hlv2_hotwallet': [
        ToncoinHLv2Withdraw(),
        ToncoinHLv2Withdraw(hotwallet_index=1),
        ToncoinHLv2Withdraw(hotwallet_index=2),
        ToncoinHLv2Withdraw(hotwallet_index=3),
        ToncoinHLv2Withdraw(hotwallet_index=4),
        ToncoinHLv2Withdraw(hotwallet_index=5),
        ToncoinHLv2Withdraw(hotwallet_index=6),
        ToncoinHLv2Withdraw(hotwallet_index=7),
        ToncoinHLv2Withdraw(hotwallet_index=8),
        ToncoinHLv2Withdraw(hotwallet_index=9),
        ToncoinHLv2Withdraw(hotwallet_index=10),
        ToncoinHLv2Withdraw(hotwallet_index=11),
        ToncoinHLv2Withdraw(hotwallet_index=12),
        ToncoinHLv2Withdraw(hotwallet_index=13),
        ToncoinHLv2Withdraw(hotwallet_index=14),
        ToncoinHLv2Withdraw(hotwallet_index=15),
        ToncoinHLv2Withdraw(hotwallet_index=16),
        ToncoinHLv2Withdraw(hotwallet_index=17),
        ToncoinHLv2Withdraw(hotwallet_index=18),
        ToncoinHLv2Withdraw(hotwallet_index=19),
    ],
    'ton_token_hlv2_hotwallet': ToncoinTokenHLv2Withdraw(),
    'xtz_hotwallet': TezosWithdraw(),
    'enj_hotwallet': EnjinWithdraw(),
    's_hd_hotwallet': SonicHDWithdraw(),
    'solana_hotwallet_tokens': SolanaTokenWithdraw(),
    'base_hd_hotwallet': BaseHDWithdraw(),
    'base_hd_hotwallet_erc20': BaseERC20HDWithdraw(),
}


class ProcessingWithdrawMethod:
    __slots__ = [
        'batch_withdraws',
        'batch_withdraws_seen',
        'currency',
        'min_batch_timeout',
        'max_batch_timeout',
        'max_batch_size',
    ]
    AVAILABLE_METHODS = []

    def __init__(self, currency, min_batch_timeout=300, max_batch_timeout=900, max_batch_size=None):
        self.batch_withdraws = defaultdict(list)
        self.batch_withdraws_seen = set()
        self.currency = currency
        self.min_batch_timeout = min_batch_timeout
        self.max_batch_timeout = max_batch_timeout
        self.max_batch_size = max_batch_size

    @staticmethod
    def check_user_diff_enabled():
        return not Settings.is_disabled('withdraw_check_user_diff')

    @classmethod
    def check_user_diff(cls, user):
        """Check user account to find diff
        :param user: User
        :return: Boolean-- True if everything is OK
        """
        # Check user diff
        if cls.check_user_diff_enabled():
            user_wallets = Wallet.get_user_wallets(user)
            for wallet in user_wallets:
                if not wallet.is_current_balance_valid():
                    msg = '[Error] wallet has negative balance wallet id: {}'.format(wallet.id)
                    print(msg)
                    report_event(msg)
                    return False
            if get_user_diff(user=user):
                return False
        return True

    def check_withdraw_is_enabled(self, withdraw):
        """ Return whether withdrawals are enabled for this withdraw's currency """
        currency_name = get_currency_codename(withdraw.wallet.currency)
        flag_key = 'withdraw_enabled_{}_{}'.format(currency_name, withdraw.network.lower())
        if withdraw.contract_address:
            flag_key += f'_{withdraw.contract_address}'
        return Settings.get_trio_flag(
            flag_key,
            default='yes',  # all network in network_list filter by withdraw_enable=True
            third_option_value=cache.get(f'binance_withdraw_status_{currency_name}_{withdraw.network}'),
        )

    def get_auto_withdraw(
        self,
        address: str,
        withdraw_method_key: str = None,
        default_method: str = None,
        network: str = None,
        contract_address: str = None,
        hotwallet_index: int = 0,
    ) -> Dict:
        """Returns method key and method which want to send

        Args:
            address: Address to send. Currently not used. For future uses(Can be eliminated)
            withdraw_method_key: Manual value of method key
            default_method: Default method if key not exist
            network: Network of withdraw
            contract_address: Contract address of withdraw
            hotwallet_index: Hotwallet index to send

        Returns: Dictionary Like this:
        {
            'method_key': 'electrum',
            'method': ElectrumWithdraw(),
        }

        """
        if not withdraw_method_key:
            withdraw_method_key = 'withdraw_method_{}'.format(get_currency_codename(self.currency))
        if not default_method:
            default_method = DEFAULT_WITHDRAW_METHODS[self.currency]
            if isinstance(default_method, dict):
                if network is None:
                    network = CURRENCY_INFO.get(self.currency).get('default_network')
                default_method = default_method.get(network)
                withdraw_method_key += '_{}'.format(network)
        if contract_address:
            withdraw_method_key += f'_{contract_address}'
        method_key = Settings.get(withdraw_method_key, default_method)
        method = withdraw_method[method_key]

        if isinstance(method, list):
            method = method[hotwallet_index]
            method_key += f'#{hotwallet_index}'

        if not settings.IS_PROD:
            if not method.TESTNET_ENABLED:
                if method.BATCH_ENABLED:
                    return {
                        'method_key': 'fake_batch',
                        'method': withdraw_method['fake_batch'],
                    }
                else:
                    return {
                        'method_key': 'fake',
                        'method': withdraw_method['fake'],
                    }

        return {
            'method_key': method_key,
            'method': method,
        }

    def accept_withdraw(self, withdraw, log, a_withdraw):
        """Accept withdraw automatically.

        :param withdraw: Withdraw request that must be processed
        :type withdraw: WithdrawRequest

        :param log: Log instance
        :type log: AutomaticWithdrawLog

        :param a_withdraw: Automatic Withdraw instance
        :type a_withdraw: AutomaticWithdraw
        """
        # Integrity cross-check
        if a_withdraw.withdraw != withdraw:
            report_event('Withdraw!=AutomaticWithdraw')
            return

        # Check status of the original WithdrawRequest
        if a_withdraw.status not in AutomaticWithdraw.STATUSES_RETRY:
            print('Withdraw#{} already processed - ignoring'.format(withdraw.pk))
            return
        if withdraw.status not in WithdrawRequest.STATUSES_ACCEPTABLE:
            m = 'Change the status of withdraw #{} to verified'.format(withdraw.pk)
            print(m)
            log.description = m
            log.status = 6
            log.save()
            return

        if settings.WITHDRAW_CREATE_TX_VERIFY and not (withdraw.transaction and withdraw.transaction.pk):
            msg = '[Error] Withdraw request is not valid. withdraw id: {}'.format(withdraw.pk)
            print(msg)
            raise ValueError(msg)

        if not withdraw.wallet.user.is_user_eligible_to_withdraw:
            if a_withdraw.status != AutomaticWithdraw.STATUS.waiting:
                update_auto_withdraw_status(a_withdraw, AutomaticWithdraw.STATUS.waiting)
                withdraw.status = WithdrawRequest.STATUS.waiting
                withdraw.save(update_fields=['status'])
            return

        # Check system diff
        if not self.check_user_diff(withdraw.wallet.user):
            update_auto_withdraw_status(a_withdraw, AutomaticWithdraw.STATUS.diff)
            return

        # Accept the request
        update_auto_withdraw_status(a_withdraw, AutomaticWithdraw.STATUS.accepted)
        print('[Withdraw] Accepted withdraw: {}'.format(withdraw.pk))
        withdraw.status = WithdrawRequest.STATUS.accepted
        withdraw.save(update_fields=['status'])

    def pre_processing_withdraw(self, withdraw, log, a_withdraw):
        """Pre-processing of withdraw after verified by user.

        :param withdraw: Withdraw request that must be processed
        :type withdraw: WithdrawRequest

        :param log: Log instance
        :type log: AutomaticWithdrawLog

        :param a_withdraw: Automatic Withdraw instance
        :type a_withdraw: AutomaticWithdraw

        """
        if a_withdraw.status in AutomaticWithdraw.STATUSES_RETRY:
            pass
        else:
            print('Withdraw#{} already pre-processed - ignoring'.format(withdraw.pk))
            return
        if withdraw.status != WithdrawRequest.STATUS.accepted:
            m = 'Change the status of withdraw #{} to accept'.format(withdraw.pk)
            print(m)
            log.description = m
            log.status = 6
            log.save()
            return

        if settings.WITHDRAW_CREATE_TX_VERIFY and not (withdraw.transaction and withdraw.transaction.pk):
            msg = '[Error] Withdraw request is not valid. withdraw id: {}'.format(withdraw.pk)
            print(msg)
            raise ValueError(msg)

        withdraw.status = WithdrawRequest.STATUS.processing
        withdraw.save(update_fields=['status'])

    def processing_withdraws(self, withdraws, hotwallet_index=0):
        """Processing withdraw after wait time in processing state.

        :param withdraws: Withdraw requests that must be processed
        :type withdraws: List[tuple[WithdrawRequest, AutomaticWithdrawLog, AutomaticWithdraw]]

        """
        for withdraw, log, a_withdraw in withdraws:
            if a_withdraw.status not in AutomaticWithdraw.STATUSES_RETRY:
                print('Withdraw#{} already processed - ignoring'.format(withdraw.pk))
                continue
            if withdraw.status != WithdrawRequest.STATUS.processing:
                m = 'Change the status of withdraw #{} to processing'.format(withdraw.pk)
                print(m)
                log.description = m
                log.status = 6
                log.save()
                continue

            method_key_result = self.get_auto_withdraw(
                withdraw.target_address,
                network=withdraw.network,
                contract_address=withdraw.contract_address,
                hotwallet_index=hotwallet_index,
            )
            method_key = method_key_result['method_key']
            method = method_key_result['method']
            method_type_key = method_key.split('#')[0]

            if method.BATCH_ENABLED:
                if self.max_batch_size is not None and len(self.batch_withdraws[method_key]) >= self.max_batch_size:
                    break

            withdraw_timeout = a_withdraw.processing_timeout()
            if not withdraw_timeout:
                continue
            data = [(withdraw, log, a_withdraw)]
            try:
                if withdraw.status != WithdrawRequest.STATUS.processing:
                    m = 'Cancel the processing of withdraw: {}'.format(withdraw.pk)
                    print(m)
                    log.description = m
                    log.status = 6
                    log.save()
                    continue

                # Check transaction for the withdraw request
                if not settings.WITHDRAW_CREATE_TX_VERIFY:
                    withdraw.create_transaction()
                if not (withdraw.transaction and withdraw.transaction.pk):
                    msg = '[Error] Withdraw request is not valid. withdraw id: {}'.format(withdraw.pk)
                    print(msg)
                    raise ValueError(msg)

                # Start sending transaction on blockchain
                a_withdraw.status = AutomaticWithdraw.STATUS.sending
                a_withdraw.tp = withdraw_type[method_type_key]
                a_withdraw.save(update_fields=['tp', 'status'])
                with transaction.atomic():
                    if method.BATCH_ENABLED:
                        if withdraw.pk not in self.batch_withdraws_seen:
                            self.batch_withdraws_seen.add(withdraw.pk)
                            self.batch_withdraws[method_key].append((withdraw, log, a_withdraw))
                            continue

                    method.process_withdraw(data, self.currency)

            except NobitexWithdrawException as e:
                report_exception()
                update_auto_withdraw_status(data, AutomaticWithdraw.STATUS.failed)
                exc_type, exc_value, exc_tb = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_tb)
                log.description = str(e)[:1000]
                log.status = 4
                log.save()
                continue
            except Exception as e:
                report_exception()
                update_auto_withdraw_status(data, AutomaticWithdraw.STATUS.failed)
                exc_type, exc_value, exc_tb = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_tb)
                log.description = str(e)[:1000]
                log.status = 4
                log.save()
                continue
        for method_key in list(self.batch_withdraws):
            method_info = method_key.split('#')
            method_key_without_index = method_info[0]
            method_key_index = 0
            if len(method_info) > 1:
                method_key_index = int(method_info[1])

            method = withdraw_method[method_key_without_index]
            if isinstance(method, list):
                method = method[method_key_index]

            if not method.BATCH_ENABLED:
                continue
            if not self.batch_withdraws[method_key]:
                continue
            withdraws_pk = [withdraw.pk for withdraw, _, _ in self.batch_withdraws[method_key]]
            print(f'Batch Withdraws for {method_key}: {withdraws_pk}')
            sorted_withdraw = sorted(self.batch_withdraws[method_key], key=lambda withdraw_tuple: withdraw_tuple[2].created_at)
            first_batch_element = sorted_withdraw[0]
            last_batch_element = sorted_withdraw[-1]
            # If we wait for more than min_batch_timeout or total wait is more than max_batch_match skip this condition
            wait_more = True
            if self.max_batch_size is not None and len(sorted_withdraw) >= self.max_batch_size:
                wait_more = False
            if last_batch_element[2].processing_timeout(timeout=self.min_batch_timeout) or first_batch_element[
                2
            ].processing_timeout(timeout=self.max_batch_timeout):
                wait_more = False
            if wait_more:
                continue
            data = sorted_withdraw
            if not data:
                continue
            try:
                with transaction.atomic():
                    self.batch_withdraws[method_key] = []
                    self.batch_withdraws_seen = set()
                    method.process_withdraw(data, self.currency)
            except NobitexWithdrawException as e:
                report_exception()
                update_auto_withdraw_status(data, AutomaticWithdraw.STATUS.failed, error_msg=str(e)[:1000])
                exc_type, exc_value, exc_tb = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_tb)
                continue
            except Exception as e:
                report_exception()
                update_auto_withdraw_status(data, AutomaticWithdraw.STATUS.failed, error_msg=str(e)[:1000])
                exc_type, exc_value, exc_tb = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_tb)
                continue

    def settle_to_internal_wallet(self, withdraw, target_wallet=None):
        if not withdraw.is_accepted:
            raise ValueError('Only accepted requests can be settled')
        target_wallet = target_wallet or withdraw.get_internal_target_wallet()
        if not target_wallet:
            raise ValueError('Target address is not an internal wallet')
        if withdraw.currency == Currencies.rls:
            return self.settle_to_internal_system_rial_wallet(withdraw, target_wallet=target_wallet)

        with transaction.atomic():
            withdraw.status = withdraw.STATUS.sent
            withdraw.save(update_fields=['status'])
            withdraw.status = withdraw.STATUS.done
            withdraw.tp = withdraw.TYPE.internal
            currency = withdraw.wallet.get_currency_display()
            withdraw.blockchain_url = settings.PROD_FRONT_URL + 'receipt/{}/{}'.format(currency, withdraw.uid.hex)
            withdraw.save(update_fields=['status', 'tp', 'blockchain_url'])
            if not (withdraw.transaction and withdraw.transaction.pk):
                raise ValueError('Withdraw transaction is null')
            # Prepare a description for transaction
            gift_user = User.get_gift_system_user()
            if target_wallet.wallet.user_id == gift_user.id:
                transaction_description = f'صدور کارت هدیه برای کاربر #{withdraw.wallet.user_id}'
            elif withdraw.wallet.user_id == gift_user.id:
                transaction_description = 'دریافت کارت هدیه'
            else:
                network = withdraw.network
                if network is None:
                    network = CURRENCY_INFO.get(withdraw.currency).get('default_network')
                from_addr = withdraw.wallet.get_current_deposit_address(network=network)
                if from_addr:
                    from_addr = from_addr if isinstance(from_addr, str) else from_addr.address
                else:
                    from_addr = 'uid#{}'.format(withdraw.wallet.user_id)
                transaction_description = f'Internal transfer from "{from_addr}"'
            # Create deposit transaction
            target_wallet.wallet.refresh_from_db()
            deposit_transaction = target_wallet.wallet.create_transaction(
                tp='deposit',
                amount=withdraw.amount,
                description=transaction_description,
            )
            if not deposit_transaction:
                raise ValueError('Cannot create deposit transaction for internal coin transfer')
            deposit_transaction.commit(ref=Transaction.Ref('InternalTransferDeposit', withdraw.pk))
            if isinstance(target_wallet, WalletDepositTag):
                tag = target_wallet
                target_wallet = None
            else:
                tag = None
            rial_value = PriceEstimator.get_rial_value_by_best_price(withdraw.amount, withdraw.wallet.currency, 'sell')
            deposit = ConfirmedWalletDeposit.objects.create(
                tx_hash='nobitex-internal-W{}'.format(withdraw.pk),
                address=target_wallet,
                confirmed=True,
                confirmations=1000,
                amount=withdraw.amount,
                transaction=deposit_transaction,
                tag=tag,
                rial_value=rial_value,
                contract_address=withdraw.contract_address,
            )
            print(deposit.wallet)

    def settle_to_internal_system_rial_wallet(self, withdraw, target_wallet=None):
        """Settle internal Rial withdraws. This is currently only used for GiftCard withdraws."""
        if not withdraw.is_accepted:
            raise ValueError('Only accepted requests can be settled')
        if withdraw.currency != Currencies.rls:
            raise ValueError('This method is only for system rial transfer.')
        target_wallet = target_wallet or withdraw.get_internal_target_wallet()
        if not target_wallet:
            raise ValueError('Target address is not an internal wallet')
        with transaction.atomic():
            withdraw.status = withdraw.STATUS.sent
            withdraw.save(update_fields=['status'])
            withdraw.status = withdraw.STATUS.done
            withdraw.tp = withdraw.TYPE.internal
            withdraw.blockchain_url = '{}receipt/{}/{}'.format(
                settings.PROD_FRONT_URL,
                withdraw.wallet.get_currency_display(),
                withdraw.uid.hex,
            )
            withdraw.save(update_fields=['status', 'tp', 'blockchain_url'])
            if not (withdraw.transaction and withdraw.transaction.pk):
                raise ValueError('Withdraw transaction is null')
            # Prepare a description for transaction
            gift_user = User.get_gift_system_user()
            if target_wallet.user_id == gift_user.id:
                transaction_description = f'صدور کارت هدیه برای کاربر #{withdraw.wallet.user_id}'
            else:
                transaction_description = f'Internal transfer from "uid#{withdraw.wallet.user_id}"'
            # Create deposit transaction
            target_wallet.refresh_from_db()
            deposit_transaction = target_wallet.create_transaction(
                tp='manual',
                amount=withdraw.amount,
                description=transaction_description,
            )
            if not deposit_transaction:
                raise ValueError('Cannot create deposit transaction for internal coin transfer')
            deposit_transaction.commit(ref=Transaction.Ref('InternalTransferDeposit', withdraw.pk))

    def process_internal_transfer(self, withdraw, log, a_withdraw):
        if withdraw.status in WithdrawRequest.STATUSES_COMMITED:
            # Do not alter any committed withdraws
            return
        if not withdraw.is_accepted:
            return
        try:
            target_wallet = withdraw.get_internal_target_wallet()
            if not target_wallet:
                return
            if withdraw.tp == withdraw.TYPE.normal:
                withdraw.tp = withdraw.TYPE.internal
                WithdrawRequest.objects.filter(pk=withdraw.pk).update(tp=withdraw.tp)
            self.settle_to_internal_wallet(withdraw=withdraw, target_wallet=target_wallet)
            update_auto_withdraw_status(a_withdraw, AutomaticWithdraw.STATUS.done)
        except (ValueError, ParseError) as error:
            report_exception()
            update_auto_withdraw_status(a_withdraw, AutomaticWithdraw.STATUS.failed)
            m = f'Internal withdraw error #withdraw:{withdraw.pk} error:{error}'
            print(m)
            log.description = m
            log.status = 12
            log.save()

    def withdraw_change_states(self, withdraws, hotwallet_index=0):
        """ Process one withdraw.

            :param withdraws: List[WithdrawRequest]
        """
        processing_withdraws_obj = []
        accepting_withdraws_obj = []
        for withdraw in withdraws:
            # Check Withdraw Enabled
            if not self.check_withdraw_is_enabled(withdraw):
                continue

            log = AutomaticWithdrawLog(withdraw=withdraw)
            try:
                a_withdraw = withdraw.auto_withdraw
            except AutomaticWithdraw.DoesNotExist:
                auto_withdraw_type_info = self.get_auto_withdraw(
                    address=withdraw.target_address,
                    network=withdraw.network,
                    contract_address=withdraw.contract_address,
                    hotwallet_index=hotwallet_index,
                )
                auto_withdraw_type_key = auto_withdraw_type_info['method_key'].split('#')[0]
                auto_withdraw_tp = withdraw_type.get(auto_withdraw_type_key)
                if not auto_withdraw_tp:
                    print('Unsupported withdraw type: {}'.format(auto_withdraw_type_key))
                    continue
                a_withdraw = AutomaticWithdraw.objects.create(
                    withdraw=withdraw,
                    tp=auto_withdraw_tp,
                )

            # Only process non-internal withdraw
            if withdraw.status == WithdrawRequest.STATUS.accepted:
                self.process_internal_transfer(withdraw=withdraw, log=log, a_withdraw=a_withdraw)
            # Pre-processing withdraw request: Accepted --> Processing
            if withdraw.status == WithdrawRequest.STATUS.accepted:
                self.pre_processing_withdraw(withdraw, log, a_withdraw)

            # Processing withdraw request: Processing --> Send
            if withdraw.status == WithdrawRequest.STATUS.processing and a_withdraw.status != AutomaticWithdraw.STATUS.failed:
                processing_withdraws_obj.append((withdraw, log, a_withdraw))

            # Accept withdraw request: Verified/Waiting --> Accepted
            if withdraw.status in WithdrawRequest.STATUSES_ACCEPTABLE:
                accepting_withdraws_obj.append((withdraw, log, a_withdraw))
        self.processing_withdraws(processing_withdraws_obj, hotwallet_index=hotwallet_index)
        for withdraw, log, a_withdraw in accepting_withdraws_obj:
            self.accept_withdraw(withdraw, log, a_withdraw)

    def process_withdraws(self, withdraw_requests, status, hotwallet_index=0):
        """Process all withdraw automatically.
        Only process once. If fails does not retry automatically.
        """
        processing_withdraw_requests = []
        for withdraw in withdraw_requests:
            # Filtering unprocessable withdraws, like Rial withdraws in the night
            if not withdraw.can_automatically_send():
                continue
            try:
                already_processed = withdraw.auto_withdraw.status not in AutomaticWithdraw.STATUSES_AUTOMATIC_RETRY
            except AutomaticWithdraw.DoesNotExist:
                already_processed = False
            if already_processed:
                continue

            # Check User Restrictions
            user = withdraw.wallet.user
            if user.is_restricted('WithdrawRequest'):
                print('WithdrawRequest is restricted for user: {}'.format(user.username))
                continue
            if settings.WITHDRAW_FRAUD_ENABLED and not withdraw.is_rial:
                restriction = user.get_restriction('WithdrawRequestCoin')
                if restriction:
                    try:
                        self.reject_withdraw_based_on_fraud_detection(withdraw, restriction)
                    except IntegrityError:
                        report_exception()
                        continue
                    continue
            # Check Withdraw Enabled
            if not self.check_withdraw_is_enabled(withdraw):
                continue
            if withdraw.status != status:
                print('WithdrawRequest status has been changed during the processing: {}'.format(withdraw.pk))
                continue
            # Process
            print('Processing withdraw {}'.format(withdraw.pk))
            processing_withdraw_requests.append(withdraw)
        self.withdraw_change_states(processing_withdraw_requests, hotwallet_index=hotwallet_index)

        # done_processing()
    @staticmethod
    def reject_withdraw_based_on_fraud_detection(withdraw: WithdrawRequest, restriction: UserRestriction) -> bool:
        """
        Rejects a withdrawal request based on fraud detection.

        Args:
            withdraw (WithdrawRequest): The withdrawal request to be rejected.
            restriction (UserRestriction): The restriction object containing considerations.

        Returns:
            bool: True if the withdrawal request was successfully rejected, False otherwise.
        """
        if any(item in restriction.considerations for item in Settings.get_list('withdrawal_restrictions')):
            withdraw.refresh_from_db()
            if withdraw.is_cancelable:
                with transaction.atomic():
                    m = 'Change the status of withdraw #{} to rejected due to fraud detection'.format(withdraw.pk)
                    # change log
                    auto_log = AutomaticWithdrawLog.objects.filter(withdraw=withdraw).first()
                    if auto_log:
                        auto_log.description = m
                        auto_log.status = 8
                        auto_log.save()
                    # change automatic withdraw
                    if hasattr(withdraw, 'auto_withdraw'):
                        withdraw.auto_withdraw.status = AutomaticWithdraw.STATUS.canceled
                        withdraw.auto_withdraw.save(update_fields=['status'])
                    # Change withdraw status
                    withdraw.status = WithdrawRequest.STATUS.rejected
                    withdraw.save(update_fields=['status'])
                return True
        return False
