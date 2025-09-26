import pytz
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from abc import abstractmethod
from decimal import Decimal
from typing import List, Optional

from exchange.base.models import Currencies
from exchange.blockchain.api.ton.ton_explorer_interface import TonExplorerInterface
from exchange.blockchain.contracts_conf import ton_contract_info


class AbstractBlockchainExplorer:
    @classmethod
    @abstractmethod
    def get_transactions_details(cls, tx_hashes: List[str], network: str, currency: Optional[int]) -> dict:
        raise NotImplemented

    @classmethod
    @abstractmethod
    def get_wallets_balance(cls, address_list: dict, currency: Currencies):
        raise NotImplemented

    @classmethod
    @abstractmethod
    def get_wallet_transactions(cls, address, currency, network=None, tx_direction_filter=''):
        raise NotImplemented

    @classmethod
    @abstractmethod
    def get_latest_block_addresses(cls, network, after_block_number=None, to_block_number=None, include_inputs=False,
                                   include_info=False):
        raise NotImplemented

    @classmethod
    def get_transactions_values_by_address(cls, txs_data):
        """
        This method get a list of transactions data like tx hash, address in tx, tx network and currency related
            to the coin or token transferred in tx, and add tx details, value transferred in tx and memo, if existed,
            to it.
        Errors will be caught in lower layers and logged, here tx details will be None and value will be Zero in error
            cases.
        sample input: [
            {
                'hash': '0x6f661d01d67a177217450ff155da24099ee04ecfc3ef0f2f4914a441d96bd3a5',
                'address': '0x7b0e01a1e814e78a68c48f7bd3d59dcdbafdde05',
                'network': 'ETH',
                'currency': Currencies.eth,
                'memo': '' (required for tagged networks)
            },
        ]
        sample output: [
            {
                'hash': '0x6f661d01d67a177217450ff155da24099ee04ecfc3ef0f2f4914a441d96bd3a5',
                'address': '0x7b0e01a1e814e78a68c48f7bd3d59dcdbafdde05',
                'network': 'ETH',
                'currency': Currencies.eth,
                'value': Decimal('0.5'),
                'details: 'details of transaction',
                'memo': '',
            },
        ]
        """
        txs_details = {}
        txs_hashes_networks = {}

        # Separate different networks txs hashed to dict of networks as keys and list of related hashed as values.
        for item in txs_data:
            network_properties = txs_hashes_networks.get(item.get("network"))
            if network_properties:
                if network_properties.get(item.get('currency')):
                    network_properties.get(item.get('currency')).append(item.get("hash"))
                else:
                    network_properties[item.get('currency')] = [item.get("hash")]
            else:
                txs_hashes_networks[item.get("network")] = {item.get('currency'): [item.get("hash")]}

        # Get transactions details of each network
        for network, currencies in txs_hashes_networks.items():
            for currency, tx_hashes in currencies.items():
                txs_details.update(
                    cls.get_transactions_details(
                        tx_hashes=tx_hashes,
                        network=network,
                        currency=currency))

        # Search txs details to find value of coin or token transferred to each address
        for item in txs_data:
            currency = item.get("currency")
            item["value"] = Decimal("0")
            tx_details = txs_details.get(item.get("hash"))
            item["details"] = tx_details
            if tx_details is None:
                continue
            item["value"], memo = cls._get_transaction_values(
                tx_details, item.get("address"), currency, item.get('memo')
            )
            # Following tx_details.get("memo") is because of old structures, they store memo in outer layer of dict
            if not memo and tx_details.get("memo"):
                try:
                    if int(item.get('memo')) == int(tx_details.get("memo")):
                        memo = tx_details.get("memo")
                except:
                    memo = ""
            item["memo"] = memo
        return txs_data

    @classmethod
    def _get_transaction_values(cls, tx_details, address, currency, input_memo):
        memo = ''
        addresses = address if type(address) is list else [address]
        value = Decimal('0')
        tx_details['from_address'] = []
        values = []
        if tx_details.get('success'):
            for input_ in tx_details.get('inputs') or []:
                tx_details['from_address'].append(input_.get('address'))
                if (
                        input_.get('address') in addresses
                        and input_.get('currency') == currency
                ):
                    if input_.get('is_valid') is not False:
                        value = -input_.get('value')
                        address = input_.get('address')
                        values.append((value, '', address))
                    break
            for output in tx_details.get('outputs') or []:
                if (
                        output.get('address') in addresses
                        and output.get('currency') == currency
                ):
                    if output.get('is_valid') is not False:
                        value += output.get('value')
                        address = output.get('address')
                        values.append((value, '', address))

            transfers = tx_details.get('transfers') or []
            memo_exists = False
            for tr in transfers:
                # In cases where input_memo is None, it should prevent None == None
                if input_memo and tr.get('memo') and str(input_memo).strip() == str(tr.get('memo')).strip():
                    memo_exists = True
                    break

            for transfer in transfers:
                if (
                        transfer.get('is_valid') is not False
                        and transfer.get('currency') == currency
                ):
                    try:
                        if memo_exists and int(input_memo) != int(transfer.get('memo')):
                            continue
                    except (ValueError, TypeError):
                        continue

                    if transfer.get('from') in addresses:
                        value -= transfer.get('value')
                        memo = transfer.get('memo')
                        address = transfer.get('from')
                        values.append((value, memo, address))
                        continue
                    if transfer.get('to') in addresses:
                        tx_details['from_address'].append(transfer.get('from'))
                        value = transfer.get('value')
                        memo = transfer.get('memo')
                        address = transfer.get('to')
                        values.append((value, memo, address))

        return value, memo

    @classmethod
    def get_wallet_withdraws(cls, address, currency, network):
        withdraws = cls.get_wallet_transactions(address, currency, network, tx_direction_filter='outgoing') or {
            currency: []}
        start_time = pytz.timezone('UTC').localize(datetime.datetime.utcnow()) - datetime.timedelta(
            hours=5 if network == 'TON' else 3)
        time_filtered_withdraws = [wtd for wtd in withdraws.get(currency) if
                                   wtd.timestamp > start_time and wtd.value < Decimal('0')]
        if network != 'TON':
            return time_filtered_withdraws

        withdraws = time_filtered_withdraws  # withdraws.get(currency)

        token_withdraws = cls.process_token_withdraws_concurrently(address, network, start_time)

        for token_withdraw in token_withdraws:
            for withdraw in withdraws[:]:
                if withdraw.hash == token_withdraw.hash:
                    withdraws.remove(withdraw)
                    break
        withdraws += token_withdraws

        return withdraws

    @classmethod
    def process_token_withdraws_concurrently(cls, address, network, start_time):
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(cls.get_token_withdraws, address, token_currency, network, start_time)
                for token_currency in ton_contract_info.get('mainnet', {}).keys()
            ]

            token_withdraws = []
            for future in as_completed(futures):
                token_withdraws.extend(future.result())

        return token_withdraws

    @classmethod
    def get_token_withdraws(cls, address, token_currency, network, start_time):
        token_withdraws = cls.get_wallet_transactions(address, token_currency, network,
                                                      tx_direction_filter='outgoing') or {token_currency: []}
        token_withdraws = [wtd for wtd in token_withdraws.get(token_currency) if
                           wtd.timestamp > start_time and wtd.value < Decimal('0')]

        for token_withdraw in token_withdraws:
            withdraw_hash = TonExplorerInterface.get_withdraw_hash(tx_hash=token_withdraw.hash)
            if not withdraw_hash:
                continue
            token_withdraw.hash = withdraw_hash

        return token_withdraws

    @classmethod
    def _sync_token_and_main_coin_results(cls, main_coin_result, token_result):
        if not (main_coin_result and token_result):
            return main_coin_result, token_result

        max_main_coin_timestamp = max(main_coin_result, key=lambda tx: tx.timestamp).timestamp
        max_token_result_timestamp = max(token_result, key=lambda tx: tx.timestamp).timestamp

        if max_main_coin_timestamp > max_token_result_timestamp:
            main_coin_result = list(filter(lambda tx: tx.timestamp <= max_token_result_timestamp, main_coin_result))
        elif max_main_coin_timestamp < max_token_result_timestamp:
            token_result = list(filter(lambda tx: tx.timestamp <= max_main_coin_timestamp, token_result))

        return main_coin_result, token_result
