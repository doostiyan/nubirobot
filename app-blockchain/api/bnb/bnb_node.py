import base64
from decimal import Decimal

from exchange.base.models import Currencies
from exchange.blockchain.utils import BlockchainUtilsMixin, APIError
from exchange.blockchain.api.general_block_api import NobitexBlockchainBlockAPI


class BinanceNodeAPI(NobitexBlockchainBlockAPI, BlockchainUtilsMixin):

    currency = Currencies.bnb
    symbol = 'BNB'
    PRECISION = 8
    cache_key = 'bnb'

    _base_url = 'https://nodes.nobitex1.ir/bnb'
    testnet_url = 'https://seed-pre-s3.binance.org:443'

    supported_requests = {
        'get_balance': '/abci_query?path="/store/acc/key"&data={account_data}',
    }

    def get_name(self):
        return 'node_api'

    def get_balance(self, address):
        from binance_chain.utils import segwit_addr
        try:
            decoded_address = segwit_addr.decode_address(address).hex().upper()
            response = self.request('get_balance', account_data='0x6163636F756E743A' + decoded_address)

            balance_info = response.get('result', {}).get('response', {}).get('value')
            if not balance_info:
                raise APIError('Failed to get BNB address info from BNB node')

            balance = self.parse_balance(balance_info)
            return {
                self.currency: {
                    'symbol': self.symbol,
                    'amount': balance,
                    'unconfirmed_amount': Decimal(0),
                    'address': address
                }
            }
        except Exception as error:
            raise APIError(f'BNB get_balance is failed! Error:{error}')

    def parse_balance(self, data, only_free=True):
        from exchange.blockchain.api.bnb import bnb_dex_account_pb2
        account_decoded = base64.b64decode(data)
        account_info = bnb_dex_account_pb2.AppAccount().FromString(account_decoded[4:])

        balance = 0
        for coin in account_info.base.coins:
            if coin.denom == 'BNB':
                balance += coin.amount
                break
        if not only_free:
            for coin in account_info.locked:
                if coin.denom == 'BNB':
                    balance += coin.amount

        return self.from_unit(balance)

    def get_latest_block(self):
        pass
