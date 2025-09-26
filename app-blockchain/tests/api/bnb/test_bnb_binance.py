import datetime
from unittest import TestCase
from decimal import Decimal
from unittest.mock import Mock
import pytest
from django.conf import settings
from pytz import UTC

from exchange.blockchain.api.general.dtos import TransferTx

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

from exchange.blockchain.api.bnb.binance_new import BnbBinanceApi
from exchange.blockchain.api.bnb.bnb_explorer_interface import BnbExplorerInterface


@pytest.mark.slow
class TestBnbBinanceApiCalls(TestCase):
    api = BnbBinanceApi
    addresses_of_accounts = ['bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn']

    def check_general_response(self, response, keys):
        if set(keys).issubset(set(response.keys())):
            return True
        return False

    def test_get_tx_details_api(self):
        transaction_keys = {'txHash', 'blockHeight', 'txType', 'timeStamp', 'fromAddr', 'toAddr', 'value', 'txAsset',
                            'txFee', 'proposalId', 'txAge', 'orderId', 'code', 'data', 'confirmBlocks', 'memo',
                            'source', 'sequence'}
        transaction_types_check = [('txHash', str), ('blockHeight', int), ('txType', str), ('timeStamp', str),
                                   ('fromAddr', str), ('toAddr', str), ('value', str), ('txAsset', str), ('txFee', str),
                                   ('code', int), ('confirmBlocks', int), ('memo', str)]
        for address in self.addresses_of_accounts:
            get_address_txs_response = self.api.get_address_txs(address)
            assert (get_address_txs_response and isinstance(get_address_txs_response, dict))
            assert (get_address_txs_response.get('tx') and isinstance(get_address_txs_response.get('tx'), list))
            transactions = get_address_txs_response.get('tx')
            for transaction in transactions:
                assert self.check_general_response(transaction, transaction_keys)
                for key, value in transaction_types_check:
                    assert isinstance(transaction.get(key), value)

    def test_get_balance_api(self):
        first_layer_keys = ['balances']
        second_layer_keys = ['free', 'frozen', 'locked', 'symbol']
        for address in self.addresses_of_accounts:
            get_balance_result = self.api.get_balance(address)
            assert self.check_general_response(get_balance_result, first_layer_keys)
            assert isinstance(get_balance_result.get('balances'), list)
            for balance in get_balance_result.get('balances'):
                assert self.check_general_response(balance, second_layer_keys)

    def test_get_block_head_api(self):
        blockhead_keys = {'node_info', 'sync_info', 'validator_info'}
        get_block_head_response = self.api.get_block_head()
        assert self.check_general_response(get_block_head_response, blockhead_keys)
        assert 'latest_block_height' in get_block_head_response.get('sync_info')
        assert isinstance(get_block_head_response.get('sync_info').get('latest_block_height'), int)


