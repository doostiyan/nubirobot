import datetime
from decimal import Decimal
from unittest import TestCase
from unittest.mock import Mock

import pytest

from exchange.base.models import Currencies
from exchange.blockchain.api.elrond.bitquery_elrond import BitqueryElrondApi
from exchange.blockchain.api.elrond.elrond_explorer_interface import ElrondExplorerInterface
from exchange.blockchain.explorer_original import BlockchainExplorer


@pytest.mark.slow
class TestBitqueryElrondApiCalls(TestCase):
    api = BitqueryElrondApi

    addresses = ['erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm',
                 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu']
    txs_hash = ['75171707167a6ade4d142b579b9a6d725e126ab67ad6a3dfb8703bbaa006b1cb',
                'd2cc0655144c0257a37168b4da26b9f736bf4c13c11967657435857f0aaa2487']

    @classmethod
    def check_general_response(cls, response):
        if set(response.keys()) != {'data'}:
            return False
        if set(response.get('data').keys()) != {'elrond'}:
            return False
        return True

    def test_get_block_head_api(self):
        get_block_head_response = self.api.get_block_head()
        assert self.check_general_response(get_block_head_response)
        assert set(get_block_head_response.get('data').get('elrond').keys()) == {'blocks'}
        blocks = get_block_head_response.get('data').get('elrond').get('blocks')
        assert len(blocks) == 1
        assert set(blocks[0].keys()) == {'time', 'height'}
        assert set(blocks[0].get('time').keys()) == {'time'}

    def test_get_tx_details_api(self):
        for tx_hash in self.txs_hash:
            get_tx_details_response = self.api.get_tx_details(tx_hash)
            assert self.check_general_response(get_tx_details_response)
            transactions = get_tx_details_response.get('data').get('elrond').get('transactions')
            assert 0 <= len(transactions) <= 1
            if len(transactions) == 1:
                assert set(transactions[0].keys()) == {'any', 'sender', 'receiver', 'status', 'value', 'hash', 'fee',
                                                       'function', 'time', 'senderShard','senderBlock'}
                assert set(transactions[0].get('sender').keys()) == {'address'}
                assert set(transactions[0].get('receiver').keys()) == {'address'}
                assert set(transactions[0].get('time').keys()) == {'time'}

    def test_get_address_txs_api(self):
        for address in self.addresses:
            get_address_txs_response = self.api.get_address_txs(address)
            assert self.check_general_response(get_address_txs_response)
            transactions = get_address_txs_response.get('data').get('elrond').get('transactions')
            for transaction in transactions:
                assert set(transaction.keys()) == {'any', 'sender', 'receiver', 'status', 'value', 'hash', 'fee',
                                                   'time', 'senderShard','senderBlock','function'}
                assert set(transaction.get('sender').keys()) == {'address'}
                assert set(transaction.get('receiver').keys()) == {'address'}
                assert set(transaction.get('time').keys()) == {'time'}


class TestBitqueryElrondFromExplorer(TestCase):
    api = BitqueryElrondApi

    addresses = ['erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm',
                 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu']
    txs_hash = ['75171707167a6ade4d142b579b9a6d725e126ab67ad6a3dfb8703bbaa006b1cb',
                'd2cc0655144c0257a37168b4da26b9f736bf4c13c11967657435857f0aaa2487']

    def test_get_tx_details(self):
        tx_details_mock_responses = [

            {'data': {'elrond': {'transactions': []}}},
            {'data': {'elrond': {'transactions': [{'any': '13539603', 'sender': {
                'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm'}, 'receiver': {
                'address': 'erd1mnetnuvf683nx4t5dl0ega0frvjvekgtfcqltx5eejlr46ylc77qjl9yk6'}, 'status': 'success',
                                                   'value': 0.37683112893499976,
                                                   'hash': 'd2cc0655144c0257a37168b4da26b9f736bf4c13c11967657435857f0aaa2487',
                                                   'fee': 5e-05, 'function': '',
                                                   'time': {'time': '2023-02-26 11:38:48'}, 'senderShard': '1',
                                                   'senderBlock': {
                                                       'hash': '0374634a08a3b28bc5b60b78aad97a43d17ff524c1fd2b8920cd77a1575f0ce8'}}]}}}]
        block_head_mock_responses = [
            {'data': {'elrond': {'blocks': [{'time': {'time': '2023-03-10 14:50:36'}, 'height': '13714257'}]}}},
            {'data': {'elrond': {'blocks': [{'time': {'time': '2023-03-10 14:50:36'}, 'height': '13714257'}]}}}]
        self.api.get_block_head = Mock(side_effect=block_head_mock_responses)
        self.api.get_tx_details = Mock(side_effect=tx_details_mock_responses)
        ElrondExplorerInterface.tx_details_apis[0] = self.api
        txs_details = BlockchainExplorer.get_transactions_details(self.txs_hash, 'EGLD')
        expected_txs_details = [{'success': False},
                                {'hash': 'd2cc0655144c0257a37168b4da26b9f736bf4c13c11967657435857f0aaa2487',
                                 'success': True, 'block': 0, 'date': datetime.datetime(2023, 2, 26, 11, 38, 48),
                                 'fees': Decimal('0.00005'), 'memo': None, 'confirmations': 2421137,
                                 'raw': None, 'inputs': [], 'outputs': [], 'transfers': [
                                    {'type': 'MainCoin', 'symbol': 'EGLD', 'currency': 74,
                                     'from': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm',
                                     'to': 'erd1mnetnuvf683nx4t5dl0ega0frvjvekgtfcqltx5eejlr46ylc77qjl9yk6',
                                     'value': Decimal('0.37683112893499976'), 'is_valid': True,'memo': None, 'token': None}]}]
        for expected_tx_details, tx_hash in zip(expected_txs_details, self.txs_hash):
            if txs_details[tx_hash].get('success'):
                txs_details[tx_hash]['confirmations'] = expected_tx_details.get('confirmations')
            assert txs_details.get(tx_hash) == expected_tx_details

    @pytest.mark.slow
    def test_get_address_txs(self):
        block_head_mock_response = [
            {'data': {'elrond': {'blocks': [{'time': {'time': '2023-03-10 14:50:36'}, 'height': '13714257'}]}}},
            {'data': {'elrond': {'blocks': [{'time': {'time': '2023-03-10 14:50:36'}, 'height': '13714257'}]}}}]
        address_txs_mock_responses = [
            {'data': {'elrond': {'transactions': [{'time': {'time': '2023-08-12 00:13:54'},
                                                   'hash': 'd48d49ab374b6b18fb0b122996ec0a82e155cc3210f8b072704e4254ada0559c',
                                                   'status': 'success', 'any': '15935940', 'receiver': {
                    'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm'}, 'sender': {
                    'address': 'erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'}, 'value': 159.9992,
                                                   'fee': 5e-05, 'senderShard': '1', 'function': '', 'senderBlock': {
                    'hash': 'e51ff11818d2de29aa700bc6e9b321e5a0c2c4d713defff632813c148e50385b'}},
                                                  {'time': {'time': '2023-08-10 20:56:54'},
                                                   'hash': '632d08c576cb48d4dcf1771e566f159b49827899257684059c0050aba8ee9568',
                                                   'status': 'success', 'any': '15919581', 'receiver': {
                                                      'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm'},
                                                   'sender': {
                                                       'address': 'erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'},
                                                   'value': 37.0392, 'fee': 5e-05, 'senderShard': '1', 'function': '',
                                                   'senderBlock': {
                                                       'hash': '75075c18fe83183e2223229695d144b63edbfc04591ca70c9a1118c8eaa2767c'}},
                                                  {'time': {'time': '2023-08-10 16:42:36'},
                                                   'hash': '6cf660c9339b3c047440fd5eee0b738671c1f0dc074a79e4d46825c81b3cdde1',
                                                   'status': 'success', 'any': '15917039', 'receiver': {
                                                      'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm'},
                                                   'sender': {
                                                       'address': 'erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'},
                                                   'value': 29.5092, 'fee': 5e-05, 'senderShard': '1', 'function': '',
                                                   'senderBlock': {
                                                       'hash': '6428c7ff7dbd7ff139d6eab01f27949efacd846f3b98856eef314678a79fa656'}},
                                                  {'time': {'time': '2023-08-10 13:42:12'},
                                                   'hash': 'c7694f34014b7e5faff02d049ff5a5a61c39ade6c092f30f4d616574d7937a8d',
                                                   'status': 'success', 'any': '15915243', 'receiver': {
                                                      'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm'},
                                                   'sender': {
                                                       'address': 'erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'},
                                                   'value': 66.4192, 'fee': 5e-05, 'senderShard': '1', 'function': '',
                                                   'senderBlock': {
                                                       'hash': '2e9f98713eb5969b9aabf59327adc75f4491a54fbdea3dc154251768e8e49480'}},
                                                  {'time': {'time': '2023-08-09 20:46:12'},
                                                   'hash': '426a70aefb9773e9df13954d03698dde72f30a787692e5fe718a53384a794ef0',
                                                   'status': 'success', 'any': '15905097', 'receiver': {
                                                      'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm'},
                                                   'sender': {
                                                       'address': 'erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'},
                                                   'value': 34.9992, 'fee': 5e-05, 'senderShard': '1', 'function': '',
                                                   'senderBlock': {
                                                       'hash': '8fa462e0d48a1c88fdc9b7a84ec9efee9b8dd47038443324e9be3e43a41d037b'}},
                                                  {'time': {'time': '2023-08-09 16:14:18'},
                                                   'hash': 'e245018756f4193281c87c0e75016e0c21db9b2ce44f878c8c69cf280f5e016d',
                                                   'status': 'success', 'any': '15902393', 'receiver': {
                                                      'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm'},
                                                   'sender': {
                                                       'address': 'erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'},
                                                   'value': 104.5492, 'fee': 5e-05, 'senderShard': '1', 'function': '',
                                                   'senderBlock': {
                                                       'hash': '0a77003a169c727fc853366cc15db2eba6f724ff1c44966ad2b44c4228fb91b6'}},
                                                  {'time': {'time': '2023-08-09 13:48:30'},
                                                   'hash': '0ab5385a32dbc1a4221611dae1535f563f5bc3bbaa70f5dbb8aafb15cfc0bd9b',
                                                   'status': 'success', 'any': '15900939', 'receiver': {
                                                      'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm'},
                                                   'sender': {
                                                       'address': 'erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'},
                                                   'value': 103.0292, 'fee': 5e-05, 'senderShard': '1', 'function': '',
                                                   'senderBlock': {
                                                       'hash': '47156f80f24f6814bd3530340a71671fa8ce406a5655438c2aed02ec0562670a'}},
                                                  {'time': {'time': '2023-08-09 09:20:54'},
                                                   'hash': '6aa60d6d5bd589840a028c0072aa9d649be5dd6a5f6b6ea77da32e9a3e26901f',
                                                   'status': 'success', 'any': '15898264', 'receiver': {
                                                      'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm'},
                                                   'sender': {
                                                       'address': 'erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'},
                                                   'value': 64.4992, 'fee': 5e-05, 'senderShard': '1', 'function': '',
                                                   'senderBlock': {
                                                       'hash': '8a3111617cbc5c1efd963f42e838c82fe1d9e0c098c442fd1b6c15c7e231ac05'}},
                                                  {'time': {'time': '2023-08-08 13:54:36'},
                                                   'hash': '186f963b2faa9be5c334048642232fa0259effeae794141226792a8bc4f53058',
                                                   'status': 'success', 'any': '15886608', 'receiver': {
                                                      'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm'},
                                                   'sender': {
                                                       'address': 'erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'},
                                                   'value': 17.9992, 'fee': 5e-05, 'senderShard': '1', 'function': '',
                                                   'senderBlock': {
                                                       'hash': '23c043c940a2bf8466a8238caaf9d824584b4ce5262c3866d298e437f1cedc05'}},
                                                  {'time': {'time': '2023-08-07 21:08:30'},
                                                   'hash': 'b540eca2e17e787f4cbf5940b72b01435ded9c13c55e1571b2c3f1d8b8e201f3',
                                                   'status': 'success', 'any': '15876549', 'receiver': {
                                                      'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm'},
                                                   'sender': {
                                                       'address': 'erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'},
                                                   'value': 30.1492, 'fee': 5e-05, 'senderShard': '1', 'function': '',
                                                   'senderBlock': {
                                                       'hash': '63478c1e72edb7b1b5c37877066f33e7ee010ef447f4a351bf2a240de618553e'}},
                                                  {'time': {'time': '2023-08-07 11:12:12'},
                                                   'hash': '9826fa4840556ef602cd938839e9201b8ee26e9a726a1c811123e41ff3caa478',
                                                   'status': 'success', 'any': '15870589', 'receiver': {
                                                      'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm'},
                                                   'sender': {
                                                       'address': 'erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'},
                                                   'value': 162.2692, 'fee': 5e-05, 'senderShard': '1', 'function': '',
                                                   'senderBlock': {
                                                       'hash': 'b1835a84c15323d10804cd5145dfe2b4a748ec009545fcb72fd8d54e6dbd3990'}},
                                                  {'time': {'time': '2023-08-06 12:51:54'},
                                                   'hash': '4176d78328deca542dbefd96623499389525942473ba8cd12a0c36d9bd2d5a93',
                                                   'status': 'success', 'any': '15857193', 'receiver': {
                                                      'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm'},
                                                   'sender': {
                                                       'address': 'erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'},
                                                   'value': 49.4792, 'fee': 5e-05, 'senderShard': '1', 'function': '',
                                                   'senderBlock': {
                                                       'hash': '13ee2248b645b8b37516c00d59b0814016886ad43adf9ec757e3039f35a6f084'}},
                                                  {'time': {'time': '2023-08-05 20:15:54'},
                                                   'hash': '43d7751f9f8622a1f6aba4a45b4d9a0caa7eaeac1bc02f7b0e491ce5ba01774f',
                                                   'status': 'success', 'any': '15847233', 'receiver': {
                                                      'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm'},
                                                   'sender': {
                                                       'address': 'erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'},
                                                   'value': 66.8492, 'fee': 5e-05, 'senderShard': '1', 'function': '',
                                                   'senderBlock': {
                                                       'hash': 'd1e7cd4b693ba8e9ad4f4259591a7333cc03682deb580d576eefbb0ee4c10341'}},
                                                  {'time': {'time': '2023-08-04 21:39:12'},
                                                   'hash': '7f66e17d432f0add2785d96e74975c107bf2f17dd5c4cdaa88fee30d6ef4cf83',
                                                   'status': 'success', 'any': '15833674', 'receiver': {
                                                      'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm'},
                                                   'sender': {
                                                       'address': 'erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'},
                                                   'value': 64.8092, 'fee': 5e-05, 'senderShard': '1', 'function': '',
                                                   'senderBlock': {
                                                       'hash': '4cda50c02c6c2ed1ab056dfbf644037f29e92c977353d3f6702f8d365cb37027'}},
                                                  {'time': {'time': '2023-08-04 20:02:12'},
                                                   'hash': '3204d1ef47ce171eafa111600c429a2120ca2c06289a9e961f684be2908a8083',
                                                   'status': 'success', 'any': '15832705', 'receiver': {
                                                      'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm'},
                                                   'sender': {
                                                       'address': 'erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'},
                                                   'value': 17.8292, 'fee': 5e-05, 'senderShard': '1', 'function': '',
                                                   'senderBlock': {
                                                       'hash': '7c5f662bc4de054647967a7b5d69ad3b5fb7e8aee0d423b07d0af622f2c29b8d'}},
                                                  {'time': {'time': '2023-08-04 13:48:18'},
                                                   'hash': 'c8892c63879c2e5718ea566371d49117220ad9f9297b054ef0835b9ca20b66ab',
                                                   'status': 'success', 'any': '15828975', 'receiver': {
                                                      'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm'},
                                                   'sender': {
                                                       'address': 'erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'},
                                                   'value': 44.4192, 'fee': 5e-05, 'senderShard': '1', 'function': '',
                                                   'senderBlock': {
                                                       'hash': '092cda1e0d2721356a0d6a8281ed0904bd781dfe0e14691452cdaa54487e4fb8'}},
                                                  {'time': {'time': '2023-08-03 20:19:54'},
                                                   'hash': '4dceba496838b7dde6a8a76f80c19b8608d4db43d85c5ee10c360fd87e0c0644',
                                                   'status': 'success', 'any': '15818493', 'receiver': {
                                                      'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm'},
                                                   'sender': {
                                                       'address': 'erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'},
                                                   'value': 0.0, 'fee': 0.00013, 'senderShard': '1', 'function': '',
                                                   'senderBlock': {
                                                       'hash': 'c1a5588ea0c489310a855e12fff13a87b82daedf681156c69ce5ab174981e70a'}},
                                                  {'time': {'time': '2023-08-03 07:45:54'},
                                                   'hash': 'ff24574e13377090d0d6a5d2a898dee644039d01d4384c39358e22408641e5c8',
                                                   'status': 'success', 'any': '15810957', 'receiver': {
                                                      'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm'},
                                                   'sender': {
                                                       'address': 'erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'},
                                                   'value': 45.3392, 'fee': 5e-05, 'senderShard': '1', 'function': '',
                                                   'senderBlock': {
                                                       'hash': '43830dcf9fe0ff5c322c6ec071c4c4bde8761fbb177c045c74d9c06ae82aac8e'}},
                                                  {'time': {'time': '2023-08-02 21:03:24'},
                                                   'hash': '7a362568a4c9fab1914337b586cefd66dd67f28e8009df7c06a3c62b198fe793',
                                                   'status': 'success', 'any': '15810303', 'receiver': {
                                                      'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm'},
                                                   'sender': {
                                                       'address': 'erd1glj072awamhq2njhjs6n6zng2t0h8kjemjgylyg7k6zs5xzrkw7qzur02h'},
                                                   'value': 0.0, 'fee': 0.000136, 'senderShard': '0', 'function': '',
                                                   'senderBlock': {
                                                       'hash': 'd349ed1ead1162e9ac29b73242766649818f0df9e0d29aaf2c1fb0204cf4995a'}},
                                                  {'time': {'time': '2023-08-02 20:24:12'},
                                                   'hash': '37fde2b82ba3a5cfc082a4da9e338247f6e9c2e597d81d8da0e5e6e327004d23',
                                                   'status': 'success', 'any': '15804141', 'receiver': {
                                                      'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm'},
                                                   'sender': {
                                                       'address': 'erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'},
                                                   'value': 0.0, 'fee': 0.00013, 'senderShard': '1', 'function': '',
                                                   'senderBlock': {
                                                       'hash': '83677b9d4b2e0d760c67ae6b41b8d1ff061326e579592f90b57a1f450700a8b6'}}]}}},
            {'data': {'elrond': {'transactions': [{'time': {'time': '2023-08-09 18:17:06'},
                                                   'hash': '8f8e1c817f2488d8067d034756db918629ebed2d70948bd68536b517a30dcab7',
                                                   'status': 'success', 'any': '15903607', 'receiver': {
                    'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu'}, 'sender': {
                    'address': 'erd1mvmu03jl78vp56j769j99zlvmp2n5x4ggaehmfswgwzf7ma5xm0s4u70az'},
                                                   'value': 0.2049178452207804, 'fee': 5e-05, 'senderShard': '1',
                                                   'function': '', 'senderBlock': {
                    'hash': '6492e89b2a4c995598ebe7bcc25574f092501279df97de6c0cbb70ae0d3b3fdb'}},
                                                  {'time': {'time': '2023-08-09 15:15:54'},
                                                   'hash': '8b0a652b2ac38861cffc5d71f30474754d04bf51577b7c2f85e3a452ecf79d21',
                                                   'status': 'success', 'any': '15901811', 'receiver': {
                                                      'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu'},
                                                   'sender': {
                                                       'address': 'erd1mvmu03jl78vp56j769j99zlvmp2n5x4ggaehmfswgwzf7ma5xm0s4u70az'},
                                                   'value': 0.19598732424557158, 'fee': 5e-05, 'senderShard': '1',
                                                   'function': '', 'senderBlock': {
                                                      'hash': '63c0b30b02d4f6e6dad3b43f9e964af84f83381a934c66a715d69fc3ca0a3dde'}},
                                                  {'time': {'time': '2023-08-07 14:40:00'},
                                                   'hash': '837222fce7f283bdf1de3c8029838aa4a0970c8a8434fe4e4b63148111a122b9',
                                                   'status': 'success', 'any': '15878440', 'receiver': {
                                                      'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu'},
                                                   'sender': {
                                                       'address': 'erd15s83lzdcmcu7cn4pynlat4uysjj9ssrfawn63a8p7p43kw8jq9yq6tp43m'},
                                                   'value': 0.6095938537065532, 'fee': 5e-05, 'senderShard': '0',
                                                   'function': '', 'senderBlock': {
                                                      'hash': 'b6346ab2a9d50009b2aa44b4de0120c63c793eec76e5ebc6baf72ec79ff28257'}},
                                                  {'time': {'time': '2023-08-02 17:53:18'},
                                                   'hash': 'a7f021829672544ac25aac591e2fb53e6e82819d28e598dbd5c67ea85b30ac24',
                                                   'status': 'success', 'any': '15802632', 'receiver': {
                                                      'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu'},
                                                   'sender': {
                                                       'address': 'erd1mvmu03jl78vp56j769j99zlvmp2n5x4ggaehmfswgwzf7ma5xm0s4u70az'},
                                                   'value': 0.37019907586370937, 'fee': 5e-05, 'senderShard': '1',
                                                   'function': '', 'senderBlock': {
                                                      'hash': '8c7b833599841a5c156eff60619207aa6dd2696e3996a83670dcf3a5708362f9'}},
                                                  {'time': {'time': '2023-08-02 10:04:00'},
                                                   'hash': '3dd7b8b9e72923fa508fd44422cb6cbf825835ca64b593d53637f6cfe43966f2',
                                                   'status': 'success', 'any': '15803720', 'receiver': {
                                                      'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu'},
                                                   'sender': {
                                                       'address': 'erd15s83lzdcmcu7cn4pynlat4uysjj9ssrfawn63a8p7p43kw8jq9yq6tp43m'},
                                                   'value': 0.27428910682025204, 'fee': 5e-05, 'senderShard': '0',
                                                   'function': '', 'senderBlock': {
                                                      'hash': '61d67f2e6311cbd46a72edc1f404acac96abef9e51355155ccca208c5188a8d3'}},
                                                  {'time': {'time': '2023-08-01 09:40:42'},
                                                   'hash': '7789255c5e0f354ff27594768913c548a59498f4421ee417dfbbd981d5c837c1',
                                                   'status': 'success', 'any': '15783313', 'receiver': {
                                                      'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu'},
                                                   'sender': {
                                                       'address': 'erd15ztdsku37sjp5vrzewxyy9ctps699rssj504w882lfletn89gpfslqsze0'},
                                                   'value': 0.6227583046708809, 'fee': 5e-05, 'senderShard': '1',
                                                   'function': '', 'senderBlock': {
                                                      'hash': '1dd0c9f57311686fb4329c267e1fc9b1ad625905a45120c71ad322e9f0deff3f'}},
                                                  {'time': {'time': '2023-08-01 09:39:36'},
                                                   'hash': '74837d7322c0f8e785887fc6c37aeead998a660c1a7fc079bb8bc831ae75ec73',
                                                   'status': 'success', 'any': '15789516', 'receiver': {
                                                      'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu'},
                                                   'sender': {
                                                       'address': 'erd1najsu55hpvv2eyhn8987dt2avn5ehn3r4qu4a5nk9hmf274w4apq37f0te'},
                                                   'value': 0.7363637724498022, 'fee': 5e-05, 'senderShard': '2',
                                                   'function': '', 'senderBlock': {
                                                      'hash': '476c8209790d2c2c3785339fd5703d36c9e4620c68655b99ff906fc4b08a2fef'}},
                                                  {'time': {'time': '2023-08-01 07:46:42'},
                                                   'hash': '5d1b40c1a00bda8901bedd9be6b2dd918f87bd1da3880242274aa76d982111a1',
                                                   'status': 'success', 'any': '15782173', 'receiver': {
                                                      'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu'},
                                                   'sender': {
                                                       'address': 'erd15ztdsku37sjp5vrzewxyy9ctps699rssj504w882lfletn89gpfslqsze0'},
                                                   'value': 0.26883161221999086, 'fee': 5e-05, 'senderShard': '1',
                                                   'function': '', 'senderBlock': {
                                                      'hash': 'b011e097eb9af7db29777115378fc3d542f6828f1ba7746e8762bd98176a40fa'}},
                                                  {'time': {'time': '2023-07-31 18:11:12'},
                                                   'hash': 'a49d11ad9b7f4619fc8fb3a5267d8b5ea2795b2b2bece60276413ed0d1f38892',
                                                   'status': 'success', 'any': '15774019', 'receiver': {
                                                      'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu'},
                                                   'sender': {
                                                       'address': 'erd15ztdsku37sjp5vrzewxyy9ctps699rssj504w882lfletn89gpfslqsze0'},
                                                   'value': 1.4634299616058553, 'fee': 5e-05, 'senderShard': '1',
                                                   'function': '', 'senderBlock': {
                                                      'hash': 'b397949db652f797a018b500e4382726f9a898974934b5ac4f0fd3f2004f756b'}},
                                                  {'time': {'time': '2023-07-30 10:37:18'},
                                                   'hash': '528bf0fce216b3ab9e921782428e15e84987011ba2b2cef02fb0b734e6023084',
                                                   'status': 'success', 'any': '15755089', 'receiver': {
                                                      'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu'},
                                                   'sender': {
                                                       'address': 'erd1mvmu03jl78vp56j769j99zlvmp2n5x4ggaehmfswgwzf7ma5xm0s4u70az'},
                                                   'value': 0.758952174859175, 'fee': 5e-05, 'senderShard': '1',
                                                   'function': '', 'senderBlock': {
                                                      'hash': '608b4e93bdf3c4e7c13ad33b2d4f4a8783112a970d5baf7adf964c88dbc66f8a'}},
                                                  {'time': {'time': '2023-07-28 17:25:18'},
                                                   'hash': '7719c6e70d7a1941db89e1a0b1497848bee2238d2f6099c19c127bb28021e61b',
                                                   'status': 'success', 'any': '15736212', 'receiver': {
                                                      'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu'},
                                                   'sender': {
                                                       'address': 'erd15s83lzdcmcu7cn4pynlat4uysjj9ssrfawn63a8p7p43kw8jq9yq6tp43m'},
                                                   'value': 0.5249281881669717, 'fee': 5e-05, 'senderShard': '0',
                                                   'function': '', 'senderBlock': {
                                                      'hash': '8603bc5999c50e342cab21c9792f50ebcdf877cae7a2eccb7a5a4488cb8ba2cc'}},
                                                  {'time': {'time': '2023-07-28 14:29:18'},
                                                   'hash': '99824dca40f15e330c83f32d110c962b8bb136c32fdea341aea5f5cb7da15035',
                                                   'status': 'success', 'any': '15734830', 'receiver': {
                                                      'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu'},
                                                   'sender': {
                                                       'address': 'erd1najsu55hpvv2eyhn8987dt2avn5ehn3r4qu4a5nk9hmf274w4apq37f0te'},
                                                   'value': 0.3913597261465233, 'fee': 5e-05, 'senderShard': '2',
                                                   'function': '', 'senderBlock': {
                                                      'hash': '3271cf2f0c07272be4a20b06ab41b12147f3313b5a4fbd03d126bbafbea3d45e'}},
                                                  {'time': {'time': '2023-07-27 11:35:30'},
                                                   'hash': 'a68405ebcef9d7fa18c7f85e66de2179352bea5953bf8737fa910858ba6038c7',
                                                   'status': 'success', 'any': '15718326', 'receiver': {
                                                      'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu'},
                                                   'sender': {
                                                       'address': 'erd15s83lzdcmcu7cn4pynlat4uysjj9ssrfawn63a8p7p43kw8jq9yq6tp43m'},
                                                   'value': 0.1960985133236294, 'fee': 5e-05, 'senderShard': '0',
                                                   'function': '', 'senderBlock': {
                                                      'hash': '7f006469b81bf0fbe5801480c55cebf004fe4d80d07d031c740d2532744c1919'}},
                                                  {'time': {'time': '2023-07-25 09:30:12'},
                                                   'hash': 'cf265faa4fd3b40f7d3360860010a730264c1459d7660bb8e2d068137f302732',
                                                   'status': 'success', 'any': '15682461', 'receiver': {
                                                      'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu'},
                                                   'sender': {
                                                       'address': 'erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'},
                                                   'value': 0.79214465, 'fee': 5e-05, 'senderShard': '1',
                                                   'function': '', 'senderBlock': {
                                                      'hash': '3fd64e86b56e4227205a3b6709612151f5a6d504da7697f837ce6e5732698486'}},
                                                  {'time': {'time': '2023-07-25 08:26:54'},
                                                   'hash': 'd715acd1ffd5dfbb3374c2c564f4a04eb0dddff5538d2bea3983a5855348829b',
                                                   'status': 'success', 'any': '15681828', 'receiver': {
                                                      'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu'},
                                                   'sender': {
                                                       'address': 'erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'},
                                                   'value': 0.6528704, 'fee': 5e-05, 'senderShard': '1', 'function': '',
                                                   'senderBlock': {
                                                       'hash': 'bd9cd8fb13dac96e23f5dd74d0323ef174988f57b9573551b530bdbb26963320'}},
                                                  {'time': {'time': '2023-07-24 16:06:54'},
                                                   'hash': '1069f822ea24bc9a5b0385e7fa53a84d1d4ca0f7b69aa2820f5a9081cc585bbb',
                                                   'status': 'success', 'any': '15672031', 'receiver': {
                                                      'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu'},
                                                   'sender': {
                                                       'address': 'erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'},
                                                   'value': 1.95254559, 'fee': 5e-05, 'senderShard': '1',
                                                   'function': '', 'senderBlock': {
                                                      'hash': '0783ac1b1eef76d2ca079b13e3139d82ed1b0804272d71cbd092ac2b58d10967'}},
                                                  {'time': {'time': '2023-07-24 13:41:54'},
                                                   'hash': '42858427f25af5c444e4ee4bb138fa712bad4f70dad3a0168020e90b49f83ea8',
                                                   'status': 'success', 'any': '15670581', 'receiver': {
                                                      'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu'},
                                                   'sender': {
                                                       'address': 'erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'},
                                                   'value': 2.27574508, 'fee': 5e-05, 'senderShard': '1',
                                                   'function': '', 'senderBlock': {
                                                      'hash': 'bd5d98de31082d204a5d57b0cbc4c7b1fca493c7eb59577d985f00c20b5c1c80'}},
                                                  {'time': {'time': '2023-07-24 10:57:48'},
                                                   'hash': '36cd731d24305436012d474c266f06eb7fb957515a1e58eca44057a9686cd8a7',
                                                   'status': 'success', 'any': '15668940', 'receiver': {
                                                      'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu'},
                                                   'sender': {
                                                       'address': 'erd15ztdsku37sjp5vrzewxyy9ctps699rssj504w882lfletn89gpfslqsze0'},
                                                   'value': 0.3047368136006862, 'fee': 5e-05, 'senderShard': '1',
                                                   'function': '', 'senderBlock': {
                                                      'hash': 'd1911e6c7b167c3c3ba5f2426ddf80812d86a8b2119db2442f46d5bfc5838e63'}},
                                                  {'time': {'time': '2023-07-24 09:10:42'},
                                                   'hash': '7972da819b93927ec8d312ed22c5c1bb85f64b28c6529e978d1960cd1fa81fe4',
                                                   'status': 'success', 'any': '15667869', 'receiver': {
                                                      'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu'},
                                                   'sender': {
                                                       'address': 'erd15ztdsku37sjp5vrzewxyy9ctps699rssj504w882lfletn89gpfslqsze0'},
                                                   'value': 1.543678364786938, 'fee': 5e-05, 'senderShard': '1',
                                                   'function': '', 'senderBlock': {
                                                      'hash': 'bbad723e92ba89b1fee6a1e7888a2ba7ebba7306374d4ca3977412f0e56cf57d'}},
                                                  {'time': {'time': '2023-07-24 08:25:54'},
                                                   'hash': '88349572540f56c6d8416c31d2401ad3870a15f411512fab7e11b2db39096664',
                                                   'status': 'success', 'any': '15667421', 'receiver': {
                                                      'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu'},
                                                   'sender': {
                                                       'address': 'erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'},
                                                   'value': 1.26147386, 'fee': 5e-05, 'senderShard': '1',
                                                   'function': '', 'senderBlock': {
                                                      'hash': 'a7a64a92a935bc135fc677846387a3e806165438463df367cb4ec7e8dc4b4112'}}]}}}

        ]
        self.api.get_block_head = Mock(side_effect=block_head_mock_response)
        self.api.get_address_txs = Mock(side_effect=address_txs_mock_responses)
        ElrondExplorerInterface.address_txs_apis[0] = self.api
        expected_addresses_txs = [
            [
                {'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm',
                 'from_address': ['erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'],
                 'hash': 'd48d49ab374b6b18fb0b122996ec0a82e155cc3210f8b072704e4254ada0559c', 'block': None,
                 'timestamp': datetime.datetime(2023, 8, 12, 0, 13, 54), 'value': Decimal('159.9992'),
                 'confirmations': 22716, 'is_double_spend': False, 'details': {}, 'tag': None,'contract_address': None,
                 'huge': False, 'invoice': None},
                {'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm',
                 'from_address': ['erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'],
                 'hash': '632d08c576cb48d4dcf1771e566f159b49827899257684059c0050aba8ee9568', 'block': None,
                 'timestamp': datetime.datetime(2023, 8, 10, 20, 56, 54), 'value': Decimal('37.0392'),
                 'confirmations': 39086, 'is_double_spend': False, 'details': {}, 'tag': None,'contract_address': None,
                 'huge': False, 'invoice': None},
                {'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm',
                 'from_address': ['erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'],
                 'hash': '6cf660c9339b3c047440fd5eee0b738671c1f0dc074a79e4d46825c81b3cdde1', 'block': None,
                 'timestamp': datetime.datetime(2023, 8, 10, 16, 42, 36), 'value': Decimal('29.5092'),
                 'confirmations': 41629, 'is_double_spend': False, 'details': {}, 'tag': None,'contract_address': None,
                 'huge': False, 'invoice': None},
                {'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm',
                 'from_address': ['erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'],
                 'hash': 'c7694f34014b7e5faff02d049ff5a5a61c39ade6c092f30f4d616574d7937a8d', 'block': None,
                 'timestamp': datetime.datetime(2023, 8, 10, 13, 42, 12), 'value': Decimal('66.4192'),
                 'confirmations': 43433, 'is_double_spend': False, 'details': {}, 'tag': None,'contract_address': None,
                 'huge': False, 'invoice': None},
                {'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm',
                 'from_address': ['erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'],
                 'hash': '426a70aefb9773e9df13954d03698dde72f30a787692e5fe718a53384a794ef0', 'block': None,
                 'timestamp': datetime.datetime(2023, 8, 9, 20, 46, 12), 'value': Decimal('34.9992'),
                 'confirmations': 53593, 'is_double_spend': False, 'details': {}, 'tag': None,'contract_address': None,
                 'huge': False, 'invoice': None},
                {'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm',
                 'from_address': ['erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'],
                 'hash': 'e245018756f4193281c87c0e75016e0c21db9b2ce44f878c8c69cf280f5e016d', 'block': None,
                 'timestamp': datetime.datetime(2023, 8, 9, 16, 14, 18), 'value': Decimal('104.5492'),
                 'confirmations': 56312, 'is_double_spend': False, 'details': {}, 'tag': None,'contract_address': None,
                 'huge': False, 'invoice': None},
                {'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm',
                 'from_address': ['erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'],
                 'hash': '0ab5385a32dbc1a4221611dae1535f563f5bc3bbaa70f5dbb8aafb15cfc0bd9b', 'block': None,
                 'timestamp': datetime.datetime(2023, 8, 9, 13, 48, 30), 'value': Decimal('103.0292'),
                 'confirmations': 57770, 'is_double_spend': False, 'details': {}, 'tag': None,'contract_address': None,
                 'huge': False, 'invoice': None},
                {'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm',
                 'from_address': ['erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'],
                 'hash': '6aa60d6d5bd589840a028c0072aa9d649be5dd6a5f6b6ea77da32e9a3e26901f', 'block': None,
                 'timestamp': datetime.datetime(2023, 8, 9, 9, 20, 54), 'value': Decimal('64.4992'),
                 'confirmations': 60446, 'is_double_spend': False, 'details': {}, 'tag': None,'contract_address': None,
                 'huge': False, 'invoice': None},
                {'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm',
                 'from_address': ['erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'],
                 'hash': '186f963b2faa9be5c334048642232fa0259effeae794141226792a8bc4f53058', 'block': None,
                 'timestamp': datetime.datetime(2023, 8, 8, 13, 54, 36), 'value': Decimal('17.9992'),
                 'confirmations': 72109, 'is_double_spend': False, 'details': {}, 'tag': None,'contract_address': None,
                 'huge': False, 'invoice': None},
                {'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm',
                 'from_address': ['erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'],
                 'hash': 'b540eca2e17e787f4cbf5940b72b01435ded9c13c55e1571b2c3f1d8b8e201f3', 'block': None,
                 'timestamp': datetime.datetime(2023, 8, 7, 21, 8, 30), 'value': Decimal('30.1492'),
                 'confirmations': 82170, 'is_double_spend': False, 'details': {}, 'tag': None,'contract_address': None,
                 'huge': False, 'invoice': None},
                {'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm',
                 'from_address': ['erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'],
                 'hash': '9826fa4840556ef602cd938839e9201b8ee26e9a726a1c811123e41ff3caa478', 'block': None,
                 'timestamp': datetime.datetime(2023, 8, 7, 11, 12, 12), 'value': Decimal('162.2692'),
                 'confirmations': 88133, 'is_double_spend': False, 'details': {}, 'tag': None,'contract_address': None,
                 'huge': False, 'invoice': None},
                {'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm',
                 'from_address': ['erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'],
                 'hash': '4176d78328deca542dbefd96623499389525942473ba8cd12a0c36d9bd2d5a93', 'block': None,
                 'timestamp': datetime.datetime(2023, 8, 6, 12, 51, 54), 'value': Decimal('49.4792'),
                 'confirmations': 101536, 'is_double_spend': False, 'details': {}, 'tag': None,'contract_address': None,
                 'huge': False, 'invoice': None},
                {'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm',
                 'from_address': ['erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'],
                 'hash': '43d7751f9f8622a1f6aba4a45b4d9a0caa7eaeac1bc02f7b0e491ce5ba01774f', 'block': None,
                 'timestamp': datetime.datetime(2023, 8, 5, 20, 15, 54), 'value': Decimal('66.8492'),
                 'confirmations': 111496, 'is_double_spend': False, 'details': {}, 'tag': None,'contract_address': None,
                 'huge': False, 'invoice': None},
                {'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm',
                 'from_address': ['erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'],
                 'hash': '7f66e17d432f0add2785d96e74975c107bf2f17dd5c4cdaa88fee30d6ef4cf83', 'block': None,
                 'timestamp': datetime.datetime(2023, 8, 4, 21, 39, 12), 'value': Decimal('64.8092'),
                 'confirmations': 125063, 'is_double_spend': False, 'details': {}, 'tag': None,'contract_address': None,
                 'huge': False, 'invoice': None},
                {'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm',
                 'from_address': ['erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'],
                 'hash': '3204d1ef47ce171eafa111600c429a2120ca2c06289a9e961f684be2908a8083', 'block': None,
                 'timestamp': datetime.datetime(2023, 8, 4, 20, 2, 12), 'value': Decimal('17.8292'),
                 'confirmations': 126033, 'is_double_spend': False, 'details': {}, 'tag': None,'contract_address': None,
                 'huge': False, 'invoice': None},
                {'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm',
                 'from_address': ['erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'],
                 'hash': 'c8892c63879c2e5718ea566371d49117220ad9f9297b054ef0835b9ca20b66ab', 'block': None,
                 'timestamp': datetime.datetime(2023, 8, 4, 13, 48, 18), 'value': Decimal('44.4192'),
                 'confirmations': 129772, 'is_double_spend': False, 'details': {}, 'tag': None,'contract_address': None,
                 'huge': False, 'invoice': None},
                {'address': 'erd1swns5yj0vlj05pxx79qafp582mww74lzcwd499lay3z4t3x3sdxsup9fjm',
                 'from_address': ['erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'],
                 'hash': 'ff24574e13377090d0d6a5d2a898dee644039d01d4384c39358e22408641e5c8', 'block': None,
                 'timestamp': datetime.datetime(2023, 8, 3, 7, 45, 54), 'value': Decimal('45.3392'),
                 'confirmations': 147796, 'is_double_spend': False, 'details': {}, 'tag': None,'contract_address': None,
                 'huge': False, 'invoice': None},

            ],
            [
                {'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu',
                 'from_address': ['erd1mvmu03jl78vp56j769j99zlvmp2n5x4ggaehmfswgwzf7ma5xm0s4u70az'],
                 'hash': '8f8e1c817f2488d8067d034756db918629ebed2d70948bd68536b517a30dcab7',
                 'block': None,
                 'timestamp': datetime.datetime(2023, 8, 9, 18, 17, 6),
                 'value': Decimal('0.2049178452207804'),
                 'confirmations': 55276,
                 'is_double_spend': False,
                 'details': {},
                 'tag': None,
                 'contract_address': None,
                 'huge': False,
                 'invoice': None},
                {'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu',
                 'from_address': ['erd1mvmu03jl78vp56j769j99zlvmp2n5x4ggaehmfswgwzf7ma5xm0s4u70az'],
                 'hash': '8b0a652b2ac38861cffc5d71f30474754d04bf51577b7c2f85e3a452ecf79d21',
                 'block': None,
                 'timestamp': datetime.datetime(2023, 8, 9, 15, 15, 54),
                 'value': Decimal('0.19598732424557158'),
                 'confirmations': 57088,
                 'is_double_spend': False,
                 'details': {},
                 'tag': None,
                 'contract_address': None,
                 'huge': False,
                 'invoice': None},
                {'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu',
                 'from_address': ['erd15s83lzdcmcu7cn4pynlat4uysjj9ssrfawn63a8p7p43kw8jq9yq6tp43m'],
                 'hash': '837222fce7f283bdf1de3c8029838aa4a0970c8a8434fe4e4b63148111a122b9',
                 'block': None,
                 'timestamp': datetime.datetime(2023, 8, 7, 14, 40),
                 'value': Decimal('0.6095938537065532'),
                 'confirmations': 86247,
                 'is_double_spend': False,
                 'details': {},
                 'tag': None,
                 'contract_address': None,
                 'huge': False,
                 'invoice': None},
                {'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu',
                 'from_address': ['erd1mvmu03jl78vp56j769j99zlvmp2n5x4ggaehmfswgwzf7ma5xm0s4u70az'],
                 'hash': 'a7f021829672544ac25aac591e2fb53e6e82819d28e598dbd5c67ea85b30ac24',
                 'block': None,
                 'timestamp': datetime.datetime(2023, 8, 2, 17, 53, 18),
                 'value': Decimal('0.37019907586370937'),
                 'confirmations': 156314,
                 'is_double_spend': False,
                 'details': {},
                 'tag': None,
                 'contract_address': None,
                 'huge': False,
                 'invoice': None},
                {'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu',
                 'from_address': ['erd15s83lzdcmcu7cn4pynlat4uysjj9ssrfawn63a8p7p43kw8jq9yq6tp43m'],
                 'hash': '3dd7b8b9e72923fa508fd44422cb6cbf825835ca64b593d53637f6cfe43966f2',
                 'block': None,
                 'timestamp': datetime.datetime(2023, 8, 2, 10, 4),
                 'value': Decimal('0.27428910682025204'),
                 'confirmations': 161007,
                 'is_double_spend': False,
                 'details': {},
                 'tag': None,
                 'contract_address': None,
                 'huge': False,
                 'invoice': None},
                {'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu',
                 'from_address': ['erd15ztdsku37sjp5vrzewxyy9ctps699rssj504w882lfletn89gpfslqsze0'],
                 'hash': '7789255c5e0f354ff27594768913c548a59498f4421ee417dfbbd981d5c837c1',
                 'block': None,
                 'timestamp': datetime.datetime(2023, 8, 1, 9, 40, 42),
                 'value': Decimal('0.6227583046708809'),
                 'confirmations': 175640,
                 'is_double_spend': False,
                 'details': {},
                 'tag': None,
                 'contract_address': None,
                 'huge': False,
                 'invoice': None},
                {'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu',
                 'from_address': ['erd1najsu55hpvv2eyhn8987dt2avn5ehn3r4qu4a5nk9hmf274w4apq37f0te'],
                 'hash': '74837d7322c0f8e785887fc6c37aeead998a660c1a7fc079bb8bc831ae75ec73',
                 'block': None,
                 'timestamp': datetime.datetime(2023, 8, 1, 9, 39, 36),
                 'value': Decimal('0.7363637724498022'),
                 'confirmations': 175651,
                 'is_double_spend': False,
                 'details': {},
                 'tag': None,
                 'contract_address': None,
                 'huge': False,
                 'invoice': None},
                {'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu',
                 'from_address': ['erd15ztdsku37sjp5vrzewxyy9ctps699rssj504w882lfletn89gpfslqsze0'],
                 'hash': '5d1b40c1a00bda8901bedd9be6b2dd918f87bd1da3880242274aa76d982111a1',
                 'block': None,
                 'timestamp': datetime.datetime(2023, 8, 1, 7, 46, 42),
                 'value': Decimal('0.26883161221999086'),
                 'confirmations': 176780,
                 'is_double_spend': False,
                 'details': {},
                 'tag': None,
                 'contract_address': None,
                 'huge': False,
                 'invoice': None},
                {'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu',
                 'from_address': ['erd15ztdsku37sjp5vrzewxyy9ctps699rssj504w882lfletn89gpfslqsze0'],
                 'hash': 'a49d11ad9b7f4619fc8fb3a5267d8b5ea2795b2b2bece60276413ed0d1f38892',
                 'block': None,
                 'timestamp': datetime.datetime(2023, 7, 31, 18, 11, 12),
                 'value': Decimal('1.4634299616058553'),
                 'confirmations': 184935,
                 'is_double_spend': False,
                 'details': {},
                 'tag': None,
                 'contract_address': None,
                 'huge': False,
                 'invoice': None},
                {'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu',
                 'from_address': ['erd1mvmu03jl78vp56j769j99zlvmp2n5x4ggaehmfswgwzf7ma5xm0s4u70az'],
                 'hash': '528bf0fce216b3ab9e921782428e15e84987011ba2b2cef02fb0b734e6023084',
                 'block': None,
                 'timestamp': datetime.datetime(2023, 7, 30, 10, 37, 18),
                 'value': Decimal('0.758952174859175'),
                 'confirmations': 203874,
                 'is_double_spend': False,
                 'details': {},
                 'tag': None,
                 'contract_address': None,
                 'huge': False,
                 'invoice': None},
                {'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu',
                 'from_address': ['erd15s83lzdcmcu7cn4pynlat4uysjj9ssrfawn63a8p7p43kw8jq9yq6tp43m'],
                 'hash': '7719c6e70d7a1941db89e1a0b1497848bee2238d2f6099c19c127bb28021e61b',
                 'block': None,
                 'timestamp': datetime.datetime(2023, 7, 28, 17, 25, 18),
                 'value': Decimal('0.5249281881669717'),
                 'confirmations': 228594,
                 'is_double_spend': False,
                 'details': {},
                 'tag': None,
                 'contract_address': None,
                 'huge': False,
                 'invoice': None},
                {'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu',
                 'from_address': ['erd1najsu55hpvv2eyhn8987dt2avn5ehn3r4qu4a5nk9hmf274w4apq37f0te'],
                 'hash': '99824dca40f15e330c83f32d110c962b8bb136c32fdea341aea5f5cb7da15035',
                 'block': None,
                 'timestamp': datetime.datetime(2023, 7, 28, 14, 29, 18),
                 'value': Decimal('0.3913597261465233'),
                 'confirmations': 230354,
                 'is_double_spend': False,
                 'details': {},
                 'tag': None,
                 'contract_address': None,
                 'huge': False,
                 'invoice': None},
                {'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu',
                 'from_address': ['erd15s83lzdcmcu7cn4pynlat4uysjj9ssrfawn63a8p7p43kw8jq9yq6tp43m'],
                 'hash': 'a68405ebcef9d7fa18c7f85e66de2179352bea5953bf8737fa910858ba6038c7',
                 'block': None,
                 'timestamp': datetime.datetime(2023, 7, 27, 11, 35, 30),
                 'value': Decimal('0.1960985133236294'),
                 'confirmations': 246492,
                 'is_double_spend': False,
                 'details': {},
                 'tag': None,
                 'contract_address': None,
                 'huge': False,
                 'invoice': None},
                {'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu',
                 'from_address': ['erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'],
                 'hash': 'cf265faa4fd3b40f7d3360860010a730264c1459d7660bb8e2d068137f302732',
                 'block': None,
                 'timestamp': datetime.datetime(2023, 7, 25, 9, 30, 12),
                 'value': Decimal('0.79214465'),
                 'confirmations': 276545,
                 'is_double_spend': False,
                 'details': {},
                 'tag': None,
                 'contract_address': None,
                 'huge': False,
                 'invoice': None},
                {'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu',
                 'from_address': ['erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'],
                 'hash': 'd715acd1ffd5dfbb3374c2c564f4a04eb0dddff5538d2bea3983a5855348829b',
                 'block': None,
                 'timestamp': datetime.datetime(2023, 7, 25, 8, 26, 54),
                 'value': Decimal('0.6528704'),
                 'confirmations': 277178,
                 'is_double_spend': False,
                 'details': {},
                 'tag': None,
                 'contract_address': None,
                 'huge': False,
                 'invoice': None},
                {'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu',
                 'from_address': ['erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'],
                 'hash': '1069f822ea24bc9a5b0385e7fa53a84d1d4ca0f7b69aa2820f5a9081cc585bbb',
                 'block': None,
                 'timestamp': datetime.datetime(2023, 7, 24, 16, 6, 54),
                 'value': Decimal('1.95254559'),
                 'confirmations': 286978,
                 'is_double_spend': False,
                 'details': {},
                 'tag': None,
                 'contract_address': None,
                 'huge': False,
                 'invoice': None},
                {'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu',
                 'from_address': ['erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'],
                 'hash': '42858427f25af5c444e4ee4bb138fa712bad4f70dad3a0168020e90b49f83ea8',
                 'block': None,
                 'timestamp': datetime.datetime(2023, 7, 24, 13, 41, 54),
                 'value': Decimal('2.27574508'),
                 'confirmations': 288428,
                 'is_double_spend': False,
                 'details': {},
                 'tag': None,
                 'contract_address': None,
                 'huge': False,
                 'invoice': None},
                {'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu',
                 'from_address': ['erd15ztdsku37sjp5vrzewxyy9ctps699rssj504w882lfletn89gpfslqsze0'],
                 'hash': '36cd731d24305436012d474c266f06eb7fb957515a1e58eca44057a9686cd8a7',
                 'block': None,
                 'timestamp': datetime.datetime(2023, 7, 24, 10, 57, 48),
                 'value': Decimal('0.3047368136006862'),
                 'confirmations': 290069,
                 'is_double_spend': False,
                 'details': {},
                 'tag': None,
                 'contract_address': None,
                 'huge': False,
                 'invoice': None},
                {'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu',
                 'from_address': ['erd15ztdsku37sjp5vrzewxyy9ctps699rssj504w882lfletn89gpfslqsze0'],
                 'hash': '7972da819b93927ec8d312ed22c5c1bb85f64b28c6529e978d1960cd1fa81fe4',
                 'block': None,
                 'timestamp': datetime.datetime(2023, 7, 24, 9, 10, 42),
                 'value': Decimal('1.543678364786938'),
                 'confirmations': 291140,
                 'is_double_spend': False,
                 'details': {},
                 'tag': None,
                 'contract_address': None,
                 'huge': False,
                 'invoice': None},
                {'address': 'erd1czuwkkx8a7zyz8pp2zd2nfysra80a9gctm0ar5wnemx0hxdz60zssknnvu',
                 'from_address': ['erd1sdslvlxvfnnflzj42l8czrcngq3xjjzkjp3rgul4ttk6hntr4qdsv6sets'],
                 'hash': '88349572540f56c6d8416c31d2401ad3870a15f411512fab7e11b2db39096664',
                 'block': None,
                 'timestamp': datetime.datetime(2023, 7, 24, 8, 25, 54),
                 'value': Decimal('1.26147386'),
                 'confirmations': 291588,
                 'is_double_spend': False,
                 'details': {},
                 'tag': None,
                 'contract_address': None,
                 'huge': False,
                 'invoice': None}
            ]
        ]
        for address, expected_address_txs in zip(self.addresses, expected_addresses_txs):
            address_txs = BlockchainExplorer.get_wallet_transactions(address, Currencies.egld, 'EGLD')
            assert len(expected_address_txs) == len(address_txs.get(Currencies.egld))
            for expected_address_tx, address_tx in zip(expected_address_txs, address_txs.get(Currencies.egld)):
                assert address_tx.confirmations > expected_address_tx.get('confirmations')
                address_tx.confirmations = expected_address_tx.get('confirmations')
                assert address_tx.__dict__ == expected_address_tx
