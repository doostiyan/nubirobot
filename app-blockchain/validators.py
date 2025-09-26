import base64
import binascii
import re
import struct
from base64 import b32decode
from binascii import crc32, unhexlify
from hashlib import blake2b, sha256
from typing import Optional, Tuple, Union

import base58
import base58check
import coinaddrvalidator
from cbor import cbor
from Crypto.Hash import SHA512, keccak
from django.conf import settings

from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.models import INTEGER_ONLY_TAG_CURRENCIES, Currencies
from exchange.blockchain import segwit_address
from exchange.blockchain.encodings.crc16 import crc16_x_modem
from exchange.blockchain.models import ETHEREUM_LIKE_NETWORKS, CurrenciesNetworkName
from exchange.blockchain.monero_address_validation import decode
from exchange.blockchain.ss58 import is_valid_ss58_address
from exchange.blockchain.utils import NetworkNotExist

__all__ = [
    'validate_crypto_address',
    'validate_crypto_address_by_network',
    'validate_crypto_address_v2',
    'validate_memo_v2',
    'validate_tag',
]


def big_endian_to_int(value: bytes) -> int:
    return int.from_bytes(value, 'big')


def sha3(seed: Union[bytes, str, int]) -> bytes:
    return keccak.new(digest_bits=256, data=to_string(seed)).digest()


def to_string(value: Union[bytes, str, int]) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return bytes(value, 'utf-8')
    if isinstance(value, int):
        return bytes(str(value), 'utf-8')
    return b''


def validate_omni_address(address: str, currency: str) -> bool:
    """ checking validity omni USDT address """

    if currency != Currencies.usdt:
        return False
    try:
        is_btc_address = validate_btc_address(address, currency)
    except Exception:
        return False
    if is_btc_address and address.startswith(('1', '3')):
        return True
    return False


def validate_sol_address(address: str, _currency: str) -> bool:
    expected_length = 32
    try:
        decoded_address = base58.b58decode(address)
    except ValueError:
        return False
    return len(decoded_address) == expected_length


def validate_xlm_address(address: str, _currency: str) -> bool:
    """ checking validity XLM address """
    bytes_types = (bytes, bytearray)
    if isinstance(address, (str, bytes)):
        try:
            encoded = address.encode('ascii')
        except UnicodeEncodeError:
            return False
    elif isinstance(address, bytes_types):
        encoded = address
    else:
        try:
            encoded = memoryview(address).tobytes()
        except TypeError:
            return False

    try:
        decoded = base64.b32decode(encoded)
        if encoded != base64.b32encode(decoded):
            return False
        payload = decoded[0:-2]
        checksum = decoded[-2:]
        expected_version = binascii.a2b_hex('30')
        if decoded[0:1] != expected_version:
            return False
        expected_checksum = crc16_x_modem(payload)  # This code calculates CRC16-XModem checksum of payload
        expected_checksum = struct.pack('<H', expected_checksum)  # Ensure that the checksum is in LSB order.
        return expected_checksum == checksum
    except (ValueError, TypeError):
        return False


def validate_trx_address(address: str, _currency: str) -> bool:
    trx_address_length = 34
    trx_decoded_length = 25
    trx_first_byte = 0x41

    if len(address) != trx_address_length:
        return False
    decode_address = base58.b58decode(address)
    if len(decode_address) != trx_decoded_length:
        return False
    if decode_address[0] != trx_first_byte:
        return False
    check_sum = sha256(sha256(decode_address[:-4]).digest()).digest()[:4]
    return decode_address[-4:] == check_sum


def validate_bech32_address(hrp: str, address: str, currency: str, ignore_length: bool = False) -> bool:
    _ = currency
    encoding, wit_ver, wit_prog = segwit_address.bech32_decode(address, ignore_long_length=ignore_length)
    return wit_ver is not None and wit_ver == hrp


def convert_eth_address_to_checksum(address: str) -> str:
    address = address.lower().replace('0x', '')
    address_bytes = to_string(address)
    address_hash = keccak.new(digest_bits=256).update(address_bytes).hexdigest()
    new_addr = '0x'
    checksum_threshold = 8

    for i, char in enumerate(address_bytes):
        if int(address_hash[i], 16) >= checksum_threshold:
            new_addr += chr(char).upper()
        else:
            new_addr += chr(char)
    return new_addr


