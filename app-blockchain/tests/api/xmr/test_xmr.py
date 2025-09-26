import datetime
from decimal import Decimal
from unittest import TestCase
from unittest.mock import Mock

import pytz
from django.core.cache import cache

from exchange.base.connections import MoneroExplorerClient
from exchange.base.models import Currencies
from exchange.blockchain.api.general.dtos import TransferTx
from exchange.blockchain.api.xmr.monero_new import MoneroAPI
from exchange.blockchain.api.xmr.xmr_explorer_interface import XmrExplorerInterface


class TestMoneroAPIFromExplorer(TestCase):
    api = MoneroAPI
    client = MoneroExplorerClient.get_client()
    currency = Currencies.xmr
    hash_of_transactions = ['105aacf041f6e94c1cc922015bec4928982ee62aa3fb70b6645f8d17dd98dc00']
    addresses_of_accounts = [
        '854Ppy4p1jdiL3HF54ULL69VEt1bpY8rt6Ss8c5AQZZ5BQ4ffN5neuihbkvF9B9RtuTqJTPPznJtC6hjg35WShwaUyja1hm']

    def test_get_tx_details(self):
        XmrExplorerInterface.tx_details_apis[0] = self.api
        tx_details_mock_responses = [
            {
                'transfers': [{
                    'amount': 100000000000,
                    'confirmation': 576,
                    'destination': '854Ppy4p1jdiL3HF54ULL69VEt1bpY8rt6Ss8c5AQZZ5BQ4ffN5neuihbkvF9B9RtuTqJTPPznJtC6hjg35WShwaUyja1hm',
                    'fee': 30700000,
                    'height': 3233116,
                    'status': True,
                    'timestamp': 1725812661,
                    'tx_hash': '105aacf041f6e94c1cc922015bec4928982ee62aa3fb70b6645f8d17dd98dc00'
                }]
            }
        ]

        self.client.request = Mock(side_effect=tx_details_mock_responses)
        txs_details = []

        for tx_hash in self.hash_of_transactions:
            api_response = self.api.get_tx_details(tx_hash)
            parsed_response = self.api.parser.parse_tx_details_response(api_response, None)
            txs_details.append(parsed_response)

        expected_expected_txs_details = [[
            TransferTx(
                tx_hash='105aacf041f6e94c1cc922015bec4928982ee62aa3fb70b6645f8d17dd98dc00',
                success=True,
                from_address='',
                to_address='854Ppy4p1jdiL3HF54ULL69VEt1bpY8rt6Ss8c5AQZZ5BQ4ffN5neuihbkvF9B9RtuTqJTPPznJtC6hjg35WShwaUyja1hm',
                value=Decimal('0.100000000000'),
                symbol='XMR',
                confirmations=576,
                block_height=3233116,
                block_hash=None,
                date=datetime.datetime(2024, 9, 8, 16, 24, 21, tzinfo=pytz.UTC),
                memo=None, tx_fee=Decimal('0.000030700000'),
                token=None,
                index=None
            )
        ]]
        for expected_tx_details, tx_details in zip(expected_expected_txs_details, txs_details):
            assert expected_tx_details == tx_details

    def test_get_txs(self):
        address_txs_mock_responses = [{'transfers': [{'amount': '0.100000000000',
                                                      'confirmation': 574,
                                                      'destination': '854Ppy4p1jdiL3HF54ULL69VEt1bpY8rt6Ss8c5AQZZ5BQ4ffN5neuihbkvF9B9RtuTqJTPPznJtC6hjg35WShwaUyja1hm',
                                                      'fee': '0.000030700000',
                                                      'height': 3233116,
                                                      'timestamp': 1725812661.0,
                                                      'tx_hash': '105aacf041f6e94c1cc922015bec4928982ee62aa3fb70b6645f8d17dd98dc00'}]}]

        XmrExplorerInterface.address_txs_apis[0] = self.api
        self.client.request = Mock(side_effect=address_txs_mock_responses)

        addresses_txs = []
        for address in self.addresses_of_accounts:
            api_response = self.api.get_address_txs(address)
            parsed_response = self.api.parser.parse_address_txs_response(address, api_response, None)
            addresses_txs.append(parsed_response)
        expected_addresses_txs = [[TransferTx(
            tx_hash='105aacf041f6e94c1cc922015bec4928982ee62aa3fb70b6645f8d17dd98dc00', success=True, from_address='',
            to_address='854Ppy4p1jdiL3HF54ULL69VEt1bpY8rt6Ss8c5AQZZ5BQ4ffN5neuihbkvF9B9RtuTqJTPPznJtC6hjg35WShwaUyja1hm',
            value=Decimal('0.100000000000'), symbol='XMR', confirmations=574, block_height=3233116, block_hash=None,
            date=datetime.datetime(2024, 9, 8, 16, 24, 21, tzinfo=pytz.UTC), memo=None,
            tx_fee=Decimal('0.000030700000'), token=None, index=None)]]
        for expected_address_txs, address_txs in zip(expected_addresses_txs, addresses_txs):
            assert expected_address_txs == address_txs

    def test_get_block_head(self):
        XmrExplorerInterface.block_head_apis[0] = self.api
        block_head_mock_responses = [{'block_head': 3233690}]
        self.client.request = Mock(side_effect=block_head_mock_responses)
        api_response = self.api.get_block_head()
        parsed_response = self.api.parser.parse_block_head_response(api_response)
        expected_block_head = 3233690
        assert parsed_response == expected_block_head

    def test_get_block_txs(self):
        cache.delete('latest_block_height_processed_xmr')
        XmrExplorerInterface.block_txs_apis[0] = self.api

        block_head_mock_responses = [{'block_head': 3233690}]
        self.api.get_block_head = Mock(side_effect=block_head_mock_responses)

        block_txs_mock_responses = [[{'transfers': [{'amount': '0.100000000000',
                                                     'confirmation': 574,
                                                     'destination': '854Ppy4p1jdiL3HF54ULL69VEt1bpY8rt6Ss8c5AQZZ5BQ4ffN5neuihbkvF9B9RtuTqJTPPznJtC6hjg35WShwaUyja1hm',
                                                     'fee': '0.000030700000',
                                                     'height': 3233116,
                                                     'timestamp': 1725812661.0,
                                                     'tx_hash': '105aacf041f6e94c1cc922015bec4928982ee62aa3fb70b6645f8d17dd98dc00'},
                                                    {'amount': '0.022645543761',
                                                     'confirmation': 591,
                                                     'destination': '84P5NM54USL2Yej3JikZVRMa8G2XzUUegTegPzKXDwK3D5JEh7KRZovetjsV4LUz7i8wq4RRgY5KX7YTPd1zsQunBekcoda',
                                                     'fee': '0.000125680000',
                                                     'height': 3233099,
                                                     'timestamp': 1725811875.0,
                                                     'tx_hash': 'bffa7a0a2c0563a7efea5677aa086115ae36f79c31ec3540171e86564d7429a1'},
                                                    {'amount': '0.019763471693',
                                                     'confirmation': 618,
                                                     'destination': '84P5NM54USL2Yej3JikZVRMa8G2XzUUegTegPzKXDwK3D5JEh7KRZovetjsV4LUz7i8wq4RRgY5KX7YTPd1zsQunBekcoda',
                                                     'fee': '0.000135080000',
                                                     'height': 3233072,
                                                     'timestamp': 1725809518.0,
                                                     'tx_hash': 'd5dcef53d8a932b9c9d3d737a0216498271e673c21ace2a5f32213c6cb30f1a8'},
                                                    {'amount': '0.184524339998',
                                                     'confirmation': 627,
                                                     'destination': '82yTexMu4xvizgRQt53LdSTYan6VtxNZWMaseiTL6eCL6bGG8P5TAXz8g1JWXDHLsL2cdbvyaeitYY8AQ8nLW3KK5u3oLkD',
                                                     'fee': '0.000236920000',
                                                     'height': 3233063,
                                                     'timestamp': 1725808676.0,
                                                     'tx_hash': 'c71f8c18eef476b6599ce622a9e54a7377a0d65474d515fb24d9450dfe1a9a3d'},
                                                    {'amount': '0.061350000000',
                                                     'confirmation': 630,
                                                     'destination': '842gRTJ6vHhUX4YDRwzEMiRxh1QB5PUjbFHtZ3PZLgCJjJcJwsG36F7X6ze8rr3Zh4j7dP8We9LMSbaf1tXWwT7bBLnkg6P',
                                                     'fee': '0.000122720000',
                                                     'height': 3233060,
                                                     'timestamp': 1725808163.0,
                                                     'tx_hash': 'f59d4f838ba3ae4612cfab9b2ac768b50a9a846e72a5e4307c01e1605ca01a7b'},
                                                    {'amount': '0.225980580000',
                                                     'confirmation': 664,
                                                     'destination': '887xgFaBjZAPTbbmB3hNhwJ1DyWmWwKAdEhLrZJaRQ2YHmJoA7jCcEEQedBgv2f4r58zUzWUcF1SmbowN9j7uCcKPPCg97e',
                                                     'fee': '0.000030700000',
                                                     'height': 3233026,
                                                     'timestamp': 1725804868.0,
                                                     'tx_hash': 'f130aae7b1fad6d49bc08689b84abfc878f0faf0e0dafabdbd8635331ba014f2'},
                                                    {'amount': '0.006910150288',
                                                     'confirmation': 665,
                                                     'destination': '84P5NM54USL2Yej3JikZVRMa8G2XzUUegTegPzKXDwK3D5JEh7KRZovetjsV4LUz7i8wq4RRgY5KX7YTPd1zsQunBekcoda',
                                                     'fee': '0.000148000000',
                                                     'height': 3233025,
                                                     'timestamp': 1725804789.0,
                                                     'tx_hash': '389870e695b821281508bd4bb14e7900d30bc1007115a76d017e6fe8d58b7ac6'},
                                                    {'amount': '0.018300000000',
                                                     'confirmation': 677,
                                                     'destination': '858TspXaDqbBXC9Sng1fcSFHpqXHeobfGe4iD1RGgYWSDkVrbWaDsHeBGnmjze3pibENZQERPEP23fFWtdAKcHPVR5VwYqW',
                                                     'fee': '0.000209260000',
                                                     'height': 3233013,
                                                     'timestamp': 1725803219.0,
                                                     'tx_hash': 'ba94e244b4de374757c5c9f453508bcd8d7b01c1e57839124a82fcaa6ae6178b'}]}]]

        self.api.get_batch_block_txs = Mock(side_effect=block_txs_mock_responses)
        result = XmrExplorerInterface().get_latest_block(include_inputs=True, include_info=True)
        expected_result = ({'input_addresses': set(), 'output_addresses': {
            '858TspXaDqbBXC9Sng1fcSFHpqXHeobfGe4iD1RGgYWSDkVrbWaDsHeBGnmjze3pibENZQERPEP23fFWtdAKcHPVR5VwYqW',
            '84P5NM54USL2Yej3JikZVRMa8G2XzUUegTegPzKXDwK3D5JEh7KRZovetjsV4LUz7i8wq4RRgY5KX7YTPd1zsQunBekcoda',
            '887xgFaBjZAPTbbmB3hNhwJ1DyWmWwKAdEhLrZJaRQ2YHmJoA7jCcEEQedBgv2f4r58zUzWUcF1SmbowN9j7uCcKPPCg97e',
            '842gRTJ6vHhUX4YDRwzEMiRxh1QB5PUjbFHtZ3PZLgCJjJcJwsG36F7X6ze8rr3Zh4j7dP8We9LMSbaf1tXWwT7bBLnkg6P',
            '854Ppy4p1jdiL3HF54ULL69VEt1bpY8rt6Ss8c5AQZZ5BQ4ffN5neuihbkvF9B9RtuTqJTPPznJtC6hjg35WShwaUyja1hm',
            '82yTexMu4xvizgRQt53LdSTYan6VtxNZWMaseiTL6eCL6bGG8P5TAXz8g1JWXDHLsL2cdbvyaeitYY8AQ8nLW3KK5u3oLkD'}},
                           {'outgoing_txs': {}, 'incoming_txs': {
                               '854Ppy4p1jdiL3HF54ULL69VEt1bpY8rt6Ss8c5AQZZ5BQ4ffN5neuihbkvF9B9RtuTqJTPPznJtC6hjg35WShwaUyja1hm': {
                                   22: [{'tx_hash': '105aacf041f6e94c1cc922015bec4928982ee62aa3fb70b6645f8d17dd98dc00',
                                         'value': Decimal('0.100000000000'), 'contract_address': None, 'block_height': 3233116, 'symbol': 'XMR'}]},
                               '84P5NM54USL2Yej3JikZVRMa8G2XzUUegTegPzKXDwK3D5JEh7KRZovetjsV4LUz7i8wq4RRgY5KX7YTPd1zsQunBekcoda': {
                                   22: [{'tx_hash': 'bffa7a0a2c0563a7efea5677aa086115ae36f79c31ec3540171e86564d7429a1',
                                         'value': Decimal('0.022645543761'), 'contract_address': None, 'block_height': 3233099, 'symbol': 'XMR'},
                                        {'tx_hash': 'd5dcef53d8a932b9c9d3d737a0216498271e673c21ace2a5f32213c6cb30f1a8',
                                         'value': Decimal('0.019763471693'), 'contract_address': None, 'block_height': 3233072, 'symbol': 'XMR'},
                                        {'tx_hash': '389870e695b821281508bd4bb14e7900d30bc1007115a76d017e6fe8d58b7ac6',
                                         'value': Decimal('0.006910150288'), 'contract_address': None, 'block_height': 3233025, 'symbol': 'XMR'}]},
                               '82yTexMu4xvizgRQt53LdSTYan6VtxNZWMaseiTL6eCL6bGG8P5TAXz8g1JWXDHLsL2cdbvyaeitYY8AQ8nLW3KK5u3oLkD': {
                                   22: [{'tx_hash': 'c71f8c18eef476b6599ce622a9e54a7377a0d65474d515fb24d9450dfe1a9a3d',
                                         'value': Decimal('0.184524339998'), 'contract_address': None, 'block_height': 3233063, 'symbol': 'XMR'}]},
                               '842gRTJ6vHhUX4YDRwzEMiRxh1QB5PUjbFHtZ3PZLgCJjJcJwsG36F7X6ze8rr3Zh4j7dP8We9LMSbaf1tXWwT7bBLnkg6P': {
                                   22: [{'tx_hash': 'f59d4f838ba3ae4612cfab9b2ac768b50a9a846e72a5e4307c01e1605ca01a7b',
                                         'value': Decimal('0.061350000000'), 'contract_address': None, 'block_height': 3233060, 'symbol': 'XMR'}]},
                               '887xgFaBjZAPTbbmB3hNhwJ1DyWmWwKAdEhLrZJaRQ2YHmJoA7jCcEEQedBgv2f4r58zUzWUcF1SmbowN9j7uCcKPPCg97e': {
                                   22: [{'tx_hash': 'f130aae7b1fad6d49bc08689b84abfc878f0faf0e0dafabdbd8635331ba014f2',
                                         'value': Decimal('0.225980580000'), 'contract_address': None, 'block_height': 3233026, 'symbol': 'XMR'}]},
                               '858TspXaDqbBXC9Sng1fcSFHpqXHeobfGe4iD1RGgYWSDkVrbWaDsHeBGnmjze3pibENZQERPEP23fFWtdAKcHPVR5VwYqW': {
                                   22: [{'tx_hash': 'ba94e244b4de374757c5c9f453508bcd8d7b01c1e57839124a82fcaa6ae6178b',
                                         'value': Decimal('0.018300000000'), 'contract_address': None, 'block_height': 3233013, 'symbol': 'XMR'}]}}}, 3233685)
        self.assertTupleEqual(result, expected_result)
