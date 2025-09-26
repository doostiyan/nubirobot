"""
Coin Deposit Handling


APIs used for connecting to blockchains:
 * https://btc.com/api-doc

"""

import concurrent.futures
import datetime
import os
import random
import time
from collections import defaultdict
from decimal import ROUND_UP, Decimal
from typing import Iterable, List, Mapping, Set

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.utils.timezone import now

from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.formatting import f_m
from exchange.base.logging import log_event, report_exception
from exchange.base.models import (
    ACTIVE_CRYPTO_CURRENCIES,
    ADDRESS_TYPE,
    ALL_CRYPTO_CURRENCIES,
    NOT_COIN,
    PROCESSING_BLOCK_NETWORK,
    TAG_NEEDED_CURRENCIES,
    Currencies,
    Settings,
    get_address_type_codename,
    get_currency_codename,
)
from exchange.base.money import money_is_close
from exchange.blockchain.contracts_conf import (
    BASE_ERC20_contract_info,
    BEP20_contract_info,
    ERC20_contract_info,
    TRC20_contract_info,
    arbitrum_ERC20_contract_info,
    sol_contract_info,
    ton_contract_info,
)
from exchange.blockchain.explorer import BlockchainExplorer
from exchange.blockchain.inspector import BlockchainInspector
from exchange.blockchain.models import CurrenciesNetworkName, Transaction
from exchange.wallet.estimator import PriceEstimator
from exchange.wallet.models import (
    AvailableDepositAddress,
    AvailableHotWalletAddress,
    BalanceWatch,
    ConfirmedWalletDeposit,
    SystemColdAddress,
    WalletDepositAddress,
    WalletDepositTag,
)

confirmers = {}

DEFAULT_INTERNAL_DEPOSIT_CHECKER_NETWORK_TO_CURRENCY_MAP = {
    CurrenciesNetworkName.ETH: {Currencies.eth},
    CurrenciesNetworkName.BSC: {Currencies.bnb},
    CurrenciesNetworkName.FTM: {Currencies.ftm},
    CurrenciesNetworkName.AVAX: {Currencies.avax},
    CurrenciesNetworkName.ETC: {Currencies.etc},
    CurrenciesNetworkName.MATIC: {Currencies.pol},
    CurrenciesNetworkName.ONE: {Currencies.one},
    CurrenciesNetworkName.ARB: {Currencies.eth},
    CurrenciesNetworkName.TRX: {Currencies.trx},
    CurrenciesNetworkName.BASE: {Currencies.eth},
    CurrenciesNetworkName.SONIC: {Currencies.s},
}

class InternalDepositChecker:
    """A utility class to identify and filter out internal deposit transactions.

    This class provides functionality to determine if a specific currency is
    associated with a given network and to remove transactions that are considered
    "internal deposits" (i.e., originating from user deposit addresses within
    the system). By maintaining a mapping of networks to currencies, it can check
    the applicability of this rule and filter transaction details accordingly.
    the reason for this to not detect transactions between system because of providing fee.
    """

    READ_DB: str = 'replica' if 'replica' in settings.DATABASES else 'default'
    def __init__(self, network_to_currency_map: Mapping[str, Iterable[int]] = None):
        """Initializes an InternalDepositChecker instance.

        Args:
            network_to_currency_map: Optional mapping of network names to a
                collection of currency codes. If not provided, a default mapping
                of ethereum like networks with their main currency for fee will be used.

        Attributes:
            network_to_currency_map: A dictionary mapping network names to sets
                of currency codes. This mapping is used by the checker to
                determine if the rule applies to a given currency and network.
        """
        if network_to_currency_map is None:
            self.network_to_currency_map = DEFAULT_INTERNAL_DEPOSIT_CHECKER_NETWORK_TO_CURRENCY_MAP
        else:
            self.currencies_to_check = network_to_currency_map

    def is_rule_applicable(self, currency_code: int, network_name: str) -> bool:
        """Check if a given currency and is applicable based on its network in network_to_currency_map.

        Args:
            currency_code: The integer code representing the currency.
            network_name: The name of the network to check.

        Returns:
            A boolean indicating whether the specified currency is included in
            the network's currency set, and therefor applicable to filter transactions.
        """
        currencies_to_check = self.network_to_currency_map.get(network_name, set())
        return currency_code in currencies_to_check

    @classmethod
    def get_source_addresses(cls, txs_info: Iterable[Transaction]) -> Set[str]:
        """Extract unique source addresses from a collection of transactions.

        Args:
            txs_info: An iterable of `Transaction` objects.

        Returns:
            A set of unique source addresses found in the provided transactions.
        """
        source_addresses = set()
        for tx in txs_info:
            for address in tx.from_address:
                source_addresses.add(address)
        return source_addresses

    @classmethod
    def get_users_deposit_addresses(cls, source_addresses: Set[str]) -> Set[str]:
        """Retrieve deposit addresses that belong to users from a set of source addresses.

        This method queries the `WalletDepositAddress` model to find user-owned
        deposit addresses among the provided source addresses.

        Args:
            source_addresses: A set of source addresses to check against the
                wallet deposit database entries.

        Returns:
            A set of user deposit addresses.
        """
        return set(
            WalletDepositAddress.objects.using(cls.READ_DB)
            .filter(address__in=source_addresses)
            .values_list('address', flat=True)
        )

    def remove_internal_deposits_tx_detail(self, txs_details: Iterable[Transaction]) -> List[Transaction]:
        """Remove internal deposit transactions from a given set of transaction details.

        Internal deposits are defined as transactions whose `from_address` is a
        user deposit address. Such transactions will be filtered out and not
        returned in the final list.

        Args:
            txs_details: An iterable of `Transaction` objects to be filtered.

        Returns:
            A list of `Transaction` objects where internal deposit transactions
            have been removed.
        """
        source_addresses = self.get_source_addresses(txs_details)
        user_deposit_addresses = self.get_users_deposit_addresses(source_addresses)

        return [tx for tx in txs_details if all(address not in user_deposit_addresses for address in tx.from_address)]


