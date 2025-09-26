import json

from exchange.blockchain.api.general.general import GeneralApi


class JSONRPCClientMixin(GeneralApi):
    need_transaction_receipt = True

    @classmethod
    def get_block_head_body(cls) -> str:
        return json.dumps({
            'jsonrpc': '2.0',
            'method': 'eth_blockNumber',
            'params': [],
            'id': 1,
        })

    @classmethod
    def get_block_txs_body(cls, block_height: str) -> str:
        return json.dumps({
            'jsonrpc': '2.0',
            'method': 'eth_getBlockByNumber',
            'params': [
                block_height,
                True,
            ],
            'id': 1,
        })

    @classmethod
    def get_tx_receipt_body(cls, tx_hash: str) -> str:
        return json.dumps({
            'jsonrpc': '2.0',
            'method': 'eth_getTransactionReceipt',
            'params': [tx_hash],
            'id': 1,
        })

    @classmethod
    def get_tx_details_body(cls, tx_hash: str) -> str:
        return json.dumps(
            {
                'jsonrpc': '2.0',
                'method': 'eth_getTransactionByHash',
                'params': [tx_hash],
                'id': 1
            }
        )
