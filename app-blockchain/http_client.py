import json

from exchange.base.models import Currencies
from exchange.blockchain.utils import Service


class ServiceBasedHttpClient(Service):
    _base_url = 'http://localhost:8144'
    supported_requests = {
        'get_balance': '/wallets/balance/?network={network}&currency={currency}',
        'get_address_txs': '/wallets/transactions?network=fil&address={address}&currency={currency}'
    }

    @staticmethod
    def get_headers():
        return {'Content-Type': 'application/json'}

    def get_wallets_balance(self, address_list, currency):
        network, addresses = next(iter(address_list.items()))
        currency_symbol = self.get_symbol_from_currency_code(currency)
        return self.request(
            request_method='get_balance',
            network=network.lower(),
            currency=currency_symbol,
            body=json.dumps({'addresses': addresses}),
            headers=self.get_headers()
        )

    def get_wallet_transactions(self, address, currency):
        currency_symbol = self.get_symbol_from_currency_code(currency)
        return self.request(
            request_method='get_address_txs',
            currency=currency_symbol,
            address=address,
            headers=self.get_headers()
        )

    @staticmethod
    def get_symbol_from_currency_code(currency_code):
        for k, v in Currencies._identifier_map.items():
            if v == currency_code:
                return k.lower()
        return None
