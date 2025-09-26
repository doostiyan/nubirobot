from unittest import TestCase
from exchange.blockchain.explorer_original import BlockchainExplorer


class CompareTest(TestCase):
    apis = []
    addresses = []
    txs_hash = []
    block_heights = []
    symbol = None
    currencies = None
    explorerInterface = None

    @classmethod
    def balance_compare(cls):
        for address in cls.addresses:
            balance_responses = []
            for api in cls.apis:
                cls.explorerInterface.balance_apis[0] = api
                balance_responses.append(
                    BlockchainExplorer.get_wallets_balance({cls.symbol: address}, cls.currencies))
            assert len(balance_responses) > 1
            for balance in balance_responses:
                assert balance_responses[0] == balance

    @classmethod
    def tx_details_compare(cls):
        for tx_hash in cls.txs_hash:
            tx_details_responses = []
            for api in cls.apis:
                cls.explorerInterface.tx_details_apis[0] = api
                tx_details_responses.append(
                    BlockchainExplorer.get_transactions_details(tx_hash, cls.symbol))
            assert len(tx_details_responses) > 1
            for tx_details in tx_details_responses:
                assert tx_details_responses[0] == tx_details

    @classmethod
    def address_txs_compare(cls):
        for address in cls.addresses:
            txs_responses = []
            for api in cls.apis:
                cls.explorerInterface.address_txs_apis[0] = api
                txs_responses.append(
                    BlockchainExplorer.get_wallet_transactions(address, cls.currencies, cls.symbol))
            assert len(txs_responses) > 1
            for txs in txs_responses:
                assert len(txs_responses[0].get(cls.currencies)) == len(txs.get(cls.currencies))
                for tx0, txN in zip(txs_responses[0].get(cls.currencies), txs.get(cls.currencies)):
                    assert tx0.__dict__ == txN.__dict__

    @classmethod
    def block_txs_compare(cls):
        for from_block, to_block in cls.block_heights:
            txs_addresses = []
            txs_info = []
            for api in cls.apis:
                cls.explorerInterface.block_txs_apis[0] = api
                txs_address, tx_info, _ = BlockchainExplorer.get_latest_block_addresses(
                    cls.symbol, from_block, to_block, True, True)
                txs_addresses.append(txs_address)
                txs_info.append(tx_info)
            assert len(txs_addresses) > 1
            for txs in txs_addresses:
                assert txs_addresses[0] == txs
            assert len(txs_info) > 1
            for info in txs_info:
                assert txs_info[0] == info
