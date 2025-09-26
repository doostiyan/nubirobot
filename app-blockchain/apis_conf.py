from typing import Dict

from exchange.blockchain.api.ada.cardano_explorer_interface import CardanoExplorerInterface
from exchange.blockchain.api.algorand.algorand_explorer_interface import AlgorandExplorerInterface
from exchange.blockchain.api.apt.aptos_explorer_interface import AptosExplorerInterface
from exchange.blockchain.api.arbitrum.arbitrum_explorer_interface import ArbitrumExplorerInterface
from exchange.blockchain.api.atom.atom_explorer_interface import AtomExplorerInterface
from exchange.blockchain.api.atom.atom_node import (
                                                    AtomAllthatnode,
                                                    AtomGetblockNode,
                                                    AtomscanNode,
                                                    CosmosNetworkNode,
                                                    FigmentNode,
                                                    LavenderFiveNode,
                                                    PupmosNode,
)
from exchange.blockchain.api.avax.avax_explorer_interface import AvalancheExplorerInterface
from exchange.blockchain.api.base.base_explorer_interface import BaseExplorerInterface
from exchange.blockchain.api.bch import BitcoinCashExplorerInterface
from exchange.blockchain.api.bch.bch_blockbook import BitcoinCashBlockbookAPI
from exchange.blockchain.api.bch.bch_node import BchElectronNode
from exchange.blockchain.api.bnb.binance import BinanceAPI
from exchange.blockchain.api.bnb.bnb_explorer_interface import BnbExplorerInterface
from exchange.blockchain.api.bnb.bnb_node import BinanceNodeAPI
from exchange.blockchain.api.bnb.mintscan import BnbMintscan
from exchange.blockchain.api.bsc.bsc_bitquery import BscBitqueryAPI
from exchange.blockchain.api.bsc.bsc_blockbook import BscBlockbookAPI, BscKleverBlockbookAPI, BscNobitexBlockbookAPI
from exchange.blockchain.api.bsc.bsc_covalent import BSCCovalenthqAPI
from exchange.blockchain.api.bsc.bsc_explorer_interface import BscExplorerInterface
from exchange.blockchain.api.bsc.bscscan import BscScanAPI
from exchange.blockchain.api.bsc.moralis import MoralisAPI
from exchange.blockchain.api.btc import BTCExplorerInterface
from exchange.blockchain.api.btc.bitaps import BitapsAPI
from exchange.blockchain.api.btc.btc_chain import BtcAPI
from exchange.blockchain.api.btc.btc_sochain import BitcoinSochainAPI
from exchange.blockchain.api.btc.cryptoid import CryptoidAPI
from exchange.blockchain.api.btc.electrum import BtcElectrum
from exchange.blockchain.api.btc.smartbit import SmartbitAPI
from exchange.blockchain.api.doge.coinexplorer import CoinexplorerAPI
from exchange.blockchain.api.doge.doge_blockbook import DogeBlockbookAPIv2, DogeNowNodesAPI
from exchange.blockchain.api.doge.doge_blockchair import DogeBlockChairApi
from exchange.blockchain.api.doge.doge_blockcypher import DogeBlockcypherAPI
from exchange.blockchain.api.doge.doge_explorer_interface import DogeExplorerInterface
from exchange.blockchain.api.doge.doge_sochain import DogeSochainAPI
from exchange.blockchain.api.doge.dogechain import DogechainAPI
from exchange.blockchain.api.dot.dot_explorer_interface import DotExplorerInterface
from exchange.blockchain.api.dot.dot_figmentAPI import DotFigmentAPI
from exchange.blockchain.api.dot.polkascan import PolkascanAPI
from exchange.blockchain.api.dot.subscan import SubscanAPI
from exchange.blockchain.api.dydx.dydx_explorer_interface import DydxExplorerInterface
from exchange.blockchain.api.elrond.elrond_explorer_interface import ElrondExplorerInterface
from exchange.blockchain.api.enj.enjin_explorer_interface import EnjinExplorerInterface
from exchange.blockchain.api.eos.eos_explorer_interface import EosExplorerInterface
from exchange.blockchain.api.eos.eosn import EosrioAPI
from exchange.blockchain.api.etc.etc_blockbook import EtcBlockBookAPI, EthereumClassicBlockbookAPI
from exchange.blockchain.api.etc.etc_blockscout import ETCBlockscoutAPI
from exchange.blockchain.api.etc.etc_explorer_interface import EtcExplorerInterface
from exchange.blockchain.api.eth.eth_blockbook import (
                                                    EthereumBlockbookAPI,
                                                    EthereumEthBlockBlockbookAPI,
                                                    EthereumEthMetaWireBlockBookAPI,
                                                    EthereumHeatWallet1BlockbookAPI,
                                                    EthereumHeatWallet2BlockbookAPI,
)
from exchange.blockchain.api.eth.eth_blockcypher import EthBlockcypherAPI
from exchange.blockchain.api.eth.eth_covalent import ETHCovalenthqAPI
from exchange.blockchain.api.eth.eth_ethplorer import EthplorerAPI
from exchange.blockchain.api.eth.eth_explorer_interface import EthExplorerInterface
from exchange.blockchain.api.eth.eth_web3 import ETHWeb3
from exchange.blockchain.api.filecoin.filecoin_explorer_interface import FilecoinExplorerInterface
from exchange.blockchain.api.flow.flow_explorer_interface import FlowExplorerInterface
from exchange.blockchain.api.flr.flare_explorer_interface import FlareExplorerInterface
from exchange.blockchain.api.ftm.ftm_covalent import FantomCovalenthqAPI
from exchange.blockchain.api.ftm.ftm_explorer_interface import FTMExplorerInterface
from exchange.blockchain.api.ftm.ftm_ftmscan import FtmScanAPI
from exchange.blockchain.api.ftm.ftm_graphql import FantomGraphQlAPI
from exchange.blockchain.api.ftm.ftm_web3 import FtmWeb3API
from exchange.blockchain.api.general.explorer_interface import ExplorerInterface
from exchange.blockchain.api.hedera.hedera_explorer_interface import HederaExplorerInterface
from exchange.blockchain.api.ltc.electrum import ElectrumAPI
from exchange.blockchain.api.ltc.ltc_blockbook import (
                                                    LitecoinAtomicWalletBlockbookAPI,
                                                    LitecoinBinanceBlockbookAPI,
                                                    LitecoinBlockbookAPI,
                                                    LitecoinHeatWalletBlockbookAPI,
)
from exchange.blockchain.api.ltc.ltc_blockcypher import LtcBlockcypherAPI
from exchange.blockchain.api.ltc.ltc_explorer_interface import LTCExplorerInterface
from exchange.blockchain.api.ltc.ltc_sochain import LitecoinSochainAPI
from exchange.blockchain.api.near.near_explorer_interface import (
                                                    NearExplorerInterface,
                                                    OfficialNearExplorerInterface,
                                                    QuickNodeNearExplorerInterface,
                                                    RpcNearExplorerInterface,
)
from exchange.blockchain.api.near.near_figment import NearFigmentEnrichedAPI
from exchange.blockchain.api.near.near_indexer import NearIndexerAPI
from exchange.blockchain.api.near.near_nearblocks import NearBlocksAPI
from exchange.blockchain.api.near.near_nearscan import NearScan
from exchange.blockchain.api.one.one_covalent import ONECovalenthqAPI
from exchange.blockchain.api.one.one_explorer_interface import OneExplorerInterface
from exchange.blockchain.api.one.one_rpc import AnkrHarmonyRpc, HarmonyRPC
from exchange.blockchain.api.one.one_web3 import OneWeb3API
from exchange.blockchain.api.pmn.kuknos_horizon import KuknosHorizonAPI
from exchange.blockchain.api.polygon.polygon_explorer_interface import PolygonExplorerInterface
from exchange.blockchain.api.sol.sol_explorer_interface import (
                                                    BitqueryExplorerInterface,
                                                    RpcSolExplorerInterface,
                                                    SolExplorerInterface,
)
from exchange.blockchain.api.sonic.sonic_explorer_interface import SonicExplorerInterface

