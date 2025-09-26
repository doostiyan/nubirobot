from typing import List, Optional

from django.conf import settings
from django.core.cache import cache

from exchange.base.models import Currencies
from exchange.blockchain.models import Transaction, UTXO_BASED_NETWORKS
from exchange.blockchain.service_based.http_client import ServiceBasedHttpClient
from exchange.blockchain.validators import validate_crypto_address_v2
from exchange.blockchain.abstractـexplorer import AbstractBlockchainExplorer
from exchange.blockchain.utils import APIError

from .convertors import (
    convert_tx_details_to_dict,
    get_symbol_from_currency_code,
    convert_block_addresses,
    convert_block_tx_info,
    convert_transfer_tx_to_transaction,
    convert_all_wallet_balances_to_decimal, convert_utxo_based_tx_details_to_dict
)
from .logging import logger
from ..metrics import metric_set


class ServiceBasedExplorer(AbstractBlockchainExplorer):
    main_server_http_client = ServiceBasedHttpClient(settings.MAIN_SERVER_HTTP_CLIENT)
    diff_server_http_client = ServiceBasedHttpClient(settings.DIFF_SERVER_HTTP_CLIENT)

    @classmethod
    def get_transactions_details(
        cls,
        tx_hashes: List[str],
        network: str,
        currency: Optional[int],
        provider: Optional[str] = None,
        base_url: Optional[str] = None) -> dict:
        currency_symbol = get_symbol_from_currency_code(currency)
        tx_details = cls.diff_server_http_client.get_tx_details_batch(
            tx_hashes=tx_hashes,
            network=network,
            provider=provider,
            base_url=base_url,
            currency_symbol=currency_symbol
        )
        result = {}
        if tx_details:
            for tx in tx_details.get('transactions', []):
                if network in UTXO_BASED_NETWORKS:
                    result[tx.get('tx_hash')] = convert_utxo_based_tx_details_to_dict(tx, result.get(tx.get('tx_hash')))
                else:
                    result[tx.get('tx_hash')] = convert_tx_details_to_dict(tx, result.get(tx.get('tx_hash')))
        return result

    @classmethod
    def get_wallets_balance(cls, address_list: dict, currency: Currencies) -> dict:
        if not address_list or not currency:
            return {}
        network, addresses = next(iter(address_list.items()))
        currency_symbol = get_symbol_from_currency_code(currency)
        balances = cls.main_server_http_client.get_wallets_balance(
            network=network,
            currency_symbol=currency_symbol,
            addresses=addresses
        )
        balances = convert_all_wallet_balances_to_decimal(balances.get('wallet_balances'))
        return {currency: balances}

    @classmethod
    def get_wallet_transactions(cls, address, currency, network=None, contract_address=None, tx_direction_filter=''):
        if network is None:
            if network == 'ONE' or currency == Currencies.one:
                _, network = validate_crypto_address_v2(address, currency=Currencies.eth,
                                                        network='ETH')
            else:
                _, network = validate_crypto_address_v2(address, currency)
        currency_symbol = get_symbol_from_currency_code(currency)
        txs = cls.main_server_http_client.get_wallet_transactions(
            network=network,
            currency_symbol=currency_symbol,
            address=address,
            contract_address=contract_address,
            tx_direction_filter=tx_direction_filter
        )
        transactions = {}
        for tx in txs:
            converted_tx = convert_transfer_tx_to_transaction(tx)
            key = (converted_tx['hash'], converted_tx['value'])
            if key in transactions and network != 'TON':
                transactions[key]['from_address'].append(converted_tx['from_address'][0])
            else:
                transactions[key] = converted_tx
        transactions_list = [Transaction(**tx_data, **{'address': address}) for tx_data in
                             transactions.values()]
        return {currency: transactions_list}

    @classmethod
    def get_latest_block_addresses(cls, network, after_block_number=None, to_block_number=None, include_inputs=True,
                                   include_info=True):
        """
        calculate unprocessed block-height range and list all addresses in all transaction in all blocks in that range
        """
        max_height, min_height = cls.calculate_unprocessed_block_range(network, after_block_number, to_block_number)
        logger.info(
            f'Running get_latest_block_addresses from service-based with {min_height} to {max_height} block number')

        blocks_txs = cls.main_server_http_client.get_blocks_txs(network=network, after_block_number=min_height,
                                                                to_block_number=max_height)
        if blocks_txs.get('latest_processed_block'):
            metric_set(name='latest_block_processed', labels=[network.lower()], amount=blocks_txs.get('latest_processed_block'))
            cache.set(f'{settings.BLOCKCHAIN_CACHE_PREFIX}latest_block_height_processed_{network.lower()}',
                      blocks_txs.get('latest_processed_block'), 86400)

        return convert_block_addresses(blocks_txs.get('transactions'), include_inputs), convert_block_tx_info(
            blocks_txs.get('transactions'), include_inputs, include_info), blocks_txs.get('latest_processed_block')

    @classmethod
    def calculate_unprocessed_block_range(cls, network, after_block_number, to_block_number):
        if not to_block_number:
            response = cls.main_server_http_client.get_block_head(network=network)
            latest_block_height_mined = response.get('block_head')
            if not latest_block_height_mined:
                raise APIError(f'{network}: API Not Return block height')
        else:
            latest_block_height_mined = to_block_number
        if not after_block_number:
            latest_block_height_processed = cache. \
                get(f'{settings.BLOCKCHAIN_CACHE_PREFIX}latest_block_height_processed_{network.lower()}')
            if latest_block_height_processed is None:
                latest_block_height_processed = latest_block_height_mined - 5
        else:
            latest_block_height_processed = after_block_number
        print('Cache latest block height: {}'.format(latest_block_height_processed))

        if latest_block_height_mined > latest_block_height_processed:
            min_height = latest_block_height_processed
        else:
            min_height = latest_block_height_mined
        max_height = latest_block_height_mined
        return max_height, min_height

    @classmethod
    def get_block_head(cls, network):
        block_head = cls.main_server_http_client.get_block_head(network=network) or {}
        return block_head.get('block_head')


    @classmethod
    def get_ata(cls, address, currency):
        currency_symbol = get_symbol_from_currency_code(currency)
        ata = cls.main_server_http_client.get_ata(address=address, currency_symbol=currency_symbol) or {}
        return ata
