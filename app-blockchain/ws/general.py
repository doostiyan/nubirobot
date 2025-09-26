import sys
import traceback
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import List, Dict, Tuple, Set

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q


from exchange.base.models import Currencies
from exchange.blockchain.utils import BlockchainUtilsMixin
from exchange.blockchain.api.general_block_api import NobitexBlockchainBlockAPI
from exchange.blockchain.metrics import metric_set, metric_incr
from exchange.blockchain.api.near.near_nearscan import NearScan
from exchange.blockchain.explorer import BlockchainExplorer

if settings.IS_EXPLORER_SERVER:
    INHERITANCE_CLASSES = (BlockchainUtilsMixin, ABC)
else:
    from exchange.wallet.block_processing import NobitexBlockProcessing
    from exchange.wallet.models import WalletDepositAddress
    INHERITANCE_CLASSES = (BlockchainUtilsMixin, NobitexBlockProcessing, ABC)


class GeneralWS(*INHERITANCE_CLASSES):
    """
    coins:
    API docs: https://github.com/trezor/blockbook/blob/master/docs/api.md
    Explorer:
    """

    currency: Currencies
    currencies: List

    PRECISION = 18
    USE_PROXY = True if settings.IS_PROD and settings.NO_INTERNET and not settings.IS_VIP else False
    TESTNET_ENABLE = False
    network = 'testnet' if settings.USE_TESTNET_BLOCKCHAINS and TESTNET_ENABLE else 'mainnet'

    ws = None
    blockchain_ws = None
    network_symbol = None
    network_required = True
    keep_alive_interval = 25
    block_latest_number = 2

    sub_addresses = None

    def __init__(self, network=None):
        if network is not None:
            self.network = network

    @classmethod
    def get_ws(cls, *args, **kwargs):
        if cls.blockchain_ws is None:
            cls.blockchain_ws = cls(*args, **kwargs)
        return cls.blockchain_ws

    def get_deposits_addresses(self):
        currency_filter = Q(currency__in=self.currencies)
        if self.network_symbol:
            network_filter = Q(network=self.network_symbol)
            if not self.network_required:
                network_filter = network_filter | Q(network__isnull=True)
            currency_filter = currency_filter & network_filter
        return set(WalletDepositAddress.objects.using(self.READ_DB).filter(
            currency_filter, is_disabled=False
        ).values_list('address', flat=True))

    @abstractmethod
    def get_height(self, info, *args, **kwargs):
        raise NotImplementedError

    # TODO Replace output of function with DTO to prevent confusion
    @classmethod
    def decode_transactions_info_into_address_and_hash_pair(cls, transactions_info: Dict) -> Tuple:
        """Decode transaction information to identify address and transaction hash relationships.

        This method parses a dictionary containing incoming and outgoing transactions,
        maps them to their respective addresses and transaction hashes, and identifies
        transactions where there is a common transaction hash appearing both as an
        incoming and outgoing transaction.

        Specifically, it produces a tuple of triples in the form `(source_address, destination_address, tx_hash)`
        representing the pairs of addresses associated with the same transaction hash.
        """
        incoming_txs, outgoing_txs = transactions_info['incoming_txs'], transactions_info['outgoing_txs']
        hash_to_source_address_map = defaultdict(set)
        for addr, addr_txs in outgoing_txs.items():
            for currency, txs_list in addr_txs.items():
                for tx in txs_list:
                    hash_to_source_address_map[tx['tx_hash']].add(addr)

        hash_to_destination_address_map = defaultdict(set)
        for addr, addr_txs in incoming_txs.items():
            for currency, txs_list in addr_txs.items():
                for tx in txs_list:
                    hash_to_destination_address_map[tx['tx_hash']].add(addr)

        # Find common tx_hashes
        common_tx_hashes = hash_to_source_address_map.keys() & hash_to_destination_address_map.keys()

        # Create triples (incoming_address, outgoing_address, tx_hash)
        pairs = set()
        for tx_hash in common_tx_hashes:
            for in_addr in hash_to_source_address_map[tx_hash]:
                for out_addr in hash_to_destination_address_map[tx_hash]:
                    pairs.add((in_addr, out_addr, tx_hash))
        return tuple(pairs)

    # TODO Replace output of function with DTO to prevent confusion
    @classmethod
    def determine_updated_deposit_addresses_and_txs_info(
        cls, addresses_pairs: Tuple, transactions_info: Dict, deposit_addresses: Set[str]
    ) -> Tuple[Set, Dict]:
        """Determine which deposit addresses need updating and filter transaction info accordingly.

        This method takes pairs of addresses and associated transaction hashes, along with
        a set of known deposit addresses, and uses them to determine:
          1. Which addresses require an update (those that appear as outgoing addresses
             in the pairs but source address in pair(pair[0]) are not in `deposit_addresses`).
          2. Which transactions should be filtered out based on the presence of known
             deposit addresses. Any transaction hash that is associated with a deposit
             address (as an incoming address) will be excluded from the transaction info.

        Args:
            addresses_pairs (tuple): A tuple of `(source_address, destination_address, tx_hash)` triples.
            transactions_info (dict): A dictionary containing incoming and outgoing transactions,
                structured similarly to the input of `decode_transactions_info_into_address_and_hash_pair`.
            deposit_addresses (set[str]): A set of addresses expecting system deposit addresses.

        Returns:
            tuple[set, dict]: A tuple containing:
                - A set of addresses that should be updated based on the provided addresses pairs.
                - A modified `transactions_info` dict where transactions associated with
                  deposit addresses have been filtered out.
        """
        addresses_to_update = set()
        hashes_to_exclude = set()
        for pair in addresses_pairs:
            if pair[0] not in deposit_addresses:
                addresses_to_update.add(pair[1])
            else:
                hashes_to_exclude.add(pair[2])

        for addr, block_dict in transactions_info.items():
            for currency, txs_list in block_dict.items():
                filtered_txs = [tx for tx in txs_list if tx['tx_hash'] not in hashes_to_exclude]
                block_dict[currency] = filtered_txs

        return addresses_to_update, transactions_info

    def receive_block(self, info, *args, **kwargs):
        try:
            height = self.get_height(info, *args, **kwargs)
            if not height:
                return
            new_height = height - self.block_latest_number
            print(f'[Block] Block {height} has been mined in the blockchain. Getting {new_height}')
            metric_set(name='ws_latest_block_mined', labels=[self.network_symbol], amount=height)

            transactions_addresses, transactions_info, _ = BlockchainExplorer.get_latest_block_addresses(
                network=self.network_symbol,
                # to_block_number=new_height,
                include_inputs=True,
                include_info=True)

            print(f"# input addresses: {len(transactions_addresses['input_addresses'])}, # output addresses: {len(transactions_addresses['output_addresses'])}")
            if (not transactions_addresses
                    or transactions_addresses == {'input_addresses': set(), 'output_addresses': set()}
                    or settings.IS_EXPLORER_SERVER):
                # addresses collection did not fill
                return
            # handle whole deposits stuff
            deposit_addresses = self.get_deposits_addresses()
            if isinstance(transactions_addresses, set):
                # result has the old form, so we can just handle deposits in the old way
                updated_deposit_addresses = deposit_addresses.intersection(transactions_addresses)
                print('here', len(updated_deposit_addresses))
                self.updating_wallet(updated_addresses=updated_deposit_addresses,
                                     currencies=self.currencies,
                                     transactions_info=transactions_info,
                                     network=self.network_symbol,
                                     network_required=self.network_required)
                print(f'[Block] Update these addresses: {updated_deposit_addresses}')
                return
            else:
                # result has the new form, so based on that we handle deposits (by addresses appeared in the outputs)
                # TODO this 2 functions now completely depends on one another and they didn't follow SOC rule
                address_pairs = self.decode_transactions_info_into_address_and_hash_pair(transactions_info)
                updated_deposit_addresses, incoming_tx_info = self.determine_updated_deposit_addresses_and_txs_info(
                    address_pairs, transactions_info['incoming_txs'], deposit_addresses
                )
                self.updating_wallet(updated_addresses=updated_deposit_addresses,
                                     currencies=self.currencies,
                                     transactions_info=incoming_tx_info,
                                     network=self.network_symbol,
                                     network_required=self.network_required)
                print(f'[Block] Update these addresses: {updated_deposit_addresses}')

            if not settings.ENABLE_HOT_WALLET_DIFF:
                return

            # handle whole withdraws stuff (only when 1: output result of each coin file is appropriate (we can)
            #                                         2: flag has been set in settings (we want))
            hot_wallet_addresses = self.get_hot_wallet_addresses()
            updated_hot_wallet_addresses = hot_wallet_addresses.intersection(
                set(map(lambda a: a.lower(), transactions_addresses['input_addresses']))
            )
            if updated_hot_wallet_addresses:
                print(f'[Block] Update these hot wallet addresses: {updated_hot_wallet_addresses}')
            self.update_withdraw_status(updated_hot_wallet_addresses=updated_hot_wallet_addresses,
                                        transactions_info=transactions_info['outgoing_txs'])

        except Exception:
            traceback.print_exception(*sys.exc_info())
            metric_incr('ws_receive_block_error', labels=[self.network_symbol])
            return

    @abstractmethod
    def run(self):
        raise NotImplementedError
