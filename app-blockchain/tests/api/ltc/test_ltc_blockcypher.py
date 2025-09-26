from decimal import Decimal
from unittest import TestCase
import datetime
from unittest.mock import Mock

import pytest
from pytz import UTC

from exchange.base.models import Currencies
from exchange.blockchain.api.general.dtos import TransferTx
from exchange.blockchain.api.ltc.ltc_explorer_interface import LTCExplorerInterface
from exchange.blockchain.api.ltc.ltc_blockcypher_new import LiteCoinBlockcypherAPI
from exchange.blockchain.tests.api.general_test.general_test_from_explorer import TestFromExplorer


@pytest.mark.slow
class TestLiteCoinBlockcypherApiCalls(TestCase):
    api = LiteCoinBlockcypherAPI
    txs_hash = [
        'a9e13035052225a65ed7d9fd400d65a57e471d1d1fbf7121207f803e4e9681ef',
        '83b41ceb8e79209bec1c82aa0ae8c9a83db87e6e199f764a167b6ee5e01a3026',
        '29c38cc2b50b6da5d42f2af92325ea1295fce613b3bd10f6c8205d35f16a9f2d'
    ]
    addresses_of_accounts = ['MTQHeDv2U8XnkkxsnwKWRaGRDKPr1QS5aw', 'LcNS6c8RddAMjewDrUAAi8BzecKoosnkN3']

    @classmethod
    def check_general_response(cls, response, keys):
        if set(keys).issubset(response.keys()):
            return True
        return False

    def test_get_balance_response(self):
        for address in self.addresses_of_accounts:
            get_balance_response = self.api.get_balance(address)
            self.assertIsInstance(get_balance_response, dict)
            self.assertIsInstance(get_balance_response.get('balance'), int)
            self.assertIsInstance(get_balance_response.get('unconfirmed_balance'), int)

    def test_get_tx_details_api(self):
        tx_details_keys = {'block_hash', 'block_height', 'hash', 'confirmations', 'inputs', 'outputs', 'confirmed',
                           'double_spend', 'fees'}
        tx_details_keys_types = [('block_hash', str), ('block_height', int), ('hash', str), ('confirmations', int),
                                 ('inputs', list), ('outputs', list), ('confirmed', str), ('double_spend', int),
                                 ('fees', int), ('double_spend', bool)]
        input_keys = {'output_value', 'script_type', 'addresses'}
        input_key_stypes = [('output_value', int), ('script_type', str), ('addresses', list)]
        output_keys = {'value', 'script_type', 'addresses'}
        output_key_stypes = [('value', int), ('script_type', str), ('addresses', list)]

        for tx_hash in self.txs_hash:
            get_tx_details_response = self.api.get_tx_details(tx_hash)
            self.assertIsInstance(get_tx_details_response, dict)
            assert self.check_general_response(get_tx_details_response, tx_details_keys)
            for key, value in tx_details_keys_types:
                self.assertIsInstance(get_tx_details_response.get(key), value)
            assert get_tx_details_response.get('inputs')
            self.assertIsInstance(get_tx_details_response.get('inputs'), list)
            for input in get_tx_details_response.get('inputs'):
                self.assertIsInstance(input, dict)
                assert self.check_general_response(input, input_keys)
                for key, value in input_key_stypes:
                    self.assertIsInstance(input.get(key), value)
            assert get_tx_details_response.get('outputs')
            self.assertIsInstance(get_tx_details_response.get('outputs'), list)
            for output in get_tx_details_response.get('outputs'):
                self.assertIsInstance(output, dict)
                assert self.check_general_response(output, output_keys)
                for key, value in output_key_stypes:
                    self.assertIsInstance(output.get(key), value)


