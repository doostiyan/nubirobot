import random
import time
from collections import defaultdict
from decimal import Decimal

import coinaddrvalidator
from django.conf import settings
from exchange.base.connections import get_geth
from exchange.base.logging import log_event, report_exception
from exchange.base.parsers import parse_utc_timestamp
from exchange.blockchain.api.eth.eth_blockbook import EthereumBlockbookAPI
from exchange.blockchain.contracts_conf import ERC20_contract_currency, ERC20_contract_info
from exchange.blockchain.metrics import metric_incr
from exchange.blockchain.models import BaseBlockchainInspector, Transaction
from exchange.blockchain.utils import AddressNotExist, APIError, BadGateway, GatewayTimeOut, InternalServerError


class Erc20BlockchainInspector(BaseBlockchainInspector):
    """ Based on: etherscan.io
        Rate limit: ? requests/sec
    """
    TESTNET_ENABLED = False
    network = 'testnet' if TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS else 'mainnet'
    currency_list = None

    USE_EXPLORER_BALANCE_ETH = 'etherscan'  # Available options: etherscan, fullnode, blockbook, web3
    USE_EXPLORER_TRANSACTION_ETH = 'etherscan'  # Available options: etherscan, blockbook

    @classmethod
    def erc20_contract_currency_list(cls, network=None):
        if network is None:
            network = cls.network
        return ERC20_contract_currency[network]

    @classmethod
    def erc20_contract_info_list(cls, network=None):
        if network is None:
            network = cls.network
        if cls.currency_list is not None:
            currency_subset = {currency: ERC20_contract_info[network][currency] for currency in cls.currency_list if
                               currency in ERC20_contract_info[network]}
            return currency_subset
        return ERC20_contract_info[network]

    @classmethod
    def are_erc20_addresses_equal(cls, addr1, addr2):
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
    def get_transaction_details_eth(cls, tx_hash):
        tx_details = None
        try:
            tx_details = EthereumBlockbookAPI.get_api(network=cls.network).get_tx_details(tx_hash=tx_hash)
            tx_details['transfers'] = tx_details.get('transfers').get(cls.currency) or []
        except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut, Exception):
            pass
        return tx_details

    @classmethod
    def get_wallets_balance_eth(cls, address_list):
        if cls.USE_EXPLORER_BALANCE_ETH == 'etherscan':
            return cls.get_wallets_balance_eth_etherscan(address_list)
        if cls.USE_EXPLORER_BALANCE_ETH == 'fullnode':
            return cls.get_wallets_balance_eth_fullnode(address_list)
        if cls.USE_EXPLORER_BALANCE_ETH == 'blockbook':
            return cls.get_wallets_balance_eth_blockbook(address_list)
        if cls.USE_EXPLORER_BALANCE_ETH == 'web3':
            return cls.get_wallets_balance_eth_web3(address_list)
        return cls.get_wallets_balance_eth_etherscan(address_list)

    @classmethod
    def get_wallets_balance_eth_fullnode(cls, address_list, raise_error=False):
        try:
            geth = get_geth()
        except Exception as e:
            if raise_error:
                raise e
            return
        balances = defaultdict(list)
        for addr in address_list:
            original_addr = addr
            if addr.startswith('0x'):
                addr = addr[2:]
            for currency, contract_info in cls.erc20_contract_info_list().items():
                contract_addr = contract_info['address']
                params = {
                    'to': contract_addr,
                    'data': '0x70a08231000000000000000000000000{}'.format(addr)
                }
                try:
                    res = geth.request('eth_call', [params, 'latest'])
                except Exception as e:
                    if raise_error:
                        raise e
                    metric_incr('api_errors_count', labels=['eth', 'full_node'])
                    print('Failed to get ERC20 wallet balance from Geth: {}, {}'.format(addr, str(e)))
                    continue
                error = res.get('error')
                result = res.get('result')
                if error or not result or result == '0x':
                    print('Failed to get ERC20 wallet balance from Geth: {}, {}'.format(addr, str(res)))
                    # report_event('Geth Response Error')
                    continue
                balance = int(result, 0) / Decimal(f'1e{contract_info["decimals"]}')
                balance = balance.quantize(Decimal('1e-8'))
                balances[currency].append({
                    'address': original_addr,
                    'received': balance,
                    'sent': Decimal('0'),
                    'rewarded': Decimal('0'),
                    'balance': balance,
                })
        return balances

    @classmethod
    def get_wallets_balance_eth_etherscan(cls, address_list, raise_error=False):
        """
            Note: in list of addresses, each address should include the initial "0x"
            Note: this function only returns net balances for each address and not sent/etc. details
        """
        balances = defaultdict(list)
        for address in address_list:
            if not bool(coinaddrvalidator.validate('eth', address.lower())):
                print('\t[InvalidETHAddress]')
                continue
            if cls.TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS:
                explorer_url = 'https://api-ropsten.etherscan.io/'
            else:
                explorer_url = 'https://api.etherscan.io/'
            explorer_url = explorer_url + 'api?module=account&action=tokenbalance'
            for currency, contract_info in cls.erc20_contract_info_list().items():
                time.sleep(0.1)
                try:
                    api_key = random.choice(settings.ETHERSCAN_API_KEYS)
                    url = explorer_url + f'&contractaddress={contract_info["address"]}&address={address}&tag=latest&apikey={api_key}'
                    api_response = cls.get_session().get(url, timeout=25)
                    api_response.raise_for_status()
                except Exception as e:
                    if raise_error:
                        raise e
                    metric_incr('api_errors_count', labels=['eth', 'etherscan'])
                    print('Failed to get ERC20 wallet balance from API: {}'.format(str(e)))
                    return None
                info = api_response.json()
                if info['status'] != '1':
                    # report_event('Etherscan API Error')
                    print('Failed to get ERC20 wallet balance from API: {}'.format(info['result']))
                    return None
                balance = Decimal(info['result'] or '0') / Decimal(f'1e{contract_info["decimals"]}')
                # TODO: currently we only return balance and set other fields to zero
                balances[currency].append({
                    'address': address,
                    'received': balance,
                    'sent': Decimal('0'),
                    'rewarded': Decimal('0'),
                    'balance': balance,
                })

        return balances

    @classmethod
    def get_wallets_balance_eth_blockbook(cls, address_list, raise_error=False):
        if not address_list:
            return []
        api = EthereumBlockbookAPI.get_api()
        balances = defaultdict(list)
        for address in address_list:
            try:
                response = api.get_balance(address)
                for currency, contract_info in cls.erc20_contract_info_list().items():
                    tx_info = response.get(currency)
                    if not tx_info:
                        continue
                    balance = tx_info.get('amount', Decimal('0'))
                    unconfirmed_balance = tx_info.get('unconfirmed_amount', Decimal('0'))
                    balances[currency].append({
                        'address': address,
                        'received': balance,
                        'sent': Decimal('0'),
                        'balance': balance,
                        'unconfirmed': unconfirmed_balance,
                    })
            except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut) as error:
                if raise_error:
                    raise error
                metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
                continue
        return balances

    @classmethod
    def get_wallets_balance_eth_web3(cls, address_list, raise_error=False):
        from exchange.blockchain.api.eth.eth_web3 import ETHWeb3
        if not address_list:
            return []
        api = ETHWeb3.get_api()
        balances = defaultdict(list)
        for address in address_list:
            try:
                for currency, contract_info in cls.erc20_contract_info_list().items():
                    response = api.get_token_balance(address, contract_info)
                    if not response:
                        continue
                    balance = response.get('amount', Decimal('0'))
                    unconfirmed_balance = response.get('unconfirmed_amount', Decimal('0'))
                    balances[currency].append({
                        'address': address,
                        'received': balance,
                        'sent': Decimal('0'),
                        'balance': balance,
                        'unconfirmed': unconfirmed_balance,
                    })
            except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut) as error:
                if raise_error:
                    raise error
                metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
                continue
        return balances

    @classmethod
    def get_wallet_transactions_eth(cls, address_list):
        if cls.USE_EXPLORER_TRANSACTION_ETH == 'etherscan':
            return cls.get_wallet_transactions_eth_etherscan(address_list)
        if cls.USE_EXPLORER_TRANSACTION_ETH == 'blockbook':
            return cls.get_wallet_transactions_eth_blockbook(address_list)
        return cls.get_wallet_transactions_eth_blockbook(address_list)

    @classmethod
    def get_wallet_transactions_eth_etherscan(cls, address, raise_error=False):
        # Check address validity
        if not address or len(address) <= 10:
            return None
        if not address.startswith('0x'):
            address = '0x' + address
        if not bool(coinaddrvalidator.validate('eth', address.lower())):
            print('\t[InvalidETHAddress]')
            return None

        # Get data from API
        if cls.TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS:
            explorer_url = 'https://api-ropsten.etherscan.io/'
        else:
            explorer_url = 'https://api.etherscan.io/'
        explorer_url = explorer_url + 'api?module=account&action=tokentx'
        transactions = defaultdict(list)
        for currency, contract_info in cls.erc20_contract_info_list().items():
            time.sleep(0.1)
            try:
                api_key = random.choice(settings.ETHERSCAN_API_KEYS)
                url = explorer_url + f'&contractaddress={contract_info["address"]}&address={address}&page=1&offset=50&sort=desc&apikey={api_key}'
                api_response = cls.get_session().get(url, timeout=60)
                api_response.raise_for_status()
            except Exception as e:
                if raise_error:
                    raise e
                metric_incr('api_errors_count', labels=['eth', 'etherscan'])
                print('Failed to get ERC20 wallet transactions from API: {}'.format(str(e)))
                continue
            info = api_response.json()
            if info.get('message') != 'OK':
                # report_event(info)
                continue
            info = info.get('result')
            # Parse transactions
            for tx_info in info:
                value = Decimal(str(round(int(tx_info.get('value', 0))))) / Decimal(f'1e{contract_info["decimals"]}')

                # Process transaction types
                if cls.are_erc20_addresses_equal(tx_info.get('from'), address):
                    # Transaction is from this address, so it is a withdraw
                    value = -value
                elif not cls.are_erc20_addresses_equal(tx_info.get('to'), address):
                    # Transaction is not to this address, and is not a withdraw, so no deposit should be made
                    #  this is a special case and should not happen, so we ignore such special transaction (value will be zero)
                    value = Decimal('0')
                elif cls.are_erc20_addresses_equal(tx_info.get('from'),
                                                   '0x70Fd2842096f451150c5748a30e39b64e35A3CdF') or cls.are_erc20_addresses_equal(
                    tx_info.get('from'), '0x491fe5F4724e642C90372B0B95b60c4aC8d13F1c') or cls.are_erc20_addresses_equal(
                    tx_info.get('from'), '0xB256caa23992e461E277CfA44a2FD72E2d6d2344') or cls.are_erc20_addresses_equal(
                    tx_info.get('from'), '0x06cC26db08674CbD9FF4d52444712E23cA3d046d'):
                    value = Decimal('0')
                if contract_info.get('from_block', 0) >= int(tx_info.get('blockNumber')):
                    continue

                transactions[currency].append(Transaction(
                    address=address,
                    from_address=[tx_info.get('from')],
                    hash=tx_info.get('hash'),
                    timestamp=parse_utc_timestamp(tx_info.get('timeStamp')),
                    value=value,
                    confirmations=int(tx_info.get('confirmations', 0)),
                    is_double_spend=False,  # TODO: check for double spends for ETH
                    details=tx_info,
                ))
        return transactions

    @classmethod
    def get_wallet_transactions_eth_blockbook(cls, address, raise_error=False):
        api = EthereumBlockbookAPI.get_api()
        try:
            txs = api.get_txs(address, limit=40)
            transactions = defaultdict(list)
            for tx_info_list in txs:
                for currency, contract_info in cls.erc20_contract_info_list().items():
                    tx_info = tx_info_list.get(currency)
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
                    if cls.are_erc20_addresses_equal(
                            from_addr, '0x70Fd2842096f451150c5748a30e39b64e35A3CdF'
                    ) or cls.are_erc20_addresses_equal(
                        from_addr, '0x491fe5F4724e642C90372B0B95b60c4aC8d13F1c'
                    ) or cls.are_erc20_addresses_equal(
                        from_addr, '0xB256caa23992e461E277CfA44a2FD72E2d6d2344'
                    ) or cls.are_erc20_addresses_equal(
                        from_addr, '0x06cC26db08674CbD9FF4d52444712E23cA3d046d'
                    ):
                        value = Decimal('0')
                    if contract_info.get('from_block', 0) >= tx_info.get('raw').get('blockHeight'):
                        continue
                    transactions[currency].append(Transaction(
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
            return None
