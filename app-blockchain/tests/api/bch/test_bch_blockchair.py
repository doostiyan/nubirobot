from unittest import TestCase
from unittest.mock import Mock

from django.conf import settings
from pytz import UTC
import datetime
import pytest
from _decimal import Decimal

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

from exchange.blockchain.api.general.dtos import TransferTx

from exchange.blockchain.api.bch.bch_blockchair import BitcoinCashBlockchairApi


@pytest.mark.slow
class BitcoinCashBlockchairApiCalls(TestCase):
    api = BitcoinCashBlockchairApi
    # one address is cashaddress and one address is legacy address
    addresses_of_account = ['qrxumkdjh5hfw7za08u2t9qcjag7dqud0v5g9mt6d8', '1JpdvWEBvxoy4RLDsWVouHkasmkg2rQH6n']
    hash_of_transactions = ['16bbab91b66a37c4b6c914790519e067a84d0aa24259e7537bbb6fc42db1d2bd',
                            '1633e17f7b8a6b85a0dddd8811d321d69074be36432f063f43b910ec3e606982',
                            '0ec96e719c85a061cae84cc103ca853b19776de91f731b9f9de657883f1efc15'
                            ]

    @classmethod
    def check_general_response(cls, response):
        if not response or not isinstance(response, dict):
            return False
        if not response.get('data') or not isinstance(response.get('data'), dict):
            return False
        if not response.get('context') or not isinstance(response.get('context'), dict):
            return False
        if not response.get('context').get('state') or not isinstance(response.get('context').get('state'), int):
            return False
        return True

    def test_get_address_txs_api(self):

        address_keys = {'type', 'formats'}
        formats = {'cashaddr', 'legacy'}
        address_types_check = [('type', str), ('formats', dict)]
        transfer_keys = {'block_id', 'hash', 'time', 'balance_change'}
        transfer_type_check = [('block_id', int), ('hash', str), ('time', str), ('balance_change', int)]
        for address in self.addresses_of_account:
            get_address_txs_response = self.api.get_address_txs(address)
            assert self.check_general_response(get_address_txs_response)
            assert (get_address_txs_response.get('address') and
                    isinstance(get_address_txs_response.get('address'), str))
            address = get_address_txs_response.get('address')
            assert (get_address_txs_response.get('data').get(address)
                    and isinstance(get_address_txs_response.get('data').get(address), dict))
            data = get_address_txs_response.get('data').get(address)
            if address_keys.issubset(set(data.get('address').keys())):
                for key, value in address_types_check:
                    assert isinstance(data.get('address').get(key), value)
                assert formats.issubset(data.get('address').get('formats').keys())
                transactions = data.get('transactions')
                for transfer in transactions:
                    if transfer_keys.issubset(transfer.keys()):
                        for key, value in transfer_type_check:
                            assert isinstance(transfer.get(key), value)

    def test_get_tx_details_api(self):
        transaction_keys = {'block_id', 'hash', 'date', 'time', 'fee'}
        types_check = [('block_id', int), ('hash', str), ('date', str), ('fee', int), ('time', str)]
        transfer_keys = {'block_id', 'date', 'time', 'value', 'recipient', 'type', 'is_from_coin_base'}
        transfer_type_check = [('block_id', int), ('value', int), ('date', str), ('time', str), ('recipient', str),
                               ('type', str), ('is_from_coin_base', bool)]
        for tx_hash in self.hash_of_transactions:
            get_tx_details_response = self.api.get_tx_details(tx_hash)
            assert self.check_general_response(get_tx_details_response)
            assert (get_tx_details_response.get('tx_hash') and
                    isinstance(get_tx_details_response.get('tx_hash'), str))
            hash = get_tx_details_response.get('tx_hash')
            assert (get_tx_details_response.get('data').get(hash)
                    and isinstance(get_tx_details_response.get('data').get(hash), dict))
            data = get_tx_details_response.get('data').get(hash)
            assert (data.get('inputs') and data.get('outputs'))
            if transaction_keys.issubset(data.get('transaction').keys()):
                for key, value in types_check:
                    assert isinstance(data.get('transaction').get(key), value)
                transfers = data.get('inputs') + data.get('outputs')
                for transfer in transfers:
                    if transfer_keys.issubset(transfer.keys()):
                        for key, value in transfer_type_check:
                            assert isinstance(transfer.get(key), value)


