import base64
from typing import Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


class EDDSA:
    @classmethod
    def generate_api_key_pair(cls) -> Tuple[str, str]:
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        private_key_b64 = base64.urlsafe_b64encode(private_key.private_bytes_raw()).decode()
        public_key_b64 = base64.urlsafe_b64encode(public_key.public_bytes_raw()).decode()
        return private_key_b64, public_key_b64

    @classmethod
    def verify_signature(cls, public_key_b64: str, message: str, signature_b64: str) -> bool:
        public_key = cls.load_public_key(public_key_b64)
        signature = base64.urlsafe_b64decode(signature_b64)
        message_bytes = message.encode()
        try:
            public_key.verify(signature, message_bytes)
            return True
        except InvalidSignature:
            return False

    @classmethod
    def load_private_key(cls, b64: str) -> Ed25519PrivateKey:
        key_bytes = base64.urlsafe_b64decode((b64))
        return Ed25519PrivateKey.from_private_bytes(key_bytes)

    @classmethod
    def load_public_key(cls, b64: str) -> Ed25519PublicKey:
        key_bytes = base64.urlsafe_b64decode(b64)
        return Ed25519PublicKey.from_public_bytes(key_bytes)

    @classmethod
    def sign(cls, private_key_b64, message: str) -> bytes:
        private_key = cls.load_private_key(private_key_b64)
        signature = private_key.sign(message.encode())
        signature_b64 = base64.urlsafe_b64encode(signature).decode()
        return signature_b64
