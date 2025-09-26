import datetime
from decimal import Decimal
from unittest import TestCase
from unittest.mock import Mock

import pytest
from django.conf import settings
from pytz import UTC

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

from exchange.blockchain.api.general.dtos import TransferTx
from exchange.blockchain.api.eos.new_eos_bitquery import EosBitqueryApi


@pytest.mark.slow
class TestEosBitqueryApiCalls(TestCase):
    api = EosBitqueryApi
    hash_of_transactions = ['139a3feebed6eb9a93be9d5e64eca5ce6265022715584384f20d6d2635c43591',
                            '1b613521679c3c51de24b50a1b5c1b707ff1991d922781dfdfa26d53bd6c26b9',
                            '2062e1b8ca7832cd3f442c56228d430885b9ff6a413906b30638ee90bed90b25',
                            ]

    def check_general_response(self, response, keys):
        if set(keys).issubset(set(response.keys())):
            return True
        return False

    def keys_types_check(self, response, keys_types_check):
        for key, value in keys_types_check:
            self.assertIsInstance(response.get(key), value)

    def test_get_tx_details_api(self):
        transaction_keys = {'hash', 'block', 'success'}
        transaction_keys_types_check = [('hash', str), ('block', dict), ('success', bool)]
        transfer_keys = {'txHash', 'sender', 'receiver', 'amount', 'memo', 'currency', 'success'}
        transfer_keys_types_check = [('txHash', str), ('receiver', dict), ('sender', dict),
                                     ('currency', dict), ('success', bool)]
        get_tx_details_response = self.api.get_tx_details_batch(self.hash_of_transactions)
        self.assertIsInstance(get_tx_details_response, dict)
        self.assertIsInstance(get_tx_details_response.get('data'), dict)
        self.assertIsInstance(get_tx_details_response.get('data').get('eos'), dict)
        response = get_tx_details_response.get('data').get('eos')
        self.assertIsInstance(response.get('blocks'), list)
        self.assertIsInstance(response.get('blocks')[0], dict)
        self.assertIsInstance(response.get('blocks')[0].get('height'), int)
        self.assertIsInstance(response.get('transactions'), list)
        self.assertIsInstance(response.get('transfers'), list)
        transactions = response.get('transactions')
        transfers = response.get('transfers')
        for transaction in transactions:
            assert self.check_general_response(transaction, transaction_keys)
            self.keys_types_check(transaction, transaction_keys_types_check)
            self.assertIsInstance(transaction.get('block').get('height'), int)
            self.assertIsInstance(transaction.get('block').get('timestamp'), dict)
            self.assertIsInstance(transaction.get('block').get('timestamp').get('time'), str)
        for transfer in transfers:
            assert self.check_general_response(transfer, transfer_keys)
            self.keys_types_check(transfer, transfer_keys_types_check)
            self.assertIsInstance(transfer.get('sender').get('address'), str)
            self.assertIsInstance(transfer.get('receiver').get('address'), str)
            self.assertIsInstance(transfer.get('currency').get('address'), str)
            self.assertIsInstance(transfer.get('currency').get('symbol'), str)


class TestEosBitqueryFromExplorer(TestCase):
    api = EosBitqueryApi
    currency = Currencies.eos
    symbol = 'EOS'
    # Txs in order of success, success, fail
    hash_of_transactions = ['139a3feebed6eb9a93be9d5e64eca5ce6265022715584384f20d6d2635c43591',
                            '1b613521679c3c51de24b50a1b5c1b707ff1991d922781dfdfa26d53bd6c26b9',
                            '2062e1b8ca7832cd3f442c56228d430885b9ff6a413906b30638ee90bed90b25'
                            ]

    def test_get_tx_details(self):
        tx_details_mock_responses = [
            {'data': {'eos': {'blocks': [{'height': 386418563}], 'transactions': [
                {'hash': '139a3feebed6eb9a93be9d5e64eca5ce6265022715584384f20d6d2635c43591',
                 'block': {'height': 342475516, 'timestamp': {'time': '2023-11-19T21:03:35Z'}}, 'success': True},
                {'hash': '1b613521679c3c51de24b50a1b5c1b707ff1991d922781dfdfa26d53bd6c26b9',
                 'block': {'height': 241188596, 'timestamp': {'time': '2022-04-12T11:14:45Z'}}, 'success': True},
                {'hash': '2062e1b8ca7832cd3f442c56228d430885b9ff6a413906b30638ee90bed90b25',
                 'block': {'height': 241188201, 'timestamp': {'time': '2022-04-12T11:11:28Z'}}, 'success': True}],
                              'transfers': [
                                  {'txHash': '139a3feebed6eb9a93be9d5e64eca5ce6265022715584384f20d6d2635c43591',
                                   'sender': {'address': 'axygsk5vbquz'}, 'receiver': {'address': 'eostexpriwh1'},
                                   'amount': 418.3748, 'memo': '',
                                   'currency': {'symbol': 'EOS', 'address': 'eosio.token'}, 'success': True},
                                  {'txHash': '1b613521679c3c51de24b50a1b5c1b707ff1991d922781dfdfa26d53bd6c26b9',
                                   'sender': {'address': 'newposincome'}, 'receiver': {'address': 'geytmmrvgene'},
                                   'amount': 1.2653, 'memo': '',
                                   'currency': {'symbol': 'EOS', 'address': 'eosio.token'}, 'success': True}]}}}
        ]
        self.api.request = Mock(side_effect=tx_details_mock_responses)
        api_response = self.api.get_tx_details_batch(self.hash_of_transactions)
        parsed_response = self.api.parser.parse_batch_tx_details_response(api_response, None)
        expected_txs_details = [TransferTx(tx_hash='139a3feebed6eb9a93be9d5e64eca5ce6265022715584384f20d6d2635c43591', success=True, from_address='axygsk5vbquz', to_address='eostexpriwh1', value=Decimal('418.3748'), symbol='EOS', confirmations=43943047, block_height=342475516, block_hash=None, date=datetime.datetime(2023, 11, 19, 21, 3, 35, tzinfo=UTC), memo='', tx_fee=None, token=None, index=None), TransferTx(tx_hash='1b613521679c3c51de24b50a1b5c1b707ff1991d922781dfdfa26d53bd6c26b9', success=True, from_address='newposincome', to_address='geytmmrvgene', value=Decimal('1.2653'), symbol='EOS', confirmations=145229967, block_height=241188596, block_hash=None, date=datetime.datetime(2022, 4, 12, 11, 14, 45, tzinfo=UTC), memo='', tx_fee=None, token=None, index=None)]
        for expected_tx_details, tx_details in zip(expected_txs_details, parsed_response):
            assert tx_details == expected_tx_details
