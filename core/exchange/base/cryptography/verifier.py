import base64
from abc import ABC, abstractmethod
from typing import Protocol

from Crypto.Hash import SHA256


class VerifierProtocol(Protocol):
    def verify(self, msg: bytes, signature: bytes) -> bool:
        ...


class Verifier(ABC):
    """
    Abstract base class for message verification.

    Subclasses of this class are used for verifying the authenticity and integrity of messages
    using cryptographic signatures.

    Attributes:
        verifier: The verifier object that performs the cryptographic signature verification.
        hasher: The default hashing algorithm (SHA-256) used for message hashing.

    Methods:
        __init__: Abstract method to set the `verifier` property in child classes.
        verify: Verify a message against its signature.
        hash_msg: Hash a message using the specified or default hashing algorithm.
        _verify: Perform the actual cryptographic verification of a hashed message and signature.

    Example usage:
        ```python
        # Create a custom verifier by subclassing Verifier and implementing __init__.
        class RSAVerifier(Verifier):
            def __init__(self, public_key_str) -> None:
                public_key = RSA.import_key(public_key_str)
                self.verifier = PKCS1_v1_5.new(public_key)
        ```

    Note:
        - Ensure that subclasses of `Verifier` implement the `__init__` method to set the `verifier` property.
        - Subclasses may use different cryptographic verification schemes based on their requirements.
    """

    verifier: VerifierProtocol
    hasher = SHA256

    @abstractmethod
    def __init__(self, *args, **kwargs) -> None:
        "Set self.verifier in child classes"
        raise NotImplementedError()

    def verify(self, msg: str, signature: str) -> bool:
        hash_msg = self.hash_msg(msg)
        decoded_signature = base64.b64decode(signature)
        return self._verify(hash_msg, decoded_signature)

    def hash_msg(self, msg: str):
        return self.hasher.new(msg.encode('utf-8'))

    def _verify(self, hash_msg: bytes, signature: bytes) -> bool:
        return self.verifier.verify(hash_msg, signature)
