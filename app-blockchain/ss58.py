import warnings
from typing import Optional

import base58
from hashlib import blake2b


def ss58_decode(address: str, valid_ss58_format: Optional[int] = None, valid_address_type=None) -> str:

    # Check if address is already decoded
    if address.startswith('0x'):
        return address

    if valid_address_type is not None:
        warnings.warn("Keyword 'valid_address_type' will be replaced by 'valid_ss58_format'", DeprecationWarning)
        valid_ss58_format = valid_address_type

    checksum_prefix = b'SS58PRE'

    address_decoded = base58.b58decode(address)

    if address_decoded[0] & 0b0100_0000:
        ss58_format_length = 2
        ss58_format = ((address_decoded[0] & 0b0011_1111) << 2) | (address_decoded[1] >> 6) | \
                      ((address_decoded[1] & 0b0011_1111) << 8)
    else:
        ss58_format_length = 1
        ss58_format = address_decoded[0]

    if ss58_format in [46, 47]:
        raise ValueError(f"{ss58_format} is a reserved SS58 format")

    if valid_ss58_format is not None and ss58_format != valid_ss58_format:
        raise ValueError("Invalid SS58 format")

    # Determine checksum length according to length of address string
    if len(address_decoded) in [3, 4, 6, 10]:
        checksum_length = 1
    elif len(address_decoded) in [5, 7, 11, 34 + ss58_format_length, 35 + ss58_format_length]:
        checksum_length = 2
    elif len(address_decoded) in [8, 12]:
        checksum_length = 3
    elif len(address_decoded) in [9, 13]:
        checksum_length = 4
    elif len(address_decoded) in [14]:
        checksum_length = 5
    elif len(address_decoded) in [15]:
        checksum_length = 6
    elif len(address_decoded) in [16]:
        checksum_length = 7
    elif len(address_decoded) in [17]:
        checksum_length = 8
    else:
        raise ValueError("Invalid address length")

    checksum = blake2b(checksum_prefix + address_decoded[0:-checksum_length]).digest()

    if checksum[0:checksum_length] != address_decoded[-checksum_length:]:
        raise ValueError("Invalid checksum")

    return address_decoded[ss58_format_length:len(address_decoded)-checksum_length].hex()


def ss58_encode(address: str, ss58_format: int = 42, address_type=None) -> str:

    checksum_prefix = b'SS58PRE'

    if address_type is not None:
        warnings.warn("Keyword 'address_type' will be replaced by 'ss58_format'", DeprecationWarning)
        ss58_format = address_type

    if ss58_format < 0 or ss58_format > 16383 or ss58_format in [46, 47]:
        raise ValueError("Invalid value for ss58_format")

    if type(address) is bytes or type(address) is bytearray:
        address_bytes = address
    else:
        address_bytes = bytes.fromhex(address.replace('0x', ''))

    if len(address_bytes) in [32, 33]:
        # Checksum size is 2 bytes for public key
        checksum_length = 2
    elif len(address_bytes) in [1, 2, 4, 8]:
        # Checksum size is 1 byte for account index
        checksum_length = 1
    else:
        raise ValueError("Invalid length for address")

    if ss58_format < 64:
        ss58_format_bytes = bytes([ss58_format])
    else:
        ss58_format_bytes = bytes([
            ((ss58_format & 0b0000_0000_1111_1100) >> 2) | 0b0100_0000,
            (ss58_format >> 8) | ((ss58_format & 0b0000_0000_0000_0011) << 6)
        ])

    input_bytes = ss58_format_bytes + address_bytes
    checksum = blake2b(checksum_prefix + input_bytes).digest()

    return base58.b58encode(input_bytes + checksum[:checksum_length]).decode()


def is_valid_ss58_address(value: str, valid_ss58_format: Optional[int] = None) -> bool:

    # Return False in case a public key is provided
    if value.startswith('0x'):
        return False

    try:
        ss58_decode(value, valid_ss58_format=valid_ss58_format)
    except ValueError:
        return False

    return True
