import datetime
from decimal import Decimal

from django.db.models import Q
from django.utils.timezone import now

from exchange.accounts.models import Notification
from exchange.base.logging import report_event
from exchange.base.models import Settings, ALL_CRYPTO_CURRENCIES, TAG_NEEDED_CURRENCIES, Currencies, get_currency_codename
from exchange.base.money import money_is_close_decimal
from exchange.base.tasks import run_admin_task
from exchange.blockchain.explorer import BlockchainExplorer
from exchange.blockchain.models import CurrenciesNetworkName
from exchange.wallet.deposit import tag_coins_addresses
from exchange.wallet.models import ConfirmedWalletDeposit


class DepositDiffChecker:
    currencies = ALL_CRYPTO_CURRENCIES
    excluded_currencies = [Currencies.pmn]
    excluded_networks = ['BTCLN', CurrenciesNetworkName.ZTRX]
    latest_deposit_checked_cache_key = 'latest_deposit_diff_checked'
    recheck_deposit_limit = 300

    @classmethod
    def recheck_confirmed_deposits(
        cls,
        currencies=None,
        networks=None,
        excluded_currencies=None,
        excluded_networks=None,
        cache_key=None,
        recheck_deposit_limit=None,
    ):
        """Recheck all deposits after cache with other explorer"""
        if currencies is None:
            currencies = cls.currencies
        if excluded_currencies is None:
            excluded_currencies = cls.excluded_currencies
        if excluded_networks is None:
            excluded_networks = cls.excluded_networks
        if cache_key is None:
            cache_key = cls.latest_deposit_checked_cache_key
        if not recheck_deposit_limit:
            recheck_deposit_limit = cls.recheck_deposit_limit


        # for tag coins ConfirmedWalletDeposit object has no address
        destination_filter = Q(address__isnull=False) | Q(tag__isnull=False, _wallet__currency__in=TAG_NEEDED_CURRENCIES)

        to_recheck_deposits = ConfirmedWalletDeposit.objects.filter(
            destination_filter,
            created_at__gt=now() - datetime.timedelta(days=1),
            confirmed=True,
            rechecked=False,
            _wallet__currency__in=currencies,
        ).exclude(
            Q(tx_hash__startswith='nobitex-internal') |
            Q(_wallet__currency__in=excluded_currencies) |
            Q(address__network__in=excluded_networks),
        ).select_related('tag')

        if networks:
            to_recheck_deposits = to_recheck_deposits.filter(address__network__in=networks)

        recheck_deposits = list(to_recheck_deposits.order_by('id')[:recheck_deposit_limit])
        if not recheck_deposits:
            print('[DepositDiff] No deposit found')
            return
        txs_data = [
            {
                'hash': deposit.tx_hash,
                'address': deposit.address.address if deposit.address else tag_coins_addresses(deposit.currency),
                'network': deposit.network,
                'currency': deposit.currency,
                'memo': deposit.tag.tag if deposit.tag else None,
            }
            for deposit in recheck_deposits
        ]
        print(txs_data)
        txs_details = BlockchainExplorer.get_transactions_values_by_address(txs_data)
        if len(txs_details) != len(txs_data):
            report_event("[DepositDiff] Length of input and output not equal in get transactions details")
            return

        for index, tx_details in enumerate(txs_details):
            deposit = recheck_deposits[index]
            value = tx_details.get('value', Decimal('0'))
            details = tx_details.get('details')
            addr = deposit.address.address if deposit.address else tx_details.get('address')
            if deposit.contract_address:
                value -= Decimal(Settings.get(f'deposit_fee_{get_currency_codename(deposit.currency)}_{deposit.network.lower()}_{deposit.contract_address}', '0'))
            if not details:
                report_event("[DepositDiff] Error in getting tx details")
                continue

            tx_details_memo = str(tx_details.get('memo')).strip()
            # check if memo includes persian numerics, convert it to Latin
            if tx_details_memo.isnumeric():
                try:
                    tx_details_memo = str(int(tx_details_memo))
                except:
                    continue
            channel_name = 'important_ton' if deposit.network == 'TON' else 'important'
            if deposit.tag and str(deposit.tag.tag).strip() != tx_details_memo:
                message = f'*Deposit ID:* {deposit.id}\n'\
                          f'*Currency:* {get_currency_codename(deposit.currency)}\n'\
                          f'*Network:* {deposit.network}\n*Hash*: {deposit.tx_hash}\n'\
                          f'*Debug Parameters:*\n\t*Amount in System:* {deposit.amount}\n'\
                          f'\t*Amount in Network:* {value}\n\t*Address:* {addr}\n'\
                          f'\t*Details:* Tag Incompatibility!'
                title = '❌️ اختلاف در سیستم واریز'
                Notification.notify_admins(
                    message=message,
                    title=title,
                    channel=channel_name
                )
                run_admin_task(
                    'admin.add_notification_log',
                    channel=channel_name,
                    message=message,
                    title=title)
                run_admin_task('admin.add_deposit_diff', deposit_id=deposit.id, network_amount=value, address=addr)
                continue
            elif not money_is_close_decimal(value, deposit.amount, decimals=8):
                message = f'*Deposit ID:* {deposit.id}\n'\
                          f'*Currency:* {get_currency_codename(deposit.currency)}\n'\
                          f'*Network:* {deposit.network}\n*Hash*: {deposit.tx_hash}\n'\
                          f'*Debug Parameters:*\n\t*Amount in System:* {deposit.amount}\n'\
                          f'\t*Amount in Network:* {value}\n\t*Address:* {addr}\n'\
                          f'\t*Details:* {details}'
                title = '❌️ اختلاف در سیستم واریز'
                Notification.notify_admins(
                    message=message,
                    title=title,
                    channel=channel_name
                )
                run_admin_task(
                    'admin.add_notification_log',
                    channel=channel_name,
                    message=message,
                    title=title)
                run_admin_task('admin.add_deposit_diff', deposit_id=deposit.id, network_amount=value, address=addr)
                continue

            deposit.rechecked = True
            deposit.save(update_fields=['rechecked'])
