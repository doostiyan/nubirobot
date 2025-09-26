import datetime
import pytest
from decimal import Decimal
from unittest import TestCase
from unittest.mock import Mock
from django.core.cache import cache
from django.conf import settings
from pytz import UTC
if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies
from exchange.blockchain.utils import BlockchainUtilsMixin
from exchange.blockchain.explorer_original import BlockchainExplorer
from exchange.blockchain.api.filecoin.filecoin_explorer_interface import FilecoinExplorerInterface
from exchange.blockchain.api.filecoin.filecoin_bitquery import FilecoinBitqueryApi


@pytest.mark.slow
class TestBitqueryFilecoinApiCalls(TestCase):
    api = FilecoinBitqueryApi
    general_api = FilecoinExplorerInterface.get_api()

    addresses_of_account = ['f410f6vyzxlrug5vux6x5a7pvdl2orafibezzpbywv6y',
                            'f1emm55jaulyucsuttc7a6cf62uysn5rcwd7k4qyy',
                            ]
    hash_of_transactions = ['bafy2bzacedjn33wphjyplalpldglnsdobuh2thbgovwtpwkrwjcut6u454mms',
                            'bafy2bzaced4vjqvjy6eh6ne64czr6xilplpogehc33og362334lztxxcn57d2']

    @classmethod
    def check_general_response(cls, response, keys):
        if set(response.keys()).issubset(keys):
            return True
        return False

    def test_get_balance_api(self):

        keys = {'address', 'balance'}
        for address in self.addresses_of_account:
            get_balance_result = self.api.get_balance(address)
            assert isinstance(get_balance_result, dict)
            assert isinstance(get_balance_result.get('data'), dict)
            assert isinstance(get_balance_result.get('data').get('filecoin'), dict)
            assert isinstance(get_balance_result.get('data').get('filecoin').get('address'), list)
            assert self.check_general_response(get_balance_result.get('data').get('filecoin').get('address')[0], keys)

    def test_get_tx_details_api(self):
        transaction_keys = {'method', 'block', 'hash', 'success', 'date', 'sender', 'receiver', 'gasFeeCap', 'gasLimit',
                            'gasLimit', 'gasPremium', 'gas', 'minerTip', 'baseFeeBurn', 'amount', 'exitCode'}
        for tx_hash in self.hash_of_transactions:
            get_tx_details_response = self.api.get_tx_details(tx_hash)
            assert isinstance(get_tx_details_response, dict)
            assert isinstance(get_tx_details_response.get('data'), dict)
            assert isinstance(get_tx_details_response.get('data').get('filecoin'), dict)
            assert isinstance(get_tx_details_response.get('data').get('filecoin').get('messages'), list)
            if get_tx_details_response.get('data').get('filecoin').get('messages'):
                assert isinstance(get_tx_details_response.get('data').get('filecoin').get('messages')[0], dict)
                assert len(get_tx_details_response) != 0
                assert self.check_general_response(get_tx_details_response.get('data').get('filecoin').get('messages')[0],
                                                   transaction_keys)

    def test_get_blocks_txs_api(self):
        transaction_keys = {'hash', 'method', 'any', 'receiver', 'sender', 'success', 'block', 'baseFeeBurn', 'minerTip', 'exitCode'}
        from_block = 3590157
        to_block = 3590160
        get_blocks_txs_response = self.api.get_batch_block_txs(from_block, to_block)
        assert isinstance(get_blocks_txs_response, dict)
        assert isinstance(get_blocks_txs_response.get('data'), dict)
        assert isinstance(get_blocks_txs_response.get('data').get('filecoin'), dict)
        assert isinstance(get_blocks_txs_response.get('data').get('filecoin').get('blocks'), list)
        assert isinstance(get_blocks_txs_response.get('data').get('filecoin').get('blocks')[0].get('height'), int)
        assert isinstance(get_blocks_txs_response.get('data').get('filecoin').get('messages'), list)
        transactions = get_blocks_txs_response.get('data').get('filecoin').get('messages')
        for transaction in transactions:
            assert isinstance(transaction, dict)
            assert self.check_general_response(transaction, transaction_keys)


