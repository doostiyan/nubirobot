from collections import defaultdict
import json
import datetime

from django.core.cache import cache
from django.conf import settings

from exchange.blockchain.metrics import metric_set
from exchange.blockchain.segwit_address import one_to_eth_address
from exchange.blockchain.utils import BlockchainUtilsMixin, APIError
from exchange.blockchain.api.general_api import NobitexBlockchainAPI
if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import (CURRENCIES as Currencies, get_currency_codename, harmony_ERC20_contract_currency,
                               harmony_ERC20_contract_info)
    from blockchain.parsers import parse_utc_timestamp
else:
    from exchange.base.models import Currencies, get_currency_codename
    from exchange.base.parsers import parse_utc_timestamp
    from exchange.blockchain.contracts_conf import harmony_ERC20_contract_info, harmony_ERC20_contract_currency


class HarmonyRPC(NobitexBlockchainAPI, BlockchainUtilsMixin):
    symbol = 'ONE'
    currency = Currencies.one
    # rate limit is not clear
    rate_limit = 0
    PRECISION = 18
    cache_key = 'one'
    headers = {'content-type': 'application/json'}

    # you can use https://api.harmony.one or https://harmony.public-rpc.com or https://api.s0.t.hmny.io
    # _base_url = 'https://harmony.public-rpc.com'
    _base_url = 'https://api.harmony.one'
    # _base_url = 'https://harmony-0-rpc.gateway.pokt.network'
    # _base_url = 'https://1rpc.io/one'

    USE_PROXY = False

    @property
    def contract_currency_list(self):
        return harmony_ERC20_contract_currency.get(self.network)

    @property
    def contract_info_list(self):
        return harmony_ERC20_contract_info.get(self.network)

    def get_token_txs(self, address, contract_info, offset=0, limit=25, direction=''):
        return self.get_all_txs(address=address, contract_info=contract_info, offset=offset, limit=limit)

    def get_txs(self, address, offset=0, limit=25):
        return self.get_all_txs(address=address, offset=offset, limit=limit)

    def get_all_txs(self, address, contract_info=None, offset=0, limit=25):
        tx_type = 'native'
        if contract_info is not None:
            tx_type = 'token'
        self.validate_address(address)
        payload = json.dumps({
            'jsonrpc': '2.0',
            'method': 'hmyv2_getTransactionsHistory',
            'params': [
                {
                    'address': address,
                    'pageIndex': offset,
                    'pageSize': limit,
                    'fullTx': True,
                    'txType': 'ALL',
                    'order': 'DESC'
                }
            ],
            'id': 1
        })

        transactions_resp = self.request('', body=payload, headers=self.headers)
        error = transactions_resp.get('error', None)
        if error:
            raise APIError('one_rpc_get_all_txs: Invalid transactions resp')
        transactions_resp = transactions_resp['result']['transactions']
        if len(transactions_resp) == 0:
            return []
        multi_receipt_data = []
        receipt_id = 1
        for transaction in transactions_resp:
            single_receipt_data = {'jsonrpc': '2.0', 'method': 'hmyv2_getTransactionReceipt',
                                   'params': [transaction['ethHash']], 'id': receipt_id}
            multi_receipt_data.append(single_receipt_data)
            receipt_id += 1
        receipt_resp = self.request('', body=json.dumps(multi_receipt_data), headers=self.headers)
        if type(receipt_resp) == dict:
            receipt_resp = [receipt_resp]
        error = receipt_resp[0].get('error', None)
        if error:
            raise APIError('one_rpc_get_all_txs: Invalid receipt resp')
        transfers = []
        block_head = self.check_block_status()
        for tx, receipt in zip(transactions_resp, receipt_resp):
            success = True if receipt.get('result').get('status', None) == 1 else False

            if ((tx_type == 'native' and self.validate_native_transaction(tx)) or (
                    tx_type == 'token' and self.validate_token_transaction(tx))) and success:
                if tx_type == 'token' and one_to_eth_address(tx.get('to')).lower() != contract_info['address']:
                    continue

                if tx['shardID'] != 0 or tx['toShardID'] != 0:
                    continue

                tx_info = self.get_transaction_data(tx)
                if tx_info:
                    direction = 'incoming'
                    value = tx_info.get('amount')
                    if tx_info.get('from') == address:
                        # Transaction is from this address, so it is a withdraw
                        value = -value
                        direction = 'outgoing'
                    transfers.append(
                        {
                            tx_info.get('currency'): {
                                'address': address,
                                'hash': tx.get('ethHash'),
                                'from_address': tx_info.get('from'),
                                'to_address': tx_info.get('to'),
                                'amount': value,
                                'block': tx.get('blockNumber'),
                                'date': parse_utc_timestamp(tx.get('timestamp')),
                                # 'confirmations': self.calculate_tx_confirmations(parse_utc_timestamp(tx.get('timestamp'))),
                                'confirmations': block_head - tx.get('blockNumber'),
                                'direction': direction,
                                'raw': tx,
                            }
                        }
                    )
        return transfers

    def get_tx_details(self, tx_hash):
        transfers = []

        receipt_data = {'jsonrpc': '2.0', 'method': 'hmyv2_getTransactionReceipt', 'params': [tx_hash], 'id': 1}
        tx_data = {'jsonrpc': '2.0', 'method': 'hmyv2_getTransactionByHash', 'params': [tx_hash], 'id': 1}
        tx = self.request('', body=json.dumps(tx_data), headers=self.headers)
        receipt = self.request('', body=json.dumps(receipt_data), headers=self.headers)
        receipt = receipt.get('result', None)
        tx = tx.get('result', None)
        if not tx or not receipt:
            return None
        is_valid = False
        success = True if receipt.get('status') == 1 else False
        if self.validate_transaction(tx) and success:
            tx_info = self.get_transaction_data(tx)
            if tx_info:
                is_valid = True
                transfers.append({
                    'symbol': get_currency_codename(tx_info.get('currency')).upper(),
                    'currency': tx_info.get('currency'),
                    'from': tx_info.get('from'),
                    'to': tx_info.get('to'),
                    'value': tx_info.get('amount'),
                    'is_valid': True
                })
        return {
            'hash': tx.get('ethHash'),
            'success': success,
            'is_valid': is_valid and success,
            'inputs': [],
            'outputs': [],
            'transfers': transfers,
            'block': tx.get('blockNumber'),
        }

    @classmethod
    def decode_tx_input_data(cls, input_data):
        return {
            'value': int(input_data[74:138], 16),
            'to': '0x' + input_data[34:74]
        }

    def get_transaction_data(self, tx_info):
        input_ = tx_info.get('input')
        if input_ == '0x' or input_ == '0x0000000000000000000000000000000000000000':
            value = self.from_unit(int(tx_info.get('value')))
            to_address = tx_info.get('to')
            if to_address:
                to_address = one_to_eth_address(to_address)
            else:
                return
            from_address = tx_info.get('from')
            from_address = one_to_eth_address(from_address)
            currency = self.currency
        else:
            try:
                to_address = tx_info.get('to')
                to_address = one_to_eth_address(to_address)
                currency = self.contract_currency(to_address.lower())
            except Exception as e:
                return
            if currency is None:
                return
            input_data = self.decode_tx_input_data(tx_info.get('input'))
            to_address = input_data.get('to')
            from_address = one_to_eth_address(tx_info.get('from'))
            contract_info = self.contract_info(currency)
            value = self.from_unit(input_data.get('value'), contract_info.get('decimals'))

        if not to_address or not from_address:
            return

        return {
            'from': from_address.lower(),
            'to': to_address.lower(),
            'amount': value,
            'currency': currency,
        }

    def check_block_status(self):
        data = {'jsonrpc': '2.0', 'method': 'hmyv2_latestHeader', 'params': [], 'id': 1}
        info = self.request('', body=json.dumps(data), headers=self.headers)
        if not info:
            raise APIError('Empty info')
        if not info.get('result'):
            raise APIError('Invalid info')
        return info.get('result').get('blockNumber')

    def get_block_head(self):
        return self.check_block_status()

    def get_latest_block(self, after_block_number=None, to_block_number=None, include_inputs=False, include_info=False,
                         update_cache=True):
        if not to_block_number:
            latest_block_height_mined = self.check_block_status()
            if not latest_block_height_mined:
                raise APIError('API Not Returned block height')
        else:
            latest_block_height_mined = to_block_number

        if not after_block_number:
            latest_block_height_processed = cache.get(f'latest_block_height_processed_{self.cache_key}')
            if latest_block_height_processed is None:
                latest_block_height_processed = latest_block_height_mined - 5
        else:
            latest_block_height_processed = after_block_number

        if latest_block_height_mined > latest_block_height_processed:
            min_height = latest_block_height_processed + 1
        else:
            min_height = latest_block_height_mined + 1
        max_height = latest_block_height_mined + 1
        if max_height - min_height > 100:
            max_height = min_height + 100

        # input_addresses ~ outgoing_txs and output_addresses ~ incoming_txs
        transactions_addresses = {'input_addresses': set(), 'output_addresses': set()}
        transactions_info = {'outgoing_txs': defaultdict(lambda: defaultdict(list)),
                             'incoming_txs': defaultdict(lambda: defaultdict(list))}
        if min_height >= max_height:
            return transactions_addresses, transactions_info, 0
        print('Cache latest block height: {}'.format(latest_block_height_processed))

        get_blocks_data = {
            'jsonrpc': '2.0',
            'method': 'hmyv2_getBlocks',
            'params': [
                min_height,
                max_height - 1,
                {
                    'withSigners': False,
                    'fullTx': True,
                    'inclStaking': False
                }
            ],
            'id': 1
        }

        response = self.request('', body=json.dumps(get_blocks_data), headers=self.headers)

        if not response:
            raise APIError('Get block API returns empty response')

        blocks_transactions = response.get('result', None)
        if not blocks_transactions:
            raise APIError('Get block API returns error response')

        if type(blocks_transactions) == dict:
            blocks_transactions = [blocks_transactions]

        for block_transactions in blocks_transactions:
            transactions = block_transactions.get('transactions')
            for transaction in transactions:
                tx_hash = transaction.get('ethHash')
                if not tx_hash:
                    continue

                if not self.validate_transaction(transaction):
                    continue

                tx_data = self.get_transaction_data(transaction)
                if tx_data is None:
                    continue

                from_address = tx_data.get('from')
                to_address = tx_data.get('to')
                value = tx_data.get('amount')
                currency = tx_data.get('currency')

                transactions_addresses['output_addresses'].add(to_address)
                if include_inputs:
                    transactions_addresses['input_addresses'].add(from_address)

                if include_info:
                    if include_inputs:
                        transactions_info['outgoing_txs'][from_address][currency].append({
                            'tx_hash': tx_hash,
                            'value': value,
                        })
                    transactions_info['incoming_txs'][to_address][currency].append({
                        'tx_hash': tx_hash,
                        'value': value,
                    })
        if update_cache:
            metric_set(name='latest_block_processed', labels=[self.symbol.lower()], amount=max_height - 1)
            cache.set(f'{settings.BLOCKCHAIN_CACHE_PREFIX}latest_block_height_processed_{self.cache_key}',
                      max_height - 1,
                      86400)
        return transactions_addresses, transactions_info, max_height - 1

    def contract_currency(self, token_address):
        return self.contract_currency_list.get(token_address)

    def contract_info(self, currency):
        return self.contract_info_list.get(currency)

    def get_txs_hashes(self, txs_hash):
        result = []
        get_txs_data = []
        tx_id = 1
        for tx_hash in txs_hash:
            tx_data = {'jsonrpc': '2.0', 'method': 'hmyv2_getTransactionByHash', 'params': [tx_hash], 'id': tx_id}
            get_txs_data.append(tx_data)
            tx_id += 1
        txs_resp = self.request('', body=json.dumps(get_txs_data), headers=self.headers)
        if not txs_resp:
            return None
        if type(txs_resp) == dict:
            txs_resp = [txs_resp]
        error = txs_resp[0].get('error', None)
        if error:
            return None
        for tx_resp in txs_resp:
            result.append(tx_resp['result']['ethHash'])
        return result

    @classmethod
    def calculate_tx_confirmations(cls, tx_date):
        diff = (datetime.datetime.now(datetime.timezone.utc) - tx_date).total_seconds()
        return int(diff / 2.2)  # ONE block time is 1 seconds, for more reliability we get it for '2.2'.

    @staticmethod
    def validate_transaction(tx_info):
        if tx_info.get('input') == '0x' or tx_info.get('input') == '0x0000000000000000000000000000000000000000':
            return True
        if tx_info.get('input')[0:10] == '0xa9059cbb' and len(tx_info.get('input')) == 138:
            return True
        return False

    @staticmethod
    def validate_native_transaction(tx_info):
        if tx_info.get('input') == '0x' or tx_info.get('input') == '0x0000000000000000000000000000000000000000':
            return True
        return False

    @staticmethod
    def validate_token_transaction(tx_info):
        if tx_info.get('input')[0:10] == '0xa9059cbb' and len(tx_info.get('input')) == 138:
            return True
        return False


class AnkrHarmonyRpc(HarmonyRPC):
    """
    rate limit doc: https://www.ankr.com/docs/rpc-service/service-plans/#rate-limits
    """
    _base_url = 'https://rpc.ankr.com/harmony'
    rate_limit = 0.033  # ≈1800 requests/minute — guaranteed

