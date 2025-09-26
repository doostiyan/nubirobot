import math
from typing import List, Optional

from django.conf import settings

from exchange.blockchain.api.general.dtos import TransferTx
from exchange.blockchain.api.general.explorer_interface import ExplorerInterface
from exchange.blockchain.api.general.general import GeneralApi
from exchange.blockchain.api.sol.bitquery_sol import BitQuerySolApi
from exchange.blockchain.api.sol.getblock_sol import GetBlockSolApi
from exchange.blockchain.api.sol.rpc_sol import AlchemyRPC, AnkrRPC, MainRPC, QuickNodeRPC, RpcSolAPI
from exchange.blockchain.api.sol.solanabeach_sol import SolanaBeachSolApi
from exchange.blockchain.explorer_common import BlockchainExplorer

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies
from exchange.blockchain.utils import APIError

# if you want to use RPC APIs, you must set APIS_CONF on 'rpc_sol_explorer_interface'
# else you want to use Bitquery you must set APIS_CONF on 'bitquery_sol_explorer_interface'

class SolExplorerInterface(ExplorerInterface):
    instance = None
    balance_apis = [GetBlockSolApi, SolanaBeachSolApi]
    tx_details_apis = [SolanaBeachSolApi]
    address_txs_apis = [SolanaBeachSolApi]
    block_txs_apis = [BitQuerySolApi, GetBlockSolApi]
    block_head_apis = [SolanaBeachSolApi]
    symbol = 'SOL'
    USE_AGGREGATION_SERVICE = True