class TestBitqueryFilecoinFromExplorer(TestCase):
    api = FilecoinBitqueryApi
    currency = Currencies.fil
    addresses_of_account = ['f410f6vyzxlrug5vux6x5a7pvdl2orafibezzpbywv6y',
                            'f1emm55jaulyucsuttc7a6cf62uysn5rcwd7k4qyy']
    hash_of_transactions = ['bafy2bzacedng6z2vcuxcrz2xxl5h44d74itvvhx6afnelpusfhib7iarcndp2',
                            'bafy2bzaceaq24cuu6uurwtpyb3fymv7burkkl4rbv52mri427gvzmid5wxqye',
                            'bafy2bzacedjn33wphjyplalpldglnsdobuh2thbgovwtpwkrwjcut6u454mms'
                            ]

    def test_get_balance(self):
        balance_mock_response = [{'data': {'filecoin': {'address': [
            {'address': 'f410f6vyzxlrug5vux6x5a7pvdl2orafibezzpbywv6y', 'balance': 0.000205375181867332}]}}},
            {'data': {'filecoin': {'address': [
                {'address': 'f1emm55jaulyucsuttc7a6cf62uysn5rcwd7k4qyy', 'balance': 0.2989301155524801}]}}}]
        self.api.request = Mock(side_effect=balance_mock_response)
        FilecoinExplorerInterface.balance_apis[0] = self.api
        balances = BlockchainExplorer.get_wallets_balance({'FIL': self.addresses_of_account}, Currencies.fil)
        expected_balances = {Currencies.fil: [
            {'address': 'f410f6vyzxlrug5vux6x5a7pvdl2orafibezzpbywv6y', 'balance': Decimal('0.000205375181867332'),
             'received': Decimal('0.000205375181867332'), 'rewarded': Decimal('0'), 'sent': Decimal('0')},
            {'address': 'f1emm55jaulyucsuttc7a6cf62uysn5rcwd7k4qyy', 'balance': Decimal('0.2989301155524801'),
             'received': Decimal('0.2989301155524801'), 'rewarded': Decimal('0'), 'sent': Decimal('0')}]}

        assert self.currency in balances.keys()
        expected_values = expected_balances.values()
        expected_merged_list = []
        for sublist in expected_values:
            expected_merged_list.extend(sublist)
        for balance, expected_balance in zip(balances.get(Currencies.fil), expected_merged_list):
            assert balance == expected_balance

    def test_get_tx_details(self):
        tx_details_mock_responses = [{'data': {'filecoin': {'blocks': [{'height': 3607430}], 'messages': [{'method': {'name': 'Transfer'}, 'block': {'height': 2349511}, 'hash': 'bafy2bzacedng6z2vcuxcrz2xxl5h44d74itvvhx6afnelpusfhib7iarcndp2', 'success': True, 'date': {'date': '2022-11-18 00:00:00'}, 'sender': {'address': 'f15425tij5zososhjq7g3vnsnkccrw3xwddrqhi5y'}, 'receiver': {'address': 'f1mzw4fhuobcdaamwyyk343otpo2sldu776uojbji'}, 'gas': 490568, 'minerTip': 8.7326800948e-08, 'baseFeeBurn': 0.000127748553369528, 'amount': 1.6, 'exitCode': '0'}]}}},
                                     {'data': {'filecoin': {'blocks': [{'height': 3607430}], 'messages': []}}},
                                     {'data': {'filecoin': {'blocks': [{'height': 3607430}], 'messages': [{'method': {'name': 'Transfer'}, 'block': {'height': 2268538}, 'hash': 'bafy2bzacedjn33wphjyplalpldglnsdobuh2thbgovwtpwkrwjcut6u454mms', 'success': False, 'date': {'date': '2022-10-21 00:00:00'}, 'sender': {'address': 'f3ugesb7mvq6wsph7ajymfaxber34ucttqu5agdy4xs72jgaxl7dctnuzmxfot5qjkrnztli4ngapgjmxnjldq'}, 'receiver': {'address': 'f3qvhtg33nq56e4qunx5cvnj5rzykfwszl6kuvetbd7jqngmf4uzgmlcbxqxbqqy5etuw23dvdbodhgamogdra'}, 'gas': 477568, 'minerTip': 1.68309652225e-07, 'baseFeeBurn': 2.1993944848512e-05, 'amount': 5.0, 'exitCode': '6'}]}}},
                                     ]
        self.api.request = Mock(side_effect=tx_details_mock_responses)
        FilecoinExplorerInterface.tx_details_apis[0] = self.api
        txs_details = BlockchainExplorer.get_transactions_details(self.hash_of_transactions, 'FIL')
        expected_txs_details = [{'bafy2bzacedng6z2vcuxcrz2xxl5h44d74itvvhx6afnelpusfhib7iarcndp2': {
            'hash': 'bafy2bzacedng6z2vcuxcrz2xxl5h44d74itvvhx6afnelpusfhib7iarcndp2', 'success': True, 'block': 2349511,
            'date': datetime.datetime(2022, 11, 18, 0, 0, tzinfo=UTC), 'fees': Decimal('0.000127835880170476'), 'memo': None,
            'confirmations': 1257920, 'raw': None, 'inputs': [], 'outputs': [], 'transfers': [
                {'type': 'MainCoin', 'symbol': 'FIL', 'currency': 39,
                 'from': 'f15425tij5zososhjq7g3vnsnkccrw3xwddrqhi5y', 'to': 'f1mzw4fhuobcdaamwyyk343otpo2sldu776uojbji',
                 'value': Decimal('1.6'), 'is_valid': True, 'memo': None, 'token': None}]}},
            {'bafy2bzaceaq24cuu6uurwtpyb3fymv7burkkl4rbv52mri427gvzmid5wxqye': {'success': False}
             },
            {'bafy2bzacedjn33wphjyplalpldglnsdobuh2thbgovwtpwkrwjcut6u454mms': {'success': False}}]

        for expected_tx_details, tx_hash in zip(expected_txs_details, self.hash_of_transactions):
            assert txs_details[tx_hash].get('success') == expected_tx_details[tx_hash].get('success')
            if txs_details[tx_hash].get('success'):
                txs_details[tx_hash]['confirmations'] = expected_tx_details[tx_hash]['confirmations']
                assert txs_details[tx_hash] == expected_tx_details[tx_hash]

    def test_get_blocks_txs(self):
        cache.delete('latest_block_height_processed_fil')
        block_txs_mock_responses = [{'data': {'filecoin': {'blocks': [{'height': 3592577}]}}},
                                    {'data': {'filecoin': {'blocks': [{'height': 3592577}], 'messages': [{'hash': 'bafy2bzaceaqu3mppgbwl24obskikpxskms6cycfag3f7lb5mkcq5iar5teiyk', 'method': {'id': '0', 'name':'Transfer'}, 'any': '19.969', 'receiver': {'address': 'f1yce27zr6nqkuhapquqk65jmapwdy5rkc44e57fy'}, 'sender': {'address': 'f1khdd2v7il7lxn4zjzzrqwceh466mq5k333ktu7q'}, 'success': True, 'block': {'height': 3592577, 'timestamp': {'iso8601': '2024-01-24T08:08:30Z'}}, 'baseFeeBurn': 2.1268582513573195e-07, 'minerTip': 1.556815077431489e-07, 'exitCode': '0'}, {'hash': 'bafy2bzaceamqs5vbni23kwczausmevm5z2s6qyq6gv77vej4tri36r7tatqcm', 'method': {'id': '0', 'name':'Transfer'}, 'any': '14999.999', 'receiver': {'address': 'f1riz5aowcaozls4k42n5c444hp74zvch4q5riadi'}, 'sender': {'address': 'f1khdd2v7il7lxn4zjzzrqwceh466mq5k333ktu7q'}, 'success': True, 'block': {'height': 3592577, 'timestamp': {'iso8601': '2024-01-24T08:08:30Z'}}, 'baseFeeBurn': 2.12909874939248e-07, 'minerTip': 1.5674883317089872e-07, 'exitCode': '0'}, {'hash': 'bafy2bzacecqtneble5v2njx4s5vm6ped6re5ykslmhsdnfm2yumwbmibkgbec', 'method': {'id': '0', 'name':'Transfer'}, 'any': '0.2', 'receiver': {'address': 'f1424hqqhyxv5syecwfrf3fyncxkkraly2msyyrvq'}, 'sender': {'address': 'f3wmvs57sqhxnwi3z76gyjkrtadsgsymy2j5umobkjtzij3ysyi6crbb7bm4hnzgjkx6ci6whvlppu4spnokga'}, 'success': True, 'block': {'height': 3592577, 'timestamp': {'iso8601': '2024-01-24T08:08:30Z'}}, 'baseFeeBurn': 2.0305168358454096e-07, 'minerTip': 1.4717745944969275e-07, 'exitCode': '0'}, {'hash': 'bafy2bzacedqwiecaqkw56iigyqtvv42sucgua62v3vaua6nhbhjx7mmawdzzq', 'method': {'id': '0', 'name':'Transfer'}, 'any': '147.34', 'receiver': {'address': 'f1ps6i2laemihel7bcduzba2hd62acy6dltq22dla'}, 'sender': {'address': 'f1ph6a2baxrrokhmaopp7wl4guhlx7pouos7af3iq'}, 'success': True, 'block': {'height': 3592576, 'timestamp': {'iso8601': '2024-01-24T08:08:00Z'}}, 'baseFeeBurn': 2.1811940461000246e-07, 'minerTip': 1.5304500240177357e-07, 'exitCode': '0'}, {'hash': 'bafy2bzacebn3rngujoehvplroa5teeaszd3zzgywyjgbzj5c6qet7cyfa4yzy', 'method': {'id': '0', 'name':'Transfer'}, 'any': '6.8', 'receiver': {'address': 'f1xcextdkr2ecurxrlrovcmvggtx46vlkzkjd5n4q'}, 'sender': {'address': 'f1bm26wrfmytxoclxxdkc73ouav3ar3xofe2uidli'}, 'success': True, 'block': {'height': 3592575, 'timestamp': {'iso8601': '2024-01-24T08:07:30Z'}}, 'baseFeeBurn': 1.965074854138412e-07, 'minerTip': 6.917585122759397e-08, 'exitCode': '0'}, {'hash': 'bafy2bzaced7gmf3ipng6yxayq5j2zaizo6xvglfa7ucgoca3odaqmycbqj6ok', 'method': {'id': '0', 'name':'Transfer'}, 'any': '9999.999995850745', 'receiver': {'address': 'f1sxfq7jjsvihkkzgqax3zzyimhpgxjikws3w2kmy'}, 'sender': {'address': 'f1ekfyrsyptc7watykeq5j4dcfso7jlwgzzkyxilq'}, 'success': True, 'block': {'height': 3592574, 'timestamp': {'iso8601': '2024-01-24T08:07:00Z'}}, 'baseFeeBurn': 1.9689937497599123e-07, 'minerTip': 1.2270280192560582e-06, 'exitCode': '0'}, {'hash': 'bafy2bzacedhnud76aorx4vngqlzld5liad3jwpixfxjsjmyhjcvsxyigsejsq', 'method': {'id': '0', 'name':'Transfer'}, 'any': '6.8', 'receiver': {'address': 'f1yatjzecfzhtllk62stmbedrsdqilqifiigqkqoa'}, 'sender': {'address': 'f1bm26wrfmytxoclxxdkc73ouav3ar3xofe2uidli'}, 'success': True, 'block': {'height': 3592573, 'timestamp': {'iso8601': '2024-01-24T08:06:30Z'}}, 'baseFeeBurn': 1.7690957798228634e-07, 'minerTip': 6.835659614273719e-08, 'exitCode': '0'}, {'hash': 'bafy2bzaceb6n5uhqtaxllsmpj3rv6n3bdwbksuuovfg6w57nrgtjmhymniw2a', 'method': {'id': '0', 'name':'Transfer'}, 'any': '3.0', 'receiver': {'address': 'f157ljxfnq2h3s4qf54nej56asnit32n7gouoczyq'}, 'sender': {'address': 'f3rdhcj4k7r2nwmctmv7dh67v3a3pmh7pcc2qzb2gkeij5ayeqhzv2f3hkdbshvsy6xadf5cbgbfp6263gqjfa'}, 'success': True, 'block': {'height': 3592573, 'timestamp': {'iso8601': '2024-01-24T08:06:30Z'}}, 'baseFeeBurn': 1.6961070446774327e-07, 'minerTip': 1.8586322621179818e-07, 'exitCode': '0'}, {'hash': 'bafy2bzacebregdan27kdgyzrchsg53cdktw7fwrxnscdk4yp5wk6cwwwbf75y', 'method': {'id': '0', 'name':'Transfer'}, 'any': '3.0', 'receiver': {'address': 'f157ljxfnq2h3s4qf54nej56asnit32n7gouoczyq'}, 'sender': {'address': 'f3rdhcj4k7r2nwmctmv7dh67v3a3pmh7pcc2qzb2gkeij5ayeqhzv2f3hkdbshvsy6xadf5cbgbfp6263gqjfa'}, 'success': True, 'block': {'height': 3592573, 'timestamp': {'iso8601': '2024-01-24T08:06:30Z'}}, 'baseFeeBurn': 1.6961070446774327e-07, 'minerTip': 1.869335544185951e-07, 'exitCode': '0'}, {'hash': 'bafy2bzacedl5urfykaev5bpt5lddhp2upxwlthpvb6xmgldguwiu7hlvmzb5i', 'method': {'id': '0', 'name':'Transfer'}, 'any': '3.0', 'receiver': {'address': 'f157ljxfnq2h3s4qf54nej56asnit32n7gouoczyq'}, 'sender': {'address': 'f3rdhcj4k7r2nwmctmv7dh67v3a3pmh7pcc2qzb2gkeij5ayeqhzv2f3hkdbshvsy6xadf5cbgbfp6263gqjfa'}, 'success': True, 'block': {'height': 3592573, 'timestamp': {'iso8601': '2024-01-24T08:06:30Z'}}, 'baseFeeBurn': 1.6961070446774327e-07, 'minerTip': 1.8666670546840737e-07, 'exitCode': '0'}, {'hash': 'bafy2bzacebhfdyumitx6h25lamtl2mznpfhkgpgmqpczdokwzy5sd3v33p4oc', 'method': {'id': '0', 'name':'Transfer'}, 'any': '15.722379617341659', 'receiver': {'address': 'f1vgdm3eo2z4uqgslcps6mhpae6jg6nwn2idqanjy'}, 'sender': {'address': 'f3rr7lhpysn2be3fzsgoun23abcz53c3uesb5c2e263ob7dksja4mz3wkmzsch757cirkdqm6znciftd4ldezq'}, 'success': True, 'block': {'height': 3592573, 'timestamp': {'iso8601': '2024-01-24T08:06:30Z'}}, 'baseFeeBurn': 1.6961070446774327e-07, 'minerTip': 1.4841053619204373e-07, 'exitCode': '0'}]}}}]
        self.api.request = Mock(side_effect=block_txs_mock_responses)
        settings.USE_TESTNET_BLOCKCHAINS = False
        FilecoinExplorerInterface.block_txs_apis[0] = self.api
        expected_txs_addresses = {'input_addresses': {'f3rdhcj4k7r2nwmctmv7dh67v3a3pmh7pcc2qzb2gkeij5ayeqhzv2f3hkdbshvsy6xadf5cbgbfp6263gqjfa', 'f1ekfyrsyptc7watykeq5j4dcfso7jlwgzzkyxilq', 'f1ph6a2baxrrokhmaopp7wl4guhlx7pouos7af3iq', 'f1khdd2v7il7lxn4zjzzrqwceh466mq5k333ktu7q', 'f1bm26wrfmytxoclxxdkc73ouav3ar3xofe2uidli', 'f3rr7lhpysn2be3fzsgoun23abcz53c3uesb5c2e263ob7dksja4mz3wkmzsch757cirkdqm6znciftd4ldezq', 'f3wmvs57sqhxnwi3z76gyjkrtadsgsymy2j5umobkjtzij3ysyi6crbb7bm4hnzgjkx6ci6whvlppu4spnokga'},
                                  'output_addresses': {'f1riz5aowcaozls4k42n5c444hp74zvch4q5riadi', 'f1424hqqhyxv5syecwfrf3fyncxkkraly2msyyrvq', 'f1yce27zr6nqkuhapquqk65jmapwdy5rkc44e57fy', 'f1ps6i2laemihel7bcduzba2hd62acy6dltq22dla', 'f1xcextdkr2ecurxrlrovcmvggtx46vlkzkjd5n4q', 'f1sxfq7jjsvihkkzgqax3zzyimhpgxjikws3w2kmy', 'f1yatjzecfzhtllk62stmbedrsdqilqifiigqkqoa', 'f157ljxfnq2h3s4qf54nej56asnit32n7gouoczyq', 'f1vgdm3eo2z4uqgslcps6mhpae6jg6nwn2idqanjy'}}

        expected_txs_info = {
            'outgoing_txs': {'f1khdd2v7il7lxn4zjzzrqwceh466mq5k333ktu7q': {Currencies.fil: [{'contract_address': None, 'tx_hash': 'bafy2bzaceaqu3mppgbwl24obskikpxskms6cycfag3f7lb5mkcq5iar5teiyk', 'value': Decimal('19.969'), 'block_height': 3592577, 'symbol':'FIL'},
                                                                                            {'contract_address': None, 'tx_hash': 'bafy2bzaceamqs5vbni23kwczausmevm5z2s6qyq6gv77vej4tri36r7tatqcm', 'value': Decimal('14999.999'), 'block_height': 3592577, 'symbol':'FIL'}]},
                             'f3wmvs57sqhxnwi3z76gyjkrtadsgsymy2j5umobkjtzij3ysyi6crbb7bm4hnzgjkx6ci6whvlppu4spnokga': {Currencies.fil: [{'contract_address': None, 'tx_hash': 'bafy2bzacecqtneble5v2njx4s5vm6ped6re5ykslmhsdnfm2yumwbmibkgbec', 'value': Decimal('0.2'), 'block_height': 3592577, 'symbol':'FIL'}]},
                             'f1ph6a2baxrrokhmaopp7wl4guhlx7pouos7af3iq': {Currencies.fil: [{'contract_address': None, 'tx_hash': 'bafy2bzacedqwiecaqkw56iigyqtvv42sucgua62v3vaua6nhbhjx7mmawdzzq', 'value': Decimal('147.34'), 'block_height': 3592576, 'symbol':'FIL'}]},
                             'f1bm26wrfmytxoclxxdkc73ouav3ar3xofe2uidli': {Currencies.fil: [{'contract_address': None, 'tx_hash': 'bafy2bzacebn3rngujoehvplroa5teeaszd3zzgywyjgbzj5c6qet7cyfa4yzy', 'value': Decimal('6.8'), 'block_height': 3592575, 'symbol':'FIL'},
                                                                                            {'contract_address': None, 'tx_hash': 'bafy2bzacedhnud76aorx4vngqlzld5liad3jwpixfxjsjmyhjcvsxyigsejsq', 'value': Decimal('6.8'), 'block_height': 3592573, 'symbol':'FIL'}]},
                             'f1ekfyrsyptc7watykeq5j4dcfso7jlwgzzkyxilq': {Currencies.fil: [{'contract_address': None, 'tx_hash': 'bafy2bzaced7gmf3ipng6yxayq5j2zaizo6xvglfa7ucgoca3odaqmycbqj6ok', 'value': Decimal('9999.999995850745'), 'block_height': 3592574, 'symbol':'FIL'}]},
                             'f3rdhcj4k7r2nwmctmv7dh67v3a3pmh7pcc2qzb2gkeij5ayeqhzv2f3hkdbshvsy6xadf5cbgbfp6263gqjfa': {Currencies.fil: [{'contract_address': None, 'tx_hash': 'bafy2bzaceb6n5uhqtaxllsmpj3rv6n3bdwbksuuovfg6w57nrgtjmhymniw2a', 'value': Decimal('3.0'), 'block_height': 3592573, 'symbol':'FIL'},
                                                                                                                                         {'contract_address': None, 'tx_hash': 'bafy2bzacebregdan27kdgyzrchsg53cdktw7fwrxnscdk4yp5wk6cwwwbf75y', 'value': Decimal('3.0'), 'block_height': 3592573, 'symbol':'FIL'},
                                                                                                                                         {'contract_address': None, 'tx_hash': 'bafy2bzacedl5urfykaev5bpt5lddhp2upxwlthpvb6xmgldguwiu7hlvmzb5i', 'value': Decimal('3.0'), 'block_height': 3592573, 'symbol':'FIL'}]},
                             'f3rr7lhpysn2be3fzsgoun23abcz53c3uesb5c2e263ob7dksja4mz3wkmzsch757cirkdqm6znciftd4ldezq': {Currencies.fil: [{'contract_address': None, 'tx_hash': 'bafy2bzacebhfdyumitx6h25lamtl2mznpfhkgpgmqpczdokwzy5sd3v33p4oc', 'value': Decimal('15.722379617341659'), 'block_height': 3592573, 'symbol':'FIL'}]}},
            'incoming_txs': {'f1yce27zr6nqkuhapquqk65jmapwdy5rkc44e57fy': {Currencies.fil: [{'contract_address': None, 'tx_hash': 'bafy2bzaceaqu3mppgbwl24obskikpxskms6cycfag3f7lb5mkcq5iar5teiyk', 'value': Decimal('19.969'), 'block_height': 3592577, 'symbol':'FIL'}]},
                             'f1riz5aowcaozls4k42n5c444hp74zvch4q5riadi': {Currencies.fil: [{'contract_address': None, 'tx_hash': 'bafy2bzaceamqs5vbni23kwczausmevm5z2s6qyq6gv77vej4tri36r7tatqcm', 'value': Decimal('14999.999'), 'block_height': 3592577, 'symbol':'FIL'}]},
                             'f1424hqqhyxv5syecwfrf3fyncxkkraly2msyyrvq': {Currencies.fil: [{'contract_address': None, 'tx_hash': 'bafy2bzacecqtneble5v2njx4s5vm6ped6re5ykslmhsdnfm2yumwbmibkgbec', 'value': Decimal('0.2'), 'block_height': 3592577, 'symbol':'FIL'}]},
                             'f1ps6i2laemihel7bcduzba2hd62acy6dltq22dla': {Currencies.fil: [{'contract_address': None, 'tx_hash': 'bafy2bzacedqwiecaqkw56iigyqtvv42sucgua62v3vaua6nhbhjx7mmawdzzq', 'value': Decimal('147.34'), 'block_height': 3592576, 'symbol':'FIL'}]},
                             'f1xcextdkr2ecurxrlrovcmvggtx46vlkzkjd5n4q': {Currencies.fil: [{'contract_address': None, 'tx_hash': 'bafy2bzacebn3rngujoehvplroa5teeaszd3zzgywyjgbzj5c6qet7cyfa4yzy', 'value': Decimal('6.8'), 'block_height': 3592575, 'symbol':'FIL'}]},
                             'f1sxfq7jjsvihkkzgqax3zzyimhpgxjikws3w2kmy': {Currencies.fil: [{'contract_address': None, 'tx_hash': 'bafy2bzaced7gmf3ipng6yxayq5j2zaizo6xvglfa7ucgoca3odaqmycbqj6ok', 'value': Decimal('9999.999995850745'), 'block_height': 3592574, 'symbol':'FIL'}]},
                             'f1yatjzecfzhtllk62stmbedrsdqilqifiigqkqoa': {Currencies.fil: [{'contract_address': None, 'tx_hash': 'bafy2bzacedhnud76aorx4vngqlzld5liad3jwpixfxjsjmyhjcvsxyigsejsq', 'value': Decimal('6.8'), 'block_height': 3592573, 'symbol':'FIL'}]},
                             'f157ljxfnq2h3s4qf54nej56asnit32n7gouoczyq': {Currencies.fil: [{'contract_address': None, 'tx_hash': 'bafy2bzaceb6n5uhqtaxllsmpj3rv6n3bdwbksuuovfg6w57nrgtjmhymniw2a', 'value': Decimal('3.0'), 'block_height': 3592573, 'symbol':'FIL'},
                                                                                            {'contract_address': None, 'tx_hash': 'bafy2bzacebregdan27kdgyzrchsg53cdktw7fwrxnscdk4yp5wk6cwwwbf75y', 'value': Decimal('3.0'), 'block_height': 3592573, 'symbol':'FIL'},
                                                                                            {'contract_address': None, 'tx_hash': 'bafy2bzacedl5urfykaev5bpt5lddhp2upxwlthpvb6xmgldguwiu7hlvmzb5i', 'value': Decimal('3.0'), 'block_height': 3592573, 'symbol':'FIL'}]},
                             'f1vgdm3eo2z4uqgslcps6mhpae6jg6nwn2idqanjy': {Currencies.fil: [{'contract_address': None, 'tx_hash': 'bafy2bzacebhfdyumitx6h25lamtl2mznpfhkgpgmqpczdokwzy5sd3v33p4oc', 'value': Decimal('15.722379617341659'), 'block_height': 3592573, 'symbol':'FIL'}]}}
        }
        txs_addresses, txs_info, _ = BlockchainExplorer.get_latest_block_addresses('FIL', None, None, True, True)
        assert BlockchainUtilsMixin.compare_dicts_without_order(expected_txs_addresses, txs_addresses)
        assert BlockchainUtilsMixin.compare_dicts_without_order(expected_txs_info, txs_info)