def update_address_balances(currencies=None):
    if currencies is None:
        currencies = ACTIVE_CRYPTO_CURRENCIES
    currency_filter = Q(currency__in=currencies)
    addresses = WalletDepositAddress.objects.filter(currency_filter, is_disabled=False)

    MIN, MAX = 400, 700

    # Categorize wallets
    eligible_wallets = []
    outdated_wallets = []
    other_wallets = []
    for addr in addresses.select_related('wallet', 'wallet__user'):
        if addr.is_eligible_to_update():
            eligible_wallets.append(addr)
        elif addr.is_balance_outdated():
            outdated_wallets.append(addr)
        else:
            other_wallets.append(addr)

    # Check size of eligible wallets list
    to_select = 0
    if len(eligible_wallets) < MAX:
        to_select = MAX - len(eligible_wallets)
        eligible_wallets += random.sample(outdated_wallets, min(len(outdated_wallets), to_select))
    if len(eligible_wallets) < MIN:
        to_select = MIN - len(eligible_wallets)
    eligible_wallets += random.sample(other_wallets, min(len(other_wallets), to_select))

    # Batch wallets by currency
    batches = []
    user_wallets = 0
    system_wallets = 0
    for currency in currencies:
        batch = []
        batch_size = 100 if currency in [Currencies.btc, Currencies.trx] else 30
        for addr in eligible_wallets:
            if addr.currency != currency:
                continue
            batch.append(addr)
            user_wallets += 1
            if len(batch) >= batch_size:
                batches.append(batch)
                batch = []

        # batch hot and system cold addresses by currency
        hot_addresses = AvailableHotWalletAddress.objects.filter(currency_filter)
        system_cold_addresses = SystemColdAddress.objects.filter(currency_filter, is_disabled=False)
        for addr in list(hot_addresses) + list(system_cold_addresses):
            if addr.currency != currency:
                continue
            if isinstance(addr, SystemColdAddress) and addr.is_disabled:
                continue
            batch.append(addr)
            system_wallets += 1
            if len(batch) >= batch_size:
                batches.append(batch)
                batch = []

        if batch:
            batches.append(batch)
    random.shuffle(batches)
    skipped_wallets = len(addresses) - user_wallets
    print('Users: {},  System: {},  Batches: {},  Skipped: {}'.format(
        user_wallets, system_wallets, len(batches), skipped_wallets))

    # Update wallets' balances
    for batch in batches:
        update_address_balances_for_currency(batch)
        time.sleep(1)
    print('Done')


