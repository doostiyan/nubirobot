from base58 import b58decode_check, b58encode_check

from exchange.base.models import Currencies
from exchange.blockchain.api.common_apis.sochain import SochainAPI
from exchange.blockchain.utils import ValidationError


class LitecoinSochainAPI(SochainAPI):

    symbol = 'LTC'
    currency = Currencies.ltc
    PRECISION = 8

    @classmethod
    def convert_address(cls, address):
        try:
            decoded = b58decode_check(address)
            version = decoded[:1].hex()
            data = decoded[1:]
            if version == '05':  # 05:mainet  3xxx
                version = '32'
            elif version == '32':  # 50:mainet  Mxxx
                version = '05'
            elif version == 'c4':  # 196:testnet 2xxx
                version = '3a'
            elif version == '3a':  # 58:testnet Qxxx
                version = 'c4'
            else:
                raise Exception('unknow version {}'.format(version))

            converted_address = b58encode_check(bytes.fromhex(version + data.hex()))
        except Exception as e:
            raise ValidationError('Address is not valid.')
        return str(converted_address, 'utf-8')
