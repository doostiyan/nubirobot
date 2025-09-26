from decimal import Decimal
from typing import Dict

from exchange.blockchain.api.general.explorer_interface import ExplorerInterface
from exchange.blockchain.api.general.general import GeneralApi
from exchange.blockchain.api.trx.new_trongrid import TrongridTronApi
from exchange.blockchain.api.trx.new_tronscan import TronscanTronApi
from exchange.blockchain.api.trx.tron_contract_balance_checker import TronContractBalanceCheckerV2Api
from exchange.blockchain.api.trx.tron_full_node_new import TronFullNodeAPI
from exchange.blockchain.api.trx.tron_tatum import TatumTronApi
from exchange.blockchain.metrics import metric_incr


class TronExplorerInterface(ExplorerInterface):
    balance_apis = [TronContractBalanceCheckerV2Api, TrongridTronApi, TronFullNodeAPI]
    token_balance_apis = [TrongridTronApi, TronFullNodeAPI]
    block_txs_apis = [TronFullNodeAPI]
    block_head_apis = [TrongridTronApi, TronFullNodeAPI]
    tx_details_apis = [TronscanTronApi, TatumTronApi]
    token_tx_details_apis = [TronscanTronApi, TatumTronApi]
    address_txs_apis = [TrongridTronApi, TronscanTronApi]
    token_txs_apis = [TrongridTronApi, TronscanTronApi]
    symbol = 'TRX'
    min_valid_tx_amount = Decimal('0.001')

    @classmethod
    def check_blocks_raw_response(cls, api: GeneralApi, block_txs_api_response: Dict[str, any]) -> None:
        if not block_txs_api_response or not isinstance(block_txs_api_response, dict):
            return
        if not block_txs_api_response.get('block') or not isinstance(block_txs_api_response.get('block'), list):
            return
        for block in block_txs_api_response.get('block'):
            validate_block_txs_api_response = api.parser.validator.validate_block_txs_raw_response(block)
            if not validate_block_txs_api_response:
                metric_incr('missed_block_txs_by_network_provider', labels=[api.get_name(), api.parser.symbol])
