import concurrent.futures
import copy
import time
from typing import Callable
from functools import partial

from django.conf import settings
from django.core.cache import cache

from exchange.base.logging import report_event
from exchange.blockchain.abstractـexplorer import AbstractBlockchainExplorer
from exchange.blockchain.explorer_original import \
    BlockchainExplorer as OriginalBlockchainExplorer
from exchange.blockchain.service_based import ServiceBasedExplorer
from exchange.blockchain.service_based.convertors import \
    are_transaction_objects_equal
from exchange.blockchain.service_based.logging import logger
from exchange.blockchain.utils import BlockchainUtilsMixin
from exchange.blockchain.validators import validate_crypto_address_v2

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

report_event = partial(report_event, level='warning')


def log_wrapper(func: Callable, params: dict):
    start_time = time.monotonic()
    convert_class_to_log_name = {
        'BlockchainExplorer': '---submodule---',
        'ServiceBasedExplorer': '---service_based---'
    }
    method_name = func.__name__
    class_name = convert_class_to_log_name[func.__self__.__name__]
    logger.info(f'Running of {method_name} from {class_name} by these arguments: {params}')
    try:
        result = func(**params)
        logger.info(f'{class_name}: elapsed time of {method_name}: {time.monotonic() - start_time} seconds\n')
        return result
    except Exception as e:
        logger.warning(f'Exception of {class_name} occurred: {e}')
        if settings.BLOCKCHAIN_SERVER:
            report_event(f'Exception of {class_name} occurred')


def run_two_func_concurrent(func1: Callable, func2: Callable, func1_params_dict: dict, func2_params_dict: dict):
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_one = executor.submit(log_wrapper, func1, func1_params_dict)
        future_two = executor.submit(log_wrapper, func2, func2_params_dict)

        concurrent.futures.wait([future_two, future_one])
        # Collect results when ready
        result_one = future_one.result()
        result_two = future_two.result()
        return [result_one, result_two]


