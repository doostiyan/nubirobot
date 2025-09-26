from typing import Optional

from exchange.explorer.blocks.services import BlockExplorerService
from exchange.explorer.networkproviders.dtos.provider import CheckProviderResultDto, CheckProviderResultDtoCreator
from exchange.explorer.networkproviders.models import Operation
from exchange.explorer.networkproviders.services import ProviderService
from exchange.explorer.transactions.services import TransactionExplorerService
from exchange.explorer.wallets.services import WalletExplorerService


class CheckNetworkProviderService:

    @classmethod
    def check_provider(
        cls,
        provider_id: int,
        base_url: str,
        operation: str,
        currency: Optional[str] = None
    ) -> CheckProviderResultDto:

        provider = ProviderService.get_provider_by_id(provider_id=provider_id)
        provider_name = provider.name
        network = provider.network

        is_healthy = True
        block_head = None
        message = None

        try:
            block_head = BlockExplorerService.check_get_block_head(
                network=network.name,
                provider_name=provider_name,
                url=base_url,
            )

            latest_transaction = TransactionExplorerService.get_latest_transaction_from_db_by_network_id(network.id)

            result = None

            if latest_transaction and operation == Operation.TX_DETAILS:
                tx_hash = latest_transaction.tx_hash
                result = TransactionExplorerService().get_transaction_details_based_on_provider_name_and_url(
                    provider_name=provider_name,
                    base_url=base_url,
                    network=network,
                    tx_hashes=[tx_hash],
                    currency=currency,
                )
            elif latest_transaction and operation in {Operation.ADDRESS_TXS, Operation.BALANCE}:
                address = latest_transaction.from_address_str or latest_transaction.to_address_str
                result = WalletExplorerService.check_get_wallet_balance(
                    network.name,
                    [address],
                    currency,
                    provider_name=provider_name,
                    url=base_url,
                )
            elif operation == Operation.BLOCK_HEAD:
                result = block_head
            elif operation == Operation.BLOCK_TXS:
                result, _ = BlockExplorerService.check_block_txs_provider_health(
                    network=network.name,
                    provider_name=provider_name,
                    url=base_url,
                )
            is_healthy = bool(result)

        except Exception as e:
            is_healthy = False
            block_head = None
            message = str(e)

        return CheckProviderResultDtoCreator.get_dto(
            is_healthy=is_healthy,
            block_head=block_head,
            message=message,
        )