# from exchange.blockchain.api.sui.sui_explorer_interface import RpcSuiExplorerInterface # noqa: ERA001
from exchange.blockchain.api.tezos.tezos_explorer_interface import TezosExplorerInterface
from exchange.blockchain.api.ton.ton_explorer_interface import TonExplorerInterface
from exchange.blockchain.api.trx.tron_explorer_interface import TronExplorerInterface
from exchange.blockchain.api.trx.tron_full_node import TronFullNodeAPI
from exchange.blockchain.api.trx.tron_solidity_node import TronSolidityNodeAPI
from exchange.blockchain.api.trx.trongrid import TrongridAPI
from exchange.blockchain.api.trx.tronscan import TronscanAPI
from exchange.blockchain.api.trx.trx_blockbook import TrxBlockbookAPI
from exchange.blockchain.api.xlm.expert import XlmExpertAPI
from exchange.blockchain.api.xlm.xlm_explorer_interface import StellarExplorerInterface
from exchange.blockchain.api.xmr.monero import MoneroAPI
from exchange.blockchain.api.xmr.xmr_explorer_interface import XmrExplorerInterface
from exchange.blockchain.api.xrp.ripple import RippleAPI
from exchange.blockchain.api.xrp.ripple_explorer_interface import RippleExplorerInterface
from exchange.blockchain.api.xrp.xrp_rpc import RippleRpcAPI

"""
    NETWORK = {
        'get_balances': '{network}_{api}',

        - list all apis for this network that support get_balance
        - same for other functions
        'get_balances_alternatives': ['{network}_{api}', '{network}_{api2}'],

        'get_txs': '',
        'get_txs_alternatives': [],

        'txs_details': '',
        'txs_details_alternatives': [],

        - if tagged network,  no need to these fields
        'get_blocks_addresses': '',
        'get_blocks_addresses_alternatives': [],
    }
"""

