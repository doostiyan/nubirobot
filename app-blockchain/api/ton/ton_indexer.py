import urllib.parse
from typing import Any, Dict

from exchange.blockchain.api.general.general import GeneralApi
from exchange.blockchain.api.ton.toncenter_ton import ToncenterTonResponseParser

from .utils import TonAddressConvertor


class TonIndexerTonResponseParser(ToncenterTonResponseParser):

    @classmethod
    def get_memo(cls, transaction: Dict[str, Any]) -> str:
        return transaction.get('in_msg').get('body').get('comment')

    @classmethod
    def get_user_friendly_address(cls, address: str) -> str:
        return TonAddressConvertor.convert_hex_to_bounceable(address[2:])


class TonIndexerApi(GeneralApi):
    parser = TonIndexerTonResponseParser
    _base_url = 'https://blockapi2.nobitex1.ir/tonindexer/v1/'
    cache_key = 'ton'
    workchain = 0
    supported_requests = {
        'get_block_head': 'getBlocks?workchain=' + str(workchain) + '&limit=1',
        'get_address_txs': 'getTransactionsByAddress?address={address}&limit=' + str(
            GeneralApi.TRANSACTIONS_LIMIT) + '&include_msg_body=true',
        'get_tx_details': 'getTransactionByHash?tx_hash={tx_hash}&include_msg_body=true'
    }

    @classmethod
    def get_tx_details(cls, tx_hash: str) -> Any:
        tx_hash_url_encoded = urllib.parse.quote_plus(tx_hash)
        return cls.request(request_method='get_tx_details', body=cls.get_tx_details_body(tx_hash),
                           headers=cls.get_headers(), tx_hash=tx_hash_url_encoded)