class TestBitcoinCashBlockchairApiFromExplorer(TestCase):
    api = BitcoinCashBlockchairApi
    currency = Currencies.bch
    address_txs = ['qrxumkdjh5hfw7za08u2t9qcjag7dqud0v5g9mt6d8', '1JpdvWEBvxoy4RLDsWVouHkasmkg2rQH6n']
    hash_of_transactions = ['16bbab91b66a37c4b6c914790519e067a84d0aa24259e7537bbb6fc42db1d2bd',
                            '1633e17f7b8a6b85a0dddd8811d321d69074be36432f063f43b910ec3e606982',
                            '0ec96e719c85a061cae84cc103ca853b19776de91f731b9f9de657883f1efc15'
                            ]

    def test_get_tx_details(self):
        tx_details_mock_response = [
            {'data': {'16bbab91b66a37c4b6c914790519e067a84d0aa24259e7537bbb6fc42db1d2bd': {
                'transaction': {'block_id': 853849, 'id': 395886279,
                                'hash': '16bbab91b66a37c4b6c914790519e067a84d0aa24259e7537bbb6fc42db1d2bd',
                                'date': '2024-07-10', 'time': '2024-07-10 08:16:28', 'size': 373, 'version': 2,
                                'lock_time': 0, 'is_coinbase': False, 'input_count': 2, 'output_count': 2,
                                'input_total': 330005573806, 'input_total_usd': 1091990, 'output_total': 330005572672,
                                'output_total_usd': 1091990, 'fee': 1134, 'fee_usd': 0.00375241, 'fee_per_kb': 3040.21,
                                'fee_per_kb_usd': 0.0100601, 'cdd_total': 18.700310362014}, 'inputs': [
                    {'block_id': 853195, 'transaction_id': 395412537, 'index': 1,
                     'transaction_hash': '5b152083cd01194df6b70df7f17060ad4edb8b1b9ea8253b44ea9eecbf1a3f3c',
                     'date': '2024-07-04', 'time': '2024-07-04 09:02:28', 'value': 11914646, 'value_usd': 44.3987,
                     'recipient': 'qrpheq5xdshy84tp7klp7u5phuyg7ffy0v4jkj8hqn', 'type': 'pubkeyhash',
                     'script_hex': '76a914c37c82866c2e43d561f5be1f7281bf088f25247b88ac', 'is_from_coinbase': False,
                     'is_spendable': None, 'is_spent': True, 'spending_block_id': 853849,
                     'spending_transaction_id': 395886279, 'spending_index': 0,
                     'spending_transaction_hash': '16bbab91b66a37c4b6c914790519e067a84d0aa24259e7537bbb6fc42db1d2bd',
                     'spending_date': '2024-07-10', 'spending_time': '2024-07-10 08:16:28',
                     'spending_value_usd': 39.4256, 'spending_sequence': 4294967295,
                     'spending_signature_hex': '473044022033818011c3579a24fe542c750076cb6a5803fe6150e94de1fba82870cc7e03730220023c176c512fc1f9913d3d216c434205457f1a97dd3d44abebeed538b4db8299412103e668efb0d32744f477e6ab280ea25601d969c0a7d2fdadac2899fbdbeceffe70',
                     'lifespan': 515640, 'cdd': 0}, {'block_id': 853845, 'transaction_id': 395886139, 'index': 0,
                                                     'transaction_hash': '726f973af90ec0b2d97a7635698b308a7762710d2d7cc1fda964aba2db53a24b',
                                                     'date': '2024-07-10', 'time': '2024-07-10 08:08:37',
                                                     'value': 329993659160, 'value_usd': 1091950,
                                                     'recipient': 'qrpheq5xdshy84tp7klp7u5phuyg7ffy0v4jkj8hqn',
                                                     'type': 'pubkeyhash',
                                                     'script_hex': '76a914c37c82866c2e43d561f5be1f7281bf088f25247b88ac',
                                                     'is_from_coinbase': False, 'is_spendable': None, 'is_spent': True,
                                                     'spending_block_id': 853849, 'spending_transaction_id': 395886279,
                                                     'spending_index': 1,
                                                     'spending_transaction_hash': '16bbab91b66a37c4b6c914790519e067a84d0aa24259e7537bbb6fc42db1d2bd',
                                                     'spending_date': '2024-07-10',
                                                     'spending_time': '2024-07-10 08:16:28',
                                                     'spending_value_usd': 1091950, 'spending_sequence': 4294967295,
                                                     'spending_signature_hex': '483045022100d57847d8be2f68f2e16fc96b57ed1db9a62bd8cf30215a5b4fcb8fe73673d7d102201da1d142fcf12ab2593da1f2fd1b7ce7a97c26203c3687711414c7b320321df2412103e668efb0d32744f477e6ab280ea25601d969c0a7d2fdadac2899fbdbeceffe70',
                                                     'lifespan': 471, 'cdd': 17.9841319444444}], 'outputs': [
                    {'block_id': 853849, 'transaction_id': 395886279, 'index': 0,
                     'transaction_hash': '16bbab91b66a37c4b6c914790519e067a84d0aa24259e7537bbb6fc42db1d2bd',
                     'date': '2024-07-10', 'time': '2024-07-10 08:16:28', 'value': 220000000000, 'value_usd': 727980,
                     'recipient': 'qrxumkdjh5hfw7za08u2t9qcjag7dqud0v5g9mt6d8', 'type': 'pubkeyhash',
                     'script_hex': '76a914cdcdd9b2bd2e97785d79f8a594189751e6838d7b88ac', 'is_from_coinbase': False,
                     'is_spendable': None, 'is_spent': True, 'spending_block_id': 853855,
                     'spending_transaction_id': 395886816, 'spending_index': 1,
                     'spending_transaction_hash': '11a89edb7ce306f2e61a98b4a6d8f27a4a5d583ab5f6c67cd5cde09164c414b0',
                     'spending_date': '2024-07-10', 'spending_time': '2024-07-10 09:31:22',
                     'spending_value_usd': 727980, 'spending_sequence': 4294967295,
                     'spending_signature_hex': '47304402204551627c8af2da6602cd8892614b937e690d9f0260b9a379c254b57b9114579102200385b34d2dd4b114b9ae4152ec2c9c899b62dd9bf7cc04054e049f1d42cc142d412102247185fa670623722743fd7d42e340d77227cd8a76ff1050a8bc6b1232ea6344',
                     'lifespan': 4494, 'cdd': 114.430555555556},
                    {'block_id': 853849, 'transaction_id': 395886279, 'index': 1,
                     'transaction_hash': '16bbab91b66a37c4b6c914790519e067a84d0aa24259e7537bbb6fc42db1d2bd',
                     'date': '2024-07-10', 'time': '2024-07-10 08:16:28', 'value': 110005572672, 'value_usd': 364008,
                     'recipient': 'qrpheq5xdshy84tp7klp7u5phuyg7ffy0v4jkj8hqn', 'type': 'pubkeyhash',
                     'script_hex': '76a914c37c82866c2e43d561f5be1f7281bf088f25247b88ac', 'is_from_coinbase': False,
                     'is_spendable': None, 'is_spent': True, 'spending_block_id': 853849,
                     'spending_transaction_id': 395886278, 'spending_index': 0,
                     'spending_transaction_hash': '1633e17f7b8a6b85a0dddd8811d321d69074be36432f063f43b910ec3e606982',
                     'spending_date': '2024-07-10', 'spending_time': '2024-07-10 08:16:28',
                     'spending_value_usd': 364008, 'spending_sequence': 4294967295,
                     'spending_signature_hex': '47304402202d5b5f435bb148afd069fbfb0c684812778bff4e57a69cfda7b6d0e4b35ff079022048d040eb653bef041d2d87961d6dfde1377c4a019c035695f9df0f38d0f87766412103e668efb0d32744f477e6ab280ea25601d969c0a7d2fdadac2899fbdbeceffe70',
                     'lifespan': 0, 'cdd': 0}]}},
             'context': {'code': 200, 'source': 'D', 'results': 1, 'state': 853882, 'market_price_usd': 336.4,
                         'cache': {'live': True, 'duration': 120, 'since': '2024-07-10 14:55:35',
                                   'until': '2024-07-10 14:57:35', 'time': None},
                         'api': {'version': '2.0.95-ie', 'last_major_update': '2022-11-07 02:00:00',
                                 'next_major_update': '2023-11-12 02:00:00',
                                 'documentation': 'https://blockchair.com/api/docs',
                                 'notice': 'Try out our new API v.3: https://3xpl.com/data'}, 'servers': 'API4,BCH0',
                         'time': 1.1393301486968994, 'render_time': 0.04388785362243652, 'full_time': 1.183218002319336,
                         'request_cost': 1}},
            {'data': {'1633e17f7b8a6b85a0dddd8811d321d69074be36432f063f43b910ec3e606982': {
                'transaction': {'block_id': 853849, 'id': 395886278,
                                'hash': '1633e17f7b8a6b85a0dddd8811d321d69074be36432f063f43b910ec3e606982',
                                'date': '2024-07-10', 'time': '2024-07-10 08:16:28', 'size': 225, 'version': 2,
                                'lock_time': 0, 'is_coinbase': False, 'input_count': 1, 'output_count': 2,
                                'input_total': 110005572672, 'input_total_usd': 364008, 'output_total': 110005571988,
                                'output_total_usd': 364008, 'fee': 684, 'fee_usd': 0.00226336, 'fee_per_kb': 3040,
                                'fee_per_kb_usd': 0.0100594, 'cdd_total': 0}, 'inputs': [
                    {'block_id': 853849, 'transaction_id': 395886279, 'index': 1,
                     'transaction_hash': '16bbab91b66a37c4b6c914790519e067a84d0aa24259e7537bbb6fc42db1d2bd',
                     'date': '2024-07-10', 'time': '2024-07-10 08:16:28', 'value': 110005572672, 'value_usd': 364008,
                     'recipient': 'qrpheq5xdshy84tp7klp7u5phuyg7ffy0v4jkj8hqn', 'type': 'pubkeyhash',
                     'script_hex': '76a914c37c82866c2e43d561f5be1f7281bf088f25247b88ac', 'is_from_coinbase': False,
                     'is_spendable': None, 'is_spent': True, 'spending_block_id': 853849,
                     'spending_transaction_id': 395886278, 'spending_index': 0,
                     'spending_transaction_hash': '1633e17f7b8a6b85a0dddd8811d321d69074be36432f063f43b910ec3e606982',
                     'spending_date': '2024-07-10', 'spending_time': '2024-07-10 08:16:28',
                     'spending_value_usd': 364008, 'spending_sequence': 4294967295,
                     'spending_signature_hex': '47304402202d5b5f435bb148afd069fbfb0c684812778bff4e57a69cfda7b6d0e4b35ff079022048d040eb653bef041d2d87961d6dfde1377c4a019c035695f9df0f38d0f87766412103e668efb0d32744f477e6ab280ea25601d969c0a7d2fdadac2899fbdbeceffe70',
                     'lifespan': 0, 'cdd': 0}], 'outputs': [
                    {'block_id': 853849, 'transaction_id': 395886278, 'index': 0,
                     'transaction_hash': '1633e17f7b8a6b85a0dddd8811d321d69074be36432f063f43b910ec3e606982',
                     'date': '2024-07-10', 'time': '2024-07-10 08:16:28', 'value': 100000000000, 'value_usd': 330900,
                     'recipient': 'qqvhuykkllnv8jv44xtz5r2mqhlhlx64asmgvahn44', 'type': 'pubkeyhash',
                     'script_hex': '76a914197e12d6ffe6c3c995a9962a0d5b05ff7f9b55ec88ac', 'is_from_coinbase': False,
                     'is_spendable': None, 'is_spent': True, 'spending_block_id': 853850,
                     'spending_transaction_id': 395886372, 'spending_index': 1,
                     'spending_transaction_hash': '88bbc26c97a44f8b86bd6366a6a62820d3318c93f1742901ef6b5d88066390c3',
                     'spending_date': '2024-07-10', 'spending_time': '2024-07-10 08:28:52',
                     'spending_value_usd': 330900, 'spending_sequence': 4294967295,
                     'spending_signature_hex': '4830450221009751ab91d08f6d3df2fa7ef25e15e4cb8f400fa7b7909ee86d0658fbc4da43470220388090b7de8f680d0f20a7e7fe1bf52e78923af8b958062abe2e42614080c1e541210395a3fb8a0098dbe5770ca6460cc47b1c65fa084e1c8ac94f4ef10cbd628b2bb6',
                     'lifespan': 744, 'cdd': 8.61111111111111},
                    {'block_id': 853849, 'transaction_id': 395886278, 'index': 1,
                     'transaction_hash': '1633e17f7b8a6b85a0dddd8811d321d69074be36432f063f43b910ec3e606982',
                     'date': '2024-07-10', 'time': '2024-07-10 08:16:28', 'value': 10005571988, 'value_usd': 33108.4,
                     'recipient': 'qrpheq5xdshy84tp7klp7u5phuyg7ffy0v4jkj8hqn', 'type': 'pubkeyhash',
                     'script_hex': '76a914c37c82866c2e43d561f5be1f7281bf088f25247b88ac', 'is_from_coinbase': False,
                     'is_spendable': None, 'is_spent': True, 'spending_block_id': 853850,
                     'spending_transaction_id': 395886379, 'spending_index': 0,
                     'spending_transaction_hash': 'a4cde0864f4f78161210ce60f8234b7b5bcb1522069b68797b9b588fdb6257de',
                     'spending_date': '2024-07-10', 'spending_time': '2024-07-10 08:28:52',
                     'spending_value_usd': 33108.4, 'spending_sequence': 4294967295,
                     'spending_signature_hex': '47304402206797ecde75cadb3b25424705d870cec73f8fe46b5b7694edfa1ca75d0e29d77702206fff2170c2306f9a5fc4b0b516e89eb8441a97966aa28be14168456e63cbee9a412103e668efb0d32744f477e6ab280ea25601d969c0a7d2fdadac2899fbdbeceffe70',
                     'lifespan': 744, 'cdd': 0.861111111111111}]}},
             'context': {'code': 200, 'source': 'D', 'results': 1, 'state': 853882, 'market_price_usd': 336.4,
                         'cache': {'live': True, 'duration': 120, 'since': '2024-07-10 14:55:53',
                                   'until': '2024-07-10 14:57:53', 'time': None},
                         'api': {'version': '2.0.95-ie', 'last_major_update': '2022-11-07 02:00:00',
                                 'next_major_update': '2023-11-12 02:00:00',
                                 'documentation': 'https://blockchair.com/api/docs',
                                 'notice': 'Try out our new API v.3: https://3xpl.com/data'}, 'servers': 'API4,BCH0',
                         'time': 1.0888409614562988, 'render_time': 0.044265031814575195,
                         'full_time': 1.133105993270874, 'request_cost': 1}},
            {'data': {'0ec96e719c85a061cae84cc103ca853b19776de91f731b9f9de657883f1efc15': {
                'transaction': {'block_id': 851870, 'id': 394620440,
                                'hash': '0ec96e719c85a061cae84cc103ca853b19776de91f731b9f9de657883f1efc15',
                                'date': '2024-06-26', 'time': '2024-06-26 08:05:56', 'size': 669, 'version': 2,
                                'lock_time': 0, 'is_coinbase': False, 'input_count': 4, 'output_count': 2,
                                'input_total': 131097588578, 'input_total_usd': 509576, 'output_total': 131097587900,
                                'output_total_usd': 509576, 'fee': 678, 'fee_usd': 0.00263539, 'fee_per_kb': 1013.45,
                                'fee_per_kb_usd': 0.00393929, 'cdd_total': 744.08042104266}, 'inputs': [
                    {'block_id': 851195, 'transaction_id': 393875892, 'index': 1,
                     'transaction_hash': '066a90ad415bf53a1ec65cbe2b232f0604e815e05ee1d14666514dec2f2c7212',
                     'date': '2024-06-21', 'time': '2024-06-21 18:44:29', 'value': 884878, 'value_usd': 3.44872,
                     'recipient': 'qrd08wrtsum82vcvu63fhfscf59dp9xta5kg0el077', 'type': 'pubkeyhash',
                     'script_hex': '76a914daf3b86b873675330ce6a29ba6184d0ad094cbed88ac', 'is_from_coinbase': False,
                     'is_spendable': None, 'is_spent': True, 'spending_block_id': 851870,
                     'spending_transaction_id': 394620440, 'spending_index': 0,
                     'spending_transaction_hash': '0ec96e719c85a061cae84cc103ca853b19776de91f731b9f9de657883f1efc15',
                     'spending_date': '2024-06-26', 'spending_time': '2024-06-26 08:05:56',
                     'spending_value_usd': 3.43952, 'spending_sequence': 4294967295,
                     'spending_signature_hex': '4830450221009cbc5cf826f10d0cb156e2c38cdc89c6b4dcdc047ceebfa88e7953931c24daac02205b8984431858d4c3a39cf69bc2afee902efb2aa14e32fe400e4585d31cae32a8412103237e1762d1511057af202b5c689280aff71d1d7d762ae0cd11e2403cdd41dab6',
                     'lifespan': 393687, 'cdd': 0}, {'block_id': 851795, 'transaction_id': 394240749, 'index': 2,
                                                     'transaction_hash': '985aa0ce7a401000c94c0efcddb984bdf08c9ba003add7e52a1e12ed5e1be732',
                                                     'date': '2024-06-25', 'time': '2024-06-25 18:24:44',
                                                     'value': 14271850000, 'value_usd': 51898.2,
                                                     'recipient': 'qrd08wrtsum82vcvu63fhfscf59dp9xta5kg0el077',
                                                     'type': 'pubkeyhash',
                                                     'script_hex': '76a914daf3b86b873675330ce6a29ba6184d0ad094cbed88ac',
                                                     'is_from_coinbase': False, 'is_spendable': None, 'is_spent': True,
                                                     'spending_block_id': 851870, 'spending_transaction_id': 394620440,
                                                     'spending_index': 1,
                                                     'spending_transaction_hash': '0ec96e719c85a061cae84cc103ca853b19776de91f731b9f9de657883f1efc15',
                                                     'spending_date': '2024-06-26',
                                                     'spending_time': '2024-06-26 08:05:56',
                                                     'spending_value_usd': 55474.7, 'spending_sequence': 4294967295,
                                                     'spending_signature_hex': '483045022100d2e5e6742f35357587439f05ab62839f96fae9219bacf6a10fedf67246b9816c02205359f6823a0532d1b60bcad9ba673cfaee4e21f5747865761b5774772d287fe7412103237e1762d1511057af202b5c689280aff71d1d7d762ae0cd11e2403cdd41dab6',
                                                     'lifespan': 49272, 'cdd': 80.9794444444444},
                    {'block_id': 851795, 'transaction_id': 394240735, 'index': 2,
                     'transaction_hash': '6b0128f9edb16e029d45a63a08dee2b1a79c2b5458cb81e40d136d4e70abdcd5',
                     'date': '2024-06-25', 'time': '2024-06-25 18:24:44', 'value': 17178686400, 'value_usd': 62468.6,
                     'recipient': 'qrd08wrtsum82vcvu63fhfscf59dp9xta5kg0el077', 'type': 'pubkeyhash',
                     'script_hex': '76a914daf3b86b873675330ce6a29ba6184d0ad094cbed88ac', 'is_from_coinbase': False,
                     'is_spendable': None, 'is_spent': True, 'spending_block_id': 851870,
                     'spending_transaction_id': 394620440, 'spending_index': 2,
                     'spending_transaction_hash': '0ec96e719c85a061cae84cc103ca853b19776de91f731b9f9de657883f1efc15',
                     'spending_date': '2024-06-26', 'spending_time': '2024-06-26 08:05:56',
                     'spending_value_usd': 66773.6, 'spending_sequence': 4294967295,
                     'spending_signature_hex': '483045022100e55f4825284f4c04a587cc1939103350f4191f6fe555ce77a7f262266ee3359602202f99d69bbdb5571da62c720c75ecf6a979c02dda3bfdc9e3b8e7a7b0ad0ac9d7412103237e1762d1511057af202b5c689280aff71d1d7d762ae0cd11e2403cdd41dab6',
                     'lifespan': 49272, 'cdd': 97.5175}, {'block_id': 851796, 'transaction_id': 394240838, 'index': 2,
                                                          'transaction_hash': 'd095599f9fc16308e3edf38e528f1efcfea6184213bcbaf6af14974ace6e465d',
                                                          'date': '2024-06-25', 'time': '2024-06-25 18:29:54',
                                                          'value': 99646167300, 'value_usd': 362353,
                                                          'recipient': 'qrd08wrtsum82vcvu63fhfscf59dp9xta5kg0el077',
                                                          'type': 'pubkeyhash',
                                                          'script_hex': '76a914daf3b86b873675330ce6a29ba6184d0ad094cbed88ac',
                                                          'is_from_coinbase': False, 'is_spendable': None,
                                                          'is_spent': True, 'spending_block_id': 851870,
                                                          'spending_transaction_id': 394620440, 'spending_index': 3,
                                                          'spending_transaction_hash': '0ec96e719c85a061cae84cc103ca853b19776de91f731b9f9de657883f1efc15',
                                                          'spending_date': '2024-06-26',
                                                          'spending_time': '2024-06-26 08:05:56',
                                                          'spending_value_usd': 387325, 'spending_sequence': 4294967295,
                                                          'spending_signature_hex': '473044022006ad6d014d1647efb36ee16c6ceddbc8761f16e04f87a9bed24cd5e111d04e070220726de832393d4e81172e7267bb85ade4643aeac04c452c133c3040affddb1f1f412103237e1762d1511057af202b5c689280aff71d1d7d762ae0cd11e2403cdd41dab6',
                                                          'lifespan': 48962, 'cdd': 564.423055555556}], 'outputs': [
                    {'block_id': 851870, 'transaction_id': 394620440, 'index': 0,
                     'transaction_hash': '0ec96e719c85a061cae84cc103ca853b19776de91f731b9f9de657883f1efc15',
                     'date': '2024-06-26', 'time': '2024-06-26 08:05:56', 'value': 131096703700, 'value_usd': 509573,
                     'recipient': 'qrpheq5xdshy84tp7klp7u5phuyg7ffy0v4jkj8hqn', 'type': 'pubkeyhash',
                     'script_hex': '76a914c37c82866c2e43d561f5be1f7281bf088f25247b88ac', 'is_from_coinbase': False,
                     'is_spendable': None, 'is_spent': True, 'spending_block_id': 851875,
                     'spending_transaction_id': 394621138, 'spending_index': 1,
                     'spending_transaction_hash': '9b16b44043049bde0a6a4344b1bb9adbfdd8a5f851b630e04c4e768d82db56e1',
                     'spending_date': '2024-06-26', 'spending_time': '2024-06-26 08:37:19',
                     'spending_value_usd': 509573, 'spending_sequence': 4294967295,
                     'spending_signature_hex': '483045022100b2b31d3dbfc80588c280b168d8b84b7d0d4bb64f78f68cea1b217ad3b209112802207075afb1dedf98926dfce00348ced3168a1a5b1f49031a8adfcdb19e398080b2412103e668efb0d32744f477e6ab280ea25601d969c0a7d2fdadac2899fbdbeceffe70',
                     'lifespan': 1883, 'cdd': 28.5501157407407},
                    {'block_id': 851870, 'transaction_id': 394620440, 'index': 1,
                     'transaction_hash': '0ec96e719c85a061cae84cc103ca853b19776de91f731b9f9de657883f1efc15',
                     'date': '2024-06-26', 'time': '2024-06-26 08:05:56', 'value': 884200, 'value_usd': 3.43689,
                     'recipient': 'qrd08wrtsum82vcvu63fhfscf59dp9xta5kg0el077', 'type': 'pubkeyhash',
                     'script_hex': '76a914daf3b86b873675330ce6a29ba6184d0ad094cbed88ac', 'is_from_coinbase': False,
                     'is_spendable': None, 'is_spent': False, 'spending_block_id': None,
                     'spending_transaction_id': None, 'spending_index': None, 'spending_transaction_hash': None,
                     'spending_date': None, 'spending_time': None, 'spending_value_usd': None,
                     'spending_sequence': None, 'spending_signature_hex': None, 'lifespan': None, 'cdd': None}]}},
             'context': {'code': 200, 'source': 'D', 'results': 1, 'state': 853882, 'market_price_usd': 336.4,
                         'cache': {'live': True, 'duration': 120, 'since': '2024-07-10 14:56:09',
                                   'until': '2024-07-10 14:58:09', 'time': None},
                         'api': {'version': '2.0.95-ie', 'last_major_update': '2022-11-07 02:00:00',
                                 'next_major_update': '2023-11-12 02:00:00',
                                 'documentation': 'https://blockchair.com/api/docs',
                                 'notice': 'Try out our new API v.3: https://3xpl.com/data'}, 'servers': 'API4,BCH0',
                         'time': 1.1258769035339355, 'render_time': 0.04507017135620117,
                         'full_time': 1.1709470748901367, 'request_cost': 1}}
        ]
        self.api.request = Mock(side_effect=tx_details_mock_response)
        parsed_responses = []
        for tx_hash in self.hash_of_transactions:
            api_response = self.api.get_tx_details(tx_hash)
            parsed_response = self.api.parser.parse_tx_details_response(api_response, None)
            parsed_responses.append(parsed_response)
        expected_txs_details = [[TransferTx(tx_hash='16bbab91b66a37c4b6c914790519e067a84d0aa24259e7537bbb6fc42db1d2bd', success=True, from_address='1JpdvWEBvxoy4RLDsWVouHkasmkg2rQH6n', to_address='', value=Decimal('2200.00001134'), symbol='BCH', confirmations=33, block_height=853849, block_hash=None, date=datetime.datetime(2024, 7, 10, 8, 16, 28, tzinfo=UTC), memo=None, tx_fee=Decimal('0.00001134'), token=None, index=None), TransferTx(tx_hash='16bbab91b66a37c4b6c914790519e067a84d0aa24259e7537bbb6fc42db1d2bd', success=True, from_address='', to_address='1KmC84WxyKVMXVheFExKBfnQVqDFEipJHK', value=Decimal('2200.00000000'), symbol='BCH', confirmations=33, block_height=853849, block_hash=None, date=datetime.datetime(2024, 7, 10, 8, 16, 28, tzinfo=UTC), memo=None, tx_fee=Decimal('0.00001134'), token=None, index=None)], [TransferTx(tx_hash='1633e17f7b8a6b85a0dddd8811d321d69074be36432f063f43b910ec3e606982', success=True, from_address='1JpdvWEBvxoy4RLDsWVouHkasmkg2rQH6n', to_address='', value=Decimal('1000.00000684'), symbol='BCH', confirmations=33, block_height=853849, block_hash=None, date=datetime.datetime(2024, 7, 10, 8, 16, 28, tzinfo=UTC), memo=None, tx_fee=Decimal('0.00000684'), token=None, index=None), TransferTx(tx_hash='1633e17f7b8a6b85a0dddd8811d321d69074be36432f063f43b910ec3e606982', success=True, from_address='', to_address='13KnvYUEtZmt3RueKthw7G3ewTxAPyLcu8', value=Decimal('1000.00000000'), symbol='BCH', confirmations=33, block_height=853849, block_hash=None, date=datetime.datetime(2024, 7, 10, 8, 16, 28, tzinfo=UTC), memo=None, tx_fee=Decimal('0.00000684'), token=None, index=None)], [TransferTx(tx_hash='0ec96e719c85a061cae84cc103ca853b19776de91f731b9f9de657883f1efc15', success=True, from_address='1LxiGouK1h6cYkSFWoK2oZwJZeqcgEXSQy', to_address='', value=Decimal('1310.96704378'), symbol='BCH', confirmations=2012, block_height=851870, block_hash=None, date=datetime.datetime(2024, 6, 26, 8, 5, 56, tzinfo=UTC), memo=None, tx_fee=Decimal('0.00000678'), token=None, index=None), TransferTx(tx_hash='0ec96e719c85a061cae84cc103ca853b19776de91f731b9f9de657883f1efc15', success=True, from_address='', to_address='1JpdvWEBvxoy4RLDsWVouHkasmkg2rQH6n', value=Decimal('1310.96703700'), symbol='BCH', confirmations=2012, block_height=851870, block_hash=None, date=datetime.datetime(2024, 6, 26, 8, 5, 56, tzinfo=UTC), memo=None, tx_fee=Decimal('0.00000678'), token=None, index=None)]]
        for expected_tx_details, tx_details in zip(expected_txs_details, parsed_responses):
            assert tx_details == expected_tx_details

    def test_get_address_txs(self):
        address_txs_mock_response = [
            {'data': {'qrxumkdjh5hfw7za08u2t9qcjag7dqud0v5g9mt6d8': {
                'address': {'type': 'pubkeyhash', 'script_hex': '76a914cdcdd9b2bd2e97785d79f8a594189751e6838d7b88ac',
                            'balance': 0, 'balance_usd': 0, 'received': 220000000000, 'received_usd': 727980,
                            'spent': 220000000000, 'spent_usd': 727980, 'output_count': 1, 'unspent_output_count': 0,
                            'first_seen_receiving': '2024-07-10 08:16:28', 'last_seen_receiving': '2024-07-10 08:16:28',
                            'first_seen_spending': '2024-07-10 09:31:22', 'last_seen_spending': '2024-07-10 09:31:22',
                            'scripthash_type': None, 'transaction_count': 2,
                            'formats': {'legacy': '1KmC84WxyKVMXVheFExKBfnQVqDFEipJHK',
                                        'cashaddr': 'qrxumkdjh5hfw7za08u2t9qcjag7dqud0v5g9mt6d8'}}, 'transactions': [
                    {'block_id': 853855, 'hash': '11a89edb7ce306f2e61a98b4a6d8f27a4a5d583ab5f6c67cd5cde09164c414b0',
                     'time': '2024-07-10 09:31:22', 'balance_change': -220000000000},
                    {'block_id': 853849, 'hash': '16bbab91b66a37c4b6c914790519e067a84d0aa24259e7537bbb6fc42db1d2bd',
                     'time': '2024-07-10 08:16:28', 'balance_change': 220000000000}], 'utxo': []}},
             'context': {'code': 200, 'source': 'D', 'limit': '15,15', 'offset': '0,0', 'results': 1, 'state': 853882,
                         'market_price_usd': 336.4,
                         'cache': {'live': True, 'duration': 60, 'since': '2024-07-10 15:00:18',
                                   'until': '2024-07-10 15:01:18', 'time': None},
                         'api': {'version': '2.0.95-ie', 'last_major_update': '2022-11-07 02:00:00',
                                 'next_major_update': '2023-11-12 02:00:00',
                                 'documentation': 'https://blockchair.com/api/docs',
                                 'notice': 'Try out our new API v.3: https://3xpl.com/data'}, 'servers': 'API4,BCH0',
                         'time': 0.9938948154449463, 'render_time': 0.003319263458251953,
                         'full_time': 0.9972140789031982, 'request_cost': 2}},
            {'data': {'1JpdvWEBvxoy4RLDsWVouHkasmkg2rQH6n': {
                'address': {'type': 'pubkeyhash', 'script_hex': '76a914c37c82866c2e43d561f5be1f7281bf088f25247b88ac',
                            'balance': 11912144, 'balance_usd': 40.072452416, 'received': 3765845645016,
                            'received_usd': 16408700.3918, 'spent': 3765833732872, 'spent_usd': 16408776.2977,
                            'output_count': 42, 'unspent_output_count': 1,
                            'first_seen_receiving': '2024-02-06 19:09:30', 'last_seen_receiving': '2024-07-10 08:28:52',
                            'first_seen_spending': '2024-02-06 20:26:03', 'last_seen_spending': '2024-07-10 08:28:52',
                            'scripthash_type': None, 'transaction_count': 42,
                            'formats': {'legacy': '1JpdvWEBvxoy4RLDsWVouHkasmkg2rQH6n',
                                        'cashaddr': 'qrpheq5xdshy84tp7klp7u5phuyg7ffy0v4jkj8hqn'}}, 'transactions': [
                    {'block_id': 853850, 'hash': 'a4cde0864f4f78161210ce60f8234b7b5bcb1522069b68797b9b588fdb6257de',
                     'time': '2024-07-10 08:28:52', 'balance_change': -9993659844},
                    {'block_id': 853849, 'hash': '16bbab91b66a37c4b6c914790519e067a84d0aa24259e7537bbb6fc42db1d2bd',
                     'time': '2024-07-10 08:16:28', 'balance_change': -220000001134},
                    {'block_id': 853849, 'hash': '1633e17f7b8a6b85a0dddd8811d321d69074be36432f063f43b910ec3e606982',
                     'time': '2024-07-10 08:16:28', 'balance_change': -100000000684},
                    {'block_id': 853845, 'hash': '726f973af90ec0b2d97a7635698b308a7762710d2d7cc1fda964aba2db53a24b',
                     'time': '2024-07-10 08:08:37', 'balance_change': 329993659160},
                    {'block_id': 853195, 'hash': '6b17cf7c51e3541d82ea76d4c938a668e59954621c6680022ee98adcf64b25bb',
                     'time': '2024-07-04 09:02:28', 'balance_change': -49455000378},
                    {'block_id': 853195, 'hash': '5b152083cd01194df6b70df7f17060ad4edb8b1b9ea8253b44ea9eecbf1a3f3c',
                     'time': '2024-07-04 09:02:28', 'balance_change': -100000000228},
                    {'block_id': 853194, 'hash': '30988e32d6442284bd22dc6df7fd63bfe9e9bbe936f2c924b9940f651b3c6dcc',
                     'time': '2024-07-04 08:43:47', 'balance_change': 149455892888},
                    {'block_id': 851882, 'hash': 'cc7ec77867abc174e1412a30c5a0c47d6ec0b6d3e8167c63bf89aea2d9d13a7a',
                     'time': '2024-06-26 09:58:26', 'balance_change': -65000000456},
                    {'block_id': 851882, 'hash': 'a4948005648c11102aeafb0ecb616d7150e3d8a2ab6ba4a0acb2724f538a6770',
                     'time': '2024-06-26 09:58:26', 'balance_change': -10000000456},
                    {'block_id': 851882, 'hash': '4e382d63527bd36929141b9e12c4ba8626eaccc4f25e65fe3256f195de4cef19',
                     'time': '2024-06-26 09:58:26', 'balance_change': -25000000228},
                    {'block_id': 851875, 'hash': '9b16b44043049bde0a6a4344b1bb9adbfdd8a5f851b630e04c4e768d82db56e1',
                     'time': '2024-06-26 08:37:19', 'balance_change': -31096704078},
                    {'block_id': 851870, 'hash': '0ec96e719c85a061cae84cc103ca853b19776de91f731b9f9de657883f1efc15',
                     'time': '2024-06-26 08:05:56', 'balance_change': 131096703700},
                    {'block_id': 851211, 'hash': 'a946727b136bcb67ab92a068adf68239587776a68d3a868f7ddf163dee00d711',
                     'time': '2024-06-21 21:24:56', 'balance_change': -56230981268},
                    {'block_id': 851211, 'hash': '9f046457af689728e39a2143a92ee1bc1aea2818f2aab54b647d51f6137fcbdb',
                     'time': '2024-06-21 21:24:56', 'balance_change': -20000000228},
                    {'block_id': 851209, 'hash': 'e8d33439936a290355fdbe35b04c5bf49df51cb5d3b9a99bde8cfab8855e33d3',
                     'time': '2024-06-21 21:14:05', 'balance_change': -100000228}], 'utxo': [{'block_id': 853850,
                                                                                              'transaction_hash': 'a4cde0864f4f78161210ce60f8234b7b5bcb1522069b68797b9b588fdb6257de',
                                                                                              'index': 1,
                                                                                              'value': 11912144}]}},
             'context': {'code': 200, 'source': 'D', 'limit': '15,15', 'offset': '0,0', 'results': 1, 'state': 853882,
                         'market_price_usd': 336.4,
                         'cache': {'live': True, 'duration': 60, 'since': '2024-07-10 15:00:47',
                                   'until': '2024-07-10 15:01:47', 'time': None},
                         'api': {'version': '2.0.95-ie', 'last_major_update': '2022-11-07 02:00:00',
                                 'next_major_update': '2023-11-12 02:00:00',
                                 'documentation': 'https://blockchair.com/api/docs',
                                 'notice': 'Try out our new API v.3: https://3xpl.com/data'}, 'servers': 'API4,BCH0',
                         'time': 1.0865299701690674, 'render_time': 0.0028879642486572266,
                         'full_time': 1.0894179344177246, 'request_cost': 2}}
        ]
        self.api.request = Mock(side_effect=address_txs_mock_response)
        addresses_txs = []
        for address in self.address_txs:
            api_response = self.api.get_address_txs(address)
            parsed_response = self.api.parser.parse_address_txs_response(address, api_response, None)
            addresses_txs.append(parsed_response)
        expected_addresses_txs = [[TransferTx(tx_hash='16bbab91b66a37c4b6c914790519e067a84d0aa24259e7537bbb6fc42db1d2bd', success=True, from_address='', to_address='1KmC84WxyKVMXVheFExKBfnQVqDFEipJHK', value=Decimal('2200.00000000'), symbol='BCH', confirmations=33, block_height=853849, block_hash=None, date=datetime.datetime(2024, 7, 10, 8, 16, 28, tzinfo=UTC), memo=None, tx_fee=None, token=None, index=None)], [TransferTx(tx_hash='726f973af90ec0b2d97a7635698b308a7762710d2d7cc1fda964aba2db53a24b', success=True, from_address='', to_address='1JpdvWEBvxoy4RLDsWVouHkasmkg2rQH6n', value=Decimal('3299.93659160'), symbol='BCH', confirmations=37, block_height=853845, block_hash=None, date=datetime.datetime(2024, 7, 10, 8, 8, 37, tzinfo=UTC), memo=None, tx_fee=None, token=None, index=None), TransferTx(tx_hash='30988e32d6442284bd22dc6df7fd63bfe9e9bbe936f2c924b9940f651b3c6dcc', success=True, from_address='', to_address='1JpdvWEBvxoy4RLDsWVouHkasmkg2rQH6n', value=Decimal('1494.55892888'), symbol='BCH', confirmations=688, block_height=853194, block_hash=None, date=datetime.datetime(2024, 7, 4, 8, 43, 47, tzinfo=UTC), memo=None, tx_fee=None, token=None, index=None), TransferTx(tx_hash='0ec96e719c85a061cae84cc103ca853b19776de91f731b9f9de657883f1efc15', success=True, from_address='', to_address='1JpdvWEBvxoy4RLDsWVouHkasmkg2rQH6n', value=Decimal('1310.96703700'), symbol='BCH', confirmations=2012, block_height=851870, block_hash=None, date=datetime.datetime(2024, 6, 26, 8, 5, 56, tzinfo=UTC), memo=None, tx_fee=None, token=None, index=None)]]
        for address_txs, expected_address_txs in zip(addresses_txs, expected_addresses_txs):
            assert address_txs == expected_address_txs
