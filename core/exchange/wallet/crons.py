import datetime
from abc import ABC, abstractmethod
from collections import defaultdict
from decimal import Decimal
from typing import Dict, List, Optional, Set, Tuple

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, DecimalField, F, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.utils.timezone import now

from exchange.accounts.models import Notification
from exchange.base.calendar import ir_now
from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.crons import CronJob, Schedule
from exchange.base.models import Currencies, Settings, get_currency_codename
from exchange.base.tasks import run_admin_task
from exchange.blockchain.api.exchange.binance import BinancePublicAPI
from exchange.blockchain.contracts_conf import (
    BASE_ERC20_contract_info,
    TRC20_contract_info,
    arbitrum_ERC20_contract_info,
    sol_contract_info,
)
from exchange.blockchain.explorer import BlockchainExplorer
from exchange.blockchain.models import CurrenciesNetworkName
from exchange.margin.models import Position
from exchange.wallet.balancechecker import BalanceChecker
from exchange.wallet.block_processing import NobitexBlockProcessing
from exchange.wallet.deposit import (
    confirm_tagged_deposits,
    refresh_address_deposits,
    update_address_balances_for_currency,
    update_deposits,
)
from exchange.wallet.deposit_diff import DepositDiffChecker
from exchange.wallet.models import (
    ConfirmedWalletDeposit,
    TransactionHistoryFile,
    Wallet,
    WalletDepositAddress,
    WithdrawRequest,
)
from exchange.wallet.withdraw_diff import to_done_tagged_withdraws


class UpdateDepositsCron(CronJob):
    schedule = Schedule(run_every_mins=settings.ADMIN_OPTIONS['updateDepositCronIntervalMinutes'])
    code = 'update_deposits'

    def run(self):
        deposit_processing_mode = Settings.get('module_deposit_processing', default='enabled')
        if deposit_processing_mode in ['disabled', 'onrequest']:
            return
        # Full Scan Modes
        n = now()
        full_mode = n.hour in [7, 23] and n.minute <= 30
        if deposit_processing_mode != 'enabled':
            full_mode = False
        update_deposits()


class UpdateNeededUpdatesCron(CronJob):
    schedule = Schedule(run_every_mins=1)
    code = 'update_needed_update_deposits'

    def run(self):
        if Settings.get('module_deposit_processing') == 'disabled':
            return

        # Check deposits for wallets with updated balances
        # TODO: CHECK DEPOSITS FOR HOT WALLETS!
        count_deposit_check = 0
        updated_addresses_qs = WalletDepositAddress.objects.filter(
            Q(last_update__gt=F('last_deposit_check')) | Q(needs_update=True),
            is_disabled=False,
        )
        updated_addresses = updated_addresses_qs.select_related('wallet')
        # Process deposits
        print('Refreshing {} queued addresses...'.format(len(updated_addresses)))
        addresses_to_check_balance = {}
        deposit_recheck_threshold = now() - datetime.timedelta(minutes=30)
        deposit_status = {}
        for address in updated_addresses:
            # We check tag-required currencies separately in the end of this cron
            network = address.get_network()
            if address.wallet.is_address_tag_required(network):
                continue
            # Check if deposit is enabled
            currency_name = get_currency_codename(address.currency)
            if currency_name in deposit_status and network in deposit_status[currency_name]:
                if not deposit_status[currency_name][network]:
                    continue
            else:
                if currency_name not in deposit_status:
                    deposit_status[currency_name] = {}
                default_value = 'no'
                try:
                    if CURRENCY_INFO[address.currency]['network_list'][network].get('deposit_enable', True):
                        default_value = 'yes'
                except KeyError:
                    pass
                deposit_status[currency_name][network] = Settings.get_trio_flag(
                    f'deposit_enabled_{currency_name}_{network.lower()}',
                    default=default_value,  # all network in network_list filter by withdraw_enable=True
                    third_option_value=cache.get(f'binance_deposit_status_{currency_name}_{network}'),
                )
            # Validate user update requests by checking if there is any balance change for the user's address
            is_really_updated = address.last_update and (
                    not address.last_deposit_check or address.last_update > address.last_deposit_check)
            # User has requested deposit check, so if the last deposit check is older than 30 minutes ago,
            #  it is better to acknowledge user request and do the deposit check although we think it is
            #  not required because of no balance change
            if not address.last_deposit_check or address.last_deposit_check < deposit_recheck_threshold:
                is_really_updated = True
            if is_really_updated:
                count_deposit_check += 1
                refresh_address_deposits(address, retry=True)
            else:
                addresses_to_check_balance.setdefault(address.currency, [])
                addresses_to_check_balance[address.currency].append(address)
        # Clear not updated user requested queue items
        WalletDepositAddress.objects.filter(
            Q(last_update__isnull=True) | Q(last_update__lte=F('last_deposit_check')),
            needs_update=True,
        ).update(needs_update=False)

        # Check balance update for user requests
        count_balance_update = 0
        for address_list in addresses_to_check_balance.values():
            count_balance_update += len(address_list)
            update_address_balances_for_currency(address_list, sleep=0)
        print('Checked balance for {} addresses, check deposits for {}'.format(count_balance_update, count_deposit_check))