def update_address_balances_for_currency(addresses, sleep=1, is_segwit=False, quiet=False):
    if not addresses:
        return
    currency = addresses[0].currency
    addresses_map = {w.address: w for w in addresses if not isinstance(w, WalletDepositAddress) or w.contract_address is None}
    addresses_tuple = [(w.address, w.get_network()) for w in addresses if not isinstance(w, WalletDepositAddress) or w.contract_address is None]
    if not quiet:
        print('[{}] Processing {} wallets...'.format(get_currency_codename(currency).upper(), len(addresses)), end='\t' * 4)
    wallets_balances = BlockchainExplorer.get_wallets_balance(addresses_tuple, currency)
    if not wallets_balances:
        if not quiet:
            print('[FAILED]')
        time.sleep(sleep)
        return 0
    if isinstance(wallets_balances, dict):
        wallets_balances = wallets_balances[currency]
    for wallet_info in wallets_balances:
        if not wallet_info:
            continue
        addr = wallet_info['address']
        obj = addresses_map.get(addr)
        if not obj:
            print('Warning: a returned address was not requested!')
            continue
        received = wallet_info['received']
        sent = wallet_info['sent']
        initial_balance = obj.total_received - obj.total_sent
        update_fields = []
        if obj.total_received != received:
            obj.total_received = received
            update_fields.append('total_received')
        if obj.total_sent != sent:
            obj.total_sent = sent
            update_fields.append('total_sent')
        current_balance = obj.total_received - obj.total_sent
        if not money_is_close(current_balance, initial_balance):
            obj.last_update = now()
            update_fields.append('last_update')
            if isinstance(obj, WalletDepositAddress):
                obj.needs_update = obj.needs_update or current_balance > initial_balance
                update_fields.append('needs_update')
            if settings.FULL_LOGGING:
                log_event('{} Wallet balance updated for {}: {} -> {}'.format(
                    obj.get_currency_display(),
                    addr,
                    f_m(initial_balance, c=obj.currency),
                    f_m(current_balance, c=obj.currency),
                ), level='info', module='wallet', category='update', runner='deposit')
        if isinstance(obj, BalanceWatch):
            obj.last_update_check = now()
            update_fields.append('last_update_check')
        obj.save(update_fields=update_fields)
    if not quiet:
        print('[OK]')
    return len(wallets_balances)


def refresh_wallet_deposits(wallet, run_now=False):
    available_non_memo_network = [network
                                  for network, info in CURRENCY_INFO.get(wallet.currency).get('network_list').items() if
                                  info.get('deposit_enable', True) and not wallet.is_address_tag_required(network=network)]

    if len(available_non_memo_network) <= 0:
        # Tagged deposits are handled directly in UpdatePendingDepositsCron
        return
    if 'BTCLN' in available_non_memo_network:
        available_non_memo_network.remove('BTCLN')
        refresh_wallet_invoice_deposits(wallet, 'BTCLN')

    if run_now:
        if wallet.currency not in confirmers:
            return
        network_query = Q(network__in=available_non_memo_network) | Q(network__isnull=True)
        deposit_addresses = WalletDepositAddress.objects.filter(wallet=wallet, is_disabled=False).filter(network_query)
        for addr in deposit_addresses.select_related('wallet'):
            confirmers[wallet.currency](addr)
    else:
        for network in available_non_memo_network:
            deposit_address = wallet.get_current_deposit_address(network=network)
            if deposit_address:
                deposit_address.enqueue_for_update()


def refresh_wallet_invoice_deposits(wallet, network='BTCLN'):
    invoices_deposit = ConfirmedWalletDeposit.objects.filter(_wallet=wallet,
                                                             invoice__isnull=False,
                                                             expired=False,
                                                             confirmed=False,
                                                             created_at__gt=now()-datetime.timedelta(hours=3))
    for invoice_deposit in invoices_deposit:
        invoice_info = BlockchainInspector.get_invoice_status(invoice_deposit.tx_hash, wallet.currency)
        if not invoice_info:
            continue
        tx_hash = invoice_info['hash']
        tx_value = invoice_info['value']
        tx_invoice = invoice_info['invoice']
        tx_timestamp = invoice_info['timestamp']
        if tx_invoice != invoice_deposit.invoice:
            continue
        confirmation = 1 if invoice_info.get('state') == 'SETTLED' else 0

        if invoice_info['state'] not in ['OPEN', 'SETTLED']:
            invoice_deposit.expired = True
            invoice_deposit.save(update_fields=['expired'])

        if invoice_info['state'] != 'SETTLED':
            continue

        transaction = Transaction(
            hash=tx_hash,
            invoice=tx_invoice,
            value=tx_value,
            timestamp=tx_timestamp,
            confirmations=confirmation,
        )
        save_deposit_from_blockchain_transaction_invoice(transaction, currency=wallet.currency, network=network)


def refresh_address_deposits(wallet_deposit_address, retry=False):
    """ Recheck blockchain for any new deposits made to this WalletDepositAddress
    """
    currency = wallet_deposit_address.currency
    confirmers[currency](wallet_deposit_address, retry=retry, currency=currency)


def update_deposits(currencies=None):
    deposit_addresses = WalletDepositAddress.objects.all().select_related('wallet').exclude(
        network__in=PROCESSING_BLOCK_NETWORK
    )
    if currencies is not None:
        deposit_addresses = deposit_addresses.filter(wallet__currency__in=currencies)
    for addr in deposit_addresses:
        if addr.wallet.currency in confirmers:
            confirmers[addr.wallet.currency](addr)
    # Tagged Deposits
    if currencies is None:
        confirm_tagged_deposits()
    else:
        for c in currencies:
            if c in TAG_NEEDED_CURRENCIES:
                confirm_tagged_deposits(currency=c)


