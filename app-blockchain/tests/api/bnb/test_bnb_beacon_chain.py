from unittest import TestCase
from decimal import Decimal
from unittest.mock import Mock
import pytest
from django.conf import settings

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

from exchange.blockchain.api.bnb.bnb_beacon_chain import BeaconChainApi
from exchange.blockchain.explorer_original import BlockchainExplorer
from exchange.blockchain.api.bnb.bnb_explorer_interface import BnbExplorerInterface


@pytest.mark.slow
class TestBnbBeaconChainApiCalls(TestCase):
    api = BeaconChainApi
    hash_of_transactions = ['402646BA0BC060586EA5B638BCE96D7D3C7BCCC9F86581D293DEE24C377C3964',
                            '4B2C00CCDDF0DD13A75C288CCB706A06EAA6743A45ED2B3DA2A9BD852CB08D0C',
                            '412F173ABED751F6AC9B1B772D610D7036CA14D95452F0D8FE68697C2157F6A1',
                            'AA8CD4363BA72753BF935AFF0602E88CB2768829C5BA7B0016625A23BA965C2C']

    def check_general_response(self, response, keys):
        if set(response.keys()).issubset(keys):
            return True
        return False

    def test_get_tx_details_api(self):
        transaction_keys = {
            'hash', 'blockHeight', 'blockTime', 'type', 'fee', 'code', 'source', 'sequence', 'memo', 'log', 'data',
            'asset', 'amount', 'fromAddr', 'toAddr'
        }
        for tx_hash in self.hash_of_transactions:
            get_tx_details_response = self.api.get_tx_details(tx_hash)
            assert self.check_general_response(get_tx_details_response, transaction_keys)


class TestBnbBeaconChainFromExplorer(TestCase):
    api = BeaconChainApi
    currency = Currencies.bnb
    # transactions in order success,invalid(transfer Type but invalid asset),invalid( type freeze which is != transfer),invalid(type CANCEL_ORDER which is != transfer and contains data field)
    # invalid type and no asset, invalid type but correct asset
    hash_of_transactions = ['4B2C00CCDDF0DD13A75C288CCB706A06EAA6743A45ED2B3DA2A9BD852CB08D0C',
                            '402646BA0BC060586EA5B638BCE96D7D3C7BCCC9F86581D293DEE24C377C3964',
                            '412F173ABED751F6AC9B1B772D610D7036CA14D95452F0D8FE68697C2157F6A1',
                            'AA8CD4363BA72753BF935AFF0602E88CB2768829C5BA7B0016625A23BA965C2C',
                            '7B289DEBB530D1F1153B659AAAC6EE3DCFB7370727E108DAB396A02416564B22',
                            'F756A40911AC12732A8B2463F57FDC0E49B689D76BF7C53BA8B7A5CC8E5307F4']

    def test_get_tx_details(self):
        tx_details_mock_responses = [
            {'hash': '4B2C00CCDDF0DD13A75C288CCB706A06EAA6743A45ED2B3DA2A9BD852CB08D0C', 'blockHeight': 346920885,
             'blockTime': 1698062416312, 'type': 'TRANSFER', 'fee': 7500, 'code': 0, 'source': 1, 'sequence': 54495,
             'memo': '', 'log': 'Msg 0: ', 'data': None, 'asset': 'BNB', 'amount': 88960363,
             'fromAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn',
             'toAddr': 'bnb159l73gp5a0685m3cnha320uxlwzpq0dk553np9'},
            {'hash': '402646BA0BC060586EA5B638BCE96D7D3C7BCCC9F86581D293DEE24C377C3964', 'blockHeight': 346920978,
             'blockTime': 1698062458311, 'type': 'TRANSFER', 'fee': 7500, 'code': 0, 'source': 1, 'sequence': 40417,
             'memo': '', 'log': 'Msg 0: ', 'data': None, 'asset': 'CAS-167', 'amount': 4538682000000,
             'fromAddr': 'bnb13q87ekxvvte78t2q7z05lzfethnlht5agfh4ur',
             'toAddr': 'bnb1humvl4yawfg9rgrclgkczey9x3pty6nnzgza8j'},
            {'hash': '412F173ABED751F6AC9B1B772D610D7036CA14D95452F0D8FE68697C2157F6A1', 'blockHeight': 346921823,
             'blockTime': 1698062847774, 'type': 'FREEZE_TOKEN', 'fee': 100000, 'code': 0, 'source': 0, 'sequence': 2,
             'memo': '', 'log': 'Msg 0: ', 'data': None, 'asset': 'NOW-E68', 'amount': 630248483585,
             'fromAddr': 'bnb15ar96n84dsjvg4rkxzyeag2mhmju9m0f944r9p', 'toAddr': None},
            {'hash': 'AA8CD4363BA72753BF935AFF0602E88CB2768829C5BA7B0016625A23BA965C2C', 'blockHeight': 269616240,
             'blockTime': 1664555159259, 'type': 'CANCEL_ORDER', 'fee': 0, 'code': 0, 'source': 2, 'sequence': 1065,
             'memo': '', 'log': 'Msg 0: ',
             'data': '{"orderId":"FB0AE07A39BC0999DB8CC1E01DFEF2A99C2ADBBD-1059","symbol":"ATP-38C_BNB"}',
             'asset': None, 'amount': None, 'fromAddr': 'bnb1lv9wq73ehsyenkuvc8spmlhj4xwz4kaajea7dy', 'toAddr': None}

        ]
        BnbExplorerInterface.tx_details_apis[0] = self.api
        self.api.request = Mock(side_effect=tx_details_mock_responses)
        txs_details = BlockchainExplorer.get_transactions_details(self.hash_of_transactions, 'BNB')
        expected_txs_details = [
            {'4B2C00CCDDF0DD13A75C288CCB706A06EAA6743A45ED2B3DA2A9BD852CB08D0C': {
                'hash': '4B2C00CCDDF0DD13A75C288CCB706A06EAA6743A45ED2B3DA2A9BD852CB08D0C', 'success': True,
                'block': 346920885, 'date': None, 'fees': Decimal('0.00007500'), 'memo': '', 'confirmations': 0,
                'raw': None, 'inputs': [], 'outputs': [], 'transfers': [
                    {'type': 'MainCoin', 'symbol': 'BNB', 'currency': 16,
                     'from': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn',
                     'to': 'bnb159l73gp5a0685m3cnha320uxlwzpq0dk553np9', 'value': Decimal('0.88960363'),
                     'is_valid': True, 'memo': '', 'token': None}]},
                '402646BA0BC060586EA5B638BCE96D7D3C7BCCC9F86581D293DEE24C377C3964': {'success': False},
                '412F173ABED751F6AC9B1B772D610D7036CA14D95452F0D8FE68697C2157F6A1': {'success': False},
                'AA8CD4363BA72753BF935AFF0602E88CB2768829C5BA7B0016625A23BA965C2C': {'success': False},
                '7B289DEBB530D1F1153B659AAAC6EE3DCFB7370727E108DAB396A02416564B22': {'success': False},
                'F756A40911AC12732A8B2463F57FDC0E49B689D76BF7C53BA8B7A5CC8E5307F4': {'success': False}}
        ]
        for expected_tx_details, tx_hash in zip(expected_txs_details, self.hash_of_transactions):
            assert txs_details[tx_hash].get('success') == expected_tx_details[tx_hash].get('success')
            if txs_details[tx_hash].get('success'):
                assert txs_details[tx_hash] == expected_tx_details[tx_hash]