class UpdatePendingDepositsCron(CronJob, ABC):
    schedule = Schedule(run_every_mins=3)
    code = 'update_pending_deposits'
    currencies: Optional[List] = None
    excluded_currencies: Optional[List] = None
    networks: Optional[List] = None
    excluded_networks: Optional[List] = None

    def unconfirmed_deposit_list(self):
        deposit_filter = Q(confirmed=False) | Q(validated=False)
        if self.currencies:
            deposit_filter = deposit_filter & Q(address__currency__in=self.currencies)
        if self.networks:
            deposit_filter = deposit_filter & Q(address__network__in=self.networks)
        unconfirmed_deposit = ConfirmedWalletDeposit.objects.filter(
            deposit_filter,
            created_at__gt=now() - datetime.timedelta(hours=3 if self.networks == ['DOGE'] else 12),
            address__isnull=False,
        )
        if self.excluded_currencies:
            unconfirmed_deposit = unconfirmed_deposit.exclude(Q(address__currency__in=self.excluded_currencies))
        if self.excluded_networks:
            unconfirmed_deposit = unconfirmed_deposit.exclude(Q(address__network__in=self.excluded_networks))
        return unconfirmed_deposit.select_related('_wallet', 'address')

    def run(self):
        if Settings.get('module_deposit_processing') == 'disabled':
            return
        count_deposit_check = 0
        # Process unconfirmed deposits
        unconfirmed_deposits = self.unconfirmed_deposit_list()
        deposit_status = {}
        for deposit in unconfirmed_deposits:
            # Check if deposit is enabled
            deposit_currency = deposit.wallet.currency
            deposit_network = deposit.address.get_network()
            contract_address = deposit.address.contract_address
            currency_name = get_currency_codename(deposit_currency)
            if currency_name in deposit_status:
                if not deposit_status.get(currency_name):
                    continue
            else:
                default_value = 'no'
                try:
                    if CURRENCY_INFO[deposit_currency]['network_list'][deposit_network].get('deposit_enable', True):
                        default_value = 'yes'
                except KeyError:
                    pass
                deposit_cache_key = f'deposit_enabled_{currency_name}_{deposit_network.lower()}'
                if contract_address:
                    deposit_cache_key += f'_{contract_address}'
                deposit_status[currency_name] = Settings.get_trio_flag(
                    deposit_cache_key,
                    default=default_value,  # all network in network_list filter by withdraw_enable=True
                    third_option_value=cache.get(f'binance_deposit_status_{currency_name}_{deposit_network}'),
                )
            count_deposit_check += 1
            refresh_address_deposits(deposit.address, retry=True)

        print('Check deposits for {}'.format(count_deposit_check))


class UpdateOtherPendingDepositCron(UpdatePendingDepositsCron):
    schedule = Schedule(run_every_mins=1)
    code = 'update_other_pending_deposits'
    excluded_networks = [
        CurrenciesNetworkName.BTC, CurrenciesNetworkName.TRX, CurrenciesNetworkName.LTC,
        CurrenciesNetworkName.BCH, CurrenciesNetworkName.DOGE, CurrenciesNetworkName.BSC
    ]


class UpdateBtcPendingDepositCron(UpdatePendingDepositsCron):
    schedule = Schedule(run_every_mins=3)
    code = 'update_btc_pending_deposits'
    networks = [CurrenciesNetworkName.BTC]


class UpdateTrxPendingDepositCron(UpdatePendingDepositsCron):
    schedule = Schedule(run_every_mins=3)
    code = 'update_trx_pending_deposits'
    networks = [CurrenciesNetworkName.TRX]


class UpdateLtcPendingDepositCron(UpdatePendingDepositsCron):
    schedule = Schedule(run_every_mins=3)
    code = 'update_ltc_pending_deposits'
    networks = [CurrenciesNetworkName.LTC]


class UpdateBchPendingDepositCron(UpdatePendingDepositsCron):
    schedule = Schedule(run_every_mins=3)
    code = 'update_bch_pending_deposits'
    networks = [CurrenciesNetworkName.BCH]


class UpdateDogePendingDepositCron(UpdatePendingDepositsCron):
    schedule = Schedule(run_every_mins=3)
    code = 'update_doge_pending_deposits'
    networks = [CurrenciesNetworkName.DOGE]


class UpdateBscPendingDepositCron(UpdatePendingDepositsCron):
    schedule = Schedule(run_every_mins=3)
    code = 'update_bsc_pending_deposits'
    networks = [CurrenciesNetworkName.BSC]


class UpdateTagDepositsCron(CronJob):
    schedule = Schedule(run_every_mins=1)
    code = 'update_tag_deposits'

    @classmethod
    def run(cls):
        if Settings.get('module_deposit_processing') == 'disabled':
            return

        # Check tagged Currencies
        cls.run_for_tagged_currencies()

    @classmethod
    def run_for_tagged_currencies(cls):
        confirm_tagged_deposits()
        if settings.ENABLE_HOT_WALLET_DIFF:
            to_done_tagged_withdraws([Currencies.eos, Currencies.xrp, Currencies.bnb, Currencies.xlm, Currencies.atom, Currencies.hbar, ])


class CheckWithdrawRequestsCron(CronJob):
    schedule = Schedule(run_every_mins=30)
    code = 'check_withdraw_requests'

    def run(self):
        print('[CRON] check_withdraw_requests')
        nw = ir_now()
        quarter_ago = nw - datetime.timedelta(minutes=15)
        day_ago = nw - datetime.timedelta(days=1)
        suspended_withdraws = WithdrawRequest.objects.filter(
            status__in=WithdrawRequest.STATUSES_PENDING,
            created_at__range=[day_ago, quarter_ago],
        ).exclude(
            status=WithdrawRequest.STATUS.waiting,  # Pending requests that are in waiting state are OK
        ).values('wallet__currency', 'network').order_by('wallet__currency', 'network').annotate(count=Count('wallet__currency'))

        # Rial suspended withdraws are checked only at specific hours
        if nw.hour not in [14, 22]:
            suspended_withdraws = suspended_withdraws.exclude(wallet__currency=Currencies.rls)
        if not suspended_withdraws.exists():
            return

        notif_title = '❌️ *درخواست برداشت معوق*'
        msg = ''
        for sw in suspended_withdraws:
            msg += '*{}:{}* {}\n'.format(Currencies[sw['wallet__currency']], sw['network'], sw['count'])
        Notification.notify_admins(msg, title=notif_title, channel='critical')
        Notification.notify_admins(msg, title=notif_title, channel='operation')


