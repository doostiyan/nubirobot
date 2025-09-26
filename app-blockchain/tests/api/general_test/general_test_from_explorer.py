from unittest import TestCase
from unittest.mock import Mock
from django.conf import settings
from django.core.cache import cache

from exchange.blockchain.explorer_original import BlockchainExplorer
from exchange.blockchain.utils import BlockchainUtilsMixin


class TestFromExplorer(TestCase):
    api = None
    addresses = []
    txs_addresses = []
    txs_hash = []
    block_heights = []
    symbol = None
    currencies = None
    explorerInterface = None
    BlockchainExplorer.ONLY_SUBMODULE = True

    @classmethod
    def get_balance(cls, mock_balances, expected_balances):
        balance_mock_responses = mock_balances
        cls.api.request = Mock(side_effect=balance_mock_responses)
        cls.explorerInterface.balance_apis[0] = cls.api
        if not cls.addresses:
            assert False, 'None type!'
        balances = BlockchainExplorer.get_wallets_balance({cls.symbol: cls.addresses}, cls.currencies)
        if not balances:
            assert not expected_balances, 'None type!'
        if cls.api.SUPPORT_GET_BALANCE_BATCH:
            assert balances.get(cls.currencies) == expected_balances
        else:
            for balance, expected_balance in zip(balances.get(cls.currencies), expected_balances):
                assert balance == expected_balance

    @classmethod
    def get_tx_details(cls, tx_details_mock_response, expected_txs_details):
        cls.api.request = Mock(side_effect=tx_details_mock_response)
        cls.explorerInterface.tx_details_apis[0] = cls.api
        if not cls.txs_hash:
            assert False, 'None type!'
        txs_details = BlockchainExplorer.get_transactions_details(cls.txs_hash, cls.symbol)
        if not txs_details:
            assert not expected_txs_details, 'None type!'
        for expected_tx_detail, tx_hash in zip(expected_txs_details, cls.txs_hash):
            assert txs_details.get(tx_hash) == expected_tx_detail

    @classmethod
    def get_address_txs(cls, address_txs_mock_response, expected_addresses_txs):
        cls.api.request = Mock(side_effect=address_txs_mock_response)
        cls.explorerInterface.address_txs_apis[0] = cls.api
        if not cls.txs_addresses:
            assert False, 'None type!'
        for address, expected_address_txs in zip(cls.txs_addresses, expected_addresses_txs):
            address_txs = BlockchainExplorer.get_wallet_transactions(address, cls.currencies, cls.symbol)
            if not address_txs:
                assert not expected_address_txs, 'None type!'
            assert len(expected_address_txs) == len(address_txs.get(cls.currencies))
            for expected_address_tx, address_tx in zip(expected_address_txs, address_txs.get(cls.currencies)):
                assert address_tx.__dict__ == expected_address_tx

    @classmethod
    def get_block_txs(cls, block_txs_mock_response, expected_txs_addresses, expected_txs_info):
        cls.api.request = Mock(side_effect=block_txs_mock_response)
        cls.explorerInterface.block_txs_apis[0] = cls.api
        settings.USE_TESTNET_BLOCKCHAINS = False
        cache.set(f'{settings.BLOCKCHAIN_CACHE_PREFIX}latest_block_height_processed_{cls.api.cache_key}', None)
        txs_addresses, txs_info, _ = BlockchainExplorer.get_latest_block_addresses(
            cls.symbol, None, None, True, True)
        assert BlockchainUtilsMixin.compare_dicts_without_order(expected_txs_info, txs_info)
        assert BlockchainUtilsMixin.compare_dicts_without_order(expected_txs_addresses, txs_addresses)
