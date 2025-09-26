import datetime
from decimal import Decimal
from unittest import TestCase

import pytest
from pytz import UTC

from exchange.base.models import Currencies
from exchange.blockchain.api.ltc.ltc_explorer_interface import LTCExplorerInterface
from exchange.blockchain.api.ltc.ltc_space import LiteCoinSpaceApi
from exchange.blockchain.apis_conf import APIS_CONF
from exchange.blockchain.tests.api.general_test.general_test_from_explorer import TestFromExplorer


@pytest.mark.slow
class TestLTCSpaceFlowApiCalls(TestCase):
    api = LiteCoinSpaceApi
    txs_hash = [
        'a9e13035052225a65ed7d9fd400d65a57e471d1d1fbf7121207f803e4e9681ef',
        '83b41ceb8e79209bec1c82aa0ae8c9a83db87e6e199f764a167b6ee5e01a3026',
        '29c38cc2b50b6da5d42f2af92325ea1295fce613b3bd10f6c8205d35f16a9f2d'
    ]

    @classmethod
    def check_general_response(cls, response, keys) -> bool:
        if set(response.keys()).issubset(keys):
            return True
        return False

    def test_get_tx_details_api(self):
        tx_details_keys = {'txid', 'version', 'locktime', 'vin', 'vout', 'size', 'weight', 'fee', 'status'}
        status_keys = {'confirmed', 'block_height', 'block_hash', 'block_time'}
        vin_keys = {'txid', 'vout', 'prevout', 'scriptsig', 'scriptsig_asm', 'is_coinbase', 'sequence',
                    'inner_redeemscript_asm', 'witness'}
        vout_keys = {'scriptpubkey', 'scriptpubkey_asm', 'scriptpubkey_type', 'scriptpubkey_address', 'value'}
        for tx_hash in self.txs_hash:
            get_tx_details_response = self.api.get_tx_details(tx_hash)
            assert isinstance(get_tx_details_response, dict)
            assert self.check_general_response(get_tx_details_response, tx_details_keys)
            assert get_tx_details_response.get('status')
            assert isinstance(get_tx_details_response.get('status'), dict)
            assert self.check_general_response(get_tx_details_response.get('status'), status_keys)
            assert get_tx_details_response.get('vin')
            assert isinstance(get_tx_details_response.get('vin'), list)
            for vin in get_tx_details_response.get('vin'):
                assert isinstance(vin, dict)
                assert self.check_general_response(vin, vin_keys)
            assert get_tx_details_response.get('vout')
            assert isinstance(get_tx_details_response.get('vout'), list)
            for vout in get_tx_details_response.get('vout'):
                assert isinstance(vout, dict)
                assert self.check_general_response(vout, vout_keys)