class CheckWithdrawDiffStatusCron(CronJob):
    schedule = Schedule(run_every_mins=30)
    code = 'check_withdraw_diff_status'
    ignore_currencies = [Currencies.pmn, Currencies.rls]
    ignore_networks = ['BTCLN']

    def run(self):
        print('[CRON] check_withdraw_diff_status')
        nw = ir_now()
        quarter_ago = nw - datetime.timedelta(minutes=15)
        day_ago = nw - datetime.timedelta(days=1)
        suspended_withdraws_diff = WithdrawRequest.objects.filter(
            status=WithdrawRequest.STATUS.sent,
            created_at__range=[day_ago, quarter_ago],
        ).exclude(
            wallet__currency__in=self.ignore_currencies
        ).exclude(
            network__in=self.ignore_networks
        ).values('wallet__currency', 'network').order_by('wallet__currency', 'network').annotate(count=Count('wallet__currency'))

        if not suspended_withdraws_diff.exists():
            return

        notif_title = '❌️ *درخواست برداشت چک نشده*'
        msg = ''
        for sw in suspended_withdraws_diff:
            msg += '*{}:{}* {}\n'.format(Currencies[sw['wallet__currency']], sw['network'], sw['count'])
        Notification.notify_admins(msg, title=notif_title, channel='important')
        run_admin_task('admin.add_notification_log',
                       channel='important',
                       message=msg,
                       title=notif_title)


class CheckDepositDiffStatusCron(CronJob):
    schedule = Schedule(run_every_mins=30)
    code = 'check_deposit_diff_status'
    ignore_currencies = [Currencies.pmn, Currencies.rls]
    ignore_networks = ['BTCLN', 'ZTRX']

    def run(self):
        print('[CRON] check_deposit_diff_status')
        nw = ir_now()
        quarter_ago = nw - datetime.timedelta(minutes=15)
        day_ago = nw - datetime.timedelta(days=1)
        suspended_deposits_diff = ConfirmedWalletDeposit.objects.filter(
            confirmed=True,
            rechecked=False,
            created_at__range=[day_ago, quarter_ago],
        ).exclude(
            tx_hash__startswith='nobitex-internal'
        ).exclude(
            _wallet__currency__in=self.ignore_currencies
        ).exclude(
            address__network__in=self.ignore_networks
        ).values('_wallet__currency', 'address__network').order_by('_wallet__currency').annotate(count=Count('_wallet__currency'))

        if not suspended_deposits_diff.exists():
            return

        notif_title = '❌️ *درخواست واریز چک نشده*'
        msg = ''
        for sdd in suspended_deposits_diff:
            msg += f"*({Currencies[sdd['_wallet__currency']]}, {sdd['address__network']}):* {sdd['count']}\n"
        Notification.notify_admins(msg, title=notif_title, channel='important')
        run_admin_task('admin.add_notification_log',
                       channel='important',
                       message=msg,
                       title=notif_title)


class BalanceCheckerCron(CronJob):
    """ Cron class to update system hot wallet balances, including Binance and blockchain wallets
    """
    schedule = Schedule(run_at_times=[
        '{}:58'.format(str(i).zfill(2)) for i in range(24)
    ] if settings.IS_PROD else ['11:58', '23:58'])
    code = 'balance_checker'

    def run(self):
        print('[CRON] Balance checker...')
        BalanceChecker.update_system_wallets_balance()


class MarginBlockedBalanceCheckerCron(CronJob):
    """Check blocked balances of margin wallets

    Double check for block/unblock methods consistency in positions
    """
    schedule = Schedule(run_at_times=('03:30',))
    code = 'margin_blocked_balance_checker'

    def run(self):
        margin_positions = Position.objects.filter(
            dst_currency=OuterRef('currency'),
            user_id=OuterRef('user_id'),
            pnl__isnull=True,
        )

        margin_wallets = (
            Wallet.objects.filter(type=Wallet.WALLET_TYPE.margin)
            .annotate(
                collateral=Coalesce(
                    Subquery(
                        margin_positions.values('user_id', 'dst_currency')
                        .annotate(total=Sum('collateral'))
                        .values('total')
                    ),
                    Value(Decimal('0')),
                    output_field=DecimalField(),
                )
            )
            .annotate(blocked_balance_diff=F('balance_blocked') - F('collateral'))
            .exclude(blocked_balance_diff=Decimal('0'))
        )

        for wallet in margin_wallets:
            Notification.notify_admins(
                f'Wallet: #{wallet.id}\n'
                f'Diff: {float(wallet.blocked_balance_diff):+g} {wallet.get_currency_display()}',
                title='‼ Margin Wallet Inconsistency',
                channel='pool',
            )


