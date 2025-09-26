from datetime import datetime
from decimal import Decimal
from unittest import TestCase
from unittest.mock import Mock

from exchange.base.models import Currencies
from exchange.blockchain.api.near.near_indexer import NearIndexerAPI


class TestNearIndexer(TestCase):
    near_indexer = NearIndexerAPI()
    near_indexer.request = Mock()

    def test_get_latestblock(self):
        mocked_response = [
            {'block_height': 72407825},
            [
                {'from_address': 'eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294', 'to_address': 'e9b2fd9f3a6280ab37f6ce6909f4487aa86e76be3627c83583c0c69a11dd0fe1', 'tx_hash': 'EYf7MFDneobGfVWXwjJGbc7gSJWsafUbPxfap5BVBVx', 'value': '0.999000000000000000000000'},
                {'from_address': 'sweat_welcome.near', 'to_address': 'ff9a4f8786622c52def096128f1622c990254fdb3f036cc62982af82159d7dab', 'tx_hash': 'Fk1NfiSU6VFBhMiNKhhdkFoBo3GsyeUHWd5pQ17AUAF9', 'value': '0.050000000000000000000000'},
                {'from_address': 'sweat_welcome.near', 'to_address': '8cd58b2a8784129021715646759cc57f498910a7fec47820e635bb7cbd9fb43e', 'tx_hash': 'Epm7uAMAFMj2Lapic7ExdExXS3PX2wSdXXoFbwGVL9Gd', 'value': '0.050000000000000000000000'}
                ]
        ]
        self.near_indexer.request.side_effect = mocked_response
        transactions_addresses, transactions_info, _ = self.near_indexer.get_latest_block(after_block_number=71902390,
                                                                                       to_block_number=71902392,
                                                                                       include_info=True,
                                                                                       include_inputs=True)
        expected_transactions_addresses = {'input_addresses': {'eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294'}, 'output_addresses': {'e9b2fd9f3a6280ab37f6ce6909f4487aa86e76be3627c83583c0c69a11dd0fe1'}}
        expected_transactions_info = {'outgoing_txs': {'eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294': {Currencies.near: [{'tx_hash': 'EYf7MFDneobGfVWXwjJGbc7gSJWsafUbPxfap5BVBVx', 'value': Decimal('0.999000000000000000000000')}]}}, 'incoming_txs': {'e9b2fd9f3a6280ab37f6ce6909f4487aa86e76be3627c83583c0c69a11dd0fe1': {Currencies.near: [{'tx_hash': 'EYf7MFDneobGfVWXwjJGbc7gSJWsafUbPxfap5BVBVx', 'value': Decimal('0.999000000000000000000000')}]}}}
        assert transactions_info == expected_transactions_info
        assert transactions_addresses == expected_transactions_addresses

    def test_get_txs(self):
        mocked_responses = [
            {'block_height': 74397224},
            {'txs': [{'block_height': 74332956, 'block_time': '1663422048431590034',
                      'receiver': '2f8acf54f09c5f4956ccd937aa56f7603bcb5b80416330231612661e719b1c00',
                      'sender': '5623c9fbb2f1b6b12ba775031dbf52fab977a8b466b64f153f3743069e13bb34',
                      'tx_hash': 'C8ak7XND1nNXaTF289jNxd82D283pibHLXNVRMJasMJC',
                      'value': '8.835643520000000000000000'}]}
        ]
        self.near_indexer.request.side_effect = mocked_responses
        address = '2f8acf54f09c5f4956ccd937aa56f7603bcb5b80416330231612661e719b1c00'
        txs = self.near_indexer.get_txs(address)
        expected_result = [{Currencies.near: {'address': '2f8acf54f09c5f4956ccd937aa56f7603bcb5b80416330231612661e719b1c00', 'hash': 'C8ak7XND1nNXaTF289jNxd82D283pibHLXNVRMJasMJC', 'from_address': '5623c9fbb2f1b6b12ba775031dbf52fab977a8b466b64f153f3743069e13bb34', 'to_address': '2f8acf54f09c5f4956ccd937aa56f7603bcb5b80416330231612661e719b1c00', 'amount': Decimal('8.835643520000000000000000'), 'block': 74332956, 'date': datetime(2022, 9, 17, 13, 40, 48, 431590), 'confirmations': 64268, 'direction': 'incoming', 'raw': ''}}]
        assert txs == expected_result

    def test_get_txs_incoming(self):
        mocked_responses = [
            {'block_height': 74607508},
            {'txs': [{'block_height': 74602727, 'block_time': '1663768639062182257', 'receiver': '601483a1b22699b636f1df800b9b709466eba4e1d5ce7c2e1e20317af8bbd1f3', 'sender': '9b56361965b58267e6de7cbbfcde9952e13e907fb4512a0e659785b0774df96e', 'status': 'SUCCESS_VALUE', 'tx_hash': '25Mb2ZYG4a2NigZympbFvHX2tNM6XkuRXJZTXX6Ti5Pe', 'value': '140.989915088987500000000000'}, {'block_height': 74601352, 'block_time': '1663766913471184261', 'receiver': '601483a1b22699b636f1df800b9b709466eba4e1d5ce7c2e1e20317af8bbd1f3', 'sender': 'cf8deb4e5943d2e05c8f2611de99e46d1663f68d831eeee68b4944444a2c035d', 'status': 'SUCCESS_VALUE', 'tx_hash': 'tdFjG1FvVs4Ar1cqABhA1A8GJ3AmpUoCZHHnGwSx7xA', 'value': '180.259745266962500000000000'}, {'block_height': 74599963, 'block_time': '1663765117086669128', 'receiver': '601483a1b22699b636f1df800b9b709466eba4e1d5ce7c2e1e20317af8bbd1f3', 'sender': '401f5929ddcf6ff631e058b1b1bea2548bb852c63397c71184a4801053c794e4', 'status': 'SUCCESS_VALUE', 'tx_hash': '4pyCKDDZdhoidQ7hmucR9huK83146ZP1izbr9cppCYyK', 'value': '199.999915088987500000000000'}]}
        ]
        self.near_indexer.request.side_effect = mocked_responses
        address = '601483a1b22699b636f1df800b9b709466eba4e1d5ce7c2e1e20317af8bbd1f3'
        txs = self.near_indexer.get_txs(address, tx_direction_filter='incoming')
        expected_result = [{Currencies.near: {'address': '601483a1b22699b636f1df800b9b709466eba4e1d5ce7c2e1e20317af8bbd1f3', 'hash': '25Mb2ZYG4a2NigZympbFvHX2tNM6XkuRXJZTXX6Ti5Pe', 'from_address': '9b56361965b58267e6de7cbbfcde9952e13e907fb4512a0e659785b0774df96e', 'to_address': '601483a1b22699b636f1df800b9b709466eba4e1d5ce7c2e1e20317af8bbd1f3', 'amount': Decimal('140.989915088987500000000000'), 'block': 74602727, 'date': datetime(2022, 9, 21, 13, 57, 19, 62182), 'confirmations': 4781, 'direction': 'incoming', 'raw': ''}}, {Currencies.near: {'address': '601483a1b22699b636f1df800b9b709466eba4e1d5ce7c2e1e20317af8bbd1f3', 'hash': 'tdFjG1FvVs4Ar1cqABhA1A8GJ3AmpUoCZHHnGwSx7xA', 'from_address': 'cf8deb4e5943d2e05c8f2611de99e46d1663f68d831eeee68b4944444a2c035d', 'to_address': '601483a1b22699b636f1df800b9b709466eba4e1d5ce7c2e1e20317af8bbd1f3', 'amount': Decimal('180.259745266962500000000000'), 'block': 74601352, 'date': datetime(2022, 9, 21, 13, 28, 33, 471184), 'confirmations': 6156, 'direction': 'incoming', 'raw': ''}}, {Currencies.near: {'address': '601483a1b22699b636f1df800b9b709466eba4e1d5ce7c2e1e20317af8bbd1f3', 'hash': '4pyCKDDZdhoidQ7hmucR9huK83146ZP1izbr9cppCYyK', 'from_address': '401f5929ddcf6ff631e058b1b1bea2548bb852c63397c71184a4801053c794e4', 'to_address': '601483a1b22699b636f1df800b9b709466eba4e1d5ce7c2e1e20317af8bbd1f3', 'amount': Decimal('199.999915088987500000000000'), 'block': 74599963, 'date': datetime(2022, 9, 21, 12, 58, 37, 86669), 'confirmations': 7545, 'direction': 'incoming', 'raw': ''}}]
        assert txs == expected_result

    def test_get_txs_outgoing(self):
        mocked_responses = [
            {'block_height': 74607698},
            {'txs': [{'block_height': 74606725, 'block_time': '1663773805815395626', 'receiver': 'e0e3d9522b94391afeb8ba9848bb546df5a97c672d0e0ce417488f686244ef48', 'sender': '601483a1b22699b636f1df800b9b709466eba4e1d5ce7c2e1e20317af8bbd1f3', 'status': 'SUCCESS_VALUE', 'tx_hash': 'E1ofP2frRdeZWFJFa6rHSxMjWSKRq84vFG8gMKcLEYx7', 'value': '5999.990000000000000000000000'}, {'block_height': 74606719, 'block_time': '1663773797807521926', 'receiver': 'simpleguy.near', 'sender': '601483a1b22699b636f1df800b9b709466eba4e1d5ce7c2e1e20317af8bbd1f3', 'status': 'SUCCESS_VALUE', 'tx_hash': 'BnGHbCx5aZ2MTr42tpjx5tNmTAbzN2bVGcMrvBm64hhS', 'value': '262.848796000000000000000000'}, {'block_height': 74606711, 'block_time': '1663773786369947878', 'receiver': 'grandalex.near', 'sender': '601483a1b22699b636f1df800b9b709466eba4e1d5ce7c2e1e20317af8bbd1f3', 'status': 'SUCCESS_VALUE', 'tx_hash': 'xR324Co1RgofSF8wTLyvrBvdunxwW3Vrg3FA5pVbDfg', 'value': '175.257770000000000000000000'}]}
        ]
        address = '601483a1b22699b636f1df800b9b709466eba4e1d5ce7c2e1e20317af8bbd1f3'
        self.near_indexer.request.side_effect = mocked_responses
        txs = self.near_indexer.get_txs(address, tx_direction_filter='outgoing')
        expected_result = [{Currencies.near: {'address': '601483a1b22699b636f1df800b9b709466eba4e1d5ce7c2e1e20317af8bbd1f3', 'hash': 'E1ofP2frRdeZWFJFa6rHSxMjWSKRq84vFG8gMKcLEYx7', 'from_address': '601483a1b22699b636f1df800b9b709466eba4e1d5ce7c2e1e20317af8bbd1f3', 'to_address': 'e0e3d9522b94391afeb8ba9848bb546df5a97c672d0e0ce417488f686244ef48', 'amount': Decimal('-5999.990000000000000000000000'), 'block': 74606725, 'date': datetime(2022, 9, 21, 15, 23, 25, 815396), 'confirmations': 973, 'direction': 'outgoing', 'raw': ''}}, {Currencies.near: {'address': '601483a1b22699b636f1df800b9b709466eba4e1d5ce7c2e1e20317af8bbd1f3', 'hash': 'BnGHbCx5aZ2MTr42tpjx5tNmTAbzN2bVGcMrvBm64hhS', 'from_address': '601483a1b22699b636f1df800b9b709466eba4e1d5ce7c2e1e20317af8bbd1f3', 'to_address': 'simpleguy.near', 'amount': Decimal('-262.848796000000000000000000'), 'block': 74606719, 'date': datetime(2022, 9, 21, 15, 23, 17, 807522), 'confirmations': 979, 'direction': 'outgoing', 'raw': ''}}, {Currencies.near: {'address': '601483a1b22699b636f1df800b9b709466eba4e1d5ce7c2e1e20317af8bbd1f3', 'hash': 'xR324Co1RgofSF8wTLyvrBvdunxwW3Vrg3FA5pVbDfg', 'from_address': '601483a1b22699b636f1df800b9b709466eba4e1d5ce7c2e1e20317af8bbd1f3', 'to_address': 'grandalex.near', 'amount': Decimal('-175.257770000000000000000000'), 'block': 74606711, 'date': datetime(2022, 9, 21, 15, 23, 6, 369948), 'confirmations': 987, 'direction': 'outgoing', 'raw': ''}}]
        assert txs == expected_result
