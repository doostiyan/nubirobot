from unittest import TestCase
import pytest
import datetime
import pytz
from decimal import Decimal

from exchange.base.models import Currencies
from unittest.mock import Mock

from exchange.blockchain.api.ton.ton_explorer_interface import TonExplorerInterface

from exchange.blockchain.explorer_original import BlockchainExplorer

from exchange.blockchain.api.ton.ton_indexer import TonIndexerApi


class TestTonIndexerTonApiCalls(TestCase):
    api = TonIndexerApi

    addresses = ['EQCA1BI4QRZ8qYmskSRDzJmkucGodYRTZCf_b9hckjla6dZl']
    txs_hash = ['tdOToZDKIeTzzSua9Q/qnBM21nx2k2actWNfCSC7RYA=']

    @pytest.mark.slow
    def test_get_block_head_api(self):
        get_block_head_response = self.api.get_block_head()
        assert len(get_block_head_response) == 1
        assert {'seqno'}.issubset(set(get_block_head_response[0].keys()))

    @pytest.mark.slow
    def test_get_tx_details_api(self):
        for tx_hash in self.txs_hash:
            get_tx_details_response = self.api.get_tx_details(tx_hash)
            assert {'hash', 'utime', 'compute_skip_reason',
                    'compute_exit_code', 'in_msg', 'out_msgs'}.issubset(set(get_tx_details_response.keys()))
            assert {'source', 'destination', 'value'}.issubset(set(get_tx_details_response.get('in_msg')))

    @pytest.mark.slow
    def test_get_address_txs_api(self):
        for address in self.addresses:
            get_address_txs_response = self.api.get_address_txs(address)
            assert {'hash', 'utime', 'compute_skip_reason', 'compute_exit_code', 'in_msg', 'out_msgs'}.issubset(
                set(get_address_txs_response[0].keys()))
            assert {'source', 'destination', 'value'}.issubset(set(get_address_txs_response[0].get('in_msg')))


