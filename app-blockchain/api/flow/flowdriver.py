import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.conf import settings

from exchange.base.parsers import parse_iso_date
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.api.general_block_api import NobitexBlockchainBlockAPI


class FlowdriverFlowValidator(ResponseValidator):
    valid_event_names = ['A.1654653399040a61.FlowToken.TokensDeposited', 'A.1654653399040a61.FlowToken.TokensWithdrawn']
    FEE_ADDRESS = '0xf919ee77447b7497'

    @classmethod
    def validate_general_response(cls, response: Dict[str, Any]) -> bool:
        if not response:
            return False
        if not response.get('data'):
            return False
        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(tx_details_response):
            return False
        if not tx_details_response.get('data').get('transactions'):
            return False
        if not isinstance(tx_details_response.get('data').get('transactions'), list):
            return False
        tx_details_response_needed = tx_details_response.get('data').get('transactions')[0]
        if not cls.validate_transaction(tx_details_response_needed):
            return False
        return True

    @classmethod
    def validate_transaction(cls, transaction: Dict[str, Any]) -> bool:
        if not any(transaction.get(field) for field in
                   ['id', 'timestamp', 'block_height', 'fee', 'block_id']):
            return False
        if not transaction.get('status') or transaction.get(
                'status').casefold() != 'Sealed'.casefold():
            return False
        if not transaction.get('payer'):
            return False
        if transaction.get('__typename').casefold() != 'transactions'.casefold():
            return False
        if transaction.get('error'):
            return False
        if not transaction.get('events') or not isinstance(transaction.get('events'),
                                                           list):
            return False
        return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(address_txs_response):
            return False
        if not address_txs_response.get('data').get('participations') or not isinstance(
                address_txs_response.get('data').get('participations'), list):
            return False
        return True

    @classmethod
    def validate_transfer(cls, transfer: Dict[str, Any]) -> bool:
        if not transfer.get('name') or transfer.get('name') not in cls.valid_event_names:
            return False
        if not transfer.get('__typename') or transfer.get('__typename').casefold() != 'events'.casefold():
            return False
        if not transfer.get('fields') or not isinstance(transfer.get('fields'), dict):
            return False
        if not transfer.get('fields').get('amount'):
            return False
        value = Decimal(str(transfer.get('fields').get('amount')))
        if value <= cls.min_valid_tx_amount:
            return False
        if not transfer.get('fields').get('from') and not transfer.get('fields').get('to'):
            return False
        if transfer.get('fields').get('to') and transfer.get('fields').get('to') in cls.FEE_ADDRESS:
            return False
        return True

    @classmethod
    def address_validation(cls, address: str, transfer: Dict[str, Any]) -> bool:
        event_type = transfer.get('name').replace('A.1654653399040a61.FlowToken.', '')
        if (transfer.get('fields').get('from')
                and event_type == 'TokensWithdrawn'
                and transfer.get('fields').get('from') != address):
            return False
        if (transfer.get('fields').get('to')
                and event_type == 'TokensDeposited'
                and transfer.get('fields').get('to') != address):
            return False
        return True


class FlowdriverResponseParser(ResponseParser):
    """
        coins: Flow
        API docs: https://developers.flow.com/http-api
        rate limit: https://developers.flow.com/nodes/access-api-rate-limits
        get latest block rate limit : 100 request per second per client IP
        other request rate limit: 2000 rps

        """
    symbol = 'FLOW'
    currency = Currencies.flow
    validator = FlowdriverFlowValidator
    BLOCK_TIME = 2
    fee_address = ['0xf919ee77447b7497', 'f919ee77447b7497']

    @classmethod
    def parse_tx_details_response(cls, tx_details_response: Dict[str, Any], _: Optional[int]) -> List[TransferTx]:
        transfers: List[TransferTx] = []
        if cls.validator.validate_tx_details_response(tx_details_response):
            tx_details = tx_details_response.get('data').get('transactions')[0]
            tx_hash = tx_details.get('id')
            block_hash = tx_details.get('block_id')
            tx_fee = Decimal(str(tx_details.get('fee')))
            events = tx_details.get('events')
            date = parse_iso_date(tx_details.get('timestamp'))
            block_height = tx_details.get('block_height')
            transfers: List[TransferTx] = []
            for event in events:
                # In here we have events just like events in FlowNode
                # You can check the description there
                if cls.validator.validate_transfer(event):
                    from_address = ''
                    to_address = ''
                    event_type = event.get('name').replace('A.1654653399040a61.FlowToken.', '')
                    if event.get('fields').get('from') and event_type == 'TokensWithdrawn':
                        from_address = event.get('fields').get('from')
                    elif event.get('fields').get('to') and event_type == 'TokensDeposited':
                        to_address = event.get('fields').get('to')
                    else:
                        continue
                    tx_value = Decimal(str(event.get('fields').get('amount')))
                    transfer = TransferTx(
                        tx_hash=tx_hash,
                        success=True,
                        block_height=block_height,
                        symbol=cls.symbol,
                        memo=None,
                        from_address=from_address,
                        to_address=to_address,
                        token=None,
                        block_hash=block_hash,
                        value=tx_value,
                        tx_fee=tx_fee,
                        confirmations=cls.calculate_confirmation(date),
                        date=date
                    )
                    transfers.append(transfer)

        return transfers

    @classmethod
    def calculate_confirmation(cls, tx_date: datetime) -> int:
        diff = (datetime.now(timezone.utc) - tx_date).total_seconds()
        return int(diff / cls.BLOCK_TIME)

    @classmethod
    def parse_address_txs_response(cls,
                                   address: str,
                                   address_txs_response: Dict[str, Any],
                                   _: Optional[int]) -> List[TransferTx]:
        transfers: List[TransferTx] = []
        if cls.validator.validate_address_txs_response(address_txs_response) and address not in cls.fee_address:
            transactions = address_txs_response.get('data').get('participations')
            for tx in transactions:
                if tx.get('transaction') and cls.validator.validate_transaction(tx.get('transaction')):
                    tx_transaction_field = tx.get('transaction')
                    tx_hash = tx_transaction_field.get('id')
                    block_hash = tx_transaction_field.get('block_id')
                    tx_fee = Decimal(str(tx_transaction_field.get('fee')))
                    events = tx_transaction_field.get('events')
                    date = parse_iso_date(tx_transaction_field.get('timestamp'))
                    block_height = tx_transaction_field.get('block_height')
                    for event in events:
                        # In here we have events just like events in FlowNode
                        # You can check the description there
                        if cls.validator.validate_transfer(event) and \
                                cls.validator.address_validation(address, event):
                            from_address = ''
                            to_address = ''
                            if event.get('fields').get('from'):
                                from_address = event.get('fields').get('from')
                            elif event.get('fields').get('to'):
                                to_address = event.get('fields').get('to')
                            else:
                                continue
                            tx_value = Decimal(str(event.get('fields').get('amount')))
                            transfer = TransferTx(
                                tx_hash=tx_hash,
                                success=True,
                                block_height=block_height,
                                symbol=cls.symbol,
                                memo=None,
                                from_address=from_address,
                                to_address=to_address,
                                token=None,
                                block_hash=block_hash,
                                value=tx_value,
                                tx_fee=tx_fee,
                                confirmations=cls.calculate_confirmation(date),
                                date=date
                            )
                            transfers.append(transfer)
        return transfers


