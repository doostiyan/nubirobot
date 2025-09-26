from unittest import TestCase
from decimal import Decimal
from unittest.mock import Mock

import pytest
from django.conf import settings
from exchange.blockchain.api.algorand.algorand_explorer_interface import AlgorandExplorerInterface
from exchange.blockchain.explorer_original import BlockchainExplorer
from exchange.blockchain.utils import BlockchainUtilsMixin

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies
from exchange.blockchain.api.algorand.algorand_bloq_cloud import BloqCloudAlgorandApi


@pytest.mark.slow
class TestBloqCloudAlgorandApiCalls(TestCase):
    api = BloqCloudAlgorandApi
    addresses_of_account = ['GIBQHQSQZRMOHM4ZNNAZXJ75BBKQEYBRU5KCEJL4Y77V36FDBXRJ6ZSUPE']
    hash_of_transactions = ['5JI6E6UKBFDDE2GOMATHEGBQGKOUKLYG7VI6N4RQKLS6KRAWALQQ']
    block_heights = [31463255, 31464256]

    @classmethod
    def check_general_response(cls, response, keys):
        if set(response.keys()).issubset(keys):
            return True
        return False

    def test_get_balance_api(self):
        keys = {'address', 'amount', 'amount-without-pending-rewards', 'created-at-round', 'deleted', 'min-balance',
                'pending-rewards', 'reward-base', 'rewards', 'round', 'sig-type', 'status', 'transactions-count',
                'total-apps-opted-in', 'total-assets-opted-in', 'total-created-apps', 'total-created-assets',
                'total-box-bytes', 'total-boxes'}
        for address in self.addresses_of_account:
            get_balance_result = self.api.get_balance(address)
            assert self.check_general_response(get_balance_result.get('account'), keys)
            assert isinstance(get_balance_result.get('account'), dict)
            assert isinstance(get_balance_result.get('current-round'), int)

    def test_get_address_txs_api(self):

        address_keys = {'transactions', 'current-round', 'next-token'}
        transaction_keys = {'block-rewards-level', 'close-rewards', 'closing-amount', 'confirmed-round', 'fee',
                            'first-valid', 'id',
                            'index', 'inner-tx-offset', 'intra-round-offset', 'last-valid', 'logs', 'note',
                            'payment-transaction', 'genesis-hash', 'genesis-id',
                            'receiver-rewards', 'round-time', 'sender', 'sender-acc-rewards', 'sender-balance',
                            'sender-rewards',
                            'sender-tx-counter', 'signature', 'tx-type'}
        payment_transaction_keys = {'amount', 'close-acc-rewards', 'close-amount', 'close-balance', 'receiver',
                                    'receiver-acc-rewards', 'receiver-balance', 'receiver-tx-counter'}
        for address in self.addresses_of_account:
            get_address_txs_response = self.api.get_address_txs(address)
            assert self.check_general_response(get_address_txs_response, address_keys)
            assert len(get_address_txs_response) > 0
            if get_address_txs_response.get('transactions') is None:
                continue
            for transaction in get_address_txs_response.get('transactions'):
                if transaction.get('tx-type') == 'pay':
                    assert self.check_general_response(transaction, transaction_keys)
                    assert self.check_general_response(transaction.get('payment-transaction'), payment_transaction_keys)

    def test_get_block_head_api(self):

        blockhead_keys = {'transactions', 'current-round', 'next-token'}
        get_block_head_response = self.api.get_block_head()
        assert self.check_general_response(get_block_head_response, blockhead_keys)
        assert isinstance(get_block_head_response.get('current-round'), int)

    def test_get_tx_details_api(self):
        address_keys = {'transaction', 'current-round'}
        transaction_keys = {'block-rewards-level', 'close-rewards', 'closing-amount', 'confirmed-round', 'fee',
                            'first-valid', 'id',
                            'index', 'inner-tx-offset', 'intra-round-offset', 'last-valid', 'logs', 'note',
                            'payment-transaction', 'genesis-hash', 'genesis-id',
                            'receiver-rewards', 'round-time', 'sender', 'sender-acc-rewards', 'sender-balance',
                            'sender-rewards',
                            'sender-tx-counter', 'signature', 'tx-type'}
        payment_transaction_keys = {'amount', 'close-acc-rewards', 'close-amount', 'close-balance', 'receiver',
                                    'receiver-acc-rewards', 'receiver-balance', 'receiver-tx-counter'}
        for tx_hash in self.hash_of_transactions:
            get_tx_details_response = self.api.get_tx_details(tx_hash)
            assert len(get_tx_details_response) != 0
            assert self.check_general_response(get_tx_details_response, address_keys)
            if not get_tx_details_response.get('transaction'):
                continue
            if get_tx_details_response.get('transaction').get('tx-type') == 'pay':
                assert self.check_general_response(get_tx_details_response.get('transaction'), transaction_keys)
                assert self.check_general_response(
                    get_tx_details_response.get('transaction').get('payment-transaction'), payment_transaction_keys)

    def test_get_block_txs_api(self):
        block_keys = {'expired-part-accounts', 'first-root-tx-index', 'genesis-hash', 'genesis-id', 'hash',
                      'original-proposer', 'previous-block-hash', 'rewards', 'root-transactions-count', 'round', 'seed',
                      'summary', 'timestamp', 'transactions', 'transactions-count', 'transactions-root',
                      'state-proof-tracking',
                      'transactions-root-sha256', 'txn-counter', 'upgrade-state', 'upgrade-vote', 'voter-addresses'}
        transaction_keys = {'block-rewards-level', 'close-rewards', 'closing-amount', 'confirmed-round', 'fee',
                            'first-valid', 'id',
                            'index', 'inner-tx-offset', 'intra-round-offset', 'last-valid', 'logs', 'note',
                            'payment-transaction', 'genesis-hash', 'genesis-id',
                            'receiver-rewards', 'round-time', 'sender', 'sender-acc-rewards', 'sender-balance',
                            'sender-rewards',
                            'sender-tx-counter', 'signature', 'tx-type'}
        payment_transaction_keys = {'amount', 'close-acc-rewards', 'close-amount', 'close-balance', 'receiver',
                                    'receiver-acc-rewards', 'receiver-balance', 'receiver-tx-counter'}
        for block_hash in self.block_heights:
            get_block_txs_response = self.api.get_block_txs(block_hash)
            assert len(get_block_txs_response) != 0
            assert self.check_general_response(get_block_txs_response, block_keys)
            for transaction in get_block_txs_response.get('transactions'):
                if transaction.get('tx-type') == 'pay':
                    assert self.check_general_response(transaction, transaction_keys)
                    assert self.check_general_response(transaction.get('payment-transaction'), payment_transaction_keys)

    def test_get_blocks_txs_api(self):
        blocks_txs_keys = {'current-round', 'next-token', 'transactions'}
        transaction_keys = {'block-rewards-level', 'close-rewards', 'closing-amount', 'confirmed-round', 'fee',
                            'first-valid', 'id',
                            'index', 'inner-tx-offset', 'intra-round-offset', 'last-valid', 'logs', 'note',
                            'payment-transaction', 'genesis-hash', 'genesis-id',
                            'receiver-rewards', 'round-time', 'sender', 'sender-acc-rewards', 'sender-balance',
                            'sender-rewards',
                            'sender-tx-counter', 'signature', 'tx-type'}
        payment_transaction_keys = {'amount', 'close-amount', 'receiver'}
        get_blocks_txs_response = self.api.get_batch_block_txs(31845478, 31845490)
        assert len(get_blocks_txs_response) != 0
        assert self.check_general_response(get_blocks_txs_response, blocks_txs_keys)
        for transaction in get_blocks_txs_response.get('transactions'):
            if transaction.get('tx-type') == 'pay':
                assert self.check_general_response(transaction, transaction_keys)
                assert self.check_general_response(transaction.get('payment-transaction'), payment_transaction_keys)