class TestBnbBinanceFromExplorer(TestCase):
    api = BnbBinanceApi
    currency = Currencies.bnb
    addresses_of_accounts = ['bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn']
    # transactions in order success,invalid(transfer Type but invalid asset),invalid( type freeze which is != transfer),invalid(type CANCEL_ORDER which is != transfer and contains data field)
    # invalid type and no asset, invalid type but correct asset
    hash_of_transactions = [
        '4B2C00CCDDF0DD13A75C288CCB706A06EAA6743A45ED2B3DA2A9BD852CB08D0C',
        '402646BA0BC060586EA5B638BCE96D7D3C7BCCC9F86581D293DEE24C377C3964',
        '412F173ABED751F6AC9B1B772D610D7036CA14D95452F0D8FE68697C2157F6A1',
        'AA8CD4363BA72753BF935AFF0602E88CB2768829C5BA7B0016625A23BA965C2C',
        '7B289DEBB530D1F1153B659AAAC6EE3DCFB7370727E108DAB396A02416564B22',
        'F756A40911AC12732A8B2463F57FDC0E49B689D76BF7C53BA8B7A5CC8E5307F4'
    ]

    def test_get_txs(self):
        address_txs_mock_responses = [
            {'tx': [
                {'txHash': 'D40755E5A85E12814F7257B0EBD7F31324C61D59E269526A2E61058995A8DC1C', 'blockHeight': 378788621,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-28T12:57:11.626Z',
                 'fromAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn',
                 'toAddr': 'bnb1c4lqcngks8fceqa6tmm2laqkeykx9ahje72er9', 'value': '0.01304383', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 291, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '', 'source': 1, 'sequence': 65745},
                {'txHash': 'FD8374AC1764669B71A7EB8EBDB22D4B89F2615EF53453BA5CF8E6450727ED7A', 'blockHeight': 378788314,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-28T12:48:29.426Z',
                 'fromAddr': 'bnb1fjrzr02vkcx2ne7vgn0p2whwy523yhqd88s2qr',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.12359106', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 813, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '2184198175716975', 'source': 0, 'sequence': 3},
                {'txHash': '474520DE959D8411D339D91160CD2C4E13E1737A30344F24FEDDF2F0044AD428', 'blockHeight': 378788245,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-28T12:46:33.316Z',
                 'fromAddr': 'bnb1gjpapcfapgh2fn2c76jzzj0amxnzqh6fttren6',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.04776590', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 929, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '1641896196256716', 'source': 0, 'sequence': 0},
                {'txHash': 'E0C16E12349FA652C45545E4A0FA89D990860E8793B799EB4BE1238BCB1E4DD0', 'blockHeight': 378788232,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-28T12:46:12.022Z',
                 'fromAddr': 'bnb15n4lvd5prx5yug9ascumvsjevu202azemkr5z8',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.01050284', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 950, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '2137829375513396', 'source': 0, 'sequence': 1},
                {'txHash': 'DE816C3EB24F9BAAC9614AC49E408824C4371B2D554B5B097E445833744981F0', 'blockHeight': 378788123,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-28T12:43:06.303Z',
                 'fromAddr': 'bnb1z0yq08d8zens3lptzhm85c03k3rkmtlx9v3ruf',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.06000000', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 1136, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '2285618258489977', 'source': 0, 'sequence': 0},
                {'txHash': '6FAF0239DF55ED527B50F33787C2CA41AA2252F4FC44B8518B2C66DF6131B402', 'blockHeight': 378787842,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-28T12:35:07.030Z',
                 'fromAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn',
                 'toAddr': 'bnb15n4lvd5prx5yug9ascumvsjevu202azemkr5z8', 'value': '0.01120284', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 1615, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '', 'source': 1, 'sequence': 65744},
                {'txHash': 'E9F48D8B4FA029B625DEC8ADA5A4270A91506787FA13D741723CEB1C7640C5C4', 'blockHeight': 378787644,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-28T12:29:30.729Z',
                 'fromAddr': 'bnb14tymwp2fumdfkchyty4chs6x0ft54hel2eq8ep',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.01303832', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 1951, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '6936233769646827', 'source': 0, 'sequence': 2},
                {'txHash': '9C74313AC8C3F7D5767B325E1F9EB331800FFFA52FF9BDD71C178CE77F1038FF', 'blockHeight': 378786888,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-28T12:08:09.293Z',
                 'fromAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn',
                 'toAddr': 'bnb1cdmchksjmdyvjpv6g00znregwxqxryn08cxy7p', 'value': '0.01148265', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 3233, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '', 'source': 1, 'sequence': 65743},
                {'txHash': '19A10E653A909E287DE4BB34F5B73439199D41622C7ABDD1AB65DE36F70035AA', 'blockHeight': 378786203,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-28T11:48:41.795Z',
                 'fromAddr': 'bnb1ewg7nyfyjme39ntlhw4527n09ymtfsakecltyy',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.01569126', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 4400, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '3841293934442973', 'source': 0, 'sequence': 0},
                {'txHash': '2742A9D72E2E14C67B583FA2ED0495296D22769E3595384F2EE11B00D7A35797', 'blockHeight': 378785235,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-28T11:21:16.147Z',
                 'fromAddr': 'bnb1fnd0k5l4p3ck2j9x9dp36chk059w977pszdgdz',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.01888024', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 6046, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '7178479675467958', 'source': 0, 'sequence': 3771977},
                {'txHash': '724DCE262EEBF43EDCBE47F525042647866126E2A37505A50761D7B76D773FDD', 'blockHeight': 378784399,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-28T10:57:34.256Z',
                 'fromAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn',
                 'toAddr': 'bnb19dfp3z6plv6duf9t5p7qe9ckhhvhfan0dj6knp', 'value': '0.01787200', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 7468, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '', 'source': 1, 'sequence': 65742},
                {'txHash': 'CBF74AB2931ABB03783B43A35A595B24F62E528B2BC6DC25928A0773AEF0487C', 'blockHeight': 378784300,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-28T10:54:45.429Z',
                 'fromAddr': 'bnb1udsvwhld9au7c400m734xyzhtgghlvzd3crh5h',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.11630970', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 7637, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '5516177234493279', 'source': 0, 'sequence': 0},
                {'txHash': 'DAD44832238B14A89F2BA5AE32896802ADF72CB46B2AA9415E3C8D0CAC9D5BB5', 'blockHeight': 378784157,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-28T10:50:42.029Z',
                 'fromAddr': 'bnb1skn8wacypqgrp7yqrjtjx0de8a8eyxcrdggazm',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.09492500', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 7880, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '3196259826422798', 'source': 0, 'sequence': 23},
                {'txHash': 'CACEDB094DF2A815D658BAA9D7FAEB3BD9D3EF5213CABDC7A44664926FB1B5AC', 'blockHeight': 378783369,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-28T10:28:24.097Z',
                 'fromAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn',
                 'toAddr': 'bnb19dfp3z6plv6duf9t5p7qe9ckhhvhfan0dj6knp', 'value': '0.00368000', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 9218, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '', 'source': 1, 'sequence': 65741},
                {'txHash': '21DEB865D5B47B539699636701F2FC7898C674670500C83D1653EA95F0F8E06C', 'blockHeight': 378782303,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-28T09:58:09.778Z',
                 'fromAddr': 'bnb1xrfwzlu9c5208lhtn7ywt0mjrhjh4nt4fjyqxy',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.82070593', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 11032, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '6625297343655927', 'source': 0, 'sequence': 1373923},
                {'txHash': '3B63337B3DB1B59E0A26BE7A2E7EBCA5B7F1C74271E86B76CF04A5CA0AEA899A', 'blockHeight': 378777273,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-28T07:35:37.938Z',
                 'fromAddr': 'bnb1trqnvple8425c3nnnc896w2uwvxgs43z7g3uz3',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.52942683', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 19584, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '4427175894944153', 'source': 0, 'sequence': 0},
                {'txHash': '238D00D8B1A8059F31D2F7B9906B47A7E6D92A566594AA63A92D5038727446AD', 'blockHeight': 378774950,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-28T06:29:45.628Z',
                 'fromAddr': 'bnb1fnd0k5l4p3ck2j9x9dp36chk059w977pszdgdz',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.17343799', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 23537, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '1914167618833531', 'source': 0, 'sequence': 3771953},
                {'txHash': 'EAF8CC27F11D301F8D023FB486F3B78C96E33436944B172AAD9A652060264122', 'blockHeight': 378772959,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-28T05:33:18.713Z',
                 'fromAddr': 'bnb18n6nduplpajevxdxptl8669p86hpm4fylugc8u',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.24838876', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 26923, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '5646546384276736', 'source': 0, 'sequence': 0},
                {'txHash': 'E16266B04C7804FD8A12DF8F085712401A0E529DB1CF2423A19ADA68C5DA2F21', 'blockHeight': 378770797,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-28T04:32:06.111Z',
                 'fromAddr': 'bnb1xrfwzlu9c5208lhtn7ywt0mjrhjh4nt4fjyqxy',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.17359048', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 30596, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '5934394816496522', 'source': 0, 'sequence': 1373910},
                {'txHash': '18F6C460EC5E5CF68FC45E8457937A41A16634D3EA6DE51A9811709D1A059204', 'blockHeight': 378768981,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-28T03:40:39.295Z',
                 'fromAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn',
                 'toAddr': 'bnb1nfmpwp7v0huz7zx0pl02955cladfx9ezhcnwpq', 'value': '0.01612388', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 33683, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '', 'source': 1, 'sequence': 65740},
                {'txHash': '14BD3475D27A33AFE7228E794F0D1042FA1EA729074E488B1B79F136D5653B4E', 'blockHeight': 378766630,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-28T02:34:02.521Z',
                 'fromAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn',
                 'toAddr': 'bnb1zdq466jdun9kfhfhyrq4mr3lwpx2ernjv423wq', 'value': '0.01178445', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 37680, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '', 'source': 1, 'sequence': 65739},
                {'txHash': 'B319530A99120BA524976678A1064210CB9FF0DDC3034E38785920D3488E9FBE', 'blockHeight': 378765963,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-28T02:15:07.283Z',
                 'fromAddr': 'bnb1je24se46fqz8l5klldw48fu2r37a2jnm7p06p2',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.11992500', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 38815, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '4313245781891981', 'source': 1, 'sequence': 0},
                {'txHash': 'CBD3382A1B41C47805109417586BA77F0F7AEE698A1DE23ED241739E8EE1B8F3', 'blockHeight': 378765555,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-28T02:03:34.204Z',
                 'fromAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn',
                 'toAddr': 'bnb1adfak2twduzjk4kqkqupppdtydu6kq48r6wlz7', 'value': '0.01955293', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 39508, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '', 'source': 1, 'sequence': 65738},
                {'txHash': 'A2DA68EC83CE5D323363F9DB56C1B6B7D30D6236C55052398366947496E6D285', 'blockHeight': 378765491,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-28T02:01:48.893Z',
                 'fromAddr': 'bnb1fnd0k5l4p3ck2j9x9dp36chk059w977pszdgdz',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.00173698', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 39613, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '7514238385635121', 'source': 0, 'sequence': 3771942},
                {'txHash': '603D859F76A7A87A4694672021F408CE2E2CA976F1A7DAB80DBD419264AE24DD', 'blockHeight': 378760352,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T23:36:09.594Z',
                 'fromAddr': 'bnb1fnd0k5l4p3ck2j9x9dp36chk059w977pszdgdz',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.02785974', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 48353, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '3714573523788641', 'source': 0, 'sequence': 3771935},
                {'txHash': 'E9E32EF947F6F9F23CA8603013268562768474CA8CD61FE6A8312657E40DF718', 'blockHeight': 378759738,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T23:18:49.767Z',
                 'fromAddr': 'bnb1fnd0k5l4p3ck2j9x9dp36chk059w977pszdgdz',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.17244695', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 49392, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '7242213523741684', 'source': 0, 'sequence': 3771933},
                {'txHash': '83E66132E49FA413DB0AEEB381AF2EAEFBD8A77257CB8FD06434C2A2924AD7AE', 'blockHeight': 378758879,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T22:54:25.914Z',
                 'fromAddr': 'bnb1596s4vt360r53y5lgdpd6g7ldqtj9fy8sf7m9j',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.01652101', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 50856, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '7159796537258482', 'source': 0, 'sequence': 0},
                {'txHash': '4B52D6F70D941E22C6DF4F22082E142B490CBEC96C36BABCEEF9AE8F3D623445', 'blockHeight': 378758426,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T22:41:37.970Z',
                 'fromAddr': 'bnb16gj3a52rpj8hnz5tvtesqsrud457a7aju4g749',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '7.89880000', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 51624, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '4843148176114985', 'source': 0, 'sequence': 47},
                {'txHash': '96E3897F6D6D74C3FA6107620109FA66B2E03773C8488E0E3AE1E7696F8E3A07', 'blockHeight': 378758411,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T22:41:14.036Z',
                 'fromAddr': 'bnb16gj3a52rpj8hnz5tvtesqsrud457a7aju4g749',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '7.00000000', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 51648, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '8132873581273229', 'source': 0, 'sequence': 46},
                {'txHash': '09A8E106BD444ECF613502431A954781D3B472D7B9F32C6A3E16BF869F4B9DA6', 'blockHeight': 378758378,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T22:40:17.976Z',
                 'fromAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn',
                 'toAddr': 'bnb1596s4vt360r53y5lgdpd6g7ldqtj9fy8sf7m9j', 'value': '0.01714601', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 51704, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '', 'source': 1, 'sequence': 65737},
                {'txHash': 'CCAFB2A2F3D7982096EF476A1F8FDF146D8BE608B89EC9817C036633DD95748D', 'blockHeight': 378758302,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T22:38:08.520Z',
                 'fromAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn',
                 'toAddr': 'bnb1kr2f90ny954epjfwlx7xetrjt5cmzvhucn5a4d', 'value': '0.02897175', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 51834, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '', 'source': 1, 'sequence': 65736},
                {'txHash': '5457D4748EEEF28C8115C6B9973683194B65B4EE30775FFC43ED56DEF63EAF31', 'blockHeight': 378758295,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T22:37:55.097Z',
                 'fromAddr': 'bnb16gj3a52rpj8hnz5tvtesqsrud457a7aju4g749',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '7.00000000', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 51847, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '3595991541748197', 'source': 0, 'sequence': 45},
                {'txHash': '56E12DAB1DF28522E6DD0B48D2EDBE153B0B02AA466D50A4CC8D179BA726A33E', 'blockHeight': 378758142,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T22:33:34.630Z',
                 'fromAddr': 'bnb16gj3a52rpj8hnz5tvtesqsrud457a7aju4g749',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.10000000', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 52108, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '4115312338316924', 'source': 0, 'sequence': 44},
                {'txHash': '203336E0F913F9ACB6B8BCA8DBCD625877B976AC5F4D15B2812E58553A684BFA', 'blockHeight': 378758065,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T22:31:23.672Z',
                 'fromAddr': 'bnb16gj3a52rpj8hnz5tvtesqsrud457a7aju4g749',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '6.00000000', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 52239, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '2263217411932216', 'source': 0, 'sequence': 43},
                {'txHash': '52F13AC90770B661E68A76D30F9FD953817687C0521E59E1F9F4DC2502D85AC6', 'blockHeight': 378757977,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T22:28:54.325Z',
                 'fromAddr': 'bnb16gj3a52rpj8hnz5tvtesqsrud457a7aju4g749',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '5.50000000', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 52388, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '9835711516362753', 'source': 0, 'sequence': 42},
                {'txHash': 'C6B2B517122419CFDE6E8E322FBA123FA205E14EC1FB1768855788D2B53EA347', 'blockHeight': 378757779,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T22:23:17.674Z',
                 'fromAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn',
                 'toAddr': 'bnb165q9dz39mqh789zuuuqwkv22plut6f4nzy9jc9', 'value': '27.06412900', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 52725, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '432491806', 'source': 1, 'sequence': 65735},
                {'txHash': '0B8E4D032893C16D96519DB75987B20DF0EB176AF3D64886DD0929EEE3676FE3', 'blockHeight': 378757732,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T22:21:58.951Z',
                 'fromAddr': 'bnb16gj3a52rpj8hnz5tvtesqsrud457a7aju4g749',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '8.00000000', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 52803, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '9284811951922867', 'source': 0, 'sequence': 41},
                {'txHash': '46DD541737661FEAB1283C22FAC3B0F4BDB084109120498CEC24D2CFF548974F', 'blockHeight': 378757699,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T22:21:02.954Z',
                 'fromAddr': 'bnb16gj3a52rpj8hnz5tvtesqsrud457a7aju4g749',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '8.00000000', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 52859, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '7142288458237916', 'source': 0, 'sequence': 40},
                {'txHash': 'E4C5EFB689A10EE68AC87914BAFE68DDDE1EB06EF460F244C210AB6CB092749F', 'blockHeight': 378757656,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T22:19:49.497Z',
                 'fromAddr': 'bnb16gj3a52rpj8hnz5tvtesqsrud457a7aju4g749',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '8.00000000', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 52933, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '8714666529632565', 'source': 0, 'sequence': 39},
                {'txHash': '083A1C753DF4384B7ECB268E81A4B2B2EF59B874BA408D76CE037307B286CC2F', 'blockHeight': 378757592,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T22:17:59.842Z',
                 'fromAddr': 'bnb16gj3a52rpj8hnz5tvtesqsrud457a7aju4g749',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '5.00000000', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 53042, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '8458616961282733', 'source': 0, 'sequence': 38},
                {'txHash': '57E1703BBA704AE5BA1A5723CC840501F1979FCFFB57E8B0846F0C8EF015DD0A', 'blockHeight': 378757523,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T22:16:03.750Z',
                 'fromAddr': 'bnb147rfvps9kasdgnqlv72cj7337qx5jcfq267wk4',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.02988348', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 53158, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '7231532984244892', 'source': 0, 'sequence': 2},
                {'txHash': '31F720B65B9B5EA38D726FB0D80A44B90EBB1A1901F8CFF09E1E7E9BEA8A068E', 'blockHeight': 378756847,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T21:56:57.333Z',
                 'fromAddr': 'bnb16gj3a52rpj8hnz5tvtesqsrud457a7aju4g749',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '5.00000000', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 54305, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '3323353646894969', 'source': 0, 'sequence': 37},
                {'txHash': 'F401C8C09D5B5E44E600F04EED5156F8F4623432A6C940CF3A9B13F380BAB70B', 'blockHeight': 378756787,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T21:55:13.198Z',
                 'fromAddr': 'bnb16gj3a52rpj8hnz5tvtesqsrud457a7aju4g749',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '10.00000000', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 54409, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '5691445972695919', 'source': 0, 'sequence': 36},
                {'txHash': '49240F4D34E8ACC558ADCA3A763DD0CD555AD89F36BE3451DA673CC8D8EDE126', 'blockHeight': 378756756,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T21:54:19.678Z',
                 'fromAddr': 'bnb16gj3a52rpj8hnz5tvtesqsrud457a7aju4g749',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '7.00000000', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 54463, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '3996587426519698', 'source': 0, 'sequence': 35},
                {'txHash': '0AB8BE193DC9AEBA1B5837CFBDE963BB688111D7E4B467E094A4140460F8CE99', 'blockHeight': 378756479,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T21:46:29.889Z',
                 'fromAddr': 'bnb16gj3a52rpj8hnz5tvtesqsrud457a7aju4g749',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '5.00000000', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 54932, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '2551585456144824', 'source': 0, 'sequence': 34},
                {'txHash': '420FB2E8B50F5B0C03101D54563B761FA5E501A6797C9104813451E6C6E923C9', 'blockHeight': 378756371,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T21:43:25.493Z',
                 'fromAddr': 'bnb16gj3a52rpj8hnz5tvtesqsrud457a7aju4g749',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '5.50000000', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 55117, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '7959469586646797', 'source': 0, 'sequence': 33},
                {'txHash': '81D7FBC123541ABC8E825EAC81517863F919183EDB5C76134F8B7FE017C7CFA1', 'blockHeight': 378756338,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T21:42:29.419Z',
                 'fromAddr': 'bnb16gj3a52rpj8hnz5tvtesqsrud457a7aju4g749',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '5.00000000', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 55173, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '6657447141949716', 'source': 0, 'sequence': 32},
                {'txHash': '735E2D07C41DDBE0AC3A0067E6940F5F82B5EE8D12894EF8C941DE5627D4823C', 'blockHeight': 378756175,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T21:37:55.879Z',
                 'fromAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn',
                 'toAddr': 'bnb147rfvps9kasdgnqlv72cj7337qx5jcfq267wk4', 'value': '0.03003348', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 55446, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '', 'source': 1, 'sequence': 65734},
                {'txHash': 'BF3CA9A1D4676E3A16090C1724748A61B4140BA873CC6531B1844947DB3FD676', 'blockHeight': 378756152,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T21:37:17.269Z',
                 'fromAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn',
                 'toAddr': 'bnb165q9dz39mqh789zuuuqwkv22plut6f4nzy9jc9', 'value': '37.88731200', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 55485, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '432491806', 'source': 1, 'sequence': 65733},
                {'txHash': '65A437D70BBD80863F532C2073A49A118AFDEAD5164297ED0CA7A23806EA14F4', 'blockHeight': 378756104,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T21:35:53.001Z',
                 'fromAddr': 'bnb16gj3a52rpj8hnz5tvtesqsrud457a7aju4g749',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '5.04663575', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 55569, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '5546124129333772', 'source': 0, 'sequence': 31},
                {'txHash': 'A5EA8059FB1D7D41A5599ABD3134C33A86C7BC47FCD34D280E8EBF34899DE98A', 'blockHeight': 378755117,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T21:07:55.037Z',
                 'fromAddr': 'bnb1w6nfsadqtazkst20zsgyunvhsv9ptm6xn6dkup',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.02536622', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 57247, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '4491769715385914', 'source': 0, 'sequence': 6},
                {'txHash': 'DF5B1F105C5E6D150439F0F5EA6123BDC23D416AA205D75AAFFD9FF77E9571E2', 'blockHeight': 378753966,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T20:35:22.913Z',
                 'fromAddr': 'bnb1m5amny2gs3xdyta6pksmr43zu4727w24syyks7',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.02884022', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 59199, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '4976598773281811', 'source': 0, 'sequence': 1317633},
                {'txHash': '3FBA943232723D05CA2F9AFD4AB63200F3D8DC88C0D3522991DA5876030E04DB', 'blockHeight': 378753302,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T20:16:31.890Z',
                 'fromAddr': 'bnb1j3y47w5fephrlx09k27adw6uaca0syhphpqvu9',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.04600000', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 60330, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '4968838642239131', 'source': 2, 'sequence': 3},
                {'txHash': 'F1721F99CC6B1D907CA66BF417572B81C8629E658BD71110532504C2E400864F', 'blockHeight': 378753104,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T20:10:55.569Z',
                 'fromAddr': 'bnb1n6rfzrxdw9k50nhzywhgw55j4s7qsr3qq5j9jv',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.53424758', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 60667, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '6283755877858295', 'source': 0, 'sequence': 0},
                {'txHash': '97029E9DE6050FC235A5023BE3B4EE01C4E1C21D4DACB968D091EF2B6238C639', 'blockHeight': 378752452,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T19:52:28.702Z',
                 'fromAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn',
                 'toAddr': 'bnb17xevd366kj6zwxhgmnapsuu2qyctyn37d0ay6r', 'value': '0.02812016', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 61773, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '', 'source': 1, 'sequence': 65732},
                {'txHash': 'E7DD5EC8E93D536D5ECB6337C236F4100D59A63BCD0BC6892AFD48E6994B760A', 'blockHeight': 378752324,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T19:48:54.006Z',
                 'fromAddr': 'bnb1sveg9w8jkjez7tk7z3yxd3npz53s2pepqw9hpn',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.01369321', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 61988, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '4311629194928867', 'source': 2, 'sequence': 287},
                {'txHash': '8F4B82CA4CDCCA2D3E474CDAA84844832ABE379AB520768F5498237AF7FF2AB4', 'blockHeight': 378751719,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T19:31:46.094Z',
                 'fromAddr': 'bnb1uh3r7v0mrq9898qpg5x9gdj9lpalrw6thgfyev',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.03193973', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 63016, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '1181538934611895', 'source': 0, 'sequence': 0},
                {'txHash': '5554B7C8988B33829932E84F989B505C5B400C8566666FCFC2DF47F1A361C5A9', 'blockHeight': 378750866,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T19:07:34.871Z',
                 'fromAddr': 'bnb1drcvgps5stpua88x88jzgce6v7yad77nlvt48h',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.02100000', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 64467, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '1469162138539396', 'source': 2, 'sequence': 83},
                {'txHash': 'A7013F36862ED990553E68F250E4B8D73B25F38FAAA1A1D9B5775E99FF2BC8DB', 'blockHeight': 378750416,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T18:54:49.769Z',
                 'fromAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn',
                 'toAddr': 'bnb1drcvgps5stpua88x88jzgce6v7yad77nlvt48h', 'value': '0.03406211', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 65232, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '', 'source': 1, 'sequence': 65731},
                {'txHash': '02CC1F97DE8586C0CE1B4B4ED85364DBA43688E21EEA4F65E6E54983A2210C8D', 'blockHeight': 378749754,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T18:36:05.939Z',
                 'fromAddr': 'bnb1negwwepq32ygfvtar8j6ykmc6aea8x4550wpke',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '1.87428505', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 66356, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '1394662578394591', 'source': 0, 'sequence': 119},
                {'txHash': '964D7F43A5595F4C86C40BE59B464B0370AA6ED350AE2CAC74F3A07C6DE584FE', 'blockHeight': 378749742,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T18:35:45.928Z',
                 'fromAddr': 'bnb1ervh8nkpfm67xu7mhs4mlqhfe8auyn96wcuw2s',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.02371542', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 66376, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '9771494579942733', 'source': 2, 'sequence': 11},
                {'txHash': '76B03CC99C139BA47228928F530E171038BE6A62596AA6D803D8FEEAB06F1358', 'blockHeight': 378748750,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T18:07:41.144Z',
                 'fromAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn',
                 'toAddr': 'bnb1j3y47w5fephrlx09k27adw6uaca0syhphpqvu9', 'value': '0.08092207', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 68061, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '', 'source': 1, 'sequence': 65730},
                {'txHash': '90B08DBB8862F4099D52377E5E6E4DC2DD99E722785AB0E97B8E93F49F277969', 'blockHeight': 378748698,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T18:06:11.668Z',
                 'fromAddr': 'bnb1d7phje96m3takzccfekr5chcn59an3k7wygaxu',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.01867500', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 68151, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '4267173749241134', 'source': 2, 'sequence': 2},
                {'txHash': '5E20FA5DC4A3572EB80D4505E10EABE2F6A1FABBE9D7641DF67C6ECD640BEEC8', 'blockHeight': 378748474,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T17:59:52.710Z',
                 'fromAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn',
                 'toAddr': 'bnb1j3y47w5fephrlx09k27adw6uaca0syhphpqvu9', 'value': '0.01310015', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 68529, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '', 'source': 1, 'sequence': 65729},
                {'txHash': 'C9D957F0D232AFC371914FD6CCB2AF7FB9FB88F91D3398F706115581E6506895', 'blockHeight': 378746729,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T17:10:25.170Z',
                 'fromAddr': 'bnb1xrfwzlu9c5208lhtn7ywt0mjrhjh4nt4fjyqxy',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.01405500', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 71497, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '6894177251314446', 'source': 0, 'sequence': 1373879},
                {'txHash': '8BF2A61E7FAB6770256091CEE7AF9A366BFABC27067E59971BAB595A329FFE50', 'blockHeight': 378746439,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T17:02:13.885Z',
                 'fromAddr': 'bnb1fpayyw8lw2l3apxlsy7ge9ghh362dhu6ghgfyj',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.03050484', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 71988, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '5248733942875457', 'source': 0, 'sequence': 7},
                {'txHash': '4A73395914676195717B1D2EEF69BD65987676C423DF9479BD69362B458E4722', 'blockHeight': 378745449,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T16:34:11.719Z',
                 'fromAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn',
                 'toAddr': 'bnb1sveg9w8jkjez7tk7z3yxd3npz53s2pepqw9hpn', 'value': '0.01791821', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 73670, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '', 'source': 1, 'sequence': 65728},
                {'txHash': '27BEA2745BDC9216C5E1CC4601427715CDE7EB887B93FD633F8F758532F89772', 'blockHeight': 378745371,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T16:31:55.165Z',
                 'fromAddr': 'bnb1fgvwqh2v7h96mnjhny4dmna5qpg0nu6vf845lz',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.23867400', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 73807, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '9454396282775739', 'source': 0, 'sequence': 3},
                {'txHash': 'B30757DA84741EDBF4FEC44548263877F2FE1D8FCC9E6754C383DEE973F13380', 'blockHeight': 378744659,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T16:11:47.676Z',
                 'fromAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn',
                 'toAddr': 'bnb1dzennvrgmvzx76jp764eaqw4cw06vmvc3ex2ez', 'value': '0.01874191', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 75015, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '', 'source': 1, 'sequence': 65727},
                {'txHash': 'C91B7633FA2F831899E5ED045CD6379774D8A538A10A726CE529D924FCD77D39', 'blockHeight': 378744587,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T16:09:43.204Z',
                 'fromAddr': 'bnb1m7fl5hqhg0mklfwtyge742svva3g836cze9h3f',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.20892894', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 75139, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '6835437955641997', 'source': 0, 'sequence': 5},
                {'txHash': '655A09ADAEDEA03C7DE1276F27B327E734E9A91324273BE51DC5AFC8E0866182', 'blockHeight': 378744251,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T16:00:14.149Z',
                 'fromAddr': 'bnb1w5v9avmk2pa0m76en7xszap6kpjuh0tjckvpaa',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.02883967', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 75708, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '9727667511967422', 'source': 2, 'sequence': 1},
                {'txHash': 'BFC6996A5195D5043F75CFA289005A1AB2FA513C883C4BF022F57F291C177674', 'blockHeight': 378743300,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T15:33:14.434Z',
                 'fromAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn',
                 'toAddr': 'bnb1w5v9avmk2pa0m76en7xszap6kpjuh0tjckvpaa', 'value': '0.02898967', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 77328, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '', 'source': 1, 'sequence': 65726},
                {'txHash': 'C2AE8D0E619264B133F9307A55A8E1C73E3B5405E43C394F7387A3CECA29A5CB', 'blockHeight': 378743284,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T15:32:49.191Z',
                 'fromAddr': 'bnb1m5amny2gs3xdyta6pksmr43zu4727w24syyks7',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.01568103', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 77353, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '9146314118744161', 'source': 0, 'sequence': 1317611},
                {'txHash': 'C45879E776CEF4BFA73CDEEC3BC80F5335F52135797FDDAB25CC08E3FB065F32', 'blockHeight': 378742766,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T15:18:08.495Z',
                 'fromAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn',
                 'toAddr': 'bnb1n6rfzrxdw9k50nhzywhgw55j4s7qsr3qq5j9jv', 'value': '0.53487258', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 78234, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '', 'source': 1, 'sequence': 65725},
                {'txHash': '3695A2DEA1D56139D857A734C6500CEF0D98A1456A10E8B75A6B08706EFDA48B', 'blockHeight': 378741784,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T14:50:16.310Z',
                 'fromAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn',
                 'toAddr': 'bnb1avhj030fl69k82zvhjxxwa4u277wa5zrp0kr44', 'value': '0.07217657', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 79906, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '', 'source': 1, 'sequence': 65724},
                {'txHash': '0BB0EFDAB551A888D5B040430B00A9BA3678545114448E56D7DF5752E02BDEB4', 'blockHeight': 378740423,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T14:11:45.534Z',
                 'fromAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn',
                 'toAddr': 'bnb1fpayyw8lw2l3apxlsy7ge9ghh362dhu6ghgfyj', 'value': '0.03057984', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 82217, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '', 'source': 1, 'sequence': 65723},
                {'txHash': '7C52EFF6C24B134B4CEEC5140F16FE87BF1FEDE430FCBDE756A022C6E75AA3F9', 'blockHeight': 378739724,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T13:51:51.989Z',
                 'fromAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn',
                 'toAddr': 'bnb1un6rzq36mle8zx99sadwukc874zy3ncdv76atr', 'value': '0.01345795', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 83410, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '', 'source': 1, 'sequence': 65722},
                {'txHash': 'D857B85F40E5DD600D4A264A7307037ED82BD1D0170354DA95D821BA2AAE946A', 'blockHeight': 378738408,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T13:14:08.312Z',
                 'fromAddr': 'bnb1xrfwzlu9c5208lhtn7ywt0mjrhjh4nt4fjyqxy',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.56227100', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 85674, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '6595976663465736', 'source': 0, 'sequence': 1373859},
                {'txHash': '6C8E86888B09DEDF6B06DFC4C1C65B6BCE1BDCE112035BCED853BA83037AD92C', 'blockHeight': 378738384,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T13:13:27.950Z',
                 'fromAddr': 'bnb10gy4t3myu39qx7fxc0xp35mk5lu77ul9lwht0m',
                 'toAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', 'value': '0.04841503', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 85714, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '9187296267823131', 'source': 0, 'sequence': 0},
                {'txHash': '0F4A881384B96BCD86CE257ED39FC7F497E3DD816CF66FED21273F1159747731', 'blockHeight': 378738298,
                 'txType': 'TRANSFER', 'timeStamp': '2024-07-27T13:10:59.233Z',
                 'fromAddr': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn',
                 'toAddr': 'bnb10gy4t3myu39qx7fxc0xp35mk5lu77ul9lwht0m', 'value': '0.04904003', 'txAsset': 'BNB',
                 'txFee': '0.00007500', 'proposalId': None, 'txAge': 85863, 'orderId': None, 'code': 0, 'data': None,
                 'confirmBlocks': 0, 'memo': '', 'source': 1, 'sequence': 65721}], 'total': 80}
        ]
        BnbExplorerInterface.tx_details_apis[0] = self.api
        self.api.request = Mock(side_effect=address_txs_mock_responses)
        addresses_txs = []
        for address in self.addresses_of_accounts:
            api_response = self.api.get_address_txs(address)
            parsed_response = self.api.parser.parse_address_txs_response(address, api_response, None)
            addresses_txs.append(parsed_response)
        expected_addresses_txs = [[TransferTx(tx_hash='D40755E5A85E12814F7257B0EBD7F31324C61D59E269526A2E61058995A8DC1C', success=True, from_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', to_address='bnb1c4lqcngks8fceqa6tmm2laqkeykx9ahje72er9', value=Decimal('0.01304383'), symbol='BNB', confirmations=0, block_height=378788621, block_hash=None, date=datetime.datetime(2024, 7, 28, 12, 57, 11, 626000, tzinfo=UTC), memo='', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='FD8374AC1764669B71A7EB8EBDB22D4B89F2615EF53453BA5CF8E6450727ED7A', success=True, from_address='bnb1fjrzr02vkcx2ne7vgn0p2whwy523yhqd88s2qr', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.12359106'), symbol='BNB', confirmations=0, block_height=378788314, block_hash=None, date=datetime.datetime(2024, 7, 28, 12, 48, 29, 426000, tzinfo=UTC), memo='2184198175716975', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='474520DE959D8411D339D91160CD2C4E13E1737A30344F24FEDDF2F0044AD428', success=True, from_address='bnb1gjpapcfapgh2fn2c76jzzj0amxnzqh6fttren6', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.04776590'), symbol='BNB', confirmations=0, block_height=378788245, block_hash=None, date=datetime.datetime(2024, 7, 28, 12, 46, 33, 316000, tzinfo=UTC), memo='1641896196256716', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='E0C16E12349FA652C45545E4A0FA89D990860E8793B799EB4BE1238BCB1E4DD0', success=True, from_address='bnb15n4lvd5prx5yug9ascumvsjevu202azemkr5z8', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.01050284'), symbol='BNB', confirmations=0, block_height=378788232, block_hash=None, date=datetime.datetime(2024, 7, 28, 12, 46, 12, 22000, tzinfo=UTC), memo='2137829375513396', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='DE816C3EB24F9BAAC9614AC49E408824C4371B2D554B5B097E445833744981F0', success=True, from_address='bnb1z0yq08d8zens3lptzhm85c03k3rkmtlx9v3ruf', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.06000000'), symbol='BNB', confirmations=0, block_height=378788123, block_hash=None, date=datetime.datetime(2024, 7, 28, 12, 43, 6, 303000, tzinfo=UTC), memo='2285618258489977', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='6FAF0239DF55ED527B50F33787C2CA41AA2252F4FC44B8518B2C66DF6131B402', success=True, from_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', to_address='bnb15n4lvd5prx5yug9ascumvsjevu202azemkr5z8', value=Decimal('0.01120284'), symbol='BNB', confirmations=0, block_height=378787842, block_hash=None, date=datetime.datetime(2024, 7, 28, 12, 35, 7, 30000, tzinfo=UTC), memo='', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='E9F48D8B4FA029B625DEC8ADA5A4270A91506787FA13D741723CEB1C7640C5C4', success=True, from_address='bnb14tymwp2fumdfkchyty4chs6x0ft54hel2eq8ep', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.01303832'), symbol='BNB', confirmations=0, block_height=378787644, block_hash=None, date=datetime.datetime(2024, 7, 28, 12, 29, 30, 729000, tzinfo=UTC), memo='6936233769646827', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='9C74313AC8C3F7D5767B325E1F9EB331800FFFA52FF9BDD71C178CE77F1038FF', success=True, from_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', to_address='bnb1cdmchksjmdyvjpv6g00znregwxqxryn08cxy7p', value=Decimal('0.01148265'), symbol='BNB', confirmations=0, block_height=378786888, block_hash=None, date=datetime.datetime(2024, 7, 28, 12, 8, 9, 293000, tzinfo=UTC), memo='', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='19A10E653A909E287DE4BB34F5B73439199D41622C7ABDD1AB65DE36F70035AA', success=True, from_address='bnb1ewg7nyfyjme39ntlhw4527n09ymtfsakecltyy', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.01569126'), symbol='BNB', confirmations=0, block_height=378786203, block_hash=None, date=datetime.datetime(2024, 7, 28, 11, 48, 41, 795000, tzinfo=UTC), memo='3841293934442973', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='2742A9D72E2E14C67B583FA2ED0495296D22769E3595384F2EE11B00D7A35797', success=True, from_address='bnb1fnd0k5l4p3ck2j9x9dp36chk059w977pszdgdz', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.01888024'), symbol='BNB', confirmations=0, block_height=378785235, block_hash=None, date=datetime.datetime(2024, 7, 28, 11, 21, 16, 147000, tzinfo=UTC), memo='7178479675467958', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='724DCE262EEBF43EDCBE47F525042647866126E2A37505A50761D7B76D773FDD', success=True, from_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', to_address='bnb19dfp3z6plv6duf9t5p7qe9ckhhvhfan0dj6knp', value=Decimal('0.01787200'), symbol='BNB', confirmations=0, block_height=378784399, block_hash=None, date=datetime.datetime(2024, 7, 28, 10, 57, 34, 256000, tzinfo=UTC), memo='', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='CBF74AB2931ABB03783B43A35A595B24F62E528B2BC6DC25928A0773AEF0487C', success=True, from_address='bnb1udsvwhld9au7c400m734xyzhtgghlvzd3crh5h', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.11630970'), symbol='BNB', confirmations=0, block_height=378784300, block_hash=None, date=datetime.datetime(2024, 7, 28, 10, 54, 45, 429000, tzinfo=UTC), memo='5516177234493279', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='DAD44832238B14A89F2BA5AE32896802ADF72CB46B2AA9415E3C8D0CAC9D5BB5', success=True, from_address='bnb1skn8wacypqgrp7yqrjtjx0de8a8eyxcrdggazm', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.09492500'), symbol='BNB', confirmations=0, block_height=378784157, block_hash=None, date=datetime.datetime(2024, 7, 28, 10, 50, 42, 29000, tzinfo=UTC), memo='3196259826422798', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='CACEDB094DF2A815D658BAA9D7FAEB3BD9D3EF5213CABDC7A44664926FB1B5AC', success=True, from_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', to_address='bnb19dfp3z6plv6duf9t5p7qe9ckhhvhfan0dj6knp', value=Decimal('0.00368000'), symbol='BNB', confirmations=0, block_height=378783369, block_hash=None, date=datetime.datetime(2024, 7, 28, 10, 28, 24, 97000, tzinfo=UTC), memo='', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='21DEB865D5B47B539699636701F2FC7898C674670500C83D1653EA95F0F8E06C', success=True, from_address='bnb1xrfwzlu9c5208lhtn7ywt0mjrhjh4nt4fjyqxy', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.82070593'), symbol='BNB', confirmations=0, block_height=378782303, block_hash=None, date=datetime.datetime(2024, 7, 28, 9, 58, 9, 778000, tzinfo=UTC), memo='6625297343655927', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='3B63337B3DB1B59E0A26BE7A2E7EBCA5B7F1C74271E86B76CF04A5CA0AEA899A', success=True, from_address='bnb1trqnvple8425c3nnnc896w2uwvxgs43z7g3uz3', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.52942683'), symbol='BNB', confirmations=0, block_height=378777273, block_hash=None, date=datetime.datetime(2024, 7, 28, 7, 35, 37, 938000, tzinfo=UTC), memo='4427175894944153', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='238D00D8B1A8059F31D2F7B9906B47A7E6D92A566594AA63A92D5038727446AD', success=True, from_address='bnb1fnd0k5l4p3ck2j9x9dp36chk059w977pszdgdz', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.17343799'), symbol='BNB', confirmations=0, block_height=378774950, block_hash=None, date=datetime.datetime(2024, 7, 28, 6, 29, 45, 628000, tzinfo=UTC), memo='1914167618833531', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='EAF8CC27F11D301F8D023FB486F3B78C96E33436944B172AAD9A652060264122', success=True, from_address='bnb18n6nduplpajevxdxptl8669p86hpm4fylugc8u', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.24838876'), symbol='BNB', confirmations=0, block_height=378772959, block_hash=None, date=datetime.datetime(2024, 7, 28, 5, 33, 18, 713000, tzinfo=UTC), memo='5646546384276736', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='E16266B04C7804FD8A12DF8F085712401A0E529DB1CF2423A19ADA68C5DA2F21', success=True, from_address='bnb1xrfwzlu9c5208lhtn7ywt0mjrhjh4nt4fjyqxy', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.17359048'), symbol='BNB', confirmations=0, block_height=378770797, block_hash=None, date=datetime.datetime(2024, 7, 28, 4, 32, 6, 111000, tzinfo=UTC), memo='5934394816496522', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='18F6C460EC5E5CF68FC45E8457937A41A16634D3EA6DE51A9811709D1A059204', success=True, from_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', to_address='bnb1nfmpwp7v0huz7zx0pl02955cladfx9ezhcnwpq', value=Decimal('0.01612388'), symbol='BNB', confirmations=0, block_height=378768981, block_hash=None, date=datetime.datetime(2024, 7, 28, 3, 40, 39, 295000, tzinfo=UTC), memo='', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='14BD3475D27A33AFE7228E794F0D1042FA1EA729074E488B1B79F136D5653B4E', success=True, from_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', to_address='bnb1zdq466jdun9kfhfhyrq4mr3lwpx2ernjv423wq', value=Decimal('0.01178445'), symbol='BNB', confirmations=0, block_height=378766630, block_hash=None, date=datetime.datetime(2024, 7, 28, 2, 34, 2, 521000, tzinfo=UTC), memo='', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='B319530A99120BA524976678A1064210CB9FF0DDC3034E38785920D3488E9FBE', success=True, from_address='bnb1je24se46fqz8l5klldw48fu2r37a2jnm7p06p2', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.11992500'), symbol='BNB', confirmations=0, block_height=378765963, block_hash=None, date=datetime.datetime(2024, 7, 28, 2, 15, 7, 283000, tzinfo=UTC), memo='4313245781891981', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='CBD3382A1B41C47805109417586BA77F0F7AEE698A1DE23ED241739E8EE1B8F3', success=True, from_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', to_address='bnb1adfak2twduzjk4kqkqupppdtydu6kq48r6wlz7', value=Decimal('0.01955293'), symbol='BNB', confirmations=0, block_height=378765555, block_hash=None, date=datetime.datetime(2024, 7, 28, 2, 3, 34, 204000, tzinfo=UTC), memo='', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='A2DA68EC83CE5D323363F9DB56C1B6B7D30D6236C55052398366947496E6D285', success=True, from_address='bnb1fnd0k5l4p3ck2j9x9dp36chk059w977pszdgdz', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.00173698'), symbol='BNB', confirmations=0, block_height=378765491, block_hash=None, date=datetime.datetime(2024, 7, 28, 2, 1, 48, 893000, tzinfo=UTC), memo='7514238385635121', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='603D859F76A7A87A4694672021F408CE2E2CA976F1A7DAB80DBD419264AE24DD', success=True, from_address='bnb1fnd0k5l4p3ck2j9x9dp36chk059w977pszdgdz', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.02785974'), symbol='BNB', confirmations=0, block_height=378760352, block_hash=None, date=datetime.datetime(2024, 7, 27, 23, 36, 9, 594000, tzinfo=UTC), memo='3714573523788641', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='E9E32EF947F6F9F23CA8603013268562768474CA8CD61FE6A8312657E40DF718', success=True, from_address='bnb1fnd0k5l4p3ck2j9x9dp36chk059w977pszdgdz', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.17244695'), symbol='BNB', confirmations=0, block_height=378759738, block_hash=None, date=datetime.datetime(2024, 7, 27, 23, 18, 49, 767000, tzinfo=UTC), memo='7242213523741684', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='83E66132E49FA413DB0AEEB381AF2EAEFBD8A77257CB8FD06434C2A2924AD7AE', success=True, from_address='bnb1596s4vt360r53y5lgdpd6g7ldqtj9fy8sf7m9j', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.01652101'), symbol='BNB', confirmations=0, block_height=378758879, block_hash=None, date=datetime.datetime(2024, 7, 27, 22, 54, 25, 914000, tzinfo=UTC), memo='7159796537258482', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='4B52D6F70D941E22C6DF4F22082E142B490CBEC96C36BABCEEF9AE8F3D623445', success=True, from_address='bnb16gj3a52rpj8hnz5tvtesqsrud457a7aju4g749', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('7.89880000'), symbol='BNB', confirmations=0, block_height=378758426, block_hash=None, date=datetime.datetime(2024, 7, 27, 22, 41, 37, 970000, tzinfo=UTC), memo='4843148176114985', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='96E3897F6D6D74C3FA6107620109FA66B2E03773C8488E0E3AE1E7696F8E3A07', success=True, from_address='bnb16gj3a52rpj8hnz5tvtesqsrud457a7aju4g749', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('7.00000000'), symbol='BNB', confirmations=0, block_height=378758411, block_hash=None, date=datetime.datetime(2024, 7, 27, 22, 41, 14, 36000, tzinfo=UTC), memo='8132873581273229', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='09A8E106BD444ECF613502431A954781D3B472D7B9F32C6A3E16BF869F4B9DA6', success=True, from_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', to_address='bnb1596s4vt360r53y5lgdpd6g7ldqtj9fy8sf7m9j', value=Decimal('0.01714601'), symbol='BNB', confirmations=0, block_height=378758378, block_hash=None, date=datetime.datetime(2024, 7, 27, 22, 40, 17, 976000, tzinfo=UTC), memo='', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='CCAFB2A2F3D7982096EF476A1F8FDF146D8BE608B89EC9817C036633DD95748D', success=True, from_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', to_address='bnb1kr2f90ny954epjfwlx7xetrjt5cmzvhucn5a4d', value=Decimal('0.02897175'), symbol='BNB', confirmations=0, block_height=378758302, block_hash=None, date=datetime.datetime(2024, 7, 27, 22, 38, 8, 520000, tzinfo=UTC), memo='', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='5457D4748EEEF28C8115C6B9973683194B65B4EE30775FFC43ED56DEF63EAF31', success=True, from_address='bnb16gj3a52rpj8hnz5tvtesqsrud457a7aju4g749', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('7.00000000'), symbol='BNB', confirmations=0, block_height=378758295, block_hash=None, date=datetime.datetime(2024, 7, 27, 22, 37, 55, 97000, tzinfo=UTC), memo='3595991541748197', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='56E12DAB1DF28522E6DD0B48D2EDBE153B0B02AA466D50A4CC8D179BA726A33E', success=True, from_address='bnb16gj3a52rpj8hnz5tvtesqsrud457a7aju4g749', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.10000000'), symbol='BNB', confirmations=0, block_height=378758142, block_hash=None, date=datetime.datetime(2024, 7, 27, 22, 33, 34, 630000, tzinfo=UTC), memo='4115312338316924', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='203336E0F913F9ACB6B8BCA8DBCD625877B976AC5F4D15B2812E58553A684BFA', success=True, from_address='bnb16gj3a52rpj8hnz5tvtesqsrud457a7aju4g749', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('6.00000000'), symbol='BNB', confirmations=0, block_height=378758065, block_hash=None, date=datetime.datetime(2024, 7, 27, 22, 31, 23, 672000, tzinfo=UTC), memo='2263217411932216', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='52F13AC90770B661E68A76D30F9FD953817687C0521E59E1F9F4DC2502D85AC6', success=True, from_address='bnb16gj3a52rpj8hnz5tvtesqsrud457a7aju4g749', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('5.50000000'), symbol='BNB', confirmations=0, block_height=378757977, block_hash=None, date=datetime.datetime(2024, 7, 27, 22, 28, 54, 325000, tzinfo=UTC), memo='9835711516362753', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='C6B2B517122419CFDE6E8E322FBA123FA205E14EC1FB1768855788D2B53EA347', success=True, from_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', to_address='bnb165q9dz39mqh789zuuuqwkv22plut6f4nzy9jc9', value=Decimal('27.06412900'), symbol='BNB', confirmations=0, block_height=378757779, block_hash=None, date=datetime.datetime(2024, 7, 27, 22, 23, 17, 674000, tzinfo=UTC), memo='432491806', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='0B8E4D032893C16D96519DB75987B20DF0EB176AF3D64886DD0929EEE3676FE3', success=True, from_address='bnb16gj3a52rpj8hnz5tvtesqsrud457a7aju4g749', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('8.00000000'), symbol='BNB', confirmations=0, block_height=378757732, block_hash=None, date=datetime.datetime(2024, 7, 27, 22, 21, 58, 951000, tzinfo=UTC), memo='9284811951922867', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='46DD541737661FEAB1283C22FAC3B0F4BDB084109120498CEC24D2CFF548974F', success=True, from_address='bnb16gj3a52rpj8hnz5tvtesqsrud457a7aju4g749', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('8.00000000'), symbol='BNB', confirmations=0, block_height=378757699, block_hash=None, date=datetime.datetime(2024, 7, 27, 22, 21, 2, 954000, tzinfo=UTC), memo='7142288458237916', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='E4C5EFB689A10EE68AC87914BAFE68DDDE1EB06EF460F244C210AB6CB092749F', success=True, from_address='bnb16gj3a52rpj8hnz5tvtesqsrud457a7aju4g749', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('8.00000000'), symbol='BNB', confirmations=0, block_height=378757656, block_hash=None, date=datetime.datetime(2024, 7, 27, 22, 19, 49, 497000, tzinfo=UTC), memo='8714666529632565', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='083A1C753DF4384B7ECB268E81A4B2B2EF59B874BA408D76CE037307B286CC2F', success=True, from_address='bnb16gj3a52rpj8hnz5tvtesqsrud457a7aju4g749', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('5.00000000'), symbol='BNB', confirmations=0, block_height=378757592, block_hash=None, date=datetime.datetime(2024, 7, 27, 22, 17, 59, 842000, tzinfo=UTC), memo='8458616961282733', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='57E1703BBA704AE5BA1A5723CC840501F1979FCFFB57E8B0846F0C8EF015DD0A', success=True, from_address='bnb147rfvps9kasdgnqlv72cj7337qx5jcfq267wk4', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.02988348'), symbol='BNB', confirmations=0, block_height=378757523, block_hash=None, date=datetime.datetime(2024, 7, 27, 22, 16, 3, 750000, tzinfo=UTC), memo='7231532984244892', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='31F720B65B9B5EA38D726FB0D80A44B90EBB1A1901F8CFF09E1E7E9BEA8A068E', success=True, from_address='bnb16gj3a52rpj8hnz5tvtesqsrud457a7aju4g749', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('5.00000000'), symbol='BNB', confirmations=0, block_height=378756847, block_hash=None, date=datetime.datetime(2024, 7, 27, 21, 56, 57, 333000, tzinfo=UTC), memo='3323353646894969', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='F401C8C09D5B5E44E600F04EED5156F8F4623432A6C940CF3A9B13F380BAB70B', success=True, from_address='bnb16gj3a52rpj8hnz5tvtesqsrud457a7aju4g749', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('10.00000000'), symbol='BNB', confirmations=0, block_height=378756787, block_hash=None, date=datetime.datetime(2024, 7, 27, 21, 55, 13, 198000, tzinfo=UTC), memo='5691445972695919', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='49240F4D34E8ACC558ADCA3A763DD0CD555AD89F36BE3451DA673CC8D8EDE126', success=True, from_address='bnb16gj3a52rpj8hnz5tvtesqsrud457a7aju4g749', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('7.00000000'), symbol='BNB', confirmations=0, block_height=378756756, block_hash=None, date=datetime.datetime(2024, 7, 27, 21, 54, 19, 678000, tzinfo=UTC), memo='3996587426519698', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='0AB8BE193DC9AEBA1B5837CFBDE963BB688111D7E4B467E094A4140460F8CE99', success=True, from_address='bnb16gj3a52rpj8hnz5tvtesqsrud457a7aju4g749', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('5.00000000'), symbol='BNB', confirmations=0, block_height=378756479, block_hash=None, date=datetime.datetime(2024, 7, 27, 21, 46, 29, 889000, tzinfo=UTC), memo='2551585456144824', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='420FB2E8B50F5B0C03101D54563B761FA5E501A6797C9104813451E6C6E923C9', success=True, from_address='bnb16gj3a52rpj8hnz5tvtesqsrud457a7aju4g749', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('5.50000000'), symbol='BNB', confirmations=0, block_height=378756371, block_hash=None, date=datetime.datetime(2024, 7, 27, 21, 43, 25, 493000, tzinfo=UTC), memo='7959469586646797', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='81D7FBC123541ABC8E825EAC81517863F919183EDB5C76134F8B7FE017C7CFA1', success=True, from_address='bnb16gj3a52rpj8hnz5tvtesqsrud457a7aju4g749', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('5.00000000'), symbol='BNB', confirmations=0, block_height=378756338, block_hash=None, date=datetime.datetime(2024, 7, 27, 21, 42, 29, 419000, tzinfo=UTC), memo='6657447141949716', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='735E2D07C41DDBE0AC3A0067E6940F5F82B5EE8D12894EF8C941DE5627D4823C', success=True, from_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', to_address='bnb147rfvps9kasdgnqlv72cj7337qx5jcfq267wk4', value=Decimal('0.03003348'), symbol='BNB', confirmations=0, block_height=378756175, block_hash=None, date=datetime.datetime(2024, 7, 27, 21, 37, 55, 879000, tzinfo=UTC), memo='', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='BF3CA9A1D4676E3A16090C1724748A61B4140BA873CC6531B1844947DB3FD676', success=True, from_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', to_address='bnb165q9dz39mqh789zuuuqwkv22plut6f4nzy9jc9', value=Decimal('37.88731200'), symbol='BNB', confirmations=0, block_height=378756152, block_hash=None, date=datetime.datetime(2024, 7, 27, 21, 37, 17, 269000, tzinfo=UTC), memo='432491806', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='65A437D70BBD80863F532C2073A49A118AFDEAD5164297ED0CA7A23806EA14F4', success=True, from_address='bnb16gj3a52rpj8hnz5tvtesqsrud457a7aju4g749', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('5.04663575'), symbol='BNB', confirmations=0, block_height=378756104, block_hash=None, date=datetime.datetime(2024, 7, 27, 21, 35, 53, 1000, tzinfo=UTC), memo='5546124129333772', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='A5EA8059FB1D7D41A5599ABD3134C33A86C7BC47FCD34D280E8EBF34899DE98A', success=True, from_address='bnb1w6nfsadqtazkst20zsgyunvhsv9ptm6xn6dkup', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.02536622'), symbol='BNB', confirmations=0, block_height=378755117, block_hash=None, date=datetime.datetime(2024, 7, 27, 21, 7, 55, 37000, tzinfo=UTC), memo='4491769715385914', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='DF5B1F105C5E6D150439F0F5EA6123BDC23D416AA205D75AAFFD9FF77E9571E2', success=True, from_address='bnb1m5amny2gs3xdyta6pksmr43zu4727w24syyks7', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.02884022'), symbol='BNB', confirmations=0, block_height=378753966, block_hash=None, date=datetime.datetime(2024, 7, 27, 20, 35, 22, 913000, tzinfo=UTC), memo='4976598773281811', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='3FBA943232723D05CA2F9AFD4AB63200F3D8DC88C0D3522991DA5876030E04DB', success=True, from_address='bnb1j3y47w5fephrlx09k27adw6uaca0syhphpqvu9', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.04600000'), symbol='BNB', confirmations=0, block_height=378753302, block_hash=None, date=datetime.datetime(2024, 7, 27, 20, 16, 31, 890000, tzinfo=UTC), memo='4968838642239131', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='F1721F99CC6B1D907CA66BF417572B81C8629E658BD71110532504C2E400864F', success=True, from_address='bnb1n6rfzrxdw9k50nhzywhgw55j4s7qsr3qq5j9jv', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.53424758'), symbol='BNB', confirmations=0, block_height=378753104, block_hash=None, date=datetime.datetime(2024, 7, 27, 20, 10, 55, 569000, tzinfo=UTC), memo='6283755877858295', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='97029E9DE6050FC235A5023BE3B4EE01C4E1C21D4DACB968D091EF2B6238C639', success=True, from_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', to_address='bnb17xevd366kj6zwxhgmnapsuu2qyctyn37d0ay6r', value=Decimal('0.02812016'), symbol='BNB', confirmations=0, block_height=378752452, block_hash=None, date=datetime.datetime(2024, 7, 27, 19, 52, 28, 702000, tzinfo=UTC), memo='', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='E7DD5EC8E93D536D5ECB6337C236F4100D59A63BCD0BC6892AFD48E6994B760A', success=True, from_address='bnb1sveg9w8jkjez7tk7z3yxd3npz53s2pepqw9hpn', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.01369321'), symbol='BNB', confirmations=0, block_height=378752324, block_hash=None, date=datetime.datetime(2024, 7, 27, 19, 48, 54, 6000, tzinfo=UTC), memo='4311629194928867', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='8F4B82CA4CDCCA2D3E474CDAA84844832ABE379AB520768F5498237AF7FF2AB4', success=True, from_address='bnb1uh3r7v0mrq9898qpg5x9gdj9lpalrw6thgfyev', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.03193973'), symbol='BNB', confirmations=0, block_height=378751719, block_hash=None, date=datetime.datetime(2024, 7, 27, 19, 31, 46, 94000, tzinfo=UTC), memo='1181538934611895', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='5554B7C8988B33829932E84F989B505C5B400C8566666FCFC2DF47F1A361C5A9', success=True, from_address='bnb1drcvgps5stpua88x88jzgce6v7yad77nlvt48h', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.02100000'), symbol='BNB', confirmations=0, block_height=378750866, block_hash=None, date=datetime.datetime(2024, 7, 27, 19, 7, 34, 871000, tzinfo=UTC), memo='1469162138539396', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='A7013F36862ED990553E68F250E4B8D73B25F38FAAA1A1D9B5775E99FF2BC8DB', success=True, from_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', to_address='bnb1drcvgps5stpua88x88jzgce6v7yad77nlvt48h', value=Decimal('0.03406211'), symbol='BNB', confirmations=0, block_height=378750416, block_hash=None, date=datetime.datetime(2024, 7, 27, 18, 54, 49, 769000, tzinfo=UTC), memo='', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='02CC1F97DE8586C0CE1B4B4ED85364DBA43688E21EEA4F65E6E54983A2210C8D', success=True, from_address='bnb1negwwepq32ygfvtar8j6ykmc6aea8x4550wpke', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('1.87428505'), symbol='BNB', confirmations=0, block_height=378749754, block_hash=None, date=datetime.datetime(2024, 7, 27, 18, 36, 5, 939000, tzinfo=UTC), memo='1394662578394591', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='964D7F43A5595F4C86C40BE59B464B0370AA6ED350AE2CAC74F3A07C6DE584FE', success=True, from_address='bnb1ervh8nkpfm67xu7mhs4mlqhfe8auyn96wcuw2s', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.02371542'), symbol='BNB', confirmations=0, block_height=378749742, block_hash=None, date=datetime.datetime(2024, 7, 27, 18, 35, 45, 928000, tzinfo=UTC), memo='9771494579942733', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='76B03CC99C139BA47228928F530E171038BE6A62596AA6D803D8FEEAB06F1358', success=True, from_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', to_address='bnb1j3y47w5fephrlx09k27adw6uaca0syhphpqvu9', value=Decimal('0.08092207'), symbol='BNB', confirmations=0, block_height=378748750, block_hash=None, date=datetime.datetime(2024, 7, 27, 18, 7, 41, 144000, tzinfo=UTC), memo='', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='90B08DBB8862F4099D52377E5E6E4DC2DD99E722785AB0E97B8E93F49F277969', success=True, from_address='bnb1d7phje96m3takzccfekr5chcn59an3k7wygaxu', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.01867500'), symbol='BNB', confirmations=0, block_height=378748698, block_hash=None, date=datetime.datetime(2024, 7, 27, 18, 6, 11, 668000, tzinfo=UTC), memo='4267173749241134', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='5E20FA5DC4A3572EB80D4505E10EABE2F6A1FABBE9D7641DF67C6ECD640BEEC8', success=True, from_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', to_address='bnb1j3y47w5fephrlx09k27adw6uaca0syhphpqvu9', value=Decimal('0.01310015'), symbol='BNB', confirmations=0, block_height=378748474, block_hash=None, date=datetime.datetime(2024, 7, 27, 17, 59, 52, 710000, tzinfo=UTC), memo='', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='C9D957F0D232AFC371914FD6CCB2AF7FB9FB88F91D3398F706115581E6506895', success=True, from_address='bnb1xrfwzlu9c5208lhtn7ywt0mjrhjh4nt4fjyqxy', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.01405500'), symbol='BNB', confirmations=0, block_height=378746729, block_hash=None, date=datetime.datetime(2024, 7, 27, 17, 10, 25, 170000, tzinfo=UTC), memo='6894177251314446', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='8BF2A61E7FAB6770256091CEE7AF9A366BFABC27067E59971BAB595A329FFE50', success=True, from_address='bnb1fpayyw8lw2l3apxlsy7ge9ghh362dhu6ghgfyj', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.03050484'), symbol='BNB', confirmations=0, block_height=378746439, block_hash=None, date=datetime.datetime(2024, 7, 27, 17, 2, 13, 885000, tzinfo=UTC), memo='5248733942875457', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='4A73395914676195717B1D2EEF69BD65987676C423DF9479BD69362B458E4722', success=True, from_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', to_address='bnb1sveg9w8jkjez7tk7z3yxd3npz53s2pepqw9hpn', value=Decimal('0.01791821'), symbol='BNB', confirmations=0, block_height=378745449, block_hash=None, date=datetime.datetime(2024, 7, 27, 16, 34, 11, 719000, tzinfo=UTC), memo='', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='27BEA2745BDC9216C5E1CC4601427715CDE7EB887B93FD633F8F758532F89772', success=True, from_address='bnb1fgvwqh2v7h96mnjhny4dmna5qpg0nu6vf845lz', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.23867400'), symbol='BNB', confirmations=0, block_height=378745371, block_hash=None, date=datetime.datetime(2024, 7, 27, 16, 31, 55, 165000, tzinfo=UTC), memo='9454396282775739', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='B30757DA84741EDBF4FEC44548263877F2FE1D8FCC9E6754C383DEE973F13380', success=True, from_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', to_address='bnb1dzennvrgmvzx76jp764eaqw4cw06vmvc3ex2ez', value=Decimal('0.01874191'), symbol='BNB', confirmations=0, block_height=378744659, block_hash=None, date=datetime.datetime(2024, 7, 27, 16, 11, 47, 676000, tzinfo=UTC), memo='', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='C91B7633FA2F831899E5ED045CD6379774D8A538A10A726CE529D924FCD77D39', success=True, from_address='bnb1m7fl5hqhg0mklfwtyge742svva3g836cze9h3f', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.20892894'), symbol='BNB', confirmations=0, block_height=378744587, block_hash=None, date=datetime.datetime(2024, 7, 27, 16, 9, 43, 204000, tzinfo=UTC), memo='6835437955641997', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='655A09ADAEDEA03C7DE1276F27B327E734E9A91324273BE51DC5AFC8E0866182', success=True, from_address='bnb1w5v9avmk2pa0m76en7xszap6kpjuh0tjckvpaa', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.02883967'), symbol='BNB', confirmations=0, block_height=378744251, block_hash=None, date=datetime.datetime(2024, 7, 27, 16, 0, 14, 149000, tzinfo=UTC), memo='9727667511967422', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='BFC6996A5195D5043F75CFA289005A1AB2FA513C883C4BF022F57F291C177674', success=True, from_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', to_address='bnb1w5v9avmk2pa0m76en7xszap6kpjuh0tjckvpaa', value=Decimal('0.02898967'), symbol='BNB', confirmations=0, block_height=378743300, block_hash=None, date=datetime.datetime(2024, 7, 27, 15, 33, 14, 434000, tzinfo=UTC), memo='', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='C2AE8D0E619264B133F9307A55A8E1C73E3B5405E43C394F7387A3CECA29A5CB', success=True, from_address='bnb1m5amny2gs3xdyta6pksmr43zu4727w24syyks7', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.01568103'), symbol='BNB', confirmations=0, block_height=378743284, block_hash=None, date=datetime.datetime(2024, 7, 27, 15, 32, 49, 191000, tzinfo=UTC), memo='9146314118744161', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='C45879E776CEF4BFA73CDEEC3BC80F5335F52135797FDDAB25CC08E3FB065F32', success=True, from_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', to_address='bnb1n6rfzrxdw9k50nhzywhgw55j4s7qsr3qq5j9jv', value=Decimal('0.53487258'), symbol='BNB', confirmations=0, block_height=378742766, block_hash=None, date=datetime.datetime(2024, 7, 27, 15, 18, 8, 495000, tzinfo=UTC), memo='', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='3695A2DEA1D56139D857A734C6500CEF0D98A1456A10E8B75A6B08706EFDA48B', success=True, from_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', to_address='bnb1avhj030fl69k82zvhjxxwa4u277wa5zrp0kr44', value=Decimal('0.07217657'), symbol='BNB', confirmations=0, block_height=378741784, block_hash=None, date=datetime.datetime(2024, 7, 27, 14, 50, 16, 310000, tzinfo=UTC), memo='', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='0BB0EFDAB551A888D5B040430B00A9BA3678545114448E56D7DF5752E02BDEB4', success=True, from_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', to_address='bnb1fpayyw8lw2l3apxlsy7ge9ghh362dhu6ghgfyj', value=Decimal('0.03057984'), symbol='BNB', confirmations=0, block_height=378740423, block_hash=None, date=datetime.datetime(2024, 7, 27, 14, 11, 45, 534000, tzinfo=UTC), memo='', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='7C52EFF6C24B134B4CEEC5140F16FE87BF1FEDE430FCBDE756A022C6E75AA3F9', success=True, from_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', to_address='bnb1un6rzq36mle8zx99sadwukc874zy3ncdv76atr', value=Decimal('0.01345795'), symbol='BNB', confirmations=0, block_height=378739724, block_hash=None, date=datetime.datetime(2024, 7, 27, 13, 51, 51, 989000, tzinfo=UTC), memo='', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='D857B85F40E5DD600D4A264A7307037ED82BD1D0170354DA95D821BA2AAE946A', success=True, from_address='bnb1xrfwzlu9c5208lhtn7ywt0mjrhjh4nt4fjyqxy', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.56227100'), symbol='BNB', confirmations=0, block_height=378738408, block_hash=None, date=datetime.datetime(2024, 7, 27, 13, 14, 8, 312000, tzinfo=UTC), memo='6595976663465736', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='6C8E86888B09DEDF6B06DFC4C1C65B6BCE1BDCE112035BCED853BA83037AD92C', success=True, from_address='bnb10gy4t3myu39qx7fxc0xp35mk5lu77ul9lwht0m', to_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', value=Decimal('0.04841503'), symbol='BNB', confirmations=0, block_height=378738384, block_hash=None, date=datetime.datetime(2024, 7, 27, 13, 13, 27, 950000, tzinfo=UTC), memo='9187296267823131', tx_fee=Decimal('0.00007500'), token=None, index=None), TransferTx(tx_hash='0F4A881384B96BCD86CE257ED39FC7F497E3DD816CF66FED21273F1159747731', success=True, from_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', to_address='bnb10gy4t3myu39qx7fxc0xp35mk5lu77ul9lwht0m', value=Decimal('0.04904003'), symbol='BNB', confirmations=0, block_height=378738298, block_hash=None, date=datetime.datetime(2024, 7, 27, 13, 10, 59, 233000, tzinfo=UTC), memo='', tx_fee=Decimal('0.00007500'), token=None, index=None)]]
        for expected_address_txs, address_txs in zip(expected_addresses_txs, addresses_txs):
            assert expected_address_txs == address_txs

    def test_get_tx_details(self):
        BnbExplorerInterface.tx_details_apis[0] = self.api
        tx_details_mock_responses = [
            {'code': 0, 'hash': '4B2C00CCDDF0DD13A75C288CCB706A06EAA6743A45ED2B3DA2A9BD852CB08D0C',
             'height': '346920885',
             'log': 'Msg 0: ', 'ok': True,
             'tx': {'type': 'auth/StdTx',
                    'value': {
                        'data': None, 'memo': '',
                        'msg': [
                            {'type': 'cosmos-sdk/Send',
                             'value': {'inputs': [{
                                 'address': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn',
                                 'coins': [
                                     {
                                         'amount': '88960363',
                                         'denom': 'BNB'}]}],
                                 'outputs': [{
                                     'address': 'bnb159l73gp5a0685m3cnha320uxlwzpq0dk553np9',
                                     'coins': [
                                         {
                                             'amount': '88960363',
                                             'denom': 'BNB'}]}]}}],
                        'signatures': [
                            {'account_number': '6839768',
                             'pub_key': {
                                 'type': 'tendermint/PubKeySecp256k1',
                                 'value': 'A6Spio9Knf5VjX37g2kc9PHqf+iesS8tL5xFleuzKD92'},
                             'sequence': '54495',
                             'signature': 'lOUiDrlxUO6i15+7b4ZuwVApHPbkxvKlOYsaQVIVVOoqXc1y8AG/xUXKrZsnscaIw2p3kpdWBWk4R4hCHhtxtA=='}],
                        'source': '1'}}},
            {'code': 0, 'hash': '402646BA0BC060586EA5B638BCE96D7D3C7BCCC9F86581D293DEE24C377C3964',
             'height': '346920978', 'log': 'Msg 0: ', 'ok': True,
             'tx': {'type': 'auth/StdTx',
                    'value': {
                        'data': None, 'memo': '',
                        'msg': [
                            {'type': 'cosmos-sdk/Send', 'value': {
                                'inputs': [{
                                    'address': 'bnb13q87ekxvvte78t2q7z05lzfethnlht5agfh4ur',
                                    'coins': [{
                                        'amount': '4538682000000',
                                        'denom': 'CAS-167'}]}],
                                'outputs': [{
                                    'address': 'bnb1humvl4yawfg9rgrclgkczey9x3pty6nnzgza8j',
                                    'coins': [{
                                        'amount': '4538682000000',
                                        'denom': 'CAS-167'}]}]}}],
                        'signatures': [
                            {'account_number': '753531',
                             'pub_key': {
                                 'type': 'tendermint/PubKeySecp256k1',
                                 'value': 'A3h83Xb8Kl6G+JBvQQyKgldB3x/aXxY7EMGpwPdLY0Aa'},
                             'sequence': '40417',
                             'signature': 'UDzQ/gXNzeQLZkU1txvl1g/v0fdcLprVN+ARJO3vI1cRS4u3WRQWnfQek62cSohR5VdFY68pDydwqiCfn9IJsQ=='}],
                        'source': '1'}}},
            {'code': 0, 'hash': '412F173ABED751F6AC9B1B772D610D7036CA14D95452F0D8FE68697C2157F6A1',
             'height': '346921823', 'log': 'Msg 0: ', 'ok': True,
             'tx': {'type': 'auth/StdTx',
                    'value':
                        {'data': None, 'memo': '',
                         'msg': [
                             {'type': 'tokens/FreezeMsg',
                              'value': {'amount': '630248483585',
                                        'from': 'bnb15ar96n84dsjvg4rkxzyeag2mhmju9m0f944r9p',
                                        'symbol': 'NOW-E68'}}],
                         'signatures': [
                             {'account_number': '7664846',
                              'pub_key': {
                                  'type': 'tendermint/PubKeySecp256k1',
                                  'value': 'A0pY0qlk7qC60e8f3xhTTjhlUeM4EffArG8tbbiWUiyD'},
                              'sequence': '2',
                              'signature': 'sSW9D7SlJI9g/d/g9Ubs2bdEpp0kMqr9hRSecqgXfE4Klub835UrfhfWYmToR3Jb0GGDigX3/xAFBEt2g+fh9w=='}],
                         'source': '0'}}},
            {'code': 0, 'hash': 'AA8CD4363BA72753BF935AFF0602E88CB2768829C5BA7B0016625A23BA965C2C',
             'height': '269616240', 'log': 'Msg 0: ', 'ok': True,
             'tx': {'type': 'auth/StdTx',
                    'value':
                        {'data': None, 'memo': '',
                         'msg': [
                             {'type': 'dex/CancelOrder', 'value': {
                                 'refid': 'FB0AE07A39BC0999DB8CC1E01DFEF2A99C2ADBBD-1059',
                                 'sender': 'bnb1lv9wq73ehsyenkuvc8spmlhj4xwz4kaajea7dy',
                                 'symbol': 'ATP-38C_BNB'}}],
                         'signatures': [
                             {'account_number': '7152934',
                              'pub_key': {
                                  'type': 'tendermint/PubKeySecp256k1',
                                  'value': 'A4gT8gBVzHS6Y8T9Ez9SEWOgJHOiKtc7+QymIdwD3Hvh'},
                              'sequence': '1065',
                              'signature': 'Wcm+4jpkELSXBe4kAEe9X9P+2G8YZUsUq7vGvkrIwOs61LeWrcOKl21qydw71U9tTgsO3wPaXWd7NKxY7bnlCA=='}],
                         'source': '2'}}},
            {'code': 0, 'hash': '7B289DEBB530D1F1153B659AAAC6EE3DCFB7370727E108DAB396A02416564B22',
             'height': '263999994', 'log': 'Msg 0: ', 'ok': True,
             'tx': {'type': 'auth/StdTx',
                    'value': {
                        'data': None, 'memo': '',
                        'msg': [
                            {'type': 'dex/NewOrder', 'value': {
                                'id': '83C57CAA0A204ABC53E406EF54DF385456276A84-4668029',
                                'ordertype': 2, 'price': '499999',
                                'quantity': '1000000000000',
                                'sender': 'bnb1s0zhe2s2yp9tc5lyqmh4fhec23tzw65yclspxu',
                                'side': 2, 'symbol': 'DOS-120_BNB',
                                'timeinforce': 1}}], 'signatures': [
                            {'account_number': '336041', 'pub_key': {
                                'type': 'tendermint/PubKeySecp256k1',
                                'value': 'A8mXNAYgZ7PSxNdoW72aamg++Oh07P8L9Eo1Pqmr+3KO'},
                             'sequence': '4668028',
                             'signature': 'TWiq2JU+ns7fpNTpxyzAtWILE7aEGC2ijX3dB529PwUwy+CmyPZe1Fv3Vnu+sgYM2Q12HW2jzP3TNPVNuuNQlw=='}],
                        'source': '0'}}},
            {'code': 0, 'hash': 'F756A40911AC12732A8B2463F57FDC0E49B689D76BF7C53BA8B7A5CC8E5307F4',
             'height': '345543307', 'log': 'Msg 0: ', 'ok': True,
             'tx': {'type': 'auth/StdTx',
                    'value': {
                        'data': None, 'memo': '',
                        'msg': [
                            {'type': 'tokens/BurnMsg',
                             'value': {'amount': '213886829000000',
                                       'from': 'bnb127a2uwn6cpe6nvaza6py3dxjrede5794skw00u',
                                       'symbol': 'BNB'}}],
                        'signatures': [
                            {'account_number': '66355',
                             'pub_key': {
                                 'type': 'tendermint/PubKeySecp256k1',
                                 'value': 'Ap3ftVDCom4uQ4RCc5xx9r1gzeTa+TLBNHUu8N2/NhgG'},
                             'sequence': '12',
                             'signature': 'QTsFrIuGZRJrf/Bi2VsoZQ9yf5//BQS8Tvp9QOO94SYaj2IpxholqQXPHzQ+fcZ0cGkC5L0FTbpSaD7eCI1uUg=='}],
                        'source': '1'}}}

        ]
        self.api.request = Mock(side_effect=tx_details_mock_responses)
        txs_details = []
        for tx_hash in self.hash_of_transactions:
            api_response = self.api.get_tx_details(tx_hash)
            parsed_response = self.api.parser.parse_tx_details_response(api_response, None)
            txs_details.append(parsed_response)
        expected_expected_txs_details = [
            [
                TransferTx(tx_hash='4B2C00CCDDF0DD13A75C288CCB706A06EAA6743A45ED2B3DA2A9BD852CB08D0C', success=True,
                           from_address='bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn', to_address='bnb159l73gp5a0685m3cnha320uxlwzpq0dk553np9',
                           value=Decimal('0.88960363'), symbol='BNB', confirmations=0, block_height=346920885,
                           block_hash=None, date=None, memo='', tx_fee=None, token=None, index=None)
            ],
            [],
            [],
            [],
            [],
            [],
        ]
        for expected_tx_details, tx_details in zip(expected_expected_txs_details, txs_details):
            assert expected_tx_details == tx_details

    def test_get_balance(self):
        BnbExplorerInterface.balance_apis[0] = self.api
        balance_mock_responses = [
            {'account_number': 6839768, 'address': 'bnb1d4u8amvqx3rm6022gnuhp7nq0tuj7fm4yt4azn',
             'balances': [{'free': '62.53054124', 'frozen': '0.00000000', 'locked': '0.00000000', 'symbol': 'BUSD-BD1'},
                          {'free': '464.25000000', 'frozen': '0.00000000', 'locked': '0.00000000',
                           'symbol': 'DOGE-B67'},
                          {'free': '0.19287516', 'frozen': '0.00000000', 'locked': '0.00000000', 'symbol': 'ETH-1C9'},
                          {'free': '239.48300000', 'frozen': '0.00000000', 'locked': '0.00000000', 'symbol': 'FTM-A64'},
                          {'free': '208.00000000', 'frozen': '0.00000000', 'locked': '0.00000000', 'symbol': 'ADA-9F4'},
                          {'free': '10628.74810911', 'frozen': '0.00000000', 'locked': '0.00000000',
                           'symbol': 'AWC-986'},
                          {'free': '30.57656186', 'frozen': '0.00000000', 'locked': '0.00000000', 'symbol': 'BNB'},
                          {'free': '0.00737848', 'frozen': '0.00000000', 'locked': '0.00000000', 'symbol': 'BTCB-1DE'},
                          {'free': '361.22652100', 'frozen': '0.00000000', 'locked': '0.00000000',
                           'symbol': 'USDT-6D8'},
                          {'free': '10.48000000', 'frozen': '0.00000000', 'locked': '0.00000000',
                           'symbol': 'MATIC-84A'},
                          {'free': '9.00000000', 'frozen': '0.00000000', 'locked': '0.00000000', 'symbol': 'NEXO-A84'},
                          {'free': '289.00000000', 'frozen': '0.00000000', 'locked': '0.00000000',
                           'symbol': 'NOW-E68'}], 'flags': 1,
             'public_key': [3, 164, 169, 138, 143, 74, 157, 254, 85, 141, 125, 251, 131, 105, 28, 244, 241, 234, 127,
                            232, 158, 177, 47, 45, 47, 156, 69, 149, 235, 179, 40, 63, 118], 'sequence': 65828}
        ]
        self.api.request = Mock(side_effect=balance_mock_responses)
        balances = []

        for address in self.addresses_of_accounts:
            api_response = self.api.get_address_txs(address)
            parsed_response = self.api.parser.parse_balance_response(api_response)
            balances.append(parsed_response)

        expected_balances = [Decimal('30.576561860000000000')]
        for balance, expected_balance in zip(balances, expected_balances):
            assert balance == expected_balance

    def test_get_block_head(self):
        BnbExplorerInterface.block_head_apis[0] = self.api
        block_head_mock_responses = [{'node_info': {'protocol_version': {'p2p': 7, 'block': 10, 'app': 0},
                                                  'id': 'f52252fcda9c161c0089d971c9f1b941a26023ef',
                                                  'listen_addr': '10.211.33.206:27146',
                                                  'network': 'Binance-Chain-Tigris', 'version': '0.32.3',
                                                  'channels': '3640202122233038', 'moniker': 'Everest',
                                                  'other': {'tx_index': 'on', 'rpc_address': 'tcp://0.0.0.0:27147'}},
                                    'sync_info': {
                                        'latest_block_hash': '9EB58AB25115E6CF448FFC2C5C3F8CE8DE98AA45C32FDDD8A6392B57C9EE5C71',
                                        'latest_app_hash': 'DD7948536A8C66C7FD51E935EC0326797691B224836710925248889E20DAFC92',
                                        'latest_block_height': 378943193,
                                        'latest_block_time': '2024-07-31T14:00:36.053240121Z', 'catching_up': False},
                                    'validator_info': {'address': 'B0FBB52FF7EE93CC476DFE6B74FA1FC88584F30D',
                                                       'pub_key': [12, 145, 14, 47, 230, 80, 228, 224, 20, 6, 179, 49,
                                                                   11, 72, 159, 182, 10, 132, 188, 63, 245, 197, 190,
                                                                   227, 165, 109, 88, 152, 182, 168, 175, 50],
                                                       'voting_power': 1000000000000}}]
        self.api.request = Mock(side_effect=block_head_mock_responses)
        api_response = self.api.get_block_head()
        parsed_response = self.api.parser.parse_block_head_response(api_response)
        expected_block_head = 378943193
        assert parsed_response == expected_block_head
