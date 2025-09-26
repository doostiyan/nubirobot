import json
from collections import defaultdict
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache

from exchange.base.models import get_currency_codename
from exchange.blockchain.api.common_apis.blockscan import are_addresses_equal
from exchange.blockchain.decorators import handle_exception
from exchange.blockchain.metrics import metric_set
from exchange.blockchain.models import get_token_code, CurrenciesNetworkName
from exchange.blockchain.utils import BlockchainUtilsMixin, APIError
from exchange.blockchain.api.general_block_api import NobitexBlockchainBlockAPI

from exchange.blockchain.utils import get_currency_symbol_from_currency_code


class Web3API(NobitexBlockchainBlockAPI, BlockchainUtilsMixin):
    """
    Web3 API

    supported coins: Ethereum and Erc20 tokens
    API docs: https://web3py.readthedocs.io/
    """

    active = True
    TOKEN_NETWORK = True
    symbol = 'ETH'
    rate_limit = 1.2
    PRECISION = 18
    babydoge_contract = None
    block_height_offset = 5

    def get_name(self):
        return '{}_web3'.format(self.symbol.lower())

    def __init__(self):
        from web3 import Web3
        super().__init__()
        requests_kwargs = {'timeout': 30}
        if self.USE_PROXY and not settings.IS_VIP:
            requests_kwargs['proxies'] = settings.DEFAULT_PROXY
        self.w3 = Web3(Web3.HTTPProvider(self.base_url, request_kwargs=requests_kwargs))
        if self.symbol == 'BSC':
            contract_abi_path = settings.BASE_DIR + '/exchange/blockchain/contract_abis/babydoge_bsc.abi'
            with open(contract_abi_path) as contract_file:
                contract_abi = contract_file.read()
            self.babydoge_contract = self.w3.eth.contract(
                self.w3.to_checksum_address(self.contract_info(get_token_code('1b_babydoge', 'bep20')).get('address')),
                abi=contract_abi)

    @handle_exception
    def get_tx_details(self, tx_hash):
        transfers = []
        tx = self.w3.eth.get_transaction(tx_hash)
        receipt = self.w3.eth.get_transaction_receipt(tx_hash)
        success = True if receipt.get('status') == 1 else False
        if self.validate_transaction(tx) and success:
            transfers_data = self.get_transaction_data(tx)
            if transfers_data:
                for transfer in transfers_data:
                    transfers.append({
                        'symbol': get_currency_codename(transfer.get('currency')).upper(),
                        'currency': transfer.get('currency'),
                        'from': transfer.get('from'),
                        'to': transfer.get('to'),
                        'value': transfer.get('amount'),
                        'is_valid': True,
                        'token': transfer.get('contract_address')
                    })
        return {
            'hash': tx.get('hash').to_0x_hex(),
            'success': success,
            'inputs': [],
            'outputs': [],
            'transfers': transfers,
            'block': tx.get('blockNumber'),
            'memo': None,
            'confirmations': None,
            'date': None,
            'fees': None
        }

    @handle_exception
    def get_balance(self, address):
        checksum_address = self.w3.to_checksum_address(address)
        balance = self.from_unit(self.w3.eth.get_balance(checksum_address))
        if balance is None:
            return None
        return {
            'address': address,
            'balance': balance,
        }

    @handle_exception
    def get_token_balance(self, address, contracts_info):
        if type(list(contracts_info.values())[0]) is dict:
            contract_info = list(contracts_info.values())[0]
        else:
            contract_info = contracts_info
        checksum_address = self.w3.to_checksum_address(address)
        contract_address = self.w3.to_checksum_address(contract_info.get('address'))
        abi = json.loads('[{"inputs":[{"internalType":"address","name":"account","type":"address"}],'
                         '"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],'
                         '"stateMutability":"view","type":"function"}]')
        contract = self.w3.eth.contract(contract_address, abi=abi)
        token_balance = self.from_unit(int(contract.functions.balanceOf(checksum_address).call()), contract_info.get('decimals'))
        return {
            'symbol': contract_info.get('symbol'),
            'amount': token_balance,
            'address': address
        }

    @handle_exception
    def check_block_status(self):
        block_number = self.w3.eth.block_number
        if not block_number:
            raise APIError(f'[{self.__class__.__name__}][CheckStatus] Unsuccessful.')
        return block_number

    @handle_exception
    def get_block_head(self):
        return self.check_block_status()

    # Note: in this method we could not recognize if a detected transaction was successfully done or not (to skip it in
    # block processing if it was not successful)
    @handle_exception
    def get_latest_block(self, after_block_number=None, to_block_number=None, include_inputs=False, include_info=False, update_cache=True):
        from web3.exceptions import BlockNotFound
        if not to_block_number:
            latest_block_height_mined = self.check_block_status() - self.block_height_offset
            if not latest_block_height_mined:
                raise APIError('API Not Returned block height')
        else:
            latest_block_height_mined = to_block_number

        if not after_block_number:
            latest_block_height_processed = cache.get(
                f'{settings.BLOCKCHAIN_CACHE_PREFIX}latest_block_height_processed_{self.cache_key}')
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

        print(self.base_url)
        # input_addresses ~ outgoing_txs and output_addresses ~ incoming_txs
        transactions_addresses = {'input_addresses': set(), 'output_addresses': set()}
        transactions_info = {'outgoing_txs': defaultdict(lambda: defaultdict(list)),
                             'incoming_txs': defaultdict(lambda: defaultdict(list))}
        print('Cache latest block height: {}'.format(latest_block_height_processed))
        for block_height in range(min_height, max_height):
            try:
                response = self.w3.eth.get_block(block_identifier=block_height, full_transactions=True)
                if not response:
                    raise APIError(f'[{self.__class__.__name__}][GetBlock] Get block API returns empty response')
            except BlockNotFound:
                raise APIError(
                    f'[{self.__class__.__name__}][GetBlock] Block with blcoknumber: {block_height} not found')
            transactions = response.get('transactions')
            for tx in transactions:
                tx_hash = tx.get('hash').to_0x_hex()
                if not tx_hash:
                    continue
                if not self.validate_transaction(tx):
                    continue
                transfers = self.get_transaction_data(tx)
                if transfers is None:
                    continue
                for transfer in transfers:
                    from_address = transfer.get('from')
                    to_address = transfer.get('to')
                    value = transfer.get('amount')
                    currency = transfer.get('currency')
                    contract_address = transfer.get('contract_address')

                    if are_addresses_equal(
                        from_address, '0x70Fd2842096f451150c5748a30e39b64e35A3CdF') or are_addresses_equal(
                        from_address, '0x491fe5F4724e642C90372B0B95b60c4aC8d13F1c') or are_addresses_equal(
                        from_address, '0xB256caa23992e461E277CfA44a2FD72E2d6d2344') or are_addresses_equal(
                        from_address, '0x06cC26db08674CbD9FF4d52444712E23cA3d046d') or are_addresses_equal(
                        from_address, '0x4752B9bD4E73E2f52323E18137F0E66CDDF3f6C9'
                    ):
                        continue

                    transactions_addresses['output_addresses'].add(to_address)
                    if include_inputs:
                        transactions_addresses['input_addresses'].add(from_address)

                    if include_info:
                        if include_inputs:
                            transactions_info['outgoing_txs'][from_address][currency].append({
                                'tx_hash': tx_hash,
                                'value': value,
                                'contract_address': contract_address,
                                'block_height': block_height,
                                'symbol': get_currency_symbol_from_currency_code(currency)
                            })
                        transactions_info['incoming_txs'][to_address][currency].append({
                            'tx_hash': tx_hash,
                            'value': value,
                            'contract_address': contract_address,
                            'block_height': block_height,
                            'symbol': get_currency_symbol_from_currency_code(currency)
                        })
        if update_cache:
            metric_set(name='latest_block_processed', labels=[self.symbol.lower()], amount=max_height - 1)
            cache.set(f'{settings.BLOCKCHAIN_CACHE_PREFIX}latest_block_height_processed_{self.cache_key}',
                      max_height - 1,
                      86400)
        return transactions_addresses, transactions_info, max_height - 1

    def decode_tx_input_data(cls, input_data):
        return {
            'value': int(input_data[74:138], 16),
            'to': '0x' + input_data[34:74]
        }

    @staticmethod
    def split_batch_inpt_data(input_data, splitter):
        parts = []
        current_part = ""

        for i in range(0, len(input_data), 64):
            chunk = input_data[i:i + 64]  # Chunk input data into 64-character part
            if chunk == splitter:  # Check if the chunk is the splitter
                if current_part:
                    parts.append(current_part)
                current_part = ""
            else:
                current_part += chunk

        if current_part:
            parts.append(current_part)

        return parts

    def parse_batch_transfer_erc20_input_data(self, input_data, from_address):
        _, tokens, addresses, values = self.split_batch_inpt_data(input_data[10:], input_data[10:][192:256])
        transfers_count = len(tokens)
        transfers = []
        for i in range(0, transfers_count, 64):
            token = '0x' + tokens[i: i+64][24:64]
            currency = self.contract_currency(token.lower())
            if not currency:
                continue
            contract_info = self.contract_info(currency[0], token.lower())
            if not contract_info:
                continue
            transfers.append({
                'from': from_address.lower(),
                'to': '0x' + addresses[i: i+64][24:64].lower(),
                'amount':  self.from_unit(int(values[i: i+64], 16), contract_info.get('decimals')),
                'currency':  currency[0],
                'contract_address': contract_info.get('address'),
            })
        return transfers

    def get_transaction_data(self, tx_info):
        input_ = tx_info.get('input').to_0x_hex()
        if input_[0:10] == '0xe6930a22' and self.symbol == 'ETH':
            # because the from address of token transfers is from the contract which is "to" address in tx
            from_address = tx_info.get('to')
            try:
                return self.parse_batch_transfer_erc20_input_data(input_, from_address)
            except:
                return
        if input_ == '0x' or input_ == '0x0000000000000000000000000000000000000000':
            value = self.from_unit(int(tx_info.get('value')))
            to_address = tx_info.get('to')
            from_address = tx_info.get('from')
            currency = self.currency
            contract_address = None
        else:
            try:
                currency, contract_address = self.contract_currency(tx_info.get('to').lower())
            except Exception as e:
                return
            if currency is None:
                return
            input_data = self.decode_tx_input_data(input_)
            to_address = input_data.get('to')
            from_address = tx_info.get('from')
            contract_info = self.contract_info(currency, contract_address)
            value = self.from_unit(input_data.get('value'), contract_info.get('decimals'))
            if currency == get_token_code('1b_babydoge', 'bep20') and self.symbol == 'BSC':
                transaction = self.w3.eth.get_transaction_receipt(tx_info.get('hash'))
                logs = self.babydoge_contract.events.Transfer().process_receipt(transaction)
                if len(logs) == 0:
                    return
                log = logs[0] if len(logs) == 1 else logs[-1]
                value = self.from_unit(log.get('args').get('value'), contract_info.get('decimals'))

        if not to_address or not from_address:
            return

        return [{
            'from': from_address.lower(),
            'to': to_address.lower(),
            'amount': value,
            'currency': currency,
            'contract_address': contract_address,
        }]

    def contract_currency(self, token_address):
        currency_with_default_contract = self.contract_currency_list.get(token_address)
        if currency_with_default_contract:
            return currency_with_default_contract, None
        if token_address in CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.keys():
            return CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.get(token_address, {}).get("destination_currency"), token_address

    @property
    def contract_currency_list(self):
        return {}

    def contract_info(self, currency, contract_address=None):
        if contract_address in CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.keys():
            return CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.get(contract_address, {}).get('info')
        return self.contract_info_list.get(currency)

    @property
    def contract_info_list(self):
        return {}

    @staticmethod
    def validate_transaction(tx_info):
        input_ = tx_info.get('input').to_0x_hex()
        if input_ == '0x' or input_ == '0x0000000000000000000000000000000000000000':
            return True
        if input_[0:10] == '0xa9059cbb' and len(input_) == 138:
            return True
        if input_[0:10] == '0xe6930a22':
            return True
        return False