def validate_eth_address(address: str, _currency: str) -> bool:
    eth_address_length: int = 42

    if not address.startswith('0x'):
        return False
    if len(address) != eth_address_length:
        return False
    if re.match(r'[a-z0-9.]{42}', address):
        address = convert_eth_address_to_checksum(address)
    try:
        addr = bytes.fromhex(address[2:])
    except (TypeError, ValueError):
        return False

    result_addr = ''
    v = big_endian_to_int(sha3(addr.hex()))
    for i, c in enumerate(addr.hex()):
        if c in '0123456789':
            result_addr += c
        else:
            result_addr += c.upper() if (v & (2 ** (255 - 4 * i))) else c.lower()
    return address == '0x' + result_addr


def validate_btc_address(address: str, _currency: str, testnet: bool = False) -> bool:
    try:
        btc_bytes = base58.b58decode(address)
    except (TypeError, ValueError):
        btc_bytes = None

    if (btc_bytes is not None and
            btc_bytes[-4:] == sha256(sha256(btc_bytes[:-4]).digest()).digest()[:4]):
        if testnet:
            return address.startswith(('2', 'm', 'n'))
        return address.startswith(('1', '3'))

    hrp = 'bc'
    wit_ver, wit_prog = segwit_address.decode_segwit_address(hrp, address)
    if wit_ver is None and testnet:
        hrp = 'tb'
        wit_ver, wit_prog = segwit_address.decode_segwit_address(hrp, address)
    return wit_ver is not None


def validate_ltc_segwit_address(address: str, _currency: str) -> bool:
    hrp = 'ltc'
    wit_ver, wit_prog = segwit_address.decode_segwit_address(hrp, address)
    if wit_ver is None and not settings.IS_PROD:
        hrp = 'tltc'
        wit_ver, wit_prog = segwit_address.decode_segwit_address(hrp, address)
    return wit_ver is not None


def validate_ada_segwit_address(address: str, _testnet: bool = False) -> bool:
    hrp = 'addr'
    if address is None:
        return False
    encoding, hrpgot, data = segwit_address.ada_bech32_decode(address)
    return hrpgot == hrp


def validate_ada_byron_address(address: str, testnet: bool = False) -> bool:
    try:
        ada_bytes = base58check.b58decode(address)
    except (TypeError, ValueError):
        return False

    if not ada_bytes:
        return False

    try:
        decoded_address = cbor.loads(ada_bytes)
        tagged_address = decoded_address[0]
        expected_checksum = decoded_address[1]
        checksum = crc32(tagged_address.value)
        if checksum == expected_checksum:
            if not testnet:
                return address.startswith('DdzFF')
            return address.startswith('37btjrVyb4K')
    except Exception:
        return False
    return False


def validate_ada_address(address: str, testnet: bool = False) -> bool:
    if address.startswith('addr'):
        return validate_ada_segwit_address(address, testnet)
    return validate_ada_byron_address(address, testnet)


def validate_atom_address(address: str) -> bool:
    return coinaddrvalidator.validate('cosmos', address)


def validate_xmr_address(address: str) -> bool:
    _valid_netbytes = (42, 63, 36, 18, 53, 24)
    _decoded = bytearray(unhexlify(decode(address)))
    checksum = _decoded[-4:]
    if checksum != keccak.new(digest_bits=256, data=_decoded[:-4]).digest()[:4]:
        return False
    return _decoded[0] in _valid_netbytes


def validate_near_address(address: str) -> bool:
    if address.endswith('.near'):  # Account ID format
        pattern = re.compile(r'^[a-z0-9][a-z0-9\-_]{0,57}[a-z0-9]$')
        return bool(pattern.match(address[:-5]))
    # implicit format
    pattern = re.compile('^[a-z0-9]{64}$')
    return bool(pattern.match(address))


