import concurrent.futures
from typing import Optional

from exchange.blockchain.api.general.explorer_interface import ExplorerInterface
from exchange.blockchain.api.general.general import GeneralApi
from exchange.blockchain.api.sui.sui_blastapi import BlastApiSuiApi


class RpcSuiExplorerInterface(ExplorerInterface):
    tx_details_apis = [BlastApiSuiApi]
    address_txs_apis = [BlastApiSuiApi]
    block_txs_apis = [BlastApiSuiApi]
    block_head_apis = [BlastApiSuiApi]
    network = 'SUI'

    @classmethod
    def get_block_in_thread(cls, api: GeneralApi, block_height: int) -> Optional[tuple]:
        block_txs_api_response = api.get_block_txs(block_height)
        cls.check_blocks_raw_response(api, block_txs_api_response)
        if api.parser.validator.validate_block_txs_response(response=block_txs_api_response):
            tx_hashes = block_txs_api_response.get('result').get('data')[0].get('transactions')

            chunk_size = 50
            tx_batches = [tx_hashes[i:i + chunk_size] for i in range(0, len(tx_hashes), chunk_size)]

            block_txs = []
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future_to_batch = {executor.submit(api.get_tx_details_batch, batch): batch for batch in tx_batches}

                for future in concurrent.futures.as_completed(future_to_batch):
                    receipts = future.result()
                    if tx_detail := api.parser.parse_batch_tx_details_response(batch_tx_details_response=receipts,
                                                                               block_head=block_height):
                        block_txs.extend(tx_detail)

            return block_height, block_txs

        return None