class BlockchainExplorer(AbstractBlockchainExplorer):
    """
    Purpose of this class is compare the results of service-base and submodule methods so that leave appropriate log
    """
    TX_DETAILS_TESTING_NETWORKS = []
    TX_DETAILS_TESTED_NETWORKS = ['ONE', 'TON', 'TRX']
    BALANCE_TESTING_NETWORKS = []
    BALANCE_TESTED_NETWORKS = []
    WALLET_TXS_TESTING_NETWORKS = ['EOS', 'HBAR', 'TRX']
    WALLET_TXS_TESTED_NETWORKS = ['ADA', 'ALGO', 'APT', 'ARB', 'ATOM', 'AVAX', 'BASE', 'BCH', 'BSC', 'BTC', 'DOGE',
                                  'DOT', 'EGLD', 'ENJ', 'FIL', 'FLOW', 'LTC', 'MATIC', 'SONIC']
    BLOCK_TXS_TESTING_NETWORKS = []
    BLOCK_TXS_TESTED_NETWORKS = ['ADA', 'ALGO', 'APT', 'ARB', 'AVAX', 'BASE', 'BCH', 'BSC', 'BTC', 'DOGE', 'DOT',
                                 'EGLD', 'ENJ', 'ETC', 'ETH', 'FIL', 'FLOW', 'FTM', 'LTC', 'MATIC', 'NEAR', 'ONE',
                                 'SOL', 'SONIC', 'TRX', 'XMR', 'XTZ']
    ONLY_SUBMODULE = settings.IS_EXPLORER_WRAPPER_USES_ONLY_SUBMODULE
    RESULTS_NOT_EQUAL_ERROR_MESSAGE = "Results of submodule and service-base are not equal !! {}\n"

    @classmethod
    def get_wallet_ata(cls, address, currency):
        return cls._get_value_from_service_base(
            'get_ata',
            address=address,
            currency=currency,
        )

    @classmethod
    def get_transactions_details(cls, tx_hashes, network, currency=None, api_name=None, raise_error=True):
        cls._validate_tested_networks(cls.TX_DETAILS_TESTING_NETWORKS, cls.TX_DETAILS_TESTED_NETWORKS)

        if cls._is_item_in_list(network, cls.TX_DETAILS_TESTED_NETWORKS) and not cls.ONLY_SUBMODULE:
            return cls._get_value_from_service_base(method_name='get_transactions_details', tx_hashes=tx_hashes,
                                                    network=network, currency=currency)

        elif not cls._is_item_in_list(network, cls.TX_DETAILS_TESTING_NETWORKS) or cls.ONLY_SUBMODULE:
            return OriginalBlockchainExplorer.get_transactions_details(tx_hashes=tx_hashes, network=network,
                                                                       currency=currency,
                                                                       api_name=api_name,
                                                                       raise_error=False)

        submodule_result, service_based_result = run_two_func_concurrent(
            OriginalBlockchainExplorer.get_transactions_details,
            ServiceBasedExplorer.get_transactions_details,
            func1_params_dict={'tx_hashes': tx_hashes,
                               'network': network,
                               'currency': currency,
                               'api_name': api_name,
                               'raise_error': raise_error},
            func2_params_dict={'tx_hashes': tx_hashes,
                               'network': network,
                               'currency': currency})

        if not service_based_result and not submodule_result:
            return submodule_result

        if (not service_based_result and submodule_result) or (
                service_based_result and not submodule_result):
            return submodule_result

        submodule_result_copy = copy.deepcopy(submodule_result)
        service_based_result_copy = copy.deepcopy(service_based_result)

        # Synchronizing responses
        # below .copy() is for avoiding this error: "RuntimeError: dictionary changed size during iteration"
        for tx_hash, tx_detail in submodule_result_copy.copy().items():
            if not tx_detail.get('transfers') and not (tx_detail.get('inputs') or tx_detail.get('outputs')):
                submodule_result_copy.pop(tx_hash)

        for (sub_mod_tx_hash, sub_mod_tx_detail), (service_tx_hash, service_tx_detail) \
                in zip(submodule_result_copy.items(), service_based_result_copy.items()):

            critical_keys = ['hash', 'success', 'is_valid', 'transfers', 'block', 'fees', 'memo', 'confirmations',
                             'date', 'inputs', 'outputs']
            submodule_result_copy[sub_mod_tx_hash] = {key: sub_mod_tx_detail.get(key, None) for key in critical_keys}
            service_based_result_copy[service_tx_hash] = {key: service_tx_detail.get(key, None) for key in
                                                          critical_keys}
            if submodule_result_copy[sub_mod_tx_hash].get('transfers', None):
                for transfer in submodule_result_copy[sub_mod_tx_hash]['transfers']:
                    transfer.pop('type') if transfer.get('type') else None

        if not BlockchainUtilsMixin.compare_dicts_without_order(submodule_result_copy, service_based_result_copy):
            if settings.BLOCKCHAIN_SERVER:
                report_event(cls.RESULTS_NOT_EQUAL_ERROR_MESSAGE.format(
                    f"get_transactions_details-{network}-{tx_hashes}, '---service_based---': {service_based_result}, "
                    f"---submodule---: {submodule_result}"))
            logger.warning(cls.RESULTS_NOT_EQUAL_ERROR_MESSAGE.format(
                f"get_transactions_details-{network}-{tx_hashes}, '---service_based---': {service_based_result}, "
                f"---submodule---: {submodule_result}"))
        return submodule_result

    @classmethod
    def get_wallets_balance(cls, address_list, currency, api_name=None, raise_error=True):
        cls._validate_tested_networks(cls.BALANCE_TESTING_NETWORKS, cls.BALANCE_TESTED_NETWORKS)

        if cls.ONLY_SUBMODULE:
            return OriginalBlockchainExplorer.get_wallets_balance(address_list=address_list,
                                                                  currency=currency,
                                                                  api_name=api_name,
                                                                  raise_error=False)
        keys_to_compare = ['address', 'balance', 'received', 'sent', 'rewarded']

        categorize_addresses = cls._categorize_addresses(address_list, currency)
        not_listed_networks = categorize_addresses.get('not_listed_networks')
        testing_networks = categorize_addresses.get('testing_networks')
        tested_networks = categorize_addresses.get('tested_networks')
        tested_networks_result = cls._get_value_from_service_base(method_name='get_wallets_balance',
                                                                  address_list=tested_networks,
                                                                  currency=currency) or {}
        not_listed_networks_result = OriginalBlockchainExplorer.get_wallets_balance(address_list=not_listed_networks,
                                                                                    currency=currency)

        if not testing_networks:
            return {**tested_networks_result, **not_listed_networks_result}

        submodule_testing, service_based_testing = run_two_func_concurrent(
            OriginalBlockchainExplorer.get_wallets_balance,
            ServiceBasedExplorer.get_wallets_balance,
            func1_params_dict={
                'address_list': testing_networks,
                'currency': currency},
            func2_params_dict={
                'address_list': testing_networks,
                'currency': currency})

        if not submodule_testing and not service_based_testing:
            return {**tested_networks_result, **not_listed_networks_result}

        if (not service_based_testing and submodule_testing) or (service_based_testing and not submodule_testing):
            return {**not_listed_networks_result, **submodule_testing, **tested_networks_result}

        for bc_currency, bc_balances in submodule_testing.items():
            sb_balances = service_based_testing[bc_currency]
            for bc_balance, sb_balance in zip(bc_balances, sb_balances):
                if not any(filter(lambda b: bc_balance[b] == sb_balance[b], keys_to_compare)):
                    if settings.BLOCKCHAIN_SERVER:
                        report_event(cls.RESULTS_NOT_EQUAL_ERROR_MESSAGE.format(
                            f"get_wallets_balance-{address_list}-{currency}, "
                            f"'---service_based---': {service_based_testing}, ---submodule---: {submodule_testing}"))
                    logger.warning(cls.RESULTS_NOT_EQUAL_ERROR_MESSAGE.format(
                        f"get_wallets_balance-{address_list}-{currency}, "
                        f"'---service_based---': {service_based_testing}, ---submodule---: {submodule_testing}"))
                    break
        return {**not_listed_networks_result, **submodule_testing, **tested_networks_result}

    @classmethod
    def _categorize_addresses(cls, address_list, currency):
        if not isinstance(address_list, dict):
            address_list = OriginalBlockchainExplorer.to_address_list_per_network(
                address_list, currency
            )

        tested_networks = {}
        testing_networks = {}
        not_listed_networks = {}

        for key, value in address_list.items():
            if cls._is_item_in_list(key, cls.BALANCE_TESTED_NETWORKS):
                tested_networks[key] = value
            elif cls._is_item_in_list(key, cls.BALANCE_TESTING_NETWORKS):
                testing_networks[key] = value
            else:
                not_listed_networks[key] = value
        return {
            'tested_networks': tested_networks,
            'testing_networks': testing_networks,
            'not_listed_networks': not_listed_networks,
        }

    @classmethod
    def get_wallet_transactions(cls, address, currency, network=None,
                                api_name=None, raise_error=True, tx_direction_filter='', contract_address=None):
        cls._validate_tested_networks(cls.WALLET_TXS_TESTING_NETWORKS, cls.WALLET_TXS_TESTED_NETWORKS)

        if network == 'ONE' or currency == Currencies.one:
            _, network_based_on_address = validate_crypto_address_v2(address, currency=Currencies.eth,
                                                                     network='ETH')
        else:
            _, network_based_on_address = validate_crypto_address_v2(address, currency)
        if network is None:
            network = network_based_on_address

        if cls._is_item_in_list(network, cls.WALLET_TXS_TESTED_NETWORKS) and not cls.ONLY_SUBMODULE:
            return cls._get_value_from_service_base(method_name='get_wallet_transactions',
                                                    address=address,
                                                    currency=currency,
                                                    network=network,
                                                    contract_address=contract_address,
                                                    tx_direction_filter=tx_direction_filter)

        elif not cls._is_item_in_list(network, cls.WALLET_TXS_TESTING_NETWORKS) or cls.ONLY_SUBMODULE:
            return OriginalBlockchainExplorer.get_wallet_transactions(address=address, currency=currency,
                                                                      network=network,
                                                                      api_name=api_name,
                                                                      tx_direction_filter=tx_direction_filter,
                                                                      contract_address=contract_address,
                                                                      raise_error=False)
        submodule_result, service_based_result = run_two_func_concurrent(
            OriginalBlockchainExplorer.get_wallet_transactions,
            ServiceBasedExplorer.get_wallet_transactions,
            func1_params_dict={
                'address': address,
                'currency': currency,
                'network': network,
                'api_name': api_name,
                'tx_direction_filter': tx_direction_filter,
                'contract_address': contract_address,
                'raise_error': raise_error
            },
            func2_params_dict={
                'address': address,
                'currency': currency,
                'network': network,
                'contract_address': contract_address,
                'tx_direction_filter': tx_direction_filter
            })

        if not submodule_result and not service_based_result:
            return submodule_result

        if (not service_based_result and submodule_result) or (service_based_result and not submodule_result):
            return submodule_result

        if not are_transaction_objects_equal(submodule_result[currency], service_based_result[currency]):
            if settings.BLOCKCHAIN_SERVER:
                report_event(cls.RESULTS_NOT_EQUAL_ERROR_MESSAGE.format(
                    f"get_wallet_transactions-{network}-{address}-{currency}"))
            logger.warning(cls.RESULTS_NOT_EQUAL_ERROR_MESSAGE.format(
                f"get_wallet_transactions-{network}-{address}-{currency}"))
        return submodule_result

    @classmethod
    def get_latest_block_addresses(cls, network, after_block_number=None, to_block_number=None, include_inputs=False,
                                   include_info=True, raise_error=True):
        cls._validate_tested_networks(cls.BLOCK_TXS_TESTING_NETWORKS, cls.BLOCK_TXS_TESTED_NETWORKS)

        if cls._is_item_in_list(network, cls.BLOCK_TXS_TESTED_NETWORKS) and not cls.ONLY_SUBMODULE:
            return cls._get_value_from_service_base(method_name='get_latest_block_addresses',
                                                    network=network,
                                                    after_block_number=after_block_number,
                                                    to_block_number=to_block_number,
                                                    include_inputs=include_inputs,
                                                    include_info=include_info)

        elif not cls._is_item_in_list(network, cls.BLOCK_TXS_TESTING_NETWORKS) or cls.ONLY_SUBMODULE:
            return OriginalBlockchainExplorer.get_latest_block_addresses(network=network,
                                                                         after_block_number=after_block_number,
                                                                         to_block_number=to_block_number,
                                                                         include_inputs=include_inputs,
                                                                         include_info=include_info,
                                                                         raise_error=False)

        if not to_block_number:
            try:
                to_block_number = ServiceBasedExplorer.get_block_head(network)
                latest_block_height_processed = cache.get(f'latest_block_height_processed_{network.lower()}')
                if latest_block_height_processed >= to_block_number:
                    return None
            except Exception as e:
                logger.warning(f'An exception occurred within the service-base layer')
                if settings.BLOCKCHAIN_SERVER:
                    report_event(f'An exception occurred within the service-base layer: {e}')

        submodule_result, service_based_result = run_two_func_concurrent(
            OriginalBlockchainExplorer.get_latest_block_addresses,
            ServiceBasedExplorer.get_latest_block_addresses,
            func1_params_dict={
                'network': network,
                'after_block_number': after_block_number,
                'to_block_number': to_block_number,
                'include_inputs': include_inputs,
                'include_info': include_info,
                'raise_error': raise_error
            },
            func2_params_dict={
                'network': network,
                'after_block_number': after_block_number,
                'to_block_number': to_block_number,
                'include_inputs': include_inputs,
                'include_info': include_info
            })
        if (not service_based_result and submodule_result) or (service_based_result and not submodule_result):
            return submodule_result

        elif not submodule_result and not service_based_result:
            return submodule_result

        for submodule, service_based in zip(submodule_result[::-1], service_based_result[::-1]):
            if not BlockchainUtilsMixin.compare_dicts_without_order(submodule, service_based):
                if settings.BLOCKCHAIN_SERVER:
                    report_event(cls.RESULTS_NOT_EQUAL_ERROR_MESSAGE.format(f"get_latest_block_addresses-{network}"))
                logger.warning(cls.RESULTS_NOT_EQUAL_ERROR_MESSAGE.format(f"get_latest_block_addresses-{network}"))
                break
        return submodule_result

    @classmethod
    def _validate_tested_networks(cls, testing: list, tested: list):
        if set(testing).intersection(set(tested)):
            raise ValueError(f'Networks inside of {tested} and {testing} lists should not be common.')

    @classmethod
    def _is_item_in_list(cls, network: str, network_list: list) -> bool:
        return any(network.casefold() == item.casefold() for item in network_list)

    @classmethod
    def _get_value_from_service_base(cls, method_name: str, **kwargs):
        method_names = [
            'get_latest_block_addresses',
            'get_wallet_transactions',
            'get_transactions_details',
            'get_wallets_balance',
            'get_ata',
        ]
        if method_name not in method_names:
            raise TypeError(f"You should set method_name between this list: {method_name}")
        try:
            method = getattr(ServiceBasedExplorer, method_name)
            return method(**kwargs)
        except Exception as e:
            logger.warning(f'An exception occurred within the service-base layer: {e}')
            if settings.BLOCKCHAIN_SERVER:
                report_event(f'An exception occurred within the service-base layer')
