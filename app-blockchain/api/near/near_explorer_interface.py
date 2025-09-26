import concurrent.futures
import sys
import time
import traceback
from typing import List, Optional, Tuple

from exchange.blockchain.api.general.dtos import TransferTx
from exchange.blockchain.api.general.explorer_interface import ExplorerInterface
from exchange.blockchain.api.near.near_1rpc import Near1RpcAPI, NearTatumApi
from exchange.blockchain.api.near.near_ankr_rpc import NearAnkrRpcAPI
from exchange.blockchain.api.near.near_getblocks import NearGetBlocksApi
from exchange.blockchain.api.near.near_rpc import NearRpcAPI
from exchange.blockchain.api.near.nearblocks_near import NearBlocksApi
from exchange.blockchain.api.near.official_near import NearOfficialAPI

from .near_quicknode import NearDrpcApi, NearQuickNodeApi
from .pickespeak import NearPikeApi


class NearExplorerInterface(ExplorerInterface):
    balance_apis = [NearBlocksApi]
    tx_details_apis = [Near1RpcAPI, NearBlocksApi, NearTatumApi]
    address_txs_apis = [NearBlocksApi, NearPikeApi]
    # if you want to use NearOfficialAPI for block_txs_apis, you must
    # set APIS_CONF['NEAR']['get_blocks_addresses'] on 'official_near_explorer_interface'
    block_txs_apis = []
    block_head_apis = []
    symbol = 'NEAR'


class OfficialNearExplorerInterface(NearExplorerInterface):
    instance = None
    block_txs_apis = [NearOfficialAPI]
    block_head_apis = [NearOfficialAPI]

    @classmethod
    def get_block_in_thread(cls, api: NearOfficialAPI, block_height: int) -> \
            Tuple[Optional[int], Optional[List[TransferTx]]]:
        try:
            block_hash_api_response = api.get_block_hash(block_height)
            block_hash, txs_count = api.parser.parse_block_hash_response(block_hash_api_response)
            block_txs_api_response = api.get_block_txs(block_hash, txs_count)
            block_txs = api.parser.parse_block_txs_response(block_txs_api_response)
            if block_txs is None or len(block_txs) == 0:
                return block_height, []
            return block_height, block_txs
        except Exception:
            traceback.print_exception(*sys.exc_info())
            return None, None


class RpcNearExplorerInterface(NearExplorerInterface):
    instance = None
    block_txs_apis = [NearRpcAPI, NearAnkrRpcAPI, NearGetBlocksApi]
    block_head_apis = [NearRpcAPI, NearGetBlocksApi]

    @classmethod
    def get_block_in_thread(cls,
                            api: NearGetBlocksApi,
                            block_height: int) -> Tuple[Optional[int], Optional[List[TransferTx]]]:
        block_txs = []
        try:
            futures = []
            number_of_workers = 6
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=number_of_workers)
            for shard_id in range(number_of_workers):
                future = executor.submit(api.get_block_txs, block_height, shard_id)
                futures.append(future)
            for future in concurrent.futures.as_completed(futures):
                block_tx_api_response = future.result()
                block_tx = api.parser.parse_block_txs_response(block_tx_api_response)
                if not block_tx:
                    continue
                block_txs.extend(block_tx)
            return block_height, block_txs
        except Exception:
            traceback.print_exception(*sys.exc_info())
            return None, None


class QuickNodeNearExplorerInterface(NearExplorerInterface):
    block_txs_apis = [NearQuickNodeApi, NearDrpcApi]
    block_head_apis = [NearQuickNodeApi, NearDrpcApi]

    @classmethod
    def get_batch_blocks(cls, api: NearQuickNodeApi, from_block: int, to_block: int) -> list:
        import concurrent.futures
        from threading import Event

        blocks_txs = []
        block_step = api.block_step  # Number of blocks per request
        shard_step = api.shard_step  # Number of shards per request
        max_shard = 5
        max_retries = 5

        # Event to signal termination
        stop_event = Event()

        def process_block_shard_range(start_block: int,
                                      end_block: int,
                                      start_shard: int,
                                      end_shard: int) -> Optional[List[TransferTx]]:
            retry_count = 0
            while retry_count < max_retries:
                if stop_event.is_set():
                    return None  # Stop if another task has signaled termination
                try:
                    # Fetch transactions for the block and shard range
                    batch_response = api.get_batch_block_txs(start_block, end_block, start_shard, end_shard)
                    return api.parser.parse_batch_block_txs_response(batch_response)
                except Exception:
                    retry_count += 1
                    time.sleep(1)  # Optional: delay before retrying
            # Signal termination if retries are exhausted
            stop_event.set()
            return None

        tasks = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=api.number_of_workers) as executor:
            # Loop through the range of blocks in steps of block_step
            for start_block in range(from_block, to_block + 1, block_step):
                end_block = min(start_block + block_step - 1, to_block)

                # Loop through the range of shards in steps of shard_step
                for start_shard in range(0, max_shard, shard_step):
                    end_shard = min(start_shard + shard_step - 1, max_shard)

                    # Submit the task to the executor
                    tasks.append(
                        executor.submit(process_block_shard_range, start_block, end_block, start_shard, end_shard)
                    )

            # Collect results as tasks complete
            for future in concurrent.futures.as_completed(tasks):
                if stop_event.is_set():
                    return None  # Abort the operation if a failure is signaled
                result = future.result()
                if result is not None:
                    blocks_txs += result

        return blocks_txs
