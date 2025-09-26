import random
from typing import List

from django.conf import settings

from exchange.base.models import Currencies
from exchange.blockchain.api.commons.covalenthq import CovalenthqApi, CovalenthqResponseParser
from exchange.blockchain.api.general.dtos import TransferTx
from exchange.blockchain.api.one.one_rpc import HarmonyRPC
from exchange.blockchain.contracts_conf import harmony_ERC20_contract_info, harmony_ERC20_contract_currency


class ONECovalenthqResponseParser(CovalenthqResponseParser):
    precision = 18
    currency = Currencies.one
    symbol = 'ONE'
    rpc = HarmonyRPC()

    @classmethod
    def parse_address_txs_response(cls, address, address_txs_response, block_head) -> List[TransferTx]:
        address_txs = super().parse_address_txs_response(address, address_txs_response, block_head)
        one_tx_hashes = list()
        for address_tx in address_txs:
            one_tx_hashes.append(address_tx.tx_hash)
        eth_tx_hashes = cls.rpc.get_txs_hashes(one_tx_hashes)
        for eth_hash, address_tx in zip(eth_tx_hashes, address_txs):
            address_tx.tx_hash = eth_hash
        return address_txs

    @classmethod
    def contract_currency_list(cls):
        return harmony_ERC20_contract_currency.get(cls.network_mode)

    @classmethod
    def contract_info_list(cls):
        return harmony_ERC20_contract_info.get(cls.network_mode)


class ONECovalenthqAPI(CovalenthqApi):
    """
    tx_details: only support One Tx_hash (instead of ETH Tx_hash)
    """

    _base_url = 'https://api.covalenthq.com/v1/1666600000'
    testnet_url = 'https://api.covalenthq.com/v1/1666700000'
    parser = ONECovalenthqResponseParser
    cache_key = 'one'
    rpc = HarmonyRPC()

    @classmethod
    def get_api_key(cls):
        return random.choice(settings.COVALENT_API_KEYS)
