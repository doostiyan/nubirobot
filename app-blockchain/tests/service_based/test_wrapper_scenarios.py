import random
import time
from typing import Optional, List

if False:
    import yaml
    import schedule

from dataclasses import dataclass, field
from datetime import datetime

from exchange.blockchain.explorer import BlockchainExplorer
from exchange.blockchain.service_based.logging import logger


@dataclass
class NetworkProperties:
    network: str
    currency: int
    choose_rate: int
    active: bool
    is_memo_based: bool
    address_list: Optional[List[str]] = field(default_factory=list)


def get_errors_decorator(func):
    def inner(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception as e:
            logger.error(f'General exception occurred: {e}\n\n')
    return inner


def time_duration_decorator(func):
    def inner(*args, **kwargs):
        start_time = time.monotonic()
        func(*args, **kwargs)
        end_time = time.monotonic()
        logger.info(f'Total elapsed time: {end_time - start_time} seconds\n\n')

    return inner


def chunked_iterable(iterable, chunk_size):
    for i in range(0, len(iterable), chunk_size):
        yield iterable[i:i + chunk_size]


def _tx_diff_checker(tx, address, network_properties):
    tx_details = BlockchainExplorer.get_transactions_values_by_address(
        [
            {
                'hash': tx.hash,
                'address': address,
                'network': network_properties.network,
                'currency': network_properties.currency,
            },
        ]
    )
    if tx_details:
        # Compare addr_tx and tx_details in case of existence
        addr_tx_value, addr_tx_addr = tx.value, tx.address
        tx_details_value, tx_details_addr = tx_details[0].get('value'), tx_details[0].get('address')

        if abs(addr_tx_value) != abs(tx_details_value):
            logger.warning(
                f"Diff occurred: ---get-txs-value---: {abs(addr_tx_value)} "
                f"!= tx-details-value: {abs(tx_details_value)} in tx: {tx.hash}")
        if addr_tx_addr != tx_details_addr:
            logger.warning(
                f"Diff occurred: ---get-txs-addr---: {addr_tx_addr} "
                f"!= tx-details-addr: {tx_details_addr} in tx: {tx.hash}")


def _balance_diff_checker(addresses, network_properties, no_balance_message):
    if network_properties.network.casefold() == 'ETH'.casefold():
        for chunk in chunked_iterable(addresses, 19):
            addresses_balances = BlockchainExplorer.get_wallets_balance(
                {network_properties.network: list(chunk)},
                network_properties.currency)
            if not addresses_balances:
                logger.warning(no_balance_message.format(addresses=chunk))
    else:
        addresses_balances = BlockchainExplorer.get_wallets_balance(
            {network_properties.network: list(addresses)},
            network_properties.currency)
        if not addresses_balances:
            logger.warning(no_balance_message.format(addresses=addresses))


class TestMultipleWrapperScenarios:

    @time_duration_decorator
    @get_errors_decorator
    def core_simulation_memo_based(self, network_properties: NetworkProperties):
        addresses = network_properties.address_list
        for address in addresses:
            address_txs = BlockchainExplorer.get_wallet_transactions(address=address,
                                                                     currency=network_properties.currency,
                                                                     network=network_properties.network)
            addr_txs = address_txs.get(network_properties.currency)
            if not addr_txs:
                continue
            # Ensure at least one transaction is chosen
            sample_size = max(1, int(network_properties.choose_rate / 100.0 * len(addr_txs)))
            sampled_txs = random.sample(addr_txs, sample_size)
            for tx in sampled_txs:
                _tx_diff_checker(tx, address, network_properties)

    @time_duration_decorator
    @get_errors_decorator
    def core_simulation(self, network_properties: NetworkProperties):
        logger.info(f'Running Network: {network_properties.network}, Currency: {network_properties.currency}')
        block_txs = BlockchainExplorer.get_latest_block_addresses(network=network_properties.network,
                                                                  include_inputs=True,
                                                                  include_info=True)
        output_addresses = block_txs[0].get('output_addresses')
        if not output_addresses:
            return logger.info('There are no any output addresses')
        num_addresses_to_select = int(len(output_addresses) * (network_properties.choose_rate / 100.0))
        num_addresses_to_select = 1 if num_addresses_to_select == 0 else num_addresses_to_select
        addresses = random.sample(output_addresses, num_addresses_to_select)
        for address in addresses:
            address_txs = BlockchainExplorer.get_wallet_transactions(address=address,
                                                                     currency=network_properties.currency,
                                                                     network=network_properties.network)
            addr_txs = address_txs.get(network_properties.currency)
            if not addr_txs:
                continue
            latest_addr_tx = max(addr_txs, key=lambda tx: tx.timestamp)
            _tx_diff_checker(latest_addr_tx, address, network_properties)

    @time_duration_decorator
    @get_errors_decorator
    def cold_simulation(self, network_properties: NetworkProperties):
        no_balance_message = 'There are not any balances for given addresses: {addresses}\n'
        logger.info(f'Running Network: {network_properties.network}, Currency: {network_properties.currency}')
        block_txs = BlockchainExplorer.get_latest_block_addresses(network_properties.network,
                                                                  include_inputs=True,
                                                                  include_info=True)
        output_addresses = block_txs[0].get('output_addresses')
        if not output_addresses:
            return 'There are not any input addresses'
        num_addresses_to_select = int(len(output_addresses) * (network_properties.choose_rate / 100.0))
        num_addresses_to_select = 1 if num_addresses_to_select == 0 else num_addresses_to_select
        random_addresses = random.sample(output_addresses, num_addresses_to_select)
        _balance_diff_checker(random_addresses, network_properties, no_balance_message)

    @time_duration_decorator
    @get_errors_decorator
    def cold_simulation_memo_based(self, network_properties: NetworkProperties):
        no_balance_message = 'There are not any balances for given addresses: {addresses}\n'
        logger.info(f'Running Network: {network_properties.network}, Currency: {network_properties.currency}')
        addresses = network_properties.address_list
        _balance_diff_checker(addresses, network_properties, no_balance_message)

    def run_scheduled_jobs(self, network: Optional[str] = None):
        """
        If network passed so that it runs for the passed network otherwise, it will run whole config networks
        """
        with open('exchange/blockchain/tests/service_based/config.yaml', 'r') as f:
            data = yaml.load(f, Loader=yaml.FullLoader).get('networks')

        for network_name, network_property in data.items():
            if network and network_name.casefold() != network.casefold() or not network_property['active']:
                continue
            schedule_every = network_property.pop('schedule_every')
            if network_property['is_memo_based']:
                schedule.every(schedule_every).minutes.do(self.core_simulation_memo_based,
                                                          network_properties=NetworkProperties(
                                                              **network_property))
                # schedule.every(schedule_every).minutes.do(self.cold_simulation_memo_based,
                #                                           network_properties=NetworkProperties(
                #                                               **network_property))
            else:
                schedule.every(schedule_every).minutes.do(self.core_simulation,
                                                          network_properties=NetworkProperties(
                                                              **network_property))
                # schedule.every(schedule_every).minutes.do(self.cold_simulation,
                #                                           network_properties=NetworkProperties(
                #                                               **network_property))
        if not schedule.get_jobs():
            return 'There are not any scheduled jobs'

        logger.info(f'Starting test at {datetime.now()}\n')
        while True:
            schedule.run_pending()
            # sleep added to prevent the loop from consuming too much CPU
            time.sleep(1)