def confirm_bitcoin_deposits(addr: WalletDepositAddress, retry=False, **_):
    """ Check for and confirm all recent deposits to the given WalletDepositAddress
    """
    # Basic Checks
    if addr is None:
        return
    currency_name = get_currency_codename(addr.wallet.currency)
    network = addr.get_network()
    default_value = 'yes' if CURRENCY_INFO[addr.wallet.currency]['network_list'][network].get('deposit_enable', True) else 'no'
    cache_key = f'deposit_enabled_{currency_name}_{network.lower()}'
    if addr.contract_address:
        cache_key += f'_{addr.contract_address}'
    if not Settings.get_trio_flag(
        cache_key,
        default=default_value,  # all network in network_list filter by withdraw_enable=True
        third_option_value=cache.get(f'binance_deposit_status_{currency_name}_{network}'),
    ):
        time.sleep(1)
        return
    if addr.is_disabled:
        print('Address is disabled')
        return
    # Starting check
    message = f'Checking {addr.wallet.get_currency_display()} address in {network} network: {addr.address}'
    if addr.contract_address:
        message += f'(with contract: {addr.contract_address})'
    print(message, end='..')
    time.sleep(0.3)
    # Get address transactions from blockchain
    try:
        txs_object = BlockchainExplorer.get_wallet_transactions(
            addr.address, addr.wallet.currency, network=network, contract_address=addr.contract_address
        )
    except Exception:
        report_exception()
        txs_object = None
    if txs_object is None:
        print('BLOCKCHAIN INSPECT FAILED!')
        return

    # Process and save deposits
    ignore_before_date = now() - datetime.timedelta(days=3)
    if addr.is_disabled:
        ignore_before_date -= datetime.timedelta(days=7)
    if currency_name == 'etc':
        ignore_before_date -= datetime.timedelta(days=11)
    if currency_name == 'xmr':
        ignore_before_date -= datetime.timedelta(days=60)
    if isinstance(txs_object, dict):
        deposit_internal_checker_rule = InternalDepositChecker()
        for currency, txs in txs_object.items():
            if deposit_internal_checker_rule.is_rule_applicable(currency, network):
                txs = deposit_internal_checker_rule.remove_internal_deposits_tx_detail(txs)
            network_model_filter = Q(network=network)
            if network == CURRENCY_INFO[currency]['default_network']:
                network_model_filter |= Q(network__isnull=True)
            new_addr = addr
            if currency != addr.wallet.currency:
                try:
                    new_addr = WalletDepositAddress.get_unique_instance(address=addr.address, currency=currency, network=network, contract_address=addr.contract_address)
                except WalletDepositAddress.DoesNotExist:
                    print('No such {} address: {}'.format(get_currency_codename(currency), addr.address))
                    continue
            print('.\t\t\t[{}TXs]'.format(len(txs)))
            for tx in txs:
                save_deposit_from_blockchain_transaction(tx, new_addr, ignore_before_date=ignore_before_date)
    elif isinstance(txs_object, list):
        txs = txs_object
        print('.\t\t\t[{}TXs]'.format(len(txs)))
        for tx in txs:
            save_deposit_from_blockchain_transaction(tx, addr, ignore_before_date=ignore_before_date)
    addr.last_deposit_check = now()
    addr.save(update_fields=['last_deposit', 'last_deposit_check'])


