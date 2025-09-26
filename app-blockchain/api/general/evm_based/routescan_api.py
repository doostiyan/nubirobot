from typing import Any, Optional

from exchange.blockchain.api.commons.blockscan import BlockScanResponseParser, BlockScanResponseValidator
from exchange.blockchain.api.general.general import GeneralApi


class RoutescanResponseValidator(BlockScanResponseValidator):

    @classmethod
    def _validate_input_data(cls, input_data: str) -> bool:
        if not cls._is_valid_native_currency_input_address(input_data=input_data):
            return False

        return True


class RoutescanResponseParser(BlockScanResponseParser):
    validator = RoutescanResponseValidator


class RoutescanApi(GeneralApi):
    parser = RoutescanResponseParser
    _base_url: str = 'https://api.routescan.io'
    chain_id: Optional[int] = None
    need_transaction_receipt = True
    supported_requests: dict = {
        'get_block_head': '/v2/network/mainnet/evm/{chain_id}/etherscan/api?module=proxy&action=eth_blockNumber'
                          '&apikey={apikey}',
        'get_block_txs': '/v2/network/mainnet/evm/{chain_id}/etherscan/api?module=proxy&action=eth_getBlockByNumber'
                         '&tag={height}&boolean=true&apikey={apikey}',
        'get_tx_details': '/v2/network/mainnet/evm/{chain_id}/etherscan/api?module=proxy'
                          '&action=eth_getTransactionByHash&txhash={tx_hash}&apikey={apikey}',
        'get_tx_receipt': '/v2/network/mainnet/evm/{chain_id}/etherscan/api?module=proxy'
                          '&action=eth_getTransactionReceipt&txhash={tx_hash}&apikey={apikey}',
        'get_address_txs': '/v2/network/mainnet/evm/{chain_id}/etherscan/api?module=account&action=txlist'
                           '&address={address}&page=1&offset=50&sort=desc&apikey={apikey}',
    }

    @classmethod
    def get_block_head(cls) -> any:
        return cls.request(
            request_method='get_block_head',
            body=cls.get_block_head_body(),
            headers=cls.get_headers(),
            apikey=cls.get_api_key(),
            chain_id=cls.chain_id,
            timeout=cls.timeout,
        )

    @classmethod
    def get_block_txs(cls, block_height: int) -> any:
        return cls.request(
            request_method='get_block_txs',
            body=cls.get_block_txs_body(block_height),
            headers=cls.get_headers(),
            height=hex(block_height),
            apikey=cls.get_api_key(),
            chain_id=cls.chain_id,
            timeout=60,
        )

    @classmethod
    def get_tx_receipt(cls, tx_hash: str) -> any:
        return cls.request(
            request_method='get_tx_receipt',
            body=cls.get_tx_receipt_body(tx_hash),
            headers=cls.get_headers(),
            tx_hash=tx_hash,
            apikey=cls.get_api_key(),
            chain_id=cls.chain_id,
        )

    @classmethod
    def get_tx_details(cls, tx_hash: str) -> any:
        return cls.request(
            request_method='get_tx_details',
            body=cls.get_tx_details_body(tx_hash),
            headers=cls.get_headers(),
            tx_hash=tx_hash,
            apikey=cls.get_api_key(),
            chain_id=cls.chain_id,
            timeout=cls.timeout,
        )

    @classmethod
    def get_address_txs(cls, address: str, **kwargs: Any) -> any:
        return cls.request(
            request_method='get_address_txs',
            body=cls.get_address_txs_body(address),
            headers=cls.get_headers(),
            address=address,
            apikey=cls.get_api_key(),
            chain_id=cls.chain_id,
            timeout=cls.timeout,
        )
