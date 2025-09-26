import datetime
import pytest
from decimal import Decimal
from unittest import TestCase

from exchange.base.models import Currencies
from exchange.blockchain.api.xlm.horizon_new import StellarHorizonAPI
from exchange.blockchain.api.xlm.xlm_explorer_interface import StellarExplorerInterface
from exchange.blockchain.apis_conf import APIS_CONF
from exchange.blockchain.tests.api.general_test.general_test_from_explorer import TestFromExplorer


class TestHorizonApiCalls(TestCase):
    api = StellarHorizonAPI
    account_address = ['GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5']

    @pytest.mark.slow
    def test_get_balance_api(self):
        for address in self.account_address:
            get_balance_result = self.api.get_balance(address)
            assert isinstance(get_balance_result, dict)
            assert isinstance(get_balance_result['balances'], list)
            assert isinstance(get_balance_result['balances'][0], dict)
            assert isinstance(get_balance_result['balances'][0]['balance'], str)

    @pytest.mark.slow
    def test_get_address_txs_api(self):
        for address in self.account_address:
            get_address_txs_result = self.api.get_address_txs(address)
            assert isinstance(get_address_txs_result, dict)
            assert isinstance(get_address_txs_result.get('pay_response').get('_embedded').get('records'), list)
            assert isinstance(get_address_txs_result.get('tx_response').get('_embedded').get('records'), list)
            pay_records = get_address_txs_result.get('pay_response').get('_embedded').get('records')
            tx_records = get_address_txs_result.get('tx_response').get('_embedded').get('records')
            key2check = [('hash', str), ('successful', bool), ('source_account', str), ('ledger', int)]
            for tx in tx_records:
                assert isinstance(tx, dict)
                for key, value in key2check:
                    assert isinstance(tx.get(key), value)
            key2check_pay = [('transaction_successful', bool), ('type_i', int), ('asset_type', str),
                             ('created_at', str), ('transaction_hash', str), ('source_account', str), ('from', str),
                             ('to', str)]
            for record in pay_records:
                assert isinstance(record, dict)
                for key, value in key2check_pay:
                    assert isinstance(record.get(key), value)