def validate_transaction(tx: Transaction, currency, network, address_type=ADDRESS_TYPE.standard, ignore_before_date=None, is_tagged=False, is_invoice=False):
    network_key = network or CURRENCY_INFO[currency]['default_network']
    network_deposit_info = CURRENCY_INFO[currency]['network_list'][network_key].get('deposit_info', {}).get(get_address_type_codename(address_type), {})

    ###############
    # Check hash
    ###############
    tx_hash = tx.hash
    if not tx_hash:
        return
    if tx_hash.startswith('0x') and len(tx_hash) > 20 and currency in [Currencies.eth, Currencies.etc, Currencies.usdt]:
        tx_hash = tx_hash[2:]

    ###############
    # Check time
    ###############
    tx_datetime = tx.timestamp
    print('\tTX#{}'.format(tx_hash), end='\t')

    # Check transaction validity
    if tx_datetime is None:
        print('[Invalid]')
        return

    if network == 'BSC' and tx_datetime < settings.BSC_NETWORK_LAUNCH:
        print('[BSC Before launch]')
        return

    # Ignore old transactions
    if ignore_before_date and tx_datetime < ignore_before_date:
        print('[Old]')
        return

    ###############
    # Check value
    ###############
    # Get deposited value
    if tx.value < Decimal('0'):
        print('[Withdraw]')
        return

    if tx.value == Decimal('0'):
        if not tx.huge:
            print('[Zero]')
            return
        print('[Huge]', end=' ')

    if settings.DEPOSIT_MIN_CHECK_ENABLED and tx.value < Decimal(network_deposit_info.get('deposit_min', '0.00000000')):
        print('[Dust]')
        return

    tx_value = tx.value
    if settings.DEPOSIT_FEE_ENABLED:
        tx_value -= Decimal(network_deposit_info.get('deposit_fee', '0.00000000'))

    if tx.contract_address and tx.contract_address in CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.keys():
        cache_key = f'deposit_fee_{get_currency_codename(currency)}_{network.lower()}_{tx.contract_address}'
        deposit_fee = Settings.get(cache_key, '0')
        tx_value -= Decimal(deposit_fee)

    if tx_value <= Decimal('0'):
        print('[Zero-Fee]')
        return
    tx_value = tx_value.quantize(Decimal('0.0000000001'), rounding=ROUND_UP)

    raw_sources_list = tx.from_address or []

    if not isinstance(raw_sources_list, list) or [raw_record for raw_record in raw_sources_list if not isinstance(raw_record, str)]:
        # to make sure that from_addresses definitely is a list of strings before parsing it
        raw_sources_list = []
        report_exception()

    source_addresses = defaultdict(lambda: defaultdict())

    for addr in raw_sources_list:
        source_addresses[addr] = defaultdict()

    result = {
        'hash': tx_hash,
        'datetime': tx_datetime,
        'value': tx_value,
        'source_addresses': source_addresses,
        'contract_address': tx.contract_address if tx.contract_address in CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.keys() else None,
    }

    ###############
    # Check tag if needed
    ###############
    if is_tagged:
        tag = tx.tag
        if not tag:
            print('[Tag] no tag, ignoring...')
            return
        try:
            tag = int(tag)
        except ValueError:
            print('[Tag] tag value is not numeric')
            return
        result['tag'] = tag

    ###############
    # Check invoice if needed
    ###############
    if is_invoice:
        invoice = tx.invoice
        if not invoice:
            print('[Invoice] no invoice, ignoring...')
            return
        result['invoice'] = invoice
    return result


def save_deposit_from_blockchain_transaction(blockchain_transaction, deposit_address, ignore_before_date=None):
    """ Process a transaction in blockchain and save deposit in DB if there is
        any deposit to the given deposit_address in the blockchain_transaction
    """
    with transaction.atomic():
        tx = blockchain_transaction
        wallet, address = deposit_address.wallet, deposit_address.address
        if deposit_address.is_disabled:
            return
        network, currency, addr_type = deposit_address.network, deposit_address.currency, deposit_address.type
        if currency == Currencies.unknown:
            currency = wallet.currency
        # Validate transaction params
        tx_info = validate_transaction(tx=tx, currency=currency, network=network, address_type=addr_type,
                                       ignore_before_date=ignore_before_date, is_tagged=False)
        if tx_info is None:
            return
        tx_hash, tx_value, tx_datetime, tx_source, tx_contract_address = tx_info['hash'], tx_info['value'], tx_info['datetime'], tx_info['source_addresses'], tx_info.get('contract_address')

        # Get Deposit Object
        try:
            deposit = ConfirmedWalletDeposit.objects.get(tx_hash=tx_hash, address=deposit_address, contract_address=tx_contract_address)
        except ConfirmedWalletDeposit.DoesNotExist:
            rial_value = PriceEstimator.get_rial_value_by_best_price(tx_value, wallet.currency, 'sell')
            deposit = ConfirmedWalletDeposit.objects.create(
                _wallet=wallet,
                tx_hash=tx_hash,
                address=deposit_address,
                amount=tx_value,
                rial_value=rial_value,
                source_addresses=tx_source,
                contract_address=tx_contract_address,
                tx_datetime=tx_datetime
            )
        if deposit.address.address != address:
            log_event('DepositMismatchedAddress', level='warning', module='wallet', category='notice', runner='deposit')
            print('[MismatchedAddress]')
            return
        if not deposit.validated:
            deposit.validated = True
            deposit.save(update_fields=['validated'])
        # Ignore already processed deposits
        if deposit.confirmed:
            if not deposit_address.last_deposit or tx_datetime > deposit_address.last_deposit:
                deposit_address.last_deposit = tx_datetime
            print('[AlreadyConfirmed]')
            return
        # Update amount in case or invalild amount
        deposit.amount = tx_value

        # Add transaction datetime
        deposit.tx_datetime = tx_datetime

        # Update confirmations count
        deposit.confirmations = tx.confirmations

        # Check confirmations and add to wallet balance
        needed_confirms = deposit.required_confirmations
        print('confirms={}/{}'.format(tx.confirmations, needed_confirms), end='\t')
        if tx.is_double_spend:
            print('[!DoubleSpend]', end='\t')
            needed_confirms *= 3
        if tx.confirmations >= needed_confirms:
            deposit.confirmed = True
            wallet.refresh_from_db()
            _transaction = wallet.create_transaction(
                tp='deposit',
                amount=tx_value,
                description='Deposit - address:{}, tx:{}'.format(address, tx_hash),
                allow_negative_balance=True,
            )
            if _transaction is None:
                print('[TransactionFailed]')
            else:
                _transaction.commit(ref=deposit, allow_negative_balance=True)
                deposit.transaction = _transaction
                print('[Confirmed]')

            # To save source addresses
            deposit.source_addresses = tx_source
            deposit.save()
            if not deposit_address.last_deposit or tx_datetime > deposit_address.last_deposit:
                deposit_address.last_deposit = tx_datetime
        else:
            deposit.save(update_fields=['confirmations', 'amount', 'tx_datetime'])
            print('[NotConfirmedYet]')


