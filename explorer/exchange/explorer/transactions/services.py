from typing import Any, Dict, List, Optional

from django.db.models import Q

from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.api.general.utilities import Utilities
from exchange.blockchain.apis_conf import APIS_CONF
from exchange.blockchain.explorer_original import BlockchainExplorer
from exchange.explorer.networkproviders.models import Operation
from exchange.explorer.networkproviders.services import (
    NetworkDefaultProviderService,
    NetworkService,
    ProviderService,
)
from exchange.explorer.transactions.dtos import TransactionDTOCreator
from exchange.explorer.transactions.models import Transfer
from exchange.explorer.transactions.utils.exceptions import TransactionNotFoundException
from exchange.explorer.utils.blockchain import (
    is_main_currency_of_network,
    is_network_ready,
    parse_currency2code,
)
from exchange.explorer.utils.exception import NetworkNotFoundException, NotFoundException


class TransactionExplorerService:

    @classmethod
    def get_transaction_detail_dto_from_transaction_details_data(
            cls, transactions_details_data: dict, tx_hashes: List[str]
    ) -> List[TransferTx]:
        tx_details_dtos = []
        for tx_hash in tx_hashes:
            txs_data = transactions_details_data.get(tx_hash)
            if txs_data:
                tx_details_dtos.extend(TransactionDTOCreator.get_tx_details_dto(txs_data))

        return tx_details_dtos

    @classmethod
    def get_transaction_details_from_default_provider_dtos(
            cls,
            network: str,
            tx_hashes: Optional[List[str]] = None,
            currency: Optional[str] = None,
    ) -> List[TransferTx]:
        tx_hashes = tx_hashes or []
        parsed_currency = parse_currency2code(currency)
        tx_hashes = Utilities.normalize_hash(network=network,
                                             currency=parsed_currency,
                                             tx_hashes=tx_hashes,
                                             output_format='base64')
        if network not in APIS_CONF or not is_network_ready(network, Operation.TX_DETAILS):
            raise NetworkNotFoundException

        transactions_details_data = cls.get_transaction_details_from_default_provider(
            network=network,
            tx_hashes=tx_hashes,
            currency=currency,
        )

        if transactions_details_data:
            return cls.get_transaction_detail_dto_from_transaction_details_data(
                transactions_details_data=transactions_details_data, tx_hashes=tx_hashes
            )

        return []

    @staticmethod
    def read_transfers_from_db_by_hash(tx_hash: str, network: str) -> List[Dict[str, Any]]:
        network_obj = NetworkService.get_network_by_name(network)
        transfers = Transfer.objects.for_network(network).filter(network_id=network_obj.id, tx_hash=tx_hash).values()
        return list(transfers)

    @classmethod
    def get_transaction_details_from_default_provider(
            cls, network: str, tx_hashes: List[str], currency: Optional[str]
    ) -> Dict[str, Any]:
        if not currency or is_main_currency_of_network(currency, network):
            operation = Operation.TX_DETAILS
            parsed_currency = None
        else:
            operation = Operation.TOKEN_TX_DETAILS
            provider_data = NetworkDefaultProviderService.load_default_provider_data(network, operation)
            if not provider_data:
                operation = Operation.TX_DETAILS
            try:
                parsed_currency = parse_currency2code(currency.lower()) if currency else None
            except NotFoundException:
                parsed_currency = True
        provider_data = NetworkDefaultProviderService.load_default_provider_data(network, operation)
        api_name = provider_data.interface_name or provider_data.provider_name

        return BlockchainExplorer.get_transactions_details(
            tx_hashes=tx_hashes,
            network=network,
            currency=parsed_currency,
            api_name=api_name,
            raise_error=True,
            retry_with_main_api=True,
        )

    @classmethod
    def get_transaction_details_from_dynamic_provider_dtos(
            cls,
            network: str,
            tx_hashes: List[str],
            provider_name: Optional[str] = None,
            url: Optional[str] = None,
    ) -> List[TransferTx]:
        provider_data = ProviderService.get_check_provider_data(
            network=network,
            operation=Operation.TX_DETAILS,
            provider_name=provider_name,
            url=url,
        )
        api_name = provider_data.interface_name or provider_data.provider_name

        transactions_details_data = BlockchainExplorer.get_transactions_details(
            tx_hashes=tx_hashes,
            network=network,
            api_name=api_name,
            is_provider_check=True,
            raise_error=True,
        )
        if transactions_details_data:
            return cls.get_transaction_detail_dto_from_transaction_details_data(
                transactions_details_data=transactions_details_data, tx_hashes=tx_hashes
            )

        raise TransactionNotFoundException

    @staticmethod
    def get_latest_transaction_from_db_by_network_id(network_id: int) -> Optional[Transfer]:
        return Transfer.objects.filter(network_id=network_id).order_by('created_at').last()

    @staticmethod
    def get_confirmed_transaction_details(
            network: str, tx_hash: str, address: Optional[str] = None
    ) -> List[TransferTx]:
        transfers = Transfer.objects.filter(
            network__name__iexact=network,
            tx_hash=tx_hash,
            source_operation=Operation.ADDRESS_TXS,
        )
        if address:
            transfers = transfers.filter(Q(from_address_str=address) | Q(to_address_str=address))

        return TransactionDTOCreator.get_db_txs_dto(list(transfers))

    @classmethod
    def get_transaction_details_based_on_provider_name_and_url(
            cls,
            provider_name: str,
            base_url: str,
            network: str,
            tx_hashes: List[str],
            currency: str,
    ) -> List[TransferTx]:
        if provider_name and base_url:
            return cls.get_transaction_details_from_dynamic_provider_dtos(
                network=network,
                tx_hashes=tx_hashes,
                provider_name=provider_name,
                url=base_url,
            )
        return cls.get_transaction_details_from_default_provider_dtos(
            network=network,
            tx_hashes=tx_hashes,
            currency=currency,
        )
