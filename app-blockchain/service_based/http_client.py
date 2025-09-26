import json
import random

from django.conf import settings
from exchange.blockchain.utils import Service


class ServiceBasedHttpClient(Service):

    def __init__(self, url):
        super().__init__()
        self._base_url = url
        self.use_proxy = False
        self.cert_key_path = settings.CERT_KEY_PATH
        self.cert_file_path = settings.CERT_FILE_PATH
        self.is_local = '127.0.0.1' in url or 'localhost' in url

    supported_requests = {
        'get_balance': '/{network}/wallets/balance',
        'get_address_txs': '/{network}/wallets/{address}/transactions?tx_direction={tx_direction_filter}&currency={currency}&contract_address={contract_address}',  # noqa
        'get_ata': '/sol/wallets/{address}/ata/?currency={currency}',
        'get_tx_details': '/{network}/transactions/{tx_hash}',
        'get_txs_details': '/{network}/transactions/?currency={currency}&provider={provider}&base_url={base_url}',
        'get_blocks_txs': '/{network}/blocks/info?after_block_number={after_block_number}&to_block_number={to_block_number}',  # noqa
        'get_block_head': '/{network}/blocks/head',
    }

    @staticmethod
    def get_headers():
        return {
            'Content-Type': 'application/json',
            'NOBITEXPLORER-API-KEY': random.choice(settings.SERVICE_BASE_API_KEY)
        }

    def get_wallets_balance(self, network, currency_symbol, addresses):
        return self.request(
            request_method='get_balance',
            network=network.lower(),
            body=json.dumps({'addresses': addresses, 'currency': currency_symbol}),
            headers=self.get_headers()
        )

    def get_wallet_transactions(self, network, currency_symbol, address, contract_address, tx_direction_filter=''):
        return self.request(
            request_method='get_address_txs',
            network=network,
            currency=currency_symbol,
            address=address,
            contract_address=contract_address,
            tx_direction_filter=tx_direction_filter,
            headers=self.get_headers()
        )

    def get_tx_details(self, network, tx_hash):
        return self.request(
            request_method='get_tx_details',
            network=network,
            tx_hash=tx_hash,
            headers=self.get_headers(),
            timeout=180,
        )

    def get_tx_details_batch(self, network, tx_hashes, currency_symbol, provider = None, base_url=None) -> dict:
        return self.request(
            request_method='get_txs_details',
            network=network,
            currency=currency_symbol,
            provider=provider,
            base_url=base_url,
            body=json.dumps({'tx_hashes': tx_hashes}),
            headers=self.get_headers(),
            timeout=180,
        )

    def get_block_head(self, network):
        return self.request(
            request_method='get_block_head',
            network=network,
            headers=self.get_headers()
        )

    def get_blocks_txs(self, network, after_block_number, to_block_number):
        return self.request(
            request_method='get_blocks_txs',
            network=network,
            after_block_number=after_block_number,
            to_block_number=to_block_number,
            headers=self.get_headers(),
            timeout=120
        )

    def get_ata(self, address, currency_symbol):
        return self.request(
            request_method='get_ata',
            address=address,
            currency=currency_symbol,
            headers=self.get_headers(),
            timeout=120
        )

    def request(self, request_method, with_rate_limit=True,
                body=None, headers=None, timeout=30, proxies=None,
                force_post=False, **params):
        try:
            # if proxies is None:
            #     if self.use_proxy:
            #         proxies = settings.DEFAULT_PROXY
            return super(ServiceBasedHttpClient, self).request(
                request_method=request_method, with_rate_limit=with_rate_limit,
                body=body, headers=headers, timeout=timeout, proxies=proxies,
                force_post=force_post,
                cert=(self.cert_file_path, self.cert_key_path) if not self.is_local else None,
                **params)
        except ConnectionError as e:
            raise e