def save_deposit_from_blockchain_transaction_tagged(
    blockchain_transaction,
    deposit_address_info,
    currency,
    network=None,
    addr_type=ADDRESS_TYPE.standard,
    ignore_before_date=None,
):
    with transaction.atomic():
        tx = blockchain_transaction
        address = deposit_address_info['address']
        tag_required = deposit_address_info['used_for'] is None

        # TODO: Move this part to validate_transaction
        transaction_address = tx.address
        if address != transaction_address:
            print('[AddressMismatch]')
            return
        # Validate transaction params
        tx_info = validate_transaction(
            tx=tx,
            currency=currency,
            network=network,
            address_type=addr_type,
            ignore_before_date=ignore_before_date,
            is_tagged=tag_required,
        )
        if tx_info is None:
            return
        tx_hash, tx_value, tx_source, tag, tx_datetime = (
            tx_info['hash'],
            tx_info['value'],
            tx_info['source_addresses'],
            tx_info.get('tag'),
            tx_info.get('datetime')
        )
        if tag is None and tag_required:
            print('[TagDoesNotProvided]')
            return
        if tag_required:
            tag_wallet = (
                WalletDepositTag.objects.filter(tag=tag, wallet__currency=currency).select_related('wallet').first()
            )
            if not tag_wallet:
                print('[NotDedicateTag]')
                return
            wallet = tag_wallet.wallet
            unique_filter = Q(tag=tag_wallet)
            tag_address_wallet = None
        else:
            tag_address_wallet = (
                WalletDepositAddress.objects.filter(address=address, wallet__currency=currency)
                .select_related('wallet')
                .first()
            )
            if not tag_address_wallet:
                print('[NotDedicateWallet]')
                return
            wallet = tag_address_wallet.wallet
            unique_filter = Q(address=tag_address_wallet)
            tag_wallet = None
        # Get Deposit Object
        try:
            deposit = ConfirmedWalletDeposit.objects.get(unique_filter, tx_hash=tx_hash)
        except ConfirmedWalletDeposit.DoesNotExist:
            rial_value = PriceEstimator.get_rial_value_by_best_price(tx_value, currency, 'sell')
            deposit = ConfirmedWalletDeposit.objects.create(
                _wallet=wallet,
                tx_hash=tx_hash,
                tag=tag_wallet,
                rial_value=rial_value,
                source_addresses=tx_source,
                address=tag_address_wallet,
                tx_datetime=tx_datetime
            )
        if not deposit.validated:
            deposit.validated = True
            deposit.save(update_fields=['validated'])

        # Ignore already processed deposits
        if deposit.confirmed:
            print('[AlreadyConfirmed]')
            return

        # Set object values
        deposit.amount = tx_value
        deposit.confirmations = tx.confirmations
        deposit.tx_datetime = tx_datetime

        # Check confirmations and add to wallet balance
        needed_confirms = deposit.required_confirmations
        print('confirms={}/{}'.format(tx.confirmations, needed_confirms), end='\t')
        if tx.is_double_spend:
            print('[!DoubleSpend]', end='\t')
            needed_confirms += 1
        if tx.confirmations >= needed_confirms:
            _transaction = wallet.create_transaction(
                tp='deposit',
                amount=tx.value,
                description='Deposit - address:{}, tx:{}'.format(address, tx_hash),
                allow_negative_balance=True,
            )
            _transaction.commit(ref=deposit, allow_negative_balance=True)
            deposit.confirmed = True
            deposit.transaction = _transaction
            deposit.source_addresses = tx_source
            deposit.save()
            print('[Confirmed]')
        else:
            deposit.save(update_fields=['amount', 'confirmations', 'tx_datetime'])
            print('[NotConfirmedYet]')


