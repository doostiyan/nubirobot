import pytest
import datetime
from decimal import Decimal
from unittest import TestCase
from exchange.base.models import Currencies
from exchange.blockchain.api.xlm.blockchair_new import StellarBlockchairAPI
from exchange.blockchain.api.xlm.xlm_explorer_interface import StellarExplorerInterface
from exchange.blockchain.apis_conf import APIS_CONF
from exchange.blockchain.tests.api.general_test.general_test_from_explorer import TestFromExplorer


class TestBlockchairStellarApiCalls(TestCase):
    api = StellarBlockchairAPI
    txs_hash = ['8f8e29a55f80fc7d34722ec5a75843a8e53de233cb44292d2990595884e610be']

    @pytest.mark.slow
    def test_get_block_head_api(self):
        get_block_head_result = self.api.get_block_head()
        assert isinstance(get_block_head_result, dict)
        assert isinstance(get_block_head_result.get('data'), dict)
        assert isinstance(get_block_head_result.get('data').get('ledgers'), int)
        assert isinstance(get_block_head_result.get('data').get('best_ledger_height'), int)

    @pytest.mark.slow
    def test_get_tx_details_api(self):
        for tx_hash in self.txs_hash:
            get_tx_details_result = self.api.get_tx_details(tx_hash)
            assert isinstance(get_tx_details_result, dict)
            assert isinstance(get_tx_details_result.get('data'), dict)
            assert isinstance(get_tx_details_result.get('data').get(tx_hash), dict)
            assert isinstance(get_tx_details_result.get('data').get(tx_hash).get('transaction'), dict)
            key2check_transaction = [('memo', str), ('id', str), ('successful', bool), ('hash', str), ('ledger', int),
                                     ('created_at', str), ('source_account', str), ('max_fee', str)]
            for key, value in key2check_transaction:
                assert (get_tx_details_result.get('data').get(tx_hash).get('transaction').get(key), value)
            assert isinstance(get_tx_details_result.get('data').get(tx_hash).get('operations'), list)
            key2check_operation = [('id', str), ('transaction_account', bool), ('source_account', str),
                                   ('type', str), ('type_i', int), ('created_at', str), ('transaction_hash', str),
                                   ('asset_type', str), ('from', str), ('to', str), ('amount', str)]
            for operation in get_tx_details_result.get('data').get(tx_hash).get('operations'):
                for key, value in key2check_operation:
                    assert (operation.get(key), value)


