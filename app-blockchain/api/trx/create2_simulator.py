from typing import Union

import base58
from Crypto.Hash import keccak

MOTHER_FIXED_HEX_CODE = '6080604052348015600f57600080fd5b50d38015601b57600080fd5b50d28015602757600080fd5b503360005560718061003a6000396000f3fe6080604052348015600f57600080fd5b50d38015601b57600080fd5b50d28015602757600080fd5b5036600080376020604036600080545af45000fea26474726f6e582212204248e2207a391bae55d2c15f8da413121f4af925862744176619ec689036853964736f6c63430008060033' # noqa: E501
INITIAL_CHILD_BYTES = 0x41


def to_base58check_address(raw_addr: Union[str, bytes]) -> str:
    """Convert hex address or base58check address to base58check address(and verify it)."""
    if isinstance(raw_addr, (str,)):
        if raw_addr[0] == 'T' and len(raw_addr) == 34:  # noqa: PLR2004
            try:
                # assert checked
                base58.b58decode_check(raw_addr)
            except ValueError as e:
                raise Exception('bad base58check format') from e
            return raw_addr
        if len(raw_addr) == 42:  # noqa: PLR2004
            if raw_addr.startswith('0x'):  # eth address format
                return base58.b58encode_check(b'\x41' + bytes.fromhex(raw_addr[2:])).decode()
            return base58.b58encode_check(bytes.fromhex(raw_addr)).decode()
        if raw_addr.startswith('0x') and len(raw_addr) == 44:  # noqa: PLR2004
            return base58.b58encode_check(bytes.fromhex(raw_addr[2:])).decode()
    elif isinstance(raw_addr, (bytes, bytearray)):
        if len(raw_addr) == 21 and int(raw_addr[0]) == 0x41:  # noqa: PLR2004
            return base58.b58encode_check(raw_addr).decode()
        if len(raw_addr) == 20:  # eth address format # noqa: PLR2004
            return base58.b58encode_check(b'\x41' + raw_addr).decode()
        return to_base58check_address(raw_addr.decode())
    raise Exception(repr(raw_addr))


def to_hex_address(raw_addr: Union[str, bytes]) -> str:
    addr = to_base58check_address(raw_addr)
    return base58.b58decode_check(addr).hex()


def address_to_bytes(address: str) -> bytes:
    return bytes.fromhex(to_hex_address(address)[2:])


def generate_contract_addresses(mother: str, child_salt: str) -> str:
    mother_bytes = address_to_bytes(mother)
    mother_bytecodes = bytes.fromhex(MOTHER_FIXED_HEX_CODE)
    child_data = (
            INITIAL_CHILD_BYTES.to_bytes(1, 'little') +
            mother_bytes +
            bytes.fromhex(child_salt.rjust(64, '0')) +
            keccak.new(digest_bits=256, data=mother_bytecodes).digest()
    )
    child_addr_bytes = keccak.new(
        digest_bits=256,
        data=child_data
    ).digest()
    return to_base58check_address('41' + child_addr_bytes.hex()[-40:])
