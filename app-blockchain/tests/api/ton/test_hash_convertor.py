import unittest
import base64
from exchange.blockchain.api.ton.utils import TonHashConvertor


class TestTonHashConvertor(unittest.TestCase):

    def test_convert_to_base64(self):
        input_hash = '5b55b7ce0ac4674ba233f0c7202d7a2b66f84c7be627546352cc8f29bf96202f'
        expected_output = 'W1W3zgrEZ0uiM/DHIC16K2b4THvmJ1RjUsyPKb+WIC8='
        result = TonHashConvertor.ton_convert_hash(input_hash, 'base64')
        self.assertEqual(result, expected_output)

        input_hash = 'df5e9b1150a73c49270b6707951371c5262058f59c9e7027223d6125816ebbab'
        expected_output = '316bEVCnPEknC2cHlRNxxSYgWPWcnnAnIj1hJYFuu6s='
        result = TonHashConvertor.ton_convert_hash(input_hash, 'base64')
        self.assertEqual(result, expected_output)

        input_hash = '316bEVCnPEknC2cHlRNxxSYgWPWcnnAnIj1hJYFuu6s='
        expected_output = '316bEVCnPEknC2cHlRNxxSYgWPWcnnAnIj1hJYFuu6s='
        result = TonHashConvertor.ton_convert_hash(input_hash, 'base64')
        self.assertEqual(result, expected_output)

    def test_convert_to_hex(self):
        input_hash = 'W1W3zgrEZ0uiM/DHIC16K2b4THvmJ1RjUsyPKb+WIC8='
        expected_output = '5b55b7ce0ac4674ba233f0c7202d7a2b66f84c7be627546352cc8f29bf96202f'
        result = TonHashConvertor.ton_convert_hash(input_hash, 'hex')
        self.assertEqual(result, expected_output)

        input_hash = '316bEVCnPEknC2cHlRNxxSYgWPWcnnAnIj1hJYFuu6s='
        expected_output = 'df5e9b1150a73c49270b6707951371c5262058f59c9e7027223d6125816ebbab'
        result = TonHashConvertor.ton_convert_hash(input_hash, 'hex')
        self.assertEqual(result, expected_output)

        input_hash = 'df5e9b1150a73c49270b6707951371c5262058f59c9e7027223d6125816ebbab'
        expected_output = 'df5e9b1150a73c49270b6707951371c5262058f59c9e7027223d6125816ebbab'
        result = TonHashConvertor.ton_convert_hash(input_hash, 'hex')
        self.assertEqual(result, expected_output)

        input_hash = base64.urlsafe_b64encode(b'test').decode('utf-8')  # Base64 URL-safe input
        expected_output = '74657374'
        result = TonHashConvertor.ton_convert_hash(input_hash, 'hex')
        self.assertEqual(result, expected_output)