def validate_hbar_address(address: str) -> bool:
    checksum = False
    checksum_regex = r'^(0|(?:[1-9]\d*))\.(0|(?:[1-9]\d*))\.(0|(?:[1-9]\d*))(?:-([a-z]{5}))$'
    pattern = re.compile(checksum_regex)
    if pattern.match(address):
        checksum = True
    regex = r'^(0|(?:[1-9]\d*))\.(0|(?:[1-9]\d*))\.(0|(?:[1-9]\d*))(?:-([a-z]{5}))?$'
    pattern = re.compile(regex)
    if not pattern.match(address):
        return False
    if checksum:
        checksum = validate_hbar_checksum(address[:len(address) - 6])
        if checksum != address[len(address) - 5:]:
            return False
    return True


def validate_hbar_checksum(address: str) -> str:
    ans = ''
    ledger_id = '00'
    d, h = [], []
    sd0, sd1, sd, sh, c, cp = 0, 0, 0, 0, 0, 0
    p3 = 26 * 26 * 26
    p5 = 26 * 26 * 26 * 26 * 26
    m = 1_000_003
    w = 31
    ascii_a = ord('a')
    ledger_str = ledger_id + '000000000000'
    if len(ledger_str) % 2 == 1:
        ledger_str = '0' + ledger_str
    for i in range(0, len(ledger_str), 2):
        h.append(int(ledger_str[i:i + 2], 16))
    for char in address:
        d.append(int('10' if char == '.' else char, 10))
    for i, val in enumerate(d):
        sd = (w * sd + val) % p3
        if i % 2 == 0:
            sd0 = (sd0 + val) % 11
        else:
            sd1 = (sd1 + val) % 11
    for val in h:
        sh = (w * sh + val) % p5
    c = ((((len(address) % 5) * 11 + sd0) * 11 + sd1) * p3 + sd + sh) % p5
    cp = (c * m) % p5

    for _ in range(5):
        ans = chr(ascii_a + (int(cp % 26))) + ans
        cp /= 26
    return ans


def get_fil_address_protocol(protocol_letter: str) -> Optional[Tuple[int, str]]:
    if protocol_letter == '0':
        return 0, 'ID'
    if protocol_letter == '1':
        return 1, 'SECP256K1'
    if protocol_letter == '2':
        return 2, 'Actor'
    if protocol_letter == '3':
        return 3, 'BLS'
    return None


def validate_fil_id_address(raw: str) -> bool:
    fix_id_max_length: int = 19
    return len(raw) <= fix_id_max_length and raw.isnumeric()


def get_fil_payload_checksum(raw: str, checksum_hash_length: int) -> Tuple[bytes, bytes]:
    b32_padding = raw + ('=' * (8 - (len(raw) % 8)))
    decoded = b32decode(b32_padding.upper())
    payload = decoded[:len(decoded) - checksum_hash_length]
    expected_checksum = decoded[len(decoded) - checksum_hash_length:]
    return payload, expected_checksum


def validate_fil_address_checksum(
        payload: bytes,
        protocol_number: int,
        checksum_hash_length: int,
        expected_checksum: bytes
) -> bool:
    protocol_number_payload = protocol_number.to_bytes(1, 'big') + payload
    checksum = blake2b(protocol_number_payload, digest_size=checksum_hash_length).digest()
    return checksum == expected_checksum


def validate_fil_address(address: str) -> bool:
    checksum_hash_length = 4
    if not address or not address.startswith('f'):
        return False

    protocol = get_fil_address_protocol(address[1])
    if not protocol:
        return False

    protocol_number, address_protocol = protocol
    raw = address[2:]

    if address_protocol == 'ID':
        return validate_fil_id_address(raw)

    try:
        payload, expected_checksum = get_fil_payload_checksum(raw, checksum_hash_length)
    except Exception:
        return False

    if address_protocol in {'SECP256K1', 'Actor'}:
        payload_hash_length = 20
        if len(payload) != payload_hash_length:
            return False

    return validate_fil_address_checksum(payload, protocol_number, checksum_hash_length, expected_checksum)


def validate_egld_address(address: str) -> bool:
    hrp = 'erd'
    if address is None:
        return False
    encoding, hrpgot, data = segwit_address.ada_bech32_decode(address)
    return hrpgot == hrp


