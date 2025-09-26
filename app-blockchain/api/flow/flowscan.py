from abc import ABC
from collections import defaultdict
from decimal import Decimal
from typing import Any, Optional

from dateutil import parser
from django.conf import settings

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies
from exchange.blockchain.api.general_block_api import NobitexBlockchainBlockAPI
from exchange.blockchain.utils import BlockchainUtilsMixin


class FlowScan(NobitexBlockchainBlockAPI, BlockchainUtilsMixin, ABC):
    """
    coins: Flow
    API docs: no official documentation!
    Explorer: https://flowscan.org
    """
    rate_limit = 0  # no official or observed rate limit
    PRECISION = 8
    min_valid_tx_amount = Decimal('0.0')
    symbol = 'FLOW'
    cache_key = 'flow'
    currency = Currencies.flow
    USE_PROXY = bool(settings.IS_PROD and settings.NO_INTERNET and not settings.IS_VIP)
    SUPPORT_BATCH_BLOCK_PROCESSING = True
    FLOW_TOKEN_TESTNET_CONTRACT = '7e60df042a9c0868'  # noqa: S105
    FLOW_TOKEN_CONTRACT = '1654653399040a61'  # noqa: S105
    DEPOSIT_EVENT_CONTRACT = f'A.{FLOW_TOKEN_CONTRACT}.FlowToken.TokensDeposited'
    WITHDRAW_EVENT_CONTRACT = f'A.{FLOW_TOKEN_CONTRACT}.FlowToken.TokensWithdrawn'
    valid_contract = ['A.1654653399040a61.FlowToken']
    FEE_CONTRACT = ['A.f919ee77447b7497.FlowFees']
    FEE_ADDRESS = '0xf919ee77447b7497'
    valid_event_types = ['Deposit', 'Withdraw']
    valid_transfer_types = [DEPOSIT_EVENT_CONTRACT]
    TX_FILTER_QUERY = DEPOSIT_EVENT_CONTRACT
    FLOWSCAN_TOKEN = '5a477c43abe4ded25f1e8cc778a34911134e0590'  # noqa: S105
    excluded_addresses = ['0x1bf2b9d59ad1ba04']
    BLOCK_TIME = 2
    supported_requests = {
        'get_balance': '',
        'get_tx_details': '',
        'get_transactions': ''
    }

    def __init__(self) -> None:
        super().__init__()
        self.base_url = f'https://query.flowgraph.co/?token={self.FLOWSCAN_TOKEN}'

    def get_header(self) -> dict:
        return {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:104.0) Gecko/ https://flowscan.org/'
            if not settings.IS_VIP else
            'Mozilla/5.0 (X11; Linux x86_64; rv:95.0) Gecko/ https://flowscan.org/',
            'content-type': 'application/json',
            'origin': 'https://flowscan.org'
        }

    def get_balance_body(self, address: str) -> str:
        return f'{{"operationName":"AccountViewerByAddressQuery","variables":{{"id":"{address}"}},"query":"query AccountViewerByAddressQuery($id: ID!) {{\\n  account(id: $id) {{\\n    ...AccountViewerFragment\\n    __typename\\n  }}\\n}}\\n\\nfragment AccountViewerFragment on Account {{\\n  address\\n  tokenTransferCount\\n  nftTransferCount\\n  transactionCount\\n  tokenBalanceCount\\n  ...AccountHeaderFragment\\n  __typename\\n}}\\n\\nfragment AccountHeaderFragment on Account {{\\n  address\\n  balance\\n  domainNames {{\\n    fullName\\n    provider\\n    __typename\\n  }}\\n  creation {{\\n    time\\n    hash\\n    __typename\\n  }}\\n  contracts {{\\n    id\\n    type\\n    __typename\\n  }}\\n  __typename\\n}}\\n"}}'  # noqa: E501

    def parse_balance(self, response: dict) -> Decimal:
        balance = self.from_unit(int(response.get('data').get('account').get('balance')))
        return Decimal(balance)

    def get_details_body(self, tx_hash: str) -> str:
        return f'{{"operationName":"TransactionViewerLayoutQuery","variables":{{"id":"{tx_hash}"}},"query":"query TransactionViewerLayoutQuery($id: ID!) {{\\n  checkTransaction(id: $id) {{\\n    ...TransactionViewerHeaderFragment\\n    __typename\\n  }}\\n}}\\n\\nfragment TransactionViewerHeaderFragment on CheckTransactionResult {{\\n  status\\n  ...TransactionRolesFragment\\n  transaction {{\\n    hasError\\n    ...TransactionResultFragment\\n    ...TransactionTimeFragment\\n    ...TransactionTransfersFragment\\n    __typename\\n  }}\\n  __typename\\n}}\\n\\nfragment TransactionRolesFragment on CheckTransactionResult {{\\n  proposer {{\\n    address\\n    __typename\\n  }}\\n  payer {{\\n    address\\n    __typename\\n  }}\\n  authorizers {{\\n    address\\n    __typename\\n  }}\\n  __typename\\n}}\\n\\nfragment TransactionTimeFragment on Transaction {{\\n  time\\n  block {{\\n    height\\n    __typename\\n  }}\\n  __typename\\n}}\\n\\nfragment TransactionResultFragment on Transaction {{\\n  status\\n  error\\n  eventCount\\n  contractInteractions {{\\n    id\\n    __typename\\n  }}\\n  __typename\\n}}\\n\\nfragment TransactionTransfersFragment on Transaction {{\\n  tokenTransfers {{\\n    edges {{\\n      node {{\\n        type\\n        account {{\\n          address\\n          __typename\\n        }}\\n        amount {{\\n          token {{\\n            id\\n            __typename\\n          }}\\n          value\\n          __typename\\n        }}\\n        __typename\\n      }}\\n      __typename\\n    }}\\n    __typename\\n  }}\\n  nftTransfers {{\\n    edges {{\\n      node {{\\n        nft {{\\n          contract {{\\n            id\\n            __typename\\n          }}\\n          nftId\\n          __typename\\n        }}\\n        from {{\\n          address\\n          __typename\\n        }}\\n        to {{\\n          address\\n          __typename\\n        }}\\n        __typename\\n      }}\\n      __typename\\n    }}\\n    __typename\\n  }}\\n  __typename\\n}}\\n"}}'  # noqa: E501

    def parse_tx_details(self, response: dict, tx_hash: Optional[str] = None) -> dict:
        tx_details = response.get('data').get('checkTransaction')
        tx_status = tx_details.get('status')
        payer = tx_details.get('payer').get('address')
        has_error = tx_details.get('transaction').get('hasError')
        error = tx_details.get('transaction').get('error')
        block_height = tx_details.get('transaction').get('block').get('height')
        date = parser.parse(tx_details.get('transaction').get('time'))
        nodes = tx_details.get('transaction').get('tokenTransfers').get('edges')
        valid_events = defaultdict(list)
        tx_fee = None
        for node in nodes:  # to extract valid events
            contract = node.get('node').get('amount').get('token').get('id')
            event_type = node.get('node').get('type')
            address = node.get('node').get('account').get('address')
            tx_value = self.from_unit(int(node.get('node').get('amount').get('value')))
            if contract in self.valid_contract and event_type in self.valid_event_types:
                if address == self.FEE_ADDRESS:  # to skip fee deposit event and payer withdraw event with same value
                    tx_fee = tx_value
                    if tx_value in valid_events and \
                            {'event_type': 'Withdraw', 'address': payer} in valid_events[tx_value]:
                        valid_events[tx_value].remove({'event_type': 'Withdraw', 'address': payer})
                    if len(valid_events[tx_value]) == 0:
                        del valid_events[tx_value]
                    continue
                if tx_value == tx_fee and address == payer:
                    continue
                valid_events[tx_value].append({
                    'event_type': event_type,
                    'address': address,
                })
        linked_events = []
        for tx_value in valid_events:  # to link related events if there is only two event with same value
            tx = valid_events.get(tx_value)
            if len(tx) != 2:  # noqa: PLR2004
                linked_events = []
                break
            if tx[0].get('event_type') == tx[1].get('event_type'):
                break
            if tx[0].get('event_type') == 'Deposit':
                to_address = tx[0].get('address')
                from_address = tx[1].get('address')
            else:
                to_address = tx[1].get('address')
                from_address = tx[0].get('address')

            if to_address == self.FEE_ADDRESS:
                tx_fee = tx_value
            else:
                linked_events.append({'value': tx_value, 'to': to_address, 'from': from_address})
        inputs, outputs, transfers = [], [], []
        for event in linked_events:
            transfers.append({
                'type': 'transfer',
                'symbol': self.symbol,
                'currency': self.currency,
                'from': event.get('from'),
                'to': event.get('to'),
                'value': event.get('value'),
                'is_valid': True
            })
        # In case of more than two same-value events, we use in-outputs because we can not link them With confidence
        if not transfers:
            for tx_value in valid_events:
                for event in valid_events.get(tx_value):
                    event_dict = {
                        'currency': self.currency,
                        'address': event.get('address'),
                        'value': tx_value
                    }
                    if event.get('event_type') == 'Deposit':
                        outputs.append(event_dict)
                    else:
                        inputs.append(event_dict)
        if (inputs and outputs) or transfers:
            tx_detail = {
                'hash': tx_hash,
                'success': tx_status == 'Sealed' and not has_error and error is None,
                'inputs': inputs,
                'outputs': outputs,
                'transfers': transfers,
                'block': block_height,
                'confirmations': self.estimate_confirmation_by_date(date),
                'fees': tx_fee,
                'date': date,
                'raw': response
            }
        else:
            tx_detail = {
                'hash': tx_hash,
                'success': False
            }
        return tx_detail

    def get_txs_body(self, address: str) -> str:
        return f'{{"operationName":"AccountTransfersQuery","variables":{{"address":"{address}","first":30}},"query":"query AccountTransfersQuery($address: ID!, $first: Int!, $after: ID) {{\\n  account(id: $address) {{\\n    address\\n    transferCount\\n    tokenTransferCount\\n    nftTransferCount\\n    transferTransactions(first: $first, after: $after) {{\\n      pageInfo {{\\n        hasNextPage\\n        endCursor\\n        __typename\\n      }}\\n      edges {{\\n        ...AccountTransfersTableFragment\\n        __typename\\n      }}\\n      __typename\\n    }}\\n    __typename\\n  }}\\n}}\\n\\nfragment AccountTransfersTableFragment on AccountTransferEdge {{\\n  transaction {{\\n    hash\\n    time\\n    __typename\\n  }}\\n  tokenTransfers {{\\n    edges {{\\n      node {{\\n        type\\n        amount {{\\n          token {{\\n            id\\n            __typename\\n          }}\\n          value\\n          __typename\\n        }}\\n        counterparty {{\\n          address\\n          __typename\\n        }}\\n        counterpartiesCount\\n        __typename\\n      }}\\n      __typename\\n    }}\\n    __typename\\n  }}\\n  nftTransfers {{\\n    edges {{\\n      node {{\\n        from {{\\n          address\\n          __typename\\n        }}\\n        to {{\\n          address\\n          __typename\\n        }}\\n        nft {{\\n          contract {{\\n            id\\n            __typename\\n          }}\\n          nftId\\n          __typename\\n        }}\\n        __typename\\n      }}\\n      __typename\\n    }}\\n    __typename\\n  }}\\n  __typename\\n}}\\n"}}'  # noqa: E501

    def get_block_head(self) -> int:
        return 0

    def parse_get_txs_response(self, response: dict) -> Any:
        return response.get('data').get('account').get('transferTransactions').get('edges')

    def validate_transaction(self, tx: dict, address: Optional[str] = None) -> bool:
        if not tx.get('transaction').get('hash'):
            return False
        transfers = tx.get('tokenTransfers').get('edges')
        if len(transfers) != 1:
            return False
        tx = transfers[0].get('node')
        if tx.get('type') not in self.valid_event_types:
            return False
        if tx.get('amount').get('token').get('id') not in self.valid_contract:
            return False
        #  Check self tx
        if tx.get('counterparty').get('address') == address:
            return False
        if not self.validate_tx_amount(self.from_unit(int(tx.get('amount').get('value')))):
            return False
        return True

    def parse_tx(self, tx: dict, address: str, _: Optional[int] = None) -> Optional[dict]:
        tx_hash = tx.get('transaction').get('hash')
        date = parser.parse(tx.get('transaction').get('time'))
        transfer = tx.get('tokenTransfers').get('edges')[0].get('node')
        tx_type = transfer.get('type')
        tx_amount = transfer.get('amount').get('value')
        counterparty = transfer.get('counterparty').get('address')
        if tx_type == 'Withdraw':
            direction = 'outgoing'
            from_address = address
            to_address = counterparty
        elif tx_type == 'Deposit':
            direction = 'incoming'
            from_address = counterparty
            to_address = address
        else:
            return None
        if from_address in self.excluded_addresses:
            return None
        return {
            self.currency: {
                'address': address,
                'hash': tx_hash,
                'from_address': from_address,
                'to_address': to_address,
                'amount': self.from_unit(int(tx_amount)),
                'block': 0,
                'date': date,
                'confirmations': self.estimate_confirmation_by_date(date),
                'direction': direction,
                'raw': tx
            }
        }
