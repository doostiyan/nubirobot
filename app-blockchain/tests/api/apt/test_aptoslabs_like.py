import pytest
import datetime
from decimal import Decimal
from unittest import TestCase
from exchange.base.models import Currencies
from exchange.blockchain.api.apt.nodereal_apt import AptosNodeReal
from exchange.blockchain.api.apt.chainbase_apt import AptosChainbase
from exchange.blockchain.api.apt.aptoslabs_apt import AptoslabsAptApi
from exchange.blockchain.api.apt.aptos_explorer_interface import AptosExplorerInterface
from exchange.blockchain.tests.api.general_test.general_test_from_explorer import TestFromExplorer


class TestAptoslabsApiCalls(TestCase):
    api = AptoslabsAptApi
    addresses = ['0x2f4147c01ed25d7a10dc707d2b653c0fc741dc7a948eefa251d641b037885234']
    txs_hash = ['315982941']
    valid_resources = ['0x1::coin::CoinStore<0x1::aptos_coin::AptosCoin>']
    blocks_height = [(33255480, 33255489)]

    @pytest.mark.slow
    def test_get_balance_api(self):
        for address in self.addresses:
            get_balance_response = self.api.get_balance(address)
            assert isinstance(get_balance_response, list)
            for balance in get_balance_response:
                assert isinstance(balance.get('type'), str)
                if balance.get('type') in self.valid_resources:
                    assert isinstance(balance.get('data'), dict)
                    assert isinstance(balance.get('data').get('coin'), dict)
                    assert isinstance(balance.get('data').get('coin').get('value'), str)

    @pytest.mark.slow
    def test_get_block_head_api(self):
        get_block_head_response = self.api.get_block_head()
        assert isinstance(get_block_head_response, dict)
        assert isinstance(get_block_head_response.get('ledger_version'), str)

    @pytest.mark.slow
    def test_get_tx_details_api(self):
        for tx_hash in self.txs_hash:
            get_tx_details_response = self.api.get_tx_details(tx_hash)
            assert isinstance(get_tx_details_response, dict)
            keys2check = [('version', str), ('hash', str), ('type', str), ('success', bool), ('gas_unit_price', str),
                          ('vm_status', str), ('sender', str), ('events', list), ('gas_used', str), ('timestamp', str)]
            for key, value in keys2check:
                assert isinstance(get_tx_details_response.get(key), value)
            keys2check2 = [('function', str), ('type_arguments', list), ('type', str), ('arguments', list)]
            for key, value in keys2check2:
                assert isinstance(get_tx_details_response.get('payload').get(key), value)

    @pytest.mark.slow
    def test_get_address_txs_api(self):
        for address in self.addresses:
            get_address_txs_response = self.api.get_address_txs(address)
            assert isinstance(get_address_txs_response, list)
            for tx in get_address_txs_response:
                assert isinstance(tx, dict)
                keys2check = [('version', str), ('hash', str), ('type', str), ('timestamp', str), ('success', bool),
                              ('vm_status', str), ('payload', dict), ('events', list), ('gas_used', str),
                              ('gas_unit_price', str)]
                for key, value in keys2check:
                    assert isinstance(tx.get(key), value)
                keys2check2 = [('function', str), ('type_arguments', list), ('type', str), ('arguments', list)]
                for key, value in keys2check2:
                    assert isinstance(tx.get('payload').get(key), value)
                for i in range(2):
                    assert isinstance(tx.get('events')[i].get('data').get('amount'), str)
                    assert isinstance(tx.get('events')[i].get('guid').get('account_address'), str)

    @pytest.mark.slow
    def test_get_block_txs_api(self):
        for from_block, to_block in self.blocks_height:
            get_block_txs_response = self.api.get_batch_block_txs(from_block, to_block)
            assert isinstance(get_block_txs_response, list)
            for block in get_block_txs_response:
                assert not isinstance(block, list)
                block = [block]
                for tx in block:
                    if tx.get('type', '') == 'user_transaction':
                        assert isinstance(tx, dict)
                        keys2check = [('version', str), ('hash', str), ('timestamp', str), ('success', bool),
                                      ('vm_status', str), ('payload', dict), ('gas_used', str), ('gas_unit_price', str)]
                        for key, value in keys2check:
                            assert isinstance(tx.get(key), value)
                        keys2check2 = [('function', str), ('type_arguments', list), ('type', str), ('arguments', list)]
                        for key, value in keys2check2:
                            assert isinstance(tx.get('payload').get(key), value)
                        assert isinstance(tx.get('payload').get('arguments')[0], str)
                        assert isinstance(tx.get('payload').get('arguments')[1], str)


class TestAptosChainbase(TestCase):
    api = AptosChainbase
    addresses = ['0x2f4147c01ed25d7a10dc707d2b653c0fc741dc7a948eefa251d641b037885234']
    txs_hash = ['315982941']
    valid_resources = ['0x1::coin::CoinStore<0x1::aptos_coin::AptosCoin>']
    blocks_height = [(33255480, 33255489)]

    @pytest.mark.slow
    def test_get_block_head_api(self):
        get_block_head_response = self.api.get_block_head()
        assert isinstance(get_block_head_response, dict)
        assert isinstance(get_block_head_response.get('ledger_version'), str)

    @pytest.mark.slow
    def test_get_tx_details_api(self):
        for tx_hash in self.txs_hash:
            get_tx_details_response = self.api.get_tx_details(tx_hash)
            assert isinstance(get_tx_details_response, dict)
            keys2check = [('version', str), ('hash', str), ('type', str), ('success', bool), ('gas_unit_price', str),
                          ('vm_status', str), ('sender', str), ('events', list), ('gas_used', str), ('timestamp', str)]
            for key, value in keys2check:
                assert isinstance(get_tx_details_response.get(key), value)
            keys2check2 = [('function', str), ('type_arguments', list), ('type', str), ('arguments', list)]
            for key, value in keys2check2:
                assert isinstance(get_tx_details_response.get('payload').get(key), value)

    @pytest.mark.slow
    def test_get_address_txs_api(self):
        for address in self.addresses:
            get_address_txs_response = self.api.get_address_txs(address)
            assert isinstance(get_address_txs_response, list)
            for tx in get_address_txs_response:
                assert isinstance(tx, dict)
                keys2check = [('version', str), ('hash', str), ('type', str), ('timestamp', str), ('success', bool),
                              ('vm_status', str), ('payload', dict), ('events', list), ('gas_used', str),
                              ('gas_unit_price', str)]
                for key, value in keys2check:
                    assert isinstance(tx.get(key), value)
                keys2check2 = [('function', str), ('type_arguments', list), ('type', str), ('arguments', list)]
                for key, value in keys2check2:
                    assert isinstance(tx.get('payload').get(key), value)
                for i in range(2):
                    assert isinstance(tx.get('events')[i].get('data').get('amount'), str)
                    assert isinstance(tx.get('events')[i].get('guid').get('account_address'), str)

    @pytest.mark.slow
    def test_get_block_txs_api(self):
        for from_block, to_block in self.blocks_height:
            get_block_txs_response = self.api.get_batch_block_txs(from_block, to_block)
            assert isinstance(get_block_txs_response, list)
            for block in get_block_txs_response:
                assert not isinstance(block, list)
                block = [block]
                for tx in block:
                    if tx.get('type', '') == 'user_transaction':
                        assert isinstance(tx, dict)
                        keys2check = [('version', str), ('hash', str), ('timestamp', str), ('success', bool),
                                      ('vm_status', str), ('payload', dict), ('gas_used', str), ('gas_unit_price', str)]
                        for key, value in keys2check:
                            assert isinstance(tx.get(key), value)
                        keys2check2 = [('function', str), ('type_arguments', list), ('type', str), ('arguments', list)]
                        for key, value in keys2check2:
                            assert isinstance(tx.get('payload').get(key), value)
                        assert isinstance(tx.get('payload').get('arguments')[0], str)
                        assert isinstance(tx.get('payload').get('arguments')[1], str)


class TestAptosNodeReal(TestCase):
    api = AptosNodeReal
    addresses = ['0x2f4147c01ed25d7a10dc707d2b653c0fc741dc7a948eefa251d641b037885234']
    txs_hash = ['315982941']
    valid_resources = ['0x1::coin::CoinStore<0x1::aptos_coin::AptosCoin>']

    @pytest.mark.slow
    def test_get_block_head_api(self):
        get_block_head_response = self.api.get_block_head()
        assert isinstance(get_block_head_response, dict)
        assert isinstance(get_block_head_response.get('ledger_version'), str)

    @pytest.mark.slow
    def test_get_tx_details_api(self):
        for tx_hash in self.txs_hash:
            get_tx_details_response = self.api.get_tx_details(tx_hash)
            assert isinstance(get_tx_details_response, dict)
            keys2check = [('version', str), ('hash', str), ('type', str), ('success', bool), ('gas_unit_price', str),
                          ('vm_status', str), ('sender', str), ('events', list), ('gas_used', str), ('timestamp', str)]
            for key, value in keys2check:
                assert isinstance(get_tx_details_response.get(key), value)
            keys2check2 = [('function', str), ('type_arguments', list), ('type', str), ('arguments', list)]
            for key, value in keys2check2:
                assert isinstance(get_tx_details_response.get('payload').get(key), value)

    @pytest.mark.slow
    def test_get_address_txs_api(self):
        for address in self.addresses:
            get_address_txs_response = self.api.get_address_txs(address)
            assert isinstance(get_address_txs_response, list)
            for tx in get_address_txs_response:
                assert isinstance(tx, dict)
                keys2check = [('version', str), ('hash', str), ('type', str), ('timestamp', str), ('success', bool),
                              ('vm_status', str), ('payload', dict), ('events', list), ('gas_used', str),
                              ('gas_unit_price', str)]
                for key, value in keys2check:
                    assert isinstance(tx.get(key), value)
                keys2check2 = [('function', str), ('type_arguments', list), ('type', str), ('arguments', list)]
                for key, value in keys2check2:
                    assert isinstance(tx.get('payload').get(key), value)
                for i in range(2):
                    assert isinstance(tx.get('events')[i].get('data').get('amount'), str)
                    assert isinstance(tx.get('events')[i].get('guid').get('account_address'), str)


