import sys
import traceback
from typing import Dict, List, Optional, Tuple, Union

from django.conf import settings

from exchange.blockchain.api.filecoin.filecoin_bitquery import FilecoinBitqueryApi
from exchange.blockchain.api.filecoin.filecoin_filfox import FilecoinFilfoxApi
from exchange.blockchain.api.filecoin.filecoin_filscan import FilecoinFilscanApi
from exchange.blockchain.api.filecoin.filecoin_filscan_rpc import FilecoinFilscanRpcApi
from exchange.blockchain.api.filecoin.filecoin_filscout import FilecoinFilscoutApi
from exchange.blockchain.api.filecoin.filecoin_glif import FilecoinGlifApi, FilecoinGlifNodeAPI
from exchange.blockchain.api.general.dtos import TransferTx
from exchange.blockchain.api.general.explorer_interface import ExplorerInterface
from exchange.blockchain.api.general.general import GeneralApi

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies


class FilecoinExplorerInterface(ExplorerInterface):
    balance_apis = [FilecoinGlifApi, FilecoinFilfoxApi, FilecoinFilscanApi, FilecoinBitqueryApi, FilecoinFilscanRpcApi,
                    FilecoinFilscoutApi]
    tx_details_apis = [FilecoinFilscanApi, FilecoinBitqueryApi, FilecoinFilfoxApi, FilecoinFilscanRpcApi
        , FilecoinGlifNodeAPI, FilecoinFilscoutApi]
    block_txs_apis = [FilecoinFilfoxApi, FilecoinBitqueryApi, FilecoinFilscanApi, FilecoinFilscoutApi]
    address_txs_apis = [FilecoinFilfoxApi, FilecoinFilscanApi, FilecoinFilscanRpcApi, FilecoinFilscoutApi]
    block_head_apis = [FilecoinFilfoxApi, FilecoinFilscanApi, FilecoinBitqueryApi, FilecoinGlifNodeAPI,
                       FilecoinFilscoutApi]
    symbol = 'FIL'
    GET_TXS_MAX_RETIES = 6

    def get_txs(self, address: str, tx_direction_filter: Optional[str] = None) -> List[Dict[int, Union[List, Dict]]]:
        request_counter = 0
        get_txs = [{Currencies.fil: []}]
        while request_counter < self.GET_TXS_MAX_RETIES:
            try:
                request_counter += 1
                get_txs = super().get_txs(address, tx_direction_filter)
                break
            except Exception:
                if request_counter >= self.GET_TXS_MAX_RETIES:
                    return [{Currencies.fil: {}}]
                self.address_txs_apis[0], self.address_txs_apis[1] = self.address_txs_apis[1], \
                    self.address_txs_apis[0]
                continue
        return get_txs

    @classmethod
    def get_block_in_thread(cls,
                            api: GeneralApi,
                            block_height: int) -> Tuple[Optional[int], Optional[List[TransferTx]]]:
        block_txs = []
        try:
            tipset_blocks_response = api.get_tipset_blocks_hash(block_height)
            block_hashes = api.parser.parse_tipset_blocks(tipset_blocks_response) or []
            for block_hash in block_hashes:
                block_tx_api_response = api.get_block_txs(block_hash)
                block_tx = api.parser.parse_block_txs_response(block_tx_api_response, block_height)
                if not block_tx:
                    continue
                block_txs.append(block_tx)
            block_txs = [item for sublist in block_txs for item in sublist]
            block_txs_duplicates_removed_list = []
            for obj in block_txs:
                if obj not in block_txs_duplicates_removed_list:
                    block_txs_duplicates_removed_list.append(obj)
            if block_txs_duplicates_removed_list is None or len(block_txs) == 0:
                return block_height, []
            return block_height, block_txs_duplicates_removed_list
        except Exception:
            traceback.print_exception(*sys.exc_info())
            return None, None