class TestBloqCloudAlgorandFromExplorer(TestCase):
    api = BloqCloudAlgorandApi
    currency = Currencies.algo

    def test_get_blocks_txs(self):
        batch_get_block_txs_mock_response = [{'current-round': 31979704, 'next-token': '6PMAAAAAAAAAAAAA',
                                              'transactions': [
                                                  {'close-rewards': 0, 'closing-amount': 0, 'confirmed-round': 62440,
                                                   'fee': 1000, 'first-valid': 62000,
                                                   'genesis-hash': 'wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=',
                                                   'genesis-id': 'mainnet-v1.0',
                                                   'id': '7MK6WLKFBPC323ATSEKNEKUTQZ23TCCM75SJNSFAHEM65GYJ5ANQ',
                                                   'intra-round-offset': 0, 'last-valid': 63000,
                                                   'note': 'QS4gOyBBbGV4IE1jQ2FiZSA7IEFsbGlzb24gTm9sYW4gOyBBbm5lIFdhcm5lciA7IGLimKVhIDsgQmVuamFtaW4gQ2hhbiA7IEJlbmphbWluIEQuIFdhcmQgOyBCbyBMaSA7IENocmlzIEh1cmxleSA7IGRlcmVrIDsgZGltaXRyaXMgOyBFbGxlIFlvdSA7IEVyaWMgR2llc2VrZSA7IEV2YW4gSmFtZXMgUmljaGFyZCA7IEdyZWcgQ29sdmluIDsgR1YgOyBIb2V0ZWNrIDsgSWFuIENyb3NzIDsgSmFrZSBFdmFuIEdyZWVuc3RlaW4gOyBKYXNvbiBXZWF0aGVyc2J5IDsgSmluZyBDaGVuIDsgS2FybWFzdGljIDsgS2F0cmljZSBHcmFkeSA7IEtlbGkgSiBDYWxsYWdoYW4gOyBMZW8gUmV5emluIDsgTGl6IEJhcmFuIDsgTWFrZW5hIFN0b25lIDsgTWFzb24oWXVkZSlIdWFuZyA7IE1hdXJpY2UgSGVybGloeSA7IE1heCBKdXN0aWN6IDsgTXVzcyA7IE5hdmVlZCBJaHNhbnVsbGFoIDsgTmlja29sYWkgWmVsZG92aWNoIDsgUGFibG8gQXphciA7IFBhdWwgUmllZ2xlIDsgUmVnaW5hIDsgcmZ1c3Rpbm8gOyBSb3RlbSBIZW1vICjXqNeV16rXnSDXl9ee15UpIDsgc2FtIGFiYmFzc2kgOyBTYXd5ZXIgSHVybGV5IDsgU2VyZ2V5IEdvcmJ1bm92ICjQodC10YDQs9C10Lkg0JPQvtGA0LHRg9C90L7QsikgOyBTaWx2aW8gTWljYWxpIDsgU3Jpaml0aCBQb2R1dmFsIDsgU3RldmVuIEtva2lub3MgOyBUc2FjaGkgSGVybWFuIDsgVHlsZXIgTWFya2xleSA7IFZpY3RvciBMdWNoYW5nY28gOyBXLiBTZWFuIEZvcmQgOyBXaWxsICJaZXJvTWljcm9uIiBXaW5kZXIgOyBZb3NzaSBHaWxhZCA7IFpoZW5mZWkgWmhhbmc=',
                                                   'payment-transaction': {'amount': 100000, 'close-amount': 0,
                                                                           'receiver': 'ALGORANDAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIN5DNAU'},
                                                   'receiver-rewards': 0, 'round-time': 1560614017,
                                                   'sender': 'I3345FUQQ2GRBHFZQPLYQQX5HJMMRZMABCHRLWV6RCJYC6OO4MOLEUBEGU',
                                                   'sender-rewards': 30576000000, 'signature': {'multisig': {
                                                      'subsignature': [{
                                                          'public-key': 'fDPiywtmtrpA2WOY+Mx9y6etNBCij1VKwZmGWW4PbKk='},
                                                          {
                                                              'public-key': 'ETnffVmxyVfJtVgCWFuStLsPJna9G1SHA1yJrfIo6RU='},
                                                          {
                                                              'public-key': 'hYkIN+Iyt2675q+XuYwoAzwR8B0P17WTUFGYn456E4o=',
                                                              'signature': 'eBLuSsmbqXTtKcoDpI88t7CNyQ7ggJ8ZMGjpy+hLWnvjNi938/5U6Eb25Dmes0WLkCxnDZG7gsj3YIDmZfFLAA=='},
                                                          {
                                                              'public-key': '5ChQFEXiHWTeXoJCRymNn8rmEAJAxpaigu4wIgcaODU=',
                                                              'signature': '45ndEdxV115jUGBmqt4WSjcBDg847CiPlE0w5omziLftSRzOtJSd5zrF1zkHOa1B1GJV4AE8E2qriMIbifnYBw=='},
                                                          {
                                                              'public-key': 'RjQ91+zvYumrPm9UOEMN+GnlHW+0gliRCCV2b6KOlwk=',
                                                              'signature': 'LbmMSdKaqD/s9M1ldNAvLYGRMwxWdVPbl4i2zBVKwRnrRLM1Ape9zWMAxX1yJGxk/mAKGa9lZwAfQUlyus58Cw=='},
                                                          {
                                                              'public-key': 'k5F6WQJGyeiPHaN7fvmnBXz6YNq4NQ6BguE7yUmRWkI=',
                                                              'signature': '47b3oXSW6ZVGXmnFy59iQZohcs79v4Da05MTNr0jkUAHl5kseS7Br0C838nbZB79Yj9+wt7kuiiJkCOFgAAwBw=='}],
                                                      'threshold': 4, 'version': 1}}, 'tx-type': 'pay'}]},
                                             {'current-round': 31979713, 'next-token': 'tfjnAQAAAAAOAAAA',
                                              'transactions': [
                                                  {'close-rewards': 0, 'closing-amount': 0, 'confirmed-round': 31979700,
                                                   'fee': 1000, 'first-valid': 31979696,
                                                   'genesis-hash': 'wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=',
                                                   'genesis-id': 'mainnet-v1.0',
                                                   'id': '5MFWMG5BOQW6C4UHRQOEYPDMFMSPXSGZ3OYL2EY7QLGFLXATSYYQ',
                                                   'intra-round-offset': 0, 'last-valid': 31980696, 'note': 'aW5pdA==',
                                                   'payment-transaction': {'amount': 2100000, 'close-amount': 0,
                                                                           'receiver': 'N3TVIKRNO3IPZFVVSQOYULG5Z3OTHGLEDEQX7V7QFIOQCNWHOUN57AP3RA'},
                                                   'receiver-rewards': 0, 'round-time': 1694350166,
                                                   'sender': 'Q4VHAHM6VNR7P74MFCXM6XRY6RUVZ5O3VJL6E26YYTXHFXMZ7RSP3WWANY',
                                                   'sender-rewards': 0, 'signature': {
                                                      'sig': 'hHYcJJlsE+1bJsbo2kdpPup/rxtPbxz+yg22eYU2TX6ffNNP061RrDjnVltWbw7N2jE5B5V+PmYfpMmyVkjhDQ=='},
                                                   'tx-type': 'pay'}, {
                                                      'auth-addr': 'N6KJJWUIAICUWQCZRPLL5T4PWGAK4DDQJS2HITAQMWUMHYSQRXCX733EUQ',
                                                      'close-rewards': 0, 'closing-amount': 0,
                                                      'confirmed-round': 31979701, 'fee': 1000, 'first-valid': 31979695,
                                                      'genesis-hash': 'wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=',
                                                      'genesis-id': 'mainnet-v1.0',
                                                      'id': 'L3BT6NKBUJKQGVYQB36QH7YAIUIWF6PZJ3TQ263AJQH2KSBUBSPQ',
                                                      'intra-round-offset': 1, 'last-valid': 31980695,
                                                      'payment-transaction': {'amount': 1000000000, 'close-amount': 0,
                                                                              'receiver': 'VRX5KPJEFDGARQP5YJD6PBO2B3ZR6U5V2ILQ2N62WTW7BFE634XKA3UVNY'},
                                                      'receiver-rewards': 0, 'round-time': 1694350170,
                                                      'sender': 'STEINCMH2IQXMU37WR7SJH4WXXUGC2TB35WVMQRH3S5TOZE3VQRZEFJE5E',
                                                      'sender-rewards': 0, 'signature': {
                                                          'sig': '448w0VI0OHIpzszmTJAVjGcPF/8btKpwPp3UXdv/uZRtCoEagJF3pl38R/GNAwwm5t803K/HrXg9o30ROjZBBg=='},
                                                      'tx-type': 'pay'},
                                                  {'close-rewards': 0, 'closing-amount': 0, 'confirmed-round': 31979701,
                                                   'fee': 1000, 'first-valid': 31979699,
                                                   'genesis-hash': 'wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=',
                                                   'genesis-id': 'mainnet-v1.0',
                                                   'id': 'JWFOHOWO5A4LTQKTE2NDFQ3WINJMIALNRPTL5W6RZXNTDCRYUTWA',
                                                   'intra-round-offset': 14, 'last-valid': 31980699,
                                                   'payment-transaction': {'amount': 389900000, 'close-amount': 0,
                                                                           'receiver': 'NZMHI2VUJ5XRATLUQYIDVF3CNYJJKELFYGL3LE34VPC4SDEHLGO5CWYBLU'},
                                                   'receiver-rewards': 0, 'round-time': 1694350170,
                                                   'sender': 'HBR3NL2RR3BOKPRDNQSQO2GYOUXUM2ZHUUDDZOFYU2RT3DHLPLH2BWEA5Y',
                                                   'sender-rewards': 0, 'signature': {
                                                      'sig': 'txqh2GZcExRDjmArnn2DBOiDCJLadYN4jlnhsc712uZtbS61rmD5n5NUUbhi38BcNpbvfKKHiPEqHR/A+kcsBQ=='},
                                                   'tx-type': 'pay'}]}]
        self.api.request = Mock(side_effect=batch_get_block_txs_mock_response)
        AlgorandExplorerInterface.block_txs_apis[0] = self.api
        settings.USE_TESTNET_BLOCKCHAINS = False
        txs_addresses, txs_info, _ = BlockchainExplorer.get_latest_block_addresses('ALGO', None, None, True, True)
        expected_txs_info = {
            'outgoing_txs': {
                'Q4VHAHM6VNR7P74MFCXM6XRY6RUVZ5O3VJL6E26YYTXHFXMZ7RSP3WWANY': {Currencies.algo: [
                    {'contract_address': None, 'tx_hash': '5MFWMG5BOQW6C4UHRQOEYPDMFMSPXSGZ3OYL2EY7QLGFLXATSYYQ',
                     'value': Decimal('2.100000'), 'block_height': 31979700, 'symbol':'ALGO'}]
                },
                'STEINCMH2IQXMU37WR7SJH4WXXUGC2TB35WVMQRH3S5TOZE3VQRZEFJE5E': {Currencies.algo: [
                    {'contract_address': None, 'tx_hash': 'L3BT6NKBUJKQGVYQB36QH7YAIUIWF6PZJ3TQ263AJQH2KSBUBSPQ',
                     'value': Decimal('1000.000000'), 'block_height': 31979701, 'symbol':'ALGO'}]},
                'HBR3NL2RR3BOKPRDNQSQO2GYOUXUM2ZHUUDDZOFYU2RT3DHLPLH2BWEA5Y': {Currencies.algo: [
                    {'contract_address': None, 'tx_hash': 'JWFOHOWO5A4LTQKTE2NDFQ3WINJMIALNRPTL5W6RZXNTDCRYUTWA',
                     'value': Decimal('389.900000'), 'block_height': 31979701, 'symbol':'ALGO'}]}
            },
            'incoming_txs': {
                'N3TVIKRNO3IPZFVVSQOYULG5Z3OTHGLEDEQX7V7QFIOQCNWHOUN57AP3RA': {Currencies.algo: [
                    {'contract_address': None, 'tx_hash': '5MFWMG5BOQW6C4UHRQOEYPDMFMSPXSGZ3OYL2EY7QLGFLXATSYYQ',
                     'value': Decimal('2.100000'), 'block_height': 31979700, 'symbol':'ALGO'}]},
                'VRX5KPJEFDGARQP5YJD6PBO2B3ZR6U5V2ILQ2N62WTW7BFE634XKA3UVNY': {Currencies.algo: [
                    {'contract_address': None, 'tx_hash': 'L3BT6NKBUJKQGVYQB36QH7YAIUIWF6PZJ3TQ263AJQH2KSBUBSPQ',
                     'value': Decimal('1000.000000'), 'block_height': 31979701, 'symbol':'ALGO'}]},
                'NZMHI2VUJ5XRATLUQYIDVF3CNYJJKELFYGL3LE34VPC4SDEHLGO5CWYBLU': {Currencies.algo: [
                    {'contract_address': None, 'tx_hash': 'JWFOHOWO5A4LTQKTE2NDFQ3WINJMIALNRPTL5W6RZXNTDCRYUTWA',
                     'value': Decimal('389.900000'), 'block_height': 31979701, 'symbol':'ALGO'}]}
            }
        }
        expected_txs_addresses = {
            'input_addresses': {'HBR3NL2RR3BOKPRDNQSQO2GYOUXUM2ZHUUDDZOFYU2RT3DHLPLH2BWEA5Y',
                                'Q4VHAHM6VNR7P74MFCXM6XRY6RUVZ5O3VJL6E26YYTXHFXMZ7RSP3WWANY',
                                'STEINCMH2IQXMU37WR7SJH4WXXUGC2TB35WVMQRH3S5TOZE3VQRZEFJE5E'},
            'output_addresses': {'N3TVIKRNO3IPZFVVSQOYULG5Z3OTHGLEDEQX7V7QFIOQCNWHOUN57AP3RA',
                                 'NZMHI2VUJ5XRATLUQYIDVF3CNYJJKELFYGL3LE34VPC4SDEHLGO5CWYBLU',
                                 'VRX5KPJEFDGARQP5YJD6PBO2B3ZR6U5V2ILQ2N62WTW7BFE634XKA3UVNY'}
        }
        assert BlockchainUtilsMixin.compare_dicts_without_order(expected_txs_info, txs_info)
        assert BlockchainUtilsMixin.compare_dicts_without_order(expected_txs_addresses, txs_addresses)