class UpdateBlockCron(NobitexBlockProcessing, CronJob, ABC):
    """
        Purpose: Update deposits + withdraws (depends)
        Approach: each child class implements an inspector which is in the main file of coin (like trx.py) from that
        inspector get_latest_block_addresses method will be called which calls an api from exchange/blockchain/apis
        directory
    """
    schedule = Schedule(run_every_mins=10)
    code = 'update_block_deposits'
    network_symbol = None

    @property
    @abstractmethod
    def inspector(self):
        raise NotImplementedError("Inspector property not implemented")

    @property
    @abstractmethod
    def currency(self):
        raise NotImplementedError("Currency property not implemented")

    @property
    @abstractmethod
    def network(self):
        raise NotImplementedError("Currency property not implemented")

    @property
    def currencies(self):
        return [self.currency]

    def get_deposits_addresses(self):
        return set(
            WalletDepositAddress.objects.using(self.READ_DB)
            .filter(Q(currency=self.currency), is_disabled=False)
            .values_list('address', flat=True)
        )

    def get_blocks_info(self, include_inputs=False, include_info=True):
        return self.inspector.get_latest_block_addresses(include_inputs=include_inputs, include_info=include_info)

    # TODO Replace output of function with DTO to prevent confusion
    @classmethod
    def decode_transactions_info_into_address_and_hash_pair(cls, transactions_info: Dict) -> Tuple:
        """Decode transaction information to identify address and transaction hash relationships.

        This method parses a dictionary containing incoming and outgoing transactions,
        maps them to their respective addresses and transaction hashes, and identifies
        transactions where there is a common transaction hash appearing both as an
        incoming and outgoing transaction.

        Specifically, it produces a tuple of triples in the form `(source_address, destination_address, tx_hash)`
        representing the pairs of addresses associated with the same transaction hash.
        """
        incoming_txs, outgoing_txs = transactions_info['incoming_txs'], transactions_info['outgoing_txs']
        hash_to_source_address_map = defaultdict(set)
        for addr, addr_txs in outgoing_txs.items():
            for currency, txs_list in addr_txs.items():
                for tx in txs_list:
                    hash_to_source_address_map[tx['tx_hash']].add(addr)

        hash_to_destination_address_map = defaultdict(set)
        for addr, addr_txs in incoming_txs.items():
            for currency, txs_list in addr_txs.items():
                for tx in txs_list:
                    hash_to_destination_address_map[tx['tx_hash']].add(addr)

        # Find common tx_hashes
        common_tx_hashes = hash_to_source_address_map.keys() & hash_to_destination_address_map.keys()

        # Create triples (incoming_address, outgoing_address, tx_hash)
        pairs = set()
        for tx_hash in common_tx_hashes:
            for in_addr in hash_to_source_address_map[tx_hash]:
                for out_addr in hash_to_destination_address_map[tx_hash]:
                    pairs.add((in_addr, out_addr, tx_hash))
        return tuple(pairs)

    # TODO Replace output of function with DTO to prevent confusion
    @classmethod
    def determine_updated_deposit_addresses_and_txs_info(
        cls, addresses_pairs: Tuple, transactions_info: Dict, deposit_addresses: Set[str]
    ) -> Tuple[Set, Dict]:
        """Determine which deposit addresses need updating and filter transaction info accordingly.

        This method takes pairs of addresses and associated transaction hashes, along with
        a set of known deposit addresses, and uses them to determine:
          1. Which addresses require an update (those that appear as outgoing addresses
             in the pairs but source address in pair(pair[0]) are not in `deposit_addresses`).
          2. Which transactions should be filtered out based on the presence of known
             deposit addresses. Any transaction hash that is associated with a deposit
             address (as an incoming address) will be excluded from the transaction info.

        Args:
            addresses_pairs (tuple): A tuple of `(source_address, destination_address, tx_hash)` triples.
            transactions_info (dict): A dictionary containing incoming and outgoing transactions,
                structured similarly to the input of `decode_transactions_info_into_address_and_hash_pair`.
            deposit_addresses (set[str]): A set of addresses expecting system deposit addresses.

        Returns:
            tuple[set, dict]: A tuple containing:
                - A set of addresses that should be updated based on the provided addresses pairs.
                - A modified `transactions_info` dict where transactions associated with
                  deposit addresses have been filtered out.
        """
        addresses_to_update = set()
        hashes_to_exclude = set()
        for pair in addresses_pairs:
            if (pair[0] not in deposit_addresses) and (pair[1] in deposit_addresses):
                addresses_to_update.add(pair[1])
            elif pair[0] in deposit_addresses:
                hashes_to_exclude.add(pair[2])

        for addr, block_dict in transactions_info.items():
            for currency, txs_list in block_dict.items():
                filtered_txs = [tx for tx in txs_list if tx['tx_hash'] not in hashes_to_exclude]
                block_dict[currency] = filtered_txs

        return addresses_to_update, transactions_info

    def run(self):
        blocks_info = self.get_blocks_info(include_inputs=True, include_info=True)
        if not blocks_info:
            return  # Special case of failure in inspector
        transactions_addresses, transactions_info, _ = blocks_info
        if transactions_addresses is None or transactions_addresses == set() or \
           transactions_addresses == {'input_addresses': set(), 'output_addresses': set()}:
            # addresses collection did not fill
            return

        deposit_addresses = self.get_deposits_addresses()
        # handle whole deposits stuff
        if isinstance(transactions_addresses, set):
            # result has the old form, so we can just handle deposits in the old way
            updated_deposit_addresses = deposit_addresses.intersection(transactions_addresses)
            print(f'[Block] Update these addresses: {updated_deposit_addresses}')
            self.updating_wallet(updated_addresses=updated_deposit_addresses,
                                 currencies=self.currencies,
                                 transactions_info=transactions_info,
                                 network=self.network)
            return
        else:
            # result has the new form, so based on that we handle deposits (by addresses appeared in the outputs)
            # TODO this 2 functions now completely depends on one another and they didn't follow SOC rule
            address_pairs = self.decode_transactions_info_into_address_and_hash_pair(transactions_info)
            updated_deposit_addresses, incoming_tx_info = self.determine_updated_deposit_addresses_and_txs_info(
                address_pairs, transactions_info['incoming_txs'], deposit_addresses
            )
            if self.network == 'XMR':
                updated_deposit_addresses = deposit_addresses.intersection(transactions_addresses['output_addresses'])
            print(f'[Block] Update these addresses: {updated_deposit_addresses}')
            self.updating_wallet(
                updated_addresses=updated_deposit_addresses,
                currencies=self.currencies,
                transactions_info=incoming_tx_info,
                network=self.network,
            )

        if not settings.ENABLE_HOT_WALLET_DIFF:
            return

        # handle whole withdraws stuff (only when 1: output result of each coin file is appropriate (we can)
        #                                         2: flag has been set in settings (we want))
        hot_wallet_addresses = self.get_hot_wallet_addresses()
        updated_hot_wallet_addresses = hot_wallet_addresses.intersection(
            set(map(lambda a: a.lower(), transactions_addresses['input_addresses']))
        )
        if updated_hot_wallet_addresses:
            print(f'[Block] Update these hot wallet addresses: {updated_hot_wallet_addresses}')
        self.update_withdraw_status(updated_hot_wallet_addresses=updated_hot_wallet_addresses,
                                    transactions_info=transactions_info['outgoing_txs'])


