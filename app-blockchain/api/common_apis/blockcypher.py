import random
from decimal import Decimal

import requests
from django.conf import settings
from exchange.base.models import Currencies
from exchange.base.parsers import parse_iso_date
from exchange.blockchain.api.general_api import NobitexBlockchainAPI
from exchange.blockchain.utils import APIError, BlockchainUtilsMixin


class BlockcypherAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    coins: Doge, Btc, Ltc, Eth, Dash
    """

    _base_url = 'https://api.blockcypher.com'
    symbol = ''
    currency = None

    active = True

    rate_limit = 0.34
    max_items_per_page = 1000
    page_offset_step = None
    confirmed_num = None
    PRECISION = 8
    XPUB_SUPPORT = False
    USE_PROXY = False

    supported_requests = {
        'get_balance': '/v1/{network}/main/addrs/{address}/full?limit=1',
        'get_tx_details': '/v1/{network}/main/txs/{tx_hash}?outstart=0&limit=5000',
    }

    def get_name(self):
        return 'blockcypher_api'

    # This two functions work just fine for all child classes(all supported coins),
    # so no need to implement them in this child classes
    def get_balance(self, address):
        self.validate_address(address)
        response = self.request('get_balance', address=address, network=str(self.__class__.__name__)[:-14].lower())
        # blockcypherAPI as a prefix for all classes names in this file is of length 14 so we ignore last 14 character
        # of class name and pure coin name comes out e.g: BTCBlockcypherAPI => "btc" and we send 'btc' as argument
        if response is None:
            raise APIError("[BlockcypherAPI][Get Balance] response is None")
        balance = response.get('balance')
        return {
            'amount': self.from_unit(balance),
        }

    def get_tx_details(self, tx_hash):
        response = self.request(
            'get_tx_details',
            tx_hash=tx_hash,
            network=self.symbol.lower()
        )
        success = False
        timestamp = None
        block = response.get('block_height')
        confirmations = response.get('confirmations')
        if confirmations >= 1:
            timestamp = parse_iso_date(response.get('confirmed'))
            if timestamp and block != -1 and not response.get('execution_error'):
                success = True
        internal_txids = response.get('internal_txids')  # always None except sometimes for ETH
        raw_inputs = response.get('inputs')
        raw_outputs = response.get('outputs')
        inputs = []
        outputs = []
        for raw_input in raw_inputs:
            if raw_input.get('addresses'):
                inputs.append({
                    'address': raw_input.get('addresses')[0],
                    'currency': self.currency,
                    'value': self.from_unit(raw_input.get('output_value')),
                    'is_valid': raw_input.get('script_type') in ['pay-to-pubkey-hash', 'pay-to-witness-script-hash',
                                                                 'pay-to-witness-pubkey-hash'] and success
                })
        for raw_output in raw_outputs:
            if raw_output.get('addresses'):
                if raw_output.get('addresses')[0] in [input_.get('address') for input_ in inputs]:
                    continue
                is_valid = raw_output.get('script_type') in ['pay-to-pubkey-hash', 'pay-to-witness-script-hash',
                                                             'pay-to-witness-pubkey-hash'] and success
                if is_valid:
                    outputs.append({
                        'address': raw_output.get('addresses')[0],
                        'currency': self.currency,
                        'value': self.from_unit(raw_output.get('value')),
                        'is_valid': is_valid
                    })
        total_output_value = Decimal(str(response.get('total'))) / Decimal('1e' + str(self.PRECISION))
        return {
            'hash': tx_hash,
            'success': success and not response.get('double_spend'),
            'double_spend': response.get('double_spend'),
            'inputs': inputs,
            'outputs': outputs,
            'transfers': [],
            'internal_txids': internal_txids,
            'block': block,
            'confirmations': confirmations,
            'fees': self.from_unit(response.get('fees')),
            'date': timestamp,
            'value': total_output_value,
            'raw': response,
        }

    def get_txs(self, address, tx_direction_filter='incoming', limit=20):
        network_url = 'main' if self.network == 'mainnet' else 'test3'
        BLOCKCYPHER_BUGGED_TXS = [
            '910f4107e7e4126d8351161da1b6a29feb51805d2120815d26aa73b8fbc34144',
            'a7ffe28698b538508e0038d7edd5776d292c90cf9853f3b38c30746e94488c35',
        ]
        # API Call
        tp = self.blockcypher_parse_tp(self.currency)
        endpoint = 'https://api.blockcypher.com/v1/{}/{}/addrs/{}/full?limit={}&txlimit=10000&token={}'.format(
            tp, network_url, address, limit, self.blockcypher_get_token()
        )
        try:
            address_info = requests.get(endpoint, timeout=60, proxies=settings.DEFAULT_PROXY)
            address_info.raise_for_status()
        except Exception as e:
            return None
        address_info = address_info.json()
        txs = address_info.get('txs', [])

        transactions = []
        for tx in txs:
            txid = tx.get('hash')
            if txid in BLOCKCYPHER_BUGGED_TXS:
                continue
            value = Decimal('0')
            outputs = tx.get('outputs', [])
            inputs = tx.get('inputs', [])
            from_addresses = set()
            next_outputs = tx.get('next_outputs')
            pages_to_check = 8
            huge = False
            for i in range(pages_to_check + 1):
                for output in outputs:
                    if not output or not output.get('addresses'):
                        # Sometimes no address is specified in output, for example when the script
                        #   type is pay-to-witness-pubkey-hash
                        continue
                    if output['addresses'][0] == address and output['script_type'] in ['pay-to-pubkey-hash',
                                                                                       'pay-to-witness-script-hash',
                                                                                       'pay-to-witness-pubkey-hash']:
                        value += output.get('value', 0)

                for input_ in inputs:
                    if not input_ or not input_.get('addresses'):
                        continue
                    from_addresses.update(input_['addresses'])
                    if input_['addresses'][0] == address and input_['script_type'] in ['pay-to-pubkey-hash',
                                                                                       'pay-to-witness-script-hash',
                                                                                       'pay-to-witness-pubkey-hash']:
                        value -= input_.get('output_value')

                if value > Decimal('0'):
                    # Found, it is improbable that an address is included in multiple outputs
                    break
                if not next_outputs:
                    # Transaction seems small
                    break
                if i == pages_to_check:
                    # Huge transaction, address not seen in the first 2020 outputs
                    huge = True
                    break
                # Fetch next output batch
                outputs = self.fetch_transaction_outputs(txid, self.currency, start=20 + i * 1000, page_size=1000,
                                                         network=network_url)
                if outputs is None:
                    return None
                if not outputs:
                    break

            value = Decimal(str(round(value))) / Decimal('1e8')
            transactions.append({
                self.currency: {
                    'address': address,
                    'hash': txid,
                    'from_address': from_addresses,
                    'block': tx.get('block_height'),
                    'date': parse_iso_date(tx.get('confirmed', tx.get('received'))),
                    'amount': value,
                    'confirmations': int(tx.get('confirmations', 0)),
                    'is_double_spend': bool(tx.get('double_spend')),
                    'huge': huge,
                    'raw': tx,
                }
            })
        return transactions

    @classmethod
    def blockcypher_parse_tp(cls, currency):
        if currency == Currencies.ltc:
            return 'ltc'
        if currency == Currencies.btc:
            return 'btc'
        if currency == Currencies.eth:
            return 'eth'
        raise ValueError('Unsupported Currency: {}'.format(currency))

    @classmethod
    def blockcypher_get_token(cls):
        if not settings.IS_PROD:
            return ''
        return random.choice(settings.BLOCKCYPHER_API_KEYS)

    @classmethod
    def fetch_transaction_outputs(cls, txid, currency, start=0, page_size=300, network='main'):
        tp = cls.blockcypher_parse_tp(currency)
        endpoint = 'https://api.blockcypher.com/v1/{}/{}/txs/{}?instart=1000&outstart={}&limit={}&token={}'.format(
            tp, network, txid, start, page_size, cls.blockcypher_get_token()
        )
        try:
            outputs_info = requests.get(endpoint, timeout=60, proxies=settings.DEFAULT_PROXY)
            outputs_info.raise_for_status()
        except Exception as e:
            return None
        outputs_info = outputs_info.json()
        return outputs_info['outputs']
