import time

from django.test import TestCase

from exchange.apikey.cryptography.eddsa import EDDSA


class TestEDDSA:
    def setup_method(self):
        self.private_key_b64, self.public_key_b64 = EDDSA.generate_api_key_pair()
        self.message = f'{time.time_ns()} GET /api/v5/account/balance?ccy=BTC'
        self.signature_b64 = EDDSA.sign(self.private_key_b64, self.message)

        self.wrong_private_key_b64, self.wrong_public_key_b64 = EDDSA.generate_api_key_pair()
        self.wrong_signature_b64 = EDDSA.sign(self.wrong_private_key_b64, self.message)

    def test_valid_signature(self):
        assert EDDSA.verify_signature(self.public_key_b64, self.message, self.signature_b64)

    def test_wrong_message(self):
        tampered_message = self.message + 'A'
        assert not EDDSA.verify_signature(self.public_key_b64, tampered_message, self.signature_b64)

    def test_wrong_signature(self):
        tampered_signature = 'A' + self.signature_b64
        assert not EDDSA.verify_signature(self.public_key_b64, self.message, tampered_signature)

    def test_wrong_public_key(self):
        assert not EDDSA.verify_signature(self.wrong_public_key_b64, self.message, self.signature_b64)

    def test_wrong_private_key(self):
        assert not EDDSA.verify_signature(self.public_key_b64, self.message, self.wrong_signature_b64)
