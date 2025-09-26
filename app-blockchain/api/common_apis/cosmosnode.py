from typing import List
from decimal import Decimal
from exchange.base.parsers import parse_iso_date
from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.utils import APIError, BlockchainUtilsMixin

from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator


class CosmosNodeValidator(ResponseValidator):
    valid_transfer_types = []
    get_txs_keyword = None
    symbol = None

    @classmethod
    def get_valid_denoms(cls):
        return ['u' + cls.symbol.lower(), 'a' + cls.symbol.lower()]

    @classmethod
    def validate_general_response(cls, response):
        if not response:
            raise APIError('[CosmosNodeValidator][ValidateGeneralResponse] Response is None')
        if 'error' in response:
            raise APIError('[CosmosNodeValidator][ValidateGeneralResponse] Error: ' + response.get('error'))
        return True

    @classmethod
    def validate_balance_response(cls, balance_response) -> bool:
        if (cls.validate_general_response(balance_response)
                and (balance_response.get('balance') or balance_response.get('balances'))):
            return True
        return False

    @classmethod
    def validate_block_head_response(cls, block_head_response) -> bool:
        if (cls.validate_general_response(block_head_response)
                and block_head_response.get('block')
                and block_head_response.get('block').get('header')
                and block_head_response.get('block').get('header').get('height')):
            return True
        return False

    @classmethod
    def validate_tx_details_response(cls, tx_details_response) -> bool:
        if (cls.validate_general_response(tx_details_response)
                and tx_details_response.get('tx')
                and tx_details_response.get('tx_response')):
            return True
        return False

    @classmethod
    def validate_transaction(cls, transaction) -> bool:
        if (not transaction.get('tx')
                or not transaction.get('tx').get('body')
                or not transaction.get('tx').get('body').get('messages')):
            return False

        # check transaction keys are not empty
        if not (any(transaction.get('tx').get('body').get('messages')[0].get(field) for field in
                    ('amount', 'from_address', 'to_address'))  # based on single transaction keys
                or any(transaction.get('tx').get('body').get('messages')[0].get(field) for field in
                       ('inputs', 'outputs'))):  # based on multi-send transaction keys
            return False
        if transaction.get('tx_response'):
            if int(transaction.get('tx_response').get('code')) != 0:  # only zero code means success
                return False
        elif int(transaction.get('code')) != 0:  # only zero code means success
            return False
        msgs = transaction.get('tx').get('body').get('messages')
        tx_amount_list = msgs[0].get('amount') or msgs[0].get('inputs')[0].get('coins')
        from_address = (msgs[0].get('from_address') or msgs[0].get('inputs')[0].get('address')).casefold()
        to_address = (msgs[0].get('to_address') or msgs[0].get('outputs')[0].get('address')).casefold()
        if (not (transaction.get('txhash') or transaction.get('tx_response').get('txhash'))
                or len(msgs) != 1  # to support send and "multi-send with just one transfer"
                or (msgs[0].get('type') or msgs[0].get('@type')) not in cls.valid_transfer_types  # check type of tx
                # The API response returns the denom value in the form of u+symbol for ATOM and a+symbol for DYDX
                or tx_amount_list[0].get('denom') not in cls.get_valid_denoms()
                or from_address == to_address
                or len(tx_amount_list) != 1):  # to support send and "multi-send with just one transfer"
            return False
        return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response) -> bool:
        if cls.validate_general_response(address_txs_response) and address_txs_response.get(cls.get_txs_keyword):
            return True
        return False


