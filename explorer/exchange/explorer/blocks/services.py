from django.db.models import Q
import time

from exchange.blockchain.apis_conf import APIS_CONF, APIS_CLASSES
from exchange.blockchain.explorer_original import BlockchainExplorer
from exchange.explorer.transactions.models import Transfer
from exchange.explorer.networkproviders.models import Operation, Network
from exchange.explorer.networkproviders.services import ProviderService, NetworkService
from exchange.explorer.networkproviders.services import NetworkDefaultProviderService
from exchange.explorer.transactions.dtos import TransactionDTOCreator
from exchange.explorer.utils.exception import NetworkNotFoundException
from exchange.base.logging import report_event

from .utils.exceptions import BlockInfoNotFoundException
from .models import GetBlockStats
from .dtos import BlockInfoDTOCreator
from .dtos.block_head import BlockheadDTO
from exchange.explorer.utils.telegram_bot import send_telegram_alert


class BlockExplorerService:
    @classmethod
    def get_latest_block_info_dto(cls, network, after_block_number, to_block_number, include_inputs, include_info,
                                  use_db=True, serialize=True):

        network_obj = Network.objects.filter(name__iexact=network).first()
        if not network_obj:
            raise NetworkNotFoundException

        network_id = network_obj.id
        if use_db and network_obj.use_db:
            get_block_stats = GetBlockStats.objects.get(network_id=network_id)
            if not get_block_stats.min_available_block or after_block_number < get_block_stats.min_available_block - 1:
                raise BlockInfoNotFoundException

            transactions_info = (Transfer.objects
                                 .for_network(network)
                                 .filter(Q(network_id=network_id,
                                           block_height__gte=after_block_number,
                                           block_height__lte=to_block_number,
                                           source_operation=Operation.BLOCK_TXS))
                                 ).order_by('block_height')[:100000]
            # ..........................................................................................................

            latest_tx_block_height = to_block_number
            if transactions_info:
                if list(transactions_info)[-1].block_height != -1:
                    latest_tx_block_height = list(transactions_info)[-1].block_height

            transactions_info = sorted(transactions_info, key=lambda tx: tx.block_height, reverse=False)
            latest_processed_block = min(
                max(get_block_stats.latest_processed_block, latest_tx_block_height),
                to_block_number
            )
            source = 'db'

        else:
            if not (network in APIS_CONF and 'get_blocks_addresses' in APIS_CONF[network]):
                raise NetworkNotFoundException

            result = cls.get_block_info_from_default_provider(network=network, after_block_number=after_block_number,
                                                              to_block_number=to_block_number,
                                                              include_inputs=include_inputs, include_info=include_info)

            transactions_addresses, transactions_info, latest_processed_block = result
            if not (transactions_addresses or transactions_info):
                raise BlockInfoNotFoundException
            source = 'submodule'

        transactions = TransactionDTOCreator.get_block_txs_dto(transactions_info, source=source, serialize=serialize)
        block_info_data = {
            'transactions': transactions,
            'latest_processed_block': latest_processed_block
        }
        return BlockInfoDTOCreator.get_dto(block_info_data, serialize=serialize)

    @classmethod
    def get_block_info_from_default_provider(cls, network, after_block_number, to_block_number, include_inputs,
                                             include_info):

        provider_data = NetworkDefaultProviderService.load_default_provider_data(network, Operation.BLOCK_TXS)
        api_name = provider_data.interface_name or provider_data.provider_name

        result = BlockchainExplorer.get_latest_block_addresses(
            network=network,
            after_block_number=after_block_number,
            to_block_number=to_block_number,
            include_inputs=include_inputs,
            include_info=include_info,
            api_name=api_name,
            raise_error=True
        )
        return result

    @classmethod
    def check_block_txs_provider_health(cls, network, provider_name, url):
        provider_data = ProviderService.get_check_provider_data(
            network=network,
            operation=Operation.BLOCK_TXS,
            provider_name=provider_name,
            url=url
        )

        explorer_interface = APIS_CLASSES.get(provider_data.interface_name)
        max_block_head = explorer_interface.get_max_block_head_of_apis()
        block_time = NetworkService.get_block_time_of_network(network_name=network)
        block_offset = NetworkService.get_number_of_blocks_given_time(network_name=network, time_s=10 * 60)  # 10 min
        is_healthy = True
        cause = None
        try:
            start_time = time.time()
            transfers = explorer_interface().sample_get_blocks(
                min_block=max_block_head - block_offset,
                max_block=max_block_head,
                provider=provider_data.provider_name,
            )
            end_time = time.time()
            elapsed_time = end_time - start_time

            if not transfers:
                is_healthy = False
                cause = 'Empty Response!'

            if elapsed_time / block_offset > block_time:
                is_healthy = False
                cause = 'Response Time!'

        except Exception as e:
            cause = e
            is_healthy = False

        if not is_healthy:
            message = (f"{network}:\nThe current provider {provider_data.provider_name} is not healthy for block_txs "
                       f"due to:\n{cause}.")
            send_telegram_alert(message)

        return is_healthy, cause

    @classmethod
    def get_block_head(cls, network):
        if not (network in APIS_CONF and 'block_head_apis' in APIS_CONF[network]):
            raise NetworkNotFoundException
        try:
            network_obj = Network.objects.get(name__iexact=network)
            if network_obj.use_db:
                return cls.get_block_head_from_db(network_obj.id)
        except Network.DoesNotExist:
            report_event(f"Network {network} does not exists")
        except GetBlockStats.DoesNotExist:
            report_event(f"GetBlockStats object for network {network} does not exists")

        return cls.get_block_head_from_provider(network)

    @classmethod
    def get_block_head_from_db(cls, network_id: int) -> BlockheadDTO:
        get_block_stats = GetBlockStats.objects.get(network_id=network_id)
        latest_processed_block = get_block_stats.latest_processed_block
        if not latest_processed_block:
            # GetBlockStats model object without latest_processed_block value considered as object DoesNotExist
            raise GetBlockStats.DoesNotExist
        return BlockheadDTO(block_head=latest_processed_block)

    @classmethod
    def get_block_head_from_provider(cls, network: str) -> BlockheadDTO:
        provider_data = NetworkDefaultProviderService.load_default_provider_data(network, Operation.BLOCK_HEAD, )
        api_name = provider_data.interface_name or provider_data.provider_name

        block_head = BlockchainExplorer.get_block_head(
            network=network,
            api_name=api_name,
            raise_error=True,
        )
        return BlockheadDTO(block_head=block_head)

    @classmethod
    def check_get_block_head(cls, network, provider_name, url):
        provider_data = ProviderService.get_check_provider_data(network=network, operation=Operation.BLOCK_HEAD,
                                                                provider_name=provider_name, url=url)
        api_name = provider_data.interface_name or provider_data.provider_name

        block_head = BlockchainExplorer.get_block_head(
            network=network,
            api_name=api_name,
            is_provider_check=True,
            raise_error=False,
        )
        return block_head
