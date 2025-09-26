from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5

from .signer import Signer
from .verifier import Verifier


class RSASigner(Signer):
    def __init__(self, private_key_str) -> None:
        private_key = RSA.import_key(private_key_str)
        self.signer = PKCS1_v1_5.new(private_key)


class RSAVerifier(Verifier):
    def __init__(self, public_key_str) -> None:
        public_key = RSA.import_key(public_key_str)
        self.verifier = PKCS1_v1_5.new(public_key)