class TestStellarBlockchairFromExplorer(TestFromExplorer):
    api = StellarBlockchairAPI
    txs_hash = ['8f8e29a55f80fc7d34722ec5a75843a8e53de233cb44292d2990595884e610be']
    explorerInterface = StellarExplorerInterface
    currencies = Currencies.xlm
    symbol = 'XLM'

    @classmethod
    def test_get_tx_details(cls):
        APIS_CONF[cls.symbol]['txs_details'] = 'xlm_interface_explorer'
        tx_details_mock_responses = [
            {
                'data': {'ledgers': 52507516, 'best_ledger_height': 52507516,
                         'best_ledger_hash': 'ede42a48f16cb70259890b7daefa7ecfc5f75a78ec2f1b7d9a209f91e076a344',
                         'best_ledger_time': '2024-07-10 10:43:55', 'circulation': 1054439020873472865,
                         'ledgers_24h': 15019, 'transactions_24h': 3470529, 'successful_transactions_24h': 1603280,
                         'failed_transactions_24h': 1867249, 'operations_24h': 7100951,
                         'average_transaction_fee_24h': 772.5455264893383,
                         'average_transaction_fee_usd_24h': 6.830074999692239e-06, 'market_price_usd': 0.08841,
                         'market_price_btc': 1.5075196944378e-06, 'market_price_usd_change_24h_percentage': 0.69788,
                         'market_cap_usd': 2580736583, 'market_dominance_percentage': 0.11},
                'context': {
                    'code': 200, 'source': 'D', 'state': 52507516, 'market_price_usd': 0.08841,
                    'cache': {'live': False, 'duration': 120, 'since': '2024-07-10 10:44:05',
                              'until': '2024-07-10 10:46:05', 'time': 2.86102294921875e-06},
                    'api': {'version': '2.0.95-ie', 'last_major_update': '2022-11-07 02:00:00',
                            'next_major_update': '2023-11-12 02:00:00',
                            'documentation': 'https://blockchair.com/api/docs',
                            'notice': 'Try out our new API v.3: https://3xpl.com/data'}, 'servers': 'API4',
                    'time': 5.412101745605469e-05, 'render_time': 0.0015590190887451172,
                    'full_time': 0.001561880111694336, 'request_cost': 1}},
            {
                'data': {'8f8e29a55f80fc7d34722ec5a75843a8e53de233cb44292d2990595884e610be': {
                    'transaction': {'memo': '128464', 'memo_bytes': 'MTI4NDY0',
                                    'id': '8f8e29a55f80fc7d34722ec5a75843a8e53de233cb44292d2990595884e610be',
                                    'paging_token': '225514593681633280', 'successful': True,
                                    'hash': '8f8e29a55f80fc7d34722ec5a75843a8e53de233cb44292d2990595884e610be',
                                    'ledger': 52506708, 'created_at': '2024-07-10T09:26:17Z',
                                    'source_account': 'GDHF3HIKWM5KJAVLZBSZWUFDOEOT7IBMY22UXG4QBE326O354INLPAND',
                                    'source_account_sequence': '166409929518317083',
                                    'fee_account': 'GDHF3HIKWM5KJAVLZBSZWUFDOEOT7IBMY22UXG4QBE326O354INLPAND',
                                    'fee_charged': '100', 'max_fee': '1000000', 'operation_count': 1,
                                    'envelope_xdr': 'AAAAAgAAAADOXZ0KszqkgqvIZZtQo3EdP6AsxrVLm5AJN687feIatwAPQkACTzTzAAl+GwAAAAEAAAAAAAAAAAAAAABmjlQMAAAAAQAAAAYxMjg0NjQAAAAAAAEAAAAAAAAAAQAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAAAAAAAAAAYlXzQAAAAAAAAAABfeIatwAAAEC9mhanGrQM6kPvE5sQ23yeLiO0dK+SYET8PhT1VnHlOh2IQ9VxaZ7Ef59cJA7eUqWxmlb/NaRAXV+lpLzUeI0C',
                                    'result_xdr': 'AAAAAAAAAGQAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAA=',
                                    'result_meta_xdr': 'AAAAAwAAAAAAAAACAAAAAwMhMFQAAAAAAAAAAM5dnQqzOqSCq8hlm1CjcR0/oCzGtUubkAk3rzt94hq3AABITYAnVzQCTzTzAAl+GgAAAAIAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAMAAAAAAyEwMQAAAABmjlLsAAAAAAAAAAEDITBUAAAAAAAAAADOXZ0KszqkgqvIZZtQo3EdP6AsxrVLm5AJN687feIatwAASE2AJ1c0Ak808wAJfhsAAAACAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMhMFQAAAAAZo5TuQAAAAAAAAABAAAABAAAAAMDITBUAAAAAAAAAADOXZ0KszqkgqvIZZtQo3EdP6AsxrVLm5AJN687feIatwAASE2AJ1c0Ak808wAJfhsAAAACAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMhMFQAAAAAZo5TuQAAAAAAAAABAyEwVAAAAAAAAAAAzl2dCrM6pIKryGWbUKNxHT+gLMa1S5uQCTevO33iGrcAAEhNHdFj9AJPNPMACX4bAAAAAgAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAwAAAAADITBUAAAAAGaOU7kAAAAAAAAAAwMhL9EAAAAAAAAAANJdnWDu5Lzz4a+ZqJ3dIG0+ciDA3gcjxGoGjhecW4aZAAAGcc5V570CA8q8AAPsHwAAAAMAAAAAAAAAAAAAAAliaXRnby5jb20AAAAAAQIDAAAAAwAAAAAdSLNvNcCEWpUM1sSHHJ9W/JqMWbz1rhA/Sl1QO+4C9AAAAAEAAAAAl5Ai6URIK1qSERKZFtKcPXz/BINreqBQEc2793l1m6cAAAABAAAAAK2xJjeRTZSyAkiROb5tk6y8FeWa/G6LumaboZvAanpFAAAAAQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAwAAAAAAAAAAAAAAAAAAAAMAAAAAAyEv0QAAAABmjlDIAAAAAAAAAAEDITBUAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABnIwq9r9AgPKvAAD7B8AAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMhL9EAAAAAZo5QyAAAAAAAAAAAAAAAAA==',
                                    'fee_meta_xdr': 'AAAAAgAAAAMDITAxAAAAAAAAAADOXZ0KszqkgqvIZZtQo3EdP6AsxrVLm5AJN687feIatwAASE2AJ1eYAk808wAJfhoAAAACAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMhMDEAAAAAZo5S7AAAAAAAAAABAyEwVAAAAAAAAAAAzl2dCrM6pIKryGWbUKNxHT+gLMa1S5uQCTevO33iGrcAAEhNgCdXNAJPNPMACX4aAAAAAgAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAwAAAAADITAxAAAAAGaOUuwAAAAA',
                                    'memo_type': 'text', 'signatures': [
                            'vZoWpxq0DOpD7xObENt8ni4jtHSvkmBE/D4U9VZx5TodiEPVcWmexH+fXCQO3lKlsZpW/zWkQF1fpaS81HiNAg=='],
                                    'valid_after': '1970-01-01T00:00:00Z', 'valid_before': '2024-07-10T09:27:40Z',
                                    'preconditions': {'timebounds': {'min_time': '0', 'max_time': '1720603660'}}},
                    'operations': [
                        {'id': '225514593681633281', 'paging_token': '225514593681633281',
                         'transaction_successful': True,
                         'source_account': 'GDHF3HIKWM5KJAVLZBSZWUFDOEOT7IBMY22UXG4QBE326O354INLPAND',
                         'type': 'payment',
                         'type_i': 1, 'created_at': '2024-07-10T09:26:17Z',
                         'transaction_hash': '8f8e29a55f80fc7d34722ec5a75843a8e53de233cb44292d2990595884e610be',
                         'asset_type': 'native', 'from': 'GDHF3HIKWM5KJAVLZBSZWUFDOEOT7IBMY22UXG4QBE326O354INLPAND',
                         'to': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5', 'amount': '164.9800000'}],
                    'effects': None}},
                'context': {'code': 200, 'source': 'D', 'results': 1, 'state': 52507527, 'market_price_usd': 0.08841,
                            'cache': {'live': True, 'duration': 120, 'since': '2024-07-10 10:45:15',
                                      'until': '2024-07-10 10:47:15', 'time': None},
                            'api': {'version': '2.0.95-ie', 'last_major_update': '2022-11-07 02:00:00',
                                    'next_major_update': '2023-11-12 02:00:00',
                                    'documentation': 'https://blockchair.com/api/docs',
                                    'notice': 'Try out our new API v.3: https://3xpl.com/data'},
                            'servers': 'API4,XLM1,XLM1', 'time': 0.33130407333374023,
                            'render_time': 0.004987001419067383,
                            'full_time': 0.3362910747528076, 'request_cost': 2}}
        ]
        expected_txs_details = [
            {
                'hash': '8f8e29a55f80fc7d34722ec5a75843a8e53de233cb44292d2990595884e610be',
                'success': True,
                'inputs': [],
                'outputs': [],
                'transfers': [{'type': 'MainCoin',
                               'symbol': 'XLM',
                               'is_valid': True,
                               'from': 'GDHF3HIKWM5KJAVLZBSZWUFDOEOT7IBMY22UXG4QBE326O354INLPAND',
                               'to': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                               'currency': 19,
                               'token': None,
                               'memo': '128464',
                               'value': Decimal('164.9800000')}],
                'memo': '128464',
                'block': 52506708,
                'fees': Decimal('0.1000000'),
                'date': datetime.datetime(2024, 7, 10, 9, 26, 17, tzinfo=datetime.timezone.utc),
                'confirmations': 808,
                'raw': None,
            }
        ]
        cls.get_tx_details(tx_details_mock_responses, expected_txs_details)

        cls.txs_hash = ['f716c17ce95990f6c1815473d276e418ce53c22d0a2487e3f02f37f84b230321']
        tx_details_mock_responses2 = [
            {
                'data': {'ledgers': 40452109, 'best_ledger_height': 40452109,
                         'best_ledger_hash': '05077cbbaa9bef5ad5a383805b1c833bd8e8d7dfdf748377fb430bca8e69a1cd',
                         'best_ledger_time': '2022-04-13 14:02:53', 'circulation': 1054439020873472865,
                         'ledgers_24h': 13361, 'transactions_24h': 6250775,
                         'successful_transactions_24h': 3351213, 'failed_transactions_24h': 2899562,
                         'operations_24h': 9609545, 'average_transaction_fee_24h': 478.20047355958957,
                         'average_transaction_fee_usd_24h': 9.367038696132597e-06,
                         'market_price_usd': 0.195881, 'market_price_btc': 4.8432647611512e-06,
                         'market_price_usd_change_24h_percentage': 1.45422,
                         'market_cap_usd': 4851059267, 'market_dominance_percentage': 0.25},
                'context': {'code': 200, 'source': 'D', 'state': 40452109,
                            'cache': {'live': False, 'duration': 120, 'since': '2022-04-13 14:02:59',
                                      'until': '2022-04-13 14:04:59', 'time': 2.1457672119140625e-06},
                            'api': {'version': '2.0.95-ie', 'last_major_update': '2021-07-19 00:00:00',
                                    'next_major_update': None,
                                    'documentation': 'https://blockchair.com/api/docs', 'notice': ':)'},
                            'servers': 'API4', 'time': 5.3882598876953125e-05,
                            'render_time': 0.0015439987182617188, 'full_time': 0.0015461444854736328,
                            'request_cost': 1}},
            {'data':
                {'f716c17ce95990f6c1815473d276e418ce53c22d0a2487e3f02f37f84b230321': {
                    'transaction': {'id': 'f716c17ce95990f6c1815473d276e418ce53c22d0a2487e3f02f37f84b230321',
                                    'paging_token': '173735215286382592', 'successful': True,
                                    'hash': 'f716c17ce95990f6c1815473d276e418ce53c22d0a2487e3f02f37f84b230321',
                                    'ledger': 40450882, 'created_at': '2022-04-13T11:57:15Z',
                                    'source_account': 'GCAD67WM4IFVEEJ2Q3IPHUFKVORXLD7MOHUBLYNSCU3ERKOJQD52YZ7J',
                                    'source_account_sequence': '150630799492802931',
                                    'fee_account': 'GCAD67WM4IFVEEJ2Q3IPHUFKVORXLD7MOHUBLYNSCU3ERKOJQD52YZ7J',
                                    'fee_charged': '1000', 'max_fee': '100000', 'operation_count': 1,
                                    'envelope_xdr': 'AAAAAgAAAACAP37M4gtSETqG0PPQqqujdY/scegV4bIVNkipyYD7rAABhqACFyXqAABpcwAAAAAAAAAAAAAAAQAAAAEAAAAAgD9+zOILUhE6htDz0Kqro3WP7HHoFeGyFTZIqcmA+6wAAAABAAAAAIjx6n+V/gdpfLb3JHfGim1FkANHgQAhAzhB/ME8O8MNAAAAAkJOREVTAAAAAAAAAAAAAAAsbbXwvAicQxuVwOR7Vusm6JauNhbrDuQ70gN7T3qFzwAAATwKUjeoAAAAAAAAAAHJgPusAAAAQHAOIZArkEKx7ztB0NkvjQM9gOQEO88TUPxBMZdMyJ4wvIwVMXKyVn/31xwqLySN6KJSoUTc5FrEHQPQxhxniQU=',
                                    'result_xdr': 'AAAAAAAAA+gAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAA=',
                                    'result_meta_xdr': 'AAAAAgAAAAIAAAADAmk7QgAAAAAAAAAAgD9+zOILUhE6htDz0Kqro3WP7HHoFeGyFTZIqcmA+6wAAAAfwrHoWgIXJeoAAGlyAAAD1AAAAAEAAAAAxHHGQ3BiyVBqiTQuU4oa2kBNL0HPHTolX0Mh98bg4XUAAAAAAAAACWxvYnN0ci5jbwAAAAEAAAAAAAAAAAAAAQAAABFOLT7wAAAAHVjuZX8AAAAAAAAAAAAAAAECaTtCAAAAAAAAAACAP37M4gtSETqG0PPQqqujdY/scegV4bIVNkipyYD7rAAAAB/CsehaAhcl6gAAaXMAAAPUAAAAAQAAAADEccZDcGLJUGqJNC5TihraQE0vQc8dOiVfQyH3xuDhdQAAAAAAAAAJbG9ic3RyLmNvAAAAAQAAAAAAAAAAAAABAAAAEU4tPvAAAAAdWO5lfwAAAAAAAAAAAAAAAQAAAAQAAAADAmdhTwAAAAEAAAAAgD9+zOILUhE6htDz0Kqro3WP7HHoFeGyFTZIqcmA+6wAAAACQk5ERVMAAAAAAAAAAAAAACxttfC8CJxDG5XA5HtW6ybolq42FusO5DvSA3tPeoXPAAABPApSN6h//////////wAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQJpO0IAAAABAAAAAIA/fsziC1IROobQ89Cqq6N1j+xx6BXhshU2SKnJgPusAAAAAkJOREVTAAAAAAAAAAAAAAAsbbXwvAicQxuVwOR7Vusm6JauNhbrDuQ70gN7T3qFzwAAAAAAAAAAf/////////8AAAABAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMCaTseAAAAAQAAAACI8ep/lf4HaXy29yR3xoptRZADR4EAIQM4QfzBPDvDDQAAAAJCTkRFUwAAAAAAAAAAAAAALG218LwInEMblcDke1brJuiWrjYW6w7kO9IDe096hc8AAAAAAAAAAH//////////AAAAAQAAAAAAAAAAAAAAAQJpO0IAAAABAAAAAIjx6n+V/gdpfLb3JHfGim1FkANHgQAhAzhB/ME8O8MNAAAAAkJOREVTAAAAAAAAAAAAAAAsbbXwvAicQxuVwOR7Vusm6JauNhbrDuQ70gN7T3qFzwAAATwKUjeof/////////8AAAABAAAAAAAAAAAAAAAA',
                                    'fee_meta_xdr': 'AAAAAgAAAAMCaTs0AAAAAAAAAACAP37M4gtSETqG0PPQqqujdY/scegV4bIVNkipyYD7rAAAAB/CsexCAhcl6gAAaXIAAAPUAAAAAQAAAADEccZDcGLJUGqJNC5TihraQE0vQc8dOiVfQyH3xuDhdQAAAAAAAAAJbG9ic3RyLmNvAAAAAQAAAAAAAAAAAAABAAAAEU4tPvAAAAAdWO5lfwAAAAAAAAAAAAAAAQJpO0IAAAAAAAAAAIA/fsziC1IROobQ89Cqq6N1j+xx6BXhshU2SKnJgPusAAAAH8Kx6FoCFyXqAABpcgAAA9QAAAABAAAAAMRxxkNwYslQaok0LlOKGtpATS9Bzx06JV9DIffG4OF1AAAAAAAAAAlsb2JzdHIuY28AAAABAAAAAAAAAAAAAAEAAAARTi0+8AAAAB1Y7mV/AAAAAAAAAAA=',
                                    'memo_type': 'none', 'signatures': [
                            'cA4hkCuQQrHvO0HQ2S+NAz2A5AQ7zxNQ/EExl0zInjC8jBUxcrJWf/fXHCovJI3oolKhRNzkWsQdA9DGHGeJBQ==']},
                    'operations': [
                        {'id': '173735215286382593', 'paging_token': '173735215286382593',
                         'transaction_successful': True,
                         'source_account': 'GCAD67WM4IFVEEJ2Q3IPHUFKVORXLD7MOHUBLYNSCU3ERKOJQD52YZ7J',
                         'type': 'payment',
                         'type_i': 1, 'created_at': '2022-04-13T11:57:15Z',
                         'transaction_hash': 'f716c17ce95990f6c1815473d276e418ce53c22d0a2487e3f02f37f84b230321',
                         'asset_type': 'credit_alphanum12', 'asset_code': 'BNDES',
                         'asset_issuer': 'GAWG3NPQXQEJYQY3SXAOI62W5MTORFVOGYLOWDXEHPJAG62PPKC47DGB',
                         'from': 'GCAD67WM4IFVEEJ2Q3IPHUFKVORXLD7MOHUBLYNSCU3ERKOJQD52YZ7J',
                         'to': 'GCEPD2T7SX7AO2L4W33SI56GRJWULEADI6AQAIIDHBA7ZQJ4HPBQ2JZF', 'amount': '135738.2825896'}],
                    'effects': None}}, 'context': {'code': 200, 'source': 'D', 'results': 1, 'state': 40452123,
                                                   'market_price_usd': 0.195881,
                                                   'cache': {'live': True, 'duration': 120,
                                                             'since': '2022-04-13 14:04:29',
                                                             'until': '2022-04-13 14:06:29', 'time': None},
                                                   'api': {'version': '2.0.95-ie',
                                                           'last_major_update': '2021-07-19 00:00:00',
                                                           'next_major_update': None,
                                                           'documentation': 'https://blockchair.com/api/docs',
                                                           'notice': ':)'},
                                                   'servers': 'API4,XLM4,XLM4', 'time': 0.7469789981842041,
                                                   'render_time': 0.003933906555175781, 'full_time': 0.7509129047393799,
                                                   'request_cost': 2}}
        ]
        expected_txs_details2 = [{'success': False}]
        cls.get_tx_details(tx_details_mock_responses2, expected_txs_details2)

        cls.txs_hash = ['950b76ace2416b09564943c058e243d5d05aaad4cf19595a6170024791fe2f58']
        tx_details_mock_responses3 = [
            {
                'data': {'ledgers': 40451498, 'best_ledger_height': 40451498,
                         'best_ledger_hash': '9ef82bf5b2916ecf786082e4779247df663a0cdbe08b71c66c4a7da47f9c961d',
                         'best_ledger_time': '2022-04-13 13:00:15', 'circulation': 1054439020873472865,
                         'ledgers_24h': 13345, 'transactions_24h': 6297083,
                         'successful_transactions_24h': 3348890, 'failed_transactions_24h': 2948193,
                         'operations_24h': 9537361, 'average_transaction_fee_24h': 2341.41606663843,
                         'average_transaction_fee_usd_24h': 4.539279914231259e-05,
                         'market_price_usd': 0.193869, 'market_price_btc': 4.8641142082947e-06,
                         'market_price_usd_change_24h_percentage': -0.07729,
                         'market_cap_usd': 4799628528, 'market_dominance_percentage': 0.25},
                'context': {'code': 200, 'source': 'D', 'state': 40451498, 'market_price_usd': 0.193869,
                            'cache': {'live': True, 'duration': 120, 'since': '2022-04-13 13:00:22',
                                      'until': '2022-04-13 13:02:22', 'time': 2.1457672119140625e-06},
                            'api': {'version': '2.0.95-ie', 'last_major_update': '2021-07-19 00:00:00',
                                    'next_major_update': None,
                                    'documentation': 'https://blockchair.com/api/docs', 'notice': ':)'},
                            'servers': 'API4', 'time': 0.00012302398681640625,
                            'render_time': 0.0012459754943847656, 'full_time': 0.0012481212615966797,
                            'request_cost': 1}},
            {
                'data': {'950b76ace2416b09564943c058e243d5d05aaad4cf19595a6170024791fe2f58': {
                    'transaction': {'memo': '0.0004661', 'memo_bytes': 'MC4wMDA0NjYx',
                                    'id': '950b76ace2416b09564943c058e243d5d05aaad4cf19595a6170024791fe2f58',
                                    'paging_token': '173735292595871744', 'successful': True,
                                    'hash': '950b76ace2416b09564943c058e243d5d05aaad4cf19595a6170024791fe2f58',
                                    'ledger': 40450900, 'created_at': '2022-04-13T11:59:11Z',
                                    'source_account': 'GAOB3HQAJ62OMQKZVJWY5HSO2X5JSLFPLH2UUXBTYLE3YUBOD4KKE4LH',
                                    'source_account_sequence': '171467798969590981',
                                    'fee_account': 'GAOB3HQAJ62OMQKZVJWY5HSO2X5JSLFPLH2UUXBTYLE3YUBOD4KKE4LH',
                                    'fee_charged': '200', 'max_fee': '4100004', 'operation_count': 2,
                                    'envelope_xdr': 'AAAAAgAAAAAcHZ4AT7TmQVmqbY6eTtX6mSyvWfVKXDPCybxQLh8UogA+j6QCYS0OAAAkxQAAAAEAAAAAAAAAAAAAAABiVrskAAAAAQAAAAkwLjAwMDQ2NjEAAAAAAAACAAAAAQAAAAAGRuuAc6243f4wc2KuJTUgjpr69HCH5OJ/FXxc1GhwpQAAAAEAAAAAHB2eAE+05kFZqm2Onk7V+pksr1n1Slwzwsm8UC4fFKIAAAAAAAAAAAAAB9AAAAABAAAAAAZG64Bzrbjd/jBzYq4lNSCOmvr0cIfk4n8VfFzUaHClAAAADQAAAAAAAAAAAFlbAAAAAAAGRuuAc6243f4wc2KuJTUgjpr69HCH5OJ/FXxc1GhwpQAAAAAAAAAAAFlbAAAAAAIAAAACRE9HRVQAAAAAAAAAAAAAANxKjGGnnBspf6nGByh//R/BqPDCnKSmfXx3aIwzvvp6AAAAAVVTREMAAAAAO5kROA7+mIugqJAOsc/kTzZvfb6Ua+0HckD39iTfFcUAAAAAAAAAAi4fFKIAAABAcs79gJr1mNd0SqKbdp8gpyixbM1hl/YtSdE05OZ0LfJsAbTbb+sCZbNZCnuqEXf0lV7oUnR9KfFcZ8D0RsVfDNRocKUAAABA7Zs29aS1D03xOxr1eN6b0zqiGfRW4E662ClopaHE1XFX58C3dHq6eujx7/lvl/EMknFwoCXHxEiw5l7zmzsmAQ==',
                                    'result_xdr': 'AAAAAAAAAMgAAAAAAAAAAgAAAAAAAAABAAAAAAAAAAAAAAANAAAAAAAAAAMAAAABAAAAAJWM8z661Lq2hO7B29i3W+EY4JRTGapIbiDJPxkSKem/AAAAADnGUYYAAAACRE9HRVQAAAAAAAAAAAAAANxKjGGnnBspf6nGByh//R/BqPDCnKSmfXx3aIwzvvp6AAAAADmTiFsAAAAAAAAAAABZWwAAAAACGv1Cw4KlZnizyINPzFqMC5mXaj+Eil+skM/dVgCBZXMAAAABVVNEQwAAAAA7mRE4Dv6Yi6CokA6xz+RPNm99vpRr7QdyQPf2JN8VxQAAAAAAETfqAAAAAkRPR0VUAAAAAAAAAAAAAADcSoxhp5wbKX+pxgcof/0fwajwwpykpn18d2iMM776egAAAAA5k4hbAAAAAQAAAAByW/uudcHA3/AcxxN4oyupHyfxRZIKRGRMqMVTs6HOmgAAAAA5xlFbAAAAAAAAAAAAWYcHAAAAAVVTREMAAAAAO5kROA7+mIugqJAOsc/kTzZvfb6Ua+0HckD39iTfFcUAAAAAABE36gAAAAAGRuuAc6243f4wc2KuJTUgjpr69HCH5OJ/FXxc1GhwpQAAAAAAAAAAAFmHBwAAAAA=',
                                    'result_meta_xdr': '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',
                                    'fee_meta_xdr': 'AAAAAgAAAAMCaTtMAAAAAAAAAAAcHZ4AT7TmQVmqbY6eTtX6mSyvWfVKXDPCybxQLh8UogAAAAACdoLvAmEtDgAAJMQAAAACAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAECaTtUAAAAAAAAAAAcHZ4AT7TmQVmqbY6eTtX6mSyvWfVKXDPCybxQLh8UogAAAAACdoInAmEtDgAAJMQAAAACAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAA==',
                                    'memo_type': 'text', 'signatures': [
                            'cs79gJr1mNd0SqKbdp8gpyixbM1hl/YtSdE05OZ0LfJsAbTbb+sCZbNZCnuqEXf0lV7oUnR9KfFcZ8D0RsVfDA==',
                            '7Zs29aS1D03xOxr1eN6b0zqiGfRW4E662ClopaHE1XFX58C3dHq6eujx7/lvl/EMknFwoCXHxEiw5l7zmzsmAQ=='],
                                    'valid_after': '1970-01-01T00:00:00Z', 'valid_before': '2022-04-13T11:59:32Z'},
                    'operations': [
                        {'id': '173735292595871745', 'paging_token': '173735292595871745',
                         'transaction_successful': True,
                         'source_account': 'GADEN24AOOW3RXP6GBZWFLRFGUQI5GX26RYIPZHCP4KXYXGUNBYKK7PR',
                         'type': 'payment',
                         'type_i': 1, 'created_at': '2022-04-13T11:59:11Z',
                         'transaction_hash': '950b76ace2416b09564943c058e243d5d05aaad4cf19595a6170024791fe2f58',
                         'asset_type': 'native', 'from': 'GADEN24AOOW3RXP6GBZWFLRFGUQI5GX26RYIPZHCP4KXYXGUNBYKK7PR',
                         'to': 'GAOB3HQAJ62OMQKZVJWY5HSO2X5JSLFPLH2UUXBTYLE3YUBOD4KKE4LH', 'amount': '0.0002000'},
                        {'id': '173735292595871746', 'paging_token': '173735292595871746',
                         'transaction_successful': True,
                         'source_account': 'GADEN24AOOW3RXP6GBZWFLRFGUQI5GX26RYIPZHCP4KXYXGUNBYKK7PR',
                         'type': 'path_payment_strict_send', 'type_i': 13, 'created_at': '2022-04-13T11:59:11Z',
                         'transaction_hash': '950b76ace2416b09564943c058e243d5d05aaad4cf19595a6170024791fe2f58',
                         'asset_type': 'native', 'from': 'GADEN24AOOW3RXP6GBZWFLRFGUQI5GX26RYIPZHCP4KXYXGUNBYKK7PR',
                         'to': 'GADEN24AOOW3RXP6GBZWFLRFGUQI5GX26RYIPZHCP4KXYXGUNBYKK7PR', 'amount': '0.5867271',
                         'path': [
                             {'asset_type': 'credit_alphanum12', 'asset_code': 'DOGET',
                              'asset_issuer': 'GDOEVDDBU6OBWKL7VHDAOKD77UP4DKHQYKOKJJT5PR3WRDBTX35HUEUX'},
                             {'asset_type': 'credit_alphanum4', 'asset_code': 'USDC',
                              'asset_issuer': 'GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN'}],
                         'source_amount': '0.5856000', 'destination_min': '0.5856000', 'source_asset_type': 'native'}],
                    'effects': None}}, 'context': {'code': 200, 'source': 'D', 'results': 1, 'state': 40451193,
                                                   'market_price_usd': 0.193773,
                                                   'cache': {'live': True, 'duration': 120,
                                                             'since': '2022-04-13 12:29:08',
                                                             'until': '2022-04-13 12:31:08',
                                                             'time': 3.0994415283203125e-06},
                                                   'api': {'version': '2.0.95-ie',
                                                           'last_major_update': '2021-07-19 00:00:00',
                                                           'next_major_update': None,
                                                           'documentation': 'https://blockchair.com/api/docs',
                                                           'notice': ':)'},
                                                   'servers': 'API4,XLM4,XLM4', 'time': 0.777061939239502,
                                                   'render_time': 0.0032050609588623047,
                                                   'full_time': 0.7802670001983643,
                                                   'request_cost': 2}}
        ]
        expected_txs_details3 = [{
            'hash': '950b76ace2416b09564943c058e243d5d05aaad4cf19595a6170024791fe2f58',
            'success': True,
            'inputs': [],
            'outputs': [],
            'transfers': [
                {'type': 'MainCoin',
                 'symbol': cls.symbol,
                 'currency': Currencies.xlm,
                 'is_valid': True,
                 'token': None,
                 'memo': '0.0004661',
                 'from': 'GADEN24AOOW3RXP6GBZWFLRFGUQI5GX26RYIPZHCP4KXYXGUNBYKK7PR',
                 'to': 'GAOB3HQAJ62OMQKZVJWY5HSO2X5JSLFPLH2UUXBTYLE3YUBOD4KKE4LH',
                 'value': Decimal('0.0002000')}
            ],
            'memo': '0.0004661',
            'block': 40450900,
            'fees': Decimal('0.4100004'),
            'date': datetime.datetime(2022, 4, 13, 11, 59, 11, tzinfo=datetime.timezone.utc),
            'raw': None,
            'confirmations': 598}]
        cls.get_tx_details(tx_details_mock_responses3, expected_txs_details3)

        cls.txs_hash = ['']
        tx_details_mock_responses4 = [
            {'data': {'ledgers': 40452165, 'best_ledger_height': 40452165,
                      'best_ledger_hash': '00209e2d6e965716326b7df01da807079a5106c441782adcadd7fd59b84d39a7',
                      'best_ledger_time': '2022-04-13 14:08:48',
                      'circulation': 1054439020873472865,
                      'ledgers_24h': 13360, 'transactions_24h': 6249895,
                      'successful_transactions_24h': 3352066,
                      'failed_transactions_24h': 2897829,
                      'operations_24h': 9609290,
                      'average_transaction_fee_24h': 818.2359296729202,
                      'average_transaction_fee_usd_24h': 1.60287509207347e-05,
                      'market_price_usd': 0.195894, 'market_price_btc': 4.8388005137832e-06,
                      'market_price_usd_change_24h_percentage': 1.82224,
                      'market_cap_usd': 4847424271, 'market_dominance_percentage': 0.24},
             'context': {'code': 200, 'source': 'D', 'state': 40452165,
                         'cache': {'live': False, 'duration': 120,
                                   'since': '2022-04-13 14:09:00',
                                   'until': '2022-04-13 14:11:00',
                                   'time': 2.86102294921875e-06},
                         'api': {'version': '2.0.95-ie',
                                 'last_major_update': '2021-07-19 00:00:00',
                                 'next_major_update': None,
                                 'documentation': 'https://blockchair.com/api/docs',
                                 'notice': ':)'},
                         'servers': 'API4', 'time': 5.1975250244140625e-05,
                         'render_time': 0.001173257827758789,
                         'full_time': 0.0011761188507080078,
                         'request_cost': 1}},
            {
                'data': {'bba174b77688fc05481e73d71049f7b969b243fa94f014b6b33aa8d393613550': {
                    'transaction': {
                        'id': 'bba174b77688fc05481e73d71049f7b969b243fa94f014b6b33aa8d393613550',
                        'paging_token': '173740661302898688', 'successful': False,
                        'hash': 'bba174b77688fc05481e73d71049f7b969b243fa94f014b6b33aa8d393613550',
                        'ledger': 40452150, 'created_at': '2022-04-13T14:07:16Z',
                        'source_account': 'GCCKAJYZSVVRGKH2GTURCFBHA2FFPMJD7M7HMPBUGGUVZUYABVDKSR5Y',
                        'source_account_sequence': '167746587765140431',
                        'fee_account': 'GCCKAJYZSVVRGKH2GTURCFBHA2FFPMJD7M7HMPBUGGUVZUYABVDKSR5Y',
                        'fee_charged': '100', 'max_fee': '24042', 'operation_count': 1,
                        'envelope_xdr': 'AAAAAgAAAACEoCcZlWsTKPo06REUJwaKV7Ej+z52PDQxqVzTAA1GqQAAXeoCU/SiAAZrzwAAAAEAAAAAAAAAAAAAAABiVto8AAAAAAAAAAEAAAAAAAAAAgAAAAAAAAAAEUkMgAAAAACEoCcZlWsTKPo06REUJwaKV7Ej+z52PDQxqVzTAA1GqQAAAAAAAAAAEUkMgAAAAAEAAAABSlBFRwAAAADzA0C2VCFk/AJSuDSosPwh0tx7eSAR0CiU2pxbq7W2WQAAAAAAAAABAA1GqQAAAECZWuwMpemzo9zK5ikFuzQFw76/J2og10HvfTCGhrzDh9AvbzQgPGrpObEcYx5If47t7jN6vRJpUjsJMe7WWb8L',
                        'result_xdr': 'AAAAAAAAAGT/////AAAAAQAAAAAAAAAC////9AAAAAA=',
                        'result_meta_xdr': 'AAAAAgAAAAIAAAADAmlANgAAAAAAAAAAhKAnGZVrEyj6NOkRFCcGilexI/s+djw0Malc0wANRqkAAAAAAvbCEgJT9KIABmvOAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAABAmlANgAAAAAAAAAAhKAnGZVrEyj6NOkRFCcGilexI/s+djw0Malc0wANRqkAAAAAAvbCEgJT9KIABmvPAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA==',
                        'fee_meta_xdr': 'AAAAAgAAAAMCaUA0AAAAAAAAAACEoCcZlWsTKPo06REUJwaKV7Ej+z52PDQxqVzTAA1GqQAAAAAC9sJ2AlP0ogAGa84AAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAECaUA2AAAAAAAAAACEoCcZlWsTKPo06REUJwaKV7Ej+z52PDQxqVzTAA1GqQAAAAAC9sISAlP0ogAGa84AAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAA==',
                        'memo_type': 'none', 'signatures': [
                            'mVrsDKXps6PcyuYpBbs0BcO+vydqINdB730whoa8w4fQL280IDxq6TmxHGMeSH+O7e4zer0SaVI7CTHu1lm/Cw=='],
                        'valid_after': '1970-01-01T00:00:00Z',
                        'valid_before': '2022-04-13T14:12:12Z'},
                    'operations': [
                        {'id': '173740661302898689', 'paging_token': '173740661302898689',
                         'transaction_successful': False,
                         'source_account': 'GCCKAJYZSVVRGKH2GTURCFBHA2FFPMJD7M7HMPBUGGUVZUYABVDKSR5Y',
                         'type': 'path_payment_strict_receive', 'type_i': 2,
                         'created_at': '2022-04-13T14:07:16Z',
                         'transaction_hash': 'bba174b77688fc05481e73d71049f7b969b243fa94f014b6b33aa8d393613550',
                         'asset_type': 'native',
                         'from': 'GCCKAJYZSVVRGKH2GTURCFBHA2FFPMJD7M7HMPBUGGUVZUYABVDKSR5Y',
                         'to': 'GCCKAJYZSVVRGKH2GTURCFBHA2FFPMJD7M7HMPBUGGUVZUYABVDKSR5Y',
                         'amount': '29.0000000', 'path': [
                            {'asset_type': 'credit_alphanum4', 'asset_code': 'JPEG',
                             'asset_issuer': 'GDZQGQFWKQQWJ7ACKK4DJKFQ7QQ5FXD3PEQBDUBISTNJYW5LWW3FSCKK'}],
                         'source_amount': '0.0000000', 'source_max': '29.0000000',
                         'source_asset_type': 'native'}],
                    'effects': None}},
                'context': {'code': 200, 'source': 'D', 'results': 1, 'state': 40452161,
                            'market_price_usd': 0.195881,
                            'cache': {'live': False, 'duration': 120,
                                      'since': '2022-04-13 14:08:32',
                                      'until': '2022-04-13 14:10:32',
                                      'time': 4.0531158447265625e-06},
                            'api': {'version': '2.0.95-ie',
                                    'last_major_update': '2021-07-19 00:00:00',
                                    'next_major_update': None,
                                    'documentation': 'https://blockchair.com/api/docs',
                                    'notice': ':)'},
                            'servers': 'API4,XLM4,XLM4', 'time': 0.8539719581604004,
                            'render_time': 0.001847982406616211,
                            'full_time': 0.0018520355224609375,
                            'request_cost': 1}}]
        expected_txs_details4 = [{'success': False}]
        cls.get_tx_details(tx_details_mock_responses4, expected_txs_details4)