def save_deposit_from_blockchain_transaction_invoice(blockchain_transaction, currency, network=None, addr_type=ADDRESS_TYPE.standard, ignore_before_date=None):
    with transaction.atomic():
        tx = blockchain_transaction

        # Validate transaction params
        tx_info = validate_transaction(tx=tx, currency=currency, network=network, address_type=addr_type,
                                       ignore_before_date=ignore_before_date, is_tagged=False, is_invoice=True)
        if tx_info is None:
            return
        tx_hash, tx_value, tx_datetime, tx_invoice = tx_info['hash'], tx_info['value'], tx_info['datetime'], tx_info['invoice']

        try:
            deposit = ConfirmedWalletDeposit.objects.get(tx_hash=tx_hash, invoice=tx_invoice)
        except ConfirmedWalletDeposit.DoesNotExist:
            return

        if not deposit.validated:
            deposit.validated = True
            deposit.save(update_fields=['validated'])

        # Ignore already processed deposits
        if deposit.confirmed:
            print('[AlreadyConfirmed]')
            return

        wallet = deposit.wallet
        if not wallet:
            print('[NotInvoiceWallet]')
            return
        # Set object values
        deposit.amount = tx_value
        deposit.confirmations = tx.confirmations

        # Check confirmations and add to wallet balance
        needed_confirms = deposit.required_confirmations
        print('confirms={}/{}'.format(tx.confirmations, needed_confirms), end='\t')
        if tx.is_double_spend:
            print('[!DoubleSpend]', end='\t')
            needed_confirms += 1
        if tx.confirmations >= needed_confirms:
            _transaction = wallet.create_transaction(
                tp='deposit',
                amount=tx.value,
                description='Deposit - invoice_hash:{}'.format(tx_hash),
                allow_negative_balance=True,
            )
            _transaction.commit(ref=deposit, allow_negative_balance=True)
            deposit.confirmed = True
            deposit.transaction = _transaction
            deposit.save()
            print('[Confirmed]')
        else:
            deposit.save(update_fields=['amount', 'confirmations'])
            print('[NotConfirmedYet]')


# TODO: Fix type hint must be TypeVar
def grab_tagcoins_deposit_address(currency: Currencies) -> List[dict]:
    """To get a tag coin deposit address(es) whether from cache or db
    currency: tag coin we need its address(es)
    output: simply a list of strings
    """
    if currency in ton_contract_info['mainnet'].keys():
        currency = Currencies.ton
    addresses = cache.get(f'tag_deposit_address_on_{get_currency_codename(currency).upper()}')
    if not addresses or isinstance(addresses, str):
        # Table of available addresses may be very large, so this query is optimized
        #  by idx_tagged_currencies_address index.
        addresses = list(
            AvailableDepositAddress.objects.filter(currency=currency).order_by('-pk').values('address', 'used_for')
        )
        cache.set(f'tag_deposit_address_on_{get_currency_codename(currency).upper()}', addresses, 86400)
    return addresses


# TODO: Fix type hint must be TypeVar
def tag_coins_addresses(currency: Currencies) -> List[str]:
    """Returns only addresses in array"""
    addresses_info = grab_tagcoins_deposit_address(currency)
    return [address_info['address'] for address_info in addresses_info]