class TestStellarHorizonFromExplorer(TestFromExplorer):
    api = StellarHorizonAPI
    addresses = ['GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5']
    txs_addresses = ['GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5']
    currencies = Currencies.xlm
    explorerInterface = StellarExplorerInterface
    symbol = 'XLM'

    @classmethod
    def test_get_balance(cls):
        APIS_CONF[cls.symbol]['get_balances'] = 'xlm_interface_explorer'
        balance_mock_responses = [
            {'_links': {'self': {
                'href': 'https://horizon.stellar.org/accounts/GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5'},
                'transactions': {
                    'href': 'https://horizon.stellar.org/accounts/GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5/transactions{?cursor,limit,order}',
                    'templated': True}, 'operations': {
                    'href': 'https://horizon.stellar.org/accounts/GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5/operations{?cursor,limit,order}',
                    'templated': True}, 'payments': {
                    'href': 'https://horizon.stellar.org/accounts/GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5/payments{?cursor,limit,order}',
                    'templated': True}, 'effects': {
                    'href': 'https://horizon.stellar.org/accounts/GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5/effects{?cursor,limit,order}',
                    'templated': True}, 'offers': {
                    'href': 'https://horizon.stellar.org/accounts/GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5/offers{?cursor,limit,order}',
                    'templated': True}, 'trades': {
                    'href': 'https://horizon.stellar.org/accounts/GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5/trades{?cursor,limit,order}',
                    'templated': True}, 'data': {
                    'href': 'https://horizon.stellar.org/accounts/GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5/data/{key}',
                    'templated': True}}, 'id': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                'account_id': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                'sequence': '145182521808907275',
                'sequence_ledger': 52490377, 'sequence_time': '1720509687', 'subentry_count': 3,
                'home_domain': 'bitgo.com', 'last_modified_ledger': 52491094,
                'last_modified_time': '2024-07-09T08:29:31Z',
                'thresholds': {'low_threshold': 1, 'med_threshold': 2, 'high_threshold': 3},
                'flags': {'auth_required': False, 'auth_revocable': False, 'auth_immutable': False,
                          'auth_clawback_enabled': False}, 'balances': [
                {'balance': '686754.2506758', 'buying_liabilities': '0.0000000', 'selling_liabilities': '0.0000000',
                 'asset_type': 'native'}], 'signers': [
                {'weight': 1, 'key': 'GAOURM3PGXAIIWUVBTLMJBY4T5LPZGUMLG6PLLQQH5FF2UB35YBPIG76',
                 'type': 'ed25519_public_key'},
                {'weight': 1, 'key': 'GCLZAIXJIRECWWUSCEJJSFWSTQ6XZ7YEQNVXVICQCHG3X53ZOWN2OM7Z',
                 'type': 'ed25519_public_key'},
                {'weight': 1, 'key': 'GCW3CJRXSFGZJMQCJCITTPTNSOWLYFPFTL6G5C52M2N2DG6ANJ5EKYJ6',
                 'type': 'ed25519_public_key'},
                {'weight': 0, 'key': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                 'type': 'ed25519_public_key'}], 'data': {}, 'num_sponsoring': 0, 'num_sponsored': 0,
                'paging_token': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5'}
        ]
        expected_balances = [
            {'address': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
             'balance': Decimal('686754.2506758'),
             'received': Decimal('686754.2506758'),
             'rewarded': Decimal('0'),
             'sent': Decimal('0')}
        ]
        cls.get_balance(balance_mock_responses, expected_balances)

    @classmethod
    def test_get_address_txs(cls):
        from unittest.mock import Mock
        from django.utils import timezone
        timezone.now = Mock(return_value=datetime.datetime(2024, 7, 8, 0, 0, 0, tzinfo=datetime.timezone.utc))
        APIS_CONF[cls.symbol]['get_txs'] = 'xlm_interface_explorer'
        address_txs_mock_response = [
            {
                '_links': {'self': {
                    'href': 'https://horizon.stellar.org/accounts/GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5/payments?cursor=&limit=30&order=desc'},
                    'next': {
                        'href': 'https://horizon.stellar.org/accounts/GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5/payments?cursor=225414353438969857&limit=30&order=desc'},
                    'prev': {
                        'href': 'https://horizon.stellar.org/accounts/GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5/payments?cursor=225460949539491841&limit=30&order=asc'}},
                '_embedded': {'records': [{'_links': {
                    'self': {'href': 'https://horizon.stellar.org/operations/225460949539491841'}, 'transaction': {
                        'href': 'https://horizon.stellar.org/transactions/d730cdf46b16a1b124c082e9cb60c4e75d2daf4ff3547f7945cc14e500896080'},
                    'effects': {'href': 'https://horizon.stellar.org/operations/225460949539491841/effects'},
                    'succeeds': {'href': 'https://horizon.stellar.org/effects?order=desc&cursor=225460949539491841'},
                    'precedes': {'href': 'https://horizon.stellar.org/effects?order=asc&cursor=225460949539491841'}},
                    'id': '225460949539491841', 'paging_token': '225460949539491841',
                    'transaction_successful': True,
                    'source_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                    'type': 'payment', 'type_i': 1, 'created_at': '2024-07-09T13:28:51Z',
                    'transaction_hash': 'd730cdf46b16a1b124c082e9cb60c4e75d2daf4ff3547f7945cc14e500896080',
                    'asset_type': 'native',
                    'from': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                    'to': 'GBZLHGDYMSVF4X6DYAGKLIQX3F64W3MXNDVGHKQPR226TCJ5QJ2ZQKVA',
                    'amount': '19.5416687'}, {'_links': {
                    'self': {'href': 'https://horizon.stellar.org/operations/225460386898640897'}, 'transaction': {
                        'href': 'https://horizon.stellar.org/transactions/d6bf6931c301b3fe57a7e5921608db22b3edc861897780abe5603a18b8a9eebe'},
                    'effects': {'href': 'https://horizon.stellar.org/operations/225460386898640897/effects'},
                    'succeeds': {'href': 'https://horizon.stellar.org/effects?order=desc&cursor=225460386898640897'},
                    'precedes': {'href': 'https://horizon.stellar.org/effects?order=asc&cursor=225460386898640897'}},
                    'id': '225460386898640897',
                    'paging_token': '225460386898640897',
                    'transaction_successful': True,
                    'source_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                    'type': 'payment', 'type_i': 1,
                    'created_at': '2024-07-09T13:16:21Z',
                    'transaction_hash': 'd6bf6931c301b3fe57a7e5921608db22b3edc861897780abe5603a18b8a9eebe',
                    'asset_type': 'native',
                    'from': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                    'to': 'GDAEZBKKPVVEBPDFSY6WMQ7Y4C7FYCS6CYODNURRN4EZIGTMNKKROESG',
                    'amount': '119.8400000'}, {'_links': {
                    'self': {'href': 'https://horizon.stellar.org/operations/225459703998763009'}, 'transaction': {
                        'href': 'https://horizon.stellar.org/transactions/9b008710ebe443f9af0e840b4d83cc0bf657cee3756252ee7079008b792a2516'},
                    'effects': {'href': 'https://horizon.stellar.org/operations/225459703998763009/effects'},
                    'succeeds': {'href': 'https://horizon.stellar.org/effects?order=desc&cursor=225459703998763009'},
                    'precedes': {'href': 'https://horizon.stellar.org/effects?order=asc&cursor=225459703998763009'}},
                    'id': '225459703998763009',
                    'paging_token': '225459703998763009',
                    'transaction_successful': True,
                    'source_account': 'GDHF3HIKWM5KJAVLZBSZWUFDOEOT7IBMY22UXG4QBE326O354INLPAND',
                    'type': 'payment',
                    'type_i': 1,
                    'created_at': '2024-07-09T13:01:05Z',
                    'transaction_hash': '9b008710ebe443f9af0e840b4d83cc0bf657cee3756252ee7079008b792a2516',
                    'asset_type': 'native',
                    'from': 'GDHF3HIKWM5KJAVLZBSZWUFDOEOT7IBMY22UXG4QBE326O354INLPAND',
                    'to': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                    'amount': '238.7155619'}, {
                    '_links': {'self': {
                        'href': 'https://horizon.stellar.org/operations/225458338199187457'},
                        'transaction': {
                            'href': 'https://horizon.stellar.org/transactions/4f0f55720a10c498ac57fe4fe10b0aca3da95217f26d1b65fd833a77a2edee7f'},
                        'effects': {
                            'href': 'https://horizon.stellar.org/operations/225458338199187457/effects'},
                        'succeeds': {
                            'href': 'https://horizon.stellar.org/effects?order=desc&cursor=225458338199187457'},
                        'precedes': {
                            'href': 'https://horizon.stellar.org/effects?order=asc&cursor=225458338199187457'}},
                    'id': '225458338199187457', 'paging_token': '225458338199187457',
                    'transaction_successful': True,
                    'source_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                    'type': 'payment', 'type_i': 1, 'created_at': '2024-07-09T12:30:49Z',
                    'transaction_hash': '4f0f55720a10c498ac57fe4fe10b0aca3da95217f26d1b65fd833a77a2edee7f',
                    'asset_type': 'native',
                    'from': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                    'to': 'GABFQIK63R2NETJM7T673EAMZN4RJLLGP3OFUEJU5SZVTGWUKULZJNL6',
                    'amount': '320.8000472'}, {'_links': {
                    'self': {'href': 'https://horizon.stellar.org/operations/225456706111410177'}, 'transaction': {
                        'href': 'https://horizon.stellar.org/transactions/b55d9b5260dee2f1697ff998594e2a6e7e9b72e54b01367db1943f3dc7e47ad1'},
                    'effects': {'href': 'https://horizon.stellar.org/operations/225456706111410177/effects'},
                    'succeeds': {'href': 'https://horizon.stellar.org/effects?order=desc&cursor=225456706111410177'},
                    'precedes': {'href': 'https://horizon.stellar.org/effects?order=asc&cursor=225456706111410177'}},
                    'id': '225456706111410177',
                    'paging_token': '225456706111410177',
                    'transaction_successful': True,
                    'source_account': 'GD3UAVRI2XHOUZHLKESHC7YQLQZEVUFD6NN45SOW72LEEQUL2XLJ5R5G',
                    'type': 'payment', 'type_i': 1,
                    'created_at': '2024-07-09T11:54:31Z',
                    'transaction_hash': 'b55d9b5260dee2f1697ff998594e2a6e7e9b72e54b01367db1943f3dc7e47ad1',
                    'asset_type': 'native',
                    'from': 'GD3UAVRI2XHOUZHLKESHC7YQLQZEVUFD6NN45SOW72LEEQUL2XLJ5R5G',
                    'to': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                    'amount': '10527.3791198'}, {'_links': {
                    'self': {'href': 'https://horizon.stellar.org/operations/225455344607109121'}, 'transaction': {
                        'href': 'https://horizon.stellar.org/transactions/699ef2c2bb5653cc272fa75fe59e637f3dad22f03f3fcf011d4ebe85724d8c8a'},
                    'effects': {'href': 'https://horizon.stellar.org/operations/225455344607109121/effects'},
                    'succeeds': {'href': 'https://horizon.stellar.org/effects?order=desc&cursor=225455344607109121'},
                    'precedes': {'href': 'https://horizon.stellar.org/effects?order=asc&cursor=225455344607109121'}},
                    'id': '225455344607109121',
                    'paging_token': '225455344607109121',
                    'transaction_successful': True,
                    'source_account': 'GD6RWYUQ6FWRBWFFA4HZVPCQUKGUIHZ4SL5G5GJU4HP3LKMYSUYAGBUA',
                    'type': 'payment',
                    'type_i': 1,
                    'created_at': '2024-07-09T11:24:05Z',
                    'transaction_hash': '699ef2c2bb5653cc272fa75fe59e637f3dad22f03f3fcf011d4ebe85724d8c8a',
                    'asset_type': 'native',
                    'from': 'GD6RWYUQ6FWRBWFFA4HZVPCQUKGUIHZ4SL5G5GJU4HP3LKMYSUYAGBUA',
                    'to': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                    'amount': '188.5956000'},
                    {'_links': {'self': {
                        'href': 'https://horizon.stellar.org/operations/225453815598526465'},
                        'transaction': {
                            'href': 'https://horizon.stellar.org/transactions/e2c24b3427e1d672b9ef2d9743a0ceb081c136e9e65565f976b68c1d35c350c9'},
                        'effects': {
                            'href': 'https://horizon.stellar.org/operations/225453815598526465/effects'},
                        'succeeds': {
                            'href': 'https://horizon.stellar.org/effects?order=desc&cursor=225453815598526465'},
                        'precedes': {
                            'href': 'https://horizon.stellar.org/effects?order=asc&cursor=225453815598526465'}},
                        'id': '225453815598526465', 'paging_token': '225453815598526465',
                        'transaction_successful': True,
                        'source_account': 'GC5LF63GRVIT5ZXXCXLPI3RX2YXKJQFZVBSAO6AUELN3YIMSWPD6Z6FH',
                        'type': 'payment', 'type_i': 1, 'created_at': '2024-07-09T10:49:44Z',
                        'transaction_hash': 'e2c24b3427e1d672b9ef2d9743a0ceb081c136e9e65565f976b68c1d35c350c9',
                        'asset_type': 'native',
                        'from': 'GC5LF63GRVIT5ZXXCXLPI3RX2YXKJQFZVBSAO6AUELN3YIMSWPD6Z6FH',
                        'to': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                        'amount': '123.9078659'}, {'_links': {
                        'self': {'href': 'https://horizon.stellar.org/operations/225453016734818305'}, 'transaction': {
                            'href': 'https://horizon.stellar.org/transactions/2b8d863e4e03ec4c3643821babc67ef32c06dc349081ad74ff4eef8872cf1288'},
                        'effects': {'href': 'https://horizon.stellar.org/operations/225453016734818305/effects'},
                        'succeeds': {
                            'href': 'https://horizon.stellar.org/effects?order=desc&cursor=225453016734818305'},
                        'precedes': {
                            'href': 'https://horizon.stellar.org/effects?order=asc&cursor=225453016734818305'}},
                        'id': '225453016734818305',
                        'paging_token': '225453016734818305',
                        'transaction_successful': True,
                        'source_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                        'type': 'payment', 'type_i': 1,
                        'created_at': '2024-07-09T10:31:50Z',
                        'transaction_hash': '2b8d863e4e03ec4c3643821babc67ef32c06dc349081ad74ff4eef8872cf1288',
                        'asset_type': 'native',
                        'from': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                        'to': 'GBGII2C7M4TOEC2MVAZYG3TRFM3ATCCEWANSN4Q3AHEX3NRKXJCVZDEV',
                        'amount': '43.9130030'}, {'_links': {
                        'self': {'href': 'https://horizon.stellar.org/operations/225450504178843649'}, 'transaction': {
                            'href': 'https://horizon.stellar.org/transactions/453b8129f35cd0d7dc469db0f5468ad3e80ab84ac8041ce3e11b9284bf366083'},
                        'effects': {'href': 'https://horizon.stellar.org/operations/225450504178843649/effects'},
                        'succeeds': {
                            'href': 'https://horizon.stellar.org/effects?order=desc&cursor=225450504178843649'},
                        'precedes': {
                            'href': 'https://horizon.stellar.org/effects?order=asc&cursor=225450504178843649'}},
                        'id': '225450504178843649',
                        'paging_token': '225450504178843649',
                        'transaction_successful': True,
                        'source_account': 'GBALLUSPAPYHIJFYVSAH3O6LUARQK2T6BCOIN5HG7HMLROBDGHYBBAVV',
                        'type': 'payment',
                        'type_i': 1,
                        'created_at': '2024-07-09T09:35:18Z',
                        'transaction_hash': '453b8129f35cd0d7dc469db0f5468ad3e80ab84ac8041ce3e11b9284bf366083',
                        'asset_type': 'native',
                        'from': 'GBALLUSPAPYHIJFYVSAH3O6LUARQK2T6BCOIN5HG7HMLROBDGHYBBAVV',
                        'to': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                        'amount': '147.0000000'}, {
                        '_links': {'self': {
                            'href': 'https://horizon.stellar.org/operations/225448829142036481'},
                            'transaction': {
                                'href': 'https://horizon.stellar.org/transactions/f5f3d8967bfdd88a82c26df8511482a230eec924d4747c71f473c0aacc9d3f6e'},
                            'effects': {
                                'href': 'https://horizon.stellar.org/operations/225448829142036481/effects'},
                            'succeeds': {
                                'href': 'https://horizon.stellar.org/effects?order=desc&cursor=225448829142036481'},
                            'precedes': {
                                'href': 'https://horizon.stellar.org/effects?order=asc&cursor=225448829142036481'}},
                        'id': '225448829142036481', 'paging_token': '225448829142036481',
                        'transaction_successful': True,
                        'source_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                        'type': 'payment', 'type_i': 1, 'created_at': '2024-07-09T08:58:06Z',
                        'transaction_hash': 'f5f3d8967bfdd88a82c26df8511482a230eec924d4747c71f473c0aacc9d3f6e',
                        'asset_type': 'native',
                        'from': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                        'to': 'GD6RWYUQ6FWRBWFFA4HZVPCQUKGUIHZ4SL5G5GJU4HP3LKMYSUYAGBUA',
                        'amount': '33.6015463'}, {'_links': {
                        'self': {'href': 'https://horizon.stellar.org/operations/225447532061687809'}, 'transaction': {
                            'href': 'https://horizon.stellar.org/transactions/2700b7ee302e13f4500e3e85a6fec00c30299841638417505296b74885af233e'},
                        'effects': {'href': 'https://horizon.stellar.org/operations/225447532061687809/effects'},
                        'succeeds': {
                            'href': 'https://horizon.stellar.org/effects?order=desc&cursor=225447532061687809'},
                        'precedes': {
                            'href': 'https://horizon.stellar.org/effects?order=asc&cursor=225447532061687809'}},
                        'id': '225447532061687809',
                        'paging_token': '225447532061687809',
                        'transaction_successful': True,
                        'source_account': 'GBGHMELHHVTB6EQ5TNERZWPGFURADVSO6RW5PNNMRDMG55E74UBER45I',
                        'type': 'payment', 'type_i': 1,
                        'created_at': '2024-07-09T08:29:31Z',
                        'transaction_hash': '2700b7ee302e13f4500e3e85a6fec00c30299841638417505296b74885af233e',
                        'asset_type': 'native',
                        'from': 'GBGHMELHHVTB6EQ5TNERZWPGFURADVSO6RW5PNNMRDMG55E74UBER45I',
                        'to': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                        'amount': '112.3457510'}, {'_links': {
                        'self': {'href': 'https://horizon.stellar.org/operations/225444452570337281'}, 'transaction': {
                            'href': 'https://horizon.stellar.org/transactions/5c276d28aa3468bac79d7d0fa793abf807e996e0877ae4c97c46b2f8d21f347b'},
                        'effects': {'href': 'https://horizon.stellar.org/operations/225444452570337281/effects'},
                        'succeeds': {
                            'href': 'https://horizon.stellar.org/effects?order=desc&cursor=225444452570337281'},
                        'precedes': {
                            'href': 'https://horizon.stellar.org/effects?order=asc&cursor=225444452570337281'}},
                        'id': '225444452570337281',
                        'paging_token': '225444452570337281',
                        'transaction_successful': True,
                        'source_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                        'type': 'payment',
                        'type_i': 1,
                        'created_at': '2024-07-09T07:21:27Z',
                        'transaction_hash': '5c276d28aa3468bac79d7d0fa793abf807e996e0877ae4c97c46b2f8d21f347b',
                        'asset_type': 'native',
                        'from': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                        'to': 'GAWPTHY6233GRWZZ7JXDMVXDUDCVQVVQ2SXCSTG3R3CNP5LQPDAHNBKL',
                        'amount': '50000.0000000'},
                    {'_links': {'self': {
                        'href': 'https://horizon.stellar.org/operations/225444409620422657'},
                        'transaction': {
                            'href': 'https://horizon.stellar.org/transactions/db9f67d857684e3ca99ec9e7d2ace494ff44cc7e2efdabc9b0af7b8a300d42ad'},
                        'effects': {
                            'href': 'https://horizon.stellar.org/operations/225444409620422657/effects'},
                        'succeeds': {
                            'href': 'https://horizon.stellar.org/effects?order=desc&cursor=225444409620422657'},
                        'precedes': {
                            'href': 'https://horizon.stellar.org/effects?order=asc&cursor=225444409620422657'}},
                        'id': '225444409620422657', 'paging_token': '225444409620422657',
                        'transaction_successful': True,
                        'source_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                        'type': 'payment', 'type_i': 1, 'created_at': '2024-07-09T07:20:30Z',
                        'transaction_hash': 'db9f67d857684e3ca99ec9e7d2ace494ff44cc7e2efdabc9b0af7b8a300d42ad',
                        'asset_type': 'native',
                        'from': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                        'to': 'GABFQIK63R2NETJM7T673EAMZN4RJLLGP3OFUEJU5SZVTGWUKULZJNL6',
                        'amount': '1733.4059938'}, {'_links': {
                        'self': {'href': 'https://horizon.stellar.org/operations/225442360920678401'}, 'transaction': {
                            'href': 'https://horizon.stellar.org/transactions/5370ecc06dc79ee23c552f5bbd230195b2d564877ee4aa5749f9ba0b18c40d00'},
                        'effects': {'href': 'https://horizon.stellar.org/operations/225442360920678401/effects'},
                        'succeeds': {
                            'href': 'https://horizon.stellar.org/effects?order=desc&cursor=225442360920678401'},
                        'precedes': {
                            'href': 'https://horizon.stellar.org/effects?order=asc&cursor=225442360920678401'}},
                        'id': '225442360920678401',
                        'paging_token': '225442360920678401',
                        'transaction_successful': True,
                        'source_account': 'GDHF3HIKWM5KJAVLZBSZWUFDOEOT7IBMY22UXG4QBE326O354INLPAND',
                        'type': 'payment', 'type_i': 1,
                        'created_at': '2024-07-09T06:35:05Z',
                        'transaction_hash': '5370ecc06dc79ee23c552f5bbd230195b2d564877ee4aa5749f9ba0b18c40d00',
                        'asset_type': 'native',
                        'from': 'GDHF3HIKWM5KJAVLZBSZWUFDOEOT7IBMY22UXG4QBE326O354INLPAND',
                        'to': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                        'amount': '356.4445000'}, {'_links': {
                        'self': {'href': 'https://horizon.stellar.org/operations/225442013030813697'}, 'transaction': {
                            'href': 'https://horizon.stellar.org/transactions/14a5ead1562b71c22d4f9399a7d453730692719e4f48def731d1618696d6dc25'},
                        'effects': {'href': 'https://horizon.stellar.org/operations/225442013030813697/effects'},
                        'succeeds': {
                            'href': 'https://horizon.stellar.org/effects?order=desc&cursor=225442013030813697'},
                        'precedes': {
                            'href': 'https://horizon.stellar.org/effects?order=asc&cursor=225442013030813697'}},
                        'id': '225442013030813697',
                        'paging_token': '225442013030813697',
                        'transaction_successful': True,
                        'source_account': 'GAV6J5L473K4H6226IFNCAL7E5A2PR63YRCZDYJPTQH3S35YODXUUADV',
                        'type': 'payment',
                        'type_i': 1,
                        'created_at': '2024-07-09T06:27:25Z',
                        'transaction_hash': '14a5ead1562b71c22d4f9399a7d453730692719e4f48def731d1618696d6dc25',
                        'asset_type': 'native',
                        'from': 'GAV6J5L473K4H6226IFNCAL7E5A2PR63YRCZDYJPTQH3S35YODXUUADV',
                        'to': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                        'amount': '252.7154330'},
                    {'_links': {'self': {
                        'href': 'https://horizon.stellar.org/operations/225434367987757057'},
                        'transaction': {
                            'href': 'https://horizon.stellar.org/transactions/34a547aa9854384deeb4b321caac0c87b0beec2a076f7a8818ca2a7f82a06606'},
                        'effects': {
                            'href': 'https://horizon.stellar.org/operations/225434367987757057/effects'},
                        'succeeds': {
                            'href': 'https://horizon.stellar.org/effects?order=desc&cursor=225434367987757057'},
                        'precedes': {
                            'href': 'https://horizon.stellar.org/effects?order=asc&cursor=225434367987757057'}},
                        'id': '225434367987757057', 'paging_token': '225434367987757057',
                        'transaction_successful': True,
                        'source_account': 'GDHF3HIKWM5KJAVLZBSZWUFDOEOT7IBMY22UXG4QBE326O354INLPAND',
                        'type': 'payment', 'type_i': 1, 'created_at': '2024-07-09T03:38:15Z',
                        'transaction_hash': '34a547aa9854384deeb4b321caac0c87b0beec2a076f7a8818ca2a7f82a06606',
                        'asset_type': 'native',
                        'from': 'GDHF3HIKWM5KJAVLZBSZWUFDOEOT7IBMY22UXG4QBE326O354INLPAND',
                        'to': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                        'amount': '68.9227920'}, {'_links': {
                        'self': {'href': 'https://horizon.stellar.org/operations/225432349352439809'}, 'transaction': {
                            'href': 'https://horizon.stellar.org/transactions/135c4be71c4cea1cf5200a1ef3c227535dfe62a9f046f351fc19b6bf6e1693a2'},
                        'effects': {'href': 'https://horizon.stellar.org/operations/225432349352439809/effects'},
                        'succeeds': {
                            'href': 'https://horizon.stellar.org/effects?order=desc&cursor=225432349352439809'},
                        'precedes': {
                            'href': 'https://horizon.stellar.org/effects?order=asc&cursor=225432349352439809'}},
                        'id': '225432349352439809',
                        'paging_token': '225432349352439809',
                        'transaction_successful': True,
                        'source_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                        'type': 'payment', 'type_i': 1,
                        'created_at': '2024-07-09T02:53:24Z',
                        'transaction_hash': '135c4be71c4cea1cf5200a1ef3c227535dfe62a9f046f351fc19b6bf6e1693a2',
                        'asset_type': 'native',
                        'from': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                        'to': 'GCTDX47GLG7UOHXWMOXJCGS46LKWX64BXADGXX2UOLM7CWMUBM3MTLNG',
                        'amount': '4.8551000'}, {'_links': {
                        'self': {'href': 'https://horizon.stellar.org/operations/225432108835401729'}, 'transaction': {
                            'href': 'https://horizon.stellar.org/transactions/f91af004a0b1a33cdbba23a5db526d7f147621a1bdbe56454f477aa8598472c7'},
                        'effects': {'href': 'https://horizon.stellar.org/operations/225432108835401729/effects'},
                        'succeeds': {
                            'href': 'https://horizon.stellar.org/effects?order=desc&cursor=225432108835401729'},
                        'precedes': {
                            'href': 'https://horizon.stellar.org/effects?order=asc&cursor=225432108835401729'}},
                        'id': '225432108835401729',
                        'paging_token': '225432108835401729',
                        'transaction_successful': True,
                        'source_account': 'GD6RWYUQ6FWRBWFFA4HZVPCQUKGUIHZ4SL5G5GJU4HP3LKMYSUYAGBUA',
                        'type': 'payment',
                        'type_i': 1,
                        'created_at': '2024-07-09T02:48:06Z',
                        'transaction_hash': 'f91af004a0b1a33cdbba23a5db526d7f147621a1bdbe56454f477aa8598472c7',
                        'asset_type': 'native',
                        'from': 'GD6RWYUQ6FWRBWFFA4HZVPCQUKGUIHZ4SL5G5GJU4HP3LKMYSUYAGBUA',
                        'to': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                        'amount': '67.2548000'}, {
                        '_links': {'self': {
                            'href': 'https://horizon.stellar.org/operations/225427852521476097'},
                            'transaction': {
                                'href': 'https://horizon.stellar.org/transactions/210e36caca2377401da2cbf0e6a9f64b94c64dd85da0832046fd639d57f7a81e'},
                            'effects': {
                                'href': 'https://horizon.stellar.org/operations/225427852521476097/effects'},
                            'succeeds': {
                                'href': 'https://horizon.stellar.org/effects?order=desc&cursor=225427852521476097'},
                            'precedes': {
                                'href': 'https://horizon.stellar.org/effects?order=asc&cursor=225427852521476097'}},
                        'id': '225427852521476097', 'paging_token': '225427852521476097',
                        'transaction_successful': True,
                        'source_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                        'type': 'payment', 'type_i': 1, 'created_at': '2024-07-09T01:13:39Z',
                        'transaction_hash': '210e36caca2377401da2cbf0e6a9f64b94c64dd85da0832046fd639d57f7a81e',
                        'asset_type': 'native',
                        'from': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                        'to': 'GABFQIK63R2NETJM7T673EAMZN4RJLLGP3OFUEJU5SZVTGWUKULZJNL6',
                        'amount': '158.2706505'}, {'_links': {
                        'self': {'href': 'https://horizon.stellar.org/operations/225423317036126209'}, 'transaction': {
                            'href': 'https://horizon.stellar.org/transactions/7bc532dee93c5f90d13b6178f9045d36d86de36d92f18fe2cc0e57ae076e6f90'},
                        'effects': {'href': 'https://horizon.stellar.org/operations/225423317036126209/effects'},
                        'succeeds': {
                            'href': 'https://horizon.stellar.org/effects?order=desc&cursor=225423317036126209'},
                        'precedes': {
                            'href': 'https://horizon.stellar.org/effects?order=asc&cursor=225423317036126209'}},
                        'id': '225423317036126209',
                        'paging_token': '225423317036126209',
                        'transaction_successful': True,
                        'source_account': 'GB5FUSCVVV7ZLKJVL7FRCSBQHZXYLMSWWXXYC7NH35GV57S5XWKEVA4V',
                        'type': 'payment', 'type_i': 1,
                        'created_at': '2024-07-08T23:31:56Z',
                        'transaction_hash': '7bc532dee93c5f90d13b6178f9045d36d86de36d92f18fe2cc0e57ae076e6f90',
                        'asset_type': 'native',
                        'from': 'GB5FUSCVVV7ZLKJVL7FRCSBQHZXYLMSWWXXYC7NH35GV57S5XWKEVA4V',
                        'to': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                        'amount': '5.0000000'}, {'_links': {
                        'self': {'href': 'https://horizon.stellar.org/operations/225422926194528257'}, 'transaction': {
                            'href': 'https://horizon.stellar.org/transactions/76410c7616ab46b02b435edcd391286b524af7c05af3c0ecc4fd700c5c891c9d'},
                        'effects': {'href': 'https://horizon.stellar.org/operations/225422926194528257/effects'},
                        'succeeds': {
                            'href': 'https://horizon.stellar.org/effects?order=desc&cursor=225422926194528257'},
                        'precedes': {
                            'href': 'https://horizon.stellar.org/effects?order=asc&cursor=225422926194528257'}},
                        'id': '225422926194528257',
                        'paging_token': '225422926194528257',
                        'transaction_successful': True,
                        'source_account': 'GDUQXQAR4ECNAYCTGZAS4TH4KJJIZDLXPR5V2YYRFRGGQ3LTXBFTBVW6',
                        'type': 'payment',
                        'type_i': 1,
                        'created_at': '2024-07-08T23:23:13Z',
                        'transaction_hash': '76410c7616ab46b02b435edcd391286b524af7c05af3c0ecc4fd700c5c891c9d',
                        'asset_type': 'native',
                        'from': 'GDUQXQAR4ECNAYCTGZAS4TH4KJJIZDLXPR5V2YYRFRGGQ3LTXBFTBVW6',
                        'to': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                        'amount': '200.0000000'},
                    {'_links': {'self': {
                        'href': 'https://horizon.stellar.org/operations/225421916876750849'},
                        'transaction': {
                            'href': 'https://horizon.stellar.org/transactions/b46adf2d07154a357eca34596bb0640518a218662aa91427151d2ad72eb87ed8'},
                        'effects': {
                            'href': 'https://horizon.stellar.org/operations/225421916876750849/effects'},
                        'succeeds': {
                            'href': 'https://horizon.stellar.org/effects?order=desc&cursor=225421916876750849'},
                        'precedes': {
                            'href': 'https://horizon.stellar.org/effects?order=asc&cursor=225421916876750849'}},
                        'id': '225421916876750849', 'paging_token': '225421916876750849',
                        'transaction_successful': True,
                        'source_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                        'type': 'payment', 'type_i': 1, 'created_at': '2024-07-08T23:00:52Z',
                        'transaction_hash': 'b46adf2d07154a357eca34596bb0640518a218662aa91427151d2ad72eb87ed8',
                        'asset_type': 'native',
                        'from': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                        'to': 'GCGMJ63NTBSQKW7OEQ3J2RZH6PYXSTEUK4TVE35IPXLB7XWNI2PUDCY6',
                        'amount': '4.4355200'}, {'_links': {
                        'self': {'href': 'https://horizon.stellar.org/operations/225419833817423873'}, 'transaction': {
                            'href': 'https://horizon.stellar.org/transactions/96e7cc22bb4cb249c9a85f1ac2320dcd02dd72d08b2e6a6c23e5359eb23c9009'},
                        'effects': {'href': 'https://horizon.stellar.org/operations/225419833817423873/effects'},
                        'succeeds': {
                            'href': 'https://horizon.stellar.org/effects?order=desc&cursor=225419833817423873'},
                        'precedes': {
                            'href': 'https://horizon.stellar.org/effects?order=asc&cursor=225419833817423873'}},
                        'id': '225419833817423873',
                        'paging_token': '225419833817423873',
                        'transaction_successful': True,
                        'source_account': 'GBZLHGDYMSVF4X6DYAGKLIQX3F64W3MXNDVGHKQPR226TCJ5QJ2ZQKVA',
                        'type': 'payment', 'type_i': 1,
                        'created_at': '2024-07-08T22:15:09Z',
                        'transaction_hash': '96e7cc22bb4cb249c9a85f1ac2320dcd02dd72d08b2e6a6c23e5359eb23c9009',
                        'asset_type': 'native',
                        'from': 'GBZLHGDYMSVF4X6DYAGKLIQX3F64W3MXNDVGHKQPR226TCJ5QJ2ZQKVA',
                        'to': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                        'amount': '456.2000000'}, {'_links': {
                        'self': {'href': 'https://horizon.stellar.org/operations/225416913239658497'}, 'transaction': {
                            'href': 'https://horizon.stellar.org/transactions/917b3a51f47a5b70f36f6bdd265b669f843a9650ee99f93212a4c0b5af494561'},
                        'effects': {'href': 'https://horizon.stellar.org/operations/225416913239658497/effects'},
                        'succeeds': {
                            'href': 'https://horizon.stellar.org/effects?order=desc&cursor=225416913239658497'},
                        'precedes': {
                            'href': 'https://horizon.stellar.org/effects?order=asc&cursor=225416913239658497'}},
                        'id': '225416913239658497',
                        'paging_token': '225416913239658497',
                        'transaction_successful': True,
                        'source_account': 'GA4IRJ52YGZQJDS7XJ375UGSI4FE4KQXHFYUUYNR5QXDVQNAXQTLRJAB',
                        'type': 'payment',
                        'type_i': 1,
                        'created_at': '2024-07-08T21:10:41Z',
                        'transaction_hash': '917b3a51f47a5b70f36f6bdd265b669f843a9650ee99f93212a4c0b5af494561',
                        'asset_type': 'native',
                        'from': 'GA4IRJ52YGZQJDS7XJ375UGSI4FE4KQXHFYUUYNR5QXDVQNAXQTLRJAB',
                        'to': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                        'amount': '347.5786758'}, {
                        '_links': {'self': {
                            'href': 'https://horizon.stellar.org/operations/225415190958120961'},
                            'transaction': {
                                'href': 'https://horizon.stellar.org/transactions/ff1e1b7bbdcd575984ee2ef4d339b253afb84107792ffce43b24c165c4f5fdca'},
                            'effects': {
                                'href': 'https://horizon.stellar.org/operations/225415190958120961/effects'},
                            'succeeds': {
                                'href': 'https://horizon.stellar.org/effects?order=desc&cursor=225415190958120961'},
                            'precedes': {
                                'href': 'https://horizon.stellar.org/effects?order=asc&cursor=225415190958120961'}},
                        'id': '225415190958120961', 'paging_token': '225415190958120961',
                        'transaction_successful': True,
                        'source_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                        'type': 'payment', 'type_i': 1, 'created_at': '2024-07-08T20:32:42Z',
                        'transaction_hash': 'ff1e1b7bbdcd575984ee2ef4d339b253afb84107792ffce43b24c165c4f5fdca',
                        'asset_type': 'native',
                        'from': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                        'to': 'GDS4HKW74QFQ2JEFTT5W5OXQBEPP3C6I6VNZSMSVSKI7DXYS332U5H2W',
                        'amount': '10.5494000'}, {'_links': {
                        'self': {'href': 'https://horizon.stellar.org/operations/225415113648803841'}, 'transaction': {
                            'href': 'https://horizon.stellar.org/transactions/c08bd472abe2d4757c138fa2b277a3eecd847da7fb9f895735dc48e61e21b0b1'},
                        'effects': {'href': 'https://horizon.stellar.org/operations/225415113648803841/effects'},
                        'succeeds': {
                            'href': 'https://horizon.stellar.org/effects?order=desc&cursor=225415113648803841'},
                        'precedes': {
                            'href': 'https://horizon.stellar.org/effects?order=asc&cursor=225415113648803841'}},
                        'id': '225415113648803841',
                        'paging_token': '225415113648803841',
                        'transaction_successful': True,
                        'source_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                        'type': 'payment', 'type_i': 1,
                        'created_at': '2024-07-08T20:31:00Z',
                        'transaction_hash': 'c08bd472abe2d4757c138fa2b277a3eecd847da7fb9f895735dc48e61e21b0b1',
                        'asset_type': 'native',
                        'from': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                        'to': 'GB33O7V4PSLEV5Y725V3CBCM4WPW6YYJIDA27YUYRKA76LK2ZBNMJREW',
                        'amount': '233.7260000'}, {'_links': {
                        'self': {'href': 'https://horizon.stellar.org/operations/225414499467804673'}, 'transaction': {
                            'href': 'https://horizon.stellar.org/transactions/da840859197f71d99350757de57b6e6ba35304ad3c6c54ca6da3769b741f1bb1'},
                        'effects': {'href': 'https://horizon.stellar.org/operations/225414499467804673/effects'},
                        'succeeds': {
                            'href': 'https://horizon.stellar.org/effects?order=desc&cursor=225414499467804673'},
                        'precedes': {
                            'href': 'https://horizon.stellar.org/effects?order=asc&cursor=225414499467804673'}},
                        'id': '225414499467804673',
                        'paging_token': '225414499467804673',
                        'transaction_successful': True,
                        'source_account': 'GAG2TQZMIZMZTFPQZ3ACCSAOMMFLF4ITR53Z4X2WTAI62Z3QSPQ5XB35',
                        'type': 'payment',
                        'type_i': 1,
                        'created_at': '2024-07-08T20:17:30Z',
                        'transaction_hash': 'da840859197f71d99350757de57b6e6ba35304ad3c6c54ca6da3769b741f1bb1',
                        'asset_type': 'native',
                        'from': 'GAG2TQZMIZMZTFPQZ3ACCSAOMMFLF4ITR53Z4X2WTAI62Z3QSPQ5XB35',
                        'to': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                        'amount': '312.8809891'},
                    {'_links': {'self': {
                        'href': 'https://horizon.stellar.org/operations/225414417863778305'},
                        'transaction': {
                            'href': 'https://horizon.stellar.org/transactions/9ba96e961d794be757bf8e66cae47a7203be996104c95312360638491bb50d39'},
                        'effects': {
                            'href': 'https://horizon.stellar.org/operations/225414417863778305/effects'},
                        'succeeds': {
                            'href': 'https://horizon.stellar.org/effects?order=desc&cursor=225414417863778305'},
                        'precedes': {
                            'href': 'https://horizon.stellar.org/effects?order=asc&cursor=225414417863778305'}},
                        'id': '225414417863778305', 'paging_token': '225414417863778305',
                        'transaction_successful': True,
                        'source_account': 'GDHF3HIKWM5KJAVLZBSZWUFDOEOT7IBMY22UXG4QBE326O354INLPAND',
                        'type': 'payment', 'type_i': 1, 'created_at': '2024-07-08T20:15:43Z',
                        'transaction_hash': '9ba96e961d794be757bf8e66cae47a7203be996104c95312360638491bb50d39',
                        'asset_type': 'native',
                        'from': 'GDHF3HIKWM5KJAVLZBSZWUFDOEOT7IBMY22UXG4QBE326O354INLPAND',
                        'to': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                        'amount': '102.8234388'}, {'_links': {
                        'self': {'href': 'https://horizon.stellar.org/operations/225414396389048321'}, 'transaction': {
                            'href': 'https://horizon.stellar.org/transactions/6cdfa6e805ac42f1d980345bf949876592edef8cc51fb0eba0d92e55d4f23fa1'},
                        'effects': {'href': 'https://horizon.stellar.org/operations/225414396389048321/effects'},
                        'succeeds': {
                            'href': 'https://horizon.stellar.org/effects?order=desc&cursor=225414396389048321'},
                        'precedes': {
                            'href': 'https://horizon.stellar.org/effects?order=asc&cursor=225414396389048321'}},
                        'id': '225414396389048321',
                        'paging_token': '225414396389048321',
                        'transaction_successful': True,
                        'source_account': 'GDHF3HIKWM5KJAVLZBSZWUFDOEOT7IBMY22UXG4QBE326O354INLPAND',
                        'type': 'payment', 'type_i': 1,
                        'created_at': '2024-07-08T20:15:15Z',
                        'transaction_hash': '6cdfa6e805ac42f1d980345bf949876592edef8cc51fb0eba0d92e55d4f23fa1',
                        'asset_type': 'native',
                        'from': 'GDHF3HIKWM5KJAVLZBSZWUFDOEOT7IBMY22UXG4QBE326O354INLPAND',
                        'to': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                        'amount': '613.0947248'}, {'_links': {
                        'self': {'href': 'https://horizon.stellar.org/operations/225414353438969857'}, 'transaction': {
                            'href': 'https://horizon.stellar.org/transactions/6e8423c7ba4be166534c26230db957751bee5e7b2a4dd5a83201bdca61a31b8b'},
                        'effects': {'href': 'https://horizon.stellar.org/operations/225414353438969857/effects'},
                        'succeeds': {
                            'href': 'https://horizon.stellar.org/effects?order=desc&cursor=225414353438969857'},
                        'precedes': {
                            'href': 'https://horizon.stellar.org/effects?order=asc&cursor=225414353438969857'}},
                        'id': '225414353438969857',
                        'paging_token': '225414353438969857',
                        'transaction_successful': True,
                        'source_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                        'type': 'payment',
                        'type_i': 1,
                        'created_at': '2024-07-08T20:14:18Z',
                        'transaction_hash': '6e8423c7ba4be166534c26230db957751bee5e7b2a4dd5a83201bdca61a31b8b',
                        'asset_type': 'native',
                        'from': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                        'to': 'GDS4HKW74QFQ2JEFTT5W5OXQBEPP3C6I6VNZSMSVSKI7DXYS332U5H2W',
                        'amount': '26.9330000'}]}},
            {
                '_links': {'self': {
                    'href': 'https://horizon.stellar.org/accounts/GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5/transactions?cursor=&limit=30&order=desc'},
                    'next': {
                        'href': 'https://horizon.stellar.org/accounts/GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5/transactions?cursor=225414353438969856&limit=30&order=desc'},
                    'prev': {
                        'href': 'https://horizon.stellar.org/accounts/GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5/transactions?cursor=225460949539491840&limit=30&order=asc'}},
                '_embedded': {'records': [{'memo': '215976', '_links': {'self': {
                    'href': 'https://horizon.stellar.org/transactions/d730cdf46b16a1b124c082e9cb60c4e75d2daf4ff3547f7945cc14e500896080'},
                    'account': {
                        'href': 'https://horizon.stellar.org/accounts/GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5'},
                    'ledger': {
                        'href': 'https://horizon.stellar.org/ledgers/52494218'},
                    'operations': {
                        'href': 'https://horizon.stellar.org/transactions/d730cdf46b16a1b124c082e9cb60c4e75d2daf4ff3547f7945cc14e500896080/operations{?cursor,limit,order}',
                        'templated': True}, 'effects': {
                        'href': 'https://horizon.stellar.org/transactions/d730cdf46b16a1b124c082e9cb60c4e75d2daf4ff3547f7945cc14e500896080/effects{?cursor,limit,order}',
                        'templated': True}, 'precedes': {
                        'href': 'https://horizon.stellar.org/transactions?order=asc&cursor=225460949539491840'},
                    'succeeds': {
                        'href': 'https://horizon.stellar.org/transactions?order=desc&cursor=225460949539491840'},
                    'transaction': {
                        'href': 'https://horizon.stellar.org/transactions/d730cdf46b16a1b124c082e9cb60c4e75d2daf4ff3547f7945cc14e500896080'}},
                                           'id': 'd730cdf46b16a1b124c082e9cb60c4e75d2daf4ff3547f7945cc14e500896080',
                                           'paging_token': '225460949539491840', 'successful': True,
                                           'hash': 'd730cdf46b16a1b124c082e9cb60c4e75d2daf4ff3547f7945cc14e500896080',
                                           'ledger': 52494218, 'created_at': '2024-07-09T13:28:51Z',
                                           'source_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                                           'source_account_sequence': '145182521808907280',
                                           'fee_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                                           'fee_charged': '100', 'max_fee': '45000', 'operation_count': 1,
                                           'envelope_xdr': 'AAAAAgAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAAr8gCA8q8AAPsEAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAA0uoAAAAAQAAAAAAAAABAAAAAHKzmHhkql5fw8AMpaIX2X3LbZdo6mOqD4616Yk9gnWYAAAAAAAAAAALpdJvAAAAAAAAAALAanpFAAAAQBMLpqew71Dy9K6AvcfWizfl/0glLQOgFZRKMS8X7TgRvLMx19Ufj1VhrWGUF5+ZRCnBKgE5OgDguRqULTMtAwJ5dZunAAAAQGnrkDuAwI3OccRvDGKT2FSkBx5fAkLIoAxz1wbvzrtcTXZpRN2kItbQdnbTaHMWABpYW3+ZKvVigU0BgRZmUgY=',
                                           'result_xdr': 'AAAAAAAAAGQAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAA=',
                                           'result_meta_xdr': 'AAAAAwAAAAAAAAACAAAAAwMg/4oAAAAAAAAAANJdnWDu5Lzz4a+ZqJ3dIG0+ciDA3gcjxGoGjhecW4aZAAAGV+eQtMkCA8q8AAPsDwAAAAMAAAAAAAAAAAAAAAliaXRnby5jb20AAAAAAQIDAAAAAwAAAAAdSLNvNcCEWpUM1sSHHJ9W/JqMWbz1rhA/Sl1QO+4C9AAAAAEAAAAAl5Ai6URIK1qSERKZFtKcPXz/BINreqBQEc2793l1m6cAAAABAAAAAK2xJjeRTZSyAkiROb5tk6y8FeWa/G6LumaboZvAanpFAAAAAQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAwAAAAAAAAAAAAAAAAAAAAMAAAAAAyD/BwAAAABmjTglAAAAAAAAAAEDIP+KAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABlfnkLTJAgPKvAAD7BAAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg/4oAAAAAZo07EwAAAAAAAAABAAAABAAAAAMDIP+KAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABlfnkLTJAgPKvAAD7BAAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg/4oAAAAAZo07EwAAAAAAAAABAyD/igAAAAAAAAAA0l2dYO7kvPPhr5mond0gbT5yIMDeByPEagaOF5xbhpkAAAZX2+riWgIDyrwAA+wQAAAAAwAAAAAAAAAAAAAACWJpdGdvLmNvbQAAAAABAgMAAAADAAAAAB1Is281wIRalQzWxIccn1b8moxZvPWuED9KXVA77gL0AAAAAQAAAACXkCLpREgrWpIREpkW0pw9fP8Eg2t6oFARzbv3eXWbpwAAAAEAAAAArbEmN5FNlLICSJE5vm2TrLwV5Zr8bou6Zpuhm8BqekUAAAABAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAADAAAAAAAAAAAAAAAAAAAAAwAAAAADIP+KAAAAAGaNOxMAAAAAAAAAAwMg+y4AAAAAAAAAAHKzmHhkql5fw8AMpaIX2X3LbZdo6mOqD4616Yk9gnWYAAAdXKh+rnoBr+2LAAOjGgAAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAMAAAAAAyD7LgAAAABmjSIYAAAAAAAAAAEDIP+KAAAAAAAAAABys5h4ZKpeX8PADKWiF9l9y22XaOpjqg+OtemJPYJ1mAAAHVy0JIDpAa/tiwADoxoAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg+y4AAAAAZo0iGAAAAAAAAAAAAAAAAA==',
                                           'fee_meta_xdr': 'AAAAAgAAAAMDIP8HAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABlfnkLUtAgPKvAAD7A8AAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg/wcAAAAAZo04JQAAAAAAAAABAyD/igAAAAAAAAAA0l2dYO7kvPPhr5mond0gbT5yIMDeByPEagaOF5xbhpkAAAZX55C0yQIDyrwAA+wPAAAAAwAAAAAAAAAAAAAACWJpdGdvLmNvbQAAAAABAgMAAAADAAAAAB1Is281wIRalQzWxIccn1b8moxZvPWuED9KXVA77gL0AAAAAQAAAACXkCLpREgrWpIREpkW0pw9fP8Eg2t6oFARzbv3eXWbpwAAAAEAAAAArbEmN5FNlLICSJE5vm2TrLwV5Zr8bou6Zpuhm8BqekUAAAABAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAADAAAAAAAAAAAAAAAAAAAAAwAAAAADIP8HAAAAAGaNOCUAAAAA',
                                           'memo_type': 'id', 'signatures': [
                        'Ewump7DvUPL0roC9x9aLN+X/SCUtA6AVlEoxLxftOBG8szHX1R+PVWGtYZQXn5lEKcEqATk6AOC5GpQtMy0DAg==',
                        'aeuQO4DAjc5xxG8MYpPYVKQHHl8CQsigDHPXBu/Ou1xNdmlE3aQi1tB2dtNocxYAGlhbf5kq9WKBTQGBFmZSBg=='],
                                           'valid_after': '1970-01-01T00:00:00Z',
                                           'preconditions': {'timebounds': {'min_time': '0'}}}, {'memo': '16386',
                                                                                                 '_links': {'self': {
                                                                                                     'href': 'https://horizon.stellar.org/transactions/d6bf6931c301b3fe57a7e5921608db22b3edc861897780abe5603a18b8a9eebe'},
                                                                                                     'account': {
                                                                                                         'href': 'https://horizon.stellar.org/accounts/GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5'},
                                                                                                     'ledger': {
                                                                                                         'href': 'https://horizon.stellar.org/ledgers/52494087'},
                                                                                                     'operations': {
                                                                                                         'href': 'https://horizon.stellar.org/transactions/d6bf6931c301b3fe57a7e5921608db22b3edc861897780abe5603a18b8a9eebe/operations{?cursor,limit,order}',
                                                                                                         'templated': True},
                                                                                                     'effects': {
                                                                                                         'href': 'https://horizon.stellar.org/transactions/d6bf6931c301b3fe57a7e5921608db22b3edc861897780abe5603a18b8a9eebe/effects{?cursor,limit,order}',
                                                                                                         'templated': True},
                                                                                                     'precedes': {
                                                                                                         'href': 'https://horizon.stellar.org/transactions?order=asc&cursor=225460386898640896'},
                                                                                                     'succeeds': {
                                                                                                         'href': 'https://horizon.stellar.org/transactions?order=desc&cursor=225460386898640896'},
                                                                                                     'transaction': {
                                                                                                         'href': 'https://horizon.stellar.org/transactions/d6bf6931c301b3fe57a7e5921608db22b3edc861897780abe5603a18b8a9eebe'}},
                                                                                                 'id': 'd6bf6931c301b3fe57a7e5921608db22b3edc861897780abe5603a18b8a9eebe',
                                                                                                 'paging_token': '225460386898640896',
                                                                                                 'successful': True,
                                                                                                 'hash': 'd6bf6931c301b3fe57a7e5921608db22b3edc861897780abe5603a18b8a9eebe',
                                                                                                 'ledger': 52494087,
                                                                                                 'created_at': '2024-07-09T13:16:21Z',
                                                                                                 'source_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                                                                                                 'source_account_sequence': '145182521808907279',
                                                                                                 'fee_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                                                                                                 'fee_charged': '100',
                                                                                                 'max_fee': '45000',
                                                                                                 'operation_count': 1,
                                                                                                 'envelope_xdr': 'AAAAAgAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAAr8gCA8q8AAPsDwAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAEACAAAAAQAAAAAAAAABAAAAAMBMhUp9akC8ZZY9ZkP44L5cCl4WHDbSMW8JlBpsapUXAAAAAAAAAABHbiIAAAAAAAAAAALAanpFAAAAQKMwmzx7qXAF+jayv4wZvxpmEcPHftEoMQpzurRgM3ma9WTe4r32Wm3hVEOWkacRDg/E5SfkSma4/7JRMLfZAgF5dZunAAAAQMxBsBnufC/CVqLdJiMuJ7zbuOZNb3SosPc6T0BmtP3G5ylGYpOdBRHpVnH31oPW6AaZx48o730L6VEIPBC79wQ=',
                                                                                                 'result_xdr': 'AAAAAAAAAGQAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAA=',
                                                                                                 'result_meta_xdr': 'AAAAAwAAAAAAAAACAAAAAwMg/wcAAAAAAAAAANJdnWDu5Lzz4a+ZqJ3dIG0+ciDA3gcjxGoGjhecW4aZAAAGWC7+1y0CA8q8AAPsDgAAAAMAAAAAAAAAAAAAAAliaXRnby5jb20AAAAAAQIDAAAAAwAAAAAdSLNvNcCEWpUM1sSHHJ9W/JqMWbz1rhA/Sl1QO+4C9AAAAAEAAAAAl5Ai6URIK1qSERKZFtKcPXz/BINreqBQEc2793l1m6cAAAABAAAAAK2xJjeRTZSyAkiROb5tk6y8FeWa/G6LumaboZvAanpFAAAAAQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAwAAAAAAAAAAAAAAAAAAAAMAAAAAAyD9KgAAAABmjS15AAAAAAAAAAEDIP8HAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABlgu/tctAgPKvAAD7A8AAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg/wcAAAAAZo04JQAAAAAAAAABAAAABAAAAAMDIP8HAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABlgu/tctAgPKvAAD7A8AAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg/wcAAAAAZo04JQAAAAAAAAABAyD/BwAAAAAAAAAA0l2dYO7kvPPhr5mond0gbT5yIMDeByPEagaOF5xbhpkAAAZX55C1LQIDyrwAA+wPAAAAAwAAAAAAAAAAAAAACWJpdGdvLmNvbQAAAAABAgMAAAADAAAAAB1Is281wIRalQzWxIccn1b8moxZvPWuED9KXVA77gL0AAAAAQAAAACXkCLpREgrWpIREpkW0pw9fP8Eg2t6oFARzbv3eXWbpwAAAAEAAAAArbEmN5FNlLICSJE5vm2TrLwV5Zr8bou6Zpuhm8BqekUAAAABAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAADAAAAAAAAAAAAAAAAAAAAAwAAAAADIP8HAAAAAGaNOCUAAAAAAAAAAwMg/YwAAAAAAAAAAMBMhUp9akC8ZZY9ZkP44L5cCl4WHDbSMW8JlBpsapUXAAAAhH8CZswDABiNAAAEYAAAAAEAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAMAAAAAAyD9jAAAAABmjS+mAAAAAAAAAAEDIP8HAAAAAAAAAADATIVKfWpAvGWWPWZD+OC+XApeFhw20jFvCZQabGqVFwAAAITGcIjMAwAYjQAABGAAAAABAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg/YwAAAAAZo0vpgAAAAAAAAAAAAAAAA==',
                                                                                                 'fee_meta_xdr': 'AAAAAgAAAAMDIP5oAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABlgu/teRAgPKvAAD7A4AAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg/SoAAAAAZo0teQAAAAAAAAABAyD/BwAAAAAAAAAA0l2dYO7kvPPhr5mond0gbT5yIMDeByPEagaOF5xbhpkAAAZYLv7XLQIDyrwAA+wOAAAAAwAAAAAAAAAAAAAACWJpdGdvLmNvbQAAAAABAgMAAAADAAAAAB1Is281wIRalQzWxIccn1b8moxZvPWuED9KXVA77gL0AAAAAQAAAACXkCLpREgrWpIREpkW0pw9fP8Eg2t6oFARzbv3eXWbpwAAAAEAAAAArbEmN5FNlLICSJE5vm2TrLwV5Zr8bou6Zpuhm8BqekUAAAABAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAADAAAAAAAAAAAAAAAAAAAAAwAAAAADIP0qAAAAAGaNLXkAAAAA',
                                                                                                 'memo_type': 'id',
                                                                                                 'signatures': [
                                                                                                     'ozCbPHupcAX6NrK/jBm/GmYRw8d+0SgxCnO6tGAzeZr1ZN7ivfZabeFUQ5aRpxEOD8TlJ+RKZrj/slEwt9kCAQ==',
                                                                                                     'zEGwGe58L8JWot0mIy4nvNu45k1vdKiw9zpPQGa0/cbnKUZik50FEelWcffWg9boBpnHjyjvfQvpUQg8ELv3BA=='],
                                                                                                 'valid_after': '1970-01-01T00:00:00Z',
                                                                                                 'preconditions': {
                                                                                                     'timebounds': {
                                                                                                         'min_time': '0'}}},
                                          {'memo': '185960', 'memo_bytes': 'MTg1OTYw', '_links': {'self': {
                                              'href': 'https://horizon.stellar.org/transactions/9b008710ebe443f9af0e840b4d83cc0bf657cee3756252ee7079008b792a2516'},
                                              'account': {
                                                  'href': 'https://horizon.stellar.org/accounts/GDHF3HIKWM5KJAVLZBSZWUFDOEOT7IBMY22UXG4QBE326O354INLPAND'},
                                              'ledger': {
                                                  'href': 'https://horizon.stellar.org/ledgers/52493928'},
                                              'operations': {
                                                  'href': 'https://horizon.stellar.org/transactions/9b008710ebe443f9af0e840b4d83cc0bf657cee3756252ee7079008b792a2516/operations{?cursor,limit,order}',
                                                  'templated': True},
                                              'effects': {
                                                  'href': 'https://horizon.stellar.org/transactions/9b008710ebe443f9af0e840b4d83cc0bf657cee3756252ee7079008b792a2516/effects{?cursor,limit,order}',
                                                  'templated': True},
                                              'precedes': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=asc&cursor=225459703998763008'},
                                              'succeeds': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=desc&cursor=225459703998763008'},
                                              'transaction': {
                                                  'href': 'https://horizon.stellar.org/transactions/9b008710ebe443f9af0e840b4d83cc0bf657cee3756252ee7079008b792a2516'}},
                                           'id': '9b008710ebe443f9af0e840b4d83cc0bf657cee3756252ee7079008b792a2516',
                                           'paging_token': '225459703998763008', 'successful': True,
                                           'hash': '9b008710ebe443f9af0e840b4d83cc0bf657cee3756252ee7079008b792a2516',
                                           'ledger': 52493928, 'created_at': '2024-07-09T13:01:05Z',
                                           'source_account': 'GDHF3HIKWM5KJAVLZBSZWUFDOEOT7IBMY22UXG4QBE326O354INLPAND',
                                           'source_account_sequence': '166409929518316834',
                                           'fee_account': 'GDHF3HIKWM5KJAVLZBSZWUFDOEOT7IBMY22UXG4QBE326O354INLPAND',
                                           'fee_charged': '100', 'max_fee': '1000000', 'operation_count': 1,
                                           'envelope_xdr': 'AAAAAgAAAADOXZ0KszqkgqvIZZtQo3EdP6AsxrVLm5AJN687feIatwAPQkACTzTzAAl9IgAAAAEAAAAAAAAAAAAAAABmjTTpAAAAAQAAAAYxODU5NjAAAAAAAAEAAAAAAAAAAQAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAAAAAAAAAAjkkaowAAAAAAAAABfeIatwAAAEB2gLsMm96BnFbKSw1C1XlQT+XDrqrPBFlTSrql4plVbhM+nWTvMuQuWsKYdQc+XpjzaFJULodYtsy2iBYeZ4wD',
                                           'result_xdr': 'AAAAAAAAAGQAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAA=',
                                           'result_meta_xdr': 'AAAAAwAAAAAAAAACAAAAAwMg/mgAAAAAAAAAAM5dnQqzOqSCq8hlm1CjcR0/oCzGtUubkAk3rzt94hq3AAAzjt6JyDgCTzTzAAl9IQAAAAIAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAMAAAAAAyD+RQAAAABmjTPLAAAAAAAAAAEDIP5oAAAAAAAAAADOXZ0KszqkgqvIZZtQo3EdP6AsxrVLm5AJN687feIatwAAM47eicg4Ak808wAJfSIAAAACAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg/mgAAAAAZo00kQAAAAAAAAABAAAABAAAAAMDIP5oAAAAAAAAAADOXZ0KszqkgqvIZZtQo3EdP6AsxrVLm5AJN687feIatwAAM47eicg4Ak808wAJfSIAAAACAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg/mgAAAAAZo00kQAAAAAAAAABAyD+aAAAAAAAAAAAzl2dCrM6pIKryGWbUKNxHT+gLMa1S5uQCTevO33iGrcAADOOUECtlQJPNPMACX0iAAAAAgAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAwAAAAADIP5oAAAAAGaNNJEAAAAAAAAAAwMg/SoAAAAAAAAAANJdnWDu5Lzz4a+ZqJ3dIG0+ciDA3gcjxGoGjhecW4aZAAAGV6C1vO4CA8q8AAPsDgAAAAMAAAAAAAAAAAAAAAliaXRnby5jb20AAAAAAQIDAAAAAwAAAAAdSLNvNcCEWpUM1sSHHJ9W/JqMWbz1rhA/Sl1QO+4C9AAAAAEAAAAAl5Ai6URIK1qSERKZFtKcPXz/BINreqBQEc2793l1m6cAAAABAAAAAK2xJjeRTZSyAkiROb5tk6y8FeWa/G6LumaboZvAanpFAAAAAQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAwAAAAAAAAAAAAAAAAAAAAMAAAAAAyD9KgAAAABmjS15AAAAAAAAAAEDIP5oAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABlgu/teRAgPKvAAD7A4AAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg/SoAAAAAZo0teQAAAAAAAAAAAAAAAA==',
                                           'fee_meta_xdr': 'AAAAAgAAAAMDIP5FAAAAAAAAAADOXZ0KszqkgqvIZZtQo3EdP6AsxrVLm5AJN687feIatwAAM47eicicAk808wAJfSEAAAACAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg/kUAAAAAZo0zywAAAAAAAAABAyD+aAAAAAAAAAAAzl2dCrM6pIKryGWbUKNxHT+gLMa1S5uQCTevO33iGrcAADOO3onIOAJPNPMACX0hAAAAAgAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAwAAAAADIP5FAAAAAGaNM8sAAAAA',
                                           'memo_type': 'text', 'signatures': [
                                              'doC7DJvegZxWyksNQtV5UE/lw66qzwRZU0q6peKZVW4TPp1k7zLkLlrCmHUHPl6Y82hSVC6HWLbMtogWHmeMAw=='],
                                           'valid_after': '1970-01-01T00:00:00Z',
                                           'valid_before': '2024-07-09T13:02:33Z',
                                           'preconditions': {
                                               'timebounds': {'min_time': '0', 'max_time': '1720530153'}}},
                                          {'memo': '325339001', '_links': {'self': {
                                              'href': 'https://horizon.stellar.org/transactions/4f0f55720a10c498ac57fe4fe10b0aca3da95217f26d1b65fd833a77a2edee7f'},
                                              'account': {
                                                  'href': 'https://horizon.stellar.org/accounts/GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5'},
                                              'ledger': {
                                                  'href': 'https://horizon.stellar.org/ledgers/52493610'},
                                              'operations': {
                                                  'href': 'https://horizon.stellar.org/transactions/4f0f55720a10c498ac57fe4fe10b0aca3da95217f26d1b65fd833a77a2edee7f/operations{?cursor,limit,order}',
                                                  'templated': True}, 'effects': {
                                                  'href': 'https://horizon.stellar.org/transactions/4f0f55720a10c498ac57fe4fe10b0aca3da95217f26d1b65fd833a77a2edee7f/effects{?cursor,limit,order}',
                                                  'templated': True}, 'precedes': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=asc&cursor=225458338199187456'},
                                              'succeeds': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=desc&cursor=225458338199187456'},
                                              'transaction': {
                                                  'href': 'https://horizon.stellar.org/transactions/4f0f55720a10c498ac57fe4fe10b0aca3da95217f26d1b65fd833a77a2edee7f'}},
                                           'id': '4f0f55720a10c498ac57fe4fe10b0aca3da95217f26d1b65fd833a77a2edee7f',
                                           'paging_token': '225458338199187456', 'successful': True,
                                           'hash': '4f0f55720a10c498ac57fe4fe10b0aca3da95217f26d1b65fd833a77a2edee7f',
                                           'ledger': 52493610, 'created_at': '2024-07-09T12:30:49Z',
                                           'source_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                                           'source_account_sequence': '145182521808907278',
                                           'fee_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                                           'fee_charged': '100', 'max_fee': '45000', 'operation_count': 1,
                                           'envelope_xdr': 'AAAAAgAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAAr8gCA8q8AAPsDgAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAATZEd5AAAAAQAAAAAAAAABAAAAAAJYIV7cdNJNLPz9/ZAMy3kUrWZ+3FoRNOyzWZrUVReUAAAAAAAAAAC/NjPYAAAAAAAAAALAanpFAAAAQIdHISueDi/McO2ioYurD9CCTOVzudrgxDntMePQDHcNMB/wPG1zkn0258uRMi0yfGFU1OimvMcYydlXLmdUzAV5dZunAAAAQPE44NP2dmtOxWSkNupTVCgSnIXLLQ8mpZrhtJjvs03wR3TAhH6dLSD08mezGSktgrf/YsHZtOq87DJ80iSc5wc=',
                                           'result_xdr': 'AAAAAAAAAGQAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAA=',
                                           'result_meta_xdr': 'AAAAAwAAAAAAAAACAAAAAwMg/SoAAAAAAAAAANJdnWDu5Lzz4a+ZqJ3dIG0+ciDA3gcjxGoGjhecW4aZAAAGWF/r8MYCA8q8AAPsDQAAAAMAAAAAAAAAAAAAAAliaXRnby5jb20AAAAAAQIDAAAAAwAAAAAdSLNvNcCEWpUM1sSHHJ9W/JqMWbz1rhA/Sl1QO+4C9AAAAAEAAAAAl5Ai6URIK1qSERKZFtKcPXz/BINreqBQEc2793l1m6cAAAABAAAAAK2xJjeRTZSyAkiROb5tk6y8FeWa/G6LumaboZvAanpFAAAAAQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAwAAAAAAAAAAAAAAAAAAAAMAAAAAAyD4UwAAAABmjRGWAAAAAAAAAAEDIP0qAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABlhf6/DGAgPKvAAD7A4AAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg/SoAAAAAZo0teQAAAAAAAAABAAAABAAAAAMDIP0qAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABlhf6/DGAgPKvAAD7A4AAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg/SoAAAAAZo0teQAAAAAAAAABAyD9KgAAAAAAAAAA0l2dYO7kvPPhr5mond0gbT5yIMDeByPEagaOF5xbhpkAAAZXoLW87gIDyrwAA+wOAAAAAwAAAAAAAAAAAAAACWJpdGdvLmNvbQAAAAABAgMAAAADAAAAAB1Is281wIRalQzWxIccn1b8moxZvPWuED9KXVA77gL0AAAAAQAAAACXkCLpREgrWpIREpkW0pw9fP8Eg2t6oFARzbv3eXWbpwAAAAEAAAAArbEmN5FNlLICSJE5vm2TrLwV5Zr8bou6Zpuhm8BqekUAAAABAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAADAAAAAAAAAAAAAAAAAAAAAwAAAAADIP0qAAAAAGaNLXkAAAAAAAAAAwMg/SQAAAAAAAAAAAJYIV7cdNJNLPz9/ZAMy3kUrWZ+3FoRNOyzWZrUVReUAAAAAAX14DgCm0CuAAJryQAAAAIAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAMAAAAAAyD9JAAAAABmjS1WAAAAAAAAAAEDIP0qAAAAAAAAAAACWCFe3HTSTSz8/f2QDMt5FK1mftxaETTss1ma1FUXlAAAAADFLBQQAptArgACa8kAAAACAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg/SQAAAAAZo0tVgAAAAAAAAAAAAAAAA==',
                                           'fee_meta_xdr': 'AAAAAgAAAAMDIPuuAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABlhf6/EqAgPKvAAD7A0AAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg+FMAAAAAZo0RlgAAAAAAAAABAyD9KgAAAAAAAAAA0l2dYO7kvPPhr5mond0gbT5yIMDeByPEagaOF5xbhpkAAAZYX+vwxgIDyrwAA+wNAAAAAwAAAAAAAAAAAAAACWJpdGdvLmNvbQAAAAABAgMAAAADAAAAAB1Is281wIRalQzWxIccn1b8moxZvPWuED9KXVA77gL0AAAAAQAAAACXkCLpREgrWpIREpkW0pw9fP8Eg2t6oFARzbv3eXWbpwAAAAEAAAAArbEmN5FNlLICSJE5vm2TrLwV5Zr8bou6Zpuhm8BqekUAAAABAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAADAAAAAAAAAAAAAAAAAAAAAwAAAAADIPhTAAAAAGaNEZYAAAAA',
                                           'memo_type': 'id', 'signatures': [
                                              'h0chK54OL8xw7aKhi6sP0IJM5XO52uDEOe0x49AMdw0wH/A8bXOSfTbny5EyLTJ8YVTU6Ka8xxjJ2VcuZ1TMBQ==',
                                              '8Tjg0/Z2a07FZKQ26lNUKBKchcstDyalmuG0mO+zTfBHdMCEfp0tIPTyZ7MZKS2Ct/9iwdm06rzsMnzSJJznBw=='],
                                           'valid_after': '1970-01-01T00:00:00Z',
                                           'preconditions': {'timebounds': {'min_time': '0'}}},
                                          {'memo': '47615', 'memo_bytes': 'NDc2MTU=', '_links': {'self': {
                                              'href': 'https://horizon.stellar.org/transactions/b55d9b5260dee2f1697ff998594e2a6e7e9b72e54b01367db1943f3dc7e47ad1'},
                                              'account': {
                                                  'href': 'https://horizon.stellar.org/accounts/GD3UAVRI2XHOUZHLKESHC7YQLQZEVUFD6NN45SOW72LEEQUL2XLJ5R5G'},
                                              'ledger': {
                                                  'href': 'https://horizon.stellar.org/ledgers/52493230'},
                                              'operations': {
                                                  'href': 'https://horizon.stellar.org/transactions/b55d9b5260dee2f1697ff998594e2a6e7e9b72e54b01367db1943f3dc7e47ad1/operations{?cursor,limit,order}',
                                                  'templated': True},
                                              'effects': {
                                                  'href': 'https://horizon.stellar.org/transactions/b55d9b5260dee2f1697ff998594e2a6e7e9b72e54b01367db1943f3dc7e47ad1/effects{?cursor,limit,order}',
                                                  'templated': True},
                                              'precedes': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=asc&cursor=225456706111410176'},
                                              'succeeds': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=desc&cursor=225456706111410176'},
                                              'transaction': {
                                                  'href': 'https://horizon.stellar.org/transactions/b55d9b5260dee2f1697ff998594e2a6e7e9b72e54b01367db1943f3dc7e47ad1'}},
                                           'id': 'b55d9b5260dee2f1697ff998594e2a6e7e9b72e54b01367db1943f3dc7e47ad1',
                                           'paging_token': '225456706111410176', 'successful': True,
                                           'hash': 'b55d9b5260dee2f1697ff998594e2a6e7e9b72e54b01367db1943f3dc7e47ad1',
                                           'ledger': 52493230, 'created_at': '2024-07-09T11:54:31Z',
                                           'source_account': 'GD3UAVRI2XHOUZHLKESHC7YQLQZEVUFD6NN45SOW72LEEQUL2XLJ5R5G',
                                           'source_account_sequence': '110149736295564533',
                                           'fee_account': 'GD3UAVRI2XHOUZHLKESHC7YQLQZEVUFD6NN45SOW72LEEQUL2XLJ5R5G',
                                           'fee_charged': '100', 'max_fee': '100', 'operation_count': 1,
                                           'envelope_xdr': 'AAAAAgAAAAD3QFYo1c7qZOtRJHF/EFwyStCj81vOydb+lkJCi9XWngAAAGQBh1SaAAAE9QAAAAEAAAAAAAAAAAAAAABmkbjVAAAAAQAAAAU0NzYxNQAAAAAAAAEAAAAAAAAAAQAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAAAAAAAAAYgs6S3gAAAAAAAAABi9XWngAAAEA7fiG1wVtbPFfNOPTq+ACkLQxShwEos+gvX5jZ0pxqW8Ygon1LTgQrYTB5T+li4tUNJTDFjb+qRrm4OA+JDccK',
                                           'result_xdr': 'AAAAAAAAAGQAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAA=',
                                           'result_meta_xdr': 'AAAAAwAAAAAAAAACAAAAAwMg+64AAAAAAAAAAPdAVijVzupk61EkcX8QXDJK0KPzW87J1v6WQkKL1daeAAAAKEY3NBEBh1SaAAAE9AAAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAMAAAAAAyDHfgAAAABmi/qtAAAAAAAAAAEDIPuuAAAAAAAAAAD3QFYo1c7qZOtRJHF/EFwyStCj81vOydb+lkJCi9XWngAAAChGNzQRAYdUmgAABPUAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg+64AAAAAZo0k9wAAAAAAAAABAAAABAAAAAMDIPuuAAAAAAAAAAD3QFYo1c7qZOtRJHF/EFwyStCj81vOydb+lkJCi9XWngAAAChGNzQRAYdUmgAABPUAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg+64AAAAAZo0k9wAAAAAAAAABAyD7rgAAAAAAAAAA90BWKNXO6mTrUSRxfxBcMkrQo/NbzsnW/pZCQovV1p4AAAAPw2ihMwGHVJoAAAT1AAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAwAAAAADIPuuAAAAAGaNJPcAAAAAAAAAAwMg+nEAAAAAAAAAANJdnWDu5Lzz4a+ZqJ3dIG0+ciDA3gcjxGoGjhecW4aZAAAGP90dXkwCA8q8AAPsDQAAAAMAAAAAAAAAAAAAAAliaXRnby5jb20AAAAAAQIDAAAAAwAAAAAdSLNvNcCEWpUM1sSHHJ9W/JqMWbz1rhA/Sl1QO+4C9AAAAAEAAAAAl5Ai6URIK1qSERKZFtKcPXz/BINreqBQEc2793l1m6cAAAABAAAAAK2xJjeRTZSyAkiROb5tk6y8FeWa/G6LumaboZvAanpFAAAAAQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAwAAAAAAAAAAAAAAAAAAAAMAAAAAAyD4UwAAAABmjRGWAAAAAAAAAAEDIPuuAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABlhf6/EqAgPKvAAD7A0AAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg+FMAAAAAZo0RlgAAAAAAAAAAAAAAAA==',
                                           'fee_meta_xdr': 'AAAAAgAAAAMDIMd+AAAAAAAAAAD3QFYo1c7qZOtRJHF/EFwyStCj81vOydb+lkJCi9XWngAAAChGNzR1AYdUmgAABPQAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMgx34AAAAAZov6rQAAAAAAAAABAyD7rgAAAAAAAAAA90BWKNXO6mTrUSRxfxBcMkrQo/NbzsnW/pZCQovV1p4AAAAoRjc0EQGHVJoAAAT0AAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAwAAAAADIMd+AAAAAGaL+q0AAAAA',
                                           'memo_type': 'text', 'signatures': [
                                              'O34htcFbWzxXzTj06vgApC0MUocBKLPoL1+Y2dKcalvGIKJ9S04EK2EweU/pYuLVDSUwxY2/qka5uDgPiQ3HCg=='],
                                           'valid_after': '1970-01-01T00:00:00Z',
                                           'valid_before': '2024-07-12T23:14:29Z',
                                           'preconditions': {
                                               'timebounds': {'min_time': '0', 'max_time': '1720826069'}}},
                                          {'memo': '158916', 'memo_bytes': 'MTU4OTE2', '_links': {'self': {
                                              'href': 'https://horizon.stellar.org/transactions/699ef2c2bb5653cc272fa75fe59e637f3dad22f03f3fcf011d4ebe85724d8c8a'},
                                              'account': {
                                                  'href': 'https://horizon.stellar.org/accounts/GD6RWYUQ6FWRBWFFA4HZVPCQUKGUIHZ4SL5G5GJU4HP3LKMYSUYAGBUA'},
                                              'ledger': {
                                                  'href': 'https://horizon.stellar.org/ledgers/52492913'},
                                              'operations': {
                                                  'href': 'https://horizon.stellar.org/transactions/699ef2c2bb5653cc272fa75fe59e637f3dad22f03f3fcf011d4ebe85724d8c8a/operations{?cursor,limit,order}',
                                                  'templated': True},
                                              'effects': {
                                                  'href': 'https://horizon.stellar.org/transactions/699ef2c2bb5653cc272fa75fe59e637f3dad22f03f3fcf011d4ebe85724d8c8a/effects{?cursor,limit,order}',
                                                  'templated': True},
                                              'precedes': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=asc&cursor=225455344607109120'},
                                              'succeeds': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=desc&cursor=225455344607109120'},
                                              'transaction': {
                                                  'href': 'https://horizon.stellar.org/transactions/699ef2c2bb5653cc272fa75fe59e637f3dad22f03f3fcf011d4ebe85724d8c8a'}},
                                           'id': '699ef2c2bb5653cc272fa75fe59e637f3dad22f03f3fcf011d4ebe85724d8c8a',
                                           'paging_token': '225455344607109120', 'successful': True,
                                           'hash': '699ef2c2bb5653cc272fa75fe59e637f3dad22f03f3fcf011d4ebe85724d8c8a',
                                           'ledger': 52492913, 'created_at': '2024-07-09T11:24:05Z',
                                           'source_account': 'GD6RWYUQ6FWRBWFFA4HZVPCQUKGUIHZ4SL5G5GJU4HP3LKMYSUYAGBUA',
                                           'source_account_sequence': '225406622497767442',
                                           'fee_account': 'GD6RWYUQ6FWRBWFFA4HZVPCQUKGUIHZ4SL5G5GJU4HP3LKMYSUYAGBUA',
                                           'fee_charged': '100', 'max_fee': '200001', 'operation_count': 1,
                                           'envelope_xdr': 'AAAAAgAAAAD9G2KQ8W0Q2KUHD5q8UKKNRB88kvpumTTh37WpmJUwAwADDUEDIM4hAAAAEgAAAAEAAAAAD73SGQAAAABmjUf8AAAAAQAAAAYxNTg5MTYAAAAAAAEAAAAAAAAAAQAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAAAAAAAAAAcGlnoAAAAAAAAAABmJUwAwAAAEBl/8xxBOm5V6g5O85hJr5mi4F7JyM3r6ilXlIlVNZhwOlAg0H0ul1fsZb+ADggEtDUIlIS9JoKKN+K6vVy84kA',
                                           'result_xdr': 'AAAAAAAAAGQAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAA=',
                                           'result_meta_xdr': 'AAAAAwAAAAAAAAACAAAAAwMg+nEAAAAAAAAAAP0bYpDxbRDYpQcPmrxQoo1EHzyS+m6ZNOHftamYlTADAAAUVmijBGsDIM4hAAAAEQAAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAMAAAAAAyD5LAAAAABmjRZ9AAAAAAAAAAEDIPpxAAAAAAAAAAD9G2KQ8W0Q2KUHD5q8UKKNRB88kvpumTTh37WpmJUwAwAAFFZoowRrAyDOIQAAABIAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg+nEAAAAAZo0d1QAAAAAAAAABAAAABAAAAAMDIPpxAAAAAAAAAAD9G2KQ8W0Q2KUHD5q8UKKNRB88kvpumTTh37WpmJUwAwAAFFZoowRrAyDOIQAAABIAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg+nEAAAAAZo0d1QAAAAAAAAABAyD6cQAAAAAAAAAA/RtikPFtENilBw+avFCijUQfPJL6bpk04d+1qZiVMAMAABRV+DmcywMgziEAAAASAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAwAAAAADIPpxAAAAAGaNHdUAAAAAAAAAAwMg+Q0AAAAAAAAAANJdnWDu5Lzz4a+ZqJ3dIG0+ciDA3gcjxGoGjhecW4aZAAAGP2yz9qwCA8q8AAPsDQAAAAMAAAAAAAAAAAAAAAliaXRnby5jb20AAAAAAQIDAAAAAwAAAAAdSLNvNcCEWpUM1sSHHJ9W/JqMWbz1rhA/Sl1QO+4C9AAAAAEAAAAAl5Ai6URIK1qSERKZFtKcPXz/BINreqBQEc2793l1m6cAAAABAAAAAK2xJjeRTZSyAkiROb5tk6y8FeWa/G6LumaboZvAanpFAAAAAQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAwAAAAAAAAAAAAAAAAAAAAMAAAAAAyD4UwAAAABmjRGWAAAAAAAAAAEDIPpxAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABj/dHV5MAgPKvAAD7A0AAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg+FMAAAAAZo0RlgAAAAAAAAAAAAAAAA==',
                                           'fee_meta_xdr': 'AAAAAgAAAAMDIPksAAAAAAAAAAD9G2KQ8W0Q2KUHD5q8UKKNRB88kvpumTTh37WpmJUwAwAAFFZoowTPAyDOIQAAABEAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg+SwAAAAAZo0WfQAAAAAAAAABAyD6cQAAAAAAAAAA/RtikPFtENilBw+avFCijUQfPJL6bpk04d+1qZiVMAMAABRWaKMEawMgziEAAAARAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAwAAAAADIPksAAAAAGaNFn0AAAAA',
                                           'memo_type': 'text', 'signatures': [
                                              'Zf/McQTpuVeoOTvOYSa+ZouBeycjN6+opV5SJVTWYcDpQINB9LpdX7GW/gA4IBLQ1CJSEvSaCijfiur1cvOJAA=='],
                                           'valid_after': '1978-05-15T16:38:49Z',
                                           'valid_before': '2024-07-09T14:23:56Z',
                                           'preconditions': {
                                               'timebounds': {'min_time': '264098329', 'max_time': '1720535036'}}},
                                          {'memo': '189947', 'memo_bytes': 'MTg5OTQ3', '_links': {'self': {
                                              'href': 'https://horizon.stellar.org/transactions/e2c24b3427e1d672b9ef2d9743a0ceb081c136e9e65565f976b68c1d35c350c9'},
                                              'account': {
                                                  'href': 'https://horizon.stellar.org/accounts/GC5LF63GRVIT5ZXXCXLPI3RX2YXKJQFZVBSAO6AUELN3YIMSWPD6Z6FH'},
                                              'ledger': {
                                                  'href': 'https://horizon.stellar.org/ledgers/52492557'},
                                              'operations': {
                                                  'href': 'https://horizon.stellar.org/transactions/e2c24b3427e1d672b9ef2d9743a0ceb081c136e9e65565f976b68c1d35c350c9/operations{?cursor,limit,order}',
                                                  'templated': True},
                                              'effects': {
                                                  'href': 'https://horizon.stellar.org/transactions/e2c24b3427e1d672b9ef2d9743a0ceb081c136e9e65565f976b68c1d35c350c9/effects{?cursor,limit,order}',
                                                  'templated': True},
                                              'precedes': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=asc&cursor=225453815598526464'},
                                              'succeeds': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=desc&cursor=225453815598526464'},
                                              'transaction': {
                                                  'href': 'https://horizon.stellar.org/transactions/e2c24b3427e1d672b9ef2d9743a0ceb081c136e9e65565f976b68c1d35c350c9'}},
                                           'id': 'e2c24b3427e1d672b9ef2d9743a0ceb081c136e9e65565f976b68c1d35c350c9',
                                           'paging_token': '225453815598526464', 'successful': True,
                                           'hash': 'e2c24b3427e1d672b9ef2d9743a0ceb081c136e9e65565f976b68c1d35c350c9',
                                           'ledger': 52492557, 'created_at': '2024-07-09T10:49:44Z',
                                           'source_account': 'GC5LF63GRVIT5ZXXCXLPI3RX2YXKJQFZVBSAO6AUELN3YIMSWPD6Z6FH',
                                           'source_account_sequence': '164213689401717304',
                                           'fee_account': 'GC5LF63GRVIT5ZXXCXLPI3RX2YXKJQFZVBSAO6AUELN3YIMSWPD6Z6FH',
                                           'fee_charged': '100', 'max_fee': '1000000', 'operation_count': 1,
                                           'envelope_xdr': 'AAAAAgAAAAC6svtmjVE+5vcV1vRuN9YupMC5qGQHeBQi27whkrPH7AAPQkACR2d7AAuyOAAAAAEAAAAAAAAAAAAAAABmjRYfAAAAAQAAAAYxODk5NDcAAAAAAAEAAAAAAAAAAQAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAAAAAAAAAASdrXAwAAAAAAAAABkrPH7AAAAEC8/GjkkvRv3beYCSmRvaSwsEbtTKYeqjQ81yHmF2C0/CJLt9OxWXGklIELsndq2EmKfQJL7St78hYzRXYsJnIE',
                                           'result_xdr': 'AAAAAAAAAGQAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAA=',
                                           'result_meta_xdr': 'AAAAAwAAAAAAAAACAAAAAwMg+Q0AAAAAAAAAALqy+2aNUT7m9xXW9G431i6kwLmoZAd4FCLbvCGSs8fsAAFsX0ClBN8CR2d7AAuyNwAAAAIAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAMAAAAAAyD5AQAAAABmjRWEAAAAAAAAAAEDIPkNAAAAAAAAAAC6svtmjVE+5vcV1vRuN9YupMC5qGQHeBQi27whkrPH7AABbF9ApQTfAkdnewALsjgAAAACAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg+Q0AAAAAZo0VyAAAAAAAAAABAAAABAAAAAMDIPkNAAAAAAAAAAC6svtmjVE+5vcV1vRuN9YupMC5qGQHeBQi27whkrPH7AABbF9ApQTfAkdnewALsjgAAAACAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg+Q0AAAAAZo0VyAAAAAAAAAABAyD5DQAAAAAAAAAAurL7Zo1RPub3Fdb0bjfWLqTAuahkB3gUItu8IZKzx+wAAWxe9sot3AJHZ3sAC7I4AAAAAgAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAwAAAAADIPkNAAAAAGaNFcgAAAAAAAAAAwMg+FMAAAAAAAAAANJdnWDu5Lzz4a+ZqJ3dIG0+ciDA3gcjxGoGjhecW4aZAAAGPyLZH6kCA8q8AAPsDQAAAAMAAAAAAAAAAAAAAAliaXRnby5jb20AAAAAAQIDAAAAAwAAAAAdSLNvNcCEWpUM1sSHHJ9W/JqMWbz1rhA/Sl1QO+4C9AAAAAEAAAAAl5Ai6URIK1qSERKZFtKcPXz/BINreqBQEc2793l1m6cAAAABAAAAAK2xJjeRTZSyAkiROb5tk6y8FeWa/G6LumaboZvAanpFAAAAAQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAwAAAAAAAAAAAAAAAAAAAAMAAAAAAyD4UwAAAABmjRGWAAAAAAAAAAEDIPkNAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABj9ss/asAgPKvAAD7A0AAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg+FMAAAAAZo0RlgAAAAAAAAAAAAAAAA==',
                                           'fee_meta_xdr': 'AAAAAgAAAAMDIPkBAAAAAAAAAAC6svtmjVE+5vcV1vRuN9YupMC5qGQHeBQi27whkrPH7AABbF9ApQVDAkdnewALsjcAAAACAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg+QEAAAAAZo0VhAAAAAAAAAABAyD5DQAAAAAAAAAAurL7Zo1RPub3Fdb0bjfWLqTAuahkB3gUItu8IZKzx+wAAWxfQKUE3wJHZ3sAC7I3AAAAAgAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAwAAAAADIPkBAAAAAGaNFYQAAAAA',
                                           'memo_type': 'text', 'signatures': [
                                              'vPxo5JL0b923mAkpkb2ksLBG7UymHqo0PNch5hdgtPwiS7fTsVlxpJSBC7J3athJin0CS+0re/IWM0V2LCZyBA=='],
                                           'valid_after': '1970-01-01T00:00:00Z',
                                           'valid_before': '2024-07-09T10:51:11Z',
                                           'preconditions': {
                                               'timebounds': {'min_time': '0', 'max_time': '1720522271'}}},
                                          {'memo': '6060175', '_links': {'self': {
                                              'href': 'https://horizon.stellar.org/transactions/2b8d863e4e03ec4c3643821babc67ef32c06dc349081ad74ff4eef8872cf1288'},
                                              'account': {
                                                  'href': 'https://horizon.stellar.org/accounts/GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5'},
                                              'ledger': {
                                                  'href': 'https://horizon.stellar.org/ledgers/52492371'},
                                              'operations': {
                                                  'href': 'https://horizon.stellar.org/transactions/2b8d863e4e03ec4c3643821babc67ef32c06dc349081ad74ff4eef8872cf1288/operations{?cursor,limit,order}',
                                                  'templated': True}, 'effects': {
                                                  'href': 'https://horizon.stellar.org/transactions/2b8d863e4e03ec4c3643821babc67ef32c06dc349081ad74ff4eef8872cf1288/effects{?cursor,limit,order}',
                                                  'templated': True}, 'precedes': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=asc&cursor=225453016734818304'},
                                              'succeeds': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=desc&cursor=225453016734818304'},
                                              'transaction': {
                                                  'href': 'https://horizon.stellar.org/transactions/2b8d863e4e03ec4c3643821babc67ef32c06dc349081ad74ff4eef8872cf1288'}},
                                           'id': '2b8d863e4e03ec4c3643821babc67ef32c06dc349081ad74ff4eef8872cf1288',
                                           'paging_token': '225453016734818304', 'successful': True,
                                           'hash': '2b8d863e4e03ec4c3643821babc67ef32c06dc349081ad74ff4eef8872cf1288',
                                           'ledger': 52492371, 'created_at': '2024-07-09T10:31:50Z',
                                           'source_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                                           'source_account_sequence': '145182521808907277',
                                           'fee_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                                           'fee_charged': '100', 'max_fee': '45000', 'operation_count': 1,
                                           'envelope_xdr': 'AAAAAgAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAAr8gCA8q8AAPsDQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAXHiPAAAAAQAAAAAAAAABAAAAAEyEaF9nJuILTKgzg25xKzYJiESwGybyGwHJfbYqukVcAAAAAAAAAAAaLJeuAAAAAAAAAALAanpFAAAAQPwxPIQnwWiICy8Ek99U7duEY5jB2PXPqlzNcrIWYnJRrRIrlfXf2jJW69zIyr+QfmdSi/6eKFr+H5EQwCnqHwx5dZunAAAAQO0VerBa1ONQSbLVSezXK4u5bV0xEUtCCyHkpe/FlNPg15Fz97WVqX7szKSZmus1G5ONCwQ1g3QcL0lt9ZbXow8=',
                                           'result_xdr': 'AAAAAAAAAGQAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAA=',
                                           'result_meta_xdr': 'AAAAAwAAAAAAAAACAAAAAwMg+FMAAAAAAAAAANJdnWDu5Lzz4a+ZqJ3dIG0+ciDA3gcjxGoGjhecW4aZAAAGPz0Ft1cCA8q8AAPsDAAAAAMAAAAAAAAAAAAAAAliaXRnby5jb20AAAAAAQIDAAAAAwAAAAAdSLNvNcCEWpUM1sSHHJ9W/JqMWbz1rhA/Sl1QO+4C9AAAAAEAAAAAl5Ai6URIK1qSERKZFtKcPXz/BINreqBQEc2793l1m6cAAAABAAAAAK2xJjeRTZSyAkiROb5tk6y8FeWa/G6LumaboZvAanpFAAAAAQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAwAAAAAAAAAAAAAAAAAAAAMAAAAAAyD0hAAAAABmjPueAAAAAAAAAAEDIPhTAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABj89BbdXAgPKvAAD7A0AAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg+FMAAAAAZo0RlgAAAAAAAAABAAAABAAAAAMDIPhTAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABj89BbdXAgPKvAAD7A0AAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg+FMAAAAAZo0RlgAAAAAAAAABAyD4UwAAAAAAAAAA0l2dYO7kvPPhr5mond0gbT5yIMDeByPEagaOF5xbhpkAAAY/ItkfqQIDyrwAA+wNAAAAAwAAAAAAAAAAAAAACWJpdGdvLmNvbQAAAAABAgMAAAADAAAAAB1Is281wIRalQzWxIccn1b8moxZvPWuED9KXVA77gL0AAAAAQAAAACXkCLpREgrWpIREpkW0pw9fP8Eg2t6oFARzbv3eXWbpwAAAAEAAAAArbEmN5FNlLICSJE5vm2TrLwV5Zr8bou6Zpuhm8BqekUAAAABAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAADAAAAAAAAAAAAAAAAAAAAAwAAAAADIPhTAAAAAGaNEZYAAAAAAAAAAwMg+EYAAAAAAAAAAEyEaF9nJuILTKgzg25xKzYJiESwGybyGwHJfbYqukVcAAL84HSz4pIBJ4IvAAOC8QAAAAQAAAAAAAAAAAAAAAABAQICAAAAAQAAAACx2lbjiqiaTYYG+t+y+IosiUQNuQTPtzzTwV9vwgf1hgAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAEAAAAAAAAAAwAAAAAC1ljkAAAAAGTVpPoAAAAAAAAAAQMg+FMAAAAAAAAAAEyEaF9nJuILTKgzg25xKzYJiESwGybyGwHJfbYqukVcAAL84I7gekABJ4IvAAOC8QAAAAQAAAAAAAAAAAAAAAABAQICAAAAAQAAAACx2lbjiqiaTYYG+t+y+IosiUQNuQTPtzzTwV9vwgf1hgAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAEAAAAAAAAAAwAAAAAC1ljkAAAAAGTVpPoAAAAAAAAAAAAAAAA=',
                                           'fee_meta_xdr': 'AAAAAgAAAAMDIPYKAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABj89Bbe7AgPKvAAD7AwAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg9IQAAAAAZoz7ngAAAAAAAAABAyD4UwAAAAAAAAAA0l2dYO7kvPPhr5mond0gbT5yIMDeByPEagaOF5xbhpkAAAY/PQW3VwIDyrwAA+wMAAAAAwAAAAAAAAAAAAAACWJpdGdvLmNvbQAAAAABAgMAAAADAAAAAB1Is281wIRalQzWxIccn1b8moxZvPWuED9KXVA77gL0AAAAAQAAAACXkCLpREgrWpIREpkW0pw9fP8Eg2t6oFARzbv3eXWbpwAAAAEAAAAArbEmN5FNlLICSJE5vm2TrLwV5Zr8bou6Zpuhm8BqekUAAAABAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAADAAAAAAAAAAAAAAAAAAAAAwAAAAADIPSEAAAAAGaM+54AAAAA',
                                           'memo_type': 'id', 'signatures': [
                                              '/DE8hCfBaIgLLwST31Tt24RjmMHY9c+qXM1yshZiclGtEiuV9d/aMlbr3MjKv5B+Z1KL/p4oWv4fkRDAKeofDA==',
                                              '7RV6sFrU41BJstVJ7Ncri7ltXTERS0ILIeSl78WU0+DXkXP3tZWpfuzMpJma6zUbk40LBDWDdBwvSW31ltejDw=='],
                                           'valid_after': '1970-01-01T00:00:00Z',
                                           'preconditions': {'timebounds': {'min_time': '0'}}},
                                          {'memo': '203684', 'memo_bytes': 'MjAzNjg0', '_links': {'self': {
                                              'href': 'https://horizon.stellar.org/transactions/453b8129f35cd0d7dc469db0f5468ad3e80ab84ac8041ce3e11b9284bf366083'},
                                              'account': {
                                                  'href': 'https://horizon.stellar.org/accounts/GBALLUSPAPYHIJFYVSAH3O6LUARQK2T6BCOIN5HG7HMLROBDGHYBBAVV'},
                                              'ledger': {
                                                  'href': 'https://horizon.stellar.org/ledgers/52491786'},
                                              'operations': {
                                                  'href': 'https://horizon.stellar.org/transactions/453b8129f35cd0d7dc469db0f5468ad3e80ab84ac8041ce3e11b9284bf366083/operations{?cursor,limit,order}',
                                                  'templated': True},
                                              'effects': {
                                                  'href': 'https://horizon.stellar.org/transactions/453b8129f35cd0d7dc469db0f5468ad3e80ab84ac8041ce3e11b9284bf366083/effects{?cursor,limit,order}',
                                                  'templated': True},
                                              'precedes': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=asc&cursor=225450504178843648'},
                                              'succeeds': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=desc&cursor=225450504178843648'},
                                              'transaction': {
                                                  'href': 'https://horizon.stellar.org/transactions/453b8129f35cd0d7dc469db0f5468ad3e80ab84ac8041ce3e11b9284bf366083'}},
                                           'id': '453b8129f35cd0d7dc469db0f5468ad3e80ab84ac8041ce3e11b9284bf366083',
                                           'paging_token': '225450504178843648', 'successful': True,
                                           'hash': '453b8129f35cd0d7dc469db0f5468ad3e80ab84ac8041ce3e11b9284bf366083',
                                           'ledger': 52491786, 'created_at': '2024-07-09T09:35:18Z',
                                           'source_account': 'GBALLUSPAPYHIJFYVSAH3O6LUARQK2T6BCOIN5HG7HMLROBDGHYBBAVV',
                                           'source_account_sequence': '159807439502353920',
                                           'fee_account': 'GBALLUSPAPYHIJFYVSAH3O6LUARQK2T6BCOIN5HG7HMLROBDGHYBBAVV',
                                           'fee_charged': '100', 'max_fee': '10000', 'operation_count': 1,
                                           'envelope_xdr': 'AAAAAgAAAABAtdJPA/B0JLisgH27y6AjBWp+CJyG9Ob52Li4IzHwEAAAJxACN8AFAACmAAAAAAEAAAAAAAAAAAAAAABmjQUIAAAAAQAAAAYyMDM2ODQAAAAAAAEAAAAAAAAAAQAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAAAAAAAAAAV55rgAAAAAAAAAABIzHwEAAAAEAC4/9k+aeAASeA7UJQ1iLYrINXt5mwwq4MRo/WRWAaikhIziRBpsWBGonjqbhV2CKQpYsUMMyAd4QiS7AG0g0A',
                                           'result_xdr': 'AAAAAAAAAGQAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAA=',
                                           'result_meta_xdr': 'AAAAAwAAAAAAAAACAAAAAwMg9goAAAAAAAAAAEC10k8D8HQkuKyAfbvLoCMFan4InIb05vnYuLgjMfAQAAAQBOlpYQsCN8AFAACl/wAAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAMAAAAAAyD1zwAAAABmjQMDAAAAAAAAAAEDIPYKAAAAAAAAAABAtdJPA/B0JLisgH27y6AjBWp+CJyG9Ob52Li4IzHwEAAAEATpaWELAjfABQAApgAAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg9goAAAAAZo0EVgAAAAAAAAABAAAABAAAAAMDIPYKAAAAAAAAAABAtdJPA/B0JLisgH27y6AjBWp+CJyG9Ob52Li4IzHwEAAAEATpaWELAjfABQAApgAAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg9goAAAAAZo0EVgAAAAAAAAABAyD2CgAAAAAAAAAAQLXSTwPwdCS4rIB9u8ugIwVqfgichvTm+di4uCMx8BAAABAEkcr1iwI3wAUAAKYAAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAwAAAAADIPYKAAAAAGaNBFYAAAAAAAAAAwMg9IQAAAAAAAAAANJdnWDu5Lzz4a+ZqJ3dIG0+ciDA3gcjxGoGjhecW4aZAAAGPuVnTDsCA8q8AAPsDAAAAAMAAAAAAAAAAAAAAAliaXRnby5jb20AAAAAAQIDAAAAAwAAAAAdSLNvNcCEWpUM1sSHHJ9W/JqMWbz1rhA/Sl1QO+4C9AAAAAEAAAAAl5Ai6URIK1qSERKZFtKcPXz/BINreqBQEc2793l1m6cAAAABAAAAAK2xJjeRTZSyAkiROb5tk6y8FeWa/G6LumaboZvAanpFAAAAAQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAwAAAAAAAAAAAAAAAAAAAAMAAAAAAyD0hAAAAABmjPueAAAAAAAAAAEDIPYKAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABj89Bbe7AgPKvAAD7AwAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg9IQAAAAAZoz7ngAAAAAAAAAAAAAAAA==',
                                           'fee_meta_xdr': 'AAAAAgAAAAMDIPXPAAAAAAAAAABAtdJPA/B0JLisgH27y6AjBWp+CJyG9Ob52Li4IzHwEAAAEATpaWFvAjfABQAApf8AAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg9c8AAAAAZo0DAwAAAAAAAAABAyD2CgAAAAAAAAAAQLXSTwPwdCS4rIB9u8ugIwVqfgichvTm+di4uCMx8BAAABAE6WlhCwI3wAUAAKX/AAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAwAAAAADIPXPAAAAAGaNAwMAAAAA',
                                           'memo_type': 'text', 'signatures': [
                                              'AuP/ZPmngAEngO1CUNYi2KyDV7eZsMKuDEaP1kVgGopISM4kQabFgRqJ46m4VdgikKWLFDDMgHeEIkuwBtINAA=='],
                                           'valid_after': '1970-01-01T00:00:00Z',
                                           'valid_before': '2024-07-09T09:38:16Z',
                                           'preconditions': {
                                               'timebounds': {'min_time': '0', 'max_time': '1720517896'}}},
                                          {'memo': '3427155930', '_links': {'self': {
                                              'href': 'https://horizon.stellar.org/transactions/f5f3d8967bfdd88a82c26df8511482a230eec924d4747c71f473c0aacc9d3f6e'},
                                              'account': {
                                                  'href': 'https://horizon.stellar.org/accounts/GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5'},
                                              'ledger': {
                                                  'href': 'https://horizon.stellar.org/ledgers/52491396'},
                                              'operations': {
                                                  'href': 'https://horizon.stellar.org/transactions/f5f3d8967bfdd88a82c26df8511482a230eec924d4747c71f473c0aacc9d3f6e/operations{?cursor,limit,order}',
                                                  'templated': True}, 'effects': {
                                                  'href': 'https://horizon.stellar.org/transactions/f5f3d8967bfdd88a82c26df8511482a230eec924d4747c71f473c0aacc9d3f6e/effects{?cursor,limit,order}',
                                                  'templated': True}, 'precedes': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=asc&cursor=225448829142036480'},
                                              'succeeds': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=desc&cursor=225448829142036480'},
                                              'transaction': {
                                                  'href': 'https://horizon.stellar.org/transactions/f5f3d8967bfdd88a82c26df8511482a230eec924d4747c71f473c0aacc9d3f6e'}},
                                           'id': 'f5f3d8967bfdd88a82c26df8511482a230eec924d4747c71f473c0aacc9d3f6e',
                                           'paging_token': '225448829142036480', 'successful': True,
                                           'hash': 'f5f3d8967bfdd88a82c26df8511482a230eec924d4747c71f473c0aacc9d3f6e',
                                           'ledger': 52491396, 'created_at': '2024-07-09T08:58:06Z',
                                           'source_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                                           'source_account_sequence': '145182521808907276',
                                           'fee_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                                           'fee_charged': '100', 'max_fee': '45000', 'operation_count': 1,
                                           'envelope_xdr': 'AAAAAgAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAAr8gCA8q8AAPsDAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAADMRj/aAAAAAQAAAAAAAAABAAAAAP0bYpDxbRDYpQcPmrxQoo1EHzyS+m6ZNOHftamYlTADAAAAAAAAAAAUBzBnAAAAAAAAAALAanpFAAAAQDvuhnMICNXIoDOgSo/6FIQ3o5t4PZE5zm8t1/Tk+gwubxR91em7Bj7dpxh00YfNvlHtRrCLFa2e1rX3bLa5eQR5dZunAAAAQMhYhCu7+sHoFNLFBcazvmL7xJ6byZkS/1m6BTZDsUywpo6m2VDPQeP9N8YNFcPLb8iAPXA36LaaWI7atzmi0Ac=',
                                           'result_xdr': 'AAAAAAAAAGQAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAA=',
                                           'result_meta_xdr': 'AAAAAwAAAAAAAAACAAAAAwMg9IQAAAAAAAAAANJdnWDu5Lzz4a+ZqJ3dIG0+ciDA3gcjxGoGjhecW4aZAAAGPvlufKICA8q8AAPsCwAAAAMAAAAAAAAAAAAAAAliaXRnby5jb20AAAAAAQIDAAAAAwAAAAAdSLNvNcCEWpUM1sSHHJ9W/JqMWbz1rhA/Sl1QO+4C9AAAAAEAAAAAl5Ai6URIK1qSERKZFtKcPXz/BINreqBQEc2793l1m6cAAAABAAAAAK2xJjeRTZSyAkiROb5tk6y8FeWa/G6LumaboZvAanpFAAAAAQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAwAAAAAAAAAAAAAAAAAAAAMAAAAAAyDwiQAAAABmjOT3AAAAAAAAAAEDIPSEAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABj75bnyiAgPKvAAD7AwAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg9IQAAAAAZoz7ngAAAAAAAAABAAAABAAAAAMDIPSEAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABj75bnyiAgPKvAAD7AwAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg9IQAAAAAZoz7ngAAAAAAAAABAyD0hAAAAAAAAAAA0l2dYO7kvPPhr5mond0gbT5yIMDeByPEagaOF5xbhpkAAAY+5WdMOwIDyrwAA+wMAAAAAwAAAAAAAAAAAAAACWJpdGdvLmNvbQAAAAABAgMAAAADAAAAAB1Is281wIRalQzWxIccn1b8moxZvPWuED9KXVA77gL0AAAAAQAAAACXkCLpREgrWpIREpkW0pw9fP8Eg2t6oFARzbv3eXWbpwAAAAEAAAAArbEmN5FNlLICSJE5vm2TrLwV5Zr8bou6Zpuhm8BqekUAAAABAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAADAAAAAAAAAAAAAAAAAAAAAwAAAAADIPSEAAAAAGaM+54AAAAAAAAAAwMg8+EAAAAAAAAAAP0bYpDxbRDYpQcPmrxQoo1EHzyS+m6ZNOHftamYlTADAAAUVu9VltgDIM4hAAAADwAAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAMAAAAAAyDz4QAAAABmjPf9AAAAAAAAAAEDIPSEAAAAAAAAAAD9G2KQ8W0Q2KUHD5q8UKKNRB88kvpumTTh37WpmJUwAwAAFFcDXMc/AyDOIQAAAA8AAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg8+EAAAAAZoz3/QAAAAAAAAAAAAAAAA==',
                                           'fee_meta_xdr': 'AAAAAgAAAAMDIPNWAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABj75bn0GAgPKvAAD7AsAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg8IkAAAAAZozk9wAAAAAAAAABAyD0hAAAAAAAAAAA0l2dYO7kvPPhr5mond0gbT5yIMDeByPEagaOF5xbhpkAAAY++W58ogIDyrwAA+wLAAAAAwAAAAAAAAAAAAAACWJpdGdvLmNvbQAAAAABAgMAAAADAAAAAB1Is281wIRalQzWxIccn1b8moxZvPWuED9KXVA77gL0AAAAAQAAAACXkCLpREgrWpIREpkW0pw9fP8Eg2t6oFARzbv3eXWbpwAAAAEAAAAArbEmN5FNlLICSJE5vm2TrLwV5Zr8bou6Zpuhm8BqekUAAAABAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAADAAAAAAAAAAAAAAAAAAAAAwAAAAADIPCJAAAAAGaM5PcAAAAA',
                                           'memo_type': 'id', 'signatures': [
                                              'O+6GcwgI1cigM6BKj/oUhDejm3g9kTnOby3X9OT6DC5vFH3V6bsGPt2nGHTRh82+Ue1GsIsVrZ7Wtfdstrl5BA==',
                                              'yFiEK7v6wegU0sUFxrO+YvvEnpvJmRL/WboFNkOxTLCmjqbZUM9B4/03xg0Vw8tvyIA9cDfotppYjtq3OaLQBw=='],
                                           'valid_after': '1970-01-01T00:00:00Z',
                                           'preconditions': {'timebounds': {'min_time': '0'}}},
                                          {'memo': '39265', 'memo_bytes': 'MzkyNjU=', '_links': {'self': {
                                              'href': 'https://horizon.stellar.org/transactions/2700b7ee302e13f4500e3e85a6fec00c30299841638417505296b74885af233e'},
                                              'account': {
                                                  'href': 'https://horizon.stellar.org/accounts/GBGHMELHHVTB6EQ5TNERZWPGFURADVSO6RW5PNNMRDMG55E74UBER45I'},
                                              'ledger': {
                                                  'href': 'https://horizon.stellar.org/ledgers/52491094'},
                                              'operations': {
                                                  'href': 'https://horizon.stellar.org/transactions/2700b7ee302e13f4500e3e85a6fec00c30299841638417505296b74885af233e/operations{?cursor,limit,order}',
                                                  'templated': True},
                                              'effects': {
                                                  'href': 'https://horizon.stellar.org/transactions/2700b7ee302e13f4500e3e85a6fec00c30299841638417505296b74885af233e/effects{?cursor,limit,order}',
                                                  'templated': True},
                                              'precedes': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=asc&cursor=225447532061687808'},
                                              'succeeds': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=desc&cursor=225447532061687808'},
                                              'transaction': {
                                                  'href': 'https://horizon.stellar.org/transactions/2700b7ee302e13f4500e3e85a6fec00c30299841638417505296b74885af233e'}},
                                           'id': '2700b7ee302e13f4500e3e85a6fec00c30299841638417505296b74885af233e',
                                           'paging_token': '225447532061687808', 'successful': True,
                                           'hash': '2700b7ee302e13f4500e3e85a6fec00c30299841638417505296b74885af233e',
                                           'ledger': 52491094, 'created_at': '2024-07-09T08:29:31Z',
                                           'source_account': 'GBGHMELHHVTB6EQ5TNERZWPGFURADVSO6RW5PNNMRDMG55E74UBER45I',
                                           'source_account_sequence': '193165312324012076',
                                           'fee_account': 'GBGHMELHHVTB6EQ5TNERZWPGFURADVSO6RW5PNNMRDMG55E74UBER45I',
                                           'fee_charged': '100', 'max_fee': '150', 'operation_count': 1,
                                           'envelope_xdr': 'AAAAAgAAAABMdhFnPWYfEh2bSRzZ5i0iAdZO9G3XtayI2G70n+UCSAAAAJYCrkLUAAAILAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAUzOTI2NQAAAAAAAAEAAAAAAAAAAQAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAAAAAAAAAAQvaZ5gAAAAAAAAABn+UCSAAAAEAQXzd3KxuM2P9//t0pNUnUeIV1qoItTC/pscoy02UtnnqLRJ19grtPOdhD6UL1Zp+FL73jiVIAVwkH1nIK0IYJ',
                                           'result_xdr': 'AAAAAAAAAGQAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAA=',
                                           'result_meta_xdr': 'AAAAAwAAAAAAAAACAAAAAwMg81YAAAAAAAAAAEx2EWc9Zh8SHZtJHNnmLSIB1k70bde1rIjYbvSf5QJIAAAMJKRUaO8CrkLUAAAIKwAAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAMAAAAAAyDrAAAAAABmjMVnAAAAAAAAAAEDIPNWAAAAAAAAAABMdhFnPWYfEh2bSRzZ5i0iAdZO9G3XtayI2G70n+UCSAAADCSkVGjvAq5C1AAACCwAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg81YAAAAAZoz06wAAAAAAAAABAAAABAAAAAMDIPNWAAAAAAAAAABMdhFnPWYfEh2bSRzZ5i0iAdZO9G3XtayI2G70n+UCSAAADCSkVGjvAq5C1AAACCwAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg81YAAAAAZoz06wAAAAAAAAABAyDzVgAAAAAAAAAATHYRZz1mHxIdm0kc2eYtIgHWTvRt17WsiNhu9J/lAkgAAAwkYV3PCQKuQtQAAAgsAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAwAAAAADIPNWAAAAAGaM9OsAAAAAAAAAAwMg8IkAAAAAAAAAANJdnWDu5Lzz4a+ZqJ3dIG0+ciDA3gcjxGoGjhecW4aZAAAGPrZ34yACA8q8AAPsCwAAAAMAAAAAAAAAAAAAAAliaXRnby5jb20AAAAAAQIDAAAAAwAAAAAdSLNvNcCEWpUM1sSHHJ9W/JqMWbz1rhA/Sl1QO+4C9AAAAAEAAAAAl5Ai6URIK1qSERKZFtKcPXz/BINreqBQEc2793l1m6cAAAABAAAAAK2xJjeRTZSyAkiROb5tk6y8FeWa/G6LumaboZvAanpFAAAAAQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAwAAAAAAAAAAAAAAAAAAAAMAAAAAAyDwiQAAAABmjOT3AAAAAAAAAAEDIPNWAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABj75bn0GAgPKvAAD7AsAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg8IkAAAAAZozk9wAAAAAAAAAAAAAAAA==',
                                           'fee_meta_xdr': 'AAAAAgAAAAMDIOsAAAAAAAAAAABMdhFnPWYfEh2bSRzZ5i0iAdZO9G3XtayI2G70n+UCSAAADCSkVGlTAq5C1AAACCsAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg6wAAAAAAZozFZwAAAAAAAAABAyDzVgAAAAAAAAAATHYRZz1mHxIdm0kc2eYtIgHWTvRt17WsiNhu9J/lAkgAAAwkpFRo7wKuQtQAAAgrAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAwAAAAADIOsAAAAAAGaMxWcAAAAA',
                                           'memo_type': 'text', 'signatures': [
                                              'EF83dysbjNj/f/7dKTVJ1HiFdaqCLUwv6bHKMtNlLZ56i0SdfYK7TznYQ+lC9WafhS+944lSAFcJB9ZyCtCGCQ=='],
                                           'valid_after': '1970-01-01T00:00:00Z',
                                           'preconditions': {'timebounds': {'min_time': '0'}}},
                                          {'memo': '44b1cce539d53d7f20', 'memo_bytes': 'NDRiMWNjZTUzOWQ1M2Q3ZjIw',
                                           '_links': {'self': {
                                               'href': 'https://horizon.stellar.org/transactions/5c276d28aa3468bac79d7d0fa793abf807e996e0877ae4c97c46b2f8d21f347b'},
                                               'account': {
                                                   'href': 'https://horizon.stellar.org/accounts/GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5'},
                                               'ledger': {'href': 'https://horizon.stellar.org/ledgers/52490377'},
                                               'operations': {
                                                   'href': 'https://horizon.stellar.org/transactions/5c276d28aa3468bac79d7d0fa793abf807e996e0877ae4c97c46b2f8d21f347b/operations{?cursor,limit,order}',
                                                   'templated': True}, 'effects': {
                                                   'href': 'https://horizon.stellar.org/transactions/5c276d28aa3468bac79d7d0fa793abf807e996e0877ae4c97c46b2f8d21f347b/effects{?cursor,limit,order}',
                                                   'templated': True}, 'precedes': {
                                                   'href': 'https://horizon.stellar.org/transactions?order=asc&cursor=225444452570337280'},
                                               'succeeds': {
                                                   'href': 'https://horizon.stellar.org/transactions?order=desc&cursor=225444452570337280'},
                                               'transaction': {
                                                   'href': 'https://horizon.stellar.org/transactions/5c276d28aa3468bac79d7d0fa793abf807e996e0877ae4c97c46b2f8d21f347b'}},
                                           'id': '5c276d28aa3468bac79d7d0fa793abf807e996e0877ae4c97c46b2f8d21f347b',
                                           'paging_token': '225444452570337280', 'successful': True,
                                           'hash': '5c276d28aa3468bac79d7d0fa793abf807e996e0877ae4c97c46b2f8d21f347b',
                                           'ledger': 52490377, 'created_at': '2024-07-09T07:21:27Z',
                                           'source_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                                           'source_account_sequence': '145182521808907275',
                                           'fee_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                                           'fee_charged': '100', 'max_fee': '45000', 'operation_count': 1,
                                           'envelope_xdr': 'AAAAAgAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAAr8gCA8q8AAPsCwAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAQAAABI0NGIxY2NlNTM5ZDUzZDdmMjAAAAAAAAEAAAAAAAAAAQAAAAAs+Z8e1vZo2zn6bjZW46DFWFaw1K4pTNuOxNf1cHjAdgAAAAAAAAB0alKIAAAAAAAAAAACwGp6RQAAAEB1KAVgwgS78wAs5sksihGqpgBEMVAxcsn8uHo9PoXXSyhJOLFtcuTlCFhvExxts2qu2encC95WWmPHod/rf5cMeXWbpwAAAEA/VmVIguIrjMmdf5t3MBd8sUfCrZgVqYIqRGvUU9QKigk+fnbgGwbhwSapdhLZJqr1LcQqsHC1e5XZpZPxG3gA',
                                           'result_xdr': 'AAAAAAAAAGQAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAA=',
                                           'result_meta_xdr': 'AAAAAwAAAAAAAAACAAAAAwMg8IkAAAAAAAAAANJdnWDu5Lzz4a+ZqJ3dIG0+ciDA3gcjxGoGjhecW4aZAAAGsyDKayACA8q8AAPsCgAAAAMAAAAAAAAAAAAAAAliaXRnby5jb20AAAAAAQIDAAAAAwAAAAAdSLNvNcCEWpUM1sSHHJ9W/JqMWbz1rhA/Sl1QO+4C9AAAAAEAAAAAl5Ai6URIK1qSERKZFtKcPXz/BINreqBQEc2793l1m6cAAAABAAAAAK2xJjeRTZSyAkiROb5tk6y8FeWa/G6LumaboZvAanpFAAAAAQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAwAAAAAAAAAAAAAAAAAAAAMAAAAAAyDwfwAAAABmjOS+AAAAAAAAAAEDIPCJAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABrMgymsgAgPKvAAD7AsAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg8IkAAAAAZozk9wAAAAAAAAABAAAABAAAAAMDIPCJAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABrMgymsgAgPKvAAD7AsAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg8IkAAAAAZozk9wAAAAAAAAABAyDwiQAAAAAAAAAA0l2dYO7kvPPhr5mond0gbT5yIMDeByPEagaOF5xbhpkAAAY+tnfjIAIDyrwAA+wLAAAAAwAAAAAAAAAAAAAACWJpdGdvLmNvbQAAAAABAgMAAAADAAAAAB1Is281wIRalQzWxIccn1b8moxZvPWuED9KXVA77gL0AAAAAQAAAACXkCLpREgrWpIREpkW0pw9fP8Eg2t6oFARzbv3eXWbpwAAAAEAAAAArbEmN5FNlLICSJE5vm2TrLwV5Zr8bou6Zpuhm8BqekUAAAABAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAADAAAAAAAAAAAAAAAAAAAAAwAAAAADIPCJAAAAAGaM5PcAAAAAAAAAAwMg2vgAAAAAAAAAACz5nx7W9mjbOfpuNlbjoMVYVrDUrilM247E1/VweMB2AACrZ2ohwb4BCsyFAAD2/wAAAAIAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAMAAAAAAyDYSQAAAABmjFpaAAAAAAAAAAEDIPCJAAAAAAAAAAAs+Z8e1vZo2zn6bjZW46DFWFaw1K4pTNuOxNf1cHjAdgAAq9vUdEm+AQrMhQAA9v8AAAACAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg2EkAAAAAZoxaWgAAAAAAAAAAAAAAAA==',
                                           'fee_meta_xdr': 'AAAAAgAAAAMDIPB/AAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABrMgymuEAgPKvAAD7AoAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg8H8AAAAAZozkvgAAAAAAAAABAyDwiQAAAAAAAAAA0l2dYO7kvPPhr5mond0gbT5yIMDeByPEagaOF5xbhpkAAAazIMprIAIDyrwAA+wKAAAAAwAAAAAAAAAAAAAACWJpdGdvLmNvbQAAAAABAgMAAAADAAAAAB1Is281wIRalQzWxIccn1b8moxZvPWuED9KXVA77gL0AAAAAQAAAACXkCLpREgrWpIREpkW0pw9fP8Eg2t6oFARzbv3eXWbpwAAAAEAAAAArbEmN5FNlLICSJE5vm2TrLwV5Zr8bou6Zpuhm8BqekUAAAABAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAADAAAAAAAAAAAAAAAAAAAAAwAAAAADIPB/AAAAAGaM5L4AAAAA',
                                           'memo_type': 'text', 'signatures': [
                                              'dSgFYMIEu/MALObJLIoRqqYARDFQMXLJ/Lh6PT6F10soSTixbXLk5QhYbxMcbbNqrtnp3AveVlpjx6Hf63+XDA==',
                                              'P1ZlSILiK4zJnX+bdzAXfLFHwq2YFamCKkRr1FPUCooJPn524BsG4cEmqXYS2Saq9S3EKrBwtXuV2aWT8Rt4AA=='],
                                           'valid_after': '1970-01-01T00:00:00Z',
                                           'preconditions': {'timebounds': {'min_time': '0'}}}, {'memo': '292423124',
                                                                                                 '_links': {'self': {
                                                                                                     'href': 'https://horizon.stellar.org/transactions/db9f67d857684e3ca99ec9e7d2ace494ff44cc7e2efdabc9b0af7b8a300d42ad'},
                                                                                                     'account': {
                                                                                                         'href': 'https://horizon.stellar.org/accounts/GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5'},
                                                                                                     'ledger': {
                                                                                                         'href': 'https://horizon.stellar.org/ledgers/52490367'},
                                                                                                     'operations': {
                                                                                                         'href': 'https://horizon.stellar.org/transactions/db9f67d857684e3ca99ec9e7d2ace494ff44cc7e2efdabc9b0af7b8a300d42ad/operations{?cursor,limit,order}',
                                                                                                         'templated': True},
                                                                                                     'effects': {
                                                                                                         'href': 'https://horizon.stellar.org/transactions/db9f67d857684e3ca99ec9e7d2ace494ff44cc7e2efdabc9b0af7b8a300d42ad/effects{?cursor,limit,order}',
                                                                                                         'templated': True},
                                                                                                     'precedes': {
                                                                                                         'href': 'https://horizon.stellar.org/transactions?order=asc&cursor=225444409620422656'},
                                                                                                     'succeeds': {
                                                                                                         'href': 'https://horizon.stellar.org/transactions?order=desc&cursor=225444409620422656'},
                                                                                                     'transaction': {
                                                                                                         'href': 'https://horizon.stellar.org/transactions/db9f67d857684e3ca99ec9e7d2ace494ff44cc7e2efdabc9b0af7b8a300d42ad'}},
                                                                                                 'id': 'db9f67d857684e3ca99ec9e7d2ace494ff44cc7e2efdabc9b0af7b8a300d42ad',
                                                                                                 'paging_token': '225444409620422656',
                                                                                                 'successful': True,
                                                                                                 'hash': 'db9f67d857684e3ca99ec9e7d2ace494ff44cc7e2efdabc9b0af7b8a300d42ad',
                                                                                                 'ledger': 52490367,
                                                                                                 'created_at': '2024-07-09T07:20:30Z',
                                                                                                 'source_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                                                                                                 'source_account_sequence': '145182521808907274',
                                                                                                 'fee_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                                                                                                 'fee_charged': '100',
                                                                                                 'max_fee': '45000',
                                                                                                 'operation_count': 1,
                                                                                                 'envelope_xdr': 'AAAAAgAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAAr8gCA8q8AAPsCgAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAARbgXUAAAAAQAAAAAAAAABAAAAAAJYIV7cdNJNLPz9/ZAMy3kUrWZ+3FoRNOyzWZrUVReUAAAAAAAAAAQJMMOiAAAAAAAAAALAanpFAAAAQMRc+0JUCPwj1ViUsI8sDKKbeVuhjpPfQBm5Eyy95j9Lz51iy+ctrRmKBKoOvl2kpnU9W5N6/wskKgdQvkODnA95dZunAAAAQCd64A+0NxTE5HiPZkQS4jVvVa0SvwMnIoKWh+pmGDBbQ0cUn8xySRSUQ1TBBtbi4GpC1+EdWR8LoLUEEvHflQc=',
                                                                                                 'result_xdr': 'AAAAAAAAAGQAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAA=',
                                                                                                 'result_meta_xdr': 'AAAAAwAAAAAAAAACAAAAAwMg8H8AAAAAAAAAANJdnWDu5Lzz4a+ZqJ3dIG0+ciDA3gcjxGoGjhecW4aZAAAGtyn7LyYCA8q8AAPsCQAAAAMAAAAAAAAAAAAAAAliaXRnby5jb20AAAAAAQIDAAAAAwAAAAAdSLNvNcCEWpUM1sSHHJ9W/JqMWbz1rhA/Sl1QO+4C9AAAAAEAAAAAl5Ai6URIK1qSERKZFtKcPXz/BINreqBQEc2793l1m6cAAAABAAAAAK2xJjeRTZSyAkiROb5tk6y8FeWa/G6LumaboZvAanpFAAAAAQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAwAAAAAAAAAAAAAAAAAAAAMAAAAAAyDlhwAAAABmjKYkAAAAAAAAAAEDIPB/AAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABrcp+y8mAgPKvAAD7AoAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg8H8AAAAAZozkvgAAAAAAAAABAAAABAAAAAMDIPB/AAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABrcp+y8mAgPKvAAD7AoAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg8H8AAAAAZozkvgAAAAAAAAABAyDwfwAAAAAAAAAA0l2dYO7kvPPhr5mond0gbT5yIMDeByPEagaOF5xbhpkAAAazIMprhAIDyrwAA+wKAAAAAwAAAAAAAAAAAAAACWJpdGdvLmNvbQAAAAABAgMAAAADAAAAAB1Is281wIRalQzWxIccn1b8moxZvPWuED9KXVA77gL0AAAAAQAAAACXkCLpREgrWpIREpkW0pw9fP8Eg2t6oFARzbv3eXWbpwAAAAEAAAAArbEmN5FNlLICSJE5vm2TrLwV5Zr8bou6Zpuhm8BqekUAAAABAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAADAAAAAAAAAAAAAAAAAAAAAwAAAAADIPB/AAAAAGaM5L4AAAAAAAAAAwMg8GoAAAAAAAAAAAJYIV7cdNJNLPz9/ZAMy3kUrWZ+3FoRNOyzWZrUVReUAAAAALfYXVgCm0CuAAJrcQAAAAIAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAMAAAAAAyDwZgAAAABmjOQwAAAAAAAAAAEDIPB/AAAAAAAAAAACWCFe3HTSTSz8/f2QDMt5FK1mftxaETTss1ma1FUXlAAAAATBCSD6AptArgACa3EAAAACAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg8GYAAAAAZozkMAAAAAAAAAAAAAAAAA==',
                                                                                                 'fee_meta_xdr': 'AAAAAgAAAAMDIO6iAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABrcp+y+KAgPKvAAD7AkAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg5YcAAAAAZoymJAAAAAAAAAABAyDwfwAAAAAAAAAA0l2dYO7kvPPhr5mond0gbT5yIMDeByPEagaOF5xbhpkAAAa3KfsvJgIDyrwAA+wJAAAAAwAAAAAAAAAAAAAACWJpdGdvLmNvbQAAAAABAgMAAAADAAAAAB1Is281wIRalQzWxIccn1b8moxZvPWuED9KXVA77gL0AAAAAQAAAACXkCLpREgrWpIREpkW0pw9fP8Eg2t6oFARzbv3eXWbpwAAAAEAAAAArbEmN5FNlLICSJE5vm2TrLwV5Zr8bou6Zpuhm8BqekUAAAABAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAADAAAAAAAAAAAAAAAAAAAAAwAAAAADIOWHAAAAAGaMpiQAAAAA',
                                                                                                 'memo_type': 'id',
                                                                                                 'signatures': [
                                                                                                     'xFz7QlQI/CPVWJSwjywMopt5W6GOk99AGbkTLL3mP0vPnWLL5y2tGYoEqg6+XaSmdT1bk3r/CyQqB1C+Q4OcDw==',
                                                                                                     'J3rgD7Q3FMTkeI9mRBLiNW9VrRK/AycigpaH6mYYMFtDRxSfzHJJFJRDVMEG1uLgakLX4R1ZHwugtQQS8d+VBw=='],
                                                                                                 'valid_after': '1970-01-01T00:00:00Z',
                                                                                                 'preconditions': {
                                                                                                     'timebounds': {
                                                                                                         'min_time': '0'}}},
                                          {'memo': '186674', 'memo_bytes': 'MTg2Njc0', '_links': {'self': {
                                              'href': 'https://horizon.stellar.org/transactions/5370ecc06dc79ee23c552f5bbd230195b2d564877ee4aa5749f9ba0b18c40d00'},
                                              'account': {
                                                  'href': 'https://horizon.stellar.org/accounts/GDHF3HIKWM5KJAVLZBSZWUFDOEOT7IBMY22UXG4QBE326O354INLPAND'},
                                              'ledger': {
                                                  'href': 'https://horizon.stellar.org/ledgers/52489890'},
                                              'operations': {
                                                  'href': 'https://horizon.stellar.org/transactions/5370ecc06dc79ee23c552f5bbd230195b2d564877ee4aa5749f9ba0b18c40d00/operations{?cursor,limit,order}',
                                                  'templated': True},
                                              'effects': {
                                                  'href': 'https://horizon.stellar.org/transactions/5370ecc06dc79ee23c552f5bbd230195b2d564877ee4aa5749f9ba0b18c40d00/effects{?cursor,limit,order}',
                                                  'templated': True},
                                              'precedes': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=asc&cursor=225442360920678400'},
                                              'succeeds': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=desc&cursor=225442360920678400'},
                                              'transaction': {
                                                  'href': 'https://horizon.stellar.org/transactions/5370ecc06dc79ee23c552f5bbd230195b2d564877ee4aa5749f9ba0b18c40d00'}},
                                           'id': '5370ecc06dc79ee23c552f5bbd230195b2d564877ee4aa5749f9ba0b18c40d00',
                                           'paging_token': '225442360920678400', 'successful': True,
                                           'hash': '5370ecc06dc79ee23c552f5bbd230195b2d564877ee4aa5749f9ba0b18c40d00',
                                           'ledger': 52489890, 'created_at': '2024-07-09T06:35:05Z',
                                           'source_account': 'GDHF3HIKWM5KJAVLZBSZWUFDOEOT7IBMY22UXG4QBE326O354INLPAND',
                                           'source_account_sequence': '166409929518316738',
                                           'fee_account': 'GDHF3HIKWM5KJAVLZBSZWUFDOEOT7IBMY22UXG4QBE326O354INLPAND',
                                           'fee_charged': '100', 'max_fee': '1000000', 'operation_count': 1,
                                           'envelope_xdr': 'AAAAAgAAAADOXZ0KszqkgqvIZZtQo3EdP6AsxrVLm5AJN687feIatwAPQkACTzTzAAl8wgAAAAEAAAAAAAAAAAAAAABmjNpuAAAAAQAAAAYxODY2NzQAAAAAAAEAAAAAAAAAAQAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAAAAAAAAAA1HUdSAAAAAAAAAABfeIatwAAAEB9fl5gUWQZo/lY7M4nvCVVT+aUM6fZzunoxEd/zxAXq+T9Qyqog5p03pTHCMND1TaBE3tjAsv3sS5Kpb9+uIwG',
                                           'result_xdr': 'AAAAAAAAAGQAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAA=',
                                           'result_meta_xdr': 'AAAAAwAAAAAAAAACAAAAAwMg7qIAAAAAAAAAAM5dnQqzOqSCq8hlm1CjcR0/oCzGtUubkAk3rzt94hq3AABDfnRvBDMCTzTzAAl8wQAAAAIAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAMAAAAAAyDuQQAAAABmjNfxAAAAAAAAAAEDIO6iAAAAAAAAAADOXZ0KszqkgqvIZZtQo3EdP6AsxrVLm5AJN687feIatwAAQ350bwQzAk808wAJfMIAAAACAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg7qIAAAAAZozaGQAAAAAAAAABAAAABAAAAAMDIO6iAAAAAAAAAADOXZ0KszqkgqvIZZtQo3EdP6AsxrVLm5AJN687feIatwAAQ350bwQzAk808wAJfMIAAAACAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg7qIAAAAAZozaGQAAAAAAAAABAyDuogAAAAAAAAAAzl2dCrM6pIKryGWbUKNxHT+gLMa1S5uQCTevO33iGrcAAEN9n/nm6wJPNPMACXzCAAAAAgAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAwAAAAADIO6iAAAAAGaM2hkAAAAAAAAAAwMg7lEAAAAAAAAAANJdnWDu5Lzz4a+ZqJ3dIG0+ciDA3gcjxGoGjhecW4aZAAAGtlWGEkICA8q8AAPsCQAAAAMAAAAAAAAAAAAAAAliaXRnby5jb20AAAAAAQIDAAAAAwAAAAAdSLNvNcCEWpUM1sSHHJ9W/JqMWbz1rhA/Sl1QO+4C9AAAAAEAAAAAl5Ai6URIK1qSERKZFtKcPXz/BINreqBQEc2793l1m6cAAAABAAAAAK2xJjeRTZSyAkiROb5tk6y8FeWa/G6LumaboZvAanpFAAAAAQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAwAAAAAAAAAAAAAAAAAAAAMAAAAAAyDlhwAAAABmjKYkAAAAAAAAAAEDIO6iAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABrcp+y+KAgPKvAAD7AkAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg5YcAAAAAZoymJAAAAAAAAAAAAAAAAA==',
                                           'fee_meta_xdr': 'AAAAAgAAAAMDIO5BAAAAAAAAAADOXZ0KszqkgqvIZZtQo3EdP6AsxrVLm5AJN687feIatwAAQ350bwSXAk808wAJfMEAAAACAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg7kEAAAAAZozX8QAAAAAAAAABAyDuogAAAAAAAAAAzl2dCrM6pIKryGWbUKNxHT+gLMa1S5uQCTevO33iGrcAAEN+dG8EMwJPNPMACXzBAAAAAgAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAwAAAAADIO5BAAAAAGaM1/EAAAAA',
                                           'memo_type': 'text', 'signatures': [
                                              'fX5eYFFkGaP5WOzOJ7wlVU/mlDOn2c7p6MRHf88QF6vk/UMqqIOadN6UxwjDQ9U2gRN7YwLL97EuSqW/friMBg=='],
                                           'valid_after': '1970-01-01T00:00:00Z',
                                           'valid_before': '2024-07-09T06:36:30Z',
                                           'preconditions': {
                                               'timebounds': {'min_time': '0', 'max_time': '1720506990'}}},
                                          {'memo': '174756', '_links': {'self': {
                                              'href': 'https://horizon.stellar.org/transactions/14a5ead1562b71c22d4f9399a7d453730692719e4f48def731d1618696d6dc25'},
                                              'account': {
                                                  'href': 'https://horizon.stellar.org/accounts/GAV6J5L473K4H6226IFNCAL7E5A2PR63YRCZDYJPTQH3S35YODXUUADV'},
                                              'ledger': {
                                                  'href': 'https://horizon.stellar.org/ledgers/52489809'},
                                              'operations': {
                                                  'href': 'https://horizon.stellar.org/transactions/14a5ead1562b71c22d4f9399a7d453730692719e4f48def731d1618696d6dc25/operations{?cursor,limit,order}',
                                                  'templated': True}, 'effects': {
                                                  'href': 'https://horizon.stellar.org/transactions/14a5ead1562b71c22d4f9399a7d453730692719e4f48def731d1618696d6dc25/effects{?cursor,limit,order}',
                                                  'templated': True}, 'precedes': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=asc&cursor=225442013030813696'},
                                              'succeeds': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=desc&cursor=225442013030813696'},
                                              'transaction': {
                                                  'href': 'https://horizon.stellar.org/transactions/14a5ead1562b71c22d4f9399a7d453730692719e4f48def731d1618696d6dc25'}},
                                           'id': '14a5ead1562b71c22d4f9399a7d453730692719e4f48def731d1618696d6dc25',
                                           'paging_token': '225442013030813696', 'successful': True,
                                           'hash': '14a5ead1562b71c22d4f9399a7d453730692719e4f48def731d1618696d6dc25',
                                           'ledger': 52489809, 'created_at': '2024-07-09T06:27:25Z',
                                           'source_account': 'GAV6J5L473K4H6226IFNCAL7E5A2PR63YRCZDYJPTQH3S35YODXUUADV',
                                           'source_account_sequence': '153493713023492603',
                                           'fee_account': 'GAV6J5L473K4H6226IFNCAL7E5A2PR63YRCZDYJPTQH3S35YODXUUADV',
                                           'fee_charged': '5001', 'max_fee': '1000000', 'operation_count': 1,
                                           'envelope_xdr': 'AAAAAgAAAAAr5PV8/tXD+1ryCtEBfydBp8fbxEWR4S+cD7lvuHDvSgAPQkACIVG4AAVh+wAAAAEAAAAAAAAAAAAAAABmjNl1AAAAAgAAAAAAAqqkAAAAAQAAAAAAAAABAAAAANJdnWDu5Lzz4a+ZqJ3dIG0+ciDA3gcjxGoGjhecW4aZAAAAAAAAAACWoVCaAAAAAAAAAAG4cO9KAAAAQMH+VaESjvD5U7kYMEOgCd8VmydjZOGzPxjRZPUOxPL8jo6sj2m0x9X4WEDHv/Z2qOI/vHPAtiKEMDv5TcY6IQw=',
                                           'result_xdr': 'AAAAAAAAE4kAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAA=',
                                           'result_meta_xdr': 'AAAAAwAAAAAAAAACAAAAAwMg7lEAAAAAAAAAACvk9Xz+1cP7WvIK0QF/J0Gnx9vERZHhL5wPuW+4cO9KAAAC6ZLXHpYCIVG4AAVh+gAAAAEAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAMAAAAAAyDsiwAAAABmjM42AAAAAAAAAAEDIO5RAAAAAAAAAAAr5PV8/tXD+1ryCtEBfydBp8fbxEWR4S+cD7lvuHDvSgAAAumS1x6WAiFRuAAFYfsAAAABAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg7lEAAAAAZozYTQAAAAAAAAABAAAABAAAAAMDIO5RAAAAAAAAAAAr5PV8/tXD+1ryCtEBfydBp8fbxEWR4S+cD7lvuHDvSgAAAumS1x6WAiFRuAAFYfsAAAABAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg7lEAAAAAZozYTQAAAAAAAAABAyDuUQAAAAAAAAAAK+T1fP7Vw/ta8grRAX8nQafH28RFkeEvnA+5b7hw70oAAALo/DXN/AIhUbgABWH7AAAAAQAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAwAAAAADIO5RAAAAAGaM2E0AAAAAAAAAAwMg510AAAAAAAAAANJdnWDu5Lzz4a+ZqJ3dIG0+ciDA3gcjxGoGjhecW4aZAAAGtb7kwagCA8q8AAPsCQAAAAMAAAAAAAAAAAAAAAliaXRnby5jb20AAAAAAQIDAAAAAwAAAAAdSLNvNcCEWpUM1sSHHJ9W/JqMWbz1rhA/Sl1QO+4C9AAAAAEAAAAAl5Ai6URIK1qSERKZFtKcPXz/BINreqBQEc2793l1m6cAAAABAAAAAK2xJjeRTZSyAkiROb5tk6y8FeWa/G6LumaboZvAanpFAAAAAQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAwAAAAAAAAAAAAAAAAAAAAMAAAAAAyDlhwAAAABmjKYkAAAAAAAAAAEDIO5RAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABrZVhhJCAgPKvAAD7AkAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg5YcAAAAAZoymJAAAAAAAAAAAAAAAAA==',
                                           'fee_meta_xdr': 'AAAAAgAAAAMDIOyLAAAAAAAAAAAr5PV8/tXD+1ryCtEBfydBp8fbxEWR4S+cD7lvuHDvSgAAAumS1zIfAiFRuAAFYfoAAAABAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg7IsAAAAAZozONgAAAAAAAAABAyDuUQAAAAAAAAAAK+T1fP7Vw/ta8grRAX8nQafH28RFkeEvnA+5b7hw70oAAALpktcelgIhUbgABWH6AAAAAQAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAwAAAAADIOyLAAAAAGaMzjYAAAAA',
                                           'memo_type': 'id', 'signatures': [
                                              'wf5VoRKO8PlTuRgwQ6AJ3xWbJ2Nk4bM/GNFk9Q7E8vyOjqyPabTH1fhYQMe/9nao4j+8c8C2IoQwO/lNxjohDA=='],
                                           'valid_after': '1970-01-01T00:00:00Z',
                                           'valid_before': '2024-07-09T06:32:21Z',
                                           'preconditions': {
                                               'timebounds': {'min_time': '0', 'max_time': '1720506741'}}},
                                          {'memo': '167866', 'memo_bytes': 'MTY3ODY2', '_links': {'self': {
                                              'href': 'https://horizon.stellar.org/transactions/34a547aa9854384deeb4b321caac0c87b0beec2a076f7a8818ca2a7f82a06606'},
                                              'account': {
                                                  'href': 'https://horizon.stellar.org/accounts/GDHF3HIKWM5KJAVLZBSZWUFDOEOT7IBMY22UXG4QBE326O354INLPAND'},
                                              'ledger': {
                                                  'href': 'https://horizon.stellar.org/ledgers/52488029'},
                                              'operations': {
                                                  'href': 'https://horizon.stellar.org/transactions/34a547aa9854384deeb4b321caac0c87b0beec2a076f7a8818ca2a7f82a06606/operations{?cursor,limit,order}',
                                                  'templated': True},
                                              'effects': {
                                                  'href': 'https://horizon.stellar.org/transactions/34a547aa9854384deeb4b321caac0c87b0beec2a076f7a8818ca2a7f82a06606/effects{?cursor,limit,order}',
                                                  'templated': True},
                                              'precedes': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=asc&cursor=225434367987757056'},
                                              'succeeds': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=desc&cursor=225434367987757056'},
                                              'transaction': {
                                                  'href': 'https://horizon.stellar.org/transactions/34a547aa9854384deeb4b321caac0c87b0beec2a076f7a8818ca2a7f82a06606'}},
                                           'id': '34a547aa9854384deeb4b321caac0c87b0beec2a076f7a8818ca2a7f82a06606',
                                           'paging_token': '225434367987757056', 'successful': True,
                                           'hash': '34a547aa9854384deeb4b321caac0c87b0beec2a076f7a8818ca2a7f82a06606',
                                           'ledger': 52488029, 'created_at': '2024-07-09T03:38:15Z',
                                           'source_account': 'GDHF3HIKWM5KJAVLZBSZWUFDOEOT7IBMY22UXG4QBE326O354INLPAND',
                                           'source_account_sequence': '166409929518316710',
                                           'fee_account': 'GDHF3HIKWM5KJAVLZBSZWUFDOEOT7IBMY22UXG4QBE326O354INLPAND',
                                           'fee_charged': '100', 'max_fee': '1000000', 'operation_count': 1,
                                           'envelope_xdr': 'AAAAAgAAAADOXZ0KszqkgqvIZZtQo3EdP6AsxrVLm5AJN687feIatwAPQkACTzTzAAl8pgAAAAEAAAAAAAAAAAAAAABmjLD8AAAAAQAAAAYxNjc4NjYAAAAAAAEAAAAAAAAAAQAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAAAAAAAAAAKRTIkAAAAAAAAAABfeIatwAAAECy5SZ6ZdegaQYZXLV7nYXj174qqxlt8XSdTEwq13xezpqtEFEItpYXzPOVz6TCvR4Iu5/0U6IpK1nDmaHrDjUH',
                                           'result_xdr': 'AAAAAAAAAGQAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAA=',
                                           'result_meta_xdr': 'AAAAAwAAAAAAAAACAAAAAwMg510AAAAAAAAAAM5dnQqzOqSCq8hlm1CjcR0/oCzGtUubkAk3rzt94hq3AABDqC2rGSICTzTzAAl8pQAAAAIAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAMAAAAAAyDnJQAAAABmjK9mAAAAAAAAAAEDIOddAAAAAAAAAADOXZ0KszqkgqvIZZtQo3EdP6AsxrVLm5AJN687feIatwAAQ6gtqxkiAk808wAJfKYAAAACAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg510AAAAAZoywpwAAAAAAAAABAAAABAAAAAMDIOddAAAAAAAAAADOXZ0KszqkgqvIZZtQo3EdP6AsxrVLm5AJN687feIatwAAQ6gtqxkiAk808wAJfKYAAAACAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg510AAAAAZoywpwAAAAAAAAABAyDnXQAAAAAAAAAAzl2dCrM6pIKryGWbUKNxHT+gLMa1S5uQCTevO33iGrcAAEOoBJZQkgJPNPMACXymAAAAAgAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAwAAAAADIOddAAAAAGaMsKcAAAAAAAAAAwMg5YcAAAAAAAAAANJdnWDu5Lzz4a+ZqJ3dIG0+ciDA3gcjxGoGjhecW4aZAAAGtZXP+RgCA8q8AAPsCQAAAAMAAAAAAAAAAAAAAAliaXRnby5jb20AAAAAAQIDAAAAAwAAAAAdSLNvNcCEWpUM1sSHHJ9W/JqMWbz1rhA/Sl1QO+4C9AAAAAEAAAAAl5Ai6URIK1qSERKZFtKcPXz/BINreqBQEc2793l1m6cAAAABAAAAAK2xJjeRTZSyAkiROb5tk6y8FeWa/G6LumaboZvAanpFAAAAAQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAwAAAAAAAAAAAAAAAAAAAAMAAAAAAyDlhwAAAABmjKYkAAAAAAAAAAEDIOddAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABrW+5MGoAgPKvAAD7AkAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg5YcAAAAAZoymJAAAAAAAAAAAAAAAAA==',
                                           'fee_meta_xdr': 'AAAAAgAAAAMDIOclAAAAAAAAAADOXZ0KszqkgqvIZZtQo3EdP6AsxrVLm5AJN687feIatwAAQ6gtqxmGAk808wAJfKUAAAACAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg5yUAAAAAZoyvZgAAAAAAAAABAyDnXQAAAAAAAAAAzl2dCrM6pIKryGWbUKNxHT+gLMa1S5uQCTevO33iGrcAAEOoLasZIgJPNPMACXylAAAAAgAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAwAAAAADIOclAAAAAGaMr2YAAAAA',
                                           'memo_type': 'text', 'signatures': [
                                              'suUmemXXoGkGGVy1e52F49e+KqsZbfF0nUxMKtd8Xs6arRBRCLaWF8zzlc+kwr0eCLuf9FOiKStZw5mh6w41Bw=='],
                                           'valid_after': '1970-01-01T00:00:00Z',
                                           'valid_before': '2024-07-09T03:39:40Z',
                                           'preconditions': {
                                               'timebounds': {'min_time': '0', 'max_time': '1720496380'}}},
                                          {'memo': '1212878250', '_links': {'self': {
                                              'href': 'https://horizon.stellar.org/transactions/135c4be71c4cea1cf5200a1ef3c227535dfe62a9f046f351fc19b6bf6e1693a2'},
                                              'account': {
                                                  'href': 'https://horizon.stellar.org/accounts/GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5'},
                                              'ledger': {
                                                  'href': 'https://horizon.stellar.org/ledgers/52487559'},
                                              'operations': {
                                                  'href': 'https://horizon.stellar.org/transactions/135c4be71c4cea1cf5200a1ef3c227535dfe62a9f046f351fc19b6bf6e1693a2/operations{?cursor,limit,order}',
                                                  'templated': True}, 'effects': {
                                                  'href': 'https://horizon.stellar.org/transactions/135c4be71c4cea1cf5200a1ef3c227535dfe62a9f046f351fc19b6bf6e1693a2/effects{?cursor,limit,order}',
                                                  'templated': True}, 'precedes': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=asc&cursor=225432349352439808'},
                                              'succeeds': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=desc&cursor=225432349352439808'},
                                              'transaction': {
                                                  'href': 'https://horizon.stellar.org/transactions/135c4be71c4cea1cf5200a1ef3c227535dfe62a9f046f351fc19b6bf6e1693a2'}},
                                           'id': '135c4be71c4cea1cf5200a1ef3c227535dfe62a9f046f351fc19b6bf6e1693a2',
                                           'paging_token': '225432349352439808', 'successful': True,
                                           'hash': '135c4be71c4cea1cf5200a1ef3c227535dfe62a9f046f351fc19b6bf6e1693a2',
                                           'ledger': 52487559, 'created_at': '2024-07-09T02:53:24Z',
                                           'source_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                                           'source_account_sequence': '145182521808907273',
                                           'fee_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                                           'fee_charged': '100', 'max_fee': '45000', 'operation_count': 1,
                                           'envelope_xdr': 'AAAAAgAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAAr8gCA8q8AAPsCQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAABISw2qAAAAAQAAAAAAAAABAAAAAKY78+ZZv0ce9mOukRpc8tVr+4G4BmvfVHLZ8VmUCzbJAAAAAAAAAAAC5NRYAAAAAAAAAALAanpFAAAAQMCoMH0ATKkXFxrBXaFwjLTIcGE8dUuAN44nImjlgPDeHexk/YBawTI9G1C0YXdZk4vNPTFoNqtests6tCwOzAV5dZunAAAAQIuELRr2FM2strSbQwtwmBNX8wQ3oym4BPLySbuCHZgMCYEZ/jfOEV8RbBCys5kOOttgsLfuDiAFbdaEfR7/hAs=',
                                           'result_xdr': 'AAAAAAAAAGQAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAA=',
                                           'result_meta_xdr': 'AAAAAwAAAAAAAAACAAAAAwMg5YcAAAAAAAAAANJdnWDu5Lzz4a+ZqJ3dIG0+ciDA3gcjxGoGjhecW4aZAAAGtZi0zXACA8q8AAPsCAAAAAMAAAAAAAAAAAAAAAliaXRnby5jb20AAAAAAQIDAAAAAwAAAAAdSLNvNcCEWpUM1sSHHJ9W/JqMWbz1rhA/Sl1QO+4C9AAAAAEAAAAAl5Ai6URIK1qSERKZFtKcPXz/BINreqBQEc2793l1m6cAAAABAAAAAK2xJjeRTZSyAkiROb5tk6y8FeWa/G6LumaboZvAanpFAAAAAQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAwAAAAAAAAAAAAAAAAAAAAMAAAAAAyDhcAAAAABmjI7DAAAAAAAAAAEDIOWHAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABrWYtM1wAgPKvAAD7AkAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg5YcAAAAAZoymJAAAAAAAAAABAAAABAAAAAMDIOWHAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABrWYtM1wAgPKvAAD7AkAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg5YcAAAAAZoymJAAAAAAAAAABAyDlhwAAAAAAAAAA0l2dYO7kvPPhr5mond0gbT5yIMDeByPEagaOF5xbhpkAAAa1lc/5GAIDyrwAA+wJAAAAAwAAAAAAAAAAAAAACWJpdGdvLmNvbQAAAAABAgMAAAADAAAAAB1Is281wIRalQzWxIccn1b8moxZvPWuED9KXVA77gL0AAAAAQAAAACXkCLpREgrWpIREpkW0pw9fP8Eg2t6oFARzbv3eXWbpwAAAAEAAAAArbEmN5FNlLICSJE5vm2TrLwV5Zr8bou6Zpuhm8BqekUAAAABAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAADAAAAAAAAAAAAAAAAAAAAAwAAAAADIOWHAAAAAGaMpiQAAAAAAAAAAwMg4uMAAAAAAAAAAKY78+ZZv0ce9mOukRpc8tVr+4G4BmvfVHLZ8VmUCzbJAAAAABfXggwCWO7dAAB4jgAAAAEAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAMAAAAAAyDi4wAAAABmjJcQAAAAAAAAAAEDIOWHAAAAAAAAAACmO/PmWb9HHvZjrpEaXPLVa/uBuAZr31Ry2fFZlAs2yQAAAAAavFZkAlju3QAAeI4AAAABAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg4uMAAAAAZoyXEAAAAAAAAAAAAAAAAA==',
                                           'fee_meta_xdr': 'AAAAAgAAAAMDIOVPAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABrWYtM3UAgPKvAAD7AgAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg4XAAAAAAZoyOwwAAAAAAAAABAyDlhwAAAAAAAAAA0l2dYO7kvPPhr5mond0gbT5yIMDeByPEagaOF5xbhpkAAAa1mLTNcAIDyrwAA+wIAAAAAwAAAAAAAAAAAAAACWJpdGdvLmNvbQAAAAABAgMAAAADAAAAAB1Is281wIRalQzWxIccn1b8moxZvPWuED9KXVA77gL0AAAAAQAAAACXkCLpREgrWpIREpkW0pw9fP8Eg2t6oFARzbv3eXWbpwAAAAEAAAAArbEmN5FNlLICSJE5vm2TrLwV5Zr8bou6Zpuhm8BqekUAAAABAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAADAAAAAAAAAAAAAAAAAAAAAwAAAAADIOFwAAAAAGaMjsMAAAAA',
                                           'memo_type': 'id', 'signatures': [
                                              'wKgwfQBMqRcXGsFdoXCMtMhwYTx1S4A3jiciaOWA8N4d7GT9gFrBMj0bULRhd1mTi809MWg2q16y2zq0LA7MBQ==',
                                              'i4QtGvYUzay2tJtDC3CYE1fzBDejKbgE8vJJu4IdmAwJgRn+N84RXxFsELKzmQ4622Cwt+4OIAVt1oR9Hv+ECw=='],
                                           'valid_after': '1970-01-01T00:00:00Z',
                                           'preconditions': {'timebounds': {'min_time': '0'}}},
                                          {'memo': '203239', 'memo_bytes': 'MjAzMjM5', '_links': {'self': {
                                              'href': 'https://horizon.stellar.org/transactions/f91af004a0b1a33cdbba23a5db526d7f147621a1bdbe56454f477aa8598472c7'},
                                              'account': {
                                                  'href': 'https://horizon.stellar.org/accounts/GD6RWYUQ6FWRBWFFA4HZVPCQUKGUIHZ4SL5G5GJU4HP3LKMYSUYAGBUA'},
                                              'ledger': {
                                                  'href': 'https://horizon.stellar.org/ledgers/52487503'},
                                              'operations': {
                                                  'href': 'https://horizon.stellar.org/transactions/f91af004a0b1a33cdbba23a5db526d7f147621a1bdbe56454f477aa8598472c7/operations{?cursor,limit,order}',
                                                  'templated': True},
                                              'effects': {
                                                  'href': 'https://horizon.stellar.org/transactions/f91af004a0b1a33cdbba23a5db526d7f147621a1bdbe56454f477aa8598472c7/effects{?cursor,limit,order}',
                                                  'templated': True},
                                              'precedes': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=asc&cursor=225432108835401728'},
                                              'succeeds': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=desc&cursor=225432108835401728'},
                                              'transaction': {
                                                  'href': 'https://horizon.stellar.org/transactions/f91af004a0b1a33cdbba23a5db526d7f147621a1bdbe56454f477aa8598472c7'}},
                                           'id': 'f91af004a0b1a33cdbba23a5db526d7f147621a1bdbe56454f477aa8598472c7',
                                           'paging_token': '225432108835401728', 'successful': True,
                                           'hash': 'f91af004a0b1a33cdbba23a5db526d7f147621a1bdbe56454f477aa8598472c7',
                                           'ledger': 52487503, 'created_at': '2024-07-09T02:48:06Z',
                                           'source_account': 'GD6RWYUQ6FWRBWFFA4HZVPCQUKGUIHZ4SL5G5GJU4HP3LKMYSUYAGBUA',
                                           'source_account_sequence': '225406622497767427',
                                           'fee_account': 'GD6RWYUQ6FWRBWFFA4HZVPCQUKGUIHZ4SL5G5GJU4HP3LKMYSUYAGBUA',
                                           'fee_charged': '100', 'max_fee': '100159', 'operation_count': 1,
                                           'envelope_xdr': 'AAAAAgAAAAD9G2KQ8W0Q2KUHD5q8UKKNRB88kvpumTTh37WpmJUwAwABhz8DIM4hAAAAAwAAAAEAAAAAN4zJmwAAAABmjM8MAAAAAQAAAAYyMDMyMzkAAAAAAAEAAAAAAAAAAQAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAAAAAAAAAAKBZEoAAAAAAAAAABmJUwAwAAAEDv3PoeRRz5yJXI6BOOmuiOfTuwZ+LAAqPHPOtLZEz3Ven++rbDgku/RL5jSyArcuo10/1O2tM6xeOXe4eh0ngE',
                                           'result_xdr': 'AAAAAAAAAGQAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAA=',
                                           'result_meta_xdr': 'AAAAAwAAAAAAAAACAAAAAwMg5U8AAAAAAAAAAP0bYpDxbRDYpQcPmrxQoo1EHzyS+m6ZNOHftamYlTADAAAVMhqswYoDIM4hAAAAAgAAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAMAAAAAAyDiMQAAAABmjJMTAAAAAAAAAAEDIOVPAAAAAAAAAAD9G2KQ8W0Q2KUHD5q8UKKNRB88kvpumTTh37WpmJUwAwAAFTIarMGKAyDOIQAAAAMAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg5U8AAAAAZoyk5gAAAAAAAAABAAAABAAAAAMDIOVPAAAAAAAAAAD9G2KQ8W0Q2KUHD5q8UKKNRB88kvpumTTh37WpmJUwAwAAFTIarMGKAyDOIQAAAAMAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg5U8AAAAAZoyk5gAAAAAAAAABAyDlTwAAAAAAAAAA/RtikPFtENilBw+avFCijUQfPJL6bpk04d+1qZiVMAMAABUx8pZ86gMgziEAAAADAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAwAAAAADIOVPAAAAAGaMpOYAAAAAAAAAAwMg4XAAAAAAAAAAANJdnWDu5Lzz4a+ZqJ3dIG0+ciDA3gcjxGoGjhecW4aZAAAGtXCeiTQCA8q8AAPsCAAAAAMAAAAAAAAAAAAAAAliaXRnby5jb20AAAAAAQIDAAAAAwAAAAAdSLNvNcCEWpUM1sSHHJ9W/JqMWbz1rhA/Sl1QO+4C9AAAAAEAAAAAl5Ai6URIK1qSERKZFtKcPXz/BINreqBQEc2793l1m6cAAAABAAAAAK2xJjeRTZSyAkiROb5tk6y8FeWa/G6LumaboZvAanpFAAAAAQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAwAAAAAAAAAAAAAAAAAAAAMAAAAAAyDhcAAAAABmjI7DAAAAAAAAAAEDIOVPAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABrWYtM3UAgPKvAAD7AgAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg4XAAAAAAZoyOwwAAAAAAAAAAAAAAAA==',
                                           'fee_meta_xdr': 'AAAAAgAAAAMDIOIxAAAAAAAAAAD9G2KQ8W0Q2KUHD5q8UKKNRB88kvpumTTh37WpmJUwAwAAFTIarMHuAyDOIQAAAAIAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg4jEAAAAAZoyTEwAAAAAAAAABAyDlTwAAAAAAAAAA/RtikPFtENilBw+avFCijUQfPJL6bpk04d+1qZiVMAMAABUyGqzBigMgziEAAAACAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAwAAAAADIOIxAAAAAGaMkxMAAAAA',
                                           'memo_type': 'text', 'signatures': [
                                              '79z6HkUc+ciVyOgTjprojn07sGfiwAKjxzzrS2RM91Xp/vq2w4JLv0S+Y0sgK3LqNdP9TtrTOsXjl3uHodJ4BA=='],
                                           'valid_after': '1999-07-14T17:32:11Z',
                                           'valid_before': '2024-07-09T05:47:56Z',
                                           'preconditions': {
                                               'timebounds': {'min_time': '931973531', 'max_time': '1720504076'}}},
                                          {'memo': '242316001', '_links': {'self': {
                                              'href': 'https://horizon.stellar.org/transactions/210e36caca2377401da2cbf0e6a9f64b94c64dd85da0832046fd639d57f7a81e'},
                                              'account': {
                                                  'href': 'https://horizon.stellar.org/accounts/GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5'},
                                              'ledger': {
                                                  'href': 'https://horizon.stellar.org/ledgers/52486512'},
                                              'operations': {
                                                  'href': 'https://horizon.stellar.org/transactions/210e36caca2377401da2cbf0e6a9f64b94c64dd85da0832046fd639d57f7a81e/operations{?cursor,limit,order}',
                                                  'templated': True}, 'effects': {
                                                  'href': 'https://horizon.stellar.org/transactions/210e36caca2377401da2cbf0e6a9f64b94c64dd85da0832046fd639d57f7a81e/effects{?cursor,limit,order}',
                                                  'templated': True}, 'precedes': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=asc&cursor=225427852521476096'},
                                              'succeeds': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=desc&cursor=225427852521476096'},
                                              'transaction': {
                                                  'href': 'https://horizon.stellar.org/transactions/210e36caca2377401da2cbf0e6a9f64b94c64dd85da0832046fd639d57f7a81e'}},
                                           'id': '210e36caca2377401da2cbf0e6a9f64b94c64dd85da0832046fd639d57f7a81e',
                                           'paging_token': '225427852521476096', 'successful': True,
                                           'hash': '210e36caca2377401da2cbf0e6a9f64b94c64dd85da0832046fd639d57f7a81e',
                                           'ledger': 52486512, 'created_at': '2024-07-09T01:13:39Z',
                                           'source_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                                           'source_account_sequence': '145182521808907272',
                                           'fee_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                                           'fee_charged': '100', 'max_fee': '45000', 'operation_count': 1,
                                           'envelope_xdr': 'AAAAAgAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAAr8gCA8q8AAPsCAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAOcXLhAAAAAQAAAAAAAAABAAAAAAJYIV7cdNJNLPz9/ZAMy3kUrWZ+3FoRNOyzWZrUVReUAAAAAAAAAABeVi9JAAAAAAAAAALAanpFAAAAQFIMQSxnU+ytzoUmN/35T7BoFA+n8RQHHdPh1ZGqgq4RL6zfzTPmA5ydNlWYE7bUTnkEgmqZavSzNDAXPkiGrQF5dZunAAAAQPLNdI/XZhVv4L2UnNOjzuX4hNo+ZbKYKV3tODJa7t5ANmWsC5HZehpadmJHpzIlSqQ8Ug3VQrzFzAi2ojO1nQQ=',
                                           'result_xdr': 'AAAAAAAAAGQAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAA=',
                                           'result_meta_xdr': 'AAAAAwAAAAAAAAACAAAAAwMg4XAAAAAAAAAAANJdnWDu5Lzz4a+ZqJ3dIG0+ciDA3gcjxGoGjhecW4aZAAAGtc70uH0CA8q8AAPsBwAAAAMAAAAAAAAAAAAAAAliaXRnby5jb20AAAAAAQIDAAAAAwAAAAAdSLNvNcCEWpUM1sSHHJ9W/JqMWbz1rhA/Sl1QO+4C9AAAAAEAAAAAl5Ai6URIK1qSERKZFtKcPXz/BINreqBQEc2793l1m6cAAAABAAAAAK2xJjeRTZSyAkiROb5tk6y8FeWa/G6LumaboZvAanpFAAAAAQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAwAAAAAAAAAAAAAAAAAAAAMAAAAAAyDcCgAAAABmjG+kAAAAAAAAAAEDIOFwAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABrXO9Lh9AgPKvAAD7AgAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg4XAAAAAAZoyOwwAAAAAAAAABAAAABAAAAAMDIOFwAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABrXO9Lh9AgPKvAAD7AgAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg4XAAAAAAZoyOwwAAAAAAAAABAyDhcAAAAAAAAAAA0l2dYO7kvPPhr5mond0gbT5yIMDeByPEagaOF5xbhpkAAAa1cJ6JNAIDyrwAA+wIAAAAAwAAAAAAAAAAAAAACWJpdGdvLmNvbQAAAAABAgMAAAADAAAAAB1Is281wIRalQzWxIccn1b8moxZvPWuED9KXVA77gL0AAAAAQAAAACXkCLpREgrWpIREpkW0pw9fP8Eg2t6oFARzbv3eXWbpwAAAAEAAAAArbEmN5FNlLICSJE5vm2TrLwV5Zr8bou6Zpuhm8BqekUAAAABAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAADAAAAAAAAAAAAAAAAAAAAAwAAAAADIOFwAAAAAGaMjsMAAAAAAAAAAwMg4WEAAAAAAAAAAAJYIV7cdNJNLPz9/ZAMy3kUrWZ+3FoRNOyzWZrUVReUAAAAAAX14DgCm0CuAAJrDAAAAAIAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAMAAAAAAyDhYQAAAABmjI5rAAAAAAAAAAEDIOFwAAAAAAAAAAACWCFe3HTSTSz8/f2QDMt5FK1mftxaETTss1ma1FUXlAAAAABkTA+BAptArgACawwAAAACAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg4WEAAAAAZoyOawAAAAAAAAAAAAAAAA==',
                                           'fee_meta_xdr': 'AAAAAgAAAAMDIN1QAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABrXO9LjhAgPKvAAD7AcAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg3AoAAAAAZoxvpAAAAAAAAAABAyDhcAAAAAAAAAAA0l2dYO7kvPPhr5mond0gbT5yIMDeByPEagaOF5xbhpkAAAa1zvS4fQIDyrwAA+wHAAAAAwAAAAAAAAAAAAAACWJpdGdvLmNvbQAAAAABAgMAAAADAAAAAB1Is281wIRalQzWxIccn1b8moxZvPWuED9KXVA77gL0AAAAAQAAAACXkCLpREgrWpIREpkW0pw9fP8Eg2t6oFARzbv3eXWbpwAAAAEAAAAArbEmN5FNlLICSJE5vm2TrLwV5Zr8bou6Zpuhm8BqekUAAAABAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAADAAAAAAAAAAAAAAAAAAAAAwAAAAADINwKAAAAAGaMb6QAAAAA',
                                           'memo_type': 'id', 'signatures': [
                                              'UgxBLGdT7K3OhSY3/flPsGgUD6fxFAcd0+HVkaqCrhEvrN/NM+YDnJ02VZgTttROeQSCaplq9LM0MBc+SIatAQ==',
                                              '8s10j9dmFW/gvZSc06PO5fiE2j5lspgpXe04Mlru3kA2ZawLkdl6Glp2YkenMiVKpDxSDdVCvMXMCLaiM7WdBA=='],
                                           'valid_after': '1970-01-01T00:00:00Z',
                                           'preconditions': {'timebounds': {'min_time': '0'}}}, {'memo': '1477',
                                                                                                 '_links': {'self': {
                                                                                                     'href': 'https://horizon.stellar.org/transactions/7bc532dee93c5f90d13b6178f9045d36d86de36d92f18fe2cc0e57ae076e6f90'},
                                                                                                     'account': {
                                                                                                         'href': 'https://horizon.stellar.org/accounts/GB5FUSCVVV7ZLKJVL7FRCSBQHZXYLMSWWXXYC7NH35GV57S5XWKEVA4V'},
                                                                                                     'ledger': {
                                                                                                         'href': 'https://horizon.stellar.org/ledgers/52485456'},
                                                                                                     'operations': {
                                                                                                         'href': 'https://horizon.stellar.org/transactions/7bc532dee93c5f90d13b6178f9045d36d86de36d92f18fe2cc0e57ae076e6f90/operations{?cursor,limit,order}',
                                                                                                         'templated': True},
                                                                                                     'effects': {
                                                                                                         'href': 'https://horizon.stellar.org/transactions/7bc532dee93c5f90d13b6178f9045d36d86de36d92f18fe2cc0e57ae076e6f90/effects{?cursor,limit,order}',
                                                                                                         'templated': True},
                                                                                                     'precedes': {
                                                                                                         'href': 'https://horizon.stellar.org/transactions?order=asc&cursor=225423317036126208'},
                                                                                                     'succeeds': {
                                                                                                         'href': 'https://horizon.stellar.org/transactions?order=desc&cursor=225423317036126208'},
                                                                                                     'transaction': {
                                                                                                         'href': 'https://horizon.stellar.org/transactions/7bc532dee93c5f90d13b6178f9045d36d86de36d92f18fe2cc0e57ae076e6f90'}},
                                                                                                 'id': '7bc532dee93c5f90d13b6178f9045d36d86de36d92f18fe2cc0e57ae076e6f90',
                                                                                                 'paging_token': '225423317036126208',
                                                                                                 'successful': True,
                                                                                                 'hash': '7bc532dee93c5f90d13b6178f9045d36d86de36d92f18fe2cc0e57ae076e6f90',
                                                                                                 'ledger': 52485456,
                                                                                                 'created_at': '2024-07-08T23:31:56Z',
                                                                                                 'source_account': 'GB5FUSCVVV7ZLKJVL7FRCSBQHZXYLMSWWXXYC7NH35GV57S5XWKEVA4V',
                                                                                                 'source_account_sequence': '151241818720588127',
                                                                                                 'fee_account': 'GB5FUSCVVV7ZLKJVL7FRCSBQHZXYLMSWWXXYC7NH35GV57S5XWKEVA4V',
                                                                                                 'fee_charged': '100',
                                                                                                 'max_fee': '500000',
                                                                                                 'operation_count': 1,
                                                                                                 'envelope_xdr': 'AAAAAgAAAAB6WkhVrX+VqTVfyxFIMD5vhbJWte+BfaffTV7+Xb2USgAHoSACGVGiAAZRXwAAAAEAAAAAAAAAAAAAAABmjHgXAAAAAgAAAAAAAAXFAAAAAQAAAAAAAAABAAAAANJdnWDu5Lzz4a+ZqJ3dIG0+ciDA3gcjxGoGjhecW4aZAAAAAAAAAAAC+vCAAAAAAAAAAAFdvZRKAAAAQPLPP6Fn/y3BlGK8kGgdYIK8e1czBKDlhViv+s5I+6Ps2i3QoilIQIjcjUwsAd3eaQF6GYrgswfqDwsJfLb8Pw0=',
                                                                                                 'result_xdr': 'AAAAAAAAAGQAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAA=',
                                                                                                 'result_meta_xdr': 'AAAAAwAAAAAAAAACAAAAAwMg3VAAAAAAAAAAAHpaSFWtf5WpNV/LEUgwPm+Fsla174F9p99NXv5dvZRKAAAC/DOelqcCGVGiAAZRXgAAAAEAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAMAAAAAAyDdMwAAAABmjHZDAAAAAAAAAAEDIN1QAAAAAAAAAAB6WkhVrX+VqTVfyxFIMD5vhbJWte+BfaffTV7+Xb2USgAAAvwznpanAhlRogAGUV8AAAABAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg3VAAAAAAZox27AAAAAAAAAABAAAABAAAAAMDIN1QAAAAAAAAAAB6WkhVrX+VqTVfyxFIMD5vhbJWte+BfaffTV7+Xb2USgAAAvwznpanAhlRogAGUV8AAAABAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg3VAAAAAAZox27AAAAAAAAAABAyDdUAAAAAAAAAAAelpIVa1/lak1X8sRSDA+b4WyVrXvgX2n301e/l29lEoAAAL8MKOmJwIZUaIABlFfAAAAAQAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAwAAAAADIN1QAAAAAGaMduwAAAAAAAAAAwMg3PUAAAAAAAAAANJdnWDu5Lzz4a+ZqJ3dIG0+ciDA3gcjxGoGjhecW4aZAAAGtcv5yGECA8q8AAPsBwAAAAMAAAAAAAAAAAAAAAliaXRnby5jb20AAAAAAQIDAAAAAwAAAAAdSLNvNcCEWpUM1sSHHJ9W/JqMWbz1rhA/Sl1QO+4C9AAAAAEAAAAAl5Ai6URIK1qSERKZFtKcPXz/BINreqBQEc2793l1m6cAAAABAAAAAK2xJjeRTZSyAkiROb5tk6y8FeWa/G6LumaboZvAanpFAAAAAQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAwAAAAAAAAAAAAAAAAAAAAMAAAAAAyDcCgAAAABmjG+kAAAAAAAAAAEDIN1QAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABrXO9LjhAgPKvAAD7AcAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg3AoAAAAAZoxvpAAAAAAAAAAAAAAAAA==',
                                                                                                 'fee_meta_xdr': 'AAAAAgAAAAMDIN0zAAAAAAAAAAB6WkhVrX+VqTVfyxFIMD5vhbJWte+BfaffTV7+Xb2USgAAAvwznpcLAhlRogAGUV4AAAABAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg3TMAAAAAZox2QwAAAAAAAAABAyDdUAAAAAAAAAAAelpIVa1/lak1X8sRSDA+b4WyVrXvgX2n301e/l29lEoAAAL8M56WpwIZUaIABlFeAAAAAQAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAwAAAAADIN0zAAAAAGaMdkMAAAAA',
                                                                                                 'memo_type': 'id',
                                                                                                 'signatures': [
                                                                                                     '8s8/oWf/LcGUYryQaB1ggrx7VzMEoOWFWK/6zkj7o+zaLdCiKUhAiNyNTCwB3d5pAXoZiuCzB+oPCwl8tvw/DQ=='],
                                                                                                 'valid_after': '1970-01-01T00:00:00Z',
                                                                                                 'valid_before': '2024-07-08T23:36:55Z',
                                                                                                 'preconditions': {
                                                                                                     'timebounds': {
                                                                                                         'min_time': '0',
                                                                                                         'max_time': '1720481815'}}},
                                          {'_links': {'self': {
                                              'href': 'https://horizon.stellar.org/transactions/76410c7616ab46b02b435edcd391286b524af7c05af3c0ecc4fd700c5c891c9d'},
                                              'account': {
                                                  'href': 'https://horizon.stellar.org/accounts/GDUQXQAR4ECNAYCTGZAS4TH4KJJIZDLXPR5V2YYRFRGGQ3LTXBFTBVW6'},
                                              'ledger': {'href': 'https://horizon.stellar.org/ledgers/52485365'},
                                              'operations': {
                                                  'href': 'https://horizon.stellar.org/transactions/76410c7616ab46b02b435edcd391286b524af7c05af3c0ecc4fd700c5c891c9d/operations{?cursor,limit,order}',
                                                  'templated': True}, 'effects': {
                                                  'href': 'https://horizon.stellar.org/transactions/76410c7616ab46b02b435edcd391286b524af7c05af3c0ecc4fd700c5c891c9d/effects{?cursor,limit,order}',
                                                  'templated': True}, 'precedes': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=asc&cursor=225422926194528256'},
                                              'succeeds': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=desc&cursor=225422926194528256'},
                                              'transaction': {
                                                  'href': 'https://horizon.stellar.org/transactions/76410c7616ab46b02b435edcd391286b524af7c05af3c0ecc4fd700c5c891c9d'}},
                                              'id': '76410c7616ab46b02b435edcd391286b524af7c05af3c0ecc4fd700c5c891c9d',
                                              'paging_token': '225422926194528256', 'successful': True,
                                              'hash': '76410c7616ab46b02b435edcd391286b524af7c05af3c0ecc4fd700c5c891c9d',
                                              'ledger': 52485365, 'created_at': '2024-07-08T23:23:13Z',
                                              'source_account': 'GDUQXQAR4ECNAYCTGZAS4TH4KJJIZDLXPR5V2YYRFRGGQ3LTXBFTBVW6',
                                              'source_account_sequence': '165671847978045531',
                                              'fee_account': 'GDUQXQAR4ECNAYCTGZAS4TH4KJJIZDLXPR5V2YYRFRGGQ3LTXBFTBVW6',
                                              'fee_charged': '100', 'max_fee': '500000', 'operation_count': 1,
                                              'envelope_xdr': 'AAAAAgAAAADpC8AR4QTQYFM2QS5M/FJSjI13fHtdYxEsTGhtc7hLMAAHoSACTJWrAAOQWwAAAAEAAAAAAAAAAAAAAABmjHYLAAAAAAAAAAEAAAAAAAAAAQAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAAAAAAAAAAdzWUAAAAAAAAAAABc7hLMAAAAEASOlWykeNajAWnTM0kdCXo0vvCcwUP4yqD5IpA5HihWcYKJKklgu7CutQLSDsd/BaNaph67PYoGqdWG2Snz40M',
                                              'result_xdr': 'AAAAAAAAAGQAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAA=',
                                              'result_meta_xdr': 'AAAAAwAAAAAAAAACAAAAAwMg3PUAAAAAAAAAAOkLwBHhBNBgUzZBLkz8UlKMjXd8e11jESxMaG1zuEswAAANioYJGKwCTJWrAAOQWgAAAAEAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAMAAAAAAyDcbAAAAABmjHHUAAAAAAAAAAEDINz1AAAAAAAAAADpC8AR4QTQYFM2QS5M/FJSjI13fHtdYxEsTGhtc7hLMAAADYqGCRisAkyVqwADkFsAAAABAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg3PUAAAAAZox04QAAAAAAAAABAAAABAAAAAMDINz1AAAAAAAAAADpC8AR4QTQYFM2QS5M/FJSjI13fHtdYxEsTGhtc7hLMAAADYqGCRisAkyVqwADkFsAAAABAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg3PUAAAAAZox04QAAAAAAAAABAyDc9QAAAAAAAAAA6QvAEeEE0GBTNkEuTPxSUoyNd3x7XWMRLExobXO4SzAAAA2KDtOErAJMlasAA5BbAAAAAQAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAwAAAAADINz1AAAAAGaMdOEAAAAAAAAAAwMg3AoAAAAAAAAAANJdnWDu5Lzz4a+ZqJ3dIG0+ciDA3gcjxGoGjhecW4aZAAAGtVTENGECA8q8AAPsBwAAAAMAAAAAAAAAAAAAAAliaXRnby5jb20AAAAAAQIDAAAAAwAAAAAdSLNvNcCEWpUM1sSHHJ9W/JqMWbz1rhA/Sl1QO+4C9AAAAAEAAAAAl5Ai6URIK1qSERKZFtKcPXz/BINreqBQEc2793l1m6cAAAABAAAAAK2xJjeRTZSyAkiROb5tk6y8FeWa/G6LumaboZvAanpFAAAAAQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAwAAAAAAAAAAAAAAAAAAAAMAAAAAAyDcCgAAAABmjG+kAAAAAAAAAAEDINz1AAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABrXL+chhAgPKvAAD7AcAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg3AoAAAAAZoxvpAAAAAAAAAAAAAAAAA==',
                                              'fee_meta_xdr': 'AAAAAgAAAAMDINxsAAAAAAAAAADpC8AR4QTQYFM2QS5M/FJSjI13fHtdYxEsTGhtc7hLMAAADYqGCRkQAkyVqwADkFoAAAABAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg3GwAAAAAZoxx1AAAAAAAAAABAyDc9QAAAAAAAAAA6QvAEeEE0GBTNkEuTPxSUoyNd3x7XWMRLExobXO4SzAAAA2KhgkYrAJMlasAA5BaAAAAAQAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAwAAAAADINxsAAAAAGaMcdQAAAAA',
                                              'memo_type': 'none', 'signatures': [
                                              'EjpVspHjWowFp0zNJHQl6NL7wnMFD+Mqg+SKQOR4oVnGCiSpJYLuwrrUC0g7HfwWjWqYeuz2KBqnVhtkp8+NDA=='],
                                              'valid_after': '1970-01-01T00:00:00Z',
                                              'valid_before': '2024-07-08T23:28:11Z',
                                              'preconditions': {
                                                  'timebounds': {'min_time': '0', 'max_time': '1720481291'}}},
                                          {'memo': '2959942072', '_links': {'self': {
                                              'href': 'https://horizon.stellar.org/transactions/b46adf2d07154a357eca34596bb0640518a218662aa91427151d2ad72eb87ed8'},
                                              'account': {
                                                  'href': 'https://horizon.stellar.org/accounts/GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5'},
                                              'ledger': {
                                                  'href': 'https://horizon.stellar.org/ledgers/52485130'},
                                              'operations': {
                                                  'href': 'https://horizon.stellar.org/transactions/b46adf2d07154a357eca34596bb0640518a218662aa91427151d2ad72eb87ed8/operations{?cursor,limit,order}',
                                                  'templated': True}, 'effects': {
                                                  'href': 'https://horizon.stellar.org/transactions/b46adf2d07154a357eca34596bb0640518a218662aa91427151d2ad72eb87ed8/effects{?cursor,limit,order}',
                                                  'templated': True}, 'precedes': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=asc&cursor=225421916876750848'},
                                              'succeeds': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=desc&cursor=225421916876750848'},
                                              'transaction': {
                                                  'href': 'https://horizon.stellar.org/transactions/b46adf2d07154a357eca34596bb0640518a218662aa91427151d2ad72eb87ed8'}},
                                           'id': 'b46adf2d07154a357eca34596bb0640518a218662aa91427151d2ad72eb87ed8',
                                           'paging_token': '225421916876750848', 'successful': True,
                                           'hash': 'b46adf2d07154a357eca34596bb0640518a218662aa91427151d2ad72eb87ed8',
                                           'ledger': 52485130, 'created_at': '2024-07-08T23:00:52Z',
                                           'source_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                                           'source_account_sequence': '145182521808907271',
                                           'fee_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                                           'fee_charged': '100', 'max_fee': '45000', 'operation_count': 1,
                                           'envelope_xdr': 'AAAAAgAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAAr8gCA8q8AAPsBwAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAACwbSG4AAAAAQAAAAAAAAABAAAAAIzE+22YZQVb7iQ2nUcn8/F5TJRXJ1JvqH3WH97NRp9BAAAAAAAAAAACpM6AAAAAAAAAAALAanpFAAAAQADbLtlsGr9Gxtys5mPkamR9VnY7wh2z/0g9ydRDrXxpZqnjSEmVE6OI3V+kzVbScP0VDf6x8g3S6KrfH3866wZ5dZunAAAAQFQNhgPrF3jYBWGg4uGzqR3EjRpf90I3hCCQMeAMPQ1Fhby05ZTNArgf2aGdjUGoxsvYp7F7GvjWk0grERfE0gE=',
                                           'result_xdr': 'AAAAAAAAAGQAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAA=',
                                           'result_meta_xdr': 'AAAAAwAAAAAAAAACAAAAAwMg3AoAAAAAAAAAANJdnWDu5Lzz4a+ZqJ3dIG0+ciDA3gcjxGoGjhecW4aZAAAGtVdpAuECA8q8AAPsBgAAAAMAAAAAAAAAAAAAAAliaXRnby5jb20AAAAAAQIDAAAAAwAAAAAdSLNvNcCEWpUM1sSHHJ9W/JqMWbz1rhA/Sl1QO+4C9AAAAAEAAAAAl5Ai6URIK1qSERKZFtKcPXz/BINreqBQEc2793l1m6cAAAABAAAAAK2xJjeRTZSyAkiROb5tk6y8FeWa/G6LumaboZvAanpFAAAAAQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAwAAAAAAAAAAAAAAAAAAAAMAAAAAAyDV7AAAAABmjEzqAAAAAAAAAAEDINwKAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABrVXaQLhAgPKvAAD7AcAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg3AoAAAAAZoxvpAAAAAAAAAABAAAABAAAAAMDINwKAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABrVXaQLhAgPKvAAD7AcAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg3AoAAAAAZoxvpAAAAAAAAAABAyDcCgAAAAAAAAAA0l2dYO7kvPPhr5mond0gbT5yIMDeByPEagaOF5xbhpkAAAa1VMQ0YQIDyrwAA+wHAAAAAwAAAAAAAAAAAAAACWJpdGdvLmNvbQAAAAABAgMAAAADAAAAAB1Is281wIRalQzWxIccn1b8moxZvPWuED9KXVA77gL0AAAAAQAAAACXkCLpREgrWpIREpkW0pw9fP8Eg2t6oFARzbv3eXWbpwAAAAEAAAAArbEmN5FNlLICSJE5vm2TrLwV5Zr8bou6Zpuhm8BqekUAAAABAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAADAAAAAAAAAAAAAAAAAAAAAwAAAAADINwKAAAAAGaMb6QAAAAAAAAAAwMg29MAAAAAAAAAAIzE+22YZQVb7iQ2nUcn8/F5TJRXJ1JvqH3WH97NRp9BAAAxniSPvN8CfuqhAAK1RgAAAAEAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAMAAAAAAyDaugAAAABmjGg3AAAAAAAAAAEDINwKAAAAAAAAAACMxPttmGUFW+4kNp1HJ/PxeUyUVydSb6h91h/ezUafQQAAMZ4nNItfAn7qoQACtUYAAAABAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg2roAAAAAZoxoNwAAAAAAAAAAAAAAAA==',
                                           'fee_meta_xdr': 'AAAAAgAAAAMDINolAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABrVXaQNFAgPKvAAD7AYAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg1ewAAAAAZoxM6gAAAAAAAAABAyDcCgAAAAAAAAAA0l2dYO7kvPPhr5mond0gbT5yIMDeByPEagaOF5xbhpkAAAa1V2kC4QIDyrwAA+wGAAAAAwAAAAAAAAAAAAAACWJpdGdvLmNvbQAAAAABAgMAAAADAAAAAB1Is281wIRalQzWxIccn1b8moxZvPWuED9KXVA77gL0AAAAAQAAAACXkCLpREgrWpIREpkW0pw9fP8Eg2t6oFARzbv3eXWbpwAAAAEAAAAArbEmN5FNlLICSJE5vm2TrLwV5Zr8bou6Zpuhm8BqekUAAAABAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAADAAAAAAAAAAAAAAAAAAAAAwAAAAADINXsAAAAAGaMTOoAAAAA',
                                           'memo_type': 'id', 'signatures': [
                                              'ANsu2Wwav0bG3KzmY+RqZH1WdjvCHbP/SD3J1EOtfGlmqeNISZUTo4jdX6TNVtJw/RUN/rHyDdLoqt8ffzrrBg==',
                                              'VA2GA+sXeNgFYaDi4bOpHcSNGl/3QjeEIJAx4Aw9DUWFvLTllM0CuB/ZoZ2NQajGy9insXsa+NaTSCsRF8TSAQ=='],
                                           'valid_after': '1970-01-01T00:00:00Z',
                                           'preconditions': {'timebounds': {'min_time': '0'}}},
                                          {'memo': '86644', 'memo_bytes': 'ODY2NDQ=', '_links': {'self': {
                                              'href': 'https://horizon.stellar.org/transactions/96e7cc22bb4cb249c9a85f1ac2320dcd02dd72d08b2e6a6c23e5359eb23c9009'},
                                              'account': {
                                                  'href': 'https://horizon.stellar.org/accounts/GBZLHGDYMSVF4X6DYAGKLIQX3F64W3MXNDVGHKQPR226TCJ5QJ2ZQKVA'},
                                              'ledger': {
                                                  'href': 'https://horizon.stellar.org/ledgers/52484645'},
                                              'operations': {
                                                  'href': 'https://horizon.stellar.org/transactions/96e7cc22bb4cb249c9a85f1ac2320dcd02dd72d08b2e6a6c23e5359eb23c9009/operations{?cursor,limit,order}',
                                                  'templated': True},
                                              'effects': {
                                                  'href': 'https://horizon.stellar.org/transactions/96e7cc22bb4cb249c9a85f1ac2320dcd02dd72d08b2e6a6c23e5359eb23c9009/effects{?cursor,limit,order}',
                                                  'templated': True},
                                              'precedes': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=asc&cursor=225419833817423872'},
                                              'succeeds': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=desc&cursor=225419833817423872'},
                                              'transaction': {
                                                  'href': 'https://horizon.stellar.org/transactions/96e7cc22bb4cb249c9a85f1ac2320dcd02dd72d08b2e6a6c23e5359eb23c9009'}},
                                           'id': '96e7cc22bb4cb249c9a85f1ac2320dcd02dd72d08b2e6a6c23e5359eb23c9009',
                                           'paging_token': '225419833817423872', 'successful': True,
                                           'hash': '96e7cc22bb4cb249c9a85f1ac2320dcd02dd72d08b2e6a6c23e5359eb23c9009',
                                           'ledger': 52484645, 'created_at': '2024-07-08T22:15:09Z',
                                           'source_account': 'GBZLHGDYMSVF4X6DYAGKLIQX3F64W3MXNDVGHKQPR226TCJ5QJ2ZQKVA',
                                           'source_account_sequence': '121576896218768132',
                                           'fee_account': 'GBZLHGDYMSVF4X6DYAGKLIQX3F64W3MXNDVGHKQPR226TCJ5QJ2ZQKVA',
                                           'fee_charged': '100', 'max_fee': '100', 'operation_count': 1,
                                           'envelope_xdr': 'AAAAAgAAAABys5h4ZKpeX8PADKWiF9l9y22XaOpjqg+OtemJPYJ1mAAAAGQBr+2LAAOjBAAAAAAAAAABAAAABTg2NjQ0AAAAAAAAAQAAAAAAAAABAAAAANJdnWDu5Lzz4a+ZqJ3dIG0+ciDA3gcjxGoGjhecW4aZAAAAAAAAAAEP6piAAAAAAAAAAAE9gnWYAAAAQB5Iz29Pd45rdgiAryM0lTcSuklPt5AFZgT5fT4vKS3sIoXjFGUVsV6gnFAQuUO/UAt488A+GQ+AztPzfEuU3wA=',
                                           'result_xdr': 'AAAAAAAAAGQAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAA=',
                                           'result_meta_xdr': 'AAAAAwAAAAAAAAACAAAAAwMg2iUAAAAAAAAAAHKzmHhkql5fw8AMpaIX2X3LbZdo6mOqD4616Yk9gnWYAAAdWFFiW4MBr+2LAAOjAwAAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAMAAAAAAyDYxwAAAABmjF0tAAAAAAAAAAEDINolAAAAAAAAAABys5h4ZKpeX8PADKWiF9l9y22XaOpjqg+OtemJPYJ1mAAAHVhRYluDAa/tiwADowQAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg2iUAAAAAZoxk7QAAAAAAAAABAAAABAAAAAMDINolAAAAAAAAAABys5h4ZKpeX8PADKWiF9l9y22XaOpjqg+OtemJPYJ1mAAAHVhRYluDAa/tiwADowQAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg2iUAAAAAZoxk7QAAAAAAAAABAyDaJQAAAAAAAAAAcrOYeGSqXl/DwAylohfZfcttl2jqY6oPjrXpiT2CdZgAAB1XQXfDAwGv7YsAA6MEAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAwAAAAADINolAAAAAGaMZO0AAAAAAAAAAwMg130AAAAAAAAAANJdnWDu5Lzz4a+ZqJ3dIG0+ciDA3gcjxGoGjhecW4aZAAAGtEd+asUCA8q8AAPsBgAAAAMAAAAAAAAAAAAAAAliaXRnby5jb20AAAAAAQIDAAAAAwAAAAAdSLNvNcCEWpUM1sSHHJ9W/JqMWbz1rhA/Sl1QO+4C9AAAAAEAAAAAl5Ai6URIK1qSERKZFtKcPXz/BINreqBQEc2793l1m6cAAAABAAAAAK2xJjeRTZSyAkiROb5tk6y8FeWa/G6LumaboZvAanpFAAAAAQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAwAAAAAAAAAAAAAAAAAAAAMAAAAAAyDV7AAAAABmjEzqAAAAAAAAAAEDINolAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABrVXaQNFAgPKvAAD7AYAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg1ewAAAAAZoxM6gAAAAAAAAAAAAAAAA==',
                                           'fee_meta_xdr': 'AAAAAgAAAAMDINjHAAAAAAAAAABys5h4ZKpeX8PADKWiF9l9y22XaOpjqg+OtemJPYJ1mAAAHVhRYlvnAa/tiwADowMAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg2McAAAAAZoxdLQAAAAAAAAABAyDaJQAAAAAAAAAAcrOYeGSqXl/DwAylohfZfcttl2jqY6oPjrXpiT2CdZgAAB1YUWJbgwGv7YsAA6MDAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAwAAAAADINjHAAAAAGaMXS0AAAAA',
                                           'memo_type': 'text', 'signatures': [
                                              'HkjPb093jmt2CICvIzSVNxK6SU+3kAVmBPl9Pi8pLewiheMUZRWxXqCcUBC5Q79QC3jzwD4ZD4DO0/N8S5TfAA==']},
                                          {'memo': '1477', '_links': {'self': {
                                              'href': 'https://horizon.stellar.org/transactions/917b3a51f47a5b70f36f6bdd265b669f843a9650ee99f93212a4c0b5af494561'},
                                              'account': {
                                                  'href': 'https://horizon.stellar.org/accounts/GA4IRJ52YGZQJDS7XJ375UGSI4FE4KQXHFYUUYNR5QXDVQNAXQTLRJAB'},
                                              'ledger': {
                                                  'href': 'https://horizon.stellar.org/ledgers/52483965'},
                                              'operations': {
                                                  'href': 'https://horizon.stellar.org/transactions/917b3a51f47a5b70f36f6bdd265b669f843a9650ee99f93212a4c0b5af494561/operations{?cursor,limit,order}',
                                                  'templated': True}, 'effects': {
                                                  'href': 'https://horizon.stellar.org/transactions/917b3a51f47a5b70f36f6bdd265b669f843a9650ee99f93212a4c0b5af494561/effects{?cursor,limit,order}',
                                                  'templated': True}, 'precedes': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=asc&cursor=225416913239658496'},
                                              'succeeds': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=desc&cursor=225416913239658496'},
                                              'transaction': {
                                                  'href': 'https://horizon.stellar.org/transactions/917b3a51f47a5b70f36f6bdd265b669f843a9650ee99f93212a4c0b5af494561'}},
                                           'id': '917b3a51f47a5b70f36f6bdd265b669f843a9650ee99f93212a4c0b5af494561',
                                           'paging_token': '225416913239658496', 'successful': True,
                                           'hash': '917b3a51f47a5b70f36f6bdd265b669f843a9650ee99f93212a4c0b5af494561',
                                           'ledger': 52483965, 'created_at': '2024-07-08T21:10:41Z',
                                           'source_account': 'GA4IRJ52YGZQJDS7XJ375UGSI4FE4KQXHFYUUYNR5QXDVQNAXQTLRJAB',
                                           'source_account_sequence': '143558233897347626',
                                           'fee_account': 'GA4IRJ52YGZQJDS7XJ375UGSI4FE4KQXHFYUUYNR5QXDVQNAXQTLRJAB',
                                           'fee_charged': '100', 'max_fee': '1000000', 'operation_count': 1,
                                           'envelope_xdr': 'AAAAAgAAAAA4iKe6wbMEjl+6d/7Q0kcKTioXOXFKYbHsLjrBoLwmuAAPQkAB/gV0AAiqKgAAAAEAAAAAAAAAAAAAAABmjFb5AAAAAgAAAAAAAAXFAAAAAQAAAAAAAAABAAAAANJdnWDu5Lzz4a+ZqJ3dIG0+ciDA3gcjxGoGjhecW4aZAAAAAAAAAADPLEwGAAAAAAAAAAGgvCa4AAAAQOT6Xa/Z+9mEkblG09qKfhO3wAIahuDOzXQMCBn/wiuXEz6cCibWwGMYae8UbafPswB4nVqz0ob6mK8fTBvangk=',
                                           'result_xdr': 'AAAAAAAAAGQAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAA=',
                                           'result_meta_xdr': 'AAAAAwAAAAAAAAACAAAAAwMg130AAAAAAAAAADiIp7rBswSOX7p3/tDSRwpOKhc5cUphsewuOsGgvCa4AAAB+wXNcV4B/gV0AAiqKQAAAAEAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAMAAAAAAyDXEgAAAABmjFNtAAAAAAAAAAEDINd9AAAAAAAAAAA4iKe6wbMEjl+6d/7Q0kcKTioXOXFKYbHsLjrBoLwmuAAAAfsFzXFeAf4FdAAIqioAAAABAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg130AAAAAZoxV0QAAAAAAAAABAAAABAAAAAMDINd9AAAAAAAAAAA4iKe6wbMEjl+6d/7Q0kcKTioXOXFKYbHsLjrBoLwmuAAAAfsFzXFeAf4FdAAIqioAAAABAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg130AAAAAZoxV0QAAAAAAAAABAyDXfQAAAAAAAAAAOIinusGzBI5funf+0NJHCk4qFzlxSmGx7C46waC8JrgAAAH6NqElWAH+BXQACKoqAAAAAQAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAwAAAAADINd9AAAAAGaMVdEAAAAAAAAAAwMg1ewAAAAAAAAAANJdnWDu5Lzz4a+ZqJ3dIG0+ciDA3gcjxGoGjhecW4aZAAAGs3hSHr8CA8q8AAPsBgAAAAMAAAAAAAAAAAAAAAliaXRnby5jb20AAAAAAQIDAAAAAwAAAAAdSLNvNcCEWpUM1sSHHJ9W/JqMWbz1rhA/Sl1QO+4C9AAAAAEAAAAAl5Ai6URIK1qSERKZFtKcPXz/BINreqBQEc2793l1m6cAAAABAAAAAK2xJjeRTZSyAkiROb5tk6y8FeWa/G6LumaboZvAanpFAAAAAQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAwAAAAAAAAAAAAAAAAAAAAMAAAAAAyDV7AAAAABmjEzqAAAAAAAAAAEDINd9AAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABrRHfmrFAgPKvAAD7AYAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg1ewAAAAAZoxM6gAAAAAAAAAAAAAAAA==',
                                           'fee_meta_xdr': 'AAAAAgAAAAMDINctAAAAAAAAAAA4iKe6wbMEjl+6d/7Q0kcKTioXOXFKYbHsLjrBoLwmuAAAAfsFzXHCAf4FdAAIqikAAAABAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg1xIAAAAAZoxTbQAAAAAAAAABAyDXfQAAAAAAAAAAOIinusGzBI5funf+0NJHCk4qFzlxSmGx7C46waC8JrgAAAH7Bc1xXgH+BXQACKopAAAAAQAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAwAAAAADINcSAAAAAGaMU20AAAAA',
                                           'memo_type': 'id', 'signatures': [
                                              '5Ppdr9n72YSRuUbT2op+E7fAAhqG4M7NdAwIGf/CK5cTPpwKJtbAYxhp7xRtp8+zAHidWrPShvqYrx9MG9qeCQ=='],
                                           'valid_after': '1970-01-01T00:00:00Z',
                                           'valid_before': '2024-07-08T21:15:37Z',
                                           'preconditions': {
                                               'timebounds': {'min_time': '0', 'max_time': '1720473337'}}},
                                          {'memo': '691965', '_links': {'self': {
                                              'href': 'https://horizon.stellar.org/transactions/ff1e1b7bbdcd575984ee2ef4d339b253afb84107792ffce43b24c165c4f5fdca'},
                                              'account': {
                                                  'href': 'https://horizon.stellar.org/accounts/GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5'},
                                              'ledger': {
                                                  'href': 'https://horizon.stellar.org/ledgers/52483564'},
                                              'operations': {
                                                  'href': 'https://horizon.stellar.org/transactions/ff1e1b7bbdcd575984ee2ef4d339b253afb84107792ffce43b24c165c4f5fdca/operations{?cursor,limit,order}',
                                                  'templated': True}, 'effects': {
                                                  'href': 'https://horizon.stellar.org/transactions/ff1e1b7bbdcd575984ee2ef4d339b253afb84107792ffce43b24c165c4f5fdca/effects{?cursor,limit,order}',
                                                  'templated': True}, 'precedes': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=asc&cursor=225415190958120960'},
                                              'succeeds': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=desc&cursor=225415190958120960'},
                                              'transaction': {
                                                  'href': 'https://horizon.stellar.org/transactions/ff1e1b7bbdcd575984ee2ef4d339b253afb84107792ffce43b24c165c4f5fdca'}},
                                           'id': 'ff1e1b7bbdcd575984ee2ef4d339b253afb84107792ffce43b24c165c4f5fdca',
                                           'paging_token': '225415190958120960', 'successful': True,
                                           'hash': 'ff1e1b7bbdcd575984ee2ef4d339b253afb84107792ffce43b24c165c4f5fdca',
                                           'ledger': 52483564, 'created_at': '2024-07-08T20:32:42Z',
                                           'source_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                                           'source_account_sequence': '145182521808907270',
                                           'fee_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                                           'fee_charged': '100', 'max_fee': '45000', 'operation_count': 1,
                                           'envelope_xdr': 'AAAAAgAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAAr8gCA8q8AAPsBgAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAACo79AAAAAQAAAAAAAAABAAAAAOXDqt/kCw0khZz7brrwCR79i8j1W5kyVZKR8d8S3vVOAAAAAAAAAAAGSbXwAAAAAAAAAALAanpFAAAAQIYedPwEYeBX2TmPr+oXf5CWPVqmOCS8UXmHcljvaLs+RDA7xC2XF5bvmBadtP1GB3JSIIX4A+Q+UsoU4N442w95dZunAAAAQLBod7iSKX5AgnM1R5lhg4AZHWAWzcN9Z8nGDKK46czao08z8+BSHidstWqj3Vvcuump9PPE3MnLjDxTiasFnwE=',
                                           'result_xdr': 'AAAAAAAAAGQAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAA=',
                                           'result_meta_xdr': 'AAAAAwAAAAAAAAACAAAAAwMg1ewAAAAAAAAAANJdnWDu5Lzz4a+ZqJ3dIG0+ciDA3gcjxGoGjhecW4aZAAAGs36b1K8CA8q8AAPsBQAAAAMAAAAAAAAAAAAAAAliaXRnby5jb20AAAAAAQIDAAAAAwAAAAAdSLNvNcCEWpUM1sSHHJ9W/JqMWbz1rhA/Sl1QO+4C9AAAAAEAAAAAl5Ai6URIK1qSERKZFtKcPXz/BINreqBQEc2793l1m6cAAAABAAAAAK2xJjeRTZSyAkiROb5tk6y8FeWa/G6LumaboZvAanpFAAAAAQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAwAAAAAAAAAAAAAAAAAAAAMAAAAAAyDV2gAAAABmjEyEAAAAAAAAAAEDINXsAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABrN+m9SvAgPKvAAD7AYAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg1ewAAAAAZoxM6gAAAAAAAAABAAAABAAAAAMDINXsAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABrN+m9SvAgPKvAAD7AYAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg1ewAAAAAZoxM6gAAAAAAAAABAyDV7AAAAAAAAAAA0l2dYO7kvPPhr5mond0gbT5yIMDeByPEagaOF5xbhpkAAAazeFIevwIDyrwAA+wGAAAAAwAAAAAAAAAAAAAACWJpdGdvLmNvbQAAAAABAgMAAAADAAAAAB1Is281wIRalQzWxIccn1b8moxZvPWuED9KXVA77gL0AAAAAQAAAACXkCLpREgrWpIREpkW0pw9fP8Eg2t6oFARzbv3eXWbpwAAAAEAAAAArbEmN5FNlLICSJE5vm2TrLwV5Zr8bou6Zpuhm8BqekUAAAABAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAADAAAAAAAAAAAAAAAAAAAAAwAAAAADINXsAAAAAGaMTOoAAAAAAAAAAwMg1ekAAAAAAAAAAOXDqt/kCw0khZz7brrwCR79i8j1W5kyVZKR8d8S3vVOAAAACSHSFKgCYcLAAABKJAAAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAMAAAAAAyDUmQAAAABmjEVrAAAAAAAAAAEDINXsAAAAAAAAAADlw6rf5AsNJIWc+2668Ake/YvI9VuZMlWSkfHfEt71TgAAAAkoG8qYAmHCwAAASiQAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg1JkAAAAAZoxFawAAAAAAAAAAAAAAAA==',
                                           'fee_meta_xdr': 'AAAAAgAAAAMDINXaAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABrN+m9UTAgPKvAAD7AUAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg1doAAAAAZoxMhAAAAAAAAAABAyDV7AAAAAAAAAAA0l2dYO7kvPPhr5mond0gbT5yIMDeByPEagaOF5xbhpkAAAazfpvUrwIDyrwAA+wFAAAAAwAAAAAAAAAAAAAACWJpdGdvLmNvbQAAAAABAgMAAAADAAAAAB1Is281wIRalQzWxIccn1b8moxZvPWuED9KXVA77gL0AAAAAQAAAACXkCLpREgrWpIREpkW0pw9fP8Eg2t6oFARzbv3eXWbpwAAAAEAAAAArbEmN5FNlLICSJE5vm2TrLwV5Zr8bou6Zpuhm8BqekUAAAABAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAADAAAAAAAAAAAAAAAAAAAAAwAAAAADINXaAAAAAGaMTIQAAAAA',
                                           'memo_type': 'id', 'signatures': [
                                              'hh50/ARh4FfZOY+v6hd/kJY9WqY4JLxReYdyWO9ouz5EMDvELZcXlu+YFp20/UYHclIghfgD5D5SyhTg3jjbDw==',
                                              'sGh3uJIpfkCCczVHmWGDgBkdYBbNw31nycYMorjpzNqjTzPz4FIeJ2y1aqPdW9y66an088TcycuMPFOJqwWfAQ=='],
                                           'valid_after': '1970-01-01T00:00:00Z',
                                           'preconditions': {'timebounds': {'min_time': '0'}}}, {'memo': '3988502092',
                                                                                                 '_links': {'self': {
                                                                                                     'href': 'https://horizon.stellar.org/transactions/c08bd472abe2d4757c138fa2b277a3eecd847da7fb9f895735dc48e61e21b0b1'},
                                                                                                     'account': {
                                                                                                         'href': 'https://horizon.stellar.org/accounts/GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5'},
                                                                                                     'ledger': {
                                                                                                         'href': 'https://horizon.stellar.org/ledgers/52483546'},
                                                                                                     'operations': {
                                                                                                         'href': 'https://horizon.stellar.org/transactions/c08bd472abe2d4757c138fa2b277a3eecd847da7fb9f895735dc48e61e21b0b1/operations{?cursor,limit,order}',
                                                                                                         'templated': True},
                                                                                                     'effects': {
                                                                                                         'href': 'https://horizon.stellar.org/transactions/c08bd472abe2d4757c138fa2b277a3eecd847da7fb9f895735dc48e61e21b0b1/effects{?cursor,limit,order}',
                                                                                                         'templated': True},
                                                                                                     'precedes': {
                                                                                                         'href': 'https://horizon.stellar.org/transactions?order=asc&cursor=225415113648803840'},
                                                                                                     'succeeds': {
                                                                                                         'href': 'https://horizon.stellar.org/transactions?order=desc&cursor=225415113648803840'},
                                                                                                     'transaction': {
                                                                                                         'href': 'https://horizon.stellar.org/transactions/c08bd472abe2d4757c138fa2b277a3eecd847da7fb9f895735dc48e61e21b0b1'}},
                                                                                                 'id': 'c08bd472abe2d4757c138fa2b277a3eecd847da7fb9f895735dc48e61e21b0b1',
                                                                                                 'paging_token': '225415113648803840',
                                                                                                 'successful': True,
                                                                                                 'hash': 'c08bd472abe2d4757c138fa2b277a3eecd847da7fb9f895735dc48e61e21b0b1',
                                                                                                 'ledger': 52483546,
                                                                                                 'created_at': '2024-07-08T20:31:00Z',
                                                                                                 'source_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                                                                                                 'source_account_sequence': '145182521808907269',
                                                                                                 'fee_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                                                                                                 'fee_charged': '100',
                                                                                                 'max_fee': '45000',
                                                                                                 'operation_count': 1,
                                                                                                 'envelope_xdr': 'AAAAAgAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAAr8gCA8q8AAPsBQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAADtu7ZMAAAAAQAAAAAAAAABAAAAAHe3frx8lkr3H9drsQRM5Z9vYwlAwa/imIqB/y1ayFrEAAAAAAAAAACLT8HgAAAAAAAAAALAanpFAAAAQLLoODMa56WxDmXVs1mjgXSe9uOQxo65Qgwn76FJ+qN8SnWVgePSslEvNbdKnPMIvHbxTLhj818xgwnPWj2iaQp5dZunAAAAQGvo53IIdqsDhBYjH02iT6cE1oVIlMqGOurYTFaAIRHCi0RERjSgSCvv6mBysxYFqO/DN2Y83RSt8LSgz0sTnQg=',
                                                                                                 'result_xdr': 'AAAAAAAAAGQAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAA=',
                                                                                                 'result_meta_xdr': 'AAAAAwAAAAAAAAACAAAAAwMg1doAAAAAAAAAANJdnWDu5Lzz4a+ZqJ3dIG0+ciDA3gcjxGoGjhecW4aZAAAGtAnrlvMCA8q8AAPsBAAAAAMAAAAAAAAAAAAAAAliaXRnby5jb20AAAAAAQIDAAAAAwAAAAAdSLNvNcCEWpUM1sSHHJ9W/JqMWbz1rhA/Sl1QO+4C9AAAAAEAAAAAl5Ai6URIK1qSERKZFtKcPXz/BINreqBQEc2793l1m6cAAAABAAAAAK2xJjeRTZSyAkiROb5tk6y8FeWa/G6LumaboZvAanpFAAAAAQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAwAAAAAAAAAAAAAAAAAAAAMAAAAAAyDVKQAAAABmjEiaAAAAAAAAAAEDINXaAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABrQJ65bzAgPKvAAD7AUAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg1doAAAAAZoxMhAAAAAAAAAABAAAABAAAAAMDINXaAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABrQJ65bzAgPKvAAD7AUAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg1doAAAAAZoxMhAAAAAAAAAABAyDV2gAAAAAAAAAA0l2dYO7kvPPhr5mond0gbT5yIMDeByPEagaOF5xbhpkAAAazfpvVEwIDyrwAA+wFAAAAAwAAAAAAAAAAAAAACWJpdGdvLmNvbQAAAAABAgMAAAADAAAAAB1Is281wIRalQzWxIccn1b8moxZvPWuED9KXVA77gL0AAAAAQAAAACXkCLpREgrWpIREpkW0pw9fP8Eg2t6oFARzbv3eXWbpwAAAAEAAAAArbEmN5FNlLICSJE5vm2TrLwV5Zr8bou6Zpuhm8BqekUAAAABAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAADAAAAAAAAAAAAAAAAAAAAAwAAAAADINXaAAAAAGaMTIQAAAAAAAAAAwMg1WUAAAAAAAAAAHe3frx8lkr3H9drsQRM5Z9vYwlAwa/imIqB/y1ayFrEAASCWxU2YjECbC1XAAACIwAAAAIAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAMAAAAAAyDOwgAAAABmjCRYAAAAAAAAAAEDINXaAAAAAAAAAAB3t368fJZK9x/Xa7EETOWfb2MJQMGv4piKgf8tWshaxAAEglughiQRAmwtVwAAAiMAAAACAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMgzsIAAAAAZowkWAAAAAAAAAAAAAAAAA==',
                                                                                                 'fee_meta_xdr': 'AAAAAgAAAAMDINVLAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABrQJ65dXAgPKvAAD7AQAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg1SkAAAAAZoxImgAAAAAAAAABAyDV2gAAAAAAAAAA0l2dYO7kvPPhr5mond0gbT5yIMDeByPEagaOF5xbhpkAAAa0CeuW8wIDyrwAA+wEAAAAAwAAAAAAAAAAAAAACWJpdGdvLmNvbQAAAAABAgMAAAADAAAAAB1Is281wIRalQzWxIccn1b8moxZvPWuED9KXVA77gL0AAAAAQAAAACXkCLpREgrWpIREpkW0pw9fP8Eg2t6oFARzbv3eXWbpwAAAAEAAAAArbEmN5FNlLICSJE5vm2TrLwV5Zr8bou6Zpuhm8BqekUAAAABAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAADAAAAAAAAAAAAAAAAAAAAAwAAAAADINUpAAAAAGaMSJoAAAAA',
                                                                                                 'memo_type': 'id',
                                                                                                 'signatures': [
                                                                                                     'sug4MxrnpbEOZdWzWaOBdJ7245DGjrlCDCfvoUn6o3xKdZWB49KyUS81t0qc8wi8dvFMuGPzXzGDCc9aPaJpCg==',
                                                                                                     'a+jncgh2qwOEFiMfTaJPpwTWhUiUyoY66thMVoAhEcKLRERGNKBIK+/qYHKzFgWo78M3ZjzdFK3wtKDPSxOdCA=='],
                                                                                                 'valid_after': '1970-01-01T00:00:00Z',
                                                                                                 'preconditions': {
                                                                                                     'timebounds': {
                                                                                                         'min_time': '0'}}},
                                          {'memo': '115238', 'memo_bytes': 'MTE1MjM4', '_links': {'self': {
                                              'href': 'https://horizon.stellar.org/transactions/da840859197f71d99350757de57b6e6ba35304ad3c6c54ca6da3769b741f1bb1'},
                                              'account': {
                                                  'href': 'https://horizon.stellar.org/accounts/GAG2TQZMIZMZTFPQZ3ACCSAOMMFLF4ITR53Z4X2WTAI62Z3QSPQ5XB35'},
                                              'ledger': {
                                                  'href': 'https://horizon.stellar.org/ledgers/52483403'},
                                              'operations': {
                                                  'href': 'https://horizon.stellar.org/transactions/da840859197f71d99350757de57b6e6ba35304ad3c6c54ca6da3769b741f1bb1/operations{?cursor,limit,order}',
                                                  'templated': True},
                                              'effects': {
                                                  'href': 'https://horizon.stellar.org/transactions/da840859197f71d99350757de57b6e6ba35304ad3c6c54ca6da3769b741f1bb1/effects{?cursor,limit,order}',
                                                  'templated': True},
                                              'precedes': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=asc&cursor=225414499467804672'},
                                              'succeeds': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=desc&cursor=225414499467804672'},
                                              'transaction': {
                                                  'href': 'https://horizon.stellar.org/transactions/da840859197f71d99350757de57b6e6ba35304ad3c6c54ca6da3769b741f1bb1'}},
                                           'id': 'da840859197f71d99350757de57b6e6ba35304ad3c6c54ca6da3769b741f1bb1',
                                           'paging_token': '225414499467804672', 'successful': True,
                                           'hash': 'da840859197f71d99350757de57b6e6ba35304ad3c6c54ca6da3769b741f1bb1',
                                           'ledger': 52483403, 'created_at': '2024-07-08T20:17:30Z',
                                           'source_account': 'GAG2TQZMIZMZTFPQZ3ACCSAOMMFLF4ITR53Z4X2WTAI62Z3QSPQ5XB35',
                                           'source_account_sequence': '208840521320255891',
                                           'fee_account': 'GAG2TQZMIZMZTFPQZ3ACCSAOMMFLF4ITR53Z4X2WTAI62Z3QSPQ5XB35',
                                           'fee_charged': '100', 'max_fee': '250005', 'operation_count': 1,
                                           'envelope_xdr': 'AAAAAgAAAAANqcMsRlmZlfDOwCFIDmMKsvETj3eeX1aYEe1ncJPh2wAD0JUC5fNZAABRkwAAAAEAAAAAAQtgswAAAABmjHN6AAAAAQAAAAYxMTUyMzgAAAAAAAEAAAAAAAAAAQAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAAAAAAAAAAun3ZowAAAAAAAAABcJPh2wAAAEByNlNLkEMW1850fZS5zoYjlPZOHK8pJhNc5WtjSizS5RZ4hdh75sdnAQicuxKf6giO70EJqsEHOI9kIpdwzEAA',
                                           'result_xdr': 'AAAAAAAAAGQAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAA=',
                                           'result_meta_xdr': 'AAAAAwAAAAAAAAACAAAAAwMg1UsAAAAAAAAAAA2pwyxGWZmV8M7AIUgOYwqy8ROPd55fVpgR7Wdwk+HbAAAWbCIjeM0C5fNZAABRkgAAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAMAAAAAAyDTtgAAAABmjEBuAAAAAAAAAAEDINVLAAAAAAAAAAANqcMsRlmZlfDOwCFIDmMKsvETj3eeX1aYEe1ncJPh2wAAFmwiI3jNAuXzWQAAUZMAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg1UsAAAAAZoxJWgAAAAAAAAABAAAABAAAAAMDINVLAAAAAAAAAAANqcMsRlmZlfDOwCFIDmMKsvETj3eeX1aYEe1ncJPh2wAAFmwiI3jNAuXzWQAAUZMAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg1UsAAAAAZoxJWgAAAAAAAAABAyDVSwAAAAAAAAAADanDLEZZmZXwzsAhSA5jCrLxE493nl9WmBHtZ3CT4dsAABZrZ6WfKgLl81kAAFGTAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAwAAAAADINVLAAAAAGaMSVoAAAAAAAAAAwMg1TgAAAAAAAAAANJdnWDu5Lzz4a+ZqJ3dIG0+ciDA3gcjxGoGjhecW4aZAAAGs09tvbQCA8q8AAPsBAAAAAMAAAAAAAAAAAAAAAliaXRnby5jb20AAAAAAQIDAAAAAwAAAAAdSLNvNcCEWpUM1sSHHJ9W/JqMWbz1rhA/Sl1QO+4C9AAAAAEAAAAAl5Ai6URIK1qSERKZFtKcPXz/BINreqBQEc2793l1m6cAAAABAAAAAK2xJjeRTZSyAkiROb5tk6y8FeWa/G6LumaboZvAanpFAAAAAQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAwAAAAAAAAAAAAAAAAAAAAMAAAAAAyDVKQAAAABmjEiaAAAAAAAAAAEDINVLAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABrQJ65dXAgPKvAAD7AQAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg1SkAAAAAZoxImgAAAAAAAAAAAAAAAA==',
                                           'fee_meta_xdr': 'AAAAAgAAAAMDINO2AAAAAAAAAAANqcMsRlmZlfDOwCFIDmMKsvETj3eeX1aYEe1ncJPh2wAAFmwiI3kxAuXzWQAAUZIAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg07YAAAAAZoxAbgAAAAAAAAABAyDVSwAAAAAAAAAADanDLEZZmZXwzsAhSA5jCrLxE493nl9WmBHtZ3CT4dsAABZsIiN4zQLl81kAAFGSAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAwAAAAADINO2AAAAAGaMQG4AAAAA',
                                           'memo_type': 'text', 'signatures': [
                                              'cjZTS5BDFtfOdH2Uuc6GI5T2ThyvKSYTXOVrY0os0uUWeIXYe+bHZwEInLsSn+oIju9BCarBBziPZCKXcMxAAA=='],
                                           'valid_after': '1970-07-22T19:27:47Z',
                                           'valid_before': '2024-07-08T23:17:14Z',
                                           'preconditions': {
                                               'timebounds': {'min_time': '17522867', 'max_time': '1720480634'}}},
                                          {'memo': '208814', 'memo_bytes': 'MjA4ODE0', '_links': {'self': {
                                              'href': 'https://horizon.stellar.org/transactions/9ba96e961d794be757bf8e66cae47a7203be996104c95312360638491bb50d39'},
                                              'account': {
                                                  'href': 'https://horizon.stellar.org/accounts/GDHF3HIKWM5KJAVLZBSZWUFDOEOT7IBMY22UXG4QBE326O354INLPAND'},
                                              'ledger': {
                                                  'href': 'https://horizon.stellar.org/ledgers/52483384'},
                                              'operations': {
                                                  'href': 'https://horizon.stellar.org/transactions/9ba96e961d794be757bf8e66cae47a7203be996104c95312360638491bb50d39/operations{?cursor,limit,order}',
                                                  'templated': True},
                                              'effects': {
                                                  'href': 'https://horizon.stellar.org/transactions/9ba96e961d794be757bf8e66cae47a7203be996104c95312360638491bb50d39/effects{?cursor,limit,order}',
                                                  'templated': True},
                                              'precedes': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=asc&cursor=225414417863778304'},
                                              'succeeds': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=desc&cursor=225414417863778304'},
                                              'transaction': {
                                                  'href': 'https://horizon.stellar.org/transactions/9ba96e961d794be757bf8e66cae47a7203be996104c95312360638491bb50d39'}},
                                           'id': '9ba96e961d794be757bf8e66cae47a7203be996104c95312360638491bb50d39',
                                           'paging_token': '225414417863778304', 'successful': True,
                                           'hash': '9ba96e961d794be757bf8e66cae47a7203be996104c95312360638491bb50d39',
                                           'ledger': 52483384, 'created_at': '2024-07-08T20:15:43Z',
                                           'source_account': 'GDHF3HIKWM5KJAVLZBSZWUFDOEOT7IBMY22UXG4QBE326O354INLPAND',
                                           'source_account_sequence': '166409929518316644',
                                           'fee_account': 'GDHF3HIKWM5KJAVLZBSZWUFDOEOT7IBMY22UXG4QBE326O354INLPAND',
                                           'fee_charged': '100', 'max_fee': '1000000', 'operation_count': 1,
                                           'envelope_xdr': 'AAAAAgAAAADOXZ0KszqkgqvIZZtQo3EdP6AsxrVLm5AJN687feIatwAPQkACTzTzAAl8ZAAAAAEAAAAAAAAAAAAAAABmjElGAAAAAQAAAAYyMDg4MTQAAAAAAAEAAAAAAAAAAQAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAAAAAAAAAAPUmclAAAAAAAAAABfeIatwAAAEBsMoIz+kCrM/brm2JS22oVqgv/edc6xzJHzepXmQppbEwxIJrC4Qk+oOGMlLlsMMlFYdUS2ow79VqNbeY2WRMG',
                                           'result_xdr': 'AAAAAAAAAGQAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAA=',
                                           'result_meta_xdr': 'AAAAAwAAAAAAAAACAAAAAwMg1TgAAAAAAAAAAM5dnQqzOqSCq8hlm1CjcR0/oCzGtUubkAk3rzt94hq3AABHH5O5hfMCTzTzAAl8YwAAAAIAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAMAAAAAAyDVMwAAAABmjEjTAAAAAAAAAAEDINU4AAAAAAAAAADOXZ0KszqkgqvIZZtQo3EdP6AsxrVLm5AJN687feIatwAARx+TuYXzAk808wAJfGQAAAACAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg1TgAAAAAZoxI7wAAAAAAAAABAAAABAAAAAMDINU4AAAAAAAAAADOXZ0KszqkgqvIZZtQo3EdP6AsxrVLm5AJN687feIatwAARx+TuYXzAk808wAJfGQAAAACAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg1TgAAAAAZoxI7wAAAAAAAAABAyDVOAAAAAAAAAAAzl2dCrM6pIKryGWbUKNxHT+gLMa1S5uQCTevO33iGrcAAEcfVm/pXwJPNPMACXxkAAAAAgAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAwAAAAADINU4AAAAAGaMSO8AAAAAAAAAAwMg1TMAAAAAAAAAANJdnWDu5Lzz4a+ZqJ3dIG0+ciDA3gcjxGoGjhecW4aZAAAGsxIkISACA8q8AAPsBAAAAAMAAAAAAAAAAAAAAAliaXRnby5jb20AAAAAAQIDAAAAAwAAAAAdSLNvNcCEWpUM1sSHHJ9W/JqMWbz1rhA/Sl1QO+4C9AAAAAEAAAAAl5Ai6URIK1qSERKZFtKcPXz/BINreqBQEc2793l1m6cAAAABAAAAAK2xJjeRTZSyAkiROb5tk6y8FeWa/G6LumaboZvAanpFAAAAAQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAwAAAAAAAAAAAAAAAAAAAAMAAAAAAyDVKQAAAABmjEiaAAAAAAAAAAEDINU4AAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABrNPbb20AgPKvAAD7AQAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg1SkAAAAAZoxImgAAAAAAAAAAAAAAAA==',
                                           'fee_meta_xdr': 'AAAAAgAAAAMDINUzAAAAAAAAAADOXZ0KszqkgqvIZZtQo3EdP6AsxrVLm5AJN687feIatwAARx+TuYZXAk808wAJfGMAAAACAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg1TMAAAAAZoxI0wAAAAAAAAABAyDVOAAAAAAAAAAAzl2dCrM6pIKryGWbUKNxHT+gLMa1S5uQCTevO33iGrcAAEcfk7mF8wJPNPMACXxjAAAAAgAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAwAAAAADINUzAAAAAGaMSNMAAAAA',
                                           'memo_type': 'text', 'signatures': [
                                              'bDKCM/pAqzP265tiUttqFaoL/3nXOscyR83qV5kKaWxMMSCawuEJPqDhjJS5bDDJRWHVEtqMO/VajW3mNlkTBg=='],
                                           'valid_after': '1970-01-01T00:00:00Z',
                                           'valid_before': '2024-07-08T20:17:10Z',
                                           'preconditions': {
                                               'timebounds': {'min_time': '0', 'max_time': '1720469830'}}},
                                          {'memo': '185960', 'memo_bytes': 'MTg1OTYw', '_links': {'self': {
                                              'href': 'https://horizon.stellar.org/transactions/6cdfa6e805ac42f1d980345bf949876592edef8cc51fb0eba0d92e55d4f23fa1'},
                                              'account': {
                                                  'href': 'https://horizon.stellar.org/accounts/GDHF3HIKWM5KJAVLZBSZWUFDOEOT7IBMY22UXG4QBE326O354INLPAND'},
                                              'ledger': {
                                                  'href': 'https://horizon.stellar.org/ledgers/52483379'},
                                              'operations': {
                                                  'href': 'https://horizon.stellar.org/transactions/6cdfa6e805ac42f1d980345bf949876592edef8cc51fb0eba0d92e55d4f23fa1/operations{?cursor,limit,order}',
                                                  'templated': True},
                                              'effects': {
                                                  'href': 'https://horizon.stellar.org/transactions/6cdfa6e805ac42f1d980345bf949876592edef8cc51fb0eba0d92e55d4f23fa1/effects{?cursor,limit,order}',
                                                  'templated': True},
                                              'precedes': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=asc&cursor=225414396389048320'},
                                              'succeeds': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=desc&cursor=225414396389048320'},
                                              'transaction': {
                                                  'href': 'https://horizon.stellar.org/transactions/6cdfa6e805ac42f1d980345bf949876592edef8cc51fb0eba0d92e55d4f23fa1'}},
                                           'id': '6cdfa6e805ac42f1d980345bf949876592edef8cc51fb0eba0d92e55d4f23fa1',
                                           'paging_token': '225414396389048320', 'successful': True,
                                           'hash': '6cdfa6e805ac42f1d980345bf949876592edef8cc51fb0eba0d92e55d4f23fa1',
                                           'ledger': 52483379, 'created_at': '2024-07-08T20:15:15Z',
                                           'source_account': 'GDHF3HIKWM5KJAVLZBSZWUFDOEOT7IBMY22UXG4QBE326O354INLPAND',
                                           'source_account_sequence': '166409929518316643',
                                           'fee_account': 'GDHF3HIKWM5KJAVLZBSZWUFDOEOT7IBMY22UXG4QBE326O354INLPAND',
                                           'fee_charged': '100', 'max_fee': '1000000', 'operation_count': 1,
                                           'envelope_xdr': 'AAAAAgAAAADOXZ0KszqkgqvIZZtQo3EdP6AsxrVLm5AJN687feIatwAPQkACTzTzAAl8YwAAAAEAAAAAAAAAAAAAAABmjEkoAAAAAQAAAAYxODU5NjAAAAAAAAEAAAAAAAAAAQAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAAAAAAAAABbW7UsAAAAAAAAAABfeIatwAAAECc7FrNUijm7OKE1LdJKwMpA9qcer3PpDV13ymaOxAlx/kE7+njYc2oeSL5FkeLlCCf6O7nl56ixCBRkXAdesIG',
                                           'result_xdr': 'AAAAAAAAAGQAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAA=',
                                           'result_meta_xdr': 'AAAAAwAAAAAAAAACAAAAAwMg1TMAAAAAAAAAAM5dnQqzOqSCq8hlm1CjcR0/oCzGtUubkAk3rzt94hq3AABHIQEoWwcCTzTzAAl8YgAAAAIAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAMAAAAAAyDVHwAAAABmjEhjAAAAAAAAAAEDINUzAAAAAAAAAADOXZ0KszqkgqvIZZtQo3EdP6AsxrVLm5AJN687feIatwAARyEBKFsHAk808wAJfGMAAAACAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg1TMAAAAAZoxI0wAAAAAAAAABAAAABAAAAAMDINUzAAAAAAAAAADOXZ0KszqkgqvIZZtQo3EdP6AsxrVLm5AJN687feIatwAARyEBKFsHAk808wAJfGMAAAACAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg1TMAAAAAZoxI0wAAAAAAAAABAyDVMwAAAAAAAAAAzl2dCrM6pIKryGWbUKNxHT+gLMa1S5uQCTevO33iGrcAAEcfk7mGVwJPNPMACXxjAAAAAgAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAwAAAAADINUzAAAAAGaMSNMAAAAAAAAAAwMg1SkAAAAAAAAAANJdnWDu5Lzz4a+ZqJ3dIG0+ciDA3gcjxGoGjhecW4aZAAAGsaS1THACA8q8AAPsBAAAAAMAAAAAAAAAAAAAAAliaXRnby5jb20AAAAAAQIDAAAAAwAAAAAdSLNvNcCEWpUM1sSHHJ9W/JqMWbz1rhA/Sl1QO+4C9AAAAAEAAAAAl5Ai6URIK1qSERKZFtKcPXz/BINreqBQEc2793l1m6cAAAABAAAAAK2xJjeRTZSyAkiROb5tk6y8FeWa/G6LumaboZvAanpFAAAAAQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAwAAAAAAAAAAAAAAAAAAAAMAAAAAAyDVKQAAAABmjEiaAAAAAAAAAAEDINUzAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABrMSJCEgAgPKvAAD7AQAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg1SkAAAAAZoxImgAAAAAAAAAAAAAAAA==',
                                           'fee_meta_xdr': 'AAAAAgAAAAMDINUfAAAAAAAAAADOXZ0KszqkgqvIZZtQo3EdP6AsxrVLm5AJN687feIatwAARyEBKFtrAk808wAJfGIAAAACAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg1R8AAAAAZoxIYwAAAAAAAAABAyDVMwAAAAAAAAAAzl2dCrM6pIKryGWbUKNxHT+gLMa1S5uQCTevO33iGrcAAEchAShbBwJPNPMACXxiAAAAAgAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAwAAAAADINUfAAAAAGaMSGMAAAAA',
                                           'memo_type': 'text', 'signatures': [
                                              'nOxazVIo5uzihNS3SSsDKQPanHq9z6Q1dd8pmjsQJcf5BO/p42HNqHki+RZHi5Qgn+ju55eeosQgUZFwHXrCBg=='],
                                           'valid_after': '1970-01-01T00:00:00Z',
                                           'valid_before': '2024-07-08T20:16:40Z',
                                           'preconditions': {
                                               'timebounds': {'min_time': '0', 'max_time': '1720469800'}}},
                                          {'memo': '691965', '_links': {'self': {
                                              'href': 'https://horizon.stellar.org/transactions/6e8423c7ba4be166534c26230db957751bee5e7b2a4dd5a83201bdca61a31b8b'},
                                              'account': {
                                                  'href': 'https://horizon.stellar.org/accounts/GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5'},
                                              'ledger': {
                                                  'href': 'https://horizon.stellar.org/ledgers/52483369'},
                                              'operations': {
                                                  'href': 'https://horizon.stellar.org/transactions/6e8423c7ba4be166534c26230db957751bee5e7b2a4dd5a83201bdca61a31b8b/operations{?cursor,limit,order}',
                                                  'templated': True}, 'effects': {
                                                  'href': 'https://horizon.stellar.org/transactions/6e8423c7ba4be166534c26230db957751bee5e7b2a4dd5a83201bdca61a31b8b/effects{?cursor,limit,order}',
                                                  'templated': True}, 'precedes': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=asc&cursor=225414353438969856'},
                                              'succeeds': {
                                                  'href': 'https://horizon.stellar.org/transactions?order=desc&cursor=225414353438969856'},
                                              'transaction': {
                                                  'href': 'https://horizon.stellar.org/transactions/6e8423c7ba4be166534c26230db957751bee5e7b2a4dd5a83201bdca61a31b8b'}},
                                           'id': '6e8423c7ba4be166534c26230db957751bee5e7b2a4dd5a83201bdca61a31b8b',
                                           'paging_token': '225414353438969856', 'successful': True,
                                           'hash': '6e8423c7ba4be166534c26230db957751bee5e7b2a4dd5a83201bdca61a31b8b',
                                           'ledger': 52483369, 'created_at': '2024-07-08T20:14:18Z',
                                           'source_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                                           'source_account_sequence': '145182521808907268',
                                           'fee_account': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                                           'fee_charged': '100', 'max_fee': '45000', 'operation_count': 1,
                                           'envelope_xdr': 'AAAAAgAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAAr8gCA8q8AAPsBAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAACo79AAAAAQAAAAAAAAABAAAAAOXDqt/kCw0khZz7brrwCR79i8j1W5kyVZKR8d8S3vVOAAAAAAAAAAAQDaZQAAAAAAAAAALAanpFAAAAQK1Tw5cSR3AAOyFIaafKKMH0wgba+iFDYT4e4dStkZt50tmWBWCs6umf9JDTxiz09nQtvY5cCeSH/tb666uZ8wt5dZunAAAAQBICZncYtYzviifYOWmH5WbSLHphYmI61eDWxN48hRyFbJ58q1Sc12LpQrNIfQtItrQFOvTcMzR0TVJst1OgMgo=',
                                           'result_xdr': 'AAAAAAAAAGQAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAA=',
                                           'result_meta_xdr': 'AAAAAwAAAAAAAAACAAAAAwMg1SkAAAAAAAAAANJdnWDu5Lzz4a+ZqJ3dIG0+ciDA3gcjxGoGjhecW4aZAAAGsbTC8sACA8q8AAPsAwAAAAMAAAAAAAAAAAAAAAliaXRnby5jb20AAAAAAQIDAAAAAwAAAAAdSLNvNcCEWpUM1sSHHJ9W/JqMWbz1rhA/Sl1QO+4C9AAAAAEAAAAAl5Ai6URIK1qSERKZFtKcPXz/BINreqBQEc2793l1m6cAAAABAAAAAK2xJjeRTZSyAkiROb5tk6y8FeWa/G6LumaboZvAanpFAAAAAQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAwAAAAAAAAAAAAAAAAAAAAMAAAAAAyDSVwAAAABmjDioAAAAAAAAAAEDINUpAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABrG0wvLAAgPKvAAD7AQAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg1SkAAAAAZoxImgAAAAAAAAABAAAABAAAAAMDINUpAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABrG0wvLAAgPKvAAD7AQAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg1SkAAAAAZoxImgAAAAAAAAABAyDVKQAAAAAAAAAA0l2dYO7kvPPhr5mond0gbT5yIMDeByPEagaOF5xbhpkAAAaxpLVMcAIDyrwAA+wEAAAAAwAAAAAAAAAAAAAACWJpdGdvLmNvbQAAAAABAgMAAAADAAAAAB1Is281wIRalQzWxIccn1b8moxZvPWuED9KXVA77gL0AAAAAQAAAACXkCLpREgrWpIREpkW0pw9fP8Eg2t6oFARzbv3eXWbpwAAAAEAAAAArbEmN5FNlLICSJE5vm2TrLwV5Zr8bou6Zpuhm8BqekUAAAABAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAADAAAAAAAAAAAAAAAAAAAAAwAAAAADINUpAAAAAGaMSJoAAAAAAAAAAwMg1R8AAAAAAAAAAOXDqt/kCw0khZz7brrwCR79i8j1W5kyVZKR8d8S3vVOAAAAAsFCPCMCYcLAAABKJAAAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAMAAAAAAyDUmQAAAABmjEVrAAAAAAAAAAEDINUpAAAAAAAAAADlw6rf5AsNJIWc+2668Ake/YvI9VuZMlWSkfHfEt71TgAAAALRT+JzAmHCwAAASiQAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAAAAAAMg1JkAAAAAZoxFawAAAAAAAAAAAAAAAA==',
                                           'fee_meta_xdr': 'AAAAAgAAAAMDINJXAAAAAAAAAADSXZ1g7uS88+Gvmaid3SBtPnIgwN4HI8RqBo4XnFuGmQAABrG0wvMkAgPKvAAD7AMAAAADAAAAAAAAAAAAAAAJYml0Z28uY29tAAAAAAECAwAAAAMAAAAAHUizbzXAhFqVDNbEhxyfVvyajFm89a4QP0pdUDvuAvQAAAABAAAAAJeQIulESCtakhESmRbSnD18/wSDa3qgUBHNu/d5dZunAAAAAQAAAACtsSY3kU2UsgJIkTm+bZOsvBXlmvxui7pmm6GbwGp6RQAAAAEAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAADAAAAAAMg0lcAAAAAZow4qAAAAAAAAAABAyDVKQAAAAAAAAAA0l2dYO7kvPPhr5mond0gbT5yIMDeByPEagaOF5xbhpkAAAaxtMLywAIDyrwAA+wDAAAAAwAAAAAAAAAAAAAACWJpdGdvLmNvbQAAAAABAgMAAAADAAAAAB1Is281wIRalQzWxIccn1b8moxZvPWuED9KXVA77gL0AAAAAQAAAACXkCLpREgrWpIREpkW0pw9fP8Eg2t6oFARzbv3eXWbpwAAAAEAAAAArbEmN5FNlLICSJE5vm2TrLwV5Zr8bou6Zpuhm8BqekUAAAABAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAADAAAAAAAAAAAAAAAAAAAAAwAAAAADINJXAAAAAGaMOKgAAAAA',
                                           'memo_type': 'id', 'signatures': [
                                              'rVPDlxJHcAA7IUhpp8oowfTCBtr6IUNhPh7h1K2Rm3nS2ZYFYKzq6Z/0kNPGLPT2dC29jlwJ5If+1vrrq5nzCw==',
                                              'EgJmdxi1jO+KJ9g5aYflZtIsemFiYjrV4NbE3jyFHIVsnnyrVJzXYulCs0h9C0i2tAU69NwzNHRNUmy3U6AyCg=='],
                                           'valid_after': '1970-01-01T00:00:00Z',
                                           'preconditions': {'timebounds': {'min_time': '0'}}}]}},
        ]
        expected_addresses_txs = [
            [{'contract_address': None, 'address': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
              'from_address': ['GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5'],
              'hash': 'd730cdf46b16a1b124c082e9cb60c4e75d2daf4ff3547f7945cc14e500896080', 'block': None,
              'timestamp': datetime.datetime(2024, 7, 9, 13, 28, 51, tzinfo=datetime.timezone.utc), 'value': Decimal(
                    '-19.5416687'), 'confirmations': 1, 'is_double_spend': False, 'details': {}, 'tag': '215976',
              'huge': False, 'invoice': None}, {
                 'contract_address': None, 'address': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                 'from_address': ['GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5'],
                 'hash': 'd6bf6931c301b3fe57a7e5921608db22b3edc861897780abe5603a18b8a9eebe', 'block': None,
                 'timestamp': datetime.datetime(2024, 7, 9, 13, 16, 21, tzinfo=datetime.timezone.utc), 'value': Decimal(
                    '-119.8400000'), 'confirmations': 1, 'is_double_spend': False, 'details': {}, 'tag': '16386',
                 'huge': False, 'invoice': None}, {
                 'contract_address': None, 'address': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                 'from_address': ['GDHF3HIKWM5KJAVLZBSZWUFDOEOT7IBMY22UXG4QBE326O354INLPAND'],
                 'hash': '9b008710ebe443f9af0e840b4d83cc0bf657cee3756252ee7079008b792a2516', 'block': None,
                 'timestamp': datetime.datetime(2024, 7, 9, 13, 1, 5, tzinfo=datetime.timezone.utc), 'value': Decimal(
                    '238.7155619'), 'confirmations': 1, 'is_double_spend': False, 'details': {}, 'tag': '185960',
                 'huge': False, 'invoice': None}, {
                 'contract_address': None, 'address': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                 'from_address': ['GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5'],
                 'hash': '4f0f55720a10c498ac57fe4fe10b0aca3da95217f26d1b65fd833a77a2edee7f', 'block': None,
                 'timestamp': datetime.datetime(2024, 7, 9, 12, 30, 49, tzinfo=datetime.timezone.utc), 'value': Decimal(
                    '-320.8000472'), 'confirmations': 1, 'is_double_spend': False, 'details': {}, 'tag': '325339001',
                 'huge': False, 'invoice': None}, {
                 'contract_address': None, 'address': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                 'from_address': ['GD3UAVRI2XHOUZHLKESHC7YQLQZEVUFD6NN45SOW72LEEQUL2XLJ5R5G'],
                 'hash': 'b55d9b5260dee2f1697ff998594e2a6e7e9b72e54b01367db1943f3dc7e47ad1', 'block': None,
                 'timestamp': datetime.datetime(2024, 7, 9, 11, 54, 31, tzinfo=datetime.timezone.utc), 'value': Decimal(
                    '10527.3791198'), 'confirmations': 1, 'is_double_spend': False, 'details': {}, 'tag': '47615',
                 'huge': False, 'invoice': None}, {
                 'contract_address': None, 'address': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                 'from_address': ['GD6RWYUQ6FWRBWFFA4HZVPCQUKGUIHZ4SL5G5GJU4HP3LKMYSUYAGBUA'],
                 'hash': '699ef2c2bb5653cc272fa75fe59e637f3dad22f03f3fcf011d4ebe85724d8c8a', 'block': None,
                 'timestamp': datetime.datetime(2024, 7, 9, 11, 24, 5, tzinfo=datetime.timezone.utc), 'value': Decimal(
                    '188.5956000'), 'confirmations': 1, 'is_double_spend': False, 'details': {}, 'tag': '158916',
                 'huge': False, 'invoice': None}, {
                 'contract_address': None, 'address': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                 'from_address': ['GC5LF63GRVIT5ZXXCXLPI3RX2YXKJQFZVBSAO6AUELN3YIMSWPD6Z6FH'],
                 'hash': 'e2c24b3427e1d672b9ef2d9743a0ceb081c136e9e65565f976b68c1d35c350c9', 'block': None,
                 'timestamp': datetime.datetime(2024, 7, 9, 10, 49, 44, tzinfo=datetime.timezone.utc), 'value': Decimal(
                    '123.9078659'), 'confirmations': 1, 'is_double_spend': False, 'details': {}, 'tag': '189947',
                 'huge': False, 'invoice': None}, {
                 'contract_address': None, 'address': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                 'from_address': ['GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5'],
                 'hash': '2b8d863e4e03ec4c3643821babc67ef32c06dc349081ad74ff4eef8872cf1288', 'block': None,
                 'timestamp': datetime.datetime(2024, 7, 9, 10, 31, 50, tzinfo=datetime.timezone.utc), 'value': Decimal(
                    '-43.9130030'), 'confirmations': 1, 'is_double_spend': False, 'details': {}, 'tag': '6060175',
                 'huge': False, 'invoice': None}, {
                 'contract_address': None, 'address': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                 'from_address': ['GBALLUSPAPYHIJFYVSAH3O6LUARQK2T6BCOIN5HG7HMLROBDGHYBBAVV'],
                 'hash': '453b8129f35cd0d7dc469db0f5468ad3e80ab84ac8041ce3e11b9284bf366083', 'block': None,
                 'timestamp': datetime.datetime(2024, 7, 9, 9, 35, 18, tzinfo=datetime.timezone.utc), 'value': Decimal(
                    '147.0000000'), 'confirmations': 1, 'is_double_spend': False, 'details': {}, 'tag': '203684',
                 'huge': False, 'invoice': None}, {
                 'contract_address': None, 'address': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                 'from_address': ['GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5'],
                 'hash': 'f5f3d8967bfdd88a82c26df8511482a230eec924d4747c71f473c0aacc9d3f6e', 'block': None,
                 'timestamp': datetime.datetime(2024, 7, 9, 8, 58, 6, tzinfo=datetime.timezone.utc), 'value': Decimal(
                    '-33.6015463'), 'confirmations': 1, 'is_double_spend': False, 'details': {}, 'tag': '3427155930',
                 'huge': False, 'invoice': None}, {
                 'contract_address': None, 'address': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                 'from_address': ['GBGHMELHHVTB6EQ5TNERZWPGFURADVSO6RW5PNNMRDMG55E74UBER45I'],
                 'hash': '2700b7ee302e13f4500e3e85a6fec00c30299841638417505296b74885af233e', 'block': None,
                 'timestamp': datetime.datetime(2024, 7, 9, 8, 29, 31, tzinfo=datetime.timezone.utc), 'value': Decimal(
                    '112.3457510'), 'confirmations': 1, 'is_double_spend': False, 'details': {}, 'tag': '39265',
                 'huge': False, 'invoice': None}, {
                 'contract_address': None, 'address': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                 'from_address': ['GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5'],
                 'hash': '5c276d28aa3468bac79d7d0fa793abf807e996e0877ae4c97c46b2f8d21f347b', 'block': None,
                 'timestamp': datetime.datetime(2024, 7, 9, 7, 21, 27, tzinfo=datetime.timezone.utc), 'value': Decimal(
                    '-50000.0000000'), 'confirmations': 1, 'is_double_spend': False, 'details': {},
                 'tag': '44b1cce539d53d7f20', 'huge': False, 'invoice': None}, {
                 'contract_address': None, 'address': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                 'from_address': ['GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5'],
                 'hash': 'db9f67d857684e3ca99ec9e7d2ace494ff44cc7e2efdabc9b0af7b8a300d42ad', 'block': None,
                 'timestamp': datetime.datetime(2024, 7, 9, 7, 20, 30, tzinfo=datetime.timezone.utc), 'value': Decimal(
                    '-1733.4059938'), 'confirmations': 1, 'is_double_spend': False, 'details': {}, 'tag': '292423124',
                 'huge': False, 'invoice': None}, {
                 'contract_address': None, 'address': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                 'from_address': ['GDHF3HIKWM5KJAVLZBSZWUFDOEOT7IBMY22UXG4QBE326O354INLPAND'],
                 'hash': '5370ecc06dc79ee23c552f5bbd230195b2d564877ee4aa5749f9ba0b18c40d00', 'block': None,
                 'timestamp': datetime.datetime(2024, 7, 9, 6, 35, 5, tzinfo=datetime.timezone.utc), 'value': Decimal(
                    '356.4445000'), 'confirmations': 1, 'is_double_spend': False, 'details': {}, 'tag': '186674',
                 'huge': False, 'invoice': None}, {
                 'contract_address': None, 'address': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                 'from_address': ['GAV6J5L473K4H6226IFNCAL7E5A2PR63YRCZDYJPTQH3S35YODXUUADV'],
                 'hash': '14a5ead1562b71c22d4f9399a7d453730692719e4f48def731d1618696d6dc25', 'block': None,
                 'timestamp': datetime.datetime(2024, 7, 9, 6, 27, 25, tzinfo=datetime.timezone.utc), 'value': Decimal(
                    '252.7154330'), 'confirmations': 1, 'is_double_spend': False, 'details': {}, 'tag': '174756',
                 'huge': False, 'invoice': None}, {
                 'contract_address': None, 'address': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                 'from_address': ['GDHF3HIKWM5KJAVLZBSZWUFDOEOT7IBMY22UXG4QBE326O354INLPAND'],
                 'hash': '34a547aa9854384deeb4b321caac0c87b0beec2a076f7a8818ca2a7f82a06606', 'block': None,
                 'timestamp': datetime.datetime(2024, 7, 9, 3, 38, 15, tzinfo=datetime.timezone.utc), 'value': Decimal(
                    '68.9227920'), 'confirmations': 1, 'is_double_spend': False, 'details': {}, 'tag': '167866',
                 'huge': False, 'invoice': None}, {
                 'contract_address': None, 'address': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                 'from_address': ['GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5'],
                 'hash': '135c4be71c4cea1cf5200a1ef3c227535dfe62a9f046f351fc19b6bf6e1693a2', 'block': None,
                 'timestamp': datetime.datetime(2024, 7, 9, 2, 53, 24, tzinfo=datetime.timezone.utc), 'value': Decimal(
                    '-4.8551000'), 'confirmations': 1, 'is_double_spend': False, 'details': {}, 'tag': '1212878250',
                 'huge': False, 'invoice': None}, {
                 'contract_address': None, 'address': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                 'from_address': ['GD6RWYUQ6FWRBWFFA4HZVPCQUKGUIHZ4SL5G5GJU4HP3LKMYSUYAGBUA'],
                 'hash': 'f91af004a0b1a33cdbba23a5db526d7f147621a1bdbe56454f477aa8598472c7', 'block': None,
                 'timestamp': datetime.datetime(2024, 7, 9, 2, 48, 6, tzinfo=datetime.timezone.utc), 'value': Decimal(
                    '67.2548000'), 'confirmations': 1, 'is_double_spend': False, 'details': {}, 'tag': '203239',
                 'huge': False, 'invoice': None}, {
                 'contract_address': None, 'address': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                 'from_address': ['GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5'],
                 'hash': '210e36caca2377401da2cbf0e6a9f64b94c64dd85da0832046fd639d57f7a81e', 'block': None,
                 'timestamp': datetime.datetime(2024, 7, 9, 1, 13, 39, tzinfo=datetime.timezone.utc), 'value': Decimal(
                    '-158.2706505'), 'confirmations': 1, 'is_double_spend': False, 'details': {}, 'tag': '242316001',
                 'huge': False, 'invoice': None}, {
                 'contract_address': None, 'address': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                 'from_address': ['GB5FUSCVVV7ZLKJVL7FRCSBQHZXYLMSWWXXYC7NH35GV57S5XWKEVA4V'],
                 'hash': '7bc532dee93c5f90d13b6178f9045d36d86de36d92f18fe2cc0e57ae076e6f90', 'block': None,
                 'timestamp': datetime.datetime(2024, 7, 8, 23, 31, 56, tzinfo=datetime.timezone.utc), 'value': Decimal(
                    '5.0000000'), 'confirmations': 1, 'is_double_spend': False, 'details': {}, 'tag': '1477',
                 'huge': False, 'invoice': None}, {
                 'contract_address': None, 'address': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                 'from_address': ['GDUQXQAR4ECNAYCTGZAS4TH4KJJIZDLXPR5V2YYRFRGGQ3LTXBFTBVW6'],
                 'hash': '76410c7616ab46b02b435edcd391286b524af7c05af3c0ecc4fd700c5c891c9d', 'block': None,
                 'timestamp': datetime.datetime(2024, 7, 8, 23, 23, 13, tzinfo=datetime.timezone.utc), 'value': Decimal(
                    '200.0000000'), 'confirmations': 1, 'is_double_spend': False, 'details': {}, 'tag': '', 'huge': False, 'invoice': None},
             {'contract_address': None,
              'address': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
              'from_address': [
                  'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5'],
              'hash': 'b46adf2d07154a357eca34596bb0640518a218662aa91427151d2ad72eb87ed8',
              'block': None,
              'timestamp': datetime.datetime(2024, 7, 8, 23, 0, 52,
                                             tzinfo=datetime.timezone.utc),
              'value': Decimal(
                  '-4.4355200'), 'confirmations': 1,
              'is_double_spend': False, 'details': {},
              'tag': '2959942072', 'huge': False, 'invoice': None}, {
                 'contract_address': None, 'address': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                 'from_address': ['GBZLHGDYMSVF4X6DYAGKLIQX3F64W3MXNDVGHKQPR226TCJ5QJ2ZQKVA'],
                 'hash': '96e7cc22bb4cb249c9a85f1ac2320dcd02dd72d08b2e6a6c23e5359eb23c9009', 'block': None,
                 'timestamp': datetime.datetime(2024, 7, 8, 22, 15, 9, tzinfo=datetime.timezone.utc), 'value': Decimal(
                    '456.2000000'), 'confirmations': 1, 'is_double_spend': False, 'details': {}, 'tag': '86644',
                 'huge': False, 'invoice': None}, {
                 'contract_address': None, 'address': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                 'from_address': ['GA4IRJ52YGZQJDS7XJ375UGSI4FE4KQXHFYUUYNR5QXDVQNAXQTLRJAB'],
                 'hash': '917b3a51f47a5b70f36f6bdd265b669f843a9650ee99f93212a4c0b5af494561', 'block': None,
                 'timestamp': datetime.datetime(2024, 7, 8, 21, 10, 41, tzinfo=datetime.timezone.utc), 'value': Decimal(
                    '347.5786758'), 'confirmations': 1, 'is_double_spend': False, 'details': {}, 'tag': '1477',
                 'huge': False, 'invoice': None}, {
                 'contract_address': None, 'address': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                 'from_address': ['GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5'],
                 'hash': 'ff1e1b7bbdcd575984ee2ef4d339b253afb84107792ffce43b24c165c4f5fdca', 'block': None,
                 'timestamp': datetime.datetime(2024, 7, 8, 20, 32, 42, tzinfo=datetime.timezone.utc), 'value': Decimal(
                    '-10.5494000'), 'confirmations': 1, 'is_double_spend': False, 'details': {}, 'tag': '691965',
                 'huge': False, 'invoice': None}, {
                 'contract_address': None, 'address': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                 'from_address': ['GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5'],
                 'hash': 'c08bd472abe2d4757c138fa2b277a3eecd847da7fb9f895735dc48e61e21b0b1', 'block': None,
                 'timestamp': datetime.datetime(2024, 7, 8, 20, 31, tzinfo=datetime.timezone.utc), 'value': Decimal(
                    '-233.7260000'), 'confirmations': 1, 'is_double_spend': False, 'details': {}, 'tag': '3988502092',
                 'huge': False, 'invoice': None}, {
                 'contract_address': None, 'address': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                 'from_address': ['GAG2TQZMIZMZTFPQZ3ACCSAOMMFLF4ITR53Z4X2WTAI62Z3QSPQ5XB35'],
                 'hash': 'da840859197f71d99350757de57b6e6ba35304ad3c6c54ca6da3769b741f1bb1', 'block': None,
                 'timestamp': datetime.datetime(2024, 7, 8, 20, 17, 30, tzinfo=datetime.timezone.utc), 'value': Decimal(
                    '312.8809891'), 'confirmations': 1, 'is_double_spend': False, 'details': {}, 'tag': '115238',
                 'huge': False, 'invoice': None}, {
                 'contract_address': None, 'address': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                 'from_address': ['GDHF3HIKWM5KJAVLZBSZWUFDOEOT7IBMY22UXG4QBE326O354INLPAND'],
                 'hash': '9ba96e961d794be757bf8e66cae47a7203be996104c95312360638491bb50d39', 'block': None,
                 'timestamp': datetime.datetime(2024, 7, 8, 20, 15, 43, tzinfo=datetime.timezone.utc), 'value': Decimal(
                    '102.8234388'), 'confirmations': 1, 'is_double_spend': False, 'details': {}, 'tag': '208814',
                 'huge': False, 'invoice': None}, {
                 'contract_address': None, 'address': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                 'from_address': ['GDHF3HIKWM5KJAVLZBSZWUFDOEOT7IBMY22UXG4QBE326O354INLPAND'],
                 'hash': '6cdfa6e805ac42f1d980345bf949876592edef8cc51fb0eba0d92e55d4f23fa1', 'block': None,
                 'timestamp': datetime.datetime(2024, 7, 8, 20, 15, 15, tzinfo=datetime.timezone.utc), 'value': Decimal(
                    '613.0947248'), 'confirmations': 1, 'is_double_spend': False, 'details': {}, 'tag': '185960',
                 'huge': False, 'invoice': None}, {
                 'contract_address': None, 'address': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5',
                 'from_address': ['GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5'],
                 'hash': '6e8423c7ba4be166534c26230db957751bee5e7b2a4dd5a83201bdca61a31b8b', 'block': None,
                 'timestamp': datetime.datetime(2024, 7, 8, 20, 14, 18, tzinfo=datetime.timezone.utc), 'value': Decimal(
                    '-26.9330000'), 'confirmations': 1, 'is_double_spend': False, 'details': {}, 'tag': '691965',
                 'huge': False, 'invoice': None}]
        ]
        cls.get_address_txs(address_txs_mock_response, expected_addresses_txs)
