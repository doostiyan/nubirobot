from unittest import TestCase
import pytest
import datetime
from decimal import Decimal

import pytz

from exchange.blockchain.api.ton.dton_ton import DtonTonApi

from exchange.blockchain.api.ton.ton_explorer_interface import TonExplorerInterface

from exchange.blockchain.explorer_original import BlockchainExplorer

from exchange.base.models import Currencies
from unittest.mock import Mock


class TestDtonTonApiCalls(TestCase):
    api = DtonTonApi
    addresses = ['EQCA1BI4QRZ8qYmskSRDzJmkucGodYRTZCf_b9hckjla6dZl',
                 'EQC9gfdnZesicH7aqqe9dajUMigvPqADBTcLFS3IP_w8dDu5']
    txs_hash = ['tdOToZDKIeTzzSua9Q/qnBM21nx2k2actWNfCSC7RYA=']
    block_height = [33168776, 33385898]

    @pytest.mark.slow
    def test_get_balance_api(self):
        for address in self.addresses:
            get_balance_result = self.api.get_balance(address)
            assert set(get_balance_result.keys()) == {'data'}
            assert {'transactions'}.issubset(set(get_balance_result.get('data').keys()))
            assert {'account_storage_balance_grams'}.issubset(
                set(get_balance_result.get('data').get('transactions')[0].keys()))

    @pytest.mark.slow
    def test_get_block_head_api(self):
        get_block_head_response = self.api.get_block_head()
        assert set(get_block_head_response.keys()) == {'data'}
        assert {'blocks'}.issubset(set(get_block_head_response.get('data').keys()))
        assert {'seqno'}.issubset(
            set(get_block_head_response.get('data').get('blocks')[0].keys()))

    @pytest.mark.slow
    def test_get_tx_details_api(self):
        for tx_hash in self.txs_hash:
            get_tx_details_response = self.api.get_tx_details(tx_hash)
            assert set(get_tx_details_response.keys()) == {'data'}
            assert {'transactions'}.issubset(set(get_tx_details_response.get('data').keys()))
            assert {'seqno', 'aborted', 'out_msg_value_grams', 'action_ph_result_code', 'in_msg_comment',
                    'in_msg_src_addr_address_hex', 'in_msg_value_grams', 'in_msg_dest_addr_address_hex', 'gen_utime',
                    'hash'}.issubset(set(get_tx_details_response.get('data').get('transactions')[0].keys()))

    @pytest.mark.slow
    def test_get_address_txs_api(self):
        for address in self.addresses:
            get_address_txs_response = self.api.get_address_txs(address)
            assert set(get_address_txs_response.keys()) == {'data'}
            assert {'transactions'}.issubset(set(get_address_txs_response.get('data').keys()))
            assert type(get_address_txs_response.get('data').get('transactions')) == list
            assert {'seqno', 'aborted', 'out_msg_value_grams', 'action_ph_result_code', 'in_msg_comment',
                    'in_msg_src_addr_address_hex', 'in_msg_value_grams', 'in_msg_dest_addr_address_hex', 'gen_utime',
                    'hash'}.issubset(set(get_address_txs_response.get('data').get('transactions')[0].keys()))

    # @pytest.mark.slow
    # def test_get_block_txs_api(self):
    #     for block in self.block_height:
    #         get_block_txs_response = self.api.get_block_txs(block)
    #         assert set(get_block_txs_response.keys()) == {'data'}
    #         assert {'transactions'}.issubset(set(get_block_txs_response.get('data').keys()))
    #         assert type(get_block_txs_response.get('data').get('transactions')) == list
    #         assert {'seqno', 'aborted', 'in_msg_src_addr_address_hex', 'in_msg_dest_addr_address_hex', 'hash',
    #                 'outmsg_cnt', 'in_msg_value_grams', 'gen_utime'}.issubset(
    #             set(get_block_txs_response.get('data').get('transactions')[0].keys()))


