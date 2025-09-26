import pytest
import datetime
from decimal import Decimal
from unittest import TestCase
from exchange.base.models import Currencies
from exchange.blockchain.api.ada.cardano_blockfrost_new import CardanoBlockFrostApi
from exchange.blockchain.api.ada.cardano_explorer_interface import CardanoExplorerInterface
from exchange.blockchain.apis_conf import APIS_CONF
from exchange.blockchain.tests.api.general_test.general_test_from_explorer import TestFromExplorer


class TestCardanoApiCalls(TestCase):
    api = CardanoBlockFrostApi
    account_address = [
        'addr1z8p79rpkcdz8x9d6tft0x0dx5mwuzac2sa4gm8cvkw5hcnxxmamn55j2l2l620dvu22rw5ag2gfdddq6sn3aqmy374rs0raldq']
    txs_hash = ['206485c0d8e3893bc534782c3665d0bfa6f03f9c7b6d4df16fb4fe4eeb329f57']
    blocks = [10571084]

    @pytest.mark.slow
    def test_get_balance_api(self):
        for account_address in self.account_address:
            get_balance_result = self.api.get_balance(account_address)
            assert isinstance(get_balance_result, dict)
            assert isinstance(get_balance_result.get('address'), str)
            assert isinstance(get_balance_result.get('amount'), list)
            for amount in get_balance_result.get('amount'):
                assert isinstance(amount, dict)
                assert isinstance(amount.get('quantity'), str)
                assert isinstance(amount.get('unit'), str) and amount.get('unit') == 'lovelace'

    @pytest.mark.slow
    def test_get_block_head_api(self):
        get_block_head_result = self.api.get_block_head()
        assert isinstance(get_block_head_result, dict)
        assert isinstance(get_block_head_result.get('height'), int)

    @pytest.mark.slow
    def test_get_tx_details_api(self):
        for tx_hash in self.txs_hash:
            get_tx_details_result = self.api.get_tx_details(tx_hash)
            assert isinstance(get_tx_details_result, dict)
            assert isinstance(get_tx_details_result.get('tx_info'), dict)
            assert isinstance(get_tx_details_result.get('tx_utxos'), dict)
            key2check_info = [('hash', str), ('block', str), ('block_time', int), ('block_height', int),
                              ('output_amount', list), ('fees', str)]
            for key, value in key2check_info:
                assert isinstance(get_tx_details_result.get('tx_info').get(key), value)
            key2check_utxos = [('hash', str), ('inputs', list), ('outputs', list)]
            for key, value in key2check_utxos:
                assert isinstance(get_tx_details_result.get('tx_utxos').get(key), value)
            key2check_inputs = [('address', str), ('amount', list), ('tx_hash', list)]
            for input_ in get_tx_details_result.get('tx_utxos').get('inputs'):
                for key, value in key2check_inputs:
                    assert (input_.get(key), value)
            key2check_outputs = [('address', str), ('amount', list)]
            for output_ in get_tx_details_result.get('tx_utxos').get('outputs'):
                for key, value in key2check_outputs:
                    assert (output_.get(key), value)

    @pytest.mark.slow
    def test_get_address_txs_api(self):
        for address in self.account_address:
            address_txs_result = self.api.get_address_txs(address)
            assert isinstance(address_txs_result, list)
            for tx in address_txs_result:
                assert isinstance(tx.get('tx_info'), dict)
                assert isinstance(tx.get('tx_utxos'), dict)
                key2check_info = [('hash', str), ('block', str), ('block_time', int), ('block_height', int),
                                  ('output_amount', list), ('fees', str)]
                for key, value in key2check_info:
                    assert isinstance(tx.get('tx_info').get(key), value)
                key2check_utxos = [('hash', str), ('inputs', list), ('outputs', list)]
                for key, value in key2check_utxos:
                    assert isinstance(tx.get('tx_utxos').get(key), value)
                key2check_inputs = [('address', str), ('amount', list), ('tx_hash', list)]
                for input_ in tx.get('tx_utxos').get('inputs'):
                    for key, value in key2check_inputs:
                        assert (input_.get(key), value)
                key2check_outputs = [('address', str), ('amount', list)]
                for output_ in tx.get('tx_utxos').get('outputs'):
                    for key, value in key2check_outputs:
                        assert (output_.get(key), value)

    @pytest.mark.slow
    def test_get_blocks_api(self):
        for block in self.blocks:
            block_txs_response = self.api.get_block_txs(block)
            assert isinstance(block_txs_response, list)
            for tx in block_txs_response:
                assert isinstance(tx.get('tx_info'), dict)
                assert isinstance(tx.get('tx_utxos'), dict)
                key2check_info = [('hash', str), ('block', str), ('block_time', int), ('block_height', int),
                                  ('output_amount', list), ('fees', str)]
                for key, value in key2check_info:
                    assert isinstance(tx.get('tx_info').get(key), value)
                key2check_utxos = [('hash', str), ('inputs', list), ('outputs', list)]
                for key, value in key2check_utxos:
                    assert isinstance(tx.get('tx_utxos').get(key), value)
                key2check_inputs = [('address', str), ('amount', list), ('tx_hash', list)]
                for input_ in tx.get('tx_utxos').get('inputs'):
                    for key, value in key2check_inputs:
                        assert (input_.get(key), value)
                key2check_outputs = [('address', str), ('amount', list)]
                for output_ in tx.get('tx_utxos').get('outputs'):
                    for key, value in key2check_outputs:
                        assert (output_.get(key), value)