class CosmosNodeParser(ResponseParser):
    validator = CosmosNodeValidator
    precision = 6
    get_txs_keyword = None
    symbol = None
    currency = None

    @classmethod
    def get_valid_denoms(cls):
        return ['u' + cls.symbol.lower(), 'a' + cls.symbol.lower()]

    @classmethod
    def parse_balance_response(cls, balance_response) -> Decimal:
        if cls.validator.validate_balance_response(balance_response):
            balances = balance_response.get('balance') or balance_response.get('balances')
            if not isinstance(balances, list):
                balances = [balances]
            for balance in balances:
                # The API response returns the denom value in the form of u+symbol for ATOM and a+symbol for DYDX
                if balance.get('denom') in cls.get_valid_denoms():
                    return BlockchainUtilsMixin.from_unit(int(balance.get('amount')), precision=cls.precision)

    @classmethod
    def parse_block_head_response(cls, block_head_response):
        if cls.validator.validate_block_head_response(block_head_response):
            return int(block_head_response.get('block').get('header').get('height'))

    @classmethod
    def parse_tx_details_response(cls, tx_details_response, block_head) -> List[TransferTx]:
        if (cls.validator.validate_tx_details_response(tx_details_response)
                and cls.validator.validate_transaction(tx_details_response)):
            msg = tx_details_response.get('tx').get('body').get('messages')[0]
            return [
                TransferTx(
                    block_height=int(tx_details_response.get('tx_response').get('height')),
                    block_hash=None,
                    tx_hash=tx_details_response.get('tx_response').get('txhash'),
                    date=parse_iso_date(tx_details_response.get('tx_response').get('timestamp')),
                    success=True,
                    confirmations=block_head - int(tx_details_response.get('tx_response').get('height')),
                    from_address=(msg.get('from_address') or msg.get('inputs')[0].get('address')).casefold(),
                    to_address=(msg.get('to_address') or msg.get('outputs')[0].get('address')).casefold(),
                    value=BlockchainUtilsMixin.from_unit(
                        int((msg.get('amount') or msg.get('inputs')[0].get('coins'))[0].get('amount')),
                        precision=cls.precision),
                    symbol=cls.symbol,
                    memo=tx_details_response.get('tx_response').get('tx').get('body').get('memo') or '',
                    tx_fee=BlockchainUtilsMixin.from_unit(
                        int(tx_details_response.get('tx').get('auth_info').get('fee').get('amount')[0].get('amount')),
                        precision=cls.precision),
                    token=None,
                )
            ]

    @classmethod
    def parse_address_txs_response(cls, address, address_txs_response, block_head) -> List[TransferTx]:
        transfers = []
        if cls.validator.validate_address_txs_response(address_txs_response):
            for tx in address_txs_response.get(cls.get_txs_keyword):
                if cls.validator.validate_transaction(tx):
                    msg = tx.get('tx').get('body').get('messages')[0]
                    transfers.append(
                        TransferTx(
                            block_height=int(tx.get('height')),
                            block_hash=None,
                            tx_hash=tx.get('txhash'),
                            date=parse_iso_date(tx.get('timestamp')),
                            success=True,
                            confirmations=block_head - int(tx.get('height')),
                            from_address=(msg.get('from_address') or msg.get('inputs')[0].get('address')).casefold(),
                            to_address=(msg.get('to_address') or msg.get('outputs')[0].get('address')).casefold(),
                            value=BlockchainUtilsMixin.from_unit(
                                int((msg.get('amount') or msg.get('inputs')[0].get('coins'))[0].get('amount')),
                                precision=cls.precision),
                            symbol=cls.symbol,
                            memo=tx.get('tx').get('body').get('memo') or '',
                            tx_fee=None,
                            token=None,
                        )
                    )
        return transfers


class CosmosNodeApi(GeneralApi):
    parser = CosmosNodeParser

    @classmethod
    def get_address_txs(cls, address, tx_direction_filter):
        if tx_direction_filter == 'incoming':
            tx_query_direction = 'recipient'
        elif tx_direction_filter == 'outgoing':
            tx_query_direction = 'sender'
        else:
            tx_query_direction = 'recipient'
        response = cls.request(request_method='get_address_txs', body=cls.get_address_txs_body(address),
                               headers=cls.get_headers(), address=address, apikey=cls.get_api_key(),
                               tx_query_direction=tx_query_direction)
        return response