APIS_CONF = {
    'ADA': {
        'get_balances': 'ada_explorer_interface',
        'get_balances_alternatives': ['ada_explorer_interface'],
        'get_txs': 'ada_explorer_interface',
        'get_txs_alternatives': ['ada_explorer_interface'],
        'txs_details': 'ada_explorer_interface',
        'txs_details_alternatives': ['ada_explorer_interface'],
        'get_blocks_addresses': 'ada_explorer_interface',
        'get_blocks_addresses_alternatives': ['ada_explorer_interface'],
        'block_head_apis': ['ada_explorer_interface'],
    },
    'ALGO': {
        'get_balances': 'algorand_explorer_interface',
        'get_balances_alternatives': ['algorand_explorer_interface'],
        'get_txs': 'algorand_explorer_interface',
        'get_txs_alternatives': ['algorand_explorer_interface'],
        'txs_details': 'algorand_explorer_interface',
        'txs_details_alternatives': ['algorand_explorer_interface'],
        'get_blocks_addresses': 'algorand_explorer_interface',
        'get_blocks_addresses_alternatives': ['algorand_explorer_interface'],
        'block_head_apis': ['algorand_explorer_interface'],
    },
    'APT': {
        'get_balances': 'aptos_explorer_interface',
        'get_balances_alternatives': ['aptos_explorer_interface'],
        'get_txs': 'aptos_explorer_interface',
        'get_txs_alternatives': ['aptos_explorer_interface'],
        'txs_details': 'aptos_explorer_interface',
        'txs_details_alternatives': ['aptos_explorer_interface'],
        'get_blocks_addresses': 'aptos_explorer_interface',
        'get_blocks_addresses_alternatives': ['aptos_explorer_interface'],
        'block_head_apis': ['aptos_explorer_interface'],
    },
    'ARB': {
        'get_balances': 'arbitrum_explorer_interface',
        'get_balances_alternatives': ['arbitrum_explorer_interface'],
        'get_txs': 'arbitrum_explorer_interface',
        'get_txs_alternatives': ['arbitrum_explorer_interface'],
        'txs_details': 'arbitrum_explorer_interface',
        'txs_details_alternatives': ['arbitrum_explorer_interface'],
        'get_blocks_addresses': 'arbitrum_explorer_interface',
        'get_blocks_addresses_alternatives': ['arbitrum_explorer_interface'],
        'block_head_apis': ['arbitrum_explorer_interface'],
    },
    'ATOM': {
        'get_balances': 'atom_explorer_interface',
        'get_balances_alternatives': ['atom_explorer_interface'],
        'get_txs': 'atom_explorer_interface',
        'get_txs_alternatives': ['atom_explorer_interface'],
        'txs_details': 'atom_explorer_interface',
        'txs_details_alternatives': ['atom_explorer_interface'],
        'block_head_apis': ['atom_explorer_interface'],
    },
    'AVAX': {
        'get_balances': 'avax_explorer_interface',
        'get_balances_alternatives': ['avax_explorer_interface'],
        'get_txs': 'avax_explorer_interface',
        'get_txs_alternatives': ['avax_explorer_interface'],
        'txs_details': 'avax_explorer_interface',
        'txs_details_alternatives': ['avax_explorer_interface'],
        'get_blocks_addresses': 'avax_explorer_interface',
        'get_blocks_addresses_alternatives': ['avax_explorer_interface'],
        'block_head_apis': ['avax_explorer_interface'],
    },
    'BASE': {
        'get_balances': 'base_explorer_interface',
        'get_balances_alternatives': ['base_explorer_interface'],
        'get_txs': 'base_explorer_interface',
        'get_txs_alternatives': ['base_explorer_interface'],
        'txs_details': 'base_explorer_interface',
        'txs_details_alternatives': ['base_explorer_interface'],
        'get_blocks_addresses': 'base_explorer_interface',
        'get_blocks_addresses_alternatives': ['base_explorer_interface'],
        'block_head_apis': ['base_explorer_interface'],
    },
    'BNB': {
        'get_balances': 'bnb_explorer_interface',
        'get_balances_alternatives': ['bnb_explorer_interface'],
        'get_txs': 'bnb_explorer_interface',
        'get_txs_alternatives': ['bnb_explorer_interface'],
        'txs_details': 'bnb_explorer_interface',
        'txs_details_alternatives': ['bnb_explorer_interface'],
        'block_head_apis': ['bnb_explorer_interface'],
    },
    'BSC': {
        'get_balances': 'bsc_explorer_interface',
        'get_balances_alternatives': ['bsc_scan', 'bsc_moralis', 'bsc_explorer_interface', 'bsc_covalent'],
        'get_txs': 'bsc_explorer_interface',
        'get_txs_alternatives': ['bsc_scan', 'bsc_moralis', 'bsc_covalent', 'bsc_explorer_interface'],
        'txs_details': 'bsc_explorer_interface',
        'txs_details_alternatives': ['bsc_scan', 'bsc_bitquery', 'bsc_moralis', 'bsc_explorer_interface',
                                     'bsc_covalent', 'bsc_blockbook',
                                     'bsc_nobitex_blockbook', 'bsc_klever_blockbook'],
        'get_blocks_addresses': 'bsc_explorer_interface',
        'get_blocks_addresses_alternatives': ['bsc_scan', 'bsc_blockbook', 'bsc_bitquery',
                                              'bsc_moralis', 'bsc_explorer_interface', 'bsc_nobitex_blockbook',
                                              'bsc_klever_blockbook'],
        'block_head_apis': ['bsc_explorer_interface'],
    },
    'BCH': {
        'get_balances': 'bch_node',
        'get_balances_alternatives': ['bch_explorer_interface', 'bch_node'],
        'get_txs': 'bch_blockbook',
        'get_txs_alternatives': ['bch_explorer_interface', 'bch_blockbook'],
        'txs_details': 'bch_explorer_interface',
        'txs_details_alternatives': ['bch_explorer_interface'],
        'get_blocks_addresses': 'bch_blockbook',
        'get_blocks_addresses_alternatives': ['bch_explorer_interface', 'bch_blockbook'],
        'block_head_apis': ['bch_blockbook', 'bch_explorer_interface'],
    },
    'BTC': {
        'get_balances': 'btc_explorer_interface',
        'get_balances_alternatives': ['btc_explorer_interface', 'btc_electrum', 'btc_cryptoid',
                                      'btc_sochain', 'btc_smartbit'],
        'get_txs': 'btc_explorer_interface',
        'get_txs_alternatives': ['btc_explorer_interface', 'btc_smartbit'],
        'txs_details': 'btc_explorer_interface',
        'txs_details_alternatives': ['btc_explorer_interface', 'btc_bitaps', 'btc_chain', 'btc_sochain'],
        'get_blocks_addresses': 'btc_explorer_interface',
        'get_blocks_addresses_alternatives': ['btc_explorer_interface'],
        'block_head_apis': ['btc_explorer_interface'],
    },
    'DYDX': {
        'get_balances': 'dydx_explorer_interface',
        'get_balances_alternatives': ['dydx_explorer_interface'],
        'get_txs': 'dydx_explorer_interface',
        'get_txs_alternatives': ['dydx_explorer_interface'],
        'txs_details': 'dydx_explorer_interface',
        'txs_details_alternatives': ['dydx_explorer_interface'],
        'block_head_apis': ['dydx_explorer_interface'],
    },
    'DOGE': {
        'get_balances': 'doge_explorer_interface',
        'get_balances_alternatives': ['doge_explorer_interface', 'doge_blockbook2', 'doge_nownodes',
                                      'doge_chain'],
        'get_txs': 'doge_explorer_interface',
        'get_txs_alternatives': ['doge_explorer_interface', 'doge_blockbook2', 'doge_nownodes'],
        'txs_details': 'doge_explorer_interface',
        'txs_details_alternatives': ['doge_explorer_interface', 'doge_blockbook2', 'doge_nownodes', 'doge_chain'],
        # untrusted: 'doge_chain', 'doge_sochain'
        'get_blocks_addresses': 'doge_explorer_interface',
        'get_blocks_addresses_alternatives': ['doge_blockbook2', 'doge_nownodes', 'doge_explorer_interface'],
        'block_head_apis': ['doge_explorer_interface'],
    },
    'DOT': {
        'get_balances': 'dot_explorer_interface',
        'get_balances_alternatives': ['dot_explorer_interface', 'dot_polkascan'],
        'get_txs': 'dot_explorer_interface',
        'get_txs_alternatives': ['dot_explorer_interface', 'dot_polkascan'],
        'txs_details': 'dot_explorer_interface',
        'txs_details_alternatives': ['dot_explorer_interface', 'dot_polkascan', 'dot_figment'],
        'get_blocks_addresses': 'dot_explorer_interface',
        'get_blocks_addresses_alternatives': ['dot_explorer_interface', 'dot_polkascan'],
        'block_head_apis': ['dot_explorer_interface'],
    },
    'EGLD': {
        'get_balances': 'elrond_explorer_interface',
        'get_balances_alternatives': ['elrond_explorer_interface'],
        'get_txs': 'elrond_explorer_interface',
        'get_txs_alternatives': ['elrond_explorer_interface'],
        'txs_details': 'elrond_explorer_interface',
        'txs_details_alternatives': ['elrond_explorer_interface'],
        'get_blocks_addresses': 'elrond_explorer_interface',
        'get_blocks_addresses_alternatives': ['elrond_explorer_interface'],
        'block_head_apis': ['elrond_explorer_interface'],
    },
    'ENJ': {
        'get_balances': 'enjin_explorer_interface',
        'get_balances_alternatives': ['enjin_explorer_interface'],
        'get_txs': 'enjin_explorer_interface',
        'get_txs_alternatives': ['enjin_explorer_interface'],
        'txs_details': 'enjin_explorer_interface',
        'txs_details_alternatives': ['enjin_explorer_interface'],
        'get_blocks_addresses': 'enjin_explorer_interface',
        'get_blocks_addresses_alternatives': ['enjin_explorer_interface'],
        'block_head_apis': ['enjin_explorer_interface'],
    },
    'EOS': {
        'get_balances': 'eosrio',
        'get_balances_alternatives': ['eosrio', 'eos_explorer_interface'],
        'get_txs': 'eos_explorer_interface',
        'get_txs_alternatives': ['eos_explorer_interface'],
        'txs_details': 'eos_explorer_interface',
        'txs_details_alternatives': ['eos_explorer_interface'],
        'block_head_apis': ['eos_explorer_interface'],
    },
    'ETC': {
        'get_balances': 'etc_explorer_interface',
        'get_balances_alternatives': ['etc_blockbook', 'etc_blockbook2'],
        'get_txs': 'etc_blockbook2',
        'get_txs_alternatives': ['etc_blockbook', 'etc_blockbook2'],
        'txs_details': 'etc_explorer_interface',
        'txs_details_alternatives': ['etc_blockscout', 'etc_explorer_interface', 'etc_blockbook', 'etc_blockbook2'],
        'get_blocks_addresses': 'etc_blockbook2',
        'get_blocks_addresses_alternatives': ['etc_blockbook', 'etc_blockbook2'],
        'block_head_apis': ['etc_blockbook2', 'etc_explorer_interface'],
    },
    'ETH': {
        'get_balances': 'eth_explorer_interface',
        'get_balances_alternatives': ['eth_explorer_interface', 'eth_blockbook_metawire'],
        'get_txs': 'eth_explorer_interface',
        'get_txs_alternatives': ['eth_blockbook', 'eth_heatwallet_blockbook',
                                 'eth_heatwallet_blockbook2', 'eth_block_blockbook',
                                 'eth_binancechain_blockbook', 'eth_explorer_interface', 'eth_blockbook_metawire'],
        'txs_details': 'eth_explorer_interface',
        'txs_details_alternatives': ['eth_blockbook', 'eth_heatwallet_blockbook', 'eth_blockbook_metawire'
                                                                                  'eth_heatwallet_blockbook2',
                                     'eth_block_blockbook',
                                     'eth_binancechain_blockbook', 'eth_blockcypher',
                                     'eth_ethplorer', 'eth_explorer_interface'],
        'get_blocks_addresses': 'eth_explorer_interface',
        'get_blocks_addresses_alternatives': ['eth_blockbook', 'eth_heatwallet_blockbook', 'eth_explorer_interface',
                                              'eth_blockbook_metawire'],
        'block_head_apis': ['eth_explorer_interface', 'eth_heatwallet_blockbook', 'eth_blockbook',
                            'eth_blockbook_metawire'],
    },
    'FIL': {
        'get_balances': 'filecoin_explorer_interface',
        'get_balances_alternatives': ['filecoin_explorer_interface'],
        'get_txs': 'filecoin_explorer_interface',
        'get_txs_alternatives': ['filecoin_explorer_interface'],
        'txs_details': 'filecoin_explorer_interface',
        'txs_details_alternatives': ['filecoin_explorer_interface'],
        'get_blocks_addresses': 'filecoin_explorer_interface',
        'get_blocks_addresses_alternatives': ['filecoin_explorer_interface'],
        'block_head_apis': ['filecoin_explorer_interface'],
    },
    'FLOW': {
        'get_balances': 'flow_explorer_interface',
        'get_balances_alternatives': ['flow_explorer_interface'],
        'get_txs': 'flow_explorer_interface',
        'get_txs_alternatives': ['flow_explorer_interface'],
        'txs_details': 'flow_explorer_interface',
        'txs_details_alternatives': ['flow_explorer_interface'],
        'get_blocks_addresses': 'flow_explorer_interface',
        'get_blocks_addresses_alternatives': ['flow_explorer_interface'],
        'block_head_apis': ['flow_explorer_interface'],
    },
    'FLR': {
        'get_balances': 'flare_explorer_interface',
        'get_balances_alternatives': ['flare_explorer_interface'],
        'get_txs': 'flare_explorer_interface',
        'get_txs_alternatives': ['flare_explorer_interface'],
        'txs_details': 'flare_explorer_interface',
        'txs_details_alternatives': ['flare_explorer_interface'],
        'get_blocks_addresses': 'flare_explorer_interface',
        'get_blocks_addresses_alternatives': ['flare_explorer_interface'],
        'block_head_apis': ['flare_explorer_interface'],
    },
    'FTM': {
        'get_balances': 'ftm_explorer_interface',
        'get_balances_alternatives': ['ftm_explorer_interface'],
        'get_txs': 'ftm_explorer_interface',
        'get_txs_alternatives': ['ftm_explorer_interface'],
        'txs_details': 'ftm_explorer_interface',
        'txs_details_alternatives': ['ftm_explorer_interface'],
        'get_blocks_addresses': 'ftm_explorer_interface',
        'get_blocks_addresses_alternatives': ['ftm_explorer_interface'],
        'block_head_apis': ['ftm_explorer_interface'],
    },
    'HBAR': {
        'get_balances': 'hedera_explorer_interface',
        'get_balances_alternatives': ['hedera_explorer_interface'],
        'get_txs': 'hedera_explorer_interface',
        'get_txs_alternatives': ['hedera_explorer_interface'],
        'txs_details': 'hedera_explorer_interface',
        'txs_details_alternatives': ['hedera_explorer_interface'],
        'block_head_apis': ['hedera_explorer_interface'],
    },
    'LTC': {
        'get_balances': 'ltc_electrum',
        'get_balances_alternatives': ['ltc_explorer_interface', 'ltc_litecoinnet',
                                      'ltc_blockcypher', 'ltc_sochain', 'ltc_electrum'],
        'get_txs': 'ltc_explorer_interface',
        'get_txs_alternatives': ['ltc_explorer_interface'],
        'txs_details': 'ltc_explorer_interface',
        'txs_details_alternatives': ['ltc_blockcypher', 'ltc_sochain', 'ltc_explorer_interface'],
        'get_blocks_addresses': 'ltc_explorer_interface',
        'get_blocks_addresses_alternatives': ['ltc_explorer_interface'],
        'block_head_apis': ['ltc_explorer_interface'],
    },
    'MATIC': {
        'get_balances': 'polygon_explorer_interface',
        'get_balances_alternatives': ['polygon_explorer_interface'],
        'get_txs': 'polygon_explorer_interface',
        'get_txs_alternatives': ['polygon_explorer_interface'],
        'txs_details': 'polygon_explorer_interface',
        'txs_details_alternatives': ['polygon_explorer_interface'],
        'get_blocks_addresses': 'polygon_explorer_interface',
        'get_blocks_addresses_alternatives': ['polygon_explorer_interface'],
        'block_head_apis': ['polygon_explorer_interface'],
    },
    'NEAR': {
        'get_balances': 'near_explorer_interface',
        'get_balances_alternatives': ['near_explorer_interface'],
        'get_txs': 'near_explorer_interface',
        'get_txs_alternatives': ['near_explorer_interface'],
        'txs_details': 'near_explorer_interface',
        'txs_details_alternatives': ['near_explorer_interface'],
        'get_blocks_addresses': 'rpc-near-explorer-interface',
        'get_blocks_addresses_alternatives': ['near_explorer_interface', 'rpc-near-explorer-interface',
                                              'near_quicknode_explorer_interface'],
        'block_head_apis': ['rpc-near-explorer-interface', 'near_quicknode_explorer_interface'],
    },
    'ONE': {
        'get_balances': 'one_explorer_interface',
        'get_balances_alternatives': ['one_web3', 'one_covalent'],
        'get_txs': 'one_explorer_interface',
        'get_txs_alternatives': ['one_explorer_interface'],
        'txs_details': 'one_explorer_interface',
        'txs_details_alternatives': ['one_explorer_interface', 'one_ankr_rpc'],
        'get_blocks_addresses': 'one_explorer_interface',
        'get_blocks_addresses_alternatives': ['one_ankr_rpc', 'one_explorer_interface'],
        'block_head_apis': ['one_covalent', 'one_rpc', 'one_ankr_rpc'],
    },
    'PMN': {
        'get_balances': 'pmn_kuknos',
        'get_balances_alternatives': ['pmn_kuknos'],
        'get_txs': 'pmn_kuknos',
        'get_txs_alternatives': ['pmn_kuknos'],
        'txs_details': 'pmn_kuknos',
        'txs_details_alternatives': ['pmn_kuknos'],
        'block_head_apis': [''],
    },
    'SOL': {
        'get_balances': 'sol_explorer_interface',
        'get_balances_alternatives': ['sol_explorer_interface'],
        'get_txs': 'rpc_sol_explorer_interface',
        'get_txs_alternatives': ['sol_explorer_interface', 'rpc_sol_explorer_interface'],
        'txs_details': 'rpc_sol_explorer_interface',
        'txs_details_alternatives': ['sol_explorer_interface', 'rpc_sol_explorer_interface'],
        'get_blocks_addresses': 'rpc_sol_explorer_interface',
        'get_blocks_addresses_alternatives': ['rpc_sol_explorer_interface', 'sol_explorer_interface',
                                              'bitquery_sol_explorer_interface'],
        'block_head_apis': ['sol_explorer_interface', 'rpc_sol_explorer_interface'],
    },
    'SONIC': {
        'get_balances': 'sonic_explorer_interface',
        'get_balances_alternatives': ['sonic_explorer_interface'],
        'get_txs': 'sonic_explorer_interface',
        'get_txs_alternatives': ['sonic_explorer_interface'],
        'txs_details': 'sonic_explorer_interface',
        'txs_details_alternatives': ['sonic_explorer_interface', 'sonic_explorer_interface'],
        'get_blocks_addresses': 'sonic_explorer_interface',
        'get_blocks_addresses_alternatives': ['sonic_explorer_interface'],
        'block_head_apis': ['sonic_explorer_interface'],
    },
    'SUI': {
        'get_balances': 'rpc_sui_explorer_interface',
        'get_balances_alternatives': ['rpc_sui_explorer_interface'],
        'get_txs': 'rpc_sui_explorer_interface',
        'get_txs_alternatives': ['rpc_sui_explorer_interface'],
        'txs_details': 'rpc_sui_explorer_interface',
        'txs_details_alternatives': ['rpc_sui_explorer_interface'],
        'get_blocks_addresses': 'rpc_sui_explorer_interface',
        'get_blocks_addresses_alternatives': ['rpc_sui_explorer_interface'],
        'block_head_apis': ['rpc_sui_explorer_interface'],
    },
    'TON': {
        'get_balances': 'ton_explorer_interface',
        'get_balances_alternatives': ['ton_explorer_interface'],
        'get_txs': 'ton_explorer_interface',
        'get_txs_alternatives': ['ton_explorer_interface'],
        'txs_details': 'ton_explorer_interface',
        'txs_details_alternatives': ['ton_explorer_interface'],
        'get_blocks_addresses': 'ton_explorer_interface',
        'get_blocks_addresses_alternatives': ['ton_explorer_interface'],
        'block_head_apis': ['ton_explorer_interface'],
    },
    'XTZ': {
        'get_balances': 'xtz_explorer_interface',
        'get_balances_alternatives': ['xtz_explorer_interface'],
        'get_txs': 'xtz_explorer_interface',
        'get_txs_alternatives': ['xtz_explorer_interface'],
        'txs_details': 'xtz_explorer_interface',
        'txs_details_alternatives': ['xtz_explorer_interface'],
        'get_blocks_addresses': 'xtz_explorer_interface',
        'get_blocks_addresses_alternatives': ['xtz_explorer_interface'],
        'block_head_apis': ['xtz_explorer_interface'],
    },
    'TRX': {
        'get_balances': 'tron_explorer_interface',
        'get_balances_alternatives': ['tron_explorer_interface', 'trx_full_node', 'trx_tron_grid', 'trx_tronscan',
                                      'trx_blockbook'],
        'get_txs': 'trx_tron_grid',
        'get_txs_alternatives': ['tron_explorer_interface', 'trx_tron_grid', 'trx_tronscan'],
        'txs_details': 'tron_explorer_interface',
        'txs_details_alternatives': ['tron_explorer_interface', 'trx_tronscan', 'trx_blockbook'],
        'get_blocks_addresses': 'trx_full_node',
        'get_blocks_addresses_alternatives': ['tron_explorer_interface', 'trx_full_node', 'trx_blockbook'],
        'block_head_apis': ['tron_explorer_interface', 'trx_full_node', 'trx_tronscan'],
    },
    'XLM': {
        'get_balances': 'xlm_interface_explorer',
        'get_balances_alternatives': ['xlm_interface_explorer'],
        'get_txs': 'xlm_interface_explorer',
        'get_txs_alternatives': ['xlm_interface_explorer', 'xlm_expert'],
        'txs_details': 'xlm_interface_explorer',
        'txs_details_alternatives': ['xlm_interface_explorer'],
        'block_head_apis': ['xlm_interface_explorer'],
    },
    'XMR': {
        'get_balances': 'xmr_hot_wallet',
        'get_txs': 'xmr_hot_wallet',
        'txs_details': 'xmr_hot_wallet',
        'get_blocks_addresses': 'xmr_hot_wallet',
        'block_head_apis': ['xmr_hot_wallet'],
        'get_blocks_addresses_alternatives': ['xmr_explorer_interface'],
    },
    'XRP': {
        'get_balances': 'xrp_explorer_interface',
        'get_balances_alternatives': ['xrp_explorer_interface'],
        'get_txs': 'xrp_explorer_interface',
        'get_txs_alternatives': ['xrp_explorer_interface'],
        'txs_details': 'xrp_explorer_interface',
        'txs_details_alternatives': ['xrp_explorer_interface'],
        'block_head_apis': ['xrp_explorer_interface'],
    },
}