class TestCardanoFromExplorer(TestFromExplorer):
    api = CardanoBlockFrostApi
    addresses = [
        'DdzFFzCqrhszAisfe4k7wNnA8Ue4L3AyHVpdeewZkyrfScRqRptz6RxzzVdbvYNscoq7cWyz69sECE2tKwC7gKFiqu5dzLZfTs3ez1xy']
    txs_addresses = [
        'addr1z8p79rpkcdz8x9d6tft0x0dx5mwuzac2sa4gm8cvkw5hcnxxmamn55j2l2l620dvu22rw5ag2gfdddq6sn3aqmy374rs0raldq']
    txs_hash = ['206485c0d8e3893bc534782c3665d0bfa6f03f9c7b6d4df16fb4fe4eeb329f57']
    explorerInterface = CardanoExplorerInterface
    currencies = Currencies.ada
    symbol = 'ADA'

    @classmethod
    def test_get_balance(cls):
        APIS_CONF['ADA']['get_balances'] = 'ada_explorer_interface'
        balance_mock_responses = [
            {
                'address': 'DdzFFzCqrhszAisfe4k7wNnA8Ue4L3AyHVpdeewZkyrfScRqRptz6RxzzVdbvYNscoq7cWyz69sECE2tKwC7gKFiqu5dzLZfTs3ez1xy',
                'amount': [{'quantity': '79212743262', 'unit': 'lovelace'}], 'script': False,
                'stake_address': None,
                'type': 'byron'}
        ]
        expected_balances = [
            {
                'address': 'DdzFFzCqrhszAisfe4k7wNnA8Ue4L3AyHVpdeewZkyrfScRqRptz6RxzzVdbvYNscoq7cWyz69sECE2tKwC7gKFiqu5dzLZfTs3ez1xy',
                'balance': Decimal('79212.743262'),
                'received': Decimal('79212.743262'),
                'rewarded': Decimal('0'),
                'sent': Decimal('0')
            }
        ]
        cls.get_balance(balance_mock_responses, expected_balances)

    @classmethod
    def test_get_tx_details(cls):
        APIS_CONF['ADA']['get_tx_details'] = 'ada_explorer_interface'
        tx_details_mock_responses = [
            {'time': 1721045071, 'height': 10575914,
             'hash': '4f30b31910ae80bb6ce9d73f75ec15fdcb6c610bedc2c7f615e5874c5ce1e0a3', 'slot': 129478780,
             'epoch': 497, 'epoch_slot': 137980,
             'slot_leader': 'pool1kcfe6evpfmh5rh40yta3qrrudsy956scuwfl7wgts0z926z6kuw', 'size': 8737, 'tx_count': 3,
             'output': '200679383021', 'fees': '962257',
             'block_vrf': 'vrf_vk1lerhzrtn5yl9t6dkl9ad3l4ch8lm8x424q0qqrdy93fycneczcds0k6qw4',
             'op_cert': 'c6571f5e78cb730a849b6d41fd92076e0f4d2e90b237765851f0c455038689b0', 'op_cert_counter': '3',
             'previous_block': '5e5468bcbb792968dc2601b14da26edd8461fcf950c53000386766b904701c51', 'next_block': None,
             'confirmations': 0},
            {'hash': '206485c0d8e3893bc534782c3665d0bfa6f03f9c7b6d4df16fb4fe4eeb329f57',
             'block': 'ac2419578b9e139931c74d3cf69a2d530eed01933945a98b8f50154bda4350ff', 'block_height': 10568207,
             'block_time': 1720887796, 'slot': 129321505, 'index': 24,
             'output_amount': [{'unit': 'lovelace', 'quantity': '150276011'},
                               {'unit': '086849cd9f672e731e0d9590a2d28a6a690ffa2f73bae0e1970f04914754494a3030363732',
                                'quantity': '1'},
                               {'unit': '086849cd9f672e731e0d9590a2d28a6a690ffa2f73bae0e1970f04914754494a3130333636',
                                'quantity': '1'}], 'fees': '228785', 'deposit': '0', 'size': 1048,
             'invalid_before': '129321459', 'invalid_hereafter': '129325059', 'utxo_count': 7, 'withdrawal_count': 0,
             'mir_cert_count': 0, 'delegation_count': 0, 'stake_cert_count': 0, 'pool_update_count': 0,
             'pool_retire_count': 0, 'asset_mint_or_burn_count': 0, 'redeemer_count': 0, 'valid_contract': True},
            {
                'hash': '206485c0d8e3893bc534782c3665d0bfa6f03f9c7b6d4df16fb4fe4eeb329f57', 'inputs': [{
                'address': 'addr1q8u9r5uaa5lsl2vrd979htq6c7mslx5hsnteqz7rjnp92kr5e04vm5h6ln9pplarzjdtp8grwl5ntjk9693twyh9xzeqctht6m',
                'amount': [{
                    'unit': 'lovelace',
                    'quantity': '54236009'}],
                'tx_hash': '8272268871c0119369465eb942adcc1fd8473819b32b85704fcd4b0583d3346e',
                'output_index': 2,
                'data_hash': None,
                'inline_datum': None,
                'reference_script_hash': None,
                'collateral': False,
                'reference': False},
                {
                    'address': 'addr1q8u9r5uaa5lsl2vrd979htq6c7mslx5hsnteqz7rjnp92kr5e04vm5h6ln9pplarzjdtp8grwl5ntjk9693twyh9xzeqctht6m',
                    'amount': [{
                        'unit': 'lovelace',
                        'quantity': '1206800'},
                        {
                            'unit': '086849cd9f672e731e0d9590a2d28a6a690ffa2f73bae0e1970f04914754494a3030363732',
                            'quantity': '1'},
                        {
                            'unit': '086849cd9f672e731e0d9590a2d28a6a690ffa2f73bae0e1970f04914754494a3130333636',
                            'quantity': '1'}],
                    'tx_hash': 'cc7dac79e98e0e4785154f826511004a580f7ea46c0932094d462d484e8f4297',
                    'output_index': 6,
                    'data_hash': None,
                    'inline_datum': None,
                    'reference_script_hash': None,
                    'collateral': False,
                    'reference': False},
                {
                    'address': 'addr1q8u9r5uaa5lsl2vrd979htq6c7mslx5hsnteqz7rjnp92kr5e04vm5h6ln9pplarzjdtp8grwl5ntjk9693twyh9xzeqctht6m',
                    'amount': [{
                        'unit': 'lovelace',
                        'quantity': '95061987'}],
                    'tx_hash': 'f3839b726318371fcce1d144c0fb94482bea18ac068f716426cced8dd1840871',
                    'output_index': 1,
                    'data_hash': None,
                    'inline_datum': None,
                    'reference_script_hash': None,
                    'collateral': False,
                    'reference': False}],
                'outputs': [{
                    'address': 'addr1q8u9r5uaa5lsl2vrd979htq6c7mslx5hsnteqz7rjnp92kr5e04vm5h6ln9pplarzjdtp8grwl5ntjk9693twyh9xzeqctht6m',
                    'amount': [{'unit': 'lovelace', 'quantity': '1452470'}, {
                        'unit': '086849cd9f672e731e0d9590a2d28a6a690ffa2f73bae0e1970f04914754494a3030363732',
                        'quantity': '1'}, {
                                   'unit': '086849cd9f672e731e0d9590a2d28a6a690ffa2f73bae0e1970f04914754494a3130333636',
                                   'quantity': '1'}], 'output_index': 0, 'data_hash': None,
                    'inline_datum': None, 'collateral': False, 'reference_script_hash': None}, {
                    'address': 'addr1z8d70g7c58vznyye9guwagdza74x36f3uff0eyk2zwpcpxm5e04vm5h6ln9pplarzjdtp8grwl5ntjk9693twyh9xzeq22kq5u',
                    'amount': [{'unit': 'lovelace', 'quantity': '102500000'}], 'output_index': 1,
                    'data_hash': 'd71fa401781e472dc8658e05e2784f99d579eac35a90386371def93acd646c8c',
                    'inline_datum': 'd8799f4100581c27b673721bdc18c1ed8d865595efd4979c1c4a390007ab5f7672f3acd8799f4040ff1a05f5e1001a0007a1201917f0d8799f581cc881c20e49dbaca3ff6cef365969354150983230c39520b917f5cf7c444e696b65ffd8799f1917f01a05f5e100ff00d8799fd8799f581cf851d39ded3f0fa983697c5bac1ac7b70f9a9784d7900bc394c25558ffd8799fd8799fd8799f581c74cbeacdd2fafcca10ffa3149ab09d0377e935cac5d162b712e530b2ffffffff581cf851d39ded3f0fa983697c5bac1ac7b70f9a9784d7900bc394c255589f581c2f9ff04d8914bf64d671a03d34ab7937eb417831ea6b9f7fbcab96f5ffff',
                    'collateral': False, 'reference_script_hash': None}, {
                    'address': 'addr1q8l7hny7x96fadvq8cukyqkcfca5xmkrvfrrkt7hp76v3qvssm7fz9ajmtd58ksljgkyvqu6gl23hlcfgv7um5v0rn8qtnzlfk',
                    'amount': [{'unit': 'lovelace', 'quantity': '1000000'}], 'output_index': 2,
                    'data_hash': None, 'inline_datum': None, 'collateral': False,
                    'reference_script_hash': None}, {
                    'address': 'addr1q8u9r5uaa5lsl2vrd979htq6c7mslx5hsnteqz7rjnp92kr5e04vm5h6ln9pplarzjdtp8grwl5ntjk9693twyh9xzeqctht6m',
                    'amount': [{'unit': 'lovelace', 'quantity': '45323541'}], 'output_index': 3,
                    'data_hash': None, 'inline_datum': None, 'collateral': False,
                    'reference_script_hash': None}]}
        ]
        expected_txs_details = [
            {'hash': '206485c0d8e3893bc534782c3665d0bfa6f03f9c7b6d4df16fb4fe4eeb329f57', 'success': True,
             'block': 10568207, 'date': datetime.datetime(2024, 7, 13, 16, 23, 16, tzinfo=datetime.timezone.utc),
             'fees': Decimal('0.228785'),
             'memo': None, 'confirmations': 7707, 'raw': None, 'inputs': [], 'outputs': [],
             'transfers': [
                 {'type': 'MainCoin', 'symbol': 'ADA', 'currency': 21,
                  'from': 'addr1q8u9r5uaa5lsl2vrd979htq6c7mslx5hsnteqz7rjnp92kr5e04vm5h6ln9pplarzjdtp8grwl5ntjk9693twyh9xzeqctht6m',
                  'to': '', 'value': Decimal('103.728785'), 'is_valid': True, 'token': None, 'memo': None},
                 {'type': 'MainCoin', 'symbol': 'ADA', 'currency': 21, 'from': '',
                  'to': 'addr1z8d70g7c58vznyye9guwagdza74x36f3uff0eyk2zwpcpxm5e04vm5h6ln9pplarzjdtp8grwl5ntjk9693twyh9xzeq22kq5u',
                  'value': Decimal('102.500000'), 'is_valid': True, 'token': None,  'memo': None},
                 {'type': 'MainCoin', 'symbol': 'ADA', 'currency': 21, 'from': '',
                  'to': 'addr1q8l7hny7x96fadvq8cukyqkcfca5xmkrvfrrkt7hp76v3qvssm7fz9ajmtd58ksljgkyvqu6gl23hlcfgv7um5v0rn8qtnzlfk',
                  'value': Decimal('1.000000'), 'is_valid': True, 'token': None,  'memo': None}]}
        ]
        cls.get_tx_details(tx_details_mock_responses, expected_txs_details)

    @classmethod
    def test_get_address_txs(cls):
        APIS_CONF[cls.symbol]['get_txs'] = 'ada_explorer_interface'
        address_txs_mock_response = [
            {'time': 1721045071, 'height': 10580372,
             'hash': '4f30b31910ae80bb6ce9d73f75ec15fdcb6c610bedc2c7f615e5874c5ce1e0a3', 'slot': 129478780,
             'epoch': 497, 'epoch_slot': 137980,
             'slot_leader': 'pool1kcfe6evpfmh5rh40yta3qrrudsy956scuwfl7wgts0z926z6kuw', 'size': 8737, 'tx_count': 3,
             'output': '200679383021', 'fees': '962257',
             'block_vrf': 'vrf_vk1lerhzrtn5yl9t6dkl9ad3l4ch8lm8x424q0qqrdy93fycneczcds0k6qw4',
             'op_cert': 'c6571f5e78cb730a849b6d41fd92076e0f4d2e90b237765851f0c455038689b0', 'op_cert_counter': '3',
             'previous_block': '5e5468bcbb792968dc2601b14da26edd8461fcf950c53000386766b904701c51', 'next_block': None,
             'confirmations': 0},

            [{'tx_hash': '1ce151f58225c0236197a1267f1907787e58c4ae61444c0fd5815aa1d94d5c75', 'tx_index': 5,
              'block_height': 10571084, 'block_time': 1720946191},
             {'tx_hash': '13cbf66386e24fcada40d216ef95de3bd1a0fd522019e6e37665bda7725d587f', 'tx_index': 2,
              'block_height': 10571081, 'block_time': 1720946177},
             {'tx_hash': '1771d7c0def86b707e81fdbc5b235570cbe70a95b9346ab97fe20b1fb80448d0', 'tx_index': 0,
              'block_height': 10571054, 'block_time': 1720945493},
             {'tx_hash': '3f5f201912d095bd2663d0485a890cd38d4229bd6a354bc08183f0e112e137ec', 'tx_index': 4,
              'block_height': 10571052, 'block_time': 1720945463}],

            {'hash': '1ce151f58225c0236197a1267f1907787e58c4ae61444c0fd5815aa1d94d5c75',
             'block': 'd1cd0d9c18f1bd79ce2637e3e544e7ba08d1bf6d80ba3d8955c8efe973e101f2', 'block_height': 10571084,
             'block_time': 1720946191, 'slot': 129379900, 'index': 5,
             'output_amount': [{'unit': 'lovelace', 'quantity': '12132481802964'}, {
                 'unit': 'f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c82e2b1fd27a7712a1a9cf750dfbea1a5778611b20e06dd6a611df7a643f8cb75',
                 'quantity': '4302755750'}, {'unit': '29d222ce763455e3d7a09a665ce554f00ac89d2e99a1a83d267170c64d494e',
                                             'quantity': '230026576471709'},
                               {'unit': 'f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c4d5350',
                                'quantity': '1'},
                               {
                                   'unit': 'f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c82e2b1fd27a7712a1a9cf750dfbea1a5778611b20e06dd6a611df7a643f8cb75',
                                   'quantity': '9223319672781908880'}], 'fees': '387150', 'deposit': '0', 'size': 1268,
             'invalid_before': '129379897', 'invalid_hereafter': '129380077', 'utxo_count': 6, 'withdrawal_count': 1,
             'mir_cert_count': 0, 'delegation_count': 0, 'stake_cert_count': 0, 'pool_update_count': 0,
             'pool_retire_count': 0, 'asset_mint_or_burn_count': 0, 'redeemer_count': 3, 'valid_contract': True},
            {
                'hash': '1ce151f58225c0236197a1267f1907787e58c4ae61444c0fd5815aa1d94d5c75', 'inputs': [
                {'address': 'addr1w86cprpvnyxcdkj5hlyhmzwwumh6yrxcgctpvdv50rvkknqyhz3rc',
                 'amount': [{'unit': 'lovelace', 'quantity': '1961050'},
                            {'unit': 'f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c4d534753',
                             'quantity': '1'}],
                 'tx_hash': '0dc17712e37a4e741767db2f90d4ffbf69faf88b9bed4c47864f7bd912924bea', 'output_index': 0,
                 'data_hash': '32e2ec40277e3c0dabf47f5134b84ee8aae3f66bd8b8834db20ff60d7ecbe14a',
                 'inline_datum': 'd8799f9fd8799f581c5b7e23228dba75595645fc357d0f97ba258cfccfff5d588d4bb9165bffffd8799f581cac1871003b670526048af46deffac5aa1e40043652771d58cf210be8ffd8799f581cac1871003b670526048af46deffac5aa1e40043652771d58cf210be8ffd8799f581cc4121a88897f44e5da27899320861e020e2977b34f6b2c8afaa6f3c3ffd8799f581c25af0fc61d7285b51293a67742b588e3a6e6ad20a1b7ff5dd3379587ffd87a9f581c4abd7063ce15ef6b959630a16dc5df3b56db667ee6c9c539c2511f2affff',
                 'reference_script_hash': None, 'collateral': False, 'reference': True}, {
                    'address': 'addr1qyqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqzj2c79gy9l76sdg0xwhd7r0c0kna0tycz4y5s6mlenh8pq6a0h00',
                    'amount': [{'unit': 'lovelace', 'quantity': '18114930'}],
                    'tx_hash': '2536194d2a976370a932174c10975493ab58fd7c16395d50e62b7c0e1949baea', 'output_index': 0,
                    'data_hash': None, 'inline_datum': None,
                    'reference_script_hash': 'ea07b733d932129c378af627436e7cbc2ef0bf96e0036bb51b3bde6b',
                    'collateral': False, 'reference': True}, {
                    'address': 'addr1qyqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqzj2c79gy9l76sdg0xwhd7r0c0kna0tycz4y5s6mlenh8pq6a0h00',
                    'amount': [{'unit': 'lovelace', 'quantity': '12486070'}],
                    'tx_hash': 'cf4ecddde0d81f9ce8fcc881a85eb1f8ccdaf6807f03fea4cd02da896a621776', 'output_index': 0,
                    'data_hash': None, 'inline_datum': None,
                    'reference_script_hash': 'c3e28c36c3447315ba5a56f33da6a6ddc1770a876a8d9f0cb3a97c4c',
                    'collateral': False, 'reference': True}, {
                    'address': 'addr1qyqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqzj2c79gy9l76sdg0xwhd7r0c0kna0tycz4y5s6mlenh8pq6a0h00',
                    'amount': [{'unit': 'lovelace', 'quantity': '68429870'}],
                    'tx_hash': 'd46bd227bd2cf93dedd22ae9b6d92d30140cf0d68b756f6608e38d680c61ad17', 'output_index': 0,
                    'data_hash': None, 'inline_datum': None,
                    'reference_script_hash': '1eae96baf29e27682ea3f815aba361a0c6059d45e4bfbe95bbd2f44a',
                    'collateral': False, 'reference': True}, {
                    'address': 'addr1z8p79rpkcdz8x9d6tft0x0dx5mwuzac2sa4gm8cvkw5hcnxxmamn55j2l2l620dvu22rw5ag2gfdddq6sn3aqmy374rs0raldq',
                    'amount': [{'unit': 'lovelace', 'quantity': '999841432'},
                               {'unit': '29d222ce763455e3d7a09a665ce554f00ac89d2e99a1a83d267170c64d494e',
                                'quantity': '18901290910'}],
                    'tx_hash': '13cbf66386e24fcada40d216ef95de3bd1a0fd522019e6e37665bda7725d587f', 'output_index': 0,
                    'data_hash': 'd6733b9142a9b5460936d5bd93af44740c43546adaa0396c28dbe1f17d894a2d',
                    'inline_datum': 'd8799fd8799f581c6b22d12477ed7e3b6b9f9a8b56406a8b055cce960caa6bc91d14df12ffd8799fd8799f581c6b22d12477ed7e3b6b9f9a8b56406a8b055cce960caa6bc91d14df12ffd8799fd8799fd8799f581cc6df773a524afabfa53dace2943753a85212d6b41a84e3d06c91f547ffffffffd87980d8799fd8799f581c6b22d12477ed7e3b6b9f9a8b56406a8b055cce960caa6bc91d14df12ffd8799fd8799fd8799f581cc6df773a524afabfa53dace2943753a85212d6b41a84e3d06c91f547ffffffffd87980d8799f581cf5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c582082e2b1fd27a7712a1a9cf750dfbea1a5778611b20e06dd6a611df7a643f8cb75ffd87d9fd8799f1a3b6a97d81b00000004669acf9eff1aff3033a1d87980ff1a000f4240d87a80ff',
                    'reference_script_hash': None, 'collateral': False, 'reference': False}, {
                    'address': 'addr1z84q0denmyep98ph3tmzwsmw0j7zau9ljmsqx6a4rvaau66j2c79gy9l76sdg0xwhd7r0c0kna0tycz4y5s6mlenh8pq777e2a',
                    'amount': [{'unit': 'lovelace', 'quantity': '12130473859063'},
                               {'unit': '29d222ce763455e3d7a09a665ce554f00ac89d2e99a1a83d267170c64d494e',
                                'quantity': '230007675180799'},
                               {'unit': 'f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c4d5350',
                                'quantity': '1'}, {
                                   'unit': 'f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c82e2b1fd27a7712a1a9cf750dfbea1a5778611b20e06dd6a611df7a643f8cb75',
                                   'quantity': '9223319677084664630'}],
                    'tx_hash': 'e3c4891578091f7ce3043e40f0301f45d063178ffd277a6a4a0b1adef383a23d', 'output_index': 1,
                    'data_hash': '8a4f96dc11a7e03467c530e9242f388a7890a7afc58ce3f7c916f8dc6615e89e',
                    'inline_datum': 'd8799fd8799fd87a9f581c1eae96baf29e27682ea3f815aba361a0c6059d45e4bfbe95bbd2f44affffd8799f4040ffd8799f581c29d222ce763455e3d7a09a665ce554f00ac89d2e99a1a83d267170c6434d494eff1b00002f9ef57f7cd31b00000b08581685771b0000d130d029720a181e1864d8799f190d05ffd87980ff',
                    'reference_script_hash': None, 'collateral': False, 'reference': False}, {
                    'address': 'addr1q9dhugez3ka82k2kgh7r2lg0j7aztr8uell46kydfwu3vk6n8w2cdu8mn2ha278q6q25a9rc6gmpfeekavuargcd32vsvxhl7e',
                    'amount': [{'unit': 'lovelace', 'quantity': '1008489619'}],
                    'tx_hash': 'e710cbd3c72613291f82362521e12294b233f5b504c103abfac20dd3bd9f60a9', 'output_index': 2,
                    'data_hash': None, 'inline_datum': None, 'reference_script_hash': None, 'collateral': False,
                    'reference': False}, {
                    'address': 'addr1q9dhugez3ka82k2kgh7r2lg0j7aztr8uell46kydfwu3vk6n8w2cdu8mn2ha278q6q25a9rc6gmpfeekavuargcd32vsvxhl7e',
                    'amount': [{'unit': 'lovelace', 'quantity': '1008489619'}],
                    'tx_hash': 'e710cbd3c72613291f82362521e12294b233f5b504c103abfac20dd3bd9f60a9', 'output_index': 2,
                    'data_hash': None, 'inline_datum': None, 'reference_script_hash': None, 'collateral': True,
                    'reference': False}], 'outputs': [{
                'address': 'addr1q94j95fywlkhuwmtn7dgk4jqd29s2hxwjcx2567fr52d7ykxmamn55j2l2l620dvu22rw5ag2gfdddq6sn3aqmy374rs5tq5qa',
                'amount': [{'unit': 'lovelace', 'quantity': '2000000'}, {
                    'unit': 'f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c82e2b1fd27a7712a1a9cf750dfbea1a5778611b20e06dd6a611df7a643f8cb75',
                    'quantity': '4302755750'}], 'output_index': 0,
                'data_hash': None, 'inline_datum': None, 'collateral': False,
                'reference_script_hash': None}, {
                'address': 'addr1z84q0denmyep98ph3tmzwsmw0j7zau9ljmsqx6a4rvaau66j2c79gy9l76sdg0xwhd7r0c0kna0tycz4y5s6mlenh8pq777e2a',
                'amount': [{'unit': 'lovelace', 'quantity': '12131470700495'},
                           {
                               'unit': '29d222ce763455e3d7a09a665ce554f00ac89d2e99a1a83d267170c64d494e',
                               'quantity': '230026576471709'}, {
                               'unit': 'f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c4d5350',
                               'quantity': '1'}, {
                               'unit': 'f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c82e2b1fd27a7712a1a9cf750dfbea1a5778611b20e06dd6a611df7a643f8cb75',
                               'quantity': '9223319672781908880'}],
                'output_index': 1,
                'data_hash': '5b1989cf56bc68aedbb908262b9afd75504a45a5d5314e1b7c6e45edd9efd540',
                'inline_datum': 'd8799fd8799fd87a9f581c1eae96baf29e27682ea3f815aba361a0c6059d45e4bfbe95bbd2f44affffd8799f4040ffd8799f581c29d222ce763455e3d7a09a665ce554f00ac89d2e99a1a83d267170c6434d494eff1b00002f9ff5f654791b00000b0893811d4f1b0000d13536c44175181e1864d8799f190d05ffd87980ff',
                'collateral': False, 'reference_script_hash': None}, {
                'address': 'addr1q9dhugez3ka82k2kgh7r2lg0j7aztr8uell46kydfwu3vk6n8w2cdu8mn2ha278q6q25a9rc6gmpfeekavuargcd32vsvxhl7e',
                'amount': [{'unit': 'lovelace', 'quantity': '1009102469'}],
                'output_index': 2, 'data_hash': None, 'inline_datum': None,
                'collateral': False, 'reference_script_hash': None}, {
                'address': 'addr1q9dhugez3ka82k2kgh7r2lg0j7aztr8uell46kydfwu3vk6n8w2cdu8mn2ha278q6q25a9rc6gmpfeekavuargcd32vsvxhl7e',
                'amount': [{'unit': 'lovelace', 'quantity': '1003489619'}],
                'output_index': 3, 'data_hash': None, 'inline_datum': None,
                'collateral': True, 'reference_script_hash': None}]},

            {'hash': '13cbf66386e24fcada40d216ef95de3bd1a0fd522019e6e37665bda7725d587f',
             'block': '70bbb31b734f4412d4ca2ced880a8a71b95e8455c9060ba9f43f2ce5a702eb49', 'block_height': 10571081,
             'block_time': 1720946177, 'slot': 129379886, 'index': 2,
             'output_amount': [{'unit': 'lovelace', 'quantity': '1009486360'},
                               {'unit': '29d222ce763455e3d7a09a665ce554f00ac89d2e99a1a83d267170c64d494e',
                                'quantity': '18901290910'}], 'fees': '203341', 'deposit': '0', 'size': 1085,
             'invalid_before': None, 'invalid_hereafter': '129390487', 'utxo_count': 4, 'withdrawal_count': 0,
             'mir_cert_count': 0, 'delegation_count': 0, 'stake_cert_count': 0, 'pool_update_count': 0,
             'pool_retire_count': 0, 'asset_mint_or_burn_count': 0, 'redeemer_count': 0, 'valid_contract': True},
            {
                'hash': '13cbf66386e24fcada40d216ef95de3bd1a0fd522019e6e37665bda7725d587f', 'inputs': [{
                'address': 'addr1q94j95fywlkhuwmtn7dgk4jqd29s2hxwjcx2567fr52d7ykxmamn55j2l2l620dvu22rw5ag2gfdddq6sn3aqmy374rs5tq5qa',
                'amount': [{
                    'unit': 'lovelace',
                    'quantity': '2000000'},
                    {
                        'unit': '29d222ce763455e3d7a09a665ce554f00ac89d2e99a1a83d267170c64d494e',
                        'quantity': '18901290910'}],
                'tx_hash': '1771d7c0def86b707e81fdbc5b235570cbe70a95b9346ab97fe20b1fb80448d0',
                'output_index': 0,
                'data_hash': None,
                'inline_datum': None,
                'reference_script_hash': None,
                'collateral': False,
                'reference': False},
                {
                    'address': 'addr1q94j95fywlkhuwmtn7dgk4jqd29s2hxwjcx2567fr52d7ykxmamn55j2l2l620dvu22rw5ag2gfdddq6sn3aqmy374rs5tq5qa',
                    'amount': [{
                        'unit': 'lovelace',
                        'quantity': '1007689701'}],
                    'tx_hash': '3f5f201912d095bd2663d0485a890cd38d4229bd6a354bc08183f0e112e137ec',
                    'output_index': 1,
                    'data_hash': None,
                    'inline_datum': None,
                    'reference_script_hash': None,
                    'collateral': False,
                    'reference': False}],
                'outputs': [{
                    'address': 'addr1z8p79rpkcdz8x9d6tft0x0dx5mwuzac2sa4gm8cvkw5hcnxxmamn55j2l2l620dvu22rw5ag2gfdddq6sn3aqmy374rs0raldq',
                    'amount': [{'unit': 'lovelace', 'quantity': '999841432'},
                               {'unit': '29d222ce763455e3d7a09a665ce554f00ac89d2e99a1a83d267170c64d494e',
                                'quantity': '18901290910'}], 'output_index': 0,
                    'data_hash': 'd6733b9142a9b5460936d5bd93af44740c43546adaa0396c28dbe1f17d894a2d',
                    'inline_datum': 'd8799fd8799f581c6b22d12477ed7e3b6b9f9a8b56406a8b055cce960caa6bc91d14df12ffd8799fd8799f581c6b22d12477ed7e3b6b9f9a8b56406a8b055cce960caa6bc91d14df12ffd8799fd8799fd8799f581cc6df773a524afabfa53dace2943753a85212d6b41a84e3d06c91f547ffffffffd87980d8799fd8799f581c6b22d12477ed7e3b6b9f9a8b56406a8b055cce960caa6bc91d14df12ffd8799fd8799fd8799f581cc6df773a524afabfa53dace2943753a85212d6b41a84e3d06c91f547ffffffffd87980d8799f581cf5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c582082e2b1fd27a7712a1a9cf750dfbea1a5778611b20e06dd6a611df7a643f8cb75ffd87d9fd8799f1a3b6a97d81b00000004669acf9eff1aff3033a1d87980ff1a000f4240d87a80ff',
                    'collateral': False, 'reference_script_hash': None}, {
                    'address': 'addr1q94j95fywlkhuwmtn7dgk4jqd29s2hxwjcx2567fr52d7ykxmamn55j2l2l620dvu22rw5ag2gfdddq6sn3aqmy374rs5tq5qa',
                    'amount': [{'unit': 'lovelace', 'quantity': '9644928'}], 'output_index': 1,
                    'data_hash': None, 'inline_datum': None, 'collateral': False,
                    'reference_script_hash': None}]},

            {'hash': '1771d7c0def86b707e81fdbc5b235570cbe70a95b9346ab97fe20b1fb80448d0',
             'block': 'e8ba2e4b98e2254a3a6c84e89fbe7d73e130b068c115f9da58e05df17529fa18', 'block_height': 10571054,
             'block_time': 1720945493, 'slot': 129379202, 'index': 0,
             'output_amount': [{'unit': 'lovelace', 'quantity': '12129852969430'},
                               {'unit': '29d222ce763455e3d7a09a665ce554f00ac89d2e99a1a83d267170c64d494e',
                                'quantity': '18901290910'},
                               {'unit': '29d222ce763455e3d7a09a665ce554f00ac89d2e99a1a83d267170c64d494e',
                                'quantity': '229978731839912'},
                               {'unit': 'f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c4d5350',
                                'quantity': '1'}, {
                                   'unit': 'f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c82e2b1fd27a7712a1a9cf750dfbea1a5778611b20e06dd6a611df7a643f8cb75',
                                   'quantity': '9223319683715756074'}], 'fees': '333353', 'deposit': '0', 'size': 1238,
             'invalid_before': '129379176', 'invalid_hereafter': '129379356', 'utxo_count': 6, 'withdrawal_count': 1,
             'mir_cert_count': 0, 'delegation_count': 0, 'stake_cert_count': 0, 'pool_update_count': 0,
             'pool_retire_count': 0, 'asset_mint_or_burn_count': 0, 'redeemer_count': 3, 'valid_contract': True},
            {
                'hash': '1771d7c0def86b707e81fdbc5b235570cbe70a95b9346ab97fe20b1fb80448d0', 'inputs': [
                {'address': 'addr1w86cprpvnyxcdkj5hlyhmzwwumh6yrxcgctpvdv50rvkknqyhz3rc',
                 'amount': [{'unit': 'lovelace', 'quantity': '1961050'},
                            {'unit': 'f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c4d534753',
                             'quantity': '1'}],
                 'tx_hash': '0dc17712e37a4e741767db2f90d4ffbf69faf88b9bed4c47864f7bd912924bea', 'output_index': 0,
                 'data_hash': '32e2ec40277e3c0dabf47f5134b84ee8aae3f66bd8b8834db20ff60d7ecbe14a',
                 'inline_datum': 'd8799f9fd8799f581c5b7e23228dba75595645fc357d0f97ba258cfccfff5d588d4bb9165bffffd8799f581cac1871003b670526048af46deffac5aa1e40043652771d58cf210be8ffd8799f581cac1871003b670526048af46deffac5aa1e40043652771d58cf210be8ffd8799f581cc4121a88897f44e5da27899320861e020e2977b34f6b2c8afaa6f3c3ffd8799f581c25af0fc61d7285b51293a67742b588e3a6e6ad20a1b7ff5dd3379587ffd87a9f581c4abd7063ce15ef6b959630a16dc5df3b56db667ee6c9c539c2511f2affff',
                 'reference_script_hash': None, 'collateral': False, 'reference': True}, {
                    'address': 'addr1qyqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqzj2c79gy9l76sdg0xwhd7r0c0kna0tycz4y5s6mlenh8pq6a0h00',
                    'amount': [{'unit': 'lovelace', 'quantity': '18114930'}],
                    'tx_hash': '2536194d2a976370a932174c10975493ab58fd7c16395d50e62b7c0e1949baea', 'output_index': 0,
                    'data_hash': None, 'inline_datum': None,
                    'reference_script_hash': 'ea07b733d932129c378af627436e7cbc2ef0bf96e0036bb51b3bde6b',
                    'collateral': False, 'reference': True}, {
                    'address': 'addr1qyqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqzj2c79gy9l76sdg0xwhd7r0c0kna0tycz4y5s6mlenh8pq6a0h00',
                    'amount': [{'unit': 'lovelace', 'quantity': '12486070'}],
                    'tx_hash': 'cf4ecddde0d81f9ce8fcc881a85eb1f8ccdaf6807f03fea4cd02da896a621776', 'output_index': 0,
                    'data_hash': None, 'inline_datum': None,
                    'reference_script_hash': 'c3e28c36c3447315ba5a56f33da6a6ddc1770a876a8d9f0cb3a97c4c',
                    'collateral': False, 'reference': True}, {
                    'address': 'addr1qyqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqzj2c79gy9l76sdg0xwhd7r0c0kna0tycz4y5s6mlenh8pq6a0h00',
                    'amount': [{'unit': 'lovelace', 'quantity': '68429870'}],
                    'tx_hash': 'd46bd227bd2cf93dedd22ae9b6d92d30140cf0d68b756f6608e38d680c61ad17', 'output_index': 0,
                    'data_hash': None, 'inline_datum': None,
                    'reference_script_hash': '1eae96baf29e27682ea3f815aba361a0c6059d45e4bfbe95bbd2f44a',
                    'collateral': False, 'reference': True}, {
                    'address': 'addr1z84q0denmyep98ph3tmzwsmw0j7zau9ljmsqx6a4rvaau66j2c79gy9l76sdg0xwhd7r0c0kna0tycz4y5s6mlenh8pq777e2a',
                    'amount': [{'unit': 'lovelace', 'quantity': '12127928005624'},
                               {'unit': '29d222ce763455e3d7a09a665ce554f00ac89d2e99a1a83d267170c64d494e',
                                'quantity': '229997633130822'},
                               {'unit': 'f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c4d5350',
                                'quantity': '1'}, {
                                   'unit': 'f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c82e2b1fd27a7712a1a9cf750dfbea1a5778611b20e06dd6a611df7a643f8cb75',
                                   'quantity': '9223319683715756074'}],
                    'tx_hash': '247dfd24d9fb380f1b342b582abf0154ac40a9b80cc456521403203033957df8', 'output_index': 1,
                    'data_hash': 'f951ee936fad28b657bb7598fd78e406f2d820fb4e223ca56ed1ff1028f7cd9b',
                    'inline_datum': 'd8799fd8799fd87a9f581c1eae96baf29e27682ea3f815aba361a0c6059d45e4bfbe95bbd2f44affffd8799f4040ffd8799f581c29d222ce763455e3d7a09a665ce554f00ac89d2e99a1a83d267170c6434d494eff1b00002f9d6a410fdf1b00000b07c06748cb1b0000d12e799bec51181e1864d8799f190d05ffd87980ff',
                    'reference_script_hash': None, 'collateral': False, 'reference': False}, {
                    'address': 'addr1q9dhugez3ka82k2kgh7r2lg0j7aztr8uell46kydfwu3vk6n8w2cdu8mn2ha278q6q25a9rc6gmpfeekavuargcd32vsvxhl7e',
                    'amount': [{'unit': 'lovelace', 'quantity': '922538536'}],
                    'tx_hash': '247dfd24d9fb380f1b342b582abf0154ac40a9b80cc456521403203033957df8', 'output_index': 2,
                    'data_hash': None, 'inline_datum': None, 'reference_script_hash': None, 'collateral': False,
                    'reference': False}, {
                    'address': 'addr1z8p79rpkcdz8x9d6tft0x0dx5mwuzac2sa4gm8cvkw5hcnxxmamn55j2l2l620dvu22rw5ag2gfdddq6sn3aqmy374rs0raldq',
                    'amount': [{'unit': 'lovelace', 'quantity': '1002758623'}],
                    'tx_hash': '3f5f201912d095bd2663d0485a890cd38d4229bd6a354bc08183f0e112e137ec', 'output_index': 0,
                    'data_hash': 'e6c2217299677dd7ca376ddb185a26dd49208f43ea4917e7dc4822e88da1014b',
                    'inline_datum': 'd8799fd8799f581c6b22d12477ed7e3b6b9f9a8b56406a8b055cce960caa6bc91d14df12ffd8799fd8799f581c6b22d12477ed7e3b6b9f9a8b56406a8b055cce960caa6bc91d14df12ffd8799fd8799fd8799f581cc6df773a524afabfa53dace2943753a85212d6b41a84e3d06c91f547ffffffffd87980d8799fd8799f581c6b22d12477ed7e3b6b9f9a8b56406a8b055cce960caa6bc91d14df12ffd8799fd8799fd8799f581cc6df773a524afabfa53dace2943753a85212d6b41a84e3d06c91f547ffffffffd87980d8799f581cf5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c582082e2b1fd27a7712a1a9cf750dfbea1a5778611b20e06dd6a611df7a643f8cb75ffd8799fd87a80d8799f1a3b971b1fff1b0000000460ffeef8d87980ff1a000f4240d87a80ff',
                    'reference_script_hash': None, 'collateral': False, 'reference': False}, {
                    'address': 'addr1q9dhugez3ka82k2kgh7r2lg0j7aztr8uell46kydfwu3vk6n8w2cdu8mn2ha278q6q25a9rc6gmpfeekavuargcd32vsvxhl7e',
                    'amount': [{'unit': 'lovelace', 'quantity': '922538536'}],
                    'tx_hash': '247dfd24d9fb380f1b342b582abf0154ac40a9b80cc456521403203033957df8', 'output_index': 2,
                    'data_hash': None, 'inline_datum': None, 'reference_script_hash': None, 'collateral': True,
                    'reference': False}], 'outputs': [{
                'address': 'addr1q94j95fywlkhuwmtn7dgk4jqd29s2hxwjcx2567fr52d7ykxmamn55j2l2l620dvu22rw5ag2gfdddq6sn3aqmy374rs5tq5qa',
                'amount': [{'unit': 'lovelace', 'quantity': '2000000'}, {
                    'unit': '29d222ce763455e3d7a09a665ce554f00ac89d2e99a1a83d267170c64d494e',
                    'quantity': '18901290910'}], 'output_index': 0,
                'data_hash': None, 'inline_datum': None, 'collateral': False,
                'reference_script_hash': None}, {
                'address': 'addr1z84q0denmyep98ph3tmzwsmw0j7zau9ljmsqx6a4rvaau66j2c79gy9l76sdg0xwhd7r0c0kna0tycz4y5s6mlenh8pq777e2a',
                'amount': [{'unit': 'lovelace', 'quantity': '12128927764247'},
                           {
                               'unit': '29d222ce763455e3d7a09a665ce554f00ac89d2e99a1a83d267170c64d494e',
                               'quantity': '229978731839912'}, {
                               'unit': 'f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c4d5350',
                               'quantity': '1'}, {
                               'unit': 'f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c82e2b1fd27a7712a1a9cf750dfbea1a5778611b20e06dd6a611df7a643f8cb75',
                               'quantity': '9223319683715756074'}],
                'output_index': 1,
                'data_hash': 'd041bd153d8016531bce293fb9327531f859ad76258655681738f47ccdb26772',
                'inline_datum': 'd8799fd8799fd87a9f581c1eae96baf29e27682ea3f815aba361a0c6059d45e4bfbe95bbd2f44affffd8799f4040ffd8799f581c29d222ce763455e3d7a09a665ce554f00ac89d2e99a1a83d267170c6434d494eff1b00002f9d6a410fdf1b00000b07fbef23001b0000d12a13011cb3181e1864d8799f190d05ffd87980ff',
                'collateral': False, 'reference_script_hash': None}, {
                'address': 'addr1q9dhugez3ka82k2kgh7r2lg0j7aztr8uell46kydfwu3vk6n8w2cdu8mn2ha278q6q25a9rc6gmpfeekavuargcd32vsvxhl7e',
                'amount': [{'unit': 'lovelace', 'quantity': '923205183'}],
                'output_index': 2, 'data_hash': None, 'inline_datum': None,
                'collateral': False, 'reference_script_hash': None}, {
                'address': 'addr1q9dhugez3ka82k2kgh7r2lg0j7aztr8uell46kydfwu3vk6n8w2cdu8mn2ha278q6q25a9rc6gmpfeekavuargcd32vsvxhl7e',
                'amount': [{'unit': 'lovelace', 'quantity': '917538536'}],
                'output_index': 3, 'data_hash': None, 'inline_datum': None,
                'collateral': True, 'reference_script_hash': None}]},

            {'hash': '3f5f201912d095bd2663d0485a890cd38d4229bd6a354bc08183f0e112e137ec',
             'block': '2cc4819bdb74e973496c8991c91bae4bcc9333346f034279482aa1067ed261a4', 'block_height': 10571052,
             'block_time': 1720945463, 'slot': 129379172, 'index': 4,
             'output_amount': [{'unit': 'lovelace', 'quantity': '2010448324'}], 'fees': '185213', 'deposit': '0',
             'size': 673, 'invalid_before': None, 'invalid_hereafter': '129389918', 'utxo_count': 3,
             'withdrawal_count': 0, 'mir_cert_count': 0, 'delegation_count': 0, 'stake_cert_count': 0,
             'pool_update_count': 0, 'pool_retire_count': 0, 'asset_mint_or_burn_count': 0, 'redeemer_count': 0,
             'valid_contract': True},
            {
                'hash': '3f5f201912d095bd2663d0485a890cd38d4229bd6a354bc08183f0e112e137ec', 'inputs': [{
                'address': 'addr1q94j95fywlkhuwmtn7dgk4jqd29s2hxwjcx2567fr52d7ykxmamn55j2l2l620dvu22rw5ag2gfdddq6sn3aqmy374rs5tq5qa',
                'amount': [{
                    'unit': 'lovelace',
                    'quantity': '2010633537'}],
                'tx_hash': 'd1697275ee311e9b9b08822217dec1897fc79f1c5c16d1b6aedf30080a19774d',
                'output_index': 0,
                'data_hash': None,
                'inline_datum': None,
                'reference_script_hash': None,
                'collateral': False,
                'reference': False}],
                'outputs': [{
                    'address': 'addr1z8p79rpkcdz8x9d6tft0x0dx5mwuzac2sa4gm8cvkw5hcnxxmamn55j2l2l620dvu22rw5ag2gfdddq6sn3aqmy374rs0raldq',
                    'amount': [{'unit': 'lovelace', 'quantity': '1002758623'}], 'output_index': 0,
                    'data_hash': 'e6c2217299677dd7ca376ddb185a26dd49208f43ea4917e7dc4822e88da1014b',
                    'inline_datum': 'd8799fd8799f581c6b22d12477ed7e3b6b9f9a8b56406a8b055cce960caa6bc91d14df12ffd8799fd8799f581c6b22d12477ed7e3b6b9f9a8b56406a8b055cce960caa6bc91d14df12ffd8799fd8799fd8799f581cc6df773a524afabfa53dace2943753a85212d6b41a84e3d06c91f547ffffffffd87980d8799fd8799f581c6b22d12477ed7e3b6b9f9a8b56406a8b055cce960caa6bc91d14df12ffd8799fd8799fd8799f581cc6df773a524afabfa53dace2943753a85212d6b41a84e3d06c91f547ffffffffd87980d8799f581cf5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c582082e2b1fd27a7712a1a9cf750dfbea1a5778611b20e06dd6a611df7a643f8cb75ffd8799fd87a80d8799f1a3b971b1fff1b0000000460ffeef8d87980ff1a000f4240d87a80ff',
                    'collateral': False, 'reference_script_hash': None}, {
                    'address': 'addr1q94j95fywlkhuwmtn7dgk4jqd29s2hxwjcx2567fr52d7ykxmamn55j2l2l620dvu22rw5ag2gfdddq6sn3aqmy374rs5tq5qa',
                    'amount': [{'unit': 'lovelace', 'quantity': '1007689701'}], 'output_index': 1,
                    'data_hash': None, 'inline_datum': None, 'collateral': False,
                    'reference_script_hash': None}]}
        ]
        expected_address_txs = [
            [{'contract_address': None,
              'address': 'addr1z8p79rpkcdz8x9d6tft0x0dx5mwuzac2sa4gm8cvkw5hcnxxmamn55j2l2l620dvu22rw5ag2gfdddq6sn3aqmy374rs0raldq',
              'from_address': [
                  'addr1z8p79rpkcdz8x9d6tft0x0dx5mwuzac2sa4gm8cvkw5hcnxxmamn55j2l2l620dvu22rw5ag2gfdddq6sn3aqmy374rs0raldq'],
              'hash': '1ce151f58225c0236197a1267f1907787e58c4ae61444c0fd5815aa1d94d5c75', 'block': 10571084,
              'timestamp': datetime.datetime(2024, 7, 14, 8, 36, 31, tzinfo=datetime.timezone.utc),
              'value': Decimal('-999.841432'),
              'confirmations': 9288, 'is_double_spend': False, 'details': {}, 'tag': None, 'huge': False,
              'invoice': None},
             {'contract_address': None,
              'address': 'addr1z8p79rpkcdz8x9d6tft0x0dx5mwuzac2sa4gm8cvkw5hcnxxmamn55j2l2l620dvu22rw5ag2gfdddq6sn3aqmy374rs0raldq',
              'from_address': [],
              'hash': '13cbf66386e24fcada40d216ef95de3bd1a0fd522019e6e37665bda7725d587f',
              'block': 10571081, 'timestamp': datetime.datetime(2024, 7, 14, 8, 36, 17, tzinfo=datetime.timezone.utc),
              'value': Decimal('999.841432'), 'confirmations': 9291, 'is_double_spend': False,
              'details': {}, 'tag': None, 'huge': False, 'invoice': None},
             {'contract_address': None,
              'address': 'addr1z8p79rpkcdz8x9d6tft0x0dx5mwuzac2sa4gm8cvkw5hcnxxmamn55j2l2l620dvu22rw5ag2gfdddq6sn3aqmy374rs0raldq',
              'from_address': [
                  'addr1z8p79rpkcdz8x9d6tft0x0dx5mwuzac2sa4gm8cvkw5hcnxxmamn55j2l2l620dvu22rw5ag2gfdddq6sn3aqmy374rs0raldq'],
              'hash': '1771d7c0def86b707e81fdbc5b235570cbe70a95b9346ab97fe20b1fb80448d0',
              'block': 10571054,
              'timestamp': datetime.datetime(2024, 7, 14, 8, 24, 53, tzinfo=datetime.timezone.utc),
              'value': Decimal('-1002.758623'),
              'confirmations': 9318,
              'is_double_spend': False,
              'details': {},
              'tag': None,
              'huge': False,
              'invoice': None},
             {'contract_address': None,
              'address': 'addr1z8p79rpkcdz8x9d6tft0x0dx5mwuzac2sa4gm8cvkw5hcnxxmamn55j2l2l620dvu22rw5ag2gfdddq6sn3aqmy374rs0raldq',
              'from_address': [], 'hash': '3f5f201912d095bd2663d0485a890cd38d4229bd6a354bc08183f0e112e137ec',
              'block': 10571052, 'timestamp': datetime.datetime(2024, 7, 14, 8, 24, 23, tzinfo=datetime.timezone.utc),
              'value': Decimal('1002.758623'), 'confirmations': 9320, 'is_double_spend': False, 'details': {},
              'tag': None, 'huge': False, 'invoice': None}]
        ]
        cls.get_address_txs(address_txs_mock_response, expected_address_txs)

    @classmethod
    def test_get_block_txs(cls):
        APIS_CONF[cls.symbol]['get_blocks_addresses'] = 'ada_explorer_interface'
        block_txs_mock_response = [
            {'time': 1721045071, 'height': 10580372,
             'hash': '4f30b31910ae80bb6ce9d73f75ec15fdcb6c610bedc2c7f615e5874c5ce1e0a3', 'slot': 129478780,
             'epoch': 497, 'epoch_slot': 137980,
             'slot_leader': 'pool1kcfe6evpfmh5rh40yta3qrrudsy956scuwfl7wgts0z926z6kuw', 'size': 8737, 'tx_count': 3,
             'output': '200679383021', 'fees': '962257',
             'block_vrf': 'vrf_vk1lerhzrtn5yl9t6dkl9ad3l4ch8lm8x424q0qqrdy93fycneczcds0k6qw4',
             'op_cert': 'c6571f5e78cb730a849b6d41fd92076e0f4d2e90b237765851f0c455038689b0', 'op_cert_counter': '3',
             'previous_block': '5e5468bcbb792968dc2601b14da26edd8461fcf950c53000386766b904701c51', 'next_block': None,
             'confirmations': 0},

            ['5a54c4ec018f6a08ff0ea573d3d38c6f39fa0590a8b5c250d9b350a516fd2e4a',
             '76bf48e35c69b835b205b6728692a78e585d994fe55bc514e0a0e6329980886b',
             '39af7d9b43d7a56bc37fe98edd1cf68342218b912ebfecde23f660893ce87072',
             '2cd17d51dadd1cd2d2476666a04eb681f479031b136dd1e749e948b78ce38a85',
             '3c9f57e6fc0b32e94b87a2bfa5bd4f1cd69c4d1a1379a1130e28989ae7597dc7'],

            {'hash': '5a54c4ec018f6a08ff0ea573d3d38c6f39fa0590a8b5c250d9b350a516fd2e4a',
             'block': '5ba3b3ce142a73c01c1a543ba91f14eaf45ab014fb5511815d03ee2372771e67', 'block_height': 10579202,
             'block_time': 1721112252, 'slot': 129545961, 'index': 0,
             'output_amount': [{'unit': 'lovelace', 'quantity': '10864907863'}], 'fees': '186181', 'deposit': '0',
             'size': 695, 'invalid_before': None, 'invalid_hereafter': None, 'utxo_count': 7, 'withdrawal_count': 0,
             'mir_cert_count': 0, 'delegation_count': 0, 'stake_cert_count': 0, 'pool_update_count': 0,
             'pool_retire_count': 0, 'asset_mint_or_burn_count': 0, 'redeemer_count': 0, 'valid_contract': True},
            {
                'hash': '5a54c4ec018f6a08ff0ea573d3d38c6f39fa0590a8b5c250d9b350a516fd2e4a', 'inputs': [{
                'address': 'addr1qy9vxqa5x2txd3s8p9hap6adpkn779havzftrc9e7cvta6snshevc7a5l3n43ru8jmv093m73appnlkvn6748nqg4vjqzfhn5t',
                'amount': [{
                    'unit': 'lovelace',
                    'quantity': '2240674102'}],
                'tx_hash': '6b1791d9f07606778f2b4a3eae4d1e6434c6ab542cc288a22349b34371e6398d',
                'output_index': 1,
                'data_hash': None,
                'inline_datum': None,
                'reference_script_hash': None,
                'collateral': False,
                'reference': False},
                {
                    'address': 'addr1qy9vxqa5x2txd3s8p9hap6adpkn779havzftrc9e7cvta6snshevc7a5l3n43ru8jmv093m73appnlkvn6748nqg4vjqzfhn5t',
                    'amount': [{
                        'unit': 'lovelace',
                        'quantity': '2000000000'}],
                    'tx_hash': 'b0d86e5d1a4c46e3772e5a870b3c8c41a3355f7496931cab80c355afc0268e6e',
                    'output_index': 0,
                    'data_hash': None,
                    'inline_datum': None,
                    'reference_script_hash': None,
                    'collateral': False,
                    'reference': False},
                {
                    'address': 'addr1qy9vxqa5x2txd3s8p9hap6adpkn779havzftrc9e7cvta6snshevc7a5l3n43ru8jmv093m73appnlkvn6748nqg4vjqzfhn5t',
                    'amount': [{
                        'unit': 'lovelace',
                        'quantity': '2274386941'}],
                    'tx_hash': 'c82fd3444ffef56def35c80c043bd5d2059d282c10f93f798b5688fce114ef02',
                    'output_index': 1,
                    'data_hash': None,
                    'inline_datum': None,
                    'reference_script_hash': None,
                    'collateral': False,
                    'reference': False},
                {
                    'address': 'addr1qy9vxqa5x2txd3s8p9hap6adpkn779havzftrc9e7cvta6snshevc7a5l3n43ru8jmv093m73appnlkvn6748nqg4vjqzfhn5t',
                    'amount': [{
                        'unit': 'lovelace',
                        'quantity': '2190848212'}],
                    'tx_hash': 'cb740f9a1ad653b2397258f99d9df767e20c00d6ebb1b2d1589db84e3ecc6f5c',
                    'output_index': 1,
                    'data_hash': None,
                    'inline_datum': None,
                    'reference_script_hash': None,
                    'collateral': False,
                    'reference': False},
                {
                    'address': 'addr1qy9vxqa5x2txd3s8p9hap6adpkn779havzftrc9e7cvta6snshevc7a5l3n43ru8jmv093m73appnlkvn6748nqg4vjqzfhn5t',
                    'amount': [{
                        'unit': 'lovelace',
                        'quantity': '2159184789'}],
                    'tx_hash': 'cbb8e201c792864e20987a98112f65e6b006edb75d3ed2426a24b8aba89e2b76',
                    'output_index': 1,
                    'data_hash': None,
                    'inline_datum': None,
                    'reference_script_hash': None,
                    'collateral': False,
                    'reference': False}],
                'outputs': [{
                    'address': 'addr1z8d70g7c58vznyye9guwagdza74x36f3uff0eyk2zwpcpxcnshevc7a5l3n43ru8jmv093m73appnlkvn6748nqg4vjq9xzljd',
                    'amount': [{'unit': 'lovelace', 'quantity': '10002000000'}], 'output_index': 0,
                    'data_hash': 'e36c91d9b4b314c15556fb0c9a2e11cb7dd4a1357e554498510b08cd630890f2',
                    'inline_datum': 'd8798c4100581c00d22470b9b511281e21009bfaf60fdc3fc73d85f1b9dcb2b5d62180d8798240401b00000002540be4001a0007a1201b000000021d8f8974d87982581cf6099832f9563e4cf59602b3351c3c5a8a7dda2d44575ef69b82cf8d40d879821b0020478f73212c7f1b002386f26fc1000000d87982d87981581c0ac303b4329666c607096fd0ebad0da7ef16fd6092b1e0b9f618beead87981d87981d87981581c1385f2cc7bb4fc67588f8796d8f2c77e8f4219fecc9ebd53cc08ab24581c0ac303b4329666c607096fd0ebad0da7ef16fd6092b1e0b9f618beea81581c2f9ff04d8914bf64d671a03d34ab7937eb417831ea6b9f7fbcab96f5',
                    'collateral': False, 'reference_script_hash': None}, {
                    'address': 'addr1qy9vxqa5x2txd3s8p9hap6adpkn779havzftrc9e7cvta6snshevc7a5l3n43ru8jmv093m73appnlkvn6748nqg4vjqzfhn5t',
                    'amount': [{'unit': 'lovelace', 'quantity': '862907863'}], 'output_index': 1,
                    'data_hash': None, 'inline_datum': None, 'collateral': False,
                    'reference_script_hash': None}]},

            {
                'hash': '76bf48e35c69b835b205b6728692a78e585d994fe55bc514e0a0e6329980886b',
                'block': '5ba3b3ce142a73c01c1a543ba91f14eaf45ab014fb5511815d03ee2372771e67', 'block_height': 10579202,
                'block_time': 1721112252, 'slot': 129545961, 'index': 1,
                'output_amount': [{'unit': 'lovelace', 'quantity': '5575940037328'},
                                  {'unit': '54ebc6127f8eb6a4c297827db6e3139ee3820f5e216cf5e0889256416c71',
                                   'quantity': '9223359879277249250'},
                                  {'unit': '9b04cc602ed685b69356c050653ffd92bb291f8e599dc9827252ef416e6674',
                                   'quantity': '1'},
                                  {'unit': 'f6099832f9563e4cf59602b3351c3c5a8a7dda2d44575ef69b82cf8d',
                                   'quantity': '6626166627540'},
                                  {'unit': 'f6099832f9563e4cf59602b3351c3c5a8a7dda2d44575ef69b82cf8d',
                                   'quantity': '9994396047'}], 'fees': '330824', 'deposit': '0', 'size': 924,
                'invalid_before': None, 'invalid_hereafter': None, 'utxo_count': 4, 'withdrawal_count': 1,
                'mir_cert_count': 0, 'delegation_count': 0, 'stake_cert_count': 0, 'pool_update_count': 0,
                'pool_retire_count': 0, 'asset_mint_or_burn_count': 0, 'redeemer_count': 3, 'valid_contract': True},
            {
                'hash': '76bf48e35c69b835b205b6728692a78e585d994fe55bc514e0a0e6329980886b', 'inputs': [
                {'address': 'addr1w98v2rexyjaxyppmaezyfz7fkwy059ewpde7l9xr4vhcp9qhtzss2',
                 'amount': [{'unit': 'lovelace', 'quantity': '14606590'}],
                 'tx_hash': '43da5e009b4c7d8594c5dc51d3901b89da9d64d208b7b2fa8980a90c42601132', 'output_index': 0,
                 'data_hash': None, 'inline_datum': None,
                 'reference_script_hash': '5d3df99fcfbbf282bd76a3d76a2e30bdd22e61c56f1462447938933b',
                 'collateral': False, 'reference': True},
                {'address': 'addr1w98v2rexyjaxyppmaezyfz7fkwy059ewpde7l9xr4vhcp9qhtzss2',
                 'amount': [{'unit': 'lovelace', 'quantity': '9076860'}],
                 'tx_hash': 'bbe217640f5ef47f2fd0efd70724f8dfbf674b1376ddffb30817d07c7e512d1e', 'output_index': 1,
                 'data_hash': None, 'inline_datum': None,
                 'reference_script_hash': '221ad845313837904c15a0f0107dd0cbe8bdf4a41701866dabe996e4',
                 'collateral': False, 'reference': True},
                {'address': 'addr1w98v2rexyjaxyppmaezyfz7fkwy059ewpde7l9xr4vhcp9qhtzss2',
                 'amount': [{'unit': 'lovelace', 'quantity': '5534040'}],
                 'tx_hash': 'cb0a5c67993d3bfa965f2b948f9975e0308a25c6c47e05e61773656fc58ad13c', 'output_index': 0,
                 'data_hash': None, 'inline_datum': None,
                 'reference_script_hash': 'dbe7a3d8a1d82990992a38eea1a2efaa68e931e252fc92ca1383809b',
                 'collateral': False, 'reference': True},
                {'address': 'addr1w9wnm7vle7al9q4aw63aw63wxz7aytnpc4h3gcjy0yufxwc3mr3e5',
                 'amount': [{'unit': 'lovelace', 'quantity': '5565938368152'},
                            {'unit': '54ebc6127f8eb6a4c297827db6e3139ee3820f5e216cf5e0889256416c71',
                             'quantity': '9223359879277249250'},
                            {'unit': '9b04cc602ed685b69356c050653ffd92bb291f8e599dc9827252ef416e6674', 'quantity': '1'},
                            {'unit': 'f6099832f9563e4cf59602b3351c3c5a8a7dda2d44575ef69b82cf8d',
                             'quantity': '6636161023587'}],
                 'tx_hash': '07f065f04dbf3397e3cdcc7b09a59ea53d4a40bcf8be1cbbfcb5d99464a53156', 'output_index': 0,
                 'data_hash': 'bf8e8564a0700cdb659d5e36c7fd6326157dad3f7941a763f1a91b2a9d33d81f',
                 'inline_datum': 'd8799fd8799f581c9b04cc602ed685b69356c050653ffd92bb291f8e599dc9827252ef41436e6674ff190c80d8799f4040ffd8799f581cf6099832f9563e4cf59602b3351c3c5a8a7dda2d44575ef69b82cf8d40ff0101d8799f581c54ebc6127f8eb6a4c297827db6e3139ee3820f5e216cf5e088925641426c71ffd87980d8798018640040400000ff',
                 'reference_script_hash': None, 'collateral': False, 'reference': False}, {
                    'address': 'addr1z8d70g7c58vznyye9guwagdza74x36f3uff0eyk2zwpcpxcnshevc7a5l3n43ru8jmv093m73appnlkvn6748nqg4vjq9xzljd',
                    'amount': [{'unit': 'lovelace', 'quantity': '10002000000'}],
                    'tx_hash': '5a54c4ec018f6a08ff0ea573d3d38c6f39fa0590a8b5c250d9b350a516fd2e4a', 'output_index': 0,
                    'data_hash': 'e36c91d9b4b314c15556fb0c9a2e11cb7dd4a1357e554498510b08cd630890f2',
                    'inline_datum': 'd8798c4100581c00d22470b9b511281e21009bfaf60fdc3fc73d85f1b9dcb2b5d62180d8798240401b00000002540be4001a0007a1201b000000021d8f8974d87982581cf6099832f9563e4cf59602b3351c3c5a8a7dda2d44575ef69b82cf8d40d879821b0020478f73212c7f1b002386f26fc1000000d87982d87981581c0ac303b4329666c607096fd0ebad0da7ef16fd6092b1e0b9f618beead87981d87981d87981581c1385f2cc7bb4fc67588f8796d8f2c77e8f4219fecc9ebd53cc08ab24581c0ac303b4329666c607096fd0ebad0da7ef16fd6092b1e0b9f618beea81581c2f9ff04d8914bf64d671a03d34ab7937eb417831ea6b9f7fbcab96f5',
                    'reference_script_hash': None, 'collateral': False, 'reference': False},
                {'address': 'addr1vyheluzd3y2t7exkwxsr6d9t0ym7kstcx84xh8mlhj4edag5p9quv',
                 'amount': [{'unit': 'lovelace', 'quantity': '25000000'}],
                 'tx_hash': '66965c50b1ec5dd4280ef452e03df19791a3f55613e7845f7b9e24bf9737c15d', 'output_index': 0,
                 'data_hash': None, 'inline_datum': None, 'reference_script_hash': None, 'collateral': True,
                 'reference': False}], 'outputs': [
                {'address': 'addr1w9wnm7vle7al9q4aw63aw63wxz7aytnpc4h3gcjy0yufxwc3mr3e5',
                 'amount': [{'unit': 'lovelace', 'quantity': '5575938368152'},
                            {'unit': '54ebc6127f8eb6a4c297827db6e3139ee3820f5e216cf5e0889256416c71',
                             'quantity': '9223359879277249250'},
                            {'unit': '9b04cc602ed685b69356c050653ffd92bb291f8e599dc9827252ef416e6674', 'quantity': '1'},
                            {'unit': 'f6099832f9563e4cf59602b3351c3c5a8a7dda2d44575ef69b82cf8d',
                             'quantity': '6626166627540'}], 'output_index': 0,
                 'data_hash': 'bf8e8564a0700cdb659d5e36c7fd6326157dad3f7941a763f1a91b2a9d33d81f',
                 'inline_datum': 'd8799fd8799f581c9b04cc602ed685b69356c050653ffd92bb291f8e599dc9827252ef41436e6674ff190c80d8799f4040ffd8799f581cf6099832f9563e4cf59602b3351c3c5a8a7dda2d44575ef69b82cf8d40ff0101d8799f581c54ebc6127f8eb6a4c297827db6e3139ee3820f5e216cf5e088925641426c71ffd87980d8798018640040400000ff',
                 'collateral': False, 'reference_script_hash': None}, {
                    'address': 'addr1qy9vxqa5x2txd3s8p9hap6adpkn779havzftrc9e7cvta6snshevc7a5l3n43ru8jmv093m73appnlkvn6748nqg4vjqzfhn5t',
                    'amount': [{'unit': 'lovelace', 'quantity': '1669176'},
                               {'unit': 'f6099832f9563e4cf59602b3351c3c5a8a7dda2d44575ef69b82cf8d',
                                'quantity': '9994396047'}], 'output_index': 1, 'data_hash': None, 'inline_datum': None,
                    'collateral': False, 'reference_script_hash': None}]},

            {
                'hash': '39af7d9b43d7a56bc37fe98edd1cf68342218b912ebfecde23f660893ce87072',
                'block': '5ba3b3ce142a73c01c1a543ba91f14eaf45ab014fb5511815d03ee2372771e67', 'block_height': 10579202,
                'block_time': 1721112252, 'slot': 129545961, 'index': 2,
                'output_amount': [{'unit': 'lovelace', 'quantity': '1830957961'},
                                  {'unit': '533bb94a8850ee3ccbe483106489399112b74c905342cb1792a797a0494e4459',
                                   'quantity': '16244219'},
                                  {'unit': '533bb94a8850ee3ccbe483106489399112b74c905342cb1792a797a0494e4459',
                                   'quantity': '1868016'}], 'fees': '224033', 'deposit': '0', 'size': 1044,
                'invalid_before': '129545096', 'invalid_hereafter': '129548696', 'utxo_count': 4, 'withdrawal_count': 0,
                'mir_cert_count': 0, 'delegation_count': 0, 'stake_cert_count': 0, 'pool_update_count': 0,
                'pool_retire_count': 0, 'asset_mint_or_burn_count': 0, 'redeemer_count': 0, 'valid_contract': True},
            {
                'hash': '39af7d9b43d7a56bc37fe98edd1cf68342218b912ebfecde23f660893ce87072', 'inputs': [{
                'address': 'addr1qxwzkpxr6dsaf4eg0rnupsr8eekdl8ef2cdl4dw9ju5vfcj5jckntpnwx7j5868kd7d09hcta6ad0ynsudyjgn30h82qjq8gxn',
                'amount': [{
                    'unit': 'lovelace',
                    'quantity': '1831181994'},
                    {
                        'unit': '533bb94a8850ee3ccbe483106489399112b74c905342cb1792a797a0494e4459',
                        'quantity': '18112235'}],
                'tx_hash': '795a0b91292ac65f2dd1a873362b326bdbeee9acfbd7181b6c421a7cdb95d6d3',
                'output_index': 2,
                'data_hash': None,
                'inline_datum': None,
                'reference_script_hash': None,
                'collateral': False,
                'reference': False},
                {
                    'address': 'addr1q98vmjmnxl2epge8fsetvy7hr867lkcqera8cc55scpm248r7vg0n8j87h2dxxsjdyc6h963tm0h5t2wn7z8jt05gawqjlctqr',
                    'amount': [{
                        'unit': 'lovelace',
                        'quantity': '5000000'}],
                    'tx_hash': '7091bdcaa8a14ad87f9874bf9b5bae96e5ea381b36ebb2c7aa2dc20f8116e34d',
                    'output_index': 0,
                    'data_hash': None,
                    'inline_datum': None,
                    'reference_script_hash': None,
                    'collateral': True,
                    'reference': False}],
                'outputs': [{
                    'address': 'addr1z8ax5k9mutg07p2ngscu3chsauktmstq92z9de938j8nqa65jckntpnwx7j5868kd7d09hcta6ad0ynsudyjgn30h82qukjfqz',
                    'amount': [{'unit': 'lovelace', 'quantity': '2500000'},
                               {'unit': '533bb94a8850ee3ccbe483106489399112b74c905342cb1792a797a0494e4459',
                                'quantity': '16244219'}], 'output_index': 0,
                    'data_hash': 'e3878c61ef1c2f145d2ac0c263bbc8c3c163d61e75b49f4312a60a47e12c1807',
                    'inline_datum': 'd8799fd8799f581c27f51c29cde11887b667d9632533677a82baa305a6ea43993b68909effd8799f581c54962d35866e37a543e8f66f9af2df0beebad79270e349244e2fb9d4ff1a0007a120d8799fd8799fd8799f581c9c2b04c3d361d4d72878e7c0c067ce6cdf9f29561bfab5c59728c4e2ffd8799fd8799fd8799f581c54962d35866e37a543e8f66f9af2df0beebad79270e349244e2fb9d4ffffffffd8799fffffd87a9f9f581c533bb94a8850ee3ccbe483106489399112b74c905342cb1792a797a044494e44591a00f7ddfbff9f40401a01c3d4a8ffff43d87980ff',
                    'collateral': False, 'reference_script_hash': None}, {
                    'address': 'addr1qx9sltr8w7y3hyjav340zunarmegsvu009ny2k5neccal0p3yzmswj59yx7vn630qh3ce7yjflahhjr3a0a2xkhf30eq3rd5k5',
                    'amount': [{'unit': 'lovelace', 'quantity': '1000000'}], 'output_index': 1,
                    'data_hash': None, 'inline_datum': None, 'collateral': False,
                    'reference_script_hash': None}, {
                    'address': 'addr1qxwzkpxr6dsaf4eg0rnupsr8eekdl8ef2cdl4dw9ju5vfcj5jckntpnwx7j5868kd7d09hcta6ad0ynsudyjgn30h82qjq8gxn',
                    'amount': [{'unit': 'lovelace', 'quantity': '1827457961'},
                               {'unit': '533bb94a8850ee3ccbe483106489399112b74c905342cb1792a797a0494e4459',
                                'quantity': '1868016'}], 'output_index': 2, 'data_hash': None,
                    'inline_datum': None, 'collateral': False, 'reference_script_hash': None}]},

            {
                'hash': '2cd17d51dadd1cd2d2476666a04eb681f479031b136dd1e749e948b78ce38a85',
                'block': '5ba3b3ce142a73c01c1a543ba91f14eaf45ab014fb5511815d03ee2372771e67', 'block_height': 10579202,
                'block_time': 1721112252, 'slot': 129545961, 'index': 3,
                'output_amount': [{'unit': 'lovelace', 'quantity': '4011513142'}, {
                    'unit': 'de27f9eb9ed6f011e30a56dbe09d982c9facde3a37efd92f4dfac015446f6e616c644a5472756d70',
                    'quantity': '13315892'}], 'fees': '222757', 'deposit': '0', 'size': 914,
                'invalid_before': '129545905',
                'invalid_hereafter': '129546805', 'utxo_count': 5, 'withdrawal_count': 0, 'mir_cert_count': 0,
                'delegation_count': 0, 'stake_cert_count': 0, 'pool_update_count': 0, 'pool_retire_count': 0,
                'asset_mint_or_burn_count': 0, 'redeemer_count': 0, 'valid_contract': True},
            {
                'hash': '2cd17d51dadd1cd2d2476666a04eb681f479031b136dd1e749e948b78ce38a85', 'inputs': [{
                'address': 'addr1q9qyjr3g870zsafqhyzy2nt54c366eufl064je8rthkxdlaerwjxy3uk23kjlerscpm2qxn4sp8twka333zvphrannqq2sy364',
                'amount': [{
                    'unit': 'lovelace',
                    'quantity': '2000000'},
                    {
                        'unit': 'de27f9eb9ed6f011e30a56dbe09d982c9facde3a37efd92f4dfac015446f6e616c644a5472756d70',
                        'quantity': '13315892'}],
                'tx_hash': '00183808140590cd845128ad2e9579ac3c6ac647da62346c0dae92e06aed1674',
                'output_index': 1,
                'data_hash': None,
                'inline_datum': None,
                'reference_script_hash': None,
                'collateral': False,
                'reference': False},
                {
                    'address': 'addr1q9qyjr3g870zsafqhyzy2nt54c366eufl064je8rthkxdlaerwjxy3uk23kjlerscpm2qxn4sp8twka333zvphrannqq2sy364',
                    'amount': [{
                        'unit': 'lovelace',
                        'quantity': '4009735899'}],
                    'tx_hash': '7e59582ac53440a6c63e3e8aacf0db23a48ba6fb58e67885b7f5825c9a58f201',
                    'output_index': 0,
                    'data_hash': None,
                    'inline_datum': None,
                    'reference_script_hash': None,
                    'collateral': False,
                    'reference': False}],
                'outputs': [{
                    'address': 'addr1z8ax5k9mutg07p2ngscu3chsauktmstq92z9de938j8nqaaerwjxy3uk23kjlerscpm2qxn4sp8twka333zvphrannqq3krpwy',
                    'amount': [{'unit': 'lovelace', 'quantity': '2500000'}, {
                        'unit': 'de27f9eb9ed6f011e30a56dbe09d982c9facde3a37efd92f4dfac015446f6e616c644a5472756d70',
                        'quantity': '13315892'}], 'output_index': 0,
                    'data_hash': '7fd60547e29df4eb51eb11288c494afa76ed311330ef22474399cef21b00b59a',
                    'inline_datum': 'd8799fd8799f581c913c17e9b7d6f44cdad16840efcb1cee32842b7d47f312d9bc36545fffd8799f581cb91ba4624796546d2fe470c076a01a75804eb75bb18c44c0dc7d9cc0ff1a0007a120d8799fd8799fd8799f581c40490e283f9e287520b904454d74ae23ad6789fbf55964e35dec66ffffd8799fd8799fd8799f581cb91ba4624796546d2fe470c076a01a75804eb75bb18c44c0dc7d9cc0ffffffffd8799fffffd87a9f9f581cde27f9eb9ed6f011e30a56dbe09d982c9facde3a37efd92f4dfac0154c446f6e616c644a5472756d701a00cb2f34ff9f40401a03f7ec04ffff43d87980ff',
                    'collateral': False, 'reference_script_hash': None}, {
                    'address': 'addr1qx9sltr8w7y3hyjav340zunarmegsvu009ny2k5neccal0p3yzmswj59yx7vn630qh3ce7yjflahhjr3a0a2xkhf30eq3rd5k5',
                    'amount': [{'unit': 'lovelace', 'quantity': '1000000'}], 'output_index': 1,
                    'data_hash': None, 'inline_datum': None, 'collateral': False,
                    'reference_script_hash': None}, {
                    'address': 'addr1q9qyjr3g870zsafqhyzy2nt54c366eufl064je8rthkxdlaerwjxy3uk23kjlerscpm2qxn4sp8twka333zvphrannqq2sy364',
                    'amount': [{'unit': 'lovelace', 'quantity': '4008013142'}], 'output_index': 2,
                    'data_hash': None, 'inline_datum': None, 'collateral': False,
                    'reference_script_hash': None}]},

            {'hash': '3c9f57e6fc0b32e94b87a2bfa5bd4f1cd69c4d1a1379a1130e28989ae7597dc7',
             'block': '5ba3b3ce142a73c01c1a543ba91f14eaf45ab014fb5511815d03ee2372771e67', 'block_height': 10579202,
             'block_time': 1721112252, 'slot': 129545961, 'index': 4,
             'output_amount': [{'unit': 'lovelace', 'quantity': '55130054844'}], 'fees': '168317', 'deposit': '0',
             'size': 293, 'invalid_before': None, 'invalid_hereafter': '129553149', 'utxo_count': 3,
             'withdrawal_count': 0, 'mir_cert_count': 0, 'delegation_count': 0, 'stake_cert_count': 0,
             'pool_update_count': 0, 'pool_retire_count': 0, 'asset_mint_or_burn_count': 0, 'redeemer_count': 0,
             'valid_contract': True},
            {
                'hash': '3c9f57e6fc0b32e94b87a2bfa5bd4f1cd69c4d1a1379a1130e28989ae7597dc7', 'inputs': [{
                'address': 'addr1q9ys3tqt7zxn7g8pk0r7sfl2qc8t2t2ut5qsnk3tn0zk00fyhhj0xpkpwcwqec92a62rt3uzm3t4jnnsuk5nwr32arxsdl0h36',
                'amount': [{
                    'unit': 'lovelace',
                    'quantity': '55130223161'}],
                'tx_hash': '7ff6fd9e0e7639fc399766aa6e8e5918a454825af7b90007beab0fdae38828eb',
                'output_index': 1,
                'data_hash': None,
                'inline_datum': None,
                'reference_script_hash': None,
                'collateral': False,
                'reference': False}],
                'outputs': [{
                    'address': 'addr1q9nxgzrc47sr2ngl898sfdjcczrk6svjrcvehnpn2t2cayq7zzjzvv2gwdncxr8hgpnqxzstfrk8z9vfzkzavqt6gjmq4pa4la',
                    'amount': [{'unit': 'lovelace', 'quantity': '50000000'}], 'output_index': 0,
                    'data_hash': None, 'inline_datum': None, 'collateral': False,
                    'reference_script_hash': None}, {
                    'address': 'addr1qy5kwrh7k3ff9677mtmn234zwclwmnwewka93uk56y49cc3yhhj0xpkpwcwqec92a62rt3uzm3t4jnnsuk5nwr32arxs2wae0t',
                    'amount': [{'unit': 'lovelace', 'quantity': '55080054844'}], 'output_index': 1,
                    'data_hash': None, 'inline_datum': None, 'collateral': False,
                    'reference_script_hash': None}]},
            {}, {}, {}, {}
        ]
        expected_txs_addresses = {
            'input_addresses': {
                'addr1w98v2rexyjaxyppmaezyfz7fkwy059ewpde7l9xr4vhcp9qhtzss2',
                'addr1qxwzkpxr6dsaf4eg0rnupsr8eekdl8ef2cdl4dw9ju5vfcj5jckntpnwx7j5868kd7d09hcta6ad0ynsudyjgn30h82qjq8gxn',
                'addr1qy9vxqa5x2txd3s8p9hap6adpkn779havzftrc9e7cvta6snshevc7a5l3n43ru8jmv093m73appnlkvn6748nqg4vjqzfhn5t',
                'addr1z8d70g7c58vznyye9guwagdza74x36f3uff0eyk2zwpcpxcnshevc7a5l3n43ru8jmv093m73appnlkvn6748nqg4vjq9xzljd',
                'addr1q9qyjr3g870zsafqhyzy2nt54c366eufl064je8rthkxdlaerwjxy3uk23kjlerscpm2qxn4sp8twka333zvphrannqq2sy364',
                'addr1q98vmjmnxl2epge8fsetvy7hr867lkcqera8cc55scpm248r7vg0n8j87h2dxxsjdyc6h963tm0h5t2wn7z8jt05gawqjlctqr',
                'addr1vyheluzd3y2t7exkwxsr6d9t0ym7kstcx84xh8mlhj4edag5p9quv',
                'addr1w9wnm7vle7al9q4aw63aw63wxz7aytnpc4h3gcjy0yufxwc3mr3e5',
                'addr1q9ys3tqt7zxn7g8pk0r7sfl2qc8t2t2ut5qsnk3tn0zk00fyhhj0xpkpwcwqec92a62rt3uzm3t4jnnsuk5nwr32arxsdl0h36'},
            'output_addresses': {
                'addr1q9nxgzrc47sr2ngl898sfdjcczrk6svjrcvehnpn2t2cayq7zzjzvv2gwdncxr8hgpnqxzstfrk8z9vfzkzavqt6gjmq4pa4la',
                'addr1qy5kwrh7k3ff9677mtmn234zwclwmnwewka93uk56y49cc3yhhj0xpkpwcwqec92a62rt3uzm3t4jnnsuk5nwr32arxs2wae0t',
                'addr1qy9vxqa5x2txd3s8p9hap6adpkn779havzftrc9e7cvta6snshevc7a5l3n43ru8jmv093m73appnlkvn6748nqg4vjqzfhn5t',
                'addr1z8ax5k9mutg07p2ngscu3chsauktmstq92z9de938j8nqa65jckntpnwx7j5868kd7d09hcta6ad0ynsudyjgn30h82qukjfqz',
                'addr1z8d70g7c58vznyye9guwagdza74x36f3uff0eyk2zwpcpxcnshevc7a5l3n43ru8jmv093m73appnlkvn6748nqg4vjq9xzljd',
                'addr1qx9sltr8w7y3hyjav340zunarmegsvu009ny2k5neccal0p3yzmswj59yx7vn630qh3ce7yjflahhjr3a0a2xkhf30eq3rd5k5',
                'addr1z8ax5k9mutg07p2ngscu3chsauktmstq92z9de938j8nqaaerwjxy3uk23kjlerscpm2qxn4sp8twka333zvphrannqq3krpwy'}}
        expected_txs_info = {'outgoing_txs': {
            'addr1qy9vxqa5x2txd3s8p9hap6adpkn779havzftrc9e7cvta6snshevc7a5l3n43ru8jmv093m73appnlkvn6748nqg4vjqzfhn5t': {
                21: [{'tx_hash': '5a54c4ec018f6a08ff0ea573d3d38c6f39fa0590a8b5c250d9b350a516fd2e4a',
                      'value': Decimal('10002.186181'), 'contract_address': None, 'block_height': 10579202,
                      'symbol': 'ADA'}]}, 'addr1w98v2rexyjaxyppmaezyfz7fkwy059ewpde7l9xr4vhcp9qhtzss2': {21: [
                {'tx_hash': '76bf48e35c69b835b205b6728692a78e585d994fe55bc514e0a0e6329980886b',
                 'value': Decimal('29.217490'), 'contract_address': None, 'block_height': 10579202, 'symbol': 'ADA'}]},
            'addr1w9wnm7vle7al9q4aw63aw63wxz7aytnpc4h3gcjy0yufxwc3mr3e5': {21: [
                {'tx_hash': '76bf48e35c69b835b205b6728692a78e585d994fe55bc514e0a0e6329980886b',
                 'value': Decimal('-10000.000000'), 'contract_address': None, 'block_height': 10579202,
                 'symbol': 'ADA'}]},
            'addr1z8d70g7c58vznyye9guwagdza74x36f3uff0eyk2zwpcpxcnshevc7a5l3n43ru8jmv093m73appnlkvn6748nqg4vjq9xzljd': {
                21: [{'tx_hash': '76bf48e35c69b835b205b6728692a78e585d994fe55bc514e0a0e6329980886b',
                      'value': Decimal('10002.000000'), 'contract_address': None, 'block_height': 10579202,
                      'symbol': 'ADA'}]}, 'addr1vyheluzd3y2t7exkwxsr6d9t0ym7kstcx84xh8mlhj4edag5p9quv': {21: [
                {'tx_hash': '76bf48e35c69b835b205b6728692a78e585d994fe55bc514e0a0e6329980886b',
                 'value': Decimal('25.000000'), 'contract_address': None, 'block_height': 10579202, 'symbol': 'ADA'}]},
            'addr1qxwzkpxr6dsaf4eg0rnupsr8eekdl8ef2cdl4dw9ju5vfcj5jckntpnwx7j5868kd7d09hcta6ad0ynsudyjgn30h82qjq8gxn': {
                21: [{'tx_hash': '39af7d9b43d7a56bc37fe98edd1cf68342218b912ebfecde23f660893ce87072',
                      'value': Decimal('3.724033'), 'contract_address': None, 'block_height': 10579202,
                      'symbol': 'ADA'}]},
            'addr1q98vmjmnxl2epge8fsetvy7hr867lkcqera8cc55scpm248r7vg0n8j87h2dxxsjdyc6h963tm0h5t2wn7z8jt05gawqjlctqr': {
                21: [{'tx_hash': '39af7d9b43d7a56bc37fe98edd1cf68342218b912ebfecde23f660893ce87072',
                      'value': Decimal('5.000000'), 'contract_address': None, 'block_height': 10579202,
                      'symbol': 'ADA'}]},
            'addr1q9qyjr3g870zsafqhyzy2nt54c366eufl064je8rthkxdlaerwjxy3uk23kjlerscpm2qxn4sp8twka333zvphrannqq2sy364': {
                21: [{'tx_hash': '2cd17d51dadd1cd2d2476666a04eb681f479031b136dd1e749e948b78ce38a85',
                      'value': Decimal('3.722757'), 'contract_address': None, 'block_height': 10579202,
                      'symbol': 'ADA'}]},
            'addr1q9ys3tqt7zxn7g8pk0r7sfl2qc8t2t2ut5qsnk3tn0zk00fyhhj0xpkpwcwqec92a62rt3uzm3t4jnnsuk5nwr32arxsdl0h36': {
                21: [{'tx_hash': '3c9f57e6fc0b32e94b87a2bfa5bd4f1cd69c4d1a1379a1130e28989ae7597dc7',
                      'value': Decimal('55130.223161'), 'contract_address': None, 'block_height': 10579202,
                      'symbol': 'ADA'}]}}, 'incoming_txs': {
            'addr1z8d70g7c58vznyye9guwagdza74x36f3uff0eyk2zwpcpxcnshevc7a5l3n43ru8jmv093m73appnlkvn6748nqg4vjq9xzljd': {
                21: [{'tx_hash': '5a54c4ec018f6a08ff0ea573d3d38c6f39fa0590a8b5c250d9b350a516fd2e4a',
                      'value': Decimal('10002.000000'), 'contract_address': None, 'block_height': 10579202,
                      'symbol': 'ADA'}]},
            'addr1qy9vxqa5x2txd3s8p9hap6adpkn779havzftrc9e7cvta6snshevc7a5l3n43ru8jmv093m73appnlkvn6748nqg4vjqzfhn5t': {
                21: [{'tx_hash': '76bf48e35c69b835b205b6728692a78e585d994fe55bc514e0a0e6329980886b',
                      'value': Decimal('1.669176'), 'contract_address': None, 'block_height': 10579202,
                      'symbol': 'ADA'}]},
            'addr1z8ax5k9mutg07p2ngscu3chsauktmstq92z9de938j8nqa65jckntpnwx7j5868kd7d09hcta6ad0ynsudyjgn30h82qukjfqz': {
                21: [{'tx_hash': '39af7d9b43d7a56bc37fe98edd1cf68342218b912ebfecde23f660893ce87072',
                      'value': Decimal('2.500000'), 'contract_address': None, 'block_height': 10579202,
                      'symbol': 'ADA'}]},
            'addr1qx9sltr8w7y3hyjav340zunarmegsvu009ny2k5neccal0p3yzmswj59yx7vn630qh3ce7yjflahhjr3a0a2xkhf30eq3rd5k5': {
                21: [{'tx_hash': '39af7d9b43d7a56bc37fe98edd1cf68342218b912ebfecde23f660893ce87072',
                      'value': Decimal('1.000000'), 'contract_address': None, 'block_height': 10579202,
                      'symbol': 'ADA'}, {'tx_hash': '2cd17d51dadd1cd2d2476666a04eb681f479031b136dd1e749e948b78ce38a85',
                                         'value': Decimal('1.000000'), 'contract_address': None,
                                         'block_height': 10579202, 'symbol': 'ADA'}]},
            'addr1z8ax5k9mutg07p2ngscu3chsauktmstq92z9de938j8nqaaerwjxy3uk23kjlerscpm2qxn4sp8twka333zvphrannqq3krpwy': {
                21: [{'tx_hash': '2cd17d51dadd1cd2d2476666a04eb681f479031b136dd1e749e948b78ce38a85',
                      'value': Decimal('2.500000'), 'contract_address': None, 'block_height': 10579202,
                      'symbol': 'ADA'}]},
            'addr1q9nxgzrc47sr2ngl898sfdjcczrk6svjrcvehnpn2t2cayq7zzjzvv2gwdncxr8hgpnqxzstfrk8z9vfzkzavqt6gjmq4pa4la': {
                21: [{'tx_hash': '3c9f57e6fc0b32e94b87a2bfa5bd4f1cd69c4d1a1379a1130e28989ae7597dc7',
                      'value': Decimal('50.000000'), 'contract_address': None, 'block_height': 10579202,
                      'symbol': 'ADA'}]},
            'addr1qy5kwrh7k3ff9677mtmn234zwclwmnwewka93uk56y49cc3yhhj0xpkpwcwqec92a62rt3uzm3t4jnnsuk5nwr32arxs2wae0t': {
                21: [{'tx_hash': '3c9f57e6fc0b32e94b87a2bfa5bd4f1cd69c4d1a1379a1130e28989ae7597dc7',
                      'value': Decimal('55080.054844'), 'contract_address': None, 'block_height': 10579202,
                      'symbol': 'ADA'}]}}}
        cls.get_block_txs(block_txs_mock_response, expected_txs_addresses, expected_txs_info)
