from exchange.blockchain.api.atom.atomnode import CosmosNetworkNode, LavenderFiveNode, PupmosNode
from exchange.blockchain.api.general.explorer_interface import ExplorerInterface


class AtomExplorerInterface(ExplorerInterface):
    balance_apis = [PupmosNode, LavenderFiveNode, CosmosNetworkNode]
    tx_details_apis = [CosmosNetworkNode, PupmosNode, LavenderFiveNode]
    address_txs_apis = [CosmosNetworkNode, LavenderFiveNode, PupmosNode]
    block_head_apis = [PupmosNode, CosmosNetworkNode, LavenderFiveNode]
    symbol = 'ATOM'

    def get_txs(self, address, tx_direction_filter='incoming'):
        address_txs_api = self.address_txs_apis[0].get_instance()
        block_head = None
        if address_txs_api.need_block_head_for_confirmation:
            block_head_api_response = address_txs_api.get_block_head()
            block_head = address_txs_api.parser.parse_block_head_response(block_head_api_response)
        address_txs_api_response = address_txs_api.get_address_txs(address, tx_direction_filter)
        transfers = address_txs_api.parser.parse_address_txs_response(address, address_txs_api_response, block_head)

        if tx_direction_filter == 'incoming':
            transfers = [item for item in transfers if item.to_address.casefold() == address.casefold()]
        elif tx_direction_filter == 'outgoing':
            transfers = [item for item in transfers if item.from_address.casefold() == address.casefold()]

        return self.convert_transfers2list_of_address_txs_dict(address, transfers, address_txs_api.parser.currency)
