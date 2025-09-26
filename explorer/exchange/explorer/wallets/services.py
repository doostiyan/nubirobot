from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.db import transaction
from django.db.models import Q

from exchange.base.logging import report_event
from exchange.blockchain.api.general.utilities import Utilities
from exchange.blockchain.apis_conf import APIS_CONF
from exchange.blockchain.explorer import BlockchainExplorer
from exchange.blockchain.explorer_original import BlockchainExplorer as BlockchainExplorerOriginal
from exchange.explorer.blocks.models import GetBlockStats
from exchange.explorer.networkproviders.models import Operation
from exchange.explorer.networkproviders.services import (
    NetworkDefaultProviderService,
    NetworkService,
    ProviderService,
)
from exchange.explorer.transactions.dtos import TransactionDTOCreator
from exchange.explorer.transactions.models import Transfer
from exchange.explorer.transactions.services import TransactionExplorerService
from exchange.explorer.transactions.utils.exceptions import TransactionNotFoundException
from exchange.explorer.utils.blockchain import (
    get_currency2parse,
    is_main_currency_of_network,
    is_network_address_txs_double_checkable,
    parse_currency2code,
)
from exchange.explorer.utils.exception import NetworkNotFoundException

from .dtos import WalletBalanceDTOCreator
from .tasks import chunked_bulk_create, transaction_data
from .utils.exceptions import AddressNotFoundException


