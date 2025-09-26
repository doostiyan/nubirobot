from decimal import Decimal

from exchange.blockchain.api.near.near_general import NearGeneralAPI
from exchange.blockchain.utils import APIError, ParseError


class NearScan(NearGeneralAPI):
    """
    API Doc: requests inspected from https://www.nearscan.org
    """
    _base_url = 'https://nearscan-api.octopus-network.workers.dev/'
    get_txs_keyword = 'transactions'
    supported_requests = {
        'get_block_head': 'common/latestBlocks',
        'get_block_txs': 'block/{block_height}'
    }

    def get_name(self) -> str:
        return 'scan_api'

    def parse_block_head(self, response: list) -> int:
        try:
            block_height = int(response[0].get('height'))
        except AttributeError as e:
            raise ParseError(f'{self.symbol} get block head parsing error.') from e
        return block_height

    def parse_block_transactions(self, response: dict) -> list:
        if not response:
            raise APIError(f'{self.symbol} Get block API returns empty response')
        return response.get(self.get_txs_keyword)

    def validate_transaction(self, tx: dict) -> bool:
        try:
            tx_hash = tx.get('hash')
            if not tx_hash:
                return False
            # There is no field to check status of tx
            actions_count = len(tx.get('actions'))
            if actions_count != 1:  # as we do not support multiple transfer
                return False
            tx_type = tx.get('actions')[0].get('kind')
            if tx_type not in self.valid_transfer_types:
                return False
            tx_amount = self.from_unit(int(Decimal(tx.get('actions')[0].get('args').get('deposit'))))
            if not self.validate_tx_amount(tx_amount):
                return False
        except AttributeError as e:
            raise ParseError(f'{self.symbol} parsing error Tx is {tx}.') from e
        return True

    def parse_transaction_data(self, tx: dict) -> dict:
        try:
            tx_data = {
                'hash': tx.get('hash'),
                'from': self.parse_tx_sender(tx),
                'to': self.parse_tx_receiver(tx),
                'amount': self.from_unit(int(Decimal(tx.get('actions')[0].get('args').get('deposit')))),
                'currency': self.currency
            }
        except AttributeError as e:
            raise ParseError(f'{self.symbol} parsing error. tx is {tx}.') from e
        return tx_data

    def parse_tx_sender(self, tx: dict) -> str:
        return tx.get('signerId')

    def parse_tx_receiver(self, tx: dict) -> str:
        return tx.get('receiverId')