class TestLTCSpaceFromExplorer(TestFromExplorer):
    api = LiteCoinSpaceApi
    symbol = 'LTC'
    explorerInterface = LTCExplorerInterface  # noqa: N815
    currencies = Currencies.ltc

    txs_hash = [
        'a9e13035052225a65ed7d9fd400d65a57e471d1d1fbf7121207f803e4e9681ef',
        '83b41ceb8e79209bec1c82aa0ae8c9a83db87e6e199f764a167b6ee5e01a3026',
        '29c38cc2b50b6da5d42f2af92325ea1295fce613b3bd10f6c8205d35f16a9f2d'
    ]

    @classmethod
    def test_get_tx_details(cls) -> None:
        tx_details_mock_responses = [
            2707118,
            {'txid': 'a9e13035052225a65ed7d9fd400d65a57e471d1d1fbf7121207f803e4e9681ef', 'version': 1, 'locktime': 0,
             'vin': [{'txid': '51d543dd3cbed2d50f707794e52a6bc209771457dff557300cd50eec997a23b2', 'vout': 2,
                      'prevout': {'scriptpubkey': '76a914b96758481720ca64e02538df543b75880dabc44b88ac',
                                  'scriptpubkey_asm': 'OP_DUP OP_HASH160 OP_PUSHBYTES_20 b96758481720ca64e02538df5'
                                                      '43b75880dabc44b OP_EQUALVERIFY OP_CHECKSIG',
                                  'scriptpubkey_type': 'p2pkh',
                                  'scriptpubkey_address': 'Lc8H5EAFBKbGmnJGRNGkLVpLY9XXaeiujw', 'value': 60011160078},
                      'scriptsig': '4730440220185f082c0b3b38a8b34454228fe289e7b4b1e1a86357c532605d9af096a46d5b022'
                                   '0064717fa8717f7f55b0569a61154108733f6dc5f1975731fe1f8975e87ea2ff50121039703bb'
                                   '51ec58e29d3daf13f227a531cfce0768a0a6fe28e2b15ed206592a9f40',
                      'scriptsig_asm': 'OP_PUSHBYTES_71 30440220185f082c0b3b38a8b34454228fe289e7b4b1e1a86357c532'
                                       '605d9af096a46d5b0220064717fa8717f7f55b0569a61154108733f6dc5f1975731fe1f89'
                                       '75e87ea2ff501 OP_PUSHBYTES_33 039703bb51ec58e29d3daf13f227a531cfce0768a0a6f'
                                       'e28e2b15ed206592a9f40',
                      'is_coinbase': False, 'sequence': 4294967295}], 'vout': [
                {'scriptpubkey': 'a9147cfd7e9a8fa7894e2e0fa04253a6dd96f7de053287',
                 'scriptpubkey_asm': 'OP_HASH160 OP_PUSHBYTES_20 7cfd7e9a8fa7894e2e0fa04253a6dd96f7de0532 OP_EQUAL',
                 'scriptpubkey_type': 'p2sh', 'scriptpubkey_address': 'MKJ3hKvF75dA47PyFceqK8P1jpsFqJzLYJ',
                 'value': 1390822}, {
                    'scriptpubkey': '001411cb684376102fa1542a4bd3474e5e4edb233fa7',
                    'scriptpubkey_asm': 'OP_0 OP_PUSHBYTES_20 11cb684376102fa1542a4bd3474e5e4edb233fa7',
                    'scriptpubkey_type': 'v0_p2wpkh',
                    'scriptpubkey_address': 'ltc1qz89kssmkzqh6z4p2f0f5wnj7fmdjx0a8sxxvju',
                    'value': 2941137,
                },
                {'scriptpubkey': '76a914b96758481720ca64e02538df543b75880dabc44b88ac',
                 'scriptpubkey_asm': 'OP_DUP OP_HASH160 OP_PUSHBYTES_20 b96758481720ca64e02538df543b75880dabc44b '
                                     'OP_EQUALVERIFY OP_CHECKSIG',
                 'scriptpubkey_type': 'p2pkh', 'scriptpubkey_address': 'Lc8H5EAFBKbGmnJGRNGkLVpLY9XXaeiujw',
                 'value': 60006824419}], 'size': 254, 'weight': 1016, 'fee': 3700,
             'status': {'confirmed': True, 'block_height': 2707106,
                        'block_hash': '9ceb7e83248bccd734693bc7c60ce4fe98c3f12db7df479f8be45b66abab1ed6',
                        'block_time': 1719010699}},
            2707118, {'txid': '83b41ceb8e79209bec1c82aa0ae8c9a83db87e6e199f764a167b6ee5e01a3026', 'version': 2,
                      'locktime': 2707103, 'vin': [
                    {'txid': 'f7237d8780614297b617b528a7b857a22df3a295558b4e7ec8246d5bef1b6291', 'vout': 33,
                     'prevout': {'scriptpubkey': 'a914c443e60fdb7090820bfbd9934254468656f842cd87',
                                 'scriptpubkey_asm': 'OP_HASH160 OP_PUSHBYTES_20 c443e60fdb7090820bfbd993425446865'
                                                     '6f842cd OP_EQUAL',
                                 'scriptpubkey_type': 'p2sh',
                                 'scriptpubkey_address': 'MRnv1iF722SUsrFZxmZSg1Ey7Vhghy8Gz6', 'value': 4944048},
                     'scriptsig': '160014fb2fcd12d1c3de40c08a75fd76558b0c9ac44477',
                     'scriptsig_asm': 'OP_PUSHBYTES_22 0014fb2fcd12d1c3de40c08a75fd76558b0c9ac44477', 'witness': [
                        '304402207af29700bd6bb8d9d328bafb2f4d451e2686c067b598eb85f458fde9d61940350220347ce41945d4e3'
                        '0f53ee233f01795ad4d0a134ab492e066f35af8f4be4b0918201',
                        '03f1c6c2b807a31442acdec4e0df6aba28dc05b35869de1b10d8ffd19a4e2a89a6'], 'is_coinbase': False,
                     'sequence': 4294967294,
                     'inner_redeemscript_asm': 'OP_0 OP_PUSHBYTES_20 fb2fcd12d1c3de40c08a75fd76558b0c9ac44477'},
                    {'txid': 'fbb2cdfa0e624bf1ab81213953837b5dadc170f9f0af5c3142b782a0ba2bb8e8', 'vout': 11,
                     'prevout': {'scriptpubkey': 'a914c0692e46f1320af7d0ccb205961c6e5a1a674d2287',
                                 'scriptpubkey_asm': 'OP_HASH160 OP_PUSHBYTES_20 c0692e46f1320af7d0ccb205961c6e5a1a6'
                                                     '74d22 OP_EQUAL',
                                 'scriptpubkey_type': 'p2sh',
                                 'scriptpubkey_address': 'MRSXyMETyqz1zrAvNjhHNsspDz1vGjZv6f', 'value': 59312},
                     'scriptsig': '16001462ac308d033d417c9a4965655d89eca455fcb453',
                     'scriptsig_asm': 'OP_PUSHBYTES_22 001462ac308d033d417c9a4965655d89eca455fcb453', 'witness': [
                        '304402205d3dfd36e1fae82cafead7f0559e5e84080f4a30a95902cc781c53b033dc5e9d02202e5eeb66eba255c'
                        '64a937346c53b13b5410a5ec8c4309b48dfbf0f9eed5575b301',
                        '03c8c1d9e47af6ca0d4d1719ece768ac33c2778537cac7ca99b7d28fa571249c21'], 'is_coinbase': False,
                     'sequence': 4294967294,
                     'inner_redeemscript_asm': 'OP_0 OP_PUSHBYTES_20 62ac308d033d417c9a4965655d89eca455fcb453'}],
                      'vout': [{'scriptpubkey': '76a914b5050584153d964c70bb658d613638a65879c44888ac',
                                'scriptpubkey_asm': 'OP_DUP OP_HASH160 OP_PUSHBYTES_20 b5050584153d964c70bb658d613638'
                                                    'a65879c448 OP_EQUALVERIFY OP_CHECKSIG',
                                'scriptpubkey_type': 'p2pkh',
                                'scriptpubkey_address': 'Lbj6aqXbjagnyJhvbtArC5ozQhksmdL5mV', 'value': 5000000}],
                      'size': 388, 'weight': 904, 'fee': 3360, 'status': {
                    'confirmed': True, 'block_height': 2707106,
                    'block_hash': '9ceb7e83248bccd734693bc7c60ce4fe98c3f12db7df479f8be45b66abab1ed6',
                    'block_time': 1719010699}},
            2707118,
            {'txid': '29c38cc2b50b6da5d42f2af92325ea1295fce613b3bd10f6c8205d35f16a9f2d', 'version': 2, 'locktime': 0,
             'vin': [{'txid': '293ff1a0eb6557b60d4f7276a8c734e80d1555193c405dba319f7cfb641420f3', 'vout': 1,
                      'prevout': {'scriptpubkey': '0014fd829e597fef822e962656a6363cc9185f6f590d',
                                  'scriptpubkey_asm': 'OP_0 OP_PUSHBYTES_20 fd829e597fef822e962656a6363cc9185f6f590d',
                                  'scriptpubkey_type': 'v0_p2wpkh',
                                  'scriptpubkey_address': 'ltc1qlkpfuktla7pza93x26nrv0xfrp0k7kgdy35qaa',
                                  'value': 2285974}, 'scriptsig': '', 'scriptsig_asm': '', 'witness': [
                     '304402200c3d17340b7a226045bbd25a2ff731d495ac0809b905b724a2ed2c03452f9534022013db8413'
                     '5a72dfb9363ebb23033abdc0b6fd31a4740d847dab0581890ad0a34401',
                     '02cf2a44f4640a340ccf562703a1f696195ea5cdac14ff440fd7cf69d94e3e07d6'], 'is_coinbase': False,
                      'sequence': 4294967293},
                     {'txid': '69081fca1141f6fd0df227fe3bc6795b0c895c159fb178e4306e6f5d740bfd49', 'vout': 1,
                      'prevout': {'scriptpubkey': '0014fd829e597fef822e962656a6363cc9185f6f590d',
                                  'scriptpubkey_asm': 'OP_0 OP_PUSHBYTES_20 fd829e597fef822e962656a6363cc9185f6f590d',
                                  'scriptpubkey_type': 'v0_p2wpkh',
                                  'scriptpubkey_address': 'ltc1qlkpfuktla7pza93x26nrv0xfrp0k7kgdy35qaa',
                                  'value': 221553216}, 'scriptsig': '', 'scriptsig_asm': '', 'witness': [
                         '30440220012b438a7ec21d8ec9b18229aab9c797082e9184cc477bda64e4914f7fd6dc10'
                         '02207cbea1666c315b818ca67f0a6cf68b5e3aaef1de9fd2c818ee027d6d5e0a2f6201',
                         '02cf2a44f4640a340ccf562703a1f696195ea5cdac14ff440fd7cf69d94e3e07d6'], 'is_coinbase': False,
                      'sequence': 4294967293}], 'vout': [
                {
                    'scriptpubkey': '76a9148eed6fed35c29149c4bc42d236eb5dc44cde468788ac',
                    'scriptpubkey_asm': 'OP_DUP OP_HASH160 OP_PUSHBYTES_20 '
                                        '8eed6fed35c29149c4bc42d236eb5dc44cde4687 OP_EQUALVERIFY OP_CHECKSIG',
                    'scriptpubkey_type': 'p2pkh', 'scriptpubkey_address': 'LYFgesyfnXNCmCaKKKjcppWCzMHk19x7xx',
                    'value': 66768444},
                {'scriptpubkey': '0014d3f2e2d1a2f77d83c9d0173dfe31adb270ae04fe',
                 'scriptpubkey_asm': 'OP_0 OP_PUSHBYTES_20 d3f2e2d1a2f77d83c9d0173dfe31adb270ae04fe',
                 'scriptpubkey_type': 'v0_p2wpkh',
                 'scriptpubkey_address': 'ltc1q60ew95dz7a7c8jwszu7luvddkfc2up875jcyql',
                 'value': 157064386}], 'size': 373, 'weight': 844, 'fee': 6360,
             'status': {'confirmed': True, 'block_height': 2707106,
                        'block_hash': '9ceb7e83248bccd734693bc7c60ce4fe98c3f12db7df479f8be45b66abab1ed6',
                        'block_time': 1719010699}}
        ]
        APIS_CONF[cls.symbol]['txs_details'] = 'ltc_explorer_interface'
        expected_txs_details = [
            {'hash': 'a9e13035052225a65ed7d9fd400d65a57e471d1d1fbf7121207f803e4e9681ef', 'success': True,
             'block': 2707106, 'date': datetime.datetime(2024, 6, 21, 22, 58, 19, tzinfo=UTC),
             'fees': Decimal('0.00003700'), 'memo': None, 'confirmations': 12, 'raw': None, 'inputs': [], 'outputs': [],
             'transfers': [
                 {'type': 'MainCoin', 'symbol': 'LTC', 'currency': 12, 'from': 'Lc8H5EAFBKbGmnJGRNGkLVpLY9XXaeiujw',
                  'to': '', 'value': Decimal('0.04335659'), 'is_valid': True, 'memo': None, 'token': None},
                 {'type': 'MainCoin', 'symbol': 'LTC', 'currency': 12, 'from': '',
                  'to': 'MKJ3hKvF75dA47PyFceqK8P1jpsFqJzLYJ', 'value': Decimal('0.01390822'), 'is_valid': True,
                  'memo': None,
                  'token': None}, {'type': 'MainCoin', 'symbol': 'LTC', 'currency': 12, 'from': '',
                                   'to': 'ltc1qz89kssmkzqh6z4p2f0f5wnj7fmdjx0a8sxxvju', 'value': Decimal('0.02941137'),
                                   'is_valid': True, 'memo': None, 'token': None}]},
            {'hash': '83b41ceb8e79209bec1c82aa0ae8c9a83db87e6e199f764a167b6ee5e01a3026', 'success': True,
             'block': 2707106, 'date': datetime.datetime(2024, 6, 21, 22, 58, 19, tzinfo=UTC),
             'fees': Decimal('0.00003360'), 'memo': None, 'confirmations': 12, 'raw': None, 'inputs': [], 'outputs': [],
             'transfers': [
                 {'type': 'MainCoin', 'symbol': 'LTC', 'currency': 12, 'from': 'MRnv1iF722SUsrFZxmZSg1Ey7Vhghy8Gz6',
                  'to': '', 'value': Decimal('0.04944048'), 'is_valid': True, 'memo': None, 'token': None},
                 {'type': 'MainCoin', 'symbol': 'LTC', 'currency': 12, 'from': 'MRSXyMETyqz1zrAvNjhHNsspDz1vGjZv6f',
                  'to': '', 'value': Decimal('0.00059312'), 'is_valid': True, 'memo': None, 'token': None},
                 {'type': 'MainCoin', 'symbol': 'LTC', 'currency': 12, 'from': '',
                  'to': 'Lbj6aqXbjagnyJhvbtArC5ozQhksmdL5mV', 'value': Decimal('0.05000000'), 'is_valid': True,
                  'memo': None,
                  'token': None}]},
            {'hash': '29c38cc2b50b6da5d42f2af92325ea1295fce613b3bd10f6c8205d35f16a9f2d',
             'success': True, 'block': 2707106,
             'date': datetime.datetime(2024, 6, 21, 22, 58, 19, tzinfo=UTC),
             'fees': Decimal('0.00006360'), 'memo': None, 'confirmations': 12, 'raw': None, 'inputs': [], 'outputs': [],
             'transfers': [{
                 'type': 'MainCoin', 'symbol': 'LTC', 'currency': 12, 'from': 'ltc1qlkpfuktla7pza93x26nrv0'
                                                                              'xfrp0k7kgdy35qaa', 'to': '',
                 'value': Decimal('2.23839190'), 'is_valid': True, 'memo': None, 'token': None},
                 {'type': 'MainCoin', 'symbol': 'LTC', 'currency': 12, 'from': '',
                  'to': 'LYFgesyfnXNCmCaKKKjcppWCzMHk19x7xx', 'value': Decimal('0.66768444'), 'is_valid': True,
                  'memo': None, 'token': None}, {'type': 'MainCoin', 'symbol': 'LTC', 'currency': 12, 'from': '',
                                                 'to': 'ltc1q60ew95dz7a7c8jwszu7luvddkfc2up875jcyql',
                                                 'value': Decimal('1.57064386'), 'is_valid': True, 'memo': None,
                                                 'token': None}]}]
        cls.get_tx_details(tx_details_mock_responses, expected_txs_details)