class WalletExplorerService:

    @staticmethod
    def get_wallet_balance_dtos(
            network: str,
            addresses: List[str],
            currency: str
    ) -> List[WalletBalanceDTOCreator]:
        currency2parse = get_currency2parse(currency, network).lower()
        parsed_currency = parse_currency2code(currency2parse)

        provider_data = NetworkDefaultProviderService.load_default_provider_data(
            network, Operation.BALANCE
        )

        api_name = provider_data.interface_name or provider_data.provider_name

        address_list = {network: addresses}
        balances_data = BlockchainExplorerOriginal.get_wallets_balance(
            address_list=address_list,
            currency=parsed_currency,
            api_name=api_name,
            raise_error=True
        )

        if balances_data:
            return [
                WalletBalanceDTOCreator.get_dto(balance_data)
                for balance_data in balances_data.get(parsed_currency, [])
            ]
        raise AddressNotFoundException

    @classmethod
    def check_get_wallet_balance(
            cls,
            network: str,
            addresses: List[str],
            currency: str,
            provider_name: str,
            url: str
    ) -> Dict[str, Any]:
        currency2parse = get_currency2parse(currency, network).lower()
        parsed_currency = parse_currency2code(currency2parse)

        provider_data = ProviderService.get_check_provider_data(
            network=network,
            operation=Operation.BALANCE,
            provider_name=provider_name,
            url=url
        )
        api_name = provider_data.interface_name or provider_data.provider_name

        address_list = {network: addresses}
        return BlockchainExplorerOriginal.get_wallets_balance(
            address_list=address_list,
            currency=parsed_currency,
            api_name=api_name,
            is_provider_check=True,
            raise_error=True,
        )

    @classmethod
    def get_wallet_transactions_dto(
            cls,
            network: str,
            address: str,
            currency: str,
            contract_address: Optional[str] = None,
            tx_hash: Optional[str] = None,
            tx_direction_filter: str = '',
            double_check: bool = True
    ) -> List[Any]:
        if not (network in APIS_CONF and 'get_txs' in APIS_CONF[network]):
            raise NetworkNotFoundException

        double_check = double_check and (
                network in BlockchainExplorer.WALLET_TXS_TESTED_NETWORKS and
                is_network_address_txs_double_checkable(network)
        )

        wallet_txs_dto = cls.get_wallet_transactions_dto_from_default_provider(
            currency, network, address, contract_address,
            tx_direction_filter, double_check=double_check
        )

        if tx_hash:
            wallet_txs_dto = filter(lambda tx_dto: tx_dto.tx_hash == tx_hash, wallet_txs_dto)
        return wallet_txs_dto

    @staticmethod
    def get_wallet_transactions_dto_from_db(
            network: str,
            address: str,
            symbol: Optional[str] = None,
            contract_address: Optional[str] = None
    ) -> List[Any]:
        if not symbol or is_main_currency_of_network(symbol, network):
            operation = Operation.ADDRESS_TXS
        else:
            operation = Operation.TOKEN_TXS
        queryset = Transfer.objects.filter(
            network__name__iexact=network,
            source_operation=operation
        )

        if address:
            address = Utilities.normalize_address(network, address)
            queryset = queryset.filter(Q(from_address_str=address) | Q(to_address_str=address))
        if symbol:
            queryset = queryset.filter(symbol=symbol.upper())

        if contract_address:
            queryset = queryset.filter(token=contract_address)

        transfers = queryset.order_by('-date')
        return TransactionDTOCreator.get_db_txs_dto(list(transfers))

    @staticmethod
    def is_nobitex_deposit_wallet(network: str, wallet_address: str) -> bool:
        address = Utilities.normalize_address(network, wallet_address)
        queryset = Transfer.objects.filter(network__name__iexact=network)
        transfers = queryset.filter(Q(to_address_str=address))
        return bool(transfers)

    @classmethod
    def get_wallet_transactions_dto_from_default_provider(
            cls,
            currency: str,
            network: str,
            address: str,
            contract_address: Optional[str] = None,
            tx_direction_filter: str = '',
            double_check: bool = False,
            start_date: Optional[int] = None,
            end_date: Optional[int] = None
    ) -> List[Any]:
        currency2parse = get_currency2parse(currency, network).lower()
        parsed_currency = parse_currency2code(currency2parse)

        if not currency or is_main_currency_of_network(currency, network):
            operation = Operation.ADDRESS_TXS
        else:
            operation = Operation.TOKEN_TXS
        provider_data = NetworkDefaultProviderService.load_default_provider_data(network, operation)
        api_name = provider_data.interface_name or provider_data.provider_name

        wallet_txs = BlockchainExplorerOriginal.get_wallet_transactions(
            address=address,
            currency=parsed_currency,
            network=network,
            api_name=api_name,
            contract_address=contract_address,
            raise_error=True,
            tx_direction_filter=tx_direction_filter,
            start_date=start_date,
            end_date=end_date,
        )

        if wallet_txs:
            kwargs = {'symbol': currency2parse.upper()}
            wallet_txs_dto = []
            for wallet_tx in wallet_txs.get(parsed_currency):
                wallet_txs_dto.extend(TransactionDTOCreator.get_address_txs_dto(wallet_tx, **kwargs))

            network_obj = NetworkService.get_network_by_name(network)
            if double_check:
                use_tx_details = network in BlockchainExplorer.WALLET_TXS_TESTED_NETWORKS
                wallet_txs_dto = cls.double_check_wallet_txs_dtos(
                    wallet_txs_dto,
                    network_name=network_obj.name,
                    network_id=network_obj.id,
                    address=address,
                    use_tx_details=use_tx_details
                )

            if network_obj.save_address_txs:
                cls._save_wallet_transactions(wallet_txs_dto, network_obj.id, network_obj.name, operation)
            return wallet_txs_dto
        raise AddressNotFoundException

    @staticmethod
    def _save_wallet_transactions(
            transactions: List[Any],
            network_id: int,
            network_name: str,
            operation: str
    ) -> None:
        transfers = [transaction_data(tx, network_id, operation) for tx in transactions]
        batch_size = 1000
        with transaction.atomic():
            if transfers:
                chunked_bulk_create(Transfer,
                                    transfers,
                                    batch_size=batch_size,
                                    network=network_name,
                                    ignore_conflicts=True)

    @staticmethod
    def check_get_wallet_transactions(
            network: str,
            address: str,
            currency: str,
            provider_name: str,
            url: str = '',
    ) -> Dict[str, Any]:
        currency2parse = get_currency2parse(currency, network).lower()
        parsed_currency = parse_currency2code(currency2parse)

        provider_data = ProviderService.get_check_provider_data(
            network=network,
            operation=Operation.ADDRESS_TXS,
            provider_name=provider_name,
            url=url
        )
        api_name = provider_data.interface_name or provider_data.provider_name

        return BlockchainExplorerOriginal.get_wallet_transactions(
            address=address,
            currency=parsed_currency,
            network=network,
            api_name=api_name,
            is_provider_check=True,
            raise_error=False
        )

    @staticmethod
    def get_registered_addresses_of_client(client: str, currency: str) -> None:
        pass

    @classmethod
    def double_check_wallet_txs_dtos(
            cls,
            wallet_txs_dtos: List[Any],
            network_name: str,
            network_id: int,
            address: str,
            use_tx_details: bool = False
    ) -> List[Any]:
        checked_wallet_txs, unchecked_wallet_txs = cls.double_check_with_block_txs_in_db(
            wallet_txs_dtos,
            network_name=network_name,
            network_id=network_id,
            address=address
        )

        if use_tx_details and unchecked_wallet_txs:
            checked_wallet_txs.extend(
                cls.double_check_with_tx_details(unchecked_wallet_txs, network=network_name, address=address)
            )

        return checked_wallet_txs

    @staticmethod
    def double_check_with_block_txs_in_db(
            wallet_txs_dtos: List[Any],
            network_name: str,
            network_id: int,
            address: str
    ) -> Tuple[List[Any], List[Any]]:
        db_wallet_txs = set(
            Transfer.get_address_transfers_by_network_and_source_operation(
                network_id=network_id,
                address=address,
                source_operation=Operation.BLOCK_TXS
            )
        )
        db_wallet_txs = [list(tx) for tx in db_wallet_txs]
        for db_tx in db_wallet_txs:
            db_tx[0] = db_tx[0].casefold()
            if db_tx[1]:
                db_tx[1] = db_tx[1].casefold()
            if db_tx[2]:
                db_tx[2] = db_tx[2].casefold()
        unchecked_wallet_txs_dtos = []
        successful_checked_wallet_txs_dtos = []
        failed_checked_wallet_txs_dtos = []
        tx_hashes = {tx[0] for tx in db_wallet_txs}
        for tx in wallet_txs_dtos:
            if tx.tx_hash.casefold() in tx_hashes:
                deposit_fields_value = [
                    tx.tx_hash.casefold(),
                    '',
                    (tx.to_address or '').casefold(),
                    float(tx.value),
                ]
                withdraw_fields_value = [
                    tx.tx_hash.casefold(),
                    (tx.from_address or '').casefold(),
                    '',
                    float(-tx.value),
                ]
                is_matched = False
                if tx.from_address and tx.from_address.casefold() == address.casefold():
                    is_matched = withdraw_fields_value in db_wallet_txs
                elif tx.to_address and tx.to_address.casefold() == address.casefold():
                    is_matched = deposit_fields_value in db_wallet_txs

                if is_matched:
                    successful_checked_wallet_txs_dtos.append(tx)
                else:
                    report_event(
                        'Results of address txs and block txs are different for '
                        f'network:{network_name}, address:{address} and hash:{tx.tx_hash}, '
                        f'address txs values:{(tx.from_address, tx.to_address, tx.value)}'
                    )
                    failed_checked_wallet_txs_dtos.append(tx)
            else:
                unchecked_wallet_txs_dtos.append(tx)

        if failed_checked_wallet_txs_dtos:
            return successful_checked_wallet_txs_dtos, []
        return successful_checked_wallet_txs_dtos, unchecked_wallet_txs_dtos

    @staticmethod
    def double_check_with_tx_details(
            wallet_txs_dtos: List[Any],
            network: str,
            address: str
    ) -> List[Any]:
        block_stats = GetBlockStats.get_block_stats_by_network_name(network)
        min_available_block = block_stats.min_available_block
        wallet_txs_dtos = list(filter(
            lambda t: t.block_height > min_available_block,
            wallet_txs_dtos
        ))
        unchecked_wallet_txs_dtos = []
        successful_checked_wallet_txs_dtos = []
        failed_checked_wallet_txs_dtos = []
        wallet_txs_hash = [tx.tx_hash for tx in wallet_txs_dtos]
        try:
            txs_details_dtos = TransactionExplorerService.get_transaction_details_from_default_provider_dtos(
                network=network,
                tx_hashes=wallet_txs_hash
            )
        except Exception:
            txs_details_dtos = []

        if txs_details_dtos:
            txs_details_compare_values = {
                (
                    tx.tx_hash.casefold(),
                    tx.from_address.casefold() if tx.from_address else None,
                    tx.to_address.casefold() if tx.to_address else None,
                    tx.value
                )
                for tx in txs_details_dtos
            }
            txs_details_hashes = [tx.tx_hash for tx in txs_details_dtos]
            for tx in wallet_txs_dtos:
                if tx.tx_hash in txs_details_hashes:
                    if tx.to_address and tx.to_address == address:
                        compare_value = (
                            tx.tx_hash.casefold(),
                            tx.from_address.casefold() if tx.from_address else None,
                            tx.to_address.casefold(),
                            tx.value
                        )
                    elif tx.from_address and tx.from_address == address:
                        compare_value = (
                            tx.tx_hash.casefold(),
                            tx.from_address.casefold(),
                            tx.to_address.casefold() if tx.to_address else None,
                            -tx.value
                        )
                    else:
                        compare_value = None

                    matched = False
                    if compare_value is not None:
                        # Partial match: only compare non-null fields
                        for cv in txs_details_compare_values:
                            if (
                                    cv[0] == compare_value[0] and  # tx_hash
                                    (compare_value[1] is None or cv[1] == compare_value[1]) and  # from_address
                                    (compare_value[2] is None or cv[2] == compare_value[2]) and  # to_address
                                    cv[3] == compare_value[3]  # value
                            ):
                                matched = True
                                break

                    if matched:
                        successful_checked_wallet_txs_dtos.append(tx)
                    else:
                        report_event(
                            'Results of address txs and tx_details are different for '
                            f'address:{address} and hash:{tx.tx_hash}, '
                            f'address txs values:{(tx.from_address, tx.to_address, tx.value)}'
                        )
                        failed_checked_wallet_txs_dtos.append(tx)
                else:
                    report_event(
                        'Unchecked transaction with '
                        f'tx_hash:{tx.tx_hash}, network:{network}, address:{address}, '
                        f'address txs values:{(tx.from_address, tx.to_address, tx.value)}'
                    )
                    unchecked_wallet_txs_dtos.append(tx)

        return successful_checked_wallet_txs_dtos

    @classmethod
    def get_wallet_transactions_dto_around_tx(
            cls,
            network: str,
            currency: str,
            tx_hash: str,
            address: str,
            contract_address: Optional[str] = None
    ) -> List[Any]:
        tx_details_dtos = TransactionExplorerService.get_transaction_details_from_default_provider_dtos(
            network=network,
            currency=currency,
            tx_hashes=[tx_hash],
        )
        if tx_details_dtos:
            base_time = tx_details_dtos[0].__dict__.get('date')
            if base_time:
                start_time = base_time - timedelta(minutes=5)
                end_time = base_time + timedelta(minutes=5)
                start_timestamp = int(start_time.timestamp())
                end_timestamp = int(end_time.timestamp())

                return cls.get_wallet_transactions_dto_from_default_provider(
                    currency=currency,
                    network=network,
                    address=address,
                    contract_address=contract_address,
                    start_date=start_timestamp,
                    end_date=end_timestamp
                )

        raise TransactionNotFoundException
