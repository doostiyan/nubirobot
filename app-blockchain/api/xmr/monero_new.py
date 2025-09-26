from decimal import Decimal
from typing import Any, Dict, List, Optional

from exchange.base.connections import MoneroExplorerClient
from exchange.base.models import Currencies
from exchange.blockchain.api.general.dtos import Balance, TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.utils import BlockchainUtilsMixin, v2_parse_utc_timestamp


class MoneroValidator(ResponseValidator):
    min_valid_tx_amount = Decimal('0.001')
    precision = 12

    @classmethod
    def validate_general_response(cls, response: Dict[str, Any]) -> bool:
        if response.get('status') == 'failed':
            return False
        return True

    @classmethod
    def validate_transaction(cls, transaction: Dict[str, Any]) -> bool:
        if Decimal(transaction.get('amount')) < cls.min_valid_tx_amount:
            return False
        return True

    @classmethod
    def validate_tx_details_transaction(cls, transaction: Dict[str, Any]) -> bool:
        if BlockchainUtilsMixin.from_unit(transaction.get('amount'), precision=cls.precision) < cls.min_valid_tx_amount:
            return False
        if not transaction.get('status'):
            return False
        return True

    @classmethod
    def validate_block_txs_response(cls, block_txs_response: List[Dict[str, Any]]) -> bool:
        return all(response.get('status') != 'failed' for response in block_txs_response)


class MoneroParser(ResponseParser):
    validator = MoneroValidator
    symbol = 'XMR'
    currency = Currencies.xmr
    precision = 12

    @classmethod
    def parse_block_head_response(cls, block_head_response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if cls.validator.validate_general_response(block_head_response):
            return block_head_response.get('block_head')
        return None

    @classmethod
    def parse_balance_response(cls, balance_response: Dict[str, Any]) -> Balance:
        if not cls.validator.validate_general_response(balance_response):
            return Balance(
                balance=Decimal('0'),
                unconfirmed_balance=Decimal('0')
            )
        return Balance(
            balance=Decimal(balance_response.get('confirmed_balance')),
            unconfirmed_balance=Decimal(balance_response.get('unconfirmed_balance')),
            symbol=cls.symbol
        )

    @classmethod
    def parse_address_txs_response(
        cls,
        address: str,
        address_txs_response: Dict[str, Any],
        __: int,
    ) -> List[TransferTx]:
        _ = address
        address_txs: List[TransferTx] = []
        if cls.validator.validate_general_response(address_txs_response):
            for tx in address_txs_response.get('transfers'):
                if cls.validator.validate_transaction(tx):
                    transfer = TransferTx(
                        tx_hash=tx.get('tx_hash'),
                        from_address='',
                        to_address=tx.get('destination'),
                        value=Decimal(tx.get('amount')),
                        block_height=tx.get('height'),
                        confirmations=tx.get('confirmation'),
                        success=True,
                        symbol=cls.symbol,
                        date=v2_parse_utc_timestamp(tx.get('timestamp')),
                        tx_fee=Decimal(tx.get('fee'))
                    )
                    address_txs.append(transfer)

        return address_txs

    @classmethod
    def parse_tx_details_response(
        cls,
        tx_details_response: Dict[str, Any],
        __: int,
    ) -> List[TransferTx]:
        transfers: List[TransferTx] = []
        if cls.validator.validate_general_response(tx_details_response):
            for tx in tx_details_response.get('transfers'):
                if cls.validator.validate_tx_details_transaction(tx):
                    transfer = TransferTx(
                        tx_hash=tx.get('tx_hash'),
                        from_address='',
                        to_address=tx.get('destination'),
                        value=BlockchainUtilsMixin.from_unit(tx.get('amount'),
                                                         precision=cls.precision),
                        block_height=tx.get('height'),
                        confirmations=tx.get('confirmation'),
                        success=True,
                        symbol=cls.symbol,
                        date=v2_parse_utc_timestamp(tx.get('timestamp')),
                        tx_fee=BlockchainUtilsMixin.from_unit(tx.get('fee'), precision=cls.precision)
                    )
                    transfers.append(transfer)

        return transfers

    @classmethod
    def parse_batch_block_txs_response(cls, batch_block_txs_response: List[Dict[str, Any]]) -> List[TransferTx]:
        block_txs_list: List[TransferTx] = []
        if cls.validator.validate_block_txs_response(batch_block_txs_response):
            for blocks in batch_block_txs_response:
                for tx in blocks.get('transfers'):
                    transfer = TransferTx(
                        tx_hash=tx.get('tx_hash'),
                        from_address=tx.get('sender'),
                        to_address=tx.get('destination'),
                        value=Decimal(tx.get('amount')),
                        block_height=tx.get('height'),
                        confirmations=tx.get('confirmation'),
                        success=True,
                        symbol=cls.symbol,
                        date=v2_parse_utc_timestamp(tx.get('timestamp')),
                        tx_fee=Decimal(tx.get('fee'))
                    )
                    block_txs_list.append(transfer)

        return block_txs_list


class MoneroAPI(GeneralApi):
    parser = MoneroParser
    _base_url = ''
    symbol = 'XMR'
    cache_key = 'xmr'
    USE_PROXY = False
    SUPPORT_BATCH_GET_BLOCKS = True
    block_height_offset = 5

    @classmethod
    def get_block_head(cls) -> Dict[str, Any]:
        hot_wallet = MoneroExplorerClient.get_client()
        return hot_wallet.request(
            method='get_block_head',
            params={
                'password': hot_wallet.password,
            },
            rpc_id='curltext',
        )

    @classmethod
    def get_balance(cls, address: str) -> Dict[str, Any]:
        hot_wallet = MoneroExplorerClient.get_client()
        return hot_wallet.request(
            method='get_balance',
            params={
                'address': address,
                'password': hot_wallet.password,
            },
            rpc_id='curltext',
        )

    @classmethod
    def get_address_txs(cls, address: str, **kwargs: Any) -> Dict[str, Any]:
        hot_wallet = MoneroExplorerClient.get_client()
        return hot_wallet.request(
            method='get_txs',
            params={
                'address': address,
                'password': hot_wallet.password,
            },
            rpc_id='curltext',
        )

    @classmethod
    def get_tx_details(cls, tx_hash: str) -> Dict[str, Any]:
        hot_wallet = MoneroExplorerClient.get_client()
        return hot_wallet.request(
            method='get_tx_details',
            params={
                'tx_hash': tx_hash,
                'password': hot_wallet.password,
            },
            rpc_id='curltext',
        )

    @classmethod
    def get_batch_block_txs(cls, from_block: int, to_block: int) -> List[Dict[str, Any]]:
        hot_wallet = MoneroExplorerClient.get_client()
        incoming = hot_wallet.request(
            method='get_blocks_txs',
            params={
                'min_height': from_block,
                'max_height': to_block,
                'password': hot_wallet.password,
            },
            rpc_id='curltext',
        )
        outgoing = hot_wallet.request(
            method='get_outgoing_txs',
            params={
                'min_height': from_block,
                'max_height': to_block,
                'password': hot_wallet.password,
            },
            rpc_id='curltext',
        )
        return [incoming, outgoing]
