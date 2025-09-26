import datetime
import json
import random
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.utils.timezone import now

from exchange.blockchain.contracts_conf import BEP20_contract_currency, BEP20_contract_info
from exchange.base.parsers import parse_iso_date
from exchange.blockchain.utils import BlockchainUtilsMixin, APIError
from exchange.blockchain.api.general_api import NobitexBlockchainAPI


class BscBitqueryAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    coins: BNB
    API docs: https://graphql.bitquery.io/ide
    :exception ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut
    """

    active = True
    _base_url = 'https://graphql.bitquery.io/'
    testnet_url = 'https://graphql.bitquery.io/'
    symbol = 'ETH'
    bsc_symbol = 'BNB'
    cache_key = 'bsc'
    rate_limit = 0
    PRECISION = 18
    max_items_per_page = 20
    page_offset_step = None
    confirmed_num = None
    ignore_warning = False
    last_sync_datetime = None

    queries = {
        'get_tx': """
                query ($hash: String!, $from: ISO8601DateTime) {
                  ethereum(network: bsc) {
                    blocks(options: {desc: "height", limit: 1}, date: {since: $from}) {
                      height
                    }
                    transactions(txHash: {is: $hash}) {
                      hash
                      block {
                        height
                        timestamp {
                          time(format: "%Y-%m-%dT%H:%M:%SZ")
                        }
                      }
                      amount
                      currency {
                        symbol
                      }
                      creates {
                        address
                        annotation
                      }
                      error
                      success
                      sender {
                        address
                        annotation
                      }
                      to {
                        address
                        annotation
                      }
                      gas
                      gasPrice
                      gasCurrency {
                        symbol
                      }
                      gasValue
                    }
                    transfers(
                      txHash: {is: $hash}
                    ) {
                      sender {
                        address
                        annotation
                      }
                      receiver {
                        address
                        annotation
                      }
                      amount
                      currency {
                        symbol
                        address
                        decimals
                      }
                      external
                    }
                  }
                }
            """,
    }

    def get_name(self):
        return 'bitquery_api'

    @property
    def contract_currency_list(self):
        return BEP20_contract_currency.get(self.network)

    @property
    def contract_info_list(self):
        return BEP20_contract_info.get(self.network)

    def get_api_key(self):
        return random.choice(settings.BITQUERY_API_KEY)

    def get_tx_details(self, tx_hash):
        data = {
            'query': self.queries.get('get_tx'),
            'variables': {
                'hash': tx_hash,
                "from": datetime.datetime.now().strftime("%Y-%m-%d"),
            }
        }
        response = self.request('', headers={'Content-Type': 'application/json', 'X-API-KEY': self.get_api_key()},  body=json.dumps(data))
        if not response:
            raise APIError('Response is none')
        if response.get('errors'):
            raise APIError('Response is none')
        tx = response.get('data').get('ethereum')
        if not tx:
            raise APIError('Response is none')
        tx = self.parse_tx_details(tx)
        return tx

    def parse_tx_details(self, tx_info):
        inputs = []
        outputs = []
        transfers = []
        if not tx_info.get('transactions'):
            return None
        tx = tx_info.get('transactions')[0]
        if tx_info.get('transfers'):
            for transfer in tx_info.get('transfers'):
                transfers.append({
                    'type': 'BEP20',
                    'symbol': transfer.get('currency').get('symbol'),
                    'from': transfer.get('sender').get('address'),
                    'to': transfer.get('receiver').get('address'),
                    'token': transfer.get('currency').get('address'),
                    'name': '',
                    'value': Decimal(str(transfer.get('amount')))
                })
        else:
            transfers.append({
                'type': 'BEP20',
                'symbol': tx.get('currency').get('symbol'),
                'from': tx.get('sender').get('address'),
                'to': tx.get('to').get('address'),
                'value': Decimal(str(tx.get('amount'))),
                'token': '',
                'name': '',
            })
        return {
            'hash': tx.get('hash'),
            'success': tx.get('success'),
            'inputs': inputs,
            'outputs': outputs,
            'transfers': transfers,
            'block': tx.get('block').get('height'),
            'confirmations': tx_info.get('blocks')[0].get('height') - tx.get('block').get('height'),
            'fees': Decimal(str(tx.get('gasValue'))),
            'date': parse_iso_date(tx.get('block').get('timestamp').get('time')),
        }

    def get_balance(self, address, info=None):
        balances = {}
        self.validate_address(address)
        data = {"query": "query (\n  $network: EthereumNetwork!,\n  $address: String!\n) {\n  ethereum(network: "
                         "$network) {\n    address(address: {is: $address}) {\n      balances {\n        currency {\n  "
                         "        address\n          symbol\n          tokenType\n        }\n        value\n      }\n  "
                         "  }\n  }\n}\n",
                "variables": {'limit': 10, 'offset': 0, 'network': 'bsc', 'address': address}
                }
        response = self.request('get_balance', address=address, headers={'Content-Type': 'application/json',
                                                                         'X-API-KEY': self.api_key},
                                body=json.dumps(data))
        if response is None:
            raise APIError("[BitqueryAPI][Get Balance] response is none")
        if response.get('status') == '0':
            raise APIError(f"[BitqueryAPI][Get Balance] {response.get('result')}")
        res_balances = response['data']['ethereum']['address'][0]['balances']
        if info:
            for index in range(0, len(res_balances)):
                symbol = res_balances[index]['currency']['symbol']
                contract_address = res_balances[index]['currency']['address']
                balance = res_balances[index]['value']
                if info == 'BNB':
                    if symbol == info:
                        balances = {
                            'symbol': symbol,
                            'amount': Decimal(str(balance)),
                            'address': address,
                        }
                        return balances
                else:
                    bep20_contract_address = info.get('address')
                    if contract_address == bep20_contract_address:
                        balances[contract_address] = {
                            'symbol': symbol,
                            'amount': Decimal(str(balance)),
                            'address': address,
                        }
                        return balances
            balances[info.get('address')] = {
                'symbol': self.bsc_symbol,
                'amount': Decimal('0'),
                'address': address,
            }
            return balances
        else:
            for index in range(0, len(res_balances)):
                symbol = res_balances[index]['currency']['symbol']
                balance = res_balances[index]['value']
                contract_address = res_balances[index]['currency']['address']
                if balance != 0:
                    balances[contract_address] = {
                        'symbol': symbol,
                        'amount': Decimal(str(balance)),
                        'address': address,
                    }
            return balances

    def check_status_bitquery(self, only_check_status=False):
        """ Check status of blockbook API. Maybe it has warning, maybe it is not sync.
        :param only_check_status: If set true, only check info every one hours.
        :return: Blockbook API info
        """
        if only_check_status:
            if self.last_sync_datetime and self.last_sync_datetime >= now() - datetime.timedelta(hours=1):
                return
            self.last_sync_datetime = now()
        data = {
            "query": "query ($network: EthereumNetwork!, $limit: Int!, $offset: Int!, $from: ISO8601DateTime, "
                     "$till: ISO8601DateTime) {\n  ethereum(network: $network) {\n    blocks(options: {desc: "
                     "\"height\", limit: $limit, offset: $offset}, date: {since: $from, till: $till}) {\n      "
                     "timestamp {\n        time(format: \"%Y-%m-%d %H:%M:%S\")\n      }\n      height\n      "
                     "transactionCount\n      address: miner {\n        address\n        annotation\n      }\n    "
                     "  reward\n      rewardCurrency {\n        symbol\n      }\n    }\n  }\n}\n",
            "variables": {'limit': 1, 'offset': 0, 'network': 'bsc', 'from': self.last_sync_datetime, 'till': None,
                          'dateFormat': '%Y-%m-%d'}
        }
        info = self.request(request_method='get_info', body=json.dumps(data), headers={'Content-Type': 'application/json', 'X-API-KEY': self.api_key})
        if not info:
            raise APIError('Empty info')

        if not info.get('data').get('ethereum').get('blocks'):
            raise APIError('Invalid info(empty blockbook)')
        return info.get('data').get('ethereum').get('blocks')[0]

    def get_input_tx(self, tx_info):
        input_addresses = set()
        address = tx_info.get('sender').get('address')
        input_addresses.update([address])
        return input_addresses

    def get_output_tx(self, tx_info):
        output_addresses = set()
        address = tx_info.get('to').get('address')
        output_addresses.update([address])
        return output_addresses

    def get_input_output_tx(self, tx_info):
        # Get input and output addresses in transaction
        input_addresses = set(self.get_input_tx(tx_info))
        output_addresses = set(self.get_output_tx(tx_info))
        return input_addresses, output_addresses

    def get_latest_block(self, after_block_number=None, to_block_number=None):
        info = self.check_status_bitquery()
        if not to_block_number:
            latest_block_height_mined = info.get('height')
            if not latest_block_height_mined:
                raise APIError('API Not Return block height')
        else:
            latest_block_height_mined = to_block_number

        if not after_block_number:
            latest_block_height_processed = cache.get(f'latest_block_height_processed_{self.bsc_symbol.lower()}')
            if latest_block_height_processed is None:
                latest_block_height_processed = latest_block_height_mined - 5
        else:
            latest_block_height_processed = after_block_number

        if latest_block_height_mined > latest_block_height_processed:
            min_height = latest_block_height_processed + 1
        else:
            min_height = latest_block_height_mined + 1
        max_height = latest_block_height_mined + 1
        max_height = min(max_height, min_height + 100)

        transactions_addresses = set()
        print('Cache latest block height: {}'.format(latest_block_height_processed))

        for block_height in range(min_height, max_height):
            data = {
                "query": "query(\n  $height: Int\n) {\n  ethereum(network: bsc) {\n    blocks(height: {is: "
                         "$height}) {\n      hash\n      difficulty\n      height\n      parentHash\n      "
                         "reward\n      rewardCurrency {\n        address\n        decimals\n        name\n   "
                         "     symbol\n        tokenId\n        tokenType\n      }\n      totalDifficulty\n   "
                         "   transactionCount\n      uncleCount\n    }\n    transactions(height: {is: "
                         "$height}) {\n      gas\n      gasValue\n      gasPrice\n      hash\n      count\n   "
                         "   sender {\n        address\n        annotation\n      }\n      success\n      to "
                         "{\n        address\n        annotation\n      }\n    }\n    smartContractEvents("
                         "height: {is: $height}) {\n      smartContractEvent {\n        name\n        "
                         "signature\n        signatureHash\n      }\n      smartContract {\n        address {"
                         "\n          address\n          annotation\n        }\n        contractType\n      "
                         "}\n      transaction {\n        hash\n      }\n      eventIndex\n    }\n  }\n}",
                "variables": {'height': block_height}
            }
            response = self.request(request_method='get_block', body=json.dumps(data),
                                    headers={'Content-Type': 'application/json',
                                             'X-API-KEY': self.api_key})
            if not response:
                raise APIError('Get block API returns empty response')

            transactions = response.get('data').get('ethereum').get('transactions') or []
            for tx_info in transactions:
                input_addresses, output_addresses = self.get_input_output_tx(tx_info)
                tx_hash = tx_info.get('hash')
                if not tx_hash:
                    continue
                addresses = set(output_addresses).difference(input_addresses)
                transactions_addresses.update(addresses)
        cache.set(f'latest_block_height_processed_{self.bsc_symbol.lower()}', max_height - 1, 86400)
        return set(transactions_addresses)


class TetherBitqueryAPI(BscBitqueryAPI):
    bsc_symbol = 'USDT'


class BtcBitqueryAPI(BscBitqueryAPI):
    bsc_symbol = 'BTCB'


class EthBitqueryAPI(BscBitqueryAPI):
    bsc_symbol = 'ETH'