APIS_CONF.pop('SUI') # remove after QA completed on SUI

APIS_CLASSES = {
    'ada_explorer_interface': CardanoExplorerInterface,
    'algorand_explorer_interface': AlgorandExplorerInterface,
    'aptos_explorer_interface': AptosExplorerInterface,
    'arbitrum_explorer_interface': ArbitrumExplorerInterface,
    'atom_allthatnode': AtomAllthatnode,
    'atom_cosmos_node': CosmosNetworkNode,
    'atom_figment': FigmentNode,
    'atom_getblock': AtomGetblockNode,
    'atom_lavenderfive': LavenderFiveNode,
    'atom_pupmos': PupmosNode,
    'atom_scan_node': AtomscanNode,
    'atom_explorer_interface': AtomExplorerInterface,
    'avax_explorer_interface': AvalancheExplorerInterface,
    'base_explorer_interface': BaseExplorerInterface,
    'binance': BinanceAPI,
    'bnb_node': BinanceNodeAPI,
    'bnb_explorer_interface': BnbExplorerInterface,
    'bnb_mintscan': BnbMintscan,
    'bsc_explorer_interface': BscExplorerInterface,
    'bsc_bitquery': BscBitqueryAPI,
    'bsc_blockbook': BscBlockbookAPI,
    'bsc_nobitex_blockbook': BscNobitexBlockbookAPI,
    'bsc_klever_blockbook': BscKleverBlockbookAPI,
    'bsc_covalent': BSCCovalenthqAPI,
    'bsc_scan': BscScanAPI,
    'bsc_moralis': MoralisAPI,
    'btc_bitaps': BitapsAPI,
    'btc_chain': BtcAPI,
    'btc_cryptoid': CryptoidAPI,
    'btc_electrum': BtcElectrum,
    'btc_sochain': BitcoinSochainAPI,
    'btc_smartbit': SmartbitAPI,
    'btc_explorer_interface': BTCExplorerInterface,
    'bch_node': BchElectronNode,
    'bch_explorer_interface': BitcoinCashExplorerInterface,
    'bch_blockbook': BitcoinCashBlockbookAPI,
    'dydx_explorer_interface': DydxExplorerInterface,
    'doge_blockbook2': DogeBlockbookAPIv2,
    'doge_blockcypher': DogeBlockcypherAPI,
    'doge_chain': DogechainAPI,
    'doge_coinexplorer': CoinexplorerAPI,
    'doge_nownodes': DogeNowNodesAPI,
    'doge_sochain': DogeSochainAPI,
    'doge_blockchair': DogeBlockChairApi,
    'doge_explorer_interface': DogeExplorerInterface,
    'dot_figment': DotFigmentAPI,
    'dot_polkascan': PolkascanAPI,
    'dot_subscan': SubscanAPI,
    'dot_explorer_interface': DotExplorerInterface,
    'elrond_explorer_interface': ElrondExplorerInterface,
    'enjin_explorer_interface': EnjinExplorerInterface,
    'eosrio': EosrioAPI,
    'eos_explorer_interface': EosExplorerInterface,
    'etc_blockbook': EtcBlockBookAPI,
    'etc_blockbook2': EthereumClassicBlockbookAPI,
    'etc_blockscout': ETCBlockscoutAPI,
    'etc_explorer_interface': EtcExplorerInterface,
    'eth_blockbook': EthereumBlockbookAPI,
    'eth_block_blockbook': EthereumEthBlockBlockbookAPI,
    'eth_blockcypher': EthBlockcypherAPI,
    'eth_covalent': ETHCovalenthqAPI,
    'eth_explorer_interface': EthExplorerInterface,
    'eth_ethplorer': EthplorerAPI,
    'eth_heatwallet_blockbook': EthereumHeatWallet1BlockbookAPI,
    'eth_heatwallet_blockbook2': EthereumHeatWallet2BlockbookAPI,
    'eth_blockbook_metawire': EthereumEthMetaWireBlockBookAPI,
    'eth_web3': ETHWeb3,
    'filecoin_explorer_interface': FilecoinExplorerInterface,
    'flow_explorer_interface': FlowExplorerInterface,
    'flare_explorer_interface': FlareExplorerInterface,
    'ftm_covalent': FantomCovalenthqAPI,
    'ftm_graphql': FantomGraphQlAPI,
    'ftm_scan': FtmScanAPI,
    'ftm_web3': FtmWeb3API,
    'ftm_explorer_interface': FTMExplorerInterface,
    'hedera_explorer_interface': HederaExplorerInterface,
    'ltc_atomicwallet_blockbook': LitecoinAtomicWalletBlockbookAPI,
    'ltc_binance_blockbook': LitecoinBinanceBlockbookAPI,
    'ltc_blockbook': LitecoinBlockbookAPI,
    'ltc_blockcypher': LtcBlockcypherAPI,
    'ltc_electrum': ElectrumAPI,
    'ltc_explorer_interface': LTCExplorerInterface,
    'ltc_heatwallet_blockbook': LitecoinHeatWalletBlockbookAPI,
    'ltc_sochain': LitecoinSochainAPI,
    'polygon_explorer_interface': PolygonExplorerInterface,
    'near_blocks': NearBlocksAPI,
    'near_figment': NearFigmentEnrichedAPI,
    'near_indexer': NearIndexerAPI,
    'near_scan': NearScan,
    'near_quicknode_explorer_interface': QuickNodeNearExplorerInterface,
    'near_explorer_interface': NearExplorerInterface,
    'official_near_explorer_interface': OfficialNearExplorerInterface,
    'rpc-near-explorer-interface': RpcNearExplorerInterface,
    'one_covalent': ONECovalenthqAPI,
    'one_rpc': HarmonyRPC,
    'one_ankr_rpc': AnkrHarmonyRpc,
    'one_web3': OneWeb3API,
    'one_explorer_interface': OneExplorerInterface,
    'pmn_kuknos': KuknosHorizonAPI,
    'sol_explorer_interface': SolExplorerInterface,
    'sonic_explorer_interface': SonicExplorerInterface,
    # 'rpc_sui_explorer_interface': RpcSuiExplorerInterface, # noqa: ERA001
    'rpc_sol_explorer_interface': RpcSolExplorerInterface,
    'bitquery_sol_explorer_interface': BitqueryExplorerInterface,
    'ton_explorer_interface': TonExplorerInterface,
    'tron_explorer_interface': TronExplorerInterface,
    'xtz_explorer_interface': TezosExplorerInterface,
    'trx_blockbook': TrxBlockbookAPI,
    'trx_full_node': TronFullNodeAPI,
    'trx_solidity': TronSolidityNodeAPI,
    'trx_tron_grid': TrongridAPI,
    'trx_tronscan': TronscanAPI,
    'xlm_expert': XlmExpertAPI,
    'xlm_interface_explorer': StellarExplorerInterface,
    'xmr_hot_wallet': MoneroAPI,
    'xmr_explorer_interface': XmrExplorerInterface,
    'xrp_api': RippleAPI,
    'xrp_rpc': RippleRpcAPI,
    'xrp_explorer_interface': RippleExplorerInterface,
}

STAKING_EXPLORER_INTERFACE: Dict[str, ExplorerInterface] = {
    'bsc': BscExplorerInterface(),
}

STAKING_EXPLORER_INTERFACE: Dict[str, ExplorerInterface] = {
    'bsc': BscExplorerInterface(),
}
