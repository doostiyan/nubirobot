import random
import time
from decimal import Decimal

import base58
from django.conf import settings
from eth_keys import keys
from eth_typing import HexStr
from exchange.base.connections import get_geth
from exchange.base.logging import log_event, report_event, report_exception
from exchange.base.models import Currencies
from exchange.base.parsers import parse_utc_timestamp
from exchange.blockchain.api.eth.eth_blockbook import EthereumBlockbookAPI
from exchange.blockchain.api.eth.eth_web3 import ETHWeb3
from exchange.blockchain.bep20 import Bep20BlockchainInspector
from exchange.blockchain.general_blockchain_wallets import GeneralBlockchainWallet
from exchange.blockchain.metrics import metric_incr
from exchange.blockchain.models import Transaction
from exchange.blockchain.opera_ftm import OperaFTMBlockchainInspector
from exchange.blockchain.polygon_erc20 import PolygonERC20BlockchainInspector
from exchange.blockchain.utils import AddressNotExist, APIError, BadGateway, GatewayTimeOut, InternalServerError


class EthereumBlockchainInspector(Bep20BlockchainInspector, OperaFTMBlockchainInspector, PolygonERC20BlockchainInspector):
    """ Based on: https://etherscan.io/apis
        Rate limit: 5 requests/sec
    """
    TESTNET_ENABLED = False
    network = 'testnet' if TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS else 'mainnet'
    currency = Currencies.eth
    currency_list = [Currencies.eth]
    USE_EXPLORER_BALANCE_ETH = 'etherscan'  # Available options: etherscan, geth, web3
    USE_EXPLORER_TRANSACTION_ETH = 'etherscan'  # Available options: etherscan, ethplorer, blockbook

    get_balance_method = {
        'ETH': 'get_wallets_balance_eth',
        'BSC': 'get_wallets_balance_bsc',
        'FTM': 'get_wallets_balance_ftm',
        'MATIC': 'get_wallets_balance_polygon',
    }

    get_transactions_method = {
        'ETH': 'get_wallet_transactions_eth',
        'BSC': 'get_wallet_transactions_bsc',
        'FTM': 'get_wallet_transactions_ftm',
        'MATIC': 'get_wallet_transactions_polygon',
    }

    get_transaction_details_method = {
        'ETH': 'get_transaction_details_eth',
        'BSC': 'get_transaction_details_bsc',
    }

    @ classmethod
    def get_transaction_details_eth(cls, tx_hash, network=None, raise_error=False):
        tx_details = None
        try:
            tx_details = EthereumBlockbookAPI.get_api().get_tx_details(tx_hash=tx_hash)
        except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut, Exception) as e:
            if raise_error:
                raise e
        return tx_details


    @classmethod
    def get_wallets_balance_eth(cls, address_list):
        if cls.USE_EXPLORER_BALANCE_ETH == 'geth':
            return cls.get_wallets_balance_geth(address_list)
        if cls.USE_EXPLORER_BALANCE_ETH == 'etherscan':
            return cls.get_wallets_balance_etherscan(address_list)
        if cls.USE_EXPLORER_BALANCE_ETH == 'web3':
            return cls.get_wallets_balance_web3(address_list)
        return cls.get_wallets_balance_etherscan(address_list)

    @classmethod
    def are_addresses_equal(cls, addr1, addr2):
        if not addr1 or not addr2:
            return False
        addr1 = addr1.lower()
        if not addr1.startswith('0x'):
            addr1 = '0x' + addr1
        addr2 = addr2.lower()
        if not addr2.startswith('0x'):
            addr2 = '0x' + addr2
        return addr1 == addr2

    @classmethod
    def get_wallets_balance_etherscan(cls, address_list, raise_error=False):
        """
            Note: in list of addresses, each address should include the initial "0x"
            Note: this function only returns net balances for each address and not sent/etc. details
        """
        time.sleep(0.1)
        param = ','.join(address_list)
        try:
            if settings.USE_TESTNET_BLOCKCHAINS:
                explorer_url = 'https://api-ropsten.etherscan.io/'
            else:
                explorer_url = 'https://api.etherscan.io/'
            explorer_url = explorer_url + 'api?module=account&action=balancemulti&address={}&tag=latest&apikey={}'
            api_key = random.choice(settings.ETHERSCAN_API_KEYS)
            api_response = cls.get_session().get(explorer_url.format(param, api_key), timeout=25)
            api_response.raise_for_status()
        except Exception as e:
            raise e
            print('Failed to get ETH wallet balance from API: {}'.format(str(e)))
            # report_event('Etherscan API Error')
            return None
        info = api_response.json()
        if info.get('status') == '0' or info.get('message') == 'NOTOK':
            # report_event('Etherscan API Error')
            return None
        balances = []
        response_info = info['result']
        for addr_info in response_info:
            addr = addr_info['account']
            balance = Decimal(addr_info['balance'] or '0') / Decimal('1e18')
            # TODO: currently we only return balance and set other fields to zero
            balances.append({
                'address': addr,
                'received': balance,
                'sent': Decimal('0'),
                'rewarded': Decimal('0'),
                'balance': balance,
            })
        return balances

    @classmethod
    def get_wallets_balance_geth(cls, address_list, raise_error=False):
        try:
            geth = get_geth()
        except Exception as e:
            if raise_error:
                raise e
            # report_event('Geth Connection Error')
            return
        balances = []
        for addr in address_list:
            try:
                res = geth.request('eth_getBalance', [addr, 'latest'])
            except Exception as e:
                print('Failed to get ETH wallet balance from Geth: {}'.format(str(e)))
                # report_event('Geth API Error')
                continue
            error = res.get('error')
            result = res.get('result')
            if error or not result:
                print('Failed to get ETH wallet balance from Geth: {}'.format(str(res)))
                # report_event('Geth Response Error')
                continue
            balance = int(result, 0) / Decimal('1e18')
            balance = balance.quantize(Decimal('1e-8'))
            balances.append({
                'address': addr,
                'received': balance,
                'sent': Decimal('0'),
                'rewarded': Decimal('0'),
                'balance': balance,
            })
        return balances

    @classmethod
    def get_wallets_balance_web3(cls, address_list, raise_error=False):
        balances = []
        if not address_list:
            return []
        api = ETHWeb3.get_api()
        for address in address_list:
            try:
                response = api.get_balance(address)
                if not response:
                    continue
                balance = response.get(cls.currency).get('amount')
            except Exception as e:
                metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
                if raise_error:
                    raise e
                print('Failed to get ETH wallet balance from web3: {}'.format(str(e)))
                # report_event('Web3API Error')
                continue
            balances.append({
                'address': address,
                'received': balance,
                'sent': Decimal('0'),
                'rewarded': Decimal('0'),
                'balance': balance,
            })
        return balances

    @classmethod
    def get_wallet_transactions_eth(cls, address):
        # Check address validity
        if not address or len(address) <= 10:
            return None
        if not address.startswith('0x'):
            address = '0x' + address
        if cls.USE_EXPLORER_TRANSACTION_ETH == 'etherscan':
            return cls.get_wallet_transactions_etherscan(address)
        if cls.USE_EXPLORER_TRANSACTION_ETH == 'blockbook':
            return cls.get_wallet_transactions_blockbook(address)
        if cls.USE_EXPLORER_TRANSACTION_ETH == 'ethplorer':
            return cls.get_wallet_transactions_ethplorer(address)
        return cls.get_wallet_transactions_etherscan(address)

    @classmethod
    def get_wallet_transactions_etherscan(cls, address, raise_error=False):
        # Get data from API
        time.sleep(0.1)
        try:
            if cls.network == 'testnet':
                explorer_url = 'https://api-ropsten.etherscan.io/'
            else:
                explorer_url = 'https://api.etherscan.io/'
            explorer_url = explorer_url + 'api?module=account&action=txlist&address={}&page=1&offset=50&sort=desc&apikey={}'
            api_key = random.choice(settings.ETHERSCAN_API_KEYS)
            api_response = cls.get_session().get(explorer_url.format(address, api_key), timeout=60)
            api_response.raise_for_status()
        except Exception as e:
            if raise_error:
                raise e
            print('Failed to get ETH wallet transactions from API: {}'.format(str(e)))
            # report_event('Etherscan API Error')
            return None
        info = api_response.json()
        if info.get('message') != 'OK':
            return []
        info = info.get('result')

        # Parse transactions
        transactions = []
        for tx_info in info:
            if tx_info.get('isError') != '0' or tx_info.get('txreceipt_status') != '1':
                # report_event(f'Warning: invalid transaction received from eth. Check address {address}')
                continue
            value = Decimal(str(round(int(tx_info.get('value', 0))))) / Decimal('1e18')

            # Process transaction types
            if cls.are_addresses_equal(tx_info.get('from'), address):
                # Transaction is from this address, so it is a withdraw
                value = -value
            elif not cls.are_addresses_equal(tx_info.get('to'), address):
                # Transaction is not to this address, and is not a withdraw, so no deposit should be made
                #  this is a special case and should not happen, so we ignore such special transaction (value will be zero)
                value = Decimal('0')

            elif cls.are_addresses_equal(tx_info.get('from'),
                                         '0x70Fd2842096f451150c5748a30e39b64e35A3CdF') or cls.are_addresses_equal(
                tx_info.get('from'), '0x491fe5F4724e642C90372B0B95b60c4aC8d13F1c') or cls.are_addresses_equal(
                tx_info.get('from'), '0xB256caa23992e461E277CfA44a2FD72E2d6d2344') or cls.are_addresses_equal(
                tx_info.get('from'), '0x06cC26db08674CbD9FF4d52444712E23cA3d046d'):
                value = Decimal('0')

            transactions.append(Transaction(
                address=address,
                from_address=[tx_info.get('from')],
                hash=tx_info.get('hash'),
                block=tx_info.get('block'),
                timestamp=parse_utc_timestamp(tx_info.get('timeStamp')),
                value=value,
                confirmations=int(tx_info.get('confirmations', 0)),
                is_double_spend=False,  # TODO: check for double spends for ETH
                details=tx_info,
            ))
        return transactions

    @classmethod
    def from_hex(cls, address):
        if len(address) < 40:
            address = address.zfill(40)
        if len(address) == 40:
            address = '41' + address
        return base58.b58encode_check(bytes.fromhex(address)).decode()

    @classmethod
    def parse_actions_ethgrid(cls, records, address):
        transactions = []
        for record in records:
            if 'tokenTransfers' in list(record.keys()):
                continue
            value = record.get('value')
            if not value:
                continue

            from_address = record.get('vin')[0].get('addresses')[0]
            to_address = record.get('vout')[0].get('addresses')[0]
            confirmations = record.get('confirmations')
            block_number = record.get('blockHeight')
            timestamp = int(record.get('blockTime')) // 1000
            transactions.append(
                Transaction(
                    address=to_address,
                  # from_address=[cls.from_hex(from_address)],
                    from_address=from_address,
                    hash=record.get('txid'),
                    timestamp=parse_utc_timestamp(timestamp),
                    value=Decimal(value)/Decimal('1000000000000000000'),
                    confirmations=confirmations,
                    is_double_spend=False,
                    block=block_number,
                    details=record,
                )
            )
        return transactions

    @classmethod
    def get_wallet_transactions_ethplorer(cls, address, raise_error=False):
        # Get data from API
        time.sleep(0.1)
        try:
            if settings.USE_TESTNET_BLOCKCHAINS:
                return []
            else:
                explorer_url = 'https://api.ethplorer.io/'
            explorer_url = explorer_url + 'getAddressTransactions/{}?apiKey={}'
            api_key = random.choice(settings.ETHPLORER_API_KEYS)
            api_response = cls.get_session().post(explorer_url.format(address, api_key), timeout=60)
            api_response.raise_for_status()
        except Exception as e:
            if raise_error:
                raise e
            print('Failed to get ETH wallet transactions from API: {}'.format(str(e)))
            # report_event('Ethplorer API Error')
            return None
        info = api_response.json()

        # Parse transactions
        transactions = []
        for tx_info in info:
            value = Decimal(tx_info.get('value', 0)).quantize(Decimal('1e-8'))

            # Process transaction types
            if cls.are_addresses_equal(tx_info.get('from'), address):
                # Transaction is from this address, so it is a withdraw
                value = -value
            elif not cls.are_addresses_equal(tx_info.get('to'), address):
                # Transaction is not to this address, and is not a withdraw, so no deposit should be made
                #  this is a special case and should not happen, so we ignore such special transaction (value will be zero)
                value = Decimal('0')

            elif cls.are_addresses_equal(tx_info.get('from'),
                                         '0x70Fd2842096f451150c5748a30e39b64e35A3CdF') or cls.are_addresses_equal(
                tx_info.get('from'), '0x491fe5F4724e642C90372B0B95b60c4aC8d13F1c') or cls.are_addresses_equal(
                tx_info.get('from'), '0xB256caa23992e461E277CfA44a2FD72E2d6d2344') or cls.are_addresses_equal(
                tx_info.get('from'), '0x06cC26db08674CbD9FF4d52444712E23cA3d046d'):
                value = Decimal('0')

            transactions.append(Transaction(
                address=address,
                from_address=[tx_info.get('from')],
                hash=tx_info.get('hash'),
                timestamp=parse_utc_timestamp(tx_info.get('timestamp')),
                value=value,
                confirmations=13 if tx_info.get('success') else 0,
                is_double_spend=False,  # TODO: check for double spends for ETH
                details=tx_info,
            ))
        return transactions

    @classmethod
    def get_wallet_transactions_blockbook(cls, address, raise_error=False):
        api = EthereumBlockbookAPI.get_api()
        try:
            txs = api.get_txs(address)
            transactions = []
            for tx_info_list in txs:
                tx_info = tx_info_list.get(Currencies.eth)
                if not tx_info:
                    continue
                value = tx_info.get('amount')

                # Process transaction types
                if tx_info.get('direction') == 'outgoing':
                    # Transaction is from this address, so it is a withdraw
                    value = -value

                if tx_info.get('type') != 'normal':
                    continue

                from_addr = list(tx_info.get('from_address'))[0]
                if cls.are_addresses_equal(
                    from_addr, '0x70Fd2842096f451150c5748a30e39b64e35A3CdF'
                ) or cls.are_addresses_equal(
                    from_addr, '0x491fe5F4724e642C90372B0B95b60c4aC8d13F1c'
                ) or cls.are_addresses_equal(
                    from_addr, '0xB256caa23992e461E277CfA44a2FD72E2d6d2344'
                ) or cls.are_addresses_equal(
                    from_addr, '0x06cC26db08674CbD9FF4d52444712E23cA3d046d'
                ):
                    value = Decimal('0')

                transactions.append(Transaction(
                    address=address,
                    from_address=tx_info.get('from_address'),
                    hash=tx_info.get('hash'),
                    timestamp=tx_info.get('date'),
                    value=value,
                    confirmations=int(tx_info.get('confirmations') or 0),
                    is_double_spend=False,
                    block=tx_info.get('raw').get('blockHeight'),
                    details=tx_info,
                ))
            return transactions
        except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut) as error:
            if raise_error:
                raise error
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
            return []


class EthereumBlockchainWallet(GeneralBlockchainWallet):
    currency = Currencies.eth
    coin_type = 60

    def pub_key_to_address(self, pub_key):
        from web3 import Web3

        # First uncompress public_key from compressed one.
        uncompressed_pub = keys.PublicKey.from_compressed_bytes(pub_key)
        address = Web3.sha3(hexstr=HexStr(uncompressed_pub))[-20:]
        return Web3.toHex(address)