class UpdateBitcoinCashDepositsCron(UpdateBlockCron):
    schedule = Schedule(run_every_mins=1)
    code = 'update_bitcoin_cash_deposits'
    inspector = None
    currency = Currencies.bch
    network = CurrenciesNetworkName.BCH
    network_symbol = 'BCH'

    def get_blocks_info(self, include_inputs=False, include_info=True):
        return BlockchainExplorer.get_latest_block_addresses(network=self.network, include_inputs=include_inputs, include_info=include_info)


class UpdateTronDepositsCron(UpdateBlockCron):
    schedule = Schedule(run_every_mins=1)
    code = 'update_tron_deposits'
    inspector = None
    currency = Currencies.trx
    currencies = [Currencies.trx] + list(TRC20_contract_info['mainnet'].keys())
    network = CurrenciesNetworkName.TRX
    network_symbol = 'TRX'

    def get_blocks_info(self, include_inputs=False, include_info=True):
        return BlockchainExplorer.get_latest_block_addresses(network=self.network, include_inputs=include_inputs, include_info=include_info)


class UpdateBitcoinDepositsCron(UpdateBlockCron):
    schedule = Schedule(run_every_mins=1)
    code = 'update_btc_deposits'
    inspector = None
    currency = Currencies.btc
    network = CurrenciesNetworkName.BTC
    network_symbol = 'BTC'

    def get_blocks_info(self, include_inputs=False, include_info=True):
        return BlockchainExplorer.get_latest_block_addresses(network=self.network, include_inputs=include_inputs, include_info=include_info)


class UpdateDogecoinDepositsCron(UpdateBlockCron):
    schedule = Schedule(run_every_mins=1)
    code = 'update_doge_deposits'
    inspector = None
    currency = Currencies.doge
    network = CurrenciesNetworkName.DOGE
    network_symbol = 'DOGE'

    def get_blocks_info(self, include_inputs=False, include_info=True):
        return BlockchainExplorer.get_latest_block_addresses(network=self.network, include_inputs=include_inputs, include_info=include_info)


class UpdateLitecoinDepositsCron(UpdateBlockCron):
    schedule = Schedule(run_every_mins=1)
    code = 'update_ltc_deposits'
    inspector = None
    currency = Currencies.ltc
    network = CurrenciesNetworkName.LTC
    network_symbol = 'LTC'

    def get_blocks_info(self, include_inputs=False, include_info=True):
        return BlockchainExplorer.get_latest_block_addresses(network=self.network, include_inputs=include_inputs, include_info=include_info)


class UpdateAdaDepositsCron(UpdateBlockCron):
    schedule = Schedule(run_every_mins=2)
    code = 'update_ada_deposits'
    inspector = None
    currency = Currencies.ada
    network = CurrenciesNetworkName.ADA
    network_symbol = 'ADA'

    def get_blocks_info(self, include_inputs=False, include_info=True):
        return BlockchainExplorer.get_latest_block_addresses(network=self.network, include_inputs=include_inputs, include_info=include_info)


class UpdateMoneroDepositCron(UpdateBlockCron):
    schedule = Schedule(run_every_mins=2)
    code = 'update_xmr_deposits'
    inspector = None
    currency = Currencies.xmr
    network = CurrenciesNetworkName.XMR
    network_symbol = 'XMR'

    def get_blocks_info(self, include_inputs=False, include_info=True):
        return BlockchainExplorer.get_latest_block_addresses(network=self.network, include_inputs=include_inputs, include_info=include_info)


class UpdateAlgoDepositCron(UpdateBlockCron):
    schedule = Schedule(run_every_mins=1)
    code = 'update_algo_deposits'
    inspector = None
    currency = Currencies.algo
    network = CurrenciesNetworkName.ALGO
    network_symbol = 'ALGO'

    def get_blocks_info(self, include_inputs=False, include_info=True):
        return BlockchainExplorer.get_latest_block_addresses(network=self.network, include_inputs=include_inputs, include_info=include_info)


class UpdateFlowDepositCron(UpdateBlockCron):
    schedule = Schedule(run_every_mins=1)
    code = 'update_flow_deposits'
    inspector = None
    currency = Currencies.flow
    network = CurrenciesNetworkName.FLOW
    network_symbol = 'FLOW'

    def get_blocks_info(self, include_inputs=False, include_info=True):
        return BlockchainExplorer.get_latest_block_addresses(network=self.network, include_inputs=include_inputs, include_info=include_info)


class UpdateFilecoinDepositCron(UpdateBlockCron):
    schedule = Schedule(run_every_mins=1)
    code = 'update_fil_deposits'
    inspector = None
    currency = Currencies.fil
    network = CurrenciesNetworkName.FIL
    network_symbol = 'FIL'

    def get_blocks_info(self, include_inputs=False, include_info=True):
        return BlockchainExplorer.get_latest_block_addresses(network=self.network, include_inputs=include_inputs, include_info=include_info)


class UpdateArbitrumDepositsCron(UpdateBlockCron):
    """
        This cron used for Arbitrum block processing custom service
    """
    schedule = Schedule(run_every_mins=1)
    code = 'update_arb_deposits'
    inspector = None
    currency = Currencies.eth
    currencies = [Currencies.eth] + list(arbitrum_ERC20_contract_info['mainnet'].keys())
    network = CurrenciesNetworkName.ARB
    network_symbol = 'ARB'

    def get_blocks_info(self, include_inputs=False, include_info=True):
        return BlockchainExplorer.get_latest_block_addresses(network=self.network, include_inputs=include_inputs, include_info=include_info)


