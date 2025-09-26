from unittest import TestCase
from unittest.mock import Mock

from django.conf import settings
import datetime
import pytest
from _decimal import Decimal

from pytz import UTC

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

from exchange.blockchain.api.general.dtos import TransferTx

from exchange.blockchain.api.bch.bch_haskoin import BitcoinCashHaskoinApi


@pytest.mark.slow
class BitcoinCashHaskoinApiCalls(TestCase):
    api = BitcoinCashHaskoinApi
    hash_of_transactions = ['16bbab91b66a37c4b6c914790519e067a84d0aa24259e7537bbb6fc42db1d2bd',
                            '1633e17f7b8a6b85a0dddd8811d321d69074be36432f063f43b910ec3e606982',
                            '0ec96e719c85a061cae84cc103ca853b19776de91f731b9f9de657883f1efc15'
                            ]

    def test_get_tx_details_api(self):
        transaction_keys = {'txid', 'block', 'time', 'fee', 'inputs', 'outputs'}
        types_check = [('block', dict), ('txid', str), ('inputs', list), ('fee', int), ('time', int), ('outputs', list)]
        transfer_keys = {'coinbase', 'txid', 'output', 'sigscript', 'sequence', 'pkscript', 'value', 'address',
                         'witness'}
        transfer_type_check = [('coinbase', bool), ('txid', str), ('output', int), ('sigscript', str),
                               ('sequence', int),
                               ('pkscript', str), ('value', int), ('address', str), ('witness', list)]
        for tx_hash in self.hash_of_transactions:
            get_tx_details_response = self.api.get_tx_details(tx_hash)
            if transaction_keys.issubset(get_tx_details_response.keys()):
                if get_tx_details_response.get('inputs') and get_tx_details_response.get('outputs'):
                    for key, value in types_check:
                        assert isinstance(get_tx_details_response.get(key), value)
                    assert get_tx_details_response.get('block').get('height')
                    assert isinstance(get_tx_details_response.get('block').get('height'), int)
                    transfers = get_tx_details_response.get('inputs') + get_tx_details_response.get('outputs')
                    for transfer in transfers:
                        if transfer_keys.issubset(transfer.keys()):
                            for key, value in transfer_type_check:
                                assert isinstance(transfer.get(key), value)


