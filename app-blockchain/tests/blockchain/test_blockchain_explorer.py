import datetime
from decimal import Decimal
from unittest import TestCase
from unittest.mock import Mock

import pytest
from django.conf import settings
from django.core.cache import cache
from hexbytes import HexBytes
from pytz import UTC

from exchange.base.connections import MoneroExplorerClient
from exchange.base.models import Currencies
from exchange.blockchain.api.atom.atom_node import AtomscanNode
from exchange.blockchain.apis_conf import APIS_CONF, APIS_CLASSES
from exchange.blockchain.explorer_original import BlockchainExplorer
from exchange.blockchain.models import Transaction
from exchange.blockchain.utils import APIError
from exchange.blockchain.validators import validate_algo_address


class TestGetTransactionsDetails(TestCase):

    @pytest.mark.slow
    def test_get_tx_details_algo_rand_labs(self):
        api_name = APIS_CONF['ALGO']['txs_details']
        api = APIS_CLASSES[api_name].get_api()

        api_response = {
            'close-rewards': 0,
            'closing-amount': 0,
            'confirmed-round': 21354949,
            'fee': 1000,
            'first-valid': 21354944,
            'genesis-hash': 'wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=',
            'genesis-id': 'mainnet-v1.0',
            'id': 'MO6URKUBHTLJXAECWFLGVOF6BEXGU4LB753XTWPPWQBNXLTN64HQ',
            'intra-round-offset': 54,
            'last-valid': 21355944,
            'payment-transaction': {
                'amount': 247860970,
                'close-amount': 0,
                'receiver': 'ECUT4N5B6GC7W4PWBFMUGH6DWVH7Z2RWCJDLZJQOI6OOCEZZ7FRVY4QXYY'
            },
            'receiver-rewards': 0,
            'round-time': 1654089156,
            'sender': 'INEMEBYNS5I2CMX4JH3B7HFSY26AMJEO4T23Q3K6H6F7WR7JZMJ2YTOS7A',
            'sender-rewards': 0,
            'signature': {
                'sig': 'wKRvsIJsMcctpOECTx3uA/tHR8Tyd6tUauIQKIfVWHUDDe12UdnQqpmCqesf/JdcO6rlUFtKuAcQ0a3OguZqAQ=='
            },
            'tx-type': 'pay'}

        txs_info = {'MO6URKUBHTLJXAECWFLGVOF6BEXGU4LB753XTWPPWQBNXLTN64HQ':
                        {'hash': 'MO6URKUBHTLJXAECWFLGVOF6BEXGU4LB753XTWPPWQBNXLTN64HQ',
                         'is_valid': True,
                         'transfers':
                             [
                                 {
                                     'type': 'pay',
                                     'symbol': 'ALGO',
                                     'currency': Currencies.algo,
                                     'from': 'INEMEBYNS5I2CMX4JH3B7HFSY26AMJEO4T23Q3K6H6F7WR7JZMJ2YTOS7A',
                                     'to': 'ECUT4N5B6GC7W4PWBFMUGH6DWVH7Z2RWCJDLZJQOI6OOCEZZ7FRVY4QXYY',
                                     'value': Decimal('247.860970'),
                                     'is_valid': True
                                 }
                             ],
                         'inputs': [],
                         'outputs': [],
                         'block': 21354949,
                         'confirmations': 202,
                         'fees': Decimal('0.001000'),
                         'date': datetime.datetime(2022, 6, 1, 13, 12, 36, tzinfo=UTC),
                         'raw': api_response
                         }
                    }
        # api response + current block
        complete_api_response = {'current-round': 21355151, 'transaction': api_response}
        api.request = Mock()
        api.request.side_effect = [complete_api_response]
        results = BlockchainExplorer.get_transactions_details(list(txs_info.keys()), 'ALGO')
        for hash_, info in txs_info.items():
            result = results.get(hash_)
            assert result is not None
            for key, expected_value in txs_info.get(hash_).items():
                actual_value = result.get(key)
                assert actual_value is not None
                assert actual_value == expected_value

    def test_get_tx_details_atom_node(self):
        # Valid tx
        api_response_1 = {'tx': {'body': {'messages': [
            {'@type': '/cosmos.bank.v1beta1.MsgSend', 'from_address': 'cosmos12t0fgtlvmngh6y0n0edz8pl5qk2cpjhecvj236',
             'to_address': 'cosmos1j8pp7zvcu9z8vd882m284j29fn2dszh05cqvf9',
             'amount': [{'denom': 'uatom', 'amount': '405026'}]}], 'memo': '102314558', 'timeout_height': '0',
            'extension_options': [], 'non_critical_extension_options': []}, 'auth_info': {
            'signer_infos': [{'public_key': {'@type': '/cosmos.crypto.secp256k1.PubKey',
                                             'key': 'AmPdwFmyX2wVqCRDGoqE+8I8CXSkfj+RjAvosvem/uMK'},
                              'mode_info': {'single': {'mode': 'SIGN_MODE_DIRECT'}}, 'sequence': '0'}],
            'fee': {'amount': [{'denom': 'uatom', 'amount': '179'}], 'gas_limit': '79033', 'payer': '', 'granter': ''}},
            'signatures': [
                's2Icc1n1yuQZFnvNJWw7YXGOFxlu/OOjOParN2WSz3digsg3eKbfSy525niwXtt640j1iRjcatX/pkomtW8Afw==']},
            'tx_response': {'height': '10787747',
                            'txhash': 'E163F0D04AA2A819F8FE3FDD662EB22604758304D8ADF2AECDD96616A835B8CE',
                            'codespace': '', 'code': 0,
                            'data': '0A1E0A1C2F636F736D6F732E62616E6B2E763162657461312E4D736753656E64',
                            'raw_log': '[{"events":[{"type":"coin_received","attributes":[{"key":"receiver","value":"cosmos1j8pp7zvcu9z8vd882m284j29fn2dszh05cqvf9"},{"key":"amount","value":"405026uatom"}]},{"type":"coin_spent","attributes":[{"key":"spender","value":"cosmos12t0fgtlvmngh6y0n0edz8pl5qk2cpjhecvj236"},{"key":"amount","value":"405026uatom"}]},{"type":"message","attributes":[{"key":"action","value":"/cosmos.bank.v1beta1.MsgSend"},{"key":"sender","value":"cosmos12t0fgtlvmngh6y0n0edz8pl5qk2cpjhecvj236"},{"key":"module","value":"bank"}]},{"type":"transfer","attributes":[{"key":"recipient","value":"cosmos1j8pp7zvcu9z8vd882m284j29fn2dszh05cqvf9"},{"key":"sender","value":"cosmos12t0fgtlvmngh6y0n0edz8pl5qk2cpjhecvj236"},{"key":"amount","value":"405026uatom"}]}]}]',
                            'logs': [{'msg_index': 0, 'log': '', 'events': [{'type': 'coin_received',
                                                                             'attributes': [
                                                                                 {'key': 'receiver',
                                                                                  'value': 'cosmos1j8pp7zvcu9z8vd882m284j29fn2dszh05cqvf9'},
                                                                                 {'key': 'amount',
                                                                                  'value': '405026uatom'}]},
                                                                            {'type': 'coin_spent',
                                                                             'attributes': [
                                                                                 {'key': 'spender',
                                                                                  'value': 'cosmos12t0fgtlvmngh6y0n0edz8pl5qk2cpjhecvj236'},
                                                                                 {'key': 'amount',
                                                                                  'value': '405026uatom'}]},
                                                                            {'type': 'message',
                                                                             'attributes': [
                                                                                 {'key': 'action',
                                                                                  'value': '/cosmos.bank.v1beta1.MsgSend'},
                                                                                 {'key': 'sender',
                                                                                  'value': 'cosmos12t0fgtlvmngh6y0n0edz8pl5qk2cpjhecvj236'},
                                                                                 {'key': 'module',
                                                                                  'value': 'bank'}]},
                                                                            {'type': 'transfer',
                                                                             'attributes': [
                                                                                 {'key': 'recipient',
                                                                                  'value': 'cosmos1j8pp7zvcu9z8vd882m284j29fn2dszh05cqvf9'},
                                                                                 {'key': 'sender',
                                                                                  'value': 'cosmos12t0fgtlvmngh6y0n0edz8pl5qk2cpjhecvj236'},
                                                                                 {'key': 'amount',
                                                                                  'value': '405026uatom'}]}]}],
                            'info': '', 'gas_wanted': '79033', 'gas_used': '71839',
                            'tx': {'@type': '/cosmos.tx.v1beta1.Tx', 'body': {'messages': [
                                {'@type': '/cosmos.bank.v1beta1.MsgSend',
                                 'from_address': 'cosmos12t0fgtlvmngh6y0n0edz8pl5qk2cpjhecvj236',
                                 'to_address': 'cosmos1j8pp7zvcu9z8vd882m284j29fn2dszh05cqvf9',
                                 'amount': [{'denom': 'uatom', 'amount': '405026'}]}],
                                'memo': '102314558',
                                'timeout_height': '0',
                                'extension_options': [],
                                'non_critical_extension_options': []},
                                   'auth_info': {'signer_infos': [{'public_key': {
                                       '@type': '/cosmos.crypto.secp256k1.PubKey',
                                       'key': 'AmPdwFmyX2wVqCRDGoqE+8I8CXSkfj+RjAvosvem/uMK'},
                                       'mode_info': {'single': {
                                           'mode': 'SIGN_MODE_DIRECT'}},
                                       'sequence': '0'}],
                                       'fee': {'amount': [{'denom': 'uatom', 'amount': '179'}],
                                               'gas_limit': '79033', 'payer': '',
                                               'granter': ''}}, 'signatures': [
                                    's2Icc1n1yuQZFnvNJWw7YXGOFxlu/OOjOParN2WSz3digsg3eKbfSy525niwXtt640j1iRjcatX/pkomtW8Afw==']},
                            'timestamp': '2022-06-07T09:25:55Z', 'events': [{'type': 'coin_spent',
                                                                             'attributes': [
                                                                                 {'key': 'c3BlbmRlcg==',
                                                                                  'value': 'Y29zbW9zMTJ0MGZndGx2bW5naDZ5MG4wZWR6OHBsNXFrMmNwamhlY3ZqMjM2',
                                                                                  'index': True},
                                                                                 {'key': 'YW1vdW50',
                                                                                  'value': 'MTc5dWF0b20=',
                                                                                  'index': True}]},
                                                                            {'type': 'coin_received',
                                                                             'attributes': [
                                                                                 {'key': 'cmVjZWl2ZXI=',
                                                                                  'value': 'Y29zbW9zMTd4cGZ2YWttMmFtZzk2MnlsczZmODR6M2tlbGw4YzVsc2VycXRh',
                                                                                  'index': True},
                                                                                 {'key': 'YW1vdW50',
                                                                                  'value': 'MTc5dWF0b20=',
                                                                                  'index': True}]},
                                                                            {'type': 'transfer',
                                                                             'attributes': [
                                                                                 {'key': 'cmVjaXBpZW50',
                                                                                  'value': 'Y29zbW9zMTd4cGZ2YWttMmFtZzk2MnlsczZmODR6M2tlbGw4YzVsc2VycXRh',
                                                                                  'index': True},
                                                                                 {'key': 'c2VuZGVy',
                                                                                  'value': 'Y29zbW9zMTJ0MGZndGx2bW5naDZ5MG4wZWR6OHBsNXFrMmNwamhlY3ZqMjM2',
                                                                                  'index': True},
                                                                                 {'key': 'YW1vdW50',
                                                                                  'value': 'MTc5dWF0b20=',
                                                                                  'index': True}]},
                                                                            {'type': 'message',
                                                                             'attributes': [
                                                                                 {'key': 'c2VuZGVy',
                                                                                  'value': 'Y29zbW9zMTJ0MGZndGx2bW5naDZ5MG4wZWR6OHBsNXFrMmNwamhlY3ZqMjM2',
                                                                                  'index': True}]},
                                                                            {'type': 'tx', 'attributes': [
                                                                                {'key': 'ZmVl',
                                                                                 'value': 'MTc5dWF0b20=',
                                                                                 'index': True}]},
                                                                            {'type': 'tx', 'attributes': [
                                                                                {'key': 'YWNjX3NlcQ==',
                                                                                 'value': 'Y29zbW9zMTJ0MGZndGx2bW5naDZ5MG4wZWR6OHBsNXFrMmNwamhlY3ZqMjM2LzA=',
                                                                                 'index': True}]},
                                                                            {'type': 'tx', 'attributes': [
                                                                                {'key': 'c2lnbmF0dXJl',
                                                                                 'value': 'czJJY2MxbjF5dVFaRm52TkpXdzdZWEdPRnhsdS9PT2pPUGFyTjJXU3ozZGlnc2czZUtiZlN5NTI1bml3WHR0NjQwajFpUmpjYXRYL3Brb210VzhBZnc9PQ==',
                                                                                 'index': True}]},
                                                                            {'type': 'message',
                                                                             'attributes': [
                                                                                 {'key': 'YWN0aW9u',
                                                                                  'value': 'L2Nvc21vcy5iYW5rLnYxYmV0YTEuTXNnU2VuZA==',
                                                                                  'index': True}]},
                                                                            {'type': 'coin_spent',
                                                                             'attributes': [
                                                                                 {'key': 'c3BlbmRlcg==',
                                                                                  'value': 'Y29zbW9zMTJ0MGZndGx2bW5naDZ5MG4wZWR6OHBsNXFrMmNwamhlY3ZqMjM2',
                                                                                  'index': True},
                                                                                 {'key': 'YW1vdW50',
                                                                                  'value': 'NDA1MDI2dWF0b20=',
                                                                                  'index': True}]},
                                                                            {'type': 'coin_received',
                                                                             'attributes': [
                                                                                 {'key': 'cmVjZWl2ZXI=',
                                                                                  'value': 'Y29zbW9zMWo4cHA3enZjdTl6OHZkODgybTI4NGoyOWZuMmRzemgwNWNxdmY5',
                                                                                  'index': True},
                                                                                 {'key': 'YW1vdW50',
                                                                                  'value': 'NDA1MDI2dWF0b20=',
                                                                                  'index': True}]},
                                                                            {'type': 'transfer',
                                                                             'attributes': [
                                                                                 {'key': 'cmVjaXBpZW50',
                                                                                  'value': 'Y29zbW9zMWo4cHA3enZjdTl6OHZkODgybTI4NGoyOWZuMmRzemgwNWNxdmY5',
                                                                                  'index': True},
                                                                                 {'key': 'c2VuZGVy',
                                                                                  'value': 'Y29zbW9zMTJ0MGZndGx2bW5naDZ5MG4wZWR6OHBsNXFrMmNwamhlY3ZqMjM2',
                                                                                  'index': True},
                                                                                 {'key': 'YW1vdW50',
                                                                                  'value': 'NDA1MDI2dWF0b20=',
                                                                                  'index': True}]},
                                                                            {'type': 'message',
                                                                             'attributes': [
                                                                                 {'key': 'c2VuZGVy',
                                                                                  'value': 'Y29zbW9zMTJ0MGZndGx2bW5naDZ5MG4wZWR6OHBsNXFrMmNwamhlY3ZqMjM2',
                                                                                  'index': True}]},
                                                                            {'type': 'message',
                                                                             'attributes': [
                                                                                 {'key': 'bW9kdWxl',
                                                                                  'value': 'YmFuaw==',
                                                                                  'index': True}]}]}}
        tx_info_1 = {'E163F0D04AA2A819F8FE3FDD662EB22604758304D8ADF2AECDD96616A835B8CE': {
            'hash': 'E163F0D04AA2A819F8FE3FDD662EB22604758304D8ADF2AECDD96616A835B8CE', 'success': True, 'inputs': [],
            'outputs': [], 'transfers': [
                {'type': '/cosmos.bank.v1beta1.MsgSend', 'symbol': 'uatom', 'currency': Currencies.atom,
                 'from': 'cosmos12t0fgtlvmngh6y0n0edz8pl5qk2cpjhecvj236',
                 'to': 'cosmos1j8pp7zvcu9z8vd882m284j29fn2dszh05cqvf9', 'value': Decimal('0.405026'),
                 'is_valid': True}], 'block': 10787747, 'confirmations': 230744, 'fees': Decimal('0.000179'),
            'date': datetime.datetime(2022, 6, 7, 9, 25, 55, tzinfo=UTC), 'memo': '102314558',
            'raw': '[{"events":[{"type":"coin_received","attributes":[{"key":"receiver","value":"cosmos1j8pp7zvcu9z8vd882m284j29fn2dszh05cqvf9"},{"key":"amount","value":"405026uatom"}]},{"type":"coin_spent","attributes":[{"key":"spender","value":"cosmos12t0fgtlvmngh6y0n0edz8pl5qk2cpjhecvj236"},{"key":"amount","value":"405026uatom"}]},{"type":"message","attributes":[{"key":"action","value":"/cosmos.bank.v1beta1.MsgSend"},{"key":"sender","value":"cosmos12t0fgtlvmngh6y0n0edz8pl5qk2cpjhecvj236"},{"key":"module","value":"bank"}]},{"type":"transfer","attributes":[{"key":"recipient","value":"cosmos1j8pp7zvcu9z8vd882m284j29fn2dszh05cqvf9"},{"key":"sender","value":"cosmos12t0fgtlvmngh6y0n0edz8pl5qk2cpjhecvj236"},{"key":"amount","value":"405026uatom"}]}]}]'}}

        tx_info_1 = {'E163F0D04AA2A819F8FE3FDD662EB22604758304D8ADF2AECDD96616A835B8CE': {
            'hash': 'E163F0D04AA2A819F8FE3FDD662EB22604758304D8ADF2AECDD96616A835B8CE', 'success': True, 'inputs': [],
            'outputs': [], 'transfers': [
                {'type': '/cosmos.bank.v1beta1.MsgSend', 'symbol': 'uatom', 'currency': Currencies.atom,
                 'from': 'cosmos12t0fgtlvmngh6y0n0edz8pl5qk2cpjhecvj236',
                 'to': 'cosmos1j8pp7zvcu9z8vd882m284j29fn2dszh05cqvf9', 'value': Decimal('0.405026'),
                 'is_valid': True}], 'block': 10787747, 'confirmations': 230744, 'fees': Decimal('0.000179'),
            'date': datetime.datetime(2022, 6, 7, 9, 25, 55, tzinfo=UTC), 'memo': '102314558',
            'raw': '[{"events":[{"type":"coin_received","attributes":[{"key":"receiver","value":"cosmos1j8pp7zvcu9z8vd882m284j29fn2dszh05cqvf9"},{"key":"amount","value":"405026uatom"}]},{"type":"coin_spent","attributes":[{"key":"spender","value":"cosmos12t0fgtlvmngh6y0n0edz8pl5qk2cpjhecvj236"},{"key":"amount","value":"405026uatom"}]},{"type":"message","attributes":[{"key":"action","value":"/cosmos.bank.v1beta1.MsgSend"},{"key":"sender","value":"cosmos12t0fgtlvmngh6y0n0edz8pl5qk2cpjhecvj236"},{"key":"module","value":"bank"}]},{"type":"transfer","attributes":[{"key":"recipient","value":"cosmos1j8pp7zvcu9z8vd882m284j29fn2dszh05cqvf9"},{"key":"sender","value":"cosmos12t0fgtlvmngh6y0n0edz8pl5qk2cpjhecvj236"},{"key":"amount","value":"405026uatom"}]}]}]'}}
        block_head = {'block_id': {'hash': 'kX5+xzP5Kdr+Sj9nOW7dBjhe1wXzMkyesHSl0YHZwMw=',
                                   'part_set_header': {'total': 1,
                                                       'hash': 'TVFNwKDSn9gQlMvPp6w26ecP+3Btm0aLD4/upmme9HU='}},
                      'block': {'header': {'version': {'block': '11', 'app': '0'}, 'chain_id': 'cosmoshub-4',
                                           'height': '11018491', 'time': '2022-06-25T14:33:15.464747871Z',
                                           'last_block_id': {'hash': 'bdxTM+8JhyHDqM8cM4TZxeeWeMZyY5vkeLAXluAUYCs=',
                                                             'part_set_header': {'total': 1,
                                                                                 'hash': '0Smon/IvB6nSoKMWqwZn5Mpvd89DlnKLK+6SZE2vwcA='}},
                                           'last_commit_hash': 'Z60nEPGnFOFKwu8co5wgGr13afaaZNgIYPJuRcRikl0=',
                                           'data_hash': 'DLOd4emJex6/tw9pWZTwNzJ/sU6ur+eojFQ1sYa9Dyo=',
                                           'validators_hash': '5gG8+sygfV2D8MTyMG8PT2UP/Uowd5m6oZPEjai8afQ=',
                                           'next_validators_hash': 'tq271IPBhS8isM+1nx2S50JKMAMcGhz5lQPcfT6X6ks=',
                                           'consensus_hash': 'gDZJZbfCzJ3pYcCZi0en+T8ZcAd+uILg7Rw4IkCIiMc=',
                                           'app_hash': 'lSva1Qb6ztOd5cAxJ0GMOUywywO6Ktv68rbWo5NMP6E=',
                                           'last_results_hash': 'm2NnqaEF9KW5n6IzjOb6AhI6pYvsR5pf+osB5AgUXwE=',
                                           'evidence_hash': '47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU=',
                                           'proposer_address': 'MZIPm8Ojm2aHbMfW1eWJ4QOTvw4='}, 'data': {'txs': [
                          'CqMBCqABCjcvY29zbW9zLmRpc3RyaWJ1dGlvbi52MWJldGExLk1zZ1dpdGhkcmF3RGVsZWdhdG9yUmV3YXJkEmUKLWNvc21vczFsOGEzbXR1NmpyOTJleWVxeGEwYWRmbXB6ejh4ajllMmNybm5yahI0Y29zbW9zdmFsb3BlcjFxYWE5emVqOWEwZ2UzdWdweDNweHl4NjAybHhoM3p0cWdmbnA0MhJnClAKRgofL2Nvc21vcy5jcnlwdG8uc2VjcDI1NmsxLlB1YktleRIjCiEC67ocWoF6P4gn/RNBWmwvhhP/pWbJSC3lhr/yhvX0WWMSBAoCCH8YCBITCg0KBXVhdG9tEgQxNDAwEODFCBpATnf0aB9L8X8fU1mZMB+gbYQyCt8S7j0dGdWmjFrIHJAmg/FYOXjUJO9ZdH5XCl8kcRGhVcy7LeiRULq09mDa9w==',
                          'CsIBCpABChwvY29zbW9zLmJhbmsudjFiZXRhMS5Nc2dTZW5kEnAKLWNvc21vczE4bGQ0NjMzeXN3Y3lqZGtsZWozYXR0NmF3OTNuaGxmN2NlNHY4dRItY29zbW9zMWRucHI0MzZ0azh4ajZlNGR3N3N4cnA1ejVjMmRyOGw4bDh5eXgyGhAKBXVhdG9tEgc0OTk1MDAwEi1jb3Ntb3MxZG5wcjQzNnRrOHhqNmU0ZHc3c3hycDV6NWMyZHI4bDhsOHl5eDISaQpSCkYKHy9jb3Ntb3MuY3J5cHRvLnNlY3AyNTZrMS5QdWJLZXkSIwohAwOIzyLogx43PHjUlwouHN0DemeqKKo34+4HEmADh7ejEgQKAggBGP/CBhITCg0KBXVhdG9tEgQzMDAwEOCnEhpA3eT2oomIh9VbubEgvRNeVL1PG+xzJv3o5QwTej1r0ONx/eSM5NP7QUvKqgD+EsWg9Ha0MicfZgUbiZxoyjL0CA==']},
                                'evidence': {'evidence': []}, 'last_commit': {'height': '11018490', 'round': 0,
                                                                              'block_id': {
                                                                                  'hash': 'bdxTM+8JhyHDqM8cM4TZxeeWeMZyY5vkeLAXluAUYCs=',
                                                                                  'part_set_header': {'total': 1,
                                                                                                      'hash': '0Smon/IvB6nSoKMWqwZn5Mpvd89DlnKLK+6SZE2vwcA='}},
                                                                              'signatures': [{
                                                                                  'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                  'validator_address': 'rC1WBXzYR2Xm++MYl5CT6ORKoY8=',
                                                                                  'timestamp': '2022-06-25T14:33:15.464747871Z',
                                                                                  'signature': 'OsQovaC+ZaeExBM4srfl2Ivq/JYud+yt5JozMiu9QPjNVRHdM+dnITQX08lrf2oV04vLOlItERu/v+0uLeOPCQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'g/R9d0ew9jOmug30m33PYfkKobA=',
                                                                                      'timestamp': '2022-06-25T14:33:15.588053263Z',
                                                                                      'signature': 'w7bLLgfQK2/HgfG3tDmaia1HHBtzbKUlsT0tKY1s5jkOK+nw+KCx2ecaBE6E2yiejRTRDa5eXjxtvzxR9uDfAQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'IZnq6JTKOR+oLwHCxhS/6xA9BWw=',
                                                                                      'timestamp': '2022-06-25T14:33:15.437036750Z',
                                                                                      'signature': '3DH38srtz/KMzgAlnnC4pTutUMDJSYO3L/QofH/ZUzvK6wpeyBK1E0VW06A9P+8pfDSkomBNjtNBAQVnH1SACQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '0tRY+SCey4yiqrHZngZhG4Eqh5c=',
                                                                                      'timestamp': '2022-06-25T14:33:13.877067496Z',
                                                                                      'signature': 'SN+2QhXnp71sh4NStx1TOSucHdSZdbLkuATeEA79hQiiG9LgnhIKDU7q9sjrg6xv20fO42n9uFE/h/PzjkIxCQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'bXAfpZUyaI3xa6+VIRN+jBTLsxY=',
                                                                                      'timestamp': '2022-06-25T14:33:15.654691994Z',
                                                                                      'signature': 'mUZmE1N0shsnz5h7PeNGP0aU4q7v5/evSUfeKLVP6Te7lMCenujwgBHUOz+ILml2gBBa2LRkU0HYduGfUm4ABw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '7VCeeAl+EwapH+3o6Ft10Gvd9uM=',
                                                                                      'timestamp': '2022-06-25T14:33:15.417234860Z',
                                                                                      'signature': 'PY8at2ZhbhvgMCeMGogRQwoyMnxxLDCacbyCQT0+LrAgKSxPDr/+4N85Q4jmL48J3zO8ZC/PUTUjhacGoVI2Dw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '9Zc0qJanaJQ2vDQiJE/YYq4YnFw=',
                                                                                      'timestamp': '2022-06-25T14:33:15.582647490Z',
                                                                                      'signature': 'NvCrBboiZ2d70b2v3AMNv+ouX83a/ZVGTbYBjqfRJ4M3rCHkJ5ZBrLJmAcA7y6H1gq+Y48tJVPIHR7dfPacICQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'aPJweVkNysw6wcSJKhoAjzSPWW8=',
                                                                                      'timestamp': '2022-06-25T14:33:15.473954232Z',
                                                                                      'signature': 'uzpc0jQWmgkwaC6TRh7+B6gWFseZ07yaQyq9rXiphYzEqiD5pCT+TZrzO0iut/DNEyjUesSbHv7Oowpbh3n6AA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'Z5uJeFlzvpTU/fi2b4SpKZMukcU=',
                                                                                      'timestamp': '2022-06-25T14:33:15.400053633Z',
                                                                                      'signature': 'qdY/KhCWpCHoNATrs3Uo/Ci6OUWyGldbAJ8xwzyxs5951Ig/kMcPXxLc7IilhLETVZIH6fcWrn1XOkJyd7zNCw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'sRZ9BDfbnfDVM+4qzeSBBxOb3S4=',
                                                                                      'timestamp': '2022-06-25T14:33:15.386680954Z',
                                                                                      'signature': 'zHLKGXtjbjFb474au/M5xH8H+LYGqhufU8wVEdGLWLWpjQ9JCr3E7a4x08VAiqs010lb1lm2AdWlQUlwCeyaDQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'HO0wcz0WJciatphndgbQ43s2dqk=',
                                                                                      'timestamp': '2022-06-25T14:33:15.399683707Z',
                                                                                      'signature': 'iC4Rm5RMHJS+5ZG/Ba1vdTCCEsdqd7GE3vMLX2f5nsbdnI9c5q8A0xcnoemeEk2DentXPMhEtH29uGpNbyYsAQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '+MAcBoFXiqcA1zbWdcmZIGX2Xj4=',
                                                                                      'timestamp': '2022-06-25T14:33:15.382382673Z',
                                                                                      'signature': 'NyS6HabXhqwKMDq8rHmLoElnvhK74GaubiV68ldIi5LEZjMor+oDQkj2CgQUiKvpGB7NaCGZaWA410YhYS/mDg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'USBWWacX3/uW4FT4vREIcw4Xrqc=',
                                                                                      'timestamp': '2022-06-25T14:33:15.528753863Z',
                                                                                      'signature': 'oIF2e7FsxmwSngCw8yq7jeh/nYTHzWSTBhWRt9MHVziDGbFcLFFzJzjCesvf6S39lCjt8b3ld8bA6wwjXp51DA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '1o7sDS6CSPHsZM21he22HspDK9g=',
                                                                                      'timestamp': '2022-06-25T14:33:15.463044888Z',
                                                                                      'signature': 'L1+OQ5weUHVVKgr9OuEwSlwpTPtXAnExg2lR/8YJF+BTxD8UUgC/AyOyv5KA3fjNwJJCEln7HpzBHbY83JAmDg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'CZ4rCVgzMa/eNeX6lmc9LKfeoxY=',
                                                                                      'timestamp': '2022-06-25T14:33:15.459847995Z',
                                                                                      'signature': 'th8crqI9q8Fm737Dk0xwEuHCx7uo4DliNZkJJNluzMQ+F4xAGddiCb69/mK1VaHDKOpA6bDx8SuBGQYz5agXDw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '2mqqqVnJ74ij6zex8QfLJmfruqs=',
                                                                                      'timestamp': '2022-06-25T14:33:15.490084262Z',
                                                                                      'signature': 'K1FvJsTL0OaxyjfLIM/2G05AAUjoCxrYjJIZsVkVXL0nA2kQtshcfNs0aH39N/zj4vTPbrESAmBFGbwDGptgBw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'MZIPm8Ojm2aHbMfW1eWJ4QOTvw4=',
                                                                                      'timestamp': '2022-06-25T14:33:15.392536568Z',
                                                                                      'signature': 'Ra55LYaRwwsUBXH/ef6q9dLl2lO1BM85CyUZu1tZlxHNvcv52oSIL7WZL7gShTQICZzg+PzTUPOFShuPK7dZAA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'TrEoJnX3JLWQJvIXPCPw3Jk28Rg=',
                                                                                      'timestamp': '2022-06-25T14:33:15.615152778Z',
                                                                                      'signature': 'LNB8YDPBHnqiLnsN3GmkUZIWcnWp1I2L90xXIYLY6dHFbjUz3nMJoD/upL6kY49MyB061xSHjsTUfYHJIgz+CA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'sApjI3N/Mh6wuNWcb9SXoUtgk4o=',
                                                                                      'timestamp': '2022-06-25T14:33:15.401897239Z',
                                                                                      'signature': 'OicAdHTiRsRqqBjVDPwm4HMaooGsBWfrrNdtl4kcFVH5AGlNM/7QLxdxQyOgPjKmlzSl2Epw5ebbdJvDRTQ/Cw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'AZucopRNPMNsfHMoPvPVjlbIpdQ=',
                                                                                      'timestamp': '2022-06-25T14:33:15.546766402Z',
                                                                                      'signature': 'TGaBcca47ZAZI6ctpcQ1PgDpnNMBPYnuB673S6I2Op9z2i5q/P6OG5uZhx7/oueK8gY792q3vDSByM+qIe7ECA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '2fikG3gqpqZq3IH5U5I8fc57YAE=',
                                                                                      'timestamp': '2022-06-25T14:33:15.399848810Z',
                                                                                      'signature': 'FTSj6VY14NYAUKVwlBVvJxW6PfLblvsmclFSUMSPn0XQfvnfqtmcPPNpm69CzuwCNdVVSdB2n23q6jafey6+Dg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'nBfJT3MTu01uBkKHvu3l04iOiFU=',
                                                                                      'timestamp': '2022-06-25T14:33:15.496112278Z',
                                                                                      'signature': 'whnuGq/U3gxnOgY1E8ssBpgPnxVfW6lBVRFbKN21A7DJ4zew91P+5SeF2WY6G0GfPe7+rUe3EnxivMaZGlX1Cg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'Wlnch0b9cn/d1cv1y7kMb2Fsz5s=',
                                                                                      'timestamp': '2022-06-25T14:33:15.465185065Z',
                                                                                      'signature': 'dFkNKMUSa372KV0vJk04lCvxHqIyw3RxlOPi+6p4mR/jobZFlFpOJZrH/wZnGgzjyytKx342+YLS6iHE+6rTDw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'ZxRgkwzNybBsXQVeTVUOuNryKR4=',
                                                                                      'timestamp': '2022-06-25T14:33:15.549899112Z',
                                                                                      'signature': 'yNDND2BaArwHh9Bay/Sf9XosNKybB86Bii/Xior4rSIloLRdNDqMVrWJRdTkUoBqIw9PAW71oRuNPZwEhmBlAQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '6Dv8Q20s6NzJ7AWJsuW3NeN/uFw=',
                                                                                      'timestamp': '2022-06-25T14:33:15.389943902Z',
                                                                                      'signature': 'WFkNtunRNc3MIwS/XRJAVnEu7X0hYqN+NMjqXInqfS5LTJWJKpHCH/royQs2guIrr9ZgWDkbagsYt34jpCyyAA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'gZZf6KFfqAeMkgLzLkz6cvhfKiI=',
                                                                                      'timestamp': '2022-06-25T14:33:15.484266007Z',
                                                                                      'signature': 'mTasah2qNIHNV5W3Yr5Z8GWFlPSrtTy/HWhepa/tDoRBiYDfZ8uJlAnAW/w4mhwuOVAPzbrCfAu0IcHAfNBNDA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'UdslZiBO4mZCfqimy3GYNasXC+k=',
                                                                                      'timestamp': '2022-06-25T14:33:15.410331676Z',
                                                                                      'signature': 'ysWPY0I/1Nr32/KCZ7LkNVugEqQBKwzlm0EUTfzKyRStbDxkByQkZf2UGr49HDyOsKL2CVxZLhtNvhH2BJ+tCQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'ddqzFvTKE2f1MqtxqAt/plq2kDk=',
                                                                                      'timestamp': '2022-06-25T14:33:15.590536898Z',
                                                                                      'signature': 'ExYQydFSnP75pqlYUDw/8DgjwvhLjkvr14WmZwxSLbPKl5g0wEH0OPn5BvhUfsvtn66TcSJkzH+2bSiolMQUCA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'leBg0HcTBw/pgi9sUL12vMv58Xo=',
                                                                                      'timestamp': '2022-06-25T14:33:18.125568711Z',
                                                                                      'signature': '6XLF5uiYz1KZe4t/AkyCkqxoGStF1AnRMFBAC8DcNa35EWjQ3Cjam/uDRDpXwJaXnMX8PjBLRdl9LQ3xQ0MNCQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'ppNdh3uXdsRblu6uUmlZo7mlqxo=',
                                                                                      'timestamp': '2022-06-25T14:33:15.631517915Z',
                                                                                      'signature': 'FmXMGzpv+77UHKqy2sC1UpnS72nD8MiGvF27jYhyKKuqV2XYeeFcVOeWiviiBJA+Ox4dhcKPvQSOsuPN6VgzAw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'zAWIKXj8X91qdyFofhTAKZrgBLg=',
                                                                                      'timestamp': '2022-06-25T14:33:15.465267996Z',
                                                                                      'signature': 'uqk2BO+UUH/V4n0P2gcHzGBCuVny1zKjNMb9GU2PA6YJsMtSEaZyHyLA5LdItuQ91i9K+v99xsw8Whtthe80Dg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '/V1U4Nnkdo/qTA3/3In6lrZlfzI=',
                                                                                      'timestamp': '2022-06-25T14:33:15.369445240Z',
                                                                                      'signature': 'eswYVxIHy21S+BmE93q+eFQk40j6AS3YzNCO7jz9DPEC9VKPwP4xUSLIJXuhhI08OsGysRrgEgBTKkkf3PwsAw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'V3E7t0Icf+s4G4Y/yH3tXoKaqWE=',
                                                                                      'timestamp': '2022-06-25T14:33:15.453300929Z',
                                                                                      'signature': 'ClvYQYJYbannRymF8y+UDXt1PAqsJAp73MDaipUTtx1NxlYi2q1ciy6nmqwDa3/yOxvxm4qnKD3XhKMDd5O7DA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '6AB0DGjIGzA0XDriumOPpW/2fu8=',
                                                                                      'timestamp': '2022-06-25T14:33:15.482564456Z',
                                                                                      'signature': 'VEujogdZhpUiFQxY2X0XVCrNmEg8W0BfDmrn2mjidqFebw+cUkuJFE6J97nXnLehKX1aDRbezCn1GomQ7BL4Bw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '0UpULodWw6lC2f2Ic9wumneYoX8=',
                                                                                      'timestamp': '2022-06-25T14:33:15.520989623Z',
                                                                                      'signature': '4ouhpPduv6o8UPZfJm3jmEPepzE/t3jk7buUFsGKCIvQawhVi4KtBF70iJi5HuUBbqiflRCHCYj4thch0PZuAQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'ezou/ls/zfgZ/PUmBzFM7+R1S7Y=',
                                                                                      'timestamp': '2022-06-25T14:33:15.562889288Z',
                                                                                      'signature': 'Lxba4+VJ9SLBqrUUVIquVCN3bkBNjpcnWoCOHGO6Nn69bVOlLuwU4dokF0ABfekHiBViYPUVplV8Nz+vP6/mBg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'aWq8lRhv1loHBQwoqwDJNYoxUDA=',
                                                                                      'timestamp': '2022-06-25T14:33:15.583474315Z',
                                                                                      'signature': 'LRtZkLMYkUnWZB7AXwtxvtM3PVc5aug7fgQuFVoNbxLH/+4JXKsGneYHD4JoKG1KR3PzDMOGa1q7P+4Ku8bKBA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'RqP4uDk7qhU8QOVyLq6C6g1Isy0=',
                                                                                      'timestamp': '2022-06-25T14:33:15.542615739Z',
                                                                                      'signature': 'iuE1Wgstn5qtABhFIj/FNfFP8N46R8WiLb70NLZIU9qy+Z3v2xZfbNsCcMArXdpOvgQReOfBWMhrrwWFV4drCg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'zIf1a1hiGBHitaR/OMYWbilc424=',
                                                                                      'timestamp': '2022-06-25T14:33:15.422874846Z',
                                                                                      'signature': 'HdtOE5VQR16FNr0sykC6IbDjpuPg9iu8ieGdu0xce7Pzh+XTkgCLKsF7jCQELkwplkmN9gOCIqPOCGzdALCKBQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '1UCrAiCIYSrHSyh9B22/vEo3ei4=',
                                                                                      'timestamp': '2022-06-25T14:33:15.438826653Z',
                                                                                      'signature': '6+9NvMS3V/1eQVrTpc1VvFlZxL5qtsmq+meZ54VfRJzLK9oyZuOUJMxBDk+vZN9DtBkHZMlaAPgs/y1uydIzBA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '07wmsaneyNVrCjuOzSMRDsTNRac=',
                                                                                      'timestamp': '2022-06-25T14:33:15.584793810Z',
                                                                                      'signature': 'g/4Xl4mEEU1NpG4DIEvKznKpl+rtHyoymyh/7yIFA5BKleXc7fZil1j+4p2tMpEtOMrr5vAeR/BaTaoR49teCg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'C0LkfxVOJNEBhLsS4yNHqsYca4A=',
                                                                                      'timestamp': '2022-06-25T14:33:15.445447915Z',
                                                                                      'signature': 'koD3A+fJrvD+nC6zhywqRSOH+wFTA7vrftanpNjAUZbQmMEFXO6l8gPs90gEsqz+utJnzaudOwUnSv38TqxaDg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'JURdDrNT6QUKsR7GGX1dy2EZhts=',
                                                                                      'timestamp': '2022-06-25T14:33:15.391085749Z',
                                                                                      'signature': 'kHsxcT1Nca1ciSF8+AoAmJJF6fJ4X9fM24sNcff1571SAjeWWdh7Lva4Xlbz57OVJmLPeNMz1uLCmgW5Qm9jCg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'ncQBIJm+dDGJB0uF5JiRrjs/7ps=',
                                                                                      'timestamp': '2022-06-25T14:33:15.560072650Z',
                                                                                      'signature': 'uL+eMdh9q7EPDpv0k1E+zJF/PleeOUFl1CHF4v15LwYnuuLVu9UUkyG7pMGQL910gwI5bK9cpvZgOhL+HL1WCg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '4HD6TwULr36idhxSpqVxV4BoGTk=',
                                                                                      'timestamp': '2022-06-25T14:33:15.487631175Z',
                                                                                      'signature': 'Jq3JJjiJD7OEyNxnbSPK/yj4PQUGqCMbbcLRSRiLSkHusurIEa1hyrfKtxYTVc1X9MAJKEDxcwVxKb8ze+tAAw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'sBVSUtc7fut00qjMgUOX5mlwqDk=',
                                                                                      'timestamp': '2022-06-25T14:33:15.482947732Z',
                                                                                      'signature': 'd+EfUF7jW0DO648oV8RhdcSuTWcxahSSftz9DikMXxriIYnz8O/xffNNGRemjKFVxiLNGY9FdE/824bU2RqHDg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '7nOhl1HVjF7ARMEeP7euaFoQ0sE=',
                                                                                      'timestamp': '2022-06-25T14:33:15.400317032Z',
                                                                                      'signature': '4tzaXCbgUzBLD1rDgnYz+o+1T8OjYJTv1uGUCvgkPX3mAm/HRnmnW+UQkI3YQC/FjciZ9qSEE0gzsXhP/G7kDA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'usM/NA80l3UfEkho8EnsLokwrC8=',
                                                                                      'timestamp': '2022-06-25T14:33:15.534051348Z',
                                                                                      'signature': 'IMLHqvCasp1d0nkEvIzarIpKXkEfPDGj0Tin5dvhxTKmisqlr2YM6QTQLO1Snq8SO9XZGdSvQY2BCqK6oCPpAg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'tOEIXxyeuw6plEUssbgSS6ib7Ro=',
                                                                                      'timestamp': '2022-06-25T14:33:15.415348128Z',
                                                                                      'signature': '27kIYAE7J+Z2NuErKBaEhMXfN8Ywpj1aXl3DewtX5rwtywdH3IHQ/U56YSBLSsYsMirpsTOhXmAZElLdRc0GBw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'jg7je3saA43RReMPHvl982Ge9Ck=',
                                                                                      'timestamp': '2022-06-25T14:33:15.755023742Z',
                                                                                      'signature': 'ExUba2nk6FQdJo5UhQmGPOVsX5jeLf9GYTlLtYMFY6vrFtrfFqb745OLExXHeScCGvqIpcL4xnhHi2EAtdBhCw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'kcgjp0TeUPkcF6RrYk7fj3FQp90=',
                                                                                      'timestamp': '2022-06-25T14:33:15.672855297Z',
                                                                                      'signature': '100ZWzg3sqPKs0zGkB05LnAPnxxuylMf1+d+DiRZgOEOnfKczvj9YtDKyxScktMN8MAgjEM0/4MnIvMHtK3BAg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'ez0B91Tf+EdO0ONYgS/UN+CTidw=',
                                                                                      'timestamp': '2022-06-25T14:33:15.418296387Z',
                                                                                      'signature': 'u9DoS3ds1mwvNZ2obDzu5MTn6PgQCpErrHj2c4S+TdFCK8wE0i9Lu6oZUkQys6cNPDaFI1jqg3USu8EuLGMuCA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '4KEmUlnOnHj3ayEZaATxspRtsmo=',
                                                                                      'timestamp': '2022-06-25T14:33:15.498126785Z',
                                                                                      'signature': 'lIJp/JMxxBDIM4fEs6t+/CJOM6z9WLWDIPQwR/pbC3JMJalNPX4+rZ+0PzUH/wUYKz8583HI63L1Elx6TqzOCA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'PlGqiCA216cPlPPoZBa3YBt43Yw=',
                                                                                      'timestamp': '2022-06-25T14:33:15.422882836Z',
                                                                                      'signature': 'XZQxqMpb0P6NX+eP5EMHyr1AYsrBJGxAWp/pdAPtrPoCtYrghpBipvGdHK64jL+bXZV4FwSNKeFOM0bVVw5CBA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'LJzMMX+yg9VKx0iDimTykQYDnlE=',
                                                                                      'timestamp': '2022-06-25T14:33:15.688269028Z',
                                                                                      'signature': 'RifDu7Q0NWYJ7gfBb9fYV2IwCskSkyViEnNBJcOgc37u9Lai2B0DrvfGZzFqplV7iRrtxV/nE9ERI4EVoBTQDw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'sxWB6f9XEEVTE3Di1IlaLW/t7Ps=',
                                                                                      'timestamp': '2022-06-25T14:33:15.514493932Z',
                                                                                      'signature': 'vuc+3Zlr8YLRZ6HKs/Wx1sMeCuyiVXPnfLW3qy0aVsMLnrq/HL83GGaRPl8oqW/+WF3IDJFkABERlbDD5jV8CQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'u3a8YyLHUzp8zTrxwInHs5cfsBI=',
                                                                                      'timestamp': '2022-06-25T14:33:15.450046519Z',
                                                                                      'signature': 'mUQtqCy5rMMFCd17PqSvcetTRueLhqifB6IILv/z7Sa/Rf0sdrCOaxQQ7we4aaGo5psNOfiIVEH5kHYcSNvMAw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'LCpem575AxZPor0/FAVx3fAqAMw=',
                                                                                      'timestamp': '2022-06-25T14:33:15.518347771Z',
                                                                                      'signature': 'ATDvF3iFD0USo3qPM6t5dzs1ya65GIbnkuaEWKQN43I+V2UPoIkHG4c4gvWV25gLI7rvbNV029/3yaZbmx2JBg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'nfjjOMheh5vISwqqKKCLQxvVtUg=',
                                                                                      'timestamp': '2022-06-25T14:33:15.614461232Z',
                                                                                      'signature': 'HaQbeD9FvILe/xMxn2HSfjrjal9AnB5EfhjtetGztT5TEpDOwApkVP0lcWigwMh1KBUm/bKYiWKYsWyroYHZBA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'wjVmIrSVcllhtbIBo4LdV80zBew=',
                                                                                      'timestamp': '2022-06-25T14:33:15.516151354Z',
                                                                                      'signature': '2fZwbI80G8mlVlLZ7e/mIuDGZX0Gj8DCeGQBmzf1typhYPHLtYEZkV9FgjYGFea2VlSJo0llwe2rYpX3Z2wIBg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'xSrNsyBX9ccxu91IRguTw1AN0yQ=',
                                                                                      'timestamp': '2022-06-25T14:33:15.469462166Z',
                                                                                      'signature': 'Q2k1hb8W7KDDsTcXr60TYQHh3EgbgwSlqsyXPjY/atkQNdYJz0Dj6VMGQMVRNmOKC3j9qBHXTsnVw392Fm9HDA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'Sbv7G6GnUFLjIm6OHg7+szkYuLI=',
                                                                                      'timestamp': '2022-06-25T14:33:15.416834860Z',
                                                                                      'signature': 'bNL8LDO2VibN7LuJ1vXM1qssXPR0sdvdqm7HQMDOWmzivtJY6azaiSi6I2cVsh75NkzMVxw1CveZ66AZgpSTBg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '6+1pTmzhIk+x6KLdjuY6OFaLHis=',
                                                                                      'timestamp': '2022-06-25T14:33:15.653606789Z',
                                                                                      'signature': '2Who1KHL8AyIzLqowN/P+6UiaAZPqjU7ao6nKlCiSRI33xWzqF1V2TBsXi9xweKeNrTb/9uxoJf+VByGkLIDAw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'sHZaL2/MEdisRidfrAbdNfVCF8E=',
                                                                                      'timestamp': '2022-06-25T14:33:15.457568777Z',
                                                                                      'signature': 'C1tignpyTdGIyd0+UlEd6I77sKifPBmfhv+ncCp7gYDeqBaM+EDLO+6bnRpoa9fz7UfXqu01QsVZ0b39T7JFDg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'G7KWcA1vzyMYqtotCY5NQEebbH4=',
                                                                                      'timestamp': '2022-06-25T14:33:15.464454679Z',
                                                                                      'signature': '7v0ied+zeWyyNfKm7FQ3HfiQ7uDWK1AEBIc6ZuE/7zPKl9rn1RbO8u9sjETwsW5rvGT0mbE5W3eNQRN+dbNhAw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '1/fHlIfBClzxq+sdvYHo1JdXxCI=',
                                                                                      'timestamp': '2022-06-25T14:33:15.534037513Z',
                                                                                      'signature': 'x5py3IiLDWRnga5T02P3IkRY+rkKyZOZiFoHGWUALklWayny+flRD29X6i4Hoar8MqrjUHKIdeRxZ4ufzdljDQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'QtZwXnFmFrSlRCvaoFC3xun93kM=',
                                                                                      'timestamp': '2022-06-25T14:33:15.384979203Z',
                                                                                      'signature': 'n0o5mp5lWl8BcQhlSmmfjLaGkO63WccamHSw07S6l6E/s8629pDYW22NUjErLF0orxxmVNPmnJuu+AZEIyYiAw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'GuC9Qy+aUSJHSmRjJdGvpgaGkuk=',
                                                                                      'timestamp': '2022-06-25T14:33:15.472808444Z',
                                                                                      'signature': '+lYLyopOluLlcPMKi8N62nk+Boh59BLo+JvWgCg8CKP7xsd6hv3gdmA1IHn8Hlmzog3fs5BOqDAePoO8DH5zCA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'gI1rBUoLbT/19erwplz8ZMVD+DM=',
                                                                                      'timestamp': '2022-06-25T14:33:15.542889869Z',
                                                                                      'signature': 'uO/3P9tE/IA4/JkEC885lvRnzYj8XAkaFmzHjzVGIDgLvOJPCpteh0lWdpvShUzZh1b/oqwuvj86qjs6cLNjCg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'Kl/s8mw/tDQmrGs9tYpavFgA8qA=',
                                                                                      'timestamp': '2022-06-25T14:33:15.456254730Z',
                                                                                      'signature': 'LlgF8Utf/N1jRWh+S4o+AVfk5pzJB9SFbkzcYnjQfEPbCxZTcx1pnqEt6z4hbP7rGFhkfFsLibowNWTsImrzCA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'OZZxwv5LJxTsbofU7kVO8V8zqio=',
                                                                                      'timestamp': '2022-06-25T14:33:15.569166232Z',
                                                                                      'signature': 'NeX23dOucxioouLAXNOCtOROXbvW+B8m8SZB1cTnXwHXLAN6n1AOLpZ1AFLhSNPUmKO22rNb9ZsDENyz3+PsAw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'wt3ZcAz13sBFfcQjgpsx6o/U+dQ=',
                                                                                      'timestamp': '2022-06-25T14:33:15.389095841Z',
                                                                                      'signature': 'Te3sGkfiBWs32z23KNRcEadp7pPWz2K3gZrsI9WxoF1igV30uKBrPuPncSwKoLM7yyiDC5NsXC7nkIGx87QFCQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'M2Po+XsC7MACiechc9gnVDBHrNo=',
                                                                                      'timestamp': '2022-06-25T14:33:15.454885739Z',
                                                                                      'signature': 'ac5Z0pvXrAoiaffy+f2dAkFaqz7r1Zjy389zfdF3lpkLx0miMOBAZml8rCbdL2l1la7yiIg7w66CowSvH5sWCA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'uezh17TdgOhoJj6jqvJyucfxKS0=',
                                                                                      'timestamp': '2022-06-25T14:33:15.456576923Z',
                                                                                      'signature': 'I2jh8yTO9Ejp6zB0SHD5HAnIMSR9Lfq2q7UoEGnO9aTnGwZnzLfLcUqYUpZBrtXp9FrkWcWV6pa5d/vYREvjCg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'tUOn30h4Cu/vWToAPNBgtZPE5rU=',
                                                                                      'timestamp': '2022-06-25T14:33:15.457554710Z',
                                                                                      'signature': 'NDm943bQ+dqPlHklcH2cz5x4XpaP0xHy+HXqQmdKCC292C/EGks431a9Kse9fp1D2eIl21Qg6TvJxPVHHt8YCw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'v0y01Z0Z1FHPXnvEk0nfSqIi14s=',
                                                                                      'timestamp': '2022-06-25T14:33:15.388726573Z',
                                                                                      'signature': 'zjwTN6Maun/utZTxt0UYofyF1OZzYOD/ahlV8nDgsTVvgg9RnhWj893z1LZXhFoXuXhGv3fJTMb2vVpGJf3QCQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'sr9orUztb+j3GqytAQA0Nuvgcp8=',
                                                                                      'timestamp': '2022-06-25T14:33:15.573474826Z',
                                                                                      'signature': 'U6iAnITWW2UwE8Kzp78YTPgubmHUpMB++9mZTr1EdhY5StGJH36VHr6jPgRQVmbDwjA5rCkrpm2QeyoXQhSxBQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'CrujbFTdDKankK75agHUOS42NF8=',
                                                                                      'timestamp': '2022-06-25T14:33:15.488348563Z',
                                                                                      'signature': 'ohzNZJuR4YEmuZ1tQXhZ9HuFtyfG+byRhYDlGjybyltKfuThvQL8LJJ36HI01QqDKm1k54mhrWJTUdBa6V53AA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'hLPYkiui8ko5R37BSVeZG+Gud2U=',
                                                                                      'timestamp': '2022-06-25T14:33:15.431690099Z',
                                                                                      'signature': 'dpTD/xmZV7Ub2Z5/BrWtCsGlVqO6tAa1oyJFL56i7gzrvZW3O2SGPItCqoJ7l4GuEQRmBJfMuQsDusrzR72FAg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'AAqlq/WQqBXry9rgcK/1C+Vx64s=',
                                                                                      'timestamp': '2022-06-25T14:33:15.504974855Z',
                                                                                      'signature': '0NqHlNLB7tgGETgSYWEhiOmol7FKCVLwh3hbMfn6nJMl+o9BEe0LhPZg96t7DipPVqylAZ9s4aNs1FlJNtHACA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'aPW76s7xFMcg6pyYv6L/3gHFT9E=',
                                                                                      'timestamp': '2022-06-25T14:33:15.698352037Z',
                                                                                      'signature': '4vI75VNHjCx6ewtddjMW5p7zUtBDFu3WrLH704VZJiAmPctg8aBKJ3bTqlmbsryixPei392C8Rgulj5Wi75FAw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'pPHVU08/qQWk2mBuihCDSXZRH/c=',
                                                                                      'timestamp': '2022-06-25T14:33:15.428478910Z',
                                                                                      'signature': 'nYGV9oXPFZXt9MeBGQsCkJpmad7vTIahKz4pDLw1fcCyKed7sQoSu19Rb614HcBrzUSv3nySmfHKWd1Dr9ZrCg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'WrNTt0jUXyDfzhnXO6ifJuHDTPc=',
                                                                                      'timestamp': '2022-06-25T14:33:15.472394087Z',
                                                                                      'signature': 'oZz78IecLO+/V+PKJsmSRU/4HcjGFcdRbCNhE9DawxipAsBv4cPfuq1BrVLCM7cQKe+4Ki5dNRLfnmsTis7yDQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'UuFkYTRDK/lTK0iBxu0y5Arlot0=',
                                                                                      'timestamp': '2022-06-25T14:33:15.496562994Z',
                                                                                      'signature': 'GQi9u2ITNNX098a5JYklO0PFkZf3g0aZR4R3/3zAksWLJEp3fHMz3bOp2KO5L6vBricZ4Tp+7d3bZT6YP4/hAQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '+USWk75IKU7P/0f1r7PDHB36sxM=',
                                                                                      'timestamp': '2022-06-25T14:33:15.487257191Z',
                                                                                      'signature': 'R0ZuYhBYKFcWQxXOygDP8vfoSNZkXXzNRtdEuySjX29qoGb78SvMOpVQDNpzg5bxO2wB5AlOFIaPhQgHl3TOBw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'gBF3Ltfd8syc16SMjAqiSG6fTpc=',
                                                                                      'timestamp': '2022-06-25T14:33:15.448872350Z',
                                                                                      'signature': '6WXOtcsFCkYoe8NpPoTkqhlofubvFgrrym7HjAWUcyVUtwJSiNBM7WDVwyQa6wKnoXcUymE1ypgkHBGnwyslBw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'j+PP+moHsJPkQbuE2httq/U6+i0=',
                                                                                      'timestamp': '2022-06-25T14:33:15.566211646Z',
                                                                                      'signature': 'd39kjEQ/ndD+wnY1mcYD9wCBINjKccKjQUB0NfbSu6iZxXp96EvtELcSnxJhs8FSMgtMb+evQJUVrivRoLajAQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'sjayojrXFqnY2Fagy6di8yNRXF8=',
                                                                                      'timestamp': '2022-06-25T14:33:08.450547255Z',
                                                                                      'signature': 'juBzGZ7Y+MTiUEB3Z5EBnHk09KNziCI/DcQ0y/Zp1FAtlDxzTtgycJTCwNOikmnDPmixciQs3oFEK3U310yoBw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'ISI0dc6G88fNXphaqI/CSinJeBM=',
                                                                                      'timestamp': '2022-06-25T14:33:15.426679676Z',
                                                                                      'signature': 'rOnOceoyE+Y25DRbC4c9/A4p3lcg9YlScB9zDEywUEt/guMkmXv7WIspvGNiGA522qShwsbkgTYvEj+9zQWFDQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'zFziQY2oXHjX+J/sqrCN3OMUwMw=',
                                                                                      'timestamp': '2022-06-25T14:33:15.672329942Z',
                                                                                      'signature': 'LUY0mQb4x7LOJD5iNdbkn2K/f22ysFy9WOJEQuWSvIVFusOvKx/8kYwZdz1h0+Nn66QR4Df1HRVy1vWqjPhjDw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'tMwD8qyiLEPeHtOFoQS6hrdGJ5I=',
                                                                                      'timestamp': '2022-06-25T14:33:15.420063611Z',
                                                                                      'signature': 'ggizx1c6jBxM91869qW/OSJbkD8/J6LvsL1zWbMsaUH8uK5jiaAA8vHL/zwW4SoAJo+GVbqx+PSjM1EI92FjAw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'bqhjtEujafc55lWVdw2rksiakhI=',
                                                                                      'timestamp': '2022-06-25T14:33:15.486200467Z',
                                                                                      'signature': 'pM6ZJboWgLvVMwmohPuzccADpTEwUcQPa5tgI5tAJd5IKYhHsGh5P7sJ7F8K260y//BkNq/WFoWDktNbTQcLAQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'a9RwUCEzKpC5I5fY1yyjlQy4WOs=',
                                                                                      'timestamp': '2022-06-25T14:33:15.517489162Z',
                                                                                      'signature': 'Wi+hfmUYpuvTVSOh2f89khJp7tArwrh7aOFcfwVC65dq3yvzpW6xqTQZDpv4Tiq/NinSWkPxKGt/+fpKhOawAg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '+ACDsYPEAZklxytfSC8iRqwtQ5Q=',
                                                                                      'timestamp': '2022-06-25T14:33:15.582515141Z',
                                                                                      'signature': 'vaJD9tMBiWd7WWbPA+pMCh189ipZHkkd5tDPXDta0YdgXrnVAftuijXjEtHIFf14KbZYa0cjR7ExWA2t4m6nDA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'KQZ9/jNSpASB230R7kSxChD8QpA=',
                                                                                      'timestamp': '2022-06-25T14:33:15.423417682Z',
                                                                                      'signature': 'orBMpOwueDK7PhSQe3zahZkxNyndgt7XIe5cEaEOUOpN1N37PxCmkh7KHZLny7wSc/OMgRC4Z//7nGd9pbjLDw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 's0WR2nmq0CE1NOLpFfUN5c298lA=',
                                                                                      'timestamp': '2022-06-25T14:33:15.540594349Z',
                                                                                      'signature': 'MIIs1e6W2bhHOYd5cLNF26cWVWIJALPRYuF65slpQZ79LpCkj76hZzeOh0Pa0PvmrEE0tbxS9a35AD2d6owTDQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'BYWemGKmaA2+q1EDYsELFmG5dDo=',
                                                                                      'timestamp': '2022-06-25T14:33:15.659921378Z',
                                                                                      'signature': 'YbM/gvBDW7qlBkRC0f4fpdysWypEW3MvMC0NDoWi4vnZwgk2GZUuT+y8JoBIUAJWQxA0TbAPImpFlkevWNdFAA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'xTJ9ZM30oEvhIG5l9bYdRJI2MOY=',
                                                                                      'timestamp': '2022-06-25T14:33:15.423399416Z',
                                                                                      'signature': '15l6CwFD6WCNaTjbHHVta2CL4CxxGMHnxw+CwocRjcvuLay4c9e9yPhsB0gUzzryHs85kwdsljLrBoV5IawfBw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'cyzu9Uw3Tdxq3sv9cHrv0H/twUM=',
                                                                                      'timestamp': '2022-06-25T14:33:15.501957075Z',
                                                                                      'signature': 'jZY9/U0m6scxP+T+1cgtOECK/IMMjmHZzcZ1WKQvjCgNUcfu7T5ACYP3uYirTUX1q32pDfSBz/RrxDnp/THnBw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'fmL0bLzp+x3lRGAG1tLu+4I0jaA=',
                                                                                      'timestamp': '2022-06-25T14:33:15.641006817Z',
                                                                                      'signature': 'vn384bqqbuzWaqZz2ckipfn0+b7/RjUO6XpEVMzAV49r4lwGJyd5rNOQ0Mj1bzBAi8pbIEXGC0BY/gVQLNQhCw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '1e3JNDFMibRZUmIOnJkrHckBhEI=',
                                                                                      'timestamp': '2022-06-25T14:33:15.423328172Z',
                                                                                      'signature': 'fdhV6iHu4Iub+ec+YurTCv2ZlV/91qq7q4SSg4E7gv0esObAhs1PKW43/BB4NaNsgbnZPFRgjMBq102ByEVmAQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'YKqsuC+rnZDLLfCqDM5FVRAe2Qw=',
                                                                                      'timestamp': '2022-06-25T14:33:15.529754504Z',
                                                                                      'signature': 'qBnyd3S4UmvOwj64iquLkp57RiWDXc2KrLST7FXkEKrg+gd/ShFI5Otf7UA0heQVToIzXz8FfyOWpLwbeZsSCw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'EsKqDeZvo/nWZNA9XW9tgha22oE=',
                                                                                      'timestamp': '2022-06-25T14:33:15.389309935Z',
                                                                                      'signature': 'gb9EkRWpOQxIzjiLO6RtK2VCmk6fA6jV0lwOCRkup29HcnuMbWMLauF+q/O/pjAP4g6wqOrc/4JoulDigZ6KAQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'JJNdWfqpTnk2Usv0cWxgQc16pAA=',
                                                                                      'timestamp': '2022-06-25T14:33:15.491693607Z',
                                                                                      'signature': '1lAty3KXNnJ9j5vc0NZIJB88lqwNt0xvqHslxM+rvwbhD/YJKZb/novHya337ESot9flGMHGUNk+japEN+PTBw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'Fw/v1tf0ppqucKJEFfxOLJKN4uU=',
                                                                                      'timestamp': '2022-06-25T14:33:15.479200933Z',
                                                                                      'signature': 'oeuVJs/G1ISFO3P9NGBUa/+lvfWlfH03Rs80b5WxdBfGa1uyvOeUHATjUFaQ+Tz5iDWHMNCkOMeLkdUMdaKGAA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'TJIjD6wWIwPZgcBt0iZjpPx2Irw=',
                                                                                      'timestamp': '2022-06-25T14:33:15.409657247Z',
                                                                                      'signature': 'vw2fRYe3UXNtFUE7+eKwQfF+Vs1DdRfwkwulozKWOp3wKpV1jDw0jQdGMlXoZKz1zd6odJ8ums7GyW8KrF4SCA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '+OUDK5jV0yRC4yW2lwtDT3UuET4=',
                                                                                      'timestamp': '2022-06-25T14:33:15.509721457Z',
                                                                                      'signature': '1Pb3Wt6esSprVHRoq3NsuHepzrI/gUrqwtdN4tsYC/nwRO+Mu01J0G+uTYuv1VJpQAQ/iVk3QbPTM/7HBIMnBA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'HpzpT9C6XP65AfkLxljWTYWxNNI=',
                                                                                      'timestamp': '2022-06-25T14:33:15.439398855Z',
                                                                                      'signature': '6BlYKk46Ncat2hWFgio9H2VTvbHBD0FMd3JJNyJgM3Uw5N5LQvd5/wTEV/fwARk9wibrErqLUjxVISORCDCsBw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'K5pV07+T1zdd0ge3XF7U0rkdkUY=',
                                                                                      'timestamp': '2022-06-25T14:33:15.445948133Z',
                                                                                      'signature': 'AuX+oKXSPURdq7YnOenzpw7rckHLKM6DF0a6ktUFyf39QvuIzpP98N0cXuPD/Y+TDE4aaCKgFIXDJ68lkql+CA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'yzP4IXwHlS7KGPU8H+r5E+kUMTc=',
                                                                                      'timestamp': '2022-06-25T14:33:15.394935076Z',
                                                                                      'signature': 'nIcC7yDlvLqiJLpNbansQvhOY74ApK/kU+/RLVDc4vPX+uwvBzUqg64NQs+XBhFX5ao5eYSQUihJUYuSnMpzCg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'ePHXqXc/ySJzngo3BafKBr6jCIM=',
                                                                                      'timestamp': '2022-06-25T14:33:15.448118349Z',
                                                                                      'signature': 'M2KPhPgghBn62ZGgx38fWbXEY+jys+XObmmuN+9ofeIf/jotOTIdLi4Lm3WlvaQ7AxxT8p2SMoy5ccMZHfZ5Aw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'gYlktPs20oEJw+hTd4szIxsnxfw=',
                                                                                      'timestamp': '2022-06-25T14:33:15.551687958Z',
                                                                                      'signature': 'pUzyG7j5amp0dQxp8A4+bagXmbistWcQf9rcJSw2Lr0+erJZTkgpX1KPMILUXT+gh4ejc+8gA0K+fgWC+KC8Bw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'SvadalQ2ww41hMFihDPeVedYvMo=',
                                                                                      'timestamp': '2022-06-25T14:33:15.530985687Z',
                                                                                      'signature': 'IM31Yvb142jvX4IbELqODLSJHLKS4YyIQx4j9Whh4/lTjsE/ZdZErtQT9zfGjL60kB+pHO8+JBzAi8iPeVsgBg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'nulNu4b3IzcZK/KRsOdn/Scp8Ao=',
                                                                                      'timestamp': '2022-06-25T14:33:15.379830093Z',
                                                                                      'signature': 'YB+0hvVjZDKdkqG+VpvdwsAA6yC5mVcDK8sH3xaRY8wtXDXU/jR44nk+FsmisOnIs8vyIn9K1NrMzU50S7SiDg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'znaAM9cnxqKJgK73Ny0SQyfIEKg=',
                                                                                      'timestamp': '2022-06-25T14:33:15.408365799Z',
                                                                                      'signature': 'FoSQV2QpTc4alCa1E9YJOBZFxagPIw8zdjF4OKEm7wXpUFyl1iHCiVt/I1ehLf7EShubwqajlen00nxMYW8mCA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'bzIrr11z1cdycZQZAbHYZkdtXJA=',
                                                                                      'timestamp': '2022-06-25T14:33:15.413316379Z',
                                                                                      'signature': 'joOYbQYD3OfZlomx9h914Mwu3aRahRvQtpKLyD9U3of9EzaK5p2+x3541qg7el9pyEINNH0shSPUnqzWFLhRAQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'bLR9eGsvNQwTpgu3fTmKyC6QCYU=',
                                                                                      'timestamp': '2022-06-25T14:33:15.399084240Z',
                                                                                      'signature': '0DBsA39S7cWNUutEGBMGvjj/mzTLk+OFke3aWV4W7aCuQh+VtqS+92djTRCXEtvJPU5u/tH/kew5BAIlL0lUAg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'LIgtV1Zehqnuw0M7FQJfj5YxhFM=',
                                                                                      'timestamp': '2022-06-25T14:33:15.568719247Z',
                                                                                      'signature': '/QMj8NtuBbFHqjdtusnfbhKBR0dABfOSmogjoK+BUsa1xo4JV9zkMd3l24WRUfzcblF7aSzKxa56KxidSA+wDg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'mtCqGKkqGkN0Qm7ZuBktHWw9JpE=',
                                                                                      'timestamp': '2022-06-25T14:33:15.395258711Z',
                                                                                      'signature': 'gyPmvcY6+fIe67ns+81/cuhE4Mnz7FInB+JDuz5OUiJ7ORBYEpJMv6+7aHjWwMQe//84OtninkvyS307sS3/Dg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'ak0Up6ybT3x/KNyQRuUCnRvwn0E=',
                                                                                      'timestamp': '2022-06-25T14:33:15.381293665Z',
                                                                                      'signature': 'qLv7mQscqeCoRF9mS/KubIr46ACD7PyBl3UOLj455LM0uqSOZF7bPI8rEEeIEp7n3AbaO5adGsDYDWNaqsSoBQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'jIgCqSERQWnSWBzUbjymhT9vKn8=',
                                                                                      'timestamp': '2022-06-25T14:33:15.603258719Z',
                                                                                      'signature': 'RkDPhKavxg8/hs27lOQzfLl68kT+f67JcBQzTudDSNhra4Jk797ADkcl5+1bnUBmY8mcQfj6jvLZ+BH2yNQODA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '9v1jZazFOCtq1lZs0pcZBLdffiQ=',
                                                                                      'timestamp': '2022-06-25T14:33:17.448560903Z',
                                                                                      'signature': '66hpG5YuyfMUF+gsuXiwkW4n5OjbWwXK6uxF6IEjLh32rQQCM8Vawop0li2ui8z6pEIMkwNWnHHIrUnlRe0gBQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'u+Ve2bLkFuKzfBO77pzW564xRxY=',
                                                                                      'timestamp': '2022-06-25T14:33:15.375109790Z',
                                                                                      'signature': 'jDxqSXFL3Y9LnFS55ylaLcCvWBBXE7sRVT4zVx7e19KYG+vk6kJvHui49guJ53w3fhZXQ+3PJlVFd8E9S3YPDg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'E+4/BfIMatj9J8vvM91h1fmez28=',
                                                                                      'timestamp': '2022-06-25T14:33:15.559700001Z',
                                                                                      'signature': 'eJX+xyyXSTD9l95snTxZO6eKb5QxJejRVwNYQhafzgJRSbpI5hvIJAdMNVebyg5EqQkE+Ui/BpfTggnPz9IODQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '1l2wTRHvxDXrttKWhYyt6/1ETDg=',
                                                                                      'timestamp': '2022-06-25T14:33:15.588244659Z',
                                                                                      'signature': 'gqiZu9py6xFoTesGu5gbVdFAha3M2yfltTblryQ7YmLlnAl0SIkWri3kpKi634CRYHTznXJGevRlhbFT0tU+DQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'KpE16IFgrwUsmruz9jAdfZniOEg=',
                                                                                      'timestamp': '2022-06-25T14:33:15.444236910Z',
                                                                                      'signature': '4KYxsTvMA/b81oN7hvilSl8JdTW4vQ3qiH8hKIUhaKfP3ATaDNLxOnLUUFyhsYBcBayu2V0vChqpJSOvuka/Bg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '3qELGQGaE7F9GrnK4XMhza47BIc=',
                                                                                      'timestamp': '2022-06-25T14:33:15.552659273Z',
                                                                                      'signature': 'GyBpWBOZdaO3IAp2YQLDyn880mktN5e6pWqmyKrnxYOYOanwIYCDeaFxZrB55OVOVE2bh0yhb5jWI4ojCaGGBg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'lVpHyKyGMoJd1HXpCRPUCrCdP7Q=',
                                                                                      'timestamp': '2022-06-25T14:33:15.606648452Z',
                                                                                      'signature': '5+L44ck5JzaWBc4usWp3GjQIivwcjMILiMyiuTxfXfI25T5fK+FnbGexiQW0PB7DxE0XDv2jq2S6+SzaDj2ZBg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'vbBGJZ63+3SigBXjHmTO6fCAIZk=',
                                                                                      'timestamp': '2022-06-25T14:33:15.545847028Z',
                                                                                      'signature': 'g2HjRtltjC6MdHWWSl8duCxbtZxVR15Zr09s3YQh4eHRVqMRN4eu37+LlNHu6xDsFD/0VcCVFg9dGwjkFUGDCg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '9VcUJD0y+2W22Vop0DUOoMq7qOo=',
                                                                                      'timestamp': '2022-06-25T14:33:15.498694353Z',
                                                                                      'signature': 'ZN7OfxTK0fbu0WQnKRbuMlTQPNOv7RlTYbxPeir3JVIq8mVw/z6tQOwcjaS/2E+RG8FiOP1fRVBD9aqhrtfjBA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'SP1WDTywtVKSTLwPnCumiIP6ETU=',
                                                                                      'timestamp': '2022-06-25T14:33:15.420147475Z',
                                                                                      'signature': 'jdDfV0h0xjCbuBaDr/LeqCoPlJhZxprSEKrHTRKm7i+rNs1fN21iFYCkZMzj+VuS/r3DCQTnGNq+g6/mIfY8CA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'QH8UTRyd6k7mqMvC1MAipldQa4M=',
                                                                                      'timestamp': '2022-06-25T14:33:15.522480530Z',
                                                                                      'signature': 'CnWRLmVNEbwFwiUJoTIcaWeOABFiB4ac7HLdUcbRNyyI+zCSm0Gs1t8Iq6QPT/V+46jl1W+zAxbgTq/WoHT0AQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'hGvk854xItKi0/5UVOJWEHPpVTg=',
                                                                                      'timestamp': '2022-06-25T14:33:15.514619275Z',
                                                                                      'signature': 'W/7hKz9n9ZbdOHyT7ADL/Xem2v7DeOqh+ldsgIWQuKamNg0N+JomcKTmKTGSdAFeRdcOKd1yAQ8kDOdZgCmGDg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'dCC3PxAomsoYrM0ctatUiCwE0tU=',
                                                                                      'timestamp': '2022-06-25T14:33:15.385449292Z',
                                                                                      'signature': 'i21o0pvMwMYT4RsPX1nKO+/63M/KwhzPxHTs2K9drB302EdFdjrjxrJk/MJbwccDi8SZx+wpNPn342XPmo8kDQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'biI0+IGBen25l9WUAFGFkfaSoUw=',
                                                                                      'timestamp': '2022-06-25T14:33:15.684702191Z',
                                                                                      'signature': 'AdvBMeyrifOT5yNC4vB31yDE6vUqowAbFSo/j7B92ATd1N8701rWFgi6AJeOd4Y/D2I9v9JruFTGqB9rJIZcDQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'RPBYL8sjsEQHRDaQb4IGz2VRLDY=',
                                                                                      'timestamp': '2022-06-25T14:33:15.582935769Z',
                                                                                      'signature': 'XVjYtkhtPTQjTKnUx66m+vuXnGb5WqwEfTTDuyFJzDGX8ANnYx7VCAog1LgzlfYAHd5aDrPlier6ejd1oPxzAw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'pHEVwJ+Eb0b0mfOBs1tFJyUgSYc=',
                                                                                      'timestamp': '2022-06-25T14:33:15.462642519Z',
                                                                                      'signature': 'rzcoSmNK51AfzaViROPq8DH5aQ2GLQrEdMaAUrAj3aYdP8sb5iKnr6ERdh7xBLjAAJg7EUhI9cZf+hcZWlO8AA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'iKZQRfXuUCVggm2gf3ObqeuoRww=',
                                                                                      'timestamp': '2022-06-25T14:33:15.663242535Z',
                                                                                      'signature': 'yNNm+Z7t+zQc9GTwbSAbIcsEV7UZqfDo4+HM9FN9YHZ9iwzteRlTNVDmJZPrEgmDoktWqLZTAQlSZjTbyepjDQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'h01qqDg4Snmj1NBiVB+Rv34xvbo=',
                                                                                      'timestamp': '2022-06-25T14:33:15.637060602Z',
                                                                                      'signature': 'lDHLlxYHStihnj1d9G4c+IyGEvJXiCxvT/qKgbq4Dx+1y0swBxmofPFvcVR4ZVCOA8U/T2CSi1c2JtaHJtpqDA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '35KD2iWylkJul0OGFNHGLcEBnYQ=',
                                                                                      'timestamp': '2022-06-25T14:33:15.380789514Z',
                                                                                      'signature': 'sgrBSrAAOeftCf/wfss7y3cfSvZJENwEUfXLEASiTsddOxqXDuG1tkbU/QY79kish7xG+MM541L6ph5iSZxnBg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'O4RcmvHWnp+7YgtpqyJrKLrJeYU=',
                                                                                      'timestamp': '2022-06-25T14:33:15.466213661Z',
                                                                                      'signature': 'UwonM/zNvNBvX+DcZbfwC9TRStpEXNwbJYUCfnvMd+Jy6UXxC9aIzKIM1r9Ga+nGkpneWsaSvY2ugOByr1XJCw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '0mmoHHdB9FjDHbf7FMWBdkIfsvg=',
                                                                                      'timestamp': '2022-06-25T14:33:15.500080627Z',
                                                                                      'signature': 'hfqkoD/YtB0Mcc3eARZIwGXirvmASEni3PQ9SJnNcYMpa0f1TXf9BZwga9XqZepCFbrDNFzOqIOmrjRuFPrADw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'lxOBjaVAsq1AzTqCGGXxyiiKG6o=',
                                                                                      'timestamp': '2022-06-25T14:33:15.366900932Z',
                                                                                      'signature': '5WgJwNWtrKxNHUMgtdT+UJVMh16rBNIkDIdhfhHHUDedPbp2tfx/FHaWPDVJR2jr+NPCh4m6H2U+WTZ5xOArDQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'xJAyKbnq1BXHno+mnSu6YRdhfEE=',
                                                                                      'timestamp': '2022-06-25T14:33:15.399111994Z',
                                                                                      'signature': 'PIlSeCy8seH9tvwBzXmIexaTPB0XxL3YKfszWKimbUzAtjiI7PAotkijiRd0XRCEPh8Rk3fc39ET4iUMzDGrDg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'tJmc1TXkzTK1kL60cCCnJPQLZeU=',
                                                                                      'timestamp': '2022-06-25T14:33:15.556932653Z',
                                                                                      'signature': '69xx7eJoOljOGdmV0kcAr42L2K8LC/+WxewlWbulkO66AhSFUG/oWEWRpdZu6LLM001FhNtvAv95L3SGtjhaCA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'TtfMQDiDPy6lqj9NRMWByOfL2GI=',
                                                                                      'timestamp': '2022-06-25T14:33:15.422972121Z',
                                                                                      'signature': 'B1A9OQG8ZF/JjIM50nhCSq6DPSnXPNSxFZb7tAkVKU81QNhQSdXQdwklKwbWa+7uDSOj1kWfybZxWeS/d7cHBg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '/fVplFT5OihhW6dnfFblYvn/aPo=',
                                                                                      'timestamp': '2022-06-25T14:33:22.238755323Z',
                                                                                      'signature': 'zjyGk/3O0i7U9647jkkV1ekbF6bZGlSYnfgH7PE9xPIySS39GoKPr4tsIj8VeX3agMruhpcB9uMlftshVcObDw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'o8fATWIOqjN3dfADuNCYFYFnYzE=',
                                                                                      'timestamp': '2022-06-25T14:33:15.437226270Z',
                                                                                      'signature': '0ezrB+lcd7lYv5bIDlF1oKl/ycXmWhFxKC8ghRqtnVF9gzvl7o+D3Cuz+Mc1GEbMEGmNsnj1he54VD31v+5KCg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'alFVTowM8xZaAcZ1qYosOLbrUSw=',
                                                                                      'timestamp': '2022-06-25T14:33:15.372983911Z',
                                                                                      'signature': 'Yi4Z2Dcq5SBTKzoskxFKXZ8Xdr6liJi0WDR0tduoxTnPeh4qUqtr4Dor3gHj22wNJrMfLacY1h2T6lwawpxiAg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'VbO//s6/oOV9oyLQ2iYsE2qRkmw=',
                                                                                      'timestamp': '2022-06-25T14:33:16.583999117Z',
                                                                                      'signature': 'aV92YzDpaQys2PEyD9rxEef9aDmAJrKI7TOyt+ZrwmHK7uF/m7Q6PJSS9mM/1Kb5+A/Poqgzun0dNeSqo9fRAw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'xfBrucn6GpXCm9qMMNXcchCvIWY=',
                                                                                      'timestamp': '2022-06-25T14:33:16.913147398Z',
                                                                                      'signature': 'kYko3+0UZqL61p/Ds4Yq3I6JQ1WbNuATX28KOQR99Buy1zF8xGKoY65mcAbaHFJajGyN1cuJRKP8THbG5Jp9Ag=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'cMW05necWaJM/ZFGWB4nAhwq7CY=',
                                                                                      'timestamp': '2022-06-25T14:33:15.430306914Z',
                                                                                      'signature': 'ui6KDrMLX4nYT9xhFXM03Gr2WxTiQqgXEMekHWUHN8vp6/XbGO1uYIVI5GfAFe5kfjDz1ce2+NlPXtInDLbrBQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'AMzuz9AbLTM6G1ar98/4prjtJbE=',
                                                                                      'timestamp': '2022-06-25T14:33:15.659154622Z',
                                                                                      'signature': 'jE3Y10MGyeSuh6EZ61V1Vva6Blecqzb6znu4L8OXX5Z7iZVCGnBicsqqZIwdGS+/xa9tHKhQmXzOPKN0k1WMDg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'Z0jWMuAOUkfCJi76lt6UbRruwys=',
                                                                                      'timestamp': '2022-06-25T14:33:15.403236605Z',
                                                                                      'signature': 'LEiPo1LCFTgA4oU3xBp7gYSJnMXJk8oCwCDArz5Diji4OcqQwNLp/ws7K69Xz4Mdwo1qJ9yWL+khV1PQdGoZAA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'kGsHKu2gU7GWQ0VuY97SM2QNLZE=',
                                                                                      'timestamp': '2022-06-25T14:33:15.499167927Z',
                                                                                      'signature': 'YwFJanvdCXa5zptCx5Bcms3AUyCq2L2RY1u0P9dOfNCdNrK9X6NNuEnm4+JWGkm2NGu+xBYfnClZzN2+CDiZDg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '0KzHIE1xPP+ftEny1SwFRdx8E+k=',
                                                                                      'timestamp': '2022-06-25T14:33:15.561461464Z',
                                                                                      'signature': 'dwlgAKltfiq+w0frO6UTxuf8GoNONislGJH6PHMrA8jHAcf6jrROmU9fCQS7OWZSOWniU6DPV34KRdAwLhM0BA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'XXQZZsEntvZsCcyG3J5KwuKCY8c=',
                                                                                      'timestamp': '2022-06-25T14:33:15.426039987Z',
                                                                                      'signature': 'KpQ2CG0m/BQvNpvgxUglC3OM7YVBgxPB8kMz8er3c0LwOeoIP7muA090Y0H7+iFkpu4VgNrPQpK+9Hewbqj1Dg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'AAAB5EP9I35LYW4vpp307j1JqU8=',
                                                                                      'timestamp': '2022-06-25T14:33:15.409692687Z',
                                                                                      'signature': 'RX+oq64yRHCH5XeGAV9SaD4hcbHzDAqH7uOLmXVW3PsYg/H+coqju/aCbMJ0cqJuZlLv2pUgeCeiM/RKgtS7Aw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'rkVqhaXG1G+jUMPsLcsA1mE1niA=',
                                                                                      'timestamp': '2022-06-25T14:33:15.414504135Z',
                                                                                      'signature': 'zVdT1JF9KLKAiqd09gJB4FfVC1Uj+LAddB/2Si+TqjR6IlcbtzZkIkQEJWwjZy91tYinRVHjdW0YMS5jufB+DQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'Tpyzn0sfphczl0SlYAtigCZS1pw=',
                                                                                      'timestamp': '2022-06-25T14:33:15.506479149Z',
                                                                                      'signature': 'GFzodIxnoxE49o/sZaSVNHU24gFKPw4lFME7QwhN1EiyW5ZcrJRe5KEQVNttQvsdZlUWJmJFLH+qFhw7g2lCDg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'VpsJ6j2WB8Xxo43tgc7SZMeqlMs=',
                                                                                      'timestamp': '2022-06-25T14:33:15.488352363Z',
                                                                                      'signature': 'kHnkbu+HkZYNw/XTzzBEPy4PoCXv9Hyf0SHOswGcTNTodc2cc3d1B2ZQubdsdvfuP83eHIyC/nLHOsT9b6qeCA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'bFDMRLTx3DKr0pcNis7LIErM74U=',
                                                                                      'timestamp': '2022-06-25T14:33:15.398019889Z',
                                                                                      'signature': 'QRSb2jSMJh97ah8wZEfzktzrHjyt7+P229XhdmyoY/d8QRDDv2b8hUps+zsa9la2jFKOidkQYPm7UhepLQIbCQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'EI5H/BuFRvmPfqUvJUfMREl9sb8=',
                                                                                      'timestamp': '2022-06-25T14:33:15.486256979Z',
                                                                                      'signature': '3O4vmOc+yjkVHm0dY/AQOp0/vBQlRRrOrsSNfbJuHe1INYt7xONArzIdcL2NRGz9G9PBK/erCWcFW1O5Quq9Bg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'JanUUtNfEgUK3uazGTS7hcKBfXY=',
                                                                                      'timestamp': '2022-06-25T14:33:15.402422179Z',
                                                                                      'signature': 'mOscTIGuJYyUQueJ18kXnP9LkB5u+JvdZ47SUGuHFB6SRToltDOHm8W9mEOJKlD0TZZnsEnvomihRQ/pSSMmBQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'AJA3wsdWMvO/njmhHA6B6ssmLZ4=',
                                                                                      'timestamp': '2022-06-25T14:33:15.376169687Z',
                                                                                      'signature': '23YVexpNFqZhei+5xe2spT7JZXTuf1sCDn8nSarT19ERQUmx/1B2T9+WQ4VQ+l+GmvEUl74xQtqIIGm8KNvSDg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'R3NnIYyfksOtmbXXNKNGz36KMoc=',
                                                                                      'timestamp': '2022-06-25T14:33:15.524012558Z',
                                                                                      'signature': 'QeY+t1CUSX551OTUlJz2kH2pMco135gPfMtrdzD9ZBwT8E+9Wu412k8NlAL9AOnYNhPl13xmrcNQcs+yNTNZDg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'XZ6EdZSZBLvItwxCIx/BBE5A7hI=',
                                                                                      'timestamp': '2022-06-25T14:33:15.379169499Z',
                                                                                      'signature': 'W1H1dK0Iv3nUhNnqFoLavdNQ6BBt7DL8KNCuloXbX0hf91ShF4rH7jOC9FN8Xd4uuIV836x6k5Ud0bkTPFblAg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'O0nKl8SWkDMWOochUocEie3r8IA=',
                                                                                      'timestamp': '2022-06-25T14:33:15.405726258Z',
                                                                                      'signature': 'NjTERBBw/55aVVg6xMPLbWEIyiJpSqPr47TKRVRrWWaUTdKVgyI9VQxERX0DWEojaJv4jeXte8CUzSmzm8ROAA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'LNajUj9dYVc+8eNlS0Ia0hHP6Nw=',
                                                                                      'timestamp': '2022-06-25T14:33:15.513608609Z',
                                                                                      'signature': '35yAAuEJxpy9zCJ2jjzOXq/3WKGkvyfLytdDW8uAVLcp8BxUbHvlYff2DekqXrj1HeE/vvnhwmqjpJjv9vQsDA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'sjNtyGp0pvhVLX9oasCYPvTgsM4=',
                                                                                      'timestamp': '2022-06-25T14:33:15.515821215Z',
                                                                                      'signature': '+Qk4VDbWbIPSF6rT0oY+2shiQ74rDhHzCYxxpGrL7nHryIeg1DUh/JTCXbeyDRwGu6tZeRHav1qpxjZTVhUZBA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'Fi2+6idmryfhNjtYOi+BWHdN+m8=',
                                                                                      'timestamp': '2022-06-25T14:33:15.540321053Z',
                                                                                      'signature': 'qkG+qZ1cj5f7uK2sWnxz6MnOcar2QLXYcCEfCsBsmWFx9gsQQtlaqC5ePIYcYy7+cI94TMnqUlrPjisOnUowBw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'CPHcOcmWYTC5YI64wjT6IXQ2H6I=',
                                                                                      'timestamp': '2022-06-25T14:33:15.456492561Z',
                                                                                      'signature': 'tfvSKBZj0oI6tP/Qbf5mKhiLnOH0bVB00Hms5xXE2JK56yUYn0wwF126e1W4tNbW6wbJIxnj5ovkAojoihP2BQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'v+9uLVHcfV4B0h/LSF1sPehbM3A=',
                                                                                      'timestamp': '2022-06-25T14:33:15.338511427Z',
                                                                                      'signature': 'ba5MIOp4aAfWseXebzA25Y0u+luJRCDkDRufkJ/SH2HjRnpzA9flb0LmM+Utvlp0yda7G0JgNTv0sjz+XzTMAw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'ZXGWoFt+znfMK5ak72vUXU4v1cU=',
                                                                                      'timestamp': '2022-06-25T14:33:15.533699638Z',
                                                                                      'signature': '0BYJubGKYLIPsGaoo8WZ1LHjQCyImlS+PiMEcJHZXuAj4lVyB/NZYdbDVrk9KNi7cdzMr/H/BRKpnfA2fn1KDw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'AkY0zpe4/D9saWS5UEKVyHvTNPg=',
                                                                                      'timestamp': '2022-06-25T14:33:15.455213486Z',
                                                                                      'signature': 'tqOit6j8GlFar0q1Kv4a6/MUX9SkfBdpzzcxrwuFvr+65QQ82dg+aAdbl/YCMIVCB8unk13Nl7ndHgdb/lPDAg=='}]}}}
        # Invalid tx
        api_response_2 = {'tx': {'body': {'messages': [
            {'@type': '/cosmos.bank.v1beta1.MsgSend', 'from_address': 'cosmos1a00cyvncn74nfxcq09elyy3mr67fctqx0lawj8',
             'to_address': 'cosmos14ztcmt742la63mda4zdmfd7qdtz2su0sf45mg7',
             'amount': [{'denom': 'uatom', 'amount': '15000'}]}], 'memo': '', 'timeout_height': '0',
            'extension_options': [], 'non_critical_extension_options': []}, 'auth_info': {
            'signer_infos': [{'public_key': {'@type': '/cosmos.crypto.secp256k1.PubKey',
                                             'key': 'A54Pd2GgW5epIrwDrIb6qKTesy85IK4JHkGSQOS1LSSN'},
                              'mode_info': {'single': {'mode': 'SIGN_MODE_LEGACY_AMINO_JSON'}}, 'sequence': '828'}],
            'fee': {'amount': [{'denom': 'uatom', 'amount': '800'}], 'gas_limit': '80000', 'payer': '', 'granter': ''}},
            'signatures': [
                'jdlLzYrsEDV6liOm/warySQPnRO1MKCehyflLtvv6hQjl6zrcDqh5Std7QCLhEmG71Xx68j22fm2lyuVpu3CpQ==']},
            'tx_response': {'height': '10751218',
                            'txhash': 'E1BE680AEA75EF5EEE7B36419C3E829A5BD90C0DDCF85225F8F27900B347961C',
                            'codespace': '', 'code': 0,
                            'data': '0A1E0A1C2F636F736D6F732E62616E6B2E763162657461312E4D736753656E64',
                            'raw_log': '[{"events":[{"type":"coin_received","attributes":[{"key":"receiver","value":"cosmos14ztcmt742la63mda4zdmfd7qdtz2su0sf45mg7"},{"key":"amount","value":"15000uatom"}]},{"type":"coin_spent","attributes":[{"key":"spender","value":"cosmos1a00cyvncn74nfxcq09elyy3mr67fctqx0lawj8"},{"key":"amount","value":"15000uatom"}]},{"type":"message","attributes":[{"key":"action","value":"/cosmos.bank.v1beta1.MsgSend"},{"key":"sender","value":"cosmos1a00cyvncn74nfxcq09elyy3mr67fctqx0lawj8"},{"key":"module","value":"bank"}]},{"type":"transfer","attributes":[{"key":"recipient","value":"cosmos14ztcmt742la63mda4zdmfd7qdtz2su0sf45mg7"},{"key":"sender","value":"cosmos1a00cyvncn74nfxcq09elyy3mr67fctqx0lawj8"},{"key":"amount","value":"15000uatom"}]}]}]',
                            'logs': [{'msg_index': 0, 'log': '', 'events': [{'type': 'coin_received',
                                                                             'attributes': [
                                                                                 {'key': 'receiver',
                                                                                  'value': 'cosmos14ztcmt742la63mda4zdmfd7qdtz2su0sf45mg7'},
                                                                                 {'key': 'amount',
                                                                                  'value': '15000uatom'}]},
                                                                            {'type': 'coin_spent',
                                                                             'attributes': [
                                                                                 {'key': 'spender',
                                                                                  'value': 'cosmos1a00cyvncn74nfxcq09elyy3mr67fctqx0lawj8'},
                                                                                 {'key': 'amount',
                                                                                  'value': '15000uatom'}]},
                                                                            {'type': 'message',
                                                                             'attributes': [
                                                                                 {'key': 'action',
                                                                                  'value': '/cosmos.bank.v1beta1.MsgSend'},
                                                                                 {'key': 'sender',
                                                                                  'value': 'cosmos1a00cyvncn74nfxcq09elyy3mr67fctqx0lawj8'},
                                                                                 {'key': 'module',
                                                                                  'value': 'bank'}]},
                                                                            {'type': 'transfer',
                                                                             'attributes': [
                                                                                 {'key': 'recipient',
                                                                                  'value': 'cosmos14ztcmt742la63mda4zdmfd7qdtz2su0sf45mg7'},
                                                                                 {'key': 'sender',
                                                                                  'value': 'cosmos1a00cyvncn74nfxcq09elyy3mr67fctqx0lawj8'},
                                                                                 {'key': 'amount',
                                                                                  'value': '15000uatom'}]}]}],
                            'info': '', 'gas_wanted': '80000', 'gas_used': '67275',
                            'tx': {'@type': '/cosmos.tx.v1beta1.Tx', 'body': {'messages': [
                                {'@type': '/cosmos.bank.v1beta1.MsgSend',
                                 'from_address': 'cosmos1a00cyvncn74nfxcq09elyy3mr67fctqx0lawj8',
                                 'to_address': 'cosmos14ztcmt742la63mda4zdmfd7qdtz2su0sf45mg7',
                                 'amount': [{'denom': 'uatom', 'amount': '15000'}]}], 'memo': '',
                                'timeout_height': '0',
                                'extension_options': [],
                                'non_critical_extension_options': []},
                                   'auth_info': {'signer_infos': [{'public_key': {
                                       '@type': '/cosmos.crypto.secp256k1.PubKey',
                                       'key': 'A54Pd2GgW5epIrwDrIb6qKTesy85IK4JHkGSQOS1LSSN'},
                                       'mode_info': {'single': {
                                           'mode': 'SIGN_MODE_LEGACY_AMINO_JSON'}},
                                       'sequence': '828'}],
                                       'fee': {'amount': [{'denom': 'uatom', 'amount': '800'}],
                                               'gas_limit': '80000', 'payer': '',
                                               'granter': ''}}, 'signatures': [
                                    'jdlLzYrsEDV6liOm/warySQPnRO1MKCehyflLtvv6hQjl6zrcDqh5Std7QCLhEmG71Xx68j22fm2lyuVpu3CpQ==']},
                            'timestamp': '2022-06-04T12:19:59Z', 'events': [{'type': 'coin_spent',
                                                                             'attributes': [
                                                                                 {'key': 'c3BlbmRlcg==',
                                                                                  'value': 'Y29zbW9zMWEwMGN5dm5jbjc0bmZ4Y3EwOWVseXkzbXI2N2ZjdHF4MGxhd2o4',
                                                                                  'index': True},
                                                                                 {'key': 'YW1vdW50',
                                                                                  'value': 'ODAwdWF0b20=',
                                                                                  'index': True}]},
                                                                            {'type': 'coin_received',
                                                                             'attributes': [
                                                                                 {'key': 'cmVjZWl2ZXI=',
                                                                                  'value': 'Y29zbW9zMTd4cGZ2YWttMmFtZzk2MnlsczZmODR6M2tlbGw4YzVsc2VycXRh',
                                                                                  'index': True},
                                                                                 {'key': 'YW1vdW50',
                                                                                  'value': 'ODAwdWF0b20=',
                                                                                  'index': True}]},
                                                                            {'type': 'transfer',
                                                                             'attributes': [
                                                                                 {'key': 'cmVjaXBpZW50',
                                                                                  'value': 'Y29zbW9zMTd4cGZ2YWttMmFtZzk2MnlsczZmODR6M2tlbGw4YzVsc2VycXRh',
                                                                                  'index': True},
                                                                                 {'key': 'c2VuZGVy',
                                                                                  'value': 'Y29zbW9zMWEwMGN5dm5jbjc0bmZ4Y3EwOWVseXkzbXI2N2ZjdHF4MGxhd2o4',
                                                                                  'index': True},
                                                                                 {'key': 'YW1vdW50',
                                                                                  'value': 'ODAwdWF0b20=',
                                                                                  'index': True}]},
                                                                            {'type': 'message',
                                                                             'attributes': [
                                                                                 {'key': 'c2VuZGVy',
                                                                                  'value': 'Y29zbW9zMWEwMGN5dm5jbjc0bmZ4Y3EwOWVseXkzbXI2N2ZjdHF4MGxhd2o4',
                                                                                  'index': True}]},
                                                                            {'type': 'tx', 'attributes': [
                                                                                {'key': 'ZmVl',
                                                                                 'value': 'ODAwdWF0b20=',
                                                                                 'index': True}]},
                                                                            {'type': 'tx', 'attributes': [
                                                                                {'key': 'YWNjX3NlcQ==',
                                                                                 'value': 'Y29zbW9zMWEwMGN5dm5jbjc0bmZ4Y3EwOWVseXkzbXI2N2ZjdHF4MGxhd2o4LzgyOA==',
                                                                                 'index': True}]},
                                                                            {'type': 'tx', 'attributes': [
                                                                                {'key': 'c2lnbmF0dXJl',
                                                                                 'value': 'amRsTHpZcnNFRFY2bGlPbS93YXJ5U1FQblJPMU1LQ2VoeWZsTHR2djZoUWpsNnpyY0RxaDVTdGQ3UUNMaEVtRzcxWHg2OGoyMmZtMmx5dVZwdTNDcFE9PQ==',
                                                                                 'index': True}]},
                                                                            {'type': 'message',
                                                                             'attributes': [
                                                                                 {'key': 'YWN0aW9u',
                                                                                  'value': 'L2Nvc21vcy5iYW5rLnYxYmV0YTEuTXNnU2VuZA==',
                                                                                  'index': True}]},
                                                                            {'type': 'coin_spent',
                                                                             'attributes': [
                                                                                 {'key': 'c3BlbmRlcg==',
                                                                                  'value': 'Y29zbW9zMWEwMGN5dm5jbjc0bmZ4Y3EwOWVseXkzbXI2N2ZjdHF4MGxhd2o4',
                                                                                  'index': True},
                                                                                 {'key': 'YW1vdW50',
                                                                                  'value': 'MTUwMDB1YXRvbQ==',
                                                                                  'index': True}]},
                                                                            {'type': 'coin_received',
                                                                             'attributes': [
                                                                                 {'key': 'cmVjZWl2ZXI=',
                                                                                  'value': 'Y29zbW9zMTR6dGNtdDc0MmxhNjNtZGE0emRtZmQ3cWR0ejJzdTBzZjQ1bWc3',
                                                                                  'index': True},
                                                                                 {'key': 'YW1vdW50',
                                                                                  'value': 'MTUwMDB1YXRvbQ==',
                                                                                  'index': True}]},
                                                                            {'type': 'transfer',
                                                                             'attributes': [
                                                                                 {'key': 'cmVjaXBpZW50',
                                                                                  'value': 'Y29zbW9zMTR6dGNtdDc0MmxhNjNtZGE0emRtZmQ3cWR0ejJzdTBzZjQ1bWc3',
                                                                                  'index': True},
                                                                                 {'key': 'c2VuZGVy',
                                                                                  'value': 'Y29zbW9zMWEwMGN5dm5jbjc0bmZ4Y3EwOWVseXkzbXI2N2ZjdHF4MGxhd2o4',
                                                                                  'index': True},
                                                                                 {'key': 'YW1vdW50',
                                                                                  'value': 'MTUwMDB1YXRvbQ==',
                                                                                  'index': True}]},
                                                                            {'type': 'message',
                                                                             'attributes': [
                                                                                 {'key': 'c2VuZGVy',
                                                                                  'value': 'Y29zbW9zMWEwMGN5dm5jbjc0bmZ4Y3EwOWVseXkzbXI2N2ZjdHF4MGxhd2o4',
                                                                                  'index': True}]},
                                                                            {'type': 'message',
                                                                             'attributes': [
                                                                                 {'key': 'bW9kdWxl',
                                                                                  'value': 'YmFuaw==',
                                                                                  'index': True}]}]}}
        tx_info_2 = {'E1BE680AEA75EF5EEE7B36419C3E829A5BD90C0DDCF85225F8F27900B347961C': {'success': False}}

        # Failed tx
        api_response_3 = {'tx': {'body': {'messages': [
            {'@type': '/cosmos.bank.v1beta1.MsgSend', 'from_address': 'cosmos1mt023tryqjmxn4esgsn8npnr7sfj3s4wqnl83t',
             'to_address': 'cosmos1j8pp7zvcu9z8vd882m284j29fn2dszh05cqvf9',
             'amount': [{'denom': 'uatom', 'amount': '100021352'}]}], 'memo': '101715363', 'timeout_height': '0',
            'extension_options': [], 'non_critical_extension_options': []}, 'auth_info': {
            'signer_infos': [{'public_key': {'@type': '/cosmos.crypto.secp256k1.PubKey',
                                             'key': 'A6JYq8wKdrICK3oBoAjsCK04XWSPUwrwmBpHvLLp7CKo'},
                              'mode_info': {'single': {'mode': 'SIGN_MODE_LEGACY_AMINO_JSON'}}, 'sequence': '9'}],
            'fee': {'amount': [{'denom': 'uatom', 'amount': '6250'}], 'gas_limit': '250000', 'payer': '',
                    'granter': ''}}, 'signatures': [
            'buvdiJxH+aNgzQHOIk4x0z11HtHevGCdD3fl4b3TFlxcw0CwrujWxlIsA3hH6x/ctXGEluvPCDRCxeOs212VWg==']},
            'tx_response': {'height': '10890352',
                            'txhash': '18F0E55B5D758609653CAA2B8D1BC0E552C258B47714DC9AB8A3F798F9E6DA84',
                            'codespace': 'sdk', 'code': 5, 'data': '',
                            'raw_log': 'failed to execute message; message index: 0: 51553394uatom is smaller than 100021352uatom: insufficient funds',
                            'logs': [], 'info': '', 'gas_wanted': '250000', 'gas_used': '58770',
                            'tx': {'@type': '/cosmos.tx.v1beta1.Tx', 'body': {'messages': [
                                {'@type': '/cosmos.bank.v1beta1.MsgSend',
                                 'from_address': 'cosmos1mt023tryqjmxn4esgsn8npnr7sfj3s4wqnl83t',
                                 'to_address': 'cosmos1j8pp7zvcu9z8vd882m284j29fn2dszh05cqvf9',
                                 'amount': [{'denom': 'uatom', 'amount': '100021352'}]}],
                                'memo': '101715363',
                                'timeout_height': '0',
                                'extension_options': [],
                                'non_critical_extension_options': []},
                                   'auth_info': {'signer_infos': [{'public_key': {
                                       '@type': '/cosmos.crypto.secp256k1.PubKey',
                                       'key': 'A6JYq8wKdrICK3oBoAjsCK04XWSPUwrwmBpHvLLp7CKo'},
                                       'mode_info': {'single': {
                                           'mode': 'SIGN_MODE_LEGACY_AMINO_JSON'}},
                                       'sequence': '9'}],
                                       'fee': {'amount': [{'denom': 'uatom', 'amount': '6250'}],
                                               'gas_limit': '250000', 'payer': '',
                                               'granter': ''}}, 'signatures': [
                                    'buvdiJxH+aNgzQHOIk4x0z11HtHevGCdD3fl4b3TFlxcw0CwrujWxlIsA3hH6x/ctXGEluvPCDRCxeOs212VWg==']},
                            'timestamp': '2022-06-15T11:51:50Z', 'events': [{'type': 'coin_spent',
                                                                             'attributes': [
                                                                                 {'key': 'c3BlbmRlcg==',
                                                                                  'value': 'Y29zbW9zMW10MDIzdHJ5cWpteG40ZXNnc244bnBucjdzZmozczR3cW5sODN0',
                                                                                  'index': False},
                                                                                 {'key': 'YW1vdW50',
                                                                                  'value': 'NjI1MHVhdG9t',
                                                                                  'index': False}]},
                                                                            {'type': 'coin_received',
                                                                             'attributes': [
                                                                                 {'key': 'cmVjZWl2ZXI=',
                                                                                  'value': 'Y29zbW9zMTd4cGZ2YWttMmFtZzk2MnlsczZmODR6M2tlbGw4YzVsc2VycXRh',
                                                                                  'index': False},
                                                                                 {'key': 'YW1vdW50',
                                                                                  'value': 'NjI1MHVhdG9t',
                                                                                  'index': False}]},
                                                                            {'type': 'transfer',
                                                                             'attributes': [
                                                                                 {'key': 'cmVjaXBpZW50',
                                                                                  'value': 'Y29zbW9zMTd4cGZ2YWttMmFtZzk2MnlsczZmODR6M2tlbGw4YzVsc2VycXRh',
                                                                                  'index': False},
                                                                                 {'key': 'c2VuZGVy',
                                                                                  'value': 'Y29zbW9zMW10MDIzdHJ5cWpteG40ZXNnc244bnBucjdzZmozczR3cW5sODN0',
                                                                                  'index': False},
                                                                                 {'key': 'YW1vdW50',
                                                                                  'value': 'NjI1MHVhdG9t',
                                                                                  'index': False}]},
                                                                            {'type': 'message',
                                                                             'attributes': [
                                                                                 {'key': 'c2VuZGVy',
                                                                                  'value': 'Y29zbW9zMW10MDIzdHJ5cWpteG40ZXNnc244bnBucjdzZmozczR3cW5sODN0',
                                                                                  'index': False}]},
                                                                            {'type': 'tx', 'attributes': [
                                                                                {'key': 'ZmVl',
                                                                                 'value': 'NjI1MHVhdG9t',
                                                                                 'index': False}]},
                                                                            {'type': 'tx', 'attributes': [
                                                                                {'key': 'YWNjX3NlcQ==',
                                                                                 'value': 'Y29zbW9zMW10MDIzdHJ5cWpteG40ZXNnc244bnBucjdzZmozczR3cW5sODN0Lzk=',
                                                                                 'index': False}]},
                                                                            {'type': 'tx', 'attributes': [
                                                                                {'key': 'c2lnbmF0dXJl',
                                                                                 'value': 'YnV2ZGlKeEgrYU5nelFIT0lrNHgwejExSHRIZXZHQ2REM2ZsNGIzVEZseGN3MEN3cnVqV3hsSXNBM2hINngvY3RYR0VsdXZQQ0RSQ3hlT3MyMTJWV2c9PQ==',
                                                                                 'index': False}]}]}}
        tx_info_3 = {'18F0E55B5D758609653CAA2B8D1BC0E552C258B47714DC9AB8A3F798F9E6DA84': {'success': False}}
        block_head = {'block_id': {'hash': 'kX5+xzP5Kdr+Sj9nOW7dBjhe1wXzMkyesHSl0YHZwMw=',
                                   'part_set_header': {'total': 1,
                                                       'hash': 'TVFNwKDSn9gQlMvPp6w26ecP+3Btm0aLD4/upmme9HU='}},
                      'block': {'header': {'version': {'block': '11', 'app': '0'}, 'chain_id': 'cosmoshub-4',
                                           'height': '11018491', 'time': '2022-06-25T14:33:15.464747871Z',
                                           'last_block_id': {'hash': 'bdxTM+8JhyHDqM8cM4TZxeeWeMZyY5vkeLAXluAUYCs=',
                                                             'part_set_header': {'total': 1,
                                                                                 'hash': '0Smon/IvB6nSoKMWqwZn5Mpvd89DlnKLK+6SZE2vwcA='}},
                                           'last_commit_hash': 'Z60nEPGnFOFKwu8co5wgGr13afaaZNgIYPJuRcRikl0=',
                                           'data_hash': 'DLOd4emJex6/tw9pWZTwNzJ/sU6ur+eojFQ1sYa9Dyo=',
                                           'validators_hash': '5gG8+sygfV2D8MTyMG8PT2UP/Uowd5m6oZPEjai8afQ=',
                                           'next_validators_hash': 'tq271IPBhS8isM+1nx2S50JKMAMcGhz5lQPcfT6X6ks=',
                                           'consensus_hash': 'gDZJZbfCzJ3pYcCZi0en+T8ZcAd+uILg7Rw4IkCIiMc=',
                                           'app_hash': 'lSva1Qb6ztOd5cAxJ0GMOUywywO6Ktv68rbWo5NMP6E=',
                                           'last_results_hash': 'm2NnqaEF9KW5n6IzjOb6AhI6pYvsR5pf+osB5AgUXwE=',
                                           'evidence_hash': '47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU=',
                                           'proposer_address': 'MZIPm8Ojm2aHbMfW1eWJ4QOTvw4='}, 'data': {'txs': [
                          'CqMBCqABCjcvY29zbW9zLmRpc3RyaWJ1dGlvbi52MWJldGExLk1zZ1dpdGhkcmF3RGVsZWdhdG9yUmV3YXJkEmUKLWNvc21vczFsOGEzbXR1NmpyOTJleWVxeGEwYWRmbXB6ejh4ajllMmNybm5yahI0Y29zbW9zdmFsb3BlcjFxYWE5emVqOWEwZ2UzdWdweDNweHl4NjAybHhoM3p0cWdmbnA0MhJnClAKRgofL2Nvc21vcy5jcnlwdG8uc2VjcDI1NmsxLlB1YktleRIjCiEC67ocWoF6P4gn/RNBWmwvhhP/pWbJSC3lhr/yhvX0WWMSBAoCCH8YCBITCg0KBXVhdG9tEgQxNDAwEODFCBpATnf0aB9L8X8fU1mZMB+gbYQyCt8S7j0dGdWmjFrIHJAmg/FYOXjUJO9ZdH5XCl8kcRGhVcy7LeiRULq09mDa9w==',
                          'CsIBCpABChwvY29zbW9zLmJhbmsudjFiZXRhMS5Nc2dTZW5kEnAKLWNvc21vczE4bGQ0NjMzeXN3Y3lqZGtsZWozYXR0NmF3OTNuaGxmN2NlNHY4dRItY29zbW9zMWRucHI0MzZ0azh4ajZlNGR3N3N4cnA1ejVjMmRyOGw4bDh5eXgyGhAKBXVhdG9tEgc0OTk1MDAwEi1jb3Ntb3MxZG5wcjQzNnRrOHhqNmU0ZHc3c3hycDV6NWMyZHI4bDhsOHl5eDISaQpSCkYKHy9jb3Ntb3MuY3J5cHRvLnNlY3AyNTZrMS5QdWJLZXkSIwohAwOIzyLogx43PHjUlwouHN0DemeqKKo34+4HEmADh7ejEgQKAggBGP/CBhITCg0KBXVhdG9tEgQzMDAwEOCnEhpA3eT2oomIh9VbubEgvRNeVL1PG+xzJv3o5QwTej1r0ONx/eSM5NP7QUvKqgD+EsWg9Ha0MicfZgUbiZxoyjL0CA==']},
                                'evidence': {'evidence': []}, 'last_commit': {'height': '11018490', 'round': 0,
                                                                              'block_id': {
                                                                                  'hash': 'bdxTM+8JhyHDqM8cM4TZxeeWeMZyY5vkeLAXluAUYCs=',
                                                                                  'part_set_header': {'total': 1,
                                                                                                      'hash': '0Smon/IvB6nSoKMWqwZn5Mpvd89DlnKLK+6SZE2vwcA='}},
                                                                              'signatures': [{
                                                                                  'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                  'validator_address': 'rC1WBXzYR2Xm++MYl5CT6ORKoY8=',
                                                                                  'timestamp': '2022-06-25T14:33:15.464747871Z',
                                                                                  'signature': 'OsQovaC+ZaeExBM4srfl2Ivq/JYud+yt5JozMiu9QPjNVRHdM+dnITQX08lrf2oV04vLOlItERu/v+0uLeOPCQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'g/R9d0ew9jOmug30m33PYfkKobA=',
                                                                                      'timestamp': '2022-06-25T14:33:15.588053263Z',
                                                                                      'signature': 'w7bLLgfQK2/HgfG3tDmaia1HHBtzbKUlsT0tKY1s5jkOK+nw+KCx2ecaBE6E2yiejRTRDa5eXjxtvzxR9uDfAQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'IZnq6JTKOR+oLwHCxhS/6xA9BWw=',
                                                                                      'timestamp': '2022-06-25T14:33:15.437036750Z',
                                                                                      'signature': '3DH38srtz/KMzgAlnnC4pTutUMDJSYO3L/QofH/ZUzvK6wpeyBK1E0VW06A9P+8pfDSkomBNjtNBAQVnH1SACQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '0tRY+SCey4yiqrHZngZhG4Eqh5c=',
                                                                                      'timestamp': '2022-06-25T14:33:13.877067496Z',
                                                                                      'signature': 'SN+2QhXnp71sh4NStx1TOSucHdSZdbLkuATeEA79hQiiG9LgnhIKDU7q9sjrg6xv20fO42n9uFE/h/PzjkIxCQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'bXAfpZUyaI3xa6+VIRN+jBTLsxY=',
                                                                                      'timestamp': '2022-06-25T14:33:15.654691994Z',
                                                                                      'signature': 'mUZmE1N0shsnz5h7PeNGP0aU4q7v5/evSUfeKLVP6Te7lMCenujwgBHUOz+ILml2gBBa2LRkU0HYduGfUm4ABw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '7VCeeAl+EwapH+3o6Ft10Gvd9uM=',
                                                                                      'timestamp': '2022-06-25T14:33:15.417234860Z',
                                                                                      'signature': 'PY8at2ZhbhvgMCeMGogRQwoyMnxxLDCacbyCQT0+LrAgKSxPDr/+4N85Q4jmL48J3zO8ZC/PUTUjhacGoVI2Dw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '9Zc0qJanaJQ2vDQiJE/YYq4YnFw=',
                                                                                      'timestamp': '2022-06-25T14:33:15.582647490Z',
                                                                                      'signature': 'NvCrBboiZ2d70b2v3AMNv+ouX83a/ZVGTbYBjqfRJ4M3rCHkJ5ZBrLJmAcA7y6H1gq+Y48tJVPIHR7dfPacICQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'aPJweVkNysw6wcSJKhoAjzSPWW8=',
                                                                                      'timestamp': '2022-06-25T14:33:15.473954232Z',
                                                                                      'signature': 'uzpc0jQWmgkwaC6TRh7+B6gWFseZ07yaQyq9rXiphYzEqiD5pCT+TZrzO0iut/DNEyjUesSbHv7Oowpbh3n6AA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'Z5uJeFlzvpTU/fi2b4SpKZMukcU=',
                                                                                      'timestamp': '2022-06-25T14:33:15.400053633Z',
                                                                                      'signature': 'qdY/KhCWpCHoNATrs3Uo/Ci6OUWyGldbAJ8xwzyxs5951Ig/kMcPXxLc7IilhLETVZIH6fcWrn1XOkJyd7zNCw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'sRZ9BDfbnfDVM+4qzeSBBxOb3S4=',
                                                                                      'timestamp': '2022-06-25T14:33:15.386680954Z',
                                                                                      'signature': 'zHLKGXtjbjFb474au/M5xH8H+LYGqhufU8wVEdGLWLWpjQ9JCr3E7a4x08VAiqs010lb1lm2AdWlQUlwCeyaDQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'HO0wcz0WJciatphndgbQ43s2dqk=',
                                                                                      'timestamp': '2022-06-25T14:33:15.399683707Z',
                                                                                      'signature': 'iC4Rm5RMHJS+5ZG/Ba1vdTCCEsdqd7GE3vMLX2f5nsbdnI9c5q8A0xcnoemeEk2DentXPMhEtH29uGpNbyYsAQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '+MAcBoFXiqcA1zbWdcmZIGX2Xj4=',
                                                                                      'timestamp': '2022-06-25T14:33:15.382382673Z',
                                                                                      'signature': 'NyS6HabXhqwKMDq8rHmLoElnvhK74GaubiV68ldIi5LEZjMor+oDQkj2CgQUiKvpGB7NaCGZaWA410YhYS/mDg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'USBWWacX3/uW4FT4vREIcw4Xrqc=',
                                                                                      'timestamp': '2022-06-25T14:33:15.528753863Z',
                                                                                      'signature': 'oIF2e7FsxmwSngCw8yq7jeh/nYTHzWSTBhWRt9MHVziDGbFcLFFzJzjCesvf6S39lCjt8b3ld8bA6wwjXp51DA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '1o7sDS6CSPHsZM21he22HspDK9g=',
                                                                                      'timestamp': '2022-06-25T14:33:15.463044888Z',
                                                                                      'signature': 'L1+OQ5weUHVVKgr9OuEwSlwpTPtXAnExg2lR/8YJF+BTxD8UUgC/AyOyv5KA3fjNwJJCEln7HpzBHbY83JAmDg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'CZ4rCVgzMa/eNeX6lmc9LKfeoxY=',
                                                                                      'timestamp': '2022-06-25T14:33:15.459847995Z',
                                                                                      'signature': 'th8crqI9q8Fm737Dk0xwEuHCx7uo4DliNZkJJNluzMQ+F4xAGddiCb69/mK1VaHDKOpA6bDx8SuBGQYz5agXDw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '2mqqqVnJ74ij6zex8QfLJmfruqs=',
                                                                                      'timestamp': '2022-06-25T14:33:15.490084262Z',
                                                                                      'signature': 'K1FvJsTL0OaxyjfLIM/2G05AAUjoCxrYjJIZsVkVXL0nA2kQtshcfNs0aH39N/zj4vTPbrESAmBFGbwDGptgBw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'MZIPm8Ojm2aHbMfW1eWJ4QOTvw4=',
                                                                                      'timestamp': '2022-06-25T14:33:15.392536568Z',
                                                                                      'signature': 'Ra55LYaRwwsUBXH/ef6q9dLl2lO1BM85CyUZu1tZlxHNvcv52oSIL7WZL7gShTQICZzg+PzTUPOFShuPK7dZAA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'TrEoJnX3JLWQJvIXPCPw3Jk28Rg=',
                                                                                      'timestamp': '2022-06-25T14:33:15.615152778Z',
                                                                                      'signature': 'LNB8YDPBHnqiLnsN3GmkUZIWcnWp1I2L90xXIYLY6dHFbjUz3nMJoD/upL6kY49MyB061xSHjsTUfYHJIgz+CA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'sApjI3N/Mh6wuNWcb9SXoUtgk4o=',
                                                                                      'timestamp': '2022-06-25T14:33:15.401897239Z',
                                                                                      'signature': 'OicAdHTiRsRqqBjVDPwm4HMaooGsBWfrrNdtl4kcFVH5AGlNM/7QLxdxQyOgPjKmlzSl2Epw5ebbdJvDRTQ/Cw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'AZucopRNPMNsfHMoPvPVjlbIpdQ=',
                                                                                      'timestamp': '2022-06-25T14:33:15.546766402Z',
                                                                                      'signature': 'TGaBcca47ZAZI6ctpcQ1PgDpnNMBPYnuB673S6I2Op9z2i5q/P6OG5uZhx7/oueK8gY792q3vDSByM+qIe7ECA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '2fikG3gqpqZq3IH5U5I8fc57YAE=',
                                                                                      'timestamp': '2022-06-25T14:33:15.399848810Z',
                                                                                      'signature': 'FTSj6VY14NYAUKVwlBVvJxW6PfLblvsmclFSUMSPn0XQfvnfqtmcPPNpm69CzuwCNdVVSdB2n23q6jafey6+Dg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'nBfJT3MTu01uBkKHvu3l04iOiFU=',
                                                                                      'timestamp': '2022-06-25T14:33:15.496112278Z',
                                                                                      'signature': 'whnuGq/U3gxnOgY1E8ssBpgPnxVfW6lBVRFbKN21A7DJ4zew91P+5SeF2WY6G0GfPe7+rUe3EnxivMaZGlX1Cg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'Wlnch0b9cn/d1cv1y7kMb2Fsz5s=',
                                                                                      'timestamp': '2022-06-25T14:33:15.465185065Z',
                                                                                      'signature': 'dFkNKMUSa372KV0vJk04lCvxHqIyw3RxlOPi+6p4mR/jobZFlFpOJZrH/wZnGgzjyytKx342+YLS6iHE+6rTDw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'ZxRgkwzNybBsXQVeTVUOuNryKR4=',
                                                                                      'timestamp': '2022-06-25T14:33:15.549899112Z',
                                                                                      'signature': 'yNDND2BaArwHh9Bay/Sf9XosNKybB86Bii/Xior4rSIloLRdNDqMVrWJRdTkUoBqIw9PAW71oRuNPZwEhmBlAQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '6Dv8Q20s6NzJ7AWJsuW3NeN/uFw=',
                                                                                      'timestamp': '2022-06-25T14:33:15.389943902Z',
                                                                                      'signature': 'WFkNtunRNc3MIwS/XRJAVnEu7X0hYqN+NMjqXInqfS5LTJWJKpHCH/royQs2guIrr9ZgWDkbagsYt34jpCyyAA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'gZZf6KFfqAeMkgLzLkz6cvhfKiI=',
                                                                                      'timestamp': '2022-06-25T14:33:15.484266007Z',
                                                                                      'signature': 'mTasah2qNIHNV5W3Yr5Z8GWFlPSrtTy/HWhepa/tDoRBiYDfZ8uJlAnAW/w4mhwuOVAPzbrCfAu0IcHAfNBNDA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'UdslZiBO4mZCfqimy3GYNasXC+k=',
                                                                                      'timestamp': '2022-06-25T14:33:15.410331676Z',
                                                                                      'signature': 'ysWPY0I/1Nr32/KCZ7LkNVugEqQBKwzlm0EUTfzKyRStbDxkByQkZf2UGr49HDyOsKL2CVxZLhtNvhH2BJ+tCQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'ddqzFvTKE2f1MqtxqAt/plq2kDk=',
                                                                                      'timestamp': '2022-06-25T14:33:15.590536898Z',
                                                                                      'signature': 'ExYQydFSnP75pqlYUDw/8DgjwvhLjkvr14WmZwxSLbPKl5g0wEH0OPn5BvhUfsvtn66TcSJkzH+2bSiolMQUCA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'leBg0HcTBw/pgi9sUL12vMv58Xo=',
                                                                                      'timestamp': '2022-06-25T14:33:18.125568711Z',
                                                                                      'signature': '6XLF5uiYz1KZe4t/AkyCkqxoGStF1AnRMFBAC8DcNa35EWjQ3Cjam/uDRDpXwJaXnMX8PjBLRdl9LQ3xQ0MNCQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'ppNdh3uXdsRblu6uUmlZo7mlqxo=',
                                                                                      'timestamp': '2022-06-25T14:33:15.631517915Z',
                                                                                      'signature': 'FmXMGzpv+77UHKqy2sC1UpnS72nD8MiGvF27jYhyKKuqV2XYeeFcVOeWiviiBJA+Ox4dhcKPvQSOsuPN6VgzAw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'zAWIKXj8X91qdyFofhTAKZrgBLg=',
                                                                                      'timestamp': '2022-06-25T14:33:15.465267996Z',
                                                                                      'signature': 'uqk2BO+UUH/V4n0P2gcHzGBCuVny1zKjNMb9GU2PA6YJsMtSEaZyHyLA5LdItuQ91i9K+v99xsw8Whtthe80Dg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '/V1U4Nnkdo/qTA3/3In6lrZlfzI=',
                                                                                      'timestamp': '2022-06-25T14:33:15.369445240Z',
                                                                                      'signature': 'eswYVxIHy21S+BmE93q+eFQk40j6AS3YzNCO7jz9DPEC9VKPwP4xUSLIJXuhhI08OsGysRrgEgBTKkkf3PwsAw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'V3E7t0Icf+s4G4Y/yH3tXoKaqWE=',
                                                                                      'timestamp': '2022-06-25T14:33:15.453300929Z',
                                                                                      'signature': 'ClvYQYJYbannRymF8y+UDXt1PAqsJAp73MDaipUTtx1NxlYi2q1ciy6nmqwDa3/yOxvxm4qnKD3XhKMDd5O7DA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '6AB0DGjIGzA0XDriumOPpW/2fu8=',
                                                                                      'timestamp': '2022-06-25T14:33:15.482564456Z',
                                                                                      'signature': 'VEujogdZhpUiFQxY2X0XVCrNmEg8W0BfDmrn2mjidqFebw+cUkuJFE6J97nXnLehKX1aDRbezCn1GomQ7BL4Bw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '0UpULodWw6lC2f2Ic9wumneYoX8=',
                                                                                      'timestamp': '2022-06-25T14:33:15.520989623Z',
                                                                                      'signature': '4ouhpPduv6o8UPZfJm3jmEPepzE/t3jk7buUFsGKCIvQawhVi4KtBF70iJi5HuUBbqiflRCHCYj4thch0PZuAQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'ezou/ls/zfgZ/PUmBzFM7+R1S7Y=',
                                                                                      'timestamp': '2022-06-25T14:33:15.562889288Z',
                                                                                      'signature': 'Lxba4+VJ9SLBqrUUVIquVCN3bkBNjpcnWoCOHGO6Nn69bVOlLuwU4dokF0ABfekHiBViYPUVplV8Nz+vP6/mBg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'aWq8lRhv1loHBQwoqwDJNYoxUDA=',
                                                                                      'timestamp': '2022-06-25T14:33:15.583474315Z',
                                                                                      'signature': 'LRtZkLMYkUnWZB7AXwtxvtM3PVc5aug7fgQuFVoNbxLH/+4JXKsGneYHD4JoKG1KR3PzDMOGa1q7P+4Ku8bKBA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'RqP4uDk7qhU8QOVyLq6C6g1Isy0=',
                                                                                      'timestamp': '2022-06-25T14:33:15.542615739Z',
                                                                                      'signature': 'iuE1Wgstn5qtABhFIj/FNfFP8N46R8WiLb70NLZIU9qy+Z3v2xZfbNsCcMArXdpOvgQReOfBWMhrrwWFV4drCg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'zIf1a1hiGBHitaR/OMYWbilc424=',
                                                                                      'timestamp': '2022-06-25T14:33:15.422874846Z',
                                                                                      'signature': 'HdtOE5VQR16FNr0sykC6IbDjpuPg9iu8ieGdu0xce7Pzh+XTkgCLKsF7jCQELkwplkmN9gOCIqPOCGzdALCKBQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '1UCrAiCIYSrHSyh9B22/vEo3ei4=',
                                                                                      'timestamp': '2022-06-25T14:33:15.438826653Z',
                                                                                      'signature': '6+9NvMS3V/1eQVrTpc1VvFlZxL5qtsmq+meZ54VfRJzLK9oyZuOUJMxBDk+vZN9DtBkHZMlaAPgs/y1uydIzBA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '07wmsaneyNVrCjuOzSMRDsTNRac=',
                                                                                      'timestamp': '2022-06-25T14:33:15.584793810Z',
                                                                                      'signature': 'g/4Xl4mEEU1NpG4DIEvKznKpl+rtHyoymyh/7yIFA5BKleXc7fZil1j+4p2tMpEtOMrr5vAeR/BaTaoR49teCg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'C0LkfxVOJNEBhLsS4yNHqsYca4A=',
                                                                                      'timestamp': '2022-06-25T14:33:15.445447915Z',
                                                                                      'signature': 'koD3A+fJrvD+nC6zhywqRSOH+wFTA7vrftanpNjAUZbQmMEFXO6l8gPs90gEsqz+utJnzaudOwUnSv38TqxaDg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'JURdDrNT6QUKsR7GGX1dy2EZhts=',
                                                                                      'timestamp': '2022-06-25T14:33:15.391085749Z',
                                                                                      'signature': 'kHsxcT1Nca1ciSF8+AoAmJJF6fJ4X9fM24sNcff1571SAjeWWdh7Lva4Xlbz57OVJmLPeNMz1uLCmgW5Qm9jCg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'ncQBIJm+dDGJB0uF5JiRrjs/7ps=',
                                                                                      'timestamp': '2022-06-25T14:33:15.560072650Z',
                                                                                      'signature': 'uL+eMdh9q7EPDpv0k1E+zJF/PleeOUFl1CHF4v15LwYnuuLVu9UUkyG7pMGQL910gwI5bK9cpvZgOhL+HL1WCg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '4HD6TwULr36idhxSpqVxV4BoGTk=',
                                                                                      'timestamp': '2022-06-25T14:33:15.487631175Z',
                                                                                      'signature': 'Jq3JJjiJD7OEyNxnbSPK/yj4PQUGqCMbbcLRSRiLSkHusurIEa1hyrfKtxYTVc1X9MAJKEDxcwVxKb8ze+tAAw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'sBVSUtc7fut00qjMgUOX5mlwqDk=',
                                                                                      'timestamp': '2022-06-25T14:33:15.482947732Z',
                                                                                      'signature': 'd+EfUF7jW0DO648oV8RhdcSuTWcxahSSftz9DikMXxriIYnz8O/xffNNGRemjKFVxiLNGY9FdE/824bU2RqHDg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '7nOhl1HVjF7ARMEeP7euaFoQ0sE=',
                                                                                      'timestamp': '2022-06-25T14:33:15.400317032Z',
                                                                                      'signature': '4tzaXCbgUzBLD1rDgnYz+o+1T8OjYJTv1uGUCvgkPX3mAm/HRnmnW+UQkI3YQC/FjciZ9qSEE0gzsXhP/G7kDA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'usM/NA80l3UfEkho8EnsLokwrC8=',
                                                                                      'timestamp': '2022-06-25T14:33:15.534051348Z',
                                                                                      'signature': 'IMLHqvCasp1d0nkEvIzarIpKXkEfPDGj0Tin5dvhxTKmisqlr2YM6QTQLO1Snq8SO9XZGdSvQY2BCqK6oCPpAg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'tOEIXxyeuw6plEUssbgSS6ib7Ro=',
                                                                                      'timestamp': '2022-06-25T14:33:15.415348128Z',
                                                                                      'signature': '27kIYAE7J+Z2NuErKBaEhMXfN8Ywpj1aXl3DewtX5rwtywdH3IHQ/U56YSBLSsYsMirpsTOhXmAZElLdRc0GBw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'jg7je3saA43RReMPHvl982Ge9Ck=',
                                                                                      'timestamp': '2022-06-25T14:33:15.755023742Z',
                                                                                      'signature': 'ExUba2nk6FQdJo5UhQmGPOVsX5jeLf9GYTlLtYMFY6vrFtrfFqb745OLExXHeScCGvqIpcL4xnhHi2EAtdBhCw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'kcgjp0TeUPkcF6RrYk7fj3FQp90=',
                                                                                      'timestamp': '2022-06-25T14:33:15.672855297Z',
                                                                                      'signature': '100ZWzg3sqPKs0zGkB05LnAPnxxuylMf1+d+DiRZgOEOnfKczvj9YtDKyxScktMN8MAgjEM0/4MnIvMHtK3BAg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'ez0B91Tf+EdO0ONYgS/UN+CTidw=',
                                                                                      'timestamp': '2022-06-25T14:33:15.418296387Z',
                                                                                      'signature': 'u9DoS3ds1mwvNZ2obDzu5MTn6PgQCpErrHj2c4S+TdFCK8wE0i9Lu6oZUkQys6cNPDaFI1jqg3USu8EuLGMuCA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '4KEmUlnOnHj3ayEZaATxspRtsmo=',
                                                                                      'timestamp': '2022-06-25T14:33:15.498126785Z',
                                                                                      'signature': 'lIJp/JMxxBDIM4fEs6t+/CJOM6z9WLWDIPQwR/pbC3JMJalNPX4+rZ+0PzUH/wUYKz8583HI63L1Elx6TqzOCA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'PlGqiCA216cPlPPoZBa3YBt43Yw=',
                                                                                      'timestamp': '2022-06-25T14:33:15.422882836Z',
                                                                                      'signature': 'XZQxqMpb0P6NX+eP5EMHyr1AYsrBJGxAWp/pdAPtrPoCtYrghpBipvGdHK64jL+bXZV4FwSNKeFOM0bVVw5CBA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'LJzMMX+yg9VKx0iDimTykQYDnlE=',
                                                                                      'timestamp': '2022-06-25T14:33:15.688269028Z',
                                                                                      'signature': 'RifDu7Q0NWYJ7gfBb9fYV2IwCskSkyViEnNBJcOgc37u9Lai2B0DrvfGZzFqplV7iRrtxV/nE9ERI4EVoBTQDw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'sxWB6f9XEEVTE3Di1IlaLW/t7Ps=',
                                                                                      'timestamp': '2022-06-25T14:33:15.514493932Z',
                                                                                      'signature': 'vuc+3Zlr8YLRZ6HKs/Wx1sMeCuyiVXPnfLW3qy0aVsMLnrq/HL83GGaRPl8oqW/+WF3IDJFkABERlbDD5jV8CQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'u3a8YyLHUzp8zTrxwInHs5cfsBI=',
                                                                                      'timestamp': '2022-06-25T14:33:15.450046519Z',
                                                                                      'signature': 'mUQtqCy5rMMFCd17PqSvcetTRueLhqifB6IILv/z7Sa/Rf0sdrCOaxQQ7we4aaGo5psNOfiIVEH5kHYcSNvMAw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'LCpem575AxZPor0/FAVx3fAqAMw=',
                                                                                      'timestamp': '2022-06-25T14:33:15.518347771Z',
                                                                                      'signature': 'ATDvF3iFD0USo3qPM6t5dzs1ya65GIbnkuaEWKQN43I+V2UPoIkHG4c4gvWV25gLI7rvbNV029/3yaZbmx2JBg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'nfjjOMheh5vISwqqKKCLQxvVtUg=',
                                                                                      'timestamp': '2022-06-25T14:33:15.614461232Z',
                                                                                      'signature': 'HaQbeD9FvILe/xMxn2HSfjrjal9AnB5EfhjtetGztT5TEpDOwApkVP0lcWigwMh1KBUm/bKYiWKYsWyroYHZBA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'wjVmIrSVcllhtbIBo4LdV80zBew=',
                                                                                      'timestamp': '2022-06-25T14:33:15.516151354Z',
                                                                                      'signature': '2fZwbI80G8mlVlLZ7e/mIuDGZX0Gj8DCeGQBmzf1typhYPHLtYEZkV9FgjYGFea2VlSJo0llwe2rYpX3Z2wIBg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'xSrNsyBX9ccxu91IRguTw1AN0yQ=',
                                                                                      'timestamp': '2022-06-25T14:33:15.469462166Z',
                                                                                      'signature': 'Q2k1hb8W7KDDsTcXr60TYQHh3EgbgwSlqsyXPjY/atkQNdYJz0Dj6VMGQMVRNmOKC3j9qBHXTsnVw392Fm9HDA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'Sbv7G6GnUFLjIm6OHg7+szkYuLI=',
                                                                                      'timestamp': '2022-06-25T14:33:15.416834860Z',
                                                                                      'signature': 'bNL8LDO2VibN7LuJ1vXM1qssXPR0sdvdqm7HQMDOWmzivtJY6azaiSi6I2cVsh75NkzMVxw1CveZ66AZgpSTBg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '6+1pTmzhIk+x6KLdjuY6OFaLHis=',
                                                                                      'timestamp': '2022-06-25T14:33:15.653606789Z',
                                                                                      'signature': '2Who1KHL8AyIzLqowN/P+6UiaAZPqjU7ao6nKlCiSRI33xWzqF1V2TBsXi9xweKeNrTb/9uxoJf+VByGkLIDAw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'sHZaL2/MEdisRidfrAbdNfVCF8E=',
                                                                                      'timestamp': '2022-06-25T14:33:15.457568777Z',
                                                                                      'signature': 'C1tignpyTdGIyd0+UlEd6I77sKifPBmfhv+ncCp7gYDeqBaM+EDLO+6bnRpoa9fz7UfXqu01QsVZ0b39T7JFDg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'G7KWcA1vzyMYqtotCY5NQEebbH4=',
                                                                                      'timestamp': '2022-06-25T14:33:15.464454679Z',
                                                                                      'signature': '7v0ied+zeWyyNfKm7FQ3HfiQ7uDWK1AEBIc6ZuE/7zPKl9rn1RbO8u9sjETwsW5rvGT0mbE5W3eNQRN+dbNhAw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '1/fHlIfBClzxq+sdvYHo1JdXxCI=',
                                                                                      'timestamp': '2022-06-25T14:33:15.534037513Z',
                                                                                      'signature': 'x5py3IiLDWRnga5T02P3IkRY+rkKyZOZiFoHGWUALklWayny+flRD29X6i4Hoar8MqrjUHKIdeRxZ4ufzdljDQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'QtZwXnFmFrSlRCvaoFC3xun93kM=',
                                                                                      'timestamp': '2022-06-25T14:33:15.384979203Z',
                                                                                      'signature': 'n0o5mp5lWl8BcQhlSmmfjLaGkO63WccamHSw07S6l6E/s8629pDYW22NUjErLF0orxxmVNPmnJuu+AZEIyYiAw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'GuC9Qy+aUSJHSmRjJdGvpgaGkuk=',
                                                                                      'timestamp': '2022-06-25T14:33:15.472808444Z',
                                                                                      'signature': '+lYLyopOluLlcPMKi8N62nk+Boh59BLo+JvWgCg8CKP7xsd6hv3gdmA1IHn8Hlmzog3fs5BOqDAePoO8DH5zCA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'gI1rBUoLbT/19erwplz8ZMVD+DM=',
                                                                                      'timestamp': '2022-06-25T14:33:15.542889869Z',
                                                                                      'signature': 'uO/3P9tE/IA4/JkEC885lvRnzYj8XAkaFmzHjzVGIDgLvOJPCpteh0lWdpvShUzZh1b/oqwuvj86qjs6cLNjCg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'Kl/s8mw/tDQmrGs9tYpavFgA8qA=',
                                                                                      'timestamp': '2022-06-25T14:33:15.456254730Z',
                                                                                      'signature': 'LlgF8Utf/N1jRWh+S4o+AVfk5pzJB9SFbkzcYnjQfEPbCxZTcx1pnqEt6z4hbP7rGFhkfFsLibowNWTsImrzCA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'OZZxwv5LJxTsbofU7kVO8V8zqio=',
                                                                                      'timestamp': '2022-06-25T14:33:15.569166232Z',
                                                                                      'signature': 'NeX23dOucxioouLAXNOCtOROXbvW+B8m8SZB1cTnXwHXLAN6n1AOLpZ1AFLhSNPUmKO22rNb9ZsDENyz3+PsAw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'wt3ZcAz13sBFfcQjgpsx6o/U+dQ=',
                                                                                      'timestamp': '2022-06-25T14:33:15.389095841Z',
                                                                                      'signature': 'Te3sGkfiBWs32z23KNRcEadp7pPWz2K3gZrsI9WxoF1igV30uKBrPuPncSwKoLM7yyiDC5NsXC7nkIGx87QFCQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'M2Po+XsC7MACiechc9gnVDBHrNo=',
                                                                                      'timestamp': '2022-06-25T14:33:15.454885739Z',
                                                                                      'signature': 'ac5Z0pvXrAoiaffy+f2dAkFaqz7r1Zjy389zfdF3lpkLx0miMOBAZml8rCbdL2l1la7yiIg7w66CowSvH5sWCA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'uezh17TdgOhoJj6jqvJyucfxKS0=',
                                                                                      'timestamp': '2022-06-25T14:33:15.456576923Z',
                                                                                      'signature': 'I2jh8yTO9Ejp6zB0SHD5HAnIMSR9Lfq2q7UoEGnO9aTnGwZnzLfLcUqYUpZBrtXp9FrkWcWV6pa5d/vYREvjCg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'tUOn30h4Cu/vWToAPNBgtZPE5rU=',
                                                                                      'timestamp': '2022-06-25T14:33:15.457554710Z',
                                                                                      'signature': 'NDm943bQ+dqPlHklcH2cz5x4XpaP0xHy+HXqQmdKCC292C/EGks431a9Kse9fp1D2eIl21Qg6TvJxPVHHt8YCw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'v0y01Z0Z1FHPXnvEk0nfSqIi14s=',
                                                                                      'timestamp': '2022-06-25T14:33:15.388726573Z',
                                                                                      'signature': 'zjwTN6Maun/utZTxt0UYofyF1OZzYOD/ahlV8nDgsTVvgg9RnhWj893z1LZXhFoXuXhGv3fJTMb2vVpGJf3QCQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'sr9orUztb+j3GqytAQA0Nuvgcp8=',
                                                                                      'timestamp': '2022-06-25T14:33:15.573474826Z',
                                                                                      'signature': 'U6iAnITWW2UwE8Kzp78YTPgubmHUpMB++9mZTr1EdhY5StGJH36VHr6jPgRQVmbDwjA5rCkrpm2QeyoXQhSxBQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'CrujbFTdDKankK75agHUOS42NF8=',
                                                                                      'timestamp': '2022-06-25T14:33:15.488348563Z',
                                                                                      'signature': 'ohzNZJuR4YEmuZ1tQXhZ9HuFtyfG+byRhYDlGjybyltKfuThvQL8LJJ36HI01QqDKm1k54mhrWJTUdBa6V53AA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'hLPYkiui8ko5R37BSVeZG+Gud2U=',
                                                                                      'timestamp': '2022-06-25T14:33:15.431690099Z',
                                                                                      'signature': 'dpTD/xmZV7Ub2Z5/BrWtCsGlVqO6tAa1oyJFL56i7gzrvZW3O2SGPItCqoJ7l4GuEQRmBJfMuQsDusrzR72FAg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'AAqlq/WQqBXry9rgcK/1C+Vx64s=',
                                                                                      'timestamp': '2022-06-25T14:33:15.504974855Z',
                                                                                      'signature': '0NqHlNLB7tgGETgSYWEhiOmol7FKCVLwh3hbMfn6nJMl+o9BEe0LhPZg96t7DipPVqylAZ9s4aNs1FlJNtHACA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'aPW76s7xFMcg6pyYv6L/3gHFT9E=',
                                                                                      'timestamp': '2022-06-25T14:33:15.698352037Z',
                                                                                      'signature': '4vI75VNHjCx6ewtddjMW5p7zUtBDFu3WrLH704VZJiAmPctg8aBKJ3bTqlmbsryixPei392C8Rgulj5Wi75FAw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'pPHVU08/qQWk2mBuihCDSXZRH/c=',
                                                                                      'timestamp': '2022-06-25T14:33:15.428478910Z',
                                                                                      'signature': 'nYGV9oXPFZXt9MeBGQsCkJpmad7vTIahKz4pDLw1fcCyKed7sQoSu19Rb614HcBrzUSv3nySmfHKWd1Dr9ZrCg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'WrNTt0jUXyDfzhnXO6ifJuHDTPc=',
                                                                                      'timestamp': '2022-06-25T14:33:15.472394087Z',
                                                                                      'signature': 'oZz78IecLO+/V+PKJsmSRU/4HcjGFcdRbCNhE9DawxipAsBv4cPfuq1BrVLCM7cQKe+4Ki5dNRLfnmsTis7yDQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'UuFkYTRDK/lTK0iBxu0y5Arlot0=',
                                                                                      'timestamp': '2022-06-25T14:33:15.496562994Z',
                                                                                      'signature': 'GQi9u2ITNNX098a5JYklO0PFkZf3g0aZR4R3/3zAksWLJEp3fHMz3bOp2KO5L6vBricZ4Tp+7d3bZT6YP4/hAQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '+USWk75IKU7P/0f1r7PDHB36sxM=',
                                                                                      'timestamp': '2022-06-25T14:33:15.487257191Z',
                                                                                      'signature': 'R0ZuYhBYKFcWQxXOygDP8vfoSNZkXXzNRtdEuySjX29qoGb78SvMOpVQDNpzg5bxO2wB5AlOFIaPhQgHl3TOBw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'gBF3Ltfd8syc16SMjAqiSG6fTpc=',
                                                                                      'timestamp': '2022-06-25T14:33:15.448872350Z',
                                                                                      'signature': '6WXOtcsFCkYoe8NpPoTkqhlofubvFgrrym7HjAWUcyVUtwJSiNBM7WDVwyQa6wKnoXcUymE1ypgkHBGnwyslBw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'j+PP+moHsJPkQbuE2httq/U6+i0=',
                                                                                      'timestamp': '2022-06-25T14:33:15.566211646Z',
                                                                                      'signature': 'd39kjEQ/ndD+wnY1mcYD9wCBINjKccKjQUB0NfbSu6iZxXp96EvtELcSnxJhs8FSMgtMb+evQJUVrivRoLajAQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'sjayojrXFqnY2Fagy6di8yNRXF8=',
                                                                                      'timestamp': '2022-06-25T14:33:08.450547255Z',
                                                                                      'signature': 'juBzGZ7Y+MTiUEB3Z5EBnHk09KNziCI/DcQ0y/Zp1FAtlDxzTtgycJTCwNOikmnDPmixciQs3oFEK3U310yoBw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'ISI0dc6G88fNXphaqI/CSinJeBM=',
                                                                                      'timestamp': '2022-06-25T14:33:15.426679676Z',
                                                                                      'signature': 'rOnOceoyE+Y25DRbC4c9/A4p3lcg9YlScB9zDEywUEt/guMkmXv7WIspvGNiGA522qShwsbkgTYvEj+9zQWFDQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'zFziQY2oXHjX+J/sqrCN3OMUwMw=',
                                                                                      'timestamp': '2022-06-25T14:33:15.672329942Z',
                                                                                      'signature': 'LUY0mQb4x7LOJD5iNdbkn2K/f22ysFy9WOJEQuWSvIVFusOvKx/8kYwZdz1h0+Nn66QR4Df1HRVy1vWqjPhjDw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'tMwD8qyiLEPeHtOFoQS6hrdGJ5I=',
                                                                                      'timestamp': '2022-06-25T14:33:15.420063611Z',
                                                                                      'signature': 'ggizx1c6jBxM91869qW/OSJbkD8/J6LvsL1zWbMsaUH8uK5jiaAA8vHL/zwW4SoAJo+GVbqx+PSjM1EI92FjAw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'bqhjtEujafc55lWVdw2rksiakhI=',
                                                                                      'timestamp': '2022-06-25T14:33:15.486200467Z',
                                                                                      'signature': 'pM6ZJboWgLvVMwmohPuzccADpTEwUcQPa5tgI5tAJd5IKYhHsGh5P7sJ7F8K260y//BkNq/WFoWDktNbTQcLAQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'a9RwUCEzKpC5I5fY1yyjlQy4WOs=',
                                                                                      'timestamp': '2022-06-25T14:33:15.517489162Z',
                                                                                      'signature': 'Wi+hfmUYpuvTVSOh2f89khJp7tArwrh7aOFcfwVC65dq3yvzpW6xqTQZDpv4Tiq/NinSWkPxKGt/+fpKhOawAg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '+ACDsYPEAZklxytfSC8iRqwtQ5Q=',
                                                                                      'timestamp': '2022-06-25T14:33:15.582515141Z',
                                                                                      'signature': 'vaJD9tMBiWd7WWbPA+pMCh189ipZHkkd5tDPXDta0YdgXrnVAftuijXjEtHIFf14KbZYa0cjR7ExWA2t4m6nDA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'KQZ9/jNSpASB230R7kSxChD8QpA=',
                                                                                      'timestamp': '2022-06-25T14:33:15.423417682Z',
                                                                                      'signature': 'orBMpOwueDK7PhSQe3zahZkxNyndgt7XIe5cEaEOUOpN1N37PxCmkh7KHZLny7wSc/OMgRC4Z//7nGd9pbjLDw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 's0WR2nmq0CE1NOLpFfUN5c298lA=',
                                                                                      'timestamp': '2022-06-25T14:33:15.540594349Z',
                                                                                      'signature': 'MIIs1e6W2bhHOYd5cLNF26cWVWIJALPRYuF65slpQZ79LpCkj76hZzeOh0Pa0PvmrEE0tbxS9a35AD2d6owTDQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'BYWemGKmaA2+q1EDYsELFmG5dDo=',
                                                                                      'timestamp': '2022-06-25T14:33:15.659921378Z',
                                                                                      'signature': 'YbM/gvBDW7qlBkRC0f4fpdysWypEW3MvMC0NDoWi4vnZwgk2GZUuT+y8JoBIUAJWQxA0TbAPImpFlkevWNdFAA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'xTJ9ZM30oEvhIG5l9bYdRJI2MOY=',
                                                                                      'timestamp': '2022-06-25T14:33:15.423399416Z',
                                                                                      'signature': '15l6CwFD6WCNaTjbHHVta2CL4CxxGMHnxw+CwocRjcvuLay4c9e9yPhsB0gUzzryHs85kwdsljLrBoV5IawfBw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'cyzu9Uw3Tdxq3sv9cHrv0H/twUM=',
                                                                                      'timestamp': '2022-06-25T14:33:15.501957075Z',
                                                                                      'signature': 'jZY9/U0m6scxP+T+1cgtOECK/IMMjmHZzcZ1WKQvjCgNUcfu7T5ACYP3uYirTUX1q32pDfSBz/RrxDnp/THnBw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'fmL0bLzp+x3lRGAG1tLu+4I0jaA=',
                                                                                      'timestamp': '2022-06-25T14:33:15.641006817Z',
                                                                                      'signature': 'vn384bqqbuzWaqZz2ckipfn0+b7/RjUO6XpEVMzAV49r4lwGJyd5rNOQ0Mj1bzBAi8pbIEXGC0BY/gVQLNQhCw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '1e3JNDFMibRZUmIOnJkrHckBhEI=',
                                                                                      'timestamp': '2022-06-25T14:33:15.423328172Z',
                                                                                      'signature': 'fdhV6iHu4Iub+ec+YurTCv2ZlV/91qq7q4SSg4E7gv0esObAhs1PKW43/BB4NaNsgbnZPFRgjMBq102ByEVmAQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'YKqsuC+rnZDLLfCqDM5FVRAe2Qw=',
                                                                                      'timestamp': '2022-06-25T14:33:15.529754504Z',
                                                                                      'signature': 'qBnyd3S4UmvOwj64iquLkp57RiWDXc2KrLST7FXkEKrg+gd/ShFI5Otf7UA0heQVToIzXz8FfyOWpLwbeZsSCw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'EsKqDeZvo/nWZNA9XW9tgha22oE=',
                                                                                      'timestamp': '2022-06-25T14:33:15.389309935Z',
                                                                                      'signature': 'gb9EkRWpOQxIzjiLO6RtK2VCmk6fA6jV0lwOCRkup29HcnuMbWMLauF+q/O/pjAP4g6wqOrc/4JoulDigZ6KAQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'JJNdWfqpTnk2Usv0cWxgQc16pAA=',
                                                                                      'timestamp': '2022-06-25T14:33:15.491693607Z',
                                                                                      'signature': '1lAty3KXNnJ9j5vc0NZIJB88lqwNt0xvqHslxM+rvwbhD/YJKZb/novHya337ESot9flGMHGUNk+japEN+PTBw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'Fw/v1tf0ppqucKJEFfxOLJKN4uU=',
                                                                                      'timestamp': '2022-06-25T14:33:15.479200933Z',
                                                                                      'signature': 'oeuVJs/G1ISFO3P9NGBUa/+lvfWlfH03Rs80b5WxdBfGa1uyvOeUHATjUFaQ+Tz5iDWHMNCkOMeLkdUMdaKGAA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'TJIjD6wWIwPZgcBt0iZjpPx2Irw=',
                                                                                      'timestamp': '2022-06-25T14:33:15.409657247Z',
                                                                                      'signature': 'vw2fRYe3UXNtFUE7+eKwQfF+Vs1DdRfwkwulozKWOp3wKpV1jDw0jQdGMlXoZKz1zd6odJ8ums7GyW8KrF4SCA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '+OUDK5jV0yRC4yW2lwtDT3UuET4=',
                                                                                      'timestamp': '2022-06-25T14:33:15.509721457Z',
                                                                                      'signature': '1Pb3Wt6esSprVHRoq3NsuHepzrI/gUrqwtdN4tsYC/nwRO+Mu01J0G+uTYuv1VJpQAQ/iVk3QbPTM/7HBIMnBA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'HpzpT9C6XP65AfkLxljWTYWxNNI=',
                                                                                      'timestamp': '2022-06-25T14:33:15.439398855Z',
                                                                                      'signature': '6BlYKk46Ncat2hWFgio9H2VTvbHBD0FMd3JJNyJgM3Uw5N5LQvd5/wTEV/fwARk9wibrErqLUjxVISORCDCsBw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'K5pV07+T1zdd0ge3XF7U0rkdkUY=',
                                                                                      'timestamp': '2022-06-25T14:33:15.445948133Z',
                                                                                      'signature': 'AuX+oKXSPURdq7YnOenzpw7rckHLKM6DF0a6ktUFyf39QvuIzpP98N0cXuPD/Y+TDE4aaCKgFIXDJ68lkql+CA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'yzP4IXwHlS7KGPU8H+r5E+kUMTc=',
                                                                                      'timestamp': '2022-06-25T14:33:15.394935076Z',
                                                                                      'signature': 'nIcC7yDlvLqiJLpNbansQvhOY74ApK/kU+/RLVDc4vPX+uwvBzUqg64NQs+XBhFX5ao5eYSQUihJUYuSnMpzCg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'ePHXqXc/ySJzngo3BafKBr6jCIM=',
                                                                                      'timestamp': '2022-06-25T14:33:15.448118349Z',
                                                                                      'signature': 'M2KPhPgghBn62ZGgx38fWbXEY+jys+XObmmuN+9ofeIf/jotOTIdLi4Lm3WlvaQ7AxxT8p2SMoy5ccMZHfZ5Aw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'gYlktPs20oEJw+hTd4szIxsnxfw=',
                                                                                      'timestamp': '2022-06-25T14:33:15.551687958Z',
                                                                                      'signature': 'pUzyG7j5amp0dQxp8A4+bagXmbistWcQf9rcJSw2Lr0+erJZTkgpX1KPMILUXT+gh4ejc+8gA0K+fgWC+KC8Bw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'SvadalQ2ww41hMFihDPeVedYvMo=',
                                                                                      'timestamp': '2022-06-25T14:33:15.530985687Z',
                                                                                      'signature': 'IM31Yvb142jvX4IbELqODLSJHLKS4YyIQx4j9Whh4/lTjsE/ZdZErtQT9zfGjL60kB+pHO8+JBzAi8iPeVsgBg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'nulNu4b3IzcZK/KRsOdn/Scp8Ao=',
                                                                                      'timestamp': '2022-06-25T14:33:15.379830093Z',
                                                                                      'signature': 'YB+0hvVjZDKdkqG+VpvdwsAA6yC5mVcDK8sH3xaRY8wtXDXU/jR44nk+FsmisOnIs8vyIn9K1NrMzU50S7SiDg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'znaAM9cnxqKJgK73Ny0SQyfIEKg=',
                                                                                      'timestamp': '2022-06-25T14:33:15.408365799Z',
                                                                                      'signature': 'FoSQV2QpTc4alCa1E9YJOBZFxagPIw8zdjF4OKEm7wXpUFyl1iHCiVt/I1ehLf7EShubwqajlen00nxMYW8mCA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'bzIrr11z1cdycZQZAbHYZkdtXJA=',
                                                                                      'timestamp': '2022-06-25T14:33:15.413316379Z',
                                                                                      'signature': 'joOYbQYD3OfZlomx9h914Mwu3aRahRvQtpKLyD9U3of9EzaK5p2+x3541qg7el9pyEINNH0shSPUnqzWFLhRAQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'bLR9eGsvNQwTpgu3fTmKyC6QCYU=',
                                                                                      'timestamp': '2022-06-25T14:33:15.399084240Z',
                                                                                      'signature': '0DBsA39S7cWNUutEGBMGvjj/mzTLk+OFke3aWV4W7aCuQh+VtqS+92djTRCXEtvJPU5u/tH/kew5BAIlL0lUAg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'LIgtV1Zehqnuw0M7FQJfj5YxhFM=',
                                                                                      'timestamp': '2022-06-25T14:33:15.568719247Z',
                                                                                      'signature': '/QMj8NtuBbFHqjdtusnfbhKBR0dABfOSmogjoK+BUsa1xo4JV9zkMd3l24WRUfzcblF7aSzKxa56KxidSA+wDg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'mtCqGKkqGkN0Qm7ZuBktHWw9JpE=',
                                                                                      'timestamp': '2022-06-25T14:33:15.395258711Z',
                                                                                      'signature': 'gyPmvcY6+fIe67ns+81/cuhE4Mnz7FInB+JDuz5OUiJ7ORBYEpJMv6+7aHjWwMQe//84OtninkvyS307sS3/Dg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'ak0Up6ybT3x/KNyQRuUCnRvwn0E=',
                                                                                      'timestamp': '2022-06-25T14:33:15.381293665Z',
                                                                                      'signature': 'qLv7mQscqeCoRF9mS/KubIr46ACD7PyBl3UOLj455LM0uqSOZF7bPI8rEEeIEp7n3AbaO5adGsDYDWNaqsSoBQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'jIgCqSERQWnSWBzUbjymhT9vKn8=',
                                                                                      'timestamp': '2022-06-25T14:33:15.603258719Z',
                                                                                      'signature': 'RkDPhKavxg8/hs27lOQzfLl68kT+f67JcBQzTudDSNhra4Jk797ADkcl5+1bnUBmY8mcQfj6jvLZ+BH2yNQODA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '9v1jZazFOCtq1lZs0pcZBLdffiQ=',
                                                                                      'timestamp': '2022-06-25T14:33:17.448560903Z',
                                                                                      'signature': '66hpG5YuyfMUF+gsuXiwkW4n5OjbWwXK6uxF6IEjLh32rQQCM8Vawop0li2ui8z6pEIMkwNWnHHIrUnlRe0gBQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'u+Ve2bLkFuKzfBO77pzW564xRxY=',
                                                                                      'timestamp': '2022-06-25T14:33:15.375109790Z',
                                                                                      'signature': 'jDxqSXFL3Y9LnFS55ylaLcCvWBBXE7sRVT4zVx7e19KYG+vk6kJvHui49guJ53w3fhZXQ+3PJlVFd8E9S3YPDg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'E+4/BfIMatj9J8vvM91h1fmez28=',
                                                                                      'timestamp': '2022-06-25T14:33:15.559700001Z',
                                                                                      'signature': 'eJX+xyyXSTD9l95snTxZO6eKb5QxJejRVwNYQhafzgJRSbpI5hvIJAdMNVebyg5EqQkE+Ui/BpfTggnPz9IODQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '1l2wTRHvxDXrttKWhYyt6/1ETDg=',
                                                                                      'timestamp': '2022-06-25T14:33:15.588244659Z',
                                                                                      'signature': 'gqiZu9py6xFoTesGu5gbVdFAha3M2yfltTblryQ7YmLlnAl0SIkWri3kpKi634CRYHTznXJGevRlhbFT0tU+DQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'KpE16IFgrwUsmruz9jAdfZniOEg=',
                                                                                      'timestamp': '2022-06-25T14:33:15.444236910Z',
                                                                                      'signature': '4KYxsTvMA/b81oN7hvilSl8JdTW4vQ3qiH8hKIUhaKfP3ATaDNLxOnLUUFyhsYBcBayu2V0vChqpJSOvuka/Bg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '3qELGQGaE7F9GrnK4XMhza47BIc=',
                                                                                      'timestamp': '2022-06-25T14:33:15.552659273Z',
                                                                                      'signature': 'GyBpWBOZdaO3IAp2YQLDyn880mktN5e6pWqmyKrnxYOYOanwIYCDeaFxZrB55OVOVE2bh0yhb5jWI4ojCaGGBg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'lVpHyKyGMoJd1HXpCRPUCrCdP7Q=',
                                                                                      'timestamp': '2022-06-25T14:33:15.606648452Z',
                                                                                      'signature': '5+L44ck5JzaWBc4usWp3GjQIivwcjMILiMyiuTxfXfI25T5fK+FnbGexiQW0PB7DxE0XDv2jq2S6+SzaDj2ZBg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'vbBGJZ63+3SigBXjHmTO6fCAIZk=',
                                                                                      'timestamp': '2022-06-25T14:33:15.545847028Z',
                                                                                      'signature': 'g2HjRtltjC6MdHWWSl8duCxbtZxVR15Zr09s3YQh4eHRVqMRN4eu37+LlNHu6xDsFD/0VcCVFg9dGwjkFUGDCg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '9VcUJD0y+2W22Vop0DUOoMq7qOo=',
                                                                                      'timestamp': '2022-06-25T14:33:15.498694353Z',
                                                                                      'signature': 'ZN7OfxTK0fbu0WQnKRbuMlTQPNOv7RlTYbxPeir3JVIq8mVw/z6tQOwcjaS/2E+RG8FiOP1fRVBD9aqhrtfjBA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'SP1WDTywtVKSTLwPnCumiIP6ETU=',
                                                                                      'timestamp': '2022-06-25T14:33:15.420147475Z',
                                                                                      'signature': 'jdDfV0h0xjCbuBaDr/LeqCoPlJhZxprSEKrHTRKm7i+rNs1fN21iFYCkZMzj+VuS/r3DCQTnGNq+g6/mIfY8CA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'QH8UTRyd6k7mqMvC1MAipldQa4M=',
                                                                                      'timestamp': '2022-06-25T14:33:15.522480530Z',
                                                                                      'signature': 'CnWRLmVNEbwFwiUJoTIcaWeOABFiB4ac7HLdUcbRNyyI+zCSm0Gs1t8Iq6QPT/V+46jl1W+zAxbgTq/WoHT0AQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'hGvk854xItKi0/5UVOJWEHPpVTg=',
                                                                                      'timestamp': '2022-06-25T14:33:15.514619275Z',
                                                                                      'signature': 'W/7hKz9n9ZbdOHyT7ADL/Xem2v7DeOqh+ldsgIWQuKamNg0N+JomcKTmKTGSdAFeRdcOKd1yAQ8kDOdZgCmGDg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'dCC3PxAomsoYrM0ctatUiCwE0tU=',
                                                                                      'timestamp': '2022-06-25T14:33:15.385449292Z',
                                                                                      'signature': 'i21o0pvMwMYT4RsPX1nKO+/63M/KwhzPxHTs2K9drB302EdFdjrjxrJk/MJbwccDi8SZx+wpNPn342XPmo8kDQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'biI0+IGBen25l9WUAFGFkfaSoUw=',
                                                                                      'timestamp': '2022-06-25T14:33:15.684702191Z',
                                                                                      'signature': 'AdvBMeyrifOT5yNC4vB31yDE6vUqowAbFSo/j7B92ATd1N8701rWFgi6AJeOd4Y/D2I9v9JruFTGqB9rJIZcDQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'RPBYL8sjsEQHRDaQb4IGz2VRLDY=',
                                                                                      'timestamp': '2022-06-25T14:33:15.582935769Z',
                                                                                      'signature': 'XVjYtkhtPTQjTKnUx66m+vuXnGb5WqwEfTTDuyFJzDGX8ANnYx7VCAog1LgzlfYAHd5aDrPlier6ejd1oPxzAw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'pHEVwJ+Eb0b0mfOBs1tFJyUgSYc=',
                                                                                      'timestamp': '2022-06-25T14:33:15.462642519Z',
                                                                                      'signature': 'rzcoSmNK51AfzaViROPq8DH5aQ2GLQrEdMaAUrAj3aYdP8sb5iKnr6ERdh7xBLjAAJg7EUhI9cZf+hcZWlO8AA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'iKZQRfXuUCVggm2gf3ObqeuoRww=',
                                                                                      'timestamp': '2022-06-25T14:33:15.663242535Z',
                                                                                      'signature': 'yNNm+Z7t+zQc9GTwbSAbIcsEV7UZqfDo4+HM9FN9YHZ9iwzteRlTNVDmJZPrEgmDoktWqLZTAQlSZjTbyepjDQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'h01qqDg4Snmj1NBiVB+Rv34xvbo=',
                                                                                      'timestamp': '2022-06-25T14:33:15.637060602Z',
                                                                                      'signature': 'lDHLlxYHStihnj1d9G4c+IyGEvJXiCxvT/qKgbq4Dx+1y0swBxmofPFvcVR4ZVCOA8U/T2CSi1c2JtaHJtpqDA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '35KD2iWylkJul0OGFNHGLcEBnYQ=',
                                                                                      'timestamp': '2022-06-25T14:33:15.380789514Z',
                                                                                      'signature': 'sgrBSrAAOeftCf/wfss7y3cfSvZJENwEUfXLEASiTsddOxqXDuG1tkbU/QY79kish7xG+MM541L6ph5iSZxnBg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'O4RcmvHWnp+7YgtpqyJrKLrJeYU=',
                                                                                      'timestamp': '2022-06-25T14:33:15.466213661Z',
                                                                                      'signature': 'UwonM/zNvNBvX+DcZbfwC9TRStpEXNwbJYUCfnvMd+Jy6UXxC9aIzKIM1r9Ga+nGkpneWsaSvY2ugOByr1XJCw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '0mmoHHdB9FjDHbf7FMWBdkIfsvg=',
                                                                                      'timestamp': '2022-06-25T14:33:15.500080627Z',
                                                                                      'signature': 'hfqkoD/YtB0Mcc3eARZIwGXirvmASEni3PQ9SJnNcYMpa0f1TXf9BZwga9XqZepCFbrDNFzOqIOmrjRuFPrADw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'lxOBjaVAsq1AzTqCGGXxyiiKG6o=',
                                                                                      'timestamp': '2022-06-25T14:33:15.366900932Z',
                                                                                      'signature': '5WgJwNWtrKxNHUMgtdT+UJVMh16rBNIkDIdhfhHHUDedPbp2tfx/FHaWPDVJR2jr+NPCh4m6H2U+WTZ5xOArDQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'xJAyKbnq1BXHno+mnSu6YRdhfEE=',
                                                                                      'timestamp': '2022-06-25T14:33:15.399111994Z',
                                                                                      'signature': 'PIlSeCy8seH9tvwBzXmIexaTPB0XxL3YKfszWKimbUzAtjiI7PAotkijiRd0XRCEPh8Rk3fc39ET4iUMzDGrDg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'tJmc1TXkzTK1kL60cCCnJPQLZeU=',
                                                                                      'timestamp': '2022-06-25T14:33:15.556932653Z',
                                                                                      'signature': '69xx7eJoOljOGdmV0kcAr42L2K8LC/+WxewlWbulkO66AhSFUG/oWEWRpdZu6LLM001FhNtvAv95L3SGtjhaCA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'TtfMQDiDPy6lqj9NRMWByOfL2GI=',
                                                                                      'timestamp': '2022-06-25T14:33:15.422972121Z',
                                                                                      'signature': 'B1A9OQG8ZF/JjIM50nhCSq6DPSnXPNSxFZb7tAkVKU81QNhQSdXQdwklKwbWa+7uDSOj1kWfybZxWeS/d7cHBg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '/fVplFT5OihhW6dnfFblYvn/aPo=',
                                                                                      'timestamp': '2022-06-25T14:33:22.238755323Z',
                                                                                      'signature': 'zjyGk/3O0i7U9647jkkV1ekbF6bZGlSYnfgH7PE9xPIySS39GoKPr4tsIj8VeX3agMruhpcB9uMlftshVcObDw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'o8fATWIOqjN3dfADuNCYFYFnYzE=',
                                                                                      'timestamp': '2022-06-25T14:33:15.437226270Z',
                                                                                      'signature': '0ezrB+lcd7lYv5bIDlF1oKl/ycXmWhFxKC8ghRqtnVF9gzvl7o+D3Cuz+Mc1GEbMEGmNsnj1he54VD31v+5KCg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'alFVTowM8xZaAcZ1qYosOLbrUSw=',
                                                                                      'timestamp': '2022-06-25T14:33:15.372983911Z',
                                                                                      'signature': 'Yi4Z2Dcq5SBTKzoskxFKXZ8Xdr6liJi0WDR0tduoxTnPeh4qUqtr4Dor3gHj22wNJrMfLacY1h2T6lwawpxiAg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'VbO//s6/oOV9oyLQ2iYsE2qRkmw=',
                                                                                      'timestamp': '2022-06-25T14:33:16.583999117Z',
                                                                                      'signature': 'aV92YzDpaQys2PEyD9rxEef9aDmAJrKI7TOyt+ZrwmHK7uF/m7Q6PJSS9mM/1Kb5+A/Poqgzun0dNeSqo9fRAw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'xfBrucn6GpXCm9qMMNXcchCvIWY=',
                                                                                      'timestamp': '2022-06-25T14:33:16.913147398Z',
                                                                                      'signature': 'kYko3+0UZqL61p/Ds4Yq3I6JQ1WbNuATX28KOQR99Buy1zF8xGKoY65mcAbaHFJajGyN1cuJRKP8THbG5Jp9Ag=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'cMW05necWaJM/ZFGWB4nAhwq7CY=',
                                                                                      'timestamp': '2022-06-25T14:33:15.430306914Z',
                                                                                      'signature': 'ui6KDrMLX4nYT9xhFXM03Gr2WxTiQqgXEMekHWUHN8vp6/XbGO1uYIVI5GfAFe5kfjDz1ce2+NlPXtInDLbrBQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'AMzuz9AbLTM6G1ar98/4prjtJbE=',
                                                                                      'timestamp': '2022-06-25T14:33:15.659154622Z',
                                                                                      'signature': 'jE3Y10MGyeSuh6EZ61V1Vva6Blecqzb6znu4L8OXX5Z7iZVCGnBicsqqZIwdGS+/xa9tHKhQmXzOPKN0k1WMDg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'Z0jWMuAOUkfCJi76lt6UbRruwys=',
                                                                                      'timestamp': '2022-06-25T14:33:15.403236605Z',
                                                                                      'signature': 'LEiPo1LCFTgA4oU3xBp7gYSJnMXJk8oCwCDArz5Diji4OcqQwNLp/ws7K69Xz4Mdwo1qJ9yWL+khV1PQdGoZAA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'kGsHKu2gU7GWQ0VuY97SM2QNLZE=',
                                                                                      'timestamp': '2022-06-25T14:33:15.499167927Z',
                                                                                      'signature': 'YwFJanvdCXa5zptCx5Bcms3AUyCq2L2RY1u0P9dOfNCdNrK9X6NNuEnm4+JWGkm2NGu+xBYfnClZzN2+CDiZDg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': '0KzHIE1xPP+ftEny1SwFRdx8E+k=',
                                                                                      'timestamp': '2022-06-25T14:33:15.561461464Z',
                                                                                      'signature': 'dwlgAKltfiq+w0frO6UTxuf8GoNONislGJH6PHMrA8jHAcf6jrROmU9fCQS7OWZSOWniU6DPV34KRdAwLhM0BA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'XXQZZsEntvZsCcyG3J5KwuKCY8c=',
                                                                                      'timestamp': '2022-06-25T14:33:15.426039987Z',
                                                                                      'signature': 'KpQ2CG0m/BQvNpvgxUglC3OM7YVBgxPB8kMz8er3c0LwOeoIP7muA090Y0H7+iFkpu4VgNrPQpK+9Hewbqj1Dg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'AAAB5EP9I35LYW4vpp307j1JqU8=',
                                                                                      'timestamp': '2022-06-25T14:33:15.409692687Z',
                                                                                      'signature': 'RX+oq64yRHCH5XeGAV9SaD4hcbHzDAqH7uOLmXVW3PsYg/H+coqju/aCbMJ0cqJuZlLv2pUgeCeiM/RKgtS7Aw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'rkVqhaXG1G+jUMPsLcsA1mE1niA=',
                                                                                      'timestamp': '2022-06-25T14:33:15.414504135Z',
                                                                                      'signature': 'zVdT1JF9KLKAiqd09gJB4FfVC1Uj+LAddB/2Si+TqjR6IlcbtzZkIkQEJWwjZy91tYinRVHjdW0YMS5jufB+DQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'Tpyzn0sfphczl0SlYAtigCZS1pw=',
                                                                                      'timestamp': '2022-06-25T14:33:15.506479149Z',
                                                                                      'signature': 'GFzodIxnoxE49o/sZaSVNHU24gFKPw4lFME7QwhN1EiyW5ZcrJRe5KEQVNttQvsdZlUWJmJFLH+qFhw7g2lCDg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'VpsJ6j2WB8Xxo43tgc7SZMeqlMs=',
                                                                                      'timestamp': '2022-06-25T14:33:15.488352363Z',
                                                                                      'signature': 'kHnkbu+HkZYNw/XTzzBEPy4PoCXv9Hyf0SHOswGcTNTodc2cc3d1B2ZQubdsdvfuP83eHIyC/nLHOsT9b6qeCA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'bFDMRLTx3DKr0pcNis7LIErM74U=',
                                                                                      'timestamp': '2022-06-25T14:33:15.398019889Z',
                                                                                      'signature': 'QRSb2jSMJh97ah8wZEfzktzrHjyt7+P229XhdmyoY/d8QRDDv2b8hUps+zsa9la2jFKOidkQYPm7UhepLQIbCQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'EI5H/BuFRvmPfqUvJUfMREl9sb8=',
                                                                                      'timestamp': '2022-06-25T14:33:15.486256979Z',
                                                                                      'signature': '3O4vmOc+yjkVHm0dY/AQOp0/vBQlRRrOrsSNfbJuHe1INYt7xONArzIdcL2NRGz9G9PBK/erCWcFW1O5Quq9Bg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'JanUUtNfEgUK3uazGTS7hcKBfXY=',
                                                                                      'timestamp': '2022-06-25T14:33:15.402422179Z',
                                                                                      'signature': 'mOscTIGuJYyUQueJ18kXnP9LkB5u+JvdZ47SUGuHFB6SRToltDOHm8W9mEOJKlD0TZZnsEnvomihRQ/pSSMmBQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'AJA3wsdWMvO/njmhHA6B6ssmLZ4=',
                                                                                      'timestamp': '2022-06-25T14:33:15.376169687Z',
                                                                                      'signature': '23YVexpNFqZhei+5xe2spT7JZXTuf1sCDn8nSarT19ERQUmx/1B2T9+WQ4VQ+l+GmvEUl74xQtqIIGm8KNvSDg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'R3NnIYyfksOtmbXXNKNGz36KMoc=',
                                                                                      'timestamp': '2022-06-25T14:33:15.524012558Z',
                                                                                      'signature': 'QeY+t1CUSX551OTUlJz2kH2pMco135gPfMtrdzD9ZBwT8E+9Wu412k8NlAL9AOnYNhPl13xmrcNQcs+yNTNZDg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'XZ6EdZSZBLvItwxCIx/BBE5A7hI=',
                                                                                      'timestamp': '2022-06-25T14:33:15.379169499Z',
                                                                                      'signature': 'W1H1dK0Iv3nUhNnqFoLavdNQ6BBt7DL8KNCuloXbX0hf91ShF4rH7jOC9FN8Xd4uuIV836x6k5Ud0bkTPFblAg=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'O0nKl8SWkDMWOochUocEie3r8IA=',
                                                                                      'timestamp': '2022-06-25T14:33:15.405726258Z',
                                                                                      'signature': 'NjTERBBw/55aVVg6xMPLbWEIyiJpSqPr47TKRVRrWWaUTdKVgyI9VQxERX0DWEojaJv4jeXte8CUzSmzm8ROAA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'LNajUj9dYVc+8eNlS0Ia0hHP6Nw=',
                                                                                      'timestamp': '2022-06-25T14:33:15.513608609Z',
                                                                                      'signature': '35yAAuEJxpy9zCJ2jjzOXq/3WKGkvyfLytdDW8uAVLcp8BxUbHvlYff2DekqXrj1HeE/vvnhwmqjpJjv9vQsDA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'sjNtyGp0pvhVLX9oasCYPvTgsM4=',
                                                                                      'timestamp': '2022-06-25T14:33:15.515821215Z',
                                                                                      'signature': '+Qk4VDbWbIPSF6rT0oY+2shiQ74rDhHzCYxxpGrL7nHryIeg1DUh/JTCXbeyDRwGu6tZeRHav1qpxjZTVhUZBA=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'Fi2+6idmryfhNjtYOi+BWHdN+m8=',
                                                                                      'timestamp': '2022-06-25T14:33:15.540321053Z',
                                                                                      'signature': 'qkG+qZ1cj5f7uK2sWnxz6MnOcar2QLXYcCEfCsBsmWFx9gsQQtlaqC5ePIYcYy7+cI94TMnqUlrPjisOnUowBw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'CPHcOcmWYTC5YI64wjT6IXQ2H6I=',
                                                                                      'timestamp': '2022-06-25T14:33:15.456492561Z',
                                                                                      'signature': 'tfvSKBZj0oI6tP/Qbf5mKhiLnOH0bVB00Hms5xXE2JK56yUYn0wwF126e1W4tNbW6wbJIxnj5ovkAojoihP2BQ=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'v+9uLVHcfV4B0h/LSF1sPehbM3A=',
                                                                                      'timestamp': '2022-06-25T14:33:15.338511427Z',
                                                                                      'signature': 'ba5MIOp4aAfWseXebzA25Y0u+luJRCDkDRufkJ/SH2HjRnpzA9flb0LmM+Utvlp0yda7G0JgNTv0sjz+XzTMAw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'ZXGWoFt+znfMK5ak72vUXU4v1cU=',
                                                                                      'timestamp': '2022-06-25T14:33:15.533699638Z',
                                                                                      'signature': '0BYJubGKYLIPsGaoo8WZ1LHjQCyImlS+PiMEcJHZXuAj4lVyB/NZYdbDVrk9KNi7cdzMr/H/BRKpnfA2fn1KDw=='},
                                                                                  {
                                                                                      'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                      'validator_address': 'AkY0zpe4/D9saWS5UEKVyHvTNPg=',
                                                                                      'timestamp': '2022-06-25T14:33:15.455213486Z',
                                                                                      'signature': 'tqOit6j8GlFar0q1Kv4a6/MUX9SkfBdpzzcxrwuFvr+65QQ82dg+aAdbl/YCMIVCB8unk13Nl7ndHgdb/lPDAg=='}]}}}

        # Valid multi-send tx with one transfer
        tx_info_4 = {'F3F0D53074BBAE063E937610AAD2B4328ADC2474A856BFE14452EE4CBCD5F114': {
            'hash': 'F3F0D53074BBAE063E937610AAD2B4328ADC2474A856BFE14452EE4CBCD5F114', 'success': True, 'inputs': [],
            'outputs': [], 'transfers': [
                {'type': '/cosmos.bank.v1beta1.MsgMultiSend', 'symbol': 'uatom', 'currency': Currencies.atom,
                 'from': 'cosmos144fzpepuvdftv4u4r9kq8t35ap2crruv4u3udz',
                 'to': 'cosmos1r2z7rdlfau43zh0xp0wpx4mnf4lmwry2kjsmu6', 'value': Decimal('7.696000'),
                 'is_valid': True}], 'block': 11552103, 'confirmations': 48161, 'fees': Decimal('0.001000'),
            'date': datetime.datetime(2022, 8, 6, 11, 34, 15, tzinfo=UTC), 'memo': '984708177',
            'raw': '[{"events":[{"type":"coin_received","attributes":[{"key":"receiver","value":"cosmos1r2z7rdlfau43zh0xp0wpx4mnf4lmwry2kjsmu6"},{"key":"amount","value":"7696000uatom"}]},{"type":"coin_spent","attributes":[{"key":"spender","value":"cosmos144fzpepuvdftv4u4r9kq8t35ap2crruv4u3udz"},{"key":"amount","value":"7696000uatom"}]},{"type":"message","attributes":[{"key":"action","value":"/cosmos.bank.v1beta1.MsgMultiSend"},{"key":"sender","value":"cosmos144fzpepuvdftv4u4r9kq8t35ap2crruv4u3udz"},{"key":"module","value":"bank"}]},{"type":"transfer","attributes":[{"key":"recipient","value":"cosmos1r2z7rdlfau43zh0xp0wpx4mnf4lmwry2kjsmu6"},{"key":"amount","value":"7696000uatom"}]}]}]'}}
        api_response_4 = {'tx': {'body': {'messages': [{'@type': '/cosmos.bank.v1beta1.MsgMultiSend', 'inputs': [
            {'address': 'cosmos144fzpepuvdftv4u4r9kq8t35ap2crruv4u3udz',
             'coins': [{'denom': 'uatom', 'amount': '7696000'}]}], 'outputs': [
            {'address': 'cosmos1r2z7rdlfau43zh0xp0wpx4mnf4lmwry2kjsmu6',
             'coins': [{'denom': 'uatom', 'amount': '7696000'}]}]}], 'memo': '984708177', 'timeout_height': '0',
                                          'extension_options': [], 'non_critical_extension_options': []}, 'auth_info': {
            'signer_infos': [{'public_key': {'@type': '/cosmos.crypto.secp256k1.PubKey',
                                             'key': 'AxH8+DixTsVgS+h0GyS5cNZ0RO8236182BSYPGCCguX8'},
                              'mode_info': {'single': {'mode': 'SIGN_MODE_DIRECT'}}, 'sequence': '95962'}],
            'fee': {'amount': [{'denom': 'uatom', 'amount': '1000'}], 'gas_limit': '200000', 'payer': '',
                    'granter': ''}}, 'signatures': [
            'SaOfTYvFGB9i0FiCglHNP8FjJzXHMAHyqH+Y8BRfp2hYzSOgC+I4V9PL84qd+7x7RWexPotdBU+u2nvGLzZuSA==']},
                          'tx_response': {'height': '11552103',
                                          'txhash': 'F3F0D53074BBAE063E937610AAD2B4328ADC2474A856BFE14452EE4CBCD5F114',
                                          'codespace': '', 'code': 0,
                                          'data': '0A230A212F636F736D6F732E62616E6B2E763162657461312E4D73674D756C746953656E64',
                                          'raw_log': '[{"events":[{"type":"coin_received","attributes":[{"key":"receiver","value":"cosmos1r2z7rdlfau43zh0xp0wpx4mnf4lmwry2kjsmu6"},{"key":"amount","value":"7696000uatom"}]},{"type":"coin_spent","attributes":[{"key":"spender","value":"cosmos144fzpepuvdftv4u4r9kq8t35ap2crruv4u3udz"},{"key":"amount","value":"7696000uatom"}]},{"type":"message","attributes":[{"key":"action","value":"/cosmos.bank.v1beta1.MsgMultiSend"},{"key":"sender","value":"cosmos144fzpepuvdftv4u4r9kq8t35ap2crruv4u3udz"},{"key":"module","value":"bank"}]},{"type":"transfer","attributes":[{"key":"recipient","value":"cosmos1r2z7rdlfau43zh0xp0wpx4mnf4lmwry2kjsmu6"},{"key":"amount","value":"7696000uatom"}]}]}]',
                                          'logs': [{'msg_index': 0, 'log': '', 'events': [{'type': 'coin_received',
                                                                                           'attributes': [
                                                                                               {'key': 'receiver',
                                                                                                'value': 'cosmos1r2z7rdlfau43zh0xp0wpx4mnf4lmwry2kjsmu6'},
                                                                                               {'key': 'amount',
                                                                                                'value': '7696000uatom'}]},
                                                                                          {'type': 'coin_spent',
                                                                                           'attributes': [
                                                                                               {'key': 'spender',
                                                                                                'value': 'cosmos144fzpepuvdftv4u4r9kq8t35ap2crruv4u3udz'},
                                                                                               {'key': 'amount',
                                                                                                'value': '7696000uatom'}]},
                                                                                          {'type': 'message',
                                                                                           'attributes': [
                                                                                               {'key': 'action',
                                                                                                'value': '/cosmos.bank.v1beta1.MsgMultiSend'},
                                                                                               {'key': 'sender',
                                                                                                'value': 'cosmos144fzpepuvdftv4u4r9kq8t35ap2crruv4u3udz'},
                                                                                               {'key': 'module',
                                                                                                'value': 'bank'}]},
                                                                                          {'type': 'transfer',
                                                                                           'attributes': [
                                                                                               {'key': 'recipient',
                                                                                                'value': 'cosmos1r2z7rdlfau43zh0xp0wpx4mnf4lmwry2kjsmu6'},
                                                                                               {'key': 'amount',
                                                                                                'value': '7696000uatom'}]}]}],
                                          'info': '', 'gas_wanted': '200000', 'gas_used': '68251',
                                          'tx': {'@type': '/cosmos.tx.v1beta1.Tx', 'body': {'messages': [
                                              {'@type': '/cosmos.bank.v1beta1.MsgMultiSend', 'inputs': [
                                                  {'address': 'cosmos144fzpepuvdftv4u4r9kq8t35ap2crruv4u3udz',
                                                   'coins': [{'denom': 'uatom', 'amount': '7696000'}]}], 'outputs': [
                                                  {'address': 'cosmos1r2z7rdlfau43zh0xp0wpx4mnf4lmwry2kjsmu6',
                                                   'coins': [{'denom': 'uatom', 'amount': '7696000'}]}]}],
                                              'memo': '984708177',
                                              'timeout_height': '0',
                                              'extension_options': [],
                                              'non_critical_extension_options': []},
                                                 'auth_info': {'signer_infos': [{'public_key': {
                                                     '@type': '/cosmos.crypto.secp256k1.PubKey',
                                                     'key': 'AxH8+DixTsVgS+h0GyS5cNZ0RO8236182BSYPGCCguX8'},
                                                     'mode_info': {'single': {
                                                         'mode': 'SIGN_MODE_DIRECT'}},
                                                     'sequence': '95962'}],
                                                     'fee': {'amount': [{'denom': 'uatom', 'amount': '1000'}],
                                                             'gas_limit': '200000', 'payer': '',
                                                             'granter': ''}}, 'signatures': [
                                                  'SaOfTYvFGB9i0FiCglHNP8FjJzXHMAHyqH+Y8BRfp2hYzSOgC+I4V9PL84qd+7x7RWexPotdBU+u2nvGLzZuSA==']},
                                          'timestamp': '2022-08-06T11:34:15Z', 'events': [{'type': 'coin_spent',
                                                                                           'attributes': [
                                                                                               {'key': 'c3BlbmRlcg==',
                                                                                                'value': 'Y29zbW9zMTQ0ZnpwZXB1dmRmdHY0dTRyOWtxOHQzNWFwMmNycnV2NHUzdWR6',
                                                                                                'index': True},
                                                                                               {'key': 'YW1vdW50',
                                                                                                'value': 'MTAwMHVhdG9t',
                                                                                                'index': True}]},
                                                                                          {'type': 'coin_received',
                                                                                           'attributes': [
                                                                                               {'key': 'cmVjZWl2ZXI=',
                                                                                                'value': 'Y29zbW9zMTd4cGZ2YWttMmFtZzk2MnlsczZmODR6M2tlbGw4YzVsc2VycXRh',
                                                                                                'index': True},
                                                                                               {'key': 'YW1vdW50',
                                                                                                'value': 'MTAwMHVhdG9t',
                                                                                                'index': True}]},
                                                                                          {'type': 'transfer',
                                                                                           'attributes': [
                                                                                               {'key': 'cmVjaXBpZW50',
                                                                                                'value': 'Y29zbW9zMTd4cGZ2YWttMmFtZzk2MnlsczZmODR6M2tlbGw4YzVsc2VycXRh',
                                                                                                'index': True},
                                                                                               {'key': 'c2VuZGVy',
                                                                                                'value': 'Y29zbW9zMTQ0ZnpwZXB1dmRmdHY0dTRyOWtxOHQzNWFwMmNycnV2NHUzdWR6',
                                                                                                'index': True},
                                                                                               {'key': 'YW1vdW50',
                                                                                                'value': 'MTAwMHVhdG9t',
                                                                                                'index': True}]},
                                                                                          {'type': 'message',
                                                                                           'attributes': [
                                                                                               {'key': 'c2VuZGVy',
                                                                                                'value': 'Y29zbW9zMTQ0ZnpwZXB1dmRmdHY0dTRyOWtxOHQzNWFwMmNycnV2NHUzdWR6',
                                                                                                'index': True}]},
                                                                                          {'type': 'tx', 'attributes': [
                                                                                              {'key': 'ZmVl',
                                                                                               'value': 'MTAwMHVhdG9t',
                                                                                               'index': True}]},
                                                                                          {'type': 'tx', 'attributes': [
                                                                                              {'key': 'YWNjX3NlcQ==',
                                                                                               'value': 'Y29zbW9zMTQ0ZnpwZXB1dmRmdHY0dTRyOWtxOHQzNWFwMmNycnV2NHUzdWR6Lzk1OTYy',
                                                                                               'index': True}]},
                                                                                          {'type': 'tx', 'attributes': [
                                                                                              {'key': 'c2lnbmF0dXJl',
                                                                                               'value': 'U2FPZlRZdkZHQjlpMEZpQ2dsSE5QOEZqSnpYSE1BSHlxSCtZOEJSZnAyaFl6U09nQytJNFY5UEw4NHFkKzd4N1JXZXhQb3RkQlUrdTJudkdMelp1U0E9PQ==',
                                                                                               'index': True}]},
                                                                                          {'type': 'message',
                                                                                           'attributes': [
                                                                                               {'key': 'YWN0aW9u',
                                                                                                'value': 'L2Nvc21vcy5iYW5rLnYxYmV0YTEuTXNnTXVsdGlTZW5k',
                                                                                                'index': True}]},
                                                                                          {'type': 'coin_spent',
                                                                                           'attributes': [
                                                                                               {'key': 'c3BlbmRlcg==',
                                                                                                'value': 'Y29zbW9zMTQ0ZnpwZXB1dmRmdHY0dTRyOWtxOHQzNWFwMmNycnV2NHUzdWR6',
                                                                                                'index': True},
                                                                                               {'key': 'YW1vdW50',
                                                                                                'value': 'NzY5NjAwMHVhdG9t',
                                                                                                'index': True}]},
                                                                                          {'type': 'message',
                                                                                           'attributes': [
                                                                                               {'key': 'c2VuZGVy',
                                                                                                'value': 'Y29zbW9zMTQ0ZnpwZXB1dmRmdHY0dTRyOWtxOHQzNWFwMmNycnV2NHUzdWR6',
                                                                                                'index': True}]},
                                                                                          {'type': 'coin_received',
                                                                                           'attributes': [
                                                                                               {'key': 'cmVjZWl2ZXI=',
                                                                                                'value': 'Y29zbW9zMXIyejdyZGxmYXU0M3poMHhwMHdweDRtbmY0bG13cnkya2pzbXU2',
                                                                                                'index': True},
                                                                                               {'key': 'YW1vdW50',
                                                                                                'value': 'NzY5NjAwMHVhdG9t',
                                                                                                'index': True}]},
                                                                                          {'type': 'transfer',
                                                                                           'attributes': [
                                                                                               {'key': 'cmVjaXBpZW50',
                                                                                                'value': 'Y29zbW9zMXIyejdyZGxmYXU0M3poMHhwMHdweDRtbmY0bG13cnkya2pzbXU2',
                                                                                                'index': True},
                                                                                               {'key': 'YW1vdW50',
                                                                                                'value': 'NzY5NjAwMHVhdG9t',
                                                                                                'index': True}]},
                                                                                          {'type': 'message',
                                                                                           'attributes': [
                                                                                               {'key': 'bW9kdWxl',
                                                                                                'value': 'YmFuaw==',
                                                                                                'index': True}]}]}}
        block_head_2 = {'block_id': {'hash': 'gjad00qxO/O2jsUIVLF9t2NyT18NjIprVZEsEiJJMZU=',
                                     'part_set_header': {'total': 1,
                                                         'hash': 'zDOdIRrm3C63btVDVTynndBb8FpP4zqavpf/KGt1tIM='}},
                        'block': {'header': {'version': {'block': '11', 'app': '0'}, 'chain_id': 'cosmoshub-4',
                                             'height': '11600264', 'time': '2022-08-10T07:03:48.179724216Z',
                                             'last_block_id': {'hash': 'NmbF4djYGEx21f0o3OY+FLxY1Pfba9VFestd+91u1uM=',
                                                               'part_set_header': {'total': 1,
                                                                                   'hash': '4SejLrB0yb9D/iUyTZdzEO4RDq9iH4WokRrdf4piLbc='}},
                                             'last_commit_hash': 'Eo75/SggCkUNaS5j545hEuyqkc0Npxn2YJNSvuoujKk=',
                                             'data_hash': 'i6iS/Q8BznpZNDSPmK31Klg56P8FwPNyfVl3LDvYU70=',
                                             'validators_hash': 'WSrvokYhIO2nlQKMvBluTlnHghHDPo+D2ZIDZdCdQjk=',
                                             'next_validators_hash': 'WSrvokYhIO2nlQKMvBluTlnHghHDPo+D2ZIDZdCdQjk=',
                                             'consensus_hash': 'gDZJZbfCzJ3pYcCZi0en+T8ZcAd+uILg7Rw4IkCIiMc=',
                                             'app_hash': 'GponL0KVQ69CvbcnI3kRp28ji5BBROElckH/9xAgBWc=',
                                             'last_results_hash': '7SdS3AtxAxSd79mPMSDJH8HAWybLcEELhK9ESVFHJ2Q=',
                                             'evidence_hash': '47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU=',
                                             'proposer_address': 'ezou/ls/zfgZ/PUmBzFM7+R1S7Y='}, 'data': {'txs': [
                            'Cr8BCrwBCikvaWJjLmFwcGxpY2F0aW9ucy50cmFuc2Zlci52MS5Nc2dUcmFuc2ZlchKOAQoIdHJhbnNmZXISC2NoYW5uZWwtMTQxGhAKBXVhdG9tEgc0MjM5ODAwIi1jb3Ntb3MxM2szazNuMG43empscjNtd3BwYW1kaDByNGpxa2NwMmdyZ2E2ejYqK29zbW8xM2szazNuMG43empscjNtd3BwYW1kaDByNGpxa2NwMmd0bncyNWcyBwgBEMKQ0QISZQpOCkYKHy9jb3Ntb3MuY3J5cHRvLnNlY3AyNTZrMS5QdWJLZXkSIwohAydlyvFdq9FzaEw4MwtyrbgV00kfPJA7knoYtA5W2q8iEgQKAgh/EhMKDQoFdWF0b20SBDMyNTAQ0PcHGkDisTkWsAqjvtpO4Q+hX2lqZD2fPhJ2haOzrP6+8Emc/TExU8qCHNFZCGGqIllsjZx9mcwUC8m4g4RgWjG0JXTZ',
                            'CpMBCpABChwvY29zbW9zLmJhbmsudjFiZXRhMS5Nc2dTZW5kEnAKLWNvc21vczE5bGhhcjY5aDM3NGhram05NTM1eG5yNGE0MnUyeG43eDlzM3B5ORItY29zbW9zMXdjbndwOHgyNnJyajRtbHI3dGVzMjZxcWN5eDJ0Zm5zYWQ0bGd1GhAKBXVhdG9tEgczMDAwMDAwEmcKUApGCh8vY29zbW9zLmNyeXB0by5zZWNwMjU2azEuUHViS2V5EiMKIQMs08AnkKnBSRf1PJuOU2ormAVejwyPJIddISfBPEwujxIECgIIfxgmEhMKDQoFdWF0b20SBDIxNjEQkaMFGkCav7VNRAWJH1ZHwOdYV0u+S46ArYnRhQJnbXjyussmsQgpth4/Pzq2+zzajqajKkyBmzj7YH6M6UC+9fdZUZr7']},
                                  'evidence': {'evidence': []}, 'last_commit': {'height': '11600263', 'round': 0,
                                                                                'block_id': {
                                                                                    'hash': 'NmbF4djYGEx21f0o3OY+FLxY1Pfba9VFestd+91u1uM=',
                                                                                    'part_set_header': {'total': 1,
                                                                                                        'hash': '4SejLrB0yb9D/iUyTZdzEO4RDq9iH4WokRrdf4piLbc='}},
                                                                                'signatures': [{
                                                                                    'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                    'validator_address': '1o7sDS6CSPHsZM21he22HspDK9g=',
                                                                                    'timestamp': '2022-08-10T07:03:48.189490894Z',
                                                                                    'signature': '9czENvozRZec5AdQIfxwbuGZCvv32H50fyPo1Lcc7GxCqNOql3RAexBzIbXg8aNKdivi/w8/rOF1OG4o53eEBQ=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'rC1WBXzYR2Xm++MYl5CT6ORKoY8=',
                                                                                        'timestamp': '2022-08-10T07:03:48.136064634Z',
                                                                                        'signature': 'KkviMlFewSRBOrDJpb0ENXUnYOs6Xem8JW1EcHIv1B6sXZxqBREHbJ3Sj45cB0CW1w7gs6nca2AZlX9v6mJ4Dw=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'g/R9d0ew9jOmug30m33PYfkKobA=',
                                                                                        'timestamp': '2022-08-10T07:03:48.456820282Z',
                                                                                        'signature': 'kzEfWFKDaxBsA9pr3S+Ahj8393MjQ/CP1b1EH+Clx/y7kl/R35n4xCo6MmzRRLwdpwfK6MXXWuJDjroi3IwXCQ=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'IZnq6JTKOR+oLwHCxhS/6xA9BWw=',
                                                                                        'timestamp': '2022-08-10T07:03:48.077900765Z',
                                                                                        'signature': 'RLiaNoq37chSKEskheNT5BlrPNm4B+crqxWBKLlYHpHHRQzYkB4n7i5eMmWqOh/mwj+echCgeppV5yZoVH/IAQ=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': '0tRY+SCey4yiqrHZngZhG4Eqh5c=',
                                                                                        'timestamp': '2022-08-10T07:03:43.600665616Z',
                                                                                        'signature': 'ORxGtTq5j2IeO/X32oQQJ4QK+tlsWqzqakW7h4xqn90usK73p5st/eLbNO5skswm/aZBkfyfA7xT16ojHjirCg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'bXAfpZUyaI3xa6+VIRN+jBTLsxY=',
                                                                                        'timestamp': '2022-08-10T07:03:48.447643051Z',
                                                                                        'signature': 'IYHUwZ6BfHQiCWE6zbOwZK8aCs++qEVe9Br++aic60Uq96uOTSbEFHXgOAhhutOBaiErYtJyjmGPJ3/kLMtsAQ=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': '7VCeeAl+EwapH+3o6Ft10Gvd9uM=',
                                                                                        'timestamp': '2022-08-10T07:03:48.102335262Z',
                                                                                        'signature': '3+xjErqIDYwTh1VHC+OifWkzuHHiAFXj+ApLzHVlAln/IScWarkYTihF+TmLZ/3ZWwzTuvdbsLO9qx8wAdiECw=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': '9Zc0qJanaJQ2vDQiJE/YYq4YnFw=',
                                                                                        'timestamp': '2022-08-10T07:03:48.408252218Z',
                                                                                        'signature': 'zwKdOHXpFDPTeBd2LNHeJtp0ejvoG1pBiY2pXIRvyC042L5JaBsp2tMFowAMyZ6lk6SKeJxQlCNleDVNPFIkBg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'aPJweVkNysw6wcSJKhoAjzSPWW8=',
                                                                                        'timestamp': '2022-08-10T07:03:48.269904299Z',
                                                                                        'signature': 'oHOT31M7ykJlUQnj++DB5Qk/56eHuaXfiIQfP1CZTOXG3JJ/Jl6ZYTTLkN4smeywwHx67wDMpl5hT1sMtb+BAw=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'Z5uJeFlzvpTU/fi2b4SpKZMukcU=',
                                                                                        'timestamp': '2022-08-10T07:03:48.112298721Z',
                                                                                        'signature': 'INuZjo2ooiMm1SsLj/cKKHitQGvHO2/LYBsk2/Ct/ZaAo2wFDzM9Ho4XGQEm61DgzeUMlUpMTjUlT+f2gISYAQ=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'HO0wcz0WJciatphndgbQ43s2dqk=',
                                                                                        'timestamp': '2022-08-10T07:03:48.147721620Z',
                                                                                        'signature': 'XGswJEE6KEdg1AnS2C/ipWjn8WvxTuRhrZhe1qa/wCzbMPkgAk84dplOWAvNJKDPCLHxXVUbcXlWnh+Xl/QXAA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'sRZ9BDfbnfDVM+4qzeSBBxOb3S4=',
                                                                                        'timestamp': '2022-08-10T07:03:48.135623554Z',
                                                                                        'signature': '3+6kWuQu3Ve44ihoKrWm2gaWkBxxFoHv9YMY5vxzd4M/VwowZ7zWuPw/hruJr7lrVl4+2zHNArukQdTLnv8tBw=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'USBWWacX3/uW4FT4vREIcw4Xrqc=',
                                                                                        'timestamp': '2022-08-10T07:03:48.179724216Z',
                                                                                        'signature': 'V8+JQhFlT0npWfqNhG1apGxVIEKMVfndAgiWVrqYeAwDolyZR+GW65ZhQYlPscpX7gUJk7Pc51rak7PjX0N5Ag=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'CZ4rCVgzMa/eNeX6lmc9LKfeoxY=',
                                                                                        'timestamp': '2022-08-10T07:03:48.202039943Z',
                                                                                        'signature': 'lIeLIS3Wmq2qRKEbksf50N+yyiQfZOITKc3Wx8TEfKKidFlpQcOtHF4A2Ihqf8Kio8I+aT9NCH5pQ10cKUpaDA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'MZIPm8Ojm2aHbMfW1eWJ4QOTvw4=',
                                                                                        'timestamp': '2022-08-10T07:03:48.140440873Z',
                                                                                        'signature': '6BvksnomCsa0z37oF50mALrYTIQefh2DhzMrr32KoizY75LO8hf2azxNunz9uv7Eh1oQZ2+XZGYluLBUcv8ABA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': '2mqqqVnJ74ij6zex8QfLJmfruqs=',
                                                                                        'timestamp': '2022-08-10T07:03:48.182031540Z',
                                                                                        'signature': 'MYBXGtvOKSJjztyoCzz1ALTShQRrG5YILv72KHXmHPvpSNqulCyB0IrZdA6gCtGBP4xXXqN0s37ZZPKVQmMvDw=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'TrEoJnX3JLWQJvIXPCPw3Jk28Rg=',
                                                                                        'timestamp': '2022-08-10T07:03:48.113284707Z',
                                                                                        'signature': 'bHjGiMi94h7/5ogDKBpW0H/aQDBK60eI2FefJEvUB1/2FrmuTCPgCjp0g77/+pskzouVcXfm9QEabIDBn0/KCw=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'sApjI3N/Mh6wuNWcb9SXoUtgk4o=',
                                                                                        'timestamp': '2022-08-10T07:03:48.111099790Z',
                                                                                        'signature': 'A7Y8jsdfx4aMepqcyvlT1myEewqaxFJPvXloVo3Mb1tWwZIFfenmbEUr97p9o0hhwzAHelayQebo3WSC9rncAg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'AZucopRNPMNsfHMoPvPVjlbIpdQ=',
                                                                                        'timestamp': '2022-08-10T07:03:50.186408325Z',
                                                                                        'signature': 'HUFN2dIYZNKCP60ugMKJw8T48tFEYPaw1195/qep0iX3vjcBwkARZHuQwj+AxsQ4inM5MQMRXXDkGpYjmxd/Dw=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'UdslZiBO4mZCfqimy3GYNasXC+k=',
                                                                                        'timestamp': '2022-08-10T07:03:48.163503687Z',
                                                                                        'signature': 'QAUjWzRhSsWjmQ0+/s0qW1ulpwGOLD41sGrm4k7tSypMRZUmu04jMrkY+oXSwa2zpyFxAwYQHaW2RYG4xeBKBA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'Wlnch0b9cn/d1cv1y7kMb2Fsz5s=',
                                                                                        'timestamp': '2022-08-10T07:03:48.229614639Z',
                                                                                        'signature': 'bdYkYt3ciVIWHRxl0jwnsEbCDVYEtmDeMHsVbpUueKG2Aqk2DemEir1954xU1qycQoQVooqio9IoWPsHN6pTBA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'nBfJT3MTu01uBkKHvu3l04iOiFU=',
                                                                                        'timestamp': '2022-08-10T07:03:48.314850963Z',
                                                                                        'signature': '20w5IbkRuoZ3QqxWBahmBClgQTAdEq64pD+iTM/lI2sOyC05TSgybDepIykR1qBJYxv8HV81QiGPDg6IJtKwCA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': '2fikG3gqpqZq3IH5U5I8fc57YAE=',
                                                                                        'timestamp': '2022-08-10T07:03:48.106851707Z',
                                                                                        'signature': 'pjMzHJo9k8YOcC3V/CfyAFYD6hVi7Lvvezg/MDZvBQLRea5jZ7HbIef1bSW6xUEWwaz1BmIaxe6C4uxgG6PxAQ=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'ZxRgkwzNybBsXQVeTVUOuNryKR4=',
                                                                                        'timestamp': '2022-08-10T07:03:48.235498848Z',
                                                                                        'signature': '2S9kD5bN0BW8htnjD3g5HTffN/lnhlcQy5qfZ3WAasZ3cnriUM43bqI7crv2o6AlMmIcJ81rySLAcS0h0zgrDg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': '6Dv8Q20s6NzJ7AWJsuW3NeN/uFw=',
                                                                                        'timestamp': '2022-08-10T07:03:42.342172212Z',
                                                                                        'signature': 'JdEfOJCGqwnGRVBtegdh4V2gxeoMlHlvUk8kfzkxJJtvo3d3zUrBdxniZDH39iaeRLfq70uU22G97EKxvEQiDg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'gZZf6KFfqAeMkgLzLkz6cvhfKiI=',
                                                                                        'timestamp': '2022-08-10T07:03:48.092833504Z',
                                                                                        'signature': '+i+lv3y44MdDXdRQ+r6fki5+J897hHItGWOef/gfzTlm6MFSMWthLrGsyU6UqeMIzYsxxZNYxfqgSexo2pFNCw=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'ddqzFvTKE2f1MqtxqAt/plq2kDk=',
                                                                                        'timestamp': '2022-08-10T07:03:48.325169363Z',
                                                                                        'signature': 'Fhc3SbeS3gGOp4uze3P3jJGs1WaNEGh8+qFHWN9zot/rl5VdwLCVnrmmq06VZ15cRK4MFBeVbwIuKzNFIF+CBg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'leBg0HcTBw/pgi9sUL12vMv58Xo=',
                                                                                        'timestamp': '2022-08-10T07:03:51.378521442Z',
                                                                                        'signature': 'EB7k3yPHg20cz8/L9C+EYsiGNVr6GdDQ3Aj1TTlIRcZXEC9mnedpMtmattR/VHDp+yLNx8Xjl9M+tM49rl1SBw=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'ppNdh3uXdsRblu6uUmlZo7mlqxo=',
                                                                                        'timestamp': '2022-08-10T07:03:48.248923838Z',
                                                                                        'signature': 'zAQULUQg52B1B/HxyMbcSHaW2D0waGgHSVwhTOAnkcbahG8EahktOvB+m2f0QX0P3yBvx/vzXZZlQrvRNEPYAA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'zAWIKXj8X91qdyFofhTAKZrgBLg=',
                                                                                        'timestamp': '2022-08-10T07:03:48.154435939Z',
                                                                                        'signature': '163Xff3gPfDKeLCiGnzNWkT5LtqmPNhDK5/Kay1CDff/PhBdbtt1aQu7NpoY5FxdtbZt0dLmkS+dPucN4urRCA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': '/V1U4Nnkdo/qTA3/3In6lrZlfzI=',
                                                                                        'timestamp': '2022-08-10T07:03:48.116116903Z',
                                                                                        'signature': 'bN132YHIBUeSRcivNofhjho9gAxsBNCZ13KOGKdT5atSmr/aPJOLckzhg7ID8LJteSFzNVeBU2+qxDIqvzs3Bg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'V3E7t0Icf+s4G4Y/yH3tXoKaqWE=',
                                                                                        'timestamp': '2022-08-10T07:03:48.167404819Z',
                                                                                        'signature': 'UM9HP/nQT6d6CBM7YUzBgPjFBrN+Jku7L0k8DfpTq2A68XC+TKXHMq1yU8Zubvt7/DSTgRugxLMG9cTMD0vKCA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': '6AB0DGjIGzA0XDriumOPpW/2fu8=',
                                                                                        'timestamp': '2022-08-10T07:03:48.220188110Z',
                                                                                        'signature': 'xfdtzgQrcWUdf0K9/oiT9iwQbmBMJmqVXn8Nc3PVkRUbIz4tWbDYUF1tPavDgUZhIuCMnY73lKQR4v4KmXWWBg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': '0UpULodWw6lC2f2Ic9wumneYoX8=',
                                                                                        'timestamp': '2022-08-10T07:03:48.322030809Z',
                                                                                        'signature': 'BPlLsoERrXZRdgfKa98pWc+B1GbzSo9mx5Ns2fTinw595VoWhOsqBuBMEe+E8DBW7wSOI0H6yWRusQMSRmdSBA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'ezou/ls/zfgZ/PUmBzFM7+R1S7Y=',
                                                                                        'timestamp': '2022-08-10T07:03:48.198058753Z',
                                                                                        'signature': 'jkSxA8bMSqjxumvMf4k3eYYYortxWwcphuawtlqdcERE0ZxxqsaxszmoY/rZ3ScAZagUsWq939qRN3cZeUMXCg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': '3qELGQGaE7F9GrnK4XMhza47BIc=',
                                                                                        'timestamp': '2022-08-10T07:03:48.209706791Z',
                                                                                        'signature': 'QoahXImk97R6IIcTURx1RDxL7/UpiF0P3Ivw9qXa39FlnAjZELVdF3/davyTqGkq+IvSLjt0a2WkBVd2kPNTCg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'JURdDrNT6QUKsR7GGX1dy2EZhts=',
                                                                                        'timestamp': '2022-08-10T07:03:48.136983065Z',
                                                                                        'signature': 'zrsIEbOeuHmAtPGxHDeSi9dGi92Js0jWZo6Pk7YJLmqmE9ArVzuFfUZN/3pYLzs8SDfhmJSzG9Y06sqhCxuJBg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'zIf1a1hiGBHitaR/OMYWbilc424=',
                                                                                        'timestamp': '2022-08-10T07:03:48.211164830Z',
                                                                                        'signature': 'YmpsERJozyB/eBymDepa783ZXInUEI/PD2XAiOKAax/2VX2qdyPRdqnmGSyBNKcjMkZFtcJGUqk8wnyI9/8QBA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'aWq8lRhv1loHBQwoqwDJNYoxUDA=',
                                                                                        'timestamp': '2022-08-10T07:03:48.296264316Z',
                                                                                        'signature': 'wPa9FB+wUILr2O9mAfv2JAgpux1YhW0lolVDFV1J7JukIfummbKBJAxsh5b035vwVLfZ5OOFF/uvvWq2Be9pBQ=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'RqP4uDk7qhU8QOVyLq6C6g1Isy0=',
                                                                                        'timestamp': '2022-08-10T07:03:48.321894237Z',
                                                                                        'signature': 'xoCRoDTbLUkp0aQqDag/RalyVj2bJXqtkJVxJ7sMmmdnWAntp4J3LzgG8A27CDf5MiUb50e1JfVveA+qyVX+CA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': '1UCrAiCIYSrHSyh9B22/vEo3ei4=',
                                                                                        'timestamp': '2022-08-10T07:03:48.200348522Z',
                                                                                        'signature': '8INHoozxR+w/21aAcMTHkyrSwT+k+tIf5Ifjtw4dmyX0cjLsLqVfpZUh2pa73bFK3CjYISr2APFj5YGX6vlPAg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'C0LkfxVOJNEBhLsS4yNHqsYca4A=',
                                                                                        'timestamp': '2022-08-10T07:03:48.168942980Z',
                                                                                        'signature': '2cKK0KzqSlcwefT447PV/gG4dyyWKsqztCKyopUUwCXxPsbbuUZmdkREUquN4wfFm6c6G9LSDK7+ons7TujhAg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': '07wmsaneyNVrCjuOzSMRDsTNRac=',
                                                                                        'timestamp': '2022-08-10T07:03:48.273288286Z',
                                                                                        'signature': 'gu/LO4BFcWamcDEyOkYDkeAR0Ey04Hi6z8DbvgKBPIP+RM+IYnowRGXDGdkD+gn2uGLnUka5BABjN5/6PiBbCQ=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'ncQBIJm+dDGJB0uF5JiRrjs/7ps=',
                                                                                        'timestamp': '2022-08-10T07:03:48.222938626Z',
                                                                                        'signature': 'g0XhDFbR0p02rZKpIgh5n23+zfSrI3+unlr4HCAh2QytDxZhUKaNBH4CHfXbKxMiXQGJgsCnncZpq2/9wDMKDg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': '4HD6TwULr36idhxSpqVxV4BoGTk=',
                                                                                        'timestamp': '2022-08-10T07:03:48.219125577Z',
                                                                                        'signature': 'gK3D3VLp0rMtN6Mq/bTujVZN78NAzUYXmQ7aSB7Id2LukDJE4e+Nm6a41KMRN7kOXJtsl5r7Y156KGBmHfc6AA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'hLPYkiui8ko5R37BSVeZG+Gud2U=',
                                                                                        'timestamp': '2022-08-10T07:03:48.164386048Z',
                                                                                        'signature': '9mAjRsgpgXFNZ4GO/mRacQ+Ln5GksZPT/VqMfny/MXdCba5h8/5+yN271VVQbKnTwMu2wNNjv96iMvIsXdVOBg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'sBVSUtc7fut00qjMgUOX5mlwqDk=',
                                                                                        'timestamp': '2022-08-10T07:03:48.198989135Z',
                                                                                        'signature': 'WwJEnIXQ8wjbdyaOXWBIr7fJcLn+NWQhIJVIEaHkTSRcgr2dSPGNWTUlEyI/2n5lBA7k8EduQVDpkA/1oewPDw=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': '7nOhl1HVjF7ARMEeP7euaFoQ0sE=',
                                                                                        'timestamp': '2022-08-10T07:03:48.104405568Z',
                                                                                        'signature': '2dGQjiRNf4N5Z4NPa6xcpw2uXy96QFKDBdzdpja7qhlgdqLMcFeZnJm2AtDoIv8YobfpcaGsJqskfPVqx+CsDA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'usM/NA80l3UfEkho8EnsLokwrC8=',
                                                                                        'timestamp': '2022-08-10T07:03:48.404401285Z',
                                                                                        'signature': 'CaCxwwd1R+ZEk7OnxhjwTFmZ4IMpkfpzMqz27uM5aAGVPLNaNHBh6xoHaeY2sRvOlpBVY6m38OiWS3/j72bSCA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'tOEIXxyeuw6plEUssbgSS6ib7Ro=',
                                                                                        'timestamp': '2022-08-10T07:03:48.113243466Z',
                                                                                        'signature': 'TvP/EP0tUrSqUvf+SoMeO4jy228ixZzO7yYqk0D6JGPjXRQG6/luuEit/wd9wE/R1NyS1DpL8OjwX8GJLy9UAA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'jg7je3saA43RReMPHvl982Ge9Ck=',
                                                                                        'timestamp': '2022-08-10T07:03:48.327531617Z',
                                                                                        'signature': '9MP5HIsSSRssCrmzX9ivH/W6ZutsfuqUKPdGOsw4upLJdDDGjer1WWgb9Q1K2F8N2era5iaE7S/KfJGWOvGgAA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': '4KEmUlnOnHj3ayEZaATxspRtsmo=',
                                                                                        'timestamp': '2022-08-10T07:03:48.229196351Z',
                                                                                        'signature': 'h5Zdpuv1Q/1g+5BtvYz8ztiLx97AL39ns3yI+ogSebyLokx1m2Q+cCZbTHkdLxHkVvP/AniW8SqgexcWZj3MBA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'Kl/s8mw/tDQmrGs9tYpavFgA8qA=',
                                                                                        'timestamp': '2022-08-10T07:03:48.162214419Z',
                                                                                        'signature': '+JnhrMqRRlcITIMfKPk5adzaIey6HQ5HsbcOYr/y7oYUl40S7ipGGoJUaOMcp0WCw4p3nyjE7Shsr0RX2xEnAQ=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'ez0B91Tf+EdO0ONYgS/UN+CTidw=',
                                                                                        'timestamp': '2022-08-10T07:03:48.121518340Z',
                                                                                        'signature': 'EdZf+GMbc0yhHoGHIjXV5uEavdCsDys+wNZQV0/Vrn4g6HCKMdXf20wUGbHoRDYfvqrEmH00i83RkjkGPcg+Aw=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'u3a8YyLHUzp8zTrxwInHs5cfsBI=',
                                                                                        'timestamp': '2022-08-10T07:03:48.174450543Z',
                                                                                        'signature': '/OJXO/I7N1G0ZzS5DWmjSqzVpdMc6PmxVDv0TZnNsG5wa7AMTwkpQ8yZuTjugaXBlEz7tHmbmJnzG5/tpAbhCQ=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'LJzMMX+yg9VKx0iDimTykQYDnlE=',
                                                                                        'timestamp': '2022-08-10T07:03:48.250091928Z',
                                                                                        'signature': 'qZEhVxS6VUw9wdX76KRvAHjII2vyYyVbOqDCKCw+L+nOmmXqmnhTtZkQNRR3amqsE4LVtZijmrUQLT4/cB9YCQ=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'sxWB6f9XEEVTE3Di1IlaLW/t7Ps=',
                                                                                        'timestamp': '2022-08-10T07:03:48.258930728Z',
                                                                                        'signature': 'QaLh8Bv+8s2KICfhD8qy3v3bZCfIUkVGYYmKLEFkll5itE4fqFdINrvRvH/o+Zc37w93xz/H+Buk3sZ9tDnVDg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'LCpem575AxZPor0/FAVx3fAqAMw=',
                                                                                        'timestamp': '2022-08-10T07:03:48.235691071Z',
                                                                                        'signature': 'DjG01TB3i24N9A5r47NnUcn07VzDNwMvTmrmIBQ9DuSt8lTXt69J3kulWfUrZLdwPJVeamzRihBFqVmYFWanBg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'nfjjOMheh5vISwqqKKCLQxvVtUg=',
                                                                                        'timestamp': '2022-08-10T07:03:48.246909843Z',
                                                                                        'signature': 'j3vInD7XztH9Nv7FTlFY+9LIe8cLWHSmmEybU8gSuGk/FIgvN/X2srxLAENkkc1OHFxzGpNgJztBIJ//Fls0Cw=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'wjVmIrSVcllhtbIBo4LdV80zBew=',
                                                                                        'timestamp': '2022-08-10T07:03:48.209239780Z',
                                                                                        'signature': 'jMtlzSuZgOrz6OrzFBA7G21as0YZmdtkwaMShn8LWkIS+mBaOdDqVzE7+MOPO93eHFuCnq8jxOyQiKx1F56NCA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'kcgjp0TeUPkcF6RrYk7fj3FQp90=',
                                                                                        'timestamp': '2022-08-10T07:03:48.293434068Z',
                                                                                        'signature': 'U6anI6d5S/BfGOYbd1VbC7zb+gHQDpQp2eCWmJQODiasaKamk5LrL+hbdDAdCWcAwDMNdUI95I6a/E3MCM9YDA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'xSrNsyBX9ccxu91IRguTw1AN0yQ=',
                                                                                        'timestamp': '2022-08-10T07:03:48.228274252Z',
                                                                                        'signature': '1QNEmukontEV5+UshzQEkjbfpusMDd5a4hbYniMARg4qZHGWJkCNdNJ5hOqPyp1eJLQkA6mhzT1lr6/40BybAA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': '+USWk75IKU7P/0f1r7PDHB36sxM=',
                                                                                        'timestamp': '2022-08-10T07:03:48.142306269Z',
                                                                                        'signature': 'RV4kUlYJOWoLl5BHGEEtrhMG8JpwkfXA/70PA0QHNwGEDmoews8c+5VrTuT8GALNqRe7loMA5ZsWwUXG/D8YDw=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'G7KWcA1vzyMYqtotCY5NQEebbH4=',
                                                                                        'timestamp': '2022-08-10T07:03:48.093653468Z',
                                                                                        'signature': 'Owj9MPv3+b6TSB+UUuzK1OL7x/zgc0/srU8j/stELUMn7289IIytrPJGtc9In/D33MX7vsGeRAED3CWlH5uTDg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'Sbv7G6GnUFLjIm6OHg7+szkYuLI=',
                                                                                        'timestamp': '2022-08-10T07:03:48.274218359Z',
                                                                                        'signature': 'HGqNSgZHcwTIukRgwnr9OSVu4y2l19laYBpYb298Vae+Em5iClSrpvk2lCpHDtgPZfNJKRBx/52NCH7kz9A+DQ=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': '6+1pTmzhIk+x6KLdjuY6OFaLHis=',
                                                                                        'timestamp': '2022-08-10T07:03:48.447636718Z',
                                                                                        'signature': 'ErmtlX/Dj8EB3B0UKUvcQwTH9h+TpTqppopsJ/vkhicsyH72y8UAQcf/KyOCFSU5qa3HIutVK7GrAmgl/PMVBQ=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'sHZaL2/MEdisRidfrAbdNfVCF8E=',
                                                                                        'timestamp': '2022-08-10T07:03:48.219255741Z',
                                                                                        'signature': 'TKR6FQuz77CkRWtYQRotoQ9pX/aTVGFLdVahEHZjHhRS1kM07dehRTEyhrpORq6Q/Xn7206kX3DBq3B/RJF1Aw=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': '1e3JNDFMibRZUmIOnJkrHckBhEI=',
                                                                                        'timestamp': '2022-08-10T07:03:48.187740855Z',
                                                                                        'signature': 'u5JfhXLPjl+0a62tICFSjQn9U1MK7tKjxa68k5JvXfatizr9Rtx0Z4c5uhvut7zRw7/o3AFUV2MgTdGv9FU9Bg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'uezh17TdgOhoJj6jqvJyucfxKS0=',
                                                                                        'timestamp': '2022-08-10T07:03:48.107394685Z',
                                                                                        'signature': '84hFteyDmJHc1zE8LldNf0KGYYpnxWtCd3vm19mEY/7lJ9QX60Mv6VmnaZMn5GwuNZ6/VfC14DOQauy4ULEJBA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': '1/fHlIfBClzxq+sdvYHo1JdXxCI=',
                                                                                        'timestamp': '2022-08-10T07:03:48.129756241Z',
                                                                                        'signature': 'rdb2sRcXHOIPfvM4agnANB6JhJr4Ov0ZTR4CGJprCjrEm70744g94hGEMdJDvSrvDQ1PfR0g2AWJCcLoM3YXCA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'GuC9Qy+aUSJHSmRjJdGvpgaGkuk=',
                                                                                        'timestamp': '2022-08-10T07:03:48.177313272Z',
                                                                                        'signature': 'ufTbCb4YTg5BOBtagtW7IFXo2cw+ESqwP4mPkb9vCOSryrN5UVvqUi1FJEmhOt3lwZfeQao5I3w3eFZtBPBFBA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'QtZwXnFmFrSlRCvaoFC3xun93kM=',
                                                                                        'timestamp': '2022-08-10T07:03:48.113401752Z',
                                                                                        'signature': 'eCArYNYyegJ6wZ34w9J5KvVD4gbj5akEOSQseLHq/7KTRaUXcw0RFhTpXB0wWRJduOWKnNd6F8tt1keZbSkfAg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'gI1rBUoLbT/19erwplz8ZMVD+DM=',
                                                                                        'timestamp': '2022-08-10T07:03:48.205960877Z',
                                                                                        'signature': 'V1T7190BNkxsco7jqyR/ibyOWgbY+gZKxQfjkH0YJWVPBOqsOphFpPPUbKX9dbhAUYt+ueN+OdjWnkXBslnjAA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'sr9orUztb+j3GqytAQA0Nuvgcp8=',
                                                                                        'timestamp': '2022-08-10T07:03:48.344342024Z',
                                                                                        'signature': 'dOY0s0c4n7j1gXCtDkZQVyeLL+CnFzlzI381tSzNilamG88EIV7nXZQwJ9A5Bl9NqdEA+SaaiKWn4odb5rLwDw=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'wt3ZcAz13sBFfcQjgpsx6o/U+dQ=',
                                                                                        'timestamp': '2022-08-10T07:03:48.111844949Z',
                                                                                        'signature': 'yMLVy0fJGzKJ2ZNJYN1ltCPFvPJ8pgZd7/S7CokyhCIiiYz9CY6+SPTUND+GRMGf9qnp6oRGNRbtRBEHrHcZBg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'OZZxwv5LJxTsbofU7kVO8V8zqio=',
                                                                                        'timestamp': '2022-08-10T07:03:48.282468949Z',
                                                                                        'signature': '8N2T4xiPQ9cIjq/UQ0j7RPC8LyIPlZkXa8dlRPOJVg8x1S5rAbPLgoeOPdWkWykXjpfp3S7CONi1OjJqjrK8AA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'CrujbFTdDKankK75agHUOS42NF8=',
                                                                                        'timestamp': '2022-08-10T07:03:48.093082148Z',
                                                                                        'signature': 'xaARyuZjW9EivhdBae2gfLeO/tjLXEZACVfEU9l9cR73gbpUx0iow42SXSRkyIPBPFGeISBfs9f6G1grElKpCg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'tUOn30h4Cu/vWToAPNBgtZPE5rU=',
                                                                                        'timestamp': '2022-08-10T07:03:48.119642465Z',
                                                                                        'signature': 'X4H/gwbSqYHypPEVibrPXmTNZ995r5TgogawoB0+SwgH0U0GJtLwnzk1XiYkW511DCTNMQpyxIbt2K3oVWHbAg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'v0y01Z0Z1FHPXnvEk0nfSqIi14s=',
                                                                                        'timestamp': '2022-08-10T07:03:48.119997941Z',
                                                                                        'signature': '8xB2wJrFYPbfqcInrz+Bz8VWbHo5ClT9PTYtQp/Q0EfpXntje+z/bJ/Pzyo52BdGj0I0fj/XPzuScoXxtKjlBQ=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'M2Po+XsC7MACiechc9gnVDBHrNo=',
                                                                                        'timestamp': '2022-08-10T07:03:48.246465949Z',
                                                                                        'signature': 'UjVUfTFaboYOyIn5O1V4+69Sn9KU+Q+zuZi+6BKsrYXNmHN96EiAk+443ehZKjAWzCYZsKD9jrUEjHbC3Nj3Bw=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'sjayojrXFqnY2Fagy6di8yNRXF8=',
                                                                                        'timestamp': '2022-08-10T07:03:42.342172212Z',
                                                                                        'signature': 'cgpKWH2DNJc95HOAHG8I7KTr1eRUIeliGAvF+fRoxxwdoSmwyTWmsBXGGmqvHy3W3VmFq2vGK2BghdTNjtSyDA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'aPW76s7xFMcg6pyYv6L/3gHFT9E=',
                                                                                        'timestamp': '2022-08-10T07:03:48.359765871Z',
                                                                                        'signature': '9QgBbPiJT+XqdZA0Hk/ZAz24k55rgNmOaIKsu4oD4VWjbaVHxsx1sGdZHT8IGGoKm7e2Nr4aC2hgOuJGlA2yAw=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'AAqlq/WQqBXry9rgcK/1C+Vx64s=',
                                                                                        'timestamp': '2022-08-10T07:03:48.339980914Z',
                                                                                        'signature': 'ynleAoFnqXsdUyHHVndU7Duxn2J3XP8o6GHcSvzE13bOjTP0N3sISAPhDNyRmWCiXXl6C8VhdeB/cJtgh5xnAg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'gBF3Ltfd8syc16SMjAqiSG6fTpc=',
                                                                                        'timestamp': '2022-08-10T07:03:48.164761550Z',
                                                                                        'signature': 'lBIw65qhbI/C1w0Mr2dvA0YNGwcqqutMKycrBBaR4DSHhdRKc5W1RVSuJrEkLrEagAgd1NvgpbUifL6urW8hBA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'UuFkYTRDK/lTK0iBxu0y5Arlot0=',
                                                                                        'timestamp': '2022-08-10T07:03:48.176880018Z',
                                                                                        'signature': 'PXuWU7UMfPRnik7b0W88e4sSqNnjbFfXacZ2MTKb8sa2/cTNadQdhY8Yzo2BPHgedZfiVpX9L419F01NAOx4CA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'WrNTt0jUXyDfzhnXO6ifJuHDTPc=',
                                                                                        'timestamp': '2022-08-10T07:03:48.180142783Z',
                                                                                        'signature': 'I6/DdzQRzZH5YiDUSURNQ8/TVPtgA84J0LpD9lGGxubrnu8nD1oHrXaKWThUnDEJ5GKGQQPa72Mg+XEdvumBCw=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'pPHVU08/qQWk2mBuihCDSXZRH/c=',
                                                                                        'timestamp': '2022-08-10T07:03:48.177001986Z',
                                                                                        'signature': 'Fl1OTIdRlIeZtCOCxa+0FipPcZqwf3dtzV2JPL2t0nc+TW8zTyi/unDhTimWSAfASx129WBbLcu3PoMvqUsYCA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'zFziQY2oXHjX+J/sqrCN3OMUwMw=',
                                                                                        'timestamp': '2022-08-10T07:03:48.334965723Z',
                                                                                        'signature': 'CaFSCZP2LbkzwLBSDC5uJgFNGAwq476rKX87pmM50B9O9BJElJ4f1yQ1MDwIqP/Rgtx7lYnYyuBEOQg/PXR7Cg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'ISI0dc6G88fNXphaqI/CSinJeBM=',
                                                                                        'timestamp': '2022-08-10T07:03:48.138158595Z',
                                                                                        'signature': 'il/HtsN35JHO6i7GaFF9WRfGzN6xoUuRoxO2jcx8TU9p5RbN8Ns2GpYV13bT8ARamzYj17JpVuw43tQCNvMrBQ=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'a9RwUCEzKpC5I5fY1yyjlQy4WOs=',
                                                                                        'timestamp': '2022-08-10T07:03:48.217951686Z',
                                                                                        'signature': 'JYK/Bs6izqiLqPgLecE1XSAenZl2A05mQDcGcoNDeV4ieFP0NhEpY9oCWn6KQv2o3OL2m3O7NCGaS7e7XIoHDg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'tMwD8qyiLEPeHtOFoQS6hrdGJ5I=',
                                                                                        'timestamp': '2022-08-10T07:03:48.079530125Z',
                                                                                        'signature': 'heTJYp3a4fCJM7SUHtn6sl+WZTA9H64SnVJkMzY/oN1WMc2JHgfPh1UuGu9BG0bf21nbQqrou2oZnaf+ykmzAQ=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'KQZ9/jNSpASB230R7kSxChD8QpA=',
                                                                                        'timestamp': '2022-08-10T07:03:48.101412829Z',
                                                                                        'signature': 'IQ2mMJB4GrfQpzSIwSKmW4jaXibCmPl7Nig1RDR1ujylFlx9CARolHgleIIyZ+JSrrkNObEZaKAa9zf15UddBw=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'bqhjtEujafc55lWVdw2rksiakhI=',
                                                                                        'timestamp': '2022-08-10T07:03:48.132726776Z',
                                                                                        'signature': 'ZCe4WZHj7XHoLWIXHPlkrOoIU1siB3fKvX3fj96zpKHdhi4se3I1vGWOqX9THDL+TtuspGGPzA68oLAG3q9ZDw=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'O4RcmvHWnp+7YgtpqyJrKLrJeYU=',
                                                                                        'timestamp': '2022-08-10T07:03:48.187442595Z',
                                                                                        'signature': 'DdxjUe6mM4NM1rZlaYFyIUaC3SRqi+LysN9GfTfzFXhyLn7a21UWu6jkblK981d9AoWFRVDY5cRx4ROz43fTCQ=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': '+ACDsYPEAZklxytfSC8iRqwtQ5Q=',
                                                                                        'timestamp': '2022-08-10T07:03:48.452519968Z',
                                                                                        'signature': 'l7n6+O6wgAAacFEnYJg8/8NCuArWgoCdOGF6m3mCrKK9nGp2cKK/AJd5I56+5cBLJAz4TyP5QP8FbDE1aTtlCA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'yzP4IXwHlS7KGPU8H+r5E+kUMTc=',
                                                                                        'timestamp': '2022-08-10T07:03:48.139843056Z',
                                                                                        'signature': 'AhL64HmhIBauUTRtJhLI84DJhTRz/8YrzXOpG/FeJbQWmccA32D+V0Yw7DISP1ewzX7ooJPn4UDEqVfDf5D2Cg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': '1l2wTRHvxDXrttKWhYyt6/1ETDg=',
                                                                                        'timestamp': '2022-08-10T07:03:48.286410491Z',
                                                                                        'signature': '08EkvH5L3a+nuEow173sj+7RlqHJcVv/mzwWUXIgOGXkC3IGPFdgNEqFIHo1SNY3E38PlJ25nhy89S65tL9+Dg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'znaAM9cnxqKJgK73Ny0SQyfIEKg=',
                                                                                        'timestamp': '2022-08-10T07:03:48.116581064Z',
                                                                                        'signature': 'naVinFC3PdFx86ZYdPgXFOQWWGc0VjIW8cHyHqqK7rARfuYyLsGPX4mmN1U+F+ZRtkleqXzhHcgUyspWZyJLCA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'xTJ9ZM30oEvhIG5l9bYdRJI2MOY=',
                                                                                        'timestamp': '2022-08-10T07:03:48.311799612Z',
                                                                                        'signature': 'NnNokI7/bF/3nppDOMa4xc0rybkEeW8puJQoQVjV6ASdR/ldUB6pJvY7XbV8/d0RBJdi9PDo4Yt/gS0NqKs2Bw=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'j+PP+moHsJPkQbuE2httq/U6+i0=',
                                                                                        'timestamp': '2022-08-10T07:03:48.216548169Z',
                                                                                        'signature': 'QK9sfMoj+aXn0Fb0eqUBpQEgHv2RbIU5SBFAkX1z1FrwYqMPP69EfsXI4Q+y3/vmXZOc4IXbZh7CGSde2yfSDA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 's0WR2nmq0CE1NOLpFfUN5c298lA=',
                                                                                        'timestamp': '2022-08-10T07:03:48.280737791Z',
                                                                                        'signature': 'HcXxzvVPQ84veYnR7sT8xr+fZr8QnLbH8cdAA7T3a6ptBUALu/5/zX/9daeW5365aa+WD6NmHPTl9UnUAyGeDg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'PlGqiCA216cPlPPoZBa3YBt43Yw=',
                                                                                        'timestamp': '2022-08-10T07:03:48.144605716Z',
                                                                                        'signature': 'OntRanm8xUc9NZOi8kcAba11HglP9nrjdnKhj6ObYs3cwee62LumF/yLTPcTws1BxZUbvw9c1Aqle5kg1lhLBA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': '+0+yWmG0k6W/jjzUtej1tATajiM=',
                                                                                        'timestamp': '2022-08-10T07:03:48.316736311Z',
                                                                                        'signature': 'JFfX6DsQEa4f0uTYHn1geyx2ycZf4FoU5waTbkoNTdV1cHmTAMKh+Bmlrd1evgWjR0klC9ZAFidhqH2DzeJkAg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'TJIjD6wWIwPZgcBt0iZjpPx2Irw=',
                                                                                        'timestamp': '2022-08-10T07:03:48.147471096Z',
                                                                                        'signature': 'IiRPf8Wuu+2uOmEDzabOOfuNkm/khbv1OW42pjf+8lD6CISTbxAC9Eobm674E8mOE4F9jQ8/c6I3B1PtKcKsBA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'cyzu9Uw3Tdxq3sv9cHrv0H/twUM=',
                                                                                        'timestamp': '2022-08-10T07:03:48.191720852Z',
                                                                                        'signature': '1A7IpeUNzjatuTZ/qDJvDgXsROvxoVBFgYSwX9MJ2VLm4EMCVGcCV5GRZvwBd1OlTm9idh82NaC0c05lZpFzAA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'YKqsuC+rnZDLLfCqDM5FVRAe2Qw=',
                                                                                        'timestamp': '2022-08-10T07:03:48.228419772Z',
                                                                                        'signature': 'j8iZyAWy845Sr9duhyzWIDDJjPo0DDeRynyzTLCA8fTStr6MkdXJUC+cVB63wIhK61DS0K8IDNw13UYGMuheAA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'Fw/v1tf0ppqucKJEFfxOLJKN4uU=',
                                                                                        'timestamp': '2022-08-10T07:03:48.142504393Z',
                                                                                        'signature': 'KuwEqW3X7KGc7V1YmNLbB9J3qQbxb5TTp6y40DGcHZXDSydzvYPeNSW6o1gjq3YlJaduzTYdhtgy9RPlZdIHBw=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'JJNdWfqpTnk2Usv0cWxgQc16pAA=',
                                                                                        'timestamp': '2022-08-10T07:03:48.195564764Z',
                                                                                        'signature': '3kUonXRyb0EZ/vTty6Wszwk9jaxIXRMsaWWJfbjuO42rJKhB5HXU3xH2eLiqYCdXk3ExIYN02WJpEjWH8v+cCQ=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'bLR9eGsvNQwTpgu3fTmKyC6QCYU=',
                                                                                        'timestamp': '2022-08-10T07:03:48.086192983Z',
                                                                                        'signature': 'MAl3k0OQko2n6W6ywswYP8YxLQvZWzDrbt8nkXgUdOrZD+2A09BK094hPzKG7SRVuUumvShgogSxfxF2DUjQDg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'BYWemGKmaA2+q1EDYsELFmG5dDo=',
                                                                                        'timestamp': '2022-08-10T07:03:48.319742588Z',
                                                                                        'signature': 'rDn6PXrq08hmrVUGdYKxYU3a27mye5h+Lg0OEtPLDYrrWiEkfXUe2mUnnzEQvSWhfhlU2J64kZ3LQLICXJtJDw=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'EsKqDeZvo/nWZNA9XW9tgha22oE=',
                                                                                        'timestamp': '2022-08-10T07:03:48.159269061Z',
                                                                                        'signature': 'QbEMPW5W9t7LW3uEz3wtu+CudPpvlTOT5dfllp8oP3eZodoEyajVVR2kMUhdgiK0sbhT5iPve2w54JFZfthCCg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'HpzpT9C6XP65AfkLxljWTYWxNNI=',
                                                                                        'timestamp': '2022-08-10T07:03:48.153711141Z',
                                                                                        'signature': 'lLnLsgKgOMt5Dn2WaOTUtzQeZv2m9WJvy800ObkaMhDt8iMcOxdjJe2Rn/6gAA6vH5O+p8qbz+ucqD4cbz7rDQ=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'K5pV07+T1zdd0ge3XF7U0rkdkUY=',
                                                                                        'timestamp': '2022-08-10T07:03:48.119263513Z',
                                                                                        'signature': 't/L4vTrynW+uqb15j2vY2+dE6Xu8/OxvgWmAIPQ9uB1IKUG0VEP8SQrG/0pfOEvSLGBg6TopoKzkvOfl1WgzDw=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'fmL0bLzp+x3lRGAG1tLu+4I0jaA=',
                                                                                        'timestamp': '2022-08-10T07:03:48.344503653Z',
                                                                                        'signature': 'Fr5KeCt8yrK0O1gzVjOQqs0z0iQtqipRzh1xToUGlKBMsHGbkpBHlwoTrnJleIa4Tv+VJnXqNQd8dSsgbmyxAw=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': '+OUDK5jV0yRC4yW2lwtDT3UuET4=',
                                                                                        'timestamp': '2022-08-10T07:03:48.183094841Z',
                                                                                        'signature': 'NxgaNSp1yDYaFKlFVubxYR66cf614Fk1PtcdW+0kZnr9wlSSf+prZZNAKW9IuExzG9CkorSMnTuEw+9hC3ucAw=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'ePHXqXc/ySJzngo3BafKBr6jCIM=',
                                                                                        'timestamp': '2022-08-10T07:03:48.195337857Z',
                                                                                        'signature': 'iv3Ly080W+ZhFKPqICcNmLHc+HGEPS5oV5RHLxWBK5Y7Gw9+nLTMd86RV6LDE4FFevqQB36jxsdtbEhaKqdYBQ=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'SvadalQ2ww41hMFihDPeVedYvMo=',
                                                                                        'timestamp': '2022-08-10T07:03:48.198148328Z',
                                                                                        'signature': 'yOl+4Haw+vMTfCqaPJAi2BgP4Q03//gU2M+zPv2K5URufvv/0J+T3kS7WTqn6y6Xr4VKaZMwQ8St+QOacWQZBg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'gYlktPs20oEJw+hTd4szIxsnxfw=',
                                                                                        'timestamp': '2022-08-10T07:03:48.318707708Z',
                                                                                        'signature': 'DiYNibQr6Zr9JjDgNpYkjXhqln6y1QvL4eOfculGmPjdRRLikJaLr68svnw1JW46KDNuRWotthlfBoAmsmYXCQ=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'nulNu4b3IzcZK/KRsOdn/Scp8Ao=',
                                                                                        'timestamp': '2022-08-10T07:03:48.158612393Z',
                                                                                        'signature': 'O+oxZMj+wH/xQPhtcqw6/X3vM1Qrote23L//+gKb+mySsXKhbmLnZKa2izV6HhNn2pvM0YK7Rt8WNGw5TuioDg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'bzIrr11z1cdycZQZAbHYZkdtXJA=',
                                                                                        'timestamp': '2022-08-10T07:03:48.149025281Z',
                                                                                        'signature': 'X1jMxORt4bKFrM8Pm8QBMx6zU7Mvha7p4VV/2BJT5ho5DRSuplJBHRmxtM7HR7Nud44020enbPQ12uiLWVsvCg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'E+4/BfIMatj9J8vvM91h1fmez28=',
                                                                                        'timestamp': '2022-08-10T07:03:48.203446352Z',
                                                                                        'signature': 'HXS+Rjrt+e+uP1US2b4cemkJpyDn4JhWZ06q3PbCeFZrHL5e4HApKVL+jbGHXLbL5cgSX6z9VZLUFatkuTDABQ=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'LIgtV1Zehqnuw0M7FQJfj5YxhFM=',
                                                                                        'timestamp': '2022-08-10T07:03:48.273867765Z',
                                                                                        'signature': 'Hyy7+0vpDv6SNlDxWdMNWN9Nc2OSA8lmftJcn7Ie7E61fGvoGm8GOCyOaDn4A8r74ijJWRbqdhFHezF3P4oDBQ=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'vbBGJZ63+3SigBXjHmTO6fCAIZk=',
                                                                                        'timestamp': '2022-08-10T07:03:48.244663069Z',
                                                                                        'signature': 'gqHQMtiC5k7dGCN96vrrjan6zYse65DY9MlYBV4lAj29onmYAlsk83wMiB3FZEsrSFIQElgPZeoiWjJV60xsAg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'u+Ve2bLkFuKzfBO77pzW564xRxY=',
                                                                                        'timestamp': '2022-08-10T07:03:48.113798685Z',
                                                                                        'signature': 'NmEygSSb/ppU6eLamZQqSegve0hkkh3f/GIZz120TI2hBIlW3gFz5wYStvx0JoOnK0Rnid+IcSEabqmFR/jfBA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'jIgCqSERQWnSWBzUbjymhT9vKn8=',
                                                                                        'timestamp': '2022-08-10T07:03:48.255054394Z',
                                                                                        'signature': 'X7sPqPdqq30sKVGz/FimTDEoCOx5Ft9JXPwKmmgLKJlCTE+6898uWRj7pnPoXliQXIIg8W2pTRncLQdAHIKvDQ=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'AAAB5EP9I35LYW4vpp307j1JqU8=',
                                                                                        'timestamp': '2022-08-10T07:03:48.129188536Z',
                                                                                        'signature': '7utK3CXTmKNpHObOdPvO63DmlU1SjnfYi9680AYfw/8a/YLH/DUBK+CKZhTnhshlyS76syknlPXa13PybbqkAQ=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': '9v1jZazFOCtq1lZs0pcZBLdffiQ=',
                                                                                        'timestamp': '2022-08-10T07:04:02.019631090Z',
                                                                                        'signature': 'Q2YT99nmQJ4cRU0NLuDf2mnR48w47R6iLXA2Tr50O8ehip5AMtlJc4yMtcLYbHHpL6Ko/R1bp/USCPjarbm8DQ=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'mtCqGKkqGkN0Qm7ZuBktHWw9JpE=',
                                                                                        'timestamp': '2022-08-10T07:03:48.091052001Z',
                                                                                        'signature': 'yYzQCHPBcmTI5zIOlkjj9JJEJHa3xkxBimbOgMI7k8BKXu75iC7BWinIuUazTMIE5S38qgNcCCYw0yLf8MsjAw=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'RPBYL8sjsEQHRDaQb4IGz2VRLDY=',
                                                                                        'timestamp': '2022-08-10T07:03:48.314390969Z',
                                                                                        'signature': 'Q6nco0IEhJLnOhOb1r2cxBF/irkjfwJ0X9L6s8MDLeHpZygidkDiL+hoCkHfllkoEQ+Y8HXC/zfJEOwE4BfNCg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'KpE16IFgrwUsmruz9jAdfZniOEg=',
                                                                                        'timestamp': '2022-08-10T07:03:48.225041864Z',
                                                                                        'signature': 'CkAB70qsMLqEtEzRaVEHupzhrWzxBIPuezfhNfVlNK7qkoR7/+K4KxXJbOeVbzZfK+pl6xrZvPigKHoeNZbjDA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'biI0+IGBen25l9WUAFGFkfaSoUw=',
                                                                                        'timestamp': '2022-08-10T07:03:48.368955294Z',
                                                                                        'signature': '0f61iZSUiuuSBFNpktKy4bxi9oRZthMaLx+nx1vUh7CDpHPVP5jVPrt2+f8S5n7uJ8CpKZM96ZzaxQ4FuwR7CQ=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'lVpHyKyGMoJd1HXpCRPUCrCdP7Q=',
                                                                                        'timestamp': '2022-08-10T07:03:48.382771427Z',
                                                                                        'signature': 'uCKv2YdUOYdbv0r2c7VKz80l/JE9IiNr8tJXSx+TK9h7/HttLAQ5qwtsYKnYG1QvMIDCzdQ+aW3qf17OHv/1CQ=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': '9VcUJD0y+2W22Vop0DUOoMq7qOo=',
                                                                                        'timestamp': '2022-08-10T07:03:48.131957002Z',
                                                                                        'signature': 'ESNxE+KTihEKRnsr9zBfQ813QtovDlYNZu10awH7IgL+zE7ieY1I2Fqlspw0jUFzUCzKD5PIuI52gmcifFDtAw=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': '35KD2iWylkJul0OGFNHGLcEBnYQ=',
                                                                                        'timestamp': '2022-08-10T07:03:48.118904532Z',
                                                                                        'signature': 'e/osN5G6zkksgwGo03M1mTbK1ph8FG3/zjC9IBpri89xOhhDIcKlxAOcqRHGznWDeMEk+au8MdSJD+DWhrQeBA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'ak0Up6ybT3x/KNyQRuUCnRvwn0E=',
                                                                                        'timestamp': '2022-08-10T07:03:48.090397922Z',
                                                                                        'signature': '2I4lxWC9pcL2xA8ikM9bkLr+A4AxaZOeYuGZNwDEOH98M5/JSSzPAPxzZ8He0IFDc3dWdUbFF5cQ23OX48POBQ=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'SP1WDTywtVKSTLwPnCumiIP6ETU=',
                                                                                        'timestamp': '2022-08-10T07:03:48.216664770Z',
                                                                                        'signature': 'v/MMLOL8i9a/lYer+0UlYLO53BWUy1JwhKLnl36IXmzb46pJrugAmGVUxA/RUJSIpv8brhLkHNwzRO2+cdupBg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': '0KzHIE1xPP+ftEny1SwFRdx8E+k=',
                                                                                        'timestamp': '2022-08-10T07:03:48.273706405Z',
                                                                                        'signature': '42NTsuWqaNCvAqUL/Uc3ZPa8o4VdubSX/Uas8J+4kaML0Emx0JHkiEqL5w4oYhni2ka8VRG55OnxgWz1Bx4ECg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'QH8UTRyd6k7mqMvC1MAipldQa4M=',
                                                                                        'timestamp': '2022-08-10T07:03:48.276446935Z',
                                                                                        'signature': '4NIohh7nzbJp9mi/xcZIJjEIYk7uW/l75LCYJb9sYnVI4KNlJYoiw6A075F0e0XwZGwRi6EeWzzrz6iLBpntAw=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'lxOBjaVAsq1AzTqCGGXxyiiKG6o=',
                                                                                        'timestamp': '2022-08-10T07:03:48.073979292Z',
                                                                                        'signature': 'a67kXpSXU48sBVE3rE/VV953PtQPuCs2q1Wj8avsOuSpGxAw3nfTf0NO5c8jZKefnxYFOpyQje0bJ6LIhILaCg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'dCC3PxAomsoYrM0ctatUiCwE0tU=',
                                                                                        'timestamp': '2022-08-10T07:03:48.082626793Z',
                                                                                        'signature': '8mPzR++BJ4euFm8nlRkOw5+1I7T+0sLaA932bcJMw2WjlQMH9PMbPvdfg+WSGmtPKfuMK940a7TCoD4Tz9IPBQ=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'iKZQRfXuUCVggm2gf3ObqeuoRww=',
                                                                                        'timestamp': '2022-08-10T07:03:48.354820383Z',
                                                                                        'signature': 'NKnDQQzATbizLPkvISZ6es0iuCU6C3PDBWUyGfaIr32/t5ChvZi9bQZA0ZSVJtsDRG5qr8Ltl3cJtMUPhf2CDw=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'hGvk854xItKi0/5UVOJWEHPpVTg=',
                                                                                        'timestamp': '2022-08-10T07:03:48.285619725Z',
                                                                                        'signature': 'QKCD/9Qkifwu6oscaksGdqICG9urjpMHS6FM7ft/lFKYOwMJZmrT5wZ6uGpH7d+/w9sGqgjTdtJ6YVhHa0WYDQ=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': '0mmoHHdB9FjDHbf7FMWBdkIfsvg=',
                                                                                        'timestamp': '2022-08-10T07:03:48.182876335Z',
                                                                                        'signature': 'ysOLqUKh51wcF2uDdMVyg7GjICqaQtxpksrOh15fVeoJRNDfWFpxlPp0Yo02TMRqKgfwioX5yLcxaWXOLShUCQ=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'O0nKl8SWkDMWOochUocEie3r8IA=',
                                                                                        'timestamp': '2022-08-10T07:03:48.103352890Z',
                                                                                        'signature': 'jPLeOR/2pUcHHNBqgZhma8Y3k2UmIzG6gXglQ6Q1ID7V5JOhD5MCEBmhml5cMNNHZv8bV74F/nZiA1Nl+XnNCA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'pHEVwJ+Eb0b0mfOBs1tFJyUgSYc=',
                                                                                        'timestamp': '2022-08-10T07:03:48.255062932Z',
                                                                                        'signature': 'jnsp0Ucqr+Qi6+jpCHMM1Kgc/snMi1uQQJX0+bUzIZX7Ewbi232GH3hMG0Gg82Ec7qYjqUAaM/sYKlzuA/sJCA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'XXQZZsEntvZsCcyG3J5KwuKCY8c=',
                                                                                        'timestamp': '2022-08-10T07:03:48.212456228Z',
                                                                                        'signature': '5fvAKKGjFxVQsJPu2lSuVvW4LnsKfml3nTpxdimQCRGk4AXzVh8jxpiE3CHTPPPLrFUwOZavpfODX42txuQyDg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'h01qqDg4Snmj1NBiVB+Rv34xvbo=',
                                                                                        'timestamp': '2022-08-10T07:03:48.377730972Z',
                                                                                        'signature': '5X+nw9sxfxWQR+iIDVOkgqt+4H2KwYzPoFwZ7QbQ+tOlkKnGQ4Q8ahApdwlInsBS9iNaYB+zY3FshOaVHzGrBA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'bFDMRLTx3DKr0pcNis7LIErM74U=',
                                                                                        'timestamp': '2022-08-10T07:03:48.059452121Z',
                                                                                        'signature': 'm/GJKR1PTX7EMtD+jxEkpzBZyEGSvVcMJmZ2/7tyoriYekOpt94XpPFHOsDlUzTURarg+CbQq+xLHjdV0WgrCg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'AMzuz9AbLTM6G1ar98/4prjtJbE=',
                                                                                        'timestamp': '2022-08-10T07:03:48.127209858Z',
                                                                                        'signature': 'e7it8nMZ60CPJWUkt4A9vY6Eo87JIwr6+1hxBlYKqllqOhxoO5r6arbGUaBugLH5hoQuOZxf9o6jZcf1HdelBg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'TtfMQDiDPy6lqj9NRMWByOfL2GI=',
                                                                                        'timestamp': '2022-08-10T07:03:48.133105068Z',
                                                                                        'signature': 'sxupuoMPBdjwL6d4L2fFBv8aY90rwQqXpOE06z3S5YNGHyHKNoaXmfHSZUn4Qv01mUO5iaPO9TMVTT6q4QpYCQ=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'xJAyKbnq1BXHno+mnSu6YRdhfEE=',
                                                                                        'timestamp': '2022-08-10T07:03:48.158343420Z',
                                                                                        'signature': '0g/VbZtFEBcvmvojocKvrwLWAyOb//GU1zb313nIs6OeXwZBxvtPVXsxqasfk/yCpXynGhrIOUTmpiktjq60Cw=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'rkVqhaXG1G+jUMPsLcsA1mE1niA=',
                                                                                        'timestamp': '2022-08-10T07:03:48.200034647Z',
                                                                                        'signature': 'cB7lc4/I5HGsmUTl4/keGKqVzYENSb/oF3m3K0PriEYfR+XM2LNLTFY7xJBK2s7Dwu5Dh1yKcem679iRPDcCAg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': '/fVplFT5OihhW6dnfFblYvn/aPo=',
                                                                                        'timestamp': '2022-08-10T07:03:56.837318304Z',
                                                                                        'signature': 'Uzo9Du1iHXcZPKVUlBE7TOpoDjzo8jGVCFmisL3vrGC+sdZEjGaMr3RMUmOCqw97b6eRW2adeRtCe3v1ZSMPCA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'o8fATWIOqjN3dfADuNCYFYFnYzE=',
                                                                                        'timestamp': '2022-08-10T07:03:48.171796752Z',
                                                                                        'signature': 'vVFKQv+enEe4IAHEy7CM4duuw4PSCzm4Ca82Pkjr8/JRICOmF746yrmzKvM2iFitb2ZPwLn/7z+3+ZR9eR8nCg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'VbO//s6/oOV9oyLQ2iYsE2qRkmw=',
                                                                                        'timestamp': '2022-08-10T07:03:48.201143934Z',
                                                                                        'signature': '8RgIBqjeK9W7Zma2TQ0QcdIvQdOxp8u/adohoZjFJ/vGg7aoo5He00fSKy6CAIL8vUFpVeZjk4o7shHysmFkBg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'alFVTowM8xZaAcZ1qYosOLbrUSw=',
                                                                                        'timestamp': '2022-08-10T07:03:48.149513159Z',
                                                                                        'signature': '1LSb1MFSooob7vt1KHcmxl6VyYCknHUAErEFbEbGGqFjnZHjfBJQrP4PcP649TtOFz1hA7bVd7yLoeRyGL6fBA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'cMW05necWaJM/ZFGWB4nAhwq7CY=',
                                                                                        'timestamp': '2022-08-10T07:03:48.158957536Z',
                                                                                        'signature': 'e+89Pt974XwzcfsmQ+ppQitx/zDmp2H3hJ1IIuIbik9a7OyKQNEevJ1iEF5E2mVk03gURm2nQVI2MiH0+SkwCg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'kGsHKu2gU7GWQ0VuY97SM2QNLZE=',
                                                                                        'timestamp': '2022-08-10T07:03:48.374590626Z',
                                                                                        'signature': 'k+khozjwfslovOJpqHIc6nr2+PS/KfGMHyLSDBC50AEXP9HxkRJkoMkPP16uALmgEShkUhVq/NpLsVfLU21kAg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'xfBrucn6GpXCm9qMMNXcchCvIWY=',
                                                                                        'timestamp': '2022-08-10T07:03:48.576983027Z',
                                                                                        'signature': 'soBy3mjAH6rDEOr5cnNacoGmprdyQhQEJkpRGyv+Y2QVpfMfh7uQjt07gTh8Qo3Ej5Ox6y341f71tcvvproMDA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'N8ipncFSONRTwPvufCrL7f0nweQ=',
                                                                                        'timestamp': '2022-08-10T07:03:48.218348914Z',
                                                                                        'signature': 'PlgaJsU6HBmnQNrKAoWJbpE2la+RpKCdSZQzngiUcD3hPJY282InVuMFtD8Fq75euYPgLsrRdU7aysJrwULEAA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'Z0jWMuAOUkfCJi76lt6UbRruwys=',
                                                                                        'timestamp': '2022-08-10T07:03:48.164067918Z',
                                                                                        'signature': '1BjPecWtmpf+QzNf/zNrRMks3faaOojtPgGqfaVp4l1BCuM/338JMGWzgbeUqCtM6gUa57M8RETP+GKXbNbRCQ=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'tJmc1TXkzTK1kL60cCCnJPQLZeU=',
                                                                                        'timestamp': '2022-08-10T07:03:48.265881849Z',
                                                                                        'signature': 'JTXQGOb9vmeWXpDhmxwsiiAzy3zpgnhieIpWlBlIdZLDwU/rKo8Rd7+6Ww7tmBYZc860OJ8L/AE0+E4O6h5oAg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'EI5H/BuFRvmPfqUvJUfMREl9sb8=',
                                                                                        'timestamp': '2022-08-10T07:03:48.147174368Z',
                                                                                        'signature': 'vfrUguescGaR6LHP9uDChXAESeR6xQOR2F2VP2QnN01EM0xAEbEzVNAhNj1YsMKVtTew6QXg5McyeRsYNw+TAw=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'KCVaVyCeRxJOgaOO87DOGUn3Su4=',
                                                                                        'timestamp': '2022-08-10T07:03:48.209073128Z',
                                                                                        'signature': '0Yl0ZdtNPIEa+uO2NfaTKL3CxVXUyZNwvmA30mMYe81JMaDrj5nAb6zNVzTip5vrX8+xvteb4G/qfDdYsAz4Cg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'dQuDzDkHZ+NhhNTNSuoyEEYzxhA=',
                                                                                        'timestamp': '2022-08-10T07:03:48.148565580Z',
                                                                                        'signature': 'TOEKCuWXUE1CMHss5nFXdjx87rYI82OgugCd7XCu1qV4J2JTzNi42t4TNhRl0Qtl3e8D7aw6LbDGL6683ACJDA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'AJA3wsdWMvO/njmhHA6B6ssmLZ4=',
                                                                                        'timestamp': '2022-08-10T07:03:48.069957772Z',
                                                                                        'signature': '6igSXayget8KrACK3GxSLRIH+sefhtSFOqwC8HNzSuwZ4Hy227aIkuMr7cw+jyAi/Ny5nEOR9vHygqRRcXqqBQ=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': '4xUzuCrGeqF4i3C9fphb744SUqE=',
                                                                                        'timestamp': '2022-08-10T07:03:48.140757783Z',
                                                                                        'signature': 'oictA2Sh8NOxjp3RCVFZt/79OQ4+X6Jua3G9utQAUmmA6HJ6SjqVs3nMrIc6vDmcA5C++kruh06W1kE+uYLzDQ=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'VpsJ6j2WB8Xxo43tgc7SZMeqlMs=',
                                                                                        'timestamp': '2022-08-10T07:03:48.157028571Z',
                                                                                        'signature': '1Ry4XLjIL24d5L1MQXCvpWaEuKCv/aDMQf2ePPLsleMlbZ1M1wGOyq6CFvThdM3usTiPRIUpJHAyKGfzjRIXBg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'JanUUtNfEgUK3uazGTS7hcKBfXY=',
                                                                                        'timestamp': '2022-08-10T07:03:48.069828730Z',
                                                                                        'signature': 'l2eoc30/rKZSPn0W0XLKm5ReSfLlpB7DMS8ryuyOVxPDDej5MnQRX6F5c9rwRiC9oG2pmWGNCksiocIAv3B8Cw=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'CPHcOcmWYTC5YI64wjT6IXQ2H6I=',
                                                                                        'timestamp': '2022-08-10T07:03:48.210652219Z',
                                                                                        'signature': '01BAX4mewwmN3xTseNOYxeQhYrwWsJzFuavmQB8gvFARp2AFTVH8mk2VtezfK37ha7Mm6x0Ko8OXk8J0coo7Cg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'R3NnIYyfksOtmbXXNKNGz36KMoc=',
                                                                                        'timestamp': '2022-08-10T07:03:48.063622072Z',
                                                                                        'signature': '0ik5qNJNuKn/Sg0kRVsMuvWkTCDzGs2YdV1QEHS4p3Kc9dEotQovHIlzQyySxqRtp8zs1LaeWNjyAwBdJriXDw=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'v+9uLVHcfV4B0h/LSF1sPehbM3A=',
                                                                                        'timestamp': '2022-08-10T07:03:48.068526382Z',
                                                                                        'signature': '4M23fTqzNRlKH6+y8GSdoIPb6nNxhUkWNEnaBUVYDsDMKeEp706V5mGkpMS4MiCxvXkePA2pp+l80gmgcHS9AA=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'XZ6EdZSZBLvItwxCIx/BBE5A7hI=',
                                                                                        'timestamp': '2022-08-10T07:03:48.123264944Z',
                                                                                        'signature': 'dbPRw8108tn1Zj2BX5L8TS6RARIj9EnwWGl23zA7wvqSU7XWXqudL8c8NH0pEJYnlUSmAU7hq/kVmr+ogAf5Dg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'Fi2+6idmryfhNjtYOi+BWHdN+m8=',
                                                                                        'timestamp': '2022-08-10T07:03:48.207638572Z',
                                                                                        'signature': 'xgmaUpywIJPTxbMRku683xpUrtJNRgCXj5elowA5lEvUvLL2N7dTvuut5Uqrr8SPNlaJvy3oVO6wGrDyAz9EAg=='},
                                                                                    {
                                                                                        'block_id_flag': 'BLOCK_ID_FLAG_COMMIT',
                                                                                        'validator_address': 'p9nm24yl5GphrDYjXUyBhfe/EaQ=',
                                                                                        'timestamp': '2022-08-10T07:03:48.179413916Z',
                                                                                        'signature': 'tATxoMkKNkWr981ykEPFbElrmm8KlaqRi2ilm46m29rYLpAozayzgcv59tJ36IiHoKH7HN2afjK32tTt1Q4dCg=='}]}}}
        txs_info = [tx_info_1, tx_info_2, tx_info_3, tx_info_4]
        api_names = ['atom_scan_node', 'atom_getblock', 'atom_pupmos', 'atom_figment']
        for api_name in api_names:
            APIS_CONF['ATOM']['txs_details'] = api_name
            api = APIS_CLASSES[api_name].get_api()
            api.request = Mock()
            api.request.side_effect = [api_response_1, block_head, api_response_2, api_response_3,
                                       api_response_4, block_head_2]
            for tx_info in txs_info:
                results = BlockchainExplorer.get_transactions_details(list(tx_info.keys()), 'ATOM')
                if tx_info == {}:
                    assert results == {}
                for hash_, info in tx_info.items():
                    result = results.get(hash_)
                    assert result is not None
                    for key, expected_value in tx_info.get(hash_).items():
                        actual_value = result.get(key)
                        assert actual_value is not None
                        assert actual_value == expected_value


    def test_get_tx_details_doge_blockcypher(self):
        APIS_CONF['DOGE']['txs_details'] = 'doge_blockcypher'
        api = APIS_CLASSES['doge_blockcypher'].get_api()
        api.request = Mock()

        api_response = {
            'block_hash': 'd20d12753c3f81f29e40bb92f5a4ce23f695a473a0bbda955b13a35cac1e8c42',
            'block_height': 4172543,
            'block_index': 12,
            'hash': '7700fa249904b52d6924add4a3c937dfacf5dcf41e9b9e07113b1a3701daaf3f',
            'addresses': [
                'DCZyFU5Ytzvsm6MUHfkNhvhELByAnSTgYc',
                'DN7Tn4Mh8vhWf5bsMj4xXh32StyDy4pWmq',
                'DT4D9qKja5mYQtTeVU1at7MYDYZcosHq32',
            ],
            'total': 22597000000,
            'fees': 100000000,
            'size': 226,
            'preference': 'high',
            'relayed_by': '172.104.156.166:22556',
            'confirmed': '2022-04-06T06:33:51Z',
            'received': '2022-04-06T06:33:14.181Z',
            'ver': 1,
            'lock_time': 4172541,
            'double_spend': False,
            'vin_sz': 1,
            'vout_sz': 2,
            'confirmations': 17,
            'confidence': 1,
            'inputs': [
                {
                    'prev_hash': '3dfdce92c047a40031530c34f9d1c4d41949cfd47d207dbee0489b3a54bc7bef',
                    'output_index': 1,
                    'script': '483045022100803a85f837045a813ac6014c6b3866e58e2aaebf87b233dac33878e85108e36202205f985518779cb93b2bed315d2b7441cac190068a1f90beed5815bdafcddd41f4012102b3288cd4e7a7a6b062d39b6b907be51a0ab506cb4125566a04bf774aaffa4f29',
                    'output_value': 22697000000,
                    'sequence': 4294967294,
                    'addresses': ['DN7Tn4Mh8vhWf5bsMj4xXh32StyDy4pWmq'],
                    'script_type': 'pay-to-pubkey-hash',
                    'age': 4172541,
                }
            ],
            'outputs': [
                {
                    'value': 2324782535,
                    'script': '76a914517d31cf1d500d233ea0cdfd281cc29e6534674d88ac',
                    'addresses': ['DCZyFU5Ytzvsm6MUHfkNhvhELByAnSTgYc'],
                    'script_type': 'pay-to-pubkey-hash',
                },
                {
                    'value': 20272217465,
                    'script': '76a914f066353f632d474d90dc36b14f507cfac6ea92ae88ac',
                    'spent_by': '4da8cb762366fcd9dcf64f6262ff9f98ab9b5084efdb4dc2168411e572f32d52',
                    'addresses': ['DT4D9qKja5mYQtTeVU1at7MYDYZcosHq32'],
                    'script_type': 'pay-to-pubkey-hash',
                },
            ],
        }

        api.request.side_effect = [
            api_response
        ]
        txs_info = {
            '7700fa249904b52d6924add4a3c937dfacf5dcf41e9b9e07113b1a3701daaf3f': {
                'success': True,
                'double_spend': False,
                'inputs': [
                    {
                        'address': 'DN7Tn4Mh8vhWf5bsMj4xXh32StyDy4pWmq',
                        'currency': Currencies.doge,
                        'value': Decimal('226.97'),
                        'is_valid': True
                    },
                ],
                'outputs': [
                    {
                        'address': 'DCZyFU5Ytzvsm6MUHfkNhvhELByAnSTgYc',
                        'currency': Currencies.doge,
                        'value': Decimal('23.24782535'),
                        'is_valid': True
                    },
                    {
                        'address': 'DT4D9qKja5mYQtTeVU1at7MYDYZcosHq32',
                        'currency': Currencies.doge,
                        'value': Decimal('202.72217465'),
                        'is_valid': True
                    },
                ],
                'block': 4172543,
                'fees': Decimal('1'),
                'date': datetime.datetime(2022, 4, 6, 6, 33, 51, tzinfo=UTC),
                'value': Decimal('225.97'),
                'raw': api_response
            }
        }
        results = BlockchainExplorer.get_transactions_details(list(txs_info.keys()), 'DOGE')
        for hash_, info in txs_info.items():
            result = results.get(hash_)
            assert result is not None
            for key, expected_value in txs_info.get(hash_).items():
                actual_value = result.get(key)
                assert actual_value is not None
                assert actual_value == expected_value

    def test_get_tx_details_doge_chain(self):
        APIS_CONF['DOGE']['txs_details'] = 'doge_chain'
        api = APIS_CLASSES['doge_chain'].get_api()
        api.request = Mock()

        api_response = {
            'success': 1,
            'transaction': {
                'hash': '7700fa249904b52d6924add4a3c937dfacf5dcf41e9b9e07113b1a3701daaf3f',
                'confirmations': 131328,
                'size': 226,
                'version': 1,
                'locktime': 4172541,
                'block_hash': 'd20d12753c3f81f29e40bb92f5a4ce23f695a473a0bbda955b13a35cac1e8c42',
                'time': 1649226831,
                'inputs_n': 1,
                'inputs': [
                    {
                        'pos': 0,
                        'value': '226.97000000',
                        'type': 'pubkeyhash',
                        'address': 'DN7Tn4Mh8vhWf5bsMj4xXh32StyDy4pWmq',
                        'scriptSig': {
                            'hex': '3045022100803a85f837045a813ac6014c6b3866e58e2aaebf87b233dac33878e85108e36202205f985518779cb93b2bed315d2b7441cac190068a1f90beed5815bdafcddd41f401 02b3288cd4e7a7a6b062d39b6b907be51a0ab506cb4125566a04bf774aaffa4f29'
                        },
                        'previous_output': {
                            'hash': '3dfdce92c047a40031530c34f9d1c4d41949cfd47d207dbee0489b3a54bc7bef',
                            'pos': 1,
                        },
                    }
                ],
                'inputs_value': '226.97000000',
                'outputs_n': 2,
                'outputs': [
                    {
                        'pos': 0,
                        'value': '23.24782535',
                        'type': 'pubkeyhash',
                        'address': 'DCZyFU5Ytzvsm6MUHfkNhvhELByAnSTgYc',
                    },
                    {
                        'pos': 1,
                        'value': '202.72217465',
                        'type': 'pubkeyhash',
                        'address': 'DT4D9qKja5mYQtTeVU1at7MYDYZcosHq32',
                    },
                ],
                'outputs_value': '225.97000000',
                'fee': '1.00000000',
            }
        }
        api.request.side_effect = [
            api_response
        ]
        txs_info = {
            '7700fa249904b52d6924add4a3c937dfacf5dcf41e9b9e07113b1a3701daaf3f': {
                'hash': '7700fa249904b52d6924add4a3c937dfacf5dcf41e9b9e07113b1a3701daaf3f',
                'success': True,
                'inputs': [
                    {
                        'address': 'DN7Tn4Mh8vhWf5bsMj4xXh32StyDy4pWmq',
                        'currency': Currencies.doge,
                        'value': Decimal('226.97'),
                        'type': 'pubkeyhash'
                    },
                ],
                'outputs': [
                    {
                        'address': 'DCZyFU5Ytzvsm6MUHfkNhvhELByAnSTgYc',
                        'currency': Currencies.doge,
                        'value': Decimal('23.24782535'),
                        'type': 'pubkeyhash'
                    },
                    {
                        'address': 'DT4D9qKja5mYQtTeVU1at7MYDYZcosHq32',
                        'currency': Currencies.doge,
                        'value': Decimal('202.72217465'),
                        'type': 'pubkeyhash'
                    },
                ],
                'block': 'd20d12753c3f81f29e40bb92f5a4ce23f695a473a0bbda955b13a35cac1e8c42',
                'confirmations': 131328,
                'fees': Decimal('1'),
                'date': datetime.datetime(2022, 4, 6, 11, 3, 51),
                'raw': api_response.get('transaction')
            }
        }
        results = BlockchainExplorer.get_transactions_details(list(txs_info.keys()), 'DOGE')
        for hash_, info in txs_info.items():
            result = results.get(hash_)
            assert result is not None
            for key, expected_value in txs_info.get(hash_).items():
                actual_value = result.get(key)
                assert actual_value is not None
                assert actual_value == expected_value

    def test_get_tx_details_fantom_web3(self):
        api_name = 'ftm_web3'
        APIS_CONF['FTM']['txs_details'] = api_name
        api = APIS_CLASSES[api_name].get_api()
        api.w3.eth.get_transaction = Mock()
        api.w3.eth.get_transaction_receipt = Mock()

        api_response = {
            'blockHash': HexBytes('0x0001874d00000307a854630459717f70b527bd7e6fd78c72514b6b9c95c9d0f6'),
            'blockNumber': 35361843,
            'from': '0x97F351F18B631d25120a15796aBE458469c12b9c',
            'gas': 21000,
            'gasPrice': 220590600000,
            'hash': HexBytes('0x767a8c80f87265440e6e54988b973f7a19e55aa86f0ce91557497a5e81abee49'),
            'input': HexBytes('0x'),
            'nonce': 684,
            'to': '0x62307B32Ea207D5A0BEc1F75C60BC10ae7666666',
            'transactionIndex': 22,
            'value': 5000000000000000000,
            'type': '0x0',
            'v': 536,
            'r': '0x91a878d1f68ca9e616577419bf3b4f8dc6ae2dfabbf00160c70cd046557302f3',
            's': '0x32138bd8855f0aaa3a52b069efc28ee12e1ae1e44cc91c1e0da666a0595d38a0',
        }

        api.w3.eth.get_transaction.side_effect = [
            api_response
        ]
        api.w3.eth.get_transaction_receipt.side_effect = [{'status': 1}]

        txs_info = {'0x767a8c80f87265440e6e54988b973f7a19e55aa86f0ce91557497a5e81abee49': {
            'hash': '0x767a8c80f87265440e6e54988b973f7a19e55aa86f0ce91557497a5e81abee49', 'success': True, 'inputs': [],
            'outputs': [], 'transfers': [
                {'symbol': 'FTM', 'currency': 75, 'from': '0x97f351f18b631d25120a15796abe458469c12b9c',
                 'to': '0x62307b32ea207d5a0bec1f75c60bc10ae7666666', 'value': Decimal('5.000000000000000000'),
                 'is_valid': True, 'token': None}], 'block': 35361843, 'memo': None, 'confirmations': None,
            'date': None, 'fees': None}}
        results = BlockchainExplorer.get_transactions_details(list(txs_info.keys()), 'FTM')
        for hash_, info in txs_info.items():
            result = results.get(hash_)
            assert result is not None
            for key, expected_value in txs_info.get(hash_).items():
                actual_value = result.get(key)
                assert actual_value == expected_value

    def test_get_tx_details_fantom_web3_invalid_tx(self):
        api_name = APIS_CONF['FTM']['txs_details']
        api = APIS_CLASSES[api_name].get_api()
        api.w3.eth.get_transaction = Mock()
        api.w3.eth.get_transaction_receipt = Mock()

        api_response = {
            'blockHash': HexBytes('0x000184370000000a9c19f8ddee398e1119777d024d2550b61523cc07d52302fe'),
            'blockNumber': 35146882,
            'from': '0xe88bd5aa56c29a0dcc393cf69868bf6693bfe0b4',
            'gas': 825000,
            'gasPrice': 311342000000,
            'hash': HexBytes('0x0007c7f4e01513f9758a8f7f3a609be50e8ed55e0ab4e7e71431d75b6de3d76a'),
            'input': HexBytes('0x'),
            'nonce': 684,
            'to': '0xf491e7b69e4244ad4002bc14e878a34207e38c29',
            'transactionIndex': 22,
            'value': 692201199815413071872,
            'type': '0x0',
            'v': 536,
            'r': '0x91a878d1f68ca9e616577419bf3b4f8dc6ae2dfabbf00160c70cd046557302f3',
            's': '0x32138bd8855f0aaa3a52b069efc28ee12e1ae1e44cc91c1e0da666a0595d38a0',
        }

        api.w3.eth.get_transaction.side_effect = [
            api_response
        ]
        api.w3.eth.get_transaction_receipt.side_effect = [{'status': 0}]

        txs_info = {'0x0007c7f4e01513f9758a8f7f3a609be50e8ed55e0ab4e7e71431d75b6de3d76a': {
            'hash': '0x0007c7f4e01513f9758a8f7f3a609be50e8ed55e0ab4e7e71431d75b6de3d76a', 'success': False,
            'inputs': [], 'outputs': [], 'transfers': [], 'block': 35146882, 'memo': None, 'confirmations': None,
            'date': None, 'fees': None}}
        results = BlockchainExplorer.get_transactions_details(list(txs_info.keys()), 'FTM')
        assert len(results) == len(txs_info)
        for hash_, info in txs_info.items():
            result = results.get(hash_)
            assert result is not None
            for key, expected_value in txs_info.get(hash_).items():
                actual_value = result.get(key)
                assert actual_value == expected_value

    def test_get_tx_details_ltc_blockcypher(self):
        api_name = 'ltc_blockcypher'
        APIS_CONF['LTC']['txs_details'] = api_name
        api = APIS_CLASSES[api_name].get_api()
        api.request = Mock()

        api_response = {
            'block_hash': 'af8b1aed96eca5f8912575aefd9d90a0c7b88aaaedf05a2229d4972b2f72e067',
            'block_height': 2240799,
            'block_index': 6,
            'hash': 'dc31a2d0bc4aa6e2735f7a4f4cdf970fc25817ec5e26c2a3f132ace5364218b0',
            'addresses': [
                'MGjzqHopntLHPwYfQmPM3UMuKw9qSV1xjJ',
                'ltc1q0df03xqs0a9me76j8rvnjhdjjmxrxm9xcscvrf',
                'ltc1qrcesnmqufs5razdvx2n75lzxus3ccksvzs6zpt',
            ],
            'total': 15825659,
            'fees': 426,
            'size': 224,
            'vsize': 142,
            'preference': 'low',
            'relayed_by': '95.216.119.109:9333',
            'confirmed': '2022-04-06T08:12:33Z',
            'received': '2022-04-06T08:12:27.84Z',
            'ver': 1,
            'double_spend': False,
            'vin_sz': 1,
            'vout_sz': 2,
            'confirmations': 3,
            'confidence': 1,
            'inputs': [
                {
                    'prev_hash': '799f5028be80928428228b65448265f4f18a8685fddbe462d9a43b3b97073737',
                    'output_index': 1,
                    'output_value': 15826085,
                    'sequence': 4294967295,
                    'addresses': ['ltc1qrcesnmqufs5razdvx2n75lzxus3ccksvzs6zpt'],
                    'script_type': 'pay-to-witness-pubkey-hash',
                    'age': 2240796,
                    'witness': [
                        '3045022100a9473e650c628a32784915b7634c95fc5f7db4da5f73d0a83b190b5490abc18402206ab834b6d390f3df149633320c4bd100a2ba3031bc2f14249ab22b7ffc51c75001',
                        '03a3e871cb9eced28f545f0d77a1cefdc15b3e63a9fb08b1fcdd3366f33efc21f7',
                    ],
                }
            ],
            'outputs': [
                {
                    'value': 15785776,
                    'script': 'a91460fd8ae410a179ee9b75997949ceef21d882f5a287',
                    'addresses': ['MGjzqHopntLHPwYfQmPM3UMuKw9qSV1xjJ'],
                    'script_type': 'pay-to-script-hash',
                },
                {
                    'value': 39883,
                    'script': '00147b52f898107f4bbcfb5238d9395db296cc336ca6',
                    'addresses': ['ltc1q0df03xqs0a9me76j8rvnjhdjjmxrxm9xcscvrf'],
                    'script_type': 'pay-to-witness-pubkey-hash',
                },
            ],
        }

        api.request.side_effect = [
            api_response
        ]
        txs_info = {
            'dc31a2d0bc4aa6e2735f7a4f4cdf970fc25817ec5e26c2a3f132ace5364218b0': {
                'success': True,
                'double_spend': False,
                'inputs': [
                    {
                        'address': 'ltc1qrcesnmqufs5razdvx2n75lzxus3ccksvzs6zpt',
                        'currency': Currencies.ltc,
                        'value': Decimal('0.15826085'),
                        'is_valid': True
                    },
                ],
                'outputs': [
                    {
                        'address': 'ltc1q0df03xqs0a9me76j8rvnjhdjjmxrxm9xcscvrf',
                        'currency': Currencies.ltc,
                        'value': Decimal('0.00039883'),
                        'is_valid': True,
                    },
                ],
                'block': 2240799,
                'fees': Decimal('0.00000426'),
                'date': datetime.datetime(2022, 4, 6, 8, 12, 33, tzinfo=UTC),
                'value': Decimal('0.15825659'),
                'raw': api_response
            }
        }
        results = BlockchainExplorer.get_transactions_details(list(txs_info.keys()), 'LTC')
        for hash_, info in txs_info.items():
            result = results.get(hash_)
            assert result is not None
            for key, expected_value in txs_info.get(hash_).items():
                actual_value = result.get(key)
                assert actual_value is not None
                assert actual_value == expected_value

    def test_get_tx_details_ltc_blockbook(self):
        api_name = 'ltc_blockbook'
        APIS_CONF['LTC']['txs_details'] = api_name
        api = APIS_CLASSES[api_name].get_api()
        api.request = Mock()

        api_response = {
            'txid': 'dc31a2d0bc4aa6e2735f7a4f4cdf970fc25817ec5e26c2a3f132ace5364218b0',
            'version': 1,
            'vin': [
                {
                    'txid': '799f5028be80928428228b65448265f4f18a8685fddbe462d9a43b3b97073737',
                    'vout': 1,
                    'sequence': 4294967295,
                    'n': 0,
                    'addresses': ['ltc1qrcesnmqufs5razdvx2n75lzxus3ccksvzs6zpt'],
                    'isAddress': True,
                    'value': '15826085',
                }
            ],
            'vout': [
                {
                    'value': '15785776',
                    'n': 0,
                    'spent': True,
                    'hex': 'a91460fd8ae410a179ee9b75997949ceef21d882f5a287',
                    'addresses': ['MGjzqHopntLHPwYfQmPM3UMuKw9qSV1xjJ'],
                    'isAddress': True,
                },
                {
                    'value': '39883',
                    'n': 1,
                    'spent': True,
                    'hex': '00147b52f898107f4bbcfb5238d9395db296cc336ca6',
                    'addresses': ['ltc1q0df03xqs0a9me76j8rvnjhdjjmxrxm9xcscvrf'],
                    'isAddress': True,
                },
            ],
            'blockHash': 'af8b1aed96eca5f8912575aefd9d90a0c7b88aaaedf05a2229d4972b2f72e067',
            'blockHeight': 2240799,
            'confirmations': 55582,
            'blockTime': 1649232753,
            'value': '15825659',
            'valueIn': '15826085',
            'fees': '426',
            'hex': '01000000000101373707973b3ba4d962e4dbfd85868af1f4658244658b2228849280be28509f790100000000ffffffff0230dff0000000000017a91460fd8ae410a179ee9b75997949ceef21d882f5a287cb9b0000000000001600147b52f898107f4bbcfb5238d9395db296cc336ca602483045022100a9473e650c628a32784915b7634c95fc5f7db4da5f73d0a83b190b5490abc18402206ab834b6d390f3df149633320c4bd100a2ba3031bc2f14249ab22b7ffc51c750012103a3e871cb9eced28f545f0d77a1cefdc15b3e63a9fb08b1fcdd3366f33efc21f700000000',
        }
        api.request.side_effect = [
            api_response
        ]
        txs_info = {
            'dc31a2d0bc4aa6e2735f7a4f4cdf970fc25817ec5e26c2a3f132ace5364218b0': {
                'hash': 'dc31a2d0bc4aa6e2735f7a4f4cdf970fc25817ec5e26c2a3f132ace5364218b0',
                'success': True,
                'transfers': [],
                'inputs': [
                    {
                        'address': 'ltc1qrcesnmqufs5razdvx2n75lzxus3ccksvzs6zpt',
                        'currency': Currencies.ltc,
                        'value': Decimal('0.15826085'),
                        'is_valid': True
                    },
                ],
                'outputs': [
                    {
                        'address': 'MGjzqHopntLHPwYfQmPM3UMuKw9qSV1xjJ',
                        'currency': 12,
                        'value': Decimal('0.15785776'),
                        'is_valid': True
                    },
                    {
                        'address': 'ltc1q0df03xqs0a9me76j8rvnjhdjjmxrxm9xcscvrf',
                        'currency': Currencies.ltc,
                        'value': Decimal('0.00039883'),
                        'is_valid': True
                    },
                ],
                'block': 2240799,
                'confirmations': 55582,
                'fees': Decimal('0.00000426'),
                'date': datetime.datetime(2022, 4, 6, 8, 12, 33, tzinfo=UTC),
            }
        }
        results = BlockchainExplorer.get_transactions_details(list(txs_info.keys()), 'LTC')
        for hash_, info in txs_info.items():
            result = results.get(hash_)
            assert result is not None
            for key, expected_value in txs_info.get(hash_).items():
                actual_value = result.get(key)
                assert actual_value is not None
                assert actual_value == expected_value

    def test_get_tx_details_eth_covalent(self):
        api_name = 'eth_covalent'
        APIS_CONF['ETH']['txs_details'] = api_name
        api = APIS_CLASSES[api_name].get_api()
        api.request = Mock()

        api_tx_info = {
            'block_signed_at': '2022-04-06T10:35:50Z',
            'block_height': 14531838,
            'tx_hash': '0x06da5b6f499c85349c45cde6ee2a8e737c856f1614b128cfc4b7dde62beeca22',
            'tx_offset': 190,
            'successful': True,
            'from_address': '0x636f2dc7b5c219253ca12173b80d7e3f6f04caa1',
            'from_address_label': None,
            'to_address': '0xf6cb72f581e9a8e505a57f89c3dd2efdbafda145',
            'to_address_label': None,
            'value': '14086034300000000',
            'value_quote': 47.1993984459042,
            'gas_offered': 70000,
            'gas_spent': 21000,
            'gas_price': 33521919007,
            'gas_quote': 2.358825908122144,
            'gas_quote_rate': 3350.7939453125,
            'log_events': [],
        }
        api_response = {
            'data': {
                'updated_at': '2022-04-06T10:42:38.631027200Z',
                'items': [
                    api_tx_info
                ],
                'pagination': None,
            },
            'error': False,
            'error_message': None,
            'error_code': None,
        }

        api.request.side_effect = [
            api_response
        ]
        txs_info = {'0x06da5b6f499c85349c45cde6ee2a8e737c856f1614b128cfc4b7dde62beeca22': {
            'hash': '0x06da5b6f499c85349c45cde6ee2a8e737c856f1614b128cfc4b7dde62beeca22', 'success': True,
            'transfers': [{'type': 'MainCoin', 'symbol': 'ETH', 'currency': 11,
                           'from': '0x636f2dc7b5c219253ca12173b80d7e3f6f04caa1',
                           'to': '0xf6cb72f581e9a8e505a57f89c3dd2efdbafda145', 'value': Decimal('0.014086034300000000'),
                           'is_valid': True, 'token': None}], 'inputs': [], 'outputs': [], 'block': 14531838,
            'confirmations': 0, 'fees': Decimal('0.000703960299147000'),
            'date': datetime.datetime(2022, 4, 6, 10, 35, 50, tzinfo=UTC), 'raw': {
                'block_signed_at': '2022-04-06T10:35:50Z', 'block_height': 14531838,
                'tx_hash': '0x06da5b6f499c85349c45cde6ee2a8e737c856f1614b128cfc4b7dde62beeca22', 'tx_offset': 190,
                'successful': True, 'from_address': '0x636f2dc7b5c219253ca12173b80d7e3f6f04caa1',
                'from_address_label': None, 'to_address': '0xf6cb72f581e9a8e505a57f89c3dd2efdbafda145',
                'to_address_label': None, 'value': '14086034300000000', 'value_quote': 47.1993984459042,
                'gas_offered': 70000, 'gas_spent': 21000, 'gas_price': 33521919007, 'gas_quote': 2.358825908122144,
                'gas_quote_rate': 3350.7939453125, 'log_events': []}, 'memo': None}}
        results = BlockchainExplorer.get_transactions_details(list(txs_info.keys()), 'ETH')
        for hash_, info in txs_info.items():
            result = results.get(hash_)
            assert result is not None
            for key, expected_value in txs_info.get(hash_).items():
                actual_value = result.get(key)
                assert actual_value == expected_value

    def test_get_tx_details_eth_covalent_valid_token(self):
        api_name = APIS_CONF['ETH']['txs_details']
        api = APIS_CLASSES[api_name].get_api()
        api.request = Mock()

        api_tx_info = {
            'block_signed_at': '2022-04-12T03:12:53Z',
            'block_height': 14568272,
            'tx_hash': '0xd89784aa703edb2e38b2144c30a1a060578025c83144b83f845556f0c6185f1e',
            'tx_offset': 22,
            'successful': True,
            'from_address': '0xcd13a0f9121d7d10831317e35f4f582c4581f939',
            'from_address_label': None,
            'to_address': '0xdac17f958d2ee523a2206206994597c13d831ec7',
            'to_address_label': 'Tether USD (USDT)',
            'value': '0',
            'value_quote': 0.0,
            'gas_offered': 46109,
            'gas_spent': 46109,
            'gas_price': 35000000000,
            'gas_quote': 4.805198384141845,
            'gas_quote_rate': 2977.539794921875,
            'log_events': [
                {
                    'block_signed_at': '2022-04-12T03:12:53Z',
                    'block_height': 14568272,
                    'tx_offset': 22,
                    'log_offset': 8,
                    'tx_hash': '0xd89784aa703edb2e38b2144c30a1a060578025c83144b83f845556f0c6185f1e',
                    'raw_log_topics': [
                        '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef',
                        '0x000000000000000000000000cd13a0f9121d7d10831317e35f4f582c4581f939',
                        '0x000000000000000000000000e638609d68ef59e243e2030bba4effe3d81c9f20',
                    ],
                    'sender_contract_decimals': 6,
                    'sender_name': 'Tether USD',
                    'sender_contract_ticker_symbol': 'USDT',
                    'sender_address': '0xdac17f958d2ee523a2206206994597c13d831ec7',
                    'sender_address_label': 'Tether USD (USDT)',
                    'sender_logo_url': 'https://logos.covalenthq.com/tokens/0xdac17f958d2ee523a2206206994597c13d831ec7.png',
                    'raw_log_data': '0x0000000000000000000000000000000000000000000000000000000024833aa0',
                    'decoded': {
                        'name': 'Transfer',
                        'signature': 'Transfer(indexed address from, indexed address to, uint256 value)',
                        'params': [
                            {
                                'name': 'from',
                                'type': 'address',
                                'indexed': True,
                                'decoded': True,
                                'value': '0xcd13a0f9121d7d10831317e35f4f582c4581f939',
                            },
                            {
                                'name': 'to',
                                'type': 'address',
                                'indexed': True,
                                'decoded': True,
                                'value': '0xe638609d68ef59e243e2030bba4effe3d81c9f20',
                            },
                            {
                                'name': 'value',
                                'type': 'uint256',
                                'indexed': False,
                                'decoded': True,
                                'value': '612580000',
                            },
                        ],
                    },
                }
            ],
        }
        api_response = {
            'data': {
                'updated_at': '2022-04-12T03:15:46.949582171Z',
                'items': [
                    api_tx_info
                ],
                'pagination': None,
            },
            'error': False,
            'error_message': None,
            'error_code': None,
        }

        api.request.side_effect = [
            api_response
        ]
        txs_info = {'0xd89784aa703edb2e38b2144c30a1a060578025c83144b83f845556f0c6185f1e': {
            'hash': '0xd89784aa703edb2e38b2144c30a1a060578025c83144b83f845556f0c6185f1e', 'success': True,
            'transfers': [{'type': 'Transfer', 'symbol': 'USDT', 'currency': 13,
                           'from': '0xcd13a0f9121d7d10831317e35f4f582c4581f939',
                           'to': '0xe638609d68ef59e243e2030bba4effe3d81c9f20', 'value': Decimal('612.580000'),
                           'is_valid': True, 'token': None}], 'inputs': [], 'outputs': [], 'block': 14568272,
            'confirmations': 0, 'fees': Decimal('0.001613815000000000'),
            'date': datetime.datetime(2022, 4, 12, 3, 12, 53, tzinfo=UTC), 'raw': {
                'block_signed_at': '2022-04-12T03:12:53Z', 'block_height': 14568272,
                'tx_hash': '0xd89784aa703edb2e38b2144c30a1a060578025c83144b83f845556f0c6185f1e', 'tx_offset': 22,
                'successful': True, 'from_address': '0xcd13a0f9121d7d10831317e35f4f582c4581f939',
                'from_address_label': None, 'to_address': '0xdac17f958d2ee523a2206206994597c13d831ec7',
                'to_address_label': 'Tether USD (USDT)', 'value': '0', 'value_quote': 0.0, 'gas_offered': 46109,
                'gas_spent': 46109, 'gas_price': 35000000000, 'gas_quote': 4.805198384141845,
                'gas_quote_rate': 2977.539794921875, 'log_events': [
                    {'block_signed_at': '2022-04-12T03:12:53Z', 'block_height': 14568272, 'tx_offset': 22,
                     'log_offset': 8,
                     'tx_hash': '0xd89784aa703edb2e38b2144c30a1a060578025c83144b83f845556f0c6185f1e',
                     'raw_log_topics': ['0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef',
                                        '0x000000000000000000000000cd13a0f9121d7d10831317e35f4f582c4581f939',
                                        '0x000000000000000000000000e638609d68ef59e243e2030bba4effe3d81c9f20'],
                     'sender_contract_decimals': 6, 'sender_name': 'Tether USD',
                     'sender_contract_ticker_symbol': 'USDT',
                     'sender_address': '0xdac17f958d2ee523a2206206994597c13d831ec7',
                     'sender_address_label': 'Tether USD (USDT)',
                     'sender_logo_url': 'https://logos.covalenthq.com/tokens/0xdac17f958d2ee523a2206206994597c13d831ec7.png',
                     'raw_log_data': '0x0000000000000000000000000000000000000000000000000000000024833aa0',
                     'decoded': {'name': 'Transfer',
                                 'signature': 'Transfer(indexed address from, indexed address to, uint256 value)',
                                 'params': [{'name': 'from', 'type': 'address', 'indexed': True, 'decoded': True,
                                             'value': '0xcd13a0f9121d7d10831317e35f4f582c4581f939'},
                                            {'name': 'to', 'type': 'address', 'indexed': True, 'decoded': True,
                                             'value': '0xe638609d68ef59e243e2030bba4effe3d81c9f20'},
                                            {'name': 'value', 'type': 'uint256', 'indexed': False, 'decoded': True,
                                             'value': '612580000'}]}}]}, 'memo': None}}
        results = BlockchainExplorer.get_transactions_details(list(txs_info.keys()), 'ETH')
        assert len(results) == len(txs_info)

        for hash_, info in txs_info.items():
            result = results.get(hash_)
            assert result is not None
            for key, expected_value in txs_info.get(hash_).items():
                actual_value = result.get(key)
                assert actual_value == expected_value

    def test_get_tx_details_eth_covalent_invalid_token(self):
        api_name = APIS_CONF['ETH']['txs_details']
        api = APIS_CLASSES[api_name].get_api()
        api.request = Mock()

        api_tx_info = {
            'block_signed_at': '2022-04-12T03:10:59Z',
            'block_height': 14568262,
            'tx_hash': '0x72d2562f5511f8fef54f321ba1c3086882fb22c9dca67f47847b483138b0c82b',
            'tx_offset': 58,
            'successful': True,
            'from_address': '0x77696bb39917c91a0c3908d577d5e322095425ca',
            'from_address_label': None,
            'to_address': '0xd2877702675e6ceb975b4a1dff9fb7baf4c91ea9',
            'to_address_label': None,
            'value': '0',
            'value_quote': 0.0,
            'gas_offered': 250000,
            'gas_spent': 51825,
            'gas_price': 45912160735,
            'gas_quote': 7.084751429293847,
            'gas_quote_rate': 2977.539794921875,
            'log_events': [
                {
                    'block_signed_at': '2022-04-12T03:10:59Z',
                    'block_height': 14568262,
                    'tx_offset': 58,
                    'log_offset': 61,
                    'tx_hash': '0x72d2562f5511f8fef54f321ba1c3086882fb22c9dca67f47847b483138b0c82b',
                    'raw_log_topics': [
                        '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef',
                        '0x00000000000000000000000077696bb39917c91a0c3908d577d5e322095425ca',
                        '0x00000000000000000000000077e98a800d91904aa3c152d6e5563e10f9c12cfa',
                    ],
                    'sender_contract_decimals': 18,
                    'sender_name': 'Wrapped LUNA Token',
                    'sender_contract_ticker_symbol': 'LUNA',
                    'sender_address': '0xd2877702675e6ceb975b4a1dff9fb7baf4c91ea9',
                    'sender_address_label': None,
                    'sender_logo_url': 'https://logos.covalenthq.com/tokens/0xd2877702675e6ceb975b4a1dff9fb7baf4c91ea9.png',
                    'raw_log_data': '0x00000000000000000000000000000000000000000000000141565ad3d3344000',
                    'decoded': {
                        'name': 'Transfer',
                        'signature': 'Transfer(indexed address from, indexed address to, uint256 value)',
                        'params': [
                            {
                                'name': 'from',
                                'type': 'address',
                                'indexed': True,
                                'decoded': True,
                                'value': '0x77696bb39917c91a0c3908d577d5e322095425ca',
                            },
                            {
                                'name': 'to',
                                'type': 'address',
                                'indexed': True,
                                'decoded': True,
                                'value': '0x77e98a800d91904aa3c152d6e5563e10f9c12cfa',
                            },
                            {
                                'name': 'value',
                                'type': 'uint256',
                                'indexed': False,
                                'decoded': True,
                                'value': '23154794400000000000',
                            },
                        ],
                    },
                }
            ],
        }
        api_response = {
            'data': {
                'updated_at': '2022-04-12T03:15:46.949582171Z',
                'items': [
                    api_tx_info
                ],
                'pagination': None,
            },
            'error': False,
            'error_message': None,
            'error_code': None,
        }

        api.request.side_effect = [
            api_response
        ]
        txs_info = {'0x72d2562f5511f8fef54f321ba1c3086882fb22c9dca67f47847b483138b0c82b': {
            'hash': '0x72d2562f5511f8fef54f321ba1c3086882fb22c9dca67f47847b483138b0c82b', 'success': True,
            'transfers': [], 'inputs': [], 'outputs': [], 'block': 14568262, 'confirmations': 0,
            'fees': Decimal('0.002379397730091375'),
            'date': datetime.datetime(2022, 4, 12, 3, 10, 59, tzinfo=UTC), 'raw': {
                'block_signed_at': '2022-04-12T03:10:59Z', 'block_height': 14568262,
                'tx_hash': '0x72d2562f5511f8fef54f321ba1c3086882fb22c9dca67f47847b483138b0c82b', 'tx_offset': 58,
                'successful': True, 'from_address': '0x77696bb39917c91a0c3908d577d5e322095425ca',
                'from_address_label': None, 'to_address': '0xd2877702675e6ceb975b4a1dff9fb7baf4c91ea9',
                'to_address_label': None, 'value': '0', 'value_quote': 0.0, 'gas_offered': 250000, 'gas_spent': 51825,
                'gas_price': 45912160735, 'gas_quote': 7.084751429293847, 'gas_quote_rate': 2977.539794921875,
                'log_events': [
                    {'block_signed_at': '2022-04-12T03:10:59Z', 'block_height': 14568262, 'tx_offset': 58,
                     'log_offset': 61,
                     'tx_hash': '0x72d2562f5511f8fef54f321ba1c3086882fb22c9dca67f47847b483138b0c82b',
                     'raw_log_topics': ['0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef',
                                        '0x00000000000000000000000077696bb39917c91a0c3908d577d5e322095425ca',
                                        '0x00000000000000000000000077e98a800d91904aa3c152d6e5563e10f9c12cfa'],
                     'sender_contract_decimals': 18, 'sender_name': 'Wrapped LUNA Token',
                     'sender_contract_ticker_symbol': 'LUNA',
                     'sender_address': '0xd2877702675e6ceb975b4a1dff9fb7baf4c91ea9', 'sender_address_label': None,
                     'sender_logo_url': 'https://logos.covalenthq.com/tokens/0xd2877702675e6ceb975b4a1dff9fb7baf4c91ea9.png',
                     'raw_log_data': '0x00000000000000000000000000000000000000000000000141565ad3d3344000',
                     'decoded': {'name': 'Transfer',
                                 'signature': 'Transfer(indexed address from, indexed address to, uint256 value)',
                                 'params': [{'name': 'from', 'type': 'address', 'indexed': True, 'decoded': True,
                                             'value': '0x77696bb39917c91a0c3908d577d5e322095425ca'},
                                            {'name': 'to', 'type': 'address', 'indexed': True, 'decoded': True,
                                             'value': '0x77e98a800d91904aa3c152d6e5563e10f9c12cfa'},
                                            {'name': 'value', 'type': 'uint256', 'indexed': False, 'decoded': True,
                                             'value': '23154794400000000000'}]}}]}, 'memo': None}}
        results = BlockchainExplorer.get_transactions_details(list(txs_info.keys()), 'ETH')
        assert len(results) == len(txs_info)
        for hash_, info in txs_info.items():
            result = results.get(hash_)
            assert result is not None
            for key, expected_value in txs_info.get(hash_).items():
                actual_value = result.get(key)
                assert actual_value == expected_value

    def test_get_tx_details_eth_covalent_invalid_tx(self):
        api_name = APIS_CONF['ETH']['txs_details']
        api = APIS_CLASSES[api_name].get_api()
        api.request = Mock()

        api_tx_info = {
            'block_signed_at': '2022-04-12T03:04:59Z',
            'block_height': 14568241,
            'tx_hash': '0x49982f9f67f605741ca1a21f65553a361ff04c86367aa7208dd51008796dbcb1',
            'tx_offset': 97,
            'successful': False,
            'from_address': '0xe8a2624fab5d2d8e89f87b32af18ef5a48531109',
            'from_address_label': None,
            'to_address': '0x17aad3fcf1703ef7908777084ec24e55bc58ae33',
            'to_address_label': None,
            'value': '0',
            'value_quote': 0.0,
            'gas_offered': 21000,
            'gas_spent': 21000,
            'gas_price': 40173745917,
            'gas_quote': 2.5119974707579016,
            'gas_quote_rate': 2977.539794921875,
            'log_events': [],
        }
        api_response = {
            'data': {
                'updated_at': '2022-04-12T03:07:16.680089798Z',
                'items': [
                    api_tx_info
                ],
                'pagination': None,
            },
            'error': False,
            'error_message': None,
            'error_code': None,
        }

        api.request.side_effect = [
            api_response
        ]
        txs_info = {'0x49982f9f67f605741ca1a21f65553a361ff04c86367aa7208dd51008796dbcb1': {
            'hash': '0x49982f9f67f605741ca1a21f65553a361ff04c86367aa7208dd51008796dbcb1', 'success': False,
            'transfers': [], 'inputs': [], 'outputs': [], 'block': 14568241, 'confirmations': 0,
            'fees': Decimal('0.000843648664257000'),
            'date': datetime.datetime(2022, 4, 12, 3, 4, 59, tzinfo=UTC), 'raw': {
                'block_signed_at': '2022-04-12T03:04:59Z', 'block_height': 14568241,
                'tx_hash': '0x49982f9f67f605741ca1a21f65553a361ff04c86367aa7208dd51008796dbcb1', 'tx_offset': 97,
                'successful': False, 'from_address': '0xe8a2624fab5d2d8e89f87b32af18ef5a48531109',
                'from_address_label': None, 'to_address': '0x17aad3fcf1703ef7908777084ec24e55bc58ae33',
                'to_address_label': None, 'value': '0', 'value_quote': 0.0, 'gas_offered': 21000, 'gas_spent': 21000,
                'gas_price': 40173745917, 'gas_quote': 2.5119974707579016, 'gas_quote_rate': 2977.539794921875,
                'log_events': []}, 'memo': None}}
        results = BlockchainExplorer.get_transactions_details(list(txs_info.keys()), 'ETH')
        for hash_, info in txs_info.items():
            result = results.get(hash_)
            assert result is not None
            for key, expected_value in txs_info.get(hash_).items():
                actual_value = result.get(key)
                assert actual_value == expected_value

    def test_get_tx_details_etc_blockscout(self):
        api_name = 'etc_blockscout'
        APIS_CONF['ETC']['txs_details'] = api_name
        api = APIS_CLASSES[api_name].get_api()
        api.request = Mock()

        api_tx_info = {
            'blockNumber': '14874023',
            'confirmations': '195',
            'from': '0xe9e1e4ffc79bb86ace843f34a0a90ce5e2cc8347',
            'gasLimit': '21000',
            'gasPrice': '1000000000',
            'gasUsed': '21000',
            'hash': '0x0239eb17204e3af27665ddf7d9590a5977c9b1ad131be9a0357f6b035d076f01',
            'input': '0x',
            'logs': [],
            'next_page_params': None,
            'revertReason': '',
            'success': True,
            'timeStamp': '1649239629',
            'to': '0x273ab1d97a009a1868314c54fef7bf23aa0217c3',
            'value': '1268036510000000000',
        }
        api_response = {
            'message': 'OK',
            'result': api_tx_info,
            'status': '1',
        }

        api.request.side_effect = [
            api_response
        ]
        txs_info = {
            '0x0239eb17204e3af27665ddf7d9590a5977c9b1ad131be9a0357f6b035d076f01': {
                'hash': '0x0239eb17204e3af27665ddf7d9590a5977c9b1ad131be9a0357f6b035d076f01',
                'success': True,
                'is_valid': True,
                'inputs': [],
                'outputs': [],
                'transfers': [
                    {
                        'symbol': 'ETC',
                        'currency': Currencies.etc,
                        'is_valid': True,
                        'type': 'MainCoin',
                        'from': '0xe9e1e4ffc79bb86ace843f34a0a90ce5e2cc8347',
                        'to': '0x273ab1d97a009a1868314c54fef7bf23aa0217c3',
                        'value': Decimal('1.26803651'),
                    }
                ],
                'block': '14874023',
            }
        }
        results = BlockchainExplorer.get_transactions_details(list(txs_info.keys()), 'ETC')
        for hash_, info in txs_info.items():
            result = results.get(hash_)
            assert result is not None
            for key, expected_value in txs_info.get(hash_).items():
                actual_value = result.get(key)
                assert actual_value is not None
                assert actual_value == expected_value


    def test_get_tx_details_dot_polkascan(self):
        api_name = 'dot_polkascan'
        APIS_CONF['DOT']['txs_details'] = api_name
        api = APIS_CLASSES[api_name].get_api()
        api.request = Mock()

        api_response = {
            'meta': {'authors': ['WEB3SCAN', 'POLKASCAN', 'openAware BV']},
            'errors': [],
            'data': {
                'type': 'extrinsic',
                'id': '9385748-2',
                'attributes': {
                    'block_id': 9385748,
                    'extrinsic_idx': 2,
                    'extrinsic_hash': '0e8efb361dc3ab44350c540d3651471493b99b11d877ae8d7512f36840b87efa',
                    'extrinsic_length': '148',
                    'extrinsic_version': None,
                    'signed': 1,
                    'unsigned': 0,
                    'signedby_address': 1,
                    'signedby_index': 0,
                    'address_length': None,
                    'address': '12xtAYsRUrmbniiWQqJtECiBQrMn8AypQcXhnQAc6RB6XkLW',
                    'account_index': None,
                    'account_idx': None,
                    'signature': 'a4ef696ce18174171ae169cdf2e3ddd4691d172ec54a018022872ee22e990a028788a214d341f32c014aaa2cdd94d602b87d3697d3252d71782c27eafb97cf88',
                    'nonce': 234844,
                    'era': 'f500',
                    'call': '0500',
                    'module_id': 'balances',
                    'call_id': 'transfer',
                    'params': [
                        {
                            'name': 'dest',
                            'type': 'LookupSource',
                            'value': '15S5abkeB7pcMaDi6WFhW28Vyv37LqKfPAgxvXkbHq7AZ48a',
                            'orig_value': 'c4117bf4ee9afdd022a2f1df5d6e1b0cbc9d5d788905d9840a78201ffa20f72e',
                        },
                        {'name': 'value', 'type': 'Balance', 'value': 3919227167500},
                    ],
                    'success': 1,
                    'error': 0,
                    'spec_version_id': 9170,
                    'codec_error': False,
                    'account': {
                        'type': 'account',
                        'id': '56daf75bd0f09c11d798263bc79baeb77c4b4af1dbd372bbe532b1f8702b2a7e',
                        'attributes': {
                            'id': '56daf75bd0f09c11d798263bc79baeb77c4b4af1dbd372bbe532b1f8702b2a7e',
                            'address': '12xtAYsRUrmbniiWQqJtECiBQrMn8AypQcXhnQAc6RB6XkLW',
                            'index_address': None,
                            'is_reaped': False,
                            'is_validator': False,
                            'was_validator': False,
                            'is_nominator': False,
                            'was_nominator': True,
                            'is_council_member': False,
                            'was_council_member': False,
                            'is_tech_comm_member': False,
                            'was_tech_comm_member': False,
                            'is_registrar': False,
                            'was_registrar': False,
                            'is_sudo': False,
                            'was_sudo': False,
                            'is_treasury': False,
                            'is_contract': False,
                            'count_reaped': 0,
                            'hash_blake2b': '16b0899b0ec99147b73b709526b7f072a74b9896f5f5fd2bf81c78ea13a92fc0',
                            'balance_total': 7.21773471706128517,
                            'balance_free': 7.21773471706128517,
                            'balance_reserved': 0.0,
                            'nonce': 132722,
                            'account_info': None,
                            'has_identity': False,
                            'has_subidentity': False,
                            'identity_display': None,
                            'identity_legal': None,
                            'identity_web': None,
                            'identity_riot': None,
                            'identity_email': None,
                            'identity_twitter': None,
                            'identity_judgement_good': 0,
                            'identity_judgement_bad': 0,
                            'parent_identity': None,
                            'subidentity_display': None,
                            'created_at_block': 1205138,
                            'updated_at_block': 1205138,
                        },
                    },
                    'address_id': '56daf75bd0f09c11d798263bc79baeb77c4b4af1dbd372bbe532b1f8702b2a7e',
                    'datetime': '2022-03-11T18:18:18 00:00',
                },
            },
            'links': {},
        }

        api.request.side_effect = [
            api_response
        ]
        txs_info = {
            '0x0e8efb361dc3ab44350c540d3651471493b99b11d877ae8d7512f36840b87efa': {
                'hash': '0x0e8efb361dc3ab44350c540d3651471493b99b11d877ae8d7512f36840b87efa',
                'id': '9385748-2',
                'success': True,
                'is_valid': True,
                'inputs': [],
                'outputs': [],
                'transfers': [
                    {
                        'hash': '0x0e8efb361dc3ab44350c540d3651471493b99b11d877ae8d7512f36840b87efa',
                        'currency': Currencies.dot,
                        'is_valid': True,
                        'from': '12xtAYsRUrmbniiWQqJtECiBQrMn8AypQcXhnQAc6RB6XkLW',
                        'to': '15S5abkeB7pcMaDi6WFhW28Vyv37LqKfPAgxvXkbHq7AZ48a',
                        'value': Decimal('391.9227167500'),
                    }
                ],
                'block': 9385748,
                'date': datetime.datetime(2022, 3, 11, 18, 18, 18)
            }
        }
        results = BlockchainExplorer.get_transactions_details(list(txs_info.keys()), 'DOT')
        for hash_, info in txs_info.items():
            result = results.get(hash_)
            assert result is not None
            for key, expected_value in txs_info.get(hash_).items():
                actual_value = result.get(key)
                assert actual_value is not None
                assert actual_value == expected_value

    def test_get_tx_details_dot_polkascan_failed_tx(self):
        api_name = APIS_CONF['DOT']['txs_details']
        api = APIS_CLASSES[api_name].get_api()
        api.request = Mock()

        api.request.side_effect = [
            APIError('Following error occured: {"error": "service unavailable"}, status code: 302.')
        ]
        txs_info = {
            '0x95233d183390c50d1e2164093abf2db9bf075487c8e87872dd776f0ef8137183': {
                'hash': '0x95233d183390c50d1e2164093abf2db9bf075487c8e87872dd776f0ef8137183',
                'success': False,
            }
        }
        results = BlockchainExplorer.get_transactions_details(list(txs_info.keys()), 'DOT')
        assert results == {}

    def test_get_tx_details_near_indexer(self):
        # Valid tx
        api_response_1 = {
            'details': {'date': '1657008578119042306', 'fees': '4.24555062500E-13', 'from': 'kingjav.near',
                        'hash': '3mRNgeVjt6PnHVbrTyxff5XNeuPGaCKP1YzkfNfKaq7E', 'success': 'SUCCESS_VALUE',
                        'to': 'c9cfdd8433e6c276505c7cab7f8bcc7d8bfdeb0145a107ae36791335d9200522', 'type': 'TRANSFER',
                        'value': '11.331666152307392200000000'}}
        tx_info_1 = {
            '3mRNgeVjt6PnHVbrTyxff5XNeuPGaCKP1YzkfNfKaq7E': {'hash': '3mRNgeVjt6PnHVbrTyxff5XNeuPGaCKP1YzkfNfKaq7E',
                                                             'success': True, 'inputs': [], 'outputs': [],
                                                             'transfers': [{'type': 'TRANSFER', 'symbol': 'NEAR',
                                                                            'currency': Currencies.near,
                                                                            'from': 'kingjav.near',
                                                                            'to': 'c9cfdd8433e6c276505c7cab7f8bcc7d8bfdeb0145a107ae36791335d9200522',
                                                                            'value': Decimal(
                                                                                '11.331666152307392200000000'),
                                                                            'is_valid': True}], 'block': 0,
                                                             'confirmations': 8841427,
                                                             'fees': Decimal('4.24555062500E-13'),
                                                             'date': datetime.datetime(2022, 7, 5, 8, 9, 38, 119042,
                                                                                       tzinfo=UTC),
                                                             'raw': {'date': '1657008578119042306',
                                                                     'fees': '4.24555062500E-13',
                                                                     'from': 'kingjav.near',
                                                                     'hash': '3mRNgeVjt6PnHVbrTyxff5XNeuPGaCKP1YzkfNfKaq7E',
                                                                     'success': 'SUCCESS_VALUE',
                                                                     'to': 'c9cfdd8433e6c276505c7cab7f8bcc7d8bfdeb0145a107ae36791335d9200522',
                                                                     'type': 'TRANSFER',
                                                                     'value': '11.331666152307392200000000'}}}

        # Invalid tx
        api_response_2 = {'details': {'success': 'multi_transfer'}}
        tx_info_2 = {'2zoHwcpAU1sVaY1LrHgiFAxXtsiTYzvXQcXJRZTFXnzz': {'success': False}}

        # Failed tx
        api_response_3 = {'details': {'date': '1657355799415925645', 'fees': '2.23182562500E-13',
                                      'from': '0bbe847c6734e1bbeb3d70ecd6fc07d2adf8c48ee27df84b9f3f2327b06d0001',
                                      'hash': 'AbsXYZRtjSsREtEwFyHugEHZzMsPjm9uBSAdJ7BDY3Ma', 'success': 'FAILURE',
                                      'to': 'sigma-979215773648417.near', 'type': 'TRANSFER',
                                      'value': '0.000061109700000000000000'}}
        tx_info_3 = {'AbsXYZRtjSsREtEwFyHugEHZzMsPjm9uBSAdJ7BDY3Ma': {'success': False}}

        txs_info = [tx_info_1, tx_info_2, tx_info_3]
        api_name = 'near_indexer'
        api = APIS_CLASSES[api_name].get_api()
        APIS_CONF['NEAR']['txs_details'] = api_name
        api.estimate_confirmation_by_date = Mock()
        api.request = Mock()
        api.request.side_effect = [api_response_1, api_response_2, api_response_3]
        api.estimate_confirmation_by_date.return_value = 8841427
        for tx_info in txs_info:
            results = BlockchainExplorer.get_transactions_details(list(tx_info.keys()), 'NEAR')
            if tx_info == {}:
                assert results == {}
            for hash_, info in tx_info.items():
                result = results.get(hash_)
                assert result is not None
                for key, expected_value in tx_info.get(hash_).items():
                    actual_value = result.get(key)
                    assert actual_value is not None
                    assert actual_value == expected_value

    def test_get_tx_details_one_web3(self):
        api_name = 'one_web3'
        APIS_CONF['ONE']['txs_details'] = api_name
        api = APIS_CLASSES[api_name].get_api()
        api.w3.eth.get_transaction = Mock()
        api.w3.eth.get_transaction_receipt = Mock()

        api_response = {
            'blockHash': HexBytes(
                '0xdc06ed04142ecd422d4f142e583b5887109b1e544b7d0180ac22515e777ec8bb'
            ),
            'blockNumber': 26663648,
            'from': '0x4e2d97538aa64b44326cf2e9065b65C3805863F3',
            'gas': 25000,
            'gasPrice': 30000000000,
            'hash': HexBytes(
                '0xee3c8daede87f1281238726481693d9469e31904a7ce1a29ab9d6759fc40d6cf'
            ),
            'input': HexBytes('0x'),
            'nonce': 313821,
            'r': HexBytes(
                '0x1de3e873ac3ea38603df11b8eea758d73f214940eb0b7ddd8fe6aeeb94e28cec'
            ),
            's': HexBytes(
                '0x59c37ea12d1513245a0dced0c01f68d81a64d739b4e37b4939e643fbb6078483'
            ),
            'timestamp': '0x62848e18',
            'to': '0x68860bc66DA1a7F4b81aD8BCf60c594B4fD64fB2',
            'transactionIndex': 12,
            'v': 3333200035,
            'value': 500917846080667425,
        }

        api.w3.eth.get_transaction.side_effect = [
            api_response
        ]
        api.w3.eth.get_transaction_receipt.side_effect = [{'status': 1}]

        txs_info = {'0xee3c8daede87f1281238726481693d9469e31904a7ce1a29ab9d6759fc40d6cf': {
            'hash': '0xee3c8daede87f1281238726481693d9469e31904a7ce1a29ab9d6759fc40d6cf', 'success': True, 'inputs': [],
            'outputs': [], 'transfers': [
                {'symbol': 'ONE', 'currency': 100, 'from': '0x4e2d97538aa64b44326cf2e9065b65c3805863f3',
                 'to': '0x68860bc66da1a7f4b81ad8bcf60c594b4fd64fb2', 'value': Decimal('0.500917846080667425'),
                 'is_valid': True, 'token': None}], 'block': 26663648, 'memo': None, 'confirmations': None,
            'date': None, 'fees': None}}
        results = BlockchainExplorer.get_transactions_details(list(txs_info.keys()), 'ONE')
        for hash_, info in txs_info.items():
            result = results.get(hash_)
            assert result is not None
            for key, expected_value in txs_info.get(hash_).items():
                actual_value = result.get(key)
                assert actual_value == expected_value


    def test_get_tx_details_tx_bnb_binance(self):
        api_name = 'binance'
        APIS_CONF['BNB']['txs_details'] = api_name
        api = APIS_CLASSES[api_name].get_api()
        api.request = Mock()

        # Failed tx
        api_response_1 = {'code': 393621, 'hash': 'F296E84917A92FC4876AFE77DE662CC9417F9D6F2EB8ED1AD723A5433EBB8362',
                          'height': '30771453',
                          'log': '{"codespace":6,"code":405,"abci_code":393621,"message":"Failed to find order [E0B781A5DA419E0E596D13FE8A06BF5F9CE9C37D-19450]"}',
                          'ok': False, 'tx': {'type': 'auth/StdTx', 'value': {'data': None, 'memo': '', 'msg': [
                {'type': 'dex/CancelOrder', 'value': {'refid': 'E0B781A5DA419E0E596D13FE8A06BF5F9CE9C37D-19450',
                                                      'sender': 'bnb1uzmcrfw6gx0quktdz0lg5p4lt7wwnsmat6ksd6',
                                                      'symbol': 'BNB_TUSDB-888'}}], 'signatures': [
                {'account_number': '153135', 'pub_key': {'type': 'tendermint/PubKeySecp256k1',
                                                         'value': 'AzWMnQAwvCP9mbpNyaGuOtNVum1ktvlBb+XFy8D50xmh'},
                 'sequence': '19452',
                 'signature': 'y2FTS4rAqWvDmNWLxsOg+8vrz9XZ4gDXs/tGh/psnQwRMQBtw1x1a2TSCgc0G4qbvh0YICe5ZvJFRNvg/zGG7w=='}],
                                                                              'source': '889'}}}
        tx_info_1 = {'F296E84917A92FC4876AFE77DE662CC9417F9D6F2EB8ED1AD723A5433EBB8362': {
            'hash': 'F296E84917A92FC4876AFE77DE662CC9417F9D6F2EB8ED1AD723A5433EBB8362', 'success': False,
            'is_valid': False, 'inputs': [], 'outputs': [], 'transfers': [], 'memo': '', 'block': '30771453',
            'confirmations': 0,
            'raw': {'code': 393621, 'hash': 'F296E84917A92FC4876AFE77DE662CC9417F9D6F2EB8ED1AD723A5433EBB8362',
                    'height': '30771453',
                    'log': '{"codespace":6,"code":405,"abci_code":393621,"message":"Failed to find order [E0B781A5DA419E0E596D13FE8A06BF5F9CE9C37D-19450]"}',
                    'ok': False, 'tx': {'type': 'auth/StdTx', 'value': {'data': None, 'memo': '', 'msg': [
                    {'type': 'dex/CancelOrder', 'value': {'refid': 'E0B781A5DA419E0E596D13FE8A06BF5F9CE9C37D-19450',
                                                          'sender': 'bnb1uzmcrfw6gx0quktdz0lg5p4lt7wwnsmat6ksd6',
                                                          'symbol': 'BNB_TUSDB-888'}}], 'signatures': [
                    {'account_number': '153135', 'pub_key': {'type': 'tendermint/PubKeySecp256k1',
                                                             'value': 'AzWMnQAwvCP9mbpNyaGuOtNVum1ktvlBb+XFy8D50xmh'},
                     'sequence': '19452',
                     'signature': 'y2FTS4rAqWvDmNWLxsOg+8vrz9XZ4gDXs/tGh/psnQwRMQBtw1x1a2TSCgc0G4qbvh0YICe5ZvJFRNvg/zGG7w=='}],
                                                                        'source': '889'}}}}}

        # Invalid tx
        api_response_2 = {'code': 0, 'hash': '493FBF3A3A086298B30002C78DEA4660498D5CA79C792CAAE94D2292A45E5C93',
                          'height': '234842661', 'log': 'Msg 0: ', 'ok': True, 'tx': {'type': 'auth/StdTx',
                                                                                      'value': {'data': None,
                                                                                                'memo': '', 'msg': [{
                                                                                              'type': 'cosmos-sdk/Send',
                                                                                              'value': {
                                                                                                  'inputs': [
                                                                                                      {
                                                                                                          'address': 'bnb1dtpty6hrxehwz9xew6ttj52l929cu8zehprzwj',
                                                                                                          'coins': [
                                                                                                              {
                                                                                                                  'amount': '129159832',
                                                                                                                  'denom': 'BNB'}]}],
                                                                                                  'outputs': [
                                                                                                      {
                                                                                                          'address': 'bnb15gjczjk2ku2emsa6vm0mas5vjjc6p5kat9lhhw',
                                                                                                          'coins': [
                                                                                                              {
                                                                                                                  'amount': '129159832',
                                                                                                                  'denom': 'BNB'}]}]}}],
                                                                                                'signatures': [{
                                                                                                    'account_number': '753528',
                                                                                                    'pub_key': {
                                                                                                        'type': 'tendermint/PubKeySecp256k1',
                                                                                                        'value': 'AmSPgmbqTciqtTqVv1tVxkKyvfGcv0TDyNbODgzpthzY'},
                                                                                                    'sequence': '1016219',
                                                                                                    'signature': 'AlhB6TLh8LZ9a++uAUXeT1wuxooen/fzdHTIAk5tV5Ai7zxxmWJyqDrP+yIeAycmAIrh4+ErOYR/NmPfXwzNcg=='}],
                                                                                                'source': '1'}}}
        tx_info_2 = {'493FBF3A3A086298B30002C78DEA4660498D5CA79C792CAAE94D2292A45E5C93': {
            'hash': '493FBF3A3A086298B30002C78DEA4660498D5CA79C792CAAE94D2292A45E5C93', 'success': True,
            'is_valid': True, 'inputs': [], 'outputs': [
                {'address': 'bnb15gjczjk2ku2emsa6vm0mas5vjjc6p5kat9lhhw', 'currency': 16, 'denom': 'BNB',
                 'is_valid': True, 'value': Decimal('1.29159832')}], 'transfers': [], 'memo': '', 'block': '234842661',
            'confirmations': 0,
            'raw': {'code': 0, 'hash': '493FBF3A3A086298B30002C78DEA4660498D5CA79C792CAAE94D2292A45E5C93',
                    'height': '234842661', 'log': 'Msg 0: ', 'ok': True, 'tx': {'type': 'auth/StdTx',
                                                                                'value': {'data': None, 'memo': '',
                                                                                          'msg': [{
                                                                                              'type': 'cosmos-sdk/Send',
                                                                                              'value': {
                                                                                                  'inputs': [{
                                                                                                      'address': 'bnb1dtpty6hrxehwz9xew6ttj52l929cu8zehprzwj',
                                                                                                      'coins': [
                                                                                                          {
                                                                                                              'amount': '129159832',
                                                                                                              'denom': 'BNB'}]}],
                                                                                                  'outputs': [{
                                                                                                      'address': 'bnb15gjczjk2ku2emsa6vm0mas5vjjc6p5kat9lhhw',
                                                                                                      'coins': [
                                                                                                          {
                                                                                                              'amount': '129159832',
                                                                                                              'denom': 'BNB'}]}]}}],
                                                                                          'signatures': [{
                                                                                              'account_number': '753528',
                                                                                              'pub_key': {
                                                                                                  'type': 'tendermint/PubKeySecp256k1',
                                                                                                  'value': 'AmSPgmbqTciqtTqVv1tVxkKyvfGcv0TDyNbODgzpthzY'},
                                                                                              'sequence': '1016219',
                                                                                              'signature': 'AlhB6TLh8LZ9a++uAUXeT1wuxooen/fzdHTIAk5tV5Ai7zxxmWJyqDrP+yIeAycmAIrh4+ErOYR/NmPfXwzNcg=='}],
                                                                                          'source': '1'}}}}}

        # Valid tx
        api_response_3 = {'code': 0, 'hash': 'B788637934C7EC5377F4AED3BB24545E7671B37B0CB210944DCCD5210AEE7459',
                          'height': '234847587', 'log': 'Msg 0: ', 'ok': True, 'tx': {'type': 'auth/StdTx',
                                                                                      'value': {'data': None,
                                                                                                'memo': '568596140',
                                                                                                'msg': [{
                                                                                                    'type': 'cosmos-sdk/Send',
                                                                                                    'value': {
                                                                                                        'inputs': [
                                                                                                            {
                                                                                                                'address': 'bnb1udp2gxcut83k74n9xj85jzzsjd7d6nrxjuk7vf',
                                                                                                                'coins': [
                                                                                                                    {
                                                                                                                        'amount': '1215716',
                                                                                                                        'denom': 'BNB'}]}],
                                                                                                        'outputs': [
                                                                                                            {
                                                                                                                'address': 'bnb136ns6lfw4zs5hg4n85vdthaad7hq5m4gtkgf23',
                                                                                                                'coins': [
                                                                                                                    {
                                                                                                                        'amount': '1215716',
                                                                                                                        'denom': 'BNB'}]}]}}],
                                                                                                'signatures': [{
                                                                                                    'account_number': '6326068',
                                                                                                    'pub_key': {
                                                                                                        'type': 'tendermint/PubKeySecp256k1',
                                                                                                        'value': 'AvU9mr8QC0KbPESmYTGZ6Zl7MiEchgHB0SLvp/MoYqih'},
                                                                                                    'sequence': '4',
                                                                                                    'signature': 'Cv+KUhi9JBLlSoyy8vWAUKmVqLDR3pkTxu9E9ugqY60Xo549dcY7Akv5x1imtaIObIwDJIbsXmJWTd3YC34UMQ=='}],
                                                                                                'source': '6'}}}
        tx_info_3 = {'B788637934C7EC5377F4AED3BB24545E7671B37B0CB210944DCCD5210AEE7459': {
            'hash': 'B788637934C7EC5377F4AED3BB24545E7671B37B0CB210944DCCD5210AEE7459', 'success': True,
            'is_valid': True, 'inputs': [], 'outputs': [
                {'address': 'bnb136ns6lfw4zs5hg4n85vdthaad7hq5m4gtkgf23', 'currency': Currencies.bnb,
                 'value': Decimal('0.01215716'), 'denom': 'BNB', 'is_valid': True}], 'transfers': [],
            'memo': '568596140', 'block': '234847587', 'confirmations': 0,
            'raw': {'code': 0, 'hash': 'B788637934C7EC5377F4AED3BB24545E7671B37B0CB210944DCCD5210AEE7459',
                    'height': '234847587', 'log': 'Msg 0: ', 'ok': True, 'tx': {'type': 'auth/StdTx',
                                                                                'value': {'data': None,
                                                                                          'memo': '568596140', 'msg': [
                                                                                        {'type': 'cosmos-sdk/Send',
                                                                                         'value': {'inputs': [{
                                                                                             'address': 'bnb1udp2gxcut83k74n9xj85jzzsjd7d6nrxjuk7vf',
                                                                                             'coins': [
                                                                                                 {
                                                                                                     'amount': '1215716',
                                                                                                     'denom': 'BNB'}]}],
                                                                                             'outputs': [{
                                                                                                 'address': 'bnb136ns6lfw4zs5hg4n85vdthaad7hq5m4gtkgf23',
                                                                                                 'coins': [
                                                                                                     {
                                                                                                         'amount': '1215716',
                                                                                                         'denom': 'BNB'}]}]}}],
                                                                                          'signatures': [{
                                                                                              'account_number': '6326068',
                                                                                              'pub_key': {
                                                                                                  'type': 'tendermint/PubKeySecp256k1',
                                                                                                  'value': 'AvU9mr8QC0KbPESmYTGZ6Zl7MiEchgHB0SLvp/MoYqih'},
                                                                                              'sequence': '4',
                                                                                              'signature': 'Cv+KUhi9JBLlSoyy8vWAUKmVqLDR3pkTxu9E9ugqY60Xo549dcY7Akv5x1imtaIObIwDJIbsXmJWTd3YC34UMQ=='}],
                                                                                          'source': '6'}}}}}

        txs_info = [tx_info_1, tx_info_2, tx_info_3]
        api.request.side_effect = [
            api_response_1, api_response_2, api_response_3
        ]

        for tx_info in txs_info:
            results = BlockchainExplorer.get_transactions_details(list(tx_info.keys()), 'BNB')
            for hash_, info in tx_info.items():
                result = results.get(hash_)
                assert result is not None
                for key, expected_value in tx_info.get(hash_).items():
                    actual_value = result.get(key)
                    assert actual_value is not None
                    assert actual_value == expected_value

    def test_get_tx_details_tx_pmn_kuknos(self):
        api_name = APIS_CONF['PMN']['txs_details']
        api = APIS_CLASSES[api_name].get_api()
        api.request = Mock()

        # Valid tx
        api_response_1 = {'memo': 'Mjk2OTkwMzM0', 'memo_bytes': 'TWprMk9Ua3dNek0w', '_links': {'self': {
            'href': 'https://horizon.kuknos.org/transactions/c4a9dbcfa5a2f3c3968443eae289764deca35634f255314f40a03dce53194998'},
            'account': {
                'href': 'https://horizon.kuknos.org/accounts/GDFTGWHZBRZNV64MCGXGSCAI5NSHUP5LHFMFHA7MY2NCQGFMATJ6BAGF'},
            'ledger': {
                'href': 'https://horizon.kuknos.org/ledgers/16957742'},
            'operations': {
                'href': 'https://horizon.kuknos.org/transactions/c4a9dbcfa5a2f3c3968443eae289764deca35634f255314f40a03dce53194998/operations{?cursor,limit,order}',
                'templated': True},
            'effects': {
                'href': 'https://horizon.kuknos.org/transactions/c4a9dbcfa5a2f3c3968443eae289764deca35634f255314f40a03dce53194998/effects{?cursor,limit,order}',
                'templated': True},
            'precedes': {
                'href': 'https://horizon.kuknos.org/transactions?order=asc&cursor=72832947304009728'},
            'succeeds': {
                'href': 'https://horizon.kuknos.org/transactions?order=desc&cursor=72832947304009728'},
            'transaction': {
                'href': 'https://horizon.kuknos.org/transactions/c4a9dbcfa5a2f3c3968443eae289764deca35634f255314f40a03dce53194998'}},
                          'id': 'c4a9dbcfa5a2f3c3968443eae289764deca35634f255314f40a03dce53194998',
                          'paging_token': '72832947304009728', 'successful': True,
                          'hash': 'c4a9dbcfa5a2f3c3968443eae289764deca35634f255314f40a03dce53194998',
                          'ledger': 16957742, 'created_at': '2022-04-14T05:24:02Z',
                          'source_account': 'GDFTGWHZBRZNV64MCGXGSCAI5NSHUP5LHFMFHA7MY2NCQGFMATJ6BAGF',
                          'source_account_sequence': '30152667577724802',
                          'fee_account': 'GDFTGWHZBRZNV64MCGXGSCAI5NSHUP5LHFMFHA7MY2NCQGFMATJ6BAGF',
                          'fee_charged': '50000', 'max_fee': '50000', 'operation_count': 1,
                          'envelope_xdr': 'AAAAAgAAAADLM1j5DHLa+4wRrmkICOtkej+rOVhTg+zGmigYrATT4AAAw1AAax+xAAAvggAAAAEAAAAAAAAAAAAAAABiV6/+AAAAAQAAAAxNamsyT1Rrd016TTAAAAABAAAAAQAAAADJsqRALhDt6BZDt4/SHCp4cb+nqyv67vToaDgSiNCqeQAAAAEAAAAAS8JLy5dtTFyr5n9wWSbfuNnKFpWYQAPbB1bBEtE6gWAAAAAAAAAAAA7msoAAAAAAAAAAAqwE0+AAAABAc+MejKSslZA8PUVTUW1o5WA9lzII8t++EEaYILzQwzyIBizanYWbWExfY5NleuNhaJkqWLfcggti/fRsmKOeAojQqnkAAABAa7gYxMkKcU8Q2Fe63Efa5xVBmSquJnmZ9u0eyWj3k+RN0Vzfymx/8qcP/ei8ynhHluen2WKdLd45sn2JWxOkBA==',
                          'result_xdr': 'AAAAAAAAw1AAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAA=',
                          'result_meta_xdr': 'AAAAAgAAAAIAAAADAQLBLgAAAAAAAAAAyzNY+Qxy2vuMEa5pCAjrZHo/qzlYU4PsxpooGKwE0+AAAAAAF/VFMABrH7EAAC+BAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAABAQLBLgAAAAAAAAAAyzNY+Qxy2vuMEa5pCAjrZHo/qzlYU4PsxpooGKwE0+AAAAAAF/VFMABrH7EAAC+CAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAABAAAABAAAAAMBAotMAAAAAAAAAABLwkvLl21MXKvmf3BZJt+42coWlZhAA9sHVsES0TqBYAAAAABoBBzgAP8GNwAAAAEAAAABAAAAAQAAAACNfxzb54uF1qssLu8pEvivb0wap1eOlqcCPUosaYo1ZgAAAAAAAAANd3d3Lmt1a25vcy5pcgAAAAEAAAAAAAAAAAAAAAAAAAAAAAABAQLBLgAAAAAAAAAAS8JLy5dtTFyr5n9wWSbfuNnKFpWYQAPbB1bBEtE6gWAAAAAAdurPYAD/BjcAAAABAAAAAQAAAAEAAAAAjX8c2+eLhdarLC7vKRL4r29MGqdXjpanAj1KLGmKNWYAAAAAAAAADXd3dy5rdWtub3MuaXIAAAABAAAAAAAAAAAAAAAAAAAAAAAAAwECqjsAAAAAAAAAAMmypEAuEO3oFkO3j9IcKnhxv6erK/ru9OhoOBKI0Kp5AAABk/lCusEAMGNLAABNsAAAAAMAAAABAAAAAI1/HNvni4XWqywu7ykS+K9vTBqnV46WpwI9SixpijVmAAAAAAAAAA13d3cua3Vrbm9zLmlyAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAEBAsEuAAAAAAAAAADJsqRALhDt6BZDt4/SHCp4cb+nqyv67vToaDgSiNCqeQAAAZPqXAhBADBjSwAATbAAAAADAAAAAQAAAACNfxzb54uF1qssLu8pEvivb0wap1eOlqcCPUosaYo1ZgAAAAAAAAANd3d3Lmt1a25vcy5pcgAAAAEAAAAAAAAAAAAAAAAAAAAAAAAA',
                          'fee_meta_xdr': 'AAAAAgAAAAMBAqo7AAAAAAAAAADLM1j5DHLa+4wRrmkICOtkej+rOVhTg+zGmigYrATT4AAAAAAX9giAAGsfsQAAL4EAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAEBAsEuAAAAAAAAAADLM1j5DHLa+4wRrmkICOtkej+rOVhTg+zGmigYrATT4AAAAAAX9UUwAGsfsQAAL4EAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAA==',
                          'memo_type': 'text', 'signatures': [
                'c+MejKSslZA8PUVTUW1o5WA9lzII8t++EEaYILzQwzyIBizanYWbWExfY5NleuNhaJkqWLfcggti/fRsmKOeAg==',
                'a7gYxMkKcU8Q2Fe63Efa5xVBmSquJnmZ9u0eyWj3k+RN0Vzfymx/8qcP/ei8ynhHluen2WKdLd45sn2JWxOkBA=='],
                          'valid_after': '1970-01-01T00:00:00Z', 'valid_before': '2022-04-14T05:24:14Z'}
        get_payment_1 = {'_links': {'self': {
            'href': 'https://horizon.kuknos.org/transactions/c4a9dbcfa5a2f3c3968443eae289764deca35634f255314f40a03dce53194998/payments?cursor=&limit=10&order=asc'},
            'next': {
                'href': 'https://horizon.kuknos.org/transactions/c4a9dbcfa5a2f3c3968443eae289764deca35634f255314f40a03dce53194998/payments?cursor=72832947304009729&limit=10&order=asc'},
            'prev': {
                'href': 'https://horizon.kuknos.org/transactions/c4a9dbcfa5a2f3c3968443eae289764deca35634f255314f40a03dce53194998/payments?cursor=72832947304009729&limit=10&order=desc'}},
            '_embedded': {'records': [{'_links': {
                'self': {'href': 'https://horizon.kuknos.org/operations/72832947304009729'},
                'transaction': {
                    'href': 'https://horizon.kuknos.org/transactions/c4a9dbcfa5a2f3c3968443eae289764deca35634f255314f40a03dce53194998'},
                'effects': {'href': 'https://horizon.kuknos.org/operations/72832947304009729/effects'},
                'succeeds': {
                    'href': 'https://horizon.kuknos.org/effects?order=desc&cursor=72832947304009729'},
                'precedes': {
                    'href': 'https://horizon.kuknos.org/effects?order=asc&cursor=72832947304009729'}},
                'id': '72832947304009729', 'paging_token': '72832947304009729',
                'transaction_successful': True,
                'source_account': 'GDE3FJCAFYIO32AWIO3Y7UQ4FJ4HDP5HVMV7V3XU5BUDQEUI2CVHSCZ5',
                'type': 'payment', 'type_i': 1,
                'created_at': '2022-04-14T05:24:02Z',
                'transaction_hash': 'c4a9dbcfa5a2f3c3968443eae289764deca35634f255314f40a03dce53194998',
                'asset_type': 'native',
                'from': 'GDE3FJCAFYIO32AWIO3Y7UQ4FJ4HDP5HVMV7V3XU5BUDQEUI2CVHSCZ5',
                'to': 'GBF4ES6LS5WUYXFL4Z7XAWJG364NTSQWSWMEAA63A5LMCEWRHKAWBKH4',
                'amount': '25.0000000'}]}}
        tx_info_1 = {'c4a9dbcfa5a2f3c3968443eae289764deca35634f255314f40a03dce53194998': {
            'hash': 'c4a9dbcfa5a2f3c3968443eae289764deca35634f255314f40a03dce53194998', 'success': True,
            'is_valid': True, 'inputs': [], 'outputs': [], 'transfers': [{'symbol': 'PMN', 'currency': Currencies.pmn,
                                                                          'from': 'GDE3FJCAFYIO32AWIO3Y7UQ4FJ4HDP5HVMV7V3XU5BUDQEUI2CVHSCZ5',
                                                                          'to': 'GBF4ES6LS5WUYXFL4Z7XAWJG364NTSQWSWMEAA63A5LMCEWRHKAWBKH4',
                                                                          'token': '', 'name': '',
                                                                          'value': Decimal('25.0000000')}],
            'memo': 'Mjk2OTkwMzM0', 'block': 16957742, 'confirmations': 0,
            'date': datetime.datetime(2022, 4, 14, 5, 24, 2, tzinfo=UTC)}}

        txs_info = [tx_info_1]
        api.request.side_effect = [
            api_response_1, get_payment_1
        ]

        for tx_info in txs_info:
            results = BlockchainExplorer.get_transactions_details(list(tx_info.keys()), 'PMN')
            for hash_, info in tx_info.items():
                result = results.get(hash_)
                assert result is not None
                for key, expected_value in tx_info.get(hash_).items():
                    actual_value = result.get(key)
                    assert actual_value is not None
                    assert actual_value == expected_value


class TestGetTransactionsDetailsSlow(TestCase):
    @pytest.mark.slow
    def test_get_tx_details_bnb_mintscan(self):
        txs_hash = []
        expected_results = []

        txs_hash.append('B788637934C7EC5377F4AED3BB24545E7671B37B0CB210944DCCD5210AEE7459')
        expected_results.append({
            'from': 'bnb1udp2gxcut83k74n9xj85jzzsjd7d6nrxjuk7vf',
            'to': 'bnb136ns6lfw4zs5hg4n85vdthaad7hq5m4gtkgf23',
            'value': Decimal('0.01215716'),
            'success': True,
            'valid': True
        })
        txs_hash.append('29EDDA3C394B283AE6390EBF3DDB1E8DE33F3CA5924774B312117C7F3659FD94')
        expected_results.append({
            'success': False
        })
        txs_hash.append('F296E84917A92FC4876AFE77DE662CC9417F9D6F2EB8ED1AD723A5433EBB8362')
        expected_results.append({
            'success': False
        })

        api_name = 'bnb_mintscan'
        APIS_CONF['BNB']['txs_details'] = api_name

        results = BlockchainExplorer.get_transactions_details(txs_hash, 'BNB')

        for (result_hash, info), expected_result, tx_hash in zip(results.items(), expected_results, txs_hash):
            assert result_hash == tx_hash
            assert info.get('success') == expected_result.get('success')
            if expected_result.get('success') and expected_result.get('valid'):
                assert info.get('transfers')[0].get('from') == expected_result.get('from')
                assert info.get('transfers')[0].get('to') == expected_result.get('to')
                assert info.get('transfers')[0].get('value') == expected_result.get('value')

    @pytest.mark.slow
    def test_get_transactions_values_by_address_bnb(self):
        inputs = [
            {
                'hash': 'B788637934C7EC5377F4AED3BB24545E7671B37B0CB210944DCCD5210AEE7459',
                'address': 'bnb136ns6lfw4zs5hg4n85vdthaad7hq5m4gtkgf23',
                'network': 'BNB',
                'currency': Currencies.bnb,
            },
            {
                'hash': 'F296E84917A92FC4876AFE77DE662CC9417F9D6F2EB8ED1AD723A5433EBB8362',
                'address': 'bnb1uzmcrfw6gx0quktdz0lg5p4lt7wwnsmat6ksd6',
                'network': 'BNB',
                'currency': Currencies.bnb,
            },
            {
                'hash': '493FBF3A3A086298B30002C78DEA4660498D5CA79C792CAAE94D2292A45E5C93',
                'address': 'bnb15gjczjk2ku2emsa6vm0mas5vjjc6p5kat9lhhw',
                'network': 'BNB',
                'currency': Currencies.bnb,
            },
        ]

        results = BlockchainExplorer.get_transactions_values_by_address(inputs)

        assert results[0]['value'] == Decimal('0.01215716')
        assert results[0].get('memo') == '568596140'
        assert results[1]['value'] == Decimal('0')
        assert results[1].get('memo') == ''
        assert results[2]['value'] == Decimal('0')
        assert results[2].get('memo') == ''

    @pytest.mark.slow
    def test_get_transactions_values_by_address_bsc(self):
        inputs = [
            {
                'hash': '0xa670c449bd0bd88e811e6e4d7799be6b8b7c183ad0cf0f2348528cde035c4bf5',
                'address': '0xde22637664a45a21be5f034dd1bf40b207c13c9b',
                'network': 'BSC',
                'currency': Currencies.bnb,
            },
            {
                'hash': '0xce197e322fb2d3d856bfa9e5ad6a5b093de9b500d1f0345b227e6485321f5956',
                'address': '0xba317eb490adc7edbe53afb24cf3d438c8d346b7',
                'network': 'BSC',
                'currency': Currencies.usdt,
            },
            {
                'hash': '0x849413a6b5132308ef125e1f618629c09a3db44a2f7c037fdab15a19a3824a8e',
                'address': '0x10ed43c718714eb63d5aa57b78b54704e256024e',
                'network': 'BSC',
                'currency': Currencies.bnb,
            },
            {
                'hash': '0xb70322b435be57567c9c3c6f095212eec6e1e058486cf4c1b478335743a320b0',
                'address': '0x8aa6912326b2f0a5e1c3b9fb7cd200e6c86a036f',
                'network': 'BSC',
                'currency': Currencies.bnb,
            },
        ]

        results = BlockchainExplorer.get_transactions_values_by_address(inputs)

        assert results[0]['value'] == Decimal('0.00025')
        assert results[1]['value'] == Decimal('100')
        assert results[2]['value'] == Decimal('0')
        assert results[3]['value'] == Decimal('0')

        results = BlockchainExplorer.get_transactions_values_by_address([inputs[1]])
        assert results[0]['value'] == Decimal('100')

    @pytest.mark.slow
    def test_get_transactions_values_by_address_btc(self):
        inputs = [
            {
                'hash': '4210f583f17fc32c955ea4cc299ffc38232dace8a5e3a4e6309a635ed452234c',
                'address': '159ryNJjVkK7KfMvdjbwvfdwMN8KQqMbqY',
                'network': 'BTC',
                'currency': Currencies.btc,
            },
        ]

        results = BlockchainExplorer.get_transactions_values_by_address(inputs)

        assert results[0]['value'] == Decimal('0.02989518')

    @pytest.mark.slow
    def test_get_transactions_values_by_address_bch(self):
        inputs = [
            {
                'hash': '3a70e51c46b7c601de84886359b79d2917dd207c5457f12c3c78ab0a969cbfd4',
                'address': '12vjgwG38BTxVPoMuDEFAUBGaRv9M8G4pP',
                'network': 'BCH',
                'currency': Currencies.bch,
            },
        ]

        results = BlockchainExplorer.get_transactions_values_by_address(inputs)

        assert results[0]['value'] == Decimal('0.00001841')

    @pytest.mark.slow
    def test_get_transactions_values_by_address_ada(self):
        inputs = [
            {
                'hash': 'bd45860549399c69bcb1eba0811fc6aa9dcbc88491c9950e096a0af63c9b4b75',
                'address': 'addr1qyuztplghtqavnzc8prwnvhnsqhmtv477qmptdmwefd3gg05h3lus0z66jkpaxsy6w2vwwjs5vyj0tf4ckax4shxnkmszvvfff',
                'network': 'ADA',
                'currency': Currencies.ada,
            },
        ]

        results = BlockchainExplorer.get_transactions_values_by_address(inputs)

        assert results[0]['value'] == Decimal('1999.0 ')

    @pytest.mark.slow
    def test_get_transactions_values_by_address_doge(self):
        inputs = [
            {
                'hash': '670a8f304c57654acb6cceda139f54efe37efffdd264c902133f1649bcaaef58',
                'address': 'DADMXH47ygoEU2zAN39h7SzGx42d8xVgf1',
                'network': 'DOGE',
                'currency': Currencies.doge,
            },
        ]

        results = BlockchainExplorer.get_transactions_values_by_address(inputs)

        assert results[0]['value'] == Decimal('727.06935921')

    @pytest.mark.slow
    def test_get_transactions_values_by_address_eos(self):
        inputs = [
            {
                'hash': '1b613521679c3c51de24b50a1b5c1b707ff1991d922781dfdfa26d53bd6c26b9',
                'address': 'geytmmrvgene',
                'network': 'EOS',
                'currency': Currencies.eos,
            },
        ]

        results = BlockchainExplorer.get_transactions_values_by_address(inputs)

        assert results[0]['value'] == Decimal('1.2653')

    @pytest.mark.slow
    def test_get_transactions_values_by_address_eth(self):
        inputs = [
            {
                'hash': '0x6f661d01d67a177217450ff155da24099ee04ecfc3ef0f2f4914a441d96bd3a5',
                'address': '0x7b0e01a1e814e78a68c48f7bd3d59dcdbafdde05',
                'network': 'ETH',
                'currency': Currencies.eth,
            },
        ]

        results = BlockchainExplorer.get_transactions_values_by_address(inputs)

        assert results[0]['value'] == Decimal('0.5')

    @pytest.mark.slow
    def test_get_transactions_values_by_address_etc(self):
        inputs = [
            {
                'hash': '0x98de0d90e7bf295cdd4bfbd971d08535e13603d0ff1f7916640eb15968b0dbed',
                'address': '0x97b62dfa702b64863b07255125e13d85c3965e1f',
                'network': 'ETC',
                'currency': Currencies.etc,
            },
        ]

        results = BlockchainExplorer.get_transactions_values_by_address(inputs)

        assert results[0]['value'] == Decimal('1.40305502')

    @pytest.mark.slow
    def test_get_transactions_values_by_address_ftm(self):
        inputs = [
            {
                'hash': '0x665ee860ed8814f15b9072036b4aedbb620b053393e9012605bde7fd85032940',
                'address': '0x860a317c2fe842453318b38a594d7fce72251f83',
                'network': 'FTM',
                'currency': Currencies.ftm,
            },
        ]

        results = BlockchainExplorer.get_transactions_values_by_address(inputs)

        assert results[0]['value'] == Decimal('3.4')

    @pytest.mark.slow
    def test_get_transactions_values_by_address_ltc(self):
        inputs = [
            {
                'hash': 'dc31a2d0bc4aa6e2735f7a4f4cdf970fc25817ec5e26c2a3f132ace5364218b0',
                'address': 'ltc1q0df03xqs0a9me76j8rvnjhdjjmxrxm9xcscvrf',
                'network': 'LTC',
                'currency': Currencies.ltc,
            },
        ]

        results = BlockchainExplorer.get_transactions_values_by_address(inputs)

        assert results[0]['value'] == Decimal('0.00039883')

    @pytest.mark.slow
    def test_get_transactions_values_by_address_one(self):
        inputs = [
            {
                'hash': '0xee3c8daede87f1281238726481693d9469e31904a7ce1a29ab9d6759fc40d6cf',
                'address': '0x68860bc66da1a7f4b81ad8bcf60c594b4fd64fb2',
                'network': 'ONE',
                'currency': Currencies.one,
            },
        ]

        results = BlockchainExplorer.get_transactions_values_by_address(inputs)

        assert results[0]['value'] == Decimal('0.500917846080667425')

    @pytest.mark.slow
    def test_get_transactions_values_by_address_pmn(self):
        inputs = [
            {
                'hash': 'c4a9dbcfa5a2f3c3968443eae289764deca35634f255314f40a03dce53194998',
                'address': 'GBF4ES6LS5WUYXFL4Z7XAWJG364NTSQWSWMEAA63A5LMCEWRHKAWBKH4',
                'network': 'PMN',
                'currency': Currencies.pmn,
            },
        ]

        results = BlockchainExplorer.get_transactions_values_by_address(inputs)

        assert results[0]['value'] == Decimal('25')

    @pytest.mark.slow
    def test_get_transactions_values_by_address_xrp(self):
        inputs = [
            {
                'hash': '3DE11014C9438A7F974EFD4292CD8E24F5F20AF692667DF31712F05987628694',
                'address': 'rBithomp4vj5E2kUebx7tVwipBueg55XxS',
                'network': 'XRP',
                'currency': Currencies.xrp,
            },
        ]

        results = BlockchainExplorer.get_transactions_values_by_address(inputs)

        assert results[0]['value'] == Decimal('0.001')

    @pytest.mark.slow
    def test_get_transactions_values_by_address_trx(self):
        inputs = [
            {
                'hash': '8f589584ec6c26c39750587ea361222088e02b6245af85a62962bb6c88e28da9',
                'address': 'TFcGPZmf7zigbRMxKbYd4qg4ehiqwoKNsW',
                'network': 'TRX',
                'currency': Currencies.trx,
            },
        ]

        results = BlockchainExplorer.get_transactions_values_by_address(inputs)

        assert results[0]['value'] == Decimal('0.000066')

    @pytest.mark.slow
    def test_get_transactions_values_by_address_xlm(self):
        inputs = [
            {
                'hash': '950b76ace2416b09564943c058e243d5d05aaad4cf19595a6170024791fe2f58',
                'address': 'GAOB3HQAJ62OMQKZVJWY5HSO2X5JSLFPLH2UUXBTYLE3YUBOD4KKE4LH',
                'network': 'XLM',
                'currency': Currencies.xlm,
            },
        ]

        results = BlockchainExplorer.get_transactions_values_by_address(inputs)

        assert results[0]['value'] == Decimal('0.0002')


class TestGetWalletBalances(TestCase):

    def test_near_figment_get_token_txs(self):
        address = 'sarkov.near'
        api_name = 'near_figment'
        APIS_CONF['NEAR']['get_txs'] = api_name
        api = APIS_CLASSES[api_name].get_api()

        api_responses = [
            {'height': 70756483, 'time': '2022-07-27T12:59:53.661917Z'},
            {'page': 1, 'limit': 25, 'records': [{'id': 119195351, 'created_at': '2022-04-22T12:50:27.399956Z',
                                                  'updated_at': '2022-04-22T12:50:27.399956Z',
                                                  'time': '2022-04-22T12:49:36.790943Z', 'height': 64067040,
                                                  'hash': '3KNL67MowcntuGZ6f7DFXJBpfzHaVihRK7XZHkNmMKCw',
                                                  'block_hash': 'HeJLr4PJoe6pYw4dzre6PjeuRE2xL5rMHqc318UFxtYG',
                                                  'sender': '7747991786f445efb658b69857eadc7a57b6b475beec26ed14da8bc35bb2b5b6',
                                                  'receiver': 'sarkov.near', 'gas_burnt': '870920187500',
                                                  'fee': '44636512500000000000',
                                                  'public_key': 'ed25519:92cqaxfHXZNJdkbVDKMaYcYbah9fxXJ4h2DQ5wFSQbj3',
                                                  'signature': 'ed25519:LCnmWe2fcdkk3DjZZULbaYPnvKHiPFqvdCXTRtJTNToaiV8JY5Kzwbvq2oxBCasEByjxBou93KVY8XykUrM8hUM',
                                                  'actions': [{'data': {'deposit': '311932613000000000000000000'},
                                                               'type': 'Transfer'}], 'actions_count': 1,
                                                  'outcome': {'id': '3KNL67MowcntuGZ6f7DFXJBpfzHaVihRK7XZHkNmMKCw',
                                                              'outcome': {'logs': [], 'status': {'Failure': None,
                                                                                                 'SuccessValue': None,
                                                                                                 'SuccessReceiptId': 'D5tsURHFvawiQDXwYnADcMtFycvUxu9LhHMW9HCTCkwi'},
                                                                          'gas_burnt': 223182562500,
                                                                          'executor_id': '7747991786f445efb658b69857eadc7a57b6b475beec26ed14da8bc35bb2b5b6',
                                                                          'receipt_ids': [
                                                                              'D5tsURHFvawiQDXwYnADcMtFycvUxu9LhHMW9HCTCkwi'],
                                                                          'tokens_burnt': '22318256250000000000'},
                                                              'block_hash': 'HeJLr4PJoe6pYw4dzre6PjeuRE2xL5rMHqc318UFxtYG'},
                                                  'receipt': [{'id': 'D5tsURHFvawiQDXwYnADcMtFycvUxu9LhHMW9HCTCkwi',
                                                               'outcome': {'logs': [], 'status': {'Failure': None,
                                                                                                  'SuccessValue': '',
                                                                                                  'SuccessReceiptId': None},
                                                                           'gas_burnt': 223182562500,
                                                                           'executor_id': 'sarkov.near',
                                                                           'receipt_ids': [
                                                                               'ECyKvRhSFSq3hj7biaSZrFATCgKBxua7XsKKMQy7HchT'],
                                                                           'tokens_burnt': '22318256250000000000'},
                                                               'block_hash': 'GcbCvusVfsFo99sq6RCpvzT9XYnFHaBPpvjeZEBRaKjc'},
                                                              {'id': 'ECyKvRhSFSq3hj7biaSZrFATCgKBxua7XsKKMQy7HchT',
                                                               'outcome': {'logs': [], 'status': {'Failure': None,
                                                                                                  'SuccessValue': '',
                                                                                                  'SuccessReceiptId': None},
                                                                           'gas_burnt': 424555062500,
                                                                           'executor_id': '7747991786f445efb658b69857eadc7a57b6b475beec26ed14da8bc35bb2b5b6',
                                                                           'receipt_ids': [], 'tokens_burnt': '0'},
                                                               'block_hash': '9hg8CQDPeYKsLzDtAsh6DBZUGAwurbcezsJzWtfpTsU2'}],
                                                  'success': True},
                                                 {'id': 119192511, 'created_at': '2022-04-22T12:46:42.935196Z',
                                                  'updated_at': '2022-04-22T12:46:42.935196Z',
                                                  'time': '2022-04-22T12:46:00.150394Z', 'height': 64066866,
                                                  'hash': 'DqQBLMqBH4mRUUjd9CMbo16Yg4ug5D8Gqcjgp2bjFDKo',
                                                  'block_hash': 'CkfaKCcPTWEYtP8UEfjTYPT2viuS2SA3rL8cY7wdEa1Z',
                                                  'sender': '7747991786f445efb658b69857eadc7a57b6b475beec26ed14da8bc35bb2b5b6',
                                                  'receiver': 'sarkov.near', 'gas_burnt': '870920187500',
                                                  'fee': '44636512500000000000',
                                                  'public_key': 'ed25519:92cqaxfHXZNJdkbVDKMaYcYbah9fxXJ4h2DQ5wFSQbj3',
                                                  'signature': 'ed25519:LpebWLMmLE35eYjVuriqbeCUThxBqj612AoYDbYVMp1q8tqgmxr2wLGWG9A3cRvkDbQxv4r1u8Xx8u8tFVhbnQn',
                                                  'actions': [{'data': {'deposit': '990000000000000000000000'},
                                                               'type': 'Transfer'}], 'actions_count': 1,
                                                  'outcome': {'id': 'DqQBLMqBH4mRUUjd9CMbo16Yg4ug5D8Gqcjgp2bjFDKo',
                                                              'outcome': {'logs': [], 'status': {'Failure': None,
                                                                                                 'SuccessValue': None,
                                                                                                 'SuccessReceiptId': 'FvHpp9UuMi4oRshKYNCT23exfzL35TL7Uv5GA5LzQueQ'},
                                                                          'gas_burnt': 223182562500,
                                                                          'executor_id': '7747991786f445efb658b69857eadc7a57b6b475beec26ed14da8bc35bb2b5b6',
                                                                          'receipt_ids': [
                                                                              'FvHpp9UuMi4oRshKYNCT23exfzL35TL7Uv5GA5LzQueQ'],
                                                                          'tokens_burnt': '22318256250000000000'},
                                                              'block_hash': 'CkfaKCcPTWEYtP8UEfjTYPT2viuS2SA3rL8cY7wdEa1Z'},
                                                  'receipt': [{'id': 'FvHpp9UuMi4oRshKYNCT23exfzL35TL7Uv5GA5LzQueQ',
                                                               'outcome': {'logs': [], 'status': {'Failure': None,
                                                                                                  'SuccessValue': '',
                                                                                                  'SuccessReceiptId': None},
                                                                           'gas_burnt': 223182562500,
                                                                           'executor_id': 'sarkov.near',
                                                                           'receipt_ids': [
                                                                               'HxyAi2XMHziwWzrDfxbYPibpQTMPDtPnhcpoUAkakCiQ'],
                                                                           'tokens_burnt': '22318256250000000000'},
                                                               'block_hash': '3vxRLEkstf1s4Z12bhkSQiu1mx35LE1RzVgg8DMx4WcQ'},
                                                              {'id': 'HxyAi2XMHziwWzrDfxbYPibpQTMPDtPnhcpoUAkakCiQ',
                                                               'outcome': {'logs': [], 'status': {'Failure': None,
                                                                                                  'SuccessValue': '',
                                                                                                  'SuccessReceiptId': None},
                                                                           'gas_burnt': 424555062500,
                                                                           'executor_id': '7747991786f445efb658b69857eadc7a57b6b475beec26ed14da8bc35bb2b5b6',
                                                                           'receipt_ids': [], 'tokens_burnt': '0'},
                                                               'block_hash': 'EiPxEemsydZfyZqJRvVZ46wYuh5zmUt3n8U2r5yEH5dT'}],
                                                  'success': True},
                                                 {'id': 116880200, 'created_at': '2022-04-19T21:57:03.654621Z',
                                                  'updated_at': '2022-04-19T21:57:03.654621Z',
                                                  'time': '2022-04-19T21:56:17.147738Z', 'height': 63884333,
                                                  'hash': 'vRNvtMYAYeYnUWRwJTZ2pXKWh5U86rSnTQHGp28G8aM',
                                                  'block_hash': 'DjUTJktDR9pza55zvDsz9hpm4XtWwkLcoKwK9sGVfpQE',
                                                  'sender': 'sarkov.near', 'receiver': 'sarkov.near',
                                                  'gas_burnt': '406012250000', 'fee': '40601225000000000000',
                                                  'public_key': 'ed25519:6YXBPy4r6vLYzFNMmoLCzYQ5joJpkCa4k2hnvut57Gwa',
                                                  'signature': 'ed25519:7JQZK1rv4oz4Y9fvcnqjA558VcER1Vgxdm5pwYMQEvw8V3CAUx88AbMjvU684m3fEMT5eknRkgC5X25azUpWYjD',
                                                  'actions': [{'data': {
                                                      'public_key': 'ed25519:5zRaRWJqYkETDq4RX1TEANPJjnZFHgBrkVcye1uYrJW2'},
                                                      'type': 'DeleteKey'}], 'actions_count': 1,
                                                  'outcome': {'id': 'vRNvtMYAYeYnUWRwJTZ2pXKWh5U86rSnTQHGp28G8aM',
                                                              'outcome': {'logs': [], 'status': {'Failure': None,
                                                                                                 'SuccessValue': None,
                                                                                                 'SuccessReceiptId': '5nvFw7NCEYG7v5GUDWnDKnSpaCmhdM7Cp217CJeUkxfL'},
                                                                          'gas_burnt': 203006125000,
                                                                          'executor_id': 'sarkov.near', 'receipt_ids': [
                                                                      '5nvFw7NCEYG7v5GUDWnDKnSpaCmhdM7Cp217CJeUkxfL'],
                                                                          'tokens_burnt': '20300612500000000000'},
                                                              'block_hash': 'DjUTJktDR9pza55zvDsz9hpm4XtWwkLcoKwK9sGVfpQE'},
                                                  'receipt': [{'id': '5nvFw7NCEYG7v5GUDWnDKnSpaCmhdM7Cp217CJeUkxfL',
                                                               'outcome': {'logs': [], 'status': {'Failure': None,
                                                                                                  'SuccessValue': '',
                                                                                                  'SuccessReceiptId': None},
                                                                           'gas_burnt': 203006125000,
                                                                           'executor_id': 'sarkov.near',
                                                                           'receipt_ids': [],
                                                                           'tokens_burnt': '20300612500000000000'},
                                                               'block_hash': 'DjUTJktDR9pza55zvDsz9hpm4XtWwkLcoKwK9sGVfpQE'}],
                                                  'success': True},
                                                 {'id': 116875937, 'created_at': '2022-04-19T21:53:39.651536Z',
                                                  'updated_at': '2022-04-19T21:53:39.651536Z',
                                                  'time': '2022-04-19T21:52:55.149589Z', 'height': 63884169,
                                                  'hash': 'CVD5GwNGdpz7JK8R8JhDhLaGfrwDAv5nAKcNKLJ5MeB',
                                                  'block_hash': 'H1UzNe5pyR25Dq1ZmJCszBCP5qMYdjgSaerG2pG1RQij',
                                                  'sender': 'sarkov.near', 'receiver': 'sarkov.near',
                                                  'gas_burnt': '420554250000', 'fee': '42055425000000000000',
                                                  'public_key': 'ed25519:6YXBPy4r6vLYzFNMmoLCzYQ5joJpkCa4k2hnvut57Gwa',
                                                  'signature': 'ed25519:3eyTD7AjbJwn4ceaeS72EMBdixMY5zbAiDVBm3c9FHQL7fLDKvGux9CyF7Hjf56UgzKjtnJ4Z6gk5Do4eAUVVo8w',
                                                  'actions': [{'data': {'access_key': {'nonce': 0, 'permission': {
                                                      'FunctionCall': {'allowance': '250000000000000000000000',
                                                                       'receiver_id': 'contract.main.burrow.near',
                                                                       'method_names': []}}},
                                                                        'public_key': 'ed25519:5zRaRWJqYkETDq4RX1TEANPJjnZFHgBrkVcye1uYrJW2'},
                                                               'type': 'AddKey'}], 'actions_count': 1,
                                                  'outcome': {'id': 'CVD5GwNGdpz7JK8R8JhDhLaGfrwDAv5nAKcNKLJ5MeB',
                                                              'outcome': {'logs': [], 'status': {'Failure': None,
                                                                                                 'SuccessValue': None,
                                                                                                 'SuccessReceiptId': 'DufQ7jaSfmaTqBJ6uTxk2LYmvJ6ErqPkGteGD93QJ7Pk'},
                                                                          'gas_burnt': 210277125000,
                                                                          'executor_id': 'sarkov.near', 'receipt_ids': [
                                                                      'DufQ7jaSfmaTqBJ6uTxk2LYmvJ6ErqPkGteGD93QJ7Pk'],
                                                                          'tokens_burnt': '21027712500000000000'},
                                                              'block_hash': 'H1UzNe5pyR25Dq1ZmJCszBCP5qMYdjgSaerG2pG1RQij'},
                                                  'receipt': [{'id': 'DufQ7jaSfmaTqBJ6uTxk2LYmvJ6ErqPkGteGD93QJ7Pk',
                                                               'outcome': {'logs': [], 'status': {'Failure': None,
                                                                                                  'SuccessValue': '',
                                                                                                  'SuccessReceiptId': None},
                                                                           'gas_burnt': 210277125000,
                                                                           'executor_id': 'sarkov.near',
                                                                           'receipt_ids': [],
                                                                           'tokens_burnt': '21027712500000000000'},
                                                               'block_hash': 'H1UzNe5pyR25Dq1ZmJCszBCP5qMYdjgSaerG2pG1RQij'}],
                                                  'success': True},
                                                 {'id': 116869876, 'created_at': '2022-04-19T21:48:04.183619Z',
                                                  'updated_at': '2022-04-19T21:48:04.183619Z',
                                                  'time': '2022-04-19T21:47:15.278625Z', 'height': 63883892,
                                                  'hash': '45sM5iM1mhyR3LEGe7KxVsxGmdx7cz1FDcew3CUcguTm',
                                                  'block_hash': 'GJ8zQW7BLQ7o5sozuwARSzUVcqE2QYxhGVFahhsDjso9',
                                                  'sender': 'sarkov.near', 'receiver': 'sarkov.near',
                                                  'gas_burnt': '419649250000', 'fee': '41964925000000000000',
                                                  'public_key': 'ed25519:59sw6WaGTk47TNcTp2w4TLcW4XpAC1EghHuW1rDjnyMo',
                                                  'signature': 'ed25519:9krHVFMrtpAYArNNBQ71NxRFxdsU6detiENP5boJiQmKcrZFZ2G9g3TNxwHA4jdpxBANxRJaopMXyKFofqy2SwZ',
                                                  'actions': [{'data': {
                                                      'access_key': {'nonce': 0, 'permission': 'FullAccess'},
                                                      'public_key': 'ed25519:6YXBPy4r6vLYzFNMmoLCzYQ5joJpkCa4k2hnvut57Gwa'},
                                                      'type': 'AddKey'}], 'actions_count': 1,
                                                  'outcome': {'id': '45sM5iM1mhyR3LEGe7KxVsxGmdx7cz1FDcew3CUcguTm',
                                                              'outcome': {'logs': [], 'status': {'Failure': None,
                                                                                                 'SuccessValue': None,
                                                                                                 'SuccessReceiptId': '4XEMh1Q4bwE2rBrLDZK3btnZcohZwVFsYrYFratnZqgX'},
                                                                          'gas_burnt': 209824625000,
                                                                          'executor_id': 'sarkov.near', 'receipt_ids': [
                                                                      '4XEMh1Q4bwE2rBrLDZK3btnZcohZwVFsYrYFratnZqgX'],
                                                                          'tokens_burnt': '20982462500000000000'},
                                                              'block_hash': 'GJ8zQW7BLQ7o5sozuwARSzUVcqE2QYxhGVFahhsDjso9'},
                                                  'receipt': [{'id': '4XEMh1Q4bwE2rBrLDZK3btnZcohZwVFsYrYFratnZqgX',
                                                               'outcome': {'logs': [], 'status': {'Failure': None,
                                                                                                  'SuccessValue': '',
                                                                                                  'SuccessReceiptId': None},
                                                                           'gas_burnt': 209824625000,
                                                                           'executor_id': 'sarkov.near',
                                                                           'receipt_ids': [],
                                                                           'tokens_burnt': '20982462500000000000'},
                                                               'block_hash': 'GJ8zQW7BLQ7o5sozuwARSzUVcqE2QYxhGVFahhsDjso9'}],
                                                  'success': True},
                                                 {'id': 53288264, 'created_at': '2021-12-27T20:15:13.116721Z',
                                                  'updated_at': '2021-12-27T20:15:13.116721Z',
                                                  'time': '2021-12-27T20:15:02.041074Z', 'height': 56122710,
                                                  'hash': 'AyXG4Xr5aGRrnxdLkfQVUk7ag1C53sEANyggodE2Jd54',
                                                  'block_hash': 'C6cynGeNTLqUo5tbiDgB3j95LcvZoedtF3F7bj4JWsqB',
                                                  'sender': 'sarkov.near', 'receiver': 'sarkov.near',
                                                  'gas_burnt': '419649250000', 'fee': '41964925000000000000',
                                                  'public_key': 'ed25519:59sw6WaGTk47TNcTp2w4TLcW4XpAC1EghHuW1rDjnyMo',
                                                  'signature': 'ed25519:pSkULQKhi3Qu8Jsy62U6Z5LyyZFUyLHocu4GAK7eEhsMzSzx6mJirX9DHRiWwkowptyTek2USDxLHE1dGMvs4FH',
                                                  'actions': [{'data': {
                                                      'access_key': {'nonce': 0, 'permission': 'FullAccess'},
                                                      'public_key': 'ed25519:9DiNS24us8E4vQfGtuP5yysEANr5VMXE1mSmrP4RmRb4'},
                                                      'type': 'AddKey'}], 'actions_count': 1,
                                                  'outcome': {'id': 'AyXG4Xr5aGRrnxdLkfQVUk7ag1C53sEANyggodE2Jd54',
                                                              'outcome': {'logs': [], 'status': {'Failure': None,
                                                                                                 'SuccessValue': None,
                                                                                                 'SuccessReceiptId': 'E2GpqFQWYoBZvue4avPXQysKU7vdpVZQozSJBr8mRhok'},
                                                                          'gas_burnt': 209824625000,
                                                                          'executor_id': 'sarkov.near', 'receipt_ids': [
                                                                      'E2GpqFQWYoBZvue4avPXQysKU7vdpVZQozSJBr8mRhok'],
                                                                          'tokens_burnt': '20982462500000000000'},
                                                              'block_hash': 'C6cynGeNTLqUo5tbiDgB3j95LcvZoedtF3F7bj4JWsqB'},
                                                  'receipt': [{'id': 'E2GpqFQWYoBZvue4avPXQysKU7vdpVZQozSJBr8mRhok',
                                                               'outcome': {'logs': [], 'status': {'Failure': None,
                                                                                                  'SuccessValue': '',
                                                                                                  'SuccessReceiptId': None},
                                                                           'gas_burnt': 209824625000,
                                                                           'executor_id': 'sarkov.near',
                                                                           'receipt_ids': [],
                                                                           'tokens_burnt': '20982462500000000000'},
                                                               'block_hash': 'C6cynGeNTLqUo5tbiDgB3j95LcvZoedtF3F7bj4JWsqB'}],
                                                  'success': True}]}
        ]

        txs = [
            Transaction(
                address=address,
                block=64067040,
                confirmations=6689443,
                from_address=['7747991786f445efb658b69857eadc7a57b6b475beec26ed14da8bc35bb2b5b6'],
                hash='3KNL67MowcntuGZ6f7DFXJBpfzHaVihRK7XZHkNmMKCw',
                timestamp=datetime.datetime(2022, 4, 22, 12, 49, 36, 790943, tzinfo=UTC),
                value=Decimal('311.932613000000000000000000'),
                is_double_spend=False,
                details={'id': 119195351, 'created_at': '2022-04-22T12:50:27.399956Z',
                         'updated_at': '2022-04-22T12:50:27.399956Z', 'time': '2022-04-22T12:49:36.790943Z',
                         'height': 64067040, 'hash': '3KNL67MowcntuGZ6f7DFXJBpfzHaVihRK7XZHkNmMKCw',
                         'block_hash': 'HeJLr4PJoe6pYw4dzre6PjeuRE2xL5rMHqc318UFxtYG',
                         'sender': '7747991786f445efb658b69857eadc7a57b6b475beec26ed14da8bc35bb2b5b6',
                         'receiver': 'sarkov.near', 'gas_burnt': '870920187500', 'fee': '44636512500000000000',
                         'public_key': 'ed25519:92cqaxfHXZNJdkbVDKMaYcYbah9fxXJ4h2DQ5wFSQbj3',
                         'signature': 'ed25519:LCnmWe2fcdkk3DjZZULbaYPnvKHiPFqvdCXTRtJTNToaiV8JY5Kzwbvq2oxBCasEByjxBou93KVY8XykUrM8hUM',
                         'actions': [{'data': {'deposit': '311932613000000000000000000'}, 'type': 'Transfer'}],
                         'actions_count': 1, 'outcome': {'id': '3KNL67MowcntuGZ6f7DFXJBpfzHaVihRK7XZHkNmMKCw',
                                                         'outcome': {'logs': [],
                                                                     'status': {'Failure': None, 'SuccessValue': None,
                                                                                'SuccessReceiptId': 'D5tsURHFvawiQDXwYnADcMtFycvUxu9LhHMW9HCTCkwi'},
                                                                     'gas_burnt': 223182562500,
                                                                     'executor_id': '7747991786f445efb658b69857eadc7a57b6b475beec26ed14da8bc35bb2b5b6',
                                                                     'receipt_ids': [
                                                                         'D5tsURHFvawiQDXwYnADcMtFycvUxu9LhHMW9HCTCkwi'],
                                                                     'tokens_burnt': '22318256250000000000'},
                                                         'block_hash': 'HeJLr4PJoe6pYw4dzre6PjeuRE2xL5rMHqc318UFxtYG'},
                         'receipt': [{'id': 'D5tsURHFvawiQDXwYnADcMtFycvUxu9LhHMW9HCTCkwi', 'outcome': {'logs': [],
                                                                                                        'status': {
                                                                                                            'Failure': None,
                                                                                                            'SuccessValue': '',
                                                                                                            'SuccessReceiptId': None},
                                                                                                        'gas_burnt': 223182562500,
                                                                                                        'executor_id': 'sarkov.near',
                                                                                                        'receipt_ids': [
                                                                                                            'ECyKvRhSFSq3hj7biaSZrFATCgKBxua7XsKKMQy7HchT'],
                                                                                                        'tokens_burnt': '22318256250000000000'},
                                      'block_hash': 'GcbCvusVfsFo99sq6RCpvzT9XYnFHaBPpvjeZEBRaKjc'},
                                     {'id': 'ECyKvRhSFSq3hj7biaSZrFATCgKBxua7XsKKMQy7HchT', 'outcome': {'logs': [],
                                                                                                        'status': {
                                                                                                            'Failure': None,
                                                                                                            'SuccessValue': '',
                                                                                                            'SuccessReceiptId': None},
                                                                                                        'gas_burnt': 424555062500,
                                                                                                        'executor_id': '7747991786f445efb658b69857eadc7a57b6b475beec26ed14da8bc35bb2b5b6',
                                                                                                        'receipt_ids': [],
                                                                                                        'tokens_burnt': '0'},
                                      'block_hash': '9hg8CQDPeYKsLzDtAsh6DBZUGAwurbcezsJzWtfpTsU2'}], 'success': True},
            ),
            Transaction(
                address=address,
                block=64066866,
                confirmations=6689617,
                from_address=['7747991786f445efb658b69857eadc7a57b6b475beec26ed14da8bc35bb2b5b6'],
                hash='DqQBLMqBH4mRUUjd9CMbo16Yg4ug5D8Gqcjgp2bjFDKo',
                timestamp=datetime.datetime(2022, 4, 22, 12, 46, 00, 150394, tzinfo=UTC),
                value=Decimal('0.990000000000000000000000'),
                is_double_spend=False,
                details={'id': 119192511, 'created_at': '2022-04-22T12:46:42.935196Z',
                         'updated_at': '2022-04-22T12:46:42.935196Z', 'time': '2022-04-22T12:46:00.150394Z',
                         'height': 64066866, 'hash': 'DqQBLMqBH4mRUUjd9CMbo16Yg4ug5D8Gqcjgp2bjFDKo',
                         'block_hash': 'CkfaKCcPTWEYtP8UEfjTYPT2viuS2SA3rL8cY7wdEa1Z',
                         'sender': '7747991786f445efb658b69857eadc7a57b6b475beec26ed14da8bc35bb2b5b6',
                         'receiver': 'sarkov.near', 'gas_burnt': '870920187500', 'fee': '44636512500000000000',
                         'public_key': 'ed25519:92cqaxfHXZNJdkbVDKMaYcYbah9fxXJ4h2DQ5wFSQbj3',
                         'signature': 'ed25519:LpebWLMmLE35eYjVuriqbeCUThxBqj612AoYDbYVMp1q8tqgmxr2wLGWG9A3cRvkDbQxv4r1u8Xx8u8tFVhbnQn',
                         'actions': [{'data': {'deposit': '990000000000000000000000'}, 'type': 'Transfer'}],
                         'actions_count': 1, 'outcome': {'id': 'DqQBLMqBH4mRUUjd9CMbo16Yg4ug5D8Gqcjgp2bjFDKo',
                                                         'outcome': {'logs': [],
                                                                     'status': {'Failure': None, 'SuccessValue': None,
                                                                                'SuccessReceiptId': 'FvHpp9UuMi4oRshKYNCT23exfzL35TL7Uv5GA5LzQueQ'},
                                                                     'gas_burnt': 223182562500,
                                                                     'executor_id': '7747991786f445efb658b69857eadc7a57b6b475beec26ed14da8bc35bb2b5b6',
                                                                     'receipt_ids': [
                                                                         'FvHpp9UuMi4oRshKYNCT23exfzL35TL7Uv5GA5LzQueQ'],
                                                                     'tokens_burnt': '22318256250000000000'},
                                                         'block_hash': 'CkfaKCcPTWEYtP8UEfjTYPT2viuS2SA3rL8cY7wdEa1Z'},
                         'receipt': [{'id': 'FvHpp9UuMi4oRshKYNCT23exfzL35TL7Uv5GA5LzQueQ', 'outcome': {'logs': [],
                                                                                                        'status': {
                                                                                                            'Failure': None,
                                                                                                            'SuccessValue': '',
                                                                                                            'SuccessReceiptId': None},
                                                                                                        'gas_burnt': 223182562500,
                                                                                                        'executor_id': 'sarkov.near',
                                                                                                        'receipt_ids': [
                                                                                                            'HxyAi2XMHziwWzrDfxbYPibpQTMPDtPnhcpoUAkakCiQ'],
                                                                                                        'tokens_burnt': '22318256250000000000'},
                                      'block_hash': '3vxRLEkstf1s4Z12bhkSQiu1mx35LE1RzVgg8DMx4WcQ'},
                                     {'id': 'HxyAi2XMHziwWzrDfxbYPibpQTMPDtPnhcpoUAkakCiQ', 'outcome': {'logs': [],
                                                                                                        'status': {
                                                                                                            'Failure': None,
                                                                                                            'SuccessValue': '',
                                                                                                            'SuccessReceiptId': None},
                                                                                                        'gas_burnt': 424555062500,
                                                                                                        'executor_id': '7747991786f445efb658b69857eadc7a57b6b475beec26ed14da8bc35bb2b5b6',
                                                                                                        'receipt_ids': [],
                                                                                                        'tokens_burnt': '0'},
                                      'block_hash': 'EiPxEemsydZfyZqJRvVZ46wYuh5zmUt3n8U2r5yEH5dT'}], 'success': True},
            )
        ]

        api.request = Mock()
        api.request.side_effect = api_responses

        results = BlockchainExplorer.get_wallet_transactions(address, Currencies.near, 'NEAR')
        for (result, tx) in zip(results.get(Currencies.near), txs):
            assert result.address == tx.address
            assert result.from_address == tx.from_address
            assert result.hash == tx.hash
            assert result.is_double_spend == tx.is_double_spend
            assert result.details == tx.details
            assert result.timestamp == tx.timestamp
            assert result.confirmations == tx.confirmations

    def test_near_figment_get_balance(self):
        addresses = ['sweat_welcome.near', 'd5bcc9c93414f11c9a10fd350aef5369b46870ce9bbe8c1aff9bf5fd0fe68afe']
        api_name = 'near_figment'
        api = APIS_CLASSES[api_name].get_api()
        APIS_CONF['NEAR']['get_balances'] = api_name
        api_responses = [
            {'amount': '6954471269634487588793694644', 'locked': '0', 'code_hash': '11111111111111111111111111111111',
             'storage_usage': 6332, 'storage_paid_at': 0, 'block_height': 70755276,
             'block_hash': '9Hvt8GgCdZLewSjdnKJScEMoyQbZciwVWfZUnLDg2bsq', 'staked_amount': '0',
             'staking_pools_count': 1},
            {'amount': '79899860000000000000000000', 'locked': '0', 'code_hash': '11111111111111111111111111111111',
             'storage_usage': 182, 'storage_paid_at': 0, 'block_height': 70755315,
             'block_hash': '3TGb5uQKcXGb41uzwy8KaDQ87ybWvvgZaaYSE6K6qDbF', 'staked_amount': '0',
             'staking_pools_count': 0},
        ]
        balances = [
            {'address': 'sweat_welcome.near', 'balance': Decimal('6954.471269634487588793694644'),
             'received': Decimal('6954.471269634487588793694644'), 'sent': Decimal('0'), 'rewarded': Decimal('0')},
            {'address': 'd5bcc9c93414f11c9a10fd350aef5369b46870ce9bbe8c1aff9bf5fd0fe68afe',
             'balance': Decimal('79.899860000000000000000000'), 'received': Decimal('79.899860000000000000000000'),
             'sent': Decimal('0'), 'rewarded': Decimal('0')}
        ]
        api.request = Mock()
        api.request.side_effect = api_responses
        results = BlockchainExplorer.get_wallets_balance({'NEAR': addresses}, Currencies.near)
        for (result, balance) in zip(results.get(Currencies.near), balances):
            assert result.get('address') == balance.get('address')
            assert result.get('balance') == balance.get('balance')


class TestGeneralExplorerXMR(TestCase):
    def test_monero_get_balance(self):
        addresses = ['5B6VFJxQYCN9yGfj9RtrV78iPMb6tMSbX8QcvmHUAp4tPv7Ytj5EXwt3dprQ5HcXxeCcQR1BLR55TVjfNvMym3bCTXt4Woi',
                     '7B5HumBNsh3iMNFQs72DLzKwUPq7DFDhn5fB5yB7SsVHJLgTA7KHk5zgnm4xczPYi2BhPXozrsS3NYEZyUTKHLoFVa2kaiG']
        api_responses = [
            {'confirmed_balance': '33.771573420000', 'unconfirmed_balance': '33.771573420000'},
            {
                'code': '-1',
                'message': "Get parameters error. couldn't find the given address",
                'status': 'failed',
            }

        ]
        balances = [{
            'address': '5B6VFJxQYCN9yGfj9RtrV78iPMb6tMSbX8QcvmHUAp4tPv7Ytj5EXwt3dprQ5HcXxeCcQR1BLR55TVjfNvMym3bCTXt4Woi',
            'balance': Decimal('33.771573420000'), 'received': Decimal('33.771573420000'),
            'sent': Decimal('0'), 'rewarded': Decimal('0')
        }]
        MoneroExplorerClient.get_client().request = Mock()
        MoneroExplorerClient.get_client().request.side_effect = api_responses
        results = BlockchainExplorer.get_wallets_balance({'XMR': addresses}, Currencies.xmr).get(Currencies.xmr)
        assert results[0].get('address') == balances[0].get('address')
        assert results[0].get('balance') == balances[0].get('balance')

    def test_monero_get_txs(self):
        # address = '5B6VFJxQYCN9yGfj9RtrV78iPMb6tMSbX8QcvmHUAp4tPv7Ytj5EXwt3dprQ5HcXxeCcQR1BLR55TVjfNvMym3bCTXt4Woi'
        address = '7B5HumBNsh3iMNFQs72DLzKwUPq7DFDhn5fB5yB7SsVHJLgTA7KHk5zgnm4xczPYi2BhPXozrsS3NYEZyUTKHLoFVa2kaiG'
        api_responses = [{
            'transfers': [
                {
                    'amount': '2.300000000000',
                    'confirmation': 735,
                    'destination': '7B5HumBNsh3iMNFQs72DLzKwUPq7DFDhn5fB5yB7SsVHJLgTA7KHk5zgnm4xczPYi2BhPXozrsS3NYEZyUTKHLoFVa2kaiG',
                    'fee': '0.000879900000',
                    'height': 1164340,
                    'timestamp': 1661333191.0,
                    'tx_hash': '5cb1b5ba760b2e388606227e6fbdaf27e2a0b700fe6532396d18e310c3e73957',
                }
            ]
        }]

        txs = [Transaction(
            address=address,
            from_address=[],
            block=1164340,
            hash='5cb1b5ba760b2e388606227e6fbdaf27e2a0b700fe6532396d18e310c3e73957',
            timestamp=datetime.datetime(2022, 8, 24, 13, 56, 31, tzinfo=UTC),
            value=Decimal('2.300000000000'),
            confirmations=735,
            is_double_spend=False,
            details=api_responses[0].get('transfers')[0],
            tag=None
        )]
        MoneroExplorerClient.get_client().request = Mock()
        MoneroExplorerClient.get_client().request.side_effect = api_responses
        results = BlockchainExplorer.get_wallet_transactions(address, Currencies.xmr, network='XMR')

        for (result, tx) in zip(results.get(Currencies.xmr), txs):
            assert result.address == tx.address
            assert result.value == tx.value
            assert result.block == tx.block
            assert result.from_address == tx.from_address
            assert result.hash == tx.hash
            assert result.is_double_spend == tx.is_double_spend
            assert result.details == tx.details
            assert result.timestamp == tx.timestamp
            assert result.confirmations == tx.confirmations

    def test_get_transactions_values_by_address(self):
        input_ = [
            {
                'hash': '5cb1b5ba760b2e388606227e6fbdaf27e2a0b700fe6532396d18e310c3e73957',
                'address': '75EL6VKEmJUEc3MgXkBo2ZDKPRzBe54b3fbBMG1HmWr5SUDZQZZTgviEAhi9ajXZekeKW9qjk4yYpLe5CE8tnzhrQrTvFeg',
                'network': 'XMR',
                'currency': Currencies.xmr,
            },
        ]
        api_response = {
            'transfers': [
                {
                    'amount': 1004000000000,
                    'confirmation': 795,
                    'destination': '75EL6VKEmJUEc3MgXkBo2ZDKPRzBe54b3fbBMG1HmWr5SUDZQZZTgviEAhi9ajXZekeKW9qjk4yYpLe5CE8tnzhrQrTvFeg',
                    'fee': 879900000,
                    'height': 1164340,
                    'status': True,
                    'timestamp': 1661333191,
                    'tx_hash': '5cb1b5ba760b2e388606227e6fbdaf27e2a0b700fe6532396d18e310c3e73957',
                },
                {
                    'amount': 2020000000000,
                    'confirmation': 795,
                    'destination': '73skwwyJ9rB8vepShK5GR1TmzMKYQEgkQNpx1Kuyd6XoipoJabCp5yrcGQMKwvxdL2SmzJtiFBKiqihzNUmYvtHyLVoR7SY',
                    'fee': 879900000,
                    'height': 1164340,
                    'status': True,
                    'timestamp': 1661333191,
                    'tx_hash': '5cb1b5ba760b2e388606227e6fbdaf27e2a0b700fe6532396d18e310c3e73957',
                }
            ]
        }

        MoneroExplorerClient.get_client().request = Mock()
        MoneroExplorerClient.get_client().request.side_effect = [api_response]
        results = BlockchainExplorer.get_transactions_values_by_address(input_)

        assert results[0].get('value') == Decimal('1.004')


@pytest.mark.slow
class TestGeneralExplorerALGO(TestCase):
    dummy_address = 'GIBQHQSQZRMOHM4ZNNAZXJ75BBKQEYBRU5KCEJL4Y77V36FDBXRJ6ZSUPE'

    def test_validate_addresses(self):
        result = validate_algo_address(self.dummy_address)
        self.assertTrue(result)

        bad_length_address = self.dummy_address[1:]
        result = validate_algo_address(bad_length_address)
        self.assertFalse(result)

        bad_checksum_address = self.dummy_address[:-1] + 'U'
        result = validate_algo_address(bad_checksum_address)
        self.assertFalse(result)

        bad_b32_address = self.dummy_address[:-1] + '1'
        result = validate_algo_address(bad_b32_address)
        self.assertFalse(result)

    def test_get_balance(self):
        dummy_resp = {
            "account": {"address": "GIBQHQSQZRMOHM4ZNNAZXJ75BBKQEYBRU5KCEJL4Y77V36FDBXRJ6ZSUPE", "amount": 500000,
                        "amount-without-pending-rewards": 500000, "created-at-round": 21298441, "deleted": False,
                        "pending-rewards": 0, "reward-base": 218288, "rewards": 0, "round": 21299595, "sig-type": "sig",
                        "status": "Offline", "total-apps-opted-in": 0, "total-assets-opted-in": 0,
                        "total-created-apps": 0, "total-created-assets": 0}, "current-round": 21299595}

        api_name = 'algo_pure_stake'
        api = APIS_CLASSES[api_name].get_api()
        APIS_CONF['ALGO']['get_balances'] = api_name
        api.request = Mock()
        api.request.return_value = dummy_resp

        result = BlockchainExplorer.get_wallets_balance({'ALGO': [self.dummy_address]}, Currencies.algo).get(
            Currencies.algo)

        self.assertEqual(float(result[0]['balance']), 0.5)
        self.assertEqual(self.dummy_address, result[0]['address'])

        api_name = 'algo_node'
        api = APIS_CLASSES[api_name].get_api()
        APIS_CONF['ALGO']['get_balances'] = api_name
        api.request = Mock()
        api.request.return_value = dummy_resp

        result = BlockchainExplorer.get_wallets_balance({'ALGO': [self.dummy_address]}, Currencies.algo).get(
            Currencies.algo)
        self.assertEqual(float(result[0]['balance']), 0.5)
        self.assertEqual(self.dummy_address, result[0]['address'])

        api_name = 'algo_rand_labs'
        api = APIS_CLASSES[api_name].get_api()
        APIS_CONF['ALGO']['get_balances'] = api_name
        api.request = Mock()
        api.request.return_value = dummy_resp

        result = BlockchainExplorer.get_wallets_balance({'ALGO': [self.dummy_address]}, Currencies.algo).get(
            Currencies.algo)

        self.assertEqual(float(result[0]['balance']), 0.5)
        self.assertEqual(self.dummy_address, result[0]['address'])

        api_name = 'algo_bloq_cloud'
        api = APIS_CLASSES[api_name].get_api()
        APIS_CONF['ALGO']['get_balances'] = api_name
        api.request = Mock()
        api.request.return_value = dummy_resp

        result = BlockchainExplorer.get_wallets_balance({'ALGO': [self.dummy_address]}, Currencies.algo).get(
            Currencies.algo)

        self.assertEqual(float(result[0]['balance']), 0.5)
        self.assertEqual(self.dummy_address, result[0]['address'])

    def test_get_transactions(self):
        dummy_resp = {"current-round": 21299941, "next-token": "fAFFAQAAAAAjAAAA", "transactions": [
            {"close-rewards": 0, "closing-amount": 0, "confirmed-round": 21299580, "fee": 1000, "first-valid": 21299578,
             "genesis-hash": "wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=", "genesis-id": "mainnet-v1.0",
             "id": "5JI6E6UKBFDDE2GOMATHEGBQGKOUKLYG7VI6N4RQKLS6KRAWALQQ", "intra-round-offset": 35,
             "last-valid": 21300578, "note": "Y29tbWl0", "payment-transaction": {"amount": 39499000, "close-amount": 0,
                                                                                 "receiver": "6BFMCUY4NBARUYMWVNK5THL5QYDQFX7BYZB2X7Q3T37WKOP3WFN4EPKJPY"},
             "receiver-rewards": 0, "round-time": 1653848175,
             "sender": "GIBQHQSQZRMOHM4ZNNAZXJ75BBKQEYBRU5KCEJL4Y77V36FDBXRJ6ZSUPE", "sender-rewards": 0, "signature": {
                "sig": "HCnYaRnoDGtxVQyGrjxyivl8sai7KFYCzslsPGYOR7bwUZXWx068jm/DYU654h6tRWL6EQFhOjoWeVF6EXfRAw=="},
             "tx-type": "pay"}]}

        api_name = 'algo_node'
        api = APIS_CLASSES[api_name].get_api()
        APIS_CONF['ALGO']['get_txs'] = api_name
        api.request = Mock()
        api.request.return_value = dummy_resp

        result = BlockchainExplorer.get_wallet_transactions(self.dummy_address, Currencies.algo, 'ALGO').get(
            Currencies.algo)
        result = vars(result[0])

        self.assertEqual(result['address'], self.dummy_address)
        self.assertEqual(result['from_address'][0], self.dummy_address)
        self.assertEqual(result['hash'], dummy_resp['transactions'][0]['id'])
        self.assertEqual(result['block'], dummy_resp['transactions'][0]['confirmed-round'])
        self.assertEqual(float(result['value']), -39.499)
        self.assertEqual(result['confirmations'], 361)

        api_name = 'algo_pure_stake'
        api = APIS_CLASSES[api_name].get_api()
        APIS_CONF['ALGO']['get_txs'] = api_name
        api.request = Mock()
        api.request.return_value = dummy_resp

        result = BlockchainExplorer.get_wallet_transactions(self.dummy_address, Currencies.algo, 'ALGO').get(
            Currencies.algo)
        result = vars(result[0])

        self.assertEqual(result['address'], self.dummy_address)
        self.assertEqual(result['from_address'][0], self.dummy_address)
        self.assertEqual(result['hash'], dummy_resp['transactions'][0]['id'])
        self.assertEqual(result['block'], dummy_resp['transactions'][0]['confirmed-round'])
        self.assertEqual(float(result['value']), -39.499)
        self.assertEqual(result['confirmations'], 361)

        api_name = 'algo_rand_labs'
        api = APIS_CLASSES[api_name].get_api()
        APIS_CONF['ALGO']['get_txs'] = api_name
        api.request = Mock()
        api.request.return_value = dummy_resp

        result = BlockchainExplorer.get_wallet_transactions(self.dummy_address, Currencies.algo, 'ALGO').get(
            Currencies.algo)
        result = vars(result[0])

        self.assertEqual(result['address'], self.dummy_address)
        self.assertEqual(result['from_address'][0], self.dummy_address)
        self.assertEqual(result['hash'], dummy_resp['transactions'][0]['id'])
        self.assertEqual(result['block'], dummy_resp['transactions'][0]['confirmed-round'])
        self.assertEqual(float(result['value']), -39.499)
        self.assertEqual(result['confirmations'], 361)

        api_name = 'algo_bloq_cloud'
        api = APIS_CLASSES[api_name].get_api()
        APIS_CONF['ALGO']['get_txs'] = api_name
        api.request = Mock()
        api.request.return_value = dummy_resp

        result = BlockchainExplorer.get_wallet_transactions(self.dummy_address, Currencies.algo, 'ALGO').get(
            Currencies.algo)
        result = vars(result[0])

        self.assertEqual(result['address'], self.dummy_address)
        self.assertEqual(result['from_address'][0], self.dummy_address)
        self.assertEqual(result['hash'], dummy_resp['transactions'][0]['id'])
        self.assertEqual(result['block'], dummy_resp['transactions'][0]['confirmed-round'])
        self.assertEqual(float(result['value']), -39.499)
        self.assertEqual(result['confirmations'], 361)

    def test_get_block(self):
        dummy_block_resp = {"current-round": 21308796, "next-token": "ciVFAQAAAAArAAAA", "transactions": [
            {"close-rewards": 0, "closing-amount": 0, "confirmed-round": 21308786, "fee": 1000, "first-valid": 21308784,
             "genesis-hash": "wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=", "genesis-id": "mainnet-v1.0",
             "group": "H3RbUbFtMJBpMTKFgnjNBwdi3OhX8hpnv7e7wYolYWU=",
             "id": "6EXU4PA3DHUKNGUEA6VPTV7WE7F7VNBYPKQYVYWWVML6FZYRSJ6Q", "intra-round-offset": 11,
             "last-valid": 21308788, "note": "E0ko8xcpWzdlKCVpRXQq0IRfcLqGxMorufQJyaSaofc=",
             "payment-transaction": {"amount": 2000, "close-amount": 0,
                                     "receiver": "2TUBOBZ7CP7EZXFOWULEG5HE6WJ34TT7SBZ5AMHGR222O7RZNBK3I4BUMY"},
             "receiver-rewards": 0, "round-time": 1653888146,
             "sender": "MAPEFN7K2M5Z4TPOVOXHVBTW2M46SQPROBLGYXAZ56K4SHTEUCOOZCMRZE", "sender-rewards": 0, "signature": {
                "sig": "mvXLYGyF/l8bli50NAZ1nTwTtMHDEWCnk+DW4jKYNV1CGQ1v5QlOY9+XdSvHM4usfykcNnghF6y0rHDJvE2RDQ=="},
             "tx-type": "pay"},
            {"close-rewards": 0, "closing-amount": 0, "confirmed-round": 21308786, "fee": 1000, "first-valid": 21308784,
             "genesis-hash": "wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=", "genesis-id": "mainnet-v1.0",
             "group": "j8pRocnYhmj8gO6b5btkveYaEsNqvEvD4l36h8Eo+kU=",
             "id": "4C43VJ2AAZUH3ZFCG4I6GUGILERPU542CBYX5JWHML4V62N57ECQ", "intra-round-offset": 15,
             "last-valid": 21308788, "note": "qPprK8Y6BNl5GTpW20E1wyTPsE5J/fSgBOlccyaIREk=",
             "payment-transaction": {"amount": 2000, "close-amount": 0,
                                     "receiver": "L6ENK7LD47SJZX6VQOHDZFM7PK6ZHI5436ELEVVEULQ5OAPYI3SSFXYLSY"},
             "receiver-rewards": 0, "round-time": 1653888146,
             "sender": "MAPEFN7K2M5Z4TPOVOXHVBTW2M46SQPROBLGYXAZ56K4SHTEUCOOZCMRZE", "sender-rewards": 0, "signature": {
                "sig": "AM9uML1kdj8VHO4axdwLUlVlaE5oU+6UXpxes0gOU4ftVtbj6HYN32HcymJqRwhFIz1UPsgHNwPB5yxk2me/Aw=="},
             "tx-type": "pay"},
            {"close-rewards": 0, "closing-amount": 0, "confirmed-round": 21308786, "fee": 1000, "first-valid": 21308784,
             "genesis-hash": "wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=", "genesis-id": "mainnet-v1.0",
             "group": "OL80f0YK+N4tk02wkarElpq+u8OPtGj4y0EkRjBSBcM=",
             "id": "YYGC7ISQBZNARODKOS6WJWFV2HY5LGIZB7H7PBXI732VULOUSAVA", "intra-round-offset": 19,
             "last-valid": 21308788, "note": "35Wphzb4Mktfl6mpqo29+TqXyFMR8ZKV+YJbKoBrFCY=",
             "payment-transaction": {"amount": 2000, "close-amount": 0,
                                     "receiver": "2TUBOBZ7CP7EZXFOWULEG5HE6WJ34TT7SBZ5AMHGR222O7RZNBK3I4BUMY"},
             "receiver-rewards": 0, "round-time": 1653888146,
             "sender": "MAPEFN7K2M5Z4TPOVOXHVBTW2M46SQPROBLGYXAZ56K4SHTEUCOOZCMRZE", "sender-rewards": 0, "signature": {
                "sig": "Ruu2LQI56+9oM2m/OlPwYZaI6m3knrQK0NxKPlu5OqgHln2ed2DXW/YA6tJIM9nn7UQzmFE7TEHP9Em5iyV3Ag=="},
             "tx-type": "pay"},
            {"close-rewards": 0, "closing-amount": 0, "confirmed-round": 21308786, "fee": 1000, "first-valid": 21308784,
             "genesis-hash": "wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=", "genesis-id": "mainnet-v1.0",
             "group": "kuTuMOxOcP+nBdxI5GTCtRGECuqknpgQlPdIvgN2X8M=",
             "id": "U6RVXYDSS2CWY3R3P4RPDIANRGCV22CVM7OWIQCPQUJ5O2UUEKMQ", "intra-round-offset": 22,
             "last-valid": 21308788, "note": "406nv5M0DVDsl83qapeqLiyY6BEu+iJOH6Qxp5HRpS4=",
             "payment-transaction": {"amount": 2000, "close-amount": 0,
                                     "receiver": "2TUBOBZ7CP7EZXFOWULEG5HE6WJ34TT7SBZ5AMHGR222O7RZNBK3I4BUMY"},
             "receiver-rewards": 0, "round-time": 1653888146,
             "sender": "MAPEFN7K2M5Z4TPOVOXHVBTW2M46SQPROBLGYXAZ56K4SHTEUCOOZCMRZE", "sender-rewards": 0, "signature": {
                "sig": "y3zCiwx+BPomyNQjDCNShooROo+po+zpjZ+lr9nTZMBVW1Qx9evrm83OXLmkMsHSg18b7FUWojxAh236StCmAA=="},
             "tx-type": "pay"}, {"close-rewards": 0, "closing-amount": 0, "confirmed-round": 21308786, "fee": 247000,
                                 "first-valid": 21308784,
                                 "genesis-hash": "wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=",
                                 "genesis-id": "mainnet-v1.0",
                                 "id": "UYBO35UI4MUJGPFG6H2ACJXTABQIYRXF3YF7SKL2S2J76WPYVRAA", "intra-round-offset": 36,
                                 "last-valid": 21309784, "payment-transaction": {"amount": 1000000, "close-amount": 0,
                                                                                 "receiver": "M2LCDSDNVYUPN2BBCKHBTCKREV7J4DGJSLZDJLYINGKIQ4EVOO5HZ2ZH54"},
                                 "receiver-rewards": 0, "round-time": 1653888146,
                                 "sender": "JDQ7EW3VY2ZHK4DKUHMNP35XLFPRJBND6M7SZ7W5RCFDNYAA47OC5IS62I",
                                 "sender-rewards": 0, "signature": {
                    "sig": "UFHZKt/vN/MAY5oVX3eMIo8JTgZhMbhw3XakUtuO1Rhxnyl3+n3U2nVE49P0izDxJ2ARsjq5rw3VUxriGc9IDQ=="},
                                 "tx-type": "pay"},
            {"close-rewards": 0, "closing-amount": 0, "confirmed-round": 21308786, "fee": 247000,
             "first-valid": 21308784, "genesis-hash": "wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=",
             "genesis-id": "mainnet-v1.0", "id": "Q4A4N5DWHVZJLSHWW3KGVUFGBWAPYJLLEIQALJV2RM62SH6OYSIA",
             "intra-round-offset": 43, "last-valid": 21309784,
             "payment-transaction": {"amount": 100000, "close-amount": 0,
                                     "receiver": "G3H5USFI3OJ25IEVM6GED5EBMUJDXMZPYMJ44BSSJHJTUQKOAAVSA3N43U"},
             "receiver-rewards": 0, "round-time": 1653888146,
             "sender": "JDQ7EW3VY2ZHK4DKUHMNP35XLFPRJBND6M7SZ7W5RCFDNYAA47OC5IS62I", "sender-rewards": 0, "signature": {
                "sig": "xXxTQO3cXEHA07LrHrs6qRZJnI/kKv0ldO5csrbwMn+upi35KPbQ7B28rqIVS6gMpoI3pws1G1ONHWLMihRZAA=="},
             "tx-type": "pay"}]}
        dummy_block_head_resp = {"current-round": 21308825, "next-token": "lyVFAQAAAAAcAAAA", "transactions": [
            {"close-rewards": 0, "closing-amount": 0, "confirmed-round": 21308823, "fee": 1000, "first-valid": 21308821,
             "genesis-hash": "wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=", "genesis-id": "mainnet-v1.0",
             "id": "NWTZDWUG4OAYEDFVCFHTALOO5Q7XZO4PFKVNO533EUZDQFS4QIHQ", "intra-round-offset": 28,
             "last-valid": 21309821, "payment-transaction": {"amount": 403000, "close-amount": 0,
                                                             "receiver": "VBZEOQ3VDD73BBK3KLPLI2QPNQN55FFNB4IM3UFNUJRZBKHXOLHIMX55Z4"},
             "receiver-rewards": 0, "round-time": 1653888305,
             "sender": "RDKDV7CVOXLHO2OXBJCSLFDNJBTENDVT3LMFRYTZS7EKIAMAXZKBL42KHA", "sender-rewards": 0, "signature": {
                "sig": "4A6IoJ8drs3kWP1eKXkQd0fjJH2IYBxOX7atiNKk//VJCmNLoqx0mNA7AH78OZYOibmEgDuWszLaiYnLDTvBAQ=="},
             "tx-type": "pay"}]}

        expected_input_addresses = {'JDQ7EW3VY2ZHK4DKUHMNP35XLFPRJBND6M7SZ7W5RCFDNYAA47OC5IS62I'}
        expected_output_addresses = {'M2LCDSDNVYUPN2BBCKHBTCKREV7J4DGJSLZDJLYINGKIQ4EVOO5HZ2ZH54'}

        chosen_address_for_tx_info = 'JDQ7EW3VY2ZHK4DKUHMNP35XLFPRJBND6M7SZ7W5RCFDNYAA47OC5IS62I'
        expected_tx_info_for_chosen_address = {
            103: [{'tx_hash': 'UYBO35UI4MUJGPFG6H2ACJXTABQIYRXF3YF7SKL2S2J76WPYVRAA', 'value': Decimal('1')}]}

        api_name = 'algo_rand_labs'
        api = APIS_CLASSES[api_name].get_api()
        APIS_CONF['ALGO']['get_blocks_addresses'] = api_name
        api.request = Mock()
        api.request.side_effect = [dummy_block_head_resp, dummy_block_resp]

        settings.USE_TESTNET_BLOCKCHAINS = False
        tx_address, tx_info, _ = BlockchainExplorer.get_latest_block_addresses('ALGO', include_inputs=True,
                                                                               include_info=True)

        self.assertEqual(tx_address['input_addresses'], expected_input_addresses)
        self.assertEqual(tx_address['output_addresses'], expected_output_addresses)
        self.assertEqual(tx_info['outgoing_txs'][chosen_address_for_tx_info], expected_tx_info_for_chosen_address)

        api_name = 'algo_pure_stake'
        api = APIS_CLASSES[api_name].get_api()
        APIS_CONF['ALGO']['get_blocks_addresses'] = api_name
        api.request = Mock()
        api.request.side_effect = [dummy_block_head_resp, dummy_block_resp]

        cache.delete('latest_block_height_processed_algo')
        tx_address, tx_info, _ = BlockchainExplorer.get_latest_block_addresses('ALGO', include_inputs=True,
                                                                               include_info=True)

        self.assertEqual(tx_address['input_addresses'], expected_input_addresses)
        self.assertEqual(tx_address['output_addresses'], expected_output_addresses)
        self.assertEqual(tx_info['outgoing_txs'][chosen_address_for_tx_info], expected_tx_info_for_chosen_address)

        api_name = 'algo_node'
        api = APIS_CLASSES[api_name].get_api()
        APIS_CONF['ALGO']['get_blocks_addresses'] = api_name
        api.request = Mock()
        api.request.side_effect = [dummy_block_head_resp, dummy_block_resp]

        cache.delete('latest_block_height_processed_algo')
        tx_address, tx_info, _ = BlockchainExplorer.get_latest_block_addresses('ALGO', include_inputs=True,
                                                                               include_info=True)

        self.assertEqual(tx_address['input_addresses'], expected_input_addresses)
        self.assertEqual(tx_address['output_addresses'], expected_output_addresses)
        self.assertEqual(tx_info['outgoing_txs'][chosen_address_for_tx_info], expected_tx_info_for_chosen_address)

        api_name = 'algo_bloq_cloud'
        api = APIS_CLASSES[api_name].get_api()
        APIS_CONF['ALGO']['get_blocks_addresses'] = api_name
        api.request = Mock()
        api.request.side_effect = [dummy_block_head_resp, dummy_block_resp]

        cache.delete('latest_block_height_processed_algo')
        tx_address, tx_info, _ = BlockchainExplorer.get_latest_block_addresses('ALGO', include_inputs=True,
                                                                               include_info=True)

        self.assertEqual(tx_address['input_addresses'], expected_input_addresses)
        self.assertEqual(tx_address['output_addresses'], expected_output_addresses)
        self.assertEqual(tx_info['outgoing_txs'][chosen_address_for_tx_info], expected_tx_info_for_chosen_address)