class TestTonIndexerTonFromExplorer(TestCase):
    api = TonIndexerApi

    addresses = ['EQCA1BI4QRZ8qYmskSRDzJmkucGodYRTZCf_b9hckjla6dZl']
    txs_hash = ['tdOToZDKIeTzzSua9Q/qnBM21nx2k2actWNfCSC7RYA=']

    def test_get_tx_details(self):
        tx_details_mock_responses = [
            [{
                "workchain": 0,
                "shard": "-9223372036854775808",
                "seqno": 34311242,
                "root_hash": "YcUzeYuY9slqI/pRa8s2eEHYKxbtleV6Bph1UHrC2IM=",
                "file_hash": "95h6Gdydz0J7WQLhaHo4OWf8kG+ohSymaiBGhrv57zE=",
                "gen_utime": 1681109435,
                "start_lt": 36721503000000,
                "end_lt": 36721503000001
            }],
            {'account': '0:5f00decb7da51881764dc3959cec60609045f6ca1b89e646bde49d492705d77f', 'lt': '36349091000003',
             'hash': 'tdOToZDKIeTzzSua9Q/qnBM21nx2k2actWNfCSC7RYA=', 'utime': 1679818743, 'fee': '100002',
             'storage_fee': '2', 'other_fee': '100000', 'transaction_type': 'trans_ord', 'compute_skip_reason': None,
             'compute_exit_code': 0, 'compute_gas_used': '62', 'compute_gas_limit': '1000000',
             'compute_gas_credit': None, 'compute_gas_fees': '100000', 'compute_vm_steps': 3, 'action_result_code': 0,
             'action_total_fwd_fees': None, 'action_total_action_fees': None,
             'in_msg': {'source': '0:57eb74407604a19f7e04005315ef70aeb7b675e6551977586756f6baf12125ee',
                        'destination': '0:5f00decb7da51881764dc3959cec60609045f6ca1b89e646bde49d492705d77f',
                        'value': '29999980000000', 'fwd_fee': '666672', 'ihr_fee': '0', 'import_fee': None,
                        'created_lt': '36349091000002', 'op': '0x00000000',
                        'hash': '6r7FugNmtssuyejDFQEDA9R97eq2Jl160uyaBN0Hztk=',
                        'body_hash': '7bwlAn6BaDC6XDy9dMyHWrK8OL974pHJXqFlSrIXo44=', 'bounce': False, 'bounced': False,
                        'has_init_state': False, 'body': {'type': 'text_comment', 'comment': '6044311'}},
             'out_msgs': [], 'block': None},

        ]
        self.api.request = Mock(side_effect=tx_details_mock_responses)
        TonExplorerInterface.tx_details_apis[0] = self.api
        txs_details = BlockchainExplorer.get_transactions_details(self.txs_hash, 'TON', raise_error=True)
        expected_txs_details = [
            {'success': True, 'block': 0,
             'date': datetime.datetime(2023, 3, 26, 8, 19, 3, tzinfo=datetime.timezone.utc),
             'raw': None,
             'inputs': [], 'outputs': [], 'transfers': [{'type': 'MainCoin', 'symbol': 'TON', 'currency': 145,
                                                         'to': 'EQBfAN7LfaUYgXZNw5Wc7GBgkEX2yhuJ5ka95J1JJwXXf4a8',
                                                         'value': Decimal('29999.980000000'), 'is_valid': True,
                                                         'token': None, 'memo': '6044311',
                                                         'from': 'EQBX63RAdgShn34EAFMV73Cut7Z15lUZd1hnVva68SEl7sxi'}],
             'fees': None, 'memo': '6044311', 'confirmations': 1244948,
             'hash': 'tdOToZDKIeTzzSua9Q/qnBM21nx2k2actWNfCSC7RYA='}
        ]
        for expected_tx_detail, tx_hash in zip(expected_txs_details, self.txs_hash):
            if txs_details[tx_hash].get('success'):
                txs_details[tx_hash]['confirmations'] = expected_tx_detail.get('confirmations')
            assert txs_details.get(tx_hash) == expected_tx_detail

    @pytest.mark.slow
    def test_get_address_txs(self):
        address_txs_mock_responses = [
            [{
                "workchain": 0,
                "shard": "-9223372036854775808",
                "seqno": 35802897,
                "root_hash": "XLr9dbE5e1yUaLgU9d4DUHy0XrDz2/Qfl5uZ1uVZNSk=",
                "file_hash": "hFgld245ImFZi5jUJ/D3+eMTeoJAJObRcJ9yn+Sh7Es=",
                "gen_utime": 1686042744,
                "start_lt": 38253241000000,
                "end_lt": 38253241000016
            }],
            [{'account': '0:80d4123841167ca989ac912443cc99a4b9c1a87584536427ff6fd85c92395ae9', 'lt': '38253439000001',
              'hash': 'i3QlHlO9M/0o6He66qOqWw2geLG7zOEAXIOeN2mYWus=', 'utime': 1686043377, 'fee': '5518005',
              'storage_fee': '5', 'other_fee': '5518000', 'transaction_type': 'trans_ord', 'compute_skip_reason': None,
              'compute_exit_code': 0, 'compute_gas_used': '2994', 'compute_gas_limit': '0',
              'compute_gas_credit': '10000', 'compute_gas_fees': '2994000', 'compute_vm_steps': 66,
              'action_result_code': 0, 'action_total_fwd_fees': '1000000', 'action_total_action_fees': '333328',
              'in_msg': {'source': '',
                         'destination': '0:80d4123841167ca989ac912443cc99a4b9c1a87584536427ff6fd85c92395ae9',
                         'value': '0', 'fwd_fee': '0', 'ihr_fee': '0', 'import_fee': '0', 'created_lt': '0',
                         'op': '0xe19b9ba9', 'hash': 'WTHo16JIa4/+VtETjkAZLSCcQs7l2j52WN3TziW4VDA=',
                         'body_hash': 'JQa4eVFjGnxd/egQ0XLxRSbi0PLCwjrpj1+1yu3DWZI=', 'bounce': None, 'bounced': None,
                         'has_init_state': False, 'body': {'type': 'raw',
                                                           'boc': 'te6cckEBAgEAhwABmuGbm6moQqGmBJT4EY1TdktN8CpAt7Sgo41Hg4A/63CuOeB8tVMx8UWSMqtHN2qCDUTToBkgOJIBVrPoMS7ywwwpqaMXZH8I3QAAZQEDAQBqQgBZvyuBntkOiFyocwodssYIYd+hLejJgSywV3v5Ft56figKjPf+0AAAAAAAAAAAAAAAAABqPBED'}},
              'out_msgs': [{'source': '0:80d4123841167ca989ac912443cc99a4b9c1a87584536427ff6fd85c92395ae9',
                            'destination': '0:b37e57033db21d10b950e6143b658c10c3bf425bd193025960aef7f22dbcf4fc',
                            'value': '5664341978', 'fwd_fee': '666672', 'ihr_fee': '0', 'import_fee': None,
                            'created_lt': '38253439000002', 'op': None,
                            'hash': 'VJPODgCnKMH5sltPKN8IZGXqbY1HOO5IAW6gkGiRv4s=',
                            'body_hash': 'lqKW0iTyhcZ77pPDD4owkVfw2qNdxbh+QQt4YwoJz8c=', 'bounce': False,
                            'bounced': False, 'has_init_state': False,
                            'body': {'type': 'raw', 'boc': 'te6cckEBAQEAAgAAAEysuc0='}}], 'block': None},
             {'account': '0:80d4123841167ca989ac912443cc99a4b9c1a87584536427ff6fd85c92395ae9', 'lt': '38253402000003',
              'hash': 'f35Sk2EVOaKxBequYwMYaoRWcI3gnemkUnYPnEFPdV0=', 'utime': 1686043265, 'fee': '100037',
              'storage_fee': '37', 'other_fee': '100000', 'transaction_type': 'trans_ord', 'compute_skip_reason': None,
              'compute_exit_code': 0, 'compute_gas_used': '62', 'compute_gas_limit': '1000000',
              'compute_gas_credit': None, 'compute_gas_fees': '100000', 'compute_vm_steps': 3, 'action_result_code': 0,
              'action_total_fwd_fees': None, 'action_total_action_fees': None,
              'in_msg': {'source': '0:6546cc8d471e702c88d27eecd36c52b82cb98b8644a5b236a1423cb19d625c8a',
                         'destination': '0:80d4123841167ca989ac912443cc99a4b9c1a87584536427ff6fd85c92395ae9',
                         'value': '5674341978', 'fwd_fee': '666672', 'ihr_fee': '0', 'import_fee': None,
                         'created_lt': '38253402000002', 'op': '0x00000000',
                         'hash': 'JUK0lN3i5IN9l9cLLc/t8hpHLed7X8tuw3ANYxNsaDs=',
                         'body_hash': 'ALWvBifmRpL7VwjHNoxnsfYI1jiC8LOeEzetqEzGuBY=', 'bounce': True, 'bounced': False,
                         'has_init_state': False, 'body': {'type': 'text_comment', 'comment': '1928967897'}},
              'out_msgs': [], 'block': None},
             {'account': '0:80d4123841167ca989ac912443cc99a4b9c1a87584536427ff6fd85c92395ae9', 'lt': '38253140000001',
              'hash': 'bItG8c2CLqVCr5hZAFN7ezLLV0XhwdyStZTEZUwtVRs=', 'utime': 1686042418, 'fee': '5510004',
              'storage_fee': '4', 'other_fee': '5510000', 'transaction_type': 'trans_ord', 'compute_skip_reason': None,
              'compute_exit_code': 0, 'compute_gas_used': '2994', 'compute_gas_limit': '0',
              'compute_gas_credit': '10000', 'compute_gas_fees': '2994000', 'compute_vm_steps': 66,
              'action_result_code': 0, 'action_total_fwd_fees': '1000000', 'action_total_action_fees': '333328',
              'in_msg': {'source': '',
                         'destination': '0:80d4123841167ca989ac912443cc99a4b9c1a87584536427ff6fd85c92395ae9',
                         'value': '0', 'fwd_fee': '0', 'ihr_fee': '0', 'import_fee': '0', 'created_lt': '0',
                         'op': '0x91814b4e', 'hash': 'AL/A2cE73FJVdVFb955iKu7r6q42FhHI5gWJfpVqQps=',
                         'body_hash': 'ZS2PKysR7/23jUJWyl2h7NiA2JqZ2g1qrC+oTEs/w8U=', 'bounce': None, 'bounced': None,
                         'has_init_state': False, 'body': {'type': 'raw',
                                                           'boc': 'te6cckEBAgEAhgABmpGBS05b+X2vnhlRHGKFCYAabpWio6sK+u1+LGd6vkuyAaHE0APUC3kBmQvV5IAr5jAmgCqeymyorgatb452bwEpqaMXZH8FHAAAZQADAQBoQgBZvyuBntkOiFyocwodssYIYd+hLejJgSywV3v5Ft56fiJFGpqQAAAAAAAAAAAAAAAAABxUXHo='}},
              'out_msgs': [{'source': '0:80d4123841167ca989ac912443cc99a4b9c1a87584536427ff6fd85c92395ae9',
                            'destination': '0:b37e57033db21d10b950e6143b658c10c3bf425bd193025960aef7f22dbcf4fc',
                            'value': '1218663250', 'fwd_fee': '666672', 'ihr_fee': '0', 'import_fee': None,
                            'created_lt': '38253140000002', 'op': None,
                            'hash': 'rFdXEU25/ilfVwy++ZqnpPPrs7HH9ggN26ZuDYOItqs=',
                            'body_hash': 'lqKW0iTyhcZ77pPDD4owkVfw2qNdxbh+QQt4YwoJz8c=', 'bounce': False,
                            'bounced': False, 'has_init_state': False,
                            'body': {'type': 'raw', 'boc': 'te6cckEBAQEAAgAAAEysuc0='}}], 'block': None},
             {'account': '0:80d4123841167ca989ac912443cc99a4b9c1a87584536427ff6fd85c92395ae9', 'lt': '38253111000003',
              'hash': 'tsMWjOHX5KgkBvRV+cmfM8zx7nht7dqgpxuxt0jeA/o=', 'utime': 1686042329, 'fee': '100007',
              'storage_fee': '7', 'other_fee': '100000', 'transaction_type': 'trans_ord', 'compute_skip_reason': None,
              'compute_exit_code': 0, 'compute_gas_used': '62', 'compute_gas_limit': '1000000',
              'compute_gas_credit': None, 'compute_gas_fees': '100000', 'compute_vm_steps': 3, 'action_result_code': 0,
              'action_total_fwd_fees': None, 'action_total_action_fees': None,
              'in_msg': {'source': '0:622db0f1e4eb7454e8b386b79b88d1a6e0a6863e61f25f0b04dc7267270c743f',
                         'destination': '0:80d4123841167ca989ac912443cc99a4b9c1a87584536427ff6fd85c92395ae9',
                         'value': '1228663250', 'fwd_fee': '666672', 'ihr_fee': '0', 'import_fee': None,
                         'created_lt': '38253111000002', 'op': '0x00000000',
                         'hash': 'W8QEO/wDKyW57iYBTGoHvFtQRlZ35l+pam2F1ocpzCQ=',
                         'body_hash': 'gXRAbhgIBtm1O2HRUI7Ca8RytRpIh0oHwwe3Ff2i5Ik=', 'bounce': False, 'bounced': False,
                         'has_init_state': False, 'body': {'type': 'text_comment', 'comment': '1890714229'}},
              'out_msgs': [], 'block': None},
             {'account': '0:80d4123841167ca989ac912443cc99a4b9c1a87584536427ff6fd85c92395ae9', 'lt': '38253063000001',
              'hash': 'Xwe2vXGUWQzGh2RNz9p3e3E08MVxYQA95AneTGm9e/Q=', 'utime': 1686042178, 'fee': '5518006',
              'storage_fee': '6', 'other_fee': '5518000', 'transaction_type': 'trans_ord', 'compute_skip_reason': None,
              'compute_exit_code': 0, 'compute_gas_used': '2994', 'compute_gas_limit': '0',
              'compute_gas_credit': '10000', 'compute_gas_fees': '2994000', 'compute_vm_steps': 66,
              'action_result_code': 0, 'action_total_fwd_fees': '1000000', 'action_total_action_fees': '333328',
              'in_msg': {'source': '',
                         'destination': '0:80d4123841167ca989ac912443cc99a4b9c1a87584536427ff6fd85c92395ae9',
                         'value': '0', 'fwd_fee': '0', 'ihr_fee': '0', 'import_fee': '0', 'created_lt': '0',
                         'op': '0x4ca959be', 'hash': 'cQMy7h8DRSYt4BVNL1E6X/OOLVFzGgjElfgL1Ov1/C4=',
                         'body_hash': 'C/T/KTAIWVwHKllfgMfC0lGh/hIFm3hAAve0zuh5lHE=', 'bounce': None, 'bounced': None,
                         'has_init_state': False, 'body': {'type': 'raw',
                                                           'boc': 'te6cckEBAgEAhwABmkypWb6MqLwROT4aq05Kc2tWsIScqE1ilpeegV1f3+Ks+YHpVVs3pxR8Va0eKXpDfsrVCltO1gdLzKp+27wnfQ8pqaMXZH8ELAAAZP8DAQBqQgBZvyuBntkOiFyocwodssYIYd+hLejJgSywV3v5Ft56fippfxmDAAAAAAAAAAAAAAAAAACDztKs'}},
              'out_msgs': [{'source': '0:80d4123841167ca989ac912443cc99a4b9c1a87584536427ff6fd85c92395ae9',
                            'destination': '0:b37e57033db21d10b950e6143b658c10c3bf425bd193025960aef7f22dbcf4fc',
                            'value': '331515900000', 'fwd_fee': '666672', 'ihr_fee': '0', 'import_fee': None,
                            'created_lt': '38253063000002', 'op': None,
                            'hash': 'E9hck2fK1CI0MUDRwP3PuFNIEJJR7bhoBxh3ldIA/1U=',
                            'body_hash': 'lqKW0iTyhcZ77pPDD4owkVfw2qNdxbh+QQt4YwoJz8c=', 'bounce': False,
                            'bounced': False, 'has_init_state': False,
                            'body': {'type': 'raw', 'boc': 'te6cckEBAQEAAgAAAEysuc0='}}], 'block': None}]
        ]
        self.api.request = Mock(side_effect=address_txs_mock_responses)
        TonExplorerInterface.address_txs_apis[0] = self.api
        expected_addresses_txs = [
            [
                {
                    'address': 'EQCA1BI4QRZ8qYmskSRDzJmkucGodYRTZCf_b9hckjla6dZl',
                    'block': None,
                    'confirmations': 66,
                    'details': {},
                    'from_address': ['EQCA1BI4QRZ8qYmskSRDzJmkucGodYRTZCf_b9hckjla6dZl'],
                    'hash': 'i3QlHlO9M/0o6He66qOqWw2geLG7zOEAXIOeN2mYWus=',
                    'huge': False,
                    'invoice': None,
                    'is_double_spend': False,
                    'tag': None,
                    'timestamp': datetime.datetime(2023, 6, 6, 9, 22, 57, tzinfo=pytz.utc),
                    'value': Decimal('-5.664341978'),
                    'contract_address': None

                },
                {
                    'address': 'EQCA1BI4QRZ8qYmskSRDzJmkucGodYRTZCf_b9hckjla6dZl',
                    'block': None,
                    'confirmations': 252,
                    'details': {},
                    'from_address': ['EQBlRsyNRx5wLIjSfuzTbFK4LLmLhkSlsjahQjyxnWJcii97'],
                    'hash': 'f35Sk2EVOaKxBequYwMYaoRWcI3gnemkUnYPnEFPdV0=',
                    'huge': False,
                    'invoice': None,
                    'is_double_spend': False,
                    'tag': '1928967897',
                    'timestamp': datetime.datetime(2023, 6, 6, 9, 21, 5, tzinfo=pytz.utc),
                    'value': Decimal('5.674341978'),
                    'contract_address': None

                },
                {
                    'address': 'EQCA1BI4QRZ8qYmskSRDzJmkucGodYRTZCf_b9hckjla6dZl',
                    'block': None,
                    'confirmations': 522,
                    'details': {},
                    'from_address': ['EQCA1BI4QRZ8qYmskSRDzJmkucGodYRTZCf_b9hckjla6dZl'],
                    'hash': 'bItG8c2CLqVCr5hZAFN7ezLLV0XhwdyStZTEZUwtVRs=',
                    'huge': False,
                    'invoice': None,
                    'is_double_spend': False,
                    'tag': None,
                    'timestamp': datetime.datetime(2023, 6, 6, 9, 6, 58, tzinfo=pytz.utc),
                    'value': Decimal('-1.218663250'),
                    'contract_address': None

                },
                {
                    'address': 'EQCA1BI4QRZ8qYmskSRDzJmkucGodYRTZCf_b9hckjla6dZl',
                    'block': None,
                    'confirmations': 539,
                    'details': {},
                    'from_address': ['EQBiLbDx5Ot0VOizhrebiNGm4KaGPmHyXwsE3HJnJwx0P2kJ'],
                    'hash': 'tsMWjOHX5KgkBvRV+cmfM8zx7nht7dqgpxuxt0jeA/o=',
                    'huge': False,
                    'invoice': None,
                    'is_double_spend': False,
                    'tag': '1890714229',
                    'timestamp': datetime.datetime(2023, 6, 6, 9, 5, 29, tzinfo=pytz.utc),
                    'value': Decimal('1.228663250'),
                    'contract_address': None

                },
                {
                    'address': 'EQCA1BI4QRZ8qYmskSRDzJmkucGodYRTZCf_b9hckjla6dZl',
                    'block': None,
                    'confirmations': 570,
                    'details': {},
                    'from_address': ['EQCA1BI4QRZ8qYmskSRDzJmkucGodYRTZCf_b9hckjla6dZl'],
                    'hash': 'Xwe2vXGUWQzGh2RNz9p3e3E08MVxYQA95AneTGm9e/Q=',
                    'huge': False,
                    'invoice': None,
                    'is_double_spend': False,
                    'tag': None,
                    'timestamp': datetime.datetime(2023, 6, 6, 9, 2, 58, tzinfo=pytz.utc),
                    'value': Decimal('-331.515900000'),
                    'contract_address': None
                },
            ]
        ]
        for address, expected_address_txs in zip(self.addresses, expected_addresses_txs):
            address_txs = BlockchainExplorer.get_wallet_transactions(address, Currencies.ton, 'TON')
        # assert len(expected_address_txs) == len(address_txs.get(Currencies.ton))
        for expected_address_tx, address_tx in zip(expected_address_txs, address_txs.get(Currencies.ton)):
            assert address_tx.confirmations > expected_address_tx.get('confirmations')
        address_tx.confirmations = expected_address_tx.get('confirmations')
        assert address_tx.__dict__ == expected_address_tx