class TestBitcoinCashHaskoinApiFromExplorer(TestCase):
    api = BitcoinCashHaskoinApi
    currency = Currencies.bch
    hash_of_transactions = ['16bbab91b66a37c4b6c914790519e067a84d0aa24259e7537bbb6fc42db1d2bd',
                            '1633e17f7b8a6b85a0dddd8811d321d69074be36432f063f43b910ec3e606982',
                            '0ec96e719c85a061cae84cc103ca853b19776de91f731b9f9de657883f1efc15'
                            ]

    def test_get_tx_details(self):
        tx_details_mock_response = [
            {'txid': '16bbab91b66a37c4b6c914790519e067a84d0aa24259e7537bbb6fc42db1d2bd', 'size': 373, 'version': 2,
             'locktime': 0, 'fee': 1134, 'inputs': [
                {'coinbase': False, 'txid': '5b152083cd01194df6b70df7f17060ad4edb8b1b9ea8253b44ea9eecbf1a3f3c',
                 'output': 1,
                 'sigscript': '473044022033818011c3579a24fe542c750076cb6a5803fe6150e94de1fba82870cc7e03730220023c176c512fc1f9913d3d216c434205457f1a97dd3d44abebeed538b4db8299412103e668efb0d32744f477e6ab280ea25601d969c0a7d2fdadac2899fbdbeceffe70',
                 'sequence': 4294967295, 'pkscript': '76a914c37c82866c2e43d561f5be1f7281bf088f25247b88ac',
                 'value': 11914646, 'address': 'bitcoincash:qrpheq5xdshy84tp7klp7u5phuyg7ffy0v4jkj8hqn', 'witness': []},
                {'coinbase': False, 'txid': '726f973af90ec0b2d97a7635698b308a7762710d2d7cc1fda964aba2db53a24b',
                 'output': 0,
                 'sigscript': '483045022100d57847d8be2f68f2e16fc96b57ed1db9a62bd8cf30215a5b4fcb8fe73673d7d102201da1d142fcf12ab2593da1f2fd1b7ce7a97c26203c3687711414c7b320321df2412103e668efb0d32744f477e6ab280ea25601d969c0a7d2fdadac2899fbdbeceffe70',
                 'sequence': 4294967295, 'pkscript': '76a914c37c82866c2e43d561f5be1f7281bf088f25247b88ac',
                 'value': 329993659160, 'address': 'bitcoincash:qrpheq5xdshy84tp7klp7u5phuyg7ffy0v4jkj8hqn',
                 'witness': []}], 'outputs': [{'address': 'bitcoincash:qrxumkdjh5hfw7za08u2t9qcjag7dqud0v5g9mt6d8',
                                               'pkscript': '76a914cdcdd9b2bd2e97785d79f8a594189751e6838d7b88ac',
                                               'value': 220000000000, 'spent': True, 'spender': {
                    'txid': '11a89edb7ce306f2e61a98b4a6d8f27a4a5d583ab5f6c67cd5cde09164c414b0', 'input': 1}},
                                              {'address': 'bitcoincash:qrpheq5xdshy84tp7klp7u5phuyg7ffy0v4jkj8hqn',
                                               'pkscript': '76a914c37c82866c2e43d561f5be1f7281bf088f25247b88ac',
                                               'value': 110005572672, 'spent': True, 'spender': {
                                                  'txid': '1633e17f7b8a6b85a0dddd8811d321d69074be36432f063f43b910ec3e606982',
                                                  'input': 0}}], 'block': {'height': 853849, 'position': 8},
             'deleted': False, 'time': 1720599308, 'rbf': False, 'weight': 1492},
            {'txid': '1633e17f7b8a6b85a0dddd8811d321d69074be36432f063f43b910ec3e606982', 'size': 225, 'version': 2,
             'locktime': 0, 'fee': 684, 'inputs': [
                {'coinbase': False, 'txid': '16bbab91b66a37c4b6c914790519e067a84d0aa24259e7537bbb6fc42db1d2bd',
                 'output': 1,
                 'sigscript': '47304402202d5b5f435bb148afd069fbfb0c684812778bff4e57a69cfda7b6d0e4b35ff079022048d040eb653bef041d2d87961d6dfde1377c4a019c035695f9df0f38d0f87766412103e668efb0d32744f477e6ab280ea25601d969c0a7d2fdadac2899fbdbeceffe70',
                 'sequence': 4294967295, 'pkscript': '76a914c37c82866c2e43d561f5be1f7281bf088f25247b88ac',
                 'value': 110005572672, 'address': 'bitcoincash:qrpheq5xdshy84tp7klp7u5phuyg7ffy0v4jkj8hqn',
                 'witness': []}], 'outputs': [{'address': 'bitcoincash:qqvhuykkllnv8jv44xtz5r2mqhlhlx64asmgvahn44',
                                               'pkscript': '76a914197e12d6ffe6c3c995a9962a0d5b05ff7f9b55ec88ac',
                                               'value': 100000000000, 'spent': True, 'spender': {
                    'txid': '88bbc26c97a44f8b86bd6366a6a62820d3318c93f1742901ef6b5d88066390c3', 'input': 1}},
                                              {'address': 'bitcoincash:qrpheq5xdshy84tp7klp7u5phuyg7ffy0v4jkj8hqn',
                                               'pkscript': '76a914c37c82866c2e43d561f5be1f7281bf088f25247b88ac',
                                               'value': 10005571988, 'spent': True, 'spender': {
                                                  'txid': 'a4cde0864f4f78161210ce60f8234b7b5bcb1522069b68797b9b588fdb6257de',
                                                  'input': 0}}], 'block': {'height': 853849, 'position': 7},
             'deleted': False, 'time': 1720599383, 'rbf': False, 'weight': 900},
            {'txid': '0ec96e719c85a061cae84cc103ca853b19776de91f731b9f9de657883f1efc15', 'size': 669, 'version': 2,
             'locktime': 0, 'fee': 678, 'inputs': [
                {'coinbase': False, 'txid': '066a90ad415bf53a1ec65cbe2b232f0604e815e05ee1d14666514dec2f2c7212',
                 'output': 1,
                 'sigscript': '4830450221009cbc5cf826f10d0cb156e2c38cdc89c6b4dcdc047ceebfa88e7953931c24daac02205b8984431858d4c3a39cf69bc2afee902efb2aa14e32fe400e4585d31cae32a8412103237e1762d1511057af202b5c689280aff71d1d7d762ae0cd11e2403cdd41dab6',
                 'sequence': 4294967295, 'pkscript': '76a914daf3b86b873675330ce6a29ba6184d0ad094cbed88ac',
                 'value': 884878, 'address': 'bitcoincash:qrd08wrtsum82vcvu63fhfscf59dp9xta5kg0el077', 'witness': []},
                {'coinbase': False, 'txid': '985aa0ce7a401000c94c0efcddb984bdf08c9ba003add7e52a1e12ed5e1be732',
                 'output': 2,
                 'sigscript': '483045022100d2e5e6742f35357587439f05ab62839f96fae9219bacf6a10fedf67246b9816c02205359f6823a0532d1b60bcad9ba673cfaee4e21f5747865761b5774772d287fe7412103237e1762d1511057af202b5c689280aff71d1d7d762ae0cd11e2403cdd41dab6',
                 'sequence': 4294967295, 'pkscript': '76a914daf3b86b873675330ce6a29ba6184d0ad094cbed88ac',
                 'value': 14271850000, 'address': 'bitcoincash:qrd08wrtsum82vcvu63fhfscf59dp9xta5kg0el077',
                 'witness': []},
                {'coinbase': False, 'txid': '6b0128f9edb16e029d45a63a08dee2b1a79c2b5458cb81e40d136d4e70abdcd5',
                 'output': 2,
                 'sigscript': '483045022100e55f4825284f4c04a587cc1939103350f4191f6fe555ce77a7f262266ee3359602202f99d69bbdb5571da62c720c75ecf6a979c02dda3bfdc9e3b8e7a7b0ad0ac9d7412103237e1762d1511057af202b5c689280aff71d1d7d762ae0cd11e2403cdd41dab6',
                 'sequence': 4294967295, 'pkscript': '76a914daf3b86b873675330ce6a29ba6184d0ad094cbed88ac',
                 'value': 17178686400, 'address': 'bitcoincash:qrd08wrtsum82vcvu63fhfscf59dp9xta5kg0el077',
                 'witness': []},
                {'coinbase': False, 'txid': 'd095599f9fc16308e3edf38e528f1efcfea6184213bcbaf6af14974ace6e465d',
                 'output': 2,
                 'sigscript': '473044022006ad6d014d1647efb36ee16c6ceddbc8761f16e04f87a9bed24cd5e111d04e070220726de832393d4e81172e7267bb85ade4643aeac04c452c133c3040affddb1f1f412103237e1762d1511057af202b5c689280aff71d1d7d762ae0cd11e2403cdd41dab6',
                 'sequence': 4294967295, 'pkscript': '76a914daf3b86b873675330ce6a29ba6184d0ad094cbed88ac',
                 'value': 99646167300, 'address': 'bitcoincash:qrd08wrtsum82vcvu63fhfscf59dp9xta5kg0el077',
                 'witness': []}], 'outputs': [{'address': 'bitcoincash:qrpheq5xdshy84tp7klp7u5phuyg7ffy0v4jkj8hqn',
                                               'pkscript': '76a914c37c82866c2e43d561f5be1f7281bf088f25247b88ac',
                                               'value': 131096703700, 'spent': True, 'spender': {
                    'txid': '9b16b44043049bde0a6a4344b1bb9adbfdd8a5f851b630e04c4e768d82db56e1', 'input': 1}},
                                              {'address': 'bitcoincash:qrd08wrtsum82vcvu63fhfscf59dp9xta5kg0el077',
                                               'pkscript': '76a914daf3b86b873675330ce6a29ba6184d0ad094cbed88ac',
                                               'value': 884200, 'spent': False, 'spender': None}],
             'block': {'height': 851870, 'position': 39}, 'deleted': False, 'time': 1719388037, 'rbf': False,
             'weight': 2676}
        ]
        self.api.request = Mock(side_effect=tx_details_mock_response)
        parsed_responses = []
        for tx_hash in self.hash_of_transactions:
            api_response = self.api.get_tx_details(tx_hash)
            parsed_response = self.api.parser.parse_tx_details_response(api_response, None)
            parsed_responses.append(parsed_response)
        expected_txs_details = [[TransferTx(tx_hash='16bbab91b66a37c4b6c914790519e067a84d0aa24259e7537bbb6fc42db1d2bd', success=True, from_address='1JpdvWEBvxoy4RLDsWVouHkasmkg2rQH6n', to_address='', value=Decimal('2200.00001134'), symbol='BCH', confirmations=0, block_height=853849, block_hash=None, date=datetime.datetime(2024, 7, 10, 8, 15, 8, tzinfo=UTC), memo=None, tx_fee=Decimal('0.00001134'), token=None, index=None), TransferTx(tx_hash='16bbab91b66a37c4b6c914790519e067a84d0aa24259e7537bbb6fc42db1d2bd', success=True, from_address='', to_address='1KmC84WxyKVMXVheFExKBfnQVqDFEipJHK', value=Decimal('2200.00000000'), symbol='BCH', confirmations=0, block_height=853849, block_hash=None, date=datetime.datetime(2024, 7, 10, 8, 15, 8, tzinfo=UTC), memo=None, tx_fee=Decimal('0.00001134'), token=None, index=None)], [TransferTx(tx_hash='1633e17f7b8a6b85a0dddd8811d321d69074be36432f063f43b910ec3e606982', success=True, from_address='1JpdvWEBvxoy4RLDsWVouHkasmkg2rQH6n', to_address='', value=Decimal('1000.00000684'), symbol='BCH', confirmations=0, block_height=853849, block_hash=None, date=datetime.datetime(2024, 7, 10, 8, 16, 23, tzinfo=UTC), memo=None, tx_fee=Decimal('0.00000684'), token=None, index=None), TransferTx(tx_hash='1633e17f7b8a6b85a0dddd8811d321d69074be36432f063f43b910ec3e606982', success=True, from_address='', to_address='13KnvYUEtZmt3RueKthw7G3ewTxAPyLcu8', value=Decimal('1000.00000000'), symbol='BCH', confirmations=0, block_height=853849, block_hash=None, date=datetime.datetime(2024, 7, 10, 8, 16, 23, tzinfo=UTC), memo=None, tx_fee=Decimal('0.00000684'), token=None, index=None)], [TransferTx(tx_hash='0ec96e719c85a061cae84cc103ca853b19776de91f731b9f9de657883f1efc15', success=True, from_address='1LxiGouK1h6cYkSFWoK2oZwJZeqcgEXSQy', to_address='', value=Decimal('1310.96704378'), symbol='BCH', confirmations=0, block_height=851870, block_hash=None, date=datetime.datetime(2024, 6, 26, 7, 47, 17, tzinfo=UTC), memo=None, tx_fee=Decimal('0.00000678'), token=None, index=None), TransferTx(tx_hash='0ec96e719c85a061cae84cc103ca853b19776de91f731b9f9de657883f1efc15', success=True, from_address='', to_address='1JpdvWEBvxoy4RLDsWVouHkasmkg2rQH6n', value=Decimal('1310.96703700'), symbol='BCH', confirmations=0, block_height=851870, block_hash=None, date=datetime.datetime(2024, 6, 26, 7, 47, 17, tzinfo=UTC), memo=None, tx_fee=Decimal('0.00000678'), token=None, index=None)]]
        for expected_tx_details, tx_details in zip(expected_txs_details, parsed_responses):
            assert tx_details == expected_tx_details