class TestDtonTonFromExplorer(TestCase):
    api = DtonTonApi

    addresses = ['EQCA1BI4QRZ8qYmskSRDzJmkucGodYRTZCf_b9hckjla6dZl']
    txs_hash = ['tdOToZDKIeTzzSua9Q/qnBM21nx2k2actWNfCSC7RYA=']

    def test_get_balance(self):
        balance_mock_responses = [
            {
                "data": {
                    "transactions": [
                        {
                            "account_storage_balance_grams": "35956359013517665"
                        }
                    ]
                }
            }
        ]
        self.api.request = Mock(side_effect=balance_mock_responses)
        TonExplorerInterface.balance_apis[0] = self.api
        balances = BlockchainExplorer.get_wallets_balance({'TON': self.addresses}, Currencies.ton)
        expected_balances = [
            {'address': 'EQCA1BI4QRZ8qYmskSRDzJmkucGodYRTZCf_b9hckjla6dZl', 'balance': Decimal('35956359.013517665'),
             'received': Decimal('35956359.013517665'), 'sent': Decimal('0'), 'rewarded': Decimal('0')}]
        for balance, expected_balance in zip(balances.get(Currencies.ton), expected_balances):
            assert balance == expected_balance

    def test_get_tx_details(self):
        tx_details_mock_responses = [
            {
                "data": {'raw_transactions': [{'seqno': 33946132.0, 'action_ph_result_code': 0.0, 'aborted': 0,
                                           'in_msg_src_addr_address_hex': '57EB74407604A19F7E04005315EF70AEB7B675E6551977586756F6BAF12125EE',
                                           'in_msg_dest_addr_address_hex': '5F00DECB7DA51881764DC3959CEC60609045F6CA1B89E646BDE49D492705D77F',
                                           'hash': 'B5D393A190CA21E4F3CD2B9AF50FEA9C1336D67C7693669CB5635F0920BB4580',
                                           'in_msg_value_grams': '29999980000000', 'gen_utime': '2023-03-26T11:19:03',
                                           'in_msg_comment': '6044311', 'out_msg_value_grams': [],
                                           'out_msg_dest_addr_address_hex': []}]}
            },
        ]
        self.api.request = Mock(side_effect=tx_details_mock_responses)
        TonExplorerInterface.tx_details_apis[0] = self.api
        txs_details = BlockchainExplorer.get_transactions_details(self.txs_hash, 'TON')
        expected_txs_details = [
            {'success': True, 'block': 33946132,
             'date': datetime.datetime(2023, 3, 26, 11, 19, 3, tzinfo=datetime.timezone.utc),
             'raw': None,
             'inputs': [], 'outputs': [], 'transfers': [
                {'type': 'MainCoin', 'symbol': 'TON', 'currency': 145,
                 'to': 'EQBfAN7LfaUYgXZNw5Wc7GBgkEX2yhuJ5ka95J1JJwXXf4a8', 'value': Decimal('29999.980000000'),
                 'is_valid': True, 'token': None, 'memo': '6044311',
                 'from': 'EQBX63RAdgShn34EAFMV73Cut7Z15lUZd1hnVva68SEl7sxi'}], 'fees': None, 'memo': '6044311',
             'confirmations': 780548, 'hash': 'tdOToZDKIeTzzSua9Q/qnBM21nx2k2actWNfCSC7RYA='}
        ]
        for expected_tx_detail, tx_hash in zip(expected_txs_details, self.txs_hash):
            if txs_details[tx_hash].get('success'):
                txs_details[tx_hash]['confirmations'] = expected_tx_detail.get('confirmations')
            assert txs_details.get(tx_hash) == expected_tx_detail

    @pytest.mark.slow
    def test_get_address_txs(self):
        address_txs_mock_responses = [
            {
                "data": {
                    "raw_transactions": [
                        {'seqno': 35801194.0, 'action_ph_result_code': 0.0, 'aborted': 0,
                         'in_msg_src_addr_address_hex': None,
                         'in_msg_dest_addr_address_hex': '80D4123841167CA989AC912443CC99A4B9C1A87584536427FF6FD85C92395AE9',
                         'hash': '863EE0E2A3C649870379D5B8A994448265282F76EB27511731DF5FE8FF156263',
                         'in_msg_value_grams': None, 'gen_utime': '2023-06-06T10:39:30', 'in_msg_comment': None,
                         'out_msg_value_grams': [124471286402.0], 'out_msg_dest_addr_address_hex': [
                            'B37E57033DB21D10B950E6143B658C10C3BF425BD193025960AEF7F22DBCF4FC']},
                        {'seqno': 35801169.0, 'action_ph_result_code': 0.0, 'aborted': 0,
                         'in_msg_src_addr_address_hex': '8C6F0B82E2506BEB26F12C1036BB53C8BEE922143F3FEAC4FCE70F12F06FA508',
                         'in_msg_dest_addr_address_hex': '80D4123841167CA989AC912443CC99A4B9C1A87584536427FF6FD85C92395AE9',
                         'hash': '70B8B2533DF4CA3148DA74E7A47D48393A1DF1B94B5B980DD6B147083D86C57C',
                         'in_msg_value_grams': '124481286402', 'gen_utime': '2023-06-06T10:38:12',
                         'in_msg_comment': '1883184915', 'out_msg_value_grams': [],
                         'out_msg_dest_addr_address_hex': []},
                        {'seqno': 35801165.0, 'action_ph_result_code': 0.0, 'aborted': 0,
                         'in_msg_src_addr_address_hex': None,
                         'in_msg_dest_addr_address_hex': '80D4123841167CA989AC912443CC99A4B9C1A87584536427FF6FD85C92395AE9',
                         'hash': '9A9B0F78B9F339AB407C7704CFF98824D54FB4E6DEA042A938C248B9D367C7E6',
                         'in_msg_value_grams': None, 'gen_utime': '2023-06-06T10:37:59', 'in_msg_comment': None,
                         'out_msg_value_grams': [6607019400.0], 'out_msg_dest_addr_address_hex': [
                            'B37E57033DB21D10B950E6143B658C10C3BF425BD193025960AEF7F22DBCF4FC']},
                        {'seqno': 35801136.0, 'action_ph_result_code': 0.0, 'aborted': 0,
                         'in_msg_src_addr_address_hex': '85AF78E8D035E920117CDA654615CDF371D464480B629E110D3C5310D85AB362',
                         'in_msg_dest_addr_address_hex': '80D4123841167CA989AC912443CC99A4B9C1A87584536427FF6FD85C92395AE9',
                         'hash': 'DD1937980AD44810942597A20F210BFE9D365DC55353B0C2C6890A5008FA31C9',
                         'in_msg_value_grams': '6617019400', 'gen_utime': '2023-06-06T10:36:16',
                         'in_msg_comment': '1869422685', 'out_msg_value_grams': [],
                         'out_msg_dest_addr_address_hex': []},
                        {'seqno': 35800852.0, 'action_ph_result_code': 0.0, 'aborted': 0,
                         'in_msg_src_addr_address_hex': None,
                         'in_msg_dest_addr_address_hex': '80D4123841167CA989AC912443CC99A4B9C1A87584536427FF6FD85C92395AE9',
                         'hash': '6B533227B2C4925FDDC24AEB4E85314F989783D37D992AB43E62D2F12443598F',
                         'in_msg_value_grams': None, 'gen_utime': '2023-06-06T10:20:57', 'in_msg_comment': None,
                         'out_msg_value_grams': [75968867300.0], 'out_msg_dest_addr_address_hex': [
                            'B37E57033DB21D10B950E6143B658C10C3BF425BD193025960AEF7F22DBCF4FC']}
                    ]
                }
            }
        ]
        self.api.request = Mock(side_effect=address_txs_mock_responses)
        TonExplorerInterface.address_txs_apis[0] = self.api
        expected_addresses_txs = [
            [
                {
                    'address': 'EQCA1BI4QRZ8qYmskSRDzJmkucGodYRTZCf_b9hckjla6dZl',
                    'block': 35801169,
                    'confirmations': 31,
                    'details': {},
                    'from_address': ['EQCMbwuC4lBr6ybxLBA2u1PIvukiFD8_6sT85w8S8G-lCCmD'],
                    'hash': 'cLiyUz30yjFI2nTnpH1IOTod8blLW5gN1rFHCD2GxXw=',
                    'huge': False,
                    'invoice': None,
                    'is_double_spend': False,
                    'tag': '1883184915',
                    'timestamp': datetime.datetime(2023, 6, 6, 10, 38, 12, tzinfo=pytz.utc),
                    'value': Decimal('124.481286402'),
                    'contract_address': None
                },
                {
                    'address': 'EQCA1BI4QRZ8qYmskSRDzJmkucGodYRTZCf_b9hckjla6dZl',
                    'block': 35801136,
                    'confirmations': 64,
                    'details': {},
                    'from_address': ['EQCFr3jo0DXpIBF82mVGFc3zcdRkSAtinhENPFMQ2FqzYqDB'],
                    'hash': '3Rk3mArUSBCUJZeiDyEL/p02XcVTU7DCxokKUAj6Mck=',
                    'huge': False,
                    'invoice': None,
                    'is_double_spend': False,
                    'tag': '1869422685',
                    'timestamp': datetime.datetime(2023, 6, 6, 10, 36, 16, tzinfo=pytz.utc),
                    'value': Decimal('6.617019400'),
                    'contract_address': None
                }
            ]
        ]
        for address, expected_address_txs in zip(self.addresses, expected_addresses_txs):
            address_txs = BlockchainExplorer.get_wallet_transactions(address, Currencies.ton, 'TON', raise_error=True)
            assert len(expected_address_txs) == len(address_txs.get(Currencies.ton))
            for expected_address_tx, address_tx in zip(expected_address_txs, address_txs.get(Currencies.ton)):
                assert address_tx.confirmations >= expected_address_tx.get('confirmations')
                address_tx.confirmations = expected_address_tx.get('confirmations')
                assert address_tx.__dict__ == expected_address_tx

    # def test_get_block_txs(self):
    #     block_txs_mock_responses = [
    #         {
    #             "data": {
    #                 "blocks": [
    #                     {
    #                         "seqno": 33946132.0
    #                     }
    #                 ]
    #             }
    #         },
    #         {
    #             "data": {
    #                 "transactions": [
    #                     {
    #                         "seqno": 33946135.0,
    #                         "action_ph_result_code": 0.0,
    #                         "outmsg_cnt": 1,
    #                         "aborted": 0,
    #                         "in_msg_src_addr_address_hex": None,
    #                         "in_msg_dest_addr_address_hex": "F2F4BB2332259D0BF4B6568773B33B55B5EA15E38E03096D1FB476A558962B90",
    #                         "hash": "C413B2433AAAFC1056C2396F163C310A53FC5F12975839A596DBB7C8D03E48B9",
    #                         "in_msg_value_grams": None,
    #                         "gen_utime": "2023-03-26T11:19:21"
    #                     },
    #                     {
    #                         "seqno": 33946135.0,
    #                         "action_ph_result_code": None,
    #                         "outmsg_cnt": 0,
    #                         "aborted": 1,
    #                         "in_msg_src_addr_address_hex": "F2F4BB2332259D0BF4B6568773B33B55B5EA15E38E03096D1FB476A558962B90",
    #                         "in_msg_dest_addr_address_hex": "85F4908CE86A09967690190BDC9954E8493AFC8FD23A15C41676ECA4DDCF904A",
    #                         "hash": "C2CB1F5A49E35313EF8AA53E366F6BCD915A2CB6290803625290CEE5FFE6AEDB",
    #                         "in_msg_value_grams": "992000000",
    #                         "gen_utime": "2023-03-26T11:19:21"
    #                     },
    #                     {
    #                         "seqno": 33946135.0,
    #                         "action_ph_result_code": 0.0,
    #                         "outmsg_cnt": 0,
    #                         "aborted": 0,
    #                         "in_msg_src_addr_address_hex": "4FD5A23C94ABACE03A672C4652E0068F8C0CE6F276F8FEF2C405910D1B2809D8",
    #                         "in_msg_dest_addr_address_hex": "57BB42996CE6EBD50178CF6C0A3273B40B0E10744E48D32662AD00122A8FB86D",
    #                         "hash": "35E908C6A72D1FE31B7F0C307E0FA0CD12602071AC7CBAC84CBBEF5AAE2CB9EE",
    #                         "in_msg_value_grams": "2000000000",
    #                         "gen_utime": "2023-03-26T11:19:21"
    #                     },
    #                     {
    #                         "seqno": 33946135.0,
    #                         "action_ph_result_code": 0.0,
    #                         "outmsg_cnt": 1,
    #                         "aborted": 0,
    #                         "in_msg_src_addr_address_hex": "3027154D0EB81CD04388DE96E01EDF25FC266121609C97C27AAAAEDC15B5E5DD",
    #                         "in_msg_dest_addr_address_hex": "4FD5A23C94ABACE03A672C4652E0068F8C0CE6F276F8FEF2C405910D1B2809D8",
    #                         "hash": "F4275A52BD5DF9A9876CCC90A13A1A3FB2340AFF20F5B217D7C0519823DA99B6",
    #                         "in_msg_value_grams": "3000000000",
    #                         "gen_utime": "2023-03-26T11:19:21"
    #                     },
    #                     {
    #                         "seqno": 33946135.0,
    #                         "action_ph_result_code": 0.0,
    #                         "outmsg_cnt": 1,
    #                         "aborted": 0,
    #                         "in_msg_src_addr_address_hex": None,
    #                         "in_msg_dest_addr_address_hex": "3027154D0EB81CD04388DE96E01EDF25FC266121609C97C27AAAAEDC15B5E5DD",
    #                         "hash": "FCE5A1AB00249A43433F8403800D0E07ECE93DF1575ACC31F0E25A5D709AAD53",
    #                         "in_msg_value_grams": None,
    #                         "gen_utime": "2023-03-26T11:19:21"
    #                     }
    #                 ]
    #             }
    #         }
    #     ]
    #     self.api.request = Mock(side_effect=block_txs_mock_responses)
    #     settings.USE_TESTNET_BLOCKCHAINS = False
    #     TonExplorerInterface.block_txs_apis[0] = self.api
    #     expected_txs_addresses = {
    #         'input_addresses': {'EQBP1aI8lKus4DpnLEZS4AaPjAzm8nb4_vLEBZENGygJ2EwB'},
    #         'output_addresses': {'EQBXu0KZbObr1QF4z2wKMnO0Cw4QdE5I0yZirQASKo-4bXQD'},
    #     }
    #     expected_txs_info = {
    #         'outgoing_txs': {
    #             'EQBP1aI8lKus4DpnLEZS4AaPjAzm8nb4_vLEBZENGygJ2EwB': {
    #                 Currencies.ton: [
    #                     {'tx_hash': 'NekIxqctH+Mbfwwwfg+gzRJgIHGsfLrITLvvWq4sue4=', 'value': Decimal('2.000000000')}]}
    #         },
    #         'incoming_txs': {
    #             'EQBXu0KZbObr1QF4z2wKMnO0Cw4QdE5I0yZirQASKo-4bXQD': {
    #                 Currencies.ton: [
    #                     {'tx_hash': 'NekIxqctH+Mbfwwwfg+gzRJgIHGsfLrITLvvWq4sue4=', 'value': Decimal('2.000000000')}]}
    #         }
    #     }
    #
    #     txs_addresses, txs_info, _ = BlockchainExplorer.get_latest_block_addresses('TON', True, True)
    #     assert expected_txs_info == txs_info
    #     assert expected_txs_addresses == txs_addresses