class FlowdriverApi(GeneralApi, NobitexBlockchainBlockAPI):
    """
    Api Documentation : https://lucasconstantino.github.io/graphiql-online/
    """
    USE_PROXY = not settings.IS_VIP
    parser = FlowdriverResponseParser
    need_block_head_for_confirmation = False
    _base_url = 'https://api.findlabs.io/flowdiver/v1/graphql'
    TRANSACTIONS_LIMIT = 25
    PAGINATION_OFFSET = 0
    supported_requests = {
        'get_tx_details': '',
        'get_address_txs': ''
    }

    @classmethod
    def get_tx_details_body(cls, tx_hash: str) -> str:
        return json.dumps({
            'query':
                """
                query TransactionDetails($id: String) {
                    transactions(
                        where:
                            {
                                id: {_eq: $id} ,
                                    status : {_eq : SEALED}, error:{_eq:""},
                                    events :
                                        {name : {_in :["A.1654653399040a61.FlowToken.TokensWithdrawn",
                                                     "A.1654653399040a61.FlowToken.TokensDeposited"]
                                            }
                                    }
                                }
                        ){
                             ...BasicTransaction
                             ...ExtraDetails
                              __typename
                        }
                }
                fragment BasicTransaction on transactions {
                    id
                    timestamp
                    payer
                    authorizers
                    gas_used
                    fee
                    status
                    block_height
                    error
                    __typename
                }
                fragment ExtraDetails on transactions {
                    block_id
                    proposer
                    events(
                        where : {name : {_in : ["A.1654653399040a61.FlowToken.TokensWithdrawn",
                                             "A.1654653399040a61.FlowToken.TokensDeposited"]
                                    },
                            fields:{_has_keys_any:["from","to"]}
                            }
                    )
                    {
                         name
                         fields
                         __typename
                    }
                    __typename
                }
                """,
            'variables': {
                'id': tx_hash,
            }
        })

    @classmethod
    def get_address_txs_body(cls, address: str) -> str:
        return json.dumps({

            'query':
                """
                query AccountTransactions($limit:Int ,$offset: Int,$address: String){
                    participations(
                        limit:$limit
                        offset:$offset
                        where :
                            {address : {_eq : $address},
                                transaction:{status :{_eq :"SEALED"},error:{_eq:""},
                                    events : {name : {_in : ["A.1654653399040a61.FlowToken.TokensWithdrawn",
                                                          "A.1654653399040a61.FlowToken.TokensDeposited"]
                                        }
                                }
                            }
                        }
                        order_by: {timestamp: desc_nulls_first}
                    ){
                        roles
                        transaction {
                            ...BasicTransaction
                            ...TransactionEvents
                            events(where :{name : {_in : ["A.1654653399040a61.FlowToken.TokensWithdrawn",
                                                       "A.1654653399040a61.FlowToken.TokensDeposited"]
                                           },
                                       fields:{_has_keys_any:["from","to"]}
                                     }
                            ){
                                  fields
                                  __typename
                            }
                            __typename
                        }
                        __typename
                    }
                 }
                fragment BasicTransaction on transactions {
                    id
                    timestamp
                    payer
                    authorizers
                    gas_used
                    fee
                    status
                    block_height
                    block_id
                    error
                    __typename
                }
                fragment TransactionEvents on transactions {
                    events(where :
                                 {name : {_in : ["A.1654653399040a61.FlowToken.TokensWithdrawn",
                                               "A.1654653399040a61.FlowToken.TokensDeposited"]
                                 },
                                 fields:{_has_keys_any:["from","to"]}
                         }
                    )
                    {
                        id
                        name
                        __typename
                    }
                    __typename
                }
                """,
            'variables': {
                'address': address,
                'limit': cls.TRANSACTIONS_LIMIT,
                'offset': cls.PAGINATION_OFFSET
            }
        })
