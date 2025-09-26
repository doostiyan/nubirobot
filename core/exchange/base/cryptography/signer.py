import base64
from abc import ABC, abstractmethod
from typing import Protocol

from Crypto.Hash import SHA256


class SignerProtocol(Protocol):
    def sign(self, value: bytes) -> bytes:
        ...


class Signer(ABC):
    """Abstract base class for cryptographic signers.

    Subclasses of this class are used for signing messages with cryptographic keys.
    Each subclass must implement the `__init__` method to set the `signer` property,
    which is a cryptographic signer object.

    Attributes:
        signer: The cryptographic signer object used for signing messages.
        hasher: The default hashing algorithm (SHA-256) for message hashing.

    Methods:
        __init__: Abstract method to set the `signer` property in child classes.
        sign: Signs a message after hashing it and returns the base64-encoded signature.
        hash_msg: Hashes a message using the SHA-256 algorithm and returns the hash value.
        sign_value: Signs a hash value and returns the base64-encoded signature.

    Example usage:
        ```python
        class RSASigner(Signer):
            def __init__(self, private_key_str) -> None:
                private_key = RSA.import_key(private_key_str)
                self.signer = pkcs1_15.new(private_key)
        ```

    Note:
        - Ensure that subclasses of `Signer` implement the `__init__` method to set the `signer` property.
    """

    signer: SignerProtocol
    hasher = SHA256

    @abstractmethod
    def __init__(self, *args, **kwargs) -> None:
        "Set self.signer in child classes"
        raise NotImplementedError()

    def sign(self, msg: str) -> str:
        hash_value = self.hash_msg(msg)
        return self.sign_value(hash_value)

    def hash_msg(self, msg: str):
        return self.hasher.new(msg.encode('utf-8'))

    def sign_value(self, value: bytes) -> str:
        signature = self.signer.sign(value)
        return base64.encodebytes(signature).decode()