class TestAptoslabsFromExplorer(TestFromExplorer):
    api = AptoslabsAptApi  # default
    symbol = 'APT'
    currencies = Currencies.apt
    addresses = ['0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b']
    txs_addresses = ['0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b']
    txs_hash = ['47776435']
    explorerInterface = AptosExplorerInterface

    @classmethod
    def test_get_balance(cls):
        # invalid
        balance_mock_responses1 = [
            [
                {
                    'type': '0x2::account::Account',
                    'data': {
                        'authentication_key': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                        'coin_register_events':
                            {'counter': '2',
                             'guid': {
                                 'id': {'addr': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                        'creation_num': '0'}}},
                        'guid_creation_num': '6',
                        'key_rotation_events': {
                            'counter': '0',
                            'guid': {'id': {
                                'addr': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                'creation_num': '1'}}},
                        'rotation_capability_offer': {'for': {'vec': []}},
                        'sequence_number': '104333',
                        'signer_capability_offer': {'for': {'vec': []}}}},
                {
                    'type': '0x1::coin::Coin<0x6de517a18f003625e7fba9b9dc29'
                            'b310f2e3026bbeb1997b3ada9de1e3cec8d6::opc::OPC>',
                    'data': {'coin': {'value': '6573124800000'},
                             'deposit_events': {'counter': '7', 'guid': {
                                 'id': {'addr': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                        'creation_num': '4'}}},
                             'frozen': False,
                             'withdraw_events': {
                                 'counter': '74421',
                                 'guid': {
                                     'id': {
                                         'addr': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                         'creation_num': '5'}}}}},
                {'type': '0x1::coin::Coin<0x1::aptos_coin::AptosCoin>',
                 'data': {'coin': {'value': '1821477040'},
                          'deposit_events': {'counter': '5', 'guid': {
                              'id': {
                                  'addr': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                  'creation_num': '2'}}},
                          'frozen': False,
                          'withdraw_events': {
                              'counter': '29911',
                              'guid': {
                                  'id': {
                                      'addr': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                      'creation_num': '3'}}}}
                 }
            ]
        ]
        expected_balances1 = [
            {'address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
             'balance': Decimal('0'),
             'received': Decimal('0'),
             'rewarded': Decimal('0'),
             'sent': Decimal('0')}
        ]
        cls.get_balance(balance_mock_responses1, expected_balances1)

        # valid1
        cls.addresses = ['0x21ddba785f3ae9c6f03664ab07e9ad83595a0fa5ca556cec2b9d9e7100db0f07']
        balance_mock_responses2 = [
            [
                {'type': '0x1::account::Account',
                 'data': {'authentication_key': '0x21ddba785f3ae9c6f03664ab07e9ad83595a0fa5ca556cec2b9d9e7100db0f07',
                          'coin_register_events': {'counter': '2', 'guid': {
                              'id': {'addr': '0x21ddba785f3ae9c6f03664ab07e9ad83595a0fa5ca556cec2b9d9e7100db0f07',
                                     'creation_num': '0'}}}, 'guid_creation_num': '6',
                          'key_rotation_events':
                              {'counter': '0',
                               'guid': {'id': {
                                   'addr': '0x21ddba785f3ae9c6f03664ab07e9ad83595a0fa5ca556cec2b9d9e7100db0f07',
                                   'creation_num': '1'}}},
                          'rotation_capability_offer': {'for': {'vec': []}}, 'sequence_number': '104333',
                          'signer_capability_offer': {'for': {'vec': []}}}},
                {
                    'type': '0x1::coin::CoinStore<0x6de517a18f003625e7fba9b9dc29b310f2e3026bbeb1997b3ada9de1e3cec8'
                            'd6::opc::OPC>',
                    'data': {'coin': {'value': '6573124800000'}, 'deposit_events': {'counter': '7', 'guid': {
                        'id': {'addr': '0x21ddba785f3ae9c6f03664ab07e9ad83595a0fa5ca556cec2b9d9e7100db0f07',
                               'creation_num': '4'}}}, 'frozen': False,
                             'withdraw_events': {'counter': '74421', 'guid': {
                                 'id': {'addr': '0x21ddba785f3ae9c6f03664ab07e9ad83595a0fa5ca556cec2b9d9e7100db0f07',
                                        'creation_num': '5'}}}}},
                {'type': '0x1::coin::CoinStore<0x1::aptos_coin::AptosCoin>',
                 'data': {'coin': {'value': '1821477040'},
                          'deposit_events': {'counter': '5', 'guid': {'id': {
                              'addr': '0x21ddba785f3ae9c6f03664ab07e9ad83595a0fa5ca556cec2b9d9e7100db0f07',
                              'creation_num': '2'}}}, 'frozen': False,
                          'withdraw_events': {'counter': '29911', 'guid': {'id': {
                              'addr': '0x21ddba785f3ae9c6f03664ab07e9ad83595a0fa5ca556cec2b9d9e7100db0f07',
                              'creation_num': '3'}}}}}
            ]
        ]
        expected_balances2 = [
            {
                'address': '0x21ddba785f3ae9c6f03664ab07e9ad83595a0fa5ca556cec2b9d9e7100db0f07',
                'balance': Decimal('18.21477040'), 'received': Decimal('18.21477040'), 'sent': Decimal('0'),
                'rewarded': Decimal('0')
            }
        ]
        cls.get_balance(balance_mock_responses2, expected_balances2)

        # valid2
        cls.addresses = ['0x6de517a18f003625e7fba9b9dc29b310f2e3026bbeb1997b3ada9de1e3cec8d6']
        balance_mock_responses3 = [
            [
                {'type': '0x1::account::Account',
                 'data': {'authentication_key': '0x6de517a18f003625e7fba9b9dc29b310f2e3026bbeb1997b3ada9de1e3cec8d6',
                          'coin_register_events': {'counter': '2', 'guid': {
                              'id': {'addr': '0x6de517a18f003625e7fba9b9dc29b310f2e3026bbeb1997b3ada9de1e3cec8d6',
                                     'creation_num': '0'}}}, 'guid_creation_num': '6',
                          'key_rotation_events': {
                              'counter': '0',
                              'guid': {'id': {
                                  'addr': '0x6de517a18f003625e7fba9b9dc29b310f2e3026bbeb1997b3ada9de1e3cec8d6',
                                  'creation_num': '1'}}},
                          'rotation_capability_offer': {'for': {'vec': []}}, 'sequence_number': '118221',
                          'signer_capability_offer': {'for': {'vec': []}}}},
                {
                    'type': '0x1::code::PackageRegistry',
                    'data': {
                        'packages': [
                            {'deps': [{'account': '0x1', 'package_name': 'AptosFramework'},
                                      {'account': '0x1', 'package_name': 'AptosStdlib'},
                                      {'account': '0x1', 'package_name': 'MoveStdlib'}], 'extension': {'vec': []},
                             'manifest': '0x1f8b08000000000002ff3d4e4d6bc3300cbdfb5784dc97da31'
                                         '4deac30e63b0eb762f65c892524c13cbd85db731f6df1b435bd041'
                                         '7a4fef639f004f70e4838ab070f3dcb4ef1faf1262ab2e9c4b9058'
                                         '21d3e94eb7ea2b1d33107f269903fe56026549700e7ee656a93d106'
                                         '52e85cb4149c2caeb9f81786b4630bb496b3bf45b1e270fce3bc2de7'
                                         '96bf4d4b3d5fde03d7be3dce82d103862c316197734545fe2c4913862'
                                         'a8d62fe92ce52daf6dbf259fd694bf661684b9e675dd661da81f4f2899'
                                         '6feb2217de4c77c90d7cdc6df3afaefe587b6d07010000',
                             'modules': [
                                 {'extension': {'vec': []}, 'name': 'opc', 'source': '0x', 'source_map': '0x'}],
                             'name': 'OPCoin',
                             'source_digest': '3F53E41C4FD27343491C4D308FBFA64902B48C1817221724DA72BBA9B622292C',
                             'upgrade_number': '0', 'upgrade_policy': {'policy': 1}}]}},
                {
                    'type': '0x1::coin::CoinInfo<0x6de517a18f003625e7fba9b9dc29b310f'
                            '2e3026bbeb1997b3ada9de1e3cec8d6::opc::OPC>',
                    'data': {'decimals': 6, 'name': 'Ocean Park Coin',
                             'supply': {'vec': [{'aggregator': {'vec': []}, 'integer': {
                                 'vec': [
                                     {'limit': '340282366920938463463374607431768211455',
                                      'value': '566775339200000'}]}}]},
                             'symbol': 'OPC'}},
                {
                    'type': '0x1::coin::CoinStore<0x6de517a18f003625e7fba9b9dc29b310f2e3026bb'
                            'eb1997b3ada9de1e3cec8d6::opc::OPC>',
                    'data': {'coin': {'value': '4869133080000'}, 'deposit_events': {'counter': '11', 'guid': {
                        'id': {'addr': '0x6de517a18f003625e7fba9b9dc29b310f2e3026bbeb1997b3ada9de1e3cec8d6',
                               'creation_num': '4'}}}, 'frozen': False,
                             'withdraw_events': {'counter': '82969', 'guid': {
                                 'id': {'addr': '0x6de517a18f003625e7fba9b9dc29b310f2e3026bbeb1997b3ada9de1e3cec8d6',
                                        'creation_num': '5'}}}}},
                {
                    'type': '0x1::managed_coin::Capabilities<0x6de517a18f003625e7fba9b9dc29'
                            'b310f2e3026bbeb1997b3ada9de1e3cec8d6::opc::OPC>',
                    'data': {'burn_cap': {'dummy_field': False}, 'freeze_cap': {'dummy_field': False},
                             'mint_cap': {'dummy_field': False}}},
                {'type': '0x1::coin::CoinStore<0x1::aptos_coin::AptosCoin>',
                 'data': {'coin': {'value': '3359153780'},
                          'deposit_events': {'counter': '7', 'guid': {
                              'id': {
                                  'addr': '0x6de517a18f003625e7fba9b9dc29b310f2e3026bbeb1997b3ada9de1e3cec8d6',
                                  'creation_num': '2'}}}, 'frozen': False,
                          'withdraw_events': {'counter': '34589', 'guid': {
                              'id': {
                                  'addr': '0x6de517a18f003625e7fba9b9dc29b310f2e3026bbeb1997b3ada9de1e3cec8d6',
                                  'creation_num': '3'}}}}}
            ]
        ]
        expected_balances3 = [
            {
                'address': '0x6de517a18f003625e7fba9b9dc29b310f2e3026bbeb1997b3ada9de1e3cec8d6',
                'balance': Decimal('33.59153780'), 'received': Decimal('33.59153780'), 'sent': Decimal('0'),
                'rewarded': Decimal('0')
            }
        ]
        cls.get_balance(balance_mock_responses3, expected_balances3)

    @classmethod
    def test_get_tx_details(cls):
        # valid
        tx_details_mock_responses1 = [
            {
                'chain_id': 1, 'epoch': '705', 'ledger_version': '47781050', 'oldest_ledger_version': '0',
                'ledger_timestamp': '1670671201794529', 'node_role': 'full_node', 'oldest_block_height': '0',
                'block_height': '16366603', 'git_hash': 'd7fe6d2f68e6b25bddce8e13546e0b24076f47a5'
            },
            {
                'version': '47776435',
                'hash': '0x19ce3efa3c0a9acde71fd4bd1c02370b58b5dc3e6990cefc6be54443f94462f8',
                'state_change_hash': '0x5bfc0f61e2d91de9bcb523bae4f66402b6a9d5bcbbe0d2b36e61bd2a838f11f6',
                'event_root_hash': '0x0c925bdd6c8b5163f68d3fbc1f345db84725b2e54f2ee1dc47948970f78bcf19',
                'state_checkpoint_hash': None,
                'gas_used': '585',
                'success': True,
                'vm_status': 'Executed successfully',
                'accumulator_root_hash': '0xfee40b82992f344ade7af8b9f9d41e872539799cdaffadfaec4031ab1f7e4942',
                'changes': [
                    {
                        'address': '0xe2a19dc767bf161e04eddb62167edf061763b5e0de7019b742782a908861cae',
                        'state_key_hash': '0xcfa666ff2b0f7976e38dec34c1ea7817bbe009767801705fbba9cec9abe33ce1',
                        'data': {'type': '0x1::coin::CoinStore<0x1::aptos_coin::AptosCoin>',
                                 'data': {'coin': {'value': '2309005738'},
                                          'deposit_events': {
                                              'counter': '15',
                                              'guid': {
                                                  'id': {
                                                      'addr': '0xe2a19dc767bf161e04eddb62167edf061763b'
                                                              '5e0de7019b742782a908861cae',
                                                      'creation_num': '2'}}},
                                          'frozen': False,
                                          'withdraw_events': {
                                              'counter': '12',
                                              'guid': {'id': {
                                                  'addr': '0xe2a19dc767bf161e04eddb62167edf061763b5e0'
                                                          'de7019b742782a908861cae',
                                                  'creation_num': '3'}}}}},
                        'type': 'write_resource'
                    },
                    {
                        'address': '0x2f4147c01ed25d7a10dc707d2b653c0fc741dc7a948eefa251d641b037885234',
                        'state_key_hash': '0x90038421aabd68c8a6222db334b12860fcc5e422470843b1075a0687cb5c0756',
                        'data': {'type': '0x1::coin::CoinStore<0x1::aptos_coin::AptosCoin>',
                                 'data': {'coin': {'value': '1941500'},
                                          'deposit_events': {
                                              'counter': '24',
                                              'guid': {'id': {
                                                  'addr': '0x2f4147c01ed25d7a10dc707d2b653c0fc741d'
                                                          'c7a948eefa251d641b037885234',
                                                  'creation_num': '2'}}},
                                          'frozen': False,
                                          'withdraw_events': {'counter': '24', 'guid': {
                                              'id': {
                                                  'addr': '0x2f4147c01ed25d7a10dc707d2b653c0fc741dc'
                                                          '7a948eefa251d641b037885234',
                                                  'creation_num': '3'}}}}}, 'type': 'write_resource'},
                    {'address': '0x2f4147c01ed25d7a10dc707d2b653c0fc741dc7a948eefa251d641b037885234',
                     'state_key_hash': '0x3a3985a46412358d85b1c903aa6ec3335c0ec52fe92a6d69b1ea1f0a576d8a53',
                     'data': {'type': '0x1::account::Account',
                              'data': {
                                  'authentication_key': '0x2f4147c01ed25d7a10dc707d2b653c0fc741d'
                                                        'c7a948eefa251d641b037885234',
                                  'coin_register_events': {'counter': '2', 'guid': {
                                      'id': {
                                          'addr': '0x2f4147c01ed25d7a10dc707d2b653c0fc741dc7a948eefa251d641b037885234',
                                          'creation_num': '0'}}}, 'guid_creation_num': '6',
                                  'key_rotation_events': {'counter': '0', 'guid': {
                                      'id': {
                                          'addr': '0x2f4147c01ed25d7a10dc707d2b653c0fc741dc7a948eefa251d641b037885234',
                                          'creation_num': '1'}}}, 'rotation_capability_offer': {'for': {'vec': []}},
                                  'sequence_number': '30', 'signer_capability_offer': {'for': {'vec': []}}}},
                     'type': 'write_resource'},
                    {'state_key_hash': '0x6e4b28d40f98a106a65163530924c0dcb40c1349d3aa915d108b4d6cfc1ddb19',
                     'handle': '0x1b854694ae746cdbd8d44186ca4929b2b337df21d1c74633be19b2710552fdca',
                     'key': '0x0619dc29a0aac8fa146714058e8dd6d2d0f3bdf5f6331907bf91f3acd81e6935',
                     'value': '0x746e5ae4038a66010000000000000000', 'data': None, 'type': 'write_table_item'}],
                'sender': '0x2f4147c01ed25d7a10dc707d2b653c0fc741dc7a948eefa251d641b037885234',
                'sequence_number': '29',
                'max_gas_amount': '3000',
                'gas_unit_price': '100',
                'expiration_timestamp_secs': '1670671869',
                'payload': {
                    'function': '0x1::aptos_account::transfer', 'type_arguments': [],
                    'arguments': ['0xe2a19dc767bf161e04eddb62167edf061763b5e0de7019b742782a908861cae', '2307764238'],
                    'type': 'entry_function_payload'},
                'signature': {'public_key': '0x00a229352fdd7cab01f4c8c7a283c0eaab671470a7ab8cd2223caaffa2308498',
                              'signature': '0x60754ea27c2c06422ac56193ccd4bfd73e5f89afa'
                                           '412a07c664729e4daa08f01ea0acaa17ba38529f3de2'
                                           'debe52efd24d3c7ca4eff08f054b56988c30ebedb05',
                              'type': 'ed25519_signature'},
                'events': [{
                    'guid': {'creation_number': '3',
                             'account_address': '0x2f4147c01ed25d7a10dc707d2b653c0fc741dc7a948eefa251d641b037885234'},
                    'sequence_number': '23', 'type': '0x1::coin::WithdrawEvent',
                    'data': {'amount': '2307764238'}}, {
                    'guid': {
                        'creation_number': '2',
                        'account_address': '0xe2a19dc767bf161e04eddb62167edf061763b5e0de7019b742782a908861cae'},
                    'sequence_number': '14', 'type': '0x1::coin::DepositEvent',
                    'data': {'amount': '2307764238'}}],
                'timestamp': '1670671272417347',
                'type': 'user_transaction'}
        ]
        expected_txs_details1 = [
            {
                'success': True,
                'block': 47776435,
                'date': datetime.datetime(2022, 12, 10, 11, 21, 12, 417347, tzinfo=datetime.timezone.utc),
                'raw': None,
                'inputs': [],
                'outputs': [],
                'transfers': [
                    {'type': 'MainCoin',
                     'symbol': 'APT',
                     'currency': Currencies.apt,
                     'to': '0x0e2a19dc767bf161e04eddb62167edf061763b5e0de7019b742782a908861cae',
                     'value': Decimal('23.07764238'),
                     'is_valid': True,
                     'token': None,
                     'memo': None,
                     'from': '0x2f4147c01ed25d7a10dc707d2b653c0fc741dc7a948eefa251d641b037885234'}
                ],
                'fees': Decimal('0.00058500'),
                'memo': None,
                'confirmations': 4615,
                'hash': '47776435'
            }
        ]
        cls.get_tx_details(tx_details_mock_responses1, expected_txs_details1)

        # invalid
        tx_details_mock_responses2 = [
            {
                'chain_id': 1, 'epoch': '705', 'ledger_version': '47781050', 'oldest_ledger_version': '0',
                'ledger_timestamp': '1670671201794529', 'node_role': 'full_node', 'oldest_block_height': '0',
                'block_height': '16366603', 'git_hash': 'd7fe6d2f68e6b25bddce8e13546e0b24076f47a5'
            },
            {
                'version': '47776435',
                'hash': '0x19ce3efa3c0a9acde71fd4bd1c02370b58b5dc3e6990cefc6be54443f94462f8',
                'state_change_hash': '0x5bfc0f61e2d91de9bcb523bae4f66402b6a9d5bcbbe0d2b36e61bd2a838f11f6',
                'event_root_hash': '0x0c925bdd6c8b5163f68d3fbc1f345db84725b2e54f2ee1dc47948970f78bcf19',
                'state_checkpoint_hash': None,
                'gas_used': '585',
                'success': True,
                'vm_status': 'Executed successfully',
                'accumulator_root_hash': '0xfee40b82992f344ade7af8b9f9d41e872539799cdaffadfaec4031ab1f7e4942',
                'changes': [
                    {
                        'address': '0xe2a19dc767bf161e04eddb62167edf061763b5e0de7019b742782a908861cae',
                        'state_key_hash': '0xcfa666ff2b0f7976e38dec34c1ea7817bbe009767801705fbba9cec9abe33ce1',
                        'data': {'type': '0x1::coin::CoinStore<0x1::aptos_coin::AptosCoin>',
                                 'data': {'coin': {'value': '2309005738'},
                                          'deposit_events': {
                                              'counter': '15',
                                              'guid': {
                                                  'id': {
                                                      'addr': '0xe2a19dc767bf161e04eddb62167edf061763b'
                                                              '5e0de7019b742782a908861cae',
                                                      'creation_num': '2'}}},
                                          'frozen': False,
                                          'withdraw_events': {
                                              'counter': '12',
                                              'guid': {'id': {
                                                  'addr': '0xe2a19dc767bf161e04eddb62167edf061763b5e0'
                                                          'de7019b742782a908861cae',
                                                  'creation_num': '3'}}}}},
                        'type': 'write_resource'
                    },
                    {
                        'address': '0x2f4147c01ed25d7a10dc707d2b653c0fc741dc7a948eefa251d641b037885234',
                        'state_key_hash': '0x90038421aabd68c8a6222db334b12860fcc5e422470843b1075a0687cb5c0756',
                        'data': {'type': '0x1::coin::CoinStore<0x1::aptos_coin::AptosCoin>',
                                 'data': {'coin': {'value': '1941500'},
                                          'deposit_events': {
                                              'counter': '24',
                                              'guid': {'id': {
                                                  'addr': '0x2f4147c01ed25d7a10dc707d2b653c0fc741d'
                                                          'c7a948eefa251d641b037885234',
                                                  'creation_num': '2'}}},
                                          'frozen': False,
                                          'withdraw_events': {'counter': '24', 'guid': {
                                              'id': {
                                                  'addr': '0x2f4147c01ed25d7a10dc707d2b653c0fc741dc'
                                                          '7a948eefa251d641b037885234',
                                                  'creation_num': '3'}}}}}, 'type': 'write_resource'},
                    {'address': '0x2f4147c01ed25d7a10dc707d2b653c0fc741dc7a948eefa251d641b037885234',
                     'state_key_hash': '0x3a3985a46412358d85b1c903aa6ec3335c0ec52fe92a6d69b1ea1f0a576d8a53',
                     'data': {'type': '0x1::account::Account',
                              'data': {
                                  'authentication_key': '0x2f4147c01ed25d7a10dc707d2b653c0fc741d'
                                                        'c7a948eefa251d641b037885234',
                                  'coin_register_events': {'counter': '2', 'guid': {
                                      'id': {
                                          'addr': '0x2f4147c01ed25d7a10dc707d2b653c0fc741dc7a948eefa251d641b037885234',
                                          'creation_num': '0'}}}, 'guid_creation_num': '6',
                                  'key_rotation_events': {'counter': '0', 'guid': {
                                      'id': {
                                          'addr': '0x2f4147c01ed25d7a10dc707d2b653c0fc741dc7a948eefa251d641b037885234',
                                          'creation_num': '1'}}}, 'rotation_capability_offer': {'for': {'vec': []}},
                                  'sequence_number': '30', 'signer_capability_offer': {'for': {'vec': []}}}},
                     'type': 'write_resource'},
                    {'state_key_hash': '0x6e4b28d40f98a106a65163530924c0dcb40c1349d3aa915d108b4d6cfc1ddb19',
                     'handle': '0x1b854694ae746cdbd8d44186ca4929b2b337df21d1c74633be19b2710552fdca',
                     'key': '0x0619dc29a0aac8fa146714058e8dd6d2d0f3bdf5f6331907bf91f3acd81e6935',
                     'value': '0x746e5ae4038a66010000000000000000', 'data': None, 'type': 'write_table_item'}],
                'sender': '0x2f4147c01ed25d7a10dc707d2b653c0fc741dc7a948eefa251d641b037885234',
                'sequence_number': '29',
                'max_gas_amount': '3000',
                'gas_unit_price': '100',
                'expiration_timestamp_secs': '1670671869',
                'payload': {
                    'function': '0x1::aptos_account::transfer', 'type_arguments': [],
                    'arguments': ['0xe2a19dc767bf161e04eddb62167edf061763b5e0de7019b742782a908861cae', '2307764238'],
                    'type': 'entry_function_payload'},
                'signature': {'public_key': '0x00a229352fdd7cab01f4c8c7a283c0eaab671470a7ab8cd2223caaffa2308498',
                              'signature': '0x60754ea27c2c06422ac56193ccd4bfd73e5f89afa'
                                           '412a07c664729e4daa08f01ea0acaa17ba38529f3de2'
                                           'debe52efd24d3c7ca4eff08f054b56988c30ebedb05',
                              'type': 'ed25519_signature'},
                'events': [
                    {
                        'guid': {
                            'creation_number': '3',
                            'account_address': '0x2f4147c01ed25d7a10dc707d2b653c0fc741dc7a948eefa251d641b037885234'},
                        'sequence_number': '23', 'type': '0x1::coin::WithdrawEvent',
                        'data': {'amount': '2307764238'}},
                    {
                        'guid': {
                            'creation_number': '2',
                            'account_address': '0xe2a19dc767bf161e04eddb62167edf061763b5e0de7019b742782a908861cae'},
                        'sequence_number': '14', 'type': '0x1::coin::DepositEvent',
                        'data': {'amount': '2307764238'}}],
                'timestamp': '1670671272417347',
                'type': 'mint'}
        ]
        expected_txs_details2 = [{'success': False}]
        cls.get_tx_details(tx_details_mock_responses2, expected_txs_details2)

        # invalid
        tx_details_mock_responses3 = [
            {
                'chain_id': 1, 'epoch': '705', 'ledger_version': '47781050', 'oldest_ledger_version': '0',
                'ledger_timestamp': '1670671201794529', 'node_role': 'full_node', 'oldest_block_height': '0',
                'block_height': '16366603', 'git_hash': 'd7fe6d2f68e6b25bddce8e13546e0b24076f47a5'
            },
            {
                'version': '47776435',
                'hash': '0x19ce3efa3c0a9acde71fd4bd1c02370b58b5dc3e6990cefc6be54443f94462f8',
                'state_change_hash': '0x5bfc0f61e2d91de9bcb523bae4f66402b6a9d5bcbbe0d2b36e61bd2a838f11f6',
                'event_root_hash': '0x0c925bdd6c8b5163f68d3fbc1f345db84725b2e54f2ee1dc47948970f78bcf19',
                'state_checkpoint_hash': None,
                'gas_used': '585',
                'success': True,
                'vm_status': 'Executed successfully',
                'accumulator_root_hash': '0xfee40b82992f344ade7af8b9f9d41e872539799cdaffadfaec4031ab1f7e4942',
                'changes': [
                    {
                        'address': '0xe2a19dc767bf161e04eddb62167edf061763b5e0de7019b742782a908861cae',
                        'state_key_hash': '0xcfa666ff2b0f7976e38dec34c1ea7817bbe009767801705fbba9cec9abe33ce1',
                        'data': {'type': '0x1::coin::CoinStore<0x1::aptos_coin::AptosCoin>',
                                 'data': {'coin': {'value': '2309005738'},
                                          'deposit_events': {
                                              'counter': '15',
                                              'guid': {
                                                  'id': {
                                                      'addr': '0xe2a19dc767bf161e04eddb62167edf061763b'
                                                              '5e0de7019b742782a908861cae',
                                                      'creation_num': '2'}}},
                                          'frozen': False,
                                          'withdraw_events': {
                                              'counter': '12',
                                              'guid': {'id': {
                                                  'addr': '0xe2a19dc767bf161e04eddb62167edf061763b5e0'
                                                          'de7019b742782a908861cae',
                                                  'creation_num': '3'}}}}},
                        'type': 'write_resource'
                    },
                    {
                        'address': '0x2f4147c01ed25d7a10dc707d2b653c0fc741dc7a948eefa251d641b037885234',
                        'state_key_hash': '0x90038421aabd68c8a6222db334b12860fcc5e422470843b1075a0687cb5c0756',
                        'data': {'type': '0x1::coin::CoinStore<0x1::aptos_coin::AptosCoin>',
                                 'data': {'coin': {'value': '1941500'},
                                          'deposit_events': {
                                              'counter': '24',
                                              'guid': {'id': {
                                                  'addr': '0x2f4147c01ed25d7a10dc707d2b653c0fc741d'
                                                          'c7a948eefa251d641b037885234',
                                                  'creation_num': '2'}}},
                                          'frozen': False,
                                          'withdraw_events': {'counter': '24', 'guid': {
                                              'id': {
                                                  'addr': '0x2f4147c01ed25d7a10dc707d2b653c0fc741dc'
                                                          '7a948eefa251d641b037885234',
                                                  'creation_num': '3'}}}}}, 'type': 'write_resource'},
                    {'address': '0x2f4147c01ed25d7a10dc707d2b653c0fc741dc7a948eefa251d641b037885234',
                     'state_key_hash': '0x3a3985a46412358d85b1c903aa6ec3335c0ec52fe92a6d69b1ea1f0a576d8a53',
                     'data': {'type': '0x1::account::Account',
                              'data': {
                                  'authentication_key': '0x2f4147c01ed25d7a10dc707d2b653c0fc741d'
                                                        'c7a948eefa251d641b037885234',
                                  'coin_register_events': {'counter': '2', 'guid': {
                                      'id': {
                                          'addr': '0x2f4147c01ed25d7a10dc707d2b653c0fc741dc7a948eefa251d641b037885234',
                                          'creation_num': '0'}}}, 'guid_creation_num': '6',
                                  'key_rotation_events': {'counter': '0', 'guid': {
                                      'id': {
                                          'addr': '0x2f4147c01ed25d7a10dc707d2b653c0fc741dc7a948eefa251d641b037885234',
                                          'creation_num': '1'}}}, 'rotation_capability_offer': {'for': {'vec': []}},
                                  'sequence_number': '30', 'signer_capability_offer': {'for': {'vec': []}}}},
                     'type': 'write_resource'},
                    {'state_key_hash': '0x6e4b28d40f98a106a65163530924c0dcb40c1349d3aa915d108b4d6cfc1ddb19',
                     'handle': '0x1b854694ae746cdbd8d44186ca4929b2b337df21d1c74633be19b2710552fdca',
                     'key': '0x0619dc29a0aac8fa146714058e8dd6d2d0f3bdf5f6331907bf91f3acd81e6935',
                     'value': '0x746e5ae4038a66010000000000000000', 'data': None, 'type': 'write_table_item'}],
                'sender': '0x2f4147c01ed25d7a10dc707d2b653c0fc741dc7a948eefa251d641b037885234',
                'sequence_number': '29',
                'max_gas_amount': '3000',
                'gas_unit_price': '100',
                'expiration_timestamp_secs': '1670671869',
                'payload': {
                    'function': '0x1::aptos_account::swap', 'type_arguments': [],
                    'arguments': ['0xe2a19dc767bf161e04eddb62167edf061763b5e0de7019b742782a908861cae', '2307764238'],
                    'type': 'entry_function_payload'},
                'signature': {'public_key': '0x00a229352fdd7cab01f4c8c7a283c0eaab671470a7ab8cd2223caaffa2308498',
                              'signature': '0x60754ea27c2c06422ac56193ccd4bfd73e5f89afa'
                                           '412a07c664729e4daa08f01ea0acaa17ba38529f3de2'
                                           'debe52efd24d3c7ca4eff08f054b56988c30ebedb05',
                              'type': 'ed25519_signature'},
                'events': [
                    {
                        'guid': {
                            'creation_number': '3',
                            'account_address': '0x2f4147c01ed25d7a10dc707d2b653c0fc741dc7a948eefa251d641b037885234'},
                        'sequence_number': '23', 'type': '0x1::coin::WithdrawEvent',
                        'data': {'amount': '2307764238'}},
                    {
                        'guid': {
                            'creation_number': '2',
                            'account_address': '0xe2a19dc767bf161e04eddb62167edf061763b5e0de7019b742782a908861cae'},
                        'sequence_number': '14', 'type': '0x1::coin::DepositEvent',
                        'data': {'amount': '2307764238'}}],
                'timestamp': '1670671272417347',
                'type': 'user_transaction'}
        ]
        expected_txs_details3 = [{'success': False}]
        cls.get_tx_details(tx_details_mock_responses3, expected_txs_details3)

        # invalid
        tx_details_mock_responses4 = [
            {
                'chain_id': 1, 'epoch': '705', 'ledger_version': '47781050', 'oldest_ledger_version': '0',
                'ledger_timestamp': '1670671201794529', 'node_role': 'full_node', 'oldest_block_height': '0',
                'block_height': '16366603', 'git_hash': 'd7fe6d2f68e6b25bddce8e13546e0b24076f47a5'
            },
            {
                'version': '47776435',
                'hash': '0x19ce3efa3c0a9acde71fd4bd1c02370b58b5dc3e6990cefc6be54443f94462f8',
                'state_change_hash': '0x5bfc0f61e2d91de9bcb523bae4f66402b6a9d5bcbbe0d2b36e61bd2a838f11f6',
                'event_root_hash': '0x0c925bdd6c8b5163f68d3fbc1f345db84725b2e54f2ee1dc47948970f78bcf19',
                'state_checkpoint_hash': None,
                'gas_used': '585',
                'success': True,
                'vm_status': 'Failed',
                'accumulator_root_hash': '0xfee40b82992f344ade7af8b9f9d41e872539799cdaffadfaec4031ab1f7e4942',
                'changes': [
                    {
                        'address': '0xe2a19dc767bf161e04eddb62167edf061763b5e0de7019b742782a908861cae',
                        'state_key_hash': '0xcfa666ff2b0f7976e38dec34c1ea7817bbe009767801705fbba9cec9abe33ce1',
                        'data': {'type': '0x1::coin::CoinStore<0x1::aptos_coin::AptosCoin>',
                                 'data': {'coin': {'value': '2309005738'},
                                          'deposit_events': {
                                              'counter': '15',
                                              'guid': {
                                                  'id': {
                                                      'addr': '0xe2a19dc767bf161e04eddb62167edf061763b'
                                                              '5e0de7019b742782a908861cae',
                                                      'creation_num': '2'}}},
                                          'frozen': False,
                                          'withdraw_events': {
                                              'counter': '12',
                                              'guid': {'id': {
                                                  'addr': '0xe2a19dc767bf161e04eddb62167edf061763b5e0'
                                                          'de7019b742782a908861cae',
                                                  'creation_num': '3'}}}}},
                        'type': 'write_resource'
                    },
                    {
                        'address': '0x2f4147c01ed25d7a10dc707d2b653c0fc741dc7a948eefa251d641b037885234',
                        'state_key_hash': '0x90038421aabd68c8a6222db334b12860fcc5e422470843b1075a0687cb5c0756',
                        'data': {'type': '0x1::coin::CoinStore<0x1::aptos_coin::AptosCoin>',
                                 'data': {'coin': {'value': '1941500'},
                                          'deposit_events': {
                                              'counter': '24',
                                              'guid': {'id': {
                                                  'addr': '0x2f4147c01ed25d7a10dc707d2b653c0fc741d'
                                                          'c7a948eefa251d641b037885234',
                                                  'creation_num': '2'}}},
                                          'frozen': False,
                                          'withdraw_events': {'counter': '24', 'guid': {
                                              'id': {
                                                  'addr': '0x2f4147c01ed25d7a10dc707d2b653c0fc741dc'
                                                          '7a948eefa251d641b037885234',
                                                  'creation_num': '3'}}}}}, 'type': 'write_resource'},
                    {'address': '0x2f4147c01ed25d7a10dc707d2b653c0fc741dc7a948eefa251d641b037885234',
                     'state_key_hash': '0x3a3985a46412358d85b1c903aa6ec3335c0ec52fe92a6d69b1ea1f0a576d8a53',
                     'data': {'type': '0x1::account::Account',
                              'data': {
                                  'authentication_key': '0x2f4147c01ed25d7a10dc707d2b653c0fc741d'
                                                        'c7a948eefa251d641b037885234',
                                  'coin_register_events': {'counter': '2', 'guid': {
                                      'id': {
                                          'addr': '0x2f4147c01ed25d7a10dc707d2b653c0fc741dc7a948eefa251d641b037885234',
                                          'creation_num': '0'}}}, 'guid_creation_num': '6',
                                  'key_rotation_events': {'counter': '0', 'guid': {
                                      'id': {
                                          'addr': '0x2f4147c01ed25d7a10dc707d2b653c0fc741dc7a948eefa251d641b037885234',
                                          'creation_num': '1'}}}, 'rotation_capability_offer': {'for': {'vec': []}},
                                  'sequence_number': '30', 'signer_capability_offer': {'for': {'vec': []}}}},
                     'type': 'write_resource'},
                    {'state_key_hash': '0x6e4b28d40f98a106a65163530924c0dcb40c1349d3aa915d108b4d6cfc1ddb19',
                     'handle': '0x1b854694ae746cdbd8d44186ca4929b2b337df21d1c74633be19b2710552fdca',
                     'key': '0x0619dc29a0aac8fa146714058e8dd6d2d0f3bdf5f6331907bf91f3acd81e6935',
                     'value': '0x746e5ae4038a66010000000000000000', 'data': None, 'type': 'write_table_item'}],
                'sender': '0x2f4147c01ed25d7a10dc707d2b653c0fc741dc7a948eefa251d641b037885234',
                'sequence_number': '29',
                'max_gas_amount': '3000',
                'gas_unit_price': '100',
                'expiration_timestamp_secs': '1670671869',
                'payload': {
                    'function': '0x1::aptos_account::transfer', 'type_arguments': [],
                    'arguments': ['0xe2a19dc767bf161e04eddb62167edf061763b5e0de7019b742782a908861cae', '2307764238'],
                    'type': 'entry_function_payload'},
                'signature': {'public_key': '0x00a229352fdd7cab01f4c8c7a283c0eaab671470a7ab8cd2223caaffa2308498',
                              'signature': '0x60754ea27c2c06422ac56193ccd4bfd73e5f89afa'
                                           '412a07c664729e4daa08f01ea0acaa17ba38529f3de2'
                                           'debe52efd24d3c7ca4eff08f054b56988c30ebedb05',
                              'type': 'ed25519_signature'},
                'events': [
                    {
                        'guid': {
                            'creation_number': '3',
                            'account_address': '0x2f4147c01ed25d7a10dc707d2b653c0fc741dc7a948eefa251d641b037885234'},
                        'sequence_number': '23', 'type': '0x1::coin::WithdrawEvent',
                        'data': {'amount': '2307764238'}},
                    {
                        'guid': {
                            'creation_number': '2',
                            'account_address': '0xe2a19dc767bf161e04eddb62167edf061763b5e0de7019b742782a908861cae'},
                        'sequence_number': '14', 'type': '0x1::coin::DepositEvent',
                        'data': {'amount': '2307764238'}}],
                'timestamp': '1670671272417347',
                'type': 'user_transaction'}
        ]
        expected_txs_details4 = [{'success': False}]
        cls.get_tx_details(tx_details_mock_responses4, expected_txs_details4)

    @classmethod
    def test_get_address_txs(cls):
        address_txs_mock_response = [
            {
                'chain_id': 1, 'epoch': '705', 'ledger_version': '47777119', 'oldest_ledger_version': '0',
                'ledger_timestamp': '1670671201794529', 'node_role': 'full_node', 'oldest_block_height': '0',
                'block_height': '16366603', 'git_hash': 'd7fe6d2f68e6b25bddce8e13546e0b24076f47a5'
            },
            [{
                'version': '11251017',
                'hash': '0xfcea7ab616c83e8df0c9eb50c3fb5b5f2b434fc59abd5e011d785e198e41c438',
                'state_change_hash': '0xca27ffab257ea2d45c6c080b423bb2302303d68115dcfe1167b7c69f0f77635f',
                'event_root_hash': '0x55333db79820731cc0f798e2d4a3ace2b4c16850e97fef9f32a2a10ce5fad6e9',
                'state_checkpoint_hash': None,
                'gas_used': '585',
                'success': True,
                'vm_status': 'Executed successfully',
                'accumulator_root_hash': '0x7961aacb185973809bce37f2d2adc51c7d9ac9b39ecf480e080ff0ce0116ba02',
                'changes': [
                    {'address': '0x2f4147c01ed25d7a10dc707d2b653c0fc741dc7a948eefa251d641b037885234',
                     'state_key_hash': '0x90038421aabd68c8a6222db334b12860fcc5e422470843b1075a0687cb5c0756',
                     'data': {'type': '0x1::coin::CoinStore<0x1::aptos_coin::AptosCoin>',
                              'data': {'coin': {'value': '941500'},
                                       'deposit_events': {
                                           'counter': '4',
                                           'guid': {'id': {
                                               'addr': '0x2f4147c01ed25d7a10dc707d2b653c0fc741'
                                                       'dc7a948eefa251d641b037885234',
                                               'creation_num': '2'}}},
                                       'frozen': False,
                                       'withdraw_events': {
                                           'counter': '4',
                                           'guid': {
                                               'id': {
                                                   'addr': '0x2f4147c01ed25d7a10dc707d2b653c0f'
                                                           'c741dc7a948eefa251d641b037885234',
                                                   'creation_num': '3'}}}}},
                     'type': 'write_resource'},
                    {'address': '0x2f4147c01ed25d7a10dc707d2b653c0fc741dc7a948eefa251d641b037885234',
                     'state_key_hash': '0x3a3985a46412358d85b1c903aa6ec3335c0ec52fe92a6d69b1ea1f0a576d8a53',
                     'data': {'type': '0x1::account::Account', 'data': {
                         'authentication_key': '0x2f4147c01ed25d7a10dc707d2b653c0fc741dc7a948eefa251d641b037885234',
                         'coin_register_events': {'counter': '2', 'guid': {'id': {
                             'addr': '0x2f4147c01ed25d7a10dc707d2b653c0fc741dc7a948eefa251d641b037885234',
                             'creation_num': '0'}}}, 'guid_creation_num': '6',
                         'key_rotation_events': {'counter': '0', 'guid': {'id': {
                             'addr': '0x2f4147c01ed25d7a10dc707d2b653c0fc741dc7a948eefa251d641b037885234',
                             'creation_num': '1'}}}, 'rotation_capability_offer': {'for': {'vec': []}},
                         'sequence_number': '6', 'signer_capability_offer': {'for': {'vec': []}}}},
                     'type': 'write_resource'},
                    {'address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                     'state_key_hash': '0xd8ee498dcae9a53198f342e8b53889678d46f3507d9f5bc69cac1e0d69cc17d3',
                     'data': {'type': '0x1::coin::CoinStore<0x1::aptos_coin::AptosCoin>',
                              'data': {'coin': {'value': '1412060110'},
                                       'deposit_events': {
                                           'counter': '5',
                                           'guid': {'id': {
                                               'addr': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d'
                                                       '94bb132a41e9aca76c5b259b',
                                               'creation_num': '2'}}},
                                       'frozen': False,
                                       'withdraw_events': {
                                           'counter': '2',
                                           'guid': {
                                               'id': {
                                                   'addr': '0xc0f3774ae4bd6ed534b110b7a792e415a'
                                                           '007849d94bb132a41e9aca76c5b259b',
                                                   'creation_num': '3'}}}}},
                     'type': 'write_resource'},
                    {'state_key_hash': '0x6e4b28d40f98a106a65163530924c0dcb40c1349d3aa915d108b4d6cfc1ddb19',
                     'handle': '0x1b854694ae746cdbd8d44186ca4929b2b337df21d1c74633be19b2710552fdca',
                     'key': '0x0619dc29a0aac8fa146714058e8dd6d2d0f3bdf5f6331907bf91f3acd81e6935',
                     'value': '0x05ce9b6ba2e963010000000000000000', 'data': None, 'type': 'write_table_item'}],
                'sender': '0x2f4147c01ed25d7a10dc707d2b653c0fc741dc7a948eefa251d641b037885234',
                'sequence_number': '5',
                'max_gas_amount': '3000',
                'gas_unit_price': '100',
                'expiration_timestamp_secs': '1666633121',
                'payload': {'function': '0x1::aptos_account::transfer', 'type_arguments': [],
                            'arguments': ['0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                          '1410818610'],
                            'type': 'entry_function_payload'},
                'signature': {'public_key': '0x00a229352fdd7cab01f4c8c7a283c0eaab671470a7ab8cd2223caaffa2308498',
                              'signature': '0x6aab4ac73eda792d7f338626d526d4c81f4709'
                                           '75da0279d824be265821b1de8ab7104ec0a6f6809'
                                           '751062c42c1de55800b92d0cfa0fe9054d80d310d6903fb0b',
                              'type': 'ed25519_signature'},
                'events': [
                    {
                        'guid': {
                            'creation_number': '3',
                            'account_address': '0x2f4147c01ed25d7a10dc707d2b653c0fc741dc7a948eefa251d641b037885234'},
                        'sequence_number': '3', 'type': '0x1::coin::WithdrawEvent',
                        'data': {'amount': '1410818610'}}, {
                        'guid': {
                            'creation_number': '2',
                            'account_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b'},
                        'sequence_number': '4', 'type': '0x1::coin::DepositEvent',
                        'data': {'amount': '1410818610'}}],
                'timestamp': '1666632522642858',
                'type': 'user_transaction'}]
        ]
        expected_addresses_txs = [
            [
                {
                    'address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                    'block': 11251017,
                    'confirmations': 36526102,
                    'contract_address': None,
                    'details': {},
                    'from_address': ['0x2f4147c01ed25d7a10dc707d2b653c0fc741dc7a948eefa251d641b037885234'],
                    'hash': '11251017',
                    'huge': False,
                    'invoice': None,
                    'is_double_spend': False,
                    'tag': None,
                    'timestamp': datetime.datetime(2022, 10, 24, 17, 28, 42, 642858, tzinfo=datetime.timezone.utc),
                    'value': Decimal('14.10818610')
                }
            ]
        ]
        cls.get_address_txs(address_txs_mock_response, expected_addresses_txs)

    @classmethod
    def test_get_block_txs(cls):
        block_txs_mock_response = [
            {
                'chain_id': 1, 'epoch': '705', 'ledger_version': '47775842', 'oldest_ledger_version': '0',
                'ledger_timestamp': '1670671201794529', 'node_role': 'full_node', 'oldest_block_height': '0',
                'block_height': '16366603', 'git_hash': 'd7fe6d2f68e6b25bddce8e13546e0b24076f47a5'
            },
            [
                {
                    'version': '33255488', 'hash': '0xa24f9becf7ebd0641af3ee4ed9fccdab44a8c5076a62d6e8c040a6a4a2be789b',
                    'state_change_hash': '0x0239dda5b1e6e98014d71c8bddfdd657b25352cbee8162be9a9c3916bae9ecd3',
                    'event_root_hash': '0x9df5d572544f16b463b482d21edeceeba9ebee19986198f5992b4b07febd2d3f',
                    'state_checkpoint_hash': None, 'gas_used': '541', 'success': True,
                    'vm_status': 'Executed successfully',
                    'accumulator_root_hash': '0xc461f19b7e18b8c504ab296bb7c24ae2f2b9e34813d5be962ba7565627330819',
                    'changes': [{
                        'address': '0x299e5407da4ab643b43d566bdf7ef7f28eba7b83401a5c53d8968d8848f2ca99',
                        'state_key_hash': '0x021b2ca9ab3141c3790f8228d8d26ee97d679f3a4a7fd52f2403837cfeafe386',
                        'data': {
                            'type': '0x1::coin::CoinStore<0x1::aptos_coin::AptosCoin>',
                            'data': {
                                'coin': {'value': '5507586800'},
                                'deposit_events': {
                                    'counter': '3', 'guid': {
                                        'id': {
                                            'addr': '0x299e5407da4ab643b43d566bdf7ef7f28eba7b83'
                                                    '401a5c53d8968d8848f2ca99',
                                            'creation_num': '2'}}},
                                'frozen': False,
                                'withdraw_events': {
                                    'counter': '1052', 'guid': {'id': {
                                        'addr': '0x299e5407da4ab643b43d566bdf7ef7f28eba7b83401a5c53d8968d8848f2ca99',
                                        'creation_num': '3'}}}}},
                        'type': 'write_resource'},
                        {'address': '0x299e5407da4ab643b43d566bdf7ef7f28eba7b83401a5c53d8968d8848f2ca99',
                         'state_key_hash': '0xb60da2609c1dbbff7d0aae12d5b41550f464d966ec1e32bd1dcdc00dbde0ba3f',
                         'data': {'type': '0x1::account::Account', 'data': {
                             'authentication_key': '0x299e5407da4ab643b43d566bdf7ef7f28eba7b83401a5c53d8968d8848f2ca99',
                             'coin_register_events': {'counter': '1', 'guid': {'id': {
                                 'addr': '0x299e5407da4ab643b43d566bdf7ef7f28eba7b83401a5c53d8968d8848f2ca99',
                                 'creation_num': '0'}}}, 'guid_creation_num': '4',
                             'key_rotation_events': {'counter': '0', 'guid': {'id': {
                                 'addr': '0x299e5407da4ab643b43d566bdf7ef7f28eba7b83401a5c53d8968d8848f2ca99',
                                 'creation_num': '1'}}}, 'rotation_capability_offer': {'for': {'vec': []}},
                             'sequence_number': '1052', 'signer_capability_offer': {'for': {'vec': []}}}},
                         'type': 'write_resource'},
                        {'address': '0xc20050813877b5c14941bf5d35678f6e4891564379c3bc9247913e2fabdc9e9c',
                         'state_key_hash': '0x2846b0ed1d9a870b57647557994c5bf22f4e944a0e85ef5a67074ef69e3041c2',
                         'data': {
                             'type': '0x1::coin::CoinStore<0x1::aptos_coin::AptosCoin>',
                             'data': {
                                 'coin': {'value': '24014486'},
                                 'deposit_events': {
                                     'counter': '19', 'guid': {
                                         'id': {
                                             'addr': '0xc20050813877b5c14941bf5d35678f6e4'
                                                     '891564379c3bc9247913e2fabdc9e9c',
                                             'creation_num': '2'}}},
                                 'frozen': False,
                                 'withdraw_events': {
                                     'counter': '25', 'guid': {
                                         'id': {
                                             'addr': '0xc20050813877b5c14941bf5d35678f6e4'
                                                     '891564379c3bc9247913e2fabdc9e9c',
                                             'creation_num': '3'}}}}},
                         'type': 'write_resource'},
                        {'state_key_hash': '0x6e4b28d40f98a106a65163530924c0dcb40c1349d3aa915d108b4d6cfc1ddb19',
                         'handle': '0x1b854694ae746cdbd8d44186ca4929b2b337df21d1c74633be19b2710552fdca',
                         'key': '0x0619dc29a0aac8fa146714058e8dd6d2d0f3bdf5f6331907bf91f3acd81e6935',
                         'value': '0x036cec0a463e65010000000000000000',
                         'data': None, 'type': 'write_table_item'}],
                    'sender': '0x299e5407da4ab643b43d566bdf7ef7f28eba7b83401a5c53d8968d8848f2ca99',
                    'sequence_number': '1051',
                    'max_gas_amount': '10000', 'gas_unit_price': '100', 'expiration_timestamp_secs': '1668692275',
                    'payload': {'function': '0x1::coin::transfer', 'type_arguments': ['0x1::aptos_coin::AptosCoin'],
                                'arguments': ['0xc20050813877b5c14941bf5d35678f6e4891564379c3bc9247913e2fabdc9e9c',
                                              '10300000'],
                                'type': 'entry_function_payload'},
                    'signature': {'public_key': '0xd4c1127437d60c9059be4471f45ef0fd900e86e17703edfae8d53ce7a96a02cb',
                                  'signature': '0xb10174f9742933a1824216c0383cbc2cd8db90'
                                               '83203de1e2fd66f2fcbea1e85e3abe4b7b76dff6'
                                               '96a62f0e57d31d6b03ada36321e16ddde240a8201b8f4d9e0d',
                                  'type': 'ed25519_signature'},
                    'events': [{
                        'guid': {
                            'creation_number': '3',
                            'account_address': '0x299e5407da4ab643b43d566bdf7ef7f28eba7b83401a5c53d8968d8848f2ca99'},
                        'sequence_number': '1051',
                        'type': '0x1::coin::WithdrawEvent',
                        'data': {'amount': '10300000'}}, {
                        'guid': {
                            'creation_number': '2',
                            'account_address': '0xc20050813877b5c14941bf5d35678f6e4891564379c3bc9247913e2fabdc9e9c'},
                        'sequence_number': '18',
                        'type': '0x1::coin::DepositEvent',
                        'data': {'amount': '10300000'}}],
                    'timestamp': '1668691676655812', 'type': 'user_transaction'
                },
                {
                    'version': '33255489', 'hash': '0x0b181ec64fccfcba8bf6b4abcf82ffce70c5c04f67ea9a3dd3f0e704e69b7608',
                    'state_change_hash': '0xafb6e14fe47d850fd0a7395bcfb997ffacf4715e0f895cc162c218e4a7564bc6',
                    'event_root_hash': '0x414343554d554c41544f525f504c414345484f4c4445525f4841534800000000',
                    'state_checkpoint_hash': '0x5124f4661ef3a0642f866979b06ee9f6bdb3b6459a8acd77f09aed864fae21d5',
                    'gas_used': '0',
                    'success': True, 'vm_status': 'Executed successfully',
                    'accumulator_root_hash': '0xef652a8f7459f672843653204fca711c288197f8121b475237c6757561b17ad8',
                    'changes': [],
                    'timestamp': '1668691676655812', 'type': 'state_checkpoint_transaction'
                },
                {
                    'version': '33255490',
                    'hash': '0xc5ad140d3079cad6c6939ed307b0168b2d7572622dbde0ce90f6ba6c4950644f',
                    'state_change_hash': '0xb37cd3fcf9bf033c30f7cd449ffce740cb5a66c770ad8e227717a267660547dc',
                    'event_root_hash': '0x06213d2d2d11126e4d8bff0f4085fd72878936cfa3e0e4eb52d57d9e52c21c3c',
                    'state_checkpoint_hash': None, 'gas_used': '0', 'success': True,
                    'vm_status': 'Executed successfully',
                    'accumulator_root_hash': '0x4e8bed2014ef5a173e3075ff7642e972ab659258d6f56ff5751546be1eb3a755',
                    'changes': [
                        {'address': '0x1',
                         'state_key_hash': '0x5ddf404c60e96e9485beafcabb95609fed8e38e941a725cae4dcec8296fb32d7',
                         'data': {'type': '0x1::block::BlockResource',
                                  'data': {'epoch_interval': '7200000000', 'height': '10440646',
                                           'new_block_events': {'counter': '10440647', 'guid': {
                                               'id': {'addr': '0x1', 'creation_num': '3'}}},
                                           'update_epoch_interval_events': {'counter': '0',
                                                                            'guid': {'id': {
                                                                                'addr': '0x1',
                                                                                'creation_num': '4'}}}}},
                         'type': 'write_resource'},
                        {'address': '0x1',
                         'state_key_hash': '0x8048c954221814b04533a9f0a9946c3a8d472ac62df5accb9f47c097e256e8b6',
                         'data': {'type': '0x1::stake::ValidatorPerformance', 'data': {
                             'validators': [
                                 {'failed_proposals': '0', 'successful_proposals': '49'},
                                 {'failed_proposals': '0', 'successful_proposals': '43'},
                                 {'failed_proposals': '0', 'successful_proposals': '26'},
                                 {'failed_proposals': '0', 'successful_proposals': '23'},
                                 {'failed_proposals': '0', 'successful_proposals': '20'},
                                 {'failed_proposals': '0', 'successful_proposals': '221'},
                                 {'failed_proposals': '0', 'successful_proposals': '103'},
                                 {'failed_proposals': '0', 'successful_proposals': '36'},
                                 {'failed_proposals': '0', 'successful_proposals': '30'},
                                 {'failed_proposals': '0', 'successful_proposals': '97'},
                                 {'failed_proposals': '0', 'successful_proposals': '135'},
                                 {'failed_proposals': '0', 'successful_proposals': '131'},
                                 {'failed_proposals': '0', 'successful_proposals': '134'},
                                 {'failed_proposals': '0', 'successful_proposals': '134'},
                                 {'failed_proposals': '0', 'successful_proposals': '300'},
                                 {'failed_proposals': '0', 'successful_proposals': '22'},
                                 {'failed_proposals': '0', 'successful_proposals': '30'},
                                 {'failed_proposals': '0', 'successful_proposals': '31'},
                                 {'failed_proposals': '0', 'successful_proposals': '31'},
                                 {'failed_proposals': '0', 'successful_proposals': '20'},
                                 {'failed_proposals': '0', 'successful_proposals': '634'},
                                 {'failed_proposals': '0', 'successful_proposals': '617'},
                                 {'failed_proposals': '0', 'successful_proposals': '642'},
                                 {'failed_proposals': '0', 'successful_proposals': '614'},
                                 {'failed_proposals': '0', 'successful_proposals': '632'},
                                 {'failed_proposals': '0', 'successful_proposals': '623'},
                                 {'failed_proposals': '0', 'successful_proposals': '606'},
                                 {'failed_proposals': '0', 'successful_proposals': '631'},
                                 {'failed_proposals': '0', 'successful_proposals': '539'},
                                 {'failed_proposals': '0', 'successful_proposals': '534'},
                                 {'failed_proposals': '0', 'successful_proposals': '452'},
                                 {'failed_proposals': '0', 'successful_proposals': '35'},
                                 {'failed_proposals': '0', 'successful_proposals': '33'},
                                 {'failed_proposals': '0', 'successful_proposals': '30'},
                                 {'failed_proposals': '0', 'successful_proposals': '30'},
                                 {'failed_proposals': '0', 'successful_proposals': '35'},
                                 {'failed_proposals': '0', 'successful_proposals': '23'},
                                 {'failed_proposals': '0', 'successful_proposals': '27'},
                                 {'failed_proposals': '0', 'successful_proposals': '35'},
                                 {'failed_proposals': '0', 'successful_proposals': '23'},
                                 {'failed_proposals': '0', 'successful_proposals': '31'},
                                 {'failed_proposals': '0', 'successful_proposals': '33'},
                                 {'failed_proposals': '0', 'successful_proposals': '30'},
                                 {'failed_proposals': '0', 'successful_proposals': '601'},
                                 {'failed_proposals': '0', 'successful_proposals': '28'},
                                 {'failed_proposals': '0', 'successful_proposals': '584'},
                                 {'failed_proposals': '0', 'successful_proposals': '47'},
                                 {'failed_proposals': '0', 'successful_proposals': '30'},
                                 {'failed_proposals': '0', 'successful_proposals': '22'},
                                 {'failed_proposals': '0', 'successful_proposals': '29'},
                                 {'failed_proposals': '0', 'successful_proposals': '528'},
                                 {'failed_proposals': '0', 'successful_proposals': '556'},
                                 {'failed_proposals': '0', 'successful_proposals': '41'},
                                 {'failed_proposals': '0', 'successful_proposals': '31'},
                                 {'failed_proposals': '0', 'successful_proposals': '140'},
                                 {'failed_proposals': '0', 'successful_proposals': '36'},
                                 {'failed_proposals': '0', 'successful_proposals': '434'},
                                 {'failed_proposals': '0', 'successful_proposals': '53'},
                                 {'failed_proposals': '0', 'successful_proposals': '27'},
                                 {'failed_proposals': '0', 'successful_proposals': '34'},
                                 {'failed_proposals': '0', 'successful_proposals': '25'},
                                 {'failed_proposals': '0', 'successful_proposals': '35'},
                                 {'failed_proposals': '0', 'successful_proposals': '617'},
                                 {'failed_proposals': '0', 'successful_proposals': '606'},
                                 {'failed_proposals': '0', 'successful_proposals': '431'},
                                 {'failed_proposals': '0', 'successful_proposals': '492'},
                                 {'failed_proposals': '0', 'successful_proposals': '34'},
                                 {'failed_proposals': '0', 'successful_proposals': '32'},
                                 {'failed_proposals': '0', 'successful_proposals': '253'},
                                 {'failed_proposals': '0', 'successful_proposals': '24'},
                                 {'failed_proposals': '0', 'successful_proposals': '36'},
                                 {'failed_proposals': '0', 'successful_proposals': '24'},
                                 {'failed_proposals': '0', 'successful_proposals': '28'},
                                 {'failed_proposals': '0', 'successful_proposals': '203'},
                                 {'failed_proposals': '0', 'successful_proposals': '121'},
                                 {'failed_proposals': '0', 'successful_proposals': '95'},
                                 {'failed_proposals': '0', 'successful_proposals': '120'},
                                 {'failed_proposals': '0', 'successful_proposals': '38'},
                                 {'failed_proposals': '0', 'successful_proposals': '618'},
                                 {'failed_proposals': '0', 'successful_proposals': '564'},
                                 {'failed_proposals': '0', 'successful_proposals': '31'},
                                 {'failed_proposals': '0', 'successful_proposals': '573'},
                                 {'failed_proposals': '0', 'successful_proposals': '22'},
                                 {'failed_proposals': '0', 'successful_proposals': '19'},
                                 {'failed_proposals': '0', 'successful_proposals': '646'},
                                 {'failed_proposals': '0', 'successful_proposals': '36'},
                                 {'failed_proposals': '0', 'successful_proposals': '609'},
                                 {'failed_proposals': '0', 'successful_proposals': '176'},
                                 {'failed_proposals': '0', 'successful_proposals': '145'},
                                 {'failed_proposals': '0', 'successful_proposals': '635'},
                                 {'failed_proposals': '0', 'successful_proposals': '505'},
                                 {'failed_proposals': '0', 'successful_proposals': '463'},
                                 {'failed_proposals': '0', 'successful_proposals': '27'},
                                 {'failed_proposals': '0', 'successful_proposals': '31'},
                                 {'failed_proposals': '0', 'successful_proposals': '551'},
                                 {'failed_proposals': '0', 'successful_proposals': '605'},
                                 {'failed_proposals': '0', 'successful_proposals': '619'},
                                 {'failed_proposals': '0', 'successful_proposals': '456'},
                                 {'failed_proposals': '0', 'successful_proposals': '447'},
                                 {'failed_proposals': '0', 'successful_proposals': '90'},
                                 {'failed_proposals': '0', 'successful_proposals': '490'},
                                 {'failed_proposals': '0', 'successful_proposals': '44'}]}},
                         'type': 'write_resource'},
                        {'address': '0x1',
                         'state_key_hash': '0x7b1615bf012d3c94223f3f76287ee2f7bdf31d364071128b256aeff0841b626d',
                         'data': {'type': '0x1::timestamp::CurrentTimeMicroseconds',
                                  'data': {'microseconds': '1668691676872463'}},
                         'type': 'write_resource'}],
                    'id': '0xdc65c92f7278ac65f16a90cf378a246f0a8344cfcc5cb7f7d8815367e77937f8',
                    'epoch': '430', 'round': '23342',
                    'events': [
                        {'guid': {'creation_number': '3', 'account_address': '0x1'}, 'sequence_number': '10440646',
                         'type': '0x1::block::NewBlockEvent',
                         'data': {'epoch': '430', 'failed_proposer_indices': [],
                                  'hash': '0xdc65c92f7278ac65f16a90cf378a246f0a8344cfcc5cb7f7d8815367e77937f8',
                                  'height': '10440646',
                                  'previous_block_votes_bitvec': '0xd0c1d5eeff61ef5ecfe5ffffbc',
                                  'proposer': '0x81d41a31fb5d3f827d188511e6fca1ddbed6cfa0ffbd46fa6d84a7adfe59f356',
                                  'round': '23342',
                                  'time_microseconds': '1668691676872463'}}],
                    'previous_block_votes_bitvec': [208, 193, 213, 238, 255, 97, 239, 94, 207, 229, 255, 255, 188],
                    'proposer': '0x81d41a31fb5d3f827d188511e6fca1ddbed6cfa0ffbd46fa6d84a7adfe59f356',
                    'failed_proposer_indices': [],
                    'timestamp': '1668691676872463', 'type': 'block_metadata_transaction'}
            ]
        ]
        expected_txs_addresses = {
            'input_addresses': {'0x299e5407da4ab643b43d566bdf7ef7f28eba7b83401a5c53d8968d8848f2ca99'},
            'output_addresses': {'0xc20050813877b5c14941bf5d35678f6e4891564379c3bc9247913e2fabdc9e9c'}
        }
        expected_txs_info = {
            'outgoing_txs': {
                '0x299e5407da4ab643b43d566bdf7ef7f28eba7b83401a5c53d8968d8848f2ca99': {
                    Currencies.apt: [
                        {'contract_address': None,
                         'tx_hash': '33255488',
                         'value': Decimal('0.10300000'),
                         'block_height': 33255488, 'symbol':'APT'}
                    ]
                }
            },
            'incoming_txs': {
                '0xc20050813877b5c14941bf5d35678f6e4891564379c3bc9247913e2fabdc9e9c': {
                    Currencies.apt: [
                        {'contract_address': None,
                         'tx_hash': '33255488',
                         'value': Decimal('0.10300000'),
                         'block_height': 33255488, 'symbol':'APT'}
                    ]
                }
            }
        }
        cls.get_block_txs(block_txs_mock_response, expected_txs_addresses, expected_txs_info)