def confirm_tagged_deposits(currency=None, network=None, **_):
    """ Check for and confirm all recent deposits to the given currency
    """
    # Check currency
    if currency is None:
        for c in TAG_NEEDED_CURRENCIES:
            confirm_tagged_deposits(currency=c, network=network)
        # max_workers = min([len(TAG_NEEDED_CURRENCIES), os.cpu_count() * 2])
        # with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        #     features = list()
        #     for c in TAG_NEEDED_CURRENCIES:
        #         features.append(executor.submit(confirm_tagged_deposits, c, network))
        #     concurrent.futures.wait(features)
        return
    if currency not in TAG_NEEDED_CURRENCIES:
        raise ValueError('Cannot confirm currencies without tag')

    # Basic Checks
    currency_name = get_currency_codename(currency)
    network = network or CURRENCY_INFO[currency]['default_network']
    default_value = 'yes' if CURRENCY_INFO[currency]['network_list'][network].get('deposit_enable', True) else 'no'
    if not Settings.get_trio_flag(
        f'deposit_enabled_{currency_name}_{network.lower()}',
        default=default_value,  # all network in network_list filter by withdraw_enable=True
        third_option_value=cache.get(f'binance_deposit_status_{currency_name}_{network}'),
    ):
        time.sleep(1)
        return

    addresses_info = grab_tagcoins_deposit_address(currency=currency)
    ignore_before_date = now() - datetime.timedelta(days=5)
    for address_info in addresses_info:
        print('Checking {} Address: {}'.format(currency_name, address_info['address']), end='..')

        # Get Address Transactions
        try:
            txs_object = BlockchainExplorer.get_wallet_transactions(address_info['address'], currency, network=network)
            print(txs_object)
        except Exception:
            report_exception()
            txs_object = None
        if txs_object is None:
            time.sleep(0.5)
            print('BLOCKCHAIN INSPECT FAILED!')
            return
        print('.')
        if isinstance(txs_object, dict):
            txs = txs_object[currency]
        elif isinstance(txs_object, list):
            txs = txs_object
        else:
            txs = []
        for tx in txs:
            save_deposit_from_blockchain_transaction_tagged(
                tx, address_info, currency, network=None, ignore_before_date=ignore_before_date
            )


# Debugging functions
def debug_print_deposit_queue():
    from django.db.models import F, Q
    for addr in WalletDepositAddress.objects.filter(Q(last_update__gte=F('last_deposit_check')) | Q(needs_update=True), is_disabled=False):
        print(addr.address.ljust(42), '\t', str(addr.last_update_check).ljust(32), '\t', str(addr.last_update).ljust(32), '\t', addr.last_deposit_check)


# Registering Confirmers
confirmers[Currencies.btc] = confirm_bitcoin_deposits
confirmers[Currencies.ltc] = confirm_bitcoin_deposits
confirmers[Currencies.eth] = confirm_bitcoin_deposits
confirmers[Currencies.usdt] = confirm_bitcoin_deposits
confirmers[Currencies.bch] = confirm_bitcoin_deposits
confirmers[Currencies.etc] = confirm_bitcoin_deposits
confirmers[Currencies.trx] = confirm_bitcoin_deposits
confirmers[Currencies.doge] = confirm_bitcoin_deposits
confirmers[Currencies.uni] = confirm_bitcoin_deposits
confirmers[Currencies.aave] = confirm_bitcoin_deposits
confirmers[Currencies.link] = confirm_bitcoin_deposits
confirmers[Currencies.dai] = confirm_bitcoin_deposits
confirmers[Currencies.grt] = confirm_bitcoin_deposits
confirmers[Currencies.bnb] = confirm_bitcoin_deposits
confirmers[Currencies.dot] = confirm_bitcoin_deposits
confirmers[Currencies.ada] = confirm_bitcoin_deposits
confirmers[Currencies.shib] = confirm_bitcoin_deposits
confirmers[Currencies.ftm] = confirm_bitcoin_deposits
confirmers[Currencies.pol] = confirm_bitcoin_deposits
confirmers[Currencies.avax] = confirm_bitcoin_deposits
confirmers[Currencies.one] = confirm_bitcoin_deposits
confirmers[Currencies.sol] = confirm_bitcoin_deposits
confirmers[Currencies.near] = confirm_bitcoin_deposits
confirmers[Currencies.xmr] = confirm_bitcoin_deposits
confirmers[Currencies.algo] = confirm_bitcoin_deposits
confirmers[Currencies.flow] = confirm_bitcoin_deposits
confirmers[Currencies.fil] = confirm_bitcoin_deposits
confirmers[Currencies.apt] = confirm_bitcoin_deposits
confirmers[Currencies.egld] = confirm_bitcoin_deposits
confirmers[Currencies.arb] = confirm_bitcoin_deposits
confirmers[Currencies.xtz] = confirm_bitcoin_deposits
confirmers[Currencies.enj] = confirm_bitcoin_deposits
confirmers[Currencies.s] = confirm_bitcoin_deposits
confirmers[Currencies.xrp] = confirm_tagged_deposits

# Add support for all token currencies
token_currencies = (
    BEP20_contract_info['mainnet'].keys()
    | ERC20_contract_info['mainnet'].keys()
    | TRC20_contract_info['mainnet'].keys()
    | arbitrum_ERC20_contract_info['mainnet'].keys()
    | sol_contract_info["mainnet"].keys()
    | BASE_ERC20_contract_info["mainnet"].keys()
)
for currency in token_currencies & set(ALL_CRYPTO_CURRENCIES):
    if currency not in confirmers:
        confirmers[currency] = confirm_bitcoin_deposits