class RpcSolExplorerInterface(SolExplorerInterface):
    instance = None
    balance_apis = [MainRPC, QuickNodeRPC, AlchemyRPC]
    tx_details_apis = [MainRPC, AlchemyRPC, QuickNodeRPC, AnkrRPC]
    address_txs_apis = [QuickNodeRPC, AlchemyRPC, MainRPC, AnkrRPC]
    block_txs_apis = [QuickNodeRPC, AlchemyRPC, MainRPC, AnkrRPC]
    block_head_apis = [QuickNodeRPC, AlchemyRPC, QuickNodeRPC, AnkrRPC]
    token_tx_details_apis = [QuickNodeRPC, MainRPC, AnkrRPC]
    token_txs_apis = [QuickNodeRPC, MainRPC, AnkrRPC]
    USE_AGGREGATION_SERVICE = True

    @classmethod
    def get_batch_blocks(cls, api: RpcSolAPI, from_block: int, to_block: int) -> list:
        batch_response = api.get_batch_block_txs(from_block, to_block)
        request_numbers = int(math.ceil(len(batch_response.get('result')) / api.max_block_in_single_request))
        blocks_txs = []

        import concurrent.futures
        futures = []
        for i in range(request_numbers):
            future = cls.threadpool.submit(api.get_blocks_txs, i, batch_response)
            futures.append(future)
        for future in concurrent.futures.as_completed(futures):
            # Wait for each task to complete
            block_txs_api_response = future.result()
            block_txs = api.parser.parse_batch_block_txs_response(
                block_txs_api_response
            )
            blocks_txs += block_txs
        return blocks_txs

    def get_txs(self, address: str, tx_direction_filter: Optional[str] = None) -> List[dict]:
        address_txs_api = self.address_txs_apis[0].get_instance()
        block_head = None
        if address_txs_api.need_block_head_for_confirmation:
            block_head_api_response = address_txs_api.get_block_head()
            block_head = address_txs_api.parser.parse_block_head_response(block_head_api_response)
        txs_hash_response = address_txs_api.get_txs_hash(address)
        txs_hash = address_txs_api.parser.parse_txs_hash_response(txs_hash_response)
        address_txs_api_response = address_txs_api.get_address_txs(txs_hash)
        retry_request_limit = 5
        retry_request_count = 0
        final_address_txs_response = []
        while True:
            if retry_request_count >= retry_request_limit:
                for i in range(len(address_txs_api_response)):
                    if not address_txs_api_response[i].get('error'):
                        final_address_txs_response.append(address_txs_api_response[i])
                address_txs_api_response = final_address_txs_response
                break
            index_of_txs = []
            # Collect indices where errors are present in the response
            for i in range(len(address_txs_api_response)):
                if address_txs_api_response[i].get('error'):
                    index_of_txs.append(i)

            # Break the loop if no errors are found
            if not index_of_txs:
                break

            # Retry fetching only the failed transactions
            txs_hash_failed = [txs_hash[i] for i in index_of_txs]
            retried_txs_api_response = address_txs_api.get_address_txs(txs_hash_failed)
            retry_request_count += 1

            # Update the original response with the retried results
            for idx, retry_response in zip(index_of_txs, retried_txs_api_response):
                address_txs_api_response[idx] = retry_response

        transfers = address_txs_api.parser.parse_address_txs_response(address, address_txs_api_response, block_head)

        if tx_direction_filter == 'incoming':
            transfers = [item for item in transfers if item.to_address.casefold() == address.casefold()]
        elif tx_direction_filter == 'outgoing':
            transfers = [item for item in transfers if item.from_address.casefold() == address.casefold()]

        return self.convert_transfers2list_of_address_txs_dict(address, transfers, address_txs_api.parser.currency)

    def get_token_txs(self,
                      address: str,
                      contract_info: dict,
                      direction: str = '',
                      start_date: Optional[int] = None,  # noqa: ARG002
                      end_date: Optional[int] = None) -> List[dict]:  # noqa: ARG002
        token_txs_api = self.get_provider('token_txs', self.token_txs_apis)
        block_head = None
        if token_txs_api.need_block_head_for_confirmation:
            block_head_api_response = token_txs_api.get_block_head()
            block_head = token_txs_api.parser.parse_block_head_response(
                block_head_api_response
            )
        currency_code = getattr(Currencies, contract_info.get('symbol').lower())
        ata = BlockchainExplorer.get_wallet_ata(address, currency_code)
        token_txs_hash_response = token_txs_api.get_txs_hash(ata)
        txs_hash = token_txs_api.parser.parse_txs_hash_response(
            token_txs_hash_response,
        )

        token_txs_api_response = token_txs_api.get_token_txs(txs_hash, contract_info)
        transfers = token_txs_api.parser.parse_token_txs_response(
            address, token_txs_api_response, block_head, contract_info, direction
        )

        if direction == 'incoming':
            transfers = [item for item in transfers if item.to_address.casefold() == address.casefold()]
        elif direction == 'outgoing':
            transfers = [item for item in transfers if item.from_address.casefold() == address.casefold()]

        if token_txs_api.NEED_TOKEN_TRANSACTION_RECEIPT:
            token_txs_receipt_api_response = token_txs_api.get_token_txs_receipt(
                transfers
            )
            transfers = token_txs_api.parser.parse_token_txs_receipt(
                token_txs_receipt_api_response, contract_info, block_head
            )

        return self.convert_transfers2list_of_address_txs_dict(
            address,
            transfers,
            getattr(Currencies, contract_info.get('symbol').lower()),
        )


class BitqueryExplorerInterface(SolExplorerInterface):
    instance = None
    block_txs_apis = [BitQuerySolApi]
    block_head_apis = [BitQuerySolApi]

    @classmethod
    def get_batch_blocks(cls, api: GeneralApi, from_block: int, to_block: int) -> List[TransferTx]:
        response = api.get_batch_block_txs(from_block, to_block)

        if response.get('errors'):
            if 'Limit for result exceeded' in response.get('errors')[0].get('message'):
                api.GET_BLOCK_ADDRESSES_MAX_NUM = int((to_block - from_block + 1) / 2)
                if not api.END_BLOCK_RANGE_WITH_PROBLEM:
                    api.END_BLOCK_RANGE_WITH_PROBLEM = to_block
                return None
            raise APIError(f'Get block API returns error:{response.get("errors")[0].get("message")}')

        if api.END_BLOCK_RANGE_WITH_PROBLEM and from_block > api.END_BLOCK_RANGE_WITH_PROBLEM:
            api.END_BLOCK_RANGE_WITH_PROBLEM = 0
            api.GET_BLOCK_ADDRESSES_MAX_NUM = 300

        return api.parser.parse_batch_block_txs_response(response)