class UpdateAptosDepositCron(UpdateBlockCron):
    schedule = Schedule(run_every_mins=1)
    code = 'update_apt_deposits'
    inspector = None
    currency = Currencies.apt
    network = CurrenciesNetworkName.APT
    network_symbol = 'APT'

    def get_blocks_info(self, include_inputs=False, include_info=True):
        return BlockchainExplorer.get_latest_block_addresses(network=self.network, include_inputs=include_inputs, include_info=include_info)


class UpdateElrondDepositCron(UpdateBlockCron):
    schedule = Schedule(run_every_mins=3)
    code = 'update_egld_deposits'
    currency = Currencies.egld
    inspector = None
    network = CurrenciesNetworkName.EGLD
    network_symbol = 'EGLD'

    def get_blocks_info(self, include_inputs=False, include_info=True):
        return BlockchainExplorer.get_latest_block_addresses(network=self.network, include_inputs=include_inputs, include_info=include_info)


class UpdateEnjinDepositCron(UpdateBlockCron):
    schedule = Schedule(run_every_mins=2)
    code = 'update_enj_deposits'
    currency = Currencies.enj
    inspector = None
    network = CurrenciesNetworkName.ENJ
    network_symbol = 'ENJ'

    def get_blocks_info(self, include_inputs=False, include_info=True):
        return BlockchainExplorer.get_latest_block_addresses(network=self.network, include_inputs=include_inputs, include_info=include_info)


class UpdateNearDepositCron(UpdateBlockCron):
    schedule = Schedule(run_every_mins=1)
    code = 'update_near_deposits'
    inspector = None
    currency = Currencies.near
    network = CurrenciesNetworkName.NEAR
    network_symbol = 'NEAR'

    def get_blocks_info(self, include_inputs=False, include_info=True):
        return BlockchainExplorer.get_latest_block_addresses(network=self.network, include_inputs=include_inputs, include_info=include_info)


class UpdateSolanaDepositsCron(UpdateBlockCron):
    """
        In essence this is not a real cron job, but it has the same goal, so it has too many commons with the
        other classes above. We will use this class for block processing like other coins.
        NOTE: DO NOT ADD THIS CLASS TO CRON_CLASSES IN settings.py
    """
    schedule = Schedule(run_every_mins=1)
    code = 'update_sol_deposits'
    inspector = None
    currency = Currencies.sol
    currencies = [Currencies.sol] + list(sol_contract_info["mainnet"].keys())
    network = CurrenciesNetworkName.SOL
    network_symbol = 'SOL'

    def get_blocks_info(self, include_inputs=False, include_info=True):
        return BlockchainExplorer.get_latest_block_addresses(network=self.network, include_inputs=include_inputs, include_info=include_info)


class UpdateTezosDepositCron(UpdateBlockCron):
    schedule = Schedule(run_every_mins=2)
    code = 'update_xtz_deposits'
    inspector = None
    currency = Currencies.xtz
    network = CurrenciesNetworkName.XTZ
    network_symbol = 'XTZ'

    def get_blocks_info(self, include_inputs=False, include_info=True):
        return BlockchainExplorer.get_latest_block_addresses(network=self.network, include_inputs=include_inputs, include_info=include_info)


class UpdatePolkadotDepositCron(UpdateBlockCron):
    schedule = Schedule(run_every_mins=2)
    code = 'update_dot_deposits'
    inspector = None
    currency = Currencies.dot
    network = CurrenciesNetworkName.DOT
    network_symbol = 'DOT'

    def get_blocks_info(self, include_inputs=False, include_info=True):
        return BlockchainExplorer.get_latest_block_addresses(network=self.network, include_inputs=include_inputs, include_info=include_info)


class UpdateSonicDepositCron(UpdateBlockCron):
    schedule = Schedule(run_every_mins=2)
    code = 'update_s_deposits'
    inspector = None
    currency = Currencies.s
    network = CurrenciesNetworkName.SONIC
    network_symbol = 'SONIC'

    def get_blocks_info(self, include_inputs=False, include_info=True):
        return BlockchainExplorer.get_latest_block_addresses(
            network=self.network, include_inputs=include_inputs, include_info=include_info
        )


class UpdateBaseDepositCron(UpdateBlockCron):
    schedule = Schedule(run_every_mins=1)
    code = 'update_base_deposits'
    inspector = None
    currency = Currencies.eth
    currencies = [Currencies.eth] + list(BASE_ERC20_contract_info['mainnet'].keys())
    network = CurrenciesNetworkName.BASE
    network_symbol = 'BASE'

    def get_blocks_info(self, include_inputs=False, include_info=True):
        return BlockchainExplorer.get_latest_block_addresses(
            network=self.network, include_inputs=include_inputs, include_info=include_info
        )


class CheckDepositDiff(CronJob, ABC):
    """ Cron class to double-check deposit in system
    """
    schedule = Schedule(run_every_mins=1)
    code = 'check_deposit_diff'
    currencies: Optional[List] = None
    excluded_currencies: Optional[List] = None
    excluded_networks: Optional[List] = None
    networks: Optional[List] = None
    cache_key: Optional[str] = None
    recheck_deposit_limit: Optional[int] = None

    def run(self):
        print('[CRON] Deposit diff ...')
        DepositDiffChecker.recheck_confirmed_deposits(
            currencies=self.currencies,
            networks=self.networks,
            excluded_currencies=self.excluded_currencies,
            excluded_networks=self.excluded_networks,
            cache_key=self.cache_key,
            recheck_deposit_limit=self.recheck_deposit_limit,
        )