def validate_flow_address(address: str) -> bool:
    pattern = re.compile(r'^0x[a-fA-F0-9]{16}$')
    return bool(pattern.match(address))


def validate_one_address(address: str) -> bool:
    hrp = 'one'
    if address is None:
        return False
    encoding, hrpgot, data = segwit_address.ada_bech32_decode(address)
    return hrpgot == hrp


def validate_apt_address(address: str) -> bool:
    return bool(re.match(r'^(0x)[a-fA-F0-9]{64}', address))


def __correct_padding_algorand(a: str) -> str:
    if len(a) % 8 == 0:
        return a
    return a + '=' * (8 - len(a) % 8)


def __checksum_algorand(data: bytes, check_sum_len_bytes: int) -> bytes:
    chksum = SHA512.new(truncate='256')
    chksum.update(data)
    return chksum.digest()[-check_sum_len_bytes:]


def validate_algo_address(address: str) -> bool:
    address_len = 58
    check_sum_len_bytes = 4

    if not isinstance(address, str):
        return False
    if len(address.strip('=')) != address_len:
        return False

    try:
        decoded = base64.b32decode(__correct_padding_algorand(address))
        addr = decoded[:-check_sum_len_bytes]
        expected_checksum = decoded[-check_sum_len_bytes:]
        chksum = __checksum_algorand(addr, check_sum_len_bytes)
    except Exception:
        return False

    return chksum == expected_checksum and not isinstance(addr, str)


def validate_crypto_address(
        address: str,
        currency: str,
        network: Optional[str] = None,
        testnet: bool = False,
        validate_inputs: bool = True
) -> bool:
    testnet = testnet or settings.IS_TESTNET
    # Check for extra characters
    if not address or not re.match('[a-zA-Z0-9.]+', address):
        return False

    if validate_inputs:
        if currency not in CURRENCY_INFO:
            return False
        if network is None:
            network = CURRENCY_INFO[currency]['default_network']

    if network in ETHEREUM_LIKE_NETWORKS:
        return validate_eth_address(address, currency)

    if network == CurrenciesNetworkName.TRX:
        return validate_trx_address(address, currency)

    if network == CurrenciesNetworkName.ONE:
        return validate_one_address(address)

    if network == CurrenciesNetworkName.ZTRX:
        return validate_bech32_address(hrp='ztron', address=address, currency=currency, ignore_length=True)

    if network == CurrenciesNetworkName.OMNI:
        return validate_omni_address(address, currency)

    if network == CurrenciesNetworkName.BNB:
        hrp = 'tbnb' if testnet else 'bnb'
        return validate_bech32_address(hrp=hrp, address=address, currency=currency)

    # Check Stellar like networks
    if network in [CurrenciesNetworkName.XLM, CurrenciesNetworkName.PMN]:
        return validate_xlm_address(address, currency)

    if network == CurrenciesNetworkName.BCH:
        from cashaddress import convert
        if address.startswith(('bitcoincash:', 'simpleledger:')):
            return False
        if convert.is_valid(address):
            return True
        if convert.is_valid('bitcoincash:' + address):
            return True
        return convert.is_valid('simpleledger:' + address)

    if network == CurrenciesNetworkName.EOS:
        if address in ['deposit.pro']:
            return True
        return bool(re.match(r'^[1-5a-z\\.]{1,12}$', address))

    if network == CurrenciesNetworkName.BTC:
        return validate_btc_address(address, currency, testnet=testnet)

    if network == CurrenciesNetworkName.LTC:
        try:
            if validate_ltc_segwit_address(address, currency):
                return True
            if bool(coinaddrvalidator.validate('ltc', address)):
                if address.startswith('3'):
                    return False
                return True
            return False
        except (TypeError, ValueError):
            return False

    if network == CurrenciesNetworkName.XRP:
        try:
            return bool(coinaddrvalidator.validate('xrp', address))
        except (TypeError, ValueError):
            return False

    if network == CurrenciesNetworkName.DOGE:
        try:
            return bool(coinaddrvalidator.validate('doge', address))
        except (TypeError, ValueError):
            return False

    if network == CurrenciesNetworkName.DOT:
        address_format = 42 if testnet else 0
        return is_valid_ss58_address(address, valid_ss58_format=address_format)

    if network == CurrenciesNetworkName.ADA:
        return validate_ada_address(address, testnet=testnet)

    if network == CurrenciesNetworkName.SOL:
        return validate_sol_address(address, currency)

    if network == CurrenciesNetworkName.ALGO:
        return validate_algo_address(address)

    if network == CurrenciesNetworkName.ATOM:
        return validate_atom_address(address)

    if network == CurrenciesNetworkName.XMR:
        return validate_xmr_address(address)

    if network == CurrenciesNetworkName.HBAR:
        return validate_hbar_address(address)

    if network == CurrenciesNetworkName.FLOW:
        return validate_flow_address(address)

    if network == CurrenciesNetworkName.APT:
        return validate_apt_address(address)

    if network == CurrenciesNetworkName.FIL:
        return validate_fil_address(address)

    if network == CurrenciesNetworkName.TON:
        return validate_ton_address(address)

    if network == CurrenciesNetworkName.XTZ:
        return validate_tezos_address(address)

    if network == CurrenciesNetworkName.ENJ:
        address_format = 9030 if testnet else 2135
        return is_valid_ss58_address(address, address_format)

    if network == CurrenciesNetworkName.SUI:
        return validate_sui_address(address=address)

    # Only performing a minimal check for other currencies
    return bool(re.match(r'[a-zA-Z0-9]{5,}', address))


