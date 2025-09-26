import datetime
import pytz
from django.conf import settings

from exchange.base.models import Currencies
from exchange.base.parsers import parse_utc_timestamp
from exchange.blockchain.api.common_apis.blockbook import BlockbookAPI
from exchange.blockchain.api.commons.blockbook import BlockBookApi, BlockBookParser
from exchange.blockchain.utils import BlockchainUtilsMixin, APIError
from exchange.blockchain.api.general_api import NobitexBlockchainAPI
from exchange.blockchain.validators import convert_eth_address_to_checksum


class EtcBlockBookAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    coins: etc
    API docs: https://github.com/trezor/blockbook/blob/master/docs/api.md
    Explorer: https://etcbook.guarda.co
    """

    _base_url = 'https://etcbook.guarda.co'
    symbol = 'ETC'
    cache_key = 'etc'
    active = True

    rate_limit = 0
    max_items_per_page = 1000
    page_offset_step = None
    confirmed_num = None
    PRECISION = 18
    XPUB_SUPPORT = False
    currency = Currencies.etc

    supported_requests = {
        'get_balance': '/api/v2/address/{address}?pageSize={size}',
        'get_tx': '/api/v2/tx/{tx_hash}',
    }

    def get_name(self):
        return 'etc_blockbook'

    def get_balance(self, address):
        self.validate_address(address)
        response = self.request('get_balance',
                                address=address,
                                size=10)

        if not response:
            return None

        balance = self.from_unit(int(response.get('balance')))
        balances = {
            self.currency: {
                'symbol': self.symbol,
                'amount': balance,
                'address': address
            }
        }
        return balances

    def get_txs(self, address, offset=None, limit=None, unconfirmed=False):
        self.validate_address(address)
        response = self.request('get_balance', address=address, size=20)
        tx_ids = response.get('txids') or []
        txs = []
        for tx_id in tx_ids:
            parsed_tx = self.parse_tx(tx_id, address)
            if not parsed_tx:
                continue
            txs.append(parsed_tx)
        return txs

    def parse_tx(self, tx_id, address):
        """ Get transaction data from explorer for the given tx_id and parse it

            # TODO: What is isAddress in v_in/v_out? Should we check it?
        """
        tx_data = self.request('get_tx', tx_hash=tx_id)

        # TODO: Can there be multiple inputs for an ETC transaction?
        # If so, here the deposit can return some of the coins
        if len(tx_data.get('vin') or []) != 1:
            return None
        if len(tx_data.get('vout') or []) != 1:
            return None
        v_in = tx_data['vin'][0]
        v_out = tx_data['vout'][0]

        if address in v_in['addresses']:
            direction = 'outgoing'
        else:
            direction = 'incoming'

        tx_type = 'normal'
        if tx_data.get('tokenTransfers'):
            tx_type = 'erc20'

        return {self.currency: {
            'date': parse_utc_timestamp(tx_data['blockTime']),
            'from_address': v_in['addresses'],
            'to_address': v_out['addresses'],
            'amount': self.from_unit(int(tx_data['value'])),
            'fee': self.from_unit(int(tx_data['fees'])),
            'hash': tx_id,
            'confirmations': tx_data['confirmations'],
            'is_error': False,
            'type': tx_type,
            'kind': 'transaction',
            'direction': direction,
            'status': 'confirmed' if tx_data['confirmations'] >= 50000 else 'unconfirmed',
            'raw': tx_data,
            'memo': None
        }}

    def get_tx_details(self, tx_hash):
        try:
            response = self.request('get_tx', tx_hash=tx_hash)
        except:
            raise APIError("[ETC blockbook API][Get Transaction details] unsuccessful")

        tx = self.parse_tx_details(response)
        return tx

    def parse_tx_details(self, tx_info):
        inputs = []
        outputs = []
        transfers = []
        vins = tx_info.get('vin')
        vouts = tx_info.get('vout')

        # if not vins[0].get('value') then transaction is account based transaction otherwise it's UTXO's type.
        if not vins[0].get('value'):
            if vins[0].get('isAddress') and vouts[0].get('isAddress'):
                transfers.append({
                    'type': 'MainCoin',
                    'symbol': self.symbol,
                    'from': vins[0].get('addresses')[0],
                    'to': vouts[0].get('addresses')[0],
                    'value': self.from_unit(int(tx_info.get('value')), self.PRECISION),
                    'token': '',
                    'name': '',
                })
        else:
            for vin in tx_info.get('vin'):
                if not vin.get('isAddress'):
                    continue
                inputs.append({
                    'address': vin.get('addresses')[0],
                    'value': self.from_unit(int(vin.get('value')))
                })
            for vout in tx_info.get('vout'):
                if not vout.get('isAddress'):
                    continue
                outputs.append({
                    'address': vout.get('addresses')[0],
                    'value': self.from_unit(int(vout.get('value')))
                })
        token_transfers = tx_info.get('tokenTransfers') or []
        for transfer in token_transfers:
            transfers.append({
                'type': transfer.get('type'),
                'symbol': transfer.get('symbol'),
                'from': transfer.get('from'),
                'to': transfer.get('to'),
                'token': transfer.get('token'),
                'name': transfer.get('name'),
                'value': self.from_unit(int(transfer.get('value')), transfer.get('decimals'))
            })

        return{
            'inputs': inputs,
            'outputs': outputs,
            'transfers': transfers,
            'block': tx_info.get('blockHeight'),
            'confirmations': tx_info.get('confirmations'),
            'fees': self.from_unit(int(tx_info.get('fees'))),
            'date': datetime.datetime.fromtimestamp(tx_info.get('blockTime'), pytz.utc),
        }


class EthereumClassicBlockbookAPI(BlockbookAPI):
    """
    coins: eth
    API docs: https://github.com/trezor/blockbook/blob/master/docs/api.md
    Explorer: https://blockbook-ethereum.tronwallet.me
    """

    # _base_url = 'https://etcbook.guarda.co'
    _base_url = 'https://blockbook.etc.zelcore.io'
    TOKEN_NETWORK = True
    symbol = 'ETC'
    PRECISION = 18
    currency = Currencies.etc
    cache_key = 'etc'
    USE_PROXY = True

    def get_name(self):
        return 'etc_blockbook2'

    def get_header(self):
        return {
            'User-Agent': (
                'Mozilla/5.0 (X11; Linux x86_64; rv:75.0) Gecko/20100101 Firefox/75.0' if not settings.IS_VIP else
                'Mozilla/5.0 (X11; Untu; Linux x86_64; rv:95.0) Gecko/20100101 Firefox/109.0')
        }

    def to_explorer_address_format(self, address):
        return convert_eth_address_to_checksum(address=address)

    @classmethod
    def convert_address(cls, address):
        return address.lower()


class EthereumClassicBlockBookParser(BlockBookParser):
    precision = 18
    symbol = 'ETC'
    currency = Currencies.etc
    TOKEN_NETWORK = True

    @classmethod
    def convert_address(cls, address):
        return address.lower()

    def to_explorer_address_format(self, address):
        return convert_eth_address_to_checksum(address=address)


class EthereumClassicBlockBookApi(BlockBookApi):
    parser = EthereumClassicBlockBookParser
    _base_url = 'https://etcbook.guarda.co'
    # _base_url = 'https://blockbook.etc.zelcore.io'
    symbol = 'ETC'
    cache_key = 'etc'
    SUPPORT_PAGING = True
    max_workers_for_get_block = 5

    def get_header(self):
        return {
            'User-Agent': (
                'Mozilla/5.0 (X11; Linux x86_64; rv:75.0) Gecko/20100101 Firefox/75.0' if not settings.IS_VIP else
                'Mozilla/5.0 (X11; Untu; Linux x86_64; rv:95.0) Gecko/20100101 Firefox/109.0')
        }
