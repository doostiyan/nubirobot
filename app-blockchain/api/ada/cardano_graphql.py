import json
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from django.core.cache import cache

from exchange.base.models import Currencies
from exchange.base.parsers import parse_iso_date
from exchange.blockchain.api.general_block_api import NobitexBlockchainBlockAPI
from exchange.blockchain.metrics import metric_set
from exchange.blockchain.staking.staking_models import StakingInfo
from exchange.blockchain.utils import APIError, BlockchainUtilsMixin


class CardanoAPI(NobitexBlockchainBlockAPI, BlockchainUtilsMixin):
    """
    Cardano API explorer.

    supported coins: ada
    API docs: https://graphql.adatools.io/
    Explorer: https://explorer.cardano.org/graphql/
    """

    # https://explorer.cardano.org/graphql/
    # https://graphql-api.mainnet.dandelion.link/graphql/
    # https://mainnet-graphql.adatools.io/graphql/mainnet/
    _base_url = 'https://nodes4.nobitex1.ir/ada/graphql/'
    testnet_url = 'https://graphql-testnet.adatools.io/'
    symbol = 'ADA'
    currency = Currencies.ada
    active = True

    PRECISION = 6
    cache_key = 'ada'
    USE_PROXY = False
    SUPPORT_GET_BALANCE_BATCH = True

    def get_staking_info(self, address: str, start_date: datetime, end_date: datetime) -> StakingInfo:
        data = {
            'query': """
                query get_staking_info($address: StakeAddress!, $start_date: DateTime!, $end_date: DateTime!){
                  activeStake(where:{address :{_eq:$address}} limit:1 order_by:{ epochNo:desc}){
                    epochNo
                    address
                    amount
                  }
                  withdrawals(where:{address :{_eq:$address}}){
                    address
                    amount
                  }
                  rewards_aggregate(
                    where: {
                      _and: [
                        { address: {_eq:$address} }
                        {
                          receivedIn: {
                            _and: [
                              { startedAt: { _gte: $start_date } }
                              { startedAt: { _lt: $end_date } }
                            ]
                          }
                        }
                      ]
                    }
                  ){
                    aggregate{
                      sum{
                        amount
                      }
                    }
                  }
                }
            """,
            'variables': {
                'address': address,
                'start_date': start_date.strftime('%Y-%m-%dT%H:%M:%SZ'),
                'end_date': end_date.strftime('%Y-%m-%dT%H:%M:%SZ'),
            }
        }
        response = self.request('', headers={'Content-Type': 'application/json'}, body=json.dumps(data))
        if response.get('errors'):
            raise APIError('[CardanoAPI][GetStakingData] Response is none')
        data = response.get('data')
        if not data:
            raise APIError('[CardanoAPI][GetStakingData] Unsuccessful.')
        return self.parse_staking_info(data)

    def parse_staking_info(self, data: dict) -> StakingInfo:
        return StakingInfo(
            staked_balance=self.from_unit(int(data.get('activeStake')[0].get('amount') or 0)),
            claimed_rewards=self.from_unit(int(data.get('withdrawals')[0].get('amount') or 0)),
            rewards_balance=self.from_unit(
                int(data.get('rewards_aggregate').get('aggregate').get('sum').get('amount') or 0)),
        )

    def get_name(self) -> str:
        return 'ada_graphql'

    def get_tx_details(self, tx_hash: str) -> dict:
        data = {
            'query': """
                query get_tx($hash:Hash32Hex!){
                  transactions(where:{hash :{_eq:$hash}}){

                    fee
                    hash
                    inputs{
                      address
                      value
                    }
                    outputs{
                      address
                      value
                    }
                    block{
                      number
                    }
                    includedAt

                  }
                  cardano{
                    tip{
                      number
                    }
                  }
                }
            """,
            'variables': {
                'hash': tx_hash,
            }
        }
        response = self.request('', headers={'Content-Type': 'application/json'}, body=json.dumps(data))
        if not response:
            raise APIError('Response is none')
        if response.get('errors'):
            raise APIError('Response is none')
        tx = response.get('data')
        if not tx:
            raise APIError('Response is none')
        return self.parse_tx_details(tx)

    def parse_tx_details(self, tx_info: dict) -> dict:
        inputs = []
        outputs = []
        transfers = []
        tx = tx_info.get('transactions')[0]
        for input_ in tx.get('inputs'):
            inputs.append({
                'address': input_.get('address'),
                'value': self.from_unit(int(input_.get('value')))
            })
        for output in tx.get('outputs'):
            outputs.append({
                'address': output.get('address'),
                'value': self.from_unit(int(output.get('value')))
            })
        return {
            'hash': tx.get('hash'),
            'success': True,
            'inputs': inputs,
            'outputs': outputs,
            'transfers': transfers,
            'block': tx.get('block').get('number'),
            'confirmations': tx_info.get('cardano').get('tip').get('number') - tx.get('block').get('number'),
            'fees': self.from_unit(tx.get('fee')),
            'date': parse_iso_date(tx.get('includedAt')),
        }

    def get_balances(self, addresses: list) -> list:
        balances = []
        query = """
            query paymentAddressSummay(
              $addresses: [String!]!
            ) {
              paymentAddresses (addresses: $addresses) {
                address
                summary {
                  assetBalances {
                    quantity
                  }
                }
              }
            }
        """
        data = {
            'query': query,
            'variables': {
                'addresses': addresses
            }}

        response = self.request('', headers={'Content-Type': 'application/json'}, body=json.dumps(data))
        if not response:
            raise APIError('[CardanoAPI][GetBalance] Response is None.')
        if response.get('errors'):
            raise APIError('[CardanoAPI][GetBalance] Unsuccessful.')

        payments = response.get('data').get('paymentAddresses')
        for _, payment in zip(addresses, payments):
            balance = payment.get('summary', ).get('assetBalances')
            amount = Decimal(0) if len(balance) == 0 else balance[0].get('quantity')
            balances.append({
                self.currency: {
                    'address': payment.get('address'),
                    'balance': self.from_unit(int(amount))
                }
            })
        return balances

    def get_txs(self, address: str, limit: int = 25, _: int = 0) -> dict:
        query = """
            query getAddressTransactions($address: String!) {
                  transactions(
                    limit: %s
                    where: {
                        outputs: { address: { _eq: $address } }
                    }
                    order_by: { includedAt: desc }
                  ) {
                    block {
                      number
                    }
                    hash
                    fee
                    includedAt
                    inputs {
                      address
                      value
                    }
                    outputs {
                      address
                      value
                    }
                  }
                  cardano{
                    tip{
                      number
                    }
                  }
            }
        """
        data = {
            'query': query % limit,
            'variables': {
                'address': address
            }}

        response = self.request('', headers={'Content-Type': 'application/json'}, body=json.dumps(data))
        if not response:
            raise APIError('[CardanoAPI][GetBalance] Response is None.')
        if response.get('errors'):
            raise APIError('[CardanoAPI][GetBalance] Unsuccessful.')
        transactions = response.get('data').get('transactions')
        txs = []
        block_head = response.get('data').get('cardano').get('tip').get('number')
        for tx_info in transactions:
            parsed_tx = self.parse_tx(tx_info, address, block_head)
            if not parsed_tx:
                continue
            txs.append(parsed_tx)
        return txs

    def parse_tx(self, tx_info: dict, address: str, block_head: Optional[int] = None) -> dict:
        direction = 'outgoing'
        tx_hash = tx_info.get('hash')
        input_output_info = self.get_input_output_tx(tx_info, include_info=True)
        if input_output_info is None:
            return None
        input_addresses, inputs_info, output_addresses, outputs_info = input_output_info

        addresses = set(output_addresses).difference(input_addresses)

        if address.lower() in map(str.lower, addresses):
            direction = 'incoming'

        tx_output_info = outputs_info.get(address)
        tx_input_info = inputs_info.get(address)
        transactions_info = defaultdict(lambda: Decimal('0'))
        if tx_input_info:
            for currency, value in tx_input_info.items():
                transactions_info[currency] = value
        if tx_output_info:
            for currency, value in tx_output_info.items():
                if direction == 'outgoing':
                    transactions_info[currency] -= value
                else:
                    transactions_info[currency] = value
        amount = transactions_info.get(self.currency)
        if amount == Decimal('0'):
            return None
        block = tx_info.get('block').get('number')
        confirmations = block_head - block

        return {currency: {
            'date': parse_iso_date(tx_info['includedAt']),
            'block': block,
            'from_address': list(input_addresses),
            'to_address': addresses,
            'amount': amount,
            'fee': self.from_unit(int(tx_info['fee'])),
            'hash': tx_hash,
            'direction': direction,
            'confirmations': confirmations,
            'raw': tx_info
        } for currency in transactions_info}

    def get_input_tx(self, tx_info: dict, include_info: bool = False) -> tuple:
        input_addresses = set()
        inputs = tx_info.get('inputs') or []
        inputs_details = defaultdict(lambda: defaultdict(Decimal))
        for input_tx in inputs:
            address = input_tx.get('address') or []
            if not address:
                continue
            input_addresses.update([address])
            if include_info:
                inputs_details[address][self.currency] += self.from_unit(int(input_tx['value']))

        return input_addresses, inputs_details

    def get_output_tx(self, tx_info: dict, include_info: bool = False) -> tuple:
        output_addresses = set()
        outputs = tx_info.get('outputs') or []
        outputs_details = defaultdict(lambda: defaultdict(Decimal))
        for output_tx in outputs:
            address = output_tx.get('address')
            if not address:
                continue
            output_addresses.update([address])
            if include_info:
                outputs_details[address][self.currency] += self.from_unit(int(output_tx['value']))

        return output_addresses, outputs_details

    def get_input_output_tx(self, tx_info: dict, include_info: bool = False) -> tuple:
        input_addresses, inputs_info = self.get_input_tx(tx_info, include_info=include_info)
        output_addresses, outputs_info = self.get_output_tx(tx_info, include_info=include_info)
        return input_addresses, inputs_info, output_addresses, outputs_info

    def check_block_status(self) -> dict:
        query = """
            query{
              cardano{
                tip{
                    number
                }
              }
            }
        """
        data = {'query': query}

        response = self.request('', headers={'Content-Type': 'application/json'}, body=json.dumps(data))
        if not response:
            raise APIError('[CardanoAPI][CheckStatus] Response is None.')
        if response.get('errors'):
            raise APIError('[CardanoAPI][CheckStatus] Unsuccessful.')
        return {'blockNum': response.get('data').get('cardano').get('tip').get('number')}

    def get_block_head(self) -> Any:
        block = self.check_block_status()
        return block.get('blockNum')

    # Note: No one could not find a failed ada tx until I am writing this comment ,so we are not sure if this
    # method(api) skip failed tx or not
    def get_latest_block(self,
                         after_block_number: Optional[int] = None,
                         to_block_number: Optional[int] = None,
                         include_inputs: bool = False,
                         include_info: bool = True) -> Tuple[Dict[str, set], Dict[str, dict], int]:
        info = self.check_block_status()
        if not to_block_number:
            latest_block_height_mined = int(info.get('blockNum'))
            if not latest_block_height_mined:
                raise APIError('API Not Return block height')
        else:
            latest_block_height_mined = to_block_number

        cache_key = f'latest_block_height_processed_{self.cache_key}'

        if not after_block_number:
            latest_block_height_processed = cache.get(cache_key)
            if latest_block_height_processed is None:
                latest_block_height_processed = latest_block_height_mined - 5
        else:
            latest_block_height_processed = after_block_number

        if latest_block_height_mined > latest_block_height_processed:
            min_height = latest_block_height_processed + 1
        else:
            min_height = latest_block_height_mined + 1
        max_height = latest_block_height_mined + 1
        max_height = min(max_height, min_height + 100)

        transactions_addresses = {'input_addresses': set(), 'output_addresses': set()}
        transactions_info = {'outgoing_txs': defaultdict(lambda: defaultdict(list)),
                             'incoming_txs': defaultdict(lambda: defaultdict(list))}
        query = """
        query getBlockTxs($min_height: Int!, $max_height: Int!) {
              blocks(where:  {_and: [{number: {_gte: $min_height}}, {number: {_lt: $max_height}}]}) {
                hash,
                transactions {
                  hash
                  inputs {
                    address
                    value
                  }
                  outputs {
                    address
                    value
                  }
                  fee
                }
              }
            }
        """
        data = {
            'query': query,
            'variables': {
                'min_height': min_height,
                'max_height': max_height
            }}

        response = self.request('', headers={'Content-Type': 'application/json'}, body=json.dumps(data))
        if not response:
            raise APIError('[CardanoAPI][GetBalance] Response is None.')
        if response.get('errors'):
            raise APIError('[CardanoAPI][GetBalance] Unsuccessful.')

        for block in response.get('data').get('blocks'):
            transactions = block.get('transactions') or []
            for tx_info in transactions:
                input_output_info = self.get_input_output_tx(tx_info, include_info=include_info)
                if input_output_info is None:
                    continue
                input_addresses, inputs_info, output_addresses, outputs_info = input_output_info
                tx_hash = tx_info.get('hash')
                if not tx_hash:
                    continue
                addresses = set(output_addresses).difference(input_addresses)
                transactions_addresses['output_addresses'].update(addresses)

                if include_inputs:
                    transactions_addresses['input_addresses'].update(input_addresses)

                if include_info:
                    for address in transactions_addresses['output_addresses']:
                        tx_output_info = outputs_info[address]
                        for token, value in tx_output_info.items():
                            transactions_info['incoming_txs'][address][token].append({
                                'tx_hash': tx_hash,
                                'value': value,
                            })
                    if include_inputs:
                        for address in transactions_addresses['input_addresses']:
                            tx_output_info = outputs_info[address]
                            tx_input_info = inputs_info[address]
                            for coin, value in tx_input_info.items():
                                output_value = value - tx_output_info[coin]
                                if coin == self.currency:
                                    output_value -= self.from_unit(int(tx_info.get('fee', 0)))
                                transactions_info['outgoing_txs'][address][coin].append({
                                    'tx_hash': tx_hash,
                                    'value': output_value,
                                })

        last_cache_value = cache.get(cache_key) or 0
        if max_height - 1 > last_cache_value:
            metric_set(name='latest_block_processed', labels=[self.symbol.lower()], amount=max_height - 1)
            cache.set(cache_key, max_height - 1, 86400)
        return transactions_addresses, transactions_info, max_height - 1