class CheckDepositDiffOthers(CheckDepositDiff):
    """ Cron class to double-check deposit in system, for others coin instead excluded_networks
    """
    schedule = Schedule(run_every_mins=1)
    code = 'check_deposit_diff_others'
    excluded_networks = [
        'BTCLN',
        CurrenciesNetworkName.PMN,
        CurrenciesNetworkName.TRX,
        CurrenciesNetworkName.ZTRX,
        CurrenciesNetworkName.BTC,
        CurrenciesNetworkName.LTC,
        CurrenciesNetworkName.DOGE,
        CurrenciesNetworkName.BCH,
        CurrenciesNetworkName.MATIC,
        CurrenciesNetworkName.FTM,
        CurrenciesNetworkName.BSC,
        CurrenciesNetworkName.ETH,
        CurrenciesNetworkName.SOL,
        CurrenciesNetworkName.ADA,
        CurrenciesNetworkName.NEAR,
        CurrenciesNetworkName.AVAX,
        CurrenciesNetworkName.ALGO,
        CurrenciesNetworkName.ETC,
        CurrenciesNetworkName.TON,
        CurrenciesNetworkName.SONIC,
        CurrenciesNetworkName.BASE,
    ]

    cache_key = 'latest_deposit_diff_checked_others'


class CheckDepositDiffTrx(CheckDepositDiff):
    """ Cron class to double-check deposit in system, for TRX network
    """
    schedule = Schedule(run_every_mins=1)
    code = 'check_deposit_diff_trx'
    networks = [CurrenciesNetworkName.TRX]
    cache_key = 'latest_deposit_diff_checked_TRX'


class CheckDepositDiffTon(CheckDepositDiff):
    """ Cron class to double-check deposit in system, for TON network
    """
    schedule = Schedule(run_every_mins=1)
    code = 'check_deposit_diff_ton'
    networks = [CurrenciesNetworkName.TON]
    cache_key = 'latest_deposit_diff_checked_TON'


class CheckDepositDiffDoge(CheckDepositDiff):
    """ Cron class to double-check deposit in system, for DOGE network
    """
    schedule = Schedule(run_every_mins=1)
    code = 'check_deposit_diff_doge'
    networks = [CurrenciesNetworkName.DOGE]
    cache_key = 'latest_deposit_diff_checked_DOGE'


class CheckDepositDiffBtc(CheckDepositDiff):
    """ Cron class to double-check deposit in system, for BTC network
    """
    schedule = Schedule(run_every_mins=1)
    code = 'check_deposit_diff_btc'
    networks = [CurrenciesNetworkName.BTC]
    cache_key = 'latest_deposit_diff_checked_BTC'


class CheckDepositDiffLtc(CheckDepositDiff):
    """ Cron class to double-check deposit in system, for LTC network
    """
    schedule = Schedule(run_every_mins=1)
    code = 'check_deposit_diff_ltc'
    networks = [CurrenciesNetworkName.LTC]
    cache_key = 'latest_deposit_diff_checked_LTC'


class CheckDepositDiffBch(CheckDepositDiff):
    """ Cron class to double-check deposit in system, for BCH network
    """
    schedule = Schedule(run_every_mins=1)
    code = 'check_deposit_diff_bch'
    networks = [CurrenciesNetworkName.BCH]
    cache_key = 'latest_deposit_diff_checked_BCH'


class CheckDepositDiffMatic(CheckDepositDiff):
    """ Cron class to double-check deposit in system, for MATIC network
    """
    schedule = Schedule(run_every_mins=1)
    code = 'check_deposit_diff_matic'
    networks = [CurrenciesNetworkName.MATIC]
    cache_key = 'latest_deposit_diff_checked_MATIC'


class CheckDepositDiffFtm(CheckDepositDiff):
    """ Cron class to double-check deposit in system, for FTM network
    """
    schedule = Schedule(run_every_mins=1)
    code = 'check_deposit_diff_ftm'
    networks = [CurrenciesNetworkName.FTM]
    cache_key = 'latest_deposit_diff_checked_FTM'


class CheckDepositDiffBsc(CheckDepositDiff):
    """ Cron class to double-check deposit in system, for BSC network
    """
    schedule = Schedule(run_every_mins=1)
    code = 'check_deposit_diff_bsc'
    networks = [CurrenciesNetworkName.BSC]
    cache_key = 'latest_deposit_diff_checked_BSC'


class CheckDepositDiffEth(CheckDepositDiff):
    """ Cron class to double-check deposit in system, for ETH network
    """
    schedule = Schedule(run_every_mins=1)
    code = 'check_deposit_diff_eth'
    networks = [CurrenciesNetworkName.ETH]
    cache_key = 'latest_deposit_diff_checked_ETH'


class CheckDepositDiffSol(CheckDepositDiff):
    """ Cron class to double-check deposit in system, for SOL network
    """
    schedule = Schedule(run_every_mins=1)
    code = 'check_deposit_diff_sol'
    networks = [CurrenciesNetworkName.SOL]
    cache_key = 'latest_deposit_diff_checked_SOL'


class CheckDepositDiffAda(CheckDepositDiff):
    """ Cron class to double-check deposit in system, for ADA network
    """
    schedule = Schedule(run_every_mins=1)
    code = 'check_deposit_diff_ada'
    networks = [CurrenciesNetworkName.ADA]
    cache_key = 'latest_deposit_diff_checked_ADA'


class CheckDepositDiffNear(CheckDepositDiff):
    """ Cron class to double-check deposit in system, for NEAR network
    """
    schedule = Schedule(run_every_mins=1)
    code = 'check_deposit_diff_near'
    networks = [CurrenciesNetworkName.NEAR]
    cache_key = 'latest_deposit_diff_checked_NEAR'