def validate_tag(tag: str, currency: str, target_address: Optional[str] = None) -> bool:
    from exchange.wallet.models import AvailableDepositAddress
    if not tag:
        return False
    shared_tagged_addresses = None
    if target_address:
        shared_tagged_addresses = AvailableDepositAddress.objects.filter(
            address=target_address,
            currency=currency
        ).first()
    is_integer = currency in INTEGER_ONLY_TAG_CURRENCIES
    if is_integer or shared_tagged_addresses:
        try:
            tag = int(tag)
            # Tag is unsigned 32 bit int
            tag = tag % 2 ** 32
        except (TypeError, ValueError):
            return False
        return tag > 0
    return True


def validate_crypto_address_v2(
        address: str,
        currency: int,
        network: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """ Crypto currencies' address validation version 2. Use coin_info.py to validate addresses.

    :param address: str
    :param currency: int
    :param network: Optional[str]
    :param testnet: bool
    :return: typing.Tuple[bool, Optional[str]]
    """
    if currency not in CURRENCY_INFO:
        return False, None
    networks = CURRENCY_INFO.get(currency, {}).get('network_list')
    if network is not None:
        if network not in networks:
            return False, None
        networks = {network: networks[network]}

    for net_name in networks:
        addr_regx = networks.get(net_name, {}).get('address_regex')
        if not addr_regx:
            continue
        if re.match(addr_regx, address):
            return validate_crypto_address(address=address, currency=currency, network=net_name), net_name
    return False, None


def validate_crypto_address_by_network(address: str, network: str) -> bool:
    try:
        native_coin = CurrenciesNetworkName.NETWORKS_NATIVE_CURRENCY[network.upper()]
        is_valid, _ = validate_crypto_address_v2(address=address, currency=native_coin)
        return is_valid
    except KeyError as err:
        raise NetworkNotExist(f"'{network}' network is not valid") from err


def validate_memo_v2(
        memo: str,
        currency: int,
        network: Optional[str] = None,
        memo_regex: Optional[str] = None
) -> bool:
    """ Cryptocurrencies' memo validation version 2. Use coin_info.py to validate memoes.

    Args:
        memo: Memo or tag which required by some network
        currency: Currency which we want to check memo for
        network: Network which we want check memo for
        memo_regex: Manual value of regex(optional)
    """
    if memo_regex is not None:
        memo_regx = memo_regex
    else:
        if currency not in CURRENCY_INFO:
            return False
        curr_info = CURRENCY_INFO[currency]
        networks = curr_info.get('network_list')
        if network is None:
            network = curr_info.get('default_network')
        memo_regx = networks.get(network, {}).get('memo_regex')
    if not memo_regx:
        return True
    return bool(re.match(memo_regx, memo))


def validate_memo_by_network(
        memo: str,
        network: Optional[str] = None,
        memo_regex: Optional[str] = None
) -> bool:
    """ Validate if memo is acceptable by network or not

    Args:
        memo: String which send by transaction. Also called tag or comment in some networks
        network: Network which we want to validate memo for.

    Returns: If memo is validated for network or not
    """
    native_coin = CurrenciesNetworkName.NETWORKS_NATIVE_CURRENCY[network.upper()]
    return validate_memo_v2(memo, native_coin, network=network, memo_regex=memo_regex)


def validate_ton_address(address: str) -> bool:
    b64_abc = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890+/')
    b64_abc_urlsafe = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890_-')

    if set(address).issubset(b64_abc):
        address_bytes = base64.b64decode(address.encode('utf8'))
    elif set(address).issubset(b64_abc_urlsafe):
        address_bytes = base64.urlsafe_b64decode(address.encode('utf8'))
    else:
        return False  # Not an address
    return calc_crc_ton(address_bytes[:-2]) == address_bytes[-2:]


def calc_crc_ton(message: bytes) -> bytes:
    poly = 0x1021
    comparative_reg = 0xffff
    reg = 0
    message += b'\x00\x00'
    for byte in message:
        mask = 0x80
        while mask > 0:
            reg <<= 1
            if byte & mask:
                reg += 1
            mask >>= 1
            if reg > comparative_reg:
                reg &= comparative_reg
                reg ^= poly
    return reg.to_bytes(2, 'big')


def tezos_tb(list_: list) -> bytes:
    return b''.join(x.to_bytes(1, 'big') for x in list_)


def tezos_base58_decode(v: bytes) -> bytes:
    """Decode data using Base58 with checksum + validate binary prefix against known kinds and cut in the end.
    :param v: Array of bytes (use string.encode())
    :returns: bytes
    """
    tezos_base58_encodings = [
        (b'tz1', 36, tezos_tb([6, 161, 159]), 20, 'ed25519 public key hash'),
        (b'tz2', 36, tezos_tb([6, 161, 161]), 20, 'secp256k1 public key hash'),
        (b'tz3', 36, tezos_tb([6, 161, 164]), 20, 'p256 public key hash'),
        (b'tz4', 36, tezos_tb([6, 161, 16]), 20, 'BLS-MinPk'),
    ]
    try:
        prefix_len = next(
            len(encoding[2]) for encoding in tezos_base58_encodings
            if len(v) == encoding[1] and v.startswith(encoding[0]))
    except StopIteration as e:
        raise ValueError('Invalid encoding, prefix or length mismatch.') from e
    return base58.b58decode_check(v)[prefix_len:]


def validate_tezos_address(v: Union[str, bytes]) -> bool:
    """Check if value is a KT/tz address."""
    try:
        if isinstance(v, bytes):
            v = v.decode()
        v = v.split('%')[0]
        prefixes = [b'KT1', b'tz1', b'tz2', b'tz3', b'tz4']
        if isinstance(v, str):
            v = v.encode()
            if isinstance(v, bytes):
                pass
            elif isinstance(v, str):
                try:
                    _ = int(v, 16)
                except ValueError:
                    v = v.encode('ascii')
                else:
                    if v.startswith('0x'):
                        v = v[2:]
                    v = bytes.fromhex(v)
            else:
                raise TypeError(f"a bytes-like object is required (also str), not '{type(v).__name__}'")
        if any(map(v.startswith, prefixes)):
            tezos_base58_decode(v)
        else:
            raise ValueError('Unknown prefix.')
    except (ValueError, TypeError):
        return False
    return True


def validate_sui_address(address: str) -> bool:
    sui_address_length: int = 66
    if not isinstance(address, str):
        return False
    if not address.startswith('0x'):
        return False
    if len(address) != sui_address_length:
        return False
    try:
        int(address[2:], 16)
    except ValueError:
        return False
    return True
