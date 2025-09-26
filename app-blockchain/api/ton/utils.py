import base64
import sys
import time
import traceback


class TonAddressConvertor:
    BOUNCEABLE_ADDRESS_FIRST_BYTE = 0x11
    NON_BOUNCEABLE_ADDRESS_FIRST_BYTE = 0x51
    TON_ADDRESS_LENGTH = 36

    @classmethod
    def detect_address_type(cls, address: str) -> str:
        try:
            # Decode base64 (url-safe or standard)
            try:
                address_bytes = base64.urlsafe_b64decode(address.encode('utf8') + b'=' * (4 - len(address) % 4))
            except Exception:
                address_bytes = base64.b64decode(address.encode('utf8') + b'=' * (4 - len(address) % 4))

            # Check length: Valid base64 TON addresses should be exactly 36 bytes
            if len(address_bytes) == cls.TON_ADDRESS_LENGTH:
                # Check CRC: last 2 bytes should match the calculated CRC
                calculated_crc = cls.calc_crc(address_bytes[:-2])
                if address_bytes[-2:] == calculated_crc:
                    # Check the address type based on the first byte
                    if address_bytes[0] == cls.BOUNCEABLE_ADDRESS_FIRST_BYTE:
                        return 'Bounceable'
                    if address_bytes[0] == cls.NON_BOUNCEABLE_ADDRESS_FIRST_BYTE:
                        return 'Non-Bounceable'
        except Exception:
            pass

        if len(address) == 66 and address[:2] == '0:':  # noqa: PLR2004
            address = address[2:]
        if len(address) == 64 and all(c in '0123456789abcdefABCDEF' for c in address):  # noqa: PLR2004
            try:
                # Try converting to integer to ensure it is valid
                int(address, 16)
                return 'Hex'

            except ValueError:
                pass

        return 'Unknown'

    @classmethod
    def calc_crc(cls, message: str) -> bytes:
        poly = 0x1021
        reg = 0
        message += b'\x00\x00'
        for byte in message:
            mask = 0x80
            while mask > 0:
                reg <<= 1
                if byte & mask:
                    reg += 1
                mask >>= 1
                if reg > 0xffff:  # noqa: PLR2004
                    reg &= 0xffff
                    reg ^= poly
        return reg.to_bytes(2, 'big')

    @classmethod
    def convert_bounceable_to_hex(cls, address: str) -> str:
        b64_abc = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890+/')
        b64_abc_urlsafe = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890_-')
        if set(address).issubset(b64_abc):
            address_bytes = base64.b64decode(address.encode('utf8'))
        elif set(address).issubset(b64_abc_urlsafe):
            address_bytes = base64.urlsafe_b64decode(address.encode('utf8'))
        else:
            raise Exception('Failed to convert_user_friendly_to_raw')
        hx = hex(int.from_bytes(address_bytes[2:-2], 'big'))[2:]
        hx = (64 - len(hx)) * '0' + hx
        return hx.lower()

    @classmethod
    def convert_bounceable_to_non_bounceable(cls, address: str) -> str:
        # Decode Bounceable address
        address_bytes = base64.urlsafe_b64decode(address.encode('utf8'))

        # Replace Bounceable tag (0x11) with Non-Bounceable tag (0x51)
        non_bounceable_bytes = b'\x51' + address_bytes[1:]

        # Calculate CRC
        final_bytes = non_bounceable_bytes[:-2] + cls.calc_crc(non_bounceable_bytes[:-2])
        return base64.urlsafe_b64encode(final_bytes).decode('utf8')

    @classmethod
    def convert_hex_to_bounceable(cls, raw: str) -> str:
        raw = raw[2:] if len(raw) == 66 and raw[:2] == '0:' else raw  # noqa: PLR2004
        workchain = 0
        address = int(raw, 16)
        address = address.to_bytes(32, 'big')
        workchain_tag = workchain.to_bytes(1, 'big')
        btag = b'\x11'

        preaddr_b = btag + workchain_tag + address
        return base64.urlsafe_b64encode(preaddr_b + cls.calc_crc(preaddr_b)).decode('utf8')

    @classmethod
    def convert_hex_to_non_bounceable(cls, raw: str) -> str:
        raw = raw[2:] if len(raw) == 66 and raw[:2] == '0:' else raw  # noqa: PLR2004
        workchain = 0
        address = int(raw, 16)
        address = address.to_bytes(32, 'big')
        workchain_tag = workchain.to_bytes(1, 'big')

        # Non-Bounceable tag
        btag = b'\x51'

        preaddr_b = btag + workchain_tag + address
        return base64.urlsafe_b64encode(preaddr_b + cls.calc_crc(preaddr_b)).decode('utf8')

    @classmethod
    def convert_non_bounceable_to_bounceable(cls, address: str) -> str:
        # Decode Non-Bounceable address
        address_bytes = base64.urlsafe_b64decode(address.encode('utf8'))

        # Replace Non-Bounceable tag (0x51) with Bounceable tag (0x11)
        bounceable_bytes = b'\x11' + address_bytes[1:]

        # Calculate CRC
        final_bytes = bounceable_bytes[:-2] + cls.calc_crc(bounceable_bytes[:-2])
        return base64.urlsafe_b64encode(final_bytes).decode('utf8')

    @classmethod
    def convert_non_bounceable_to_hex(cls, address: str) -> str:

        address_bytes = base64.urlsafe_b64decode(address.encode('utf8'))

        # Extract 32 bytes of address (ignore first 2 bytes and last 2 bytes)
        hx = hex(int.from_bytes(address_bytes[2:-2], 'big'))[2:]

        # Padding to 64 characters
        hx = (64 - len(hx)) * '0' + hx
        return hx.lower()


class TonHashConvertor:
    @classmethod
    def ton_convert_hash(cls, input_hash: str, output_format: str) -> str:
        try:
            if all(c in '0123456789abcdefABCDEF' for c in input_hash) and len(input_hash) % 2 == 0:
                #  Hex
                byte_data = bytes.fromhex(input_hash)
            elif '-' in input_hash or '_' in input_hash:
                #  Base64 URL-safe
                byte_data = base64.urlsafe_b64decode(input_hash + '=' * (4 - len(input_hash) % 4))
            else:
                #  Base64 - standard
                byte_data = base64.b64decode(input_hash + '=' * (4 - len(input_hash) % 4))

            # convert output
            if output_format == 'hex':
                return byte_data.hex()
            if output_format == 'base64':
                return base64.b64encode(byte_data).decode('utf-8')
            if output_format == 'base64url':
                return base64.urlsafe_b64encode(byte_data).decode('utf-8')
            raise ValueError('invalid output format!')
        except Exception:
            traceback.print_exception(*sys.exc_info())
            raise


def calculate_tx_confirmations(average_block_time: int, tx_date: float) -> int:
    current_time_in_s = time.time()
    diff = current_time_in_s - tx_date
    return int(diff / average_block_time)