class CheckDepositDiffAvax(CheckDepositDiff):
    """ Cron class to double-check deposit in system, for AVAX network
    """
    schedule = Schedule(run_every_mins=1)
    code = 'check_deposit_diff_avax'
    networks = [CurrenciesNetworkName.AVAX]
    cache_key = 'latest_deposit_diff_checked_AVAX'



class CheckDepositDiffAlgo(CheckDepositDiff):
    """ Cron class to double-check deposit in system, for ALGO network
    """
    schedule = Schedule(run_every_mins=1)
    code = 'check_deposit_diff_algo'
    networks = [CurrenciesNetworkName.ALGO]
    cache_key = 'latest_deposit_diff_checked_ALGO'


class CheckDepositDiffEtc(CheckDepositDiff):
    """ Cron class to double-check deposit in system, for ETC network
    """
    schedule = Schedule(run_every_mins=1)
    code = 'check_deposit_diff_etc'
    networks = [CurrenciesNetworkName.ETC]
    cache_key = 'latest_deposit_diff_checked_ETC'


class CheckDepositDiffBnb(CheckDepositDiff):
    """ Cron class to double-check deposit in system, for BNB network
    """
    schedule = Schedule(run_every_mins=1)
    code = 'check_deposit_diff_bnb'
    currencies = [Currencies.bnb]
    cache_key = 'latest_deposit_diff_checked_BNB'
    excluded_networks = [CurrenciesNetworkName.BSC]


class CheckDepositDiffAtom(CheckDepositDiff):
    """ Cron class to double-check deposit in system, for ATOM network
    """
    schedule = Schedule(run_every_mins=1)
    code = 'check_deposit_diff_atom'
    currencies = [Currencies.atom]
    cache_key = 'latest_deposit_diff_checked_ATOM'
    excluded_networks = [CurrenciesNetworkName.BSC]


class CheckDepositDiffXrp(CheckDepositDiff):
    """ Cron class to double-check deposit in system, for XRP network
    """
    schedule = Schedule(run_every_mins=1)
    code = 'check_deposit_diff_xrp'
    currencies = [Currencies.xrp]
    cache_key = 'latest_deposit_diff_checked_XRP'
    excluded_networks = [CurrenciesNetworkName.BSC]


class CheckDepositDiffSonic(CheckDepositDiff):
    """Cron class to double-check deposit in system, for SONIC network"""

    schedule = Schedule(run_every_mins=1)
    code = 'check_deposit_diff_s'
    currencies = [Currencies.s]
    cache_key = 'latest_deposit_diff_checked_S'

class CheckDepositDiffBase(CheckDepositDiff):
    """Cron class to double-check deposit in system, for BASE network"""

    schedule = Schedule(run_every_mins=1)
    code = 'check_deposit_diff_base'
    currencies = [Currencies.eth] + list(BASE_ERC20_contract_info['mainnet'].keys())
    cache_key = 'latest_deposit_diff_checked_BASE'


class CheckBinanceWithdrawDepositCron(CronJob):
    schedule = Schedule(run_every_mins=30)
    code = 'check_binance_withdraw_deposit'

    def run(self):
        currencies_info = BinancePublicAPI().get_available_coins_info()
        for (binance_currency_name, currency), currency_info in currencies_info.items():
            for network_info in currency_info['networkList']:
                network = CurrenciesNetworkName.binance_to_nobitex(network_info['network'])
                if network is not None and network in CURRENCY_INFO[currency]['network_list']:
                    currency_name = get_currency_codename(currency)
                    old_withdraw_status = cache.get(f'binance_withdraw_status_{currency_name}_{network}')
                    old_deposit_status = cache.get(f'binance_deposit_status_{currency_name}_{network}')
                    new_withdraw_status = network_info['withdrawEnable']
                    new_deposit_status = network_info['depositEnable']

                    if old_deposit_status is not None and new_deposit_status != old_deposit_status:
                        if not new_deposit_status:
                            notif_title = '❌️ *بسته شدن واریز در بایننس*'
                            msg = f'*{currency_name}:{network}* {network_info["depositDesc"]}\n'
                            Notification.notify_admins(msg, title=notif_title, channel='important')
                            run_admin_task('admin.add_notification_log',
                                           channel='important',
                                           message=msg,
                                           title=notif_title)
                        else:
                            notif_title = '❌️ *باز شدن واریز در بایننس*'
                            msg = f'*{currency_name}:{network}*\n'
                            Notification.notify_admins(msg, title=notif_title, channel='important')
                            run_admin_task('admin.add_notification_log',
                                           channel='important',
                                           message=msg,
                                           title=notif_title)

                    if old_withdraw_status is not None and new_withdraw_status != old_withdraw_status:
                        if not new_withdraw_status:
                            notif_title = '❌️ *بسته شدن برداشت در بایننس*'
                            msg = f'*{currency_name}:{network}* {network_info["withdrawDesc"]}\n'
                            Notification.notify_admins(msg, title=notif_title, channel='important')
                            run_admin_task('admin.add_notification_log',
                                           channel='important',
                                           message=msg,
                                           title=notif_title)
                        else:
                            notif_title = '❌️ *باز شدن برداشت در بایننس*'
                            msg = f'*{currency_name}:{network}*\n'
                            Notification.notify_admins(msg, title=notif_title, channel='important')
                            run_admin_task('admin.add_notification_log',
                                           channel='important',
                                           message=msg,
                                           title=notif_title)

                    cache.set(f'binance_withdraw_status_{currency_name}_{network}', new_withdraw_status)
                    cache.set(f'binance_deposit_status_{currency_name}_{network}', new_deposit_status)


class RemoveOldTransactionHistoriesCron(CronJob):
    schedule = Schedule(run_every_mins=30)
    code = 'remove_old_transaction_histories'

    def run(self):
        for transaction_history in TransactionHistoryFile.get_remove_candidates():
            transaction_history.delete()