class TestLiteCoinBlockcypherFromExplorer(TestFromExplorer):
    api = LiteCoinBlockcypherAPI
    symbol = 'LTC'
    explorerInterface = LTCExplorerInterface
    currencies = Currencies.ltc

    txs_hash = [
        'a9e13035052225a65ed7d9fd400d65a57e471d1d1fbf7121207f803e4e9681ef',
        '83b41ceb8e79209bec1c82aa0ae8c9a83db87e6e199f764a167b6ee5e01a3026',
        '29c38cc2b50b6da5d42f2af92325ea1295fce613b3bd10f6c8205d35f16a9f2d'
    ]
    addresses_of_accounts = ['MTQHeDv2U8XnkkxsnwKWRaGRDKPr1QS5aw', 'LcNS6c8RddAMjewDrUAAi8BzecKoosnkN3']

    def test_get_tx_details(self):
        tx_details_mock_responses = [
            {'block_hash': '9ceb7e83248bccd734693bc7c60ce4fe98c3f12db7df479f8be45b66abab1ed6', 'block_height': 2707106,
             'block_index': 19, 'hash': 'a9e13035052225a65ed7d9fd400d65a57e471d1d1fbf7121207f803e4e9681ef',
             'addresses': ['MKJ3hKvF75dA47PyFceqK8P1jpsFqJzLYJ', 'Lc8H5EAFBKbGmnJGRNGkLVpLY9XXaeiujw',
                           'ltc1qz89kssmkzqh6z4p2f0f5wnj7fmdjx0a8sxxvju'], 'total': 60011156378, 'fees': 3700,
             'size': 254, 'vsize': 254, 'preference': 'low', 'confirmed': '2024-06-21T22:58:19Z',
             'received': '2024-06-21T22:58:19Z', 'ver': 1, 'double_spend': False, 'vin_sz': 1, 'vout_sz': 3,
             'confirmations': 27504, 'confidence': 1, 'inputs': [
                {'prev_hash': '51d543dd3cbed2d50f707794e52a6bc209771457dff557300cd50eec997a23b2', 'output_index': 2,
                 'script': '4730440220185f082c0b3b38a8b34454228fe289e7b4b1e1a86357c532605d9af096a46d5b0220064717fa8717f7f55b0569a61154108733f6dc5f1975731fe1f8975e87ea2ff50121039703bb51ec58e29d3daf13f227a531cfce0768a0a6fe28e2b15ed206592a9f40',
                 'output_value': 60011160078, 'sequence': 4294967295,
                 'addresses': ['Lc8H5EAFBKbGmnJGRNGkLVpLY9XXaeiujw'], 'script_type': 'pay-to-pubkey-hash',
                 'age': 2707105}], 'outputs': [
                {'value': 1390822, 'script': 'a9147cfd7e9a8fa7894e2e0fa04253a6dd96f7de053287',
                 'spent_by': '002c313c89ba4afa11dcb15c4dbc5d7eed54f70a038ffee4b71dd3da48a3da91',
                 'addresses': ['MKJ3hKvF75dA47PyFceqK8P1jpsFqJzLYJ'], 'script_type': 'pay-to-script-hash'},
                {'value': 2941137, 'script': '001411cb684376102fa1542a4bd3474e5e4edb233fa7',
                 'spent_by': '1e78b0dc49a3a6ddefc9fb52df380569aaf1d58141459fb78b3d05d886a62c88',
                 'addresses': ['ltc1qz89kssmkzqh6z4p2f0f5wnj7fmdjx0a8sxxvju'],
                 'script_type': 'pay-to-witness-pubkey-hash'},
                {'value': 60006824419, 'script': '76a914b96758481720ca64e02538df543b75880dabc44b88ac',
                 'spent_by': 'e28e86b28ddb4a4870b82a397c01c009d7895f34f03c216095a32e81446e7a5a',
                 'addresses': ['Lc8H5EAFBKbGmnJGRNGkLVpLY9XXaeiujw'], 'script_type': 'pay-to-pubkey-hash'}]},
            {'block_hash': '9ceb7e83248bccd734693bc7c60ce4fe98c3f12db7df479f8be45b66abab1ed6', 'block_height': 2707106,
             'block_index': 18, 'hash': '83b41ceb8e79209bec1c82aa0ae8c9a83db87e6e199f764a167b6ee5e01a3026',
             'addresses': ['MRSXyMETyqz1zrAvNjhHNsspDz1vGjZv6f', 'MRnv1iF722SUsrFZxmZSg1Ey7Vhghy8Gz6',
                           'Lbj6aqXbjagnyJhvbtArC5ozQhksmdL5mV'], 'total': 5000000, 'fees': 3360, 'size': 388,
             'vsize': 226, 'preference': 'low', 'relayed_by': '195.154.187.6:9333', 'confirmed': '2024-06-21T22:58:19Z',
             'received': '2024-06-21T22:57:48.845Z', 'ver': 2, 'lock_time': 2707103, 'double_spend': False, 'vin_sz': 2,
             'vout_sz': 1, 'confirmations': 27504, 'confidence': 1, 'inputs': [
                {'prev_hash': 'f7237d8780614297b617b528a7b857a22df3a295558b4e7ec8246d5bef1b6291', 'output_index': 33,
                 'script': '160014fb2fcd12d1c3de40c08a75fd76558b0c9ac44477', 'output_value': 4944048,
                 'sequence': 4294967294, 'addresses': ['MRnv1iF722SUsrFZxmZSg1Ey7Vhghy8Gz6'],
                 'script_type': 'pay-to-script-hash', 'age': 2707018},
                {'prev_hash': 'fbb2cdfa0e624bf1ab81213953837b5dadc170f9f0af5c3142b782a0ba2bb8e8', 'output_index': 11,
                 'script': '16001462ac308d033d417c9a4965655d89eca455fcb453', 'output_value': 59312,
                 'sequence': 4294967294, 'addresses': ['MRSXyMETyqz1zrAvNjhHNsspDz1vGjZv6f'],
                 'script_type': 'pay-to-script-hash', 'age': 2706537}], 'outputs': [
                {'value': 5000000, 'script': '76a914b5050584153d964c70bb658d613638a65879c44888ac',
                 'addresses': ['Lbj6aqXbjagnyJhvbtArC5ozQhksmdL5mV'], 'script_type': 'pay-to-pubkey-hash'}]},
            {'block_hash': '9ceb7e83248bccd734693bc7c60ce4fe98c3f12db7df479f8be45b66abab1ed6', 'block_height': 2707106,
             'block_index': 15, 'hash': '29c38cc2b50b6da5d42f2af92325ea1295fce613b3bd10f6c8205d35f16a9f2d',
             'addresses': ['LYFgesyfnXNCmCaKKKjcppWCzMHk19x7xx', 'ltc1q60ew95dz7a7c8jwszu7luvddkfc2up875jcyql',
                           'ltc1qlkpfuktla7pza93x26nrv0xfrp0k7kgdy35qaa'], 'total': 223832830, 'fees': 6360,
             'size': 373, 'vsize': 211, 'preference': 'low', 'relayed_by': '70.63.170.86:9333',
             'confirmed': '2024-06-21T22:58:19Z', 'received': '2024-06-21T22:57:53.485Z', 'ver': 2,
             'double_spend': False, 'vin_sz': 2, 'vout_sz': 2, 'opt_in_rbf': True, 'confirmations': 27504,
             'confidence': 1, 'inputs': [
                {'prev_hash': '293ff1a0eb6557b60d4f7276a8c734e80d1555193c405dba319f7cfb641420f3', 'output_index': 1,
                 'output_value': 2285974, 'sequence': 4294967293,
                 'addresses': ['ltc1qlkpfuktla7pza93x26nrv0xfrp0k7kgdy35qaa'],
                 'script_type': 'pay-to-witness-pubkey-hash', 'age': 2707099, 'witness': [
                    '304402200c3d17340b7a226045bbd25a2ff731d495ac0809b905b724a2ed2c03452f9534022013db84135a72dfb9363ebb23033abdc0b6fd31a4740d847dab0581890ad0a34401',
                    '02cf2a44f4640a340ccf562703a1f696195ea5cdac14ff440fd7cf69d94e3e07d6']},
                {'prev_hash': '69081fca1141f6fd0df227fe3bc6795b0c895c159fb178e4306e6f5d740bfd49', 'output_index': 1,
                 'output_value': 221553216, 'sequence': 4294967293,
                 'addresses': ['ltc1qlkpfuktla7pza93x26nrv0xfrp0k7kgdy35qaa'],
                 'script_type': 'pay-to-witness-pubkey-hash', 'age': 2707100, 'witness': [
                    '30440220012b438a7ec21d8ec9b18229aab9c797082e9184cc477bda64e4914f7fd6dc1002207cbea1666c315b818ca67f0a6cf68b5e3aaef1de9fd2c818ee027d6d5e0a2f6201',
                    '02cf2a44f4640a340ccf562703a1f696195ea5cdac14ff440fd7cf69d94e3e07d6']}], 'outputs': [
                {'value': 66768444, 'script': '76a9148eed6fed35c29149c4bc42d236eb5dc44cde468788ac',
                 'spent_by': 'f06cd6cca0368255249e192079b289178d4b99a885dae05958c56d580a338c01',
                 'addresses': ['LYFgesyfnXNCmCaKKKjcppWCzMHk19x7xx'], 'script_type': 'pay-to-pubkey-hash'},
                {'value': 157064386, 'script': '0014d3f2e2d1a2f77d83c9d0173dfe31adb270ae04fe',
                 'spent_by': '78da1f7335d55bc11f1aba2e49af1644323f953fdd548d8d5d5d3fc9e26798d4',
                 'addresses': ['ltc1q60ew95dz7a7c8jwszu7luvddkfc2up875jcyql'],
                 'script_type': 'pay-to-witness-pubkey-hash'}]}
        ]
        self.api.request = Mock(side_effect=tx_details_mock_responses)
        parsed_responses = []
        for tx_hash in self.txs_hash:
            api_response = self.api.get_tx_details(tx_hash)
            parsed_response = self.api.parser.parse_tx_details_response(api_response, None)
            parsed_responses.append(parsed_response)
        expected_txs_details = [[TransferTx(tx_hash='a9e13035052225a65ed7d9fd400d65a57e471d1d1fbf7121207f803e4e9681ef', success=True, from_address='Lc8H5EAFBKbGmnJGRNGkLVpLY9XXaeiujw', to_address='', value=Decimal('0.04335659'), symbol='LTC', confirmations=27504, block_height=2707106, block_hash='9ceb7e83248bccd734693bc7c60ce4fe98c3f12db7df479f8be45b66abab1ed6', date=datetime.datetime(2024, 6, 21, 22, 58, 19, tzinfo=UTC), memo=None, tx_fee=Decimal('0.00003700'), token=None, index=None), TransferTx(tx_hash='a9e13035052225a65ed7d9fd400d65a57e471d1d1fbf7121207f803e4e9681ef', success=True, from_address='', to_address='ltc1qz89kssmkzqh6z4p2f0f5wnj7fmdjx0a8sxxvju', value=Decimal('0.02941137'), symbol='LTC', confirmations=27504, block_height=2707106, block_hash='9ceb7e83248bccd734693bc7c60ce4fe98c3f12db7df479f8be45b66abab1ed6', date=datetime.datetime(2024, 6, 21, 22, 58, 19, tzinfo=UTC), memo=None, tx_fee=Decimal('0.00003700'), token=None, index=None)],
                                [TransferTx(tx_hash='83b41ceb8e79209bec1c82aa0ae8c9a83db87e6e199f764a167b6ee5e01a3026', success=True, from_address='', to_address='Lbj6aqXbjagnyJhvbtArC5ozQhksmdL5mV', value=Decimal('0.05000000'), symbol='LTC', confirmations=27504, block_height=2707106, block_hash='9ceb7e83248bccd734693bc7c60ce4fe98c3f12db7df479f8be45b66abab1ed6', date=datetime.datetime(2024, 6, 21, 22, 58, 19, tzinfo=UTC), memo=None, tx_fee=Decimal('0.00003360'), token=None, index=None)],
                                [TransferTx(tx_hash='29c38cc2b50b6da5d42f2af92325ea1295fce613b3bd10f6c8205d35f16a9f2d', success=True, from_address='ltc1qlkpfuktla7pza93x26nrv0xfrp0k7kgdy35qaa', to_address='', value=Decimal('2.23839190'), symbol='LTC', confirmations=27504, block_height=2707106, block_hash='9ceb7e83248bccd734693bc7c60ce4fe98c3f12db7df479f8be45b66abab1ed6', date=datetime.datetime(2024, 6, 21, 22, 58, 19, tzinfo=UTC), memo=None, tx_fee=Decimal('0.00006360'), token=None, index=None), TransferTx(tx_hash='29c38cc2b50b6da5d42f2af92325ea1295fce613b3bd10f6c8205d35f16a9f2d', success=True, from_address='', to_address='LYFgesyfnXNCmCaKKKjcppWCzMHk19x7xx', value=Decimal('0.66768444'), symbol='LTC', confirmations=27504, block_height=2707106, block_hash='9ceb7e83248bccd734693bc7c60ce4fe98c3f12db7df479f8be45b66abab1ed6', date=datetime.datetime(2024, 6, 21, 22, 58, 19, tzinfo=UTC), memo=None, tx_fee=Decimal('0.00006360'), token=None, index=None), TransferTx(tx_hash='29c38cc2b50b6da5d42f2af92325ea1295fce613b3bd10f6c8205d35f16a9f2d', success=True, from_address='', to_address='ltc1q60ew95dz7a7c8jwszu7luvddkfc2up875jcyql', value=Decimal('1.57064386'), symbol='LTC', confirmations=27504, block_height=2707106, block_hash='9ceb7e83248bccd734693bc7c60ce4fe98c3f12db7df479f8be45b66abab1ed6', date=datetime.datetime(2024, 6, 21, 22, 58, 19, tzinfo=UTC), memo=None, tx_fee=Decimal('0.00006360'), token=None, index=None)]]
        for expected_tx_details, tx_details in zip(expected_txs_details, parsed_responses):
            assert tx_details == expected_tx_details

