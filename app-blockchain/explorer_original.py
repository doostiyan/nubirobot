import concurrent.futures
import time
from collections import defaultdict
from decimal import Decimal

from django.conf import settings
from requests import ReadTimeout
from requests.exceptions import ProxyError, SSLError

from exchange.blockchain.api.general.explorer_interface import ExplorerInterface
from exchange.blockchain.api.general.utilities import Utilities
from exchange.blockchain.apis_conf import APIS_CLASSES, APIS_CONF
from exchange.blockchain.contracts_conf import CONTRACT_INFO
from exchange.blockchain.metrics import metric_incr
from exchange.blockchain.models import MAIN_TOKEN_CURRENCIES_INFO, CurrenciesNetworkName, Transaction
from exchange.blockchain.service_based.logging import logger
from exchange.blockchain.utils import APIError, RateLimitError
from exchange.blockchain.validators import validate_crypto_address_v2
from .abstractـexplorer import AbstractBlockchainExplorer
from ..base.logging import report_exception

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies


class BlockchainExplorer(AbstractBlockchainExplorer):

    @classmethod
    def exception_handler(cls, api, api_for_metric, error, method_name):
        error_type = error.__class__.__name__
        if settings.USE_PROMETHEUS_CLIENT:
            labels = {
                'network': api.symbol,
                'api_name': api_for_metric,
                'error_type': error_type,
                'method': method_name
            }
        else:
            labels = [api.symbol, api_for_metric, error_type, method_name]
        metric_incr('api_errors_count', labels)
        logger.exception("Exception occurred")

    @classmethod
    def get_token_wallet_balance(cls, address, network, token_address, api_name=None, is_provider_check=False,
                                 raise_error=False):
        api_name = api_name or APIS_CONF[network]['get_balances']
        method_name = 'GetTokenWalletBalance'
        api = APIS_CLASSES[api_name].get_api(is_provider_check=is_provider_check)
        currency, _ = api.contract_currency(token_address)
        contract_info = api.contract_info(currency, token_address)
        try:
            balance = api.get_token_balance(address, contract_info)
            return {
                currency: cls.parse_balance(balance, address)
            }
        except (APIError, ReadTimeout, ProxyError, SSLError) as error:
            if isinstance(api, ExplorerInterface):
                api_for_metric = api.token_balance_apis[0].__name__
            else:
                api_for_metric = api.__class__.__name__
            cls.exception_handler(api, api_for_metric, error, method_name)
            if raise_error:
                raise error

        except Exception as error:
            if raise_error:
                raise error

            report_exception()

    @classmethod
    def get_wallets_balance(cls, address_list, currency, api_name=None, is_provider_check=False, raise_error=False):
        address_list_per_network = address_list
        method_name = 'GetWalletsBalance'
        if not isinstance(address_list, dict):
            address_list_per_network = cls.to_address_list_per_network(address_list, currency)
        balances = defaultdict(list)
        for network in address_list_per_network:
            address_list = address_list_per_network.get(network)
            api_name = api_name or APIS_CONF[network]['get_balances']
            api = APIS_CLASSES[api_name].get_api(is_provider_check=is_provider_check)
            if isinstance(api, ExplorerInterface):
                api_for_metric = api.balance_apis[0].__name__
            else:
                api_for_metric = api.__class__.__name__
            if api.SUPPORT_GET_BALANCE_BATCH and not (
                    network in CONTRACT_INFO.keys() and f'{currency}-{network}' not in MAIN_TOKEN_CURRENCIES_INFO.keys()):
                try:
                    res = api.get_balances(address_list)
                    balances = cls.parse_balances(res, currency)
                except (APIError, ReadTimeout, ProxyError, SSLError) as error:
                    cls.exception_handler(api, api_for_metric, error, method_name)
                    if raise_error:
                        raise error
                    report_exception()

                except Exception as error:
                    cls.exception_handler(api, api_for_metric, error, method_name)
                    if raise_error:
                        raise error
                    report_exception()

                return balances

            for address in address_list:
                try:
                    if network in CONTRACT_INFO.keys() and f'{currency}-{network}' not in MAIN_TOKEN_CURRENCIES_INFO.keys():
                        if isinstance(api, ExplorerInterface):
                            api_for_metric = api.token_balance_apis[0].__name__
                        else:
                            api_for_metric = api.__class__.__name__
                        contract_info = CONTRACT_INFO.get(network).get('mainnet').get(currency)
                        if contract_info is None:
                            break
                        res = api.get_token_balance(address, contracts_info={currency: contract_info})
                    else:
                        res = api.get_balance(address)
                except (APIError, ReadTimeout, ProxyError, SSLError) as error:
                    cls.exception_handler(api, api_for_metric, error, method_name)
                    if raise_error:
                        raise error
                    report_exception()
                    continue
                except Exception as error:
                    cls.exception_handler(api, api_for_metric, error, method_name)
                    if raise_error:
                        raise error
                    report_exception()
                    continue

                new_balance = res.get(currency) if isinstance(res, dict) else None
                balance = new_balance or res
                if not balance:
                    continue
                balances[currency].append(cls.parse_balance(balance, address))
        return balances

    @classmethod
    def get_wallet_transactions(cls, address, currency, network=None, api_name=None, raise_error=False,
                                is_provider_check=False, tx_direction_filter='', contract_address=None,
                                start_date=None, end_date=None):
        address = Utilities.normalize_address(network, address)
        transactions = []
        if network == 'ONE' or currency == Currencies.one:
            is_valid, network_based_on_address = validate_crypto_address_v2(address, currency=Currencies.eth,
                                                                            network='ETH')
        else:
            is_valid, network_based_on_address = validate_crypto_address_v2(address, currency)
        if network is None:
            network = network_based_on_address
        method_name = 'GetWalletTransactions'
        api_name = api_name or APIS_CONF[network]['get_txs']
        api = APIS_CLASSES[api_name].get_api(is_provider_check=is_provider_check)
        if isinstance(api, ExplorerInterface):
            api_for_metric = api.address_txs_apis[0].__name__
        else:
            api_for_metric = api.__class__.__name__
        try:

            if (
                    network in CONTRACT_INFO.keys() and f'{currency}-{network}' not in MAIN_TOKEN_CURRENCIES_INFO.keys()) or contract_address:
                # contract addresses (and not native currency) - we should call token related functions
                contract_info = CONTRACT_INFO.get(network).get('mainnet').get(currency)
                if contract_address and contract_address in CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.keys():
                    contract_info = CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS[contract_address].get('info')
                if isinstance(api, ExplorerInterface):
                    txs = api.get_token_txs(address, contract_info=contract_info, start_date=start_date,
                                            direction=tx_direction_filter,end_date=end_date)
                else:
                    txs = api.get_token_txs(address, contract_info=contract_info)
                if isinstance(api, ExplorerInterface):
                    api_for_metric = api.token_txs_apis[0].__name__
                else:
                    api_for_metric = api.__class__.__name__
            else:
                if tx_direction_filter:
                    txs = api.get_txs(address, tx_direction_filter=tx_direction_filter)
                else:
                    txs = api.get_txs(address)
            for item in txs:
                tx = item.get(currency) if len(item) == 1 else item
                if not tx:
                    continue
                if tx.get('direction') == 'incoming' and tx.get('from_address') == tx.get('to_address'):
                    continue
                if tx.get('direction') == 'incoming' and type(tx.get('to_address')) == str and tx.get(
                        'to_address').casefold() != address.casefold():
                    continue
                value = tx.get('amount') if not isinstance(tx.get('amount'), dict) else tx.get('amount', {}).get(
                    'value', Decimal('0'))
                if tx.get('direction') == 'outgoing' and value > 0:
                    value = - value
                if abs(value) < api.min_valid_tx_amount:
                    value = Decimal('0')
                from_address = tx.get('from_address')
                list_from_address = []
                if from_address:
                    list_from_address = [from_address] if type(from_address) != list else from_address
                transaction = Transaction(
                    address=address,
                    from_address=list_from_address,
                    block=tx.get('block'),
                    hash=tx.get('hash'),
                    timestamp=tx.get('date'),
                    value=value,
                    confirmations=int(tx.get('confirmations') or 0),
                    is_double_spend=False,
                    details=tx.get('raw'),
                    tag=tx.get('memo', ''),
                    contract_address=contract_address or tx.get('contract_address'),
                )
                transactions.append(transaction)
            return {
                currency: transactions
            }
        except (APIError, ReadTimeout, ProxyError, SSLError) as error:
            cls.exception_handler(api, api_for_metric, error, method_name)
            if raise_error:
                raise error
        except Exception as error:
            cls.exception_handler(api, api_for_metric, error, method_name)
            if raise_error:
                raise error

    @classmethod
    def get_wallet_transactions_by_hash(cls, address, hashes, currency, network):
        transactions = []
        txs_details = cls.get_transactions_details(hashes, network)
        for tx_hash in hashes:
            tx_details = txs_details.get(tx_hash)
            if not txs_details:
                continue
            value = cls.get_transaction_value(tx_details, address, currency)

            transaction = Transaction(
                address=address,
                from_address=tx_details['from_address'],
                block=tx_details.get('block'),
                hash=tx_details.get('hash'),
                timestamp=tx_details.get('date'),
                value=value,
                confirmations=int(tx_details.get('confirmations') or 0),
                is_double_spend=False,
                details=tx_details.get('raw'),
                tag=tx_details.get('memo') or ''
            )
            transactions.append(transaction)
        return {
            currency: transactions
        }

    @classmethod
    def get_transaction_value(cls, tx_details, address, currency):
        addresses = address if type(address) is list else [address]
        value = Decimal('0')
        tx_details['from_address'] = []
        if tx_details.get('success'):
            for input_ in tx_details.get('inputs') or []:
                tx_details['from_address'].append(input_.get('address'))
                if input_.get('address') in addresses and input_.get('currency') == currency:
                    if input_.get('is_valid') is not False:
                        value = - input_.get('value')
                    break
            for output in tx_details.get('outputs') or []:
                if output.get('address') in addresses and output.get('currency') == currency:
                    if output.get('is_valid') is not False:
                        value += output.get('value')

            for transfer in tx_details.get('transfers') or []:
                if transfer.get('is_valid') is not False and transfer.get('currency') == currency:
                    if transfer.get('from') in addresses:
                        value = - transfer.get('value')
                        continue
                    if transfer.get('to') in addresses:
                        tx_details['from_address'].append(transfer.get('from'))
                        value = transfer.get('value')
        return value

    @classmethod
    def get_transactions_details(cls, tx_hashes, network, currency=None, api_name=None, is_provider_check=False,
                                 raise_error=False, retry_with_main_api=True):
        txs_details = {}
        method_name = 'GetTransactionsDetails'
        api_name = api_name or APIS_CONF[network]['txs_details']
        api_class = APIS_CLASSES[api_name].get_api(is_provider_check=is_provider_check)
        tx_hashes = Utilities.normalize_hash(network=network, currency=currency, tx_hashes=tx_hashes)

        if isinstance(api_class, ExplorerInterface):
            api_for_metric = api_class.tx_details_apis[0].__name__
        else:
            api_for_metric = api_class.__class__.__name__

        if (api_class.TRANSACTION_DETAILS_BATCH or
                (isinstance(api_class, ExplorerInterface) and api_class.tx_details_apis[0].TRANSACTION_DETAILS_BATCH)):
            try:
                txs_details = api_class.get_tx_details_batch(tx_hashes=tx_hashes)
            except (APIError, ReadTimeout, ProxyError, SSLError) as error:
                cls.exception_handler(api_class, api_for_metric, error, method_name)
                if raise_error:
                    raise error
                report_exception()

            except Exception as error:
                cls.exception_handler(api_class, api_for_metric, error, method_name)
                if raise_error:
                    raise error
                report_exception()

            return txs_details

        if currency and network in CONTRACT_INFO.keys() and f'{currency}-{network}' not in MAIN_TOKEN_CURRENCIES_INFO.keys():
            if isinstance(api_class, ExplorerInterface) and api_class.token_tx_details_apis and \
                    api_class.token_tx_details_apis[0].SUPPORT_GET_BATCH_TOKEN_TX_DETAILS:
                contract_info = CONTRACT_INFO.get(network).get('mainnet').get(currency)
                txs_details = api_class.get_batch_token_tx_details(hashes=tx_hashes, contract_info=contract_info)
                return txs_details

        def fetch_tx_details(tx_hash, is_retry=False):
            try:
                if currency and network in CONTRACT_INFO.keys() and f'{currency}-{network}' not in MAIN_TOKEN_CURRENCIES_INFO.keys():
                    try:
                        return {tx_hash: api_class.get_token_tx_details(tx_hash=tx_hash)}
                    except RateLimitError as err:
                        cls.exception_handler(api_class, api_for_metric, err, method_name)
                        time.sleep(1)

                        if not is_retry:  # this is to avoid infinite loop of rate limit exception and retry
                            return fetch_tx_details(tx_hash, is_retry=True)
                        else:
                            return {tx_hash: None}
                    except Exception as e:
                        cls.exception_handler(api_class, api_for_metric, e, method_name)
                        if retry_with_main_api:
                            return {tx_hash: api_class.get_tx_details(tx_hash=tx_hash)}
                        else:
                            return {tx_hash: None}
                else:
                    try:
                        return {tx_hash: api_class.get_tx_details(tx_hash=tx_hash)}
                    except RateLimitError as err:
                        cls.exception_handler(api_class, api_for_metric, err, method_name)
                        time.sleep(1)
                        if not is_retry:  # this is to avoid infinite loop of rate limit exception and retry
                            return fetch_tx_details(tx_hash, is_retry=True)
                        else:
                            return {tx_hash: None}
                    except Exception as e:
                        cls.exception_handler(api_class, api_for_metric, e, method_name)
                        return {tx_hash: None}

            except (APIError, ReadTimeout, ProxyError, SSLError) as e:
                cls.exception_handler(api_class, api_for_metric, e, method_name)
                return {tx_hash: None}
            except Exception as e:
                cls.exception_handler(api_class, api_for_metric, error, method_name)
                return {tx_hash: None}

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_to_tx = {executor.submit(fetch_tx_details, tx_hash): tx_hash for tx_hash in tx_hashes}
            for future in concurrent.futures.as_completed(future_to_tx):
                try:
                    result = future.result()
                    if result is not None:
                        txs_details.update(result)
                except Exception:
                    pass
        filtered_txs_details = {k: v for k, v in txs_details.items() if v is not None}
        return filtered_txs_details

    @classmethod
    def get_latest_block_addresses(cls, network, after_block_number=None, to_block_number=None, include_inputs=False,
                                   include_info=True, api_name=None, is_provider_check=False, raise_error=False):
        method_name = 'GetLatestBlockAddresses'
        api_name = api_name or APIS_CONF[network]['get_blocks_addresses']
        api_class = APIS_CLASSES[api_name].get_api(is_provider_check=is_provider_check)
        if isinstance(api_class, ExplorerInterface):
            api_for_metric = api_class.block_txs_apis[0].__name__
        else:
            api_for_metric = api_class.__class__.__name__
        # todo add log for provider name in all methods
        try:
            result = api_class.get_latest_block(
                after_block_number=after_block_number,
                to_block_number=to_block_number,
                include_inputs=include_inputs,
                include_info=include_info,
            )
            transactions_addresses, transactions_info, last_processed_block = result
            return transactions_addresses, transactions_info, last_processed_block
        except (APIError, ReadTimeout, ProxyError, SSLError) as error:
            cls.exception_handler(api_class, api_for_metric, error, method_name)
            if raise_error:
                raise error
            report_exception()
        except Exception as error:
            cls.exception_handler(api_class, api_for_metric, error, method_name)
            if raise_error:
                raise error
            report_exception()

    @classmethod
    def to_address_list_per_network(cls, address_list, currency):
        if not address_list or not currency:
            return {}
        address_list_per_network = {}
        for address in address_list:
            if isinstance(address, str):
                if currency == Currencies.one:
                    is_valid, network = validate_crypto_address_v2(address, currency=Currencies.eth)
                else:
                    is_valid, network = validate_crypto_address_v2(address, currency)
            elif isinstance(address, tuple):
                if currency == Currencies.one:
                    is_valid, network = validate_crypto_address_v2(address[0], currency=Currencies.eth,
                                                                   network='ETH')
                else:
                    is_valid, network = validate_crypto_address_v2(address[0], currency, network=address[1])
                address, network = address
            else:
                is_valid, network = (False, None)
            if is_valid:
                address_list_per_network.setdefault(network, []).append(address)
        return address_list_per_network

    @classmethod
    def parse_balances(cls, balances, currency):
        res = defaultdict(list)
        for balance in balances:
            balance = balance.get(currency)
            res[currency].append({
                'address': balance.get('address'),
                'received': balance.get('amount') or balance.get('balance') or Decimal('0.0'),
                'sent': Decimal('0'),
                'rewarded': Decimal('0'),
                'balance': balance.get('amount') or balance.get('balance') or Decimal('0.0'),
            })
        return res

    @classmethod
    def parse_balance(cls, balance, address):
        return {
            'address': address,
            'balance': balance.get('amount') or balance.get('balance') or Decimal('0.0'),
            'received': balance.get('amount') or balance.get('balance') or Decimal('0.0'),
            'sent': Decimal('0'),
            'rewarded': Decimal('0'),
        }

    @classmethod
    def get_block_head(cls, network, api_name=None, is_provider_check=False, raise_error=False):
        api_name = api_name or APIS_CONF[network]['get_blocks_addresses']
        method_name = 'GetBlockHead'
        api_class = APIS_CLASSES[api_name].get_api(is_provider_check=is_provider_check)
        if isinstance(api_class, ExplorerInterface):
            api_for_metric = (api_class.block_txs_apis or api_class.block_head_apis)[0].__name__
        else:
            api_for_metric = api_class.__class__.__name__
        try:
            return api_class.get_block_head()
        except (APIError, ReadTimeout, ProxyError, SSLError) as error:
            cls.exception_handler(api_class, api_for_metric, error, method_name)
            if raise_error:
                raise error
            report_exception()
        except Exception as error:
            cls.exception_handler(api_class, api_for_metric, error, method_name)
            if raise_error:
                raise error
            report_exception()
