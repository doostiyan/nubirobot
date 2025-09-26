from unittest import TestCase
from unittest.mock import Mock
from pytz import UTC
import datetime
import pytest
from _decimal import Decimal

from exchange.blockchain.api.xlm.stellar_explorer import StellarExplorerApi
from exchange.blockchain.api.xlm.xlm_explorer_interface import StellarExplorerInterface
from exchange.base.models import Currencies


@pytest.mark.slow
class TestStellarExplorerApiCalls(TestCase):
    api = StellarExplorerApi

    hash_of_transactions = ['c15ae5bc33d010fa4d3469714a40cd9cb021837cdc0fc20c712a3b83e5af4e33']

    @classmethod
    def check_general_response(cls, response, keys):
        if set(response.keys()).issubset(keys):
            return True
        return False

    def test_get_tx_details_api(self):
        transaction_keys = {'id', 'hash', 'ledger', 'opCount', 'sourceAccount', 'time', 'fee', 'memoType', 'memo',
                            'time', 'links', 'id', 'pagingToken', 'transactionSuccessful', 'sourceAccount', 'type',
                            'typeI', 'createdAt', 'transactionHash', 'assetType', 'from', 'to', 'amount','pagingToken'}
        for tx_hash in self.hash_of_transactions:
            get_tx_details_response = self.api.get_tx_details(tx_hash)
            assert len(get_tx_details_response) == 3
            assert len(get_tx_details_response[1]) == 1
            translation = get_tx_details_response[0]
            translation.update(get_tx_details_response[1][0])
            assert self.check_general_response(translation, transaction_keys)

    def test_get_tx_details(self):
        expected_tx_details = {'hash': 'c15ae5bc33d010fa4d3469714a40cd9cb021837cdc0fc20c712a3b83e5af4e33', 'success': True, 'block': 48977558, 'date': datetime.datetime(2023, 11, 12, 1, 57, 21, tzinfo=UTC), 'fees': Decimal('100'), 'memo': '591508512', 'confirmations': 0, 'raw': None, 'inputs': [], 'outputs': [], 'transfers': [{'type': 'MainCoin', 'symbol': 'xlm', 'currency': 19, 'from': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5', 'to': 'GCNZ3SFMGWKHTFFDEAB2QYQRCIZUQ55DULDF775WH7JR77P7UPJLMY2U', 'value': Decimal('25.9340000'), 'is_valid': True, 'token': None}]}
        tx_details = StellarExplorerInterface.get_api().get_tx_details(self.hash_of_transactions[0])
        assert tx_details == expected_tx_details


class TestStellarExplorerFromExplorerInterface(TestCase):
    api = StellarExplorerApi
    currency = Currencies.xlm

    # hash of transactions in order of success, failed, invalid type, invalid token
    hash_of_transactions = [
        'c15ae5bc33d010fa4d3469714a40cd9cb021837cdc0fc20c712a3b83e5af4e33',
        '0d5ff3a0e560cb003408b3c2c83981fa976186bf9bea8a71a595d9147349c72f',
        '4a3267a272668a5799e377d73631deb27dbb1cdb77c8caba6a7e5c586e5e9a90',
        'f716c17ce95990f6c1815473d276e418ce53c22d0a2487e3f02f37f84b230321']

    def test_get_tx_details(self):
        tx_details_mock_response = [
            [{"id":"c15ae5bc33d010fa4d3469714a40cd9cb021837cdc0fc20c712a3b83e5af4e33","hash":"c15ae5bc33d010fa4d3469714a40cd9cb021837cdc0fc20c712a3b83e5af4e33","ledger":48977558,"opCount":1,"sourceAccount":"GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5","time":"2023-11-12T01:57:21Z","fee":"100","memoType":"id","memo":"591508512","pagingToken":"210357009849274368"},[{"time":"2023-11-12T01:57:21Z","links":{"self":{"href":"https://horizon.stellar.org/operations/210357009849274369"},"transaction":{"href":"https://horizon.stellar.org/transactions/c15ae5bc33d010fa4d3469714a40cd9cb021837cdc0fc20c712a3b83e5af4e33"},"effects":{"href":"https://horizon.stellar.org/operations/210357009849274369/effects"},"succeeds":{"href":"https://horizon.stellar.org/effects?order=desc&cursor=210357009849274369"},"precedes":{"href":"https://horizon.stellar.org/effects?order=asc&cursor=210357009849274369"}},"id":"210357009849274369","pagingToken":"210357009849274369","transactionSuccessful":True,"sourceAccount":"GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5","type":"payment","typeI":1,"createdAt":"2023-11-12T01:57:21Z","transactionHash":"c15ae5bc33d010fa4d3469714a40cd9cb021837cdc0fc20c712a3b83e5af4e33","assetType":"native","from":"GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5","to":"GCNZ3SFMGWKHTFFDEAB2QYQRCIZUQ55DULDF775WH7JR77P7UPJLMY2U","amount":"25.9340000"}],"https://horizon.stellar.org/"],
            [{"id":"0d5ff3a0e560cb003408b3c2c83981fa976186bf9bea8a71a595d9147349c72f","hash":"0d5ff3a0e560cb003408b3c2c83981fa976186bf9bea8a71a595d9147349c72f","ledger":48968291,"opCount":1,"sourceAccount":"GBZLHGDYMSVF4X6DYAGKLIQX3F64W3MXNDVGHKQPR226TCJ5QJ2ZQKVA","time":"2023-11-11T10:56:39Z","fee":"100","memoType":"text","memo":"4184176363","pagingToken":"210317208387305472"},[{"time":"2023-11-11T10:56:39Z","links":{"self":{"href":"https://horizon.stellar.org/operations/210317208387305473"},"transaction":{"href":"https://horizon.stellar.org/transactions/0d5ff3a0e560cb003408b3c2c83981fa976186bf9bea8a71a595d9147349c72f"},"effects":{"href":"https://horizon.stellar.org/operations/210317208387305473/effects"},"succeeds":{"href":"https://horizon.stellar.org/effects?order=desc&cursor=210317208387305473"},"precedes":{"href":"https://horizon.stellar.org/effects?order=asc&cursor=210317208387305473"}},"id":"210317208387305473","pagingToken":"210317208387305473","transactionSuccessful":False,"sourceAccount":"GBZLHGDYMSVF4X6DYAGKLIQX3F64W3MXNDVGHKQPR226TCJ5QJ2ZQKVA","type":"payment","typeI":1,"createdAt":"2023-11-11T10:56:39Z","transactionHash":"0d5ff3a0e560cb003408b3c2c83981fa976186bf9bea8a71a595d9147349c72f","assetType":"native","from":"GBZLHGDYMSVF4X6DYAGKLIQX3F64W3MXNDVGHKQPR226TCJ5QJ2ZQKVA","to":"GB2XUXQPA46RGUINQRGUHNZ3BAMTBNBQZELBCVMOADX42H27CD2PNSOP","amount":"88.9000000"}],"https://horizon.stellar.org/"],
            [{"id":"4a3267a272668a5799e377d73631deb27dbb1cdb77c8caba6a7e5c586e5e9a90","hash":"4a3267a272668a5799e377d73631deb27dbb1cdb77c8caba6a7e5c586e5e9a90","ledger":48977538,"opCount":1,"sourceAccount":"GDYQWIG7J6BULG3HUHMWKDVDM7JF4D3GA6JL4KBRRPYEK2MUKD2ACBOT","time":"2023-11-12T01:55:21Z","fee":"100","memoType":"none","pagingToken":"210356923949867008"},[{"time":"2023-11-12T01:55:21Z","links":{"self":{"href":"https://horizon.stellar.org/operations/210356923949867009"},"transaction":{"href":"https://horizon.stellar.org/transactions/4a3267a272668a5799e377d73631deb27dbb1cdb77c8caba6a7e5c586e5e9a90"},"effects":{"href":"https://horizon.stellar.org/operations/210356923949867009/effects"},"succeeds":{"href":"https://horizon.stellar.org/effects?order=desc&cursor=210356923949867009"},"precedes":{"href":"https://horizon.stellar.org/effects?order=asc&cursor=210356923949867009"}},"id":"210356923949867009","pagingToken":"210356923949867009","transactionSuccessful":True,"sourceAccount":"GDYQWIG7J6BULG3HUHMWKDVDM7JF4D3GA6JL4KBRRPYEK2MUKD2ACBOT","type":"manage_buy_offer","typeI":12,"createdAt":"2023-11-12T01:55:21Z","transactionHash":"4a3267a272668a5799e377d73631deb27dbb1cdb77c8caba6a7e5c586e5e9a90","amount":"86.0067450","price":"5.2437748","priceR":{"n":13109437,"d":2500000},"buyingAssetType":"credit_alphanum4","buyingAssetCode":"XRP","buyingAssetIssuer":"GBXRPL45NPHCVMFFAYZVUVFFVKSIZ362ZXFP7I2ETNQ3QKZMFLPRDTD5","sellingAssetType":"native","offerId":"1400705218"}],"https://horizon.stellar.org/"],
            [{"id":"f716c17ce95990f6c1815473d276e418ce53c22d0a2487e3f02f37f84b230321","hash":"f716c17ce95990f6c1815473d276e418ce53c22d0a2487e3f02f37f84b230321","ledger":40450882,"opCount":1,"sourceAccount":"GCAD67WM4IFVEEJ2Q3IPHUFKVORXLD7MOHUBLYNSCU3ERKOJQD52YZ7J","time":"2022-04-13T11:57:15Z","fee":"1000","memoType":"none","pagingToken":"173735215286382592"},[{"time":"2022-04-13T11:57:15Z","links":{"self":{"href":"https://horizon.stellar.org/operations/173735215286382593"},"transaction":{"href":"https://horizon.stellar.org/transactions/f716c17ce95990f6c1815473d276e418ce53c22d0a2487e3f02f37f84b230321"},"effects":{"href":"https://horizon.stellar.org/operations/173735215286382593/effects"},"succeeds":{"href":"https://horizon.stellar.org/effects?order=desc&cursor=173735215286382593"},"precedes":{"href":"https://horizon.stellar.org/effects?order=asc&cursor=173735215286382593"}},"id":"173735215286382593","pagingToken":"173735215286382593","transactionSuccessful":True,"sourceAccount":"GCAD67WM4IFVEEJ2Q3IPHUFKVORXLD7MOHUBLYNSCU3ERKOJQD52YZ7J","type":"payment","typeI":1,"createdAt":"2022-04-13T11:57:15Z","transactionHash":"f716c17ce95990f6c1815473d276e418ce53c22d0a2487e3f02f37f84b230321","assetType":"credit_alphanum12","assetCode":"BNDES","assetIssuer":"GAWG3NPQXQEJYQY3SXAOI62W5MTORFVOGYLOWDXEHPJAG62PPKC47DGB","from":"GCAD67WM4IFVEEJ2Q3IPHUFKVORXLD7MOHUBLYNSCU3ERKOJQD52YZ7J","to":"GCEPD2T7SX7AO2L4W33SI56GRJWULEADI6AQAIIDHBA7ZQJ4HPBQ2JZF","amount":"135738.2825896"}],"https://horizon.stellar.org/"],
        ]
        self.api.request = Mock(side_effect=tx_details_mock_response)
        StellarExplorerInterface.tx_details_apis[0] = self.api
        txs_details = []
        for tx_hash in self.hash_of_transactions:
            txs_details.append(StellarExplorerInterface.get_api().get_tx_details(tx_hash))
        expected_txs_details = [
            {'hash': 'c15ae5bc33d010fa4d3469714a40cd9cb021837cdc0fc20c712a3b83e5af4e33', 'success': True, 'block': 48977558, 'date': datetime.datetime(2023, 11, 12, 1, 57, 21, tzinfo=UTC), 'fees': Decimal('100'), 'memo': '591508512', 'confirmations': 0, 'raw': None, 'inputs': [], 'outputs': [], 'transfers': [{'type': 'MainCoin', 'symbol': 'xlm', 'currency': 19, 'from': 'GDJF3HLA53SLZ47BV6M2RHO5EBWT44RAYDPAOI6ENIDI4F44LODJSGX5', 'to': 'GCNZ3SFMGWKHTFFDEAB2QYQRCIZUQ55DULDF775WH7JR77P7UPJLMY2U', 'value': Decimal('25.9340000'), 'is_valid': True,  'memo': '591508512','token': None}]},
            {'success': False},
            {'success': False},
            {'success': False}
        ]
        for expected_tx_details, tx_details in zip(expected_txs_details, txs_details):
            assert tx_details == expected_tx_details
