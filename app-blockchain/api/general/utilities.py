from typing import List

from exchange.base.models import Currencies
from exchange.blockchain.api.ton.utils import TonAddressConvertor, TonHashConvertor


class Utilities:
    @staticmethod
    def format_url(base_url: str, path_url: str, **params: dict) -> str:
        if path_url:
            return base_url + path_url.format(**params)
        return base_url

    @staticmethod
    def normalize_hash(network: str, currency: int, tx_hashes: List[str], output_format: str = 'base64') -> List[str]:
        if network == 'TON':
            if currency and currency != Currencies.ton:
                # jettons
                return [TonHashConvertor.ton_convert_hash(input_hash=tx_hash, output_format='hex')
                        for tx_hash in tx_hashes]
            # native coin - TON
            return [TonHashConvertor.ton_convert_hash(input_hash=tx_hash, output_format=output_format)
                    for tx_hash in tx_hashes]
        return tx_hashes

    @classmethod
    def normalize_address(cls, network: str, address: str) -> str:
        if network == 'TON':
            address_format = TonAddressConvertor.detect_address_type(address)
            if address_format == 'Bounceable':
                return address
            if address_format == 'Non-Bounceable':
                return TonAddressConvertor.convert_non_bounceable_to_bounceable(address)
            if address_format == 'Hex':
                return TonAddressConvertor.convert_hex_to_bounceable(address)
            return 'InvalidAddressFormat'
        return address
